"""Consolidação — auditoria de qualidade do IBGE/PAM (todos os estados do painel).

Audita os dois arquivos que efetivamente sustentam o painel:

* ``pam_panel.csv``    — as seis UFs originais (V2.6–V3.4);
* ``pam_panel_sp.csv`` — São Paulo (V3.5).

Verifica: chave canônica, cobertura, duplicidades, semântica de zero/ausente,
consistência matemática do rendimento, valores extremos por MAD, e diferenças
entre o conjunto de municípios da PAM e o cadastro municipal do IBGE usado no
painel (crosswalk territorial).

Não altera nenhum dado original. Saídas em
``docs/data_quality/pam/`` e ``geospatial/data/manifests/pam_quality_audit.json``.

Uso: python tools/audit_pam_quality.py
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
sys.path.insert(0, HERE)

# SADEN_DATA_ROOT permite rodar de um clone limpo lendo os derivados externos.
_DATA_ROOT = os.environ.get("SADEN_DATA_ROOT") or os.path.join(ROOT, "geospatial", "data")
PROCESSED = os.path.join(_DATA_ROOT, "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUTDIR = os.path.join(ROOT, "docs", "data_quality", "pam")
OUT_JSON = os.path.join(MANIFESTS, "pam_quality_audit.json")

PAM_FILES = (
    os.path.join(PROCESSED, "pam_panel.csv"),
    os.path.join(PROCESSED, "pam_panel_sp.csv"),
)

UF_BY_CODE = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}
CROP_BY_CODE = {"40124": "soja", "40122": "milho"}

VARIABLES = (
    "quantidade_produzida_t",
    "area_colhida_ha",
    "area_plantada_ha",
    "rendimento_medio_kg_ha",
)


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {}
    for path in PAM_FILES:
        if not os.path.exists(path):
            provenance[os.path.basename(path)] = "ausente"
            continue
        count = 0
        with open(path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                count += 1
                rows.append(row)
        provenance[os.path.basename(path)] = {"rows": count, "bytes": os.path.getsize(path)}
    return rows, provenance


def to_wide(rows: list[dict[str, Any]]) -> tuple[dict[tuple, dict[str, Any]], dict[str, Any]]:
    """Reorganiza (município, ano, cultura) por variável e mede duplicidades."""
    wide: dict[tuple[str, str, str], dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    unknown_uf = 0
    for row in rows:
        code = str(row.get("geography_code") or "")
        year = str(row.get("reference_year") or "")
        crop = CROP_BY_CODE.get(str(row.get("crop_code") or ""))
        variable = str(row.get("variable_normalized") or "")
        uf = UF_BY_CODE.get(code[:2])
        if uf is None:
            unknown_uf += 1
            continue
        if crop is None or variable not in VARIABLES:
            continue
        key = (code, year, crop)
        entry = wide.setdefault(
            key,
            {
                "ibge_code": code,
                "year": year,
                "crop": crop,
                "uf": uf,
                "geography_name": row.get("geography_name"),
                "values": {},
                "status": {},
            },
        )
        if variable in entry["values"]:
            duplicates.append(
                {
                    "key": list(key),
                    "variable": variable,
                    "previous": entry["values"][variable],
                    "new": _num(row.get("value_normalized")),
                }
            )
        else:
            entry["status"][variable] = row.get("observation_status")
            entry["values"][variable] = _num(row.get("value_normalized"))
    return wide, {
        "duplicates": len(duplicates),
        "duplicate_examples": duplicates[:20],
        "unknown_uf_rows": unknown_uf,
    }


def classify(entry: dict[str, Any]) -> dict[str, Any]:
    """Classifica uma célula município-ano-cultura."""
    v = entry["values"]
    area_harvested = v.get("area_colhida_ha")
    area_planted = v.get("area_plantada_ha")
    produced = v.get("quantidade_produzida_t")
    yield_published = v.get("rendimento_medio_kg_ha")
    out: dict[str, Any] = {
        "ibge_code": entry["ibge_code"],
        "uf": entry["uf"],
        "year": entry["year"],
        "crop": entry["crop"],
        "area_planted_ha": area_planted,
        "area_harvested_ha": area_harvested,
        "production_t": produced,
        "yield_published": yield_published,
    }
    flags: list[str] = []

    if area_planted is None or area_harvested is None:
        flags.append("area_ausente")
    elif area_harvested == 0 and (area_planted or 0) == 0:
        flags.append("sem_area")
    elif area_harvested == 0 and (area_planted or 0) > 0:
        flags.append("plantado_sem_colheita")

    if area_harvested is not None and area_harvested > 0:
        if produced is None:
            flags.append("producao_ausente_com_area")
        else:
            recomputed = produced * 1000.0 / area_harvested
            out["yield_recomputed"] = recomputed
            out["yield_relative_gap"] = (
                abs(recomputed - yield_published) / yield_published
                if yield_published not in (None, 0)
                else None
            )
            if yield_published in (None, 0):
                flags.append("rendimento_zero_com_area")
            elif out["yield_relative_gap"] is not None and out["yield_relative_gap"] > 0.01:
                flags.append("rendimento_divergente")
    out["flags"] = flags
    return out


def outlier_flags(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Flag de valor extremo por MAD, dentro de (cultura, UF)."""
    summary: dict[str, Any] = {}
    groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for cell in cells:
        value = cell.get("yield_published")
        if value and value > 0:
            groups[(cell["crop"], cell["uf"])].append(value)
    thresholds: dict[tuple[str, str], tuple[float, float, float]] = {}
    for key, values in groups.items():
        array = np.asarray(values, dtype=float)
        median = float(np.median(array))
        mad = float(np.median(np.abs(array - median)))
        scale = 1.4826 * mad if mad > 0 else 0.0
        thresholds[key] = (median, scale, len(values))
        summary[f"{key[0]}|{key[1]}"] = {
            "n": len(values),
            "median": median,
            "mad_scaled": scale,
            "p01": float(np.quantile(array, 0.01)),
            "p99": float(np.quantile(array, 0.99)),
        }
    extreme = 0
    for cell in cells:
        value = cell.get("yield_published")
        if not value or value <= 0:
            continue
        median, scale, _ = thresholds[(cell["crop"], cell["uf"])]
        if scale > 0 and abs(value - median) / scale > 8.0:
            cell["flags"].append("extremo_mad")
            extreme += 1
    return {"by_group": summary, "n_extreme": extreme}


def territorial_crosswalk(wide: dict[tuple, dict[str, Any]]) -> dict[str, Any]:
    """Compara o conjunto de municípios da PAM com o cadastro IBGE do painel."""
    pam_codes: dict[str, set[str]] = defaultdict(set)
    pam_names: dict[str, str] = {}
    for entry in wide.values():
        pam_codes[entry["uf"]].add(entry["ibge_code"])
        pam_names[entry["ibge_code"]] = entry.get("geography_name")

    registry: dict[str, set[str]] = defaultdict(set)
    path = os.path.join(PROCESSED, "panel_municipalities_v35.csv")
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("state")) in {
                "PR", "RS", "MS", "MT", "GO", "BA", "SP",
            }:
                registry[str(row["state"])].add(str(row["ibge_code"]))

    only_pam = {uf: sorted(codes - registry[uf]) for uf, codes in pam_codes.items() if codes - registry[uf]}
    only_registry = {
        uf: sorted(codes - pam_codes.get(uf, set()))
        for uf, codes in registry.items()
        if codes - pam_codes.get(uf, set())
    }
    return {
        "pam_municipalities": {uf: len(codes) for uf, codes in sorted(pam_codes.items())},
        "registry_municipalities": {uf: len(codes) for uf, codes in sorted(registry.items())},
        "only_in_pam": only_pam,
        "only_in_registry": only_registry,
        "n_only_in_pam": sum(len(v) for v in only_pam.values()),
        "n_only_in_registry": sum(len(v) for v in only_registry.values()),
        "names_only_in_pam": {code: pam_names.get(code) for codes in only_pam.values() for code in codes},
    }


def year_presence(wide: dict[tuple, dict[str, Any]]) -> dict[str, Any]:
    """Municípios que não aparecem em todos os anos (criação/extinção na série)."""
    years_by_code: dict[str, set[str]] = defaultdict(set)
    uf_by_code: dict[str, str] = {}
    for (code, year, _crop) in wide:
        years_by_code[code].add(year)
        uf_by_code[code] = wide[(code, year, _crop)]["uf"]
    all_years = sorted({year for _, year, _ in wide})
    incomplete = {
        code: {"uf": uf_by_code[code], "years": sorted(years), "n_years": len(years)}
        for code, years in years_by_code.items()
        if len(years) < len(all_years)
    }
    return {
        "years": all_years,
        "n_years": len(all_years),
        "n_municipalities": len(years_by_code),
        "n_with_partial_series": len(incomplete),
        "partial_series": dict(sorted(incomplete.items())[:40]),
    }


def coverage(cells: list[dict[str, Any]]) -> dict[str, Any]:
    table: dict[str, Any] = {}
    for uf in sorted({cell["uf"] for cell in cells}):
        for crop in ("soja", "milho"):
            subset = [c for c in cells if c["uf"] == uf and c["crop"] == crop]
            if not subset:
                continue
            with_yield = [c for c in subset if (c.get("yield_published") or 0) > 0]
            table[f"{uf}|{crop}"] = {
                "cells": len(subset),
                "with_positive_yield": len(with_yield),
                "no_area": sum(1 for c in subset if "sem_area" in c["flags"]),
                "planted_not_harvested": sum(
                    1 for c in subset if "plantado_sem_colheita" in c["flags"]
                ),
                "yield_zero_with_area": sum(
                    1 for c in subset if "rendimento_zero_com_area" in c["flags"]
                ),
                "yield_divergent": sum(
                    1 for c in subset if "rendimento_divergente" in c["flags"]
                ),
                "extreme": sum(1 for c in subset if "extremo_mad" in c["flags"]),
            }
    return table


def impact_on_panel(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Quantas linhas analíticas usadas hoje dependem de células com flag."""
    flagged = {
        (c["ibge_code"], c["year"], c["crop"]): c["flags"]
        for c in cells
        if c["flags"] and c["flags"] != ["sem_area"]
    }
    path = os.path.join(PROCESSED, "v35_panel_windows.csv")
    total = 0
    affected = 0
    by_flag: Counter = Counter()
    by_state: Counter = Counter()
    by_state_affected: Counter = Counter()
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            total += 1
            state = str(row.get("state"))
            by_state[state] += 1
            key = (
                str(row["ibge_code"]),
                str(row.get("harvest_year")),
                "milho" if str(row.get("crop")) == "milho_2" else str(row.get("crop")),
            )
            if key in flagged:
                affected += 1
                by_state_affected[state] += 1
                for flag in flagged[key]:
                    by_flag[flag] += 1
    return {
        "panel": "v35_panel_windows.csv",
        "panel_rows_checked": total,
        "panel_rows_with_flagged_source": affected,
        "share": round(affected / total, 4) if total else None,
        "by_flag": dict(by_flag),
        "by_state": dict(by_state),
        "by_state_affected": dict(by_state_affected),
    }


def main() -> int:
    rows, provenance = load_rows()
    wide, duplicate_info = to_wide(rows)
    cells = [classify(entry) for entry in wide.values()]
    outliers = outlier_flags(cells)
    crosswalk = territorial_crosswalk(wide)
    presence = year_presence(wide)
    coverage_table = coverage(cells)
    impact = impact_on_panel(cells)

    flag_counts: Counter = Counter()
    for cell in cells:
        for flag in cell["flags"]:
            flag_counts[flag] += 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "institution": "IBGE — Produção Agrícola Municipal (PAM)",
            "dataset": "SIDRA tabela 5457",
            "variables": list(VARIABLES),
            "files": provenance,
            "raw_rows": len(rows),
            "safra_field": "vazio para PAM (a PAM é anual; a separação 1ª/2ª safra não existe na fonte)",
        },
        "keys": {
            "canonical": ["geography_code", "reference_year", "crop_code"],
            "n_cells": len(wide),
            "duplicates": duplicate_info["duplicates"],
            "unknown_uf_rows": duplicate_info["unknown_uf_rows"],
            "duplicate_examples": duplicate_info["duplicate_examples"],
        },
        "flag_counts": dict(flag_counts),
        "outliers": outliers,
        "coverage_by_uf_crop": coverage_table,
        "territorial_crosswalk": crosswalk,
        "year_presence": presence,
        "impact_on_panel": impact,
    }

    os.makedirs(OUTDIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")

    # tabela de células com flag (rastreável)
    flagged = [cell for cell in cells if cell["flags"]]
    with open(
        os.path.join(OUTDIR, "pam_flagged_cells.csv"), "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ibge_code", "uf", "year", "crop", "area_planted_ha", "area_harvested_ha",
                "production_t", "yield_published", "yield_recomputed", "yield_relative_gap",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(flagged)

    print(f"células município-ano-cultura: {len(wide)}")
    print(f"duplicidades de chave: {duplicate_info['duplicates']}")
    print("flags:", dict(flag_counts.most_common()))
    print(f"extremos por MAD (>8 MAD): {outliers['n_extreme']}")
    print("crosswalk:", {k: crosswalk[k] for k in ('n_only_in_pam', 'n_only_in_registry')})
    print("  só na PAM:", crosswalk["names_only_in_pam"])
    print("  séries parciais:", presence["n_with_partial_series"], "de", presence["n_municipalities"])
    print("impacto no painel:", impact)
    print(f"manifesto: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
