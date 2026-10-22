import hashlib
import math
import re

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessageChunk

from backend import auth, crypto, jobs, library, main
from config import settings
from src import rag_pipeline
from src.retrieval import reranker


class HashEmbeddings(Embeddings):
    """Deterministic bag-of-words embeddings: similar words -> similar vectors."""

    dims = 256

    def _embed(self, text):
        vector = [0.0] * self.dims
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            index = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dims
            vector[index] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts):
        return [self._embed(text) for text in texts]

    def embed_query(self, text):
        return self._embed(text)


class FakeLLM:
    """Echoes the first evidence line it was given, as a cited answer."""

    def __init__(self, calls):
        self.calls = calls

    def _answer(self, messages):
        if isinstance(messages, str):
            self.calls["rewrites"].append(messages)
            return "rewritten standalone query"
        prompt = messages[-1].content
        self.calls["prompts"].append(prompt)
        evidence = prompt.split("\n")[3] if "Sources:" in prompt else ""
        return f"Answer: {evidence} [1]"

    def invoke(self, messages):
        return AIMessageChunk(content=self._answer(messages))

    def stream(self, messages):
        for word in self._answer(messages).split(" "):
            yield AIMessageChunk(content=word + " ")


@pytest.fixture
def calls():
    return {"prompts": [], "rewrites": [], "configs": []}


@pytest.fixture
def client(tmp_path, monkeypatch, calls):

    monkeypatch.setattr(settings, "DATABASE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setattr(settings, "JWT_SECRET", "test-secret-" + "x" * 32)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "local")
    monkeypatch.setattr(settings, "WARM_UP_MODELS", False)
    monkeypatch.setattr(auth, "_secret", None)
    monkeypatch.setattr(crypto, "KEY_FILE", tmp_path / ".encryption_key")
    monkeypatch.setattr(crypto, "_fernet", None)
    monkeypatch.setattr(library, "VECTORSTORE_ROOT", tmp_path / "vectorstore")
    monkeypatch.setattr(library, "UPLOAD_ROOT", tmp_path / "uploads")
    monkeypatch.setattr(library, "_libraries", {})

    def fake_embeddings(config):
        calls["configs"].append(config)
        return HashEmbeddings()

    monkeypatch.setattr(library, "get_embeddings", fake_embeddings)
    monkeypatch.setattr(rag_pipeline, "get_llm", lambda config: FakeLLM(calls))
    monkeypatch.setattr(reranker, "RERANKER_ENABLED", False)
    monkeypatch.setattr(settings, "MAX_VECTOR_DISTANCE", 1.6)

    # Run ingestion inline so tests see the final state.
    monkeypatch.setattr(jobs, "submit", jobs.process_source)
    monkeypatch.setattr(main.jobs, "submit", jobs.process_source)
    monkeypatch.setattr(jobs, "get_image_describer", lambda config: None)

    with TestClient(main.app) as test_client:
        test_client.calls = calls
        yield test_client


def register(client, username="alice", password="password123"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )


def auth_headers(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def alice(client):
    return auth_headers(register(client, "alice"))


@pytest.fixture
def bobby(client):
    return auth_headers(register(client, "bobby"))
