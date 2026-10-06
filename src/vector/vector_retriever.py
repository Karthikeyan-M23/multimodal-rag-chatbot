from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document


RRF_K = 60


def _get_chunk_id(document):
    return document.metadata.get(
        "chunk_id",
        document.page_content,
    )


def _retrieve_faiss(
    vector_store,
    query,
    k,
):
    results = vector_store.similarity_search_with_score(
        query,
        k=k,
    )

    documents = []

    for rank, (document, score) in enumerate(results, start=1):

        metadata = document.metadata.copy()

        metadata["distance_score"] = float(score)
        metadata["retrieval_query"] = query
        metadata["retrieval_method"] = "faiss"
        metadata["faiss_rank"] = rank

        document.metadata = metadata

        documents.append(document)

    return documents


def _retrieve_bm25(
    bm25_retriever,
    query,
    k,
):
    results = bm25_retriever.retrieve(
        query,
        k=k,
    )

    documents = []

    for rank, result in enumerate(results, start=1):

        metadata = result["metadata"].copy()

        metadata["retrieval_query"] = query
        metadata["retrieval_method"] = "bm25"
        metadata["bm25_rank"] = rank

        document = Document(
            page_content=result["text"],
            metadata=metadata,
        )

        documents.append(document)

    return documents


def _rrf_score(rank):
    return 1.0 / (RRF_K + rank)


def retrieve_documents(
    vector_store: FAISS,
    query: str,
    k: int = 5,
    expanded_queries: list[str] | None = None,
    bm25_retriever=None,
):
    """
    Hybrid retrieval using:

    1. Original query
    2. Expanded queries
    3. FAISS semantic search
    4. BM25 keyword search
    5. Reciprocal Rank Fusion (RRF)

    Lower FAISS distance is better.
    Higher BM25 score is better.

    RRF avoids directly comparing those incompatible
    score scales.
    """

    queries = [query]

    if expanded_queries:
        for expanded_query in expanded_queries:
            if expanded_query.strip() and expanded_query not in queries:
                queries.append(expanded_query)

    candidate_documents = {}

    for search_query in queries:

        # ---------------------------------------------------------
        # FAISS
        # ---------------------------------------------------------

        faiss_documents = _retrieve_faiss(
            vector_store,
            search_query,
            k,
        )

        for document in faiss_documents:

            chunk_id = _get_chunk_id(document)

            entry = candidate_documents.setdefault(
                chunk_id,
                {
                    "document": document,
                    "rrf_score": 0.0,
                    "faiss_hits": 0,
                    "bm25_hits": 0,
                    "best_faiss_distance": float("inf"),
                    "best_bm25_score": 0.0,
                },
            )

            rank = document.metadata["faiss_rank"]

            entry["rrf_score"] += _rrf_score(rank)
            entry["faiss_hits"] += 1

            entry["best_faiss_distance"] = min(
                entry["best_faiss_distance"],
                document.metadata["distance_score"],
            )


        # ---------------------------------------------------------
        # BM25
        # ---------------------------------------------------------

        if bm25_retriever:

            bm25_documents = _retrieve_bm25(
                bm25_retriever,
                search_query,
                k,
            )

            for document in bm25_documents:

                chunk_id = _get_chunk_id(document)

                entry = candidate_documents.setdefault(
                    chunk_id,
                    {
                        "document": document,
                        "rrf_score": 0.0,
                        "faiss_hits": 0,
                        "bm25_hits": 0,
                        "best_faiss_distance": float("inf"),
                        "best_bm25_score": 0.0,
                    },
                )

                rank = document.metadata["bm25_rank"]

                entry["rrf_score"] += _rrf_score(rank)
                entry["bm25_hits"] += 1

                entry["best_bm25_score"] = max(
                    entry["best_bm25_score"],
                    document.metadata.get(
                        "bm25_score",
                        0.0,
                    ),
                )


    # -------------------------------------------------------------
    # Build final documents
    # -------------------------------------------------------------

    documents = []

    for entry in candidate_documents.values():

        document = entry["document"]

        metadata = document.metadata.copy()

        metadata["rrf_score"] = entry["rrf_score"]
        metadata["faiss_hits"] = entry["faiss_hits"]
        metadata["bm25_hits"] = entry["bm25_hits"]
        metadata["best_faiss_distance"] = (
            entry["best_faiss_distance"]
        )
        metadata["best_bm25_score"] = (
            entry["best_bm25_score"]
        )

        document.metadata = metadata

        documents.append(document)


    # -------------------------------------------------------------
    # Highest RRF score = best combined result
    # -------------------------------------------------------------

    documents.sort(
        key=lambda document:
            document.metadata.get(
                "rrf_score",
                0.0,
            ),
        reverse=True,
    )


    return documents[:k]