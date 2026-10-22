from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from backend import crypto, database
from backend.auth import get_current_user
from config import settings
from src.providers import (
    EMBEDDING_PROVIDERS,
    LLM_PROVIDERS,
    build_config,
    default_model,
    test_connection,
)


router = APIRouter(prefix="/api/settings", tags=["settings"])

FIELDS = (
    "llm_provider",
    "llm_model",
    "embedding_provider",
    "embedding_model",
    "vision_enabled",
    "vision_model",
    "openai_base_url",
)


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = Field(default=None, max_length=120)
    embedding_provider: str | None = None
    embedding_model: str | None = Field(default=None, max_length=120)
    vision_enabled: bool | None = None
    vision_model: str | None = Field(default=None, max_length=120)
    openai_base_url: str | None = Field(default=None, max_length=300)
    # None = keep, "" = remove, otherwise replace.
    openai_api_key: str | None = Field(default=None, max_length=300)


def _overrides(user_id: int) -> dict:

    values, key_enc = database.get_user_settings(user_id)

    overrides = {field: values.get(field) for field in FIELDS}

    key = crypto.decrypt(key_enc)

    if key:
        overrides["openai_api_key"] = key

    return overrides


def get_user_config(user_id: int):
    """ProviderConfig for a user: .env defaults + their saved overrides."""

    return build_config(_overrides(user_id))


def _validate(update: SettingsUpdate):

    if update.llm_provider and update.llm_provider not in LLM_PROVIDERS:
        raise HTTPException(400, "Unknown answer model provider.")

    if update.embedding_provider and update.embedding_provider not in EMBEDDING_PROVIDERS:
        raise HTTPException(400, "Unknown embedding provider.")

    if update.openai_base_url:
        parsed = urlparse(update.openai_base_url)

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(400, "OpenAI base URL must be an http(s) URL.")


def _describe(user_id: int) -> dict:

    values, key_enc = database.get_user_settings(user_id)
    key = crypto.decrypt(key_enc)
    config = build_config(_overrides(user_id))

    return {
        "settings": {field: values.get(field) for field in FIELDS},
        "effective": {
            "llm_provider": config.llm_provider,
            "llm_model": config.llm_model,
            "embedding_provider": config.embedding_provider,
            "embedding_model": config.embedding_model,
            "vision_enabled": config.vision_enabled,
            "vision_model": config.vision_model,
            "openai_base_url": config.openai_base_url,
        },
        "defaults": {
            "llm_provider": settings.LLM_PROVIDER,
            "embedding_provider": settings.EMBEDDING_PROVIDER,
            "vision_enabled": settings.VISION_ENABLED,
            "llm": {p: default_model("llm", p) for p in LLM_PROVIDERS},
            "vision": {p: default_model("vision", p) for p in LLM_PROVIDERS},
            "embedding": {
                p: default_model("embedding", p) for p in EMBEDDING_PROVIDERS
            },
        },
        "openai_key": {
            "saved": bool(key),
            "hint": f"…{key[-4:]}" if len(key) >= 8 else "",
            "server": bool(settings.OPENAI_API_KEY),
        },
    }


@router.get("")
def read_settings(user=Depends(get_current_user)):
    return _describe(user["id"])


@router.put("")
def update_settings(update: SettingsUpdate, user=Depends(get_current_user)):

    _validate(update)

    values, _ = database.get_user_settings(user["id"])

    for field in FIELDS:
        value = getattr(update, field)

        if value is not None:
            values[field] = value.strip() if isinstance(value, str) else value

    key_enc = None

    if update.openai_api_key is not None:
        key_enc = crypto.encrypt(update.openai_api_key.strip())

    database.save_user_settings(user["id"], values, key_enc)

    return _describe(user["id"])


@router.post("/test")
async def test_settings(update: SettingsUpdate, user=Depends(get_current_user)):
    """Test saved settings, with any unsaved values from the form applied."""

    _validate(update)

    overrides = _overrides(user["id"])

    for field in FIELDS + ("openai_api_key",):
        value = getattr(update, field)

        if value not in (None, ""):
            overrides[field] = value

    return await run_in_threadpool(test_connection, build_config(overrides))
