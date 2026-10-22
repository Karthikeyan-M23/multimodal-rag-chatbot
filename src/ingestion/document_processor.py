from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def _iter_blocks(document):
    """Paragraphs and tables in document order."""

    for child in document.element.body.iterchildren():

        if child.tag.endswith("}p"):
            yield Paragraph(child, document)

        elif child.tag.endswith("}tbl"):
            yield Table(child, document)


def _table_text(table) -> str:

    rows = [
        [cell.text.strip() for cell in row.cells]
        for row in table.rows
    ]

    if not rows:
        return ""

    header = [
        name or f"Column {index + 1}"
        for index, name in enumerate(rows[0])
    ]

    lines = []

    for row in rows[1:]:
        pairs = [
            f"{name}: {value}"
            for name, value in zip(header, row)
            if value
        ]

        if pairs:
            lines.append(" | ".join(pairs))

    if not lines:
        return " | ".join(header)

    return "\n".join(lines)


def extract_docx_content(file_path: str, progress=None) -> list[dict]:
    """
    One document per section (text under a heading), so chunks keep
    their heading as context. Tables become 'Header: value' rows.
    """

    document = Document(file_path)

    sections = []
    state = {"heading": "", "start": 1}
    buffer = []
    paragraph_number = 0

    def flush():
        text = "\n".join(buffer).strip()

        if text:
            sections.append(
                {
                    "text": text,
                    "metadata": {
                        "source": file_path,
                        "file_type": "docx",
                        "section": state["heading"],
                        "paragraph": state["start"],
                    },
                }
            )

        buffer.clear()

    for block in _iter_blocks(document):

        if isinstance(block, Table):
            text = _table_text(block)

            if text:
                buffer.append(text)

            continue

        paragraph_number += 1
        text = block.text.strip()

        if not text:
            continue

        style = (block.style.name or "").lower() if block.style else ""

        if style.startswith("heading") or style == "title":
            flush()
            state["heading"] = text
            state["start"] = paragraph_number

        buffer.append(text)

    flush()

    return sections
