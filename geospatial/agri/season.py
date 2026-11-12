"""Protocolo de janelas agrícolas (V2.5) — ZARC e pareamento com a PAM.

Este módulo fixa, **antes** de qualquer análise de correlação:

* a conversão de decêndios em datas (regra oficial do MAPA: três decêndios por
  mês — dias 1–10, 11–20 e 21–último dia);
* a **âncora de ano** de cada decêndio dentro da safra (correção V2.5: os
  decêndios de janeiro–abril pertencem ao **segundo** ano da safra);
* as janelas de plantio aplicáveis a Sorriso por cultura e safra, preservando
  as alternativas de solo, ciclo e nível de risco (nenhuma é arbitrada);
* a correspondência entre safra e ano de referência da PAM, com a regra
  principal, a alternativa e o grau de confiança;
* a separação obrigatória entre **milho principal** e **milho 2ª safra**, que
  não podem ser comparados com o rendimento municipal total como se
  descrevessem a mesma produção.

Nada aqui observa plantio real: o ZARC é recomendação de risco.

Correções aplicadas na V2.5 em relação à ingestão da V2.4
(`agri/zarc.py` → `zarc_planting_windows.csv`):

1. O campo ``decendios_com_risco`` guarda o risco por **rótulo textual**
   (``muito_baixo``/``baixo``/``medio``/``alto``), e não por código numérico.
2. A âncora de ano dos decêndios 1–12 é o **segundo** ano da safra
   (``safra_fin``), e a dos decêndios 13–36 é o primeiro (``safra_ini``).
   A verificação é objetiva: a data da portaria que publica a recomendação
   deve **preceder** o início da janela recomendada — com a regra antiga
   (todos os decêndios em ``safra_ini``) há 165 violações nas culturas-piloto
   e com a regra nova há **zero**.
"""

from __future__ import annotations

import calendar
import csv
import os
from collections import defaultdict
from typing import Any, Iterable, Sequence

# Cultura do SADEN → rótulos do ZARC (nomenclatura real do conjunto).
# "Milho" é o rótulo das safras até 2023/24; "Milho 1ª Safra" o das
# seguintes. As variantes "consorciado com Braquiária" são outro sistema de
# manejo e ficam de fora (D49 — culturas-piloto).
CROP_LABELS: dict[str, list[str]] = {
    "soja": ["Soja"],
    "milho": ["Milho", "Milho 1ª Safra"],
    "milho_2": ["Milho 2ª Safra"],
}

# Nível de risco do ZARC: código → rótulo (o CSV normalizado usa rótulos).
RISK_LEVELS: dict[int, str] = {
    10: "muito_baixo",
    20: "baixo",
    30: "medio",
    40: "alto",
}
RISK_BY_LABEL: dict[str, int] = {v: k for k, v in RISK_LEVELS.items()}
RISK_BY_LABEL.update({"muito baixo": 10, "médio": 30, "medio": 30})

# Risco máximo da **janela recomendada** na análise principal.
# A janela oficial do ZARC é a dos decêndios de risco *muito baixo ou baixo*
# (≤ 20%); este é o critério oficial do MAPA, não uma escolha guiada pela
# correlação. Os riscos ≤ 30% e ≤ 40% são cenários de sensibilidade.
PRIMARY_MAX_RISK = 20
PRIMARY_MAX_RISK_JUSTIFICATION = (
    "Janela recomendada oficial do ZARC: decêndios com risco muito baixo ou "
    "baixo (≤ 20%). É a faixa em que a recomendação do MAPA é considerada "
    "aceitável — não a faixa de maior correlação com o rendimento. As "
    "extensões ≤ 30% e ≤ 40% são cenários de sensibilidade."
)
SENSITIVITY_MAX_RISKS: tuple[int, ...] = (30, 40)

# Âncora de ano dos decêndios: 1–12 → segundo ano da safra; 13–36 → primeiro.
DECEND_YEAR_SPLIT = 12


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


def decend_year(decend: int, safra_ini: int, safra_fin: int) -> int:
    """Ano civil de um decêndio dentro da safra (correção V2.5).

    Os decêndios 1–12 (janeiro–abril) pertencem ao **segundo** ano da safra e
    os decêndios 13–36 (maio–dezembro) ao **primeiro**. A regra é verificável:
    a portaria que publica a recomendação é anterior ao início da janela
    recomendada — o que só vale com esta âncora.
    """
    if not 1 <= decend <= 36:
        raise ValueError(f"decendio fora de 1..36: {decend}")
    return safra_fin if decend <= DECEND_YEAR_SPLIT else safra_ini


def decend_months(decends: Iterable[int]) -> list[int]:
    """Meses (1–12) cobertos por um conjunto de decêndios (ordenados)."""
    return sorted({decend_month(d) for d in decends})


def read_zarc_rows(path: str) -> list[dict[str, Any]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def parse_risk_label(text: str) -> int | None:
    """Rótulo textual de risco → código (10/20/30/40)."""
    key = str(text or "").strip().lower()
    if not key:
        return None
    if key in RISK_BY_LABEL:
        return RISK_BY_LABEL[key]
    try:
        value = int(float(key))
    except ValueError:
        return None
    return value if value in RISK_LEVELS else None


def _risk_decends(text: str) -> dict[int, list[int]]:
    """Extrai ``decend: risco`` do campo ``decendios_com_risco`` (rótulo)."""
    out: dict[int, list[int]] = defaultdict(list)
    for chunk in str(text or "").split(";"):
        if ":" not in chunk:
            continue
        decend_text, risk_text = chunk.split(":", 1)
        try:
            decend = int(decend_text)
        except ValueError:
            continue
        risk = parse_risk_label(risk_text)
        if risk is None:
            continue
        out[risk].append(decend)
    return out


def recommended_decends(text: str, max_risk: int = PRIMARY_MAX_RISK) -> list[int]:
    """Decêndios da janela oficial: risco **muito baixo ou baixo** (≤ max_risk)."""
    risks = _risk_decends(text)
    decends: set[int] = set()
    for risk, values in risks.items():
        if risk <= max_risk:
            decends.update(values)
    return sorted(decends)


def build_windows(
    rows: Sequence[dict[str, Any]],
    crop: str,
    max_risk: int = PRIMARY_MAX_RISK,
) -> list[dict[str, Any]]:
    """Janelas de plantio por safra para uma cultura e um nível de risco.

    Cada registro preserva solo, ciclo, portaria e a combinação completa; as
    janelas **não** são reduzidas a uma única linha arbitrária.

    **Regra do bloco principal (correção V2.6).** Com a âncora dupla
    (decêndios 1–12 no segundo ano da safra, 13–36 no primeiro), algumas
    janelas oficiais caem em dois blocos de calendário separados — é o caso
    das culturas de ciclo curto do Nordeste (soja e milho da Bahia, janelas
    em março–junho **ou** outubro–dezembro). Nesses casos usa-se o **bloco
    contíguo de maior duração** (desempate: o de início mais antigo), que é
    o período de plantio principal da cultura. Os meses do bloco
    secundário são **descartados**, e não agregados — agregar meses
    separados por um intervalo não coberto misturaria períodos e poderia
    incorporar meses posteriores ao ano de colheita.
    """
    labels = CROP_LABELS.get(crop, [])
    grouped: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        if str(row.get("cultura")) not in labels:
            continue
        decends = recommended_decends(row.get("decendios_com_risco", ""), max_risk)
        if not decends:
            continue
        safra_ini = int(row["safra_ini"])
        safra_fin = int(row["safra_fin"])
        key = (
            row.get("safra"),
            row.get("cod_ciclo"),
            row.get("cod_solo"),
            row.get("portaria"),
        )
        entry = grouped.get(key)
        if entry is None:
            dates = [
                decend_to_dates(decend_year(d, safra_ini, safra_fin), d) for d in decends
            ]
            months_all = sorted(
                {
                    f"{decend_year(d, safra_ini, safra_fin):04d}-{decend_month(d):02d}"
                    for d in decends
                }
            )
            blocks = _month_blocks(months_all)
            primary = max(blocks, key=lambda b: (len(b), -int(b[0].replace("-", ""))))
            entry = {
                "safra": row.get("safra"),
                "safra_ini": safra_ini,
                "safra_fin": safra_fin,
                "cultura": row.get("cultura"),
                "crop": crop,
                "cod_ciclo": row.get("cod_ciclo"),
                "cod_solo": row.get("cod_solo"),
                "cod_clima": row.get("cod_clima"),
                "portaria": row.get("portaria"),
                "max_risk": max_risk,
                "decends": decends,
                "months": list(primary),
                "months_all": months_all,
                "n_blocks": len(blocks),
                "discarded_months": [m for m in months_all if m not in primary],
                "start_date": min(d[0] for d in dates),
                "end_date": max(d[1] for d in dates),
                "combinations": 0,
            }
            grouped[key] = entry
        entry["combinations"] += 1
    return sorted(
        grouped.values(),
        key=lambda w: (str(w["safra"]), str(w["cod_ciclo"]), str(w["cod_solo"])),
    )


def _month_blocks(months: Sequence[str]) -> list[list[str]]:
    """Separa uma lista de meses ``YYYY-MM`` em blocos de meses consecutivos."""
    if not months:
        return []
    ordered = sorted(months)
    blocks: list[list[str]] = [[ordered[0]]]
    for month in ordered[1:]:
        previous = blocks[-1][-1]
        year_prev, month_prev = (int(x) for x in previous.split("-"))
        year_now, month_now = (int(x) for x in month.split("-"))
        step = (year_now - year_prev) * 12 + (month_now - month_prev)
        if step == 1:
            blocks[-1].append(month)
        else:
            blocks.append([month])
    return blocks


def pam_year_candidates(safra: str, crop: str) -> dict[str, Any]:
    """Anos de referência PAM candidatos para uma safra.

    Regra (revista na V2.5): a safra ``Y/Y+1`` tem plantio na segunda metade de
    ``Y`` (soja e milho 1ª: set–dez) e colheita em ``Y+1``; o **milho 2ª
    safra** é plantado em jan–fev de ``Y+1`` e colhido em mai–jun de ``Y+1``.
    Em todos os casos o ano de referência da PAM é o **ano de colheita**
    (``safra_fin``), que é também o ano civil dos decêndios de janeiro–abril da
    janela.

    Para o **milho**, a PAM publica o **total do ano** (1ª + 2ª safras): a
    correspondência com a janela de uma safra específica é, portanto,
    ambígua — e a análise não pode tratar a safra como a mesma produção.
    """
    try:
        year = int(str(safra).split("/")[0])
    except (ValueError, IndexError):
        return {"primary": None, "alternative": None, "confidence": "none"}
    harvest_year = year + 1
    if crop == "milho_2":
        return {
            "primary": harvest_year,
            "alternative": harvest_year - 1,
            "confidence": "media",
            "ambiguity": (
                "PAM publica o total anual de milho (1ª + 2ª safras); a "
                "safra 2ª não está desagregada"
            ),
        }
    return {
        "primary": harvest_year,
        "alternative": year,
        "confidence": "media_alta" if crop == "soja" else "media",
        "ambiguity": None,
    }


def window_months_by_year(
    windows: Sequence[dict[str, Any]],
    crop: str,
) -> dict[str, list[str]]:
    """Meses ``YYYY-MM`` da janela recomendada, por safra."""
    out: dict[str, list[str]] = {}
    for window in windows:
        out.setdefault(str(window["safra"]), [])
        for month in window["months"]:
            if month not in out[str(window["safra"])]:
                out[str(window["safra"])].append(month)
    for key in out:
        out[key] = sorted(out[key])
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
