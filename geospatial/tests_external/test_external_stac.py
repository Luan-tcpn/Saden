"""Testes EXTERNOS (rede). Não fazem parte da suíte offline.

Estes testes consultam de verdade o catálogo STAC da Earth Search e a API de
malhas do IBGE. Para executá-los é preciso habilitá-los explicitamente:

    $env:SADEN_EXTERNAL_TESTS = "1"
    geospatial\\.venv\\Scripts\\python.exe -m unittest discover -s geospatial\\tests_external -t geospatial

A suíte padrão (``geospatial/tests``) permanece 100% offline.
"""

from __future__ import annotations

import os
import unittest

from s2_poc import config, geometry, network, stac_search

ENABLED = os.environ.get("SADEN_EXTERNAL_TESTS") == "1"
SKIP_REASON = (
    "teste externo: defina SADEN_EXTERNAL_TESTS=1 para executar (requer internet)"
)


@unittest.skipUnless(ENABLED, SKIP_REASON)
class CatalogTest(unittest.TestCase):
    def test_collection_is_reachable_and_documented(self):
        network.configure_tls()
        client = stac_search.open_catalog()
        meta = stac_search.collection_metadata(client)
        self.assertEqual(meta["id"], config.COLLECTION)
        self.assertIsNotNone(meta["license"])

    def test_items_cover_the_validation_aoi(self):
        network.configure_tls()
        client = stac_search.open_catalog()
        bbox = geometry.validation_aoi_bbox()
        items = stac_search.search_items(
            client, bbox, start="2025-06-01", end="2025-09-30", max_cloud=20.0
        )
        self.assertGreater(len(items), 0)
        covering = stac_search.filter_covering(items, bbox)
        self.assertGreater(len(covering), 0)

    def test_two_tiles_share_the_same_datetime(self):
        network.configure_tls()
        client = stac_search.open_catalog()
        bbox = list(config.MOSAIC_AOI["bbox"])
        items = stac_search.search_items(
            client, bbox, start="2025-01-01", end="2025-12-31", max_cloud=100.0
        )
        by_dt: dict[str, set[str]] = {}
        for item in items:
            dt = item.properties.get("datetime")
            tile = item.properties.get("grid:code")
            if dt and tile:
                by_dt.setdefault(dt, set()).add(tile)
        pairs = [dt for dt, tiles in by_dt.items() if {"MGRS-21LXG", "MGRS-21LXF"} <= tiles]
        self.assertGreater(len(pairs), 0)


@unittest.skipUnless(ENABLED, SKIP_REASON)
class MunicipalityTest(unittest.TestCase):
    def test_official_mesh_is_valid_and_named(self):
        municipality = geometry.load_municipality("maxima")
        self.assertTrue(municipality["is_valid"])
        self.assertFalse(municipality["is_empty"])
        self.assertEqual(municipality["municipality"]["ibge_code"], "5107925")
        self.assertEqual(municipality["municipality"]["name"], "Sorriso")
        self.assertGreater(municipality["area_km2_geodesic"], 9000)


if __name__ == "__main__":
    unittest.main()
