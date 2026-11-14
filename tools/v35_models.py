"""V3.5 — reprodução da V3.4, rebaseline e contraste dentro de São Paulo.

Três experimentos de ponte, com o **mesmo código** e o **mesmo protocolo**:

* **A — reconstituição**: apenas os seis estados, com os arquivos expandidos
  (as linhas históricas são cópias verbatim); deve reproduzir a V3.4;
* **B — painel expandido**: sete estados (com SP), reestimando M0/M1/M2/M2+água;
* **C — composição**: A e B lado a lado para isolar o efeito da entrada de SP.

E a análise principal: contraste **MRS 1 × MRS 3 dentro de SP**, que é a única
comparação em que a classificação regional não é determinada pela UF.

Métrica: MAE no braço TE, kg/ha. Δ = MAE(com bloco hídrico) − MAE(M2);
negativo = bloco melhor. D = Δ_grupoA − Δ_grupoB.

Uso: python tools/v35_models.py
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

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, HERE)

import run_robustness as rr  # noqa: E402
from agroclimate import generalization as gen  # noqa: E402
from agroclimate import heterogeneity, robust  # noqa: E402
from agroclimate import spatial  # noqa: E402

import v33_functional_form as v33  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
PANEL = os.path.join(PROCESSED, "v35_panel_windows.csv")
WATER = os.path.join(PROCESSED, "v35_water_variables.csv")
MAPPING = os.path.join(PROCESSED, "municipality_region_mapping_v35.csv")
OUT = os.path.join(MANIFESTS, "v35_models.json")

LEGACY_STATES = {"PR", "RS", "MS", "MT", "GO", "BA"}
CROPS = ("milho", "soja", "milho_2")
SCENARIO = {"soja": "cad_0_100", "milho": "cad_0_60", "milho_2": "cad_0_60"}
MACRO_GROUP = {"1": "MRS1", "2": "MRS2", "3": "MRS3", "4": "MRS4", "5": "MRS5"}
N_REPEATS = 3
N_BOOT = 1000


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_mapping() -> dict[str, dict[str, str]]:
    out = {}
    with open(MAPPING, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            out[str(row["ibge_code"])] = {
                "uf": row["uf"],
                "macroregion": row["macroregion"],
                "edapho_region": row["edapho_region"],
            }
    return out


def load_water() -> dict[tuple, dict]:
    out = {}
    with open(WATER, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key = (str(row["ibge_code"]), str(row["crop"]), str(row["safra"]), row["scenario"])
            out[key] = row
    return out


def load_rows() -> dict[str, list[dict]]:
    """Linhas analíticas do painel expandido, com o Δ armazenado por linha."""
    mapping = load_mapping()
    water = load_water()
    # os blocos usam o cadastro de 7 UFs; a atribuição dos municípios históricos
    # não muda com a entrada de SP (verificado: 0 alterações)
    municipalities = list(
        csv.DictReader(
            open(
                os.path.join(PROCESSED, "panel_municipalities_v35.csv"),
                newline="",
                encoding="utf-8-sig",
            )
        )
    )
    blocks = spatial.spatial_blocks(municipalities, 250.0)
    by_crop: dict[str, list[dict]] = defaultdict(list)
    dropped = defaultdict(int)
    with open(PANEL, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            crop = str(row.get("crop"))
            if crop not in CROPS:
                continue
            code = str(row["ibge_code"])
            info = mapping.get(code)
            if info is None:
                dropped["sem_regiao"] += 1
                continue
            block = blocks.get(code)
            if not block:
                dropped["sem_bloco"] += 1
                continue
            year = row.get("harvest_year")
            if year in (None, ""):
                dropped["sem_ano"] += 1
                continue
            extra = water.get((code, crop, str(row.get("safra")), SCENARIO[crop]))
            if extra is None:
                dropped["sem_agua"] += 1
                continue
            deficit = _num(extra.get("deficit_total_mm"))
            duration = _num(extra.get("stress_share"))
            if deficit is None or duration is None:
                dropped["agua_incompleta"] += 1
                continue
            precip = _num(row.get("precip_acumulada_mm_corrected"))
            temp = _num(row.get("temp_media_c_corrected"))
            yield_kg = _num(row.get("yield_kg_ha"))
            if precip is None or temp is None or yield_kg is None:
                dropped["clima_ou_produtividade"] += 1
                continue
            by_crop[crop].append(
                {
                    "ibge_code": code,
                    "crop": crop,
                    "safra": str(row.get("safra")),
                    "state": info["uf"],
                    "macroregion": info["macroregion"],
                    "year": int(float(year)),
                    "yield_kg_ha": yield_kg,
                    "spatial_block": block,
                    "precip_corrected": precip,
                    "temp_corrected": temp,
                    "wb_deficit": deficit / 100.0,
                    "wb_duration": duration,
                }
            )
    return {"crops": dict(by_crop), "dropped": dict(dropped)}


def _summarise(result: dict) -> dict[str, Any]:
    arms = result.get("arms", {})
    te = arms.get("TE", {})
    baselines = te.get("baselines", {})
    versus = result.get("model_vs_baseline", {}).get("TE_vs_state", {})
    return {
        "status": te.get("status"),
        "cells_used": result.get("cells_used"),
        "mae_model": te.get("model", {}).get("mae_kg_ha"),
        "mae_m0": baselines.get("global", {}).get("mae_kg_ha"),
        "mae_m1": baselines.get("state", {}).get("mae_kg_ha"),
        "mae_m1b": baselines.get("state_year", {}).get("mae_kg_ha"),
        "delta_vs_m1": versus.get("delta_mae"),
        "ci_vs_m1": versus.get("ci95"),
        "n": te.get("n_rows"),
    }


def _run(rows: list[dict], variables, n_repeats: int = N_REPEATS, n_boot: int = N_BOOT):
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


def _paired(left: dict, right: dict, units: str = "state_year") -> dict[str, Any]:
    a = np.asarray(left.get("row_abs_errors", {}).get("TE"))
    b = np.asarray(right.get("row_abs_errors", {}).get("TE"))
    if a.size == 0 or a.size != b.size:
        return {"status": "unaligned", "n_left": int(a.size), "n_right": int(b.size)}
    if units == "state_year":
        labels = np.array(
            [f"{s}||{y}" for s, y in zip(left["row_states"].tolist(), left["row_years"].tolist())]
        )
    elif units == "year":
        labels = np.asarray(left["row_years"]).astype(str)
    else:
        labels = np.asarray(left["row_blocks"]).astype(str)
    interval = gen.block_bootstrap_difference(a, b, labels, n_boot=N_BOOT)
    return {
        "n": int(a.size),
        "delta_mae": interval["delta_mae"],
        "ci95": interval["ci95"],
        "p_value": interval["p_value"],
        "n_units": interval["n_blocks"],
    }


def _group_delta(rows: list[dict], m2: dict, wb: dict, key: str, label: str) -> dict[str, Any]:
    a = np.asarray(m2["row_abs_errors"]["TE"])
    b = np.asarray(wb["row_abs_errors"]["TE"])
    info = {row["ibge_code"]: row for row in rows}
    labels = np.array([info.get(code, {}).get(key, "") for code in m2["row_codes"]])
    out: dict[str, Any] = {}
    for value in sorted(set(labels.tolist())):
        if not value:
            continue
        mask = labels == value
        if mask.sum() < 30:
            continue
        out[value] = {
            "n": int(mask.sum()),
            "mae_m2": float(a[mask].mean()),
            "mae_wb": float(b[mask].mean()),
            "delta": float(b[mask].mean() - a[mask].mean()),
        }
    return out


def _bootstrap_group_D(
    m2: dict, wb: dict, rows: list[dict], mask_a: np.ndarray, mask_b: np.ndarray,
    units: str, n_boot: int = N_BOOT,
) -> dict[str, Any]:
    a = np.asarray(m2["row_abs_errors"]["TE"])
    b = np.asarray(wb["row_abs_errors"]["TE"])
    diff = b - a
    if units == "year":
        labels = np.asarray(m2["row_years"]).astype(str)
    elif units == "municipality":
        labels = np.asarray(m2["row_codes"]).astype(str)
    else:
        labels = np.asarray(m2["row_blocks"]).astype(str)
    names = sorted(set(labels.tolist()))
    position = {name: i for i, name in enumerate(names)}
    codes = np.array([position[x] for x in labels.tolist()], dtype="int64")
    sum_a = np.bincount(codes, weights=np.where(mask_a, diff, 0.0), minlength=len(names))
    n_a = np.bincount(codes, weights=mask_a.astype(float), minlength=len(names))
    sum_b = np.bincount(codes, weights=np.where(mask_b, diff, 0.0), minlength=len(names))
    n_b = np.bincount(codes, weights=mask_b.astype(float), minlength=len(names))
    rng = np.random.default_rng(20261114)
    picks = rng.integers(0, len(names), size=(n_boot, len(names)))
    with np.errstate(divide="ignore", invalid="ignore"):
        delta_a = sum_a[picks].sum(axis=1) / n_a[picks].sum(axis=1)
        delta_b = sum_b[picks].sum(axis=1) / n_b[picks].sum(axis=1)
    deltas = (delta_a - delta_b)[np.isfinite(delta_a - delta_b)]
    point = float(diff[mask_a].mean() - diff[mask_b].mean()) if mask_a.any() and mask_b.any() else None
    return {
        "D": point,
        "ci95": [float(np.quantile(deltas, 0.025)), float(np.quantile(deltas, 0.975))] if deltas.size else None,
        "p_value": float(
            min(1.0, 2 * min(np.mean(deltas <= 0), np.mean(deltas >= 0)) + 1.0 / (len(deltas) + 1))
        ) if deltas.size else None,
        "n_units": len(names),
        "units": units,
    }


def main() -> int:
    started = time.time()
    loaded = load_rows()
    crops = loaded["crops"]
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "arm": "TE",
            "variant": "climate_plus_state",
            "equalize": "per_cell",
            "n_repeats": N_REPEATS,
            "n_boot": N_BOOT,
            "metric": "MAE kg/ha; delta = MAE(M2+agua) - MAE(M2); negativo = agua melhor",
            "scenario": SCENARIO,
        },
        "dropped_rows": loaded["dropped"],
        "experiments": {},
    }

    # ---------------- Experimento A: seis estados (reconstituição) ----------
    print("=== Experimento A: seis estados ===", flush=True)
    experiment_a: dict[str, Any] = {}
    kept_a: dict[str, dict] = {}
    for crop in CROPS:
        rows = [row for row in crops.get(crop, []) if row["state"] in LEGACY_STATES]
        print(f"  {crop}: {len(rows)} linhas", flush=True)
        m2 = _run(rows, v33.MODELS["M2"])
        wb = _run(rows, v33.MODELS["M2_WB_plus"])
        s2, sw = _summarise(m2), _summarise(wb)
        groups = _group_delta(rows, m2, wb, "macroregion", crop)
        sul = np.array([r["macroregion"] == "1" for r in rows])  # placeholder, refeito abaixo
        info = {row["ibge_code"]: row for row in rows}
        macro = np.array([info.get(c, {}).get("macroregion", "") for c in m2["row_codes"]])
        mask_sul = np.isin(macro, ["1"])
        mask_cerrado = np.isin(macro, ["3", "4"])
        interval = gen.block_bootstrap_difference(
            np.asarray(wb["row_abs_errors"]["TE"]),
            np.asarray(m2["row_abs_errors"]["TE"]),
            np.array(
                [
                    f"{s}||{y}"
                    for s, y in zip(m2["row_states"].tolist(), m2["row_years"].tolist())
                ]
            ),
            n_boot=N_BOOT,
        )
        del sul
        experiment_a[crop] = {
            "n_rows": len(rows),
            "m2": s2,
            "wb": sw,
            "by_macroregion": groups,
            "D_sul_vs_cerrado": _bootstrap_group_D(
                m2, wb, rows, mask_sul, mask_cerrado, units="state_year"
            ),
            "paired_wb_vs_m2": {
                "delta_mae": interval["delta_mae"],
                "ci95": interval["ci95"],
                "p_value": interval["p_value"],
            },
        }
        kept_a[crop] = {"m2": m2, "wb": wb}
        d = experiment_a[crop]["D_sul_vs_cerrado"]["D"]
        print(f"    M2={s2['mae_model']:.1f} WB={sw['mae_model']:.1f} D(Sul-Cerrado)={d:+.1f}" if d else "", flush=True)
    payload["experiments"]["A_six_states"] = experiment_a

    # ---------------- Experimento B: sete estados (expandido) --------------
    print("=== Experimento B: sete estados ===", flush=True)
    experiment_b: dict[str, Any] = {}
    kept_b: dict[str, dict] = {}
    for crop in CROPS:
        rows = crops.get(crop, [])
        print(f"  {crop}: {len(rows)} linhas", flush=True)
        m2 = _run(rows, v33.MODELS["M2"])
        wb = _run(rows, v33.MODELS["M2_WB_plus"])
        s2, sw = _summarise(m2), _summarise(wb)
        experiment_b[crop] = {
            "n_rows": len(rows),
            "m2": s2,
            "wb": sw,
            "by_state": _group_delta(rows, m2, wb, "state", crop),
            "by_macroregion": _group_delta(rows, m2, wb, "macroregion", crop),
            "paired_wb_vs_m2": _paired(wb, m2, units="state_year"),
        }
        kept_b[crop] = {"m2": m2, "wb": wb}
        print(
            f"    M0={s2['mae_m0']:.1f} M1={s2['mae_m1']:.1f} M2={s2['mae_model']:.1f} "
            f"WB={sw['mae_model']:.1f}",
            flush=True,
        )
    payload["experiments"]["B_expanded"] = experiment_b

    # ---------------- Experimento C: comparação de composição --------------
    comparison: dict[str, Any] = {}
    for crop in CROPS:
        a = experiment_a[crop]
        b = experiment_b[crop]
        comparison[crop] = {
            "mae_m0_legacy": a["m2"]["mae_m0"],
            "mae_m0_expanded": b["m2"]["mae_m0"],
            "mae_m1_legacy": a["m2"]["mae_m1"],
            "mae_m1_expanded": b["m2"]["mae_m1"],
            "mae_m2_legacy": a["m2"]["mae_model"],
            "mae_m2_expanded": b["m2"]["mae_model"],
            "mae_wb_legacy": a["wb"]["mae_model"],
            "mae_wb_expanded": b["wb"]["mae_model"],
            "delta_m1_vs_m0_legacy": a["m2"]["mae_m0"] - a["m2"]["mae_m1"],
            "delta_m1_vs_m0_expanded": b["m2"]["mae_m0"] - b["m2"]["mae_m1"],
            "note": (
                "as MAEs dos dois painéis não são diretamente comparáveis: o conjunto de "
                "linhas de teste muda com a entrada de SP"
            ),
        }
    payload["experiments"]["C_composition"] = comparison

    # ---------------- D dentro de São Paulo --------------------------------
    print("=== dentro de SP: MRS 1 x MRS 3 ===", flush=True)
    within: dict[str, Any] = {}
    for crop in CROPS:
        rows = [row for row in crops.get(crop, []) if row["state"] == "SP"]
        by_macro = defaultdict(int)
        for row in rows:
            by_macro[row["macroregion"]] += 1
        entry: dict[str, Any] = {"n_rows_sp": len(rows), "rows_by_macroregion": dict(by_macro)}
        if by_macro.get("1", 0) < 60 or by_macro.get("3", 0) < 60:
            entry["status"] = "insufficient_rows"
            within[crop] = entry
            print(f"  {crop}: insuficiente {dict(by_macro)}", flush=True)
            continue
        m2 = _run(rows, v33.MODELS["M2"])
        wb = _run(rows, v33.MODELS["M2_WB_plus"])
        info = {row["ibge_code"]: row for row in rows}
        macro = np.array([info.get(c, {}).get("macroregion", "") for c in m2["row_codes"]])
        mask1 = macro == "1"
        mask3 = macro == "3"
        entry["per_group"] = _group_delta(rows, m2, wb, "macroregion", crop)
        entry["D_mrs1_vs_mrs3"] = {
            "year": _bootstrap_group_D(m2, wb, rows, mask1, mask3, units="year"),
            "municipality": _bootstrap_group_D(m2, wb, rows, mask1, mask3, units="municipality"),
        }
        # associação: interação bloco hídrico × MRS1 (dentro de SP)
        subset = [row for row in rows if row["macroregion"] in ("1", "3")]
        for row in subset:
            row["x_water"] = row["wb_deficit"]
            row["x_mrs1"] = row["wb_deficit"] * (1.0 if row["macroregion"] == "1" else 0.0)
        entry["association"] = heterogeneity.joint_significance(
            subset, ("x_water", "x_mrs1"), test_variables=("x_mrs1",), cluster="two_way"
        )
        s2, sw = _summarise(m2), _summarise(wb)
        entry["m2"] = s2
        entry["wb"] = sw
        within[crop] = entry
        d = entry["D_mrs1_vs_mrs3"]
        print(
            f"  {crop}: n={entry['n_rows_sp']} D={d['year']['D']:+.1f} "
            f"(ano CI {d['year']['ci95']}) interação p={entry['association']['joint_test']['p_value']:.4f}"
            if d["year"]["D"] is not None
            else f"  {crop}: n={entry['n_rows_sp']} sem D",
            flush=True,
        )
    payload["within_sp"] = within

    # ---------------- transferência: treinar sem SP, testar em SP ----------
    print("=== transferência (treino sem SP, teste em SP) ===", flush=True)
    transfer: dict[str, Any] = {}
    for crop in CROPS:
        rows = crops.get(crop, [])
        legacy_rows = [row for row in rows if row["state"] in LEGACY_STATES]
        sp_rows = [row for row in rows if row["state"] == "SP"]
        if len(legacy_rows) < 500 or len(sp_rows) < 30:
            continue
        states = sorted({row["state"] for row in rows})
        position = {state: index for index, state in enumerate(states)}
        def matrix(part):
            return np.array(
                [[row["precip_corrected"], row["temp_corrected"]] for row in part],
                dtype="float64",
            ), np.array([row["yield_kg_ha"] for row in part], dtype="float64"), np.array(
                [position[row["state"]] for row in part], dtype="int64"
            )
        x_train, y_train, s_train = matrix(legacy_rows)
        x_test, y_test, s_test = matrix(sp_rows)
        prediction = gen._fit_predict(
            x_train, y_train, x_test, state_train=s_train, state_test=s_test,
            variant="climate_plus_state",
        )
        if prediction is None:
            continue
        mae_sp = float(np.mean(np.abs(prediction - y_test)))
        mae_m0 = float(np.mean(np.abs(y_test - y_train.mean())))
        transfer[crop] = {
            "n_train_legacy": len(legacy_rows),
            "n_test_sp": len(sp_rows),
            "mae_m2_trained_on_legacy": mae_sp,
            "mae_m0_global_mean": mae_m0,
            "gain_vs_m0": mae_m0 - mae_sp,
            "gain_percent": 100.0 * (mae_m0 - mae_sp) / mae_m0 if mae_m0 else None,
            "note": (
                "treino em todos os anos das 6 UFs e teste nos municípios de SP: mede "
                "transferência para uma UF nunca vista, não validação temporal"
            ),
        }
        print(
            f"  {crop}: MAE_SP={mae_sp:.1f} vs M0={mae_m0:.1f} "
            f"({transfer[crop]['gain_percent']:+.1f}%)",
            flush=True,
        )
    payload["transfer"] = transfer

    payload["elapsed_s"] = round(time.time() - started, 1)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(f"\nmanifesto: {OUT} ({payload['elapsed_s']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
