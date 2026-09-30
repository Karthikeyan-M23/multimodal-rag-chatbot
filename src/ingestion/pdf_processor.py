import pymupdf


def extract_pdf_pages(file_path: str) -> list[dict]:
    """
    Extract text from each PDF page while preserving
    source and page metadata.
    """

    document = pymupdf.open(file_path)

    pages = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text("text").strip()

        if not text:
            continue

        pages.append(
            {
                "text": text,
                "metadata": {
                    "source": file_path,
                    "file_type": "pdf",
                    "page": page_number,
                },
            }
        )

    document.close()

    return pages