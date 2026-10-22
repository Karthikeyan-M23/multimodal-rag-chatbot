from langchain_core.documents import Document

from config import settings
from src.retrieval.reranker import get_reranker, rerank


RRF_K = 60


def _chunk_id(document):
    return document.metadata.get("chunk_id", document.page_content)


def _rrf(rank):
    return 1.0 / (RRF_K + rank)


def hybrid_search(
    vector_store,
    query: str,
    bm25_retriever=None,
    expanded_queries=None,
    candidates: int | None = None,
    source_ids=None,
) -> list[Document]:
    """
    Vector (FAISS) + keyword (BM25) search fused with Reciprocal Rank
    Fusion. RRF avoids comparing FAISS distances with BM25 scores, which
    live on unrelated scales. Returns fused candidates, best first.

    source_ids: optional set restricting results to those sources.
    """

    candidates = candidates or settings.RETRIEVAL_CANDIDATES

    vector_options = {}

    if source_ids:
        # FAISS filters after fetching, so fetch enough to survive it.
        vector_options = {
            "filter": lambda metadata: metadata.get("source_id") in source_ids,
            "fetch_k": max(candidates * 20, len(vector_store.index_to_docstore_id))
            if vector_store is not None
            else 0,
        }

    queries = [query] + [
        extra
        for extra in (expanded_queries or [])
        if extra.strip() and extra != query
    ]

    pool = {}

    def add(document, rank, method):

        entry = pool.setdefault(
            _chunk_id(document),
            {"document": document, "rrf": 0.0, "methods": set()},
        )

        entry["rrf"] += _rrf(rank)
        entry["methods"].add(method)

        metadata = entry["document"].metadata

        if "distance_score" in document.metadata:
            metadata["distance_score"] = min(
                metadata.get("distance_score", float("inf")),
                document.metadata["distance_score"],
            )

        if "bm25_score" in document.metadata:
            metadata["bm25_score"] = max(
                metadata.get("bm25_score", 0.0),
                document.metadata["bm25_score"],
            )

    for search_query in queries:

        if vector_store is not None:

            results = vector_store.similarity_search_with_score(
                search_query,
                k=candidates,
                **vector_options,
            )

            for rank, (document, distance) in enumerate(results, start=1):
                document.metadata = {
                    **document.metadata,
                    "distance_score": float(distance),
                }
                add(document, rank, "vector")

        if bm25_retriever is not None:

            for rank, result in enumerate(
                bm25_retriever.retrieve(search_query, k=candidates, source_ids=source_ids),
                start=1,
            ):
                add(
                    Document(
                        page_content=result["text"],
                        metadata=result["metadata"],
                    ),
                    rank,
                    "keyword",
                )

    documents = []

    for entry in pool.values():

        document = entry["document"]
        document.metadata["rrf_score"] = entry["rrf"]
        document.metadata["retrieval_method"] = "+".join(sorted(entry["methods"]))
        documents.append(document)

    documents.sort(
        key=lambda document: document.metadata["rrf_score"],
        reverse=True,
    )

    return documents


def select_evidence(documents: list[Document], limit: int | None = None) -> list[Document]:
    """Keep only chunks that are actually relevant to the question."""

    limit = limit or settings.CONTEXT_CHUNKS

    if documents and "rerank_score" in documents[0].metadata:

        cutoff = max(
            settings.RERANK_MIN_SCORE,
            documents[0].metadata["rerank_score"] * settings.RERANK_RELATIVE_CUTOFF,
        )

        selected = [
            document
            for document in documents
            if document.metadata["rerank_score"] >= cutoff
        ][:limit]

        if selected:
            return selected

        # Cross-encoders under-score long passages that mix topics (e.g. a
        # meeting transcript). If vector and keyword search agree on a
        # passage that contains a distinctive query term, let the LLM judge.
        return [
            document
            for document in documents
            if "keyword" in document.metadata.get("retrieval_method", "")
            and "vector" in document.metadata.get("retrieval_method", "")
            and document.metadata.get("bm25_score", 0.0) >= settings.KEYWORD_RESCUE_SCORE
        ][:2]

    # Without a reranker: close vector matches, or strong keyword matches.
    selected = [
        document
        for document in documents
        if document.metadata.get("distance_score", float("inf"))
        <= settings.MAX_VECTOR_DISTANCE
        or "keyword" in document.metadata.get("retrieval_method", "")
        and "vector" in document.metadata.get("retrieval_method", "")
    ]

    return selected[:limit]


def retrieve_documents(
    vector_store,
    query: str,
    k: int | None = None,
    expanded_queries=None,
    bm25_retriever=None,
    text_of=None,
    source_ids=None,
) -> list[Document]:
    """Hybrid search, cross-encoder rerank, relevance filter."""

    documents = hybrid_search(
        vector_store,
        query,
        bm25_retriever=bm25_retriever,
        expanded_queries=expanded_queries,
        source_ids=source_ids,
    )

    if get_reranker() is not None:
        documents = rerank(
            query,
            documents[: settings.RERANK_CANDIDATES],
            text_of=text_of,
            alternate_queries=expanded_queries,
        )

    return select_evidence(documents, limit=k)
