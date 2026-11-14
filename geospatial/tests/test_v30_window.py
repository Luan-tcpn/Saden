"""Testes da V3.0 — limites da janela ZARC (D97).

O defeito corrigido nesta versão estava na comparação de ``"AAAA-MM"`` com
``"AAAA-MM-DD"``: o início era arredondado para o dia 1º e o **mês final era
excluído**. Em 28.282 das 40.990 linhas do painel o número de meses usados
difere do número de meses listados.

Os testes fixam as duas semânticas: a histórica (para reprodução) e a
corrigida (para o novo painel).
"""

from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GEO = os.path.abspath(os.path.join(HERE, ".."))
if GEO not in sys.path:
    sys.path.insert(0, GEO)

from agroclimate import cycle  # noqa: E402

MONTHS = ["2017-09", "2017-10", "2017-11", "2017-12"]
DATES = [
    "2017-08-31",
    "2017-09-01",
    "2017-09-10",
    "2017-11-30",
    "2017-12-01",
    "2017-12-31",
    "2018-01-01",
]


def _selected(months, corrected):
    start, end = cycle.window_bounds(months, corrected=corrected)
    return [d for d in DATES if start <= d <= end]


class WindowBoundsTest(unittest.TestCase):
    def test_last_day_of_month(self):
        self.assertEqual(cycle.last_day_of_month("2017-12"), "2017-12-31")
        self.assertEqual(cycle.last_day_of_month("2017-02"), "2017-02-28")
        self.assertEqual(cycle.last_day_of_month("2020-02"), "2020-02-29")
        self.assertEqual(cycle.last_day_of_month("2017-04"), "2017-04-30")

    def test_corrected_window_covers_all_months(self):
        self.assertEqual(
            cycle.window_bounds(MONTHS, corrected=True),
            ("2017-09-01", "2017-12-31"),
        )

    def test_historical_window_reproduces_the_defect(self):
        start, end = cycle.window_bounds(MONTHS, corrected=False)
        self.assertEqual((start, end), ("2017-09", "2017-12"))

    def test_historical_selection_drops_the_last_month(self):
        selected = _selected(MONTHS, corrected=False)
        self.assertIn("2017-09-01", selected)
        self.assertIn("2017-11-30", selected)
        # o mês final inteiro é excluído pela comparação lexicográfica
        self.assertNotIn("2017-12-01", selected)
        self.assertNotIn("2017-12-31", selected)

    def test_corrected_selection_includes_the_last_month(self):
        selected = _selected(MONTHS, corrected=True)
        self.assertIn("2017-12-01", selected)
        self.assertIn("2017-12-31", selected)
        self.assertNotIn("2017-08-31", selected)
        self.assertNotIn("2018-01-01", selected)

    def test_corrected_window_has_more_days(self):
        self.assertGreater(
            len(_selected(MONTHS, corrected=True)),
            len(_selected(MONTHS, corrected=False)),
        )

    def test_single_month_window(self):
        self.assertEqual(
            cycle.window_bounds(["2018-01"], corrected=True),
            ("2018-01-01", "2018-01-31"),
        )

    def test_empty_window_is_rejected(self):
        with self.assertRaises(ValueError):
            cycle.window_bounds([], corrected=True)


if __name__ == "__main__":
    unittest.main()
