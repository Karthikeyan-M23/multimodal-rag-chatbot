import jwt
import pytest

from backend import database
from tests.conftest import auth_headers, register


SECRET = "test-secret-" + "x" * 32


def test_register_returns_token_and_user(client):
    response = register(client)
    assert response.status_code == 201
    assert response.json()["user"]["username"] == "alice"
    me = client.get("/api/auth/me", headers=auth_headers(response))
    assert me.json()["username"] == "alice"


def test_duplicate_username_is_case_insensitive(client):
    register(client, "Alice")
    assert register(client, "alice").status_code == 409


@pytest.mark.parametrize(
    "username,password",
    [("ab", "password123"), ("bad name!", "password123"),
     ("bob", "short"), ("bob", "x" * 73)],
)
def test_register_validation(client, username, password):
    assert register(client, username, password).status_code == 400


def test_password_is_hashed(client):
    register(client)
    stored = database.get_user_by_username("alice")["password_hash"]
    assert "password123" not in stored and stored.startswith("$2")


def test_login_success_and_failures(client):
    register(client)
    ok = client.post("/api/auth/login",
                     json={"username": "ALICE", "password": "password123"})
    assert ok.status_code == 200 and ok.json()["access_token"]

    wrong = client.post("/api/auth/login",
                        json={"username": "alice", "password": "wrongpass1"})
    unknown = client.post("/api/auth/login",
                          json={"username": "nobody", "password": "password123"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


@pytest.mark.parametrize(
    "method,path",
    [("get", "/api/auth/me"), ("post", "/api/chat"), ("post", "/api/chat/stream"),
     ("get", "/api/conversations"), ("get", "/api/conversations/abc"),
     ("patch", "/api/conversations/abc"), ("delete", "/api/conversations/abc"),
     ("get", "/api/sources"), ("post", "/api/sources"),
     ("delete", "/api/sources/abc"), ("post", "/api/sources/abc/retry"),
     ("get", "/api/sources/abc/link"), ("post", "/api/library/reindex"),
     ("get", "/api/settings"), ("put", "/api/settings"),
     ("post", "/api/settings/test")],
)
def test_protected_routes_require_login(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_health_is_public(client):
    assert client.get("/api/health").status_code == 200


def test_bad_forged_and_expired_tokens_rejected(client):
    user_id = register(client).json()["user"]["id"]

    def get(token):
        return client.get("/api/auth/me",
                          headers={"Authorization": f"Bearer {token}"})

    assert get("garbage").status_code == 401
    forged = jwt.encode({"sub": str(user_id)}, "other-secret-" + "y" * 32, algorithm="HS256")
    assert get(forged).status_code == 401
    expired = jwt.encode({"sub": str(user_id), "exp": 1}, SECRET, algorithm="HS256")
    assert get(expired).status_code == 401
    ghost = jwt.encode({"sub": "9999"}, SECRET, algorithm="HS256")
    assert get(ghost).status_code == 401


def test_file_token_is_not_a_session_token(client):
    user_id = register(client).json()["user"]["id"]
    file_token = jwt.encode({"sub": str(user_id), "file": "abc"}, SECRET, algorithm="HS256")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {file_token}"})
    assert response.status_code == 401
