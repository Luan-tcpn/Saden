"""Testes de renderização e utilidades do pipeline (sem rede)."""

from __future__ import annotations

import csv
import os
import tempfile
import unittest

import numpy as np

from s2_poc import pipeline, render


class FakeItem:
    def __init__(self, item_id, dt, cloud, bbox):
        self.id = item_id
        self.properties = {"datetime": dt, "eo:cloud_cover": cloud}
        self.bbox = bbox


class RenderTest(unittest.TestCase):
    def test_preview_is_written(self):
        grid = {
            "crs": "EPSG:32721",
            "res": 20.0,
            "width": 32,
            "height": 24,
            "bounds": [0.0, 0.0, 640.0, 480.0],
            "transform": [20.0, 0.0, 0.0, 0.0, -20.0, 480.0],
        }
        rng = np.random.default_rng(42)
        indices = {
            "NDVI": rng.uniform(-0.2, 0.9, (24, 32)).astype("float32"),
            "EVI": rng.uniform(-0.2, 0.9, (24, 32)).astype("float32"),
            "NDMI": rng.uniform(-0.5, 0.5, (24, 32)).astype("float32"),
        }
        indices["NDVI"][0, 0] = np.nan
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "preview.png")
            render.render_indices(indices, grid, out, title="teste")
            self.assertTrue(os.path.exists(out))
            self.assertGreater(os.path.getsize(out), 1000)


class SelectScenesTest(unittest.TestCase):
    def test_one_scene_per_month_with_lowest_cloud(self):
        items = [
            FakeItem("a", "2025-07-01T10:00:00Z", 5.0, []),
            FakeItem("b", "2025-07-15T10:00:00Z", 1.0, []),
            FakeItem("c", "2025-08-02T10:00:00Z", 0.5, []),
            FakeItem("d", "2025-07-20T10:00:00Z", 1.0, []),
        ]
        from s2_poc import stac_search

        selected = stac_search.select_scenes(items, max_scenes=5)
        self.assertEqual([it.id for it in selected], ["b", "c"])  # b antes de d por id
        # determinístico
        self.assertEqual([it.id for it in stac_search.select_scenes(items)], ["b", "c"])

    def test_max_scenes_limits_result(self):
        items = [FakeItem(str(i), f"2025-0{i}-01T10:00:00Z", 1.0, []) for i in range(1, 6)]
        from s2_poc import stac_search

        self.assertEqual(len(stac_search.select_scenes(items, max_scenes=2)), 2)

    def test_filter_covering_requires_full_aoi(self):
        aoi = [0.0, 0.0, 1.0, 1.0]
        inside = FakeItem("in", "2025-07-01T10:00:00Z", 1.0, [-1.0, -1.0, 2.0, 2.0])
        partial = FakeItem("part", "2025-07-02T10:00:00Z", 1.0, [0.5, 0.5, 2.0, 2.0])
        from s2_poc import stac_search

        self.assertEqual([it.id for it in stac_search.filter_covering([inside, partial], aoi)], ["in"])


class JsonableTest(unittest.TestCase):
    def test_nan_and_inf_become_null_and_numpy_scalars_convert(self):
        data = {
            "nan": float("nan"),
            "inf": float("inf"),
            "n": np.int64(7),
            "arr": np.array([1.0, 2.0]),
        }
        out = pipeline._jsonable(data)
        self.assertIsNone(out["nan"])
        self.assertIsNone(out["inf"])
        self.assertEqual(out["n"], 7)
        self.assertEqual(out["arr"], [1.0, 2.0])


class TemporalCsvTest(unittest.TestCase):
    def test_csv_columns_and_utf8_bom(self):
        rows = [
            {
                "date": "2025-07-24",
                "item_id": "S2C_X",
                "index": "NDVI",
                "total_pixels": 100,
                "valid_pixels": 90,
                "valid_fraction": 0.9,
                "min": -0.1,
                "max": 0.95,
                "mean": 0.6,
                "median": 0.62,
                "p05": 0.2,
                "p95": 0.9,
                "std": 0.1,
                "out_of_range_pixels": 0,
                "degenerate_pixels": 0,
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "series.csv")
            pipeline.write_temporal_csv(rows, path)
            with open(path, "rb") as fh:
                self.assertTrue(fh.read(3) == b"\xef\xbb\xbf", "CSV deve ter BOM UTF-8")
            with open(path, newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                self.assertEqual(reader.fieldnames, pipeline.CSV_COLUMNS)
                read_rows = list(reader)
            self.assertEqual(len(read_rows), 1)
            self.assertEqual(read_rows[0]["index"], "NDVI")


if __name__ == "__main__":
    unittest.main()
