"""Testes da V2.5 — janelas ZARC, pareamento, estatísticas e série municipal."""

from __future__ import annotations

import csv
import os
import tempfile
import unittest

import numpy as np

from agri import pairing, season
from historical import municipal_series as mser
from historical import reeval


class DecendRuleTest(unittest.TestCase):
    """Regra oficial do MAPA: três decêndios por mês (1–10, 11–20, 21–fim)."""

    def test_month_and_segment(self):
        self.assertEqual(season.decend_month(1), 1)
        self.assertEqual(season.decend_month(3), 1)
        self.assertEqual(season.decend_month(4), 2)
        self.assertEqual(season.decend_month(36), 12)
        self.assertEqual(season.decend_segment(1), 1)
        self.assertEqual(season.decend_segment(3), 3)
        self.assertEqual(season.decend_segment(4), 1)

    def test_decend_dates(self):
        self.assertEqual(season.decend_to_dates(2023, 1), ("2023-01-01", "2023-01-10"))
        self.assertEqual(season.decend_to_dates(2023, 2), ("2023-01-11", "2023-01-20"))
        self.assertEqual(season.decend_to_dates(2023, 3), ("2023-01-21", "2023-01-31"))
        self.assertEqual(season.decend_to_dates(2023, 4), ("2023-02-01", "2023-02-10"))

    def test_february_non_leap_and_leap(self):
        self.assertEqual(season.decend_to_dates(2023, 6)[1], "2023-02-28")
        self.assertEqual(season.decend_to_dates(2024, 6)[1], "2024-02-29")

    def test_december_last_decend(self):
        self.assertEqual(season.decend_to_dates(2023, 36), ("2023-12-21", "2023-12-31"))

    def test_invalid_decend_raises(self):
        with self.assertRaises(ValueError):
            season.decend_to_dates(2023, 37)
        with self.assertRaises(ValueError):
            season.decend_to_dates(2023, 0)


class PamYearRelationTest(unittest.TestCase):
    def test_soja_primary_is_harvest_year(self):
        relation = season.pam_year_candidates("2019/20", "soja")
        self.assertEqual(relation["primary"], 2020)
        self.assertEqual(relation["alternative"], 2019)
        self.assertEqual(relation["confidence"], "media_alta")

    def test_second_saison_milho_is_planted_next_year(self):
        relation = season.pam_year_candidates("2019/20", "milho_2")
        self.assertEqual(relation["primary"], 2020)
        self.assertIn("total anual", relation["ambiguity"])

    def test_milho_total_has_no_specific_season(self):
        relation = season.pam_year_candidates("2019/20", "milho")
        self.assertEqual(relation["primary"], 2020)


class WindowTest(unittest.TestCase):
    def _rows(self):
        return [
            {
                "safra": "2019/20",
                "safra_ini": "2019",
                "safra_fin": "2020",
                "cultura": "Soja",
                "cod_ciclo": "20",
                "cod_solo": "1",
                "cod_clima": "",
                "portaria": "port.63",
                "decendios_com_risco": "29:20;30:20;31:20;32:20;33:20;34:20;35:20;36:20",
            },
            {
                "safra": "2019/20",
                "safra_ini": "2019",
                "safra_fin": "2020",
                "cultura": "Soja",
                "cod_ciclo": "21",
                "cod_solo": "1",
                "cod_clima": "",
                "portaria": "port.63",
                "decendios_com_risco": "29:20;30:20;31:20;32:20;33:20;34:20;35:20;36:20",
            },
            {
                "safra": "2019/20",
                "safra_ini": "2019",
                "safra_fin": "2020",
                "cultura": "Milho 2ª Safra",
                "cod_ciclo": "20",
                "cod_solo": "1",
                "cod_clima": "",
                "portaria": "port.99",
                "decendios_com_risco": "1:20;2:20;3:20;4:20;5:20",
            },
        ]

    def test_build_windows_preserves_combinations(self):
        windows = season.build_windows(self._rows(), "soja")
        self.assertEqual(len(windows), 2)  # duas combinações de solo/ciclo
        for window in windows:
            self.assertEqual(window["months"], [10, 11, 12])
            self.assertTrue(window["start_date"].startswith("2019-10"))
            self.assertTrue(window["end_date"].startswith("2019-12"))

    def test_second_saison_window_is_january_february(self):
        windows = season.build_windows(self._rows(), "milho_2")
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["months"], [1, 2])

    def test_consensus_window_takes_modal_combination(self):
        windows = season.build_windows(self._rows(), "soja")
        window = pairing.consensus_window(windows, "2019/20")
        self.assertIsNotNone(window)
        self.assertEqual(window["months"], [10, 11, 12])


class PairingTest(unittest.TestCase):
    def _zarc(self):
        return [
            {
                "safra": "2019/20", "safra_ini": "2019", "safra_fin": "2020",
                "cultura": "Soja", "cod_ciclo": "20", "cod_solo": "1",
                "cod_clima": "", "portaria": "port.63",
                "decendios_com_risco": "29:20;30:20;31:20",
            }
        ]

    def _pam(self):
        return [
            {
                "institution": "IBGE", "dataset_name": "PAM", "dataset_id": "SIDRA:5457",
                "crop_code": "40124", "reference_year": "2020",
                "variable_normalized": "rendimento_medio_kg_ha",
                "value_normalized": "3540", "unit_original": "Quilogramas por Hectare",
                "nature": "observed", "acquired_at": "2026-11-11T00:00:00+00:00",
            }
        ]

    def _municipal(self):
        return [
            {"month": "2019-10", "mask_variant": "stable", "ndvi_mean": "0.55",
             "valid_fraction": "0.98"},
            {"month": "2019-11", "mask_variant": "stable", "ndvi_mean": "0.58",
             "valid_fraction": "0.97"},
            {"month": "2020-10", "mask_variant": "stable", "ndvi_mean": "0.60",
             "valid_fraction": "0.99"},
        ]

    def _aoi(self):
        return [
            {"month": "2019-10", "ndvi_mean": "0.52", "valid_fraction": "0.98"},
            {"month": "2019-11", "ndvi_mean": "0.53", "valid_fraction": "0.98"},
            {"month": "2020-10", "ndvi_mean": "0.55", "valid_fraction": "0.99"},
        ]

    def test_dataset_uses_harvest_year(self):
        dataset = pairing.build_paired_dataset(
            self._zarc(), self._municipal(), self._aoi(), self._pam()
        )
        soja = [r for r in dataset if r["crop"] == "soja"]
        self.assertTrue(soja)
        row = soja[0]
        self.assertEqual(str(row["pam_reference_year"]), "2020")
        self.assertEqual(float(row["yield_kg_ha"]), 3540.0)
        self.assertEqual(row["status"], "paired_usable")

    def test_retrospective_mask_is_flagged(self):
        dataset = pairing.build_paired_dataset(
            self._zarc(), self._municipal(), self._aoi(), self._pam()
        )
        soja = [r for r in dataset if r["crop"] == "soja" and r["mask_variant"] == "stable"][0]
        self.assertTrue(soja["mask_retrospective"])
        self.assertEqual(soja["quality_flag"], "paired_with_retrospective_mask")

    def test_effective_sample_is_years_not_combinations(self):
        dataset = pairing.build_paired_dataset(
            self._zarc(), self._municipal(), self._aoi(), self._pam()
        )
        soja = [r for r in dataset if r["crop"] == "soja"]
        # uma linha por (safra, variante) — não uma por combinação ZARC
        self.assertEqual(len({r["mask_variant"] for r in soja}), len(soja))

    def test_missing_yield_is_excluded_not_dropped(self):
        dataset = pairing.build_paired_dataset(
            self._zarc(), self._municipal(), self._aoi(), []
        )
        soja = [r for r in dataset if r["crop"] == "soja"]
        self.assertTrue(soja)
        self.assertEqual(soja[0]["status"], "excluded")
        self.assertIn("rendimento", soja[0]["exclusion_reason"])


class StatisticsTest(unittest.TestCase):
    def test_correlations(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        self.assertAlmostEqual(reeval.pearson(x, y), 1.0, places=9)
        self.assertAlmostEqual(reeval.spearman(x, y), 1.0, places=9)

    def test_permutation_is_deterministic(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.1, 5.9, 8.2, 9.8]
        first = reeval.permutation_p(x, y, permutations=200, seed=7)
        second = reeval.permutation_p(x, y, permutations=200, seed=7)
        self.assertEqual(first, second)
        self.assertTrue(0.0 < first <= 1.0)

    def test_holm_correction_is_monotone_in_p(self):
        corrected = reeval.holm_correction({"a": 0.01, "b": 0.04, "c": 0.20})
        # Holm: multiplicadores decrescentes na ordem crescente de p
        self.assertLessEqual(corrected["a"], corrected["b"])
        self.assertLessEqual(corrected["b"], corrected["c"])
        for key, original in (("a", 0.01), ("b", 0.04), ("c", 0.20)):
            self.assertGreaterEqual(corrected[key], original)
            self.assertLessEqual(corrected[key], 1.0)

    def test_bootstrap_ci_brackets_point_estimate(self):
        rng = np.random.default_rng(3)
        x = list(rng.normal(size=9))
        y = [2 * v + 1 for v in x]
        low, high = reeval.bootstrap_ci(x, y, iterations=300)
        estimate = reeval.pearson(x, y)
        self.assertLessEqual(low, estimate)
        self.assertGreaterEqual(high, estimate)

    def test_walk_forward_has_no_leakage(self):
        rows = [
            {
                "pam_reference_year": 2015 + i,
                "ndvi_municipal_mean": 0.3 + 0.02 * i,
                "yield_kg_ha": 3000 + 50 * i,
            }
            for i in range(8)
        ]
        result = reeval.walk_forward(rows, "ndvi_municipal_mean", min_train=4)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["models"]["media_historica"]["n_predictions"], 4)
        # as previsões começam apenas depois do mínimo de treino
        self.assertEqual(
            result["models"]["media_historica"]["years"], [2019, 2020, 2021, 2022]
        )
        # o erro médio histórico é calculado só com o passado
        for row in result["predictions"]["media_historica"]:
            self.assertLess(row["year"], 2023)

    def test_walk_forward_requires_enough_pairs(self):
        result = reeval.walk_forward(
            [{"pam_reference_year": 2020, "ndvi_municipal_mean": 0.4, "yield_kg_ha": 3000}],
            "ndvi_municipal_mean",
            min_train=5,
        )
        self.assertEqual(result["status"], "insufficient_pairs")


class MaskVariantTest(unittest.TestCase):
    def test_variants(self):
        wc20 = np.array([[40, 30], [40, 10]], dtype="uint8")
        wc21 = np.array([[40, 40], [30, 10]], dtype="uint8")
        variants = mser.mask_variants(wc20, wc21)
        self.assertEqual(int(variants["wc2020"].sum()), 2)
        self.assertEqual(int(variants["wc2021"].sum()), 2)
        self.assertEqual(int(variants["stable"].sum()), 1)   # interseção
        self.assertEqual(int(variants["broad"].sum()), 3)    # união

    def test_load_completed_detects_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "series.csv")
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=mser.MONTHLY_FIELDS, extrasaction="ignore"
                )
                writer.writeheader()
                writer.writerow({"month": "2019-10", "mask_variant": "stable"})
            done = mser.load_completed(path)
        self.assertIn(("2019-10", "stable"), done)
        self.assertNotIn(("2019-10", "broad"), done)


if __name__ == "__main__":
    unittest.main()
