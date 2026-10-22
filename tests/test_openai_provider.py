"""
Runs the real OpenAI client code (langchain-openai) against a local fake
OpenAI-compatible server, so the cloud path is tested without a key.
"""

import io
import json
import socket
import threading
import time

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw

from backend import jobs, library
from src import providers, rag_pipeline
from tests.conftest import HashEmbeddings


requests_seen = []


def _content_text(messages):
    parts = []
    for message in messages:
        content = message["content"]
        if isinstance(content, list):
            parts.extend(p.get("text", "") for p in content if p.get("type") == "text")
            if any(p.get("type") == "image_url" for p in content):
                parts.append("<<image>>")
        else:
            parts.append(content)
    return "\n".join(parts)


def _reply_for(body):
    text = _content_text(body["messages"])
    if "<<image>>" in text:
        return "A bar chart titled Quarterly Revenue showing Q3 as the highest bar."
    if "single word" in text:
        return "ok"
    if "Sources:" in text:
        return "Q3 had the highest revenue according to the chart [1]."
    return "standalone query"


fake = FastAPI()


@fake.post("/v1/chat/completions")
async def completions(request: Request):

    body = await request.json()
    requests_seen.append({"path": "chat", "auth": request.headers.get("authorization"), "body": body})
    reply = _reply_for(body)

    if body.get("stream"):

        def events():
            for index, word in enumerate(reply.split(" ")):
                chunk = {
                    "id": "c1", "object": "chat.completion.chunk", "created": 0,
                    "model": body["model"],
                    "choices": [{"index": 0, "delta": {"content": (" " if index else "") + word},
                                 "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    return {
        "id": "c1", "object": "chat.completion", "created": 0, "model": body["model"],
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": reply}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@fake.post("/v1/embeddings")
async def embeddings(request: Request):

    body = await request.json()
    requests_seen.append({"path": "embeddings", "auth": request.headers.get("authorization"), "body": body})
    inputs = body["input"] if isinstance(body["input"], list) else [body["input"]]
    vectors = HashEmbeddings().embed_documents(inputs)

    return {
        "object": "list", "model": body["model"],
        "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vectors)],
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }


@pytest.fixture(scope="module")
def fake_openai():

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    server = uvicorn.Server(uvicorn.Config(fake, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    while not server.started:
        time.sleep(0.05)

    yield f"http://127.0.0.1:{port}/v1"

    server.should_exit = True
    thread.join(timeout=5)


def openai_config(base_url):
    return providers.build_config({
        "llm_provider": "openai",
        "embedding_provider": "openai",
        "openai_api_key": "sk-fake-key-123456",
        "openai_base_url": base_url,
        "vision_enabled": True,
    })


def chart_png(path):
    image = Image.new("RGB", (640, 360), "white")
    draw = ImageDraw.Draw(image)
    for x, h in [(80, 120), (220, 180), (360, 260), (500, 150)]:
        draw.rectangle([x, 330 - h, x + 80, 330], fill="steelblue")
    image.save(path)


def test_openai_chat_embeddings_and_vision(fake_openai, tmp_path):

    requests_seen.clear()
    config = openai_config(fake_openai)

    assert providers.get_llm(config).invoke("Reply with the single word: ok").content == "ok"

    streamed = "".join(c.content for c in providers.get_llm(config).stream("Sources: x"))
    assert "highest revenue" in streamed

    vectors = providers.get_embeddings(config).embed_documents(["a b", "c d"])
    assert len(vectors) == 2 and len(vectors[0]) == HashEmbeddings.dims

    image_path = tmp_path / "chart.png"
    chart_png(image_path)
    description = providers.get_image_describer(config)(str(image_path))
    assert "bar chart" in description

    assert {r["auth"] for r in requests_seen} == {"Bearer sk-fake-key-123456"}
    embedding_request = next(r for r in requests_seen if r["path"] == "embeddings")
    assert embedding_request["body"]["model"] == "text-embedding-3-small"
    assert embedding_request["body"]["input"] == ["a b", "c d"]  # raw strings, no tiktoken
    vision_request = [r for r in requests_seen if "<<image>>" in _content_text(r["body"].get("messages", []))]
    assert vision_request and vision_request[0]["body"]["model"] == "gpt-4o-mini"


def test_connection_test_reports_both(fake_openai):
    results = providers.test_connection(openai_config(fake_openai))
    assert results["llm"]["ok"] and results["embedding"]["ok"]


def test_missing_key_gives_clear_error():
    config = providers.build_config({"llm_provider": "openai", "embedding_provider": "openai"})
    with pytest.raises(providers.ProviderError, match="no API key"):
        providers.get_llm(config)
    results = providers.test_connection(config)
    assert not results["llm"]["ok"] and "API key" in results["llm"]["detail"]


def test_full_app_flow_on_openai(client, alice, fake_openai, monkeypatch, tmp_path):
    """User switches to OpenAI in Settings; upload, vision and chat all go to the cloud."""

    monkeypatch.setattr(library, "get_embeddings", providers.get_embeddings)
    monkeypatch.setattr(rag_pipeline, "get_llm", providers.get_llm)
    monkeypatch.setattr(jobs, "get_image_describer", providers.get_image_describer)

    saved = client.put("/api/settings", headers=alice, json={
        "llm_provider": "openai",
        "embedding_provider": "openai",
        "openai_api_key": "sk-user-key-abcdef",
        "openai_base_url": fake_openai,
        "vision_enabled": True,
    })
    assert saved.status_code == 200

    tested = client.post("/api/settings/test", json={}, headers=alice).json()
    assert tested["llm"]["ok"] and tested["embedding"]["ok"], tested

    requests_seen.clear()

    image_path = tmp_path / "chart.png"
    chart_png(image_path)
    client.post(
        "/api/sources",
        files=[("files", ("revenue-chart.png", image_path.read_bytes(), "image/png"))],
        headers=alice,
    )

    source = client.get("/api/sources", headers=alice).json()["sources"][0]
    assert source["status"] == "ready", source
    assert source["note"] == ""

    response = client.post("/api/chat/stream", json={"question": "Which quarter had the highest revenue?"}, headers=alice)
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[0]["type"] == "conversation"
    events = events[1:]

    assert events[0]["sources"][0]["name"] == "revenue-chart.png"
    assert "bar chart" in events[0]["sources"][0]["snippet"]
    assert events[-1]["type"] == "done"
    assert "Q3 had the highest revenue" in events[-1]["answer"]

    assert {r["auth"] for r in requests_seen} == {"Bearer sk-user-key-abcdef"}
    paths = [r["path"] for r in requests_seen]
    assert "embeddings" in paths and paths.count("chat") >= 2  # vision + answer
