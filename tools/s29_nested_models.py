"""V2.9 — modelos aninhados M0 → M1 → M2 (D91).

A pergunta central da V2.9 é **quanto o clima acrescenta além da região**.
Para isso a comparação precisa ser aninhada e com o mesmo conjunto de treino:

* **M0** — média global do treino;
* **M1** — média por UF do treino (fallback global para UF ausente);
* **M2** — UF + variáveis agroclimáticas (``climate_plus_state``).

As três usam exatamente o mesmo conjunto de treino e o mesmo conjunto de
teste; o que muda é a informação disponível. A resposta de interesse é
``M2 − M1`` (valor incremental do clima **dentro** da UF), com IC por
bootstrap de bloco. ``M0b`` é o modelo histórico (``climate_only``), mantido
para não apagar a comparação das versões anteriores.

Equalização estrita por célula (D90) e 5 repetições; MAE/RMSE por repetição.

Uso:
    python tools/s29_nested_models.py
    python tools/s29_nested_models.py --quick
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

OUT = os.path.join(ROOT, "geospatial", "data", "manifests", "v29_nested_models.json")
CROPS = ("soja", "milho", "milho_2")
FAMILIES = ("B_meteorologicos", "C_thermal", "D_hidricos")
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
        "delta_mae": round(block["delta_mae"], 3),
        "ci95": [round(block["ci95"][0], 3), round(block["ci95"][1], 3)],
        "significativo": bool(
            block["ci95"][0] > 0 or block["ci95"][1] < 0
        ),
    }


def _nest(result, arm):
    entry = result["arms"].get(arm, {})
    if entry.get("status") != "ok":
        return {"status": entry.get("status")}
    bases = entry.get("baselines", {})
    model = entry["model"]
    return {
        "M0_global": round(bases["global"]["mae_kg_ha"], 3),
        "M1_state": round(bases["state"]["mae_kg_ha"], 3),
        "M1b_state_year": round(bases["state_year"]["mae_kg_ha"], 3),
        "M2_model": round(model["mae_kg_ha"], 3),
        "M2_rmse": round(model["rmse_kg_ha"], 3),
        "gain_vs_M0_percent": round(bases["global"]["gain_percent"], 3),
        "gain_vs_M1_percent": round(bases["state"]["gain_percent"], 3),
        "train_size_mean": round(entry["train_size_mean"], 1),
        "train_size_min": entry["train_size_min"],
        "cells_below_target": entry.get("cells_below_target"),
        "state_fallback_share": round(entry.get("state_fallback_share", 0.0), 6),
        "mae_repeat_sd": round(
            entry.get("repeat_metrics", {}).get("mae_sd", 0.0), 4
        ),
        "M2_minus_M1": _delta(result["model_vs_baseline"][f"{arm}_vs_state"]),
        "M2_minus_M0": _delta(result["model_vs_baseline"][f"{arm}_vs_global"]),
        "M1_minus_M0": _delta(result["baseline_pairs"][f"{arm}_state_minus_global"]),
        "M1b_minus_M1": _delta(
            result["baseline_pairs"][f"{arm}_state_year_minus_state"]
        ),
        "by_state": {
            state: {
                "n": item["n"],
                "mae_model": round(item["mae_model"], 2),
                "mae_state": round(item.get("mae_state_baseline", float("nan")), 2),
                "delta": round(item.get("delta_model_minus_state", float("nan")), 2),
            }
            for state, item in result.get("by_state", {}).get(arm, {}).items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    crops = ("soja",) if args.quick else CROPS
    families = ("B_meteorologicos",) if args.quick else FAMILIES

    rows = rr.prepare(rr.load_panel())
    by_crop: dict[str, list[dict]] = {}
    for row in rows:
        by_crop.setdefault(row["crop"], []).append(row)

    payload: dict = {
        "generated_at": _now(),
        "seed": rr.SEED,
        "method": (
            "Modelos aninhados M0 (media global) -> M1 (media por UF) -> "
            "M2 (UF + clima). Mesmo treino e mesmo teste nos tres; "
            "equalizacao estrita por celula (D90); IC por bootstrap de bloco. "
            "M1b (UF x ano) e diagnostico contemporaneo, nao operacional. "
            "M0b = climate_only, mantido para a comparacao historica."
        ),
        "n_repeats": args.repeats,
        "crops": {},
    }
    started = time.time()
    for crop in crops:
        subset = by_crop.get(crop, [])
        if not subset:
            continue
        crop_out: dict = {"n_rows": len(subset), "families": {}}
        for family in families:
            variables = rr.MODELS[family]
            fair = gen.factorial_holdout(
                subset,
                variables,
                seed=rr.SEED,
                n_repeats=args.repeats,
                n_boot=1000,
                variant="climate_plus_state",
                equalize="per_cell",
            )
            historical = gen.factorial_holdout(
                subset,
                variables,
                seed=rr.SEED,
                n_repeats=args.repeats,
                n_boot=1000,
                variant="climate_only",
                equalize="per_cell",
            )
            crop_out["families"][family] = {
                "variables": list(variables),
                "cells_used": fair.get("cells_used"),
                "cells_dropped": fair.get("cells_dropped"),
                "M2_climate_plus_state": {
                    arm: _clean(_nest(fair, arm)) for arm in ARMS
                },
                "M0b_climate_only": {
                    arm: _clean(_nest(historical, arm)) for arm in ARMS
                },
            }
            row = []
            for arm in ("SS", "SE", "TS", "TE"):
                entry = crop_out["families"][family]["M2_climate_plus_state"][arm]
                if "M2_model" in entry:
                    d = entry["M2_minus_M1"]
                    row.append(
                        f"{arm}: M1={entry['M1_state']:.1f} M2={entry['M2_model']:.1f} "
                        f"d={d['delta_mae']:+.1f}[{d['ci95'][0]:+.1f},{d['ci95'][1]:+.1f}]"
                    )
            print(f"{crop:<8} {family:<16} " + " | ".join(row), flush=True)
        payload["crops"][crop] = crop_out
    payload["elapsed_s"] = round(time.time() - started, 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(f"manifesto: {OUT} ({payload['elapsed_s']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
