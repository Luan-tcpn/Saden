"""Crosswalk de culturas: SADEN ↔ IBGE/SIDRA ↔ CONAB.

Associações **não** são inferidas por semelhança de nome: cada vínculo é
declarado aqui, com a classe de correspondência e a ressalva técnica.

Classes de correspondência:

* ``exact`` — mesma definição de produto e mesma unidade de medida;
* ``equivalent_with_caveats`` — mesmo produto, mas com diferença de
  definition/unidade que exige cautela documentada;
* ``partial`` — apenas parte do produto coincide (ex.: caroço × pluma);
* ``none`` — sem correspondência utilizável.
"""

from __future__ import annotations

import re
from typing import Any

MATCH_EXACT = "exact"
MATCH_EQUIVALENT = "equivalent_with_caveats"
MATCH_PARTIAL = "partial"
MATCH_NONE = "none"

# --------------------------------------------------------------- SADEN ↔ IBGE
# Códigos confirmados na API SIDRA (tabela 5457, classificação 782) para o
# município 5107925 em 2026-11-11.
IBGE_TO_SADEN: dict[str, dict[str, Any]] = {
    "40124": {
        "saden_key": "soja",
        "saden_name": "Soja",
        "ibge_name": "Soja (em grão)",
        "match": MATCH_EXACT,
        "note": (
            "Soja em grão: mesma commodity do futuro CBOT (ZS=F) e mesma base "
            "produtiva (grão)."
        ),
    },
    "40122": {
        "saden_key": "milho",
        "saden_name": "Milho",
        "ibge_name": "Milho (em grão)",
        "match": MATCH_EXACT,
        "note": "Milho em grão: mesma commodity do futuro CBOT (ZC=F).",
    },
    "40099": {
        "saden_key": "algodao",
        "saden_name": "Algodão",
        "ibge_name": "Algodão herbáceo (em caroço)",
        "match": MATCH_PARTIAL,
        "note": (
            "O SADEN referencia o Algodão (futuro ICE CT=F) em pluma/l磅; a PAM "
            "divulga para Sorriso o algodão **herbáceo em caroço**. São "
            "produtos diferentes (o caroço é a semente; o pluma é a fibra). "
            "Rendimento não é comparável sem conversión documentada — não "
            "convertida nesta etapa."
        ),
    },
    "40140": {
        "saden_key": "cafe",
        "saden_name": "Café arábica",
        "ibge_name": "Café (em grão) Arábica",
        "match": MATCH_EQUIVALENT,
        "note": (
            "Café arábica em grão (não torrado): corresponde ao futuro ICE "
            "KC=F, mas a base física (grão seco não torrado) difere da "
            "referência de mercado (grão torrado). Em Sorriso a produção é "
            "zero (não há lavoura de café no município)."
        ),
    },
    "40127": {
        "saden_key": "trigo",
        "saden_name": "Trigo",
        "ibge_name": "Trigo (em grão)",
        "match": MATCH_EXACT,
        "note": "Trigo em grão: mesma commodity do futuro CBOT (ZW=F).",
    },
}

# --------------------------------------------------------------- SADEN ↔ CONAB
# Rótulos exatamente como aparecem nas planilhas do Boletim de Safras (UF MT).
CONAB_LABELS: dict[str, dict[str, Any]] = {
    "soja": {
        "labels": ["SOJA"],
        "match": MATCH_EXACT,
        "note": "Rótulo 'SOJA' na aba da UF; mesma commodity.",
    },
    "milho": {
        "labels": ["MILHO"],
        "match": MATCH_EXACT,
        "note": "Rótulo 'MILHO' (1ª e 2ª safra somadas) na aba da UF.",
    },
    "algodao": {
        "labels": ["ALGODÃO - CAROÇO (1)", "ALGODÃO - PLUMA", "ALGODÃO - CAROÇO"],
        "match": MATCH_PARTIAL,
        "note": (
            "A CONAB separa Caroço e Pluma; o SADEN referencia o pluma "
            "(ICE CT=F, R$/lp). Somente 'ALGODÃO - PLUMA' é comparável ao "
            "referência de mercado; o caroço não é."
        ),
    },
    "cafe": {
        "labels": ["CAFÉ ARÁBICA", "CAFÉ ARABICA", "CAFÉ"],
        "match": MATCH_EQUIVALENT,
        "note": (
            "Boletim de café em '.xls' legado; base física (grão não torrado) "
            "difere da referência de mercado."
        ),
    },
    "trigo": {
        "labels": ["TRIGO"],
        "match": MATCH_EXACT,
        "note": "Rótulo 'TRIGO' na aba da UF.",
    },
}


def classify_ibge_product(product_code: str, product_name: str) -> dict[str, Any]:
    """Classifica um produto da PAM (por código oficial, com nome de apoio)."""
    entry = IBGE_TO_SADEN.get(str(product_code))
    if entry is None:
        return {
            "saden_key": None,
            "saden_name": None,
            "match": MATCH_NONE,
            "reason": "produto PAM fora do escopo das commodities do SADEN",
            "ibge_code": str(product_code),
            "ibge_name": product_name,
        }
    return {
        "saden_key": entry["saden_key"],
        "saden_name": entry["saden_name"],
        "match": entry["match"],
        "reason": entry["note"],
        "ibge_code": str(product_code),
        "ibge_name": product_name,
    }


def classify_conab_product(label: str) -> dict[str, Any]:
    """Classifica um rótulo de produto da planilha da CONAB."""
    normalized = re.sub(r"\s+", " ", str(label or "")).strip().upper()
    for key, entry in CONAB_LABELS.items():
        for candidate in entry["labels"]:
            if normalized == candidate.upper() or normalized.startswith(candidate.upper()):
                return {
                    "saden_key": key,
                    "saden_name": next(
                        c["name"] for c in _saden_catalog() if c["key"] == key
                    ),
                    "match": entry["match"],
                    "reason": entry["note"],
                    "conab_label": label,
                }
    return {
        "saden_key": None,
        "saden_name": None,
        "match": MATCH_NONE,
        "reason": "rótulo da CONAB sem vínculo declarado com as commodities do SADEN",
        "conab_label": label,
    }


def _saden_catalog() -> list[dict[str, Any]]:
    from . import config

    return config.SADEN_COMMODITIES


def crosswalk_table() -> list[dict[str, Any]]:
    """Tabela de correspondência completa (SADEN × IBGE × CONAB)."""
    rows: list[dict[str, Any]] = []
    for commodity in _saden_catalog():
        key = commodity["key"]
        ibge = next(
            (
                entry
                for entry in IBGE_TO_SADEN.values()
                if entry["saden_key"] == key
            ),
            None,
        )
        conab = CONAB_LABELS.get(key)
        rows.append(
            {
                "saden_key": key,
                "saden_name": commodity["name"],
                "yahoo_symbol": commodity["yahoo_symbol"],
                "ibge_code": next(
                    (
                        code
                        for code, entry in IBGE_TO_SADEN.items()
                        if entry["saden_key"] == key
                    ),
                    None,
                ),
                "ibge_name": ibge["ibge_name"] if ibge else None,
                "ibge_match": ibge["match"] if ibge else MATCH_NONE,
                "conab_labels": conab["labels"] if conab else [],
                "conab_match": conab["match"] if conab else MATCH_NONE,
                "notes": "; ".join(
                    filter(
                        None,
                        [ibge["note"] if ibge else None, conab["note"] if conab else None],
                    )
                ),
            }
        )
    return rows
