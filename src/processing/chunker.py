from langchain_text_splitters import RecursiveCharacterTextSplitter


def create_chunks(documents: list[dict]) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        length_function=len,
        is_separator_regex=False,
    )

    chunks = []

    for document in documents:
        text = document["text"]
        metadata = document["metadata"].copy()

        if metadata.get("record_type") == "html_table_row":
            source = metadata.get("source", "unknown")
            table_index = metadata.get("table_index", 0)
            row_index = metadata.get("row_index", 0)

            chunks.append(
                {
                    "text": text,
                    "metadata": {
                        **metadata,
                        "chunk_id": (
                            f"{source}_table_{table_index}"
                            f"_row_{row_index}"
                        ),
                        "chunk_index": row_index,
                    },
                }
            )
            continue

        for chunk_index, chunk_text in enumerate(
            splitter.split_text(text)
        ):
            source = metadata.get("source", "unknown")

            chunks.append(
                {
                    "text": chunk_text,
                    "metadata": {
                        **metadata,
                        "chunk_id": f"{source}_chunk_{chunk_index}",
                        "chunk_index": chunk_index,
                    },
                }
            )

    return chunks
