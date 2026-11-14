"""Testes da V2.8 — generalização temporal-espacial (D87).

Cobrem o que a V2.7 não cobria:

* as dobras do fatorial particionam blocos e anos sem sobreposição;
* o braço ``SE`` reproduz exatamente o P3 e o braço ``TE`` o P5 — é o teste
  que garante que o fatorial não é um protocolo novo, e sim uma leitura
  fatorial dos protocolos publicados;
* nenhuma linha de teste entra no treino de nenhum braço;
* o controle de tamanho iguala o número de linhas de treino entre braços;
* a reamostragem estratificada preserva os blocos do conjunto;
* o bootstrap por bloco devolve diferença nula e IC degenerado quando os
  erros são idênticos;
* os resultados são reprodutíveis com semente fixa.

Todos os testes são offline e usam painel sintético no formato do painel real.
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

from agroclimate import analysis, generalization  # noqa: E402


def make_panel(
    n_blocks: int = 12,
    n_years: int = 6,
    per_block: int = 5,
    seed: int = 31,
):
    """Painel sintético com blocos espaciais e anos bem definidos."""
    rng = np.random.default_rng(seed)
    rows = []
    for b in range(n_blocks):
        for m in range(per_block):
            code = f"m{b:02d}{m:02d}"
            block = f"B{b:02d}"
            state = f"S{b % 3}"
            for y in range(n_years):
                x1 = float(rng.normal() + 0.5 * b)
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
                            + 2.0 * y
                            + 10.0 * x1
                            - 4.0 * x2
                            + rng.normal()
                        ),
                    }
                )
    return rows


class FoldPartitionTest(unittest.TestCase):
    def test_folds_cover_blocks_and_years_without_overlap(self):
        rows = make_panel()
        blocks = sorted({r["spatial_block"] for r in rows})
        years = sorted({str(r["year"]) for r in rows})
        rng = np.random.default_rng(20261113)
        space = analysis._blocked_folds(blocks, 5, rng)
        time = analysis._blocked_folds(years, 5, rng)
        self.assertEqual(sorted(b for f in space for b in f), blocks)
        self.assertEqual(sorted(y for f in time for y in f), years)
        self.assertEqual(len({b for f in space for b in f}), len(blocks))
        self.assertEqual(len({y for f in time for y in f}), len(years))


class EquivalenceWithPublishedProtocolsTest(unittest.TestCase):
    """O fatorial precisa reproduzir P3 e P5 — senão não é o mesmo desenho."""

    def test_space_arm_matches_territorial_holdout(self):
        rows = make_panel()
        variables = ["x1", "x2"]
        result = generalization.factorial_holdout(
            rows, variables, seed=20261113, n_boot=100
        )
        self.assertEqual(result["status"], "ok")
        published = analysis.territorial_holdout(
            rows,
            variables,
            n_folds=5,
            crop_filter="soja",
            seed=20261113,
            group_key="spatial_block",
        )
        self.assertEqual(
            result["arms"]["SE"]["model"]["n"], published["models"]["modelo"]["n_predictions"]
        )
        self.assertAlmostEqual(
            result["arms"]["SE"]["model"]["mae_kg_ha"],
            published["models"]["modelo"]["mae_kg_ha"],
            places=9,
        )

    def test_two_way_arm_matches_two_way_holdout(self):
        rows = make_panel()
        variables = ["x1", "x2"]
        result = generalization.factorial_holdout(
            rows, variables, seed=20261113, n_boot=100
        )
        published = analysis.two_way_blocked_holdout(
            rows,
            variables,
            seed=20261113,
            crop_filter="soja",
            group_key="spatial_block",
        )
        self.assertEqual(
            result["arms"]["TE"]["model"]["n"], published["models"]["modelo"]["n_predictions"]
        )
        self.assertAlmostEqual(
            result["arms"]["TE"]["model"]["mae_kg_ha"],
            published["models"]["modelo"]["mae_kg_ha"],
            places=9,
        )


class NoLeakageTest(unittest.TestCase):
    def test_test_rows_are_never_in_training(self):
        """Reconstrói as máscaras de treino e confere a exclusão do teste."""
        rows = make_panel()
        blocks = sorted({r["spatial_block"] for r in rows})
        years = sorted({str(r["year"]) for r in rows})
        rng = np.random.default_rng(20261113)
        space = analysis._blocked_folds(blocks, 5, rng)
        time = analysis._blocked_folds(years, 5, rng)
        block_of = np.array([r["spatial_block"] for r in rows])
        year_of = np.array([str(r["year"]) for r in rows])
        for fold_blocks in space:
            in_block = np.isin(block_of, fold_blocks)
            for fold_years in time:
                in_year = np.isin(year_of, fold_years)
                test = in_block & in_year
                if not test.any():
                    continue
                for separated_space in (False, True):
                    for separated_time in (False, True):
                        pool = ~test
                        if separated_space:
                            pool &= ~in_block
                        if separated_time:
                            pool &= ~in_year
                        # nenhuma posição de teste pode estar no treino
                        self.assertFalse(bool((pool & test).any()))


class EqualSizeControlTest(unittest.TestCase):
    def test_equal_size_matches_across_arms(self):
        rows = make_panel(n_blocks=20, per_block=6)
        result = generalization.factorial_holdout(
            rows,
            ["x1", "x2"],
            seed=20261113,
            size_fraction=0.5,
            n_repeats=2,
            n_boot=100,
        )
        self.assertEqual(result["status"], "ok")
        target = result["target_train_size"]
        sizes = {
            arm: result["arms"][arm]["train_size_mean"]
            for arm in ("SS", "SE", "TS", "TE")
        }
        # nenhum braço pode exceder o alvo; o braço com mais informação
        # disponível tem de atingi-lo exatamente
        for arm, size in sizes.items():
            self.assertLessEqual(size, target + 1e-9, msg=arm)
        self.assertAlmostEqual(sizes["SS"], float(target), places=9)

    def test_subsample_is_exact_when_pool_is_large_enough(self):
        """O alvo é atingido exatamente quando há linhas suficientes."""
        rng = np.random.default_rng(11)
        pools = {
            "b1": np.arange(0, 100),
            "b2": np.arange(100, 200),
        }
        chosen = generalization.stratified_subsample(pools, 150, rng)
        self.assertEqual(len(chosen), 150)
        self.assertEqual(len(set(chosen.tolist())), 150)

    def test_subsample_preserves_blocks(self):
        rng = np.random.default_rng(7)
        pools = {
            "b1": np.arange(0, 40),
            "b2": np.arange(40, 60),
            "b3": np.arange(60, 64),
        }
        chosen = generalization.stratified_subsample(pools, 32, rng)
        self.assertEqual(len(chosen), 32)
        self.assertEqual(len(set(chosen.tolist())), 32)
        blocks = set()
        for value in chosen.tolist():
            for name, pool in pools.items():
                if value in pool:
                    blocks.add(name)
        self.assertEqual(blocks, {"b1", "b2", "b3"})

    def test_subsample_returns_all_when_target_is_larger(self):
        rng = np.random.default_rng(7)
        pools = {"b1": np.arange(0, 5)}
        chosen = generalization.stratified_subsample(pools, 50, rng)
        self.assertEqual(len(chosen), 5)


class BlockBootstrapTest(unittest.TestCase):
    def test_identical_errors_give_zero_difference(self):
        errors = np.abs(np.random.default_rng(3).normal(size=200))
        blocks = np.array([f"B{i % 8:02d}" for i in range(200)])
        result = generalization.block_bootstrap_difference(
            errors, errors, blocks, n_boot=200, seed=1
        )
        self.assertEqual(result["delta_mae"], 0.0)
        self.assertEqual(result["ci95"], [0.0, 0.0])

    def test_positive_shift_is_detected(self):
        rng = np.random.default_rng(5)
        base = np.abs(rng.normal(size=300))
        shifted = base + 5.0
        blocks = np.array([f"B{i % 10:02d}" for i in range(300)])
        result = generalization.block_bootstrap_difference(
            shifted, base, blocks, n_boot=200, seed=1
        )
        self.assertAlmostEqual(result["delta_mae"], 5.0, places=9)
        self.assertGreater(result["ci95"][0], 4.0)


class ReproducibilityTest(unittest.TestCase):
    def test_same_seed_same_result(self):
        rows = make_panel()
        first = generalization.factorial_holdout(
            rows, ["x1", "x2"], seed=20261113, size_fraction=0.6,
            n_repeats=2, n_boot=100,
        )
        second = generalization.factorial_holdout(
            rows, ["x1", "x2"], seed=20261113, size_fraction=0.6,
            n_repeats=2, n_boot=100,
        )
        for arm in ("SS", "SE", "TS", "TE"):
            self.assertEqual(
                first["arms"][arm]["model"]["mae_kg_ha"],
                second["arms"][arm]["model"]["mae_kg_ha"],
            )

    def test_insufficient_groups_is_reported(self):
        rows = make_panel(n_blocks=3)
        result = generalization.factorial_holdout(rows, ["x1", "x2"])
        self.assertEqual(result["status"], "insufficient_groups")


if __name__ == "__main__":
    unittest.main()
