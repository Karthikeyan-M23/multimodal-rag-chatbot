# Multimodal RAG

A multi-user knowledge assistant. Upload PDFs, Word, Excel/CSV, images, audio, video, HTML, websites or YouTube videos, then ask questions. Answers are grounded only in your sources and cite the exact page, sheet rows, timestamp or section.

Runs fully local (Ollama + local embeddings) or on OpenAI (or any OpenAI-compatible API). Each user chooses in **Settings**.

## Features

- **Sources**: PDF (scanned pages are OCR'd), DOCX (sections + tables), XLSX/CSV, images (OCR + vision description), audio (Whisper transcript), video (transcript + keyframe OCR/description), HTML, websites (including linked PDFs), YouTube (captions with timestamps and chapters; falls back to downloading and transcribing the audio), TXT/MD.
- **Retrieval**: hybrid vector (FAISS) + keyword (BM25) search, reciprocal rank fusion, cross-encoder reranking (`BAAI/bge-reranker-base`), relevance cutoff that refuses to answer from unrelated passages. Follow-up questions ("what is its budget?") are rewritten before searching.
- **Answers**: streamed token by token with numbered citations `[n]`. Clicking a citation opens the passage, and plays audio/video/YouTube from the cited timestamp or opens a PDF at the page.
- **Library**: per-user, additive. Sources are processed in the background with live status, and can be removed or retried.
- **Chats**: separate conversations, grouped by date, each with its own history. Each chat can be limited to chosen sources ("Search in" picker under the message box); the choice is remembered per chat.
- **Accounts**: registration and login (bcrypt + JWT). Each user's sources, index, chat history and settings are private.
- **Providers**: `.env` sets the defaults; each user can switch answer model, embeddings and vision between local and OpenAI. Their API key is stored encrypted.

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) for local mode: `ollama pull llama3.2:3b` and, for image understanding, `ollama pull qwen2.5vl:3b`
- [FFmpeg](https://ffmpeg.org) for audio/video
- [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) for OCR

Local embedding, reranker and Whisper models download automatically on first use (~1.6 GB total).

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then edit as needed
```

## Run

```powershell
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000, create an account, add sources, ask questions.

## Using OpenAI

Either set it for everyone in `.env`:

```text
LLM_PROVIDER=openai
EMBEDDING_PROVIDER=openai      # optional; "local" keeps retrieval on this machine
OPENAI_API_KEY=sk-...
```

or let each user pick **OpenAI** in Settings and paste their own key. `OPENAI_BASE_URL` points it at any OpenAI-compatible endpoint (Azure OpenAI gateway, LiteLLM, vLLM, LM Studio).

Embeddings and the index must match: after switching the embedding provider, the library shows a **Re-index** prompt. Until you re-index, search keeps using the embedder the index was built with, so nothing breaks.

## Storage

Everything is stored under `DATA_DIR` (default `data/`: database, uploads, generated secrets) and `VECTORSTORE_DIR` (default `vectorstore/`). Back these up. Point them elsewhere to run a second instance without sharing data:

```powershell
$env:DATA_DIR="D:\rag-test\data"; $env:VECTORSTORE_DIR="D:\rag-test\vectorstore"
ag-test\data"; $env:VECTORSTORE_DIR="D:
ag-testectorstore"
uvicorn backend.main:app --port 8010
```

Databases from older versions are upgraded automatically; earlier chat history appears as "Earlier chat".

## Performance notes

On CPU, a local 3B model needs roughly 10–25 s before the first token appears. Most of that is the model reading the evidence. Ways to speed it up:

- Use OpenAI (typically 1–2 s to the first token), or a GPU for Ollama.
- Lower `MAX_CONTEXT_CHARS` or `CONTEXT_CHUNKS`.

Video and image descriptions with `qwen2.5vl:3b` take about 15–60 s per image on CPU. `VIDEO_VISION_FRAMES` caps how many frames get a description; the rest use OCR only.

## Project structure

```text
backend/
  main.py            API routes, chat streaming, file links
  auth.py            register / login / tokens
  user_settings.py   per-user provider settings (/api/settings)
  library.py         per-user FAISS + BM25 index; add / remove / re-index
  jobs.py            background ingestion queue
  database.py        SQLite: users, sources, chunks, messages, settings
  crypto.py          encryption for saved API keys
src/
  providers.py       Ollama / OpenAI chat, embeddings, vision
  ingestion/         one extractor per format
  processing/        chunking (transcript windows, row groups, text splits)
  retrieval/         BM25, reranker, citations
  vector/            hybrid search + evidence selection
  rag_pipeline.py    query rewrite -> retrieve -> cited, streamed answer
frontend/            index.html, css/style.css, js/app.js, js/markdown.js
tests/               pytest suite (no models or network needed)
```

## Tests

```powershell
python -m pytest tests
```

The suite uses deterministic fake embeddings and a fake LLM, and runs the real OpenAI client against a local fake OpenAI server. It needs no models, keys or network access.

## API

All routes except health, register and login need `Authorization: Bearer <token>`.

```text
POST   /api/auth/register | /api/auth/login     {"username","password"}
GET    /api/auth/me
GET    /api/sources                             library + processing status
POST   /api/sources                             multipart: files=..., urls=..., youtube=...
DELETE /api/sources/{id}
POST   /api/sources/{id}/retry
GET    /api/sources/{id}/link                   short-lived URL to the original file
POST   /api/library/reindex
POST   /api/chat/stream                         NDJSON: sources, token..., done | error
POST   /api/chat                                same, non-streaming
                                         body: {question, conversation_id?, source_ids?}
GET    /api/conversations
GET    /api/conversations/{id}                  messages + saved source scope
PATCH  /api/conversations/{id}                  {title?, source_ids?}
DELETE /api/conversations/{id}
GET    /api/settings | PUT /api/settings | POST /api/settings/test
```

## Security notes

- Passwords: bcrypt. Sessions: JWT (`JWT_SECRET`, 8 h by default).
- Saved API keys: encrypted with `APP_ENCRYPTION_KEY` (or `DATA_DIR/.encryption_key`). They are never returned to the browser.
- Website sources cannot reach localhost or private networks unless `ALLOW_PRIVATE_URLS=true`.
- Not yet included: login rate limiting, and restricting which `OPENAI_BASE_URL` users may set. Add both before exposing the app to untrusted users. Serve behind HTTPS.
