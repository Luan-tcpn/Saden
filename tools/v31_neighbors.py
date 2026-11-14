"""V3.1 — baseline de vizinhos históricos (M1c) no protocolo TE.

Pergunta: a produtividade **já observada** em municípios vizinhos acrescenta
informação sobre um município não observado além da média da UF?

O desenho é o TE: o treino de cada célula exclui simultaneamente o bloco
espacial e o grupo temporal do teste. Nenhuma produtividade do ano de teste e
nenhuma do bloco de teste entram na previsão.

A grade de parâmetros (raio, decaimento, mínimo de vizinhos) é fixada **antes**
da avaliação e reportada integralmente — nenhuma configuração é escolhida pelo
resultado em TE.

Uso: python tools/v31_neighbors.py
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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

import run_robustness as rr  # noqa: E402
from agroclimate import generalization as gen  # noqa: E402
from agroclimate import spatial  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
PANEL = os.path.join(PROCESSED, "v31_panel_windows.csv")
OUT_JSON = os.path.join(MANIFESTS, "v31_neighbors_baseline.json")

BLOCK_RADIUS_KM = 250.0
GRID = (
    {"radius_km": 100.0, "decay_km": 50.0, "min_neighbors": 3},
    {"radius_km": 200.0, "decay_km": 100.0, "min_neighbors": 3},
    {"radius_km": 300.0, "decay_km": 150.0, "min_neighbors": 3},
    {"radius_km": 200.0, "decay_km": None, "min_neighbors": 3},
    {"radius_km": 200.0, "decay_km": 100.0, "min_neighbors": 6},
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
    with open(PANEL, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            code = str(row["ibge_code"])
            position = coordinates.get(code)
            year = row.get("harvest_year")
            if position is None or year in (None, ""):
                continue
            if not blocks.get(code) or not row.get("state"):
                continue
            yield_value = _num(row.get("yield_kg_ha"))
            if yield_value is None:
                continue
            out[str(row["crop"])].append(
                {
                    "ibge_code": code,
                    "state": row.get("state"),
                    "year": int(float(year)),
                    "yield_kg_ha": yield_value,
                    "spatial_block": blocks.get(code),
                    "latitude": position[0],
                    "longitude": position[1],
                }
            )
    return out


def main() -> int:
    started = time.time()
    data = load_rows()
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "arm": "TE (bloco espacial e grupo temporal fora do treino)",
            "baseline": "M1c — média das produtividades de treino dos municípios vizinhos",
            "comparison": "M1 — média da UF calculada somente no treino, nas mesmas linhas",
            "grid": list(GRID),
            "block_radius_km": BLOCK_RADIUS_KM,
            "note": "grade fixada antes da avaliação; nenhuma configuração escolhida por TE",
        },
        "crops": {},
    }
    for crop in ("soja", "milho", "milho_2"):
        rows = data.get(crop, [])
        print(f"=== {crop}: {len(rows)} linhas ===", flush=True)
        crop_out: dict[str, Any] = {"n_rows": len(rows), "configs": {}}
        for config in GRID:
            label = "r{radius}_d{decay}_k{min_neighbors}".format(
                radius=int(config["radius_km"]),
                decay="none" if config["decay_km"] is None else int(config["decay_km"]),
                min_neighbors=config["min_neighbors"],
            )
            result = gen.neighbor_holdout(
                rows,
                radius_km=config["radius_km"],
                min_neighbors=config["min_neighbors"],
                decay_km=config["decay_km"],
                seed=rr.SEED,
                n_boot=1000,
            )
            entry = {
                key: value
                for key, value in result.items()
                if not key.startswith("row_")
            }
            crop_out["configs"][label] = entry
            if result.get("status") == "ok":
                print(
                    "  %-16s mae=%9.2f M1=%9.2f delta=%8.2f [%8.1f,%8.1f] cov=%.3f fb=%.3f"
                    % (
                        label,
                        entry["mae"],
                        entry["mae_baseline_state"],
                        entry["delta_mae"],
                        entry["ci95"][0],
                        entry["ci95"][1],
                        entry["coverage_direct"],
                        entry["fallback_state_share"],
                    ),
                    flush=True,
                )
        payload["crops"][crop] = crop_out
    payload["elapsed_s"] = round(time.time() - started, 1)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(f"manifesto: {OUT_JSON} ({payload['elapsed_s']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
