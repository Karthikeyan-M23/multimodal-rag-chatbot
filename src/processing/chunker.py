from langchain_text_splitters import RecursiveCharacterTextSplitter


def create_chunks(documents: list[dict]) -> list[dict]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        length_function=len,
        is_separator_regex=False,
    )

    chunks = []

    for document in documents:
        document_chunks = text_splitter.split_text(document["text"])

        for chunk_index, chunk_text in enumerate(document_chunks):

            metadata = document["metadata"].copy()

            source = metadata["source"]

            chunks.append({
                "text": chunk_text,
                "metadata": {
                    **metadata,
                    "chunk_id": (
                        f"{source}"
                        f"_chunk_{chunk_index}"
                    ),
                    "chunk_index": chunk_index,
                },
            })

    return chunks