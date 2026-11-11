"""Testes de grade, reamostragem e I/O GeoTIFF (arquivos locais sintéticos)."""

from __future__ import annotations

import os
import tempfile
import unittest

import numpy as np
import rasterio
from affine import Affine
from rasterio.enums import Resampling

from s2_poc import read


def _write_source(path, array, res, origin=(0.0, 20.0), crs="EPSG:32721", nodata=0):
    height, width = array.shape
    transform = Affine(res, 0.0, origin[0], 0.0, -res, origin[1])
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": array.dtype.name,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array, 1)
    return path


def _grid(crs, transform, width, height, res=20.0):
    left = transform.c
    top = transform.f
    return {
        "crs": crs,
        "transform": transform,
        "width": width,
        "height": height,
        "res": res,
        "bounds": [left, top - height * res, left + width * res, top],
    }


class TargetGridTest(unittest.TestCase):
    def test_grid_is_aligned_to_resolution_multiples(self):
        grid = read.target_grid("EPSG:32721", [-55.6509, -12.7438, -55.5509, -12.6438])
        self.assertEqual(grid["res"], 20.0)
        self.assertEqual(str(grid["crs"]), "EPSG:32721")
        # bounds alinhados a múltiplos de 20 m no CRS do tile
        for value in grid["bounds"]:
            self.assertAlmostEqual(value % 20.0, 0.0, places=6)
        self.assertGreater(grid["width"], 0)
        self.assertGreater(grid["height"], 0)
        self.assertEqual(grid["transform"].a, 20.0)
        self.assertEqual(grid["transform"].e, -20.0)

    def test_dimensions_match_bounds(self):
        grid = read.target_grid("EPSG:32721", [-55.65, -12.75, -55.55, -12.65])
        left, bottom, right, top = grid["bounds"]
        self.assertEqual(grid["width"], int(round((right - left) / 20.0)))
        self.assertEqual(grid["height"], int(round((top - bottom) / 20.0)))


class ResamplingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_average_is_used_for_continuous_bands(self):
        # 2x2 @ 10 m cobrindo 20x20 m; média dos quatro pixels = 2000
        array = np.array([[1000, 3000], [3000, 1000]], dtype="uint16")
        src = _write_source(os.path.join(self.tmp.name, "src10.tif"), array, res=10)
        grid = _grid("EPSG:32721", Affine(20, 0, 0, 0, -20, 20), 1, 1)
        out, meta = read.read_resampled(src, grid, Resampling.average, np.nan, "float32")
        self.assertEqual(out.shape, (1, 1))
        self.assertAlmostEqual(float(out[0, 0]), 2000.0, places=3)
        self.assertEqual(meta["resampling"], "average")

    def test_nearest_keeps_categorical_classes(self):
        # 4x4 @ 10 m -> 2x2 @ 20 m: nenhuma classe nova pode aparecer
        classes = np.array(
            [[1, 2, 3, 4], [2, 3, 4, 5], [3, 4, 5, 6], [4, 5, 6, 7]], dtype="uint8"
        )
        src = _write_source(
            os.path.join(self.tmp.name, "scl10.tif"),
            classes,
            res=10,
            nodata=0,
            origin=(0.0, 40.0),
        )
        grid = _grid("EPSG:32721", Affine(20, 0, 0, 0, -20, 40), 2, 2)
        out, meta = read.read_resampled(src, grid, Resampling.nearest, 0, "uint8")
        self.assertEqual(meta["resampling"], "nearest")
        self.assertTrue(set(np.unique(out).tolist()) <= set(np.unique(classes).tolist()))

    def test_both_sources_share_identical_grid(self):
        path_a = _write_source(
            os.path.join(self.tmp.name, "a.tif"),
            np.full((4, 4), 1000, dtype="uint16"),
            10,
            origin=(0.0, 40.0),
        )
        path_b = _write_source(
            os.path.join(self.tmp.name, "b.tif"),
            np.full((2, 2), 500, dtype="uint16"),
            20,
            origin=(0.0, 40.0),
        )
        grid = _grid("EPSG:32721", Affine(20, 0, 0, 0, -20, 40), 2, 2)
        a, _ = read.read_resampled(path_a, grid, Resampling.average, np.nan, "float32")
        b, _ = read.read_resampled(path_b, grid, Resampling.average, np.nan, "float32")
        self.assertEqual(a.shape, b.shape)
        self.assertAlmostEqual(float(a[0, 0]), 1000.0, places=3)
        self.assertAlmostEqual(float(b[0, 0]), 500.0, places=3)


class GeoTiffIOTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.grid = _grid("EPSG:32721", Affine(20, 0, 500000, 0, -20, 8600000), 3, 2)

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_preserves_grid_values_and_nan(self):
        array = np.array(
            [[0.1, 0.2, 0.3], [np.nan, -0.4, 0.9]], dtype="float32"
        )
        path = os.path.join(self.tmp.name, "ndvi.tif")
        read.write_geotiff(path, array, self.grid, tags={"SADEN_INDEX": "NDVI"})
        with rasterio.open(path) as ds:
            self.assertEqual(ds.width, 3)
            self.assertEqual(ds.height, 2)
            self.assertEqual(str(ds.crs), "EPSG:32721")
            self.assertEqual(ds.transform, self.grid["transform"])
            self.assertEqual(ds.dtypes[0], "float32")
            self.assertTrue(np.isnan(ds.nodata))
            self.assertEqual(ds.tags()["SADEN_INDEX"], "NDVI")
            back = ds.read(1)
        self.assertTrue(np.isnan(back[1, 0]))
        np.testing.assert_allclose(back[~np.isnan(back)], array[~np.isnan(array)], rtol=1e-6)

    def test_shape_mismatch_raises(self):
        with self.assertRaises(ValueError):
            read.write_geotiff(
                os.path.join(self.tmp.name, "bad.tif"), np.zeros((5, 5)), self.grid
            )

    def test_sha256_is_stable(self):
        path = os.path.join(self.tmp.name, "x.tif")
        read.write_geotiff(path, np.ones((2, 3)), self.grid)
        digest = read.sha256_file(path)
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, read.sha256_file(path))


if __name__ == "__main__":
    unittest.main()
