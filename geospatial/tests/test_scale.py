"""Testes da V2.4 — calendário ZARC, CONAB SUTIN e escala municipal (offline)."""

from __future__ import annotations

import csv
import io
import os
import tempfile
import unittest

import numpy as np

from agri import conab_sutin, zarc
from historical import landuse as lu
from historical import municipal as muni


class ZarcValueTest(unittest.TestCase):
    def test_decend_value_parsing(self):
        self.assertEqual(zarc._decend_value("20"), 20)
        self.assertEqual(zarc._decend_value("0"), 0)
        self.assertEqual(zarc._decend_value(""), 0)
        self.assertEqual(zarc._decend_value(None), 0)
        self.assertEqual(zarc._decend_value("x"), 0)

    def test_decend_to_dates(self):
        start, end = zarc._decend_to_dates(2019, 29)
        self.assertTrue(start.startswith("2019-10"))
        self.assertTrue(end.startswith("2019-10"))

    def test_risk_classes_are_documented(self):
        self.assertEqual(zarc.RISK_CLASSES[0], "fora_da_janela")
        self.assertEqual(zarc.RISK_CLASSES[10], "muito_baixo")
        self.assertEqual(zarc.RISK_CLASSES[40], "alto")
        self.assertEqual(set(zarc.RISK_RECOMMENDED), {10, 20})

    def test_safras_are_the_published_set(self):
        self.assertIn("2016/2017", zarc.SAFRAS)
        self.assertIn("2026/2027", zarc.SAFRAS)
        self.assertEqual(len(zarc.SAFRAS), 11)


class ZarcNormalizationTest(unittest.TestCase):
    def _csv(self, tmp):
        path = os.path.join(tmp, "zarc.csv")
        header = (
            "Nome_cultura;SafraIni;SafraFin;Cod_Cultura;Cod_Ciclo;Cod_Solo;geocodigo;UF;"
            "municipio;Cod_Clima;Nome_Clima;Cod_Outros_Manejos;Nome_Outros_Manejos;"
            "Produtividade;Cod_NM;Cod_Munic;Cod_Meso;Cod_Micro;Portaria;" + ";".join(
            f"dec{i}" for i in range(1, 37)
            )
        )
        decs = ["0"] * 36
        for i in range(28, 36):
            decs[i] = "20"
        row = (
            "Soja;2019;2020;12016720000011;21;12;5107925;MT;Sorriso;;;;;025535;02;510;"
            "510;510;Port.63_de_19-07-2019;" + ";".join(decs)
        )
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(header + "\n" + row + "\n")
        return path

    def test_normalization_extracts_window_and_portaria(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._csv(tmp)
            rows = zarc.normalize_rows(path, {"id": "r1"}, {"id": "d1", "license_title": "CC-BY"})
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["safra"], "2019/20")
        self.assertEqual(row["cultura"], "Soja")
        self.assertEqual(row["uf"], "MT")
        self.assertEqual(row["municipio"], "Sorriso")
        self.assertEqual(row["geocodigo"], "5107925")
        self.assertEqual(row["portaria"], "Port.63_de_19-07-2019")
        self.assertEqual(row["janela_inicio_decendio"], 29)
        self.assertEqual(row["janela_fim_decendio"], 36)
        self.assertTrue(row["janela_inicio_data"].startswith("2019-10"))
        self.assertIn("baixo", row["decendios_com_risco"])
        self.assertEqual(row["natureza"], "recomendacao_oficial_de_plantio_por_risco")

    def test_normalized_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._csv(tmp)
            rows = zarc.normalize_rows(path, {"id": "r1"}, {"id": "d1"})
            out = os.path.join(tmp, "out.csv")
            zarc.write_normalized(rows, out)
            back = zarc.read_normalized(out)
        self.assertEqual(len(back), 1)
        self.assertEqual(back[0]["cultura"], "Soja")
        self.assertEqual(back[0]["portaria"], "Port.63_de_19-07-2019")

    def test_resource_lookup_by_safra(self):
        metadata = {
            "resources": [
                {"id": "a", "name": "Tábua de risco - Safra 2023/2024", "format": "CSV", "url": "u1"},
                {"id": "b", "name": "Dicionário de Dados", "format": "PDF", "url": "u2"},
            ]
        }
        resource = zarc.resource_for_safra(metadata, "2023/2024")
        self.assertIsNotNone(resource)
        self.assertEqual(resource["id"], "a")
        self.assertIsNone(zarc.resource_for_safra(metadata, "2030/2031"))


class SutinTest(unittest.TestCase):
    def test_feature_properties_are_declared(self):
        for field in ("ID", "SIGLA_UF", "CD_MUN", "NM_MUN", "AREA_HA"):
            self.assertIn(field, conab_sutin.FEATURE_PROPERTIES)

    def test_summary_groups_by_municipality(self):
        features = [
            {"properties": {"CD_MUN": "5107925", "NM_MUN": "Sorriso", "SIGLA_UF": "MT", "AREA_HA": 10.0}},
            {"properties": {"CD_MUN": "5107925", "NM_MUN": "Sorriso", "SIGLA_UF": "MT", "AREA_HA": 5.0}},
            {"properties": {"CD_MUN": "5108501", "NM_MUN": "Vera", "SIGLA_UF": "MT", "AREA_HA": 2.0}},
        ]
        summary = conab_sutin.summarize(features)
        self.assertEqual(summary["total_features"], 3)
        self.assertAlmostEqual(summary["total_area_ha"], 17.0)
        sorrow = next(m for m in summary["municipalities"] if m["CD_MUN"] == "5107925")
        self.assertEqual(sorrow["features"], 2)
        self.assertAlmostEqual(sorrow["area_ha"], 15.0)

    def test_geojson_and_csv_writers(self):
        result = {
            "layer": "wp_geote:MT_SOJA_2021",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                    "properties": {"ID": 1, "CD_MUN": "5107925", "AREA_HA": 3.5, "_layer": "L"},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            geojson = conab_sutin.write_geojson(result, os.path.join(tmp, "a.geojson"))
            csv_path = conab_sutin.write_csv(result, os.path.join(tmp, "a.csv"))
            import json as _json

            payload = _json.load(open(geojson, encoding="utf-8"))
            rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
        self.assertEqual(payload["type"], "FeatureCollection")
        self.assertEqual(len(payload["features"]), 1)
        self.assertEqual(rows[0]["CD_MUN"], "5107925")


class MunicipalGridTest(unittest.TestCase):
    def test_blocks_cover_the_grid(self):
        grid = {
            "crs": "EPSG:32721",
            "transform": muni.read.Affine(20.0, 0.0, 500000.0, 0.0, -20.0, 8600000.0),
            "width": 100,
            "height": 80,
            "res": 20.0,
        }
        blocks = muni.grid_blocks(grid, n_blocks=4)
        self.assertEqual(len(blocks), 4)
        covered = sum(b["height"] * b["width"] for b in blocks)
        self.assertEqual(covered, 100 * 80)

    def test_block_window_and_subgrid_alignment(self):
        from affine import Affine

        grid = {
            "crs": "EPSG:32721",
            "transform": Affine(20.0, 0.0, 500000.0, 0.0, -20.0, 8600000.0),
            "width": 100,
            "height": 80,
            "res": 20.0,
        }
        block = {"row_off": 10, "col_off": 20, "height": 30, "width": 40}
        window = muni.block_window(grid, block)
        self.assertEqual(window["bounds"][0], 500000.0 + 20 * 20.0)
        self.assertEqual(window["bounds"][3], 8600000.0 - 10 * 20.0)
        subgrid = lu.block_subgrid(grid, block)
        self.assertEqual(subgrid["height"], 30)
        self.assertEqual(subgrid["width"], 40)

    def test_estimate_scales_with_dates(self):
        grid = {
            "crs": "EPSG:32721",
            "transform": muni.read.Affine(20.0, 0.0, 500000.0, 0.0, -20.0, 8600000.0),
            "width": 1000,
            "height": 1000,
            "res": 20.0,
        }
        estimate = muni.estimate_operation(grid, n_dates=3)
        self.assertEqual(estimate["grid_pixels_20m"], 1_000_000)
        self.assertGreater(estimate["download_bytes_per_date"], 0)
        self.assertIn("blocos", estimate["memory_note"])

    def test_accumulator_merges_blocks(self):
        values = np.array([[0.2, 0.4], [np.nan, 0.8]], dtype="float32")
        valid = np.array([[True, True], [True, True]])
        agricultural = np.array([[True, False], [True, True]])
        acc = muni.accumulate_ndvi(values, valid, agricultural)
        self.assertEqual(acc["count"], 2)
        merged = muni.merge_accumulators([acc, acc])
        self.assertEqual(merged["count"], 4)
        self.assertAlmostEqual(merged["mean"], (0.2 + 0.8) / 2, places=6)
        self.assertIn("p50", merged["quantiles"])

    def test_accumulator_ignores_non_agricultural_pixels(self):
        values = np.array([[0.9]], dtype="float32")
        valid = np.array([[True]])
        agricultural = np.array([[False]])
        acc = muni.accumulate_ndvi(values, valid, agricultural)
        self.assertEqual(acc["count"], 0)

    def test_scl_keep_uses_profile_b(self):
        scl = np.array([[2, 6, 4, 9]], dtype="uint8")
        keep = muni.scl_keep(scl)
        self.assertEqual(keep.tolist(), [[False, False, True, False]])


if __name__ == "__main__":
    unittest.main()
