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

    temporary.replace(path)


def fingerprint(item: dict[str, Any]) -> str:
    source_url = str(item.get("sourceUrl", "")).strip().lower()

    if source_url:
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


def parse_number(text: str | None) -> float | None:
    """
    Wandelt Angaben wie 'R$ 720.000', '185 m²' oder '4 quartos'
    in eine Zahl um.
    """
    if not text:
        return None

    cleaned = (
        text.replace("R$", "")
        .replace("m²", "")
        .replace("m2", "")
        .replace("quartos", "")
        .replace("quarto", "")
        .replace("andar", "")
        .replace("º", "")
        .replace(".", "")
        .replace(",", ".")
        .strip()
    )

    number_chars = []

    for character in cleaned:
        if character.isdigit() or character in {".", "-"}:
            number_chars.append(character)
        elif number_chars:
            break

    if not number_chars:
        return None

    try:
        return float("".join(number_chars))
    except ValueError:
        return None


def normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def extract_first_number(
    text: str,
    pattern: str,
) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)

    if not match:
        return None

    return parse_number(match.group(1))


def detect_district(text: str) -> str | None:
    lowered = text.lower()

    if "piedade" in lowered:
        return "Piedade"

    if "candeias" in lowered:
        return "Candeias"

    return None


def detect_floor(text: str) -> int | None:
    patterns = [
        r"(\d+)\s*[ºo°]?\s*andar",
        r"andar\s*(\d+)",
        r"(\d+)[ªa]\s*andar",
    ]

    for pattern in patterns:
        value = extract_first_number(text, pattern)

        if value is not None:
            return int(value)

    return None


def detect_balcony(text: str) -> bool | None:
    lowered = text.lower()

    negative_terms = [
        "sem varanda",
        "não possui varanda",
        "nao possui varanda",
    ]

    positive_terms = [
        "varanda gourmet",
        "varanda",
        "sacada",
        "terraço",
    ]

    if any(term in lowered for term in negative_terms):
        return False

    if any(term in lowered for term in positive_terms):
        return True

    return None


def detect_sea_view(text: str) -> bool | None:
    lowered = text.lower()

    negative_terms = [
        "sem vista para o mar",
        "sem vista mar",
    ]

    positive_terms = [
        "vista para o mar",
        "vista mar",
        "vista do mar",
        "frente para o mar",
        "frente mar",
        "beira-mar",
        "beira mar",
    ]

    if any(term in lowered for term in negative_terms):
        return False

    if any(term in lowered for term in positive_terms):
        return True

    return None


def evaluate_search_profile(
    item: dict[str, Any],
) -> tuple[bool, list[str]]:
    """
    Lehnt nur Anzeigen ab, die dem Suchprofil eindeutig widersprechen.

    Fehlende Angaben werden nicht automatisch abgelehnt.
    Sie erscheinen als Warnung für die manuelle Prüfung.
    """
    warnings: list[str] = []

    district = item.get("district")
    bedrooms = item.get("bedrooms")
    balcony = item.get("balcony")
    sea_view = item.get("seaView")
    floor = item.get("floor")
    price = item.get("price")

    if district not in {"Piedade", "Candeias"}:
        return False, [
            "Stadtteil liegt nicht in Piedade oder Candeias."
        ]

    if bedrooms is not None and int(bedrooms) < 4:
        return False, [
            "Weniger als vier Schlafzimmer."
        ]

    if balcony is False:
        return False, [
            "Keine Varanda erkannt."
        ]

    if sea_view is False:
        return False, [
            "Kein Meerblick erkannt."
        ]

    if floor is not None and int(floor) < 6:
        return False, [
            "Etage liegt unter der 6. Etage."
        ]

    if price is not None and float(price) > 800_000:
        return False, [
            "Preis liegt über R$ 800.000."
        ]

    if bedrooms is None:
        warnings.append(
            "Anzahl der Schlafzimmer fehlt."
        )

    if balcony is None:
        warnings.append(
            "Varanda muss manuell geprüft werden."
        )

    if sea_view is None:
        warnings.append(
            "Meerblick muss manuell geprüft werden."
        )

    if floor is None:
        warnings.append(
            "Etage muss manuell geprüft werden."
        )

    if price is None:
        warnings.append(
            "Preis muss manuell geprüft werden."
        )

    return True, warnings


def collect_ataide_detail(
    source_url: str,
    session: requests.Session,
) -> dict[str, Any] | None:
    """
    Liest eine einzelne ATAÍDE-Detailseite aus.
    """
    response = session.get(
        source_url,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    title_element = soup.select_one("h1")

    if not title_element:
        return None

    title = normalize_text(
        title_element.get_text(" ", strip=True)
    )

    page_text = normalize_text(
        soup.get_text(" ", strip=True)
    )

    property_code_match = re.search(
        r"c[oó]d\.?\s*(?:do\s+)?im[oó]vel\s*:?\s*(\d+)",
        page_text,
        flags=re.IGNORECASE,
    )

    property_code = (
        property_code_match.group(1)
        if property_code_match
        else None
    )

    price = extract_first_number(
        page_text,
        r"R\$\s*([\d.]+(?:,\d{1,2})?)",
    )

    area = extract_first_number(
        page_text,
        r"([\d.,]+)\s*m[²2]",
    )

    bedrooms_value = extract_first_number(
        page_text,
        r"(\d+)\s*quarto",
    )

    bathrooms_value = extract_first_number(
        page_text,
        r"(\d+)\s*banheiro",
    )

    parking_value = extract_first_number(
        page_text,
        r"(\d+)\s*vaga",
    )

    district = detect_district(
        f"{title} {page_text}"
    )

    image_urls: list[str] = []

    for image in soup.select("img[src]"):
        image_url = urljoin(
            source_url,
            str(image.get("src", "")),
        )

        if (
            image_url
            and image_url not in image_urls
        ):
            image_urls.append(image_url)

    searchable_text = normalize_text(
        f"{title} {page_text}"
    )

    return {
        "building": title,
        "district": district,
        "address": "",
        "price": price,
        "area": area,
        "bedrooms": (
            int(bedrooms_value)
            if bedrooms_value is not None
            else None
        ),
        "bathrooms": (
            int(bathrooms_value)
            if bathrooms_value is not None
            else None
        ),
        "parkingSpaces": (
            int(parking_value)
            if parking_value is not None
            else None
        ),
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
    """
    Sucht auf der ATAÍDE-Verkaufsseite nach Links
    zu einzelnen Immobilien und liest diese aus.
    """
    search_url = "https://www.imoveisataide.com.br/venda"

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9",
        }
    )

    response = session.get(
        search_url,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    detail_urls: set[str] = set()

    for link in soup.select("a[href]"):
        href = str(link.get("href", "")).strip()

        if not href:
            continue

        absolute_url = urljoin(
            search_url,
            href,
        )

        if "/imovel/" not in absolute_url.lower():
            continue

        detail_urls.add(absolute_url)

    print(
        f"ATAÍDE: {len(detail_urls)} "
        "mögliche Detailseiten gefunden"
    )

    results: list[dict[str, Any]] = []

    for index, detail_url in enumerate(
        sorted(detail_urls),
        start=1,
    ):
        try:
            item = collect_ataide_detail(
                detail_url,
                session,
            )

            if item:
                results.append(item)

            print(
                f"ATAÍDE: {index}/"
                f"{len(detail_urls)} gelesen"
            )

        except requests.RequestException as error:
            print(
                "ATAÍDE: Detailseite nicht lesbar: "
                f"{detail_url}: {error}"
            )

        time.sleep(1)

    return results


def collect_from_sources() -> list[dict[str, Any]]:
    all_items: list[dict[str, Any]] = []

    adapters = [
        collect_from_ataide,
    ]

    for adapter in adapters:
        try:
            items = adapter()
            all_items.extend(items)

            print(
                f"{adapter.__name__}: "
                f"{len(items)} Treffer gelesen"
            )

        except requests.RequestException as error:
            print(
                f"{adapter.__name__}: "
                f"Netzwerkfehler: {error}"
            )

        except (
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as error:
            print(
                f"{adapter.__name__}: "
                f"Datenfehler: {error}"
            )

        except Exception as error:
            print(
                f"{adapter.__name__}: "
                f"unerwarteter Fehler: {error}"
            )

    return all_items


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

    if item["fingerprint"] in existing:
        print("  Ergebnis: bereits vorhanden")
        continue

    is_candidate, warnings = evaluate_search_profile(
        item
    )

    if not is_candidate:
        print("  Ergebnis: Suchprofil nicht erfüllt")
        print(f"  Grund: {', '.join(warnings)}")
        continue

    print("  Ergebnis: wird in pending-listings.json gespeichert")

        item["reviewWarnings"] = warnings
        item.setdefault(
            "foundAt",
            date.today().isoformat(),
        )
        item.setdefault(
            "decision",
            "pending",
        )
        item.setdefault(
            "reviewNote",
            "",
        )

        price = item.get("price")
        area = item.get("area")

        if price and area:
            item["pricePerM2"] = round(
                float(price) / float(area),
                2,
            )

        new_items.append(item)
        existing.add(item["fingerprint"])

    if new_items:
        save_json(
            PENDING_FILE,
            pending + new_items,
        )

        print(
            f"{len(new_items)} neue Treffer "
            "zur Prüfung gespeichert."
        )
    else:
        print("Keine neuen Treffer.")


if __name__ == "__main__":
    main()
