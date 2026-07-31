from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    repository_root: Path = Path(__file__).resolve().parents[2]
    data_dir: Path = repository_root / "data"
    pending_file: Path = data_dir / "pending-listings.json"
    approved_file: Path = data_dir / "listings.json"
    rejected_file: Path = data_dir / "rejected-listings.json"

    allowed_districts: frozenset[str] = frozenset({"Piedade", "Candeias"})
    minimum_bedrooms: int = 4
    minimum_floor: int = 6
    maximum_price_brl: int = 800_000

    # Conservative defaults for future web adapters.
    request_timeout_seconds: int = 20
    maximum_detail_pages_per_source: int = 10
    delay_between_requests_seconds: float = 4.0


SETTINGS = Settings()
