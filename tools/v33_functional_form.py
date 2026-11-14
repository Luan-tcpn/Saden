"""V3.3 — Frente A: forma funcional do balanço hídrico e exposição térmica.

Compara, no protocolo TE, com as mesmas células e as mesmas linhas de teste:

* ``M2``             — precipitação + temperatura + UF (referência V3.1/V3.2);
* ``M2_WB``          — déficit + duração do estresse + UF (só o bloco hídrico);
* ``M2_WB_plus``     — M2 + déficit + duração (incremental sobre o clima bruto);
* ``M2_THERM``       — graus-dia + UF;
* ``M2_WB_THERM``    — déficit + duração + graus-dia + UF;
* ``M2_WB_NL``       — déficit + déficit² + duração + UF (não linearidade);
* ``M2_WB_THERM_INT``— M2_WB_THERM + interação déficit × graus-dia (exploratório).

O lado inferencial (teste de Wald conjunto do bloco, *within* de município e ano,
agrupado por UF×ano e município) é calculado no mesmo manifesto: associação e
predição são relatadas separadamente.

Uso:
    python tools/v33_functional_form.py --stage main
    python tools/v33_functional_form.py --stage robustness
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
sys.path.insert(0, HERE)

import run_robustness as rr  # noqa: E402
from agroclimate import generalization as gen  # noqa: E402
from agroclimate import heterogeneity  # noqa: E402

import v31_models as base  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
WATER = os.path.join(PROCESSED, "v33_water_variables.csv")
OUT_MAIN = os.path.join(MANIFESTS, "v33_functional_form.json")
OUT_ROBUST = os.path.join(MANIFESTS, "v33_functional_robustness.json")

SCENARIO = {"soja": "cad_0_100", "milho": "cad_0_60", "milho_2": "cad_0_60"}

MODELS: dict[str, tuple[str, ...]] = {
    "M2": ("precip_corrected", "temp_corrected"),
    "M2_WB": ("wb_deficit", "wb_duration"),
    "M2_WB_plus": ("precip_corrected", "temp_corrected", "wb_deficit", "wb_duration"),
    "M2_THERM": ("thermal_gdd",),
    "M2_WB_THERM": ("wb_deficit", "wb_duration", "thermal_gdd"),
    "M2_WB_NL": ("wb_deficit", "wb_deficit_sq", "wb_duration"),
    "M2_WB_THERM_INT": ("wb_deficit", "wb_duration", "thermal_gdd", "int_deficit_gdd"),
}

PAIRS = (
    ("M2_WB_plus", "M2"),
    ("M2_WB_THERM", "M2_WB_plus"),
    ("M2_WB_NL", "M2_WB_plus"),
    ("M2_WB", "M2"),
    ("M2_THERM", "M2"),
    ("M2_WB_THERM_INT", "M2_WB_THERM"),
)

CONFIRMATORY = (
    ("M2_WB_plus", "M2", "H1"),
    ("M2_WB_THERM", "M2_WB_plus", "H4"),
    ("M2_WB_NL", "M2_WB_plus", "H2"),
)

N_REPEATS = 3
N_BOOT = 1000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_water() -> dict[tuple, dict]:
    out = {}
    with open(WATER, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key = (str(row["ibge_code"]), str(row["crop"]), str(row["safra"]), row["scenario"])
            out[key] = row
    return out


def build_rows(crop: str, data: dict, water: dict) -> list[dict]:
    scenario = SCENARIO[crop]
    rows = []
    for row in data.get(crop, []):
        extra = water.get((row["ibge_code"], crop, row["safra"], scenario))
        if extra is None:
            continue
        deficit = _num(extra.get("deficit_total_mm"))
        duration = _num(extra.get("stress_share"))
        if deficit is None or duration is None:
            continue
        merged = dict(row)
        merged["wb_deficit"] = deficit / 100.0          # escala fixa (100 mm)
        merged["wb_duration"] = duration                # fração da janela
        merged["wb_deficit_sq"] = merged["wb_deficit"] ** 2
        merged["wb_etr"] = _num(extra.get("etr_over_etp"))
        merged["thermal_gdd"] = row["degree_days_corrected"] / 1000.0
        merged["thermal_heat"] = row["heat_corrected"] / 10.0
        merged["int_deficit_gdd"] = merged["wb_deficit"] * merged["thermal_gdd"]
        merged["water_scenario"] = scenario
        merged["cad_mm"] = _num(extra.get("cad_mm"))
        rows.append(merged)
    return rows


def _summarise(result: dict) -> dict[str, Any]:
    te = result.get("arms", {}).get("TE", {})
    versus = result.get("model_vs_baseline", {}).get("TE_vs_state", {})
    se = result.get("arms", {}).get("SE", {})
    return {
        "status": te.get("status"),
        "cells_used": result.get("cells_used"),
        "mae_te": te.get("model", {}).get("mae_kg_ha"),
        "rmse_te": te.get("model", {}).get("rmse_kg_ha"),
        "m1_te": te.get("baselines", {}).get("state", {}).get("mae_kg_ha"),
        "delta_vs_m1": versus.get("delta_mae"),
        "ci95_vs_m1": versus.get("ci95"),
        "mae_se": se.get("model", {}).get("mae_kg_ha"),
        "cells_at_target": te.get("cells_at_target"),
        "cells_below_target": te.get("cells_below_target"),
        "by_state": result.get("by_state", {}).get("TE", {}),
        "by_year": result.get("by_year", {}).get("TE", {}),
    }


def _run(rows, variables, n_repeats=N_REPEATS, n_boot=N_BOOT):
    return gen.factorial_holdout(
        rows,
        variables,
        seed=rr.SEED,
        n_repeats=n_repeats,
        n_boot=n_boot,
        variant="climate_plus_state",
        equalize="per_cell",
        keep_errors=True,
    )


def _paired(left, right, n_boot=N_BOOT) -> dict[str, Any]:
    a = np.asarray(left.get("row_abs_errors", {}).get("TE"))
    b = np.asarray(right.get("row_abs_errors", {}).get("TE"))
    if a.size == 0 or a.size != b.size:
        return {"status": "unaligned", "n_left": int(a.size), "n_right": int(b.size)}
    blocks = left["row_blocks"]
    state_years = np.array(
        [
            f"{s}||{y}"
            for s, y in zip(left["row_states"].tolist(), left["row_years"].tolist())
        ]
    )
    record: dict[str, Any] = {"n": int(a.size), "delta_mae": float(np.mean(a) - np.mean(b))}
    for label, units in (("block", blocks), ("state_year", state_years)):
        interval = gen.block_bootstrap_difference(a, b, units, n_boot=n_boot)
        record[label] = {
            "ci95": interval["ci95"],
            "p_value": interval["p_value"],
            "n_units": interval["n_blocks"],
            "excludes_zero": bool(interval["ci95"][0] > 0 or interval["ci95"][1] < 0),
        }
    return record


def _holm(p_values: dict[str, float]) -> dict[str, float]:
    from agroclimate import robust

    return robust.holm_adjust(p_values) if p_values else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="main", choices=("main", "robustness"))
    args = parser.parse_args()

    started = time.time()
    data = base.load_rows()
    data.pop("__dropped__", None)
    water = load_water()
    payload: dict[str, Any] = {
        "generated_at": _now(),
        "preregistration": "docs/V3_3_FUNCTIONAL_FORM_PREREGISTRATION.md",
        "protocol": {
            "arm": "TE",
            "variant": "climate_plus_state",
            "equalize": "per_cell",
            "n_repeats": N_REPEATS,
            "n_boot": N_BOOT,
            "scenario": SCENARIO,
            "units": "MAE em kg/ha; delta = MAE(modelo) - MAE(referencia); negativo = melhor",
            "transforms": "wb_deficit = deficit/100; gdd/1000; sq = (deficit/100)^2 (constantes fixas)",
        },
        "inference": {},
        "crops": {},
    }

    if args.stage == "main":
        out_path = OUT_MAIN
        # --- lado inferencial (within, UFxano + municipio) -------------------
        print("=== inferencia (within, UFxano + municipio) ===", flush=True)
        for crop in ("milho", "soja", "milho_2"):
            rows = build_rows(crop, data, water)
            water_block = heterogeneity.joint_significance(
                rows, ("precip_corrected", "temp_corrected", "wb_deficit", "wb_duration"),
                test_variables=("wb_deficit", "wb_duration"),
            )
            thermal_block = heterogeneity.joint_significance(
                rows, ("precip_corrected", "temp_corrected", "wb_deficit", "wb_duration", "thermal_gdd"),
                test_variables=("thermal_gdd",),
            )
            nonlinear = heterogeneity.joint_significance(
                rows,
                ("precip_corrected", "temp_corrected", "wb_deficit", "wb_deficit_sq", "wb_duration"),
                test_variables=("wb_deficit_sq",),
            )
            payload["inference"][crop] = {
                "n_rows": len(rows),
                "water_block_beyond_climate": water_block,
                "thermal_beyond_water": thermal_block,
                "nonlinearity": nonlinear,
            }
            for label, entry in (
                ("agua", water_block),
                ("termico", thermal_block),
                ("nao-linear", nonlinear),
            ):
                test = entry.get("joint_test", {})
                print(
                    "  %-8s %-11s Wald/sd=%.2f p=%.4f (G=%s)"
                    % (
                        crop,
                        label,
                        test.get("statistic") or float("nan"),
                        test.get("p_value") if test.get("p_value") is not None else float("nan"),
                        test.get("df2"),
                    ),
                    flush=True,
                )

        # --- lado preditivo ---------------------------------------------------
        for crop in ("milho", "soja", "milho_2"):
            rows = build_rows(crop, data, water)
            print(f"=== {crop}: {len(rows)} linhas ({SCENARIO[crop]}) ===", flush=True)
            entry: dict[str, Any] = {
                "n_rows": len(rows),
                "scenario": SCENARIO[crop],
                "models": {},
                "pairs": {},
            }
            kept: dict[str, Any] = {}
            for label, variables in MODELS.items():
                usable = [r for r in rows if all(r.get(v) is not None for v in variables)]
                if len(usable) < 400:
                    entry["models"][label] = {"status": "insufficient", "n": len(usable)}
                    continue
                result = _run(usable, variables)
                kept[label] = result
                summary = _summarise(result)
                summary["n_used"] = len(usable)
                entry["models"][label] = summary
                print(
                    "  %-18s TE=%9.2f M1=%9.2f dM1=%+8.2f n=%d"
                    % (
                        label,
                        summary["mae_te"] or float("nan"),
                        summary["m1_te"] or float("nan"),
                        (summary["mae_te"] - summary["m1_te"])
                        if summary["mae_te"] and summary["m1_te"]
                        else float("nan"),
                        len(usable),
                    ),
                    flush=True,
                )
            for left, right in PAIRS:
                if left not in kept or right not in kept:
                    continue
                pair = _paired(kept[left], kept[right])
                entry["pairs"][f"{left}_vs_{right}"] = pair
                if pair.get("status") != "unaligned":
                    print(
                        "  pair %-28s d=%+8.2f bloco[%8.1f,%8.1f]%s UFxano[%8.1f,%8.1f]%s"
                        % (
                            f"{left}-{right}",
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
            payload["crops"][crop] = entry

        # --- família de associação -------------------------------------------
        # O pré-registro fixou a família *preditiva* confirmatória (3 testes no
        # milho) e tratou os testes de Wald como complementares, sem fixar a
        # família. Para não ler p-valores brutos como evidência, aplica-se Holm
        # aos 3 blocos dentro de cada cultura — e isso é registrado como limite,
        # não como família pré-registrada (ver relatório).
        payload["association_families"] = {}
        for crop, entry in payload["inference"].items():
            raw = {
                "agua": entry["water_block_beyond_climate"]["joint_test"]["p_value"],
                "termico": entry["thermal_beyond_water"]["joint_test"]["p_value"],
                "nao_linear": entry["nonlinearity"]["joint_test"]["p_value"],
            }
            raw = {k: float(v) for k, v in raw.items() if v is not None}
            payload["association_families"][crop] = {
                "family": "3 blocos dentro da cultura (agua, termico, nao linear)",
                "size": len(raw),
                "method": "Holm",
                "preregistered": crop == "milho",
                "raw": raw,
                "holm": _holm(raw),
            }
        print("\n=== associação (Holm por cultura) ===")
        for crop, entry in payload["association_families"].items():
            for key in sorted(entry["raw"]):
                print(
                    "  %-8s %-10s p=%.4f holm=%.4f"
                    % (crop, key, entry["raw"][key], entry["holm"][key])
                )

        # --- família confirmatória (milho) -----------------------------------
        milho = payload["crops"]["milho"]["pairs"]
        raw: dict[str, float] = {}
        for left, right, hypothesis in CONFIRMATORY:
            pair = milho.get(f"{left}_vs_{right}")
            if not pair or pair.get("status") == "unaligned":
                continue
            # p do bootstrap pareado na unidade UF×ano (D104), não derivado do IC
            raw[hypothesis] = float(pair["state_year"]["p_value"])
        payload["confirmatory_family"] = {
            "crop": "milho",
            "size": len(raw),
            "method": "Holm",
            "p_source": "bootstrap pareado por UFxano (sinal da diferenca de MAE)",
            "raw": raw,
            "holm": _holm(raw),
            "rejected": sorted(k for k, v in _holm(raw).items() if v is not None and v < 0.05),
        }
        print("\n=== família confirmatória (milho) ===")
        holm = _holm(raw)
        for key in sorted(raw):
            print(
                "  %-3s p=%.4f holm=%.4f %s"
                % (key, raw[key], holm[key], "REJEITA" if holm[key] < 0.05 else "n.s.")
            )
    else:
        out_path = OUT_ROBUST
        for crop in ("milho", "soja", "milho_2"):
            rows = build_rows(crop, data, water)
            print(f"=== {crop}: robustez ===", flush=True)
            entry: dict[str, Any] = {"leave_one_uf_out": {}, "leave_one_year_out": {}}
            for state in sorted({r["state"] for r in rows}):
                subset = [r for r in rows if r["state"] != state]
                reference = _run(subset, MODELS["M2"], 1, 300)
                candidate = _run(subset, MODELS["M2_WB_plus"], 1, 300)
                pair = _paired(candidate, reference, n_boot=300)
                entry["leave_one_uf_out"][state] = pair
                print(
                    "  drop %-3s d=%+8.2f bloco[%8.1f,%8.1f]"
                    % (
                        state,
                        pair.get("delta_mae", float("nan")),
                        pair.get("block", {}).get("ci95", [float("nan")] * 2)[0],
                        pair.get("block", {}).get("ci95", [float("nan")] * 2)[1],
                    ),
                    flush=True,
                )
            for year in sorted({r["year"] for r in rows}):
                subset = [r for r in rows if r["year"] != year]
                reference = _run(subset, MODELS["M2"], 1, 300)
                candidate = _run(subset, MODELS["M2_WB_plus"], 1, 300)
                pair = _paired(candidate, reference, n_boot=300)
                entry["leave_one_year_out"][str(year)] = pair
                print(
                    "  drop %s d=%+8.2f" % (year, pair.get("delta_mae", float("nan"))),
                    flush=True,
                )
            payload["crops"][crop] = entry

    payload["elapsed_s"] = round(time.time() - started, 1)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(f"manifesto: {out_path} ({payload['elapsed_s']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
