import sqlite3

from backend import database
from config import settings
from tests.test_library_api import chat, chat_with, messages, sources, upload


# ---------------- conversations ----------------

def test_first_question_creates_titled_conversation(client, alice):

    upload(client, alice, "falcon.txt", b"Project Falcon is led by Dr. Meera Iyer.")

    conversation, events = chat_with(client, alice, "  Who   leads Project Falcon?  ")

    assert conversation["title"] == "Who leads Project Falcon?"
    assert events[-1]["type"] == "done"

    listed = client.get("/api/conversations", headers=alice).json()["conversations"]
    assert [c["id"] for c in listed] == [conversation["id"]]
    assert len(messages(client, alice, conversation["id"])) == 2


def test_long_titles_are_truncated(client, alice):
    conversation, _ = chat_with(client, alice, "word " * 60)
    assert len(conversation["title"]) <= 80 and conversation["title"].endswith("…")


def test_conversations_are_separate_and_most_recent_first(client, alice):

    upload(client, alice, "notes.txt", b"Zebras live in Africa. Falcons fly fast.")

    first, _ = chat_with(client, alice, "Where do zebras live?")
    second, _ = chat_with(client, alice, "How fast do falcons fly?")

    # Continue the first chat: it moves to the top.
    chat(client, alice, "Anything else?", conversation_id=first["id"])

    listed = client.get("/api/conversations", headers=alice).json()["conversations"]
    assert {c["id"] for c in listed} == {first["id"], second["id"]}
    assert len(messages(client, alice, first["id"])) == 4
    assert len(messages(client, alice, second["id"])) == 2


def test_rename_and_delete_conversation(client, alice):

    conversation, _ = chat_with(client, alice, "hello")
    cid = conversation["id"]

    renamed = client.patch(f"/api/conversations/{cid}", json={"title": "Renamed"}, headers=alice)
    assert renamed.json()["title"] == "Renamed"
    assert client.patch(f"/api/conversations/{cid}", json={"title": "  "}, headers=alice).status_code == 400

    assert client.delete(f"/api/conversations/{cid}", headers=alice).status_code == 200
    assert client.get(f"/api/conversations/{cid}", headers=alice).status_code == 404

    # Messages are removed with the conversation.
    with sqlite3.connect(settings.DATABASE_PATH) as connection:
        assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0


def test_conversations_are_private(client, alice, bobby):

    conversation, _ = chat_with(client, alice, "secret question")
    cid = conversation["id"]

    assert client.get("/api/conversations", headers=bobby).json()["conversations"] == []
    assert client.get(f"/api/conversations/{cid}", headers=bobby).status_code == 404
    assert client.delete(f"/api/conversations/{cid}", headers=bobby).status_code == 404
    assert client.patch(f"/api/conversations/{cid}", json={"title": "x"}, headers=bobby).status_code == 404

    # Bobby cannot post into Alice's conversation.
    response = client.post(
        "/api/chat/stream",
        json={"question": "hi", "conversation_id": cid},
        headers=bobby,
    )
    assert response.status_code == 404
    assert len(messages(client, alice, cid)) == 2


def test_old_single_history_is_migrated(client, alice):
    """Messages from before conversations existed land in 'Earlier chat'."""

    with sqlite3.connect(settings.DATABASE_PATH) as connection:
        connection.execute(
            "INSERT INTO messages (user_id, role, content, sources) VALUES (1, 'user', 'old q', '[]')"
        )
        connection.execute(
            "INSERT INTO messages (user_id, role, content, sources) VALUES (1, 'assistant', 'old a', '[]')"
        )

    database.init_db()  # what a server restart does

    listed = client.get("/api/conversations", headers=alice).json()["conversations"]
    assert [c["title"] for c in listed] == ["Earlier chat"]
    assert [m["content"] for m in messages(client, alice, listed[0]["id"])] == ["old q", "old a"]

    database.init_db()  # idempotent
    assert len(client.get("/api/conversations", headers=alice).json()["conversations"]) == 1


# ---------------- source scope ----------------

def test_scope_restricts_search_to_selected_sources(client, alice):

    upload(client, alice, "zebra.txt", b"A group of zebras is called a dazzle.")
    upload(client, alice, "falcon.txt", b"The falcon group is called a cast. Zebras are not birds.")

    by_name = {s["name"]: s["id"] for s in sources(client, alice)}

    everything = chat(client, alice, "What is a group of zebras called?")
    assert {s["name"] for s in everything[0]["sources"]} == {"zebra.txt", "falcon.txt"}

    conversation, scoped = chat_with(
        client, alice, "What is a group of zebras called?", source_ids=[by_name["falcon.txt"]]
    )
    assert {s["name"] for s in scoped[0]["sources"]} == {"falcon.txt"}
    assert conversation["source_ids"] == [by_name["falcon.txt"]]

    # The scope is remembered by the conversation.
    stored = client.get(f"/api/conversations/{conversation['id']}", headers=alice).json()
    assert stored["source_ids"] == [by_name["falcon.txt"]]


def test_scope_can_be_changed_on_a_conversation(client, alice):

    upload(client, alice, "a.txt", b"alpha")
    source_id = sources(client, alice)[0]["id"]
    conversation, _ = chat_with(client, alice, "alpha?")

    updated = client.patch(
        f"/api/conversations/{conversation['id']}",
        json={"source_ids": [source_id, "not-a-real-id"]},
        headers=alice,
    ).json()
    assert updated["source_ids"] == [source_id]

    cleared = client.patch(
        f"/api/conversations/{conversation['id']}", json={"source_ids": []}, headers=alice
    ).json()
    assert cleared["source_ids"] == []


def test_scope_ignores_other_users_sources(client, alice, bobby):

    upload(client, bobby, "bobby.txt", b"The vault code is 7741.")
    bobby_source = sources(client, bobby)[0]["id"]

    upload(client, alice, "alice.txt", b"Alice notes about vaults.")

    conversation, events = chat_with(client, alice, "What is the vault code?", source_ids=[bobby_source])

    assert conversation["source_ids"] == []
    assert "7741" not in str(events)


def test_scope_with_no_ready_sources(client, alice, monkeypatch):

    from backend import jobs

    monkeypatch.setattr(jobs, "submit", lambda *args: None)
    monkeypatch.setattr("backend.main.jobs.submit", jobs.submit)

    upload(client, alice, "pending.txt", b"not processed yet")
    pending = sources(client, alice)[0]["id"]

    events = chat(client, alice, "anything?", source_ids=[pending])
    assert "selected sources are ready" in events[-1]["answer"]
