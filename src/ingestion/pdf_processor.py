import pymupdf
from PIL import Image

from src.ingestion.ocr import clean_ocr_text, ocr_image


# Pages with less extractable text than this are treated as scanned.
MIN_TEXT_CHARS = 40

OCR_DPI = 200


def _ocr_page(page) -> str:

    pixmap = page.get_pixmap(dpi=OCR_DPI)

    image = Image.frombytes(
        "RGB",
        (pixmap.width, pixmap.height),
        pixmap.samples,
    )

    return clean_ocr_text(ocr_image(image))


def extract_pdf_pages(file_path: str, progress=None) -> list[dict]:

    pages = []

    with pymupdf.open(file_path) as document:

        total = len(document)

        for page_number, page in enumerate(document, start=1):

            if progress and total > 5 and page_number % 5 == 0:
                progress(f"Reading page {page_number}/{total}")

            text = page.get_text("text").strip()
            method = "text"

            if len(text) < MIN_TEXT_CHARS:
                ocr_text = _ocr_page(page)

                if len(ocr_text) > len(text):
                    text = ocr_text
                    method = "ocr"

            if not text:
                continue

            pages.append(
                {
                    "text": text,
                    "metadata": {
                        "source": file_path,
                        "file_type": "pdf",
                        "page": page_number,
                        "extraction": method,
                    },
                }
            )

    return pages
