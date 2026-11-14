"""Testes da V2.9 — grupos de ciclo do ZARC e teste de interação (D94).

Cobrem:

* o dicionário oficial (``Cod_Ciclo`` = grupo de ciclo, não cultivar);
* o teste de interação como **diferença de inclinação**, e não como
  comparação de dois coeficientes estimados em separado;
* o comportamento sob hipótese nula (inclinações iguais) e sob efeito
  verdadeiro (inclinações diferentes);
* amostra insuficiente e desenho degenerado.
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

from agroclimate import cycle  # noqa: E402


def make_rows(
    n_municipalities: int = 40,
    n_years: int = 6,
    slope_reference: float = 2.0,
    slope_difference: float = 0.0,
    seed: int = 17,
):
    """Painel sintético com classe de ciclo constante por município.

    ``y = slope_reference*x + slope_difference*x*I[Grupo II] + FE + ruído``.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for municipality in range(n_municipalities):
        grupo = "21" if municipality % 2 else "22"
        level = rng.normal() * 5.0
        for year in range(n_years):
            x = float(rng.normal())
            year_effect = 0.5 * year
            signal = slope_reference * x
            if grupo == "21":
                signal += slope_difference * x
            rows.append(
                {
                    "ibge_code": f"m{municipality:03d}",
                    "year": 2000 + year,
                    "crop": "soja",
                    "zarc_cycle": grupo,
                    "spatial_block": f"B{municipality % 8:02d}",
                    "x": x,
                    "yield_kg_ha": float(level + year_effect + signal + rng.normal()),
                }
            )
    return rows


class DictionaryTest(unittest.TestCase):
    def test_cycle_codes_are_groups_not_cultivars(self):
        self.assertEqual(cycle.class_label("20"), "Grupo I")
        self.assertEqual(cycle.class_label("21"), "Grupo II")
        self.assertEqual(cycle.class_label("22"), "Grupo III")
        self.assertEqual(cycle.class_label("13"), "Perene")
        self.assertEqual(cycle.class_label("99"), "nao documentado")

    def test_soil_codes(self):
        self.assertEqual(cycle.soil_label("1"), "Arenoso")
        self.assertEqual(cycle.soil_label("2"), "Textura Média")
        self.assertEqual(cycle.soil_label("3"), "Argiloso")
        self.assertEqual(cycle.soil_label("16"), "AD6")
        self.assertEqual(cycle.soil_label("x"), "nao documentado")

    def test_source_metadata_is_recorded(self):
        self.assertIn("dicionario-de-dados-tabua-de-risco", cycle.SOURCE["document"])
        self.assertEqual(cycle.SOURCE["accessed_at"], "2026-11-14")
        self.assertIn("agricultura.gov.br", cycle.SOURCE["url"])


class InteractionTestTest(unittest.TestCase):
    def test_detects_a_true_slope_difference(self):
        rows = make_rows(slope_difference=3.0)
        result = cycle.interaction_test(
            rows, "x", "22", "21", min_rows=100
        )
        self.assertEqual(result["status"], "ok")
        difference = result["slope_difference"]
        self.assertAlmostEqual(difference["coefficient"], 3.0, delta=0.6)
        self.assertGreater(abs(difference["t_statistic"]), 3.0)
        self.assertLess(difference["p_value"], 0.01)

    def test_does_not_invent_a_difference_under_the_null(self):
        rows = make_rows(slope_difference=0.0)
        result = cycle.interaction_test(
            rows, "x", "22", "21", min_rows=100
        )
        difference = result["slope_difference"]
        self.assertAlmostEqual(difference["coefficient"], 0.0, delta=0.6)
        self.assertGreater(difference["p_value"], 0.05)

    def test_reports_reference_and_contrast_labels(self):
        rows = make_rows()
        result = cycle.interaction_test(rows, "x", "22", "21", min_rows=100)
        self.assertEqual(result["reference_class"], "22")
        self.assertEqual(result["reference_label"], "Grupo III")
        self.assertEqual(result["contrast_class"], "21")
        self.assertEqual(result["contrast_label"], "Grupo II")

    def test_insufficient_rows_is_reported(self):
        rows = make_rows(n_municipalities=4, n_years=2)
        result = cycle.interaction_test(rows, "x", "22", "21", min_rows=500)
        self.assertEqual(result["status"], "insufficient_rows")

    def test_degenerate_design_is_reported(self):
        rows = make_rows()
        for row in rows:
            row["constant"] = 1.0
        result = cycle.interaction_test(rows, "constant", "22", "21", min_rows=100)
        self.assertEqual(result["status"], "degenerate_design")

    def test_confidence_interval_brackets_the_difference(self):
        rows = make_rows(slope_difference=3.0)
        result = cycle.interaction_test(rows, "x", "22", "21", min_rows=100)
        low, high = result["slope_difference"]["ci95"]
        self.assertLess(low, result["slope_difference"]["coefficient"])
        self.assertGreater(high, result["slope_difference"]["coefficient"])
        self.assertLess(low, 3.0)
        self.assertGreater(high, 3.0)


if __name__ == "__main__":
    unittest.main()
