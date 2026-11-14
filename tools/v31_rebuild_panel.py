"""V3.1 — reconstrução de TODAS as variáveis ambientais da janela (D100).

O defeito D97 (o painel perdia o mês final da janela ZARC) não afeta só o
balanço hídrico: afeta **toda** variável agregada dentro da janela —
precipitação, dias de chuva/secos, médias e extremos de temperatura, radiação,
umidade, vento, graus-dia, calor extremo e o balanço.

Este script recalcula as duas janelas para cada linha analítica:

* ``legacy`` — reproduz a seleção histórica (início no dia 1º, último mês
  excluído). Serve para **provar** que o pipeline é fiel ao painel publicado
  antes de qualquer correção;
* ``corrected`` — meses completos.

Cada variável é calculada com a **mesma função** que o painel usa
(`thermal.accumulate_degree_days`, `thermal.heat_wave_events`,
`thermal.extreme_heat_days`, `water_balance.*`), e não com uma reimplementação.

Uso:
    python tools/v31_rebuild_panel.py
"""

from __future__ import annotations

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
from agroclimate import thermal  # noqa: E402
from agroclimate import water_balance as wb_module  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
CAD = os.path.join(MANIFESTS, "v30_cad_polygon.json")
OUT_CSV = os.path.join(PROCESSED, "v31_panel_windows.csv")
OUT_JSON = os.path.join(MANIFESTS, "v31_window_rebuild.json")

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

PROFILE_BY_CROP = {
    "soja": "soja_gilmore",
    "milho": "milho_embrapa",
    "milho_2": "milho_embrapa",
}

CAD_SCENARIOS = {
    "cad_0_60": 60,
    "cad_0_100": 100,
    "cad_0_200": 200,
}

STORED_FIELDS = {
    "precip_acumulada_mm": "precip_acumulada_mm",
    "temp_media_c": "temp_media_c",
    "degree_days_total": "degree_days_total",
    "extreme_heat_days": "extreme_heat_days",
    "et0_total_mm": "et0_total_mm",
    "deficiency_total_mm": "deficiency_total_mm",
    "excess_total_mm": "excess_total_mm",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_cad() -> dict[str, dict[str, float | None]]:
    data = json.load(open(CAD, encoding="utf-8"))
    return {
        code: {
            name: entry.get(f"cad_0_{depth}_mm")
            for name, depth in CAD_SCENARIOS.items()
        }
        for code, entry in data["municipalities"].items()
    }


def load_centroids() -> dict[str, float]:
    path = os.path.join(PROCESSED, "panel_municipalities.csv")
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            value = _num(row.get("centroid_lat"))
            if value is not None:
                out[str(row["ibge_code"])] = value
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
            record = {
                "ibge_code": str(row["ibge_code"]),
                "crop": str(row["crop"]),
                "safra": str(row.get("safra")),
                "months": months,
                "state": row.get("state"),
                "zarc_cycle": str(row.get("zarc_cycle") or ""),
                "harvest_year": row.get("harvest_year") or row.get("pam_reference_year"),
                "yield_kg_ha": _num(row.get("yield_kg_ha")),
                "stored": {
                    key: _num(row.get(column)) for key, column in STORED_FIELDS.items()
                },
            }
            rows.append(record)
    return rows


def load_climate(codes: list[str]):
    index = {code: i for i, code in enumerate(codes)}
    path = os.path.join(PROCESSED, "climate_daily.csv")
    dates: list[str] = []
    day_index: dict[str, int] = {}
    capacity = 4000
    matrices = {
        field: np.full((len(codes), capacity), np.nan, dtype="float32")
        for field in FIELDS
    }
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
                day_index[day] = slot
                dates.append(day)
            position = index[code]
            for field in FIELDS:
                value = _num(row.get(field))
                if value is not None:
                    matrices[field][position, slot] = value
    n_days = len(dates)
    for field in FIELDS:
        matrices[field] = matrices[field][:, :n_days]
    return matrices, dates, index


def _window_records(dates, day_arrays, land, window_days, latitude):
    """Registros diários do recorte + ET0, no formato que as funções esperam."""
    records = []
    for day in window_days:
        record = {"date": dates[day]}
        for field, array in day_arrays.items():
            value = float(array[day])
            record[field] = value if np.isfinite(value) else None
        records.append(record)
    return records


def _aggregate(records, profile, latitude, cad_mm: float | None, with_balance: bool):
    """Todas as variáveis ambientais de uma janela, com as funções do painel."""
    precip = [r["precip_mm"] for r in records if r["precip_mm"] is not None]
    tmean = [r["temp_media_c"] for r in records if r["temp_media_c"] is not None]
    tmax = [r["temp_max_c"] for r in records if r["temp_max_c"] is not None]
    tmin = [r["temp_min_c"] for r in records if r["temp_min_c"] is not None]
    rad = [r["radiacao_mj_m2"] for r in records if r["radiacao_mj_m2"] is not None]
    humidity = [r["umidade_rel_pct"] for r in records if r["umidade_rel_pct"] is not None]
    wind = [r["vento_kmh"] for r in records if r["vento_kmh"] is not None]

    def mean(values):
        return sum(values) / len(values) if values else None

    out: dict[str, Any] = {
        "n_days": len(records),
        "precip_acumulada_mm": sum(precip) if precip else None,
        "precip_media_diaria_mm": mean(precip),
        "dias_com_chuva": sum(1 for v in precip if v > 0) if precip else None,
        "dias_secos": sum(1 for v in precip if v == 0) if precip else None,
        "temp_media_c": mean(tmean),
        "temp_max_media_c": mean(tmax),
        "temp_min_media_c": mean(tmin),
        "temp_max_abs_c": max(tmax) if tmax else None,
        "temp_min_abs_c": min(tmin) if tmin else None,
        "radiacao_media_mj_m2": mean(rad),
        "umidade_rel_media_pct": mean(humidity),
        "vento_media_kmh": mean(wind),
    }
    if profile is not None:
        gdd = thermal.accumulate_degree_days(
            [
                {
                    "date": r["date"],
                    "temp_max_c": r["temp_max_c"],
                    "temp_min_c": r["temp_min_c"],
                }
                for r in records
            ],
            profile,
        )
        out["degree_days_total"] = gdd["degree_days_total"]
        out["degree_days_mean"] = gdd["degree_days_mean"]
        out["degree_days_days_used"] = gdd["days_used"]
        out["degree_days_coverage"] = gdd["coverage"]
        event = thermal.heat_wave_events(
            [{"date": r["date"], "temp_max_c": r["temp_max_c"]} for r in records],
            threshold_c=35.0,
        )
        out["heat_wave_events"] = event["n_events"]
        out["heat_wave_days"] = event["total_days"]
        extreme = thermal.extreme_heat_days(
            [
                {
                    "date": r["date"],
                    "temp_max_c": r["temp_max_c"],
                    "temp_min_c": r["temp_min_c"],
                }
                for r in records
            ]
        )
        out["extreme_heat_days"] = extreme["extreme_heat_days"]
        out["warm_nights"] = extreme["warm_nights"]
    if latitude is not None:
        et_series = et_module.daily_et0_series(
            [
                {
                    "date": r["date"],
                    "temp_max_c": r["temp_max_c"],
                    "temp_min_c": r["temp_min_c"],
                    "temp_media_c": r["temp_media_c"],
                    "radiacao_mj_m2": r["radiacao_mj_m2"],
                    "vento_kmh": r["vento_kmh"],
                    "umidade_rel_pct": r["umidade_rel_pct"],
                    "pressao_kpa": r["pressao_kpa"],
                }
                for r in records
            ],
            float(latitude),
            method="fao56_penman_monteith",
            elevation_m=None,
        )
        by_date = {r["date"]: r for r in records}
        for item in et_series:
            source = by_date.get(str(item.get("date")))
            if source is not None:
                item["precip_mm"] = source.get("precip_mm")
        values = [item["et0_mm"] for item in et_series if item.get("et0_mm") is not None]
        out["et0_total_mm"] = sum(values) if values else None
        out["et0_days"] = len(values)
        out["et0_mean_mm_dia"] = mean(values)
        if with_balance and cad_mm:
            monthly = wb_module.daily_to_monthly(et_series)
            balance = wb_module.sequential_water_balance(monthly, cad_mm=float(cad_mm))
            totals = wb_module.aggregate_water_balance(balance)
            out["etp_total_mm"] = totals["etp_total_mm"]
            out["etr_total_mm"] = totals["etr_total_mm"]
            out["deficiency_total_mm"] = totals["deficiency_total_mm"]
            out["excess_total_mm"] = totals["excess_total_mm"]
            out["storage_final_mm"] = totals["storage_final_mm"]
            out["balance_months"] = totals["months"]
    return out


def main() -> int:
    started = time.time()
    rows = load_panel_rows()
    codes = sorted({row["ibge_code"] for row in rows})
    cad = load_cad()
    centroids = load_centroids()
    print(f"linhas: {len(rows)}; municípios: {len(codes)}", flush=True)
    matrices, dates, index = load_climate(codes)
    print(f"dias de clima: {len(dates)}; carregado em {time.time()-started:.0f}s", flush=True)

    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_code[row["ibge_code"]].append(row)

    out_rows: list[dict[str, Any]] = []
    for position, code in enumerate(codes):
        latitude = centroids.get(code)
        day_arrays = {
            field: matrices[field][position] for field in FIELDS
        }
        for row in by_code[code]:
            months = row["months"]
            profile = thermal.PROFILES.get(PROFILE_BY_CROP.get(row["crop"], ""))
            windows = {}
            for label, corrected in (("legacy", False), ("corrected", True)):
                start, end = cycle.window_bounds(months, corrected=corrected)
                days = [i for i, d in enumerate(dates) if start <= d <= end]
                windows[label] = days
            record: dict[str, Any] = {
                "ibge_code": code,
                "crop": row["crop"],
                "safra": row["safra"],
                "state": row["state"],
                "zarc_cycle": row["zarc_cycle"],
                "harvest_year": row["harvest_year"],
                "yield_kg_ha": row["yield_kg_ha"],
                "months": ";".join(months),
                "n_months_listed": len(months),
            }
            for label, days in windows.items():
                if len(days) < 30:
                    continue
                records = _window_records(dates, day_arrays, None, days, latitude)
                aggregate = _aggregate(
                    records,
                    profile,
                    latitude,
                    cad_mm=50.0,
                    with_balance=True,
                )
                for key, value in aggregate.items():
                    record[f"{key}_{label}"] = value
            # cenários de CAD na janela corrigida
            corrected_days = windows["corrected"]
            if len(corrected_days) >= 30:
                records = _window_records(
                    dates, day_arrays, None, corrected_days, latitude
                )
                for name, depth in CAD_SCENARIOS.items():
                    capacity = cad.get(code, {}).get(name)
                    if not capacity:
                        continue
                    aggregate = _aggregate(
                        records, profile, latitude, cad_mm=capacity, with_balance=True
                    )
                    record[f"deficiency_{name}"] = aggregate.get("deficiency_total_mm")
                    record[f"excess_{name}"] = aggregate.get("excess_total_mm")
                    record[f"cad_{name}_mm"] = float(capacity)
            record["stored"] = row["stored"]
            out_rows.append(record)
        if (position + 1) % 200 == 0:
            print(f"  {position+1}/{len(codes)} municípios", flush=True)

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    fields = []
    for row in out_rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in out_rows:
            flat = {k: v for k, v in row.items() if k != "stored"}
            for key, value in row.get("stored", {}).items():
                flat[f"stored_{key}"] = value
            writer.writerow(flat)

    # --- reprodução da janela histórica contra o painel publicado -----------
    reproduction = {}
    for key in STORED_FIELDS:
        pairs = [
            (row.get(f"{key}_legacy"), row["stored"].get(key))
            for row in out_rows
            if row.get(f"{key}_legacy") is not None
            and row["stored"].get(key) is not None
        ]
        if not pairs:
            continue
        diffs = np.abs(np.array([a for a, _ in pairs]) - np.array([b for _, b in pairs]))
        reproduction[key] = {
            "n": len(pairs),
            "max_abs_diff": float(diffs.max()),
            "median_abs_diff": float(np.median(diffs)),
            "n_exact": int((diffs < 1e-6).sum()),
        }

    # --- efeito de restaurar o último mês, variável por variável ------------
    effect = {}
    for key in ("precip_acumulada_mm", "et0_total_mm", "degree_days_total",
                "extreme_heat_days", "deficiency_total_mm", "excess_total_mm",
                "temp_media_c", "dias_com_chuva", "warm_nights"):
        pairs = [
            (row.get(f"{key}_legacy"), row.get(f"{key}_corrected"))
            for row in out_rows
            if row.get(f"{key}_legacy") is not None
            and row.get(f"{key}_corrected") is not None
        ]
        if not pairs:
            continue
        legacy = np.array([a for a, _ in pairs])
        corrected = np.array([b for _, b in pairs])
        delta = corrected - legacy
        relative = np.divide(delta, np.where(legacy == 0, np.nan, legacy))
        effect[key] = {
            "n": len(pairs),
            "median_legacy": float(np.median(legacy)),
            "median_corrected": float(np.median(corrected)),
            "median_delta": float(np.median(delta)),
            "median_relative_change": float(np.nanmedian(relative)),
            "share_increased": float(np.mean(delta > 0)),
            "share_unchanged": float(np.mean(np.abs(delta) < 1e-9)),
        }

    payload = {
        "generated_at": _now(),
        "n_rows": len(out_rows),
        "n_municipalities": len({row["ibge_code"] for row in out_rows}),
        "definition": {
            "legacy": "months[0] <= data <= months[-1] (comparação lexicográfica; último mês excluído)",
            "corrected": "primeiro dia do primeiro mês até o último dia do último mês",
            "cad_legacy": 50.0,
            "cad_corrected_scenarios": list(CAD_SCENARIOS),
        },
        "reproduction_legacy": reproduction,
        "effect_of_restoring_last_month": effect,
        "elapsed_s": round(time.time() - started, 1),
    }
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:4000])
    print(f"painel: {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
