import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend import database
from config import settings


JWT_ALGORITHM = "HS256"

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")

MIN_PASSWORD_LENGTH = 8

# bcrypt only uses the first 72 bytes.
MAX_PASSWORD_BYTES = 72

SECRET_FILE = Path(settings.DATA_DIR) / ".jwt_secret"

_secret = None

bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --------------------------------------------------
# Secret
# --------------------------------------------------

def get_secret() -> str:

    global _secret

    if _secret:
        return _secret

    if settings.JWT_SECRET:
        _secret = settings.JWT_SECRET
        return _secret

    if SECRET_FILE.exists():
        _secret = SECRET_FILE.read_text().strip()

    if not _secret:
        _secret = secrets.token_urlsafe(48)
        SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        SECRET_FILE.write_text(_secret)

    return _secret


# --------------------------------------------------
# Passwords and tokens
# --------------------------------------------------

def hash_password(password: str) -> str:

    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:

    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:MAX_PASSWORD_BYTES],
            password_hash.encode("utf-8"),
        )
    except ValueError:
        return False


def create_token(user) -> str:

    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_EXPIRE_MINUTES
    )

    return jwt.encode(
        {
            "sub": str(user["id"]),
            "username": user["username"],
            "exp": expires,
        },
        get_secret(),
        algorithm=JWT_ALGORITHM,
    )


FILE_TOKEN_MINUTES = 30


def create_file_token(user_id: int, source_id: str) -> str:
    """
    Short-lived token for one source file, so <video>/<audio>/<img> can
    load it by URL (they cannot send an Authorization header).
    """

    return jwt.encode(
        {
            "sub": str(user_id),
            "file": source_id,
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=FILE_TOKEN_MINUTES),
        },
        get_secret(),
        algorithm=JWT_ALGORITHM,
    )


def verify_file_token(token: str, source_id: str) -> int | None:
    """User id if the token grants access to this source."""

    try:
        payload = jwt.decode(token, get_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None

    if payload.get("file") != source_id:
        return None

    return int(payload["sub"])


# --------------------------------------------------
# Dependency
# --------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
            get_secret(),
            algorithms=[JWT_ALGORITHM],
        )
        user_id = int(payload["sub"])

    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized

    # File tokens travel in URLs; they must not work as session tokens.
    if "file" in payload:
        raise unauthorized

    user = database.get_user_by_id(user_id)

    if user is None:
        raise unauthorized

    return user


# --------------------------------------------------
# Routes
# --------------------------------------------------

class Credentials(BaseModel):
    username: str
    password: str


def _public_user(user):

    return {
        "id": user["id"],
        "username": user["username"],
    }


def _token_response(user):

    return {
        "access_token": create_token(user),
        "token_type": "bearer",
        "user": _public_user(user),
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(credentials: Credentials):

    username = credentials.username.strip().lower()

    if not USERNAME_PATTERN.match(username):
        raise HTTPException(
            status_code=400,
            detail=(
                "Username must be 3-32 characters: letters, "
                "numbers, '_', '.' or '-'."
            ),
        )

    if len(credentials.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Password must be at least "
                f"{MIN_PASSWORD_LENGTH} characters."
            ),
        )

    if len(credentials.password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Password is too long (72 bytes maximum).",
        )

    user = database.create_user(
        username,
        hash_password(credentials.password),
    )

    if user is None:
        raise HTTPException(
            status_code=409,
            detail="That username is already taken.",
        )

    return _token_response(user)


@router.post("/login")
def login(credentials: Credentials):

    user = database.get_user_by_username(
        credentials.username.strip().lower()
    )

    # Same error for unknown user and bad password.
    if user is None or not verify_password(
        credentials.password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )

    return _token_response(user)


@router.get("/me")
def me(user=Depends(get_current_user)):

    return _public_user(user)
