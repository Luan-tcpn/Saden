"""V3.4 — cobertura, suporte e identificabilidade do contraste regional.

Fase Dois do roadmap. Não estima o contraste: mede se os dados permitem
comparar Sul (MRS 1) e Cerrado (MRS 3∪4), e documenta o confundimento
região × UF antes de qualquer resultado.

Uso: python tools/v34_coverage.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, HERE)

from agroclimate import spatial  # noqa: E402

import run_robustness as rr  # noqa: E402
import v31_models as base  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
MAPPING = os.path.join(PROCESSED, "municipality_region_mapping.csv")
OUT = os.path.join(MANIFESTS, "v34_coverage_identifiability.json")

GROUP_OF_MACRO = {"1": "Sul", "2": "Transicao", "3": "Cerrado", "4": "Cerrado", "5": "Fora"}
CROPS = ("soja", "milho", "milho_2")
WATER_SCENARIO = {"soja": "cad_0_100", "milho": "cad_0_60", "milho_2": "cad_0_60"}


def load_mapping() -> dict[str, dict[str, str]]:
    out = {}
    with open(MAPPING, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            out[str(row["ibge_code"])] = {
                "uf": row["uf"],
                "macroregion": row["macroregion"],
                "edapho_region": row["edapho_region"],
                "group": GROUP_OF_MACRO.get(row["macroregion"], "Fora"),
            }
    return out


def load_water() -> dict[tuple, dict]:
    out = {}
    path = os.path.join(PROCESSED, "v33_water_variables.csv")
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            out[(str(row["ibge_code"]), str(row["crop"]), str(row["safra"]), row["scenario"])] = row
    return out


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def cramers_v(table: dict[tuple[str, str], int]) -> float:
    rows = sorted({key[0] for key in table})
    cols = sorted({key[1] for key in table})
    observed = np.array([[table.get((r, c), 0) for c in cols] for r in rows], dtype="float64")
    total = observed.sum()
    if total == 0:
        return 0.0
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / total
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = np.nansum((observed - expected) ** 2 / np.where(expected == 0, np.nan, expected))
    k = min(observed.shape) - 1
    return float(np.sqrt(chi2 / (total * k))) if k > 0 else 0.0


def main() -> int:
    mapping = load_mapping()
    water = load_water()
    data = base.load_rows()
    data.pop("__dropped__", None)
    blocks = spatial.spatial_blocks(rr.load_municipalities(), 250.0)

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "docs/V3_4_REGIONAL_CLASSIFICATION_PROTOCOL.md",
        "groups": {"Sul": "MRS 1", "Cerrado": "MRS 3 + MRS 4", "Transicao": "MRS 2 (excluida do contraste primario)"},
        "crops": {},
    }

    for crop in CROPS:
        scenario = WATER_SCENARIO[crop]
        rows = []
        for row in data.get(crop, []):
            info = mapping.get(row["ibge_code"])
            if info is None:
                continue
            extra = water.get((row["ibge_code"], crop, row["safra"], scenario))
            if extra is None:
                continue
            rows.append(
                {
                    **row,
                    "group": info["group"],
                    "macroregion": info["macroregion"],
                    "edapho_region": info["edapho_region"],
                    "deficit": _num(extra.get("deficit_total_mm")),
                    "stress_share": _num(extra.get("stress_share")),
                    "etr_over_etp": _num(extra.get("etr_over_etp")),
                }
            )
        print(f"=== {crop}: {len(rows)} linhas com região ===", flush=True)

        entry: dict[str, Any] = {"scenario": scenario, "n_rows": len(rows), "groups": {}}
        for group in ("Sul", "Cerrado", "Transicao"):
            subset = [r for r in rows if r["group"] == group]
            if not subset:
                continue
            by_uf = Counter(r["state"] for r in subset)
            municipalities = {r["ibge_code"] for r in subset}
            years = sorted({r["year"] for r in subset})
            state_years = {(r["state"], r["year"]) for r in subset}
            entry["groups"][group] = {
                "n_rows": len(subset),
                "n_municipalities": len(municipalities),
                "n_years": len(years),
                "years": years,
                "n_blocks": len({blocks.get(c) for c in municipalities if blocks.get(c)}),
                "n_state_years": len(state_years),
                "by_uf": dict(sorted(by_uf.items())),
                "by_macroregion": dict(sorted(Counter(r["macroregion"] for r in subset).items())),
                "yield_median": float(np.median([r["yield_kg_ha"] for r in subset])),
                "yield_sd": float(np.std([r["yield_kg_ha"] for r in subset])),
                "deficit_median": float(np.median([r["deficit"] for r in subset if r["deficit"] is not None])),
                "deficit_sd": float(np.std([r["deficit"] for r in subset if r["deficit"] is not None])),
                "deficit_p10": float(np.quantile([r["deficit"] for r in subset if r["deficit"] is not None], 0.10)),
                "deficit_p90": float(np.quantile([r["deficit"] for r in subset if r["deficit"] is not None], 0.90)),
                "stress_share_median": float(np.median([r["stress_share"] for r in subset if r["stress_share"] is not None])),
                "etr_over_etp_median": float(np.median([r["etr_over_etp"] for r in subset if r["etr_over_etp"] is not None])),
                "precip_median": float(np.median([r["precip_corrected"] for r in subset])),
                "temp_median": float(np.median([r["temp_corrected"] for r in subset])),
            }
            print(
                "  %-10s linhas=%5d munis=%3d UFs=%s anos=%d UFxano=%3d deficit med=%6.1f [p10 %.0f, p90 %.0f]"
                % (
                    group,
                    len(subset),
                    len(municipalities),
                    ",".join(sorted(by_uf)),
                    len(years),
                    len(state_years),
                    entry["groups"][group]["deficit_median"],
                    entry["groups"][group]["deficit_p10"],
                    entry["groups"][group]["deficit_p90"],
                ),
                flush=True,
            )

        # confundimento região × UF
        table = Counter((r["group"], r["state"]) for r in rows if r["group"] in ("Sul", "Cerrado"))
        entry["confounding"] = {
            "crosstab": {f"{g}|{u}": v for (g, u), v in sorted(table.items())},
            "cramers_v": cramers_v(table),
            "ufs_in_both_groups": sorted(
                {
                    uf
                    for uf in {key[1] for key in table}
                    if ("Sul", uf) in table and ("Cerrado", uf) in table
                }
            ),
            "regions_nested_in_uf": True,
        }
        shared = entry["confounding"]["ufs_in_both_groups"]
        entry["confounding"]["regions_nested_in_uf"] = len(shared) == 0
        print(
            "  confundimento: Cramer's V=%.3f | UFs nos dois grupos=%s"
            % (entry["confounding"]["cramers_v"], shared or "nenhuma"),
            flush=True,
        )

        # testes dentro do mesmo estado (macroregião varia, UF não)
        within: dict[str, Any] = {}
        for uf in sorted({r["state"] for r in rows}):
            subset = [r for r in rows if r["state"] == uf]
            macros = sorted({r["macroregion"] for r in subset})
            if len(macros) < 2:
                continue
            within[uf] = {
                "macroregions": macros,
                "by_macroregion": {
                    macro: {
                        "n_rows": sum(1 for r in subset if r["macroregion"] == macro),
                        "n_municipalities": len({r["ibge_code"] for r in subset if r["macroregion"] == macro}),
                        "deficit_median": float(
                            np.median([r["deficit"] for r in subset if r["macroregion"] == macro and r["deficit"] is not None])
                        ),
                    }
                    for macro in macros
                },
            }
        entry["within_state_variation"] = within
        if within:
            print(f"  variação dentro do estado: {list(within)}", flush=True)

        payload["crops"][crop] = entry

    # suporte climático: sobreposição das distribuições Sul × Cerrado
    support: dict[str, Any] = {}
    for crop in CROPS:
        entry = payload["crops"][crop]
        sul = entry["groups"].get("Sul", {})
        cerrado = entry["groups"].get("Cerrado", {})
        if not sul or not cerrado:
            continue
        support[crop] = {
            "deficit_median_sul": sul["deficit_median"],
            "deficit_median_cerrado": cerrado["deficit_median"],
            "deficit_ratio_cerrado_over_sul": (
                cerrado["deficit_median"] / sul["deficit_median"] if sul["deficit_median"] else None
            ),
            "range_overlap": {
                "sul": [sul["deficit_p10"], sul["deficit_p90"]],
                "cerrado": [cerrado["deficit_p10"], cerrado["deficit_p90"]],
                "overlaps": not (
                    cerrado["deficit_p10"] > sul["deficit_p90"]
                    or sul["deficit_p10"] > cerrado["deficit_p90"]
                ),
            },
            "yield_median_sul": sul["yield_median"],
            "yield_median_cerrado": cerrado["yield_median"],
        }
    payload["climate_support"] = support

    payload["identifiability_verdict"] = {
        "regions_nested_in_uf": all(
            entry["confounding"]["regions_nested_in_uf"] for entry in payload["crops"].values()
        ),
        "implication": (
            "o contraste Sul x Cerrado nao e separavel de um contraste entre grupos de estados; "
            "inclinacoes (interacoes com o bloco hidrico) continuam identificaveis por variacao "
            "temporal dentro do municipio; o nivel regional nao"
        ),
        "within_state_tests_available": sorted(
            {uf for entry in payload["crops"].values() for uf in entry["within_state_variation"]}
        ),
    }

    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(json.dumps(payload["identifiability_verdict"], ensure_ascii=False, indent=2))
    print(json.dumps(payload["climate_support"], ensure_ascii=False, indent=2))
    print(f"manifesto: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
