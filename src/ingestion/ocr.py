import os
from pathlib import Path

import pytesseract
from PIL import Image

from config.settings import TESSERACT_PATH


def _configure():

    candidates = [
        TESSERACT_PATH,
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Tesseract-OCR" / "tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    ]

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = candidate
            return


_configure()


def ocr_image(image) -> str:
    """OCR a PIL image or image path. Returns '' if Tesseract is missing."""

    try:
        if not isinstance(image, Image.Image):
            with Image.open(image) as opened:
                return pytesseract.image_to_string(opened.convert("RGB")).strip()

        return pytesseract.image_to_string(image.convert("RGB")).strip()

    except pytesseract.TesseractNotFoundError:
        return ""


def clean_ocr_text(text: str) -> str:
    """Drop OCR noise lines (stray symbols) that hurt retrieval."""

    lines = []

    for line in text.splitlines():
        line = line.strip()
        alnum = sum(character.isalnum() for character in line)

        if alnum >= 2 and alnum / max(len(line), 1) > 0.4:
            lines.append(line)

    return "\n".join(lines)
