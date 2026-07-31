from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


SOURCE_NAME = "VivaReal"
BASE_URL = "https://www.vivareal.com.br"
MAX_LINKS = 10
REQUEST_TIMEOUT_SECONDS = 20

SEARCH_URLS = (
    "https://www.vivareal.com.br/venda/pernambuco/"
    "jaboatao-dos-guararapes/bairros/piedade/apartamento_residencial/",
    "https://www.vivareal.com.br/venda/pernambuco/"
    "jaboatao-dos-guararapes/bairros/candeias/apartamento_residencial/",
)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "a":
            return

        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value)


def normalize_detail_url(candidate: str) -> str | None:
    """Return one canonical VivaReal detail URL or ``None``.

    Query parameters, fragments and accidental JSON escaping are removed so
    the same property is not requested repeatedly under several tracking URLs.
    """
    cleaned = html.unescape(candidate).strip()
    cleaned = cleaned.replace("\\/", "/").replace("\\", "")

    if not cleaned:
        return None

    absolute = urljoin(BASE_URL, cleaned)
    parts = urlsplit(absolute)

    if parts.netloc.lower() not in {
        "vivareal.com.br",
        "www.vivareal.com.br",
    }:
        return None

    path = re.sub(r"/{2,}", "/", parts.path)

    if not path.startswith("/imovel/"):
        return None

    # Real detail paths normally contain a numeric listing ID.
    if not re.search(r"(?:-id-?|/)(\d{6,})(?:/|$)", path):
        return None

    canonical_path = path.rstrip("/") + "/"
    return urlunsplit(("https", "www.vivareal.com.br", canonical_path, "", ""))


def extract_detail_links(page_html: str, limit: int = MAX_LINKS) -> list[str]:
    """Extract unique VivaReal property links without opening detail pages."""
    if limit <= 0:
        return []

    parser = _LinkParser()
    parser.feed(page_html)

    # Some pages embed URLs in JSON rather than normal anchor elements.
    embedded = re.findall(
        r"[\"']("
        r"(?:https?:\\?/\\?/www\.vivareal\.com\.br)?"
        r"\\?/imovel\\?/[^\"'<>\s]+"
        r")[\"']",
        page_html,
        flags=re.IGNORECASE,
    )

    result: list[str] = []
    seen: set[str] = set()

    for candidate in [*parser.hrefs, *embedded]:
        normalized = normalize_detail_url(candidate)

        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        result.append(normalized)

        if len(result) >= limit:
            break

    return result


def fetch_search_page(search_url: str) -> str | None:
    """
    Lädt eine VivaReal-Ergebnisseite.

    VivaReal kann Zugriffe aus GitHub Actions mit HTTP 403 oder 429
    blockieren. In diesem Fall wird der Adapter sauber beendet.
    """
    request = Request(
        search_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    )

    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            return response.read().decode(
                "utf-8",
                errors="replace",
            )

    except HTTPError as error:
        if error.code == 403:
            print(
                "VivaReal blockiert den Zugriff aus "
                "GitHub Actions (HTTP 403)."
            )
            return None

        if error.code == 429:
            print(
                "VivaReal begrenzt die Anfragen "
                "(HTTP 429)."
            )
            return None

        print(
            f"VivaReal HTTP-Fehler {error.code}: "
            f"{search_url}"
        )
        return None

    except URLError as error:
        print(
            "VivaReal Netzwerkfehler: "
            f"{error.reason}"
        )
        return None


def collect_detail_links(limit: int = MAX_LINKS) -> list[str]:
    """Read result pages and return at most ``limit`` unique detail links.

    This first adapter stage never requests a property detail page.
    """
    links: list[str] = []
    seen: set[str] = set()

    for search_url in SEARCH_URLS:
        if len(links) >= limit:
            break

        page_html = fetch_search_page(search_url)

        for detail_url in extract_detail_links(page_html, limit=limit):
            if detail_url in seen:
                continue

            seen.add(detail_url)
            links.append(detail_url)

            if len(links) >= limit:
                break

    return links


if __name__ == "__main__":
    found = collect_detail_links()
    print(f"{SOURCE_NAME}: {len(found)} eindeutige Detail-Links gefunden")

    for index, url in enumerate(found, start=1):
        print(f"{index:02d}. {url}")
