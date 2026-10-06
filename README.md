# Multimodal RAG Chatbot — HTML/CSS/JS + FastAPI

A local-first multimodal RAG chatbot with a custom ChatGPT-style frontend and FastAPI backend. The existing RAG pipeline remains the core intelligence layer, so the UI can evolve independently.

## Architecture

```text
Browser (HTML/CSS/JS)
        |
        v
FastAPI
  |--- /api/session
  |--- /api/knowledge/process
  |--- /api/knowledge/status
  |--- /api/chat
  |--- /api/knowledge/{session_id}
        |
        v
Existing RAG backend
  |
  +-- Ingestion
  |    PDF / DOCX / Image / Audio / Video / HTML / Web
  |
  +-- Processing
  |    Normalized records -> chunks + metadata
  |
  +-- Embeddings
  |    BAAI/bge-base-en-v1.5
  |
  +-- Retrieval
  |    Structured metadata filtering OR FAISS semantic search
  |
  +-- Evidence gate
  |    No sufficient evidence -> abstain
  |
  +-- Generation
       Ollama local LLM
```

## Supported sources

- PDF
- DOCX
- PNG/JPG/JPEG/WEBP OCR
- MP3/WAV/M4A/AAC/FLAC transcription
- MP4/AVI/MOV/MKV/WEBM audio transcription + frame OCR
- HTML tables and page text
- Public website URLs

## Important behavior

The current knowledge base is **replace-mode**: processing a new upload set replaces the session's previous knowledge base. Multiple files and multiple URLs can be submitted together.

The assistant follows the project's grounding rule: **No evidence -> No answer.** The LLM is used to transform retrieved evidence into a response, not as an independent source of facts.

Structured deployment-dashboard questions use exact metadata filtering. The dashboard group date is stored as `deployment_group_date`; the date inside a Git Script filename is stored separately as `script_date`.

## Setup on Windows

```powershell
cd C:\RAG_HTML_CHATBOT
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Install/run Ollama and pull the configured model:

```powershell
ollama pull llama3.2:3b
ollama serve
```

Configure `.env` from `.env.example`. For the user's existing local installation, Tesseract and FFmpeg paths may be needed:

```text
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
TESSERACT_PATH=C:\Path\to\tesseract.exe
FFMPEG_PATH=C:\Path\to\ffmpeg.exe
```

## Run

```powershell
uvicorn backend.main:app --reload
```

Open the browser at:

```text
http://127.0.0.1:8000
```

## Frontend structure

```text
frontend/
├── index.html       # page structure
├── css/style.css    # all visual styling
└── js/
    ├── api.js       # HTTP calls to FastAPI
    └── app.js       # chat, upload, state, UI behavior
```

## Backend structure

```text
backend/
└── main.py          # FastAPI routes + per-session KB state
```

The RAG modules remain under `src/`, so the frontend is not coupled to ingestion, embeddings, retrieval, or generation internals.

## API examples

Health:

```text
GET /api/health
```

Create session:

```text
POST /api/session
```

Process knowledge base:

```text
POST /api/knowledge/process
multipart/form-data:
  session_id=<id>
  urls=<one URL per line>
  files=<one or more files>
```

Chat:

```json
POST /api/chat
{
  "session_id": "...",
  "question": "Under 20260929 which files are executed in AXQA?"
}
```

## Future extensions

1. SSE/WebSocket streaming for token-by-token responses.
2. Persistent sessions instead of in-memory state.
3. Better conversational query rewriting for structured follow-ups such as “what about TPQA?”.
4. Optional reranking.
5. Neo4j/Graphiti graph retrieval as an additive retrieval path.
6. OpenAI provider behind the same generation interface.
7. Authentication and multi-user isolation for deployment.
