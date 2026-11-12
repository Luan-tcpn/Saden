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
    """Regra oficial do MAPA: três decêndios por mês (1-10, 11-20, 21-fim)."""

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

    def test_all_36_decends_are_covered(self):
        """Os 36 decêndios do ano cobrem exatamente os 12 meses."""
        seen = set()
        for decend in range(1, 37):
            seen.add(season.decend_month(decend))
        self.assertEqual(seen, set(range(1, 13)))


class RiskLabelTest(unittest.TestCase):
    """O campo ``decendios_com_risco`` guarda rótulos textuais de risco."""

    def test_parse_textual_risk_labels(self):
        self.assertEqual(season.parse_risk_label("baixo"), 20)
        self.assertEqual(season.parse_risk_label("medio"), 30)
        self.assertEqual(season.parse_risk_label("alto"), 40)
        self.assertEqual(season.parse_risk_label("muito_baixo"), 10)
        self.assertIsNone(season.parse_risk_label(""))

    def test_recommended_decends_use_official_threshold(self):
        text = "26:alto;27:medio;28:baixo;29:baixo;30:baixo"
        self.assertEqual(season.recommended_decends(text, max_risk=20), [28, 29, 30])
        self.assertEqual(
            season.recommended_decends(text, max_risk=30), [27, 28, 29, 30]
        )
        self.assertEqual(
            season.recommended_decends(text, max_risk=40), [26, 27, 28, 29, 30]
        )


class DecendYearAnchorTest(unittest.TestCase):
    """Âncora de ano dos decêndios dentro da safra (correção V2.5)."""

    def test_first_and_second_year_split(self):
        self.assertEqual(season.decend_year(1, 2019, 2020), 2020)
        self.assertEqual(season.decend_year(12, 2019, 2020), 2020)
        self.assertEqual(season.decend_year(13, 2019, 2020), 2019)
        self.assertEqual(season.decend_year(36, 2019, 2020), 2019)

    def test_portaria_precedes_window(self):
        """A portaria que publica a recomendação precede a janela."""
        # Milho 2ª Safra da safra 2016/17: portaria de 09-12-2016 e janela
        # recomendada em janeiro-fevereiro (deve ser de 2017, não de 2016).
        self.assertEqual(season.decend_year(1, 2016, 2017), 2017)
        start, _ = season.decend_to_dates(season.decend_year(1, 2016, 2017), 1)
        self.assertEqual(start, "2017-01-01")
        self.assertGreater(start, "2016-12-09")


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
                "decendios_com_risco": (
                    "29:baixo;30:baixo;31:baixo;32:baixo;"
                    "33:baixo;34:baixo;35:baixo;36:baixo"
                ),
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
                "decendios_com_risco": (
                    "29:baixo;30:baixo;31:baixo;32:baixo;"
                    "33:baixo;34:baixo;35:baixo;36:baixo"
                ),
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
                "decendios_com_risco": "1:baixo;2:baixo;3:baixo;4:baixo;5:baixo",
            },
        ]

    def test_build_windows_preserves_combinations(self):
        windows = season.build_windows(self._rows(), "soja")
        self.assertEqual(len(windows), 2)  # duas combinações de solo/ciclo
        for window in windows:
            self.assertEqual(window["months"], ["2019-10", "2019-11", "2019-12"])
            self.assertTrue(window["start_date"].startswith("2019-10"))
            self.assertTrue(window["end_date"].startswith("2019-12"))

    def test_second_saison_window_is_january_february_of_second_year(self):
        windows = season.build_windows(self._rows(), "milho_2")
        self.assertEqual(len(windows), 1)
        # 2ª safra da safra 2019/20 é plantada em jan-fev de 2020
        self.assertEqual(windows[0]["months"], ["2020-01", "2020-02"])
        self.assertTrue(windows[0]["start_date"].startswith("2020-01"))

    def test_consensus_window_takes_modal_combination(self):
        windows = season.build_windows(self._rows(), "soja")
        window = pairing.consensus_window(windows, "2019/20")
        self.assertIsNotNone(window)
        self.assertEqual(window["months"], ["2019-10", "2019-11", "2019-12"])
        self.assertEqual(window["official_combinations"], 2)


class PairingTest(unittest.TestCase):
    def _zarc(self):
        return [
            {
                "safra": "2019/20", "safra_ini": "2019", "safra_fin": "2020",
                "cultura": "Soja", "cod_ciclo": "20", "cod_solo": "1",
                "cod_clima": "", "portaria": "port.63",
                "decendios_com_risco": "29:baixo;30:baixo;31:baixo",
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
            {"month": "2019-01", "status": "observed", "ndvi_mean": "0.50",
             "valid_fraction": "0.98"},
            {"month": "2019-02", "status": "observed", "ndvi_mean": "0.51",
             "valid_fraction": "0.98"},
            {"month": "2019-10", "status": "observed", "ndvi_mean": "0.52",
             "valid_fraction": "0.98"},
            {"month": "2019-11", "status": "observed", "ndvi_mean": "0.53",
             "valid_fraction": "0.98"},
            {"month": "2020-01", "status": "observed", "ndvi_mean": "0.54",
             "valid_fraction": "0.99"},
            {"month": "2020-10", "status": "observed", "ndvi_mean": "0.55",
             "valid_fraction": "0.99"},
            {"month": "2020-11", "status": "observed", "ndvi_mean": "0.56",
             "valid_fraction": "0.99"},
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
        soja = [
            r for r in dataset if r["crop"] == "soja" and r["mask_variant"] == "stable"
        ][0]
        self.assertTrue(soja["mask_retrospective"])
        self.assertEqual(soja["quality_flag"], "paired_with_retrospective_mask")

    def test_effective_sample_is_years_not_combinations(self):
        dataset = pairing.build_paired_dataset(
            self._zarc(), self._municipal(), self._aoi(), self._pam()
        )
        soja = [
            r for r in dataset
            if r["crop"] == "soja" and r["pairing_mode"] == "zarc_sazonal"
        ]
        # uma linha por (safra, variante) — não uma por combinação ZARC
        self.assertEqual(len({r["mask_variant"] for r in soja}), len(soja))
        self.assertEqual(len({r["pam_reference_year"] for r in soja}), 1)

    def test_missing_yield_is_excluded_not_dropped(self):
        dataset = pairing.build_paired_dataset(
            self._zarc(), self._municipal(), self._aoi(), []
        )
        soja = [
            r for r in dataset
            if r["crop"] == "soja" and r["pairing_mode"] == "zarc_sazonal"
        ]
        self.assertTrue(soja)
        self.assertEqual(soja[0]["status"], "excluded")
        self.assertIn("rendimento", soja[0]["exclusion_reason"])

    def test_window_uses_absolute_months(self):
        dataset = pairing.build_paired_dataset(
            self._zarc(), self._municipal(), self._aoi(), self._pam()
        )
        soja = [
            r for r in dataset
            if r["crop"] == "soja" and r["pairing_mode"] == "zarc_sazonal"
        ][0]
        self.assertEqual(soja["window_months"], "2019-10;2019-11")

    def test_civil_year_slice_reproduces_v23_rule(self):
        """A fatia de ano civil cobre todos os anos com rendimento da PAM."""
        dataset = pairing.build_paired_dataset(
            self._zarc(), self._municipal(), self._aoi(), self._pam()
        )
        civil = [r for r in dataset if r["pairing_mode"] == "ano_civil_v23"]
        self.assertTrue(civil)
        self.assertEqual({r["pam_reference_year"] for r in civil}, {2020})
        # na fatia civil o indicador da AOI vem da série da AOI
        row = [r for r in civil if r["crop"] == "soja"][0]
        self.assertIsNotNone(row["ndvi_aoi_mean"])


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
        crop20 = np.array([[True, False], [True, False]])
        crop21 = np.array([[True, True], [False, False]])
        variants = mser.mask_variants(crop20, crop21)
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
