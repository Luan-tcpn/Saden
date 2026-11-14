"""V3.2 — comparação preditiva: M2 comum vs inclinações por UF.

Fases 4–6 e 9 do roadmap. Todos os modelos usam o **mesmo** estimador, as
mesmas células, a mesma equalização e as mesmas linhas de teste — é o que torna
a comparação pareada:

* ``M2_common``  — precipitação + temperatura + dummies de UF (V3.1, D101);
* ``M2_HET_FE``  — o mesmo + interações UF × clima, MQO (inclinações livres);
* ``M2_HET_PP``  — interações com encolhimento escolhido por validação interna
  dentro do pool de treino de cada célula (partial pooling).

O IC da diferença de MAE é calculado com **dois** esquemas de reamostragem:
bloco espacial (padrão das versões anteriores) e UF×ano (unidade
correspondente à variação climática — D104). Reportar os dois evita repetir a
superconfiança que a V3.2 encontrou na inferência de inclinações.

Uso:
    python tools/v32_predictive.py --stage main
    python tools/v32_predictive.py --stage robustness
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, HERE)

import run_robustness as rr  # noqa: E402
from agroclimate import generalization as gen  # noqa: E402

import v31_models as base  # noqa: E402

MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT_MAIN = os.path.join(MANIFESTS, "v32_predictive.json")
OUT_ROBUST = os.path.join(MANIFESTS, "v32_robustness.json")

PRIMARY = ("precip_corrected", "temp_corrected")
CROPS = ("soja", "milho", "milho_2")
PENALTY_GRID = (0.0, 0.01, 0.1, 1.0, 10.0, 100.0)
N_REPEATS = 3
N_BOOT = 1000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summarise(result: dict[str, Any]) -> dict[str, Any]:
    arms = result.get("arms", {})
    te = arms.get("TE", {})
    versus = result.get("model_vs_baseline", {}).get("TE_vs_state", {})
    se = arms.get("SE", {})
    return {
        "status": te.get("status"),
        "cells_used": result.get("cells_used"),
        "cells_dropped": result.get("cells_dropped"),
        "mae_te": te.get("model", {}).get("mae_kg_ha"),
        "rmse_te": te.get("model", {}).get("rmse_kg_ha"),
        "m1_te": te.get("baselines", {}).get("state", {}).get("mae_kg_ha"),
        "delta_vs_m1": versus.get("delta_mae"),
        "ci95_vs_m1": versus.get("ci95"),
        "mae_se": se.get("model", {}).get("mae_kg_ha"),
        "delta_vs_m1_se": (
            result.get("model_vs_baseline", {}).get("SE_vs_state", {}).get("delta_mae")
        ),
        "train_size_mean": te.get("train_size_mean"),
        "train_size_min": te.get("train_size_min"),
        "cells_at_target": te.get("cells_at_target"),
        "cells_below_target": te.get("cells_below_target"),
        "interactions": result.get("interactions"),
        "interaction_states": result.get("interaction_states"),
        "penalty_selection": result.get("penalty_selection"),
        "by_state": result.get("by_state", {}).get("TE", {}),
        "by_year": result.get("by_year", {}).get("TE", {}),
    }


def _run(rows, interactions: bool, penalty_grid, n_repeats: int, n_boot: int):
    return gen.factorial_holdout(
        rows,
        PRIMARY,
        seed=rr.SEED,
        n_repeats=n_repeats,
        n_boot=n_boot,
        variant="climate_plus_state",
        equalize="per_cell",
        keep_errors=True,
        interactions=interactions,
        penalty_grid=penalty_grid,
    )


def _paired(a, b, blocks, state_years, n_boot=N_BOOT):
    """IC da diferença de MAE com dois esquemas de reamostragem."""
    ea = np.asarray(a.get("row_abs_errors", {}).get("TE"))
    eb = np.asarray(b.get("row_abs_errors", {}).get("TE"))
    if ea.size == 0 or ea.size != eb.size:
        return {"status": "unaligned", "n": int(ea.size), "n_other": int(eb.size)}
    out: dict[str, Any] = {"n": int(ea.size), "delta_mae": float(np.mean(ea) - np.mean(eb))}
    for label, units in (("block", blocks), ("state_year", state_years)):
        interval = gen.block_bootstrap_difference(ea, eb, units, n_boot=n_boot)
        out[label] = {
            "ci95": interval["ci95"],
            "n_units": interval["n_blocks"],
            "excludes_zero": bool(interval["ci95"][0] > 0 or interval["ci95"][1] < 0),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="main", choices=("main", "robustness"))
    args = parser.parse_args()

    started = time.time()
    data = base.load_rows()
    data.pop("__dropped__", None)
    payload: dict[str, Any] = {
        "generated_at": _now(),
        "preregistration": "docs/V3_2_PREREGISTRATION.md",
        "protocol": {
            "arm": "TE (bloco espacial e grupo temporal fora do treino)",
            "variant": "climate_plus_state",
            "equalize": "per_cell",
            "n_repeats": N_REPEATS,
            "n_boot": N_BOOT,
            "variables": list(PRIMARY),
            "penalty_grid": list(PENALTY_GRID),
            "penalty_scale": "relativa a diagonal de Gram; encolhimento 1/(1+lambda)",
            "descricao_mae": "MAE em kg/ha; delta = MAE(modelo) - MAE(M2 comum); negativo = melhor",
        },
        "crops": {},
    }

    if args.stage == "main":
        out_path = OUT_MAIN
        for crop in CROPS:
            rows = data.get(crop, [])
            print(f"=== {crop}: {len(rows)} linhas ===", flush=True)
            entry: dict[str, Any] = {"n_rows": len(rows), "models": {}, "pairs": {}}
            kept: dict[str, Any] = {}
            for label, interactions, grid in (
                ("M2_common", False, None),
                ("M2_HET_FE", True, None),
                ("M2_HET_PP", True, PENALTY_GRID),
            ):
                tick = time.time()
                result = _run(rows, interactions, grid, N_REPEATS, N_BOOT)
                kept[label] = result
                summary = _summarise(result)
                entry["models"][label] = summary
                print(
                    "  %-12s TE=%9.2f M1=%9.2f delta=%+9.2f cells=%s λ=%s (%.0fs)"
                    % (
                        label,
                        summary["mae_te"] or float("nan"),
                        summary["m1_te"] or float("nan"),
                        (summary["mae_te"] - summary["m1_te"])
                        if summary["mae_te"] and summary["m1_te"]
                        else float("nan"),
                        summary["cells_used"],
                        (summary["penalty_selection"] or {}).get("TE", {}).get("lambda_counts"),
                        time.time() - tick,
                    ),
                    flush=True,
                )
            blocks = kept["M2_common"]["row_blocks"]
            state_years = np.array(
                [
                    f"{s}||{y}"
                    for s, y in zip(
                        kept["M2_common"]["row_states"].tolist(),
                        kept["M2_common"]["row_years"].tolist(),
                    )
                ]
            )
            for left, right in (
                ("M2_HET_FE", "M2_common"),
                ("M2_HET_PP", "M2_common"),
                ("M2_HET_FE", "M2_HET_PP"),
            ):
                pair = _paired(kept[left], kept[right], blocks, state_years)
                entry["pairs"][f"{left}_vs_{right}"] = pair
                if pair.get("status") != "unaligned":
                    print(
                        "  pair %-24s delta=%+8.2f bloco[%7.1f,%7.1f]%s  UFxano[%7.1f,%7.1f]%s"
                        % (
                            f"{left} vs {right}",
                            pair["delta_mae"],
                            pair["block"]["ci95"][0],
                            pair["block"]["ci95"][1],
                            "*" if pair["block"]["excludes_zero"] else " ",
                            pair["state_year"]["ci95"][0],
                            pair["state_year"]["ci95"][1],
                            "*" if pair["state_year"]["excludes_zero"] else " ",
                        ),
                        flush=True,
                    )
            # caminho de lambda: modelos com encolhimento fixo
            entry["lambda_path"] = {}
            for lam in (0.1, 1.0, 10.0):
                result = _run(rows, True, (lam,), N_REPEATS, N_BOOT)
                summary = _summarise(result)
                pair = _paired(result, kept["M2_common"], blocks, state_years)
                entry["lambda_path"][str(lam)] = {"mae_te": summary["mae_te"], "pair": pair}
                print(
                    "  lambda=%-5s TE=%9.2f delta=%+8.2f"
                    % (
                        lam,
                        summary["mae_te"] or float("nan"),
                        pair.get("delta_mae", float("nan")),
                    ),
                    flush=True,
                )
            payload["crops"][crop] = entry
    else:
        out_path = OUT_ROBUST
        for crop in CROPS:
            rows = data.get(crop, [])
            print(f"=== {crop}: robustez ===", flush=True)
            entry: dict[str, Any] = {"n_rows": len(rows), "leave_one_uf_out": {}, "leave_one_year_out": {}}
            states = sorted({row["state"] for row in rows})
            years = sorted({row["year"] for row in rows})
            for state in states:
                subset = [row for row in rows if row["state"] != state]
                common = _run(subset, False, None, 1, 300)
                hetero = _run(subset, True, PENALTY_GRID, 1, 300)
                pair = _paired(
                    hetero,
                    common,
                    common["row_blocks"],
                    np.array(
                        [
                            f"{s}||{y}"
                            for s, y in zip(
                                common["row_states"].tolist(),
                                common["row_years"].tolist(),
                            )
                        ]
                    ),
                    n_boot=300,
                )
                entry["leave_one_uf_out"][state] = pair
                print(
                    "  drop %-3s delta=%+8.2f bloco[%7.1f,%7.1f]%s"
                    % (
                        state,
                        pair.get("delta_mae", float("nan")),
                        pair.get("block", {}).get("ci95", [float("nan")] * 2)[0],
                        pair.get("block", {}).get("ci95", [float("nan")] * 2)[1],
                        "*" if pair.get("block", {}).get("excludes_zero") else " ",
                    ),
                    flush=True,
                )
            for year in years:
                subset = [row for row in rows if row["year"] != year]
                common = _run(subset, False, None, 1, 300)
                hetero = _run(subset, True, PENALTY_GRID, 1, 300)
                pair = _paired(
                    hetero,
                    common,
                    common["row_blocks"],
                    np.array(
                        [
                            f"{s}||{y}"
                            for s, y in zip(
                                common["row_states"].tolist(),
                                common["row_years"].tolist(),
                            )
                        ]
                    ),
                    n_boot=300,
                )
                entry["leave_one_year_out"][str(year)] = pair
                print(
                    "  drop %s delta=%+8.2f" % (year, pair.get("delta_mae", float("nan"))),
                    flush=True,
                )
            payload["crops"][crop] = entry

    payload["elapsed_s"] = round(time.time() - started, 1)
    os.makedirs(MANIFESTS, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(f"manifesto: {out_path} ({payload['elapsed_s']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
