"""Adjudicação das fontes climáticas: NASA POWER × INMET.

Streaming em duas passagens sobre ``climate_daily.csv``:

1. coleta todas as linhas INMET (subconjunto pequeno);
2. percorre as linhas NASA POWER e compara **apenas pares com a mesma chave**
   (município, dia).

O objetivo não é escolher a fonte por preferência, e sim medir: cobertura,
completude, viés, erro, correlação, divergência em limites agronômicos e a
natureza da diferença (produto de reanálise vs observação de estação).

Saídas:
* ``geospatial/data/manifests/climate_source_adjudication.json``
* ``docs/data_quality/climate/climate_pairs_by_uf.csv``
* ``docs/data_quality/climate/climate_pairs_by_year.csv``
* ``docs/data_quality/climate/climate_coverage_by_municipality.csv``

Uso: python tools/audit_climate_sources.py
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
_DATA_ROOT = os.environ.get("SADEN_DATA_ROOT") or os.path.join(ROOT, "geospatial", "data")
PROCESSED = os.path.join(_DATA_ROOT, "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUTDIR = os.path.join(ROOT, "docs", "data_quality", "climate")
OUT_JSON = os.path.join(MANIFESTS, "climate_source_adjudication.json")

CLIMATE_FILE = os.path.join(PROCESSED, "climate_daily.csv")

UF_BY_CODE = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}

# Variáveis comparadas e limites técnicos de divergência relevante.
# Os limites não são estatísticos: são a diferença a partir da qual a decisão
# agronômica (janela, graus-dia, balanço) mudaria de forma material.
VARIABLES = {
    "precip_mm": {"label": "precipitação diária", "unit": "mm", "limit": 5.0},
    "temp_media_c": {"label": "temperatura média", "unit": "°C", "limit": 3.0},
    "temp_max_c": {"label": "temperatura máxima", "unit": "°C", "limit": 3.0},
    "temp_min_c": {"label": "temperatura mínima", "unit": "°C", "limit": 3.0},
    "umidade_rel_pct": {"label": "umidade relativa", "unit": "pp", "limit": 20.0},
    "vento_kmh": {"label": "vento a 2 m", "unit": "km/h", "limit": 10.0},
    "radiacao_mj_m2": {"label": "radiação solar", "unit": "MJ/m²", "limit": 8.0},
}


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def collect_inmet() -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, Any]]:
    """Primeira passagem: tudo o que é INMET."""
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    stats: Counter = Counter()
    started = time.time()
    with open(CLIMATE_FILE, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            stats["rows_read"] += 1
            if row.get("source") != "INMET":
                continue
            key = (str(row.get("ibge_code")), str(row.get("date")))
            if key in rows:
                stats["inmet_duplicates"] += 1
                continue
            rows[key] = {
                "values": {name: _float(row.get(name)) for name in VARIABLES},
                "station_code": row.get("station_code"),
                "station_name": row.get("station_name"),
                "distance_km": _float(row.get("distance_km")),
                "selection_method": row.get("selection_method"),
                "n_obs_temp": _float(row.get("temp_media_c_n_obs")),
                "n_obs_precip": _float(row.get("precip_mm_n_obs")),
                "n_obs_rad": _float(row.get("radiacao_mj_m2_n_obs")),
            }
            stats["inmet_rows"] += 1
    stats["elapsed_s"] = round(time.time() - started, 1)
    return rows, dict(stats)


def compare(inmet: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    """Segunda passagem: NASA POWER contra INMET na mesma chave."""
    pairs: dict[str, list[float]] = defaultdict(list)          # variável -> diffs
    nasa_values: dict[str, list[float]] = defaultdict(list)
    inmet_values: dict[str, list[float]] = defaultdict(list)
    per_uf: dict[str, Counter] = defaultdict(Counter)
    per_year: dict[str, Counter] = defaultdict(Counter)
    per_municipality: dict[str, dict[str, Any]] = {}
    matched = 0
    nasa_rows = 0
    nasa_unmatched = 0
    incomplete_inmet = 0
    lat_gap: list[float] = []

    with open(CLIMATE_FILE, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("source") != "NASA-POWER":
                continue
            nasa_rows += 1
            code = str(row.get("ibge_code"))
            date = str(row.get("date"))
            partner = inmet.get((code, date))
            if partner is None:
                nasa_unmatched += 1
                continue
            matched += 1
            uf = UF_BY_CODE.get(code[:2], "??")
            year = date[:4]
            inmet_lat = None
            if partner["n_obs_temp"] is not None and partner["n_obs_temp"] < 24:
                incomplete_inmet += 1
            for name in VARIABLES:
                left = _float(row.get(name))
                right = partner["values"].get(name)
                if left is None or right is None:
                    per_uf[uf][f"{name}|ausente"] += 1
                    continue
                diff = left - right
                pairs[name].append(diff)
                nasa_values[name].append(left)
                inmet_values[name].append(right)
                per_uf[uf][f"{name}|n"] += 1
                per_year[year][f"{name}|n"] += 1
                if abs(diff) > VARIABLES[name]["limit"]:
                    per_uf[uf][f"{name}|acima_limite"] += 1
                    per_year[year][f"{name}|acima_limite"] += 1
            entry = per_municipality.setdefault(
                code,
                {
                    "uf": uf,
                    "station_code": partner["station_code"],
                    "station_name": partner["station_name"],
                    "distance_km": partner["distance_km"],
                    "selection_method": partner["selection_method"],
                    "paired_days": 0,
                },
            )
            entry["paired_days"] += 1

    summary: dict[str, Any] = {}
    for name, config in VARIABLES.items():
        values = np.asarray(pairs[name], dtype="float64")
        if values.size == 0:
            summary[name] = {"n": 0}
            continue
        left = np.asarray(nasa_values[name], dtype="float64")
        right = np.asarray(inmet_values[name], dtype="float64")
        absolute = np.abs(values)
        correlation = float(np.corrcoef(left, right)[0, 1]) if left.std() > 0 and right.std() > 0 else None
        summary[name] = {
            "label": config["label"],
            "unit": config["unit"],
            "limit": config["limit"],
            "n": int(values.size),
            "bias_nasa_minus_inmet": float(values.mean()),
            "median_diff": float(np.median(values)),
            "mae": float(absolute.mean()),
            "rmse": float(np.sqrt(np.mean(values**2))),
            "median_abs_diff": float(np.median(absolute)),
            "p05_diff": float(np.quantile(values, 0.05)),
            "p95_diff": float(np.quantile(values, 0.95)),
            "correlation": correlation,
            "share_above_limit": float((absolute > config["limit"]).mean()),
            "nasa_mean": float(left.mean()),
            "inmet_mean": float(right.mean()),
        }

    return {
        "matched_pairs": matched,
        "nasa_rows": nasa_rows,
        "nasa_rows_without_inmet_partner": nasa_unmatched,
        "inmet_days_with_incomplete_temp": incomplete_inmet,
        "by_variable": summary,
        "per_uf": {uf: dict(counter) for uf, counter in sorted(per_uf.items())},
        "per_year": {year: dict(counter) for year, counter in sorted(per_year.items())},
        "per_municipality": per_municipality,
    }


def coverage(inmet: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    """Cobertura: quantos municípios têm cada fonte e com que completude."""
    by_code: dict[str, list[str]] = defaultdict(list)
    for (code, date) in inmet:
        by_code[code].append(date)
    days = [len(dates) for dates in by_code.values()]
    distances = [
        entry["distance_km"] for entry in inmet.values() if entry["distance_km"] is not None
    ]
    methods: Counter = Counter(entry["selection_method"] for entry in inmet.values())
    stations = {entry["station_code"] for entry in inmet.values() if entry["station_code"]}
    return {
        "inmet_municipalities": len(by_code),
        "inmet_stations": len(stations),
        "inmet_days_per_municipality": {
            "min": min(days) if days else None,
            "median": float(np.median(days)) if days else None,
            "max": max(days) if days else None,
        },
        "inmet_distance_km": {
            "median": float(np.median(distances)) if distances else None,
            "p90": float(np.quantile(distances, 0.90)) if distances else None,
            "max": max(distances) if distances else None,
        },
        "selection_methods": dict(methods),
    }


def main() -> int:
    if not os.path.exists(CLIMATE_FILE):
        print(f"arquivo ausente: {CLIMATE_FILE}")
        return 1
    print("passagem 1/2: coletando INMET...")
    inmet, stats = collect_inmet()
    print(" ", stats, "pares:", len(inmet))
    print("passagem 2/2: comparando NASA POWER...")
    result = compare(inmet)
    print("  pareados:", result["matched_pairs"])

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "file": os.path.relpath(CLIMATE_FILE, ROOT).replace("\\", "/"),
        "bytes": os.path.getsize(CLIMATE_FILE),
        "read_stats": stats,
        "coverage": coverage(inmet),
        "comparison": {
            key: value for key, value in result.items() if key != "per_municipality"
        },
    }
    os.makedirs(OUTDIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")

    with open(os.path.join(OUTDIR, "climate_coverage_by_municipality.csv"), "w",
              newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["ibge_code", "uf", "paired_days", "station_code", "station_name",
                        "distance_km", "selection_method"],
        )
        writer.writeheader()
        for code, entry in sorted(result["per_municipality"].items()):
            writer.writerow({"ibge_code": code, **entry})

    for name, table in (("climate_pairs_by_uf.csv", result["per_uf"]),
                        ("climate_pairs_by_year.csv", result["per_year"])):
        keys = sorted({key for counter in table.values() for key in counter})
        with open(os.path.join(OUTDIR, name), "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["group"] + keys)
            for group, counter in table.items():
                writer.writerow([group] + [counter.get(key, 0) for key in keys])

    print()
    print("COBERTURA:", json.dumps(report["coverage"], ensure_ascii=False))
    print()
    print(f"{'variável':18} {'n':>7} {'viés':>8} {'MAE':>7} {'RMSE':>8} {'r':>6} {'>lim':>7}")
    for name, entry in report["comparison"]["by_variable"].items():
        if not entry.get("n"):
            continue
        print(
            f"{name:18} {entry['n']:7d} {entry['bias_nasa_minus_inmet']:8.3f} "
            f"{entry['mae']:7.3f} {entry['rmse']:8.3f} "
            f"{(entry['correlation'] or 0):6.3f} {entry['share_above_limit']:7.1%}"
        )
    print()
    print("manifesto:", OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
