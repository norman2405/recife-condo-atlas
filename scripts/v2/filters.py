from __future__ import annotations

from dataclasses import dataclass, field

from .config import SETTINGS, Settings
from .models import Listing


@dataclass(slots=True)
class FilterResult:
    accepted: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def evaluate_listing(
    listing: Listing,
    settings: Settings = SETTINGS,
) -> FilterResult:
    reasons: list[str] = []
    warnings: list[str] = []

    if listing.district not in settings.allowed_districts:
        reasons.append("Stadtteil liegt nicht in Piedade oder Candeias.")

    if listing.bedrooms is None:
        warnings.append("Anzahl der Schlafzimmer fehlt.")
    elif listing.bedrooms < settings.minimum_bedrooms:
        reasons.append("Weniger als vier Schlafzimmer.")

    if listing.has_balcony is None:
        warnings.append("Varanda muss manuell geprüft werden.")
    elif listing.has_balcony is False:
        reasons.append("Keine Varanda erkannt.")

    if listing.has_sea_view is None:
        warnings.append("Meerblick muss manuell geprüft werden.")
    elif listing.has_sea_view is False:
        reasons.append("Kein Meerblick erkannt.")

    if listing.floor is None:
        warnings.append("Etage muss manuell geprüft werden.")
    elif listing.floor < settings.minimum_floor:
        reasons.append("Etage liegt unter der 6. Etage.")

    if listing.asking_price_brl is None:
        warnings.append("Preis muss manuell geprüft werden.")
    elif listing.asking_price_brl > settings.maximum_price_brl:
        reasons.append("Preis liegt über R$ 800.000.")

    return FilterResult(
        accepted=not reasons,
        reasons=reasons,
        warnings=warnings,
    )
