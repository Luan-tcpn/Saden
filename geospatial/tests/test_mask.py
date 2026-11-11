"""Testes dos perfis de máscara SCL (dados sintéticos, sem rede)."""

from __future__ import annotations

import unittest

import numpy as np

from s2_poc import config
from s2_poc import mask as mask_mod


ALL_CLASSES = np.array([[c for c in range(12)]], dtype="uint8")


class ProfileTest(unittest.TestCase):
    def test_profile_a_matches_historical_rule(self):
        keep = mask_mod.keep_mask(ALL_CLASSES, "A_historical")
        kept = set(ALL_CLASSES[keep].tolist())
        self.assertEqual(kept, {2, 4, 5, 6})

    def test_profile_b_additionally_drops_classes_2_and_6(self):
        keep = mask_mod.keep_mask(ALL_CLASSES, "B_restrictive")
        kept = set(ALL_CLASSES[keep].tolist())
        self.assertEqual(kept, {4, 5})

    def test_profiles_are_declared_in_config(self):
        self.assertEqual(
            set(config.SCL_PROFILES["A_historical"]), {0, 1, 3, 7, 8, 9, 10, 11}
        )
        self.assertEqual(
            set(config.SCL_PROFILES["B_restrictive"]), {0, 1, 2, 3, 6, 7, 8, 9, 10, 11}
        )

    def test_v2_1_default_profile_is_the_restrictive_one(self):
        # decisão D43: Perfil B é o padrão da V2.1; o Perfil A fica na PoC
        self.assertEqual(config.V2_1_SCL_PROFILE, "B_restrictive")
        self.assertEqual(
            set(mask_mod.profile_classes(config.V2_1_SCL_PROFILE)),
            {0, 1, 2, 3, 6, 7, 8, 9, 10, 11},
        )

    def test_unknown_profile_raises(self):
        with self.assertRaises(ValueError):
            mask_mod.profile_classes("Z")

    def test_unknown_codes_are_flagged_but_not_removed(self):
        scl = np.array([[99, 4]], dtype="uint8")
        self.assertTrue(mask_mod.unknown_mask(scl)[0, 0])
        self.assertFalse(mask_mod.unknown_mask(scl)[0, 1])
        # comportamento histórico preservado: código fora 0..11 permanece válido
        self.assertTrue(mask_mod.keep_mask(scl, "A_historical")[0, 0])


class CountsTest(unittest.TestCase):
    def setUp(self):
        self.scl = np.array(
            [[4, 4, 5, 5], [6, 2, 9, 0], [3, 7, 8, 10]], dtype="uint8"
        )

    def test_counts_sum_to_total(self):
        counts = mask_mod.class_counts(self.scl)
        total = sum(c["pixels"] for c in counts["classes"])
        self.assertEqual(total, self.scl.size)
        self.assertEqual(counts["unknown_pixels"], 0)

    def test_fraction_and_flags(self):
        counts = mask_mod.class_counts(self.scl)
        by_class = {c["class"]: c for c in counts["classes"]}
        self.assertEqual(by_class[4]["pixels"], 2)
        self.assertAlmostEqual(by_class[4]["fraction"], 2 / 12, places=10)
        self.assertTrue(by_class[4]["kept_by_A"])
        self.assertTrue(by_class[4]["kept_by_B"])
        # classe 2 (dark area) e 6 (água): mantidas pelo perfil A, removidas pelo B
        self.assertTrue(by_class[2]["kept_by_A"])
        self.assertFalse(by_class[2]["kept_by_B"])
        self.assertTrue(by_class[6]["kept_by_A"])
        self.assertFalse(by_class[6]["kept_by_B"])
        self.assertFalse(by_class[9]["kept_by_A"])
        self.assertFalse(by_class[9]["kept_by_B"])

    def test_counts_with_explicit_valid_mask(self):
        keep = mask_mod.keep_mask(self.scl, "B_restrictive")
        counts = mask_mod.class_counts(self.scl, keep)
        self.assertEqual(sum(c["pixels"] for c in counts["classes"]), int(keep.sum()))


class ComparisonTest(unittest.TestCase):
    def test_transitions_are_counted(self):
        scl = np.array([[4, 6, 9, 4], [2, 5, 4, 0]], dtype="uint8")
        result = mask_mod.compare_profiles(scl)
        a, b = result["profiles"]
        # perfil A mantém 4, 6, 2, 5, 4, 4 (exclui 9 e 0)
        self.assertEqual(a["valid_pixels"], 6)
        # perfil B mantém apenas 4, 5, 4, 4
        self.assertEqual(b["valid_pixels"], 4)
        transitions = result["transitions"]
        self.assertEqual(transitions["pair"], ["A_historical", "B_restrictive"])
        self.assertEqual(transitions["changed_pixels"], 2)
        self.assertEqual(transitions["first_valid_second_invalid"], 2)
        self.assertEqual(transitions["first_invalid_second_valid"], 0)

    def test_fraction_is_consistent(self):
        scl = np.array([[4, 6, 9, 4], [2, 5, 4, 0]], dtype="uint8")
        result = mask_mod.compare_profiles(scl)
        for profile in result["profiles"]:
            self.assertAlmostEqual(
                profile["valid_fraction"],
                profile["valid_pixels"] / scl.size,
                places=10,
            )


class MaskingTest(unittest.TestCase):
    def test_masked_index_replaces_invalid_with_nan(self):
        values = np.array([0.1, 0.2, 0.3], dtype="float32")
        keep = np.array([True, False, True])
        out = mask_mod.masked_index(values, keep)
        self.assertTrue(np.isfinite(out[0]))
        self.assertTrue(np.isnan(out[1]))
        self.assertTrue(np.isfinite(out[2]))
        self.assertEqual(out.dtype, np.float32)

    def test_class_index_stats_separate_classes(self):
        scl = np.array([[4, 4], [6, 6]], dtype="uint8")
        values = np.array([[0.5, 0.7], [-0.4, -0.2]], dtype="float32")
        stats = mask_mod.class_index_stats(scl, {"NDVI": values})
        entries = {e["class"]: e for e in stats["NDVI"]}
        self.assertEqual(entries[4]["valid_pixels"], 2)
        self.assertAlmostEqual(entries[4]["mean"], 0.6, places=6)
        self.assertEqual(entries[6]["valid_pixels"], 2)
        self.assertAlmostEqual(entries[6]["mean"], -0.3, places=6)


if __name__ == "__main__":
    unittest.main()
