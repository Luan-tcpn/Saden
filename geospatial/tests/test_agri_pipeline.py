"""Testes da normalização e da validação da base de produtividade — offline."""

from __future__ import annotations

import csv
import os
import tempfile
import unittest

from agri import normalize, validate


def _sidra_record(product_code="40124", product_name="Soja (em grão)", value="2244375",
                  variable="214", unit="Toneladas", year="2023", status=None):
    record = {
        "level_code": "6",
        "level_name": "Município",
        "unit_code": "1017",
        "unit_name": unit,
        "value_raw": value,
        "value": float(value) if value.replace(".", "").isdigit() else None,
        "value_status": status or "observed",
        "locality_code": "5107925",
        "locality_name": "Sorriso (MT)",
        "variable_code": variable,
        "variable_name": {
            "214": "Quantidade produzida",
            "216": "Área colhida",
            "8331": "Área plantada ou destinada à colheita",
            "112": "Rendimento médio da produção",
        }.get(variable, variable),
        "period_code": year,
        "period_name": year,
        "product_code": product_code,
        "product_name": product_name,
    }
    return record


class IbgeNormalizationTest(unittest.TestCase):
    def test_records_keep_original_and_normalized_values(self):
        payload = {
            "url": "https://apisidra.ibge.gov.br/values/t/5457/n6/5107925/v/214/p/2023/c782/all",
            "acquired_at": "2026-11-11T00:00:00+00:00",
            "records": [
                _sidra_record(),
                _sidra_record(variable="216", value="598500", unit="Hectares"),
                _sidra_record(variable="112", value="3750", unit="Quilogramas por Hectare"),
            ],
        }
        records = normalize.build_ibge_records(payload, payload["url"])
        self.assertEqual(len(records), 3)
        soja = records[0]
        self.assertEqual(soja["institution"], "IBGE")
        self.assertEqual(soja["geography_type"], "municipio")
        self.assertEqual(soja["reference_year"], "2023")
        self.assertEqual(soja["value_original"], "2244375")
        self.assertEqual(soja["value_normalized"], 2244375.0)
        self.assertEqual(soja["unit_original"], "Toneladas")
        self.assertEqual(soja["unit_normalized"], "t")
        self.assertEqual(soja["nature"], normalize.NATURE_OBSERVED)
        self.assertEqual(soja["crop_name_normalized"], "Soja")
        self.assertEqual(soja["crop_scope"], "produto")

    def test_products_outside_saden_are_marked_without_match(self):
        payload = {
            "url": "u",
            "records": [_sidra_record(product_code="99999", product_name="Banana")],
        }
        records = normalize.build_ibge_records(payload, "u")
        self.assertEqual(records[0]["match_class"], "none")
        self.assertIsNone(records[0]["crop_name_normalized"])


class ConabNormalizationTest(unittest.TestCase):
    def test_units_are_converted_and_originals_preserved(self):
        parsed = [
            {
                "uf": "MT",
                "product_original": "SOJA",
                "product_scope": "produto",
                "period_kind": "safra",
                "period_label": "24/25",
                "area_mil_ha": 12738.7,
                "produtividade_kg_ha": 4028.0,
                "producao_mil_t": 51311.5,
            }
        ]
        records = normalize.build_conab_records(parsed, {"name": "b.xlsx"}, "https://conab")
        self.assertEqual(len(records), 3)
        area = next(r for r in records if r["variable_normalized"] == "area_plantada_ha")
        self.assertAlmostEqual(area["value_original"], 12738.7)
        self.assertAlmostEqual(area["value_normalized"], 12738700.0)
        self.assertEqual(area["unit_original"], "mil ha")
        self.assertEqual(area["unit_normalized"], "ha")
        self.assertEqual(area["safra"], "24/25")
        self.assertIsNone(area["reference_year"])
        self.assertEqual(area["nature"], normalize.NATURE_ESTIMATED)
        self.assertEqual(area["geography_code"], "51")

    def test_civil_year_block_uses_reference_year(self):
        parsed = [
            {
                "uf": "MT",
                "product_original": "TRIGO",
                "product_scope": "produto",
                "period_kind": "ano_civil",
                "period_label": "2025",
                "area_mil_ha": 0.0,
                "produtividade_kg_ha": 0.0,
                "producao_mil_t": 0.0,
            }
        ]
        records = normalize.build_conab_records(parsed, {"name": "b.xlsx"}, "u")
        self.assertEqual(records[0]["reference_year"], "2025")
        self.assertIsNone(records[0]["safra"])


class ScopeTest(unittest.TestCase):
    def test_scope_classification(self):
        self.assertEqual(normalize.classify_scope("MILHO TOTAL"), "total")
        self.assertEqual(normalize.classify_scope("FEIJÃO 1ª SAFRA"), "grupo_safra")
        self.assertEqual(normalize.classify_scope("Soja (em grão)"), "produto")


class ConversionTest(unittest.TestCase):
    def test_computed_yield(self):
        self.assertAlmostEqual(normalize.computed_yield_t_ha(3750.0, 600.0), 6.25)
        self.assertIsNone(normalize.computed_yield_t_ha(3750.0, 0))
        self.assertIsNone(normalize.computed_yield_t_ha(None, 100))

    def test_published_yield_conversion(self):
        self.assertAlmostEqual(normalize.published_yield_kg_ha_to_t_ha(3750.0), 3.75)
        self.assertIsNone(normalize.published_yield_kg_ha_to_t_ha(None))


class CsvRoundTripTest(unittest.TestCase):
    def test_write_and_read_preserves_values(self):
        record = normalize._empty_row()
        record.update(
            {
                "institution": "IBGE",
                "crop_name_original": "Soja (em grão)",
                "variable_normalized": "quantidade_produzida_t",
                "value_original": "2244375",
                "value_normalized": 2244375.0,
                "unit_normalized": "t",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "base.csv")
            normalize.write_csv([record], path)
            rows = normalize.read_csv(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["crop_name_original"], "Soja (em grão)")
        self.assertEqual(rows[0]["value_original"], "2244375")
        self.assertEqual(rows[0]["value_normalized"], "2244375.0")
        self.assertEqual(list(rows[0].keys()), normalize.NORMALIZED_FIELDS)


class ValidationTest(unittest.TestCase):
    def _record(self, **kwargs):
        record = normalize._empty_row()
        record.update(
            {
                "institution": "IBGE",
                "dataset_id": "SIDRA:5457",
                "geography_code": "5107925",
                "geography_type": "municipio",
                "crop_code": "40124",
                "crop_name_original": "Soja (em grão)",
                "crop_scope": "produto",
                "match_class": "exact",
                "variable_normalized": "quantidade_produzida_t",
                "unit_normalized": "t",
                "reference_year": "2023",
                "value_normalized": 2244375.0,
                "observation_status": "observed",
            }
        )
        record.update(kwargs)
        return record

    def test_duplicates_are_detected(self):
        findings = validate.check_duplicates([self._record(), self._record()])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["check"], "duplicidade")

    def test_invalid_municipal_code_is_error(self):
        findings = validate.check_geography([self._record(geography_code="9999999")])
        self.assertTrue(any(f["severity"] == "error" for f in findings))

    def test_unit_inconsistency_is_error(self):
        findings = validate.check_units([self._record(unit_normalized="kg")])
        self.assertEqual(findings[0]["check"], "unidade_inconsistente")
        self.assertEqual(findings[0]["severity"], "error")

    def test_area_zero_with_production_is_error(self):
        records = [
            self._record(variable_normalized="area_colhida_ha", value_normalized=0.0,
                         unit_normalized="ha"),
            self._record(variable_normalized="quantidade_produzida_t"),
        ]
        findings = validate.check_area_production_consistency(records)
        self.assertEqual(findings[0]["check"], "area_zero_com_producao")

    def test_yield_divergence_is_warning(self):
        records = [
            self._record(variable_normalized="quantidade_produzida_t", value_normalized=1_000_000.0),
            self._record(variable_normalized="area_colhida_ha", value_normalized=100_000.0,
                         unit_normalized="ha"),
            self._record(variable_normalized="rendimento_medio_kg_ha", value_normalized=3000.0,
                         unit_normalized="kg/ha"),
        ]
        findings = validate.check_yield_consistency(records)
        self.assertEqual(findings[0]["check"], "rendimento_divergente")
        self.assertGreater(findings[0]["relative_difference"], 0.05)

    def test_consistent_yield_is_not_flagged(self):
        records = [
            self._record(variable_normalized="quantidade_produzida_t", value_normalized=375_000.0),
            self._record(variable_normalized="area_colhida_ha", value_normalized=100_000.0,
                         unit_normalized="ha"),
            self._record(variable_normalized="rendimento_medio_kg_ha", value_normalized=3750.0,
                         unit_normalized="kg/ha"),
        ]
        self.assertEqual(validate.check_yield_consistency(records), [])

    def test_negative_values_are_flagged(self):
        findings = validate.check_plausibility(
            [self._record(value_normalized=-5.0)]
        )
        self.assertEqual(findings[0]["check"], "produtividade_negativa")

    def test_revision_between_bulletins_is_detected(self):
        records = [
            self._record(institution="CONAB", dataset_id="a.xlsx", geography_code="51",
                         geography_type="uf", crop_code=None, reference_year=None,
                         safra="24/25", value_normalized=4049700.0),
            self._record(institution="CONAB", dataset_id="b.xlsx", geography_code="51",
                         geography_type="uf", crop_code=None, reference_year=None,
                         safra="24/25", value_normalized=4070500.0),
        ]
        findings = validate.check_revisions_between_bulletins(records)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["check"], "revisao_entre_boletins")

    def test_aggregate_and_component_are_flagged(self):
        records = [
            self._record(institution="CONAB", crop_scope="total", crop_name_normalized="Milho"),
            self._record(institution="CONAB", crop_scope="grupo_safra", crop_name_normalized="Milho"),
        ]
        findings = validate.check_aggregate_double_counting(records)
        self.assertEqual(findings[0]["check"], "dupla_contagem_agregado_componente")

    def test_run_all_keeps_every_record(self):
        records = [self._record(), self._record(value_normalized=None)]
        report = validate.run_all(records)
        self.assertEqual(report["records_checked"], 2)
        self.assertTrue(any(f["check"] == "valor_nulo" for f in report["findings"]))
        self.assertIn("Nenhum registro foi removido", report["policy"])


if __name__ == "__main__":
    unittest.main()
