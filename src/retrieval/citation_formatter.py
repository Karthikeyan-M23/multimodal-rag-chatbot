from pathlib import Path


def format_timestamp(seconds):

    if seconds is None:
        return "Unknown time"

    seconds = int(float(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, remaining = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"

    return f"{minutes:02d}:{remaining:02d}"


def source_name(metadata) -> str:

    if metadata.get("source_name"):
        return metadata["source_name"]

    if metadata.get("file_type") == "web":
        return metadata.get("title") or metadata.get("url") or "Web page"

    return Path(str(metadata.get("source", "Unknown source"))).name


def location_label(metadata) -> str:
    """Human-readable position inside a source: page, time, rows, ..."""

    file_type = metadata.get("file_type")

    if metadata.get("page"):
        return f"Page {metadata['page']}"

    if file_type in {"excel", "csv"} or metadata.get("record_type") == "table_rows":

        sheet = metadata.get("sheet") or ""

        if metadata.get("row_start"):
            rows = (
                f"row {metadata['row_start']}"
                if metadata.get("row_start") == metadata.get("row_end")
                else f"rows {metadata['row_start']}–{metadata['row_end']}"
            )
            return f"{sheet} · {rows}" if sheet else rows.capitalize()

        return sheet

    if file_type in {"audio", "video", "youtube"}:

        if metadata.get("content_type") == "frame":
            return f"Frame at {format_timestamp(metadata.get('timestamp'))}"

        if metadata.get("start_time") is not None:
            label = (
                f"{format_timestamp(metadata.get('start_time'))}–"
                f"{format_timestamp(metadata.get('end_time'))}"
            )

            if metadata.get("chapter"):
                label += f" · {metadata['chapter']}"

            return label

    if metadata.get("section"):
        return metadata["section"]

    if file_type == "image":
        return "Image"

    return ""


def format_source(metadata) -> str:

    location = location_label(metadata)
    name = source_name(metadata)

    return f"{name} — {location}" if location else name


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
