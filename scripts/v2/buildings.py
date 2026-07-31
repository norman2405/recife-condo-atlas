from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


PREFIXES = {
    "ed",
    "edf",
    "edif",
    "edificio",
    "edificio residencial",
    "residencial",
    "condominio",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(character for character in normalized if not unicodedata.combining(character))


def normalize_building_name(value: str) -> str:
    text = strip_accents(value).lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    changed = True
    while changed and text:
        changed = False
        for prefix in sorted(PREFIXES, key=len, reverse=True):
            if text == prefix:
                text = ""
                changed = True
                break
            if text.startswith(prefix + " "):
                text = text[len(prefix) + 1 :].strip()
                changed = True
                break

    return text


def slugify_building_name(value: str) -> str:
    normalized = normalize_building_name(value)
    slug = normalized.replace(" ", "-")
    return slug or "building"


def candidate_id(name: str, district: str, address: str = "") -> str:
    raw = "|".join(
        [
            normalize_building_name(name),
            strip_accents(district).lower().strip(),
            strip_accents(address).lower().strip(),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    return f"building-{digest}"


@dataclass(slots=True)
class BuildingCandidate:
    candidate_id: str
    name: str
    district: str
    address: str = ""
    normalized_name: str = ""
    source: str = "manual"
    source_url: str = ""
    status: str = "pending"
    review_note: str = ""
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Building:
    id: str
    name: str
    district: str
    address: str = ""
    aliases: list[str] = field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None
    year_built: int | None = None
    floors: int | None = None
    apartments_per_floor: int | None = None
    status: str = "active"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
