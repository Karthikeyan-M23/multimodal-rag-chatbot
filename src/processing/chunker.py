from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import CHUNK_OVERLAP, CHUNK_SIZE


# Transcript windows: long enough to hold a complete thought, short
# enough that a citation timestamp is meaningful.
TRANSCRIPT_MAX_CHARS = 700

TRANSCRIPT_MAX_SECONDS = 45


def _splitter():

    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
    )


def _merge_transcript(segments: list[dict]) -> list[dict]:
    """
    Whisper emits one sentence per segment. Merge consecutive segments
    into windows, carrying the last segment over for continuity.
    """

    windows = []
    current = []

    def flush():
        if not current:
            return

        metadata = current[0]["metadata"].copy()
        metadata["start_time"] = current[0]["metadata"]["start_time"]
        metadata["end_time"] = current[-1]["metadata"]["end_time"]

        windows.append(
            {
                "text": " ".join(segment["text"] for segment in current),
                "metadata": metadata,
            }
        )

    for segment in segments:

        if current:
            chars = sum(len(item["text"]) for item in current) + len(segment["text"])
            seconds = (
                segment["metadata"]["end_time"]
                - current[0]["metadata"]["start_time"]
            )

            new_chapter = (
                segment["metadata"].get("chapter")
                != current[-1]["metadata"].get("chapter")
            )

            if new_chapter:
                flush()
                current = []

            elif chars > TRANSCRIPT_MAX_CHARS or seconds > TRANSCRIPT_MAX_SECONDS:
                flush()
                current = current[-1:]

        current.append(segment)

    flush()

    return windows


def create_chunks(documents: list[dict]) -> list[dict]:

    splitter = _splitter()

    chunks = []
    transcript = []

    def flush_transcript():
        chunks.extend(_merge_transcript(transcript))
        transcript.clear()

    for document in documents:

        metadata = document["metadata"].copy()
        text = document["text"].strip()

        if not text:
            continue

        if metadata.get("content_type") == "transcript":
            transcript.append({"text": text, "metadata": metadata})
            continue

        flush_transcript()

        presplit = metadata.pop("presplit", False)

        if presplit and len(text) <= CHUNK_SIZE * 2:
            chunks.append({"text": text, "metadata": metadata})
            continue

        for piece in splitter.split_text(text):
            chunks.append({"text": piece, "metadata": metadata.copy()})

    flush_transcript()

    for index, chunk in enumerate(chunks):
        chunk["metadata"]["chunk_index"] = index
        chunk["metadata"].setdefault(
            "chunk_id",
            f"{chunk['metadata'].get('source', 'unknown')}_chunk_{index}",
        )

    return chunks
