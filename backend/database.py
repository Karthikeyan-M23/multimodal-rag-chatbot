import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, id);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    location TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'queued',
    progress TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sources_user ON sources(user_id, created_at);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    text TEXT NOT NULL,
    metadata TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_user ON chunks(user_id, source_id, position);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    source_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    settings TEXT NOT NULL DEFAULT '{}',
    openai_key_enc TEXT NOT NULL DEFAULT ''
);
"""


@contextmanager
def connect():

    db_path = Path(settings.DATABASE_PATH)

    db_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(db_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db():

    with connect() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(SCHEMA)
        _migrate_messages_to_conversations(connection)
        _add_column(connection, "sources", "auth_enc", "TEXT NOT NULL DEFAULT ''")


def _add_column(connection, table, column, definition):

    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}

    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migrate_messages_to_conversations(connection):
    """
    Older databases kept one chat per user. Add messages.conversation_id
    and move each user's existing messages into an "Earlier chat".
    """

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(messages)")
    }

    if "conversation_id" not in columns:
        connection.execute(
            "ALTER TABLE messages ADD COLUMN conversation_id TEXT "
            "REFERENCES conversations(id) ON DELETE CASCADE"
        )

    orphans = connection.execute(
        "SELECT user_id, MIN(created_at) AS first, MAX(created_at) AS last "
        "FROM messages WHERE conversation_id IS NULL GROUP BY user_id"
    ).fetchall()

    for row in orphans:
        conversation_id = uuid.uuid4().hex

        connection.execute(
            "INSERT INTO conversations (id, user_id, title, created_at, updated_at) "
            "VALUES (?, ?, 'Earlier chat', ?, ?)",
            (conversation_id, row["user_id"], row["first"], row["last"]),
        )
        connection.execute(
            "UPDATE messages SET conversation_id = ? "
            "WHERE user_id = ? AND conversation_id IS NULL",
            (conversation_id, row["user_id"]),
        )

    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation "
        "ON messages(conversation_id, id)"
    )


# --------------------------------------------------
# Users
# --------------------------------------------------

def create_user(username: str, password_hash: str):
    """Returns the new user row, or None if the name is taken."""

    try:
        with connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) "
                "VALUES (?, ?)",
                (username, password_hash),
            )
            user_id = cursor.lastrowid

    except sqlite3.IntegrityError:
        return None

    return get_user_by_id(user_id)


def get_user_by_username(username: str):

    with connect() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()


def get_user_by_id(user_id: int):

    with connect() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


# --------------------------------------------------
# Conversations
# --------------------------------------------------

def public_conversation(row) -> dict:

    return {
        "id": row["id"],
        "title": row["title"],
        "source_ids": json.loads(row["source_ids"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_conversation(user_id: int, title: str, source_ids=None):

    conversation_id = uuid.uuid4().hex

    with connect() as connection:
        connection.execute(
            "INSERT INTO conversations (id, user_id, title, source_ids) "
            "VALUES (?, ?, ?, ?)",
            (conversation_id, user_id, title, json.dumps(source_ids or [])),
        )

    return get_conversation(user_id, conversation_id)


def get_conversation(user_id: int, conversation_id: str):

    with connect() as connection:
        return connection.execute(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()


def list_conversations(user_id: int):

    with connect() as connection:
        return connection.execute(
            "SELECT * FROM conversations WHERE user_id = ? "
            "ORDER BY updated_at DESC, rowid DESC",
            (user_id,),
        ).fetchall()


def update_conversation(conversation_id: str, title=None, source_ids=None):

    with connect() as connection:

        if title is not None:
            connection.execute(
                "UPDATE conversations SET title = ? WHERE id = ?",
                (title, conversation_id),
            )

        if source_ids is not None:
            connection.execute(
                "UPDATE conversations SET source_ids = ? WHERE id = ?",
                (json.dumps(source_ids), conversation_id),
            )

        connection.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,),
        )


def delete_conversation(user_id: int, conversation_id: str):

    with connect() as connection:
        connection.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )


# --------------------------------------------------
# Messages
# --------------------------------------------------

def add_message(user_id: int, conversation_id: str, role: str, content: str, sources=None):

    with connect() as connection:
        connection.execute(
            "INSERT INTO messages (user_id, conversation_id, role, content, sources) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                user_id,
                conversation_id,
                role,
                content,
                json.dumps(sources or [], default=str),
            ),
        )


def get_messages(conversation_id: str, limit: int = 500):

    with connect() as connection:
        rows = connection.execute(
            "SELECT role, content, sources FROM ("
            "  SELECT id, role, content, sources FROM messages "
            "  WHERE conversation_id = ? ORDER BY id DESC LIMIT ?"
            ") ORDER BY id ASC",
            (conversation_id, limit),
        ).fetchall()

    return [
        {
            "role": row["role"],
            "content": row["content"],
            "sources": json.loads(row["sources"]),
        }
        for row in rows
    ]


# --------------------------------------------------
# Sources
# --------------------------------------------------

SOURCE_FIELDS = (
    "id", "kind", "name", "file_type", "size_bytes", "status",
    "progress", "error", "note", "chunk_count", "created_at", "updated_at",
)


def public_source(row) -> dict:
    # Credentials never leave the server; only whether there are any.
    return {
        **{field: row[field] for field in SOURCE_FIELDS},
        "has_auth": bool(row["auth_enc"]),
    }


def create_source(user_id, kind, name, file_type, location, size_bytes=0, auth_enc=""):
    """auth_enc: encrypted sign-in credentials for protected URLs."""

    source_id = uuid.uuid4().hex

    with connect() as connection:
        connection.execute(
            "INSERT INTO sources "
            "(id, user_id, kind, name, file_type, location, size_bytes, auth_enc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (source_id, user_id, kind, name, file_type, location, size_bytes, auth_enc),
        )

    return get_source(user_id, source_id)


def get_source(user_id: int, source_id: str):

    with connect() as connection:
        return connection.execute(
            "SELECT * FROM sources WHERE id = ? AND user_id = ?",
            (source_id, user_id),
        ).fetchone()


def list_sources(user_id: int):

    with connect() as connection:
        return connection.execute(
            "SELECT * FROM sources WHERE user_id = ? "
            "ORDER BY created_at DESC, rowid DESC",
            (user_id,),
        ).fetchall()


def update_source(source_id: str, **fields):

    if not fields:
        return

    assignments = ", ".join(f"{name} = ?" for name in fields)

    with connect() as connection:
        connection.execute(
            f"UPDATE sources SET {assignments}, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*fields.values(), source_id),
        )


def delete_source(user_id: int, source_id: str):

    with connect() as connection:
        connection.execute(
            "DELETE FROM sources WHERE id = ? AND user_id = ?",
            (source_id, user_id),
        )


def unfinished_sources():
    """Sources left queued/processing by a previous server run."""

    with connect() as connection:
        return connection.execute(
            "SELECT * FROM sources WHERE status IN ('queued', 'processing') "
            "ORDER BY created_at, rowid"
        ).fetchall()


# --------------------------------------------------
# Chunks
# --------------------------------------------------

def replace_chunks(user_id: int, source_id: str, chunks: list[dict]):

    with connect() as connection:
        connection.execute(
            "DELETE FROM chunks WHERE source_id = ?",
            (source_id,),
        )
        connection.executemany(
            "INSERT INTO chunks "
            "(chunk_id, user_id, source_id, position, text, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    chunk["metadata"]["chunk_id"],
                    user_id,
                    source_id,
                    position,
                    chunk["text"],
                    json.dumps(chunk["metadata"], default=str),
                )
                for position, chunk in enumerate(chunks)
            ],
        )


def get_chunks(user_id: int, source_id: str | None = None) -> list[dict]:

    query = "SELECT text, metadata FROM chunks WHERE user_id = ?"
    params = [user_id]

    if source_id:
        query += " AND source_id = ?"
        params.append(source_id)

    query += " ORDER BY source_id, position"

    with connect() as connection:
        rows = connection.execute(query, params).fetchall()

    return [
        {"text": row["text"], "metadata": json.loads(row["metadata"])}
        for row in rows
    ]


def get_chunk_ids(user_id: int, source_id: str) -> list[str]:

    with connect() as connection:
        return [
            row["chunk_id"]
            for row in connection.execute(
                "SELECT chunk_id FROM chunks WHERE user_id = ? AND source_id = ?",
                (user_id, source_id),
            )
        ]


# --------------------------------------------------
# Settings
# --------------------------------------------------

def get_user_settings(user_id: int) -> tuple[dict, str]:
    """(settings dict, encrypted OpenAI key or '')."""

    with connect() as connection:
        row = connection.execute(
            "SELECT settings, openai_key_enc FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    if row is None:
        return {}, ""

    return json.loads(row["settings"]), row["openai_key_enc"]


def save_user_settings(user_id: int, values: dict, openai_key_enc: str | None = None):
    """openai_key_enc=None keeps the stored key."""

    with connect() as connection:
        connection.execute(
            "INSERT INTO user_settings (user_id, settings) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET settings = excluded.settings",
            (user_id, json.dumps(values)),
        )

        if openai_key_enc is not None:
            connection.execute(
                "UPDATE user_settings SET openai_key_enc = ? WHERE user_id = ?",
                (openai_key_enc, user_id),
            )
