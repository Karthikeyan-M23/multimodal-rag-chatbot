from pathlib import Path
from urllib.parse import urlparse

from src.ingestion.pdf_processor import extract_pdf_pages
from src.ingestion.document_processor import extract_docx_content
from src.ingestion.image_processor import extract_image_content
from src.ingestion.audio_processor import extract_audio_content
from src.ingestion.video_processor import extract_video_content
from src.ingestion.web_processor import extract_web_content


def load_document(file_path: str) -> list[dict]:

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    extension = path.suffix.lower()

    if extension == ".pdf":

        return extract_pdf_pages(file_path)

    elif extension == ".docx":

        return extract_docx_content(file_path)

    elif extension in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }:

        return extract_image_content(file_path)

    elif extension in {
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".flac",
    }:

        return extract_audio_content(file_path)

    elif extension in {
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".webm",
    }:

        return extract_video_content(file_path)

    else:

        raise ValueError(
            f"Unsupported file type: {extension}"
        )


def load_web_document(url: str) -> list[dict]:

    return extract_web_content(url)