from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.v2.filters import evaluate_listing
from scripts.v2.fingerprint import create_fingerprint, normalize_url
from scripts.v2.models import Listing
from scripts.v2.storage import load_json_list, save_json_list_atomic


class FingerprintTests(unittest.TestCase):
    def test_tracking_parameters_do_not_change_fingerprint(self) -> None:
        first = Listing(
            source="vivareal",
            source_url="https://example.com/imovel/123/?source=ranking&utm_source=x",
        )
        second = Listing(
            source="vivareal",
            source_url="https://example.com/imovel/123",
        )
        self.assertEqual(create_fingerprint(first), create_fingerprint(second))

    def test_url_normalization_removes_fragment(self) -> None:
        self.assertEqual(
            normalize_url("HTTPS://Example.com/path/?utm_campaign=x#gallery"),
            "https://example.com/path",
        )


class FilterTests(unittest.TestCase):
    def test_matching_listing_is_accepted(self) -> None:
        listing = Listing(
            source="test",
            source_url="https://example.com/1",
            district="Candeias",
            asking_price_brl=790_000,
            bedrooms=4,
            floor=8,
            has_balcony=True,
            has_sea_view=True,
        )
        result = evaluate_listing(listing)
        self.assertTrue(result.accepted)
        self.assertEqual(result.reasons, [])

    def test_unknown_floor_is_warning_not_rejection(self) -> None:
        listing = Listing(
            source="test",
            source_url="https://example.com/2",
            district="Piedade",
            asking_price_brl=700_000,
            bedrooms=4,
            has_balcony=True,
            has_sea_view=True,
        )
        result = evaluate_listing(listing)
        self.assertTrue(result.accepted)
        self.assertIn("Etage muss manuell geprüft werden.", result.warnings)


class StorageTests(unittest.TestCase):
    def test_atomic_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            value = [{"source": "test", "fingerprint": "abc"}]
            save_json_list_atomic(path, value)
            self.assertEqual(load_json_list(path), value)


if __name__ == "__main__":
    unittest.main()
