"""V3.4 — diagnóstico da lacuna de cobertura territorial do SADEN.

Mede a cobertura **territorial** com o que existe no repositório e explicita o
que não pode ser medido sem aquisição nova:

* quantos municípios o MAPA indica para soja em cada UF (denominador oficial);
* quantos desses estão no painel do SADEN (numerador);
* quais UFs estão ausentes e qual o tamanho do território não coberto, em
  municípios;
* por que a **participação na produção** não é reportada: o painel PAM do
  repositório cobre apenas as 6 UFs já integradas, então qualquer percentual
  nacional de produção exigiria aquisição nova — e não é estimado aqui.

Uso: python tools/v34_coverage_gap.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
EXTERNAL = os.path.join(ROOT, "geospatial", "data", "external")
XLSX = os.path.join(EXTERNAL, "MacrorregioSojicolasAtualizado_2025.xlsx")
OUT = os.path.join(MANIFESTS, "v34_coverage_gap.json")

PANEL_STATES = {"PR", "RS", "MS", "MT", "GO", "BA"}
CROPS = ("soja", "milho", "milho_2")


def official_counts() -> dict[str, dict[str, int]]:
    import v34_region_mapping as mapping

    rows = mapping.read_rows()
    per_state: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        per_state[row["uf"]]["total"] += 1
        per_state[row["uf"]][f"mrs{row['macroregion']}"] += 1
    return {uf: dict(values) for uf, values in per_state.items()}


def panel_counts() -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    with open(
        os.path.join(PROCESSED, "v31_panel_windows.csv"), newline="", encoding="utf-8-sig"
    ) as handle:
        for row in csv.DictReader(handle):
            key = f"{row['crop']}"
            counts[row["state"]][key] += 1
            counts[row["state"]]["municipalities_seen"] = counts[row["state"]].get(
                "municipalities_seen", 0
            )
    # municípios distintos
    seen: dict[str, set[str]] = defaultdict(set)
    with open(
        os.path.join(PROCESSED, "v31_panel_windows.csv"), newline="", encoding="utf-8-sig"
    ) as handle:
        for row in csv.DictReader(handle):
            seen[row["state"]].add(row["ibge_code"])
    for state, codes in seen.items():
        counts[state]["municipalities"] = len(codes)
    return {state: dict(values) for state, values in counts.items()}


def main() -> int:
    official = official_counts()
    panel = panel_counts()
    mapping_rows = {}
    with open(
        os.path.join(PROCESSED, "municipality_region_mapping.csv"),
        newline="", encoding="utf-8-sig",
    ) as handle:
        for row in csv.DictReader(handle):
            mapping_rows.setdefault(row["uf"], set()).add(row["ibge_code"])

    total_official = sum(values["total"] for values in official.values())
    total_in_panel_states = sum(
        values["total"] for uf, values in official.items() if uf in PANEL_STATES
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "denominator": {
            "source": "planilha oficial MAPA/ZARC (municípios com indicação de soja)",
            "total_municipalities_with_soybean_indication": total_official,
            "in_the_six_panel_states": total_in_panel_states,
            "share_of_indicated_territory_covered_by_scope": round(
                total_in_panel_states / total_official, 4
            ),
            "n_states_with_indication": len(official),
        },
        "covered_states": {},
        "absent_states": {},
        "not_measurable_here": {
            "production_share": (
                "o painel PAM do repositório cobre apenas MT, GO, MS, PR, RS e BA; "
                "a participação nacional na produção não pode ser calculada sem "
                "aquisição de PAM para as demais UFs"
            ),
            "agricultural_area_share": "mesma razão: sem dados de área fora das 6 UFs",
        },
    }

    for uf in sorted(official):
        if uf in PANEL_STATES:
            counts = panel.get(uf, {})
            municipalities_in_panel = counts.get("municipalities", 0)
            matched = len(mapping_rows.get(uf, set()))
            payload["covered_states"][uf] = {
                "municipalities_with_soybean_indication": official[uf]["total"],
                "by_macroregion": {
                    key: value
                    for key, value in sorted(official[uf].items())
                    if key.startswith("mrs")
                },
                "municipalities_in_panel": municipalities_in_panel,
                "municipalities_matched_to_a_region": matched,
                "rows_by_crop": {crop: counts.get(crop, 0) for crop in CROPS},
                "coverage_of_indicated_municipalities": (
                    round(matched / official[uf]["total"], 4) if official[uf]["total"] else None
                ),
            }
        else:
            payload["absent_states"][uf] = {
                "municipalities_with_soybean_indication": official[uf]["total"],
                "by_macroregion": {
                    key: value
                    for key, value in sorted(official[uf].items())
                    if key.startswith("mrs")
                },
            }

    absent_total = sum(v["municipalities_with_soybean_indication"] for v in payload["absent_states"].values())
    payload["gap"] = {
        "n_absent_states": len(payload["absent_states"]),
        "absent_states": sorted(payload["absent_states"]),
        "municipalities_with_indication_outside_scope": absent_total,
        "share_of_indicated_territory_outside_scope": round(absent_total / total_official, 4),
    }

    # prioridades: UFs ausentes que mais ampliariam a diversidade de macrorregião
    priorities = []
    covered_macros = Counter()
    for uf, values in official.items():
        if uf in PANEL_STATES:
            for key, value in values.items():
                if key.startswith("mrs"):
                    covered_macros[key] += value
    for uf, values in payload["absent_states"].items():
        macros = {key for key in values["by_macroregion"]}
        priorities.append(
            {
                "uf": uf,
                "municipalities": values["municipalities_with_soybean_indication"],
                "macroregions": sorted(macros),
                "adds_macroregion_not_covered": sorted(
                    macro for macro in macros if covered_macros.get(macro, 0) == 0
                ),
            }
        )
    priorities.sort(key=lambda item: (-len(item["adds_macroregion_not_covered"]), -item["municipalities"]))
    payload["expansion_priorities"] = priorities[:10]

    # O critério que importa para a V3.4: qual UF ausente quebraria o
    # confundimento região × UF, isto é, teria municípios nos DOIS grupos do
    # contraste primário (Sul = MRS 1; Cerrado = MRS 3∪4)?
    group_of = {"mrs1": "Sul", "mrs3": "Cerrado", "mrs4": "Cerrado",
                "mrs2": "Transicao", "mrs5": "Fora"}
    would_identify = []
    for uf, values in payload["absent_states"].items():
        groups = {
            group_of[macro]
            for macro in values["by_macroregion"]
            if group_of.get(macro) in ("Sul", "Cerrado")
        }
        if {"Sul", "Cerrado"} <= groups:
            would_identify.append(
                {
                    "uf": uf,
                    "municipalities": values["municipalities_with_soybean_indication"],
                    "macroregions": sorted(values["by_macroregion"]),
                    "spans_sul_and_cerrado": True,
                }
            )
    would_identify.sort(key=lambda item: -item["municipalities"])
    payload["would_break_confounding"] = would_identify
    payload["identification_note"] = (
        "uma UF que tenha municípios em MRS 1 e em MRS 3/4 permitiria comparar Sul e Cerrado "
        "DENTRO do mesmo estado, que é o que falta para separar região de efeito de estado"
    )

    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")

    print("denominador oficial:", payload["denominator"])
    print("\nestados cobertos:")
    for uf, values in payload["covered_states"].items():
        print(
            "  %-3s indicados=%3d painel=%3d mapeados=%3d cobertura=%.1f%% linhas=%s"
            % (
                uf,
                values["municipalities_with_soybean_indication"],
                values["municipalities_in_panel"],
                values["municipalities_matched_to_a_region"],
                100 * (values["coverage_of_indicated_municipalities"] or 0),
                values["rows_by_crop"],
            )
        )
    print("\nlacuna:", payload["gap"])
    print("\nprioridades (top 10):")
    for item in payload["expansion_priorities"]:
        print("  ", item)
    print("\nUFs que quebrariam o confundimento região x UF:")
    for item in payload["would_break_confounding"]:
        print("  ", item)
    print(f"\nmanifesto: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
