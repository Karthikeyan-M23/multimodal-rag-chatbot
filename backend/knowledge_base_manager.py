from pathlib import Path

from src.embeddings.embedding_service import (
    get_embedding_model,
)

from src.vector.vector_store import (
    load_vector_store,
)


VECTORSTORE_PATH = "vectorstore/current_index"


_vector_store = None


def get_vector_store():

    global _vector_store

    if _vector_store is not None:
        return _vector_store

    index_path = Path(VECTORSTORE_PATH)

    if not index_path.exists():
        return None

    embeddings = get_embedding_model()

    _vector_store = load_vector_store(
        embeddings,
        path=VECTORSTORE_PATH,
    )

    return _vector_store


def set_vector_store(vector_store):

    global _vector_store

    _vector_store = vector_store


def clear_vector_store():

    global _vector_store

    _vector_store = None