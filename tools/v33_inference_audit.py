"""V3.3 — Frente B: auditoria da inferência de associação de V2.7 a V3.0.

Isola o efeito da **estrutura de agrupamento**, mantendo modelo, amostra e
variável idênticos:

* modelo *within* de dois fatores (município e ano), o mesmo desde a V2.7;
* mesma amostra e mesma variável de cada família histórica;
* muda **apenas** a VCV: município, bloco 250 km, UF, UF×ano, e UF×ano+município
  (duplo, D104).

Três cenários, sempre separados (pré-registro §14.1):

* **C1** — reprodução histórica: dados históricos (`_legacy`) + agrupamento por
  bloco, a base das famílias de multiplicidade de V2.7/V3.0;
* **C2** — inferência corrigida: mesmos dados e coeficiente, agrupamento duplo;
* **C3** — reanálise com dados corrigidos (só onde o dado mudou), reportada
  separadamente e nunca usada para atribuir à inferência o que é da janela.

Famílias auditadas:
* **F1 (V2.7)** — 3 culturas × 7 variáveis = 21 hipóteses, janela histórica;
* **F2 (V3.0)** — 3 culturas × 5 definições de déficit = 15 hipóteses.

Uso: python tools/v33_inference_audit.py
"""

from __future__ import annotations

import csv
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

from agroclimate import robust, spatial_inference  # noqa: E402

import v31_models as base  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
PANEL = os.path.join(PROCESSED, "v31_panel_windows.csv")
OUT = os.path.join(MANIFESTS, "v33_inference_audit.json")
OUT_CSV = os.path.join(MANIFESTS, "v33_inference_audit.csv")

V27_VARIABLES = (
    "precip_acumulada_mm",
    "temp_media_c",
    "degree_days_total",
    "extreme_heat_days",
    "et0_total_mm",
    "deficiency_total_mm",
    "excess_total_mm",
)

V30_SPECS = {
    "deficit_hist": "deficiency_total_mm_legacy",
    "deficit_corr50": "deficiency_total_mm_corrected",
    "deficit_cad60": "deficiency_cad_0_60",
    "deficit_cad100": "deficiency_cad_0_100",
    "deficit_cad200": "deficiency_cad_0_200",
}

CROPS = ("soja", "milho", "milho_2")


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_panel() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {crop: [] for crop in CROPS}
    with open(PANEL, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            crop = str(row.get("crop"))
            if crop not in out:
                continue
            record = {
                "ibge_code": str(row["ibge_code"]),
                "state": row.get("state"),
                "year": int(float(row["harvest_year"])),
                "spatial_block": row.get("stored_spatial_block") or None,
                "yield_kg_ha": _num(row.get("yield_kg_ha")),
            }
            out[crop].append(record)
    return out


def attach_blocks(panel: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Blocos espaciais idênticos aos de V2.7/V3.2 (raio 250 km)."""
    from agroclimate import spatial

    import run_robustness as rr

    blocks = spatial.spatial_blocks(rr.load_municipalities(), 250.0)
    for crop, rows in panel.items():
        for row in rows:
            row["spatial_block"] = blocks.get(row["ibge_code"])
    return panel


def load_variables() -> dict[str, list[dict]]:
    """Valores por linha de todas as variáveis auditadas (legacy e corrigidas)."""
    wanted = list(V27_VARIABLES) + list(V30_SPECS.values())
    out: dict[str, list[dict]] = {crop: [] for crop in CROPS}
    with open(PANEL, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            crop = str(row.get("crop"))
            if crop not in out:
                continue
            record = {"key": (str(row["ibge_code"]), str(row["safra"]))}
            for variable in wanted:
                column = f"{variable}_legacy" if variable in V27_VARIABLES else variable
                record[variable] = _num(row.get(column))
            out[crop].append(record)
    return out


def associate(rows: list[dict], variable: str, min_rows: int = 400) -> dict[str, Any]:
    """Coeficiente *within* e p-valores sob cinco estruturas de agrupamento."""
    usable = [
        row
        for row in rows
        if row.get(variable) is not None
        and row.get("yield_kg_ha") is not None
        and row.get("spatial_block")
        and row.get("state")
    ]
    if len(usable) < min_rows:
        return {"status": "insufficient_rows", "n": len(usable)}
    municipalities = [row["ibge_code"] for row in usable]
    years = [row["year"] for row in usable]
    states = [row["state"] for row in usable]
    blocks = [row["spatial_block"] for row in usable]
    state_years = [f"{s}||{y}" for s, y in zip(states, years)]

    y = np.array([row["yield_kg_ha"] for row in usable], dtype="float64")
    x = np.array([row[variable] for row in usable], dtype="float64")
    y_within = spatial_inference.within_transform(y, municipalities, years)
    x_within = spatial_inference.within_transform(x, municipalities, years)
    design = x_within.reshape(-1, 1)
    if float(np.std(design)) == 0.0:
        return {"status": "degenerate_design", "n": len(usable)}
    beta, *_ = np.linalg.lstsq(design, y_within, rcond=None)
    residuals = y_within - design @ beta
    coefficient = float(beta[0])

    schemes: dict[str, Any] = {}
    definitions = {
        "municipio": (municipalities, None),
        "bloco_espacial_250km": (blocks, None),
        "uf": (states, None),
        "uf_ano": (state_years, None),
        "two_way": (state_years, municipalities),
    }
    for label, (clusters_a, clusters_b) in definitions.items():
        if clusters_b is None:
            vcv, info = robust.cluster_vcov(
                design, residuals, clusters_a, correction=robust.CR1
            )
            n_clusters = int(info["n_clusters"])
        else:
            vcv, info = robust.two_way_cluster_vcov(
                design, residuals, clusters_a, clusters_b, correction=robust.CR1
            )
            n_clusters = min(info["n_clusters_a"], info["n_clusters_b"])
        std_error = float(np.sqrt(max(vcv[0, 0], 0.0)))
        degrees = max(n_clusters - 1, 1)
        degenerate = robust.degenerate_std_error(coefficient, std_error)
        statistic = None if degenerate else coefficient / std_error
        critical = robust.t_critical(0.05, degrees)
        schemes[label] = {
            "n_clusters": n_clusters,
            "std_error": std_error,
            "t_statistic": statistic,
            "p_value": robust.t_sf(statistic, degrees) if statistic is not None else None,
            "ci95": [coefficient - critical * std_error, coefficient + critical * std_error],
            "df": degrees,
        }
    return {
        "status": "ok",
        "n": len(usable),
        "n_municipalities": len(set(municipalities)),
        "n_years": len(set(years)),
        "coefficient": coefficient,
        "r_squared_within": float(
            1.0 - np.var(residuals) / np.var(y_within)
        )
        if np.var(y_within) > 0
        else None,
        "schemes": schemes,
    }


def classify(entry: dict[str, Any], holm_block: float | None, holm_two: float | None) -> str:
    if entry.get("status") != "ok":
        return "nao_auditavel"
    p_block = entry["schemes"]["bloco_espacial_250km"]["p_value"]
    p_two = entry["schemes"]["two_way"]["p_value"]
    if p_block is None or p_two is None:
        return "nao_auditavel"
    sig_block = p_block < 0.05
    sig_two = p_two < 0.05
    sig_two_holm = holm_two is not None and holm_two < 0.05
    if sig_block and sig_two and sig_two_holm:
        return "mantida"
    if sig_block and sig_two and not sig_two_holm:
        return "mantida_apenas_bruta"
    if sig_block and p_two < 0.10:
        return "enfraquecida"
    if sig_block and not sig_two:
        return "nao_sustentada"
    if not sig_block and sig_two_holm:
        return "reforcada"
    return "sem_evidencia_em_nenhum"


def _holm(values: dict[str, float]) -> dict[str, float]:
    return robust.holm_adjust(values) if values else {}


def main() -> int:
    started = time.time()

    # painel mínimo + variáveis auditadas, na mesma ordem do CSV
    full: dict[str, list[dict]] = {crop: [] for crop in CROPS}
    with open(PANEL, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            crop = str(row.get("crop"))
            if crop not in full:
                continue
            record = {
                "ibge_code": str(row["ibge_code"]),
                "state": row.get("state"),
                "year": int(float(row["harvest_year"])),
                "spatial_block": None,
                "yield_kg_ha": _num(row.get("yield_kg_ha")),
                "safra": str(row.get("safra")),
            }
            for variable in V27_VARIABLES:
                record[variable] = _num(row.get(f"{variable}_legacy"))
            for spec, column in V30_SPECS.items():
                record[spec] = _num(row.get(column))
            full[crop].append(record)
    full = attach_blocks(full)

    historical_v27 = json.load(
        open(os.path.join(MANIFESTS, "v27_robust_inference.json"), encoding="utf-8")
    )
    historical_v30 = json.load(
        open(os.path.join(MANIFESTS, "v30_association_cad.json"), encoding="utf-8")
    )

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "within de municipio e ano; mesmo coeficiente sob todas as estruturas; "
            "somente a VCV muda (CR1). C1 = historico (bloco), C2 = duplo UFxano+municipio"
        ),
        "scenarios": {
            "C1": "dados historicos + agrupamento por bloco (base das familias historicas)",
            "C2": "mesmos dados e coeficiente + agrupamento duplo UFxano+municipio",
            "C3": "reanalise com janela corrigida (separada; nao e efeito de inferencia)",
        },
        "families": {},
    }

    # ---------------- F1: V2.7 (21 hipoteses, janela historica) --------------
    f1: dict[str, dict] = {}
    reproduction: list[float] = []
    for crop in CROPS:
        for variable in V27_VARIABLES:
            row_key = f"{crop}|{variable}"
            entry = associate(full[crop], variable)
            historical = (
                historical_v27["crops"][crop]["variables"][variable]["within_clustered"]
            )
            entry["historical_coefficient"] = historical.get("coefficient")
            entry["historical_scheme"] = {
                label: {
                    "std_error": historical["schemes"].get(label, {}).get("std_error"),
                    "p_value": historical["schemes"].get(label, {}).get("p_value"),
                }
                for label in ("municipio", "bloco_espacial_250km")
            }
            if entry.get("status") == "ok" and historical.get("coefficient") is not None:
                reproduction.append(abs(entry["coefficient"] - historical["coefficient"]))
            f1[row_key] = entry

    p_block = {
        k: v["schemes"]["bloco_espacial_250km"]["p_value"]
        for k, v in f1.items()
        if v.get("status") == "ok" and v["schemes"]["bloco_espacial_250km"]["p_value"] is not None
    }
    p_two = {
        k: v["schemes"]["two_way"]["p_value"]
        for k, v in f1.items()
        if v.get("status") == "ok" and v["schemes"]["two_way"]["p_value"] is not None
    }
    holm_block = _holm(p_block)
    holm_two = _holm(p_two)
    for key, entry in f1.items():
        entry["p_holm_block"] = holm_block.get(key)
        entry["p_holm_two_way"] = holm_two.get(key)
        entry["classification"] = classify(entry, holm_block.get(key), holm_two.get(key))
    payload["families"]["F1_v27"] = {
        "source": "v27_robust_inference.json",
        "hypotheses": len(f1),
        "reproduction_max_abs_diff": max(reproduction) if reproduction else None,
        "reproduction_n": len(reproduction),
        "historical": {
            "n_significant_raw": historical_v27["multiplicity"]["bloco_espacial_250km"][
                "n_significant_raw"
            ],
            "n_significant_holm": historical_v27["multiplicity"]["bloco_espacial_250km"][
                "n_significant_holm"
            ],
            "method": "Holm sobre 21, agrupamento por bloco 250 km",
        },
        "audited": {
            "n_significant_raw_block": sum(1 for v in p_block.values() if v < 0.05),
            "n_significant_holm_block": sum(1 for v in holm_block.values() if v < 0.05),
            "n_significant_raw_two_way": sum(1 for v in p_two.values() if v < 0.05),
            "n_significant_holm_two_way": sum(1 for v in holm_two.values() if v < 0.05),
        },
        "holm_block": holm_block,
        "holm_two_way": holm_two,
        "results": f1,
    }

    # ---------------- F2: V3.0 (15 hipoteses de deficit) --------------------
    f2: dict[str, dict] = {}
    reproduction2: list[float] = []
    for crop in CROPS:
        for spec in V30_SPECS:
            row_key = f"{crop}|{spec}"
            entry = associate(full[crop], spec)
            historical = historical_v30["crops"][crop].get(spec, {})
            entry["historical_coefficient"] = historical.get("coefficient")
            entry["historical_std_error"] = historical.get("std_error")
            entry["historical_p_value"] = historical.get("p_value")
            if entry.get("status") == "ok" and historical.get("coefficient") is not None:
                reproduction2.append(abs(entry["coefficient"] - historical["coefficient"]))
            f2[row_key] = entry
    p_block2 = {
        k: v["schemes"]["bloco_espacial_250km"]["p_value"]
        for k, v in f2.items()
        if v.get("status") == "ok" and v["schemes"]["bloco_espacial_250km"]["p_value"] is not None
    }
    p_two2 = {
        k: v["schemes"]["two_way"]["p_value"]
        for k, v in f2.items()
        if v.get("status") == "ok" and v["schemes"]["two_way"]["p_value"] is not None
    }
    holm_block2 = _holm(p_block2)
    holm_two2 = _holm(p_two2)
    for key, entry in f2.items():
        entry["p_holm_block"] = holm_block2.get(key)
        entry["p_holm_two_way"] = holm_two2.get(key)
        entry["classification"] = classify(entry, holm_block2.get(key), holm_two2.get(key))
    payload["families"]["F2_v30"] = {
        "source": "v30_association_cad.json",
        "hypotheses": len(f2),
        "reproduction_max_abs_diff": max(reproduction2) if reproduction2 else None,
        "reproduction_n": len(reproduction2),
        "historical": {
            "n_significant_holm": historical_v30.get("n_survive_holm"),
            "n_tests": historical_v30.get("n_tests"),
            "method": "Holm sobre 15, agrupamento por bloco 250 km",
        },
        "audited": {
            "n_significant_raw_block": sum(1 for v in p_block2.values() if v < 0.05),
            "n_significant_holm_block": sum(1 for v in holm_block2.values() if v < 0.05),
            "n_significant_raw_two_way": sum(1 for v in p_two2.values() if v < 0.05),
            "n_significant_holm_two_way": sum(1 for v in holm_two2.values() if v < 0.05),
        },
        "holm_block": holm_block2,
        "holm_two_way": holm_two2,
        "results": f2,
    }

    # ---------------- F3: V2.9 (interacao por grupo de ciclo) --------------
    cycle_manifest = json.load(
        open(os.path.join(MANIFESTS, "v29_cycle_interaction.json"), encoding="utf-8")
    )
    cycle_rows = {crop: [] for crop in CROPS}
    with open(PANEL, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            crop = str(row.get("crop"))
            if crop not in cycle_rows:
                continue
            cycle_rows[crop].append(
                {
                    "ibge_code": str(row["ibge_code"]),
                    "state": row.get("state"),
                    "year": int(float(row["harvest_year"])),
                    "spatial_block": None,
                    "yield_kg_ha": _num(row.get("yield_kg_ha")),
                    "zarc_cycle": str(row.get("zarc_cycle") or ""),
                    "deficiency_total_mm": _num(row.get("deficiency_total_mm_legacy")),
                    "temp_media_c": _num(row.get("temp_media_c_legacy")),
                    "precip_acumulada_mm": _num(row.get("precip_acumulada_mm_legacy")),
                }
            )
    cycle_rows = attach_blocks(cycle_rows)
    f3: dict[str, dict] = {}
    reproduction3: list[float] = []
    for crop in CROPS:
        tests = cycle_manifest["crops"][crop]["tests"]
        for variable, spec in tests.items():
            if spec.get("status") != "ok":
                continue
            reference_class = str(spec["reference_class"])
            contrast_class = str(spec["contrast_class"])
            subset = [
                row
                for row in cycle_rows[crop]
                if row.get(variable) is not None
                and row.get("yield_kg_ha") is not None
                and row.get("spatial_block")
                and row.get("state")
                and row.get("zarc_cycle") in (reference_class, contrast_class)
            ]
            key = f"{crop}|{variable}"
            if len(subset) < 400:
                f3[key] = {"status": "insufficient_rows", "n": len(subset)}
                continue
            municipalities = [row["ibge_code"] for row in subset]
            years = [row["year"] for row in subset]
            states = [row["state"] for row in subset]
            blocks = [row["spatial_block"] for row in subset]
            state_years = [f"{s}||{y}" for s, y in zip(states, years)]
            y = np.array([row["yield_kg_ha"] for row in subset], dtype="float64")
            x = np.array([row[variable] for row in subset], dtype="float64")
            indicator = np.array(
                [1.0 if row["zarc_cycle"] == contrast_class else 0.0 for row in subset]
            )
            y_w = spatial_inference.within_transform(y, municipalities, years)
            x_w = spatial_inference.within_transform(x, municipalities, years)
            interaction = spatial_inference.within_transform(
                x * indicator, municipalities, years
            )
            design = np.column_stack([x_w, interaction])
            if float(np.std(design, axis=0).max()) == 0.0:
                f3[key] = {"status": "degenerate_design", "n": len(subset)}
                continue
            beta, *_ = np.linalg.lstsq(design, y_w, rcond=None)
            residuals = y_w - design @ beta
            entry: dict[str, Any] = {
                "status": "ok",
                "n": len(subset),
                "reference_class": reference_class,
                "contrast_class": contrast_class,
                "slope_difference": float(beta[1]),
                "historical_p_value": spec["slope_difference"].get("p_value"),
                "historical_coefficient": spec["slope_difference"].get("coefficient"),
            }
            if entry["historical_coefficient"] is not None:
                reproduction3.append(
                    abs(entry["slope_difference"] - entry["historical_coefficient"])
                )
            for label, clusters in (
                ("bloco_espacial_250km", blocks),
                ("two_way", None),
            ):
                if clusters is None:
                    vcv, info = robust.two_way_cluster_vcov(
                        design, residuals, state_years, municipalities, correction=robust.CR1
                    )
                    n_clusters = min(info["n_clusters_a"], info["n_clusters_b"])
                else:
                    vcv, info = robust.cluster_vcov(
                        design, residuals, clusters, correction=robust.CR1
                    )
                    n_clusters = int(info["n_clusters"])
                std_error = float(np.sqrt(max(vcv[1, 1], 0.0)))
                degrees = max(n_clusters - 1, 1)
                statistic = (
                    None
                    if robust.degenerate_std_error(entry["slope_difference"], std_error)
                    else entry["slope_difference"] / std_error
                )
                entry[f"se_{label}"] = std_error
                entry[f"p_{label}"] = (
                    robust.t_sf(statistic, degrees) if statistic is not None else None
                )
                entry[f"n_clusters_{label}"] = n_clusters
            f3[key] = entry

    p3_block = {
        k: v["p_bloco_espacial_250km"]
        for k, v in f3.items()
        if v.get("status") == "ok" and v.get("p_bloco_espacial_250km") is not None
    }
    p3_two = {
        k: v["p_two_way"]
        for k, v in f3.items()
        if v.get("status") == "ok" and v.get("p_two_way") is not None
    }
    holm3_block = _holm(p3_block)
    holm3_two = _holm(p3_two)
    for key, entry in f3.items():
        if entry.get("status") != "ok":
            continue
        entry["p_holm_block"] = holm3_block.get(key)
        entry["p_holm_two_way"] = holm3_two.get(key)
    payload["families"]["F3_v29_interaction"] = {
        "source": "v29_cycle_interaction.json",
        "hypotheses": len(f3),
        "reproduction_max_abs_diff": max(reproduction3) if reproduction3 else None,
        "audited": {
            "n_significant_raw_block": sum(1 for v in p3_block.values() if v < 0.05),
            "n_significant_holm_block": sum(1 for v in holm3_block.values() if v < 0.05),
            "n_significant_raw_two_way": sum(1 for v in p3_two.values() if v < 0.05),
            "n_significant_holm_two_way": sum(1 for v in holm3_two.values() if v < 0.05),
        },
        "holm_block": holm3_block,
        "holm_two_way": holm3_two,
        "results": f3,
    }
    print("\n=== V2.9 interacoes: %d testes ===" % len(f3))
    for key in sorted(f3):
        entry = f3[key]
        if entry.get("status") != "ok":
            continue
        print(
            "  %-28s d=%+9.4f p_bloco=%.4f p_2way=%.4f (hist %.4f)"
            % (
                key,
                entry["slope_difference"],
                entry["p_bloco_espacial_250km"],
                entry["p_two_way"],
                entry["historical_p_value"] or 9,
            )
        )

    payload["elapsed_s"] = round(time.time() - started, 1)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")

    # CSV de rastreabilidade
    rows_out = []
    for family in ("F1_v27", "F2_v30"):
        for key, entry in payload["families"][family]["results"].items():
            if entry.get("status") != "ok":
                continue
            crop, variable = key.split("|")
            rows_out.append(
                {
                    "family": family,
                    "crop": crop,
                    "variable": variable,
                    "coefficient": entry["coefficient"],
                    "se_block": entry["schemes"]["bloco_espacial_250km"]["std_error"],
                    "se_uf": entry["schemes"]["uf"]["std_error"],
                    "se_uf_ano": entry["schemes"]["uf_ano"]["std_error"],
                    "se_two_way": entry["schemes"]["two_way"]["std_error"],
                    "p_block": entry["schemes"]["bloco_espacial_250km"]["p_value"],
                    "p_two_way": entry["schemes"]["two_way"]["p_value"],
                    "holm_block": entry.get("p_holm_block"),
                    "holm_two_way": entry.get("p_holm_two_way"),
                    "classification": entry.get("classification"),
                    "n": entry["n"],
                }
            )
    if rows_out:
        with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows_out[0].keys()))
            writer.writeheader()
            writer.writerows(rows_out)

    # ---- resumo no console -------------------------------------------------
    for family, label in (("F1_v27", "V2.7"), ("F2_v30", "V3.0")):
        block = payload["families"][family]
        print(f"\n=== {label}: {block['hypotheses']} hipoteses "
              f"(reproducao max diff {block['reproduction_max_abs_diff']:.2e}) ===")
        counts: dict[str, int] = {}
        for key, entry in block["results"].items():
            counts[entry["classification"]] = counts.get(entry["classification"], 0) + 1
        for key, value in sorted(counts.items()):
            print(f"  {key:<26} {value}")
        print("  --- hipoteses que mudam de conclusao ---")
        for key, entry in block["results"].items():
            if entry.get("status") != "ok":
                continue
            pb = entry["schemes"]["bloco_espacial_250km"]["p_value"]
            pt = entry["schemes"]["two_way"]["p_value"]
            if (pb < 0.05) != (pt < 0.05):
                ratio = entry["schemes"]["two_way"]["std_error"] / max(
                    entry["schemes"]["bloco_espacial_250km"]["std_error"], 1e-12
                )
                print(
                    "    %-34s p_bloco=%.4f p_2way=%.4f (SE x%.2f) -> %s"
                    % (key, pb, pt, ratio, entry["classification"])
                )
    print(f"\nmanifesto: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
