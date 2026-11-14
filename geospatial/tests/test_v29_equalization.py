"""Testes da V2.9 — equalização estrita por célula e métricas por repetição (D90).

Cobrem o que a V2.8 não garantia:

* no modo ``global``, braços com menos material podem ficar abaixo do alvo —
  o diagnóstico precisa mostrar isso;
* no modo ``per_cell``, os quatro braços têm **exatamente** o mesmo tamanho de
  treino em cada célula, e todas as células atingem o alvo;
* o conjunto de teste é o mesmo nos quatro braços;
* MAE e RMSE são reportados por repetição, com dispersão entre repetições;
* o modo inválido é rejeitado.
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

from agroclimate import generalization  # noqa: E402

ARMS = ("SS", "SE", "TS", "TE")


def make_panel(n_blocks: int = 20, n_years: int = 6, per_block: int = 6, seed: int = 41):
    rng = np.random.default_rng(seed)
    rows = []
    for b in range(n_blocks):
        for m in range(per_block):
            code = f"m{b:02d}{m:02d}"
            block = f"B{b:02d}"
            state = f"S{b % 4}"
            for y in range(n_years):
                x1 = float(rng.normal() + 0.4 * b)
                x2 = float(rng.normal())
                rows.append(
                    {
                        "ibge_code": code,
                        "year": 2000 + y,
                        "crop": "soja",
                        "state": state,
                        "spatial_block": block,
                        "x1": x1,
                        "x2": x2,
                        "yield_kg_ha": float(
                            100.0
                            + 3.0 * b
                            + 40.0 * (b % 4)
                            + 2.0 * y
                            + 10.0 * x1
                            - 4.0 * x2
                            + rng.normal()
                        ),
                    }
                )
    return rows


class GlobalEqualizationTest(unittest.TestCase):
    def test_global_mode_reports_cells_below_target(self):
        rows = make_panel()
        result = generalization.factorial_holdout(
            rows,
            ["x1", "x2"],
            seed=20261113,
            size_fraction=0.75,
            n_repeats=2,
            n_boot=50,
            equalize="global",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["equalize"], "global")
        self.assertEqual(result["cells_used"], result["cells_total"])
        # o braço que remove bloco e ano é o que tem menos material
        te = result["arms"]["TE"]
        ss = result["arms"]["SS"]
        self.assertGreaterEqual(te["cells_below_target"], 1)
        self.assertLessEqual(te["train_size_mean"], ss["train_size_mean"])
        self.assertGreaterEqual(te["train_size_sd"], 0.0)


class PerCellEqualizationTest(unittest.TestCase):
    def test_per_cell_mode_equalizes_every_arm(self):
        rows = make_panel()
        result = generalization.factorial_holdout(
            rows,
            ["x1", "x2"],
            seed=20261113,
            n_repeats=3,
            n_boot=50,
            equalize="per_cell",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["equalize"], "per_cell")
        self.assertEqual(result["cells_dropped"], 0)
        sizes = []
        for arm in ARMS:
            entry = result["arms"][arm]
            self.assertEqual(entry["status"], "ok")
            # todas as células atingem o alvo e o tamanho é o mesmo
            self.assertEqual(entry["cells_below_target"], 0, msg=arm)
            self.assertEqual(
                entry["cells_at_target"], result["cells_used"], msg=arm
            )
            sizes.append(entry["train_size_mean"])
        self.assertLessEqual(max(sizes) - min(sizes), 1e-9)

    def test_per_cell_mode_keeps_identical_test_sets(self):
        rows = make_panel()
        result = generalization.factorial_holdout(
            rows, ["x1", "x2"], seed=20261113, n_repeats=2, n_boot=50,
            equalize="per_cell",
        )
        n_test = [result["arms"][arm]["model"]["n"] for arm in ARMS]
        self.assertEqual(len(set(n_test)), 1)

    def test_cells_below_minimum_are_dropped_for_all_arms(self):
        rows = make_panel(n_blocks=12, n_years=3, per_block=2)
        result = generalization.factorial_holdout(
            rows,
            ["x1", "x2"],
            seed=20261113,
            n_repeats=1,
            n_boot=50,
            equalize="per_cell",
            min_cell_train=10_000,
        )
        # nenhuma célula tem 10.000 linhas de treino: todas caem, para todos
        self.assertEqual(result["cells_dropped"], result["cells_total"])
        self.assertEqual(result.get("status"), "no_test_rows")

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            generalization.factorial_holdout(
                make_panel(), ["x1", "x2"], equalize="por_dobra"
            )


class RepeatMetricsTest(unittest.TestCase):
    def test_repeat_metrics_are_reported(self):
        rows = make_panel()
        result = generalization.factorial_holdout(
            rows,
            ["x1", "x2"],
            seed=20261113,
            size_fraction=0.5,
            n_repeats=4,
            n_boot=50,
            equalize="global",
        )
        for arm in ARMS:
            metrics = result["arms"][arm]["repeat_metrics"]
            self.assertEqual(metrics["n_repeats_with_predictions"], 4, msg=arm)
            self.assertEqual(len(metrics["mae_per_repeat"]), 4)
            self.assertGreaterEqual(metrics["mae_sd"], 0.0)
            self.assertGreaterEqual(metrics["rmse_sd"], 0.0)
            self.assertGreater(metrics["rmse_mean"], metrics["mae_mean"])

    def test_repeat_mean_tracks_pooled_mae(self):
        rows = make_panel()
        result = generalization.factorial_holdout(
            rows,
            ["x1", "x2"],
            seed=20261113,
            size_fraction=0.6,
            n_repeats=3,
            n_boot=50,
        )
        for arm in ARMS:
            pooled = result["arms"][arm]["model"]["mae_kg_ha"]
            repeat_mean = result["arms"][arm]["repeat_metrics"]["mae_mean"]
            self.assertAlmostEqual(pooled, repeat_mean, delta=1e-6, msg=arm)


if __name__ == "__main__":
    unittest.main()
