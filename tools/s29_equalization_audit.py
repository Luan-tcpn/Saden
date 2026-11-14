"""V2.9 — auditoria da equalização de amostra da V2.8 (D90).

A V2.8 concluiu que a redução de amostra não explicava a inversão do P5, mas
a equalização usada era **global**: o alvo era um número único e, quando um
braço tinha menos material numa célula, ele ficava abaixo do alvo naquela
célula (11 de 25 células na soja, com o braço ``TE`` chegando a 4.308 linhas
contra um alvo de 5.686).

Este script refaz a comparação com **equalização estrita por célula**: em
cada célula, os quatro braços são reamostrados para o menor conjunto
disponível, de modo que o tamanho de treino seja idêntico *naquela célula*.
O conjunto de teste é o mesmo nos quatro braços (cada linha prevista uma vez).

Também reporta MAE e RMSE **por repetição**, com a dispersão entre repetições
— as repetições não são observações de teste independentes.

Uso:
    python tools/s29_equalization_audit.py
    python tools/s29_equalization_audit.py --quick
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

OUT = os.path.join(
    ROOT, "geospatial", "data", "manifests", "v29_equalization_audit.json"
)
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
            if not key.startswith("_") and key not in ("test_blocks", "test_years")
        }
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def _summarize(result, label):
    arms = result.get("arms", {})
    out = {
        "label": label,
        "equalize": result.get("equalize"),
        "cells_used": result.get("cells_used"),
        "cells_dropped": result.get("cells_dropped"),
        "test_rows": int(sum(1 for _ in [])) if False else None,
        "arms": {},
        "paired": {},
    }
    for arm in ARMS:
        entry = arms.get(arm, {})
        if entry.get("status") != "ok":
            out["arms"][arm] = {"status": entry.get("status")}
            continue
        repeat = entry.get("repeat_metrics", {})
        out["arms"][arm] = {
            "train_size_mean": round(entry["train_size_mean"], 1),
            "train_size_min": entry["train_size_min"],
            "train_size_max": entry["train_size_max"],
            "train_size_sd": round(entry["train_size_sd"], 1),
            "cells_at_target": entry.get("cells_at_target"),
            "cells_below_target": entry.get("cells_below_target"),
            "mae": round(entry["model"]["mae_kg_ha"], 4),
            "rmse": round(entry["model"]["rmse_kg_ha"], 4),
            "mae_repeat_sd": round(repeat.get("mae_sd", 0.0), 4),
            "rmse_repeat_sd": round(repeat.get("rmse_sd", 0.0), 4),
            "gain_vs_global_percent": round(
                entry["baselines"]["global"]["gain_percent"], 4
            ),
            "gain_vs_state_percent": round(
                entry["baselines"]["state"]["gain_percent"], 4
            ),
        }
    for key, value in result.get("paired", {}).items():
        model = value["model"]
        out["paired"][key] = {
            "delta_mae": round(model["delta_mae"], 4),
            "ci95": [round(model["ci95"][0], 4), round(model["ci95"][1], 4)],
        }
    for key, value in result.get("model_vs_baseline", {}).items():
        out["paired"].setdefault("model_vs_baseline", {})[key] = {
            "delta_mae": round(value["delta_mae"], 4),
            "ci95": [round(value["ci95"][0], 4), round(value["ci95"][1], 4)],
        }
    return out


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
            "Compara a equalizacao GLOBAL da V2.8 (alvo unico; bracos com "
            "menos material ficam abaixo do alvo) com a equalizacao ESTRITA "
            "POR CELULA (alvo = menor conjunto disponivel entre os 4 bracos). "
            "Mesmo conjunto de teste nos 4 bracos; MAE/RMSE por repeticao."
        ),
        "n_repeats": args.repeats,
        "variant": "climate_plus_state",
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
            global_res = gen.factorial_holdout(
                subset,
                variables,
                seed=rr.SEED,
                size_fraction=0.64,
                n_repeats=args.repeats,
                n_boot=1000,
                variant="climate_plus_state",
                equalize="global",
            )
            strict_res = gen.factorial_holdout(
                subset,
                variables,
                seed=rr.SEED,
                n_repeats=args.repeats,
                n_boot=1000,
                variant="climate_plus_state",
                equalize="per_cell",
            )
            crop_out["families"][family] = {
                "variables": list(variables),
                "global": _clean(_summarize(global_res, "global")),
                "per_cell": _clean(_summarize(strict_res, "per_cell")),
            }
            g = crop_out["families"][family]["global"]
            s = crop_out["families"][family]["per_cell"]
            print(
                f"{crop:<8} {family:<16} "
                + " ".join(
                    f"{arm}: g={g['arms'][arm]['mae']:.1f}"
                    f"/pc={s['arms'][arm]['mae']:.1f}"
                    for arm in ARMS
                    if g["arms"].get(arm, {}).get("status") == "ok"
                ),
                flush=True,
            )
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
