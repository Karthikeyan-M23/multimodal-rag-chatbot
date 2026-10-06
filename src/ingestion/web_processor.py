from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


def extract_web_content(url: str) -> list[dict]:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError(
            "URL must start with http:// or https://"
        )

    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0 Safari/537.36"
            )
        },
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    for element in soup(
        ["script", "style", "noscript", "nav", "footer", "header", "aside"]
    ):
        element.decompose()

    title = soup.title.get_text(strip=True) if soup.title else url
    text = soup.get_text(separator="\n", strip=True)

    if not text:
        raise ValueError(
            "No usable text could be extracted from the webpage."
        )

    return [
        {
            "text": text,
            "metadata": {
                "source": url,
                "file_type": "web",
                "title": title,
                "url": url,
            },
        }
    ]
