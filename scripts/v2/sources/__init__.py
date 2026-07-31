from __future__ import annotations

from .base import ListingSource


def enabled_sources() -> list[ListingSource]:
    """Return active source adapters.

    Sprint 1 intentionally enables no network source. This lets the
    architecture be validated without changing production data.
    """
    return []


__all__ = ["ListingSource", "enabled_sources"]
