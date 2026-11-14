"""Testes da V2.9 — integração da CAD por profundidade (D93).

O defeito encontrado nesta versão foi exatamente este: calcular a CAD de
0–100 cm usando todas as camadas disponíveis, o que devolve o valor de
0–200 cm. Os testes fixam a regra:

* a seleção de camadas por profundidade exclui as camadas atravessadas;
* a integração por pixel usa `Σ AW · espessura` e propaga ausência;
* a profundidade de 0–100 cm **não** inclui a camada de 100–200 cm.
"""

from __future__ import annotations

import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GEO = os.path.abspath(os.path.join(HERE, ".."))
if GEO not in sys.path:
    sys.path.insert(0, GEO)

from agroclimate import soil  # noqa: E402


class LayerSelectionTest(unittest.TestCase):
    def test_layers_up_to_100_cm_exclude_the_deepest_layer(self):
        keys = [layer["key"] for layer in soil.layers_up_to_depth(100.0)]
        self.assertEqual(
            keys, ["aw_0_5", "aw_5_15", "aw_15_30", "aw_30_60", "aw_60_100"]
        )
        self.assertNotIn("aw_100_200", keys)

    def test_layers_up_to_60_cm(self):
        keys = [layer["key"] for layer in soil.layers_up_to_depth(60.0)]
        self.assertEqual(keys, ["aw_0_5", "aw_5_15", "aw_15_30", "aw_30_60"])

    def test_layers_up_to_200_cm_include_everything(self):
        keys = [layer["key"] for layer in soil.layers_up_to_depth(200.0)]
        self.assertEqual(len(keys), 6)

    def test_partial_layer_is_excluded(self):
        """Uma profundidade de 50 cm não inclui a camada de 30–60 cm."""
        keys = [layer["key"] for layer in soil.layers_up_to_depth(50.0)]
        self.assertEqual(keys, ["aw_0_5", "aw_5_15", "aw_15_30"])


class PixelCapacityTest(unittest.TestCase):
    def _stack(self, value: float, n_layers: int = 6, shape=(2, 2)):
        return np.full((n_layers,) + shape, value, dtype="float64")

    def test_capacity_is_aw_times_thickness(self):
        layers = soil.layers_up_to_depth(100.0)
        stack = self._stack(2.0, n_layers=len(layers))
        capacity = soil.pixel_capacity_mm(stack, layers)
        # 2.0 mm/cm × (5+10+15+30+40) cm = 200 mm
        self.assertTrue(np.allclose(capacity, 200.0))

    def test_0_100_is_not_0_200(self):
        layers_100 = soil.layers_up_to_depth(100.0)
        layers_200 = soil.layers_up_to_depth(200.0)
        stack = self._stack(2.0, n_layers=6)
        shallow = soil.pixel_capacity_mm(stack[: len(layers_100)], layers_100)
        deep = soil.pixel_capacity_mm(stack, layers_200)
        self.assertAlmostEqual(float(shallow[0, 0]), 200.0)
        self.assertAlmostEqual(float(deep[0, 0]), 400.0)
        self.assertGreater(deep[0, 0], shallow[0, 0])

    def test_nan_in_any_layer_makes_the_pixel_missing(self):
        layers = soil.layers_up_to_depth(100.0)
        stack = self._stack(2.0, n_layers=len(layers))
        stack[3, 0, 1] = np.nan
        capacity = soil.pixel_capacity_mm(stack, layers)
        self.assertTrue(np.isfinite(capacity[0, 0]))
        self.assertTrue(np.isnan(capacity[0, 1]))

    def test_mismatched_stack_raises(self):
        layers = soil.layers_up_to_depth(100.0)
        with self.assertRaises(ValueError):
            soil.pixel_capacity_mm(self._stack(2.0, n_layers=3), layers)


class ProfileCapacityTest(unittest.TestCase):
    def test_profile_capacity_matches_layer_integration(self):
        values = {
            "aw_0_5": 2.0,
            "aw_5_15": 2.0,
            "aw_15_30": 2.0,
            "aw_30_60": 2.0,
            "aw_60_100": 2.0,
            "aw_100_200": 2.0,
        }
        self.assertAlmostEqual(soil.profile_capacity_mm(values)["capacity_mm"], 400.0)
        self.assertAlmostEqual(
            soil.profile_capacity_to_depth_mm(values, 100.0)["capacity_mm"], 200.0
        )
        self.assertAlmostEqual(
            soil.profile_capacity_to_depth_mm(values, 60.0)["capacity_mm"], 120.0
        )

    def test_missing_layer_keeps_the_profile_incomplete(self):
        values = {
            "aw_0_5": 2.0,
            "aw_5_15": None,
            "aw_15_30": 2.0,
            "aw_30_60": 2.0,
            "aw_60_100": 2.0,
        }
        result = soil.profile_capacity_to_depth_mm(values, 100.0)
        self.assertIsNone(result["capacity_mm"])
        self.assertLess(result["coverage_fraction"], 1.0)


if __name__ == "__main__":
    unittest.main()
