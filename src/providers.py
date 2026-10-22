"""
Model provider selection.

Everything that talks to an LLM, embedding model or vision model goes
through a ProviderConfig, so the same pipeline runs against a local
Ollama / sentence-transformers stack or an OpenAI-compatible API.
"""

import base64
import io
from dataclasses import dataclass, replace

import requests
from PIL import Image

from config import settings


LLM_PROVIDERS = ("ollama", "openai")

EMBEDDING_PROVIDERS = ("local", "openai")

VISION_PROMPT = (
    "Describe this image for a search index. State what it shows, any "
    "people, objects, charts or diagrams, and transcribe any visible text, "
    "numbers and labels exactly. Be factual and concise (under 120 words)."
)

# Downscale before sending to a vision model; large images are slow on
# CPU and cost more tokens in the cloud.
VISION_MAX_SIDE = 896


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderConfig:
    llm_provider: str
    llm_model: str
    embedding_provider: str
    embedding_model: str
    vision_enabled: bool
    vision_model: str
    openai_api_key: str
    openai_base_url: str
    ollama_base_url: str

    @property
    def embedding_signature(self) -> str:
        return f"{self.embedding_provider}:{self.embedding_model}"


def default_model(kind: str, provider: str) -> str:

    defaults = {
        ("llm", "ollama"): settings.OLLAMA_MODEL,
        ("llm", "openai"): settings.OPENAI_MODEL,
        ("vision", "ollama"): settings.OLLAMA_VISION_MODEL,
        ("vision", "openai"): settings.OPENAI_VISION_MODEL,
        ("embedding", "local"): settings.EMBEDDING_MODEL,
        ("embedding", "openai"): settings.OPENAI_EMBEDDING_MODEL,
    }

    return defaults[(kind, provider)]


def build_config(overrides: dict | None = None) -> ProviderConfig:
    """Server defaults from .env, with optional per-user overrides."""

    overrides = {
        key: value
        for key, value in (overrides or {}).items()
        if value not in (None, "")
    }

    llm_provider = overrides.get("llm_provider", settings.LLM_PROVIDER)
    embedding_provider = overrides.get(
        "embedding_provider",
        settings.EMBEDDING_PROVIDER,
    )

    if llm_provider not in LLM_PROVIDERS:
        llm_provider = "ollama"

    if embedding_provider not in EMBEDDING_PROVIDERS:
        embedding_provider = "local"

    return ProviderConfig(
        llm_provider=llm_provider,
        llm_model=overrides.get(
            "llm_model",
            default_model("llm", llm_provider),
        ),
        embedding_provider=embedding_provider,
        embedding_model=overrides.get(
            "embedding_model",
            default_model("embedding", embedding_provider),
        ),
        vision_enabled=bool(
            overrides.get("vision_enabled", settings.VISION_ENABLED)
        ),
        vision_model=overrides.get(
            "vision_model",
            default_model("vision", llm_provider),
        ),
        openai_api_key=overrides.get(
            "openai_api_key",
            settings.OPENAI_API_KEY,
        ),
        openai_base_url=overrides.get(
            "openai_base_url",
            settings.OPENAI_BASE_URL,
        ),
        ollama_base_url=settings.OLLAMA_BASE_URL,
    )


def with_embedding(config: ProviderConfig, signature: str) -> ProviderConfig:
    """Same config but using the embedder an existing index was built with."""

    provider, _, model = signature.partition(":")

    return replace(
        config,
        embedding_provider=provider,
        embedding_model=model,
    )


def _require_openai_key(config: ProviderConfig):

    if not config.openai_api_key:
        raise ProviderError(
            "OpenAI is selected but no API key is configured. "
            "Add one in Settings or set OPENAI_API_KEY in .env."
        )


# --------------------------------------------------
# Chat model
# --------------------------------------------------

def get_llm(config: ProviderConfig, temperature: float = 0):

    if config.llm_provider == "openai":

        from langchain_openai import ChatOpenAI

        _require_openai_key(config)

        return ChatOpenAI(
            model=config.llm_model,
            api_key=config.openai_api_key,
            base_url=config.openai_base_url or None,
            temperature=temperature,
            timeout=120,
            max_retries=2,
        )

    from langchain_ollama import ChatOllama

    return ChatOllama(
        base_url=config.ollama_base_url,
        model=config.llm_model,
        temperature=temperature,
        num_ctx=settings.OLLAMA_NUM_CTX,
    )


# --------------------------------------------------
# Embeddings
# --------------------------------------------------

def get_embeddings(config: ProviderConfig):

    if config.embedding_provider == "openai":

        from langchain_openai import OpenAIEmbeddings

        _require_openai_key(config)

        return OpenAIEmbeddings(
            model=config.embedding_model,
            api_key=config.openai_api_key,
            base_url=config.openai_base_url or None,
            # Send raw strings; chunks are far below the token limit and
            # this avoids a tiktoken download.
            check_embedding_ctx_length=False,
        )

    from src.embeddings.embedding_service import get_embedding_model

    return get_embedding_model(config.embedding_model)


# --------------------------------------------------
# Vision
# --------------------------------------------------

def _encode_image(image_path: str) -> str:

    with Image.open(image_path) as image:

        image = image.convert("RGB")
        image.thumbnail((VISION_MAX_SIDE, VISION_MAX_SIDE))

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)

    return base64.b64encode(buffer.getvalue()).decode("ascii")


def get_image_describer(config: ProviderConfig):
    """
    Returns describe(image_path) -> str, or None when vision is off.
    """

    if not config.vision_enabled:
        return None

    if config.llm_provider == "openai":

        from langchain_core.messages import HumanMessage
        from langchain_openai import ChatOpenAI

        _require_openai_key(config)

        model = ChatOpenAI(
            model=config.vision_model,
            api_key=config.openai_api_key,
            base_url=config.openai_base_url or None,
            temperature=0,
            timeout=120,
            max_retries=2,
        )

        def describe(image_path: str) -> str:

            message = HumanMessage(
                content=[
                    {"type": "text", "text": VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                "data:image/jpeg;base64,"
                                + _encode_image(image_path)
                            ),
                        },
                    },
                ]
            )

            return model.invoke([message]).content.strip()

        return describe

    def describe(image_path: str) -> str:

        response = requests.post(
            f"{config.ollama_base_url.rstrip('/')}/api/chat",
            json={
                "model": config.vision_model,
                "stream": False,
                "options": {"temperature": 0},
                "messages": [
                    {
                        "role": "user",
                        "content": VISION_PROMPT,
                        "images": [_encode_image(image_path)],
                    }
                ],
            },
            timeout=600,
        )

        if response.status_code == 404:
            raise ProviderError(
                f"Ollama vision model '{config.vision_model}' is not "
                f"installed. Run: ollama pull {config.vision_model}"
            )

        response.raise_for_status()

        return response.json()["message"]["content"].strip()

    return describe


# --------------------------------------------------
# Connection test
# --------------------------------------------------

def test_connection(config: ProviderConfig) -> dict:

    results = {}

    try:
        reply = get_llm(config).invoke("Reply with the single word: ok")
        results["llm"] = {
            "ok": True,
            "detail": f"{config.llm_provider} / {config.llm_model}: "
            f"{str(reply.content).strip()[:40]}",
        }
    except Exception as error:
        results["llm"] = {"ok": False, "detail": str(error)[:300]}

    try:
        vector = get_embeddings(config).embed_query("connection test")
        results["embedding"] = {
            "ok": True,
            "detail": f"{config.embedding_signature} ({len(vector)} dims)",
        }
    except Exception as error:
        results["embedding"] = {"ok": False, "detail": str(error)[:300]}

    return results
