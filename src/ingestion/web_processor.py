import ipaddress
import os
import socket
import tempfile
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config.settings import ALLOW_PRIVATE_URLS
from src.ingestion.html_processor import extract_html_from_soup


MAX_BYTES = 30 * 1024 * 1024

MAX_REDIRECTS = 5

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0 Safari/537.36"
)


def _check_url(url: str):
    """Block non-http(s) and (by default) internal network addresses."""

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must start with http:// or https://")

    if ALLOW_PRIVATE_URLS:
        return

    try:
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(parsed.hostname, None)
        }
    except socket.gaierror:
        raise ValueError(f"Could not resolve host: {parsed.hostname}")

    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])

        if not ip.is_global:
            raise ValueError(
                "URLs on private or local networks are not allowed. "
                "Set ALLOW_PRIVATE_URLS=true to permit them."
            )


def _fetch(url: str) -> requests.Response:

    for _ in range(MAX_REDIRECTS + 1):

        _check_url(url)

        response = requests.get(
            url,
            timeout=30,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=False,
            stream=True,
        )

        if response.is_redirect:
            url = requests.compat.urljoin(url, response.headers["location"])
            continue

        response.raise_for_status()

        return response

    raise ValueError("Too many redirects.")


def _read_limited(response) -> bytes:

    data = bytearray()

    for block in response.iter_content(64 * 1024):
        data.extend(block)

        if len(data) > MAX_BYTES:
            raise ValueError("Web page is too large.")

    return bytes(data)


def extract_web_content(url: str, progress=None) -> list[dict]:

    if progress:
        progress("Fetching page")

    response = _fetch(url)
    content_type = response.headers.get("content-type", "").lower()
    body = _read_limited(response)

    # Direct links to PDFs are common; handle them as documents.
    if "application/pdf" in content_type or url.lower().endswith(".pdf"):

        from src.ingestion.pdf_processor import extract_pdf_pages

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as file:
            file.write(body)
            pdf_path = file.name

        try:
            pages = extract_pdf_pages(pdf_path, progress)
        finally:
            os.unlink(pdf_path)

        for page in pages:
            page["metadata"].update(
                {"source": url, "url": url, "file_type": "web", "title": url}
            )

        return pages

    encoding = response.encoding or response.apparent_encoding or "utf-8"

    soup = BeautifulSoup(
        body.decode(encoding, errors="replace"),
        "html.parser",
    )

    documents = extract_html_from_soup(
        soup,
        source=url,
        file_type="web",
        fallback_title=url,
        main_content_only=True,
    )

    if not documents:
        raise ValueError(
            "No usable text could be extracted from the webpage."
        )

    for document in documents:
        document["metadata"]["url"] = url

    return documents
