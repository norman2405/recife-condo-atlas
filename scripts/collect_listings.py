from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


DATA_DIR = Path("data")
PENDING_FILE = DATA_DIR / "pending-listings.json"
LISTINGS_FILE = DATA_DIR / "listings.json"

ATAIDE_BASE_URL = "https://www.imoveisataide.com.br"
ATAIDE_SEARCH_URL = (
    "https://www.imoveisataide.com.br/"
    "venda/imovel/regiao-de-candeias/todos-os-bairros"
)
ATAIDE_MAX_PAGES = 20
REQUEST_DELAY_SECONDS = 1.0


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(f"{path} muss eine JSON-Liste enthalten.")

    return data


def save_json(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")

    temporary.replace(path)


def fingerprint(item: dict[str, Any]) -> str:
    source_url = str(item.get("sourceUrl", "")).strip().lower()
    external_id = str(item.get("externalId", "")).strip().lower()

    if external_id:
        raw = f"{item.get('source', '')}|{external_id}"
    elif source_url:
        raw = source_url
    else:
        raw = "|".join(
            [
                str(item.get("building", "")).strip().lower(),
                str(item.get("price", "")),
                str(item.get("area", "")),
                str(item.get("bedrooms", "")),
                str(item.get("broker", "")).strip().lower(),
            ]
        )

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def parse_brazilian_number(text: str | None) -> float | None:
    if not text:
        return None

    match = re.search(r"-?\d[\d.]*?(?:,\d+)?", text)
    if not match:
        return None

    cleaned = match.group(0).replace(".", "").replace(",", ".")

    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_number(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = parse_brazilian_number(match.group(1))
            if value is not None:
                return value
    return None


def detect_district(text: str) -> str | None:
    lowered = text.lower()
    if "piedade" in lowered:
        return "Piedade"
    if "candeias" in lowered:
        return "Candeias"
    return None


def detect_floor(text: str) -> int | None:
    value = extract_number(
        text,
        [
            r"(\d+)\s*[ºo°]?\s*andar",
            r"andar\s*:?[ ]*(\d+)",
            r"(\d+)\s*[ªa]\s*andar",
        ],
    )
    return int(value) if value is not None else None


def detect_balcony(text: str) -> bool | None:
    lowered = text.lower()

    if any(
        phrase in lowered
        for phrase in ["sem varanda", "não possui varanda", "nao possui varanda"]
    ):
        return False

    if any(
        phrase in lowered
        for phrase in ["varanda gourmet", "varanda", "sacada", "terraço"]
    ):
        return True

    return None


def detect_sea_view(text: str) -> bool | None:
    lowered = text.lower()

    if any(
        phrase in lowered
        for phrase in ["sem vista para o mar", "sem vista mar"]
    ):
        return False

    if any(
        phrase in lowered
        for phrase in [
            "vista para o mar",
            "vista mar",
            "vista do mar",
            "frente para o mar",
            "frente mar",
            "beira-mar",
            "beira mar",
        ]
    ):
        return True

    return None


def evaluate_search_profile(
    item: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Lehnt nur Anzeigen ab, die dem Profil eindeutig widersprechen."""
    warnings: list[str] = []

    district = item.get("district")
    bedrooms = item.get("bedrooms")
    balcony = item.get("balcony")
    sea_view = item.get("seaView")
    floor = item.get("floor")
    price = item.get("price")

    if district not in {"Piedade", "Candeias"}:
        return False, ["Stadtteil liegt nicht in Piedade oder Candeias."]
    if bedrooms is not None and int(bedrooms) < 4:
        return False, ["Weniger als vier Schlafzimmer."]
    if balcony is False:
        return False, ["Keine Varanda erkannt."]
    if sea_view is False:
        return False, ["Kein Meerblick erkannt."]
    if floor is not None and int(floor) < 6:
        return False, ["Etage liegt unter der 6. Etage."]
    if price is not None and float(price) > 800_000:
        return False, ["Preis liegt über R$ 800.000."]

    if bedrooms is None:
        warnings.append("Anzahl der Schlafzimmer fehlt.")
    if balcony is None:
        warnings.append("Varanda muss manuell geprüft werden.")
    if sea_view is None:
        warnings.append("Meerblick muss manuell geprüft werden.")
    if floor is None:
        warnings.append("Etage muss manuell geprüft werden.")
    if price is None:
        warnings.append("Preis muss manuell geprüft werden.")

    return True, warnings


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        }
    )
    return session


def extract_ataide_detail_urls(html: str, page_url: str) -> set[str]:
    """Findet Detail-URLs sowohl in Links als auch in eingebettetem JavaScript."""
    urls: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")

    for link in soup.select("a[href]"):
        href = str(link.get("href", "")).strip()
        if href:
            urls.add(urljoin(page_url, href))

    unescaped_html = html.replace("\\/", "/")
    patterns = [
        r'https?://www\.imoveisataide\.com\.br/imovel/[^"\'<>\s]+',
        r'["\'](/imovel/[^"\'<>\s]+)["\']',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, unescaped_html, flags=re.IGNORECASE):
            candidate = match.group(1) if match.lastindex else match.group(0)
            urls.add(urljoin(ATAIDE_BASE_URL, candidate))

    cleaned_urls: set[str] = set()
    for url in urls:
        url = url.split("#", 1)[0].rstrip("/.,);]")
        lowered = url.lower()
        if "/imovel/" not in lowered:
            continue
        if not re.search(r"/\d+(?:/)?(?:\?.*)?$", url):
            continue
        cleaned_urls.add(url)

    return cleaned_urls


def collect_ataide_detail(
    source_url: str,
    session: requests.Session,
) -> dict[str, Any] | None:
    response = session.get(source_url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    title_element = soup.select_one("h1")
    page_text = normalize_text(soup.get_text(" ", strip=True))

    title = (
        normalize_text(title_element.get_text(" ", strip=True))
        if title_element
        else "Imóvel ATAÍDE"
    )

    property_code_match = re.search(
        r"c[oó]d\.?\s*(?:do\s+)?im[oó]vel\s*:?\s*(\d+)",
        page_text,
        flags=re.IGNORECASE,
    )
    if property_code_match:
        property_code = property_code_match.group(1)
    else:
        url_code_match = re.search(r"/(\d+)(?:/)?(?:\?.*)?$", source_url)
        property_code = url_code_match.group(1) if url_code_match else None

    price = extract_number(
        page_text,
        [r"R\$\s*([\d.]+(?:,\d{1,2})?)"],
    )
    area = extract_number(
        page_text,
        [
            r"([\d.,]+)\s*m[²2]\s*(?:de\s+)?(?:área|area)",
            r"(?:área|area)[^\d]{0,20}([\d.,]+)\s*m[²2]",
            r"([\d.,]+)\s*m[²2]",
        ],
    )
    bedrooms_value = extract_number(
        page_text,
        [r"(\d+)\s*quarto", r"quartos?[^\d]{0,10}(\d+)"],
    )
    bathrooms_value = extract_number(
        page_text,
        [r"(\d+)\s*banh", r"banheiros?[^\d]{0,10}(\d+)"],
    )
    parking_value = extract_number(
        page_text,
        [r"(\d+)\s*vaga", r"vagas?[^\d]{0,10}(\d+)"],
    )

    image_urls: list[str] = []
    for image in soup.select("img"):
        for attribute in ("src", "data-src", "data-lazy", "data-original"):
            value = str(image.get(attribute, "")).strip()
            if not value:
                continue
            image_url = urljoin(source_url, value)
            if image_url.startswith("http") and image_url not in image_urls:
                image_urls.append(image_url)

    searchable_text = normalize_text(f"{title} {page_text}")

    return {
        "building": title,
        "district": detect_district(searchable_text),
        "address": "",
        "price": price,
        "area": area,
        "bedrooms": int(bedrooms_value) if bedrooms_value is not None else None,
        "bathrooms": (
            int(bathrooms_value) if bathrooms_value is not None else None
        ),
        "parkingSpaces": int(parking_value) if parking_value is not None else None,
        "floor": detect_floor(searchable_text),
        "balcony": detect_balcony(searchable_text),
        "seaView": detect_sea_view(searchable_text),
        "description": page_text,
        "imageUrls": image_urls,
        "externalId": property_code,
        "broker": "ATAÍDE Imóveis",
        "source": "ATAÍDE",
        "sourceUrl": source_url,
        "instagramUrl": "",
    }


def collect_from_ataide() -> list[dict[str, Any]]:
    session = make_session()
    detail_urls: set[str] = set()
    pages_without_new_urls = 0

    for page_number in range(1, ATAIDE_MAX_PAGES + 1):
        page_url = f"{ATAIDE_SEARCH_URL}?pagina={page_number}"
        response = session.get(page_url, timeout=30)
        response.raise_for_status()

        page_urls = extract_ataide_detail_urls(response.text, page_url)
        new_urls = page_urls - detail_urls
        detail_urls.update(page_urls)

        print(
            f"ATAÍDE Seite {page_number}: {len(page_urls)} Links, "
            f"davon {len(new_urls)} neu"
        )

        if new_urls:
            pages_without_new_urls = 0
        else:
            pages_without_new_urls += 1

        if pages_without_new_urls >= 2:
            print("ATAÍDE: zwei Seiten ohne neue Links; Seitensuche beendet.")
            break

        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"ATAÍDE: insgesamt {len(detail_urls)} Detailseiten gefunden")

    results: list[dict[str, Any]] = []
    for index, detail_url in enumerate(sorted(detail_urls), start=1):
        try:
            item = collect_ataide_detail(detail_url, session)
            if item:
                results.append(item)
            print(f"ATAÍDE Detailseite {index}/{len(detail_urls)} gelesen")
        except requests.RequestException as error:
            print(f"ATAÍDE Detailseite nicht lesbar: {detail_url}: {error}")

        time.sleep(REQUEST_DELAY_SECONDS)

    return results


def collect_from_sources() -> list[dict[str, Any]]:
    all_items: list[dict[str, Any]] = []
    adapters = [collect_from_ataide]

    for adapter in adapters:
        try:
            items = adapter()
            all_items.extend(items)
            print(f"{adapter.__name__}: {len(items)} Treffer gelesen")
        except requests.RequestException as error:
            print(f"{adapter.__name__}: Netzwerkfehler: {error}")
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            print(f"{adapter.__name__}: Datenfehler: {error}")
        except Exception as error:
            print(f"{adapter.__name__}: unerwarteter Fehler: {error}")

    return all_items


def print_item_diagnostics(
    item: dict[str, Any],
    result: str,
    reasons: list[str] | None = None,
) -> None:
    print("")
    print("Gefundene Anzeige:")
    print(f"  Titel: {item.get('building')}")
    print(f"  Stadtteil: {item.get('district')}")
    print(f"  Preis: {item.get('price')}")
    print(f"  Schlafzimmer: {item.get('bedrooms')}")
    print(f"  Etage: {item.get('floor')}")
    print(f"  Varanda: {item.get('balcony')}")
    print(f"  Meerblick: {item.get('seaView')}")
    print(f"  URL: {item.get('sourceUrl')}")
    print(f"  Ergebnis: {result}")
    if reasons:
        print(f"  Hinweise: {', '.join(reasons)}")


def main() -> None:
    pending = load_json(PENDING_FILE)
    approved = load_json(LISTINGS_FILE)

    existing = {
        item.get("fingerprint") or fingerprint(item)
        for item in pending + approved
    }

    new_items: list[dict[str, Any]] = []

    for item in collect_from_sources():
        item["fingerprint"] = fingerprint(item)

        if item["fingerprint"] in existing:
            print_item_diagnostics(item, "bereits vorhanden")
            continue

        is_candidate, messages = evaluate_search_profile(item)
        if not is_candidate:
            print_item_diagnostics(item, "Suchprofil nicht erfüllt", messages)
            continue

        print_item_diagnostics(
            item,
            "wird in pending-listings.json gespeichert",
            messages,
        )

        item["reviewWarnings"] = messages
        item.setdefault("foundAt", date.today().isoformat())
        item.setdefault("decision", "pending")
        item.setdefault("reviewNote", "")

        price = item.get("price")
        area = item.get("area")
        if price and area:
            item["pricePerM2"] = round(float(price) / float(area), 2)

        new_items.append(item)
        existing.add(item["fingerprint"])

    if new_items:
        save_json(PENDING_FILE, pending + new_items)
        print(f"{len(new_items)} neue Treffer zur Prüfung gespeichert.")
    else:
        print("Keine neuen Treffer.")


if __name__ == "__main__":
    main()
