from __future__ import annotations

import unittest

from scripts.v2.sources.vivareal import (
    extract_detail_links,
    normalize_detail_url,
)


class VivaRealLinkTests(unittest.TestCase):
    def test_normalizes_tracking_url(self) -> None:
        raw = (
            "/imovel/apartamento-4-quartos-candeias-"
            "jaboatao-dos-guararapes-150m2-venda-RS750000-id-2900316900/"
            "?source=ranking#gallery"
        )

        self.assertEqual(
            normalize_detail_url(raw),
            "https://www.vivareal.com.br/imovel/"
            "apartamento-4-quartos-candeias-jaboatao-dos-guararapes-"
            "150m2-venda-RS750000-id-2900316900/",
        )

    def test_extracts_and_deduplicates_links(self) -> None:
        page_html = """
        <html><body>
          <a href="/imovel/apartamento-4-quartos-piedade-id-2900316900/">
            Primeiro
          </a>
          <a href="/imovel/apartamento-4-quartos-piedade-id-2900316900/?x=1">
            Duplikat
          </a>
          <script>
            const item = "https:\\/\\/www.vivareal.com.br\\/imovel\\/apartamento-4-quartos-candeias-id-2888054382\\/";
          </script>
          <a href="https://example.com/imovel/invalido-id-1234567890/">Fremd</a>
        </body></html>
        """

        self.assertEqual(
            extract_detail_links(page_html, limit=10),
            [
                "https://www.vivareal.com.br/imovel/"
                "apartamento-4-quartos-piedade-id-2900316900/",
                "https://www.vivareal.com.br/imovel/"
                "apartamento-4-quartos-candeias-id-2888054382/",
            ],
        )

    def test_respects_limit(self) -> None:
        page_html = "".join(
            f'<a href="/imovel/apartamento-4-quartos-candeias-id-{2900000000 + i}/">x</a>'
            for i in range(5)
        )

        self.assertEqual(len(extract_detail_links(page_html, limit=2)), 2)


if __name__ == "__main__":
    unittest.main()
