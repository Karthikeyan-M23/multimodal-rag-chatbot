from threading import Lock

from config.settings import RERANKER_ENABLED, RERANKER_MODEL


_model = None

_lock = Lock()


def get_reranker():
    """Cross-encoder loaded once. Returns None when disabled."""

    global _model

    if not RERANKER_ENABLED:
        return None

    with _lock:
        if _model is None:
            from sentence_transformers import CrossEncoder

            _model = CrossEncoder(
                RERANKER_MODEL,
                max_length=512,
                device="cpu",
            )

    return _model


def rerank(query: str, documents: list, text_of=None, alternate_queries=None) -> list:
    """
    Scores each document against the query (0-1, higher is better),
    stores it as metadata['rerank_score'] and returns them best first.

    alternate_queries (e.g. the user's original wording before a
    follow-up rewrite) are scored too; a document keeps its best score,
    so a poor rewrite cannot bury the right passage.

    Returns the input unchanged when the reranker is disabled.
    """

    model = get_reranker()

    if model is None or not documents:
        return documents

    text_of = text_of or (lambda document: document.page_content)
    texts = [text_of(document) for document in documents]

    queries = [query] + [
        alternate
        for alternate in (alternate_queries or [])
        if alternate and alternate != query
    ]

    best = [float("-inf")] * len(documents)

    for search_query in queries:

        scores = model.predict(
            [(search_query, text) for text in texts],
            batch_size=16,
            show_progress_bar=False,
        )

        best = [max(a, float(b)) for a, b in zip(best, scores)]

    for document, score in zip(documents, best):
        document.metadata["rerank_score"] = score

    return sorted(
        documents,
        key=lambda document: document.metadata["rerank_score"],
        reverse=True,
    )
