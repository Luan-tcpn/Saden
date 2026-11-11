"""Testes das fontes oficiais (SIDRA/CONAB) e do crosswalk — offline."""

from __future__ import annotations

import os
import tempfile
import unittest

from agri import config, conab, crosswalk, sidra


class SidraValueTest(unittest.TestCase):
    def test_numeric_value(self):
        value, status = sidra.parse_value("2244375")
        self.assertAlmostEqual(value, 2244375.0)
        self.assertEqual(status, "observed")

    def test_missing_and_nil_conventions(self):
        self.assertEqual(sidra.parse_value(".."), (None, "missing"))
        self.assertEqual(sidra.parse_value("-"), (0.0, "zero"))
        self.assertEqual(sidra.parse_value("..."), (None, "not_applicable"))
        self.assertEqual(sidra.parse_value("x"), (None, "suppressed"))
        self.assertEqual(sidra.parse_value(""), (None, "missing"))
        self.assertEqual(sidra.parse_value(None), (None, "missing"))

    def test_comma_decimal_is_parsed(self):
        value, status = sidra.parse_value("1234,56")
        self.assertAlmostEqual(value, 1234.56)
        self.assertEqual(status, "observed")


class SidraUrlTest(unittest.TestCase):
    def test_url_shape(self):
        url = sidra.build_values_url(
            localities="5107925", variables="214,216", periods="2023,2024"
        )
        self.assertEqual(
            url,
            "https://apisidra.ibge.gov.br/values/t/5457/n6/5107925/v/214,216"
            "/p/2023,2024/c782/all",
        )

    def test_classification_can_be_omitted(self):
        url = sidra.build_values_url(classification=None)
        self.assertNotIn("/c782", url)


class SidraParsingTest(unittest.TestCase):
    def _payload(self):
        return {
            "header": {
                "NC": "Nível Territorial",
                "V": "Valor",
                "D1C": "Município (Código)",
                "D1N": "Município",
                "D2C": "Variável (Código)",
                "D2N": "Variável",
                "D3C": "Ano (Código)",
                "D3N": "Ano",
                "D4C": "Produto (Código)",
                "D4N": "Produto",
                "MN": "Unidade de Medida",
                "MC": "Unidade (Código)",
            },
            "rows": [
                {
                    "NC": "6",
                    "NN": "Município",
                    "MC": "1017",
                    "MN": "Toneladas",
                    "V": "2244375",
                    "D1C": "5107925",
                    "D1N": "Sorriso (MT)",
                    "D2C": "214",
                    "D2N": "Quantidade produzida",
                    "D3C": "2023",
                    "D3N": "2023",
                    "D4C": "40124",
                    "D4N": "Soja (em grão)",
                },
                {
                    "NC": "6",
                    "NN": "Município",
                    "MC": "1017",
                    "MN": "Toneladas",
                    "V": "-",
                    "D1C": "5107925",
                    "D1N": "Sorriso (MT)",
                    "D2C": "214",
                    "D2N": "Quantidade produzida",
                    "D3C": "2023",
                    "D3N": "2023",
                    "D4C": "40140",
                    "D4N": "Café (em grão) Arábica",
                },
            ],
            "status": 200,
            "url": "https://apisidra.ibge.gov.br/values/t/5457/n6/5107925/v/214/p/2023/c782/all",
        }

    def test_rows_to_records(self):
        records = sidra.rows_to_records(self._payload())
        self.assertEqual(len(records), 2)
        first = records[0]
        self.assertEqual(first["value"], 2244375.0)
        self.assertEqual(first["value_status"], "observed")
        self.assertEqual(first["product_code"], "40124")
        self.assertEqual(first["product_name"], "Soja (em grão)")
        self.assertEqual(first["unit_name"], "Toneladas")
        self.assertEqual(records[1]["value"], 0.0)
        self.assertEqual(records[1]["value_status"], "zero")

    def test_list_format_is_supported(self):
        payload = self._payload()
        list_payload = [payload["header"]] + payload["rows"]
        result = {"header": list_payload[0], "rows": list_payload[1:]}
        records = sidra.rows_to_records(result)
        self.assertEqual(len(records), 2)


class CrosswalkTest(unittest.TestCase):
    def test_ibge_products_are_matched_by_official_code(self):
        soja = crosswalk.classify_ibge_product("40124", "Soja (em grão)")
        self.assertEqual(soja["saden_key"], "soja")
        self.assertEqual(soja["match"], crosswalk.MATCH_EXACT)

        cafe = crosswalk.classify_ibge_product("40140", "Café (em grão) Arábica")
        self.assertEqual(cafe["saden_key"], "cafe")
        self.assertEqual(cafe["match"], crosswalk.MATCH_EQUIVALENT)

        algodao = crosswalk.classify_ibge_product("40099", "Algodão herbáceo (em caroço)")
        self.assertEqual(algodao["saden_key"], "algodao")
        self.assertEqual(algodao["match"], crosswalk.MATCH_PARTIAL)

    def test_unknown_ibge_product_has_no_match(self):
        result = crosswalk.classify_ibge_product("99999", "Produto qualquer")
        self.assertEqual(result["match"], crosswalk.MATCH_NONE)
        self.assertIsNone(result["saden_key"])

    def test_conab_labels(self):
        self.assertEqual(
            crosswalk.classify_conab_product("SOJA")["saden_key"], "soja"
        )
        self.assertEqual(
            crosswalk.classify_conab_product("MILHO TOTAL")["saden_key"], "milho"
        )
        pluma = crosswalk.classify_conab_product("ALGODÃO - PLUMA")
        self.assertEqual(pluma["saden_key"], "algodao")
        self.assertEqual(pluma["match"], crosswalk.MATCH_PARTIAL)
        self.assertEqual(
            crosswalk.classify_conab_product("FEIJÃO TOTAL")["match"],
            crosswalk.MATCH_NONE,
        )

    def test_crosswalk_covers_all_saden_commodities(self):
        table = crosswalk.crosswalk_table()
        self.assertEqual(len(table), len(config.SADEN_COMMODITIES))
        keys = {row["saden_key"] for row in table}
        self.assertEqual(keys, {c["key"] for c in config.SADEN_COMMODITIES})
        for row in table:
            self.assertIn(row["ibge_match"], {
                crosswalk.MATCH_EXACT,
                crosswalk.MATCH_EQUIVALENT,
                crosswalk.MATCH_PARTIAL,
                crosswalk.MATCH_NONE,
            })
            self.assertIn(row["conab_match"], {
                crosswalk.MATCH_EXACT,
                crosswalk.MATCH_EQUIVALENT,
                crosswalk.MATCH_PARTIAL,
                crosswalk.MATCH_NONE,
            })


class ConabParserTest(unittest.TestCase):
    """Parser da planilha da CONAB sobre um arquivo sintético equivalente."""

    def _workbook(self, path):
        import openpyxl

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "MT"
        rows = [
            ["PRODUTO", "ÁREA (Em mil ha)", None, None, "PRODUTIVIDADE (Em kg/ha)", None, None, "PRODUÇÃO (Em mil t)", None, None, None],
            [None, "Safra 24/25", "Safra 25/26", "VAR. %", "Safra 24/25", "Safra 25/26", "VAR. %", "Safra 24/25", "Safra 25/26", "VAR. %", None],
            [None, "(a)", "(b)", "(b/a)", "(c)", "(d)", "(d/c)", "(e)", "(f)", "(f/e)", None],
            ["SOJA", 12738.7, 13006.2, 2.1, 4028.0, 3969.0, -1.5, 51311.5, 51621.6, 0.6, None],
            ["FEIJÃO TOTAL", 164.2, 205.7, 25.3, 1844.0, 1669.0, -9.5, 302.7, 343.4, 13.4, None],
            ["FEIJÃO 1ª SAFRA", 10.4, 10.2, -1.9, 1626.0, 1646.0, 1.3, 16.9, 16.8, -0.6, None],
            ["Cores", 4.2, 4.0, -4.8, 2549.0, 2548.0, 0.0, 10.7, 10.2, -4.7, None],
            ["CULTURAS DE INVERNO", "ÁREA (Em mil ha)", None, None, "PRODUTIVIDADE (Em kg/ha)", None, None, "PRODUÇÃO (Em mil t)", None, None, None],
            [None, 2025, 2026, "VAR. %", 2025, 2026, "VAR. %", 2025, 2026, "VAR. %", None],
            [None, "(a)", "(b)", "(b/a)", "(c)", "(d)", "(d/c)", "(e)", "(f)", "(f/e)", None],
            ["TRIGO", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, None],
            ["Legenda: (1) Produção", None, None, None, None, None, None, None, None, None, None],
        ]
        for row in rows:
            sheet.append(row)
        workbook.save(path)
        return path

    def test_parse_state_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._workbook(os.path.join(tmp, "conab.xlsx"))
            records = conab.parse_state_sheet(path, "MT")
        by_label = {}
        for record in records:
            by_label.setdefault(record["product_original"], []).append(record)

        self.assertIn("SOJA", by_label)
        soja = by_label["SOJA"]
        self.assertEqual(len(soja), 2)
        self.assertEqual(soja[0]["safra"] if "safra" in soja[0] else soja[0]["period_label"], "24/25")
        self.assertEqual(soja[0]["period_kind"], "safra")
        self.assertAlmostEqual(soja[0]["area_mil_ha"], 12738.7)
        self.assertAlmostEqual(soja[0]["producao_mil_t"], 51311.5)

        # componente de feijão herda o rótulo do pai
        self.assertIn("FEIJÃO 1ª SAFRA - Cores", by_label)
        self.assertEqual(
            by_label["FEIJÃO 1ª SAFRA - Cores"][0]["product_scope"], "componente"
        )
        self.assertEqual(by_label["FEIJÃO TOTAL"][0]["product_scope"], "total")

        # bloco de culturas de inverno usa ano civil
        trigo = by_label["TRIGO"]
        self.assertEqual(trigo[0]["period_kind"], "ano_civil")
        self.assertEqual(trigo[0]["period_label"], "2025")

    def test_parse_returns_empty_for_missing_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._workbook(os.path.join(tmp, "conab.xlsx"))
            self.assertEqual(conab.parse_state_sheet(path, "NAO_EXISTE"), [])


if __name__ == "__main__":
    unittest.main()
