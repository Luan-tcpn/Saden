"""Correções de física validadas na etapa de fechamento (D128–D131).

Este módulo **não substitui** `evapotranspiration.py` nem `water_balance.py`:
as funções históricas permanecem intactas para que todo artefato publicado
continue reproduzível. Aqui ficam as versões corrigidas, selecionáveis pela
configuração do pipeline canônico (``et0_implementation`` e
``water_balance_implementation``).

Duas correções, ambas adjudicadas com evidência:

**C1 — pressão de vapor de saturação (ET0).**
A referência usa ``es(Tmean)``; a FAO-56 (Allen et al., 1998, eq. 12) define
``es = [e°(Tmax) + e°(Tmin)]/2``. A simplificação subestima o déficit de pressão
de vapor em dias de amplitude térmica alta.

**C2 — conversão do vento (ET0).**
``vento_kmh`` já está a 2 m (NASA POWER ``WS2M``), portanto ``u2 = vento/3,6``.
A referência aplica um fator 0,4 adicional (``u2 = 0,4 × vento/3,6``), deixando
``u2`` 60% abaixo do valor a 2 m e subestimando o termo aerodinâmico.

Efeito conjunto medido (``et0_adjudication.json``): ET0 **+10,3%** na mediana
por janela; C2 é o fator dominante (+5,9%) e C1 responde por +3,1%.

**C3 — excedente hídrico (D124).**
Quando um mês de saldo positivo satura a CAD a partir de armazenamento parcial,
a referência lança o saldo inteiro como excedente. O correto é
``EXC = ARM_anterior + (P − ETP) − CAD`` limitado a zero. Déficit, ETR e
armazenamento são idênticos nas duas versões.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

STEFAN_BOLTZMANN_MJ = 4.903e-9
SOLAR_CONSTANT = 0.0820
ALBEDO = 0.23
CORRECTION_ID = "consolidated-2026-11-14"


def saturation_vapour_pressure(temp_c: float) -> float:
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def extraterrestrial_radiation(latitude_deg: float, day_of_year: int) -> float:
    phi = math.radians(latitude_deg)
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * day_of_year / 365.0)
    delta = 0.409 * math.sin(2.0 * math.pi * day_of_year / 365.0 - 1.39)
    omega = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return (
        24.0 * 60.0 / math.pi * SOLAR_CONSTANT * dr
        * (omega * math.sin(phi) * math.sin(delta)
           + math.cos(phi) * math.cos(delta) * math.sin(omega))
    )


def _day_of_year(date: str) -> int:
    from datetime import date as date_type

    year, month, day = (int(part) for part in date.split("-"))
    return date_type(year, month, day).timetuple().tm_yday


def et0_daily(
    temp_max_c: float,
    temp_min_c: float,
    temp_mean_c: float,
    radiation_mj_m2: float,
    wind_kmh_at_2m: float,
    humidity_pct: float,
    pressure_kpa: float,
    latitude_deg: float,
    day_of_year: int,
) -> float:
    """ET0 FAO-56 Penman-Monteith com C1 e C2 aplicadas."""
    u2 = max(0.5, float(wind_kmh_at_2m) / 3.6)
    es = (
        saturation_vapour_pressure(temp_max_c) + saturation_vapour_pressure(temp_min_c)
    ) / 2.0
    ea = min(es, es * float(humidity_pct) / 100.0)
    vpd = es - ea
    gamma = 0.000665 * float(pressure_kpa)
    delta = (
        4098.0 * saturation_vapour_pressure(temp_mean_c) / ((temp_mean_c + 237.3) ** 2)
    )
    ra = extraterrestrial_radiation(latitude_deg, day_of_year)
    rso = 0.75 * ra if ra > 0 else 1e-6
    rs = float(radiation_mj_m2)
    rnl = (
        STEFAN_BOLTZMANN_MJ
        * ((temp_max_c + 273.16) ** 4 + (temp_min_c + 273.16) ** 4) / 2.0
        * max(0.0, 0.34 - 0.14 * ea)
        * max(0.0, min(1.0, 1.35 * rs / rso - 0.35))
    )
    rn = (1.0 - ALBEDO) * rs - rnl
    numerator = 0.408 * delta * rn + gamma * (900.0 / (temp_mean_c + 273.0)) * u2 * vpd
    denominator = delta + gamma * (1.0 + 0.34 * u2)
    return max(0.0, numerator / denominator) if denominator > 0 else 0.0


def daily_et0_series(
    records: Sequence[dict[str, Any]],
    latitude: float,
    elevation_m: float | None = None,
) -> list[dict[str, Any]]:
    """Série diária de ET0 corrigida, com a mesma forma de saída da histórica."""
    out: list[dict[str, Any]] = []
    for record in records:
        date = str(record.get("date"))
        try:
            value = et0_daily(
                float(record["temp_max_c"]),
                float(record["temp_min_c"]),
                float(record["temp_media_c"]),
                float(record["radiacao_mj_m2"]),
                float(record["vento_kmh"]),
                float(record["umidade_rel_pct"]),
                float(record["pressao_kpa"]),
                float(latitude),
                _day_of_year(date),
            )
        except (KeyError, TypeError, ValueError):
            value = None
        out.append(
            {
                "date": date,
                "et0_mm": value,
                "et_method": "fao56_penman_monteith_corrected",
                "correction": CORRECTION_ID,
                "precip_mm": record.get("precip_mm"),
            }
        )
    return out


def sequential_water_balance(
    monthly: Sequence[dict[str, Any]],
    cad_mm: float,
    initial_storage_mm: float | None = None,
    et_key: str = "etp_mm",
) -> list[dict[str, Any]]:
    """Thornthwaite & Mather (1955) com o excedente corrigido (C3).

    ``storage`` nunca excede ``cad_mm``; o excedente é exatamente o que
    transborda: ``ARM_anterior + (P − ETP) − CAD``, limitado a zero.
    """
    storage = cad_mm if initial_storage_mm is None else min(float(initial_storage_mm), cad_mm)
    previous = storage
    out: list[dict[str, Any]] = []
    for row in sorted(monthly, key=lambda item: str(item.get("month"))):
        precip = row.get("precip_mm")
        demand = row.get(et_key)
        if precip is None or demand is None:
            out.append(
                {
                    "month": row.get("month"), "precip_mm": precip, "etp_mm": demand,
                    "cad_mm": cad_mm, "arm_mm": None, "alt_mm": None, "etr_mm": None,
                    "def_mm": None, "exc_mm": None, "status": "incomplete",
                    "correction": CORRECTION_ID,
                }
            )
            previous = storage
            continue
        precip = float(precip)
        demand = float(demand)
        balance = precip - demand
        if balance >= 0:
            etr = demand
            excess = max(0.0, storage + balance - cad_mm)
            storage = min(cad_mm, storage + balance)
            deficit = 0.0
        else:
            available = storage + precip
            etr = min(demand, available)
            storage = max(0.0, available - etr)
            excess = 0.0
            deficit = demand - etr
        out.append(
            {
                "month": row.get("month"), "precip_mm": precip, "etp_mm": demand,
                "cad_mm": cad_mm, "arm_mm": storage, "alt_mm": storage - previous,
                "etr_mm": etr, "def_mm": deficit, "exc_mm": excess, "status": "ok",
                "correction": CORRECTION_ID,
            }
        )
        previous = storage
    return out
