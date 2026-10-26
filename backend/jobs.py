"""
Background ingestion. One worker: extraction (Whisper, OCR, vision)
and local embedding are CPU-bound, so running them in parallel only
makes every job slower.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend import crypto, database
from backend.library import get_library
from backend.user_settings import get_user_config
from src.ingestion.loader import (
    load_document,
    load_tfs_work_items,
    load_web_document,
    load_youtube_video,
)
from src.processing.chunker import create_chunks
from src.providers import get_image_describer


logger = logging.getLogger("rag.jobs")

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")

# Minimum seconds between progress writes for one source.
PROGRESS_INTERVAL = 0.75


def source_credentials(source) -> dict:
    """{"username", "password"} for a protected URL source, else {}."""

    if not source["auth_enc"]:
        return {}

    try:
        return json.loads(crypto.decrypt(source["auth_enc"]) or "{}")
    except ValueError:
        return {}


def _progress_writer(source_id: str):

    last = {"time": 0.0}

    def write(message: str):

        now = time.monotonic()

        if now - last["time"] >= PROGRESS_INTERVAL:
            database.update_source(source_id, progress=message[:200])
            last["time"] = now

    return write


def _safe_describer(config, notes: list):
    """
    Vision failures (model missing, rate limit) should not fail the whole
    source: fall back to OCR and record a note instead.
    """

    try:
        describe = get_image_describer(config)
    except Exception as error:
        notes.append(f"Vision unavailable: {error}")
        return None

    if describe is None:
        return None

    state = {"failed": False}

    def safe(image_path: str) -> str:

        if state["failed"]:
            return ""

        try:
            return describe(image_path)
        except Exception as error:
            state["failed"] = True
            notes.append(f"Vision unavailable, used OCR only: {str(error)[:200]}")
            logger.warning("vision failed: %s", error)
            return ""

    return safe


def process_source(user_id: int, source_id: str):

    source = database.get_source(user_id, source_id)

    # Deleted while waiting in the queue.
    if source is None:
        return

    database.update_source(
        source_id,
        status="processing",
        progress="Starting",
        error="",
        note="",
    )

    progress = _progress_writer(source_id)
    notes = []

    try:
        config = get_user_config(user_id)
        library = get_library(user_id)

        credentials = source_credentials(source)

        if source["kind"] == "url":
            documents = load_web_document(source["location"], progress, **credentials)
        elif source["kind"] == "tfs":
            documents = load_tfs_work_items(source["location"], progress, **credentials)
        elif source["kind"] == "youtube":
            documents = load_youtube_video(source["location"], progress)
        else:
            describe = None

            if source["file_type"] in {"image", "video"}:
                describe = _safe_describer(config, notes)

            progress("Extracting content")
            documents = load_document(source["location"], describe, progress)

        if not documents:
            raise ValueError(
                "No text could be extracted from this source."
            )

        name = source["name"]

        # Use the page / video title as the display name.
        if source["kind"] in {"url", "youtube", "tfs"} and documents[0]["metadata"].get("title"):
            name = documents[0]["metadata"]["title"][:200]
            database.update_source(source_id, name=name)

        for document in documents:
            document["metadata"].update(
                source_id=source_id,
                source_name=name,
            )

            # Never expose server paths to the browser.
            if source["kind"] == "file":
                document["metadata"]["source"] = name

        chunks = create_chunks(documents)

        for index, chunk in enumerate(chunks):
            chunk["metadata"]["chunk_id"] = f"{source_id}-{index}"

        if database.get_source(user_id, source_id) is None:
            return

        progress(f"Indexing {len(chunks)} chunks")
        library.add_source(source_id, chunks, config, progress)

        # Deleted while processing: undo.
        if database.get_source(user_id, source_id) is None:
            library.remove_source(source_id, config)
            return

        database.update_source(
            source_id,
            status="ready",
            progress="",
            chunk_count=len(chunks),
            note=" ".join(dict.fromkeys(notes))[:500],
        )

    except Exception as error:

        logger.exception("processing failed for %s", source_id)

        database.update_source(
            source_id,
            status="failed",
            progress="",
            error=str(error)[:500] or error.__class__.__name__,
        )


def submit(user_id: int, source_id: str):
    _executor.submit(process_source, user_id, source_id)


def submit_reindex(user_id: int):

    library = get_library(user_id)

    if library.reindexing:
        return False

    library.reindexing = True
    library.reindex_error = ""

    def run():
        try:
            library.reindex(get_user_config(user_id))
        except Exception as error:
            logger.exception("reindex failed for user %s", user_id)
            library.reindex_error = str(error)[:300]
        finally:
            library.reindexing = False

    _executor.submit(run)

    return True


def resume_unfinished():
    """Requeue work interrupted by a restart."""

    for source in database.unfinished_sources():

        if source["kind"] == "file" and not Path(source["location"]).exists():
            database.update_source(
                source["id"],
                status="failed",
                error="Uploaded file is missing. Please upload it again.",
            )
            continue

        database.update_source(source["id"], status="queued", progress="")
        submit(source["user_id"], source["id"])
