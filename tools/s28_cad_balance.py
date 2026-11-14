"""V2.8 — CAD oficial no balanço hídrico (D88).

A V2.7 encontrou a CAD geoespacial da Embrapa Solos (mm/cm, 90 m) e mostrou
que ela é 2–3× maior que os cenários de 35/50/70 mm da V2.6 — mas **não**
mediu o efeito dessa diferença no balanço hídrico. Este script mede.

O que é feito:

1. **Validação de unidade.** Se a unidade fosse ``cm³/cm³`` (volumétrica),
   valores observados como 2,5 seriam fisicamente impossíveis (> 1,0). A
   leitura ``mm/cm`` é a única coerente, e é confirmada numericamente.
2. **Balanço hídrico anual** (Thornthwaite & Mather, 1955) para os
   municípios com CAD amostrada, sob quatro capacidades:
   os cenários históricos (35 / 50 / 70 mm) e a CAD integrada da fonte
   oficial em três profundidades de perfil (0–60, 0–100, 0–200 cm).
3. **Sensibilidade**: quanto o déficit e o excedente mudam, por município e
   ano, e qual a fração de casos em que a mudança é material.

As profundidades 0–60/0–100/0–200 cm são **perfis de solo publicados**, não
profundidades radiculares de cultura. Atribuir uma profundidade efetiva por
cultura exigiria fonte cultivar-específica; isso fica declarado como
limitação (ver D88).

Uso:
    python tools/s28_cad_balance.py
"""

from __future__ import annotations

import csv
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import evapotranspiration as et_module  # noqa: E402
from agroclimate import soil as soil_module  # noqa: E402
from agroclimate import water_balance as wb_module  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
CAD_SAMPLE = os.path.join(MANIFESTS, "v27_cad_sample.json")
OUT_JSON = os.path.join(MANIFESTS, "v28_cad_balance.json")
OUT_CSV = os.path.join(MANIFESTS, "v28_cad_balance.csv")

DEPTHS_CM = (60.0, 100.0, 200.0)

# Cenários fixos: os três históricos da V2.6 e a CAD oficial em três perfis.
V26_SCENARIOS: dict[str, float] = {
    "v26_35mm": 35.0,
    "v26_50mm": 50.0,
    "v26_70mm": 70.0,
}
OFFICIAL_SCENARIOS: tuple[str, ...] = tuple(
    f"official_0_{int(depth)}cm" for depth in DEPTHS_CM
)
SCENARIO_ORDER: tuple[str, ...] = tuple(V26_SCENARIOS) + OFFICIAL_SCENARIOS


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_csv(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_daily(codes: set[str]) -> dict[str, list[dict[str, Any]]]:
    """Série diária NASA-POWER dos municípios pedidos (uma passada no CSV)."""
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


def validate_units(values: list[float]) -> dict[str, Any]:
    """Confere que a unidade só pode ser mm/cm (volumétrica seria impossível)."""
    observed_max = max(values) if values else 0.0
    return {
        "observed_max": observed_max,
        "observed_min": min(values) if values else 0.0,
        "volumetric_reading_possible": observed_max <= 1.0,
        "unit_consistent_with_mm_per_cm": observed_max > 1.0,
        "note": (
            "valores acima de 1,0 descartam a leitura volumetrica (cm3/cm3); "
            "mm de agua por cm de solo e a unica leitura coerente e e a "
            "declarada pela fonte"
        ),
    }


def annual_balance(
    daily: list[dict[str, Any]],
    latitude: float,
    cad_mm: float,
) -> dict[int, dict[str, Any]]:
    """Balanço hídrico anual sequencial por ano civil."""
    et_series = et_module.daily_et0_series(
        daily, float(latitude), method="fao56_penman_monteith", elevation_m=None
    )
    by_date = {str(r.get("date")): r for r in daily}
    for item in et_series:
        source = by_date.get(str(item.get("date")))
        if source is not None:
            item["precip_mm"] = source.get("precip_mm")
    per_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in et_series:
        year = str(item.get("date"))[:4]
        if len(year) == 4:
            per_year[int(year)].append(item)
    out: dict[int, dict[str, Any]] = {}
    for year, series in sorted(per_year.items()):
        monthly = wb_module.daily_to_monthly(series)
        balance = wb_module.sequential_water_balance(monthly, cad_mm=cad_mm)
        totals = wb_module.aggregate_water_balance(balance)
        out[year] = totals
    return out


def main() -> int:
    sample = json.load(open(CAD_SAMPLE, encoding="utf-8"))
    municipalities = {m["ibge_code"]: m for m in sample["municipalities"]}
    centroids = {
        r["ibge_code"]: _to_float(r.get("centroid_lat"))
        for r in _read_csv(os.path.join(PROCESSED, "panel_municipalities.csv"))
    }
    daily = load_daily(set(municipalities))
    available = sorted(daily)
    missing = sorted(set(municipalities) - set(daily))

    all_values = [
        value
        for record in municipalities.values()
        for value in record["values_mm_per_cm"].values()
        if value is not None
    ]
    unit_check = validate_units(all_values)

    capacities: dict[str, dict[str, Any]] = {}
    for code, record in municipalities.items():
        entry: dict[str, Any] = {"municipality": record["municipality"], "state": record["state"]}
        for depth in DEPTHS_CM:
            result = soil_module.profile_capacity_to_depth_mm(
                record["values_mm_per_cm"], depth
            )
            entry[f"cad_0_{int(depth)}_cm_mm"] = result["capacity_mm"]
            entry[f"coverage_0_{int(depth)}_cm"] = result["coverage_fraction"]
            entry[f"excluded_layers_0_{int(depth)}"] = result["excluded_layers"]
        capacities[code] = entry

    rows: list[dict[str, Any]] = []
    for code in available:
        latitude = centroids.get(code)
        if latitude is None:
            continue
        entry = capacities[code]
        cad_by_scenario: dict[str, float] = dict(V26_SCENARIOS)
        for depth in DEPTHS_CM:
            value = entry.get(f"cad_0_{int(depth)}_cm_mm")
            if value:
                cad_by_scenario[f"official_0_{int(depth)}cm"] = float(value)
        results = {
            name: annual_balance(daily[code], latitude, cad)
            for name, cad in cad_by_scenario.items()
        }
        for year in sorted(results["v26_50mm"]):
            row = {
                "ibge_code": code,
                "municipality": entry["municipality"],
                "state": entry["state"],
                "year": year,
            }
            for name in cad_by_scenario:
                totals = results[name].get(year, {})
                row[f"deficiency_{name}"] = totals.get("deficiency_total_mm")
                row[f"excess_{name}"] = totals.get("excess_total_mm")
                row[f"etr_{name}"] = totals.get("etr_total_mm")
                row[f"cad_{name}"] = cad_by_scenario[name]
            rows.append(row)

    # síntese: mudança relativa do déficit e do excedente
    summary: dict[str, Any] = {}
    for name in SCENARIO_ORDER:
        deficits = [
            r[f"deficiency_{name}"]
            for r in rows
            if r.get(f"deficiency_{name}") is not None
        ]
        excess = [
            r[f"excess_{name}"] for r in rows if r.get(f"excess_{name}") is not None
        ]
        if not deficits:
            continue
        summary[name] = {
            "deficiency_median_mm": statistics.median(deficits),
            "deficiency_mean_mm": statistics.fmean(deficits),
            "excess_median_mm": statistics.median(excess) if excess else None,
            "n": len(deficits),
        }
    base = summary.get("v26_50mm", {}).get("deficiency_median_mm")
    for name, entry in summary.items():
        if base and entry["deficiency_median_mm"] is not None:
            entry["deficiency_change_vs_v26_50mm_percent"] = 100.0 * (
                entry["deficiency_median_mm"] - base
            ) / base

    official_key = "official_0_100cm"
    changed_materially = [
        row
        for row in rows
        if row.get(f"deficiency_{official_key}") is not None
        and abs(
            row[f"deficiency_{official_key}"] - row["deficiency_v26_50mm"]
        )
        > 0.25 * max(abs(row["deficiency_v26_50mm"]), 1e-9)
    ]
    payload = {
        "generated_at": _now(),
        "method": (
            "Balanco hidrico anual sequencial (Thornthwaite & Mather, 1955) com "
            "ET0 FAO-56 Penman-Monteith, variando apenas a CAD. Profundidades "
            "sao perfis publicados (0-60/0-100/0-200 cm), nao profundidade "
            "radicular de cultura."
        ),
        "cad_source": sample["source"],
        "license": sample["license"],
        "unit": sample["unit"],
        "unit_validation": unit_check,
        "municipalities_with_daily_data": available,
        "municipalities_missing_daily_data": missing,
        "capacities": capacities,
        "summary": summary,
        "material_change_vs_v26_50mm": {
            "threshold_percent": 25.0,
            "n_rows": len(rows),
            "n_material": len(changed_materially),
        },
        "rows": rows,
    }
    os.makedirs(MANIFESTS, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    fields = list(rows[0].keys()) if rows else []
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(json.dumps(
        {
            "unit": unit_check,
            "n_municipalities": len(available),
            "missing": missing,
            "summary": summary,
            "material": payload["material_change_vs_v26_50mm"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
