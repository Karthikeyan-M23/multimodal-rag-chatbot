import ipaddress
import os
import socket
import tempfile
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config.settings import ALLOW_PRIVATE_URLS, PRIVATE_URL_ALLOWLIST
from src.ingestion.html_processor import extract_html_from_soup
from src.ingestion.http_auth import AuthError, SignedInSession, looks_like_login_page


MAX_BYTES = 30 * 1024 * 1024

MAX_REDIRECTS = 5

LOGIN_PAGE_MAX_TEXT = 1500

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0 Safari/537.36"
)


def check_url(url: str):
    """
    Block non-http(s) and (by default) internal network addresses, except
    hosts listed in PRIVATE_URL_ALLOWLIST (e.g. an intranet TFS server).
    """

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must start with http:// or https://")

    if ALLOW_PRIVATE_URLS or parsed.hostname.lower() in PRIVATE_URL_ALLOWLIST:
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
                f"{parsed.hostname} is on a private or local network, which is blocked. "
                f"Add it to PRIVATE_URL_ALLOWLIST in .env (or set ALLOW_PRIVATE_URLS=true)."
            )


# Kept for callers/tests that use the old name.
_check_url = check_url


def _fetch(url: str, session: SignedInSession) -> requests.Response:
    """
    Follows redirects manually so every hop is checked. The session only
    sends credentials to the host they were entered for.
    """

    for _ in range(MAX_REDIRECTS + 1):

        check_url(url)

        response = session.get(
            url,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=False,
            stream=True,
        )

        if response.is_redirect:
            url = requests.compat.urljoin(url, response.headers["location"])
            continue

        if response.status_code in {401, 403} and not session.has_credentials:
            raise AuthError(
                "This page requires sign-in. Add it again with "
                "\"Requires sign-in\" turned on."
            )

        if response.status_code == 403:
            raise AuthError("Signed in, but this account has no access to the page (403).")

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


def extract_web_content(url: str, progress=None, username: str = "", password: str = "") -> list[dict]:

    if progress:
        progress("Signing in" if password else "Fetching page")

    session = SignedInSession(username, password, url)
    response = _fetch(url, session)
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

    html = body.decode(encoding, errors="replace")

    soup = BeautifulSoup(html, "html.parser")

    # A password field on a page with little else is a login wall; a small
    # login box in the header of a real article is not.
    if looks_like_login_page(html) and len(soup.get_text(" ", strip=True)) < LOGIN_PAGE_MAX_TEXT:
        raise AuthError(
            "This site shows a login form or single sign-on page, which can't be "
            "signed in to automatically. Basic and Windows (NTLM) sign-in are supported."
            if session.has_credentials
            else "This page shows a login form. If it supports Basic or Windows "
            "sign-in, add it again with \"Requires sign-in\" turned on."
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
