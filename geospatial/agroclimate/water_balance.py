"""Balanço hídrico climatológico e sequencial — Thornthwaite & Mather (1955).

Método implementado conforme a documentação da Embrapa (Embrapa Clima e
Ambiente; ferramenta **BHCalc**, Embrapa/IAC):

* **ETP** — Thornthwaite (1948) (ver :mod:`agroclimate.evapotranspiration`);
* **sequencial** — Thornthwaite & Mather (1955): o armazenamento de água no
  solo (ARM) é limitado pela **capacidade de água disponível (CAD)**; a
  evapotranspiração real (ETR) é a ETP enquanto houver água no solo; a
  diferença vira **deficiência hídrica** (DEF) ou **excedente hídrico** (EXC).

O balanço **climatológico** usa as médias mensais de uma série de anos; o
**sequencial** percorre a série diária/mensal na ordem cronológica. O painel
usa a forma **sequencial** (a ordem temporal importa para a relação entre
precipitação, ETP e armazenamento).

**CAD**: entra como parâmetro explícito, com perfil documentado. Não se
atribui a mesma CAD a todos os municípios sem justificativa — o painel usa
cenários de solo (D68) e registra a CAD e a sua fonte em cada registro.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class SoilProfile:
    """Perfil de solo com capacidade de água disponível (CAD)."""

    key: str
    label: str
    cad_mm: float
    source: str
    limitations: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "soil_profile_key": self.key,
            "soil_profile_label": self.label,
            "cad_mm": self.cad_mm,
            "cad_source": self.source,
            "cad_limitations": self.limitations,
        }


# Perfis de solo. O valor de 50 mm para solo tipo 2 (textura média) é o
# adotado pelo MAPA (2014) e usado nos balanços hídricos da Embrapa; os
# demais são escalados proporcionalmente e declarados como **cenário**.
SOIL_PROFILES: dict[str, SoilProfile] = {
    "tipo2_medio": SoilProfile(
        key="tipo2_medio",
        label="Solo tipo 2 — textura média (MAPA/Embrapa)",
        cad_mm=50.0,
        source="MAPA (2014), citado em Embrapa (Santiago et al., 2015, CBAgro)",
        limitations=(
            "Valor de referência para textura média; não é a CAD específica do "
            "município — o painel trata os perfis como cenários."
        ),
    ),
    "tipo1_arenoso": SoilProfile(
        key="tipo1_arenoso",
        label="Solo tipo 1 — textura arenosa (cenário de baixa CAD)",
        cad_mm=35.0,
        source="Escalonamento do perfil tipo 2 para textura arenosa",
        limitations="Cenário; sem mapa de solos municipal aplicado.",
    ),
    "tipo3_argiloso": SoilProfile(
        key="tipo3_argiloso",
        label="Solo tipo 3 — textura argilosa (cenário de alta CAD)",
        cad_mm=70.0,
        source="Escalonamento do perfil tipo 2 para textura argilosa",
        limitations="Cenário; sem mapa de solos municipal aplicado.",
    ),
}


def default_soil_profile(key: str = "tipo2_medio") -> SoilProfile:
    if key not in SOIL_PROFILES:
        raise KeyError(f"perfil de solo desconhecido: {key}")
    return SOIL_PROFILES[key]


def sequential_water_balance(
    monthly: Sequence[dict[str, Any]],
    cad_mm: float,
    et_method: str = "thornthwaite_1948",
) -> list[dict[str, Any]]:
    """Balanço hídrico sequencial de Thornthwaite & Mather (1955).

    ``monthly`` exige ``month`` (AAAA-MM), ``precip_mm`` e ``etp_mm``
    (a ETP já calculada pelo método declarado em ``et_method``).

    A inicialização do armazenamento segue Pereira (2005), como no BHCalc:
    parte-se de ARM = CAD (solo saturado) e vai-se ajustando ao longo da
    série; o primeiro período é inicializado com o saldo de precipitação
    menos ETP.
    """
    out: list[dict[str, Any]] = []
    storage = cad_mm
    storage_prev = cad_mm
    for record in sorted(monthly, key=lambda r: str(r.get("month"))):
        precip = record.get("precip_mm")
        etp = record.get("etp_mm")
        if precip is None or etp is None:
            out.append(
                {
                    "month": record.get("month"),
                    "precip_mm": precip,
                    "etp_mm": etp,
                    "et_method": et_method,
                    "cad_mm": cad_mm,
                    "arm_mm": None,
                    "alt_mm": None,
                    "etr_mm": None,
                    "def_mm": None,
                    "exc_mm": None,
                    "status": "incomplete",
                }
            )
            storage_prev = storage
            continue
        precip = float(precip)
        etp = float(etp)
        # Thornthwaite & Mather: se P − ETP > 0, o solo retém até CAD e o
        # restante é excedente; se P − ETP < 0, a ETP é limitada pela água
        # disponível (ETR = ARM + P quando P < ETP).
        balance = precip - etp
        if balance >= 0:
            etr = etp
            storage = min(cad_mm, storage + balance)
            exc = max(0.0, storage + balance - cad_mm) if storage >= cad_mm else 0.0
            if storage >= cad_mm:
                exc = max(0.0, balance)
                storage = cad_mm
            else:
                exc = 0.0
        else:
            available = storage + precip
            etr = min(etp, available)
            storage = max(0.0, available - etr)
            exc = 0.0
        deficiency = max(0.0, etp - etr)
        alteration = storage - storage_prev
        out.append(
            {
                "month": record.get("month"),
                "precip_mm": precip,
                "etp_mm": etp,
                "et_method": et_method,
                "cad_mm": cad_mm,
                "arm_mm": storage,
                "alt_mm": alteration,
                "etr_mm": etr,
                "def_mm": deficiency,
                "exc_mm": exc,
                "status": "ok",
            }
        )
        storage_prev = storage
    return out


def aggregate_water_balance(
    balance: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Agrega o balanço hídrico de um período (ETP, ETR, DEF, EXC, ARM final)."""
    valid = [row for row in balance if row.get("status") == "ok"]
    if not valid:
        return {
            "etp_total_mm": None,
            "etr_total_mm": None,
            "deficiency_total_mm": None,
            "excess_total_mm": None,
            "storage_final_mm": None,
            "months": 0,
        }
    return {
        "etp_total_mm": sum(float(row["etp_mm"]) for row in valid),
        "etr_total_mm": sum(float(row["etr_mm"]) for row in valid),
        "deficiency_total_mm": sum(float(row["def_mm"]) for row in valid),
        "excess_total_mm": sum(float(row["exc_mm"]) for row in valid),
        "storage_final_mm": float(valid[-1]["arm_mm"]),
        "months": len(valid),
    }


def daily_to_monthly(
    daily_records: Sequence[dict[str, Any]],
    variables: Sequence[str] = ("precip_mm", "et0_mm"),
    etp_field: str = "et0_mm",
    sum_variables: Sequence[str] = ("precip_mm", "radiacao_mj_m2", "et0_mm"),
) -> list[dict[str, Any]]:
    """Agrega a série diária em mensal (somas e médias conforme a variável).

    ``etp_field`` entra como **soma** mensal (a ETP de um mês é a soma do
    ET0 diário) — usar a média diaria compara precipitacao (soma) com ETP
    (media) e produz um balanco hidrico sem deficiencia.
    """
    buckets: dict[str, dict[str, list[float]]] = {}
    for record in daily_records:
        month = str(record.get("date"))[:7]
        if len(month) != 7:
            continue
        bucket = buckets.setdefault(month, {})
        for variable in variables:
            value = record.get(variable)
            if value is None:
                continue
            bucket.setdefault(variable, []).append(float(value))
    out: list[dict[str, Any]] = []
    for month in sorted(buckets):
        item: dict[str, Any] = {"month": month}
        for variable in variables:
            series = buckets[month].get(variable) or []
            if not series:
                item[variable] = None
                item[f"{variable}_n"] = 0
                continue
            if variable in sum_variables:
                item[variable] = float(sum(series))
            else:
                item[variable] = float(sum(series) / len(series))
            item[f"{variable}_n"] = len(series)
        item["etp_mm"] = item.get(etp_field)
        out.append(item)
    return out
