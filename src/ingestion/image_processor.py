from pathlib import Path

from PIL import Image
import pytesseract


TESSERACT_PATH = (
    r"C:\Users\c_karthikeyanm.TPNYC.000"
    r"\AppData\Local\Tesseract-OCR\tesseract.exe"
)

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def extract_image_content(file_path: str) -> list[dict]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    image = Image.open(path)

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