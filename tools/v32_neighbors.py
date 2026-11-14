"""V3.2 — reavaliação do M1c (vizinhos históricos) com decomposição e pareamento.

Fase 10 do roadmap. A V3.1 comparou M1c com M1 nas mesmas linhas, mas não
comparou M1c com M2 de forma pareada (conjuntos de linhas diferentes) e não
separou o desempenho dos casos atendidos por vizinhos do desempenho dos casos
que caíram no fallback.

Aqui cada linha é prevista exatamente uma vez por cada modelo, e as previsões
são **alinhadas por (município, ano)** antes de qualquer comparação. Assim:

* a cobertura agregada não esconde a degeneração do baseline;
* M1c é comparado com M1 **e** com M2 nos mesmos casos;
* o IC da diferença usa bloco espacial e UF×ano (D104).

Uso: python tools/v32_neighbors.py
"""

from __future__ import annotations

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
OUT_JSON = os.path.join(MANIFESTS, "v32_neighbors_paired.json")

PRIMARY = ("precip_corrected", "temp_corrected")
CROPS = ("soja", "milho", "milho_2")
CONFIGS = (
    {"radius_km": 100.0, "decay_km": 50.0, "min_neighbors": 3},
    {"radius_km": 200.0, "decay_km": 100.0, "min_neighbors": 3},
    {"radius_km": 300.0, "decay_km": 150.0, "min_neighbors": 3},
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _align(errors: np.ndarray, codes: np.ndarray, years: np.ndarray) -> dict[str, float]:
    return {
        f"{code}||{year}": float(value)
        for code, year, value in zip(codes.tolist(), years.tolist(), errors.tolist())
    }


def _interval(a: np.ndarray, b: np.ndarray, blocks, state_years, n_boot: int = 1000):
    out = {"delta_mae": float(np.mean(a) - np.mean(b)), "n": int(a.size)}
    for label, units in (("block", blocks), ("state_year", state_years)):
        result = gen.block_bootstrap_difference(a, b, units, n_boot=n_boot)
        out[label] = {
            "ci95": result["ci95"],
            "n_units": result["n_blocks"],
            "excludes_zero": bool(result["ci95"][0] > 0 or result["ci95"][1] < 0),
        }
    return out


def main() -> int:
    started = time.time()
    data = base.load_rows()
    data.pop("__dropped__", None)
    coordinates = base.load_coordinates()
    payload: dict[str, Any] = {
        "generated_at": _now(),
        "definition": (
            "M1c = media das produtividades de treino dos municipios vizinhos; "
            "treino TE exclui bloco e ano do teste; fallback = media da UF no treino"
        ),
        "comparisons": (
            "cada linha prevista uma vez por modelo; alinhamento por (municipio, ano); "
            "M2 avaliado com equalize=global e sem subamostragem para cobrir todas as linhas"
        ),
        "configs": list(CONFIGS),
        "crops": {},
    }

    for crop in CROPS:
        rows = data.get(crop, [])
        enriched = []
        for row in rows:
            position = coordinates.get(row["ibge_code"])
            if position is None:
                continue
            enriched.append(dict(row, latitude=position[0], longitude=position[1]))
        print(f"=== {crop}: {len(enriched)} linhas ===", flush=True)
        entry: dict[str, Any] = {"n_rows": len(enriched), "configs": {}}

        common = gen.factorial_holdout(
            enriched,
            PRIMARY,
            seed=rr.SEED,
            n_repeats=1,
            n_boot=300,
            variant="climate_plus_state",
            equalize="global",
            keep_errors=True,
        )
        m2_errors = _align(
            np.asarray(common["row_abs_errors"]["TE"]),
            common["row_codes"],
            common["row_years_raw"],
        )
        blocks_map = {
            f"{code}||{year}": block
            for code, year, block in zip(
                common["row_codes"].tolist(),
                common["row_years_raw"].tolist(),
                common["row_blocks"].tolist(),
            )
        }
        print(f"  M2: {len(m2_errors)} previsões", flush=True)

        for config in CONFIGS:
            label = "r{radius}_d{decay}_k{min_neighbors}".format(
                radius=int(config["radius_km"]),
                decay=int(config["decay_km"]),
                min_neighbors=config["min_neighbors"],
            )
            result = gen.neighbor_holdout(
                enriched,
                radius_km=config["radius_km"],
                min_neighbors=config["min_neighbors"],
                decay_km=config["decay_km"],
                seed=rr.SEED,
                n_boot=1000,
            )
            if result.get("status") != "ok":
                entry["configs"][label] = {"status": result.get("status")}
                continue
            codes = result["row_codes"]
            years = np.array([str(int(v)) for v in result["row_years"]])
            keys = np.array([f"{c}||{y}" for c, y in zip(codes.tolist(), years.tolist())])
            fallback = np.asarray(result["row_fallback"], dtype=bool)
            neighbour_err = np.asarray(result["row_abs_errors"])
            state_err = np.asarray(result["row_abs_baseline"])
            blocks = np.asarray(result["row_blocks"])
            state_years = np.array([f"{s}||{y}" for s, y in zip(result["row_states"].tolist(), years.tolist())])

            has_m2 = np.array([key in m2_errors for key in keys.tolist()])
            m2_err = np.array([m2_errors.get(key, np.nan) for key in keys.tolist()])

            covered = ~fallback
            detail: dict[str, Any] = {
                "coverage_direct": float(covered.mean()),
                "fallback_share": float(fallback.mean()),
                "aggregate": {
                    "mae_m1c": float(neighbour_err.mean()),
                    "mae_m1": float(state_err.mean()),
                    "m1c_vs_m1": _interval(neighbour_err, state_err, blocks, state_years),
                },
                "covered_subset": None,
                "fallback_subset": None,
                "vs_m2": {},
                "n_aligned_with_m2": int(has_m2.sum()),
            }
            if covered.any():
                detail["covered_subset"] = {
                    "n": int(covered.sum()),
                    "mae_m1c": float(neighbour_err[covered].mean()),
                    "mae_m1": float(state_err[covered].mean()),
                    "m1c_vs_m1": _interval(
                        neighbour_err[covered], state_err[covered], blocks[covered], state_years[covered]
                    ),
                }
            if fallback.any():
                detail["fallback_subset"] = {
                    "n": int(fallback.sum()),
                    "mae_m1c": float(neighbour_err[fallback].mean()),
                    "mae_m1": float(state_err[fallback].mean()),
                }
            if has_m2.any():
                subset = has_m2 & np.isfinite(m2_err)
                detail["vs_m2"] = {
                    "n": int(subset.sum()),
                    "mae_m1c": float(neighbour_err[subset].mean()),
                    "mae_m2": float(m2_err[subset].mean()),
                    "m1c_vs_m2": _interval(
                        neighbour_err[subset], m2_err[subset], blocks[subset], state_years[subset]
                    ),
                    "subset_covered_only": None,
                }
                inner = subset & covered
                if inner.any():
                    detail["vs_m2"]["subset_covered_only"] = {
                        "n": int(inner.sum()),
                        "mae_m1c": float(neighbour_err[inner].mean()),
                        "mae_m2": float(m2_err[inner].mean()),
                        "m1c_vs_m2": _interval(
                            neighbour_err[inner], m2_err[inner], blocks[inner], state_years[inner]
                        ),
                    }
            entry["configs"][label] = detail
            agg = detail["aggregate"]["m1c_vs_m1"]
            print(
                "  %-16s mae=%8.1f M1=%8.1f dM1=%+8.2f%s cov=%.3f | vs M2 d=%+8.2f%s"
                % (
                    label,
                    detail["aggregate"]["mae_m1c"],
                    detail["aggregate"]["mae_m1"],
                    agg["delta_mae"],
                    "*" if agg["state_year"]["excludes_zero"] else " ",
                    detail["coverage_direct"],
                    detail["vs_m2"]["m1c_vs_m2"]["delta_mae"] if detail["vs_m2"] else float("nan"),
                    "*" if detail["vs_m2"] and detail["vs_m2"]["m1c_vs_m2"]["state_year"]["excludes_zero"] else " ",
                ),
                flush=True,
            )
        payload["crops"][crop] = entry

    payload["elapsed_s"] = round(time.time() - started, 1)
    os.makedirs(MANIFESTS, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(f"manifesto: {OUT_JSON} ({payload['elapsed_s']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
