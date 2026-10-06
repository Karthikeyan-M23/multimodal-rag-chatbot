import pymupdf


def extract_pdf_pages(file_path: str) -> list[dict]:
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
