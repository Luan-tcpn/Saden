"""Protocolo de janelas agrícolas (V2.5) — ZARC e pareamento com a PAM.

Este módulo fixa, **antes** de qualquer análise de correlação:

* a conversão de decêndios em datas (regra oficial do MAPA: três decêndios por
  mês — dias 1–10, 11–20 e 21–último dia);
* as janelas de plantio aplicáveis a Sorriso por cultura e safra, preservando
  as alternativas de solo, ciclo e nível de risco (nenhuma é arbitrada);
* a correspondência entre safra e ano de referência da PAM, com a regra
  principal, a alternativa e o grau de confiança;
* a separação obrigatória entre **milho principal** e **milho 2ª safra**, que
  não podem ser comparados com o rendimento municipal total como se
  descrevessem a mesma produção.

Nada aqui observa plantio real: o ZARC é recomendação de risco.
"""

from __future__ import annotations

import calendar
import csv
import os
from collections import defaultdict
from typing import Any, Iterable, Sequence

# Cultura do SADEN → rótulos do ZARC (nomenclatura real do conjunto).
CROP_LABELS: dict[str, list[str]] = {
    "soja": ["Soja"],
    "milho": ["Milho", "Milho 1ª Safra"],
    "milho_2": ["Milho 2ª Safra"],
}

# Nível de risco do ZARC (código → descrição). As janelas são recalculadas por
# nível: o resultado muda se a escolha de risco mudar.
RISK_LEVELS = {10: "muito_baixo", 20: "baixo", 30: "medio", 40: "alto"}

# Nível de risco adotado na análise principal e justification agronômica.
PRIMARY_RISK = 20
PRIMARY_RISK_JUSTIFICATION = (
    "Janela recomendada do ZARC com risco baixo (20): é a faixa em que a "
    "recomendação oficial éconsidered aceitável para a maioria das condições "
    "de solo/ciclomanage — alternativa de risco (10/30/40) é reportada como "
    "sensibilidade, não descartada."
)


def decend_month(decend: int) -> int:
    """Mês do decêndio (3 por mês)."""
    if not 1 <= decend <= 36:
        raise ValueError(f"decendio fora de 1..36: {decend}")
    return (decend - 1) // 3 + 1


def decend_segment(decend: int) -> int:
    """Segmento do decêndio no mês (1: 1–10, 2: 11–20, 3: 21–fim)."""
    if not 1 <= decend <= 36:
        raise ValueError(f"decendio fora de 1..36: {decend}")
    return (decend - 1) % 3 + 1


def decend_to_dates(year: int, decend: int) -> tuple[str, str]:
    """Início e fim de um decêndio (regra oficial MAPA)."""
    month = decend_month(decend)
    segment = decend_segment(decend)
    last_day = calendar.monthrange(year, month)[1]
    if segment == 1:
        start_day, end_day = 1, 10
    elif segment == 2:
        start_day, end_day = 11, 20
    else:
        start_day, end_day = 21, last_day
    return (
        f"{year:04d}-{month:02d}-{start_day:02d}",
        f"{year:04d}-{month:02d}-{end_day:02d}",
    )


def decend_months(decends: Iterable[int]) -> list[int]:
    """Meses cobertos por um conjunto de decêndios (ordenados)."""
    return sorted({decend_month(d) for d in decends})


def read_zarc_rows(path: str) -> list[dict[str, Any]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _risk_decends(text: str) -> dict[int, list[int]]:
    """Extrai ``decend: risco`` do campo ``decendios_com_risco``."""
    out: dict[int, list[int]] = defaultdict(list)
    for chunk in str(text or "").split(";"):
        if ":" not in chunk:
            continue
        decend_text, risk_text = chunk.split(":", 1)
        try:
            decend = int(decend_text)
            risk = int(risk_text)
        except ValueError:
            continue
        out[risk].append(decend)
    return out


def build_windows(
    rows: Sequence[dict[str, Any]],
    crop: str,
    risk: int = PRIMARY_RISK,
) -> list[dict[str, Any]]:
    """Janelas de plantio por safra para uma cultura e um nível de risco.

    Cada registro preserva solo, ciclo, portaria e a combinação completa; as
    janelas **não** são reduzidas a uma única linha arbitrária.
    """
    labels = CROP_LABELS.get(crop, [])
    grouped: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        if str(row.get("cultura")) not in labels:
            continue
        risks = _risk_decends(row.get("decendios_com_risco", ""))
        decends = risks.get(risk)
        if not decends:
            continue
        key = (
            row.get("safra"),
            row.get("cod_ciclo"),
            row.get("cod_solo"),
            row.get("portaria"),
        )
        entry = grouped.setdefault(
            key,
            {
                "safra": row.get("safra"),
                "safra_ini": row.get("safra_ini"),
                "safra_fin": row.get("safra_fin"),
                "cultura": row.get("cultura"),
                "crop": crop,
                "cod_ciclo": row.get("cod_ciclo"),
                "cod_solo": row.get("cod_solo"),
                "cod_clima": row.get("cod_clima"),
                "portaria": row.get("portaria"),
                "risk": risk,
                "decends": sorted(decends),
                "months": decend_months(decends),
                "combinations": 0,
            },
        )
        entry["combinations"] += 1
    windows = list(grouped.values())
    for window in windows:
        year = int(window["safra_ini"])
        start, _ = decend_to_dates(year, window["decends"][0])
        _, end = decend_to_dates(year, window["decends"][-1])
        window["start_date"] = start
        window["end_date"] = end
    return sorted(windows, key=lambda w: (w["safra"], str(w["cod_ciclo"]), str(w["cod_solo"])))


def pam_year_candidates(safra: str, crop: str) -> dict[str, Any]:
    """Anos de referência PAM candidatos para uma safra.

    Regra (revisada na V2.5): a safra ``Y/Y+1`` tem plantio no ano ``Y`` e
    colheita **no ano civil ``Y+1``** (soja e milho 1ª: plantio set–dez,
    colheita jan–fev do ano seguinte; milho 2ª: plantio jan–fev, colheita
    mai–jun do mesmo ano ``Y+1``). O ano de plantio ``Y`` é preservado como
    alternativa de menor confiança.

    Para o **milho**, a PAM publica o **total do ano** (1ª + 2ª safras): a
    correspondência com a janela de uma safra específica é, portanto,
    ambígua — e a análise não pode tratar a safra como a mesma produção.
    """
    try:
        year = int(str(safra).split("/")[0])
    except (ValueError, IndexError):
        return {"primary": None, "alternative": None, "confidence": "none"}
    if crop == "milho_2":
        # plantio em jan-fev de Y+1, colheita em mai-jun de Y+1
        return {
            "primary": year + 1,
            "alternative": year,
            "confidence": "media",
            "ambiguity": "PAM publica o total anual de milho (1ª + 2ª safras)",
        }
    return {
        "primary": year + 1,
        "alternative": year,
        "confidence": "media_alta" if crop == "soja" else "media",
        "ambiguity": None,
    }


def window_months_by_year(
    windows: Sequence[dict[str, Any]],
    crop: str,
) -> dict[str, list[int]]:
    """Meses da janelarecommended, por ano-safra (ano do plantio)."""
    out: dict[str, list[int]] = {}
    for window in windows:
        months = list(window["months"])
        if crop == "milho_2":
            # a 2ª safra é plantada em jan-fev do ano seguinte
            year = int(window["safra_ini"]) + 1
            out[f"{year}"] = sorted(set(out.get(f"{year}", [])) | set(months))
        else:
            year = int(window["safra_ini"])
            out[f"{year}"] = sorted(set(out.get(f"{year}", [])) | set(months))
    return out


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
