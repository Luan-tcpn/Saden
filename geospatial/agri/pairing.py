"""Construção do conjunto pareado espacial × agronômico (V2.5).

Regras metodológicas fixadas **antes** da análise estatística:

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
  difere do ano do mapa WorldCover usado;
* as janelas usam datas **absolutas** (``YYYY-MM``) derivadas da âncora
  corrigida dos decêndios (V2.5) — não de um deslocamento de ano único.
"""

from __future__ import annotations

import csv
import os
from collections import Counter, defaultdict
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
    """Janela modal de uma safra (mais combinações oficiais de solo/ciclo).

    Empates são desempatados pela data de início mais tardia — critério
    determinístico e **independente** do rendimento observado.
    """
    candidates = [w for w in windows if w.get("safra") == safra]
    if not candidates:
        return None
    counts = Counter(tuple(w.get("decends") or []) for w in candidates)
    best_key = sorted(
        counts,
        key=lambda k: (-counts[k], max(k) if k else 0),
    )[0]
    best = [w for w in candidates if tuple(w.get("decends") or []) == best_key]
    best.sort(key=lambda w: str(w.get("start_date")))
    chosen = dict(best[-1])
    chosen["official_combinations"] = counts[best_key]
    chosen["distinct_windows"] = len(counts)
    return chosen


def _months_with_data(
    monthly: Sequence[dict[str, Any]],
    months: Sequence[str],
    key: str = "ndvi_mean",
) -> dict[str, Any]:
    """Estatística do NDVI sobre os meses indicados (``YYYY-MM``)."""
    wanted = set(months)
    values: list[float] = []
    coverages: list[float] = []
    used: list[str] = []
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
            "months_observed": len(used),
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
    max_risk: int = season.PRIMARY_MAX_RISK,
    min_coverage: float = 0.5,
) -> list[dict[str, Any]]:
    """Monta o dataset pareado (uma linha por cultura × janela × máscara).

    Duas **fatias** (modos de pareamento) são produzidas, para que a comparação
    com a V2.3 separe o efeito da **escala** do efeito da **janela**:

    ``zarc_sazonal``
        janela de plantio do ZARC (modal da safra) × ano de colheita da PAM;
    ``ano_civil_v23``
        agregação por ano civil (exatamente a regra da V2.3) sobre a AOI e
        sobre o município — é a **réplica** da V2.3 e o controle que isola a
        mudança de escala.

    ``min_coverage`` é a cobertura válida média mínima exigida dos meses
    **usados** na janela: abaixo disso o período é marcado como incompleto e
    **não** entra na análise estatística (o valor original é preservado).
    """
    yields = pam_yields(pam_rows)
    municipal_by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in municipal_rows:
        variant = str(row.get("mask_variant"))
        month = str(row.get("month"))
        if not month:
            continue
        municipal_by_variant[variant].append(row)
    # a série da AOI só entra com os meses **observados** (regra da V2.3)
    aoi_observed = [
        row for row in aoi_rows if str(row.get("status")) == "observed"
    ]

    output: list[dict[str, Any]] = []
    output.extend(
        _seasonal_rows(
            zarc_rows,
            municipal_by_variant,
            aoi_observed,
            yields,
            mask_variants,
            min_months,
            max_risk,
            min_coverage,
        )
    )
    output.extend(
        _civil_year_rows(
            municipal_by_variant,
            aoi_observed,
            yields,
            mask_variants,
            min_months,
        )
    )
    return output


def _seasonal_rows(
    zarc_rows: Sequence[dict[str, Any]],
    municipal_by_variant: dict[str, list[dict[str, Any]]],
    aoi_rows: Sequence[dict[str, Any]],
    yields: dict[tuple[str, str], dict[str, Any]],
    mask_variants: Sequence[str],
    min_months: int,
    max_risk: int,
    min_coverage: float,
) -> list[dict[str, Any]]:
    """Fatia sazonal: janela ZARC × ano de colheita da PAM."""
    output: list[dict[str, Any]] = []
    for crop in ("soja", "milho", "milho_2"):
        windows = season.build_windows(zarc_rows, crop, max_risk=max_risk)
        if not windows:
            continue
        safras = sorted({str(w["safra"]) for w in windows})
        for safra in safras:
            window = consensus_window(windows, safra)
            if window is None:
                continue
            relation = season.pam_year_candidates(safra, crop)
            pam_year = relation.get("primary")
            if pam_year is None:
                continue
            months = list(window["months"])
            pam_crop = "milho" if crop == "milho_2" else crop
            pam = yields.get((pam_crop, str(pam_year)))
            for variant in mask_variants:
                monthly = municipal_by_variant.get(variant, [])
                stats = _months_with_data(monthly, months)
                aoi_stats = _months_with_data(aoi_rows, months)
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
                elif (stats["mean_coverage"] or 0.0) < min_coverage:
                    reasons.append(
                        f"cobertura média municipal ({stats['mean_coverage']:.2f}) < {min_coverage}"
                    )
                if aoi_stats["months_with_value"] < min_months:
                    reasons.append(
                        f"meses com NDVI da AOI ({aoi_stats['months_with_value']}) < {min_months}"
                    )
                if not reasons:
                    status = "paired_usable"
                output.append(
                    {
                        "pairing_mode": "zarc_sazonal",
                        "municipality": "Sorriso-MT",
                        "ibge_code": "5107925",
                        "crop": crop,
                        "crop_label": window.get("cultura"),
                        "ibge_crop_code": IBGE_CROP_CODES.get(pam_crop),
                        "safra": safra,
                        "safra_ini": window.get("safra_ini"),
                        "safra_fin": window.get("safra_fin"),
                        "pam_reference_year": pam_year,
                        "pam_year_alternative": relation.get("alternative"),
                        "pam_year_confidence": relation.get("confidence"),
                        "pam_year_ambiguity": relation.get("ambiguity"),
                        "window_months": ";".join(months),
                        "window_start": window.get("start_date"),
                        "window_end": window.get("end_date"),
                        "zarc_decends": ";".join(str(d) for d in window.get("decends", [])),
                        "zarc_soil": window.get("cod_solo"),
                        "zarc_cycle": window.get("cod_ciclo"),
                        "zarc_risk_max": window.get("max_risk"),
                        "zarc_portaria": window.get("portaria"),
                        "zarc_official_combinations": window.get("official_combinations"),
                        "zarc_distinct_windows": window.get("distinct_windows"),
                        "mask_variant": variant,
                        "mask_year": mask_year,
                        "mask_retrospective": retrospective,
                        "ndvi_mean": stats["ndvi_mean"],
                        "ndvi_median": stats["ndvi_median"],
                        "ndvi_months": stats["months_with_value"],
                        "ndvi_coverage": stats["mean_coverage"],
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


def _civil_year_rows(
    municipal_by_variant: dict[str, list[dict[str, Any]]],
    aoi_rows: Sequence[dict[str, Any]],
    yields: dict[tuple[str, str], dict[str, Any]],
    mask_variants: Sequence[str],
    min_months: int,
    min_coverage: float = 0.5,
) -> list[dict[str, Any]]:
    """Fatia de ano civil — réplica da V2.3 (mesma regra de agregação).

    Os critérios de exclusão reproduzem os da V2.3 (``min_months=3``,
    ``min_coverage=0,5`` sobre a **AOI**), de modo que a replicação é
    verificável par a par.
    """
    output: list[dict[str, Any]] = []
    for crop in ("soja", "milho"):
        years = sorted({year for (c, year) in yields if c == crop})
        for year in years:
            pam = yields.get((crop, year))
            if pam is None or pam.get("yield_kg_ha") is None:
                continue
            months = [f"{year}-{m:02d}" for m in range(1, 13)]
            aoi_stats = _months_with_data(aoi_rows, months)
            aoi_usable = (
                aoi_stats["months_with_value"] >= min_months
                and (aoi_stats["mean_coverage"] or 0.0) >= min_coverage
            )
            for variant in mask_variants:
                monthly = municipal_by_variant.get(variant, [])
                stats = _months_with_data(monthly, months)
                mask_year = (
                    "2020+2021"
                    if variant in ("stable", "broad")
                    else variant[-4:]
                )
                status = "excluded"
                reasons = []
                if not aoi_usable:
                    reasons.append(
                        "série da AOI insuficiente (meses ou cobertura)"
                    )
                if stats["months_with_value"] < min_months:
                    reasons.append(
                        f"meses com NDVI municipal ({stats['months_with_value']}) < {min_months}"
                    )
                if not reasons:
                    status = "paired_usable"
                output.append(
                    {
                        "pairing_mode": "ano_civil_v23",
                        "municipality": "Sorriso-MT",
                        "ibge_code": "5107925",
                        "crop": crop,
                        "crop_label": crop,
                        "ibge_crop_code": IBGE_CROP_CODES.get(crop),
                        "safra": None,
                        "safra_ini": None,
                        "safra_fin": None,
                        "pam_reference_year": int(year),
                        "pam_year_alternative": None,
                        "pam_year_confidence": "alta (ano civil = ano PAM)",
                        "pam_year_ambiguity": None,
                        "window_months": None,
                        "window_start": None,
                        "window_end": None,
                        "zarc_decends": None,
                        "zarc_soil": None,
                        "zarc_cycle": None,
                        "zarc_risk_max": None,
                        "zarc_portaria": None,
                        "zarc_official_combinations": None,
                        "zarc_distinct_windows": None,
                        "mask_variant": variant,
                        "mask_year": mask_year,
                        "mask_retrospective": mask_year != str(year),
                        "ndvi_mean": stats["ndvi_mean"],
                        "ndvi_median": stats["ndvi_median"],
                        "ndvi_months": stats["months_with_value"],
                        "ndvi_coverage": stats["mean_coverage"],
                        "ndvi_aoi_mean": aoi_stats["ndvi_mean"],
                        "ndvi_aoi_median": aoi_stats["ndvi_median"],
                        "ndvi_aoi_months": aoi_stats["months_with_value"],
                        "yield_kg_ha": pam.get("yield_kg_ha"),
                        "yield_unit_original": pam.get("yield_unit_original"),
                        "area_harvested_ha": pam.get("area_harvested_ha"),
                        "quantity_produced_t": pam.get("quantity_produced_t"),
                        "observation_nature": pam.get("nature"),
                        "source": pam.get("source"),
                        "source_id": pam.get("source_id"),
                        "spatial_compatibility": "B (municipal; AOI é sub-região)",
                        "temporal_compatibility": "ano civil do rendimento PAM",
                        "semantic_compatibility": (
                            "boa (mesma cultura, mesma área, mesmo ano de colheita)"
                        ),
                        "status": status,
                        "quality_flag": (
                            "paired_with_retrospective_mask"
                            if mask_year != str(year) and status == "paired_usable"
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
