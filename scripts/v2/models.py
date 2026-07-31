from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class Listing:
    source: str
    source_url: str

    external_id: str = ""
    building_name: str = ""
    district: str = ""
    address: str = ""

    asking_price_brl: float | None = None
    area_m2: float | None = None
    price_per_m2: float | None = None

    bedrooms: int | None = None
    bathrooms: int | None = None
    parking_spaces: int | None = None
    floor: int | None = None

    has_balcony: bool | None = None
    has_sea_view: bool | None = None

    description: str = ""
    image_urls: list[str] = field(default_factory=list)

    status: str = "pending"
    found_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    fingerprint: str = ""
    review_warnings: list[str] = field(default_factory=list)
    review_note: str = ""

    def calculate_price_per_m2(self) -> None:
        if self.asking_price_brl and self.area_m2 and self.area_m2 > 0:
            self.price_per_m2 = round(self.asking_price_brl / self.area_m2, 2)

    def to_dict(self) -> dict[str, Any]:
        self.calculate_price_per_m2()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Listing":
        allowed = cls.__dataclass_fields__.keys()
        clean = {key: value for key, value in data.items() if key in allowed}
        return cls(**clean)
