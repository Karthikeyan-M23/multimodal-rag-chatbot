from pathlib import Path
import os

from PIL import Image
import pytesseract


# Use the Tesseract executable from the current Windows user's
# LOCALAPPDATA directory.
TESSERACT_PATH = Path(
    os.environ.get("LOCALAPPDATA", "")
) / "Tesseract-OCR" / "tesseract.exe"

if TESSERACT_PATH.exists():
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_PATH)


def extract_image_content(file_path: str) -> list[dict]:
    image = Image.open(file_path)

    text = pytesseract.image_to_string(image).strip()

    if not text:
        return []

    return [
        {
            "text": text,
            "metadata": {
                "source": file_path,
                "file_type": "image",
            },
        }
    ]