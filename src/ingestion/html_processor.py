from pathlib import Path

from bs4 import BeautifulSoup

from src.ingestion.excel_processor import rows_to_documents


NOISE_TAGS = ["script", "style", "noscript", "template", "svg", "iframe"]

LAYOUT_TAGS = ["nav", "footer", "header", "aside", "form"]

HEADING_TAGS = ["h1", "h2", "h3", "h4"]


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


def _section_documents(root, source, file_type, title):
    """Split text at headings so each chunk keeps its section name."""

    sections = []
    heading = ""
    lines = []

    def flush():
        text = "\n".join(lines).strip()

        if text:
            sections.append(
                {
                    "text": text,
                    "metadata": {
                        "source": source,
                        "file_type": file_type,
                        "title": title,
                        "section": heading,
                    },
                }
            )

        lines.clear()

    for element in root.find_all(HEADING_TAGS + ["p", "li", "pre", "blockquote", "dd", "dt"]):

        # Nested matches (p inside li) would repeat text.
        if element.find_parent(["p", "li", "pre", "blockquote"]):
            continue

        text = element.get_text(" ", strip=True)

        if not text:
            continue

        if element.name in HEADING_TAGS:
            flush()
            heading = text

        lines.append(text)

    flush()

    # Pages built from divs only: fall back to all text.
    if not sections:
        text = root.get_text(separator="\n", strip=True)

        if text:
            sections.append(
                {
                    "text": text,
                    "metadata": {
                        "source": source,
                        "file_type": file_type,
                        "title": title,
                        "section": "",
                    },
                }
            )

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
