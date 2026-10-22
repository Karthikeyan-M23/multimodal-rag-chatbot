from backend import database
from backend.user_settings import get_user_config
from config import settings
from src.providers import build_config


def test_defaults_come_from_env(client, alice):

    data = client.get("/api/settings", headers=alice).json()

    assert data["effective"]["llm_provider"] == "ollama"
    assert data["effective"]["llm_model"] == settings.OLLAMA_MODEL
    assert data["effective"]["embedding_provider"] == "local"
    assert data["defaults"]["llm"]["openai"] == settings.OPENAI_MODEL
    assert data["openai_key"] == {"saved": False, "hint": "", "server": False}


def test_switch_to_openai_and_key_is_encrypted(client, alice):

    response = client.put(
        "/api/settings",
        json={"llm_provider": "openai", "openai_api_key": "sk-test-1234567890abcd"},
        headers=alice,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["effective"]["llm_provider"] == "openai"
    assert data["effective"]["llm_model"] == settings.OPENAI_MODEL
    assert data["openai_key"]["saved"] and data["openai_key"]["hint"] == "…abcd"
    assert "sk-test" not in response.text

    _, stored = database.get_user_settings(1)
    assert stored and "sk-test" not in stored

    config = get_user_config(1)
    assert config.openai_api_key == "sk-test-1234567890abcd"
    assert config.llm_provider == "openai"


def test_saving_without_key_keeps_it_and_empty_removes_it(client, alice):

    client.put("/api/settings", json={"openai_api_key": "sk-keep-me-please-1234"}, headers=alice)
    client.put("/api/settings", json={"llm_model": "gpt-4.1-mini"}, headers=alice)
    assert get_user_config(1).openai_api_key == "sk-keep-me-please-1234"
    assert get_user_config(1).llm_model == "gpt-4.1-mini"

    data = client.put("/api/settings", json={"openai_api_key": ""}, headers=alice).json()
    assert data["openai_key"]["saved"] is False
    assert get_user_config(1).openai_api_key == ""


def test_settings_are_per_user(client, alice, bobby):
    client.put("/api/settings", json={"llm_provider": "openai"}, headers=alice)
    assert client.get("/api/settings", headers=bobby).json()["effective"]["llm_provider"] == "ollama"


def test_validation(client, alice):
    assert client.put("/api/settings", json={"llm_provider": "anthropic-x"}, headers=alice).status_code == 400
    assert client.put("/api/settings", json={"embedding_provider": "nope"}, headers=alice).status_code == 400
    assert client.put("/api/settings", json={"openai_base_url": "file:///etc"}, headers=alice).status_code == 400


def test_server_key_used_when_user_has_none(client, alice, monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-server-default-key")
    assert get_user_config(1).openai_api_key == "sk-server-default-key"
    assert client.get("/api/settings", headers=alice).json()["openai_key"]["server"] is True


def test_build_config_ignores_unknown_providers(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bogus")
    config = build_config({"embedding_provider": "bogus"})
    assert config.llm_provider == "ollama"
    assert config.embedding_provider == "local"


def test_embedding_change_suggests_reindex_and_reindex_switches(client, alice):

    client.post(
        "/api/sources",
        files=[("files", ("a.txt", b"zebra stripes", "text/plain"))],
        headers=alice,
    )

    library = client.get("/api/sources", headers=alice).json()["library"]
    assert library["embedding"] == f"local:{settings.EMBEDDING_MODEL}"
    assert library["reindex_suggested"] is False

    client.put(
        "/api/settings",
        json={"embedding_provider": "openai", "openai_api_key": "sk-abcdefgh12345678"},
        headers=alice,
    )

    library = client.get("/api/sources", headers=alice).json()["library"]
    assert library["reindex_suggested"] is True
    assert library["selected_embedding"] == f"openai:{settings.OPENAI_EMBEDDING_MODEL}"

    # Until re-indexed, queries keep using the embedder the index was built with.
    client.calls["configs"].clear()
    client.post("/api/chat/stream", json={"question": "zebra?"}, headers=alice)
    assert {c.embedding_provider for c in client.calls["configs"]} <= {"local"}

    # Reindex runs on the background executor; wait for it.
    from backend import jobs
    assert client.post("/api/library/reindex", headers=alice).status_code == 200
    jobs._executor.submit(lambda: None).result(timeout=30)

    library = client.get("/api/sources", headers=alice).json()["library"]
    assert library["embedding"] == f"openai:{settings.OPENAI_EMBEDDING_MODEL}"
    assert library["reindex_suggested"] is False
    assert library["reindex_error"] == ""
