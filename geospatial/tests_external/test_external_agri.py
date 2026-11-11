"""Testes EXTERNOS da V2.2 (rede). Opt-in por SADEN_EXTERNAL_TESTS=1.

Verificam acesso **real** às fontes oficiais (IBGE/SIDRA e CONAB). Não fazem
parte da suíte offline.

    $env:SADEN_EXTERNAL_TESTS = "1"
    geospatial\\.venv\\Scripts\\python.exe -m unittest discover -s geospatial\\tests_external -t geospatial
"""

from __future__ import annotations

import os
import unittest

from agri import config, conab, crosswalk, sidra

ENABLED = os.environ.get("SADEN_EXTERNAL_TESTS") == "1"
SKIP_REASON = (
    "teste externo: defina SADEN_EXTERNAL_TESTS=1 para executar (requer internet)"
)


@unittest.skipUnless(ENABLED, SKIP_REASON)
class IbgeLiveTest(unittest.TestCase):
    def test_municipality_is_confirmed_official(self):
        data = sidra.fetch_municipality_metadata("5107925")
        self.assertEqual(data["nome"], "Sorriso")
        self.assertEqual(str(data["id"]), "5107925")
        imediata = data["regiao-imediata"]
        self.assertEqual(imediata["nome"], "Sorriso")
        intermediaria = imediata["regiao-intermediaria"]
        self.assertEqual(intermediaria["nome"], "Sinop")
        uf = intermediaria["UF"]
        self.assertEqual(uf["sigla"], "MT")
        self.assertEqual(uf["nome"], "Mato Grosso")

    def test_pam_returns_real_records_for_the_municipality(self):
        result = sidra.fetch_pam(years=[2024, 2025])
        self.assertGreater(len(result["records"]), 100)
        records = result["records"]
        soja = [
            r
            for r in records
            if r["product_code"] == "40124" and r["variable_code"] == "214"
        ]
        self.assertTrue(soja, "SOJA (40124) deve existir para Sorriso")
        values = [r["value"] for r in soja if r["value"] is not None]
        self.assertTrue(values)
        self.assertTrue(all(v > 0 for v in values))

    def test_aggregate_metadata_documents_variables(self):
        metadata = sidra.fetch_aggregate_metadata()
        codes = {str(v["id"]) for v in metadata["variaveis"]}
        self.assertTrue({"214", "216", "112", "8331"} <= codes)
        self.assertEqual(metadata["pesquisa"], "Produção Agrícola Municipal")


@unittest.skipUnless(ENABLED, SKIP_REASON)
class ConabLiveTest(unittest.TestCase):
    def test_bulletin_spreadsheets_are_listed(self):
        files = conab.list_spreadsheets(config.CONAB_GRAINS_INDEX)
        self.assertGreater(len(files), 3)
        self.assertTrue(any("levantamento" in f["name"] or f["url"] for f in files))

    def test_bulletin_has_state_level_sheets(self):
        files = conab.list_spreadsheets(config.CONAB_GRAINS_INDEX)
        target = files[0]
        import os as _os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = _os.path.join(tmp, target["name"])
            conab.download(target["url"], path)
            names = conab.sheet_names(path)
            self.assertIn("MT", names)
            records = conab.parse_state_sheet(path, "MT")
            self.assertTrue(records)
            self.assertTrue(any(r["product_original"] == "SOJA" for r in records))


@unittest.skipUnless(ENABLED, SKIP_REASON)
class CrosswalkLiveTest(unittest.TestCase):
    def test_ibge_product_names_match_the_declared_crosswalk(self):
        result = sidra.fetch_pam(years=[2025])
        names = {
            str(r["product_code"]): r["product_name"]
            for r in result["records"]
            if r["product_code"]
        }
        for code, entry in crosswalk.IBGE_TO_SADEN.items():
            if code in names:
                self.assertEqual(names[code], entry["ibge_name"])


if __name__ == "__main__":
    unittest.main()
