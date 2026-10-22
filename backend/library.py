"""
Per-user knowledge library: a FAISS index plus BM25 over every chunk
of every source the user has added.

Chunk text and metadata live in SQLite, so the index can be rebuilt
(re-index with another embedding model) without re-extracting files.
"""

import json
import shutil
from pathlib import Path
from threading import Lock, RLock

from langchain_community.vectorstores import FAISS

from backend import database
from config import settings
from src.providers import get_embeddings, with_embedding
from src.retrieval.bm25_retriever import BM25Retriever
from src.retrieval.citation_formatter import location_label, source_name
from src.vector.vector_retriever import retrieve_documents


VECTORSTORE_ROOT = Path(settings.VECTORSTORE_DIR) / "users"

UPLOAD_ROOT = Path(settings.DATA_DIR) / "uploads" / "users"

EMBED_BATCH = 64


def search_text(chunk: dict) -> str:
    """
    Text that is embedded and keyword-indexed: the chunk prefixed with
    its source name and location, so "the budget spreadsheet" or
    "page 4" can match.
    """

    metadata = chunk["metadata"]
    header = source_name(metadata)
    location = location_label(metadata)

    if location:
        header += f" — {location}"

    return f"{header}\n{chunk['text']}"


class Library:

    def __init__(self, user_id: int):

        self.user_id = int(user_id)
        self.lock = RLock()
        self._store = None
        self._store_loaded = False
        self._bm25 = None
        self.reindexing = False
        self.reindex_error = ""

    # ------------------------------------------
    # Paths / manifest
    # ------------------------------------------

    @property
    def index_dir(self) -> Path:
        return VECTORSTORE_ROOT / str(self.user_id) / "index"

    @property
    def manifest_path(self) -> Path:
        return VECTORSTORE_ROOT / str(self.user_id) / "manifest.json"

    def signature(self) -> str | None:
        """Embedding provider:model the index was built with."""

        if not self.manifest_path.exists():
            return None

        return json.loads(self.manifest_path.read_text())["embedding"]

    def _write_manifest(self, signature: str):

        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps({"embedding": signature}))

    def index_config(self, config):
        """
        Queries and new chunks must use the embedder the index was built
        with, even if the user has since picked another one.
        """

        signature = self.signature()

        return with_embedding(config, signature) if signature else config

    # ------------------------------------------
    # Loading
    # ------------------------------------------

    def _get_store(self, config):

        with self.lock:

            if not self._store_loaded:

                if (self.index_dir / "index.faiss").exists():
                    self._store = FAISS.load_local(
                        str(self.index_dir),
                        get_embeddings(self.index_config(config)),
                        allow_dangerous_deserialization=True,
                    )

                self._store_loaded = True

            return self._store

    def _get_bm25(self):

        with self.lock:

            if self._bm25 is None:

                chunks = database.get_chunks(self.user_id)

                for chunk in chunks:
                    chunk["search_text"] = search_text(chunk)

                self._bm25 = BM25Retriever(chunks)

            return self._bm25

    def _save(self):

        if self._store is None or not self._store.index_to_docstore_id:

            shutil.rmtree(self.index_dir.parent, ignore_errors=True)
            self._store = None
            return

        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._store.save_local(str(self.index_dir))

    # ------------------------------------------
    # Writes
    # ------------------------------------------

    def _embed(self, embeddings, chunks, progress=None):

        texts = [search_text(chunk) for chunk in chunks]
        vectors = []

        for start in range(0, len(texts), EMBED_BATCH):

            if progress and len(texts) > EMBED_BATCH:
                progress(f"Embedding {start}/{len(texts)} chunks")

            vectors.extend(
                embeddings.embed_documents(texts[start:start + EMBED_BATCH])
            )

        return vectors

    def add_source(self, source_id: str, chunks: list[dict], config, progress=None):

        config = self.index_config(config)
        embeddings = get_embeddings(config)

        vectors = self._embed(embeddings, chunks, progress)

        pairs = [
            (chunk["text"], vector)
            for chunk, vector in zip(chunks, vectors)
        ]
        metadatas = [chunk["metadata"] for chunk in chunks]
        ids = [chunk["metadata"]["chunk_id"] for chunk in chunks]

        with self.lock:

            store = self._get_store(config)

            # Re-processing a source replaces its old chunks.
            old_ids = database.get_chunk_ids(self.user_id, source_id)

            if store is not None and old_ids:
                store.delete(
                    [i for i in old_ids if i in store.index_to_docstore_id.values()]
                )

            if store is None:
                self._store = FAISS.from_embeddings(
                    pairs,
                    embeddings,
                    metadatas=metadatas,
                    ids=ids,
                )
                self._write_manifest(config.embedding_signature)
            else:
                store.add_embeddings(pairs, metadatas=metadatas, ids=ids)

            self._store_loaded = True
            self._save()

            database.replace_chunks(self.user_id, source_id, chunks)
            self._bm25 = None

    def remove_source(self, source_id: str, config):

        with self.lock:

            ids = database.get_chunk_ids(self.user_id, source_id)
            store = self._get_store(config)

            if store is not None and ids:
                present = set(store.index_to_docstore_id.values())
                store.delete([i for i in ids if i in present])
                self._save()

            database.replace_chunks(self.user_id, source_id, [])
            self._bm25 = None

    def reindex(self, config, progress=None):
        """Rebuild the whole index with the user's current embedder."""

        chunks = database.get_chunks(self.user_id)
        embeddings = get_embeddings(config)

        if not chunks:
            with self.lock:
                self._store = None
                self._store_loaded = True
                self._save()
            return

        vectors = self._embed(embeddings, chunks, progress)

        store = FAISS.from_embeddings(
            [(chunk["text"], vector) for chunk, vector in zip(chunks, vectors)],
            embeddings,
            metadatas=[chunk["metadata"] for chunk in chunks],
            ids=[chunk["metadata"]["chunk_id"] for chunk in chunks],
        )

        with self.lock:
            self._store = store
            self._store_loaded = True
            self._save()
            self._write_manifest(config.embedding_signature)

    def clear(self):

        with self.lock:
            self._store = None
            self._store_loaded = True
            self._bm25 = None
            shutil.rmtree(self.index_dir.parent, ignore_errors=True)

    # ------------------------------------------
    # Search
    # ------------------------------------------

    def search(self, query: str, config, original: str | None = None, source_ids=None):
        """source_ids: optional list restricting the search to those sources."""

        store = self._get_store(config)
        bm25 = self._get_bm25()

        if store is None and not bm25.chunks:
            return []

        with self.lock:
            documents = retrieve_documents(
                store,
                query,
                expanded_queries=[original] if original and original != query else None,
                bm25_retriever=bm25,
                text_of=lambda document: search_text(
                    {"text": document.page_content, "metadata": document.metadata}
                ),
                source_ids=set(source_ids) if source_ids else None,
            )

        return documents


_libraries = {}

_libraries_lock = Lock()


def get_library(user_id: int) -> Library:

    with _libraries_lock:

        if user_id not in _libraries:
            _libraries[user_id] = Library(user_id)

        return _libraries[user_id]


def upload_dir(user_id: int, source_id: str) -> Path:
    return UPLOAD_ROOT / str(int(user_id)) / source_id
