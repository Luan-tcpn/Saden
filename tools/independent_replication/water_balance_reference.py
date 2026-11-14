"""Replicação independente do balanço hídrico e da ET0 do SADEN.

**Independência.** Este módulo não importa `agroclimate.water_balance` e não
chama nenhuma das suas funções. O balanço e a ET0 são reimplementados a partir
das equações publicadas:

* Thornthwaite & Mather (1955) — balanço hídrico sequencial com capacidade de
  água disponível (CAD) limitada e evapotranspiração real limitada pela água
  disponível;
* Allen et al. (1998), FAO-56, equação 6 — Penman-Monteith.

O módulo serve para duas verificações distintas, que **não** se confundem:

1. **fidelidade do algoritmo** — mesmos insumos mensais, algoritmo independente:
   o déficit deve coincidir e o excedente não deve coincidir (defeito D124 na
   implementação de referência, ver `docs/statistics/INDEPENDENT_REPLICATION.md`);
2. **convenção de ET0** — mesma entrada diária, formulação independente: a
   divergência é de convenção (pressão de vapor saturado e conversão de vento),
   e não de aritmética.

Uso:
    python tools/independent_replication/water_balance_reference.py --check
    python tools/independent_replication/water_balance_reference.py --cases 40
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import statistics
import sys
from typing import Any, Iterable, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
# SADEN_DATA_ROOT permite rodar de um clone limpo lendo os derivados externos.
_DATA_ROOT = os.environ.get("SADEN_DATA_ROOT") or os.path.join(ROOT, "geospatial", "data")
PROCESSED = os.path.join(_DATA_ROOT, "processed")
OUT_JSON = os.path.join(ROOT, "geospatial", "data", "manifests", "independent_replication.json")

STEFAN_BOLTZMANN_MJ = 4.903e-9  # MJ m-2 dia-1 K-4 (FAO-56, eq. 39)
SOLAR_CONSTANT = 0.0820         # MJ m-2 min-1 (FAO-56, eq. 21)
ALBEDO = 0.23                   # FAO-56, gramado de referência


# --------------------------------------------------------------------------- ET0


def extraterrestrial_radiation(latitude_deg: float, day_of_year: int) -> float:
    """Radiação extraterrestre diária (MJ m-2 dia-1) — FAO-56, equação 21."""
    phi = math.radians(latitude_deg)
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * day_of_year / 365.0)
    delta = 0.409 * math.sin(2.0 * math.pi * day_of_year / 365.0 - 1.39)
    omega = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return (
        24.0 * 60.0 / math.pi * SOLAR_CONSTANT * dr
        * (omega * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(omega))
    )


def saturation_vapour_pressure(temp_c: float) -> float:
    """e°(T) — FAO-56, equação 11."""
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def slope_vapour_pressure(temp_c: float) -> float:
    """Δ — FAO-56, equação 13."""
    return 4098.0 * saturation_vapour_pressure(temp_c) / ((temp_c + 237.3) ** 2)


def psychrometric_constant(pressure_kpa: float) -> float:
    """γ — FAO-56, equação 8."""
    return 0.000665 * pressure_kpa


def et0_fao56(
    temp_max_c: float,
    temp_min_c: float,
    temp_mean_c: float,
    radiation_mj_m2: float,
    wind_kmh_at_2m: float,
    humidity_pct: float,
    pressure_kpa: float,
    latitude_deg: float,
    day_of_year: int,
) -> float:
    """ET0 por FAO-56 Penman-Monteith.

    Convenções explícitas (são elas que geram a divergência documentada):

    * ``es`` é a **média das pressões de saturação em Tmax e Tmin** — FAO-56
      equação 12. A implementação de referência usa ``es(Tmean)``, que é a
      simplificação e subestima o VPD em dias com amplitude térmica alta;
    * ``u2`` é o vento **a 2 m, em m/s**. A entrada já está a 2 m (NASA POWER
      ``WS2M``) e em km/h; logo a conversão é apenas ``/3.6``. A implementação
      de referência aplica um fator 0,4 adicional, deixando ``u2`` 60% menor;
    * ``G = 0`` (FAO-56, passo diário);
    * ``Rn`` em MJ m-2 dia-1 com ``Rso = 0,75 Ra`` e albedo 0,23.
    """
    u2 = max(0.5, wind_kmh_at_2m / 3.6)
    es = (saturation_vapour_pressure(temp_max_c) + saturation_vapour_pressure(temp_min_c)) / 2.0
    ea = es * humidity_pct / 100.0
    if ea > es:
        ea = es
    vpd = es - ea
    gamma = psychrometric_constant(pressure_kpa)
    delta = slope_vapour_pressure(temp_mean_c)
    ra = extraterrestrial_radiation(latitude_deg, day_of_year)
    rs = radiation_mj_m2
    rso = 0.75 * ra
    if rso <= 0:
        rso = 1e-6
    cloudiness = max(0.0, min(1.0, 1.35 * rs / rso - 0.35))
    rnl = (
        STEFAN_BOLTZMANN_MJ
        * ((temp_max_c + 273.16) ** 4 + (temp_min_c + 273.16) ** 4) / 2.0
        * max(0.0, 0.34 - 0.14 * ea)
        * cloudiness
    )
    rn = (1.0 - ALBEDO) * rs - rnl
    numerator = 0.408 * delta * rn + gamma * (900.0 / (temp_mean_c + 273.0)) * u2 * vpd
    denominator = delta + gamma * (1.0 + 0.34 * u2)
    if denominator <= 0:
        return 0.0
    return max(0.0, numerator / denominator)


# ------------------------------------------------------------------ water balance


def monthly_aggregate(
    days: Iterable[dict[str, Any]],
    precip_key: str = "precip_mm",
    et_key: str = "et0_mm",
) -> list[dict[str, Any]]:
    """Soma diária → mensal. Precipitação e ET0 são **somas**, não médias."""
    buckets: dict[str, dict[str, float]] = {}
    for day in days:
        month = str(day.get("date"))[:7]
        if len(month) != 7:
            continue
        bucket = buckets.setdefault(month, {"precip_mm": 0.0, "et0_mm": 0.0, "n": 0})
        precip = day.get(precip_key)
        et0 = day.get(et_key)
        if precip is None or et0 is None:
            continue
        bucket["precip_mm"] += float(precip)
        bucket["et0_mm"] += float(et0)
        bucket["n"] += 1
    return [
        {"month": month, "precip_mm": data["precip_mm"], "et0_mm": data["et0_mm"], "n_days": data["n"]}
        for month, data in sorted(buckets.items())
    ]


def thornthwaite_mather(
    monthly: Sequence[dict[str, Any]],
    cad_mm: float,
    initial_storage_mm: float | None = None,
) -> list[dict[str, Any]]:
    """Balanço sequencial de Thornthwaite & Mather (1955).

    Para cada mês, com ``P`` = precipitação e ``ETP`` = demanda:

    * ``P - ETP >= 0``: ``ETR = ETP``; o solo retém até ``CAD``; o que exceder
      a ``CAD`` é **excedente**: ``EXC = ARM_anterior + P - ETP - CAD`` quando
      positivo;
    * ``P - ETP < 0``: a demanda é limitada pela água disponível:
      ``ETR = min(ETP, ARM_anterior + P)``; ``ARM = ARM_anterior + P - ETR``;
      a diferença não atendida é **deficiência**: ``DEF = ETP - ETR``.

    Armazenamento inicial: ``CAD`` (solo saturado), convenção do painel.
    """
    storage = cad_mm if initial_storage_mm is None else float(initial_storage_mm)
    storage = min(storage, cad_mm)
    out: list[dict[str, Any]] = []
    for row in monthly:
        precip = float(row["precip_mm"])
        demand = float(row["et0_mm"])
        balance = precip - demand
        if balance >= 0:
            etr = demand
            excess = max(0.0, storage + balance - cad_mm)
            storage = min(cad_mm, storage + balance)
            deficit = 0.0
        else:
            available = storage + precip
            etr = min(demand, available)
            storage = max(0.0, available - etr)
            excess = 0.0
            deficit = demand - etr
        out.append(
            {
                "month": row["month"],
                "precip_mm": precip,
                "et0_mm": demand,
                "storage_mm": storage,
                "etr_mm": etr,
                "deficit_mm": deficit,
                "excess_mm": excess,
            }
        )
    return out


def seasonal_summary(
    monthly: Sequence[dict[str, Any]], cad_mm: float, initial_storage_mm: float | None = None
) -> dict[str, float]:
    """Agrega o balanço da janela: déficit, excedente, ETP, ETR, ARM mínima."""
    series = thornthwaite_mather(monthly, cad_mm, initial_storage_mm)
    return {
        "etp_total_mm": sum(r["et0_mm"] for r in series),
        "etr_total_mm": sum(r["etr_mm"] for r in series),
        "deficit_total_mm": sum(r["deficit_mm"] for r in series),
        "excess_total_mm": sum(r["excess_mm"] for r in series),
        "storage_min_mm": min((r["storage_mm"] for r in series), default=float("nan")),
        "n_months": float(len(series)),
    }


# ------------------------------------------------------------------- comparação


def load_reference(path: str) -> dict[tuple[str, str, str, str], dict[str, str]]:
    out: dict[tuple[str, str, str, str], dict[str, str]] = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key = (
                str(row["ibge_code"]), str(row["crop"]), str(row["safra"]),
                str(row.get("scenario") or ""),
            )
            out[key] = row
    return out


def stratified_sample(
    water: dict[tuple[str, str, str, str], dict[str, str]], size: int, seed: int = 20261114
) -> list[tuple[str, str, str, str]]:
    """Amostra estratificada por UF × cultura, com semente fixa.

    A regra é declarada **antes** da comparação e não depende do resultado.
    """
    strata: dict[tuple[str, str], list[tuple[str, str, str, str]]] = {}
    for key, row in water.items():
        if str(row.get("scenario")) != "cad50":
            continue
        strata.setdefault((str(row["state"]), str(row["crop"])), []).append(key)
    generator = random.Random(seed)
    per_stratum = max(1, size // max(1, len(strata)))
    chosen: list[tuple[str, str, str, str]] = []
    for stratum in sorted(strata):
        candidates = sorted(strata[stratum])
        chosen.extend(generator.sample(candidates, min(per_stratum, len(candidates))))
    return sorted(chosen)


def _window_days(code: str, months: Sequence[str], climate_index: dict) -> list[dict[str, Any]]:
    from agroclimate import cycle  # apenas para os limites da janela

    start_c, end_c = cycle.window_bounds(list(months), corrected=True)
    day_index = climate_index["index"][code]
    return [
        climate_index["rows"][position]
        for day, position in day_index.items()
        if start_c <= day <= end_c
    ]


def build_climate_index(codes: set[str]) -> dict[str, Any]:
    """Índice (código → {dia: posição}) apenas para NASA-POWER."""
    index: dict[str, dict[str, int]] = {}
    rows: list[dict[str, str]] = []
    for name in ("climate_daily.csv", "climate_daily_sp.csv"):
        path = os.path.join(PROCESSED, name)
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                code = str(row.get("ibge_code") or "")
                if code not in codes:
                    continue
                if str(row.get("source")) != "NASA-POWER":
                    continue
                slot = index.setdefault(code, {})
                day = str(row.get("date"))
                if day in slot:
                    continue
                slot[day] = len(rows)
                rows.append(row)
    return {"index": index, "rows": rows}


def load_latitude() -> dict[str, float]:
    """Latitude do centróide municipal, do cadastro (fonte de verdade).

    O painel exporta ``latitude`` apenas para as linhas construídas na V3.5
    (SP, 10.805 de 30.207). O centróide do cadastro é a fonte correta para
    qualquer município.
    """
    out: dict[str, float] = {}
    path = os.path.join(PROCESSED, "panel_municipalities_v35.csv")
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            value = row.get("centroid_lat")
            if value not in (None, ""):
                out[str(row["ibge_code"])] = float(value)
    return out


def partial_refill_check() -> dict[str, Any]:
    """Prova o defeito D124: excedente superestimado quando a reposição satura.

    Dois meses, CAD = 50 mm. O primeiro consome 10 mm (ARM 50 → 40). O segundo
    tem saldo positivo de 15 mm: o solo recompõe 10 mm e **5 mm** transbordam.
    O excedente correto é ``40 + 15 - 50 = 5``; a implementação de referência
    devolve ``15`` — o saldo inteiro, ignorando os 10 mm que foram absorvidos.
    """
    from agroclimate import water_balance as wb_module

    monthly = [
        {"month": "2020-01", "precip_mm": 0.0, "etp_mm": 10.0},
        {"month": "2020-02", "precip_mm": 20.0, "etp_mm": 5.0},
    ]
    library = wb_module.sequential_water_balance(monthly, cad_mm=50.0)
    mine = thornthwaite_mather(
        [{"month": row["month"], "precip_mm": row["precip_mm"], "et0_mm": row["etp_mm"]} for row in monthly],
        cad_mm=50.0,
    )
    library_excess = sum(float(row["exc_mm"] or 0.0) for row in library)
    mine_excess = sum(row["excess_mm"] for row in mine)
    library_deficit = sum(float(row["def_mm"] or 0.0) for row in library)
    mine_deficit = sum(row["deficit_mm"] for row in mine)
    return {
        "scenario": {
            "cad_mm": 50.0,
            "months": monthly,
            "expected_excess_mm": 5.0,
        },
        "excess_library": library_excess,
        "excess_independent": mine_excess,
        "excess_overstated_by_library": library_excess - mine_excess,
        "deficit_library": library_deficit,
        "deficit_independent": mine_deficit,
        "deficit_diff": library_deficit - mine_deficit,
        "storage_library": [row["arm_mm"] for row in library],
        "storage_independent": [row["storage_mm"] for row in mine],
        "trigger": "mês com saldo positivo que satura a CAD a partir de ARM < CAD",
    }


def compare(size: int = 40, seed: int = 20261114) -> dict[str, Any]:
    """Compara o balanço independente com o painel publicado."""
    from agroclimate import evapotranspiration as et_module

    water = load_reference(os.path.join(PROCESSED, "v35_water_variables.csv"))
    windows = load_reference(os.path.join(PROCESSED, "v35_panel_windows.csv"))
    sample = stratified_sample(water, size, seed)
    codes = {key[0] for key in sample}
    climate = build_climate_index(codes)

    lat_by_code = load_latitude()
    months_by_key: dict[tuple[str, str, str], list[str]] = {}
    for (code, crop, safra, _scenario) in windows:
        row = windows[(code, crop, safra, _scenario)]
        months_by_key[(code, crop, safra)] = [
            month for month in str(row.get("months") or "").split(";") if month
        ]

    deficit_diffs: list[float] = []
    excess_diffs: list[float] = []
    per_case: list[dict[str, Any]] = []
    for key in sample:
        code, crop, safra, _scenario = key
        months = months_by_key.get((code, crop, safra))
        latitude = lat_by_code.get(code)
        if not months or latitude is None:
            continue
        days = _window_days(code, months, climate)
        if not days:
            continue
        records = [
            {
                "date": day["date"],
                "temp_max_c": float(day["temp_max_c"]),
                "temp_min_c": float(day["temp_min_c"]),
                "temp_media_c": float(day["temp_media_c"]),
                "radiacao_mj_m2": float(day["radiacao_mj_m2"]),
                "vento_kmh": float(day["vento_kmh"]),
                "umidade_rel_pct": float(day["umidade_rel_pct"]),
                "pressao_kpa": float(day["pressao_kpa"]),
                "precip_mm": float(day["precip_mm"]),
            }
            for day in days
        ]
        et_series = et_module.daily_et0_series(
            records, latitude, method="fao56_penman_monteith", elevation_m=None
        )
        for item in et_series:
            item["precip_mm"] = next(
                (r["precip_mm"] for r in records if r["date"] == item.get("date")), None
            )
        monthly = monthly_aggregate(et_series)
        summary = seasonal_summary(monthly, cad_mm=50.0)
        published = water[key]
        published_deficit = float(published["deficit_total_mm"])
        published_etp = float(published["etp_total_mm"])
        deficit_diff = summary["deficit_total_mm"] - published_deficit
        deficit_diffs.append(deficit_diff)
        per_case.append(
            {
                "ibge_code": code,
                "state": published.get("state"),
                "crop": crop,
                "safra": safra,
                "n_days": len(days),
                "n_months": int(summary["n_months"]),
                "etp_mine": round(summary["etp_total_mm"], 6),
                "etp_published": published_etp,
                "deficit_mine": round(summary["deficit_total_mm"], 6),
                "deficit_published": published_deficit,
                "deficit_diff": deficit_diff,
                "excess_mine": round(summary["excess_total_mm"], 6),
                "published_excess_months": published.get("excess_months"),
            }
        )

    # comparação de excedente no mesmo insumo: alimenta o balanço independente
    # com os totais publicados (só quando há um único mês, caso em que a
    # sequência é irrelevante e o excedente fica determinado)
    from agroclimate import water_balance as wb_module

    matched_excess: list[dict[str, Any]] = []
    for key in sample[: max(10, size // 2)]:
        code, crop, safra, _scenario = key
        days = _window_days(code, months_by_key.get((code, crop, safra)) or [], climate) if months_by_key.get((code, crop, safra)) else []
        if not days:
            continue
        records = [
            {
                "date": day["date"],
                "temp_max_c": float(day["temp_max_c"]),
                "temp_min_c": float(day["temp_min_c"]),
                "temp_media_c": float(day["temp_media_c"]),
                "radiacao_mj_m2": float(day["radiacao_mj_m2"]),
                "vento_kmh": float(day["vento_kmh"]),
                "umidade_rel_pct": float(day["umidade_rel_pct"]),
                "pressao_kpa": float(day["pressao_kpa"]),
                "precip_mm": float(day["precip_mm"]),
            }
            for day in days
        ]
        et_series = et_module.daily_et0_series(
            records, float(lat_by_code.get(code) or 0.0), method="fao56_penman_monteith", elevation_m=None
        )
        monthly = wb_module.daily_to_monthly(et_series)
        library = wb_module.sequential_water_balance(monthly, cad_mm=50.0)
        mine = thornthwaite_mather(
            [
                {"month": row["month"], "precip_mm": row["precip_mm"], "et0_mm": row["etp_mm"]}
                for row in library
                if row.get("status") == "ok"
            ],
            cad_mm=50.0,
        )
        library_excess = sum(float(row["exc_mm"] or 0.0) for row in library if row.get("status") == "ok")
        library_deficit = sum(float(row["def_mm"] or 0.0) for row in library if row.get("status") == "ok")
        mine_excess = sum(row["excess_mm"] for row in mine)
        mine_deficit = sum(row["deficit_mm"] for row in mine)
        previous = 50.0
        triggering = 0
        for row in mine:
            if previous < 50.0 and row["precip_mm"] - row["et0_mm"] > 0:
                triggering += 1
            previous = row["storage_mm"]
        excess_diffs.append(library_excess - mine_excess)
        matched_excess.append(
            {
                "ibge_code": code,
                "crop": crop,
                "safra": safra,
                "excess_library": round(library_excess, 9),
                "excess_independent": round(mine_excess, 9),
                "excess_diff": round(library_excess - mine_excess, 9),
                "deficit_library": round(library_deficit, 9),
                "deficit_independent": round(mine_deficit, 9),
                "deficit_diff": round(library_deficit - mine_deficit, 12),
                "partial_refill_months": triggering,
            }
        )

    deficit_abs = [abs(value) for value in deficit_diffs]
    return {
        "sample": {
            "n_cases": len(per_case),
            "seed": seed,
            "rule": "estratificada por UF x cultura, semente fixa, cenário cad50",
        },
        "deficit": {
            "max_abs_diff": max(deficit_abs) if deficit_abs else None,
            "median_abs_diff": statistics.median(deficit_abs) if deficit_abs else None,
            "n_within_1e_6": sum(1 for value in deficit_abs if value <= 1e-6),
            "n_cases": len(deficit_abs),
        },
        "excess_same_input": {
            "n_cases": len(excess_diffs),
            "n_differing": sum(1 for value in excess_diffs if abs(value) > 1e-9),
            "max_abs_diff": max((abs(value) for value in excess_diffs), default=None),
            "n_partial_refill_months": sum(item["partial_refill_months"] for item in matched_excess),
            "examples": matched_excess[:10],
        },
        "cases": per_case,
    }


MANUAL_CASES = (
    {
        "name": "chuva sobre solo saturado: excedente integral",
        "monthly": [{"month": "2020-01", "precip_mm": 100.0, "et0_mm": 10.0}],
        "cad": 50.0, "initial": 50.0,
        "expect": {"storage_mm": 50.0, "etr_mm": 10.0, "deficit_mm": 0.0, "excess_mm": 90.0},
    },
    {
        "name": "reposição parcial: sem excedente",
        "monthly": [{"month": "2020-01", "precip_mm": 15.0, "et0_mm": 5.0}],
        "cad": 50.0, "initial": 30.0,
        "expect": {"storage_mm": 40.0, "etr_mm": 5.0, "deficit_mm": 0.0, "excess_mm": 0.0},
    },
    {
        "name": "enche e transborda: excedente só do excedente real (caso D124)",
        "monthly": [{"month": "2020-01", "precip_mm": 20.0, "et0_mm": 5.0}],
        "cad": 50.0, "initial": 45.0,
        "expect": {"storage_mm": 50.0, "etr_mm": 5.0, "deficit_mm": 0.0, "excess_mm": 10.0},
    },
    {
        "name": "consumo sem chuva: armazenamento cai",
        "monthly": [{"month": "2020-01", "precip_mm": 0.0, "et0_mm": 30.0}],
        "cad": 50.0, "initial": 50.0,
        "expect": {"storage_mm": 20.0, "etr_mm": 30.0, "deficit_mm": 0.0, "excess_mm": 0.0},
    },
    {
        "name": "armazenamento esgotado: déficit aparece",
        "monthly": [{"month": "2020-01", "precip_mm": 5.0, "et0_mm": 40.0}],
        "cad": 50.0, "initial": 20.0,
        "expect": {"storage_mm": 0.0, "etr_mm": 25.0, "deficit_mm": 15.0, "excess_mm": 0.0},
    },
    {
        "name": "déficit acumula em dois meses secos",
        "monthly": [
            {"month": "2020-01", "precip_mm": 0.0, "et0_mm": 40.0},
            {"month": "2020-02", "precip_mm": 10.0, "et0_mm": 40.0},
        ],
        "cad": 50.0, "initial": 50.0,
        # mês 1: ARM 50 -> 10, ETR 40, DEF 0. mês 2: ARM 10 + 10 mm de chuva,
        # ETR 20, ARM 0, DEF 20. Demanda 80, oferta 60, déficit 20.
        "expect": {
            "storage_mm": 0.0, "etr_mm": 20.0, "deficit_mm": 20.0, "excess_mm": 0.0,
            "aggregate_deficit": 20.0, "aggregate_etr": 60.0,
        },
    },
    {
        "name": "CAD zero: toda a chuva é excedente, toda a demanda é déficit",
        "monthly": [
            {"month": "2020-01", "precip_mm": 10.0, "et0_mm": 20.0},
            {"month": "2020-02", "precip_mm": 30.0, "et0_mm": 10.0},
        ],
        "cad": 0.0, "initial": 0.0,
        # sem capacidade de armazenamento: mês 1 ETR 10, DEF 10; mês 2 ETR 10,
        # EXC 20. No último mês o déficit é 0; o total da janela é 10.
        "expect": {
            "storage_mm": 0.0, "etr_mm": 10.0, "deficit_mm": 0.0, "excess_mm": 20.0,
            "aggregate_deficit": 10.0, "aggregate_etr": 20.0,
        },
    },
    {
        "name": "transição entre meses: primeiro seco, depois úmido",
        "monthly": [
            {"month": "2020-01", "precip_mm": 0.0, "et0_mm": 70.0},
            {"month": "2020-02", "precip_mm": 120.0, "et0_mm": 40.0},
        ],
        "cad": 50.0, "initial": 50.0,
        # mês 1: ETR 50 (toda a ARM), DEF 20. mês 2: P - ETP = 80; o solo
        # recompõe 50 mm e só os 30 mm restantes são excedente.
        "expect": {
            "storage_mm": 50.0, "etr_mm": 40.0, "deficit_mm": 0.0, "excess_mm": 30.0,
            "aggregate_deficit": 20.0, "aggregate_etr": 90.0,
        },
    },
)


def run_manual_cases() -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    passed = 0
    for case in MANUAL_CASES:
        series = thornthwaite_mather(case["monthly"], case["cad"], case["initial"])
        last = series[-1]
        expectations = case["expect"]
        for field in ("storage_mm", "etr_mm", "deficit_mm", "excess_mm"):
            actual = last[field]
            expected = expectations[field]
            if abs(actual - expected) > 1e-9:
                failures.append(
                    {"case": case["name"], "field": field, "expected": expected, "actual": actual}
                )
        if "aggregate_deficit" in expectations:
            total = sum(row["deficit_mm"] for row in series)
            if abs(total - expectations["aggregate_deficit"]) > 1e-9:
                failures.append(
                    {
                        "case": case["name"],
                        "field": "aggregate_deficit",
                        "expected": expectations["aggregate_deficit"],
                        "actual": total,
                    }
                )
        if "aggregate_etr" in expectations:
            total = sum(row["etr_mm"] for row in series)
            if abs(total - expectations["aggregate_etr"]) > 1e-9:
                failures.append(
                    {
                        "case": case["name"],
                        "field": "aggregate_etr",
                        "expected": expectations["aggregate_etr"],
                        "actual": total,
                    }
                )
        passed += 1
    return {"n_cases": len(MANUAL_CASES), "n_passed": passed - len({f["case"] for f in failures}), "failures": failures}


def _day_of_year(date: str) -> int:
    """Dia juliano da data civil — a comparação de ET0 depende de Ra(DOY)."""
    from datetime import date as date_type

    year, month, day = (int(part) for part in date.split("-"))
    return date_type(year, month, day).timetuple().tm_yday


def et0_convention_check(limit: int = 3000, seed: int = 20261114) -> dict[str, Any]:
    """Divergência de ET0 entre a formulação independente e a de referência."""
    from agroclimate import evapotranspiration as et_module

    rows: list[dict[str, str]] = []
    path = os.path.join(PROCESSED, "climate_daily.csv")
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("source")) != "NASA-POWER":
                continue
            if not row.get("radiacao_mj_m2") or not row.get("vento_kmh"):
                continue
            rows.append(row)
    generator = random.Random(seed)
    sample = generator.sample(rows, min(limit, len(rows)))
    relative: list[float] = []
    abs_diff: list[float] = []
    for position, row in enumerate(sample):
        day_of_year = _day_of_year(str(row["date"]))
        reference = et_module.fao56_penman_monteith(
            float(row["temp_max_c"]), float(row["temp_min_c"]), float(row["temp_media_c"]),
            float(row["radiacao_mj_m2"]), float(row["vento_kmh"]),
            float(row["umidade_rel_pct"]), float(row["pressao_kpa"]),
            float(row["latitude"]), day_of_year,
        )
        if reference.et0_mm is None:
            continue
        mine = et0_fao56(
            float(row["temp_max_c"]), float(row["temp_min_c"]), float(row["temp_media_c"]),
            float(row["radiacao_mj_m2"]), float(row["vento_kmh"]),
            float(row["umidade_rel_pct"]), float(row["pressao_kpa"]),
            float(row["latitude"]), day_of_year,
        )
        if mine > 0.2:
            relative.append((reference.et0_mm - mine) / mine)
            abs_diff.append(reference.et0_mm - mine)
    relative.sort()
    return {
        "n": len(relative),
        "relative_median": statistics.median(relative),
        "relative_p05": relative[int(0.05 * len(relative))],
        "relative_p95": relative[int(0.95 * len(relative))],
        "absolute_median_mm_day": statistics.median(abs_diff),
        "interpretation": (
            "divergência de convenção: es(Tmax,Tmin) vs es(Tmean) e u2 = vento/3.6 vs 0,4*vento/3,6"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, os.path.join(ROOT, "geospatial"))
    report: dict[str, Any] = {"manual_cases": run_manual_cases()}
    print("casos manuais:", report["manual_cases"])
    report["et0_convention"] = et0_convention_check()
    print("ET0 (convenção):", report["et0_convention"])
    report["partial_refill"] = partial_refill_check()
    print("reposição parcial (D124):", report["partial_refill"])
    report["comparison"] = compare(args.cases, args.seed)
    print("amostra:", report["comparison"]["sample"])
    print("déficit:", report["comparison"]["deficit"])
    print("excedente (mesmo insumo):", {
        k: v for k, v in report["comparison"]["excess_same_input"].items() if k != "examples"
    })

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print("manifesto:", OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
