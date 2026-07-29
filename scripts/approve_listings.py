from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path("data")
PENDING_FILE = DATA_DIR / "pending-listings.json"
LISTINGS_FILE = DATA_DIR / "listings.json"
REJECTED_FILE = DATA_DIR / "rejected-listings.json"


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, data: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(".tmp")

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    temporary.replace(path)


def main() -> None:
    pending = load_json(PENDING_FILE)
    listings = load_json(LISTINGS_FILE)
    rejected = load_json(REJECTED_FILE)

    approved_items = [
        item for item in pending if item.get("decision") == "approved"
    ]
    rejected_items = [
        item for item in pending if item.get("decision") == "rejected"
    ]
    remaining_items = [
        item
        for item in pending
        if item.get("decision") not in {"approved", "rejected"}
    ]

    existing_fingerprints = {
        item.get("fingerprint")
        for item in listings
        if item.get("fingerprint")
    }

    for item in approved_items:
        if item.get("fingerprint") not in existing_fingerprints:
            item["status"] = "active"
            item.pop("decision", None)
            listings.append(item)

    for item in rejected_items:
        item.pop("decision", None)
        rejected.append(item)

    save_json(LISTINGS_FILE, listings)
    save_json(PENDING_FILE, remaining_items)
    save_json(REJECTED_FILE, rejected)

    print(
        f"{len(approved_items)} genehmigt, "
        f"{len(rejected_items)} abgelehnt, "
        f"{len(remaining_items)} weiterhin offen."
    )


if __name__ == "__main__":
    main()
