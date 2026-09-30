from langchain_community.vectorstores import FAISS


def retrieve_documents(
    vector_store: FAISS,
    query: str,
    k: int = 5,
):
    """
    Retrieve documents along with their FAISS distance scores.
    """

    results = vector_store.similarity_search_with_score(
        query,
        k=k,
    )

    documents = []

    for document, score in results:
        document.metadata["distance_score"] = float(score)
        documents.append(document)

    return documents