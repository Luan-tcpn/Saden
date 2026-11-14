"""V3.0 — reestimação M0/M1/M2 com o déficit recalculado (D98).

Compara três representações do estresse hídrico, mantendo todo o resto igual:

* ``hist``      — déficit do painel histórico (CAD = 50 mm, janela truncada);
* ``corr50``    — janela corrigida, CAD = 50 mm (isola o efeito da janela);
* ``cad60/100/200`` — janela corrigida + CAD oficial do município.

O estimador é o mesmo de V2.9: fatorial espaço × tempo, ``climate_plus_state``,
equalização estrita por célula (D90), IC por bootstrap de bloco. ``TE`` é a
referência para qualquer alegação de generalização (D91).

Uso:
    python tools/v30_models_cad.py
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

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

import run_robustness as rr  # noqa: E402
from agroclimate import generalization as gen  # noqa: E402
from agroclimate import spatial  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
RECALC = os.path.join(PROCESSED, "v30_panel_cad.csv")
OUT = os.path.join(MANIFESTS, "v30_models_cad.json")

SPECS = {
    "climate_hist": ("precip_hist", "temp_media_c"),
    "climate_corr": ("precip_corr", "temp_media_c"),
    "water_hist": ("deficit_hist",),
    "water_corr50": ("deficit_corr50",),
    "water_cad60": ("deficit_cad60",),
    "water_cad100": ("deficit_cad100",),
    "water_cad200": ("deficit_cad200",),
}
CROPS = ("soja", "milho", "milho_2")
ARMS = ("SS", "SE", "TS", "TE")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value):
    if isinstance(value, dict):
        return {
            key: _clean(item)
            for key, item in value.items()
            if not key.startswith("_")
            and key not in ("test_blocks", "test_years", "test_states")
        }
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_rows() -> list[dict]:
    with open(RECALC, newline="", encoding="utf-8-sig") as handle:
        recalc = {
            (row["ibge_code"], row["crop"], row["safra"]): row
            for row in csv.DictReader(handle)
        }
    municipalities = rr.load_municipalities()
    blocks = spatial.spatial_blocks(municipalities, 250.0)
    raw = rr.load_panel()
    rows = []
    missing = 0
    for row in raw:
        if str(row.get("status")) != "paired_usable":
            continue
        if str(row.get("climate_source")) != "NASA-POWER":
            continue
        key = (str(row["ibge_code"]), str(row["crop"]), str(row.get("safra")))
        extra = recalc.get(key)
        if extra is None:
            missing += 1
            continue
        year = row.get("harvest_year") or row.get("pam_reference_year")
        if year in (None, ""):
            continue
        deficit_values = {
            "deficit_hist": _num(extra.get("hist_def_cad50")),
            "deficit_corr50": _num(extra.get("corr_def_v26_50")),
            "deficit_cad60": _num(extra.get("corr_def_cad_0_60")),
            "deficit_cad100": _num(extra.get("corr_def_cad_0_100")),
            "deficit_cad200": _num(extra.get("corr_def_cad_0_200")),
            "precip_hist": _num(row.get("precip_acumulada_mm")),
            "precip_corr": _num(extra.get("corr_precip_mm")),
            "temp_media_c": _num(row.get("temp_media_c")),
        }
        if any(value is None for value in deficit_values.values()):
            missing += 1
            continue
        found = dict(deficit_values)
        found.update(
            {
                "ibge_code": str(row["ibge_code"]),
                "crop": str(row["crop"]),
                "state": row.get("state"),
                "year": int(year),
                "yield_kg_ha": _num(row.get("yield_kg_ha")),
                "spatial_block": blocks.get(str(row["ibge_code"])),
            }
        )
        if found["yield_kg_ha"] is None or not found["spatial_block"]:
            missing += 1
            continue
        rows.append(found)
    return rows, {"rows": len(rows), "dropped": missing}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    rows, join = load_rows()
    print(f"linhas utilizáveis: {join['rows']} (descartadas {join['dropped']})", flush=True)
    by_crop: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_crop[row["crop"]].append(row)

    payload = {
        "generated_at": _now(),
        "method": (
            "Fatorial espaco x tempo com climate_plus_state, equalizacao "
            "estrita por celula e IC por bootstrap de bloco. Cada spec difere "
            "apenas na variavel hidrica; precipitacao e temperatura acompanham "
            "a janela (hist ou corrigida)."
        ),
        "join": join,
        "n_repeats": args.repeats,
        "crops": {},
    }
    started = time.time()
    for crop in CROPS:
        subset = by_crop.get(crop, [])
        if not subset:
            continue
        crop_out = {"n_rows": len(subset), "specs": {}}
        for spec, variables in SPECS.items():
            result = gen.factorial_holdout(
                subset,
                variables,
                seed=rr.SEED,
                n_repeats=args.repeats,
                n_boot=1000,
                variant="climate_plus_state",
                equalize="per_cell",
            )
            entry = {
                "variables": list(variables),
                "cells_used": result.get("cells_used"),
                "arms": {},
                "paired": {},
            }
            for arm in ARMS:
                arm_entry = result["arms"].get(arm, {})
                if arm_entry.get("status") != "ok":
                    continue
                entry["arms"][arm] = {
                    "mae": round(arm_entry["model"]["mae_kg_ha"], 2),
                    "rmse": round(arm_entry["model"]["rmse_kg_ha"], 2),
                    "gain_vs_M1": round(
                        arm_entry["baselines"]["state"]["gain_percent"], 3
                    ),
                    "delta_vs_M1": round(
                        result["model_vs_baseline"][f"{arm}_vs_state"]["delta_mae"], 2
                    ),
                    "ci95_vs_M1": [
                        round(result["model_vs_baseline"][f"{arm}_vs_state"]["ci95"][0], 2),
                        round(result["model_vs_baseline"][f"{arm}_vs_state"]["ci95"][1], 2),
                    ],
                }
            for key, value in result.get("paired", {}).items():
                entry["paired"][key] = {
                    "delta_mae": round(value["model"]["delta_mae"], 2),
                    "ci95": [
                        round(value["model"]["ci95"][0], 2),
                        round(value["model"]["ci95"][1], 2),
                    ],
                }
            crop_out["specs"][spec] = _clean(entry)
            te = entry["arms"].get("TE", {})
            se = entry["arms"].get("SE", {})
            print(
                f"{crop:<8} {spec:<15} TE mae={te.get('mae')} dM1={te.get('delta_vs_M1')}"
                f" {te.get('ci95_vs_M1')} | SE mae={se.get('mae')}"
                f" | espaco(SS-SE)={entry['paired'].get('SS_minus_SE', {}).get('delta_mae')}",
                flush=True,
            )
        payload["crops"][crop] = crop_out
    payload["elapsed_s"] = round(time.time() - started, 1)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(f"manifesto: {OUT} ({payload['elapsed_s']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
