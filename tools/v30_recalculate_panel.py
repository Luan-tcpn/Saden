"""V3.0 — recálculo do balanço hídrico com CAD oficial (D96, D97).

Duas coisas acontecem aqui.

**1. Correção de borda da janela ZARC (D97).** O painel histórico seleciona os
dias com ``months[0] <= data <= months[-1]`` comparando strings ``"AAAA-MM"``
com ``"AAAA-MM-DD"``. Isso (i) inclui dias antes do início real da janela,
porque o início é arredondado para o dia 1º, e (ii) **exclui o mês final
inteiro**, porque ``"2017-12-01" > "2017-12"``. Em 28.282 das 40.990 linhas
(69%) o número de meses usados difere do número de meses listados.

O script calcula **as duas janelas**: ``historical`` (reproduz o painel) e
``corrected`` (meses completos). A reprodução da CAD=50 mm na janela
histórica é a prova de que o pipeline é fiel; a diferença entre as janelas
quantifica o defeito.

**2. Cenários de CAD por município.** Para a janela corrigida, recalcula o
balanço com 35/50/70 mm (cenários da V2.6) e com a CAD oficial de 0–60,
0–100 e 0–200 cm do próprio município (D96).

Uso:
    python tools/v30_recalculate_panel.py
"""

from __future__ import annotations

import bisect
import calendar
import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import cycle  # noqa: E402
from agroclimate import evapotranspiration as et_module  # noqa: E402
from agroclimate import water_balance as wb_module  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
CAD = os.path.join(MANIFESTS, "v30_cad_polygon.json")
OUT_JSON = os.path.join(MANIFESTS, "v30_balance_recalc.json")
OUT_CSV = os.path.join(PROCESSED, "v30_panel_cad.csv")

FIELDS = (
    "temp_max_c",
    "temp_min_c",
    "temp_media_c",
    "radiacao_mj_m2",
    "vento_kmh",
    "umidade_rel_pct",
    "pressao_kpa",
    "precip_mm",
)

SCENARIOS = ("v26_35", "v26_50", "v26_70", "cad_0_60", "cad_0_100", "cad_0_200")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_cad() -> dict[str, dict[str, float | None]]:
    data = json.load(open(CAD, encoding="utf-8"))
    out: dict[str, dict[str, float | None]] = {}
    for code, entry in data["municipalities"].items():
        out[code] = {scenario: entry.get(f"cad_0_{depth}_mm") for scenario, depth in
                     (("cad_0_60", 60), ("cad_0_100", 100), ("cad_0_200", 200))}
    return out


def load_centroids() -> dict[str, float]:
    """Latitude do centroide municipal (entra no cálculo de ET0)."""
    path = os.path.join(PROCESSED, "panel_municipalities.csv")
    out: dict[str, float] = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            latitude = _to_float(row.get("centroid_lat"))
            if latitude is not None:
                out[str(row["ibge_code"])] = latitude
    return out


def load_panel_rows() -> list[dict[str, Any]]:
    path = os.path.join(PROCESSED, "agroclimatic_productivity_panel.csv")
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("status")) != "paired_usable":
                continue
            if str(row.get("climate_source")) != "NASA-POWER":
                continue
            months = [m for m in str(row.get("zarc_window_months") or "").split(";") if m]
            if not months:
                continue
            rows.append(
                {
                    "ibge_code": str(row["ibge_code"]),
                    "crop": str(row["crop"]),
                    "safra": str(row.get("safra")),
                    "months": months,
                    "stored_deficiency": _to_float(row.get("deficiency_total_mm")),
                    "stored_excess": _to_float(row.get("excess_total_mm")),
                    "stored_et0": _to_float(row.get("et0_total_mm")),
                    "stored_precip": _to_float(row.get("precip_acumulada_mm")),
                    "stored_balance_months": row.get("balance_months"),
                    "yield_kg_ha": _to_float(row.get("yield_kg_ha")),
                    "harvest_year": row.get("harvest_year") or row.get("pam_reference_year"),
                    "state": row.get("state"),
                    "zarc_cycle": str(row.get("zarc_cycle") or ""),
                }
            )
    return rows


def load_climate(codes: list[str]) -> tuple[np.ndarray, list[str], dict[str, int]]:
    """Matrizes (município × dia) das variáveis necessárias."""
    index = {code: i for i, code in enumerate(codes)}
    path = os.path.join(PROCESSED, "climate_daily.csv")
    dates: list[str] = []
    day_index: dict[str, int] = {}
    capacity = 4000
    matrices = {field: np.full((len(codes), capacity), np.nan, dtype="float32") for field in FIELDS}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            code = str(row.get("ibge_code") or "")
            if code not in index or str(row.get("source")) != "NASA-POWER":
                continue
            day = str(row.get("date"))
            slot = day_index.get(day)
            if slot is None:
                slot = len(dates)
                if slot >= capacity:
                    capacity *= 2
                    for field in FIELDS:
                        padded = np.full((len(codes), capacity), np.nan, dtype="float32")
                        padded[:, :slot] = matrices[field][:, :slot]
                        matrices[field] = padded
                    capacity = matrices[FIELDS[0]].shape[1]
                day_index[day] = slot
                dates.append(day)
            position = index[code]
            for field in FIELDS:
                value = _to_float(row.get(field))
                if value is not None:
                    matrices[field][position, slot] = value
    n_days = len(dates)
    for field in FIELDS:
        matrices[field] = matrices[field][:, :n_days]
    return matrices, dates, index


def _select(dates: list[str], start: str, end: str) -> list[int]:
    return [i for i, day in enumerate(dates) if start <= day <= end]


def _balance(daily_records, cad_mm):
    monthly = wb_module.daily_to_monthly(daily_records)
    balance = wb_module.sequential_water_balance(monthly, cad_mm=cad_mm)
    return wb_module.aggregate_water_balance(balance)


def main() -> int:
    started = time.time()
    rows = load_panel_rows()
    codes = sorted({row["ibge_code"] for row in rows})
    print(f"linhas do painel: {len(rows)}; municípios: {len(codes)}", flush=True)
    cad = load_cad()
    centroids = load_centroids()
    matrices, dates, index = load_climate(codes)
    print(f"dias: {len(dates)}; clima carregado em {time.time()-started:.0f}s", flush=True)

    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_code[row["ibge_code"]].append(row)

    out_rows: list[dict[str, Any]] = []
    for position, code in enumerate(codes):
        latitude = centroids.get(code)
        if latitude is None:
            continue
        et_series = et_module.daily_et0_series(
            [
                {
                    "date": dates[day],
                    "temp_max_c": float(matrices["temp_max_c"][position, day]),
                    "temp_min_c": float(matrices["temp_min_c"][position, day]),
                    "temp_media_c": float(matrices["temp_media_c"][position, day]),
                    "radiacao_mj_m2": float(matrices["radiacao_mj_m2"][position, day]),
                    "vento_kmh": float(matrices["vento_kmh"][position, day]),
                    "umidade_rel_pct": float(matrices["umidade_rel_pct"][position, day]),
                    "pressao_kpa": float(matrices["pressao_kpa"][position, day]),
                }
                for day in range(len(dates))
                if np.isfinite(matrices["temp_max_c"][position, day])
            ],
            float(latitude),
            method="fao56_penman_monteith",
            elevation_m=None,
        )
        et_by_day = {item["date"]: item["et0_mm"] for item in et_series}
        et_dates = sorted(et_by_day)
        precip_by_day = {
            dates[day]: float(matrices["precip_mm"][position, day])
            for day in range(len(dates))
        }
        for row in by_code[code]:
            months = row["months"]
            hist_start, hist_end = cycle.window_bounds(months, corrected=False)
            corr_start, corr_end = cycle.window_bounds(months, corrected=True)
            hist_dates = [d for d in et_dates if hist_start <= d <= hist_end]
            corr_dates = [d for d in et_dates if corr_start <= d <= corr_end]
            if len(hist_dates) < 30 or len(corr_dates) < 30:
                continue
            hist_records = [
                {"date": d, "et0_mm": et_by_day[d], "precip_mm": precip_by_day.get(d)}
                for d in hist_dates
            ]
            corr_records = [
                {"date": d, "et0_mm": et_by_day[d], "precip_mm": precip_by_day.get(d)}
                for d in corr_dates
            ]
            hist_totals = _balance(hist_records, 50.0)
            entry: dict[str, Any] = {
                "ibge_code": code,
                "crop": row["crop"],
                "safra": row["safra"],
                "state": row["state"],
                "zarc_cycle": row["zarc_cycle"],
                "harvest_year": row["harvest_year"],
                "yield_kg_ha": row["yield_kg_ha"],
                "months": ";".join(months),
                "n_months_listed": len(months),
                "n_days_hist": len(hist_dates),
                "n_days_corr": len(corr_dates),
                "hist_precip_mm": sum(
                    (r["precip_mm"] or 0.0) for r in hist_records
                ),
                "corr_precip_mm": sum(
                    (r["precip_mm"] or 0.0) for r in corr_records
                ),
                "hist_et0_mm": sum(r["et0_mm"] for r in hist_records),
                "corr_et0_mm": sum(r["et0_mm"] for r in corr_records),
                "hist_def_cad50": hist_totals.get("deficiency_total_mm"),
                "hist_exc_cad50": hist_totals.get("excess_total_mm"),
                "stored_deficiency": row["stored_deficiency"],
                "stored_excess": row["stored_excess"],
                "stored_et0": row["stored_et0"],
                "stored_precip": row["stored_precip"],
            }
            for scenario in SCENARIOS:
                if scenario == "v26_35":
                    capacity = 35.0
                elif scenario == "v26_50":
                    capacity = 50.0
                elif scenario == "v26_70":
                    capacity = 70.0
                else:
                    capacity = cad.get(code, {}).get(scenario)
                if not capacity:
                    entry[f"corr_def_{scenario}"] = None
                    entry[f"corr_exc_{scenario}"] = None
                    continue
                totals = _balance(corr_records, float(capacity))
                entry[f"corr_def_{scenario}"] = totals.get("deficiency_total_mm")
                entry[f"corr_exc_{scenario}"] = totals.get("excess_total_mm")
                entry[f"cad_{scenario}_mm"] = float(capacity)
            out_rows.append(entry)
        if (position + 1) % 200 == 0:
            print(f"  {position+1}/{len(codes)} municípios", flush=True)

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    fields = list(out_rows[0].keys()) if out_rows else []
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in out_rows:
            writer.writerow(row)

    def _ratio(numerator, denominator):
        if numerator is None or not denominator:
            return None
        return numerator / denominator

    pairs = [
        (r["hist_def_cad50"], r["stored_deficiency"]) for r in out_rows
        if r["hist_def_cad50"] is not None and r["stored_deficiency"] is not None
    ]
    diffs = [abs(a - b) for a, b in pairs]
    # efeito da JANELA: mesma CAD (50 mm), janela histórica vs corrigida
    window_ratios = [
        (r["corr_def_v26_50"] / r["hist_def_cad50"])
        for r in out_rows
        if r["corr_def_v26_50"] is not None and r["hist_def_cad50"]
    ]
    # efeito da CAD: mesma janela (corrigida), 50 mm vs CAD oficial
    cad_effects: dict[str, dict[str, Any]] = {}
    for scenario in ("cad_0_60", "cad_0_100", "cad_0_200"):
        ratios = [
            (r[f"corr_def_{scenario}"] / r["corr_def_v26_50"])
            for r in out_rows
            if r.get(f"corr_def_{scenario}") is not None and r["corr_def_v26_50"]
        ]
        if not ratios:
            continue
        cad_effects[scenario] = {
            "n": len(ratios),
            "median_ratio": float(np.median(ratios)),
            "p10": float(np.quantile(ratios, 0.10)),
            "p90": float(np.quantile(ratios, 0.90)),
            "share_eliminated": float(np.mean([x == 0 for x in ratios])),
            "share_above_1": float(np.mean([x > 1.0 for x in ratios])),
        }
    payload = {
        "generated_at": _now(),
        "n_rows": len(out_rows),
        "n_municipalities": len({r["ibge_code"] for r in out_rows}),
        "reproduction": {
            "n_pairs": len(pairs),
            "n_exact": sum(1 for a, b in pairs if abs(a - b) < 1e-6),
            "max_abs_diff": max(diffs) if diffs else None,
            "median_abs_diff": float(np.median(diffs)) if diffs else None,
        },
        "window_defect": {
            "rows_with_last_month_dropped": sum(
                1 for r in out_rows if r["n_days_hist"] < r["n_days_corr"]
            ),
            "median_days_lost": float(
                np.median([r["n_days_corr"] - r["n_days_hist"] for r in out_rows])
            ),
            "median_precip_change_mm": float(
                np.median([r["corr_precip_mm"] - r["hist_precip_mm"] for r in out_rows])
            ),
            "median_et0_change_mm": float(
                np.median([r["corr_et0_mm"] - r["hist_et0_mm"] for r in out_rows])
            ),
            "deficit_ratio_corr_over_hist_cad50": {
                "n": len(window_ratios),
                "median": float(np.median(window_ratios)) if window_ratios else None,
                "p10": float(np.quantile(window_ratios, 0.10)) if window_ratios else None,
                "p90": float(np.quantile(window_ratios, 0.90)) if window_ratios else None,
            },
        },
        "cad_effect_at_fixed_window": cad_effects,
        "elapsed_s": round(time.time() - started, 1),
    }
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"painel recalculado: {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
