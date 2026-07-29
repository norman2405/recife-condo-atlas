from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

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


def collect_from_sources() -> list[dict[str, Any]]:
    """
    Hier kommen später die einzelnen Quellenadapter hinein.

    Jeder Adapter soll nur öffentlich zugängliche Daten auslesen und die
    Nutzungsbedingungen sowie robots.txt der jeweiligen Website beachten.
    Instagram-Beiträge sollten zunächst manuell oder über eine offiziell
    erlaubte Schnittstelle aufgenommen werden.
    """
    return []


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
