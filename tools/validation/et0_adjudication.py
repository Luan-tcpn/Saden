"""Adjudicação da ET0 com decomposição exata, ancorada na biblioteca.

A primeira versão deste instrumento reimplementava a ET0 de referência e **não
reproduzia a biblioteca** (4,24 vs 4,64 mm/dia no mesmo dia): a comparação
estava contaminada pela reimplementação, não pela biblioteca. Este instrumento
foi refeito para nunca reconstruir o cálculo original.

Identidade usada: a biblioteca calcula ``u2 = 0,4 × vento_entrada / 3,6``.
Passando ``vento_entrada = vento × 2,5`` obtém-se ``u2 = vento / 3,6`` — ou seja,
o vento correto **sem tocar na biblioteca**. Isso permite isolar o fator vento
de forma exata.

Variantes (todas chamando a mesma função):

* ``referencia``   — ``fao56_penman_monteith`` com o vento original;
* ``vento_correto``— mesma função com ``vento × 2,5`` (u2 a 2 m);
* ``fao56``        — ``corrections.et0_daily`` (es de extremos **e** vento a 2 m).

A diferença entre ``referencia`` e ``vento_correto`` é o efeito do vento;
``fao56`` − ``vento_correto`` é o efeito residual da pressão de vapor.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, os.path.join(ROOT, "tools", "analysis"))

from agroclimate import corrections, cycle, evapotranspiration, water_balance  # noqa: E402

_DATA_ROOT = os.environ.get("SADEN_DATA_ROOT") or os.path.join(ROOT, "geospatial", "data")
PROCESSED = os.path.join(_DATA_ROOT, "processed")
OUT_JSON = os.path.join(ROOT, "geospatial", "data", "manifests", "et0_adjudication.json")

WIND_FACTOR = 2.5  # 1 / 0,4


def _day_of_year(date: str) -> int:
    from datetime import date as date_type

    year, month, day = (int(part) for part in date.split("-"))
    return date_type(year, month, day).timetuple().tm_yday


def sample_rows(target: int, seed: int) -> list[dict[str, str]]:
    path = os.path.join(PROCESSED, "v35_panel_windows.csv")
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row.get("months"):
                rows.append(row)
    by_crop: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_crop.setdefault(str(row.get("crop")), []).append(row)
    generator = np.random.default_rng(seed)
    per_crop = max(1, target // max(1, len(by_crop)))
    chosen: list[dict[str, str]] = []
    for crop in sorted(by_crop):
        candidates = sorted(by_crop[crop], key=lambda r: (r["ibge_code"], r["safra"]))
        take = min(per_crop, len(candidates))
        for position in generator.choice(len(candidates), size=take, replace=False):
            chosen.append(candidates[position])
    return chosen


def build_climate(codes: set[str]) -> dict[str, dict[str, dict[str, str]]]:
    index: dict[str, dict[str, dict[str, str]]] = {}
    for name in ("climate_daily.csv", "climate_daily_sp.csv"):
        path = os.path.join(PROCESSED, name)
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                code = str(row.get("ibge_code"))
                if code not in codes or str(row.get("source")) != "NASA-POWER":
                    continue
                index.setdefault(code, {}).setdefault(str(row.get("date")), row)
    return index


def library_et0(day: dict[str, str], latitude: float, wind_multiplier: float = 1.0) -> float:
    result = evapotranspiration.fao56_penman_monteith(
        float(day["temp_max_c"]), float(day["temp_min_c"]), float(day["temp_media_c"]),
        float(day["radiacao_mj_m2"]), float(day["vento_kmh"]) * wind_multiplier,
        float(day["umidade_rel_pct"]), float(day["pressao_kpa"]), latitude,
        _day_of_year(str(day["date"])),
    )
    return float(result.et0_mm) if result.et0_mm is not None else 0.0


def corrected_et0(day: dict[str, str], latitude: float) -> float:
    return corrections.et0_daily(
        float(day["temp_max_c"]), float(day["temp_min_c"]), float(day["temp_media_c"]),
        float(day["radiacao_mj_m2"]), float(day["vento_kmh"]),
        float(day["umidade_rel_pct"]), float(day["pressao_kpa"]), latitude,
        _day_of_year(str(day["date"])),
    )


def load_latitudes() -> dict[str, float]:
    """Latitude do centróide municipal (o painel só exporta latitude para SP)."""
    out: dict[str, float] = {}
    path = os.path.join(PROCESSED, "panel_municipalities_v35.csv")
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            value = row.get("centroid_lat")
            if value not in (None, ""):
                out[str(row["ibge_code"])] = float(value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=900)
    parser.add_argument("--seed", type=int, default=20261114)
    args = parser.parse_args()

    rows = sample_rows(args.rows, args.seed)
    climate = build_climate({str(row["ibge_code"]) for row in rows})
    latitudes = load_latitudes()
    print(f"amostra: {len(rows)} janelas")

    collected: dict[str, list[dict[str, Any]]] = {
        "referencia": [], "vento_correto": [], "fao56": []
    }
    identity_error: list[float] = []

    for row in rows:
        code = str(row["ibge_code"])
        months = [m for m in str(row["months"]).split(";") if m]
        start, end = cycle.window_bounds(months, corrected=True)
        days = [day for date, day in climate.get(code, {}).items() if start <= date <= end]
        if len(days) < 30:
            continue
        latitude = latitudes.get(code)
        if latitude is None:
            continue
        values: dict[str, list[float]] = {"referencia": [], "vento_correto": [], "fao56": []}
        precip: list[float] = []
        for day in days:
            values["referencia"].append(library_et0(day, latitude, 1.0))
            values["vento_correto"].append(library_et0(day, latitude, WIND_FACTOR))
            values["fao56"].append(corrected_et0(day, latitude))
            precip.append(float(day["precip_mm"]))
        for name, series in values.items():
            daily = [
                {"date": day["date"], "et0_mm": value, "precip_mm": p}
                for day, value, p in zip(days, series, precip)
            ]
            monthly = water_balance.daily_to_monthly(daily)
            balance = water_balance.sequential_water_balance(monthly, cad_mm=50.0)
            valid = [item for item in balance if item.get("status") == "ok"]
            collected[name].append(
                {
                    "et0": sum(series),
                    "deficit": sum(float(item["def_mm"] or 0.0) for item in valid),
                    "etr": sum(float(item["etr_mm"] or 0.0) for item in valid),
                    "crop": row["crop"], "yield": float(row["yield_kg_ha"]),
                    "year": row["harvest_year"], "state": row["state"], "code": code,
                }
            )
        # identidade: vento_correto com fator 2,5 deve igualar u2 = vento/3,6
        reference_u2 = 0.4 * float(days[0]["vento_kmh"]) / 3.6
        scaled_u2 = 0.4 * float(days[0]["vento_kmh"]) * WIND_FACTOR / 3.6
        identity_error.append(abs(scaled_u2 - float(days[0]["vento_kmh"]) / 3.6))

    n = min(len(v) for v in collected.values())
    print(f"janelas usadas: {n}")
    reference = np.array([item["et0"] for item in collected["referencia"]])
    outcome: dict[str, Any] = {}
    for name, items in collected.items():
        values = np.array([item["et0"] for item in items])
        deficits = np.array([item["deficit"] for item in items])
        reference_deficits = np.array([item["deficit"] for item in collected["referencia"]])
        valid = reference > 0.1
        outcome[name] = {
            "n": len(items),
            "et0_mean_mm": float(values.mean()),
            "et0_ratio_vs_reference": float(np.mean(values[valid] / reference[valid])),
            "et0_median_relative": float(np.median((values[valid] - reference[valid]) / reference[valid])),
            "deficit_mean_mm": float(deficits.mean()),
            "deficit_ratio_vs_reference": float(
                np.mean(deficits[np.abs(reference_deficits) > 1e-9] / reference_deficits[np.abs(reference_deficits) > 1e-9])
            ) if np.any(np.abs(reference_deficits) > 1e-9) else None,
            "deficit_correlation": float(np.corrcoef(deficits, reference_deficits)[0, 1]),
        }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "decomposição ancorada na biblioteca: 'vento_correto' reescala a entrada "
            "de vento por 2,5 para que u2 = vento/3,6 sem tocar no código original; "
            "'fao56' usa a implementação corrigida"
        ),
        "wind_identity_max_error": float(max(identity_error)) if identity_error else None,
        "sample": {"rows_requested": args.rows, "rows_used": n, "seed": args.seed, "cad_mm": 50.0},
        "by_variant": outcome,
        "decomposition": {
            "wind_only_median_relative": outcome["vento_correto"]["et0_median_relative"],
            "net_corrected_vs_reference_median_relative": outcome["fao56"]["et0_median_relative"],
            "net_corrected_vs_reference_mean_ratio": outcome["fao56"]["et0_ratio_vs_reference"],
            "note": (
                "o efeito do vento é medido por identidade exata (escala 2,5 na entrada). "
                "O passo seguinte muda a pressão de vapor e o denominador aerodinâmico ao "
                "mesmo tempo, de modo que a soma dos dois efeitos não é aditiva; só o "
                "total é identificado por esta via"
            ),
        },
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")

    print(f"\n{'variante':16} {'ET0 média':>10} {'razão':>8} {'med.rel':>9} {'déficit':>10} {'razão def':>10} {'r':>7}")
    for name, data in outcome.items():
        print(
            f"{name:16} {data['et0_mean_mm']:10.1f} {data['et0_ratio_vs_reference']:8.4f} "
            f"{data['et0_median_relative']:9.4f} {data['deficit_mean_mm']:10.1f} "
            f"{data['deficit_ratio_vs_reference']:10.4f} {data['deficit_correlation']:7.4f}"
        )
    print("\ndecomposição:", json.dumps(report["decomposition"], ensure_ascii=False))
    print("erro máx. da identidade do vento:", report["wind_identity_max_error"])
    print("manifesto:", OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
