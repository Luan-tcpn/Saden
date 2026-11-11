"""Testes da V2.3 — perfil radiométrico histórico, uso do solo e estudo — offline."""

from __future__ import annotations

import unittest

import numpy as np

from historical import landuse as lu
from historical import radiometry as radio
from historical import series as series_mod
from historical import study as study_mod


class FakeAsset:
    def __init__(self, href="https://example.invalid/B04.tif", scale=None, offset=None):
        self.href = href
        band = {"nodata": 0, "data_type": "uint16", "spatial_resolution": 10}
        if scale is not None:
            band["scale"] = scale
        if offset is not None:
            band["offset"] = offset
        self.extra_fields = {"raster:bands": [band]}


class FakeItem:
    def __init__(self, item_id="ITEM", datetime="2019-06-10T14:00:00Z", baseline="03.01",
                 scale=0.0001, offset=-0.1, names=("red", "nir", "scl")):
        self.id = item_id
        self.properties = {
            "datetime": datetime,
            "s2:processing_baseline": baseline,
            "grid:code": "MGRS-21LXG",
        }
        self.assets = {
            name: FakeAsset(
                href=f"https://example.invalid/{name}.tif", scale=scale, offset=offset
            )
            for name in names
        }
        self.bbox = [-56.0, -13.0, -55.0, -12.0]


class RadiometryProfileTest(unittest.TestCase):
    def test_parse_baseline(self):
        self.assertAlmostEqual(radio.parse_baseline("05.11"), 5.11)
        self.assertIsNone(radio.parse_baseline(None))
        self.assertIsNone(radio.parse_baseline("abc"))

    def test_baseline_rule(self):
        self.assertEqual(radio.baseline_derived_offsets(5.11)["offset"], -0.1)
        self.assertEqual(radio.baseline_derived_offsets(3.01)["offset"], 0.0)
        self.assertIsNone(radio.baseline_derived_offsets(None)["profile"])

    def test_date_rule(self):
        self.assertEqual(
            radio.date_derived_offsets("2021-12-31")["offset"], 0.0
        )
        self.assertEqual(
            radio.date_derived_offsets("2022-01-25")["offset"], -0.1
        )

    def test_c1_uses_uniform_offset(self):
        item = FakeItem(baseline="05.00", scale=0.0001, offset=-0.1)
        profile = radio.item_radiometry(item, radio.COLLECTION_C1)
        self.assertEqual(profile["profile"], radio.PROFILE_C1_HARMONIZED)
        self.assertEqual(profile["offset"], -0.1)
        self.assertEqual(profile["offset_source"], "metadata")

    def test_original_uses_dn_convention_without_offset(self):
        item = FakeItem(baseline="03.01", scale=0.0001, offset=-0.1)
        profile = radio.item_radiometry(item, radio.COLLECTION_ORIGINAL)
        self.assertEqual(profile["profile"], radio.PROFILE_ORIGINAL_PRE_OFFSET)
        self.assertEqual(profile["offset"], 0.0)
        self.assertIsNotNone(profile["offset_warning"])

    def test_original_uses_dn_convention_for_all_dates(self):
        # Convenção de DN verificada empiricamente (diferença de NDVI = 0,0 entre
        # a coleção original e a C1) — vale para todo o arquivo.
        item = FakeItem(datetime="2023-05-10T14:00:00Z", baseline="05.11",
                        scale=0.0001, offset=-0.1)
        profile = radio.item_radiometry(item, radio.COLLECTION_ORIGINAL)
        self.assertEqual(profile["offset"], 0.0)
        self.assertEqual(profile["profile"], radio.PROFILE_ORIGINAL_PRE_OFFSET)

    def test_missing_metadata_falls_back_to_collection_rule(self):
        item = FakeItem(scale=None, offset=None)
        profile = radio.item_radiometry(item, radio.COLLECTION_C1)
        self.assertEqual(profile["offset"], -0.1)
        self.assertEqual(profile["offset_source"], "collection_rule")

    def test_inconsistent_bands_are_rejected(self):
        item = FakeItem()
        item.assets["nir"].extra_fields["raster:bands"][0]["offset"] = 0.0
        profile = radio.item_radiometry(item, radio.COLLECTION_C1)
        self.assertFalse(profile["bands_consistent"])
        with self.assertRaises(ValueError):
            radio.assert_usable(profile)

    def test_usable_item_passes(self):
        profile = radio.item_radiometry(FakeItem(), radio.COLLECTION_C1)
        radio.assert_usable(profile)


class SeriesHelperTest(unittest.TestCase):
    def test_month_list(self):
        months = series_mod.month_list("2017-01", "2017-04")
        self.assertEqual(months, ["2017-01", "2017-02", "2017-03", "2017-04"])

    def test_asset_alias_resolution(self):
        item = FakeItem(names=("B04", "B08", "SCL"))
        self.assertTrue(series_mod.asset_href_for(item, "red").endswith("B04.tif"))
        self.assertTrue(series_mod.asset_href_for(item, "scl").endswith("SCL.tif"))

    def test_missing_asset_raises(self):
        item = FakeItem(names=("red", "nir"))
        with self.assertRaises(KeyError):
            series_mod.asset_href_for(item, "scl")

    def test_selection_prefers_lowest_obstruction(self):
        candidates = [
            {"item_id": "a", "obstruction_fraction": 0.4, "cloud_cover": 1.0},
            {"item_id": "b", "obstruction_fraction": 0.1, "cloud_cover": 9.0},
        ]
        best, reason = series_mod.select_month_scene(candidates, max_obstruction=0.5)
        self.assertEqual(best["item_id"], "b")
        self.assertEqual(reason, "selected")

    def test_selection_rejects_all_cloudy(self):
        candidates = [{"item_id": "a", "obstruction_fraction": 0.9, "cloud_cover": 90.0}]
        best, reason = series_mod.select_month_scene(candidates, max_obstruction=0.5)
        self.assertIsNone(best)
        self.assertEqual(reason, "all_candidates_exceed_max_obstruction")


class LandUseTest(unittest.TestCase):
    def test_tile_name(self):
        # a nomeação usa o limite inferior da faixa de 3°
        self.assertEqual(lu.worldcover_tile_name([-55.63, -12.73, -55.57, -12.67]), "S15W057")
        self.assertEqual(lu.worldcover_tile_name([-45.0, -12.0, -44.0, -11.0]), "S12W045")

    def test_class_areas_sum_to_total(self):
        data = np.array([[40, 40], [30, 10]], dtype="uint8")
        report = lu.class_areas(data, lon_res=0.0001, lat_res=0.0001,
                               lat_min=-12.7, lat_max=-12.69)
        total = sum(c["area_km2"] for c in report["classes"].values())
        self.assertAlmostEqual(total, report["total_area_km2"], places=6)
        self.assertIn("40", report["classes"])
        self.assertIn("Cropland", report["classes"]["40"]["name"])

    def test_cropland_mask(self):
        data = np.array([[40, 30], [40, 40]], dtype="uint8")
        mask = lu.cropland_mask(data)
        self.assertEqual(int(mask.sum()), 3)

    def test_mask_to_grid_threshold(self):
        mask = np.ones((4, 4), dtype=bool)
        mask[0:2, 0:2] = False  # bloco superior esquerdo sem cobertura
        out = lu.mask_to_grid(mask, (2, 2))
        self.assertEqual(out.shape, (2, 2))
        self.assertFalse(bool(out[0, 0]))
        self.assertTrue(bool(out[0, 1]))
        self.assertTrue(bool(out[1, 0]))
        self.assertTrue(bool(out[1, 1]))


class YieldExtractionTest(unittest.TestCase):
    def _row(self, year="2023", code="40124", variable="rendimento_medio_kg_ha", value="3750"):
        return {
            "institution": "IBGE",
            "geography_code": "5107925",
            "geography_type": "municipio",
            "crop_code": code,
            "crop_name_original": "Soja (em grão)",
            "crop_scope": "produto",
            "reference_year": year,
            "variable_normalized": variable,
            "value_normalized": value,
            "unit_original": "Quilogramas por Hectare",
            "nature": "observed",
            "dataset_name": "Produção Agrícola Municipal (PAM)",
            "dataset_id": "SIDRA:5457",
            "acquired_at": "2026-11-11T00:00:00+00:00",
        }

    def test_extracts_yield_area_and_quantity(self):
        rows = [
            self._row(),
            self._row(variable="area_colhida_ha", value="598500"),
            self._row(variable="quantidade_produzida_t", value="2244375"),
        ]
        yields = study_mod.extract_yields(rows)
        entry = yields["soja"]["2023"]
        self.assertEqual(entry["yield_kg_ha"], 3750.0)
        self.assertEqual(entry["area_harvested_ha"], 598500.0)
        self.assertEqual(entry["quantity_produced_t"], 2244375.0)
        self.assertEqual(entry["yield_unit_original"], "Quilogramas por Hectare")

    def test_other_crops_are_ignored(self):
        yields = study_mod.extract_yields([self._row(code="40127")])
        self.assertNotIn("trigo", yields)


class IndicatorTest(unittest.TestCase):
    def test_yearly_indicators(self):
        rows = [
            {"month": "2023-01", "status": "observed", "ndvi_mean": "0.40", "ndvi_median": "0.41",
             "valid_fraction": "0.98", "baseline": "05.09", "item_id": "X", "catalog": "earth-search"},
            {"month": "2023-02", "status": "observed", "ndvi_mean": "0.50", "ndvi_median": "0.51",
             "valid_fraction": "0.96", "baseline": "05.09", "item_id": "Y", "catalog": "earth-search"},
            {"month": "2023-03", "status": "no_usable_observation"},
        ]
        indicators = study_mod.yearly_indicators(rows)
        year = indicators["2023"]
        self.assertEqual(year["months_observed"], 2)
        self.assertAlmostEqual(year["ndvi_mean_of_monthly_means"], 0.45, places=6)
        self.assertAlmostEqual(year["mean_valid_fraction"], 0.97, places=6)


class DatasetTest(unittest.TestCase):
    def test_paired_and_excluded_records(self):
        yields = {
            "soja": {
                "2023": {"yield_kg_ha": 3750.0, "yield_unit_original": "kg/ha",
                         "area_harvested_ha": 598500.0, "quantity_produced_t": 2244375.0},
                "2024": {"yield_kg_ha": 3480.0, "yield_unit_original": "kg/ha",
                         "area_harvested_ha": 599000.0, "quantity_produced_t": 2084520.0},
            }
        }
        indicators = {
            "2023": {"ndvi_mean_of_monthly_means": 0.498, "ndvi_median_of_monthly_medians": 0.5,
                      "ndvi_std_of_monthly_means": 0.1, "ndvi_min_monthly_mean": 0.2,
                      "ndvi_max_monthly_mean": 0.8, "months_observed": 11,
                      "months": ["2023-01", "2023-02"], "mean_valid_fraction": 0.99,
                      "min_valid_fraction": 0.9, "baselines": ["05.09"], "items": ["X"]},
        }
        dataset = study_mod.build_dataset(yields, indicators)
        soja = [r for r in dataset if r["crop"] == "soja"]
        paired = [r for r in soja if r["status"] == "paired_usable"]
        self.assertEqual(len(paired), 1)
        self.assertEqual(paired[0]["year"], "2023")
        excluded = [r for r in soja if r["status"] == "excluded"]
        self.assertTrue(excluded)
        self.assertIn("Sentinel-2", excluded[0]["exclusion_reason"])

    def test_gate_requires_minimum_pairs(self):
        stats = {"crops": {"soja": {"n_pairs": 9}, "milho": {"n_pairs": 5}}}
        gate = study_mod.gate_evaluation(stats, minimum_pairs=9)
        self.assertFalse(gate["modeling_gate_open"])
        self.assertTrue(gate["per_crop_meets_minimum"]["soja"])
        self.assertFalse(gate["per_crop_meets_minimum"]["milho"])


class StatisticsTest(unittest.TestCase):
    def test_pearson_and_spearman(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        self.assertAlmostEqual(study_mod.pearson(x, y), 1.0, places=9)
        self.assertAlmostEqual(study_mod.spearman(x, y), 1.0, places=9)

    def test_constant_series_returns_none(self):
        self.assertIsNone(study_mod.pearson([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]))

    def test_linear_slope_and_detrend(self):
        x = [0.0, 1.0, 2.0, 3.0]
        y = [1.0, 3.0, 5.0, 7.0]
        self.assertAlmostEqual(study_mod.linear_slope(x, y), 2.0, places=9)
        residuals = study_mod.detrend(y, x)
        for value in residuals:
            self.assertAlmostEqual(value, 0.0, places=9)

    def test_permutation_p_is_deterministic(self):
        rng = np.random.default_rng(7)
        x = list(rng.normal(size=8))
        y = [v * 0.5 + 1 for v in x]
        first = study_mod.permutation_p_value(x, y, permutations=300, seed=42)
        second = study_mod.permutation_p_value(x, y, permutations=300, seed=42)
        self.assertEqual(first, second)
        self.assertTrue(0.0 < first <= 1.0)

    def test_exploratory_stats_reports_sample_size(self):
        dataset = [
            {"crop": "soja", "status": "paired_usable", "year": str(2018 + i),
             "yield_kg_ha": 3000.0 + 10 * i, "ndvi_aoi_mean": 0.4 + 0.01 * i}
            for i in range(5)
        ]
        stats = study_mod.exploratory_stats(dataset, permutations=100)
        self.assertEqual(stats["crops"]["soja"]["n_pairs"], 5)
        self.assertAlmostEqual(stats["crops"]["soja"]["pearson_r"], 1.0, places=6)
        self.assertIn("exploratórias", stats["notes"][0])


if __name__ == "__main__":
    unittest.main()
