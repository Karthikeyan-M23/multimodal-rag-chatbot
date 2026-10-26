from pathlib import Path

from src.ingestion.pdf_processor import extract_pdf_pages
from src.ingestion.document_processor import extract_docx_content
from src.ingestion.excel_processor import extract_csv_content, extract_excel_content
from src.ingestion.image_processor import extract_image_content
from src.ingestion.audio_processor import extract_audio_content
from src.ingestion.video_processor import extract_video_content
from src.ingestion.web_processor import extract_web_content
from src.ingestion.html_processor import extract_html_content
from src.ingestion.youtube_processor import extract_youtube_content
from src.ingestion.tfs_processor import extract_tfs_work_items


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}

EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".log"}

SUPPORTED_EXTENSIONS = (
    {".pdf", ".docx", ".csv", ".html", ".htm"}
    | IMAGE_EXTENSIONS
    | AUDIO_EXTENSIONS
    | VIDEO_EXTENSIONS
    | EXCEL_EXTENSIONS
    | TEXT_EXTENSIONS
)


def file_type_for(file_path: str) -> str:

    extension = Path(file_path).suffix.lower()

    if extension in IMAGE_EXTENSIONS:
        return "image"

    if extension in AUDIO_EXTENSIONS:
        return "audio"

    if extension in VIDEO_EXTENSIONS:
        return "video"

    if extension in EXCEL_EXTENSIONS:
        return "excel"

    if extension in TEXT_EXTENSIONS:
        return "text"

    if extension in {".html", ".htm"}:
        return "html"

    return extension.lstrip(".")


def _extract_text_file(file_path: str, progress=None) -> list[dict]:

    text = Path(file_path).read_text(encoding="utf-8", errors="replace").strip()

    if not text:
        return []

    return [
        {
            "text": text,
            "metadata": {"source": file_path, "file_type": "text"},
        }
    ]


def load_document(file_path: str, describe=None, progress=None) -> list[dict]:
    """
    describe: optional image_path -> description callable (vision model).
    progress: optional message callable for long-running extraction.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    extension = path.suffix.lower()

    if extension == ".pdf":
        return extract_pdf_pages(file_path, progress)

    if extension == ".docx":
        return extract_docx_content(file_path, progress)

    if extension in EXCEL_EXTENSIONS:
        return extract_excel_content(file_path, progress)

    if extension == ".csv":
        return extract_csv_content(file_path, progress)

    if extension in IMAGE_EXTENSIONS:
        return extract_image_content(file_path, describe, progress)

    if extension in AUDIO_EXTENSIONS:
        return extract_audio_content(file_path, progress)

    if extension in VIDEO_EXTENSIONS:
        return extract_video_content(file_path, describe, progress)

    if extension in {".html", ".htm"}:
        return extract_html_content(file_path, progress)

    if extension in TEXT_EXTENSIONS:
        return _extract_text_file(file_path, progress)

    raise ValueError(f"Unsupported file type: {extension}")


def load_web_document(url: str, progress=None, username: str = "", password: str = "") -> list[dict]:
    return extract_web_content(url, progress, username, password)


def load_tfs_work_items(url: str, progress=None, username: str = "", password: str = "") -> list[dict]:
    return extract_tfs_work_items(url, username, password, progress)


def load_youtube_video(url: str, progress=None) -> list[dict]:
    return extract_youtube_content(url, progress)
