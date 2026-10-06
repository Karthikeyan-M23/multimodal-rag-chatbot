MAX_DISTANCE = 0.75


def validate_evidence(
    documents,
    min_documents=1,
    max_distance=MAX_DISTANCE,
):
    if not documents:
        return {
            "sufficient": False,
            "reason": "No relevant evidence was retrieved.",
        }

    valid_documents = [
        document
        for document in documents
        if document.page_content.strip()
    ]

    if not valid_documents:
        return {
            "sufficient": False,
            "reason": "Retrieved evidence contains no usable content.",
        }

    relevant_documents = [
        document
        for document in valid_documents
        if document.metadata.get(
            "distance_score",
            float("inf"),
        ) <= max_distance
    ]

    if len(relevant_documents) < min_documents:
        return {
            "sufficient": False,
            "reason": "Retrieved evidence is not sufficiently relevant.",
        }

    return {
        "sufficient": True,
        "reason": "Sufficient relevant evidence retrieved.",
        "relevant_documents": relevant_documents,
    }
