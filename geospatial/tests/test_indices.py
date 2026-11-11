"""Testes das fórmulas, escala e máscaras (dados sintéticos, sem rede)."""

from __future__ import annotations

import unittest

import numpy as np

from s2_poc import config
from s2_poc import indices as ix


class ScaleTest(unittest.TestCase):
    def test_nodata_is_masked_before_scaling(self):
        dn = np.array([0, 1000, 2000], dtype="uint16")
        out = ix.scale_reflectance(dn, scale=1e-4, offset=-0.1, nodata=0)
        self.assertTrue(np.isnan(out[0]))
        self.assertAlmostEqual(out[1], 0.0, places=10)
        self.assertAlmostEqual(out[2], 0.1, places=10)

    def test_non_finite_input_becomes_nan(self):
        dn = np.array([1000, 2000], dtype="float32")
        dn[1] = np.nan
        out = ix.scale_reflectance(dn, 1e-4, -0.1, nodata=0)
        self.assertAlmostEqual(out[0], 0.0, places=10)
        self.assertTrue(np.isnan(out[1]))


class FormulaTest(unittest.TestCase):
    def test_ndvi_known_value(self):
        out = ix.compute_ndvi(np.array([0.6]), np.array([0.2]))
        self.assertAlmostEqual(out[0], 0.5, places=10)

    def test_evi_known_value(self):
        out = ix.compute_evi(np.array([0.5]), np.array([0.2]), np.array([0.1]))
        # 2.5*(0.3) / (0.5 + 1.2 - 0.75 + 1) = 0.75/1.95
        self.assertAlmostEqual(out[0], 0.75 / 1.95, places=10)

    def test_ndmi_known_value(self):
        out = ix.compute_ndmi(np.array([0.5]), np.array([0.2]))
        self.assertAlmostEqual(out[0], 0.3 / 0.7, places=10)

    def test_zero_denominator_yields_nan_not_inf(self):
        out = ix.compute_ndvi(np.array([-0.1]), np.array([0.1]))
        self.assertTrue(np.isnan(out[0]))

    def test_evi_degenerate_denominator_yields_nan(self):
        # den = 0.1 + 0.6 - 7.5*blue + 1 = 0  => blue = 1.7/7.5
        blue = (0.1 + 0.6 + 1.0) / 7.5
        out = ix.compute_evi(np.array([0.1]), np.array([0.1]), np.array([blue]))
        self.assertTrue(np.isnan(out[0]))

    def test_nan_propagates(self):
        out = ix.compute_ndvi(np.array([np.nan]), np.array([0.2]))
        self.assertTrue(np.isnan(out[0]))

    def test_shape_mismatch_raises(self):
        with self.assertRaises(ValueError):
            ix.safe_ratio(np.zeros((2, 2)), np.zeros((2, 3)))


class SclMaskTest(unittest.TestCase):
    def test_bad_and_unclassified_classes_removed(self):
        scl = np.array(
            [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]], dtype="uint8"
        )
        keep = ix.scl_keep_mask(scl)
        kept = set(scl[keep].tolist())
        self.assertEqual(kept, {2, 4, 5, 6})
        # água (6) e solo (5) permanecem: máscara de qualidade != agronomia
        self.assertIn(6, kept)
        self.assertIn(5, kept)

    def test_scl_config_classes_are_documented(self):
        self.assertEqual(set(config.SCL_BAD_CLASSES), {0, 1, 3, 8, 9, 10, 11})
        self.assertEqual(config.SCL_UNCLASSIFIED, 7)


class ComputeIndicesTest(unittest.TestCase):
    def _scene(self):
        shape = (4, 4)
        red = np.full(shape, 2000, dtype="uint16")
        nir = np.full(shape, 6000, dtype="uint16")
        blue = np.full(shape, 1000, dtype="uint16")
        swir = np.full(shape, 3000, dtype="uint16")
        scl = np.full(shape, 4, dtype="uint8")
        red[0, 0] = 0          # nodata -> deve sair de todos os índices
        scl[0, 1] = 9          # nuvem alta -> mascarado
        scl[0, 2] = 6          # água -> mantido (não é nuvem)
        scale = {"scale": 1e-4, "offset": -0.1, "nodata": 0.0}
        return {
            "bands": {"blue": blue, "red": red, "nir": nir, "swir": swir},
            "scl": scl,
            "scales": {k: dict(scale) for k in ("blue", "red", "nir", "swir")},
            "grid": {"crs": "EPSG:32721", "res": 20.0, "width": 4, "height": 4,
                     "bounds": [0, 0, 80, 80], "transform": [20, 0, 0, 0, -20, 80]},
        }

    def test_expected_values_and_masks(self):
        out = ix.compute_indices(self._scene())
        ndvi, evi, ndmi = out["indices"]["NDVI"], out["indices"]["EVI"], out["indices"]["NDMI"]

        self.assertTrue(np.isnan(ndvi[0, 0]), "nodata deve ser NaN")
        self.assertTrue(np.isnan(ndvi[0, 1]), "nuvem deve ser NaN")
        self.assertTrue(np.isfinite(ndvi[0, 2]), "água deve ser mantida")
        self.assertAlmostEqual(float(ndvi[1, 1]), (0.5 - 0.1) / 0.6, places=5)
        self.assertAlmostEqual(float(ndmi[1, 1]), (0.5 - 0.2) / 0.7, places=5)
        self.assertAlmostEqual(
            float(evi[1, 1]), (2.5 * 0.4) / (0.5 + 0.6 - 0.0 + 1.0), places=5
        )

        mask = out["mask_summary"]
        self.assertEqual(mask["total_pixels"], 16)
        self.assertEqual(mask["scl_masked_pixels"], 1)
        self.assertEqual(mask["nodata_masked_pixels"], 1)
        self.assertEqual(mask["kept_pixels"], 14)
        self.assertAlmostEqual(mask["kept_fraction"], 14 / 16, places=10)

        stats = out["stats"]["NDVI"]
        self.assertEqual(stats["valid_pixels"], 14)
        self.assertEqual(stats["out_of_range_pixels"], 0)
        self.assertEqual(stats["degenerate_pixels"], 0)

    def test_all_invalid_produces_none_stats(self):
        scene = self._scene()
        scene["bands"]["red"][:] = 0
        out = ix.compute_indices(scene)
        stats = out["stats"]["NDVI"]
        self.assertEqual(stats["valid_pixels"], 0)
        self.assertIsNone(stats["mean"])
        self.assertEqual(stats["out_of_range_pixels"], 0)


class StatsTest(unittest.TestCase):
    def test_stats_ignore_nan(self):
        arr = np.array([1.0, 2.0, np.nan, 3.0])
        stats = ix.array_stats(arr)
        self.assertEqual(stats["total_pixels"], 4)
        self.assertEqual(stats["valid_pixels"], 3)
        self.assertAlmostEqual(stats["mean"], 2.0)
        self.assertAlmostEqual(stats["min"], 1.0)
        self.assertAlmostEqual(stats["max"], 3.0)
        self.assertAlmostEqual(stats["valid_fraction"], 0.75)

    def test_out_of_range_count(self):
        arr = np.array([0.1, 0.9, 2.0, -2.0])
        stats = ix.array_stats(arr)
        self.assertEqual(stats["out_of_range_pixels"], 2)

    def test_empty_stats(self):
        stats = ix.array_stats(np.full((2, 2), np.nan))
        self.assertEqual(stats["valid_pixels"], 0)
        self.assertIsNone(stats["p95"])

    def test_interquartile_quantiles_are_reported(self):
        arr = np.arange(1, 101, dtype="float64")
        stats = ix.array_stats(arr)
        self.assertAlmostEqual(stats["p25"], 25.75, places=6)
        self.assertAlmostEqual(stats["p75"], 75.25, places=6)
        self.assertLess(stats["p25"], stats["median"])
        self.assertLess(stats["median"], stats["p75"])


class ProfileBehaviourTest(unittest.TestCase):
    """Perfis de máscara dentro do cálculo de índices (Checkpoint B)."""

    def _scene(self):
        shape = (3, 3)
        red = np.full(shape, 2000, dtype="uint16")
        nir = np.full(shape, 6000, dtype="uint16")
        blue = np.full(shape, 1000, dtype="uint16")
        swir = np.full(shape, 3000, dtype="uint16")
        scl = np.full(shape, 4, dtype="uint8")
        scl[0, 0] = 2  # dark area pixels
        scl[0, 1] = 6  # água
        scl[0, 2] = 9  # nuvem alta
        scale = {"scale": 1e-4, "offset": -0.1, "nodata": 0.0}
        return {
            "bands": {"blue": blue, "red": red, "nir": nir, "swir": swir},
            "scl": scl,
            "scales": {k: dict(scale) for k in ("blue", "red", "nir", "swir")},
            "grid": {"crs": "EPSG:32721", "res": 20.0, "width": 3, "height": 3,
                     "bounds": [0, 0, 60, 60], "transform": [20, 0, 0, 0, -20, 60]},
        }

    def test_default_profile_is_the_historical_rule(self):
        out = ix.compute_indices(self._scene())
        self.assertEqual(out["mask_summary"]["profile"], "A_historical")
        ndvi = out["indices"]["NDVI"]
        self.assertTrue(np.isfinite(ndvi[0, 0]))  # classe 2 mantida no perfil A
        self.assertTrue(np.isfinite(ndvi[0, 1]))  # água mantida no perfil A
        self.assertTrue(np.isnan(ndvi[0, 2]))    # nuvem excluída

    def test_restrictive_profile_drops_dark_area_and_water(self):
        out = ix.compute_indices(self._scene(), profile="B_restrictive")
        ndvi = out["indices"]["NDVI"]
        self.assertTrue(np.isnan(ndvi[0, 0]))
        self.assertTrue(np.isnan(ndvi[0, 1]))
        self.assertEqual(out["mask_summary"]["profile"], "B_restrictive")
        self.assertIn(2, out["mask_summary"]["scl_excluded_classes"])
        self.assertIn(6, out["mask_summary"]["scl_excluded_classes"])

    def test_keep_override_is_respected(self):
        scene = self._scene()
        keep = np.zeros(scene["scl"].shape, dtype=bool)
        keep[1, 1] = True
        out = ix.compute_indices(scene, keep_override=keep)
        ndvi = out["indices"]["NDVI"]
        self.assertTrue(np.isfinite(ndvi[1, 1]))
        self.assertTrue(np.isnan(ndvi[0, 0]))
        self.assertTrue(np.isnan(ndvi[2, 2]))

    def test_keep_override_with_wrong_shape_raises(self):
        scene = self._scene()
        with self.assertRaises(ValueError):
            ix.compute_indices(scene, keep_override=np.ones((2, 2), dtype=bool))


if __name__ == "__main__":
    unittest.main()
