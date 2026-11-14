"""V3.4 — contraste regional do bloco hídrico (Sul × Cerrado).

Reproduz M2 e M2+bloco hídrico **exatamente** como na V3.3 e testa se a diferença
de perda associada ao bloco hídrico difere entre as regiões agronômicas definidas
no protocolo congelado.

Métrica: MAE no braço TE, kg/ha. Δ = MAE(com bloco) − MAE(sem bloco); negativo =
o bloco reduz o erro. D = Δ_Sul − Δ_Cerrado.

Dois lados, separados:

* **predição** — contraste de ΔMAE nas mesmas linhas de teste;
* **associação** — interação bloco hídrico × Sul no modelo *within* de município
  e ano, agrupada por UF×ano + município.

Uso:
    python tools/v34_regional_contrast.py --stage main
    python tools/v34_regional_contrast.py --stage robustness
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
from agroclimate import heterogeneity, robust  # noqa: E402
from agroclimate import spatial  # noqa: E402

import v31_models as base  # noqa: E402
import v33_functional_form as v33  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
MAPPING = os.path.join(PROCESSED, "municipality_region_mapping.csv")
OUT_MAIN = os.path.join(MANIFESTS, "v34_regional_contrast.json")
OUT_ROBUST = os.path.join(MANIFESTS, "v34_regional_robustness.json")

CROPS = ("milho", "soja", "milho_2")
PRIMARY_CROP = "milho"
MACRO_GROUP = {"1": "Sul", "2": "Transicao", "3": "Cerrado", "4": "Cerrado", "5": "Fora"}
N_REPEATS = 3
N_BOOT = 1000


def load_groups() -> dict[str, dict[str, str]]:
    out = {}
    with open(MAPPING, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            out[str(row["ibge_code"])] = {
                "uf": row["uf"],
                "macroregion": row["macroregion"],
                "edapho_region": row["edapho_region"],
                "group": MACRO_GROUP.get(row["macroregion"], "Fora"),
            }
    return out


def build_rows(crop: str, data: dict, water: dict, groups: dict) -> list[dict]:
    rows = v33.build_rows(crop, data, water)
    out = []
    for row in rows:
        info = groups.get(row["ibge_code"])
        if info is None:
            continue
        merged = dict(row)
        merged["group"] = info["group"]
        merged["macroregion"] = info["macroregion"]
        merged["edapho_region"] = info["edapho_region"]
        out.append(merged)
    return out


def per_region_delta(rows: list[dict], m2: dict, wb: dict) -> dict[str, Any]:
    """ΔMAE por região nas mesmas linhas de teste."""
    a = np.asarray(m2["row_abs_errors"]["TE"])
    b = np.asarray(wb["row_abs_errors"]["TE"])
    if a.size != b.size:
        return {"status": "unaligned", "n_m2": int(a.size), "n_wb": int(b.size)}
    codes = m2["row_codes"]
    macro_by_code = {row["ibge_code"]: row["macroregion"] for row in rows}
    group_by_macro = MACRO_GROUP
    groups = np.array([group_by_macro.get(macro_by_code.get(code, ""), "Fora") for code in codes])
    out: dict[str, Any] = {"n_total": int(a.size), "groups": {}}
    for group in ("Sul", "Cerrado", "Transicao", "Fora"):
        mask = groups == group
        if not mask.any():
            continue
        out["groups"][group] = {
            "n": int(mask.sum()),
            "mae_m2": float(a[mask].mean()),
            "mae_wb": float(b[mask].mean()),
            "delta": float(b[mask].mean() - a[mask].mean()),
        }
    if "Sul" in out["groups"] and "Cerrado" in out["groups"]:
        out["D"] = out["groups"]["Sul"]["delta"] - out["groups"]["Cerrado"]["delta"]
    out["_masks"] = {group: (groups == group) for group in ("Sul", "Cerrado")}
    out["_inequality"] = b - a
    out["_groups"] = groups
    return out


def _bootstrap_D(inequality: np.ndarray, groups: np.ndarray, units: np.ndarray,
                 n_boot: int = N_BOOT, seed: int = 20261114) -> dict[str, Any]:
    names = sorted(set(units.tolist()))
    position = {name: index for index, name in enumerate(names)}
    codes = np.array([position[u] for u in units.tolist()], dtype="int64")
    sul = groups == "Sul"
    cerrado = groups == "Cerrado"
    sum_s = np.bincount(codes, weights=np.where(sul, inequality, 0.0), minlength=len(names))
    n_s = np.bincount(codes, weights=sul.astype("float64"), minlength=len(names))
    sum_c = np.bincount(codes, weights=np.where(cerrado, inequality, 0.0), minlength=len(names))
    n_c = np.bincount(codes, weights=cerrado.astype("float64"), minlength=len(names))
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(names), size=(n_boot, len(names)))
    total_s = n_s[picks].sum(axis=1)
    total_c = n_c[picks].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        delta_s = sum_s[picks].sum(axis=1) / total_s
        delta_c = sum_c[picks].sum(axis=1) / total_c
    deltas = delta_s - delta_c
    deltas = deltas[np.isfinite(deltas)]
    return {
        "n_units": len(names),
        "ci95": [float(np.quantile(deltas, 0.025)), float(np.quantile(deltas, 0.975))],
        "p_value": float(
            min(1.0, 2 * min(np.mean(deltas <= 0), np.mean(deltas >= 0)) + 1.0 / (len(deltas) + 1))
        ),
        "n_boot_effective": int(deltas.size),
    }


def contrast(entry: dict[str, Any], m2: dict, n_boot: int = N_BOOT) -> dict[str, Any]:
    inequality = entry["_inequality"]
    groups = entry["_groups"]
    blocks = m2["row_blocks"]
    state_years = np.array(
        [f"{s}||{y}" for s, y in zip(m2["row_states"].tolist(), m2["row_years"].tolist())]
    )
    out = {"D": entry.get("D"), "n_sul": entry["groups"].get("Sul", {}).get("n"),
           "n_cerrado": entry["groups"].get("Cerrado", {}).get("n")}
    for label, units in (("state_year", state_years), ("block", blocks)):
        out[label] = _bootstrap_D(inequality, groups, units, n_boot=n_boot)
    return out


def association(rows: list[dict], crop: str) -> dict[str, Any]:
    """Interação bloco hídrico × Sul no modelo within (município e ano)."""
    subset = [row for row in rows if row["group"] in ("Sul", "Cerrado")]
    for row in subset:
        row["x_water"] = row["wb_deficit"]
        row["x_sul"] = row["wb_deficit"] * (1.0 if row["group"] == "Sul" else 0.0)
    result = heterogeneity.joint_significance(
        subset, ("x_water", "x_sul"), test_variables=("x_sul",), cluster="two_way"
    )
    return {"n": len(subset), "crop": crop, **result}


def per_unit_delta(rows: list[dict], m2: dict, wb: dict) -> tuple[dict, list[dict]]:
    """ΔMAE por UF e por município, nas mesmas linhas de teste."""
    a = np.asarray(m2["row_abs_errors"]["TE"])
    b = np.asarray(wb["row_abs_errors"]["TE"])
    codes = m2["row_codes"]
    info = {row["ibge_code"]: row for row in rows}
    by_uf: dict[str, list[float]] = defaultdict(list)
    by_muni: dict[str, list[float]] = defaultdict(list)
    for code, err_a, err_b in zip(codes.tolist(), a.tolist(), b.tolist()):
        meta = info.get(code)
        if meta is None:
            continue
        by_uf[meta["state"]].append(err_b - err_a)
        by_muni[code].append(err_b - err_a)
    uf_summary = {
        uf: {"n": len(values), "delta": float(np.mean(values))}
        for uf, values in sorted(by_uf.items())
    }
    by_pair: dict[str, list[float]] = defaultdict(list)
    for code, err_a, err_b in zip(codes.tolist(), a.tolist(), b.tolist()):
        meta = info.get(code)
        if meta is None:
            continue
        by_pair[f"{meta['state']}|{meta['macroregion']}"].append(err_b - err_a)
    pair_summary = {
        key: {"n": len(values), "delta": float(np.mean(values))}
        for key, values in sorted(by_pair.items())
    }
    municipality_rows = [
        {
            "ibge_code": code,
            "uf": info[code]["state"],
            "group": info[code]["group"],
            "macroregion": info[code]["macroregion"],
            "n": len(values),
            "delta": float(np.mean(values)),
        }
        for code, values in sorted(by_muni.items())
    ]
    return uf_summary, municipality_rows, pair_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="main", choices=("main", "robustness"))
    args = parser.parse_args()

    started = time.time()
    data = base.load_rows()
    data.pop("__dropped__", None)
    water = v33.load_water()
    groups = load_groups()

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "preregistration": "docs/V3_4_REGIONAL_WATER_PREREGISTRATION.md",
        "protocol": {
            "arm": "TE",
            "metric": "MAE kg/ha; delta = MAE(com bloco) - MAE(sem bloco); negativo = bloco melhor",
            "D": "delta_Sul - delta_Cerrado; negativo = bloco relativamente melhor no Sul",
            "equalize": "per_cell",
            "n_repeats": N_REPEATS,
            "n_boot": N_BOOT,
        },
        "crops": {},
    }

    if args.stage == "main":
        out_path = OUT_MAIN
        for crop in CROPS:
            rows = build_rows(crop, data, water, groups)
            print(f"=== {crop}: {len(rows)} linhas com região ===", flush=True)
            m2 = v33._run(rows, v33.MODELS["M2"], N_REPEATS, N_BOOT)
            wb = v33._run(rows, v33.MODELS["M2_WB_plus"], N_REPEATS, N_BOOT)
            m2_summary = v33._summarise(m2)
            wb_summary = v33._summarise(wb)
            per_region = per_region_delta(rows, m2, wb)
            uf_summary, municipality_rows, pair_summary = per_unit_delta(rows, m2, wb)
            regional = contrast(per_region, m2) if "D" in per_region else {"status": "no_D"}
            entry: dict[str, Any] = {
                "n_rows": len(rows),
                "m2_mae": m2_summary["mae_te"],
                "wb_mae": wb_summary["mae_te"],
                "national_delta": (wb_summary["mae_te"] - m2_summary["mae_te"]),
                "per_region": {k: v for k, v in per_region["groups"].items()},
                "per_uf": uf_summary,
                "per_uf_macroregion": pair_summary,
                "contrast": regional,
                "association": association(rows, crop),
            }
            payload["crops"][crop] = entry
            os.makedirs(os.path.join(MANIFESTS, "v34_municipality_delta"), exist_ok=True)
            with open(
                os.path.join(MANIFESTS, "v34_municipality_delta", f"{crop}.csv"),
                "w", newline="", encoding="utf-8-sig",
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["ibge_code", "uf", "group", "macroregion", "n", "delta"],
                )
                writer.writeheader()
                writer.writerows(municipality_rows)
            print(
                "  nacional: M2=%.2f bloco=%.2f delta=%+.2f"
                % (m2_summary["mae_te"], wb_summary["mae_te"], entry["national_delta"]),
                flush=True,
            )
            for group, value in per_region["groups"].items():
                print(
                    "    %-10s n=%5d delta=%+8.2f (M2 %.1f -> bloco %.1f)"
                    % (group, value["n"], value["delta"], value["mae_m2"], value["mae_wb"]),
                    flush=True,
                )
            if "D" in per_region:
                print(
                    "  D = %+.2f | UFxano CI [%.1f, %.1f] p=%.4f | bloco CI [%.1f, %.1f]"
                    % (
                        regional["D"],
                        regional["state_year"]["ci95"][0],
                        regional["state_year"]["ci95"][1],
                        regional["state_year"]["p_value"],
                        regional["block"]["ci95"][0],
                        regional["block"]["ci95"][1],
                    ),
                    flush=True,
                )
            print(
                "  por UF: "
                + " | ".join(f"{uf} {v['delta']:+.1f}" for uf, v in uf_summary.items()),
                flush=True,
            )
            test = entry["association"].get("joint_test", {})
            coef = entry["association"].get("coefficients", {}).get("x_sul", {})
            print(
                "  interação: coef=%+.4f p=%.4f (G=%s)"
                % (
                    coef.get("coefficient", float("nan")),
                    test.get("p_value", float("nan")),
                    test.get("df2"),
                ),
                flush=True,
            )

        # família confirmatória: 2 testes no milho
        milho = payload["crops"][PRIMARY_CROP]
        raw = {
            "preditivo_D": float(milho["contrast"]["state_year"]["p_value"]),
            "associativo_interacao": float(milho["association"]["joint_test"]["p_value"]),
        }
        holm = robust.holm_adjust(raw)
        payload["confirmatory_family"] = {
            "crop": PRIMARY_CROP,
            "size": 2,
            "method": "Holm",
            "raw": raw,
            "holm": holm,
            "rejected": sorted(k for k, v in holm.items() if v is not None and v < 0.05),
        }
        print("\n=== família confirmatória (milho, 2 testes) ===")
        for key in sorted(raw):
            print("  %-24s p=%.4f holm=%.4f" % (key, raw[key], holm[key]))
    else:
        out_path = OUT_ROBUST
        for crop in CROPS:
            rows = build_rows(crop, data, water, groups)
            print(f"=== {crop}: robustez ===", flush=True)
            entry: dict[str, Any] = {"leave_one_uf_out": {}, "leave_one_year_out": {},
                                     "within_state": {}, "by_year": {}}
            m2 = v33._run(rows, v33.MODELS["M2"], 1, 300)
            wb = v33._run(rows, v33.MODELS["M2_WB_plus"], 1, 300)
            base_region = per_region_delta(rows, m2, wb)
            base_D = base_region.get("D")
            entry["baseline_D"] = base_D

            for uf in sorted({row["state"] for row in rows}):
                subset = [row for row in rows if row["state"] != uf]
                a = v33._run(subset, v33.MODELS["M2"], 1, 250)
                b = v33._run(subset, v33.MODELS["M2_WB_plus"], 1, 250)
                region = per_region_delta(subset, a, b)
                entry["leave_one_uf_out"][uf] = {
                    "D": region.get("D"),
                    "n_sul": region["groups"].get("Sul", {}).get("n"),
                    "n_cerrado": region["groups"].get("Cerrado", {}).get("n"),
                }
                print(
                    "  drop %-3s D=%s" % (uf, region.get("D")),
                    flush=True,
                )

            for year in sorted({row["year"] for row in rows}):
                subset = [row for row in rows if row["year"] != year]
                a = v33._run(subset, v33.MODELS["M2"], 1, 250)
                b = v33._run(subset, v33.MODELS["M2_WB_plus"], 1, 250)
                region = per_region_delta(subset, a, b)
                entry["leave_one_year_out"][str(year)] = {"D": region.get("D")}
                print("  drop %s D=%s" % (year, region.get("D")), flush=True)

            # testes dentro do mesmo estado
            for uf in sorted({row["state"] for row in rows}):
                subset = [row for row in rows if row["state"] == uf]
                macros = sorted({row["macroregion"] for row in subset})
                if len(macros) < 2:
                    continue
                reference = macros[0]
                for row in subset:
                    row["x_water"] = row["wb_deficit"]
                    row["x_macro"] = row["wb_deficit"] * (
                        1.0 if row["macroregion"] != reference else 0.0
                    )
                result = heterogeneity.joint_significance(
                    subset, ("x_water", "x_macro"), test_variables=("x_macro",),
                    cluster="two_way", min_rows=100,
                )
                # o lado preditivo dentro do estado é secundário e pode não ter
                # células suficientes (um estado tem poucos blocos); usa 3 dobras
                # espaciais e registra quando não é viável.
                diffs: dict[str, Any] = {}
                predictive = {"status": "not_attempted"}
                try:
                    a = gen.factorial_holdout(
                        subset, v33.MODELS["M2"], seed=rr.SEED, n_repeats=1,
                        n_boot=250, variant="climate_plus_state", equalize="per_cell",
                        keep_errors=True, min_cell_train=100, n_space_folds=3,
                    )
                    b = gen.factorial_holdout(
                        subset, v33.MODELS["M2_WB_plus"], seed=rr.SEED, n_repeats=1,
                        n_boot=250, variant="climate_plus_state", equalize="per_cell",
                        keep_errors=True, min_cell_train=100, n_space_folds=3,
                    )
                    if "row_abs_errors" in a and "row_abs_errors" in b:
                        ae = np.asarray(a["row_abs_errors"]["TE"])
                        be = np.asarray(b["row_abs_errors"]["TE"])
                        codes = a["row_codes"]
                        macro_of = {row["ibge_code"]: row["macroregion"] for row in subset}
                        labels = np.array([macro_of.get(c, "") for c in codes])
                        for macro in macros:
                            mask = labels == macro
                            if mask.any():
                                diffs[macro] = {
                                    "n": int(mask.sum()),
                                    "delta": float(be[mask].mean() - ae[mask].mean()),
                                }
                        predictive = {"status": "ok", "by_macroregion": diffs}
                    else:
                        predictive = {
                            "status": "insufficient_cells",
                            "m2": a.get("status"),
                            "wb": b.get("status"),
                        }
                except Exception as error:  # noqa: BLE001 - registrar, não mascarar
                    predictive = {"status": "error", "detail": str(error)[:200]}
                entry["within_state"][uf] = {
                    "macroregions": macros,
                    "reference": reference,
                    "predictive": predictive,
                    "by_macroregion_delta": diffs,
                    "spread": (
                        max(v["delta"] for v in diffs.values())
                        - min(v["delta"] for v in diffs.values())
                    ) if len(diffs) > 1 else None,
                    "association": result,
                }
                print(
                    "  dentro de %s: preditivo=%s | spread=%s"
                    % (
                        uf,
                        {m: round(v["delta"], 2) for m, v in diffs.items()} or predictive["status"],
                        round(entry["within_state"][uf]["spread"], 2)
                        if entry["within_state"][uf]["spread"] is not None else "-",
                    ),
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
