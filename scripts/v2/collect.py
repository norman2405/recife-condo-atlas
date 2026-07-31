from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow both `python -m scripts.v2.collect` and `python scripts/v2/collect.py`.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.v2.config import SETTINGS
    from scripts.v2.filters import evaluate_listing
    from scripts.v2.fingerprint import create_fingerprint
    from scripts.v2.logger import configure_logging
    from scripts.v2.models import Listing
    from scripts.v2.sources import enabled_sources
    from scripts.v2.storage import load_json_list, save_json_list_atomic
else:
    from .config import SETTINGS
    from .filters import evaluate_listing
    from .fingerprint import create_fingerprint
    from .logger import configure_logging
    from .models import Listing
    from .sources import enabled_sources
    from .storage import load_json_list, save_json_list_atomic


def known_fingerprints(items: list[dict[str, object]]) -> set[str]:
    values: set[str] = set()
    for item in items:
        fingerprint = str(item.get("fingerprint", "")).strip()
        if fingerprint:
            values.add(fingerprint)
    return values


def run(*, dry_run: bool) -> int:
    logger = configure_logging()
    pending = load_json_list(SETTINGS.pending_file)
    approved = load_json_list(SETTINGS.approved_file)
    existing = known_fingerprints(pending + approved)

    sources = enabled_sources()
    logger.info("V2 Collector gestartet; aktive Quellen: %d", len(sources))

    new_items: list[dict[str, object]] = []

    for source in sources:
        logger.info("Quelle %s wird gelesen.", source.name)
        try:
            collected = source.collect()
        except Exception as error:  # One source must not stop all others.
            logger.exception("Quelle %s fehlgeschlagen: %s", source.name, error)
            continue

        logger.info("Quelle %s lieferte %d Datensätze.", source.name, len(collected))

        for listing in collected:
            if not isinstance(listing, Listing):
                logger.warning("Quelle %s lieferte einen ungültigen Datensatz.", source.name)
                continue

            listing.fingerprint = create_fingerprint(listing)
            if listing.fingerprint in existing:
                continue

            result = evaluate_listing(listing)
            if not result.accepted:
                logger.info(
                    "Abgelehnt: %s (%s)",
                    listing.source_url,
                    "; ".join(result.reasons),
                )
                continue

            listing.review_warnings = result.warnings
            new_items.append(listing.to_dict())
            existing.add(listing.fingerprint)

    logger.info("Neue Prüfkandidaten: %d", len(new_items))

    if dry_run:
        logger.info("Dry-run: pending-listings.json bleibt unverändert.")
        return 0

    if new_items:
        save_json_list_atomic(SETTINGS.pending_file, pending + new_items)
        logger.info("pending-listings.json wurde sicher aktualisiert.")
    else:
        logger.info("Keine Dateiänderung erforderlich.")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recife Condo Atlas Collector V2")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Quellen und Filter testen, aber keine JSON-Datei verändern.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
