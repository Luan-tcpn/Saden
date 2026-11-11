"""Compatibilidade espacial e temporal entre as fontes oficiais e o Sentinel-2.

Classificação usada (a mesma nos relatórios):

* **A — compatibilidade espacial direta**: a fonte tem observação na mesma
  unidade espacial do indicador geoespacial, com suporte espacial
  comprovadamente compatível;
* **B — compatibilidade contextual**: a fonte pertence a uma unidade
  territorial maior (município que contém a AOI, ou UF), servindo como
  contexto, não como validação direta da AOI;
* **C — incompatibilidade espacial**: a granularidade/posição impede
  qualquer associação válida no nível da AOI.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from typing import Any, Iterable, Sequence

from . import config

CLASS_A = "A"
CLASS_B = "B"
CLASS_C = "C"

CLASS_LABELS = {
    CLASS_A: "compatibilidade espacial direta",
    CLASS_B: "compatibilidade contextual",
    CLASS_C: "incompatibilidade espacial",
}


# ------------------------------------------------------------------ espacial


def spatial_geometry_report(
    municipality_geom: Any,
    validation_aoi_geom: Any,
    equal_area_crs: str = config.EQUAL_AREA_CRS,
) -> dict[str, Any]:
    """Relaciona AOI de validação e município com geometrias reais.

    Usa interseção geométrica (não bounding boxes) e mede área em projeção de
    área igual, como definido na V2.1 (D42).
    """
    from pyproj import Transformer
    from shapely.ops import transform as shapely_transform

    transformer = Transformer.from_crs("EPSG:4326", equal_area_crs, always_xy=True)

    def to_equal_area(geometry):
        return shapely_transform(transformer.transform, geometry)

    municipality_area = to_equal_area(municipality_geom).area / 1e6
    aoi_area = to_equal_area(validation_aoi_geom).area / 1e6
    intersection = municipality_geom.intersection(validation_aoi_geom)
    intersection_area = to_equal_area(intersection).area / 1e6

    return {
        "crs": "EPSG:4326",
        "area_projection": equal_area_crs,
        "municipality_area_km2": municipality_area,
        "validation_aoi_area_km2": aoi_area,
        "intersection_area_km2": intersection_area,
        "aoi_fraction_of_municipality": (aoi_area / municipality_area) if municipality_area else None,
        "aoi_fully_inside_municipality": bool(municipality_geom.covers(validation_aoi_geom)),
        "aoi_outside_km2": max(0.0, aoi_area - intersection_area),
        "geometry_type": municipality_geom.geom_type,
        "is_valid": bool(municipality_geom.is_valid),
    }


def classify_spatial(
    source_granularity: str,
    aoi_fraction_of_municipality: float | None,
) -> dict[str, Any]:
    """Classifica a compatibilidade espacial de uma fonte com a AOI.

    ``source_granularity`` ∈ {propriedade, municipio, regiao_imediata,
    regiao_intermediaria, uf, regiao, pais}.
    """
    if source_granularity in {"propriedade", "talhao"}:
        return {
            "class": CLASS_A,
            "justification": (
                "Fonte na escala da propriedade/talhão: mesma unidade espacial "
                "do indicador geoespacial."
            ),
        }
    if source_granularity == "municipio":
        return {
            "class": CLASS_B,
            "justification": (
                "Fonte municipal: contém a AOI, mas a estatística cobre todo o "
                f"município (AOI = {aoi_fraction_of_municipality * 100:.2f}% da "
                "área municipal). Serve como contexto municipal, não como "
                "validação do pixel da AOI."
            ),
        }
    if source_granularity in {"regiao_imediata", "regiao_intermediaria"}:
        return {
            "class": CLASS_C,
            "justification": (
                "Fonte em região administrativa acima do município: não permite "
                "atribuição espacial válida dentro da AOI."
            ),
        }
    if source_granularity in {"uf", "regiao", "pais"}:
        return {
            "class": CLASS_C,
            "justification": (
                "Fonte em escala estadual/nacional: contexto de escala maior, "
                "sem validade espacial para a AOI."
            ),
        }
    return {
        "class": CLASS_C,
        "justification": f"Granularidade não classificada: {source_granularity}",
    }


# ------------------------------------------------------------------ temporal


def s2_yearly_aggregation(csv_path: str = config.S2_SERIES_CSV) -> dict[str, Any]:
    """Agrega a série Sentinel-2 (V2.1) por ano civil, sem interpolar.

    Usa a coluna de média do NDVI já apurada por mês na V2.1; a cobertura
    média do ano entra como peso. Meses sem observação permanecem ausentes.
    """
    if not os.path.exists(csv_path):
        return {"status": "serie_ausente", "path": csv_path, "years": {}}

    by_year: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row.get("index") != config.S2_INDEX:
                continue
            year = str(row.get("month"))[:4]
            by_year[year].append(row)

    years: dict[str, Any] = {}
    for year, rows in sorted(by_year.items()):
        observed = [r for r in rows if r.get("status") == "observed" and r.get("mean")]
        missing = [r for r in rows if r.get("status") != "observed"]
        means = [float(r["mean"]) for r in observed]
        weights = [float(r.get("valid_fraction") or 0.0) for r in observed]
        total_weight = sum(weights)
        weighted = (
            sum(m * w for m, w in zip(means, weights)) / total_weight
            if total_weight > 0
            else None
        )
        years[year] = {
            "months_total": len(rows),
            "months_observed": len(observed),
            "months_missing": [str(r.get("month")) for r in missing],
            "ndvi_mean_of_monthly_means": sum(means) / len(means) if means else None,
            "ndvi_coverage_weighted_mean": weighted,
            "ndvi_min_monthly_mean": min(means) if means else None,
            "ndvi_max_monthly_mean": max(means) if means else None,
            "mean_valid_fraction": (
                sum(weights) / len(weights) if weights else None
            ),
            "source": os.path.basename(csv_path),
        }
    return {
        "status": "ok",
        "path": csv_path,
        "index": config.S2_INDEX,
        "profile": config.S2_PROFILE,
        "years": years,
        "note": (
            "Agregação por ano civil a partir de médias mensais já auditadas; "
            "meses sem observação não foram interpolados."
        ),
    }


def s2_season_aggregation(
    csv_path: str,
    windows: Sequence[tuple[str, str, str, str]],
) -> dict[str, Any]:
    """Agrega a série por janelas safrais **declaradas** (com referência).

    ``windows`` = [(rótulo, data_inicial, data_final, fonte_do_calendário)].
    Sem calendário validado, esta função não é chamada (e a ausência é
    registrada no relatório).
    """
    if not os.path.exists(csv_path):
        return {"status": "serie_ausente", "path": csv_path, "windows": {}}
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row.get("index") == config.S2_INDEX:
                rows.append(row)

    result: dict[str, Any] = {}
    for label, start, end, reference in windows:
        selected = [
            r
            for r in rows
            if start <= str(r.get("month"))[:7] <= end and r.get("status") == "observed"
        ]
        means = [float(r["mean"]) for r in selected if r.get("mean")]
        result[label] = {
            "window": {"start": start, "end": end},
            "calendar_reference": reference,
            "months_observed": len(selected),
            "ndvi_mean": sum(means) / len(means) if means else None,
            "monthly_items": [
                {"month": r.get("month"), "mean": float(r["mean"]) if r.get("mean") else None}
                for r in selected
            ],
        }
    return {"status": "ok", "windows": result}


def tmp_calendar_note() -> str:
    return (
        "Não foi adotado calendário fenológico: janelas de safra próprias não "
        "foram confirmadas em fonte oficial durante esta etapa. Agregações "
        "por safra ficam como BIBLIOTECA (função disponível, não executada com "
        "janelas inventadas)."
    )


# ------------------------------------------------------------- correspondência


def correspondence_table(
    records: Iterable[dict[str, Any]],
    s2: dict[str, Any],
) -> list[dict[str, Any]]:
    """Tabela de correspondência cultura × período × fonte × indicador.

    Uma linha por (cultura, ano/safra, fonte, granularidade), com a
    produtividade oficial **e** o que a série Sentinel-2 oferece no período
    correspondente. Períodos sem observação Sentinel-2 são marcados como
    ausentes — nunca preenchidos.
    """
    s2_years = s2.get("years", {}) if isinstance(s2, dict) else {}
    rows: list[dict[str, Any]] = []

    def _s2_info(year: str) -> dict[str, Any]:
        payload = s2_years.get(year) or {}
        return {
            "ndvi_available": bool(payload),
            "ndvi_mean": payload.get("ndvi_coverage_weighted_mean"),
            "ndvi_months_observed": payload.get("months_observed"),
            "ndvi_months_total": payload.get("months_total"),
            "ndvi_mean_coverage": payload.get("mean_valid_fraction"),
            "ndvi_missing_months": ",".join(payload.get("months_missing", []) or []),
        }

    grouped: dict[tuple, dict[str, Any]] = defaultdict(dict)
    for record in records:
        crop = record.get("crop_name_normalized")
        if not crop or record.get("match_class") in (None, "none"):
            continue
        scope = record.get("crop_scope")
        if scope in {"grupo_safra", "componente", "componente_safra"}:
            # componentes/tipos entram só na base bruta; a tabela usa o
            # agregado ("TOTAL") ou o produto simples, nunca ambos
            continue
        period = str(record.get("reference_year") or record.get("safra") or "")
        key = (
            record.get("institution"),
            record.get("crop_name_original"),
            period,
            record.get("geography_code"),
        )
        grouped[key].setdefault("meta", {
            "institution": record.get("institution"),
            "crop_original": record.get("crop_name_original"),
            "crop_normalized": crop,
            "match_class": record.get("match_class"),
            "geography_code": record.get("geography_code"),
            "geography_name": record.get("geography_name"),
            "geography_type": record.get("geography_type"),
            "period": period,
            "period_type": "ano_civil" if record.get("reference_year") else "safra",
            "nature": record.get("nature"),
        })
        grouped[key][record.get("variable_normalized")] = record.get("value_normalized")

    for key, payload in sorted(grouped.items()):
        meta = payload["meta"]
        period = meta["period"]
        if meta["period_type"] == "ano_civil":
            related_years = [period]
        elif "/" in period:
            start, end = period.split("/")
            related_years = [f"20{start}", f"20{end}"]
        else:
            related_years = []
        s2_parts = [_s2_info(year) for year in related_years]
        available = [part for part in s2_parts if part["ndvi_available"]]
        rows.append(
            {
                "crop": meta["crop_normalized"],
                "crop_original": meta["crop_original"],
                "match_class": meta["match_class"],
                "source": meta["institution"],
                "period": period,
                "period_type": meta["period_type"],
                "nature": meta["nature"],
                "geography_code": meta["geography_code"],
                "geography_name": meta["geography_name"],
                "geography_type": meta["geography_type"],
                "quantity_produced_t": payload.get("quantidade_produzida_t"),
                "area_harvested_ha": payload.get("area_colhida_ha"),
                "area_planted_ha": payload.get("area_plantada_ha"),
                "published_yield_kg_ha": payload.get("rendimento_medio_kg_ha"),
                "s2_years_related": ",".join(related_years),
                "ndvi_available": bool(available),
                "ndvi_mean": (
                    sum(part["ndvi_mean"] for part in available) / len(available)
                    if available
                    else None
                ),
                "ndvi_months_observed": (
                    sum(part["ndvi_months_observed"] for part in available)
                    if available
                    else None
                ),
                "ndvi_months_total": (
                    sum(part["ndvi_months_total"] for part in available)
                    if available
                    else None
                ),
                "ndvi_missing_months": "; ".join(
                    part["ndvi_missing_months"] for part in s2_parts
                ),
            }
        )
    return rows


def temporal_overlap(
    records: Iterable[dict[str, Any]],
    s2_years: Sequence[str],
) -> dict[str, Any]:
    """Anos/safras das observações oficiais × anos da série Sentinel-2."""
    ibge_years = sorted(
        {
            str(r.get("reference_year"))
            for r in records
            if r.get("institution") == "IBGE" and r.get("reference_year")
        }
    )
    conab_safras = sorted(
        {
            str(r.get("safra"))
            for r in records
            if r.get("institution") == "CONAB" and r.get("safra")
        }
    )
    conab_calendar_years = sorted(
        {
            year
            for safra in conab_safras
            if "/" in safra
            for year in (f"20{safra.split('/')[0]}", f"20{safra.split('/')[1]}")
        }
    )
    overlap_ibge = sorted(set(ibge_years) & set(s2_years))
    overlap_conab = sorted(set(conab_calendar_years) & set(s2_years))
    return {
        "s2_years": list(s2_years),
        "ibge_years_available": ibge_years,
        "ibge_years_overlapping_s2": overlap_ibge,
        "ibge_observations_in_overlap": len(overlap_ibge),
        "conab_safras_available": conab_safras,
        "conab_calendar_years_overlapping_s2": overlap_conab,
        "conab_safras_in_overlap": [
            safra
            for safra in conab_safras
            if "/" in safra
            and (f"20{safra.split('/')[0]}" in overlap_conab or f"20{safra.split('/')[1]}" in overlap_conab)
        ],
        "note": (
            "Ano civil (IBGE) e safra (CONAB) não são equivalentes: uma safra "
            "atravessa dois anos civis e o Sentinel-2 é mensal."
        ),
    }
