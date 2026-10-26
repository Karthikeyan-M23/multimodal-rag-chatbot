"""
Protected websites (Basic / Windows sign-in) and TFS / Azure DevOps work
items, against local fake servers.
"""

import base64
import json
import socket
import sqlite3
import threading
import time

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from config import settings
from src.ingestion import http_auth, tfs_processor, web_processor
from src.ingestion.http_auth import AuthError, SignedInSession
from src.ingestion.tfs_processor import parse_tfs_url
from tests.test_library_api import chat, sources


USER, PASSWORD, PAT = "alice", "s3cret!", "pat-123"

seen = []

work_items = {
    101: {
        "System.Title": "Login fails on Safari",
        "System.WorkItemType": "Bug",
        "System.State": "Active",
        "System.TeamProject": "Payments",
        "System.AssignedTo": {"displayName": "Alice Example"},
        "Microsoft.VSTS.Common.Priority": 1,
        "Microsoft.VSTS.TCM.ReproSteps": "<div>Open the app in <b>Safari 17</b></div><div>Click Login: spinner never stops</div>",
        "System.ChangedDate": "2026-10-20T09:15:00Z",
    },
    102: {
        "System.Title": "Add export to CSV",
        "System.WorkItemType": "User Story",
        "System.State": "Closed",
        "System.TeamProject": "Payments",
        "System.Description": "<p>Finance needs monthly invoices as CSV.</p>",
        "Microsoft.VSTS.Common.AcceptanceCriteria": "<ul><li>Columns: date, amount, customer</li></ul>",
    },
}


def _basic(request) -> tuple[str, str] | None:
    header = request.headers.get("authorization", "")
    if not header.startswith("Basic "):
        return None
    user, _, password = base64.b64decode(header[6:]).decode().partition(":")
    return user, password


fake = FastAPI()


@fake.middleware("http")
async def record(request: Request, call_next):
    seen.append({"path": request.url.path, "host": request.url.hostname, "auth": request.headers.get("authorization")})
    return await call_next(request)


# ---------------- websites ----------------

@fake.get("/public")
def public():
    return HTMLResponse("<html><title>Public</title><body><p>Open content about otters.</p></body></html>")


@fake.get("/protected")
def protected(request: Request):
    if _basic(request) != (USER, PASSWORD):
        return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="intranet"'})
    return HTMLResponse("<html><title>Runbook</title><body><h1>Deploy</h1><p>Deploys freeze every Friday after 2pm.</p></body></html>")


@fake.get("/windows")
def windows():
    return Response(status_code=401, headers={"WWW-Authenticate": "Negotiate, NTLM"})


@fake.get("/login-form")
def login_form():
    return HTMLResponse('<html><body><form><input name="u"><input type="password" name="p"></form></body></html>')


@fake.get("/hop")
def hop(request: Request):
    # Redirect to the same server under a different host name.
    port = request.url.port
    return RedirectResponse(f"http://localhost:{port}/public", status_code=302)


# ---------------- TFS REST API ----------------

def _tfs_auth(request):
    credentials = _basic(request)
    return credentials is not None and credentials[1] == PAT


def _versioned(request, payload):
    if not _tfs_auth(request):
        return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="tfs"'})
    if request.query_params.get("api-version") in {"7.0", "6.0"}:
        return JSONResponse(
            {"message": "VS800071: The requested REST API version of 7.0 is out of range for this server."},
            status_code=400,
        )
    return JSONResponse(payload)


@fake.get("/tfs/DefaultCollection/_apis/connectionData")
def connection_data(request: Request):
    return _versioned(request, {"authenticatedUser": {"providerDisplayName": "Alice Example"}})


@fake.post("/tfs/DefaultCollection/{project}/_apis/wit/wiql")
async def wiql(project: str, request: Request):
    body = await request.json()
    assert "@Me" in body["query"] and "@project" in body["query"]
    return _versioned(request, {"workItems": [{"id": i} for i in sorted(work_items, reverse=True)]})


@fake.get("/tfs/DefaultCollection/_apis/wit/workitems")
def items(request: Request, ids: str):
    wanted = [int(i) for i in ids.split(",")]
    return _versioned(request, {"value": [{"id": i, "fields": work_items[i]} for i in wanted if i in work_items]})


@fake.get("/tfs/DefaultCollection/_apis/wit/workitems/{item_id}/updates")
def updates(item_id: int, request: Request):
    history = [] if item_id != 101 else [
        {"revisedBy": {"displayName": "Bob QA"},
         "fields": {"System.History": {"newValue": "<p>Also happens on iOS 18.</p>"},
                    "System.ChangedDate": {"newValue": "2026-10-21T10:00:00Z"}}},
    ]
    return _versioned(request, {"value": history})


@pytest.fixture(scope="module")
def server():

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    instance = uvicorn.Server(uvicorn.Config(fake, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=instance.run, daemon=True)
    thread.start()

    while not instance.started:
        time.sleep(0.05)

    yield f"http://127.0.0.1:{port}"

    instance.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def allow_local(monkeypatch):
    # The fake servers run on 127.0.0.1, which is private by default.
    monkeypatch.setattr(web_processor, "ALLOW_PRIVATE_URLS", True)
    seen.clear()


# ---------------- sign-in mechanics ----------------

def test_first_request_carries_no_password(server):
    session = SignedInSession(USER, PASSWORD, server)
    assert session.get(f"{server}/protected").status_code == 200
    protected_calls = [s for s in seen if s["path"] == "/protected"]
    assert protected_calls[0]["auth"] is None  # probe
    assert protected_calls[1]["auth"].startswith("Basic ")


def test_wrong_password_raises_clear_error(server):
    with pytest.raises(AuthError, match="Sign-in failed"):
        SignedInSession(USER, "wrong", server).get(f"{server}/protected")


def test_windows_challenge_selects_ntlm(server, monkeypatch):

    chosen = []

    class FakeNtlm:
        def __init__(self, username, password):
            chosen.append((username, password))

        def __call__(self, request):
            return request

    import requests_ntlm
    monkeypatch.setattr(requests_ntlm, "HttpNtlmAuth", FakeNtlm)

    with pytest.raises(AuthError):
        SignedInSession("CORP\\alice", PASSWORD, server).get(f"{server}/windows")

    assert chosen == [("CORP\\alice", PASSWORD)]
    # The password was never sent as Basic to the Windows-auth server.
    assert all(not (s["auth"] or "").startswith("Basic") for s in seen if s["path"] == "/windows")


def test_credentials_not_forwarded_to_other_host(server):
    web_processor.extract_web_content(f"{server}/hop", username=USER, password=PASSWORD)
    redirected = [s for s in seen if s["path"] == "/public"]
    assert redirected and redirected[0]["host"] == "localhost" and redirected[0]["auth"] is None


def test_protected_page_without_sign_in_explains(server):
    with pytest.raises(AuthError, match="Requires sign-in"):
        web_processor.extract_web_content(f"{server}/protected")


def test_login_form_pages_are_reported(server):
    with pytest.raises(AuthError, match="login form"):
        web_processor.extract_web_content(f"{server}/login-form", username=USER, password=PASSWORD)


def test_private_allowlist(monkeypatch):
    monkeypatch.setattr(web_processor, "ALLOW_PRIVATE_URLS", False)
    monkeypatch.setattr(web_processor, "PRIVATE_URL_ALLOWLIST", {"localhost"})
    web_processor.check_url("http://localhost:8080/tfs/DefaultCollection")
    with pytest.raises(ValueError, match="PRIVATE_URL_ALLOWLIST"):
        web_processor.check_url("http://127.0.0.1:8080/")


# ---------------- TFS ----------------

@pytest.mark.parametrize("url,expected", [
    ("https://dev.azure.com/contoso/My%20Project/_workitems/assignedtome",
     {"collection": "https://dev.azure.com/contoso", "project": "My Project"}),
    ("https://dev.azure.com/contoso", {"collection": "https://dev.azure.com/contoso", "project": None}),
    ("https://contoso.visualstudio.com/DefaultCollection/Web/_boards",
     {"collection": "https://contoso.visualstudio.com", "project": "Web"}),
    ("http://tfs01:8080/tfs/DefaultCollection/Payments/_workitems",
     {"collection": "http://tfs01:8080/tfs/DefaultCollection", "project": "Payments"}),
    ("http://devops.corp/Coll/Proj/_workitems", {"collection": "http://devops.corp/Coll", "project": "Proj"}),
    ("https://en.wikipedia.org/wiki/Zebra", None),
    ("https://example.com/_next/static/x.js", None),
])
def test_tfs_url_parsing(url, expected):
    assert parse_tfs_url(url) == expected


def test_tfs_import_with_version_fallback(server):

    documents = tfs_processor.extract_tfs_work_items(
        f"{server}/tfs/DefaultCollection/Payments/_workitems", "anyone", PAT
    )

    assert [d["metadata"]["work_item_id"] for d in documents] == [102, 101]
    bug = documents[1]
    assert bug["text"].startswith("Work item #101: Login fails on Safari")
    assert "State: Active" in bug["text"] and "Priority: 1" in bug["text"]
    assert "Assigned to: Alice Example" in bug["text"]
    assert "Repro steps:\nOpen the app in Safari 17\nClick Login: spinner never stops" in bug["text"]
    assert "Bob QA: Also happens on iOS 18." in bug["text"]
    assert bug["metadata"]["url"].endswith("/tfs/DefaultCollection/Payments/_workitems/edit/101")
    assert bug["metadata"]["title"] == "TFS · Payments · assigned to Alice Example"
    assert bug["metadata"]["section"] == "#101 Login fails on Safari"


def test_tfs_wrong_token(server):
    with pytest.raises(AuthError, match="Sign-in failed"):
        tfs_processor.extract_tfs_work_items(f"{server}/tfs/DefaultCollection/Payments", "x", "bad")


def test_tfs_requires_credentials(server):
    with pytest.raises(AuthError, match="needs sign-in"):
        tfs_processor.extract_tfs_work_items(f"{server}/tfs/DefaultCollection/Payments")


# ---------------- through the API ----------------

def add_url(client, headers, url, **auth):
    data = {"urls": url}
    if auth:
        data.update(auth_enabled="true", **auth)
    return client.post("/api/sources", data=data, headers=headers)


def test_sign_in_fields_are_required_when_enabled(client, alice):
    response = client.post(
        "/api/sources",
        data={"urls": "https://example.com/x", "auth_enabled": "true", "auth_username": "alice"},
        headers=alice,
    )
    assert response.status_code == 400 and "required" in response.json()["detail"]


def test_tfs_link_without_sign_in_rejected(client, alice):
    response = add_url(client, alice, "https://dev.azure.com/contoso/Payments/_workitems")
    assert response.status_code == 400 and "needs sign-in" in response.json()["detail"]


def test_protected_site_end_to_end(client, alice, server):

    response = add_url(client, alice, f"{server}/protected", auth_username=USER, auth_password=PASSWORD)
    assert response.status_code == 201
    assert PASSWORD not in response.text

    source = sources(client, alice)[0]
    assert source["status"] == "ready", source
    assert source["has_auth"] is True and source["name"] == "Runbook"

    with sqlite3.connect(settings.DATABASE_PATH) as connection:
        stored = connection.execute("SELECT auth_enc FROM sources").fetchone()[0]
    assert stored and PASSWORD not in stored and USER not in stored

    events = chat(client, alice, "When do deploys freeze?")
    assert events[0]["sources"][0]["name"] == "Runbook"
    assert PASSWORD not in json.dumps(events)


def test_tfs_end_to_end_and_refresh(client, alice, server):

    url = f"{server}/tfs/DefaultCollection/Payments/_workitems"
    assert add_url(client, alice, url, auth_username="me", auth_password=PAT).status_code == 201

    source = sources(client, alice)[0]
    assert source["status"] == "ready", source
    assert source["kind"] == "tfs" and source["file_type"] == "tfs"
    assert source["name"] == "TFS · Payments · assigned to Alice Example"
    assert source["chunk_count"] >= 2

    events = chat(client, alice, "What are the repro steps for the Safari login bug?")
    top = events[0]["sources"][0]
    assert top["location"] == "#101 Login fails on Safari"
    assert top["url"].endswith("/_workitems/edit/101")

    link = client.get(f"/api/sources/{source['id']}/link", headers=alice).json()
    assert link == {"url": url}

    # A new ticket is assigned; Refresh picks it up with the saved credentials.
    work_items[103] = {"System.Title": "Rotate API keys", "System.WorkItemType": "Task",
                       "System.State": "New", "System.TeamProject": "Payments"}
    try:
        assert client.post(f"/api/sources/{source['id']}/retry", headers=alice).status_code == 200
        refreshed = sources(client, alice)[0]
        assert refreshed["status"] == "ready" and refreshed["chunk_count"] > source["chunk_count"]
    finally:
        del work_items[103]
