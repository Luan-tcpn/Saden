"""Testes da V2.6 — base agroclimática, graus-dia, ET0, balanço hídrico e painel."""

from __future__ import annotations

import csv
import os
import tempfile
import unittest

import numpy as np

from agroclimate import (
    boundaries,
    evapotranspiration as et,
    gridded,
    inmet,
    panel,
    quality,
    shapefile,
    stations,
    thermal,
    water_balance as wb,
)


class RemoteZipTest(unittest.TestCase):
    """O leitor de ZIP remoto precisa devolver exatamente o pedido."""

    class _FakeResponse:
        def __init__(self, payload, start, end, total):
            self._payload = payload
            self._start = start
            self._end = end
            self.headers = {"Content-Length": str(total)}

        def read(self, size=-1):
            return self._payload[self._start : self._end + 1]

        def close(self):
            pass

    def test_read_returns_exact_size_and_advances_cursor(self):
        from agroclimate import remote_zip

        payload = bytes(range(256)) * 8

        class Reader(remote_zip.HTTPRangeReader):
            def _head_size(self):
                return len(payload)

            def _fetch(self, start, end):
                return payload[start : end + 1]

        reader = Reader("http://exemplo/x.zip")
        reader.seek(10)
        first = reader.read(4)
        self.assertEqual(first, payload[10:14])
        self.assertEqual(reader.tell(), 14)
        second = reader.read(6)
        self.assertEqual(second, payload[14:20])
        self.assertEqual(reader.tell(), 20)

    def test_truncated_response_raises(self):
        from agroclimate import remote_zip

        class Reader(remote_zip.HTTPRangeReader):
            def _head_size(self):
                return 100

            def _fetch(self, start, end):
                return b"x" * 3

        reader = Reader("http://exemplo/x.zip")
        with self.assertRaises(remote_zip.RangeHTTPError):
            reader.read(50)


class ShapefileTest(unittest.TestCase):
    """Leitor de shapefile/DBF em Python puro."""

    def _dbf(self) -> bytes:
        # cabeçalho + 2 campos + 1 registro
        header = bytearray(32)
        header[0:4] = (1).to_bytes(4, "little")  # nº de registros
        header[4:8] = (1).to_bytes(4, "little")  # registro mais recente
        header[8:10] = (97).to_bytes(2, "little")  # comprimento do cabeçalho
        header[10:12] = (18).to_bytes(2, "little")  # comprimento do registro
        field1 = bytearray(32)
        field1[0:11] = b"CD_MUN\0\0\0\0\0"
        field1[11] = 0x43
        field1[16] = 7
        field2 = bytearray(32)
        field2[0:11] = b"NM_MUN\0\0\0\0\0"
        field2[11] = 0x43
        field2[16] = 10
        terminator = bytes([0x0D])
        record = b" " + b"5107925" + b"Sorriso   "
        return bytes(header) + bytes(field1) + bytes(field2) + terminator + record

    def test_dbf_fields_and_values(self):
        names, records = shapefile._read_dbf(self._dbf())
        self.assertEqual(names, ["CD_MUN", "NM_MUN"])
        self.assertEqual(records[0]["CD_MUN"], "5107925")
        self.assertEqual(records[0]["NM_MUN"], "Sorriso")

    def test_rings_to_geojson_polygon_and_multipolygon(self):
        rings = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]]
        polygon = shapefile.rings_to_geojson(rings)
        self.assertEqual(polygon["type"], "Polygon")
        multi = shapefile.rings_to_geojson(rings + rings)
        self.assertEqual(multi["type"], "MultiPolygon")


class InmetParsingTest(unittest.TestCase):
    """Normalização dos CSVs do INMET."""

    def _csv(self) -> bytes:
        header = (
            "Data;Hora UTC;PRECIPITAÇÃO TOTAL, HORÁRIO (mm);"
            "PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB);"
            "RADIACAO GLOBAL (KJ/m²);TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);"
            "TEMPERATURA DO PONTO DE ORVALHO (°C);"
            "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C);"
            "TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C);"
            "UMIDADE RELATIVA DO AR, HORARIA (%);"
            "VENTO, DIREÇÃO HORARIA (gr) (° (gr));"
            "VENTO, VELOCIDADE HORARIA (m/s);"
        )
        rows = [
            "2019/01/01;0000 UTC;0;969,6;;22,8;21,3;23,0;22,8;92;90;1,4;",
            "2019/01/01;0100 UTC;-9999;969,6;10;22,4;20,9;22,8;22,4;91;95;1,6;",
            "2019/01/02;0000 UTC;5,5;970,0;20;25,0;21,0;26,0;23,0;80;100;2,0;",
        ]
        meta = (
            "REGIÃO:;CO\nUF:;MT\nESTAÇÃO:;SORRISO\nCODIGO (WMO):;A904\n"
            "LATITUDE:;-12,555107\nLONGITUDE:;-55,722863\nALTITUDE:;379,31\n"
        )
        return (meta + header + "\n" + "\n".join(rows) + "\n").encode("latin-1")

    def test_daily_aggregation_and_unit_conversion(self):
        payload = self._csv()
        station_file = inmet.parse_station_csv(2019, "membro.csv", payload)
        daily = inmet.to_daily_records(station_file)
        self.assertEqual(len(daily), 2)
        self.assertEqual(daily[0]["date"], "2019-01-01")
        # precipitação: 0 e ausente (-9999) -> 0,0 (ausente nao conta)
        self.assertEqual(daily[0]["precip_mm"], 0.0)
        self.assertEqual(daily[1]["precip_mm"], 5.5)
        # pressão: mB -> kPa
        self.assertAlmostEqual(daily[0]["pressao_kpa"], 96.96, places=2)
        # radiação: kJ/m² -> MJ/m²
        self.assertAlmostEqual(daily[0]["radiacao_mj_m2"], 0.010, places=6)
        # vento: m/s -> km/h (média de 1,4 e 1,6 = 1,5 m/s)
        self.assertAlmostEqual(daily[0]["vento_kmh"], 1.5 * 3.6, places=3)
        # temperatura média, máxima e mínima do dia
        self.assertAlmostEqual(daily[0]["temp_media_c"], 22.6, places=3)
        self.assertAlmostEqual(daily[0]["temp_max_c"], 23.0, places=3)
        self.assertAlmostEqual(daily[0]["temp_min_c"], 22.4, places=3)

    def test_missing_value_is_not_zero(self):
        payload = self._csv()
        station_file = inmet.parse_station_csv(2019, "m.csv", payload)
        daily = inmet.to_daily_records(station_file)
        # o dia 01 tem precipitação horária 0 e -9999: a média da soma é 0.0
        # mas o **dado ausente** não pode virar chuva
        self.assertIsNotNone(daily[0]["precip_mm"])
        self.assertEqual(daily[0]["precip_mm"], 0.0)
        self.assertEqual(daily[0]["precip_mm_n_obs"], 1)

    def test_find_member_by_wmo_code(self):
        members = [
            "2019/INMET_CO_MT_A904_SORRISO_01-01-2019_A_31-12-2019.CSV",
            "2019/INMET_CO_MT_A905_CAMPO NOVO DOS PARECIS_01-01-2019.CSV",
        ]
        found = inmet.find_member(members, "A904")
        self.assertTrue(found.endswith("A904_SORRISO_01-01-2019_A_31-12-2019.CSV"))
        self.assertIsNone(inmet.find_member(members, "A999"))


class ThermalTest(unittest.TestCase):
    """Graus-dia por perfil metodológico."""

    def test_profiles_are_documented(self):
        for key in ("soja_ometto", "soja_gilmore", "milho_embrapa"):
            profile = thermal.PROFILES[key]
            self.assertTrue(profile.source)
            self.assertTrue(profile.limitations)
            self.assertTrue(profile.formula)
        self.assertEqual(thermal.PROFILES["milho_embrapa"].base_temperature_c, 10.0)
        self.assertEqual(thermal.PROFILES["milho_embrapa"].upper_temperature_c, 30.0)
        self.assertEqual(thermal.PROFILES["soja_ometto"].base_temperature_c, 14.0)
        self.assertEqual(thermal.PROFILES["soja_ometto"].upper_temperature_c, 36.0)

    def test_milho_caps_tmax_and_tmin(self):
        profile = thermal.PROFILES["milho_embrapa"]
        # Tmax 40 e Tmin 2 -> ((30 + 10)/2) - 10 = 10
        value = thermal.degree_days(40.0, 2.0, profile)
        self.assertAlmostEqual(value, 10.0, places=6)

    def test_soja_profile_limits_mean_temperature(self):
        profile = thermal.PROFILES["soja_gilmore"]
        # Tmed 35 -> limitado a 30 -> 30 - 10 = 20
        self.assertAlmostEqual(thermal.degree_days(36.0, 34.0, profile), 20.0, places=6)

    def test_zero_below_base(self):
        profile = thermal.PROFILES["soja_gilmore"]
        self.assertEqual(thermal.degree_days(5.0, 2.0, profile), 0.0)

    def test_missing_temperature_returns_none(self):
        profile = thermal.PROFILES["milho_embrapa"]
        self.assertIsNone(thermal.degree_days(None, 10.0, profile))
        self.assertIsNone(thermal.degree_days(10.0, None, profile))

    def test_accumulate_uses_only_available_days(self):
        profile = thermal.PROFILES["soja_gilmore"]
        records = [
            {"date": "2020-01-01", "temp_max_c": 30.0, "temp_min_c": 10.0},
            {"date": "2020-01-02", "temp_max_c": None, "temp_min_c": None},
            {"date": "2020-01-03", "temp_max_c": 30.0, "temp_min_c": 10.0},
        ]
        result = thermal.accumulate_degree_days(records, profile)
        self.assertEqual(result["days_used"], 2)
        self.assertEqual(result["days_expected"], 3)
        self.assertAlmostEqual(result["degree_days_total"], 20.0, places=6)

    def test_heat_wave_needs_consecutive_days(self):
        records = [
            {"date": "2020-01-01", "temp_max_c": 36.0},
            {"date": "2020-01-02", "temp_max_c": 36.0},
            {"date": "2020-01-03", "temp_max_c": 20.0},
            {"date": "2020-01-04", "temp_max_c": 36.0},
            {"date": "2020-01-05", "temp_max_c": 36.0},
            {"date": "2020-01-06", "temp_max_c": 36.0},
        ]
        result = thermal.heat_wave_events(records, threshold_c=35.0)
        self.assertEqual(result["n_events"], 1)
        self.assertEqual(result["total_days"], 3)
        self.assertEqual(result["events"][0]["start"], "2020-01-04")

    def test_percentile(self):
        self.assertAlmostEqual(
            thermal.percentile_threshold([float(v) for v in range(1, 101)], 90.0),
            90.1,
            places=6,
        )


class EvapotranspirationTest(unittest.TestCase):
    """ET0 — FAO-56, Thornthwaite e Hargreaves."""

    def test_saturation_vapour_pressure(self):
        value = et.saturation_vapour_pressure(20.0)
        self.assertAlmostEqual(value, 2.338, places=3)

    def test_wind_conversion_10m_to_2m(self):
        self.assertAlmostEqual(et.wind_at_2m(10.0), 4.0, places=6)
        self.assertIsNone(et.wind_at_2m(None))

    def test_fao56_requires_all_inputs(self):
        result = et.fao56_penman_monteith(
            30.0, 20.0, 25.0, None, 10.0, 60.0, 96.0, -12.7, 200
        )
        self.assertFalse(result.available)
        self.assertIsNone(result.et0_mm)

    def test_fao56_returns_positive_value(self):
        result = et.fao56_penman_monteith(
            30.0, 20.0, 25.0, 20.0, 10.0, 60.0, 96.0, -12.7, 200
        )
        self.assertTrue(result.available)
        self.assertGreater(result.et0_mm, 0.0)
        self.assertEqual(result.method, "fao56_penman_monteith")

    def test_fao56_magnitude_is_physiological(self):
        """Regressão: o ET0 diário tem de ficar na faixa fisiológica.

        Um dia de céu limpo no Cerrado (Radiação 20 MJ/m², Tmax 30 °C,
        Tmin 20 °C, UR 60%, vento 10 km/h) exige ~3–7 mm/dia. A implementação
        anterior multiplicava a radiação pelo coeficiente 0,408 **sem** o
        gradiente de pressão de vapor, o que inflava o ET0 em ~6×.
        """
        result = et.fao56_penman_monteith(
            30.0, 20.0, 25.0, 20.0, 10.0, 60.0, 96.0, -12.7, 200
        )
        self.assertTrue(result.available)
        self.assertGreater(result.et0_mm, 1.0)
        self.assertLess(result.et0_mm, 12.0)

    def test_fao56_uses_delta_on_radiation(self):
        """A radiação entra multiplicada por Δ (equação 6 da FAO-56)."""
        low = et.fao56_penman_monteith(
            30.0, 20.0, 25.0, 10.0, 10.0, 60.0, 96.0, -12.7, 200
        )
        high = et.fao56_penman_monteith(
            30.0, 20.0, 25.0, 25.0, 10.0, 60.0, 96.0, -12.7, 200
        )
        self.assertLess(low.et0_mm, high.et0_mm)

    def test_thornthwaite_heat_index_and_exponent(self):
        heat, exponent = et.thornthwaite_heat_index([25.0] * 12)
        self.assertGreater(heat, 0.0)
        self.assertGreater(exponent, 0.0)
        # I = 12 * (25/5)^1,514
        expected = 12 * (5.0 ** 1.514)
        self.assertAlmostEqual(heat, expected, places=4)

    def test_hargreaves_samani(self):
        result = et.hargreaves_samani(30.0, 20.0, 30.0)
        self.assertTrue(result.available)
        self.assertGreater(result.et0_mm, 0.0)

    def test_methods_are_identifiable(self):
        series = et.daily_et0_series(
            [{"date": "2020-01-01", "temp_max_c": 30.0, "temp_min_c": 20.0,
              "temp_media_c": 25.0, "radiacao_mj_m2": 20.0, "vento_kmh": 10.0,
              "umidade_rel_pct": 60.0, "pressao_kpa": 96.0}],
            -12.7, method="fao56_penman_monteith",
        )
        self.assertEqual(series[0]["et_method"], "fao56_penman_monteith")


class WaterBalanceTest(unittest.TestCase):
    """Balanço hídrico de Thornthwaite & Mather."""

    def test_soil_profiles_are_documented(self):
        for key, profile in wb.SOIL_PROFILES.items():
            self.assertTrue(profile.source)
            self.assertTrue(profile.limitations)
            self.assertGreater(profile.cad_mm, 0.0)

    def test_sequential_balance_dry_period(self):
        monthly = [
            {"month": "2020-01", "precip_mm": 0.0, "etp_mm": 50.0},
            {"month": "2020-02", "precip_mm": 0.0, "etp_mm": 50.0},
        ]
        balance = wb.sequential_water_balance(monthly, cad_mm=50.0)
        self.assertEqual(len(balance), 2)
        # primeiro mês: ETR limitada pela água disponível
        self.assertAlmostEqual(balance[0]["etr_mm"], 50.0, places=6)
        self.assertAlmostEqual(balance[0]["def_mm"], 0.0, places=6)
        # segundo mês: solo esgotado -> deficiencia
        self.assertAlmostEqual(balance[1]["etr_mm"], 0.0, places=6)
        self.assertAlmostEqual(balance[1]["def_mm"], 50.0, places=6)
        self.assertAlmostEqual(balance[1]["arm_mm"], 0.0, places=6)

    def test_sequential_balance_excess(self):
        monthly = [{"month": "2020-01", "precip_mm": 200.0, "etp_mm": 50.0}]
        balance = wb.sequential_water_balance(monthly, cad_mm=50.0)
        self.assertAlmostEqual(balance[0]["arm_mm"], 50.0, places=6)
        self.assertAlmostEqual(balance[0]["exc_mm"], 150.0, places=6)
        self.assertAlmostEqual(balance[0]["def_mm"], 0.0, places=6)

    def test_missing_data_is_flagged(self):
        monthly = [{"month": "2020-01", "precip_mm": None, "etp_mm": 50.0}]
        balance = wb.sequential_water_balance(monthly, cad_mm=50.0)
        self.assertEqual(balance[0]["status"], "incomplete")
        self.assertIsNone(balance[0]["etr_mm"])

    def test_daily_to_monthly_sums_precipitation(self):
        daily = [
            {"date": "2020-01-01", "precip_mm": 10.0, "et0_mm": 3.0},
            {"date": "2020-01-02", "precip_mm": 5.0, "et0_mm": 4.0},
        ]
        monthly = wb.daily_to_monthly(daily)
        self.assertEqual(monthly[0]["month"], "2020-01")
        self.assertAlmostEqual(monthly[0]["precip_mm"], 15.0, places=6)
        # a ETP mensal e a SUMA do ET0 diario (nao a media diaria)
        self.assertAlmostEqual(monthly[0]["etp_mm"], 7.0, places=6)


class QualityTest(unittest.TestCase):
    """Auditoria de séries meteorológicas."""

    def test_missing_is_not_zero(self):
        records = [
            {"date": "2020-01-01", "precip_mm": None},
            {"date": "2020-01-02", "precip_mm": 0.0},
        ]
        audit = quality.audit_series(records)
        self.assertEqual(audit["missing_counts"]["precip_mm"], 1)
        self.assertEqual(audit["records"][0]["precip_mm"], None)
        self.assertEqual(audit["records"][1]["precip_mm"], 0.0)

    def test_out_of_range_values_are_flagged_not_corrected(self):
        records = [{"date": "2020-01-01", "temp_max_c": 80.0}]
        audit = quality.audit_series(records)
        self.assertEqual(audit["invalid_counts"]["temp_max_c"], 1)
        self.assertIsNone(audit["records"][0]["temp_max_c"])
        self.assertEqual(audit["records"][0]["raw_temp_max_c"], 80.0)

    def test_duplicate_dates_are_counted(self):
        records = [
            {"date": "2020-01-01", "precip_mm": 1.0},
            {"date": "2020-01-01", "precip_mm": 2.0},
        ]
        audit = quality.audit_series(records)
        self.assertEqual(audit["duplicate_dates"], 1)
        self.assertEqual(audit["n_unique_days"], 1)

    def test_inconsistent_range_flagged(self):
        records = [{"date": "2020-01-01", "temp_max_c": 10.0, "temp_min_c": 25.0}]
        audit = quality.audit_series(records)
        self.assertEqual(audit["invalid_counts"]["temp_range"], 1)

    def test_discontinuity_detected(self):
        records = [
            {"date": "2020-01-01", "precip_mm": 1.0},
            {"date": "2020-01-20", "precip_mm": 1.0},
        ]
        audit = quality.audit_series(records)
        self.assertEqual(audit["n_discontinuities"], 1)

    def test_period_coverage(self):
        records = [{"date": "2020-01-01"}, {"date": "2020-01-02"}]
        result = quality.period_coverage(records, "2020-01-01", "2020-01-10")
        self.assertEqual(result["days_expected"], 10)
        self.assertEqual(result["days_observed"], 2)
        self.assertAlmostEqual(result["coverage"], 0.2, places=6)


class StationSelectionTest(unittest.TestCase):
    """Seleção de estação por município — critério explícito."""

    def _stations(self):
        return [
            stations.Station("A001", "DENTRO", "MT", -12.0, -55.0, 300.0,
                             "Automatica", "Operante", "2002-01-01", None),
            stations.Station("A002", "LONGE", "MT", -20.0, -55.0, 300.0,
                             "Automatica", "Operante", "2002-01-01", None),
        ]

    def test_station_inside_municipality_is_preferred(self):
        from shapely.geometry import Polygon

        polygon = Polygon([(-56, -13), (-54, -13), (-54, -11), (-56, -11), (-56, -13)])
        municipalities = [
            {
                "ibge_code": "5107925", "municipality": "Sorriso", "state": "MT",
                "centroid_lat": -12.0, "centroid_lon": -55.0, "geometry": polygon,
            }
        ]
        selected = stations.select_stations_for_municipalities(
            self._stations(), municipalities
        )
        self.assertEqual(selected[0]["station_code"], "A001")
        self.assertEqual(selected[0]["selection_method"], "inside_municipality")

    def test_none_when_no_station_within_threshold(self):
        municipalities = [
            {
                "ibge_code": "1", "municipality": "X", "state": "MT",
                "centroid_lat": 0.0, "centroid_lon": 0.0, "geometry": None,
            }
        ]
        selected = stations.select_stations_for_municipalities(
            self._stations(), municipalities, max_distance_km=10.0
        )
        self.assertEqual(selected[0]["selection_method"], "none")
        self.assertIsNone(selected[0]["station_code"])

    def test_haversine_distance(self):
        distance = stations.haversine_km(-12.0, -55.0, -12.0, -56.0)
        self.assertAlmostEqual(distance, 108.8, places=0)


class AnalysisTest(unittest.TestCase):
    """Análise do painel: regressões de basal, walk-forward e efeitos fixos."""

    def _rows(self, municipalities=4, years=6, slope=2.0):
        """Painel sintético com chuva **independente** do efeito de município.

        A chuva varia dentro de cada município-ano (para que o coeficiente
        climático seja identificável) e o efeito fixo de município é
        ortogonal à chuva.
        """
        rows = []
        for m in range(municipalities):
            for y in range(years):
                rain = 100.0 + 7.0 * ((m * 3 + y * 5) % 9)
                rows.append(
                    {
                        "ibge_code": f"m{m}",
                        "municipality": f"M{m}",
                        "state": "MT",
                        "crop": "soja",
                        "year": 2018 + y,
                        "yield_kg_ha": 2000.0 + slope * rain + 7.0 * m,
                        "precip_acumulada_mm": rain,
                        "temp_media_c": 22.0 + y,
                        "degree_days_total": 1000.0 + 5.0 * y,
                        "et0_total_mm": 900.0 + 4.0 * y,
                        "deficiency_total_mm": 10.0 * y,
                        "excess_total_mm": 50.0 * y,
                    }
                )
        return rows

    def test_baselines_use_yield(self):
        from agroclimate import analysis

        rows = self._rows()
        train, test = rows[:3], rows[3]
        predictions = analysis.baseline_predictions(train, test)
        expected = sum(r["yield_kg_ha"] for r in train) / 3
        self.assertAlmostEqual(predictions["media_historica"], expected, places=6)
        self.assertAlmostEqual(
            predictions["ultimo_valor"], train[-1]["yield_kg_ha"], places=6
        )

    def test_fit_predict_uses_variables(self):
        from agroclimate import analysis

        rows = self._rows()
        train, test = rows[:12], rows[12]
        prediction = analysis.fit_predict(train, test, ("precip_acumulada_mm",))
        self.assertIsNotNone(prediction)
        # a regressao simples tem de aproximar o rendimento observado
        self.assertLess(
            abs(prediction - test["yield_kg_ha"]), 0.05 * test["yield_kg_ha"]
        )
        # sem a variavel, a previsao e a media do treino (nao usa a chuva)
        baseline = analysis.baseline_predictions(train, test)["media_historica"]
        self.assertNotAlmostEqual(prediction, baseline, places=3)

    def test_fixed_effects_recovers_coefficient(self):
        """Regressão: coeficiente do clima dentro de município e ano."""
        from agroclimate import analysis

        rows = self._rows()
        result = analysis.fixed_effects(rows, "precip_acumulada_mm")
        self.assertEqual(result["status"], "ok")
        self.assertAlmostEqual(result["coefficient"], 2.0, places=4)
        self.assertGreater(result["std_error_clustered"], 0.0)

    def test_walk_forward_has_no_leakage(self):
        from agroclimate import analysis

        rows = self._rows()
        result = analysis.walk_forward(
            rows, variables=("precip_acumulada_mm",), min_train=3
        )
        self.assertEqual(result["status"], "ok")
        self.assertIn("modelo", result["models"])
        for prediction in result["predictions"]:
            self.assertGreaterEqual(prediction["year"], 2021)

    def test_territorial_holdout_keeps_municipalities_together(self):
        from agroclimate import analysis

        rows = self._rows()
        result = analysis.territorial_holdout(
            rows, ("precip_acumulada_mm",), n_folds=2
        )
        self.assertEqual(result["status"], "ok")
        folds = {}
        for prediction in result["predictions"]:
            folds.setdefault(prediction["fold"], set()).add(prediction["ibge_code"])
        for codes in folds.values():
            self.assertEqual(len(codes), 2)  # 4 municípios, 2 folds

    def test_holm_correction_is_monotone(self):
        from agroclimate import analysis

        corrected = analysis.holm_correction({"a": 0.01, "b": 0.04, "c": 0.20})
        self.assertLessEqual(corrected["a"], corrected["b"])
        self.assertLessEqual(corrected["b"], corrected["c"])

    def test_permutation_is_deterministic(self):
        from agroclimate import analysis

        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        first = analysis.permutation_p(x, y, permutations=200, seed=7)
        second = analysis.permutation_p(x, y, permutations=200, seed=7)
        self.assertEqual(first, second)


class PanelTest(unittest.TestCase):
    """Montagem do painel agroclimático."""

    def _pam(self):
        return [
            {
                "geography_code": "5107925", "crop_code": "40124",
                "reference_year": "2020", "variable_normalized": "rendimento_medio_kg_ha",
                "value_normalized": "3540", "observation_status": "observed",
                "unit_original": "Quilogramas por Hectare",
                "dataset_name": "PAM", "dataset_id": "SIDRA:5457", "nature": "observed",
            },
            {
                "geography_code": "5107925", "crop_code": "40124",
                "reference_year": "2020", "variable_normalized": "area_colhida_ha",
                "value_normalized": "600000", "observation_status": "observed",
            },
        ]

    def _zarc(self):
        return [
            {
                "geocodigo": "5107925", "safra": "2019/20", "safra_ini": "2019",
                "safra_fin": "2020", "cultura": "Soja", "cod_ciclo": "20",
                "cod_solo": "1", "cod_clima": "", "portaria": "port.63",
                "decendios_com_risco": "29:baixo;30:baixo;31:baixo",
            }
        ]

    def _climate(self):
        """Série diária cobrindo a janela out-dez de 2019 (92 dias)."""
        records = []
        for month, last in (("10", 31), ("11", 30), ("12", 31)):
            for day in range(1, last + 1):
                records.append(
                    {
                        "date": f"2019-{month}-{day:02d}",
                        "temp_max_c": 32.0, "temp_min_c": 18.0,
                        "temp_media_c": 25.0, "precip_mm": 5.0,
                        "umidade_rel_pct": 70.0, "radiacao_mj_m2": 18.0,
                        "vento_kmh": 8.0, "pressao_kpa": 96.0,
                        "source": "NASA-POWER", "source_type": "reanalysis",
                    }
                )
        return {("5107925", "NASA-POWER"): records}

    def _municipalities(self):
        return {
            "5107925": {
                "ibge_code": "5107925", "municipality": "Sorriso", "state": "MT",
                "region": "Centro-Oeste", "centroid_lat": -12.5,
                "centroid_lon": -55.7, "elevation_m": 400.0,
            }
        }

    def test_panel_row_has_agroclimatic_indicators(self):
        rows = panel.build_panel(
            self._pam(), self._zarc(), self._climate(), self._municipalities()
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["crop"], "soja")
        self.assertEqual(row["harvest_year"], 2020)
        self.assertEqual(row["status"], "paired_usable")
        # 31 dias na janela (10-11 a 11-10 de 2019), 5 mm por dia
        self.assertAlmostEqual(row["precip_acumulada_mm"], 155.0, places=3)
        self.assertIsNotNone(row["degree_days_total"])
        self.assertIsNotNone(row["et0_total_mm"])
        self.assertIsNotNone(row["deficiency_total_mm"])
        self.assertEqual(row["climate_source_type"], "reanalysis")
        self.assertEqual(row["thermal_profile"], "soja_gilmore")

    def test_panel_excludes_when_yield_missing(self):
        rows = panel.build_panel(
            [], self._zarc(), self._climate(), self._municipalities()
        )
        self.assertEqual(rows[0]["status"], "excluded")
        self.assertIn("rendimento", rows[0]["exclusion_reason"])

    def test_panel_has_no_duplicate_observations_per_window(self):
        """Duas janelas do mesmo município-ano não criam observações extras."""
        zarc = self._zarc() + [
            {
                "geocodigo": "5107925", "safra": "2019/20", "safra_ini": "2019",
                "safra_fin": "2020", "cultura": "Soja", "cod_ciclo": "21",
                "cod_solo": "2", "cod_clima": "", "portaria": "port.63",
                "decendios_com_risco": "29:baixo;30:baixo;31:baixo",
            }
        ]
        rows = panel.build_panel(
            self._pam(), zarc, self._climate(), self._municipalities()
        )
        self.assertEqual(len(rows), 1)

    def test_milho_2_semantic_incompatibility_is_declared(self):
        zarc = [
            {
                "geocodigo": "5107925", "safra": "2019/20", "safra_ini": "2019",
                "safra_fin": "2020", "cultura": "Milho 2ª Safra", "cod_ciclo": "20",
                "cod_solo": "1", "cod_clima": "", "portaria": "port.99",
                "decendios_com_risco": "1:baixo;2:baixo",
            }
        ]
        pam = [
            {
                "geography_code": "5107925", "crop_code": "40122",
                "reference_year": "2020", "variable_normalized": "rendimento_medio_kg_ha",
                "value_normalized": "6840", "observation_status": "observed",
            }
        ]
        climate = {
            ("5107925", "NASA-POWER"): [
                {
                    "date": f"2020-01-{day:02d}", "temp_max_c": 32.0,
                    "temp_min_c": 18.0, "temp_media_c": 25.0, "precip_mm": 5.0,
                    "umidade_rel_pct": 70.0, "radiacao_mj_m2": 18.0,
                    "vento_kmh": 8.0, "pressao_kpa": 96.0,
                    "source": "NASA-POWER", "source_type": "reanalysis",
                }
                for day in range(1, 32)
            ] + [
                {
                    "date": f"2020-02-{day:02d}", "temp_max_c": 32.0,
                    "temp_min_c": 18.0, "temp_media_c": 25.0, "precip_mm": 5.0,
                    "umidade_rel_pct": 70.0, "radiacao_mj_m2": 18.0,
                    "vento_kmh": 8.0, "pressao_kpa": 96.0,
                    "source": "NASA-POWER", "source_type": "reanalysis",
                }
                for day in range(1, 30)
            ]
        }
        rows = panel.build_panel(pam, zarc, climate, self._municipalities())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["crop"], "milho_2")
        self.assertIn("incompativel", rows[0]["semantic_compatibility"])


if __name__ == "__main__":
    unittest.main()
