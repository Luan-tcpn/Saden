"""V3.1 — contrato temporal da janela ZARC (D100) e vizinhos históricos.

A V3.0 descobriu (D97) que o painel excluía o **último mês** da janela: a
consulta comparava a data diária ``"AAAA-MM-DD"`` com o rótulo mensal
``"AAAA-MM"``, e ``"2017-12-01" > "2017-12"`` na ordem lexicográfica. O efeito
não era pequeno — a janela ficava ~30% mais curta e **todas** as variáveis
agregadas (precipitação, ET0, graus-dia, calor extremo, déficit, excedente)
saíam menores que o pretendido.

Este arquivo fixa o contrato: limites explícitos, meses efetivamente
incluídos, virada de ano, ano bissexto, janela de um mês, e a garantia de que a
semântica histórica continua reproduzível para comparação.
"""

from __future__ import annotations

import numpy as np
import pytest

from agroclimate import cycle, generalization, thermal, water_balance

PROFILE = thermal.PROFILES["milho_embrapa"]


def _daily(dates, base=25.0, precip=5.0):
    return [
        {
            "date": day,
            "temp_max_c": base + 5.0,
            "temp_min_c": base - 5.0,
            "temp_media_c": base,
            "precip_mm": precip,
            "radiacao_mj_m2": 20.0,
            "umidade_rel_pct": 70.0,
            "vento_kmh": 8.0,
            "pressao_kpa": 95.0,
        }
        for day in dates
    ]


# --------------------------------------------------------------------------
# contrato dos limites
# --------------------------------------------------------------------------


def test_corrected_window_includes_last_month():
    start, end = cycle.window_bounds(["2017-10", "2017-11", "2017-12"])
    assert start == "2017-10-01"
    assert end == "2017-12-31"


def test_window_crossing_new_year_covers_all_listed_months():
    months = ["2017-11", "2017-12", "2018-01", "2018-02"]
    start, end = cycle.window_bounds(months)
    days = [
        "2017-11-30",
        "2017-12-01",
        "2017-12-31",
        "2018-01-01",
        "2018-01-31",
        "2018-02-01",
        "2018-02-28",
    ]
    inside = [d for d in days if start <= d <= end]
    assert len(inside) == len(days)
    assert {d[:7] for d in inside} == set(months)


def test_single_month_window_is_the_whole_month():
    start, end = cycle.window_bounds(["2019-04"])
    assert start == "2019-04-01"
    assert end == "2019-04-30"


def test_leap_year_last_day():
    assert cycle.window_bounds(["2020-02"])[1] == "2020-02-29"
    assert cycle.window_bounds(["2021-02"])[1] == "2021-02-28"


def test_empty_window_raises():
    with pytest.raises(ValueError):
        cycle.window_bounds([])
    with pytest.raises(ValueError):
        cycle.window_bounds(["", "   "])


def test_corrected_and_legacy_differ_on_last_bound():
    months = ["2017-10", "2017-11", "2017-12"]
    legacy = cycle.window_bounds(months, corrected=False)
    corrected = cycle.window_bounds(months, corrected=True)
    # o início efetivo é o mesmo dia (o rótulo mensal já inclui o dia 1º)
    assert "2017-10-01" >= legacy[0]
    assert corrected[0] == "2017-10-01"
    # o fim é o que muda: rótulo mensal contra último dia do mês
    assert legacy[1] == "2017-12"
    assert corrected[1] == "2017-12-31"


def test_legacy_semantics_drops_the_last_month_entirely():
    """Sob a semântica histórica, nenhum dia do último mês entra na janela."""
    months = ["2017-10", "2017-11", "2017-12"]
    _, legacy_end = cycle.window_bounds(months, corrected=False)
    dates = [f"2017-12-{day:02d}" for day in range(1, 32)]
    assert [d for d in dates if d <= legacy_end] == []


def test_window_bounds_is_deterministic_and_ignores_blank_months():
    months = ["2017-10", "", "2017-11", "  ", "2017-12"]
    assert cycle.window_bounds(months) == cycle.window_bounds(
        ["2017-10", "2017-11", "2017-12"]
    )


def test_months_used_equals_months_listed_for_full_months():
    """Invariante quebrada pela D97: um mês listado = um mês usado."""
    import calendar
    from datetime import date, timedelta

    months = ["2017-11", "2017-12", "2018-01"]
    start, end = cycle.window_bounds(months)
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    days = [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]
    expected = sum(calendar.monthrange(int(m[:4]), int(m[5:7]))[1] for m in months)
    assert len(days) == expected
    assert {day[:7] for day in days} == set(months)


# --------------------------------------------------------------------------
# agregação: somas, contagens, graus-dia, calor e balanço
# --------------------------------------------------------------------------


def test_precipitation_accumulates_the_whole_window():
    dates = ["2017-12-30", "2017-12-31", "2018-01-01", "2018-01-02"]
    records = _daily(dates, precip=10.0)
    assert sum(r["precip_mm"] for r in records) == pytest.approx(40.0)


def test_degree_days_respect_profile_and_window():
    dates = ["2018-01-01", "2018-01-02", "2018-01-03"]
    records = [
        {"date": day, "temp_max_c": 30.0, "temp_min_c": 18.0} for day in dates
    ]
    gdd = thermal.accumulate_degree_days(records, PROFILE)
    assert gdd["days_used"] == 3
    assert gdd["degree_days_total"] > 0.0
    assert gdd["coverage"] == pytest.approx(1.0)


def test_degree_days_skip_missing_values_without_breaking_coverage():
    records = [
        {"date": "2018-01-01", "temp_max_c": 30.0, "temp_min_c": 18.0},
        {"date": "2018-01-02", "temp_max_c": None, "temp_min_c": None},
        {"date": "2018-01-03", "temp_max_c": 28.0, "temp_min_c": 16.0},
    ]
    gdd = thermal.accumulate_degree_days(records, PROFILE)
    assert gdd["days_used"] == 2
    assert gdd["coverage"] == pytest.approx(2.0 / 3.0)


def test_extreme_heat_is_counted_per_day():
    records = [
        {"date": "2018-01-01", "temp_max_c": 36.0, "temp_min_c": 25.0},
        {"date": "2018-01-02", "temp_max_c": 34.0, "temp_min_c": 26.0},
        {"date": "2018-01-03", "temp_max_c": None, "temp_min_c": 27.0},
    ]
    extreme = thermal.extreme_heat_days(records)
    assert extreme["extreme_heat_days"] == 1
    # o limiar noturno é 20 °C: as três noites com Tmin observada contam
    assert extreme["warm_nights"] == 3


def test_water_balance_is_sequential_and_bounded():
    monthly = [
        {"month": "2017-12", "precip_mm": 200.0, "etp_mm": 100.0},
        {"month": "2018-01", "precip_mm": 10.0, "etp_mm": 120.0},
        {"month": "2018-02", "precip_mm": 60.0, "etp_mm": 110.0},
    ]
    balance = water_balance.sequential_water_balance(monthly, cad_mm=100.0)
    valid = [row for row in balance if row.get("status") == "ok"]
    assert len(valid) == 3
    storage = [row["arm_mm"] for row in valid]
    assert all(0.0 <= value <= 100.0 + 1e-9 for value in storage)
    # excedente só aparece quando a chuva excede a ETP e o solo está cheio
    assert valid[0]["exc_mm"] > 0.0
    # a sequência importa: o segundo mês é de déficit e o armazenamento cai
    assert valid[1]["def_mm"] > 0.0
    assert storage[1] < storage[0]
    totals = water_balance.aggregate_water_balance(balance)
    assert totals["deficiency_total_mm"] >= 0.0
    assert totals["excess_total_mm"] >= 0.0


def test_deficit_grows_when_capacity_is_smaller():
    monthly = [
        {"month": f"2018-{m:02d}", "precip_mm": 40.0, "etp_mm": 110.0}
        for m in range(1, 7)
    ]
    small = water_balance.aggregate_water_balance(
        water_balance.sequential_water_balance(monthly, cad_mm=40.0)
    )
    large = water_balance.aggregate_water_balance(
        water_balance.sequential_water_balance(monthly, cad_mm=200.0)
    )
    assert small["deficiency_total_mm"] > large["deficiency_total_mm"]


def test_daily_to_monthly_recovers_every_month():
    dates = ["2017-12-30", "2017-12-31", "2018-01-01", "2018-01-31", "2018-02-01"]
    series = [
        {
            "date": day,
            "precip_mm": 10.0,
            "et0_mm": 4.0,
            "radiacao_mj_m2": 20.0,
            "temp_media_c": 25.0,
            "temp_max_c": 30.0,
            "temp_min_c": 20.0,
            "umidade_rel_pct": 70.0,
            "vento_kmh": 8.0,
        }
        for day in dates
    ]
    monthly = water_balance.daily_to_monthly(series)
    assert [row["month"] for row in monthly] == ["2017-12", "2018-01", "2018-02"]
    assert monthly[0]["precip_mm"] == pytest.approx(20.0)
    assert monthly[1]["precip_mm"] == pytest.approx(20.0)


# --------------------------------------------------------------------------
# vizinhos históricos (M1c)
# --------------------------------------------------------------------------


def test_haversine_matches_known_distance():
    distance = generalization._haversine_km(0.0, 0.0, 0.0, 1.0)
    assert float(distance) == pytest.approx(111.19, abs=0.02)


def _neighbor_rows():
    """Seis blocos × dois anos, um município por célula (mínimo para o TE)."""
    rows = []
    centres = [
        ("A", "11", -23.0, -51.0, 4000.0),
        ("B", "21", -22.0, -50.0, 5000.0),
        ("C", "31", -21.0, -49.0, 6000.0),
        ("D", "41", -20.0, -48.0, 7000.0),
        ("E", "51", -19.0, -47.0, 8000.0),
        ("F", "61", -18.0, -46.0, 9000.0),
    ]
    for block, code, lat, lon, level in centres:
        for offset, year in enumerate((2018, 2019)):
            rows.append(
                {
                    "ibge_code": code,
                    "spatial_block": block,
                    "state": f"UF{block}",
                    "year": year,
                    "yield_kg_ha": level + 100.0 * offset,
                    "latitude": lat,
                    "longitude": lon,
                }
            )
    return rows


def test_neighbor_holdout_never_uses_the_test_rows_own_yield():
    """Vazamento mais direto: a previsão de uma linha não pode depender do y dela.

    Cada linha é testada exatamente uma vez (na célula bloco × ano). Se a
    implementação usasse, mesmo por acidente, a produtividade do próprio
    município-ano de teste, alterar esse único valor moveria a previsão.
    """
    rows = _neighbor_rows()
    original = generalization.neighbor_holdout(rows, radius_km=500.0, min_neighbors=1)
    target = 4  # bloco B, 2018
    perturbed_rows = [dict(row) for row in rows]
    perturbed_rows[target]["yield_kg_ha"] += 1_000_000.0
    perturbed = generalization.neighbor_holdout(
        perturbed_rows, radius_km=500.0, min_neighbors=1
    )
    assert np.isclose(
        original["row_predictions"][target],
        perturbed["row_predictions"][target],
        atol=1e-9,
    )
    # o erro da linha muda, porque o y mudou
    assert perturbed["row_abs_errors"][target] > original["row_abs_errors"][target]


def test_neighbor_holdout_reports_fallback_when_no_neighbor_exists():
    rows = _neighbor_rows()
    result = generalization.neighbor_holdout(rows, radius_km=1.0, min_neighbors=3)
    assert result["status"] == "ok"
    assert result["fallback_state_share"] == pytest.approx(1.0)
    assert result["coverage_direct"] == pytest.approx(0.0)


def test_neighbor_holdout_is_reproducible():
    rows = _neighbor_rows()
    first = generalization.neighbor_holdout(rows, radius_km=500.0, min_neighbors=1)
    second = generalization.neighbor_holdout(rows, radius_km=500.0, min_neighbors=1)
    assert first["mae"] == pytest.approx(second["mae"])
    assert first["ci95"] == pytest.approx(second["ci95"])


def test_neighbor_holdout_requires_enough_blocks():
    rows = [dict(row, spatial_block="A") for row in _neighbor_rows()]
    result = generalization.neighbor_holdout(rows, radius_km=500.0, min_neighbors=1)
    assert result["status"] == "insufficient_groups"
    assert result["n_blocks"] == 1
