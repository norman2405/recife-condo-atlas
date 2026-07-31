from __future__ import annotations

from typing import Protocol

from ..models import Listing


class ListingSource(Protocol):
    name: str

    def collect(self) -> list[Listing]: ...
