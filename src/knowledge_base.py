from pathlib import Path

from src.ingestion.loader import (
    load_document,
    load_web_document,
)

from src.processing.chunker import create_chunks

from src.embeddings.embedding_service import (
    get_embedding_model,
)

from src.vector.vector_store import (
    create_vector_store,
    save_vector_store,
)


def build_knowledge_base(
    file_paths=None,
    urls=None,
):

    file_paths = file_paths or []
    urls = urls or []

    documents = []

    # -----------------------------
    # Process uploaded files
    # -----------------------------

    for file_path in file_paths:

        path = Path(file_path)

        if not path.exists():

            raise FileNotFoundError(
                f"File not found: {file_path}"
            )

        extracted_documents = load_document(
            str(path)
        )

        documents.extend(
            extracted_documents
        )

    # -----------------------------
    # Process websites
    # -----------------------------

    for url in urls:

        extracted_documents = (
            load_web_document(url)
        )

        documents.extend(
            extracted_documents
        )

    # -----------------------------
    # Validate extracted content
    # -----------------------------

    if not documents:

        raise ValueError(
            "No content could be extracted "
            "from the provided sources."
        )

    # -----------------------------
    # Create chunks
    # -----------------------------

    chunks = create_chunks(documents)

    if not chunks:

        raise ValueError(
            "No chunks were created."
        )

    # -----------------------------
    # Create embeddings
    # -----------------------------

    embeddings = get_embedding_model()

    # -----------------------------
    # Create vector store
    # -----------------------------

    vector_store = create_vector_store(
        chunks,
        embeddings,
    )

    save_vector_store(vector_store)

    return {
        "vector_store": vector_store,
        "documents": documents,
        "chunks": chunks,
    }