"""V2.9 — sensibilidade à escala do bloco espacial e decomposição por UF (D92).

A V2.7 fixou o bloco em 250 km pelo correlograma, mas a correlação das
anomalias não cai a zero em 600 km. A V2.8 mostrou que a separação do bloco
domina o erro do milho. Este script responde:

1. **Qual a sensibilidade do efeito espacial à escala do bloco** — 150, 250,
   400 e 600 km —, com o número de blocos e o poder estatístico de cada
   escolha explicitamente registrados.
2. **Quanto do efeito do bloco é heterogeneidade dentro da UF**: para cada
   UF, compara-se a MAE com o bloco compartilhado (``SS``) e com o bloco
   removido (``SE``), no mesmo modelo (``climate_plus_state``).

A escolha de 250 km **não** é reotimizada para maximizar ganho: todas as
escalas são reportadas e as limitações de cada uma (poucos blocos) são
registradas.

Uso:
    python tools/s29_block_scale.py
    python tools/s29_block_scale.py --quick
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

import run_robustness as rr  # noqa: E402
from agroclimate import generalization as gen  # noqa: E402

OUT = os.path.join(ROOT, "geospatial", "data", "manifests", "v29_block_scale.json")
CROPS = ("soja", "milho", "milho_2")
FAMILIES = ("B_meteorologicos", "D_hidricos")
SCALES_KM = (150.0, 250.0, 400.0, 600.0)
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


def _delta(block):
    return {
        "delta_mae": round(block["delta_mae"], 2),
        "ci95": [round(block["ci95"][0], 2), round(block["ci95"][1], 2)],
        "significativo": bool(block["ci95"][0] > 0 or block["ci95"][1] < 0),
    }


def _summarize(result, scales_block_counts=None):
    arms = result.get("arms", {})
    out = {
        "n_blocks": result.get("n_blocks"),
        "cells_used": result.get("cells_used"),
        "cells_dropped": result.get("cells_dropped"),
        "arms": {},
        "space_effect": {},
        "by_state_space_effect": {},
    }
    for arm in ARMS:
        entry = arms.get(arm, {})
        if entry.get("status") != "ok":
            out["arms"][arm] = {"status": entry.get("status")}
            continue
        out["arms"][arm] = {
            "mae": round(entry["model"]["mae_kg_ha"], 2),
            "rmse": round(entry["model"]["rmse_kg_ha"], 2),
            "train_size_mean": round(entry["train_size_mean"], 1),
            "cells_below_target": entry.get("cells_below_target"),
        }
    for key, value in result.get("paired", {}).items():
        if key in ("SS_minus_SE", "TS_minus_TE", "SS_minus_TS", "SE_minus_TE"):
            out["space_effect"][key] = _delta(value["model"])
    ss_states = result.get("by_state", {}).get("SS", {})
    se_states = result.get("by_state", {}).get("SE", {})
    for state in sorted(set(ss_states) & set(se_states)):
        out["by_state_space_effect"][state] = {
            "n": ss_states[state]["n"],
            "mae_block_shared": round(ss_states[state]["mae_model"], 2),
            "mae_block_removed": round(se_states[state]["mae_model"], 2),
            "delta_removed_minus_shared": round(
                se_states[state]["mae_model"] - ss_states[state]["mae_model"], 2
            ),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    crops = ("milho",) if args.quick else CROPS
    families = ("B_meteorologicos",) if args.quick else FAMILIES

    payload: dict = {
        "generated_at": _now(),
        "seed": rr.SEED,
        "method": (
            "Fatorial espaco x tempo (equalizacao estrita por celula, D90) "
            "repetido em escalas de bloco de 150/250/400/600 km, com "
            "climate_plus_state. A escala de 250 km e a de referencia e NAO e "
            "reotimizada: todas sao reportadas."
        ),
        "n_repeats": args.repeats,
        "scales_km": list(SCALES_KM),
        "crops": {},
    }
    started = time.time()
    for block_km in SCALES_KM:
        os.environ["SADEN_V27_BLOCK_KM"] = str(block_km)
        rows = rr.prepare(rr.load_panel())
        by_crop: dict[str, list[dict]] = {}
        for row in rows:
            by_crop.setdefault(row["crop"], []).append(row)
        payload["crops"][str(int(block_km))] = {}
        for crop in crops:
            subset = by_crop.get(crop, [])
            if not subset:
                continue
            blocks = len({r["spatial_block"] for r in subset if r.get("spatial_block")})
            payload["crops"][str(int(block_km))][crop] = {
                "n_rows": len(subset),
                "n_blocks": blocks,
                "families": {},
            }
            for family in families:
                result = gen.factorial_holdout(
                    subset,
                    rr.MODELS[family],
                    seed=rr.SEED,
                    n_repeats=args.repeats,
                    n_boot=1000,
                    variant="climate_plus_state",
                    equalize="per_cell",
                )
                payload["crops"][str(int(block_km))][crop]["families"][family] = _clean(
                    _summarize(result)
                )
                entry = payload["crops"][str(int(block_km))][crop]["families"][family]
                space = entry["space_effect"].get("SS_minus_SE", {})
                print(
                    f"{int(block_km):>4} km {crop:<8} {family:<16} blocks={blocks:<3} "
                    f"SS={entry['arms'].get('SS', {}).get('mae', float('nan')):.1f} "
                    f"SE={entry['arms'].get('SE', {}).get('mae', float('nan')):.1f} "
                    f"space={space.get('delta_mae', float('nan')):+.1f}"
                    f"[{space.get('ci95', [float('nan'), float('nan')])[0]:+.1f},"
                    f"{space.get('ci95', [float('nan'), float('nan')])[1]:+.1f}]",
                    flush=True,
                )
    payload["elapsed_s"] = round(time.time() - started, 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(f"manifesto: {OUT} ({payload['elapsed_s']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
