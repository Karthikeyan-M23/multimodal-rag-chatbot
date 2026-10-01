from pathlib import Path

from bs4 import BeautifulSoup


def extract_html_content(file_path: str) -> list[dict]:
    """
    Extract readable text from a local HTML/HTM file.

    Returns the same document structure used by the other
    ingestion processors.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix.lower() not in {".html", ".htm"}:
        raise ValueError(f"Unsupported HTML file type: {path.suffix}")

    html_content = path.read_text(encoding="utf-8", errors="replace")

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove elements that normally don't contain useful
    # document content.
    for element in soup(
        ["script", "style", "noscript", "template"]
    ):
        element.decompose()

    title = soup.title.get_text(strip=True) if soup.title else path.name

    text = soup.get_text(separator="\n", strip=True)

    if not text:
        return []

    return [
        {
            "text": text,
            "metadata": {
                "source": str(path),
                "file_type": "html",
                "title": title,
            },
        }
    ]