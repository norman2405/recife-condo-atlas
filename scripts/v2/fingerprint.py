from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import Listing


TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "source",
    "ranking",
}


def normalize_url(url: str) -> str:
    value = url.strip()
    if not value:
        return ""

    parts = urlsplit(value)
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMETERS
    ]
    normalized_path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            normalized_path,
            urlencode(sorted(query)),
            "",
        )
    )


def create_fingerprint(listing: Listing) -> str:
    normalized_source_url = normalize_url(listing.source_url)

    if normalized_source_url:
        raw = f"{listing.source.lower()}|{normalized_source_url}"
    elif listing.external_id:
        raw = f"{listing.source.lower()}|{listing.external_id.strip().lower()}"
    else:
        raw = "|".join(
            [
                listing.source.strip().lower(),
                listing.building_name.strip().lower(),
                listing.district.strip().lower(),
                str(listing.asking_price_brl or ""),
                str(listing.area_m2 or ""),
                str(listing.bedrooms or ""),
            ]
        )

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
