import json
import logging
import shutil
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import database, jobs
from backend.auth import (
    create_file_token,
    get_current_user,
    router as auth_router,
    verify_file_token,
)
from backend.library import get_library, upload_dir
from backend.user_settings import get_user_config, router as settings_router
from config import settings
from src.ingestion.loader import SUPPORTED_EXTENSIONS, file_type_for
from src.ingestion.youtube_processor import watch_url, youtube_video_id
from src.providers import build_config, get_embeddings
from src.rag_pipeline import stream_answer
from src.retrieval.reranker import get_reranker


FRONTEND_DIR = Path("frontend")

UPLOAD_CHUNK_BYTES = 1024 * 1024

logging.basicConfig(level=logging.INFO)


def _warm_up():
    """Load local models in the background so the first question is not slow."""

    try:
        config = build_config()

        if config.embedding_provider == "local":
            get_embeddings(config).embed_query("warm up")

        get_reranker()

    except Exception:
        logging.exception("model warm-up failed")


@asynccontextmanager
async def lifespan(app: FastAPI):

    database.init_db()
    jobs.resume_unfinished()

    if settings.WARM_UP_MODELS:
        threading.Thread(target=_warm_up, daemon=True).start()

    yield


app = FastAPI(
    title="Multimodal RAG API",
    version="3.0.0",
    lifespan=lifespan,
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

# Auth uses a bearer token in the Authorization header, not cookies,
# so credentials are not needed for cross-origin requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(settings_router)


# --------------------------------------------------
# Request models
# --------------------------------------------------

# --------------------------------------------------
# Health
# --------------------------------------------------

@app.get("/api/health")
def health_check():

    return {
        "status": "ok",
        "service": "multimodal-rag-api",
    }


# --------------------------------------------------
# Library
# --------------------------------------------------

def _library_info(user_id: int) -> dict:

    library = get_library(user_id)
    config = get_user_config(user_id)
    signature = library.signature()

    return {
        "embedding": signature,
        "selected_embedding": config.embedding_signature,
        "reindex_suggested": bool(signature)
        and signature != config.embedding_signature,
        "reindexing": library.reindexing,
        "reindex_error": library.reindex_error,
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "max_upload_mb": settings.MAX_UPLOAD_MB,
    }


@app.get("/api/sources")
def list_sources(user=Depends(get_current_user)):

    return {
        "sources": [
            database.public_source(row)
            for row in database.list_sources(user["id"])
        ],
        "library": _library_info(user["id"]),
    }


async def _save_upload(uploaded_file: UploadFile, destination: Path) -> int:

    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    size = 0

    with open(destination, "wb") as file:

        while block := await uploaded_file.read(UPLOAD_CHUNK_BYTES):

            size += len(block)

            if size > limit:
                raise HTTPException(
                    413,
                    f"{uploaded_file.filename} is larger than "
                    f"{settings.MAX_UPLOAD_MB} MB.",
                )

            file.write(block)

    return size


@app.post("/api/sources", status_code=201)
async def add_sources(
    files: List[UploadFile] = File(default=[]),
    urls: List[str] = Form(default=[]),
    youtube: List[str] = Form(default=[]),
    user=Depends(get_current_user),
):

    user_id = user["id"]

    def split_lines(values):
        return [line.strip() for value in values for line in value.splitlines() if line.strip()]

    clean_urls = split_lines(urls)
    youtube_links = split_lines(youtube)

    # A YouTube link pasted into the website field is still a video.
    youtube_links += [url for url in clean_urls if youtube_video_id(url)]
    clean_urls = [url for url in clean_urls if not youtube_video_id(url)]

    video_ids = []

    for link in youtube_links:

        video_id = youtube_video_id(link)

        if not video_id:
            raise HTTPException(400, f"{link}: not a valid YouTube video link.")

        if video_id not in video_ids:
            video_ids.append(video_id)

    named_files = [file for file in files if file.filename]

    if not named_files and not clean_urls and not video_ids:
        raise HTTPException(400, "Add at least one file, website or YouTube link.")

    # Validate everything before saving anything.
    for uploaded_file in named_files:

        extension = Path(uploaded_file.filename).suffix.lower()

        if extension not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                400,
                f"{uploaded_file.filename}: unsupported file type.",
            )

    for url in clean_urls:
        if not url.lower().startswith(("http://", "https://")):
            raise HTTPException(400, f"{url}: URL must start with http:// or https://")

    created = []

    for uploaded_file in named_files:

        filename = Path(uploaded_file.filename).name

        source = database.create_source(
            user_id,
            "file",
            filename,
            file_type_for(filename),
            location="",
        )

        directory = upload_dir(user_id, source["id"])
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / filename

        try:
            size = await _save_upload(uploaded_file, destination)
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            database.delete_source(user_id, source["id"])
            raise

        database.update_source(
            source["id"],
            location=str(destination),
            size_bytes=size,
        )

        created.append(source["id"])

    for url in clean_urls:

        source = database.create_source(user_id, "url", url, "web", location=url)
        created.append(source["id"])

    for video_id in video_ids:

        url = watch_url(video_id)
        source = database.create_source(user_id, "youtube", url, "youtube", location=url)
        created.append(source["id"])

    for source_id in created:
        jobs.submit(user_id, source_id)

    return {
        "sources": [
            database.public_source(database.get_source(user_id, source_id))
            for source_id in created
        ]
    }


def _owned_source(user_id: int, source_id: str):

    source = database.get_source(user_id, source_id)

    if source is None:
        raise HTTPException(404, "Source not found.")

    return source


@app.delete("/api/sources/{source_id}")
async def delete_source(source_id: str, user=Depends(get_current_user)):

    user_id = user["id"]
    source = _owned_source(user_id, source_id)

    await run_in_threadpool(
        get_library(user_id).remove_source,
        source_id,
        get_user_config(user_id),
    )

    database.delete_source(user_id, source_id)

    if source["kind"] == "file":
        shutil.rmtree(upload_dir(user_id, source_id), ignore_errors=True)

    return {"status": "deleted"}


@app.post("/api/sources/{source_id}/retry")
def retry_source(source_id: str, user=Depends(get_current_user)):

    source = _owned_source(user["id"], source_id)

    if source["status"] in {"queued", "processing"}:
        raise HTTPException(409, "This source is already being processed.")

    database.update_source(source_id, status="queued", error="", progress="")
    jobs.submit(user["id"], source_id)

    return database.public_source(database.get_source(user["id"], source_id))


@app.get("/api/sources/{source_id}/link")
def source_link(source_id: str, user=Depends(get_current_user)):
    """URL the browser can put in <video src> / <img src> / a new tab."""

    source = _owned_source(user["id"], source_id)

    if source["kind"] == "url":
        return {"url": source["location"]}

    if source["kind"] == "youtube":
        return {
            "url": source["location"],
            "youtube_id": youtube_video_id(source["location"]),
        }

    token = create_file_token(user["id"], source_id)

    return {"url": f"/api/sources/{source_id}/file?access={token}"}


@app.get("/api/sources/{source_id}/file")
def source_file(source_id: str, access: str):

    user_id = verify_file_token(access, source_id)

    if user_id is None:
        raise HTTPException(401, "Link expired. Open the source again.")

    source = _owned_source(user_id, source_id)

    if source["kind"] != "file" or not Path(source["location"]).exists():
        raise HTTPException(404, "File not found.")

    return FileResponse(
        source["location"],
        filename=source["name"],
        content_disposition_type="inline",
    )


@app.post("/api/library/reindex")
def reindex_library(user=Depends(get_current_user)):

    if not jobs.submit_reindex(user["id"]):
        raise HTTPException(409, "Re-indexing is already running.")

    return _library_info(user["id"])


# --------------------------------------------------
# Conversations
# --------------------------------------------------

TITLE_CHARS = 80


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=TITLE_CHARS)
    source_ids: List[str] | None = None


def _owned_conversation(user_id: int, conversation_id: str):

    conversation = database.get_conversation(user_id, conversation_id)

    if conversation is None:
        raise HTTPException(404, "Conversation not found.")

    return conversation


def _valid_source_ids(user_id: int, source_ids) -> list[str]:
    """Keep only ids of sources this user owns."""

    if not source_ids:
        return []

    owned = {source["id"] for source in database.list_sources(user_id)}

    return [source_id for source_id in dict.fromkeys(source_ids) if source_id in owned]


@app.get("/api/conversations")
def list_conversations(user=Depends(get_current_user)):

    return {
        "conversations": [
            database.public_conversation(row)
            for row in database.list_conversations(user["id"])
        ]
    }


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user=Depends(get_current_user)):

    conversation = _owned_conversation(user["id"], conversation_id)

    return {
        **database.public_conversation(conversation),
        "messages": database.get_messages(conversation_id),
    }


@app.patch("/api/conversations/{conversation_id}")
def update_conversation(
    conversation_id: str,
    update: ConversationUpdate,
    user=Depends(get_current_user),
):

    _owned_conversation(user["id"], conversation_id)

    title = update.title.strip() if update.title is not None else None

    if title == "":
        raise HTTPException(400, "Title cannot be empty.")

    database.update_conversation(
        conversation_id,
        title=title,
        source_ids=(
            _valid_source_ids(user["id"], update.source_ids)
            if update.source_ids is not None
            else None
        ),
    )

    return database.public_conversation(
        database.get_conversation(user["id"], conversation_id)
    )


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, user=Depends(get_current_user)):

    _owned_conversation(user["id"], conversation_id)
    database.delete_conversation(user["id"], conversation_id)

    return {"status": "deleted"}


# --------------------------------------------------
# Chat
# --------------------------------------------------

class ChatRequest(BaseModel):
    question: str = Field(max_length=4000)
    conversation_id: str | None = None
    # Empty / missing = search the whole library.
    source_ids: List[str] | None = None


def _history(conversation_id: str) -> list[dict]:

    return [
        {"role": message["role"], "content": message["content"]}
        for message in database.get_messages(conversation_id, limit=6)
    ]


def _searcher(user_id: int, config, source_ids):

    library = get_library(user_id)

    def search(query, original):
        return library.search(query, config, original=original, source_ids=source_ids)

    return search


def _ready_sources(user_id: int, source_ids) -> list:

    return [
        source
        for source in database.list_sources(user_id)
        if source["status"] == "ready"
        and (not source_ids or source["id"] in source_ids)
    ]


NO_SOURCES = (
    "Your library has no processed sources yet. Add files, a website or a "
    "YouTube link from the Library tab, wait until they show Ready, then ask again."
)

NO_SELECTED_SOURCES = (
    "None of the selected sources are ready yet. Wait until they finish "
    "processing, or choose other sources."
)


def _answer_events(user_id: int, question: str, conversation_id=None, source_ids=None):
    """
    Chat events. A new conversation is created on the first question;
    the exchange is saved once the answer completes.
    """

    source_ids = _valid_source_ids(user_id, source_ids)

    if conversation_id:
        history = _history(conversation_id)
        database.update_conversation(conversation_id, source_ids=source_ids)
    else:
        history = []
        title = " ".join(question.split())
        title = title if len(title) <= TITLE_CHARS else title[: TITLE_CHARS - 1] + "…"
        conversation_id = database.create_conversation(user_id, title, source_ids)["id"]

    yield {
        "type": "conversation",
        "conversation": database.public_conversation(
            database.get_conversation(user_id, conversation_id)
        ),
    }

    def finish(answer, sources):
        database.add_message(user_id, conversation_id, "user", question)
        database.add_message(user_id, conversation_id, "assistant", answer, sources)
        database.update_conversation(conversation_id)

    if not _ready_sources(user_id, source_ids):
        message = NO_SELECTED_SOURCES if source_ids else NO_SOURCES
        yield {"type": "sources", "sources": []}
        yield {"type": "token", "text": message}
        yield {"type": "done", "answer": message}
        finish(message, [])
        return

    sources = []

    try:
        config = get_user_config(user_id)

        for event in stream_answer(
            config,
            _searcher(user_id, config, source_ids),
            question,
            history,
        ):
            if event["type"] == "sources":
                sources = event["sources"]

            if event["type"] == "done":
                sources = event.get("sources", sources)
                finish(event["answer"], sources)

            yield event

    except Exception as error:
        logging.exception("chat failed")
        yield {"type": "error", "message": str(error)[:500]}


def _events_for(request: ChatRequest, user):
    """Validates before streaming starts, so errors are real HTTP errors."""

    question = request.question.strip()

    if not question:
        raise HTTPException(400, "Please enter a question.")

    if request.conversation_id:
        _owned_conversation(user["id"], request.conversation_id)

    return _answer_events(
        user["id"],
        question,
        request.conversation_id,
        request.source_ids,
    )


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest, user=Depends(get_current_user)):
    """
    Newline-delimited JSON events:
    conversation, sources, token..., done (or error).
    """

    events = _events_for(request, user)

    return StreamingResponse(
        (json.dumps(event, default=str) + "\n" for event in events),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat")
def chat(request: ChatRequest, user=Depends(get_current_user)):
    """Non-streaming variant of /api/chat/stream."""

    answer = ""
    sources = []
    conversation = None

    for event in _events_for(request, user):

        if event["type"] == "conversation":
            conversation = event["conversation"]

        elif event["type"] == "sources":
            sources = event["sources"]

        elif event["type"] == "done":
            answer = event["answer"]
            sources = event.get("sources", sources)

        elif event["type"] == "error":
            raise HTTPException(502, event["message"])

    return {"answer": answer, "sources": sources, "conversation": conversation}


# --------------------------------------------------
# Frontend (served last so /api routes win)
# --------------------------------------------------

if FRONTEND_DIR.is_dir():

    app.mount(
        "/",
        StaticFiles(
            directory=FRONTEND_DIR,
            html=True,
        ),
        name="frontend",
    )
