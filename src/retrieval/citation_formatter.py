from pathlib import Path


def format_timestamp(seconds):
    """Convert seconds into MM:SS format."""

    if seconds is None:
        return "Unknown time"

    seconds = float(seconds)

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)

    return f"{minutes:02d}:{remaining_seconds:02d}"


def format_source(metadata):
    """
    Convert source metadata into a human-readable citation.
    """

    source = metadata.get(
        "source",
        "Unknown source",
    )

    file_type = metadata.get(
        "file_type",
        "unknown",
    )

    # -----------------------------
    # PDF
    # -----------------------------

    if file_type == "pdf":

        filename = Path(source).name

        page = metadata.get(
            "page",
            "Unknown",
        )

        return f"{filename} — Page {page}"

    # -----------------------------
    # DOCX
    # -----------------------------

    if file_type == "docx":

        filename = Path(source).name

        paragraph = metadata.get(
            "paragraph",
            "Unknown",
        )

        return (
            f"{filename} — "
            f"Paragraph {paragraph}"
        )

    # -----------------------------
    # Image
    # -----------------------------

    if file_type == "image":

        filename = Path(source).name

        return filename

    # -----------------------------
    # Audio
    # -----------------------------

    if file_type == "audio":

        filename = Path(source).name

        start = format_timestamp(
            metadata.get("start_time")
        )

        end = format_timestamp(
            metadata.get("end_time")
        )

        return (
            f"{filename} — "
            f"{start}–{end}"
        )

    # -----------------------------
    # Video
    # -----------------------------

    if file_type == "video":

        filename = Path(source).name

        content_type = metadata.get(
            "content_type"
        )

        if content_type == "transcript":

            start = format_timestamp(
                metadata.get("start_time")
            )

            end = format_timestamp(
                metadata.get("end_time")
            )

            return (
                f"{filename} — "
                f"{start}–{end}"
            )

        timestamp = format_timestamp(
            metadata.get("timestamp")
        )

        return (
            f"{filename} — "
            f"Frame at {timestamp}"
        )

    # -----------------------------
    # Website
    # -----------------------------

    if file_type == "web":

        title = metadata.get(
            "title",
            "Web page",
        )

        url = metadata.get(
            "url",
            source,
        )

        return f"{title} — {url}"

    # -----------------------------
    # Fallback
    # -----------------------------

    return Path(source).name


def get_unique_citations(documents):
    """
    Create unique human-readable citations
    from retrieved documents.
    """

    citations = []

    for document in documents:

        citation = format_source(
            document.metadata
        )

        if citation not in citations:
            citations.append(citation)

    return citations