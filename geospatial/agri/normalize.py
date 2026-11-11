"""Base normalizada de observações de produtividade agrícola.

Esquema único para as duas instituições (IBGE/SIDRA e CONAB), preservando
sempre o valor e a unidade **originais** ao lado dos normalizados.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from . import config, crosswalk

NORMALIZED_FIELDS = [
    "institution",
    "dataset_name",
    "dataset_id",
    "source_url",
    "acquisition_method",
    "acquired_at",
    "geography_code",
    "geography_name",
    "geography_type",
    "reference_year",
    "safra",
    "crop_code",
    "crop_name_original",
    "crop_name_normalized",
    "crop_scope",
    "match_class",
    "variable_original",
    "variable_normalized",
    "value_original",
    "value_normalized",
    "unit_original",
    "unit_normalized",
    "nature",
    "observation_status",
    "publication_date",
    "revision",
    "notes",
]


def classify_scope(product_name: str) -> str:
    """Escopo do produto: total, componente (safra) ou produto simples.

    As planilhas trazem linhas agregadas ("MILHO TOTAL") **e** suas
    componentes ("Milho 1ª Safra"). Somar ambos conta a mesma produção duas
    vezes; por isso o escopo é gravado em cada registro.
    """
    text = str(product_name or "").strip().upper()
    if text.endswith("TOTAL"):
        return "total"
    if "ª SAFRA" in text or "1 SAFRA" in text or "2 SAFRA" in text or "3 SAFRA" in text:
        return "grupo_safra"
    return "produto"

# Naturezas possíveis (o mission exige separar observados de estimados).
NATURE_OBSERVED = "observed"
NATURE_ESTIMATED = "estimated"
NATURE_PRELIMINARY = "preliminary"

# Conversões de unidade CONAB → unidades canônicas.
CONAB_UNIT_FACTORS = {
    "area_mil_ha": ("ha", 1000.0),
    "producao_mil_t": ("t", 1000.0),
    "produtividade_kg_ha": ("kg/ha", 1.0),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_row() -> dict[str, Any]:
    return {field: None for field in NORMALIZED_FIELDS}


def build_ibge_records(
    sidra_result: dict[str, Any],
    source_url: str,
    acquisition_method: str = "sidra_api",
) -> list[dict[str, Any]]:
    """Converte a resposta da SIDRA em observações normalizadas."""
    rows: list[dict[str, Any]] = []
    acquired_at = sidra_result.get("acquired_at") or _now()
    for record in sidra_result.get("records", []):
        variable_code = str(record.get("variable_code") or "")
        variable = config.PAM_VARIABLES.get(variable_code)
        if variable is None:
            continue
        product_code = str(record.get("product_code") or "")
        classification = crosswalk.classify_ibge_product(
            product_code, record.get("product_name") or ""
        )
        row = _empty_row()
        row.update(
            {
                "institution": "IBGE",
                "dataset_name": config.PAM_RESEARCH,
                "dataset_id": f"SIDRA:{config.PAM_TABLE}",
                "source_url": source_url,
                "acquisition_method": acquisition_method,
                "acquired_at": acquired_at,
                "geography_code": record.get("locality_code"),
                "geography_name": record.get("locality_name"),
                "geography_type": "municipio",
                "reference_year": record.get("period_code"),
                "safra": None,
                "crop_code": product_code,
                "crop_name_original": record.get("product_name"),
                "crop_name_normalized": classification.get("saden_name"),
                "crop_scope": classify_scope(record.get("product_name") or ""),
                "match_class": classification.get("match"),
                "variable_original": record.get("variable_name"),
                "variable_normalized": variable["normalized"],
                "value_original": record.get("value_raw"),
                "value_normalized": record.get("value"),
                "unit_original": record.get("unit_name") or variable["unit"],
                "unit_normalized": variable["normalized_unit"],
                "nature": NATURE_OBSERVED,
                "observation_status": record.get("value_status"),
                "publication_date": None,
                "revision": "PAM (coleta municipal)",
                "notes": classification.get("reason"),
            }
        )
        rows.append(row)
    return rows


def build_conab_records(
    parsed: Sequence[dict[str, Any]],
    file_meta: dict[str, Any],
    source_url: str,
    dataset_name: str = "Boletim de Safras (CONAB)",
) -> list[dict[str, Any]]:
    """Converte registros da planilha CONAB em observações normalizadas."""
    rows: list[dict[str, Any]] = []
    acquired_at = file_meta.get("acquired_at") or _now()
    for record in parsed:
        classification = crosswalk.classify_conab_product(record.get("product_original", ""))
        uf = str(record.get("uf") or "")
        uf_code = config.UF_CODES.get(uf, uf)
        uf_name = config.UF_NAMES.get(uf, uf)
        period_kind = record.get("period_kind") or "safra"
        period_label = record.get("period_label")
        if period_kind == "ano_civil":
            reference_year, safra = period_label, None
        else:
            reference_year, safra = None, period_label
        for variable, unit_key, unit_label in (
            ("area_plantada_ha", "area_mil_ha", "mil ha"),
            ("rendimento_medio_kg_ha", "produtividade_kg_ha", "kg/ha"),
            ("quantidade_produzida_t", "producao_mil_t", "mil t"),
        ):
            raw_value = record.get(unit_key)
            if raw_value is None:
                continue
            _, factor = CONAB_UNIT_FACTORS[unit_key]
            normalized_unit = CONAB_UNIT_FACTORS[unit_key][0]
            row = _empty_row()
            row.update(
                {
                    "institution": "CONAB",
                    "dataset_name": dataset_name,
                    "dataset_id": file_meta.get("dataset_id") or file_meta.get("name"),
                    "source_url": source_url,
                    "acquisition_method": "http_download_xlsx",
                    "acquired_at": acquired_at,
                    "geography_code": uf_code,
                    "geography_name": f"{uf} — {uf_name}" if uf_name != uf else uf,
                    "geography_type": "uf",
                    "reference_year": reference_year,
                    "safra": safra,
                    "crop_code": None,
                    "crop_name_original": record.get("product_original"),
                    "crop_name_normalized": classification.get("saden_name"),
                    "crop_scope": record.get("product_scope")
                    or classify_scope(record.get("product_original") or ""),
                    "match_class": classification.get("match"),
                    "variable_original": f"{unit_label}",
                    "variable_normalized": variable,
                    "value_original": raw_value,
                    "value_normalized": raw_value * factor,
                    "unit_original": unit_label,
                    "unit_normalized": normalized_unit,
                    "nature": NATURE_ESTIMATED,
                    "observation_status": "consolidated_bulletin",
                    "publication_date": file_meta.get("reference_period"),
                    "revision": file_meta.get("revision") or file_meta.get("name"),
                    "notes": classification.get("reason"),
                }
            )
            rows.append(row)
    return rows


def write_csv(records: Iterable[dict[str, Any]], path: str) -> str:
    """Grava a base normalizada em CSV (UTF-8 BOM, abre no Excel)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=NORMALIZED_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field) for field in NORMALIZED_FIELDS})
    return path


def write_json(records: Iterable[dict[str, Any]], path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(list(records), handle, ensure_ascii=False, indent=2)
    return path


def read_csv(path: str) -> list[dict[str, Any]]:
    """Lê a base normalizada de volta (usado em testes de reprodutibilidade)."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def computed_yield_t_ha(quantity_t: float | None, area_ha: float | None) -> float | None:
    """Rendimento calculado (t/ha) a partir de quantidade e área colhida."""
    if quantity_t is None or area_ha is None or area_ha <= 0:
        return None
    return quantity_t / area_ha


def published_yield_kg_ha_to_t_ha(value: float | None) -> float | None:
    """Converte rendimento publicado (kg/ha) para t/ha."""
    if value is None:
        return None
    return value / 1000.0
