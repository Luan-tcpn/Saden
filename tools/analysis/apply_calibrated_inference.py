"""Aplica a inferência calibrada aos estimandos reais do painel.

Para cada combinação cultura × exposição, com transformação *within* (município e
ano) e agrupamento em UF × ano:

* ``cr1`` — o que os relatórios publicaram;
* ``wcr`` — wild cluster bootstrap-t com H0 imposta (Rademacher), B = 9.999.

A escolha do método **não** depende do resultado: ``wcr`` foi o único calibrado na
simulação sob H0 (``bootstrap_calibration.json``), e é aplicado a todos os
estimandos, sem exceção.

Saída: ``geospatial/data/manifests/applied_inference.json``
Uso: python tools/analysis/apply_calibrated_inference.py [--boot 9999]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, HERE)

import fast_bootstrap as FB  # noqa: E402
from agroclimate import spatial_inference  # noqa: E402

_DATA_ROOT = os.environ.get("SADEN_DATA_ROOT") or os.path.join(ROOT, "geospatial", "data")
PROCESSED = os.path.join(_DATA_ROOT, "processed")
OUT_JSON = os.path.join(ROOT, "geospatial", "data", "manifests", "applied_inference.json")

CROPS = ("soja", "milho", "milho_2")
EXPOSURES = {
    "deficit": "deficiency_total_mm_corrected",
    "precipitacao": "precip_acumulada_mm_corrected",
    "et0": "et0_total_mm_corrected",
    "graus_dia": "degree_days_total_corrected",
    "calor_extremo": "extreme_heat_days_corrected",
    "temperatura": "temp_media_c_corrected",
}


def load() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {crop: [] for crop in CROPS}
    with open(os.path.join(PROCESSED, "v35_panel_windows.csv"), newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            crop = str(row.get("crop"))
            if crop in out:
                out[crop].append(row)
    return out


def classify(cr1_p: float | None, wcr_p: float | None, cr1_conclusion: bool) -> str:
    """Classifica a leitura de um estimando à luz da inferência calibrada."""
    if cr1_p is None or wcr_p is None:
        return "inconclusivo"
    if cr1_conclusion:
        return "sustentada" if wcr_p < 0.05 else "enfraquecida"
    return "nula_confirmada" if wcr_p >= 0.10 else "inconclusiva"


def run(n_boot: int, seed: int) -> dict[str, Any]:
    panel = load()
    results: dict[str, Any] = {}
    for crop in CROPS:
        rows = panel[crop]
        for name, column in EXPOSURES.items():
            usable = [
                row for row in rows
                if row.get(column) not in (None, "") and row.get("yield_kg_ha") not in (None, "")
            ]
            if len(usable) < 400:
                continue
            municipalities = [str(row["ibge_code"]) for row in usable]
            years = [str(row.get("harvest_year")) for row in usable]
            state_years = [f"{row.get('state')}||{row.get('harvest_year')}" for row in usable]
            y = np.array([float(row["yield_kg_ha"]) for row in usable])
            x = np.array([float(row[column]) for row in usable])
            y_within = spatial_inference.within_transform(y, municipalities, years)
            x_within = spatial_inference.within_transform(x, municipalities, years)
            codes, n_groups = FB.group_codes(state_years)
            fit = FB.cr1_fit(x_within, y_within, codes, n_groups)
            if fit.get("status") != "ok":
                results[f"{crop}|{name}"] = {"status": fit.get("status")}
                continue
            rng = np.random.default_rng(seed + 7919 * (len(results) + 1))
            weights = rng.choice([-1.0, 1.0], size=(n_groups, n_boot))
            wild = FB.wild_p(x_within, y_within, codes, n_groups, weights, fit["t"], restricted=True)
            cr1_p = fit["p"]
            wcr_p = wild.get("p_value")
            conclusion = cr1_p is not None and cr1_p < 0.05
            quartile = wild.get("t_boot_abs_q95")
            ci_wcr = (
                [fit["beta"] - float(quartile) * fit["se"], fit["beta"] + float(quartile) * fit["se"]]
                if quartile
                else None
            )
            results[f"{crop}|{name}"] = {
                "n": int(x.size),
                "n_clusters": n_groups,
                "beta": fit["beta"],
                "se_cr1": fit["se"],
                "t": fit["t"],
                "df": fit["df"],
                "p_cr1": cr1_p,
                "ci95_cr1": [
                    fit["beta"] - fit["critical"] * fit["se"],
                    fit["beta"] + fit["critical"] * fit["se"],
                ],
                "p_wcr": wcr_p,
                "ci95_wcr": ci_wcr,
                "classificacao": classify(cr1_p, wcr_p, conclusion),
                "n_boot": n_boot,
            }
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boot", type=int, default=9999)
    parser.add_argument("--seed", type=int, default=20261114)
    args = parser.parse_args()

    results = run(args.boot, args.seed)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methods": {"cr1": "t agrupado CR1", "wcr": "wild cluster bootstrap-t, H0 imposta, Rademacher"},
        "n_boot": args.boot,
        "results": results,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")

    print(f"{'estimando':28} {'beta':>9} {'p_cr1':>9} {'p_wcr':>9}  classificação")
    for key, value in sorted(results.items()):
        if value.get("status"):
            print(f"{key:28} {value['status']}")
            continue
        print(
            f"{key:28} {value['beta']:9.4f} {value['p_cr1']:9.4f} {value['p_wcr']:9.4f}  {value['classificacao']}"
        )
    print("manifesto:", OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
