def normalize_document(
    text: str,
    metadata: dict,
) -> dict:

    return {
        "text": text.strip(),
        "metadata": metadata,
    }