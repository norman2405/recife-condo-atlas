from __future__ import annotations

import unittest

from scripts.v2.buildings import candidate_id, normalize_building_name, slugify_building_name


class BuildingNameTests(unittest.TestCase):
    def test_common_prefixes_are_ignored(self) -> None:
        self.assertEqual(
            normalize_building_name("Edifício Maria Eduarda"),
            normalize_building_name("Edf. Maria Eduarda"),
        )

    def test_accents_and_punctuation_are_normalized(self) -> None:
        self.assertEqual(normalize_building_name("Residencial Atlântico"), "atlantico")

    def test_slug_is_stable(self) -> None:
        self.assertEqual(slugify_building_name("Ed. Solar do Mar"), "solar-do-mar")

    def test_candidate_id_is_deterministic(self) -> None:
        first = candidate_id("Ed. Solar do Mar", "Piedade", "Av. Exemplo, 10")
        second = candidate_id("Edifício Solar do Mar", "Piedade", "Av. Exemplo, 10")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
