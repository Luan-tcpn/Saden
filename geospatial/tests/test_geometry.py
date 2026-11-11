"""Testes de geometria (shapely/pyproj locais, sem rede)."""

from __future__ import annotations

import unittest

from shapely.geometry import box, shape

from s2_poc import config
from s2_poc import geometry as geometry_mod


def _poly(*rings):
    return shape({"type": "Polygon", "coordinates": list(rings)})


class BboxReportTest(unittest.TestCase):
    def test_bbox_fully_inside_polygon(self):
        municipality = box(-56.0, -13.0, -55.0, -12.0)
        report = geometry_mod.bbox_report(municipality, [-55.8, -12.8, -55.4, -12.4])
        self.assertTrue(report["fully_inside"])
        self.assertAlmostEqual(report["inside_fraction"], 1.0, places=10)
        self.assertAlmostEqual(report["outside_municipality_km2"], 0.0, places=6)

    def test_bbox_partially_outside_polygon(self):
        # quadrado que corta o canto inferior direito da bbox
        municipality = _poly(
            [[-56.0, -13.0], [-55.6, -13.0], [-55.6, -12.6], [-56.0, -12.6], [-56.0, -13.0]]
        )
        bbox = [-55.8, -12.8, -55.4, -12.4]
        report = geometry_mod.bbox_report(municipality, bbox)
        self.assertFalse(report["fully_inside"])
        self.assertGreater(report["outside_municipality_km2"], 0.0)
        self.assertLess(report["inside_fraction"], 1.0)
        self.assertGreater(report["inside_fraction"], 0.0)
        self.assertAlmostEqual(
            report["inside_municipality_km2"] + report["outside_municipality_km2"],
            report["bbox_area_km2"],
            places=6,
        )

    def test_centroid_inside_does_not_imply_full_containment(self):
        municipality = _poly(
            [[-56.0, -13.0], [-55.5, -13.0], [-55.5, -12.5], [-56.0, -12.5], [-56.0, -13.0]]
        )
        bbox = [-55.8, -12.8, -55.4, -12.4]
        report = geometry_mod.bbox_report(municipality, bbox)
        self.assertTrue(report["centroid_inside"])
        self.assertFalse(report["fully_inside"])

    def test_bbox_with_invalid_length_raises(self):
        with self.assertRaises(ValueError):
            geometry_mod.bbox_polygon([1, 2, 3])


class AoiDefinitionTest(unittest.TestCase):
    def test_historical_bbox_is_preserved_exactly(self):
        expected = [-55.6509, -12.74385, -55.5509, -12.64385]
        got = geometry_mod.historical_aoi_bbox()
        for value, ref in zip(got, expected):
            self.assertAlmostEqual(value, ref, places=9)

    def test_validation_aoi_size_and_center(self):
        bbox = geometry_mod.validation_aoi_bbox()
        size = config.VALIDATION_AOI["size_deg"]
        self.assertAlmostEqual(bbox[2] - bbox[0], size, places=9)
        self.assertAlmostEqual(bbox[3] - bbox[1], size, places=9)
        center_lon = (bbox[0] + bbox[2]) / 2
        center_lat = (bbox[1] + bbox[3]) / 2
        self.assertAlmostEqual(center_lon, config.VALIDATION_AOI["center_lon"], places=9)
        self.assertAlmostEqual(center_lat, config.VALIDATION_AOI["center_lat"], places=9)

    def test_validation_aoi_requires_municipality_containment(self):
        # recorte que não contém a AOI de validação
        small = box(-55.70, -12.90, -55.60, -12.80)
        with self.assertRaises(RuntimeError):
            geometry_mod.validation_aoi(small)

    def test_validation_aoi_estimate_within_municipality(self):
        municipality = box(-57.0, -14.0, -55.0, -11.0)
        info = geometry_mod.validation_aoi(municipality)
        self.assertTrue(info["inside_municipality"])
        expected_pixels = info["area_km2_equal_area"] * 1e6 / (config.TARGET_RES_M ** 2)
        self.assertAlmostEqual(
            info["pixels_20m_estimate"], round(expected_pixels), delta=2
        )


class OperationalEstimateTest(unittest.TestCase):
    def test_estimate_is_consistent_with_area_and_resolution(self):
        municipality = box(-56.0, -13.0, -55.0, -12.0)
        estimate = geometry_mod.operational_estimate(municipality, res_m=20.0)
        pixels = estimate["municipality_area_km2"] * 1e6 / 400
        self.assertAlmostEqual(estimate["pixels_per_band"], round(pixels), delta=2)
        self.assertAlmostEqual(
            estimate["float32_mb_per_band"], round(pixels * 4 / 1e6, 1), places=1
        )

    def test_municipality_area_is_positive(self):
        municipality = box(-56.0, -13.0, -55.0, -12.0)
        estimate = geometry_mod.operational_estimate(municipality, res_m=20.0)
        self.assertGreater(estimate["municipality_area_km2"], 0.0)


if __name__ == "__main__":
    unittest.main()
