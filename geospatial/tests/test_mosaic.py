"""Testes do mosaico determinístico (rasters sintéticos, sem rede)."""

from __future__ import annotations

import unittest

import numpy as np

from s2_poc import mosaic as mosaic_mod


def _grid(transform=None, width=4, height=3):
    from affine import Affine

    return {
        "crs": "EPSG:32721",
        "transform": transform or Affine(20.0, 0.0, 500000.0, 0.0, -20.0, 8600000.0),
        "width": width,
        "height": height,
        "res": 20.0,
        "bounds": [500000.0, 8600000.0 - height * 20.0, 500000.0 + width * 20.0, 8600000.0],
    }


class ContinuousMosaicTest(unittest.TestCase):
    def test_first_valid_wins_in_overlap(self):
        primary = np.array(
            [[1.0, 1.0, np.nan], [np.nan, 2.0, np.nan]], dtype="float32"
        )
        secondary = np.array(
            [[9.0, 9.0, 3.0], [4.0, 9.0, 5.0]], dtype="float32"
        )
        out = mosaic_mod.mosaic_continuous([primary, secondary], ["A", "B"])
        self.assertAlmostEqual(float(out["data"][0, 0]), 1.0)   # primário tem prioridade
        self.assertAlmostEqual(float(out["data"][0, 1]), 1.0)
        self.assertAlmostEqual(float(out["data"][0, 2]), 3.0)   # preenchido pelo secundário
        self.assertAlmostEqual(float(out["data"][1, 0]), 4.0)
        self.assertAlmostEqual(float(out["data"][1, 1]), 2.0)
        self.assertAlmostEqual(float(out["data"][1, 2]), 5.0)
        self.assertEqual(out["source_pixels"], {"A": 3, "B": 3})
        self.assertEqual(out["unfilled_pixels"], 0)
        self.assertEqual(out["rule"], "first_valid_wins")

    def test_unfilled_pixels_are_counted(self):
        primary = np.full((2, 2), np.nan, dtype="float32")
        secondary = np.full((2, 2), np.nan, dtype="float32")
        out = mosaic_mod.mosaic_continuous([primary, secondary])
        self.assertEqual(out["unfilled_pixels"], 4)
        self.assertTrue(np.all(np.isnan(out["data"])))

    def test_no_averaging_between_tiles(self):
        a = np.array([[1.0]], dtype="float32")
        b = np.array([[3.0]], dtype="float32")
        out = mosaic_mod.mosaic_continuous([a, b], ["A", "B"])
        self.assertAlmostEqual(float(out["data"][0, 0]), 1.0)  # não é 2.0 (média)

    def test_shape_mismatch_raises(self):
        with self.assertRaises(ValueError):
            mosaic_mod.mosaic_continuous(
                [np.zeros((2, 2)), np.zeros((3, 3))], ["A", "B"]
            )


class CategoricalMosaicTest(unittest.TestCase):
    def test_first_non_nodata_wins(self):
        primary = np.array([[0, 4], [6, 0]], dtype="uint8")
        secondary = np.array([[5, 0], [6, 7]], dtype="uint8")
        out = mosaic_mod.mosaic_categorical([primary, secondary], ["A", "B"], nodata=0)
        self.assertEqual(out["data"].tolist(), [[5, 4], [6, 7]])
        self.assertEqual(out["source_pixels"], {"A": 2, "B": 2})
        self.assertEqual(out["unfilled_pixels"], 0)


class OverlapStatsTest(unittest.TestCase):
    def test_identical_rasters_have_zero_difference(self):
        a = np.array([0.1, 0.2, 0.3], dtype="float32")
        stats = mosaic_mod.overlap_stats(a, a)
        self.assertEqual(stats["pixels"], 3)
        self.assertAlmostEqual(stats["mean_absolute_difference"], 0.0, places=10)
        self.assertAlmostEqual(stats["rmse"], 0.0, places=10)

    def test_only_common_valid_pixels_are_compared(self):
        a = np.array([1.0, np.nan, 3.0], dtype="float32")
        b = np.array([1.0, 2.0, np.nan], dtype="float32")
        stats = mosaic_mod.overlap_stats(a, b)
        self.assertEqual(stats["pixels"], 1)
        self.assertAlmostEqual(stats["mean_absolute_difference"], 0.0, places=10)

    def test_bias_and_rmse(self):
        a = np.array([2.0, 2.0], dtype="float32")
        b = np.array([1.0, 1.0], dtype="float32")
        stats = mosaic_mod.overlap_stats(a, b)
        self.assertAlmostEqual(stats["mean_difference_left_minus_right"], 1.0, places=6)
        self.assertAlmostEqual(stats["rmse"], 1.0, places=6)


class GridTest(unittest.TestCase):
    def test_identical_grids_are_accepted(self):
        grid = _grid()
        self.assertIs(mosaic_mod.mosaic_grids([grid, dict(grid)]), grid)

    def test_incompatible_grid_raises(self):
        from affine import Affine

        other = _grid(transform=Affine(20.0, 0.0, 500100.0, 0.0, -20.0, 8600000.0))
        with self.assertRaises(ValueError):
            mosaic_mod.mosaic_grids([_grid(), other])

    def test_mosaic_index_results_uses_shared_grid(self):
        results = []
        for value in (1.0, 2.0):
            results.append(
                {
                    "indices": {"NDVI": np.full((2, 2), value, dtype="float32")},
                    "grid": _grid(),
                }
            )
        out = mosaic_mod.mosaic_index_results(results, ["NDVI"], ["A", "B"])
        self.assertEqual(out["sources"]["NDVI"]["source_pixels"], {"A": 4, "B": 0})
        self.assertAlmostEqual(float(out["indices"]["NDVI"][0, 0]), 1.0)


class SeamTest(unittest.TestCase):
    def test_seam_marks_boundary_between_sources(self):
        source = np.array([[0, 0, 1], [0, 0, 1], [0, 0, 1]], dtype="int16")
        seam = mosaic_mod.seam_mask(source)
        # a mudança ocorre na fronteira entre a coluna 1 e a coluna 2
        self.assertTrue(seam[0, 2])
        self.assertTrue(seam[2, 2])
        self.assertFalse(seam[0, 0])
        self.assertFalse(seam[1, 0])


if __name__ == "__main__":
    unittest.main()
