from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from src.ingestion.excel_processor import rows_to_documents


NOISE_TAGS = ["script", "style", "noscript", "template", "svg", "iframe"]

LAYOUT_TAGS = ["nav", "footer", "header", "aside", "form"]

# <summary> titles a collapsible group, so it starts a section too.
HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "summary"]

TEXT_TAGS = ["p", "li", "pre", "blockquote", "dd", "dt", "figcaption"]

BLOCK_TAGS = HEADING_TAGS + TEXT_TAGS + [
    "div", "section", "article", "main", "aside", "header", "footer",
    "nav", "details", "ul", "ol", "dl", "table", "figure", "form",
    "fieldset", "address", "hr", "br",
]

# A classed element repeated this often is treated as a data row.
MIN_RECORDS = 3

MAX_RECORD_CHARS = 1000

MAX_CHARS_PER_GROUP = 1500


def _table_documents(soup, source, file_type):

    documents = []

    for index, table in enumerate(soup.find_all("table"), start=1):

        rows = []

        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])

            if cells:
                rows.append([cell.get_text(" ", strip=True) for cell in cells])

        # Tiny layout tables read better as text.
        if len(rows) >= 2:
            for document in rows_to_documents(
                rows,
                source,
                file_type,
                sheet=f"Table {index}",
            ):
                document["metadata"]["record_type"] = "table_rows"
                documents.append(document)

            table.decompose()

    return documents


def _clean(text: str) -> str:
    return " ".join(text.split())


def _text(element) -> str:
    """
    Visible text plus tooltips. Dashboards often keep the real value in
    title="..." (e.g. "AXQA: deployed 2026-10-28 12:51") and show only
    a short label.
    """

    if isinstance(element, NavigableString):
        return "" if isinstance(element, Comment) else _clean(str(element))

    inner = " ".join(
        part for part in (_text(child) for child in element.children) if part
    )

    title = _clean(element.get("title", ""))

    # Already shown, or the label is its short form (a 7-char hash).
    if not title or title in inner or (inner and title.startswith(inner)):
        return inner

    # Empty or symbol-only ("-") labels add nothing to the tooltip.
    if not any(char.isalnum() for char in inner):
        return title

    return f"{title} ({inner})"


def _signature(element):
    return (element.name, tuple(sorted(element.get("class") or [])))


def _record_signatures(root) -> set:
    """Classed elements that repeat, like rows of a div-based grid."""

    counts = {}

    for element in root.find_all(True):
        if element.get("class"):
            key = _signature(element)
            counts[key] = counts.get(key, 0) + 1

    return {key for key, count in counts.items() if count >= MIN_RECORDS}


def _record_text(element, signatures):
    """One line per repeated element, its cells joined by ' | '."""

    if _signature(element) not in signatures:
        return None

    if len(element.get_text(" ", strip=True)) > MAX_RECORD_CHARS:
        return None

    # A titled container (a small collapsible group) is a section, not a row.
    if element.find(HEADING_TAGS):
        return None

    cells = [text for text in (_text(child) for child in element.children) if text]

    return " | ".join(cells) if len(cells) >= 2 else None


def _section_documents(root, source, file_type, title):
    """
    Split text at headings so each chunk keeps its section name. Repeated
    rows (div grids, cards) are kept whole and grouped like table rows.
    """

    signatures = _record_signatures(root)

    sections = []
    state = {"heading": ""}
    lines = []
    records = []

    def metadata(**extra):
        return {
            "source": source,
            "file_type": file_type,
            "title": title,
            "section": state["heading"],
            **extra,
        }

    def flush_records():
        prefix = f"Section: {state['heading']}\n" if state["heading"] else ""
        group = []

        def emit():
            if group:
                sections.append(
                    {
                        "text": prefix + "\n".join(group),
                        "metadata": metadata(
                            record_type="html_records",
                            # Already sized; the chunker must not split rows apart.
                            presplit=True,
                        ),
                    }
                )
                group.clear()

        for record in records:
            if group and sum(map(len, group)) + len(record) > MAX_CHARS_PER_GROUP:
                emit()
            group.append(record)

        emit()
        records.clear()

    def flush():
        text = "\n".join(lines).strip()

        if text:
            sections.append({"text": text, "metadata": metadata()})

        lines.clear()
        flush_records()

    def walk(element):
        for child in element.children:

            if isinstance(child, NavigableString):
                text = _text(child)
                if text:
                    lines.append(text)
                continue

            if not isinstance(child, Tag):
                continue

            if child.name in HEADING_TAGS:
                text = _text(child)
                if text:
                    flush()
                    state["heading"] = text
                    lines.append(text)
                continue

            if child.name in TEXT_TAGS:
                text = _text(child)
                if text:
                    lines.append(text)
                continue

            record = _record_text(child, signatures)

            if record:
                records.append(record)
                continue

            # A container holding only inline content is one line of text.
            if child.find(BLOCK_TAGS) is None:
                text = _text(child)
                if text:
                    lines.append(text)
                continue

            walk(child)

    walk(root)
    flush()

    return sections


def extract_html_from_soup(
    soup,
    source,
    file_type="html",
    fallback_title="",
    main_content_only=False,
) -> list[dict]:

    for element in soup(NOISE_TAGS):
        element.decompose()

    title = (
        soup.title.get_text(strip=True)
        if soup.title and soup.title.get_text(strip=True)
        else fallback_title
    )

    root = soup.body or soup

    if main_content_only:
        root = soup.find("article") or soup.find("main") or root

        for element in root.find_all(LAYOUT_TAGS):
            element.decompose()

    documents = _table_documents(root, source, file_type)

    for document in documents:
        document["metadata"]["title"] = title

    return _section_documents(root, source, file_type, title) + documents


def extract_html_content(file_path: str, progress=None) -> list[dict]:
    """
    Readable text from a local HTML/HTM file, split by heading, with
    tables extracted as 'Header: value' rows.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix.lower() not in {".html", ".htm"}:
        raise ValueError(f"Unsupported HTML file type: {path.suffix}")

    soup = BeautifulSoup(
        path.read_text(encoding="utf-8", errors="replace"),
        "html.parser",
    )

    return extract_html_from_soup(
        soup,
        source=str(path),
        file_type="html",
        fallback_title=path.name,
    )
