"""Testes de compatibilidade espacial/temporal com o Sentinel-2 — offline."""

from __future__ import annotations

import csv
import os
import tempfile
import unittest

from shapely.geometry import box

from agri import compat


class SpatialClassificationTest(unittest.TestCase):
    def test_municipality_is_contextual_not_direct(self):
        result = compat.classify_spatial("municipio", 0.004654)
        self.assertEqual(result["class"], compat.CLASS_B)
        self.assertIn("0.47%", result["justification"].replace(",", "."))

    def test_state_level_is_incompatible_for_aoi(self):
        result = compat.classify_spatial("uf", 0.004654)
        self.assertEqual(result["class"], compat.CLASS_C)

    def test_parcel_level_would_be_direct(self):
        result = compat.classify_spatial("propriedade", 0.004654)
        self.assertEqual(result["class"], compat.CLASS_A)

    def test_spatial_report_uses_real_geometry(self):
        municipality = box(-56.1167, -13.6661, -55.0851, -11.7216)
        aoi = box(-55.6309, -12.7339, -55.5709, -12.6739)
        report = compat.spatial_geometry_report(municipality, aoi)
        self.assertTrue(report["aoi_fully_inside_municipality"])
        self.assertAlmostEqual(report["aoi_outside_km2"], 0.0, places=6)
        self.assertLess(report["aoi_fraction_of_municipality"], 0.01)
        self.assertGreater(report["municipality_area_km2"], 9000)


class YearlyAggregationTest(unittest.TestCase):
    def _series(self, path):
        columns = [
            "month", "status", "reason", "item_id", "datetime", "tile", "baseline",
            "cloud_cover_tile_pct", "obstruction_fraction_aoi", "scl_profile", "index",
            "total_pixels", "valid_pixels", "valid_fraction", "area_km2_valid",
            "min", "max", "mean", "median", "std", "p05", "p25", "p75", "p95",
            "out_of_range_pixels", "degenerate_pixels", "scene_count",
        ]
        rows = [
            ["2023-01", "no_usable_observation", "all_candidates_exceed_max_obstruction"] + [""] * 7 + ["NDVI"] + [""] * 16,
            ["2023-02", "observed", "", "X", "2023-02-10T10:00:00Z", "MGRS-21LXG", "05.09",
             "10", "0.03", "B_restrictive", "NDVI", "100", "96", "0.96", "0.038",
             "0.1", "0.9", "0.42", "0.44", "0.2", "0.2", "0.3", "0.8", "0.7", "0", "0", "1"],
            ["2023-03", "observed", "", "X", "2023-03-02T10:00:00Z", "MGRS-21LXG", "05.09",
             "10", "0.02", "B_restrictive", "NDVI", "100", "98", "0.98", "0.039",
             "0.1", "0.9", "0.50", "0.52", "0.2", "0.2", "0.3", "0.8", "0.8", "0", "0", "1"],
        ]
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            writer.writerows(rows)

    def test_aggregation_keeps_missing_months_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "serie.csv")
            self._series(path)
            result = compat.s2_yearly_aggregation(path)
        self.assertEqual(result["status"], "ok")
        year = result["years"]["2023"]
        self.assertEqual(year["months_observed"], 2)
        self.assertEqual(year["months_total"], 3)
        self.assertEqual(year["months_missing"], ["2023-01"])
        self.assertAlmostEqual(year["ndvi_mean_of_monthly_means"], (0.42 + 0.50) / 2, places=6)
        self.assertIsNotNone(year["ndvi_coverage_weighted_mean"])

    def test_missing_series_is_reported(self):
        result = compat.s2_yearly_aggregation("arquivo/inexistente.csv")
        self.assertEqual(result["status"], "serie_ausente")


class TemporalOverlapTest(unittest.TestCase):
    def test_overlap_between_ibge_years_and_s2_years(self):
        records = [
            {"institution": "IBGE", "reference_year": "2023", "safra": None},
            {"institution": "IBGE", "reference_year": "2024", "safra": None},
            {"institution": "IBGE", "reference_year": "2015", "safra": None},
            {"institution": "CONAB", "reference_year": None, "safra": "23/24"},
        ]
        overlap = compat.temporal_overlap(records, ["2023", "2024", "2025"])
        self.assertEqual(overlap["ibge_years_overlapping_s2"], ["2023", "2024"])
        self.assertEqual(overlap["ibge_observations_in_overlap"], 2)
        self.assertEqual(overlap["conab_safras_in_overlap"], ["23/24"])
        self.assertIn("não são equivalentes", overlap["note"])


class CorrespondenceTableTest(unittest.TestCase):
    def test_table_joins_official_and_s2(self):
        records = [
            {
                "institution": "IBGE",
                "crop_name_normalized": "Soja",
                "crop_name_original": "Soja (em grão)",
                "crop_scope": "produto",
                "match_class": "exact",
                "geography_code": "5107925",
                "geography_name": "Sorriso (MT)",
                "geography_type": "municipio",
                "reference_year": "2023",
                "safra": None,
                "nature": "observed",
                "variable_normalized": "quantidade_produzida_t",
                "value_normalized": 2244375.0,
            },
            {
                "institution": "IBGE",
                "crop_name_normalized": "Soja",
                "crop_name_original": "Soja (em grão)",
                "crop_scope": "produto",
                "match_class": "exact",
                "geography_code": "5107925",
                "geography_name": "Sorriso (MT)",
                "geography_type": "municipio",
                "reference_year": "2023",
                "safra": None,
                "nature": "observed",
                "variable_normalized": "area_colhida_ha",
                "value_normalized": 598500.0,
            },
        ]
        s2 = {
            "years": {
                "2023": {
                    "months_observed": 11,
                    "months_total": 12,
                    "ndvi_coverage_weighted_mean": 0.498,
                    "months_missing": ["2023-01"],
                }
            }
        }
        rows = compat.correspondence_table(records, s2)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["crop"], "Soja")
        self.assertEqual(row["quantity_produced_t"], 2244375.0)
        self.assertEqual(row["area_harvested_ha"], 598500.0)
        self.assertTrue(row["ndvi_available"])
        self.assertAlmostEqual(row["ndvi_mean"], 0.498, places=6)
        self.assertEqual(row["ndvi_months_observed"], 11)

    def test_missing_s2_year_is_not_filled(self):
        records = [
            {
                "institution": "IBGE",
                "crop_name_normalized": "Soja",
                "crop_name_original": "Soja (em grão)",
                "crop_scope": "produto",
                "match_class": "exact",
                "geography_code": "5107925",
                "geography_name": "Sorriso (MT)",
                "geography_type": "municipio",
                "reference_year": "2019",
                "safra": None,
                "nature": "observed",
                "variable_normalized": "quantidade_produzida_t",
                "value_normalized": 1.0,
            }
        ]
        rows = compat.correspondence_table(records, {"years": {}})
        self.assertFalse(rows[0]["ndvi_available"])
        self.assertIsNone(rows[0]["ndvi_mean"])


class SeasonWindowTest(unittest.TestCase):
    def test_season_aggregation_requires_declared_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "serie.csv")
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["month", "status", "index", "mean", "valid_fraction"])
                writer.writerow(["2023-10", "observed", "NDVI", "0.6", "0.99"])
                writer.writerow(["2024-02", "observed", "NDVI", "0.4", "0.98"])
            result = compat.s2_season_aggregation(
                path, [("safra 2023/24", "2023-10", "2024-02", "declarado")]
            )
        self.assertEqual(result["status"], "ok")
        window = result["windows"]["safra 2023/24"]
        self.assertEqual(window["months_observed"], 2)
        self.assertAlmostEqual(window["ndvi_mean"], 0.5, places=6)

    def test_calendar_note_is_explicit(self):
        self.assertIn("calendário", compat.tmp_calendar_note())


if __name__ == "__main__":
    unittest.main()
