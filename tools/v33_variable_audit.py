"""V3.3 — auditoria de dependencia entre candidatos do bloco hidrico e termico.

Antes de pre-registrar a especificacao funcional, mede-se:

* quanto de cada candidato e zero (degeneracao);
* a correlacao *within* de municipio e ano entre candidatos;
* a colinearidade (numero de condicao) do conjunto candidato.

Nada aqui testa a hipotese; e diagnostico de desenho.

Uso: python tools/v33_variable_audit.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, HERE)

from agroclimate import spatial_inference as si  # noqa: E402

import v31_models as base  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
WATER = os.path.join(PROCESSED, "v33_water_variables.csv")
OUT = os.path.join(MANIFESTS, "v33_variable_audit.json")

PRIMARY_SCENARIO = {"soja": "cad_0_100", "milho": "cad_0_60", "milho_2": "cad_0_60"}

CANDIDATES = (
    "precip_corrected",
    "temp_corrected",
    "degree_days_corrected",
    "heat_corrected",
    "deficit_total_mm",
    "stress_share",
    "max_consecutive_deficit_months",
    "etr_over_etp",
    "deficit_over_etp",
    "storage_min_mm",
    "months_to_first_stress",
)


def load_water() -> dict[tuple, dict]:
    out = {}
    with open(WATER, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key = (str(row["ibge_code"]), str(row["crop"]), str(row["safra"]), row["scenario"])
            out[key] = row
    return out


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    data = base.load_rows()
    data.pop("__dropped__", None)
    water = load_water()
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "diagnostico de degeneracao e dependencia; nao testa a hipotese",
        "primary_scenario": PRIMARY_SCENARIO,
        "crops": {},
    }
    for crop in ("soja", "milho", "milho_2"):
        scenario = PRIMARY_SCENARIO[crop]
        rows = []
        for row in data.get(crop, []):
            extra = water.get((row["ibge_code"], crop, row["safra"], scenario))
            if extra is None:
                continue
            merged = dict(row)
            for name in (
                "deficit_total_mm",
                "stress_share",
                "max_consecutive_deficit_months",
                "etr_over_etp",
                "deficit_over_etp",
                "storage_min_mm",
                "months_to_first_stress",
                "deficit_months",
                "months",
            ):
                merged[name] = _num(extra.get(name))
            merged["cad_mm"] = _num(extra.get("cad_mm"))
            rows.append(merged)
        print(f"=== {crop} ({scenario}): {len(rows)} linhas ===", flush=True)
        municipalities = [r["ibge_code"] for r in rows]
        years = [r["year"] for r in rows]
        entry = {"n": len(rows), "scenario": scenario, "candidates": {}, "within_correlation": {}}
        available = []
        for name in CANDIDATES:
            values = np.array(
                [r[name] if r.get(name) is not None else np.nan for r in rows], dtype="float64"
            )
            observed = np.isfinite(values)
            if observed.mean() < 0.9:
                entry["candidates"][name] = {
                    "status": "insufficient_presence",
                    "presence": float(observed.mean()),
                }
                continue
            filled = np.where(observed, values, np.nan)
            median = float(np.nanmedian(filled))
            filled = np.where(observed, filled, median)
            within = si.within_transform(filled, municipalities, years)
            unique = int(len(set(np.round(filled, 6).tolist())))
            zero_share = float(np.mean(np.abs(filled) < 1e-12))
            entry["candidates"][name] = {
                "status": "ok",
                "mean": float(np.mean(filled)),
                "sd": float(np.std(filled)),
                "sd_within": float(np.std(within)),
                "unique_values": unique,
                "zero_share": zero_share,
                "within_share_of_variance": (
                    float(np.var(within) / np.var(filled)) if np.var(filled) > 0 else None
                ),
            }
            if np.std(within) > 1e-9 and zero_share < 0.95:
                available.append((name, within))
            print(
                "  %-32s sd=%9.3f within=%8.3f zeros=%5.1f%% unicos=%5d"
                % (name, entry["candidates"][name].get("sd", float("nan")),
                   entry["candidates"][name]["sd_within"], 100 * zero_share, unique),
                flush=True,
            )
        matrix = np.column_stack([values for _, values in available])
        corr = np.corrcoef(matrix, rowvar=False)
        entry["within_correlation"] = {
            "variables": [name for name, _ in available],
            "matrix": [[float(v) for v in line] for line in corr],
        }
        if matrix.shape[1] > 1:
            standardized = (matrix - matrix.mean(axis=0)) / matrix.std(axis=0)
            singular = np.linalg.svd(standardized, compute_uv=False)
            entry["condition_number"] = float(singular[0] / singular[-1])
        payload["crops"][crop] = entry

    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(f"\nmanifesto: {OUT}")
    print("\n=== correlacoes within > |0.8| ===")
    for crop, entry in payload["crops"].items():
        names = entry["within_correlation"]["variables"]
        matrix = entry["within_correlation"]["matrix"]
        pairs = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                if abs(matrix[i][j]) > 0.8:
                    pairs.append(f"{names[i]} x {names[j]} = {matrix[i][j]:+.3f}")
        print(f"  {crop}: {'; '.join(pairs) if pairs else 'nenhum'}")
        print(f"    condicao: {entry.get('condition_number')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
