"""V3.1 — reavaliação dos modelos com a janela corrigida e tendência espacial.

Compara, no protocolo TE (espaço e tempo separados simultaneamente), com
equalização estrita por célula, o mesmo estimador da V2.9/V3.0:

* ``legacy_climate``      — precipitação + temperatura da janela histórica
* ``corrected_climate``   — idem, janela corrigida (D100)
* ``corrected_thermal``   — graus-dia + calor extremo corrigidos
* ``corrected_water_*``   — déficit reconstruído com CAD 0–60/0–100/0–200
* ``trend``               — M3: latitude/longitude + termos quadráticos + UF
* ``trend_climate``       — M4: tendência espacial + clima + UF

Todas usam as mesmas células, a mesma semente e as mesmas linhas de teste; as
diferenças são comparadas de forma pareada por bootstrap de bloco.

Uso: python tools/v31_models.py [--crops soja,milho,milho_2]
"""

from __future__ import annotations

import argparse
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

import run_robustness as rr  # noqa: E402
from agroclimate import generalization as gen  # noqa: E402
from agroclimate import spatial  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
PANEL = os.path.join(PROCESSED, "v31_panel_windows.csv")
OUT_JSON = os.path.join(MANIFESTS, "v31_models_te.json")

N_REPEATS = 3
N_BOOT = 1000
BLOCK_RADIUS_KM = 250.0

SPECS: dict[str, tuple[str, ...]] = {
    "legacy_climate": ("precip_legacy", "temp_legacy"),
    "corrected_climate": ("precip_corrected", "temp_corrected"),
    "corrected_thermal": ("degree_days_corrected", "heat_corrected"),
    "corrected_water_cad60": ("deficit_cad60",),
    "corrected_water_cad100": ("deficit_cad100",),
    "corrected_water_cad200": ("deficit_cad200",),
    "corrected_water_cad50": ("deficit_corrected_50",),
    "trend": ("lat_c", "lon_c", "lat2", "lon2"),
    "trend_climate": (
        "precip_corrected",
        "temp_corrected",
        "lat_c",
        "lon_c",
        "lat2",
        "lon2",
    ),
}

PAIRS = (
    ("corrected_climate", "legacy_climate"),
    ("trend", "corrected_climate"),
    ("trend_climate", "trend"),
    ("trend_climate", "corrected_climate"),
    ("corrected_water_cad100", "corrected_climate"),
    ("corrected_thermal", "corrected_climate"),
)


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_coordinates() -> dict[str, tuple[float, float]]:
    path = os.path.join(PROCESSED, "panel_municipalities.csv")
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            lat = _num(row.get("centroid_lat"))
            lon = _num(row.get("centroid_lon"))
            if lat is not None and lon is not None:
                out[str(row["ibge_code"])] = (lat, lon)
    return out


def load_rows() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    coordinates = load_coordinates()
    blocks = spatial.spatial_blocks(rr.load_municipalities(), BLOCK_RADIUS_KM)
    dropped = {"coordinate": 0, "year": 0, "missing_variable": 0, "block": 0}
    with open(PANEL, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            code = str(row["ibge_code"])
            position = coordinates.get(code)
            if position is None:
                dropped["coordinate"] += 1
                continue
            year = row.get("harvest_year")
            if year in (None, ""):
                dropped["year"] += 1
                continue
            latitude, longitude = position
            lat_c = latitude + 20.0
            lon_c = longitude + 50.0
            record: dict[str, Any] = {
                "ibge_code": code,
                "crop": str(row["crop"]),
                "safra": str(row.get("safra")),
                "state": row.get("state"),
                "year": int(float(year)),
                "yield_kg_ha": _num(row.get("yield_kg_ha")),
                "spatial_block": blocks.get(code),
                "lat_c": lat_c,
                "lon_c": lon_c,
                "lat2": lat_c * lat_c / 10.0,
                "lon2": lon_c * lon_c / 10.0,
                "precip_legacy": _num(row.get("precip_acumulada_mm_legacy")),
                "temp_legacy": _num(row.get("temp_media_c_legacy")),
                "precip_corrected": _num(row.get("precip_acumulada_mm_corrected")),
                "temp_corrected": _num(row.get("temp_media_c_corrected")),
                "degree_days_corrected": _num(row.get("degree_days_total_corrected")),
                "heat_corrected": _num(row.get("extreme_heat_days_corrected")),
                "deficit_cad60": _num(row.get("deficiency_cad_0_60")),
                "deficit_cad100": _num(row.get("deficiency_cad_0_100")),
                "deficit_cad200": _num(row.get("deficiency_cad_0_200")),
                "deficit_corrected_50": _num(row.get("deficiency_total_mm_corrected")),
            }
            if record["yield_kg_ha"] is None or not record["state"]:
                dropped["missing_variable"] += 1
                continue
            if not record["spatial_block"]:
                dropped["block"] += 1
                continue
            out[record["crop"]].append(record)
    out["__dropped__"] = dropped  # type: ignore[assignment]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crops", default="soja,milho,milho_2")
    args = parser.parse_args()
    crops = [c.strip() for c in args.crops.split(",") if c.strip()]

    data = load_rows()
    dropped = data.pop("__dropped__", {})
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "arm": "TE (bloco espacial e ano fora do treino)",
            "variant": "climate_plus_state (dummies de UF, igualando informação à M1)",
            "equalize": "per_cell",
            "n_repeats": N_REPEATS,
            "n_boot": N_BOOT,
            "block_radius_km": BLOCK_RADIUS_KM,
            "trend_centering": "lat+20 e lon+50 (constantes fixas, sem vazamento); quadráticos /10",
            "dropped": dropped,
        },
        "crops": {},
    }

    for crop in crops:
        rows = data.get(crop, [])
        print(f"=== {crop}: {len(rows)} linhas ===", flush=True)
        crop_out: dict[str, Any] = {"n_rows_crop": len(rows), "specs": {}, "pairs": {}}
        kept: dict[str, dict[str, Any]] = {}
        for name, variables in SPECS.items():
            usable = [
                r for r in rows if all(r.get(v) is not None for v in variables)
            ]
            if len(usable) < 400:
                crop_out["specs"][name] = {"status": "insufficient", "n": len(usable)}
                continue
            started = time.time()
            result = gen.factorial_holdout(
                usable,
                variables,
                seed=rr.SEED,
                n_repeats=N_REPEATS,
                n_boot=N_BOOT,
                variant="climate_plus_state",
                equalize="per_cell",
                keep_errors=True,
            )
            kept[name] = result
            arms = result.get("arms", {})
            te = arms.get("TE", {})
            se = arms.get("SE", {})
            versus = result.get("model_vs_baseline", {}).get("TE_vs_state", {})
            summary = {
                "status": te.get("status"),
                "n": te.get("n_rows", result.get("n_rows")),
                "cells_used": result.get("cells_used"),
                "cells_dropped": result.get("cells_dropped"),
                "mae": te.get("model", {}).get("mae_kg_ha"),
                "rmse": te.get("model", {}).get("rmse_kg_ha"),
                "baseline_m1": te.get("baselines", {}).get("state", {}).get("mae_kg_ha"),
                "delta_vs_m1": versus.get("delta_mae"),
                "ci_low": (versus.get("ci95") or [None, None])[0],
                "ci_high": (versus.get("ci95") or [None, None])[1],
                "excludes_zero": bool(
                    versus.get("ci95")
                    and (versus["ci95"][0] > 0 or versus["ci95"][1] < 0)
                ),
                "gain_percent": te.get("baselines", {}).get("state", {}).get("gain_percent"),
                "train_size_mean": te.get("train_size_mean"),
                "train_size_min": te.get("train_size_min"),
                "cells_at_target": te.get("cells_at_target"),
                "cells_below_target": te.get("cells_below_target"),
                "se_mae": se.get("model", {}).get("mae_kg_ha"),
                "se_delta_vs_m1": result.get("model_vs_baseline", {})
                .get("SE_vs_state", {})
                .get("delta_mae"),
                "paired": {
                    key: {
                        "delta_mae": value.get("model", {}).get("delta_mae"),
                        "ci95": value.get("model", {}).get("ci95"),
                        "baseline_delta": value.get("baseline", {}).get("delta_mae"),
                        "label": value.get("label"),
                    }
                    for key, value in (result.get("paired") or {}).items()
                },
                "elapsed_s": round(time.time() - started, 1),
            }
            crop_out["specs"][name] = summary
            print(
                "  %-23s TE=%9.2f M1=%9.2f delta=%8.2f [%8.1f,%8.1f] %-4s | SE=%9.2f"
                % (
                    name,
                    summary["mae"] if summary["mae"] is not None else float("nan"),
                    summary["baseline_m1"] if summary["baseline_m1"] is not None else float("nan"),
                    summary["delta_vs_m1"] if summary["delta_vs_m1"] is not None else float("nan"),
                    summary["ci_low"] if summary["ci_low"] is not None else float("nan"),
                    summary["ci_high"] if summary["ci_high"] is not None else float("nan"),
                    "sig" if summary["excludes_zero"] else "n.s.",
                    summary["se_mae"] if summary["se_mae"] is not None else float("nan"),
                ),
                flush=True,
            )

        for left, right in PAIRS:
            if left not in kept or right not in kept:
                continue
            a = kept[left].get("row_abs_errors", {}).get("TE")
            b = kept[right].get("row_abs_errors", {}).get("TE")
            if a is None or b is None or len(a) != len(b):
                crop_out["pairs"][f"{left}_vs_{right}"] = {
                    "status": "unaligned",
                    "n_left": None if a is None else len(a),
                    "n_right": None if b is None else len(b),
                }
                continue
            interval = gen.block_bootstrap_difference(
                np.asarray(a), np.asarray(b), kept[left]["row_blocks"], n_boot=N_BOOT
            )
            item = {
                "delta_mae": interval["delta_mae"],
                "ci_low": interval["ci95"][0],
                "ci_high": interval["ci95"][1],
                "excludes_zero": bool(interval["ci95"][0] > 0 or interval["ci95"][1] < 0),
                "n": int(len(a)),
                "n_blocks": int(interval["n_blocks"]),
            }
            crop_out["pairs"][f"{left}_vs_{right}"] = item
            print(
                "  pair %-42s delta=%8.2f [%8.1f,%8.1f] %s"
                % (
                    f"{left} vs {right}",
                    item["delta_mae"],
                    item["ci_low"],
                    item["ci_high"],
                    "sig" if item["excludes_zero"] else "n.s.",
                ),
                flush=True,
            )

        for name in ("legacy_climate", "corrected_climate", "trend", "trend_climate"):
            if name in kept:
                crop_out.setdefault("by_state", {})[name] = kept[name].get(
                    "by_state", {}
                ).get("TE", {})
                crop_out.setdefault("by_year", {})[name] = kept[name].get(
                    "by_year", {}
                ).get("TE", {})
        payload["crops"][crop] = crop_out

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(f"manifesto: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
