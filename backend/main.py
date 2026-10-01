from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.knowledge_base_manager import (
    get_vector_store,
)
from src.rag_pipeline import generate_answer

from pathlib import Path
from typing import List

from fastapi import UploadFile, File, Form

from src.knowledge_base import build_knowledge_base
from backend.knowledge_base_manager import set_vector_store


UPLOAD_DIR = Path("data/uploads")

app = FastAPI(
    title="Multimodal RAG API",
    version="1.0.0",
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Request models
# --------------------------------------------------

class ChatRequest(BaseModel):
    question: str


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
# Chat
# --------------------------------------------------

@app.post("/api/chat")
def chat(request: ChatRequest):

    question = request.question.strip()

    if not question:

        return {
            "answer": "Please enter a question.",
            "sources": [],
        }

    vector_store = get_vector_store()

    if vector_store is None:

        return {
            "answer": (
                "No knowledge base is available. "
                "Please process documents first."
            ),
            "sources": [],
        }

    result = generate_answer(
        vector_store,
        question,
        k=5,
    )

    sources = []

    for document in result["documents"]:

        sources.append(
            document.metadata
        )

    return {
        "answer": result["answer"],
        "sources": sources,
    }

# --------------------------------------------------
# knowledge process
# --------------------------------------------------


@app.post("/api/knowledge/process")
async def process_knowledge(
    files: List[UploadFile] = File(default=[]),
    urls: List[str] = Form(default=[]),
):

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_paths = []

    # ------------------------------------------
    # Save uploaded files
    # ------------------------------------------

    for uploaded_file in files:

        if not uploaded_file.filename:
            continue

        filename = Path(
            uploaded_file.filename
        ).name

        file_path = (
            UPLOAD_DIR / filename
        )

        content = await uploaded_file.read()

        with open(
            file_path,
            "wb",
        ) as file:

            file.write(content)

        file_paths.append(
            str(file_path)
        )

    # ------------------------------------------
    # Clean URLs
    # ------------------------------------------

    clean_urls = [
        url.strip()
        for url in urls
        if url.strip()
    ]

    # ------------------------------------------
    # Validate input
    # ------------------------------------------

    if not file_paths and not clean_urls:

        return {
            "status": "error",
            "message": (
                "No files or website URLs "
                "were provided."
            ),
        }

    # ------------------------------------------
    # Build knowledge base
    # ------------------------------------------

    try:

        result = build_knowledge_base(
            file_paths=file_paths,
            urls=clean_urls,
        )

        set_vector_store(
            result["vector_store"]
        )

        return {
            "status": "success",
            "message": (
                "Knowledge base created successfully."
            ),
            "files_processed": len(file_paths),
            "urls_processed": len(clean_urls),
            "documents_extracted": len(
                result["documents"]
            ),
            "chunks_created": len(
                result["chunks"]
            ),
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }