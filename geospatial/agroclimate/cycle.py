"""Grupos de ciclo do ZARC e teste formal de interação (V2.9, D94).

O painel carrega ``zarc_cycle`` e ``zarc_solo``, que são os campos
``Cod_Ciclo`` e ``Cod_Solo`` da Tábua de Risco do ZARC. A correspondência
oficial foi obtida no dicionário de dados do MAPA (ver ``SOURCE``):

``Cod_Ciclo``: 13 Perene · 19 Semiperene · **20 Grupo I · 21 Grupo II ·
22 Grupo III** · 24 Grupo IV · 25 Grupo V · 26 Grupo VI.

``Cod_Solo``: 1 Arenoso · 2 Textura Média · 3 Argiloso · 11–16 AD1–AD6.

**Grupo de ciclo não é cultivar.** O dicionário não rotula os grupos como
precoce/médio/tardio e esse rótulo não é inferido aqui.

Este módulo também implementa o teste de interação usado para verificar se a
inclinação de uma variável agroclimática **difere** entre dois grupos — em
vez de comparar dois coeficientes estimados separadamente, o que confunde
diferença de inclinação com diferença de amostra e de transformação.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from . import robust, spatial_inference

COD_CICLO: dict[str, str] = {
    "13": "Perene",
    "19": "Semiperene",
    "20": "Grupo I",
    "21": "Grupo II",
    "22": "Grupo III",
    "24": "Grupo IV",
    "25": "Grupo V",
    "26": "Grupo VI",
}

COD_SOLO: dict[str, str] = {
    "1": "Arenoso",
    "2": "Textura Média",
    "3": "Argiloso",
    "11": "AD1",
    "12": "AD2",
    "13": "AD3",
    "14": "AD4",
    "15": "AD5",
    "16": "AD6",
}

SOURCE = {
    "title": "Dicionário de Dados - Tábua de Risco (ZARC)",
    "institution": "Ministério da Agricultura e Pecuária (MAPA) — CGRA/DEGER/SPA",
    "document": "dicionario-de-dados-tabua-de-risco-2026.pdf",
    "url": (
        "https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-"
        "dc8ff323b96f/resource/bebb0ebb-bc75-460c-b900-a7a1ebd87bee/download/"
        "dicionario-de-dados-tabua-de-risco-2026.pdf"
    ),
    "accessed_at": "2026-11-14",
    "license": "CC-BY",
}


def class_label(code: Any) -> str:
    """Rótulo oficial do grupo de ciclo (ou ``"nao documentado"``)."""
    return COD_CICLO.get(str(code), "nao documentado")


def soil_label(code: Any) -> str:
    return COD_SOLO.get(str(code), "nao documentado")


def interaction_test(
    rows: Sequence[dict[str, Any]],
    variable: str,
    class_a: str,
    class_b: str,
    target: str = "yield_kg_ha",
    block_key: str = "spatial_block",
    municipality_key: str = "ibge_code",
    year_key: str = "year",
    cycle_key: str = "zarc_cycle",
    min_rows: int = 250,
) -> dict[str, Any]:
    """Testa se a inclinação de ``variable`` difere entre dois grupos.

    Modelo, após transformação *within* por município e ano::

        y_w = b1 · x_w + b2 · (x · I[grupo = class_b])_w + e

    ``b2`` é a **diferença de inclinação** entre os grupos, com o seu próprio
    erro-padrão agrupado por bloco (CR1) e ``t`` com ``G − 1`` graus de
    liberdade. Comparar dois coeficientes estimados separadamente não testa
    isso: cada estimativa usa a sua própria amostra e a sua própria
    transformação, e "um significativo, outro não" não é evidência de
    diferença.
    """
    subset = [
        row
        for row in rows
        if row.get(variable) is not None
        and str(row.get(cycle_key)) in (class_a, class_b)
        and row.get(target) is not None
    ]
    if len(subset) < min_rows:
        return {"status": "insufficient_rows", "n": len(subset)}
    municipalities = [str(row[municipality_key]) for row in subset]
    years = [row[year_key] for row in subset]
    x = np.array([float(row[variable]) for row in subset], dtype="float64")
    indicator = np.array(
        [1.0 if str(row[cycle_key]) == class_b else 0.0 for row in subset],
        dtype="float64",
    )
    y = np.array([float(row[target]) for row in subset], dtype="float64")
    x_within = spatial_inference.within_transform(x, municipalities, years)
    y_within = spatial_inference.within_transform(y, municipalities, years)
    interaction = spatial_inference.within_transform(
        x * indicator, municipalities, years
    )
    design = np.column_stack([x_within, interaction])
    if float(np.std(design, axis=0).max()) == 0.0:
        return {"status": "degenerate_design", "n": len(subset)}
    beta, *_ = np.linalg.lstsq(design, y_within, rcond=None)
    residuals = y_within - design @ beta
    blocks = [str(row.get(block_key) or "") for row in subset]
    vcv, info = robust.cluster_vcov(design, residuals, blocks, correction=robust.CR1)
    degrees = max(info["n_clusters"] - 1, 1)
    result: dict[str, Any] = {
        "status": "ok",
        "n": len(subset),
        "n_clusters": info["n_clusters"],
        "reference_class": str(class_a),
        "reference_label": class_label(class_a),
        "contrast_class": str(class_b),
        "contrast_label": class_label(class_b),
    }
    for index, name in enumerate(("slope_reference", "slope_difference")):
        coefficient = float(beta[index])
        std_error = float(np.sqrt(max(vcv[index, index], 0.0)))
        degenerate = robust.degenerate_std_error(coefficient, std_error)
        t_stat = None if degenerate else coefficient / std_error
        result[name] = {
            "coefficient": coefficient,
            "std_error": std_error,
            "t_statistic": t_stat,
            "p_value": robust.t_sf(t_stat, degrees) if t_stat is not None else None,
            "ci95": [
                coefficient - robust.t_critical(0.05, degrees) * std_error,
                coefficient + robust.t_critical(0.05, degrees) * std_error,
            ],
            "df": degrees,
        }
    return result
