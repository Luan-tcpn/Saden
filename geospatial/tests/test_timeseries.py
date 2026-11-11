"""Testes da série temporal (lógica pura, sem rede)."""

from __future__ import annotations

import csv
import os
import tempfile
import unittest

import numpy as np

from s2_poc import config
from s2_poc import timeseries as ts_mod


class MonthRangeTest(unittest.TestCase):
    def test_range_within_year(self):
        self.assertEqual(
            ts_mod.month_range("2023-01", "2023-04"),
            ["2023-01", "2023-02", "2023-03", "2023-04"],
        )

    def test_range_crossing_year(self):
        months = ts_mod.month_range("2023-11", "2024-02")
        self.assertEqual(months, ["2023-11", "2023-12", "2024-01", "2024-02"])

    def test_full_three_year_window(self):
        months = ts_mod.month_range("2023-01", "2025-12")
        self.assertEqual(len(months), 36)
        self.assertEqual(months[0], "2023-01")
        self.assertEqual(months[-1], "2025-12")

    def test_invalid_interval_raises(self):
        with self.assertRaises(ValueError):
            ts_mod.month_range("2025-12", "2023-01")

    def test_invalid_format_raises(self):
        with self.assertRaises(ValueError):
            ts_mod.month_range("2023/01", "2023-04")


class ObstructionTest(unittest.TestCase):
    def test_obstruction_fraction_counts_cloud_shadow_and_nodata(self):
        scl = np.array([[4, 4], [3, 9]], dtype="uint8")
        result = ts_mod.obstruction_fraction(scl)
        self.assertEqual(result["total_pixels"], 4)
        self.assertEqual(result["obstructed_pixels"], 2)
        self.assertAlmostEqual(result["obstruction_fraction"], 0.5, places=10)
        self.assertAlmostEqual(result["coverage_fraction"], 0.5, places=10)

    def test_dark_area_is_not_an_obstruction(self):
        scl = np.array([[2, 6], [4, 5]], dtype="uint8")
        result = ts_mod.obstruction_fraction(scl)
        self.assertEqual(result["obstructed_pixels"], 0)
        self.assertNotIn(2, result["obstruction_classes"])
        self.assertNotIn(6, result["obstruction_classes"])
        self.assertIn(3, result["obstruction_classes"])


class SelectionTest(unittest.TestCase):
    def test_lowest_obstruction_wins(self):
        candidates = [
            {"item_id": "b", "obstruction_fraction": 0.4, "cloud_cover": 1.0},
            {"item_id": "a", "obstruction_fraction": 0.1, "cloud_cover": 9.0},
        ]
        best, reason = ts_mod.choose_best_candidate(candidates)
        self.assertEqual(best["item_id"], "a")
        self.assertEqual(reason, "selected")

    def test_ties_use_cloud_then_item_id(self):
        candidates = [
            {"item_id": "z", "obstruction_fraction": 0.2, "cloud_cover": 5.0},
            {"item_id": "y", "obstruction_fraction": 0.2, "cloud_cover": 5.0},
            {"item_id": "x", "obstruction_fraction": 0.2, "cloud_cover": 1.0},
        ]
        best, _ = ts_mod.choose_best_candidate(candidates)
        self.assertEqual(best["item_id"], "x")

    def test_no_candidates(self):
        best, reason = ts_mod.choose_best_candidate([])
        self.assertIsNone(best)
        self.assertEqual(reason, ts_mod.REASON_NO_SCENE)


class SeriesTableTest(unittest.TestCase):
    def _observed(self):
        stats = {
            "total_pixels": 100,
            "valid_pixels": 80,
            "valid_fraction": 0.8,
            "min": -0.1,
            "max": 0.9,
            "mean": 0.5,
            "median": 0.55,
            "std": 0.1,
            "p05": 0.0,
            "p25": 0.3,
            "p75": 0.7,
            "p95": 0.9,
            "out_of_range_pixels": 0,
            "degenerate_pixels": 0,
        }
        return ts_mod.observed_month_record(
            month="2023-05",
            item_id="S2A_X",
            datetime_iso="2023-05-10T14:00:00Z",
            tile="MGRS-21LXG",
            baseline="05.09",
            cloud_cover=1.5,
            obstruction=0.02,
            profile="A_historical",
            indices={"NDVI": dict(stats), "EVI": dict(stats), "NDMI": dict(stats)},
        )

    def test_missing_month_is_explicit_and_empty(self):
        records = [
            self._observed(),
            ts_mod.missing_month_record("2023-06", ts_mod.REASON_ALL_CLOUDY, 3),
        ]
        rows = ts_mod.series_rows(records)
        missing = [r for r in rows if r["month"] == "2023-06"]
        self.assertEqual(len(missing), 1)
        row = missing[0]
        self.assertEqual(row["status"], ts_mod.STATUS_MISSING)
        self.assertEqual(row["reason"], ts_mod.REASON_ALL_CLOUDY)
        self.assertIsNone(row["mean"])
        self.assertIsNone(row["valid_pixels"])
        self.assertIsNone(row["item_id"])

    def test_observed_rows_carry_statistics_and_metadata(self):
        rows = ts_mod.series_rows([self._observed()])
        self.assertEqual(len(rows), 3)  # uma linha por índice
        ndvi = next(r for r in rows if r["index"] == "NDVI")
        self.assertEqual(ndvi["status"], ts_mod.STATUS_OBSERVED)
        self.assertEqual(ndvi["item_id"], "S2A_X")
        self.assertEqual(ndvi["baseline"], "05.09")
        self.assertAlmostEqual(ndvi["valid_fraction"], 0.8)
        self.assertAlmostEqual(ndvi["area_km2_valid"], 80 * 0.0004, places=9)
        self.assertEqual(ndvi["p25"], 0.3)
        self.assertEqual(ndvi["p75"], 0.7)

    def test_summary_counts_missing_months(self):
        records = [
            self._observed(),
            ts_mod.missing_month_record("2023-06", ts_mod.REASON_ALL_CLOUDY, 3),
            ts_mod.missing_month_record("2023-07", ts_mod.REASON_NO_SCENE, 0),
        ]
        summary = ts_mod.series_summary(records)
        self.assertEqual(summary["months_total"], 3)
        self.assertEqual(summary["months_observed"], 1)
        self.assertEqual(summary["months_missing"], 2)
        self.assertEqual(summary["missing_months"], ["2023-06", "2023-07"])
        self.assertIn(ts_mod.REASON_ALL_CLOUDY, summary["missing_reasons"])
        self.assertEqual(summary["baselines"], ["05.09"])

    def test_csv_is_written_with_bom_and_columns(self):
        records = [self._observed(), ts_mod.missing_month_record("2023-06", ts_mod.REASON_NO_SCENE)]
        rows = ts_mod.series_rows(records)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "series.csv")
            ts_mod.write_series_csv(rows, path)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(3), b"\xef\xbb\xbf")
            with open(path, newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                self.assertEqual(reader.fieldnames, ts_mod.SERIES_CSV_COLUMNS)
                read_rows = list(reader)
        self.assertEqual(len(read_rows), 4)
        statuses = {r["month"]: r["status"] for r in read_rows}
        self.assertEqual(statuses["2023-05"], ts_mod.STATUS_OBSERVED)
        self.assertEqual(statuses["2023-06"], ts_mod.STATUS_MISSING)


class ObstructionClassesTest(unittest.TestCase):
    def test_obstruction_classes_exclude_dark_area_and_water(self):
        self.assertNotIn(2, config.SCL_OBSTRUCTION_CLASSES)
        self.assertNotIn(6, config.SCL_OBSTRUCTION_CLASSES)
        for code in (0, 1, 3, 7, 8, 9, 10, 11):
            self.assertIn(code, config.SCL_OBSTRUCTION_CLASSES)


if __name__ == "__main__":
    unittest.main()
