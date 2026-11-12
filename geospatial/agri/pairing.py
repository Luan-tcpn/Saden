"""Construção do conjunto pareado espacial × agronômico (V2.5).

Regras metodológicas fixas **antes** da análise estatística:

* uma janela ZARC por (cultura, ano-safra) na análise principal — a
  **modal** entre as combinações oficiais de solo/ciclo no nível de risco
  principal; as demais combinações ficam na base como cenários de
  sensibilidade, **não** como observações independentes;
* o n efetivo é o número de **anos com rendimento PAM**, não o número de
  combinações ZARC;
* milho principal e milho 2ª safra são tratados separadamente e comparados
  com o rendimento municipal **total** apenas como análise de sensibilidade
  (incompatibilidade declarada);
* a máscara agrícola é marcada como **retrospectiva** quando o ano da cena
  difere do ano do mapa WorldCover usado.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from typing import Any, Iterable, Sequence

from . import season

# Códigos IBGE das culturas-piloto (D49).
IBGE_CROP_CODES = {"soja": "40124", "milho": "40122"}


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_csv(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def pam_yields(rows: Sequence[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Rendimento/área/quantidade do IBGE/PAM por (cultura-piloto, ano)."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if row.get("institution") != "IBGE":
            continue
        code = str(row.get("crop_code"))
        crop = next((k for k, v in IBGE_CROP_CODES.items() if v == code), None)
        if crop is None:
            continue
        year = str(row.get("reference_year") or "")
        if not year:
            continue
        key = (crop, year)
        entry = out.setdefault(
            key,
            {
                "crop": crop,
                "year": year,
                "yield_kg_ha": None,
                "yield_unit_original": row.get("unit_original"),
                "area_harvested_ha": None,
                "area_planted_ha": None,
                "quantity_produced_t": None,
                "nature": row.get("nature"),
                "source": row.get("dataset_name"),
                "source_id": row.get("dataset_id"),
                "acquired_at": row.get("acquired_at"),
            },
        )
        variable = row.get("variable_normalized")
        value = _to_float(row.get("value_normalized"))
        if variable == "rendimento_medio_kg_ha":
            entry["yield_kg_ha"] = value
        elif variable == "area_colhida_ha":
            entry["area_harvested_ha"] = value
        elif variable == "area_plantada_ha":
            entry["area_planted_ha"] = value
        elif variable == "quantidade_produzida_t":
            entry["quantity_produced_t"] = value
    return out


def consensus_window(
    windows: Sequence[dict[str, Any]], safra: str
) -> dict[str, Any] | None:
    """Janela modal (mais combinações oficiais) de uma safra."""
    candidates = [w for w in windows if w.get("safra") == safra]
    if not candidates:
        return None
    best = sorted(
        candidates,
        key=lambda w: (-int(w.get("combinations") or 0), str(w.get("start_date"))),
    )[0]
    return best


def _months_with_data(
    monthly: Sequence[dict[str, Any]],
    months: Sequence[int],
    year_offset: int,
    key: str = "ndvi_mean",
) -> dict[str, Any]:
    """Estatística do NDVI sobre os meses indicados (ano = ano_safra + offset)."""
    wanted = {f"{year_offset:04d}-{m:02d}" for m in months}
    values = []
    coverages = []
    used = []
    for row in monthly:
        month = str(row.get("month"))
        if month not in wanted:
            continue
        value = _to_float(row.get(key))
        coverage = _to_float(row.get("valid_fraction"))
        used.append(month)
        coverages.append(coverage if coverage is not None else 0.0)
        if value is not None:
            values.append(value)
    if not values:
        return {
            "ndvi_mean": None,
            "ndvi_median": None,
            "months_expected": len(wanted),
            "months_observed": 0,
            "months_with_value": 0,
            "months_used": sorted(used),
            "mean_coverage": None,
        }
    ordered = sorted(values)
    median = (
        ordered[len(ordered) // 2]
        if len(ordered) % 2
        else (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2
    )
    return {
        "ndvi_mean": sum(values) / len(values),
        "ndvi_median": median,
        "months_expected": len(wanted),
        "months_observed": len(used),
        "months_with_value": len(values),
        "months_used": sorted(used),
        "mean_coverage": (sum(coverages) / len(coverages)) if coverages else None,
    }


def build_paired_dataset(
    zarc_rows: Sequence[dict[str, Any]],
    municipal_rows: Sequence[dict[str, Any]],
    aoi_rows: Sequence[dict[str, Any]],
    pam_rows: Sequence[dict[str, Any]],
    mask_variants: Sequence[str] = ("stable", "wc2020", "wc2021", "broad"),
    min_months: int = 2,
) -> list[dict[str, Any]]:
    """Monta o dataset pareado (uma linha por cultura × ano × máscara)."""
    yields = pam_yields(pam_rows)
    municipal_by_variant: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in municipal_rows:
        variant = str(row.get("mask_variant"))
        month = str(row.get("month"))
        if not month:
            continue
        municipal_by_variant[variant][month] = row

    output: list[dict[str, Any]] = []
    for crop in ("soja", "milho", "milho_2"):
        windows = season.build_windows(zarc_rows, crop)
        if not windows:
            continue
        safras = sorted({w["safra"] for w in windows})
        for safra in safras:
            window = consensus_window(windows, safra)
            if window is None:
                continue
            relation = season.pam_year_candidates(safra, crop)
            pam_year = relation.get("primary")
            if pam_year is None:
                continue
            months = list(window["months"])
            year_offset = int(window["safra_ini"]) + (1 if crop == "milho_2" else 0)
            pam = yields.get((crop if crop != "milho_2" else "milho", str(pam_year)))
            for variant in mask_variants:
                monthly = list(municipal_by_variant.get(variant, {}).values())
                stats = _months_with_data(monthly, months, year_offset)
                aoi_stats = _months_with_data(aoi_rows, months, year_offset)
                mask_year = (
                    "2020+2021"
                    if variant in ("stable", "broad")
                    else variant[-4:]
                )
                retrospective = mask_year != str(pam_year)
                status = "excluded"
                reasons = []
                if pam is None or pam.get("yield_kg_ha") is None:
                    reasons.append("sem rendimento oficial do IBGE/PAM")
                if stats["months_with_value"] < min_months:
                    reasons.append(
                        f"meses com NDVI municipal ({stats['months_with_value']}) < {min_months}"
                    )
                if aoi_stats["months_with_value"] < min_months:
                    reasons.append(
                        f"meses com NDVI da AOI ({aoi_stats['months_with_value']}) < {min_months}"
                    )
                if not reasons:
                    status = "paired_usable"
                output.append(
                    {
                        "municipality": "Sorriso-MT",
                        "ibge_code": "5107925",
                        "crop": crop,
                        "crop_label": window.get("cultura"),
                        "ibge_crop_code": IBGE_CROP_CODES.get(
                            "milho" if crop == "milho_2" else crop
                        ),
                        "safra": safra,
                        "safra_ini": window.get("safra_ini"),
                        "safra_fin": window.get("safra_fin"),
                        "pam_reference_year": pam_year,
                        "pam_year_alternative": relation.get("alternative"),
                        "pam_year_confidence": relation.get("confidence"),
                        "pam_year_ambiguity": relation.get("ambiguity"),
                        "zarc_window_months": ";".join(str(m) for m in months),
                        "zarc_window_start": window.get("start_date"),
                        "zarc_window_end": window.get("end_date"),
                        "zarc_decends": ";".join(str(d) for d in window.get("decends", [])),
                        "zarc_soil": window.get("cod_solo"),
                        "zarc_cycle": window.get("cod_ciclo"),
                        "zarc_risk": window.get("risk"),
                        "zarc_portaria": window.get("portaria"),
                        "zarc_combinations": window.get("combinations"),
                        "mask_variant": variant,
                        "mask_year": mask_year,
                        "mask_retrospective": retrospective,
                        "ndvi_municipal_mean": stats["ndvi_mean"],
                        "ndvi_municipal_median": stats["ndvi_median"],
                        "ndvi_municipal_months": stats["months_with_value"],
                        "ndvi_municipal_coverage": stats["mean_coverage"],
                        "ndvi_aoi_mean": aoi_stats["ndvi_mean"],
                        "ndvi_aoi_median": aoi_stats["ndvi_median"],
                        "ndvi_aoi_months": aoi_stats["months_with_value"],
                        "yield_kg_ha": (pam or {}).get("yield_kg_ha"),
                        "yield_unit_original": (pam or {}).get("yield_unit_original"),
                        "area_harvested_ha": (pam or {}).get("area_harvested_ha"),
                        "quantity_produced_t": (pam or {}).get("quantity_produced_t"),
                        "observation_nature": (pam or {}).get("nature"),
                        "source": (pam or {}).get("source"),
                        "source_id": (pam or {}).get("source_id"),
                        "spatial_compatibility": "B (municipal; AOI é sub-região)",
                        "temporal_compatibility": (
                            "janela de plantio ZARC na safra; rendimento no ano de "
                            "colheita (derivado)"
                        ),
                        "semantic_compatibility": (
                            "parcial (milho: PAM publica o total anual, não a safra)"
                            if crop == "milho_2"
                            else "boa (mesma cultura, mesma área, mesmo ano de colheita)"
                        ),
                        "status": status,
                        "quality_flag": (
                            "paired_with_retrospective_mask"
                            if retrospective and status == "paired_usable"
                            else ("paired" if status == "paired_usable" else "unusable")
                        ),
                        "exclusion_reason": "; ".join(reasons) if reasons else None,
                    }
                )
    return output


def write_csv(rows: Iterable[dict[str, Any]], path: str) -> str:
    rows = list(rows)
    if not rows:
        return path
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path
