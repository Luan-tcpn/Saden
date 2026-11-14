"""Contrato de fonte climática — guarda única, usada por todo consumidor.

Motivo (D123/D128): ``climate_daily.csv`` contém **duas fontes sob a mesma
chave** (município, dia) — NASA-POWER (reanálise) e INMET (estação). O painel
base também contém linhas de ambas. Selecionar por ``status`` sem declarar a
fonte produz amostra misturada; a ordenação do arquivo não é contrato.

Este módulo torna a regra explícita e testável:

* ``canonical_source()`` — a fonte declarada para o painel;
* ``is_canonical_row(row)`` — predicado único;
* ``select_canonical(rows)`` — filtro com contagem do que foi descartado,
  separando "outra fonte" de "status inválido";
* ``assert_source_declared(...)`` — falha alto se um consumidor pedir uma
  amostra sem declarar a fonte.

Nada aqui altera dados: é a definição executável do contrato.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Sequence

CANONICAL_CLIMATE_SOURCE = "NASA-POWER"
AUXILIARY_CLIMATE_SOURCE = "INMET"
CANONICAL_STATUS = "paired_usable"


class ClimateContractError(ValueError):
    """Violação do contrato de fonte climática."""


def canonical_source() -> str:
    return CANONICAL_CLIMATE_SOURCE


def row_source(row: dict[str, Any]) -> str:
    """Fonte da linha, aceitando os dois nomes de campo já usados no projeto."""
    for field in ("climate_source", "source"):
        value = row.get(field)
        if value not in (None, ""):
            return str(value)
    return ""


def row_status(row: dict[str, Any]) -> str:
    return str(row.get("status") or "")


def is_canonical_row(
    row: dict[str, Any],
    required_source: str = CANONICAL_CLIMATE_SOURCE,
    required_status: str = CANONICAL_STATUS,
) -> bool:
    """Predicado único: a linha é analítica **e** da fonte declarada."""
    return row_status(row) == required_status and row_source(row) == required_source


def assert_source_declared(required_source: str | None) -> str:
    """Falha alto quando o consumidor não declara a fonte exigida."""
    if not required_source:
        raise ClimateContractError(
            "consumidor de clima sem fonte declarada: selecionar por status sem "
            "fonte mistura NASA-POWER e INMET"
        )
    return required_source


def select_canonical(
    rows: Iterable[dict[str, Any]],
    required_source: str | None = CANONICAL_CLIMATE_SOURCE,
    required_status: str = CANONICAL_STATUS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Filtra pelo contrato e devolve a contagem do descarte por motivo."""
    source = assert_source_declared(required_source)
    kept: list[dict[str, Any]] = []
    discarded = Counter()
    sources_seen = Counter()
    for row in rows:
        sources_seen[row_source(row) or "<vazio>"] += 1
        if row_status(row) != required_status:
            discarded["status"] += 1
            continue
        if row_source(row) != source:
            discarded[f"fonte:{row_source(row) or '<vazio>'}"] += 1
            continue
        kept.append(row)
    return kept, {
        "required_source": source,
        "required_status": required_status,
        "kept": len(kept),
        "discarded": dict(discarded),
        "sources_seen": dict(sources_seen),
    }


def audit_mixture(rows: Sequence[dict[str, Any]], required_source: str = CANONICAL_CLIMATE_SOURCE) -> dict[str, Any]:
    """Detecta mistura silenciosa: linhas 'utilizáveis' de fonte não canônica."""
    by_source: Counter = Counter()
    usable_offsource: list[dict[str, Any]] = []
    for row in rows:
        source = row_source(row)
        by_source[f"{row_status(row)}|{source or '<vazio>'}"] += 1
        if row_status(row) == CANONICAL_STATUS and source != required_source:
            usable_offsource.append(row)
    return {
        "required_source": required_source,
        "by_status_source": dict(sorted(by_source.items())),
        "usable_offsource_count": len(usable_offsource),
        "usable_offsource_examples": [
            {
                "ibge_code": row.get("ibge_code"),
                "crop": row.get("crop"),
                "safra": row.get("safra"),
                "climate_source": row_source(row),
            }
            for row in usable_offsource[:10]
        ],
        "mixed_sample": len(usable_offsource) > 0,
    }
