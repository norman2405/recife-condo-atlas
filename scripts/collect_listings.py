from __future__ import annotations

import hashlib
import json
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


def meets_search_profile(item: dict[str, Any]) -> bool:
    return (
        item.get("district") in {"Piedade", "Candeias"}
        and int(item.get("bedrooms") or 0) >= 4
        and item.get("balcony") is True
        and item.get("seaView") is True
        and int(item.get("floor") or 0) >= 6
        and float(item.get("price") or 10**20) <= 800_000
    )


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


def collect_from_local_broker() -> list[dict[str, Any]]:
    """
    Beispieladapter für eine lokale Maklerseite.

    WICHTIG:
    Die URL und die CSS-Selektoren sind Platzhalter.
    Der Adapter funktioniert erst, nachdem sie an eine echte Website
    angepasst wurden.
    """
    search_url = "https://www.vivareal.com.br"

    headers = {
        "User-Agent": (
            "RecifeCondoAtlas/1.0 "
            "(private research project)"
        )
    }

    response = requests.get(
        search_url,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict[str, Any]] = []

    for card in soup.select(".property-card"):
        title_element = card.select_one(".property-title")
        price_element = card.select_one(".price")
        area_element = card.select_one(".area")
        bedrooms_element = card.select_one(".bedrooms")
        floor_element = card.select_one(".floor")
        link_element = card.select_one("a[href]")

        if not title_element or not price_element or not link_element:
            continue

        title = title_element.get_text(" ", strip=True)
        price = parse_number(price_element.get_text(" ", strip=True))
        area = (
            parse_number(area_element.get_text(" ", strip=True))
            if area_element
            else None
        )
        bedrooms_value = (
            parse_number(bedrooms_element.get_text(" ", strip=True))
            if bedrooms_element
            else None
        )
        floor_value = (
            parse_number(floor_element.get_text(" ", strip=True))
            if floor_element
            else None
        )

        description = card.get_text(" ", strip=True).lower()
        source_url = urljoin(search_url, link_element["href"])

        district = None

        if "piedade" in description:
            district = "Piedade"
        elif "candeias" in description:
            district = "Candeias"

        results.append(
            {
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
                "floor": (
                    int(floor_value)
                    if floor_value is not None
                    else None
                ),
                "balcony": any(
                    word in description
                    for word in ["varanda", "sacada", "terraço"]
                ),
                "seaView": any(
                    phrase in description
                    for phrase in [
                        "vista mar",
                        "vista para o mar",
                        "frente mar",
                        "beira-mar",
                        "beira mar",
                    ]
                ),
                "broker": "Beispiel Makler",
                "source": "Lokale Maklerseite",
                "sourceUrl": source_url,
                "instagramUrl": "",
            }
        )

    time.sleep(1)
    return results


def collect_from_sources() -> list[dict[str, Any]]:
    all_items: list[dict[str, Any]] = []

    adapters = [
        collect_from_local_broker,
    ]

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
            continue

        if not meets_search_profile(item):
            continue

        item.setdefault("foundAt", date.today().isoformat())
        item.setdefault("decision", "pending")
        item.setdefault("reviewNote", "")

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
        save_json(PENDING_FILE, pending + new_items)
        print(
            f"{len(new_items)} neue Treffer zur Prüfung gespeichert."
        )
    else:
        print("Keine neuen Treffer.")


if __name__ == "__main__":
    main()
