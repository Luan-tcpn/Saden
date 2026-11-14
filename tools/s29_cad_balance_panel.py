"""V2.9 — efeito da CAD oficial no balanço hídrico, município a município (D93).

A V2.8 mediu o efeito em 9 municípios com um cenário fixo. Agora que a CAD
foi coletada para o painel, a pergunta muda: **o reescalonamento é
uniforme?** Se cada município tem a sua própria razão CAD_oficial/50 mm, o
regressor "déficit" deixa de ser uma transformação afim de si mesmo, e a
inferência passa a depender dessa heterogeneidade. Se a razão fosse
constante, o teste t não mudaria.

Para cada município com CAD e série diária:
* ET0 FAO-56 diária (mesma implementação do painel), agregada por mês;
* balanço sequencial anual com CAD = 50 mm (referência V2.6) e com a CAD
  oficial de 0–100 cm e de 0–200 cm;
* razão déficit(CAD oficial) / déficit(50 mm) por município-ano.

Uso:
    python tools/s29_cad_balance_panel.py --limit 200
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import evapotranspiration as et_module  # noqa: E402
from agroclimate import water_balance as wb_module  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
CAD_MANIFEST = os.path.join(MANIFESTS, "v29_cad_expansion.json")
OUT = os.path.join(MANIFESTS, "v29_cad_balance_panel.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_cad() -> dict[str, float]:
    data = json.load(open(CAD_MANIFEST, encoding="utf-8"))
    out: dict[str, float] = {}
    for record in data["municipalities"]:
        value = (record.get("cad_0_100_pixels") or {}).get("median")
        if value:
            out[str(record["ibge_code"])] = float(value)
    return out


def load_centroids() -> dict[str, float]:
    out: dict[str, float] = {}
    with open(
        os.path.join(PROCESSED, "panel_municipalities.csv"),
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        for row in csv.DictReader(handle):
            latitude = _to_float(row.get("centroid_lat"))
            if latitude is not None:
                out[str(row["ibge_code"])] = latitude
    return out


def load_daily(codes: set[str]) -> dict[str, list[dict[str, Any]]]:
    path = os.path.join(PROCESSED, "climate_daily.csv")
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            code = str(row.get("ibge_code") or "")
            if code not in codes or str(row.get("source")) != "NASA-POWER":
                continue
            out[code].append(
                {
                    "date": row.get("date"),
                    "temp_max_c": _to_float(row.get("temp_max_c")),
                    "temp_min_c": _to_float(row.get("temp_min_c")),
                    "temp_media_c": _to_float(row.get("temp_media_c")),
                    "radiacao_mj_m2": _to_float(row.get("radiacao_mj_m2")),
                    "vento_kmh": _to_float(row.get("vento_kmh")),
                    "umidade_rel_pct": _to_float(row.get("umidade_rel_pct")),
                    "pressao_kpa": _to_float(row.get("pressao_kpa")),
                    "precip_mm": _to_float(row.get("precip_mm")),
                }
            )
    return dict(out)


def annual_deficit(daily, latitude, cad_mm) -> dict[int, float]:
    series = et_module.daily_et0_series(
        daily, float(latitude), method="fao56_penman_monteith", elevation_m=None
    )
    by_date = {str(r.get("date")): r for r in daily}
    for item in series:
        source = by_date.get(str(item.get("date")))
        if source is not None:
            item["precip_mm"] = source.get("precip_mm")
    per_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in series:
        year = str(item.get("date"))[:4]
        if len(year) == 4:
            per_year[int(year)].append(item)
    out: dict[int, float] = {}
    for year, chunk in sorted(per_year.items()):
        monthly = wb_module.daily_to_monthly(chunk)
        balance = wb_module.sequential_water_balance(monthly, cad_mm=cad_mm)
        totals = wb_module.aggregate_water_balance(balance)
        value = totals.get("deficiency_total_mm")
        if value is not None:
            out[year] = float(value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cad = load_cad()
    centroids = load_centroids()
    codes = {code for code in cad if code in centroids}
    if args.limit:
        codes = set(sorted(codes)[: args.limit])
    print(f"municípios com CAD e centroide: {len(codes)}", flush=True)
    daily = load_daily(codes)
    codes = codes & set(daily)
    print(f"com série diária: {len(codes)}", flush=True)

    rows: list[dict[str, Any]] = []
    for index, code in enumerate(sorted(codes), start=1):
        latitude = centroids[code]
        base = annual_deficit(daily[code], latitude, 50.0)
        official = annual_deficit(daily[code], latitude, cad[code])
        for year in sorted(base):
            if base[year] <= 0 or year not in official:
                continue
            rows.append(
                {
                    "ibge_code": code,
                    "year": year,
                    "cad_official_mm": cad[code],
                    "deficit_50mm": base[year],
                    "deficit_official": official[year],
                    "ratio": official[year] / base[year],
                }
            )
        if index % 50 == 0:
            print(f"  {index}/{len(codes)}", flush=True)

    ratios = [row["ratio"] for row in rows]
    by_municipality: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_municipality[row["ibge_code"]].append(row["ratio"])
    municipality_medians = [statistics.median(values) for values in by_municipality.values()]
    payload = {
        "generated_at": _now(),
        "method": (
            "Balanco hidrico anual sequencial (Thornthwaite & Mather, 1955) com "
            "ET0 FAO-56, comparando CAD=50 mm com a CAD oficial de 0-100 cm do "
            "proprio municipio."
        ),
        "n_municipalities": len(by_municipality),
        "n_municipality_years": len(rows),
        "ratio_deficit_official_over_50mm": {
            "median": statistics.median(ratios),
            "p10": float(np.quantile(ratios, 0.10)),
            "p90": float(np.quantile(ratios, 0.90)),
            "min": min(ratios),
            "max": max(ratios),
            "share_below_0_75": float(np.mean(np.asarray(ratios) < 0.75)),
            "share_above_1_0": float(np.mean(np.asarray(ratios) > 1.0)),
        },
        "municipality_median_ratio": {
            "median": statistics.median(municipality_medians),
            "p10": float(np.quantile(municipality_medians, 0.10)),
            "p90": float(np.quantile(municipality_medians, 0.90)),
            "min": min(municipality_medians),
            "max": max(municipality_medians),
            "sd": float(np.std(municipality_medians, ddof=1))
            if len(municipality_medians) > 1
            else 0.0,
        },
        "cad_0_100_mm": {
            "min": min(cad[c] for c in codes),
            "median": statistics.median(cad[c] for c in codes),
            "max": max(cad[c] for c in codes),
        },
        "rows": rows,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(
        "razão déficit(oficial)/50mm: mediana %.3f [p10 %.3f, p90 %.3f]; "
        "medianas por município: %.3f [%.3f, %.3f], sd %.3f"
        % (
            payload["ratio_deficit_official_over_50mm"]["median"],
            payload["ratio_deficit_official_over_50mm"]["p10"],
            payload["ratio_deficit_official_over_50mm"]["p90"],
            payload["municipality_median_ratio"]["median"],
            payload["municipality_median_ratio"]["p10"],
            payload["municipality_median_ratio"]["p90"],
            payload["municipality_median_ratio"]["sd"],
        )
    )
    print(f"manifesto: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
