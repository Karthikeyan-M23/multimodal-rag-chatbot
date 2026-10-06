from pathlib import Path


def format_timestamp(seconds):
    if seconds is None:
        return "Unknown time"

    seconds = float(seconds)
    minutes = int(seconds // 60)
    remaining = int(seconds % 60)

    return f"{minutes:02d}:{remaining:02d}"


def format_source(metadata):
    source = metadata.get("source", "Unknown source")
    file_type = metadata.get("file_type", "unknown")

    if file_type == "pdf":
        return (
            f"{Path(source).name} — "
            f"Page {metadata.get('page', 'Unknown')}"
        )

    if file_type == "docx":
        return (
            f"{Path(source).name} — "
            f"Paragraph {metadata.get('paragraph', 'Unknown')}"
        )

    if file_type == "image":
        return Path(source).name

    if file_type == "audio":
        return (
            f"{Path(source).name} — "
            f"{format_timestamp(metadata.get('start_time'))}–"
            f"{format_timestamp(metadata.get('end_time'))}"
        )

    if file_type == "video":
        if metadata.get("content_type") == "transcript":
            return (
                f"{Path(source).name} — "
                f"{format_timestamp(metadata.get('start_time'))}–"
                f"{format_timestamp(metadata.get('end_time'))}"
            )

        return (
            f"{Path(source).name} — Frame at "
            f"{format_timestamp(metadata.get('timestamp'))}"
        )

    if file_type == "web":
        return (
            f"{metadata.get('title', 'Web page')} — "
            f"{metadata.get('url', source)}"
        )

    if file_type == "html":
        if metadata.get("record_type") == "html_table_row":
            return (
                f"{Path(source).name} — "
                f"{metadata.get('git_script', 'table row')}"
            )
        return f"{metadata.get('title', Path(source).name)} — {source}"

    return Path(source).name


def get_unique_citations(documents):
    citations = []

    for document in documents:
        if hasattr(document, "metadata"):
            metadata = document.metadata
        else:
            metadata = document.get("metadata", {})

        citation = format_source(metadata)

        if citation not in citations:
            citations.append(citation)

    return citations
