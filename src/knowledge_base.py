from pathlib import Path

from src.ingestion.loader import load_document, load_web_document
from src.processing.chunker import create_chunks
from src.embeddings.embedding_service import get_embedding_model
from src.vector.vector_store import create_vector_store, save_vector_store
from src.retrieval.bm25_retriever import BM25Retriever

def build_knowledge_base(file_paths=None, urls=None):
    file_paths = file_paths or []
    urls = urls or []

    documents = []

    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        documents.extend(
            load_document(str(path))
        )

    for url in urls:
        documents.extend(
            load_web_document(url)
        )

    if not documents:
        raise ValueError(
            "No content could be extracted from the provided sources."
        )

    chunks = create_chunks(documents)

    if not chunks:
        raise ValueError("No chunks were created.")
    
    bm25_retriever = BM25Retriever(chunks)

    embeddings = get_embedding_model()
    vector_store = create_vector_store(
        chunks,
        embeddings,
    )

    save_vector_store(vector_store)

    return {
        "vector_store": vector_store,
        "bm25_retriever": bm25_retriever,
        "documents": documents,
        "chunks": chunks,
    }
