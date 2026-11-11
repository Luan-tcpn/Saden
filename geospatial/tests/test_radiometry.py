"""Testes da auditoria radiométrica (metadados sintéticos, sem rede)."""

from __future__ import annotations

import unittest

from s2_poc import radiometry


class FakeAsset:
    def __init__(self, scale=0.0001, offset=-0.1, nodata=0, data_type="uint16"):
        self.href = "https://example.invalid/asset.tif"
        self.extra_fields = {
            "raster:bands": [
                {
                    "scale": scale,
                    "offset": offset,
                    "nodata": nodata,
                    "data_type": data_type,
                    "spatial_resolution": 10,
                }
            ]
        }


class FakeItem:
    def __init__(self, baseline="05.11", assets=None, item_id="ITEM"):
        self.id = item_id
        properties = {}
        if baseline is not None:
            properties["s2:processing_baseline"] = baseline
        self.properties = properties
        if assets is None:
            assets = {
                "blue": FakeAsset(),
                "red": FakeAsset(),
                "nir": FakeAsset(),
                "swir16": FakeAsset(),
            }
        self.assets = assets


class FakeDataset:
    def __init__(self, scales=(0.0001,), offsets=(-0.1,)):
        self.dtypes = ("uint16",)
        self.scales = scales
        self.offsets = offsets
        self.nodata = 0.0
        self.crs = "EPSG:32721"
        self.res = (10.0, 10.0)
        self.transform = (10.0, 0.0, 500000.0, 0.0, -10.0, 8600000.0)
        self.width = 100
        self.height = 100


class BaselineTest(unittest.TestCase):
    def test_parse_baseline(self):
        self.assertAlmostEqual(radiometry.parse_baseline("05.11"), 5.11)
        self.assertAlmostEqual(radiometry.parse_baseline("04.00"), 4.0)
        self.assertIsNone(radiometry.parse_baseline(None))
        self.assertIsNone(radiometry.parse_baseline(""))
        self.assertIsNone(radiometry.parse_baseline("xx"))

    def test_supported_baseline_is_accepted(self):
        info = radiometry.assert_supported_item(FakeItem(), ("blue", "red", "nir", "swir"))
        self.assertTrue(info["baseline_supported"])
        self.assertAlmostEqual(info["scale"], 0.0001)
        self.assertAlmostEqual(info["offset"], -0.1)
        self.assertEqual(info["conversion"], "DN * scale + offset (DN nodata -> NaN antes da escala)")

    def test_old_baseline_is_blocked(self):
        with self.assertRaises(radiometry.UnsupportedProductError):
            radiometry.assert_supported_item(
                FakeItem(baseline="03.01"), ("blue", "red", "nir", "swir")
            )

    def test_missing_baseline_is_blocked(self):
        with self.assertRaises(radiometry.UnsupportedProductError):
            radiometry.assert_supported_item(
                FakeItem(baseline=None), ("blue", "red", "nir", "swir")
            )

    def test_missing_scale_is_blocked(self):
        assets = {
            "blue": FakeAsset(scale=None),
            "red": FakeAsset(),
            "nir": FakeAsset(),
            "swir16": FakeAsset(),
        }
        with self.assertRaises(radiometry.UnsupportedProductError):
            radiometry.assert_supported_item(
                FakeItem(assets=assets), ("blue", "red", "nir", "swir")
            )

    def test_inconsistent_bands_are_blocked(self):
        assets = {
            "blue": FakeAsset(),
            "red": FakeAsset(offset=0.0),
            "nir": FakeAsset(),
            "swir16": FakeAsset(),
        }
        with self.assertRaises(radiometry.UnsupportedProductError):
            radiometry.assert_supported_item(
                FakeItem(assets=assets), ("blue", "red", "nir", "swir")
            )

    def test_missing_asset_is_blocked(self):
        assets = {"blue": FakeAsset(), "red": FakeAsset(), "nir": FakeAsset()}
        with self.assertRaises(radiometry.UnsupportedProductError):
            radiometry.assert_supported_item(
                FakeItem(assets=assets), ("blue", "red", "nir", "swir")
            )


class FileConsistencyTest(unittest.TestCase):
    def test_asset_radiometry_reads_raster_bands(self):
        meta = radiometry.asset_radiometry(FakeAsset())
        self.assertAlmostEqual(meta["scale"], 0.0001)
        self.assertAlmostEqual(meta["offset"], -0.1)
        self.assertEqual(meta["nodata"], 0)
        self.assertEqual(meta["data_type"], "uint16")

    def test_matching_file_and_asset_metadata(self):
        file_meta = radiometry.file_radiometry(FakeDataset())
        asset_meta = {"scale": 0.0001, "offset": -0.1}
        result = radiometry.check_file_matches_asset(file_meta, asset_meta)
        self.assertTrue(result["matches"])
        self.assertTrue(result["read_returns_raw_dn"])

    def test_mismatch_is_detected(self):
        file_meta = radiometry.file_radiometry(FakeDataset(offsets=(0.0,)))
        asset_meta = {"scale": 0.0001, "offset": -0.1}
        result = radiometry.check_file_matches_asset(file_meta, asset_meta)
        self.assertFalse(result["matches"])


if __name__ == "__main__":
    unittest.main()
