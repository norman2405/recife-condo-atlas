from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.v2.buildings import (
        Building,
        BuildingCandidate,
        candidate_id,
        normalize_building_name,
        slugify_building_name,
    )
    from scripts.v2.storage import load_json_list, save_json_list_atomic
else:
    from .buildings import (
        Building,
        BuildingCandidate,
        candidate_id,
        normalize_building_name,
        slugify_building_name,
    )
    from .storage import load_json_list, save_json_list_atomic


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPOSITORY_ROOT / "data"
BUILDINGS_FILE = DATA_DIR / "buildings.json"
PENDING_BUILDINGS_FILE = DATA_DIR / "pending-buildings.json"
ALLOWED_DISTRICTS = {"Piedade", "Candeias"}


def environment_value(name: str) -> str:
    return os.environ.get(name, "").strip()


def known_normalized_names(items: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for item in items:
        for value in [item.get("name", ""), *(item.get("aliases") or [])]:
            normalized = normalize_building_name(str(value))
            if normalized:
                names.add(normalized)
    return names


def add_candidate() -> int:
    name = environment_value("BUILDING_NAME")
    district = environment_value("BUILDING_DISTRICT")
    address = environment_value("BUILDING_ADDRESS")
    source = environment_value("BUILDING_SOURCE") or "manual"
    source_url = environment_value("BUILDING_SOURCE_URL")

    if not name:
        raise ValueError("BUILDING_NAME darf nicht leer sein.")
    if district not in ALLOWED_DISTRICTS:
        raise ValueError("BUILDING_DISTRICT muss Piedade oder Candeias sein.")

    buildings = load_json_list(BUILDINGS_FILE)
    pending = load_json_list(PENDING_BUILDINGS_FILE)
    normalized = normalize_building_name(name)

    if normalized in known_normalized_names(buildings):
        print(f"Gebäude bereits freigegeben: {name}")
        return 0
    if normalized in known_normalized_names(pending):
        print(f"Gebäudekandidat bereits vorhanden: {name}")
        return 0

    candidate = BuildingCandidate(
        candidate_id=candidate_id(name, district, address),
        name=name,
        district=district,
        address=address,
        normalized_name=normalized,
        source=source,
        source_url=source_url,
    )
    save_json_list_atomic(PENDING_BUILDINGS_FILE, pending + [candidate.to_dict()])
    print(f"Gebäudekandidat angelegt: {candidate.candidate_id} – {candidate.name}")
    return 0


def unique_building_id(name: str, buildings: list[dict[str, Any]]) -> str:
    base = slugify_building_name(name)
    existing = {str(item.get("id", "")).strip() for item in buildings}
    if base not in existing:
        return base

    number = 2
    while f"{base}-{number}" in existing:
        number += 1
    return f"{base}-{number}"


def approve_candidate() -> int:
    requested_id = environment_value("BUILDING_CANDIDATE_ID")
    if not requested_id:
        raise ValueError("BUILDING_CANDIDATE_ID darf nicht leer sein.")

    buildings = load_json_list(BUILDINGS_FILE)
    pending = load_json_list(PENDING_BUILDINGS_FILE)
    selected = next(
        (item for item in pending if str(item.get("candidate_id", "")) == requested_id),
        None,
    )
    if selected is None:
        raise ValueError(f"Kandidat nicht gefunden: {requested_id}")

    canonical_name = environment_value("BUILDING_CANONICAL_NAME") or str(selected.get("name", ""))
    building = Building(
        id=unique_building_id(canonical_name, buildings),
        name=canonical_name,
        district=str(selected.get("district", "")),
        address=str(selected.get("address", "")),
        aliases=sorted(
            {
                value
                for value in [str(selected.get("name", "")).strip()]
                if value and value != canonical_name
            }
        ),
    )

    remaining = [
        item for item in pending if str(item.get("candidate_id", "")) != requested_id
    ]
    save_json_list_atomic(BUILDINGS_FILE, buildings + [building.to_dict()])
    save_json_list_atomic(PENDING_BUILDINGS_FILE, remaining)
    print(f"Gebäude freigegeben: {building.id} – {building.name}")
    return 0


def list_candidates() -> int:
    pending = load_json_list(PENDING_BUILDINGS_FILE)
    if not pending:
        print("Keine Gebäudekandidaten vorhanden.")
        return 0

    print("Offene Gebäudekandidaten:")
    for item in pending:
        print(
            f"- {item.get('candidate_id')}: {item.get('name')} "
            f"({item.get('district')})"
        )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recife Condo Atlas Building Manager")
    parser.add_argument("operation", choices=["add", "approve", "list"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.operation == "add":
        return add_candidate()
    if args.operation == "approve":
        return approve_candidate()
    return list_candidates()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"FEHLER: {error}", file=sys.stderr)
        raise SystemExit(2) from error
