"""Encryption for secrets stored in the database (users' API keys)."""

from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from config import settings


KEY_FILE = Path(settings.DATA_DIR) / ".encryption_key"

_fernet = None


def _get_fernet() -> Fernet:

    global _fernet

    if _fernet is not None:
        return _fernet

    key = settings.APP_ENCRYPTION_KEY.strip()

    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text().strip()

    if not key:
        key = Fernet.generate_key().decode("ascii")
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_text(key)

    _fernet = Fernet(key.encode("ascii"))

    return _fernet


def encrypt(value: str) -> str:

    if not value:
        return ""

    return _get_fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value: str) -> str:
    """'' if empty or undecryptable (e.g. the key was rotated)."""

    if not value:
        return ""

    try:
        return _get_fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""
