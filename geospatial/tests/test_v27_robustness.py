"""Testes da V2.7 — inferência espacial, fenologia, CAD e robustez.

Cobre os itens exigidos no plano de testes da V2.7:

* distribuições estatísticas (valores tabelados);
* equivalência *within* ↔ LSDV;
* erro-padrão agrupado (CR1/CR2), dois sentidos e determinismo;
* Conley (kernel, corte, variância positiva e coerência com o agrupado);
* bootstrap wild: pesos **por grupo** (CGM), nulidade imposta, pesos novos
  por replicação, equivalência entre a forma em laço e a vetorizada;
* correções de Holm (monotonia, limites);
* divisões espaciais e **ausência de vazamento**;
* janela fenológica (perfis, soma térmica, ausência de dados);
* CAD (conversão de unidades, integração do perfil, ausência);
* persistência/retomada e ausência de duplicação;
* compatibilidade com a V2.6 (efeitos fixos reproduzidos).

Os testes são **offline**: nenhum acesso à rede.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GEO = os.path.abspath(os.path.join(HERE, ".."))
if GEO not in sys.path:
    sys.path.insert(0, GEO)

from agroclimate import (  # noqa: E402
    analysis,
    phenology,
    robust,
    soil,
    spatial,
    spatial_inference,
    thermal,
)


# --------------------------------------------------------------------- dados
def make_panel(
    n_municipalities: int = 40,
    n_years: int = 6,
    seed: int = 11,
    variable: str = "deficiency_total_mm",
):
    """Painel sintético no formato esperado por ``within_data``."""
    rng = np.random.default_rng(seed)
    rows = []
    for m in range(n_municipalities):
        base = rng.normal(size=n_years)
        for y in range(n_years):
            x = base[y] + rng.normal()
            rows.append(
                {
                    "ibge_code": f"m{m:03d}",
                    "year": 2000 + y,
                    "crop": "soja",
                    variable: float(x),
                    "yield_kg_ha": float(100.0 + 10.0 * x + rng.normal()),
                }
            )
    return rows


def make_coordinates(n: int = 40, seed: int = 5):
    rng = np.random.default_rng(seed)
    return {
        f"m{i:03d}": (float(rng.uniform(-25, -5)), float(rng.uniform(-58, -45)))
        for i in range(n)
    }


# ============================================================ distribuições
class DistributionTest(unittest.TestCase):
    def test_t_critical_matches_table(self):
        cases = [
            (12.706204736174698, 1, 0.05),
            (2.2281388519869383, 10, 0.05),
            (2.042272456301237, 30, 0.05),
            (2.7499956530698835, 30, 0.01),
        ]
        for expected, df, alpha in cases:
            self.assertAlmostEqual(
                robust.t_critical(alpha, df), expected, places=8,
                msg=f"t_critical(alpha={alpha}, df={df})",
            )

    def test_normal_cdf_and_ppf(self):
        self.assertAlmostEqual(robust.normal_cdf(1.959963984540054), 0.975, places=10)
        self.assertAlmostEqual(robust._normal_ppf(0.975), 1.9599639845, places=7)

    def test_t_sf_is_bilateral_and_symmetric(self):
        t = 2.5
        df = 17
        # t_sf e a sobrevivencia bilateral: P(|T| > |t|)
        self.assertAlmostEqual(robust.t_sf(t, df), robust.t_sf(-t, df), places=12)
        self.assertAlmostEqual(robust.t_sf(0.0, df), 1.0, places=12)

    def test_t_sf_decreases_in_t(self):
        values = [robust.t_sf(t, 10) for t in (0.5, 1.0, 2.0, 4.0)]
        self.assertEqual(values, sorted(values, reverse=True))


# ============================================================ within / LSDV
class WithinLsdvTest(unittest.TestCase):
    def test_within_equals_lsdv_on_panel(self):
        rows = make_panel()
        result = spatial_inference.within_coefficient_matches_lsdv(
            rows, "deficiency_total_mm"
        )
        self.assertEqual(result["status"], "ok")
        self.assertLess(result["absolute_difference"], 1e-8)

    def test_within_transform_removes_group_means(self):
        values = np.array([1.0, 2.0, 3.0, 5.0, 6.0, 7.0])
        groups = ["a", "a", "a", "b", "b", "b"]
        transformed = spatial_inference.within_transform(
            values, groups, [0, 0, 0, 1, 1, 1]
        )
        self.assertAlmostEqual(float(np.mean(transformed[:3])), 0.0, places=10)
        self.assertAlmostEqual(float(np.mean(transformed[3:])), 0.0, places=10)

    def test_within_data_reports_dimensions(self):
        prepared = spatial_inference.within_data(make_panel(), "deficiency_total_mm")
        self.assertEqual(prepared["status"], "ok")
        self.assertEqual(prepared["n"], 40 * 6)
        self.assertEqual(prepared["n_municipalities"], 40)
        self.assertEqual(prepared["n_years"], 6)


# ============================================================ cluster robust
class ClusterRobustTest(unittest.TestCase):
    def test_cluster_vcov_is_positive_definite(self):
        rows = make_panel()
        prepared = spatial_inference.within_data(rows, "deficiency_total_mm")
        X = np.column_stack([np.ones(prepared["n"]), prepared["x"]])
        y = prepared["y"]
        groups = [str(g) for g in prepared["municipalities"]]
        fit = robust.cluster_robust_fit(X, y, groups, coef_index=1)
        self.assertEqual(fit["status"], "ok")
        self.assertGreater(fit["std_error_clustered"], 0.0)
        self.assertEqual(fit["n_clusters"], 40)

    def test_fit_and_vcov_agree(self):
        rows = make_panel()
        prepared = spatial_inference.within_data(rows, "deficiency_total_mm")
        X = np.column_stack([np.ones(prepared["n"]), prepared["x"]])
        y = prepared["y"]
        groups = [str(g) for g in prepared["municipalities"]]
        fit = robust.cluster_robust_fit(X, y, groups, coef_index=1)
        residuals = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
        vcov, info = robust.cluster_vcov(X, residuals, groups)
        self.assertAlmostEqual(
            math.sqrt(max(vcov[1, 1], 0.0)), fit["std_error_clustered"], places=12
        )
        self.assertEqual(info["n_clusters"], 40)

    def test_determinism(self):
        rows = make_panel()
        prepared = spatial_inference.within_data(rows, "deficiency_total_mm")
        X = np.column_stack([np.ones(prepared["n"]), prepared["x"]])
        groups = [str(g) for g in prepared["municipalities"]]
        first = robust.cluster_robust_fit(X, prepared["y"], groups, coef_index=1)
        second = robust.cluster_robust_fit(X, prepared["y"], groups, coef_index=1)
        self.assertEqual(first["std_error_clustered"], second["std_error_clustered"])

    def test_cr1_multiplier(self):
        n, k, g = 100, 2, 10
        rng = np.random.default_rng(1)
        X = np.column_stack([np.ones(n), rng.normal(size=n)])
        groups = [str(i % g) for i in range(n)]
        residuals = rng.normal(size=n)
        _, info = robust.cluster_vcov(X, residuals, groups, correction=robust.CR1)
        expected = (g / (g - 1.0)) * ((n - 1.0) / (n - k))
        self.assertAlmostEqual(info["small_sample_multiplier"], expected, places=12)

    def test_two_way_vcov_positive(self):
        rows = make_panel()
        prepared = spatial_inference.within_data(rows, "deficiency_total_mm")
        X = np.column_stack([np.ones(prepared["n"]), prepared["x"]])
        y = prepared["y"]
        residuals = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
        vcov, info = robust.two_way_cluster_vcov(
            X,
            residuals,
            [str(g) for g in prepared["municipalities"]],
            [str(g) for g in prepared["years"]],
        )
        self.assertTrue(np.isfinite(vcov[1, 1]))
        self.assertGreater(vcov[1, 1], 0.0)
        self.assertGreaterEqual(info["n_clusters_a"], 2)
        self.assertGreaterEqual(info["n_clusters_b"], 2)


# ===================================================================== Conley
class ConleyTest(unittest.TestCase):
    def test_variance_positive_for_all_cutoffs(self):
        rows = make_panel()
        prepared = spatial_inference.within_data(rows, "deficiency_total_mm")
        X = np.column_stack([np.ones(prepared["n"]), prepared["x"]])
        y = prepared["y"]
        residuals = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
        groups = [str(g) for g in prepared["municipalities"]]
        coords = make_coordinates(40)
        for cutoff in (150.0, 250.0, 400.0):
            vcov, info = robust.conley_vcov(X, residuals, groups, coords, cutoff_km=cutoff)
            self.assertTrue(np.isfinite(vcov[1, 1]))
            self.assertGreater(vcov[1, 1], 0.0)
            self.assertEqual(info["cutoff_km"], cutoff)

    def test_larger_cutoff_does_not_shrink_variance(self):
        rows = make_panel()
        prepared = spatial_inference.within_data(rows, "deficiency_total_mm")
        X = np.column_stack([np.ones(prepared["n"]), prepared["x"]])
        y = prepared["y"]
        residuals = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
        groups = [str(g) for g in prepared["municipalities"]]
        coords = make_coordinates(40)
        variances = []
        for cutoff in (150.0, 400.0, 800.0):
            vcov, _ = robust.conley_vcov(X, residuals, groups, coords, cutoff_km=cutoff)
            variances.append(vcov[1, 1])
        self.assertGreaterEqual(variances[0], variances[1] * 0.999)
        self.assertGreaterEqual(variances[1], variances[2] * 0.999)

    def test_kernel_weights_are_valid(self):
        rows = make_panel()
        prepared = spatial_inference.within_data(rows, "deficiency_total_mm")
        X = np.column_stack([np.ones(prepared["n"]), prepared["x"]])
        y = prepared["y"]
        residuals = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
        groups = [str(g) for g in prepared["municipalities"]]
        coords = make_coordinates(40)
        _, info = robust.conley_vcov(X, residuals, groups, coords, cutoff_km=250.0)
        self.assertGreaterEqual(info["mean_weight"], 0.0)
        self.assertLessEqual(info["mean_weight"], 1.0)


# ============================================================ wild bootstrap
class WildBootstrapTest(unittest.TestCase):
    def test_weights_are_constant_within_cluster(self):
        groups = ["a"] * 5 + ["b"] * 5 + ["c"] * 5
        matrix = robust._rademacher_matrix(
            groups, 20, 42, robust.WEIGHT_CLUSTER
        )
        self.assertEqual(matrix.shape, (15, 20))
        for group in ("a", "b", "c"):
            idx = [i for i, g in enumerate(groups) if g == group]
            for column in range(matrix.shape[1]):
                self.assertEqual(len(set(matrix[idx, column].tolist())), 1)

    def test_observation_scheme_differs(self):
        groups = ["a"] * 5 + ["b"] * 5
        cluster = robust._rademacher_matrix(groups, 10, 7, robust.WEIGHT_CLUSTER)
        observation = robust._rademacher_matrix(
            groups, 10, 7, robust.WEIGHT_OBSERVATION
        )
        self.assertFalse(np.array_equal(cluster, observation))

    def test_new_weights_per_replication(self):
        groups = ["a"] * 5 + ["b"] * 5
        matrix = robust._rademacher_matrix(groups, 50, 11, robust.WEIGHT_CLUSTER)
        columns = {tuple(matrix[:, c].tolist()) for c in range(matrix.shape[1])}
        self.assertGreater(len(columns), 1)

    def test_vectorized_equals_loop(self):
        rows = make_panel()
        prepared = spatial_inference.within_data(rows, "deficiency_total_mm")
        groups = [str(g) for g in prepared["municipalities"]]
        loop = spatial_inference.wild_cluster_bootstrap_within(
            prepared, groups, n_boot=199, seed=13
        )
        fast = spatial_inference.wild_cluster_bootstrap_within_fast(
            prepared, groups, n_boot=199, seed=13
        )
        self.assertEqual(loop["p_value"], fast["p_value"])
        self.assertEqual(loop["p_value_imposed"], fast["p_value_imposed"])
        self.assertEqual(loop["p_value_unrestricted"], fast["p_value_unrestricted"])

    def test_null_imposed_and_unrestricted_are_reported(self):
        rows = make_panel()
        prepared = spatial_inference.within_data(rows, "deficiency_total_mm")
        groups = [str(g) for g in prepared["municipalities"]]
        result = spatial_inference.wild_cluster_bootstrap_within_fast(
            prepared, groups, n_boot=199, seed=13
        )
        self.assertIn("p_value_imposed", result)
        self.assertIn("p_value_unrestricted", result)
        self.assertTrue(0.0 < result["p_value"] <= 1.0)

    def test_null_policies_select_expected_branch(self):
        rows = make_panel()
        prepared = spatial_inference.within_data(rows, "deficiency_total_mm")
        groups = [str(g) for g in prepared["municipalities"]]
        imposed = spatial_inference.wild_cluster_bootstrap_within_fast(
            prepared, groups, n_boot=199, seed=13, null_policy=robust.NULL_POLICY_IMPOSED
        )
        unrestricted = spatial_inference.wild_cluster_bootstrap_within_fast(
            prepared,
            groups,
            n_boot=199,
            seed=13,
            null_policy=robust.NULL_POLICY_UNRESTRICTED,
        )
        self.assertEqual(imposed["p_value"], imposed["p_value_imposed"])
        self.assertEqual(
            unrestricted["p_value"], unrestricted["p_value_unrestricted"]
        )

    def test_select_null_policy_rules(self):
        self.assertEqual(
            robust.select_null_policy("imposed", 0.01, 0.5), "imposed"
        )
        self.assertEqual(
            robust.select_null_policy("unrestricted", 0.01, 0.5), "unrestricted"
        )
        # "auto": usa a irrestrita quando a imposta nao rejeita (p > 0,10)
        self.assertEqual(robust.select_null_policy("auto", 0.5, 0.6), "unrestricted")
        self.assertEqual(robust.select_null_policy("auto", 0.05, 0.6), "imposed")
        with self.assertRaises(ValueError):
            robust.select_null_policy("desconhecida", 0.1, 0.2)

    def test_ols_vectorized_equals_loop(self):
        rng = np.random.default_rng(2)
        groups = [str(i % 15) for i in range(150)]
        X = np.column_stack([np.ones(150), rng.normal(size=150)])
        y = X @ np.array([0.0, 1.5]) + rng.normal(size=150)
        loop = robust.wild_cluster_bootstrap(
            X, y, groups, coef_index=1, n_boot=199, seed=3
        )
        fast = robust.wild_cluster_bootstrap_fast(
            X, y, groups, coef_index=1, n_boot=199, seed=3
        )
        self.assertEqual(loop["p_value"], fast["p_value"])


# ============================================ coerência observado x bootstrap
class BootstrapCoherenceTest(unittest.TestCase):
    """A réplica com pesos +1 é a própria amostra.

    Esse invariante é o que garante que a estatística simulada e a observada
    são comparáveis: a distribuição bootstrap tem de reproduzir exatamente o
    mesmo erro-padrão quando os pesos não alteram os dados. Ele também
    protege contra a exclusão de clusters singleton da carne do estimador,
    que reduziria a variância simulada e inflaria a rejeição.
    """

    def test_degenerate_std_error_helper(self):
        self.assertTrue(robust.degenerate_std_error(0.0, 0.0))
        self.assertTrue(robust.degenerate_std_error(1.0, 1e-19))
        self.assertTrue(robust.degenerate_std_error(1.0, float("nan")))
        self.assertFalse(robust.degenerate_std_error(1.0, 0.05))
        self.assertFalse(robust.degenerate_std_error(0.0, 0.05))

    def test_ols_bootstrap_unit_weights_reproduce_observed_statistics(self):
        rng = np.random.default_rng(7)
        groups = [str(i % 12) for i in range(144)]
        design = np.column_stack([np.ones(144), rng.normal(size=144)])
        y = design @ np.array([0.5, 1.5]) + rng.normal(size=144)
        fit = robust.cluster_robust_fit(design, y, groups, coef_index=1)
        beta = np.linalg.lstsq(design, y, rcond=None)[0]
        weights = np.ones((144, 1))
        t_stats = robust._wild_t_stats_vectorized(
            design, design @ beta, y - design @ beta, weights, 1, groups,
        )
        self.assertAlmostEqual(float(t_stats[0]), fit["t_statistic"], places=8)

    def test_within_bootstrap_unit_weights_reproduce_observed_se(self):
        rows = make_panel(n_municipalities=30, n_years=5)
        # Três municípios ficam com um único ano: são clusters singleton e
        # precisam entrar na variância simulada exatamente como entram na
        # observada.
        singletons = {"m000", "m001", "m002"}
        trimmed = [
            row
            for row in rows
            if not (row["ibge_code"] in singletons and row["year"] != 2000)
        ]
        prepared = spatial_inference.within_data(trimmed, "deficiency_total_mm")
        self.assertEqual(prepared["status"], "ok")
        x = prepared["x_within"]
        y = prepared["y_within"]
        groups = [str(g) for g in prepared["municipalities"]]
        index: dict[str, list[int]] = {}
        for position, group in enumerate(groups):
            index.setdefault(group, []).append(position)
        self.assertTrue(any(len(v) == 1 for v in index.values()))
        n = len(x)
        g = len(index)
        denominator = float(np.dot(x, x))
        coefficient = float(np.dot(x, y) / denominator)
        residuals = y - coefficient * x
        names = sorted(index)
        position = {name: i for i, name in enumerate(names)}
        obs_position = np.array([position[name] for name in groups], dtype="int64")
        group_index = [np.asarray(index[name], dtype=int) for name in names]
        multiplier = (g / (g - 1.0)) * ((n - 1.0) / (n - 2))
        draws = np.ones((1, n))
        t_stats = spatial_inference._within_wild_t_stats(
            x,
            coefficient * x,
            residuals,
            draws,
            obs_position,
            group_index,
            denominator,
            multiplier,
            True,
        )
        observed_se, _, _ = spatial_inference._clustered_se(x, y, groups)
        self.assertAlmostEqual(
            float(t_stats[0]), coefficient / observed_se, places=8
        )

    def test_within_fast_includes_singleton_clusters(self):
        rows = make_panel(n_municipalities=25, n_years=6)
        trimmed = [
            row
            for row in rows
            if not (row["ibge_code"] == "m000" and row["year"] != 2003)
        ]
        prepared = spatial_inference.within_data(trimmed, "deficiency_total_mm")
        groups = [str(g) for g in prepared["municipalities"]]
        loop = spatial_inference.wild_cluster_bootstrap_within(
            prepared, groups, n_boot=199, seed=5
        )
        fast = spatial_inference.wild_cluster_bootstrap_within_fast(
            prepared, groups, n_boot=199, seed=5
        )
        self.assertEqual(loop["p_value"], fast["p_value"])
        self.assertGreater(loop["t_boot_sd"], 0.0)


# ======================================================================= Holm
class HolmTest(unittest.TestCase):
    def test_monotone_and_bounded(self):
        adjusted = analysis.holm_correction({"a": 0.01, "b": 0.04, "c": 0.2})
        self.assertLessEqual(adjusted["a"], adjusted["b"])
        self.assertLessEqual(adjusted["b"], adjusted["c"])
        self.assertTrue(all(0.0 < v <= 1.0 for v in adjusted.values()))

    def test_never_below_raw(self):
        raw = {"a": 0.001, "b": 0.2, "c": 0.5}
        adjusted = analysis.holm_correction(raw)
        for key, value in raw.items():
            self.assertGreaterEqual(adjusted[key], value)

    def test_alias_matches_implementation(self):
        raw = {"a": 0.01, "b": 0.3}
        self.assertEqual(robust.holm_adjust(raw), analysis.holm_correction(raw))


# ========================================================== divisões espaciais
class SpatialSplitTest(unittest.TestCase):
    def _municipalities(self, n: int = 60):
        rows = []
        rng = np.random.default_rng(4)
        for i in range(n):
            rows.append(
                {
                    "ibge_code": f"m{i:03d}",
                    "municipality": f"M{i}",
                    "state": "BA" if i % 2 == 0 else "MG",
                    "centroid_lat": float(rng.uniform(-25, -5)),
                    "centroid_lon": float(rng.uniform(-58, -45)),
                    "elevation_m": 100.0,
                }
            )
        return rows

    def test_spatial_blocks_are_disjoint(self):
        municipalities = self._municipalities()
        blocks = spatial.spatial_blocks(municipalities, 250.0)
        by_block: dict[str, list[str]] = {}
        for code, block in blocks.items():
            by_block.setdefault(str(block), []).append(code)
        self.assertGreater(len(by_block), 1)
        all_codes = [c for codes in by_block.values() for c in codes]
        self.assertEqual(len(all_codes), len(set(all_codes)))

    def test_split_by_groups_has_no_leakage(self):
        municipalities = self._municipalities()
        blocks = spatial.spatial_blocks(municipalities, 250.0)
        codes = [str(row["ibge_code"]) for row in municipalities]
        rows = [
            {"ibge_code": code, "group_id": str(blocks.get(code))} for code in codes
        ]
        unique = sorted({row["group_id"] for row in rows})
        train_groups = unique[0::2]
        test_groups = unique[1::2]
        train, test = spatial.split_by_groups(rows, train_groups, test_groups)
        self.assertEqual(len(train) + len(test), len(rows))
        self.assertEqual(
            {row["group_id"] for row in train} & {row["group_id"] for row in test},
            set(),
        )

    def test_split_by_groups_rejects_overlap(self):
        rows = [{"ibge_code": "a", "group_id": "g1"}]
        with self.assertRaises(ValueError):
            spatial.split_by_groups(rows, ["g1"], ["g1"])

    def test_leakage_report_detects_shared_values(self):
        train = [
            {"ibge_code": "m001", "cluster_id": "c1"},
            {"ibge_code": "m002", "cluster_id": "c2"},
        ]
        test = [
            {"ibge_code": "m001", "cluster_id": "c3"},
            {"ibge_code": "m003", "cluster_id": "c4"},
        ]
        report = spatial.leakage_report(train, test)
        self.assertTrue(report["ibge_code"]["leakage"])
        self.assertFalse(report["cluster_id"]["leakage"])
        self.assertFalse(report["no_leakage"])

    def test_municipality_cells_are_deterministic(self):
        municipalities = self._municipalities()
        first = spatial.municipality_cells(municipalities)
        second = spatial.municipality_cells(municipalities)
        self.assertEqual(first, second)


# ================================================== holdout espacial e temporal
class TwoWayHoldoutTest(unittest.TestCase):
    """O protocolo P5 não pode compartilhar bloco **nem** ano entre treino e teste."""

    def _rows(self, n_municipalities: int = 30, n_years: int = 8):
        rng = np.random.default_rng(23)
        rows = []
        for m in range(n_municipalities):
            for y in range(n_years):
                value = float(rng.normal())
                rows.append(
                    {
                        "ibge_code": f"m{m:03d}",
                        "year": 2000 + y,
                        "crop": "soja",
                        "v": value,
                        "yield_kg_ha": float(100.0 + 10.0 * value + rng.normal()),
                        "spatial_block_id": f"b{m % 10:02d}",
                    }
                )
        return rows

    def test_folds_are_disjoint_and_cover_groups(self):
        rows = self._rows()
        result = analysis.two_way_blocked_holdout(
            rows, ["v"], crop_filter="soja", seed=7
        )
        self.assertEqual(result["status"], "ok")
        groups = sorted({row["spatial_block_id"] for row in rows})
        times = sorted({str(row["year"]) for row in rows})
        flat_groups = sorted(g for fold in result["space_folds"] for g in fold)
        flat_times = sorted(t for fold in result["time_folds"] for t in fold)
        self.assertEqual(flat_groups, groups)
        self.assertEqual(flat_times, times)
        self.assertEqual(len(result["space_folds"]), 5)
        self.assertEqual(len(result["time_folds"]), 5)

    def test_train_and_test_share_neither_block_nor_year(self):
        rows = self._rows()
        result = analysis.two_way_blocked_holdout(
            rows, ["v"], crop_filter="soja", seed=7
        )
        self.assertGreater(result["n_folds"], 1)
        for space in result["space_folds"]:
            for time in result["time_folds"]:
                space_set, time_set = set(space), set(time)
                test_rows = [
                    r
                    for r in rows
                    if r["spatial_block_id"] in space_set and str(r["year"]) in time_set
                ]
                train_rows = [
                    r
                    for r in rows
                    if r["spatial_block_id"] not in space_set
                    and str(r["year"]) not in time_set
                ]
                self.assertFalse(
                    {r["spatial_block_id"] for r in test_rows}
                    & {r["spatial_block_id"] for r in train_rows}
                )
                self.assertFalse(
                    {r["year"] for r in test_rows} & {r["year"] for r in train_rows}
                )

    def test_predictions_cover_all_usable_cells(self):
        rows = self._rows()
        result = analysis.two_way_blocked_holdout(
            rows, ["v"], crop_filter="soja", seed=7
        )
        expected = 0
        for space in result["space_folds"]:
            for time in result["time_folds"]:
                space_set, time_set = set(space), set(time)
                has_test = any(
                    r["spatial_block_id"] in space_set and str(r["year"]) in time_set
                    for r in rows
                )
                has_train = any(
                    r["spatial_block_id"] not in space_set
                    and str(r["year"]) not in time_set
                    for r in rows
                )
                if has_test and has_train:
                    expected += sum(
                        1
                        for r in rows
                        if r["spatial_block_id"] in space_set
                        and str(r["year"]) in time_set
                    )
        self.assertEqual(result["n_predictions"], expected)

    def test_reports_baseline_and_model(self):
        rows = self._rows()
        result = analysis.two_way_blocked_holdout(
            rows, ["v"], crop_filter="soja", seed=7
        )
        self.assertIn("media_historica", result["models"])
        self.assertIn("modelo", result["models"])
        self.assertEqual(
            result["models"]["modelo"]["n_predictions"], result["n_predictions"]
        )

    def test_insufficient_groups_returns_status(self):
        rows = self._rows(n_municipalities=2, n_years=8)
        result = analysis.two_way_blocked_holdout(
            rows, ["v"], crop_filter="soja", seed=7
        )
        self.assertEqual(result["status"], "insufficient_groups")


# ================================================================= fenologia
class PhenologyTest(unittest.TestCase):
    def _daily(self, n_days: int = 200, tmax: float = 30.0, tmin: float = 20.0):
        import datetime as dt

        start = dt.date(2020, 1, 1)
        return [
            {
                "date": (start + dt.timedelta(days=i)).isoformat(),
                "temp_max_c": tmax,
                "temp_min_c": tmin,
            }
            for i in range(n_days)
        ]

    def test_profiles_have_published_requirements(self):
        self.assertEqual(phenology.SOJA_MEDIO.stages[0].degree_days, 92.5)
        self.assertEqual(phenology.SOJA_MEDIO.stages[1].degree_days, 554.0)
        self.assertEqual(phenology.MILHO_GRUPO_I.stages[0].degree_days, 780.0)
        self.assertEqual(phenology.MILHO_GRUPO_II.stages[0].degree_days, 860.0)
        self.assertEqual(phenotion_guard := phenology.MILHO_GRUPO_III.stages[0].degree_days, 1050.0)
        self.assertTrue(phenotion_guard)

    def test_thermal_profile_matches_panel(self):
        # o perfil fenológico usa a MESMA aritmética de graus-dia do painel
        for profile in phenology.PHENOLOGY_PROFILES.values():
            self.assertIn(profile.thermal_profile_key, thermal.PROFILES)
            base = thermal.PROFILES[profile.thermal_profile_key]
            self.assertEqual(profile.base_temperature_c, base.base_temperature_c)
            self.assertEqual(profile.upper_temperature_c, base.upper_temperature_c)

    def test_stage_dates_reach_r1(self):
        daily = self._daily(120)
        result = phenology.stage_dates(daily, phenology.SOJA_MEDIO, "2020-01-01")
        self.assertEqual(result["status"], "ok")
        self.assertIsNotNone(result["stages"]["R1"]["date_approx"])

    def test_grain_filling_window_has_positive_duration(self):
        daily = self._daily(200)
        window = phenology.grain_filling_window(
            daily, phenology.SOJA_MEDIO, "2020-01-01"
        )
        self.assertEqual(window["status"], "ok")
        self.assertGreater(window["window_end"], window["window_start"])

    def test_missing_daily_data_is_preserved(self):
        window = phenology.grain_filling_window(
            [], phenology.SOJA_MEDIO, "2020-01-01"
        )
        self.assertEqual(window["status"], "sem_dados")

    def test_crop_without_published_definition(self):
        window = phenology.grain_filling_window(
            self._daily(200), phenology.MILHO_2_SAFRA, "2020-01-01"
        )
        self.assertEqual(window["status"], "sem_definicao_publicada")


# ====================================================================== CAD
class SoilCadTest(unittest.TestCase):
    def test_layer_thicknesses(self):
        expected = {
            "aw_0_5": 5.0,
            "aw_5_15": 10.0,
            "aw_15_30": 15.0,
            "aw_30_60": 30.0,
            "aw_60_100": 40.0,
            "aw_100_200": 100.0,
        }
        for layer in soil.AW_LAYERS:
            self.assertAlmostEqual(
                soil.layer_thickness_cm(layer), expected[layer["key"]], places=6
            )

    def test_integration_converts_mm_per_cm_to_mm(self):
        values = {layer["key"]: 1.5 for layer in soil.AW_LAYERS}
        profile = soil.profile_capacity_mm(values)
        # 1,5 mm/cm x 200 cm = 300 mm
        self.assertAlmostEqual(profile["capacity_mm"], 300.0, places=6)
        self.assertTrue(profile["profile_complete"])

    def test_partial_profile_is_not_reported_as_complete(self):
        values = {layer["key"]: 1.5 for layer in soil.AW_LAYERS}
        values["aw_30_60"] = None
        profile = soil.profile_capacity_mm(values)
        self.assertIsNone(profile["capacity_mm"])
        self.assertFalse(profile["profile_complete"])
        self.assertLess(profile["coverage_fraction"], 1.0)

    def test_nodata_values_are_cleaned(self):
        self.assertIsNone(soil.clean_value(-9999.0))
        self.assertIsNone(soil.clean_value(-3.4028235e38))
        self.assertIsNone(soil.clean_value(None))
        self.assertIsNone(soil.clean_value(float("nan")))
        self.assertAlmostEqual(soil.clean_value(1.55), 1.55, places=9)

    def test_depth_limited_profile(self):
        values = {layer["key"]: 1.0 for layer in soil.AW_LAYERS}
        profile = soil.profile_capacity_to_depth_mm(values, 60.0)
        # 1,0 mm/cm x 60 cm = 60 mm
        self.assertAlmostEqual(profile["capacity_mm"], 60.0, places=6)
        self.assertIn("aw_60_100", profile["excluded_layers"])

    def test_comparison_with_v26_scenarios(self):
        comparison = soil.compare_with_scenarios(120.0)
        self.assertTrue(comparison["exceeds_all_scenarios"])
        self.assertAlmostEqual(comparison["ratios"]["35"], 120.0 / 35.0, places=9)
        empty = soil.compare_with_scenarios(None)
        self.assertEqual(empty["status"], "sem_dado")


# ================================================= persistência / retomada
class PersistenceTest(unittest.TestCase):
    def test_manifest_roundtrip_keeps_values(self):
        payload = {"a": 1, "b": [1.5, 2.5], "c": {"d": None}}
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "m.json")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), payload)

    def test_panel_has_no_duplicate_observations(self):
        """O painel da V2.6 não pode ter duplicatas por (município, cultura, ano)."""
        path = os.path.join(
            GEO, "data", "processed", "agroclimatic_productivity_panel.csv"
        )
        if not os.path.exists(path):
            self.skipTest("painel não disponível neste ambiente")
        import csv

        seen = set()
        duplicates = 0
        with open(path, encoding="utf-8-sig", newline="") as handle:
            for record in csv.DictReader(handle):
                key = (
                    record["ibge_code"],
                    record["crop"],
                    record["climate_source"],
                    record["harvest_year"],
                )
                if key in seen:
                    duplicates += 1
                seen.add(key)
        self.assertEqual(duplicates, 0)

    def test_missing_indicator_stays_missing(self):
        rows = make_panel()
        rows[0]["deficiency_total_mm"] = None
        prepared = spatial_inference.within_data(rows, "deficiency_total_mm")
        self.assertEqual(prepared["n"], len(rows) - 1)


# ============================================== compatibilidade com a V2.6
class V26CompatibilityTest(unittest.TestCase):
    def test_fixed_effects_keep_known_result(self):
        """Coeficiente do déficit hídrico da soja reproduz a V2.6."""
        path = os.path.join(
            GEO, "data", "processed", "agroclimatic_productivity_panel.csv"
        )
        if not os.path.exists(path):
            self.skipTest("painel não disponível neste ambiente")
        import csv

        rows = []
        with open(path, encoding="utf-8-sig", newline="") as handle:
            for record in csv.DictReader(handle):
                if record["climate_source"] != "NASA-POWER":
                    continue
                if record["crop"] != "soja":
                    continue
                rows.append(record)
        # o mesmo caminho de preparo usado pela V2.6
        prepared = analysis.prepare_rows(rows)
        result = analysis.fixed_effects(
            prepared, "deficiency_total_mm", crop_filter="soja"
        )
        self.assertEqual(result["status"], "ok")
        # valor de referência da V2.6 (manifesto da V2.6)
        self.assertAlmostEqual(result["coefficient"], -1.260169893887058, places=9)
        self.assertEqual(result["n"], 8884)
        self.assertEqual(result["n_municipalities"], 1225)
        self.assertEqual(result["n_years"], 8)


if __name__ == "__main__":
    unittest.main()
