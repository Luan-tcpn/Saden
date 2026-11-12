"""Indicadores térmicos: graus-dia, soma térmica e eventos de calor.

Cada cultura tem um **perfil metodológico** próprio, com temperatura base,
temperatura superior, fórmula e fonte publicada. Não se usa uma temperatura
base universal: os valores abaixo são os das metodologias de referência e
são sempre aplicados **com a identificação do perfil** (D67).

Perfis implementados
--------------------

``soja_ometto``
    Método de Ometto (1981), como aplicado no Centro-Norte de Mato Grosso:
    ``GD = (Tmed − Tb)`` com ``Tb = 14 °C`` e ``Tmed`` limitada a
    ``36 °C`` (temperaturas basais mínima e máxima). Fonte: UFMT, *Nativa*,
    "Graus-dias na estimativa das taxas de crescimento de quatro cultivares
    de soja em diferentes épocas de plantio".

``soja_gilmore``
    Método de Gilmore & Rogers (1958) / Arnold (1960) / Schneider et al.
    (1987): ``STd = (Tmed − Tb)`` com ``Tb = 10 °C`` e ``Tmed`` limitada a
    ``30 °C``. É o método usado para a emergência (92,5 °C·dia) e para R5
    (554 °C·dia, Martorano et al. 2012) na simulação da fenologia da soja.

``milho_em_brapa``
    Metodologia da Embrapa Milho e Sorgo (AgenTec, *Relações com o clima*):
    ``GD = (Tmax + Tmin)/2 − Tb`` com ``Tb = 10 °C``, ``Tmax`` limitada a
    ``30 °C`` e ``Tmin`` limitada a ``10 °C``. É a expressão adotada pela
    maioria das empresas de sementes no Brasil e recomendada pela Embrapa
    (1993). Exigências térmicas de referência: 780–830 °C·dia
    (superprecoces), 831–890 (precoces) e 890–1.200 (normais), da emergência
    ao início da polinização.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

# Limites térmicos de referência para a detecção de eventos de calor.
# Onda de calor = sequência de ≥ 3 dias consecutivos com Tmax acima do
# percentil 90 da climatologia de referência (definição IPCC/ETCCDI).
HEAT_WAVE_MIN_DAYS = 3
HEAT_WAVE_PERCENTILE = 90.0

# Dia com Tmax acima deste limite é considerado "dia de calor extremo"
# (usado no Brasil para a cultura de soja: Tmax > 35 °C, conforme a
# literature de estresse térmico em soja no Cerrado).
EXTREME_HEAT_DAILY_C = 35.0
EXTREME_HEAT_NIGHTS_C = 20.0   # Tmin noturna alta (estresse noturno)


@dataclass(frozen=True)
class ThermalProfile:
    """Perfil metodológico de graus-dia de uma cultura."""

    key: str
    crop: str
    label: str
    base_temperature_c: float
    upper_temperature_c: float
    formula: str
    source: str
    cultivar_group: str
    reference_requirements: str
    limitations: str
    # "mean": o limite superior entra na temperatura média (Ometto, Gilmore &
    # Rogers); "extremes": Tmax e Tmin são limitados separadamente (Embrapa
    # Milho e Sorgo).
    limit_mode: str = "mean"

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_key": self.key,
            "crop": self.crop,
            "profile_label": self.label,
            "base_temperature_c": self.base_temperature_c,
            "upper_temperature_c": self.upper_temperature_c,
            "formula": self.formula,
            "source": self.source,
            "cultivar_group": self.cultivar_group,
            "reference_requirements": self.reference_requirements,
            "limitations": self.limitations,
            "limit_mode": self.limit_mode,
        }


PROFILES: dict[str, ThermalProfile] = {
    "soja_ometto": ThermalProfile(
        key="soja_ometto",
        crop="soja",
        label="Graus-dia de Ometto (1981) — soja, Centro-Norte de MT",
        base_temperature_c=14.0,
        upper_temperature_c=36.0,
        formula="GD = (Tmed - 14), com Tmed limitada a 36 °C",
        source=(
            "UFMT/Nativa — 'Graus-dias na estimativa das taxas de crescimento "
            "de quatro cultivares de soja em diferentes épocas de plantio' "
            "(método de Ometto, 1981: Tb = 14 °C, Ts = 36 °C)"
        ),
        cultivar_group="cultivares tardias (TMG 132 RR, GB 874 RR, MSOY 8757, MSOY 8866)",
        reference_requirements="não fixado neste perfil (uso como índice de Developmento relativo)",
        limitations=(
            "Cultivares tardias do Cerrado; a Tb de 14 °C não é válida para "
            "cultivares precoces sem ajuste."
        ),
        limit_mode="mean",
    ),
    "soja_gilmore": ThermalProfile(
        key="soja_gilmore",
        crop="soja",
        label="Graus-dia de Gilmore & Rogers (1958) — soja",
        base_temperature_c=10.0,
        upper_temperature_c=30.0,
        formula="STd = (Tmed - 10), com Tmed limitada a 30 °C",
        source=(
            "Schneider et al. (1987, PAB); Martorano et al. (2012); "
            "Setiyono et al. (2007) — simulação da fenologia da soja"
        ),
        cultivar_group="todos os grupos de maturação (uso como índice de tempo biológico)",
        reference_requirements=(
            "emergência = 92,5 °C·dia; R5 = 554 °C·dia (ambos com Tb = 10 °C)"
        ),
        limitations=(
            "A Tb de 10 °C e o teto de 30 °C são uma simplificação: literatura "
            "brasileira recente usa 14 °C para o ciclo plantio-maturação "
            "(Schneider et al., 1987)."
        ),
        limit_mode="mean",
    ),
    "milho_embrapa": ThermalProfile(
        key="milho_embrapa",
        crop="milho",
        label="Graus-dia da Embrapa Milho e Sorgo — milho",
        base_temperature_c=10.0,
        upper_temperature_c=30.0,
        formula="GD = ((Tmax_c + Tmin_c)/2) - 10, com Tmax <= 30 °C e Tmin >= 10 °C",
        source=(
            "Embrapa Milho e Sorgo — AgenTec, 'Relações com o clima'; "
            "Embrapa (1993); Gilmore & Rogers (1958); Cross & Zuber (1972)"
        ),
        cultivar_group="normais, precoces e superprecoces (exigências por grupo)",
        reference_requirements=(
            "emergência → início da polinização: 780–830 °C·dia (superprecoces), "
            "831–890 (precoces), 890–1.200 (normais)"
        ),
        limitations=(
            "As exigências térmicas são referencias por grupo de maturidade; sem "
            "identificação de cultivar na PAM, o grupo é um cenário, não uma "
            "medição."
        ),
        limit_mode="extremes",
    ),
}


def list_profiles(crop: str | None = None) -> list[ThermalProfile]:
    if crop is None:
        return list(PROFILES.values())
    return [p for p in PROFILES.values() if p.crop == crop]


def daily_mean_temperature(
    temp_max_c: float | None, temp_min_c: float | None
) -> float | None:
    """Temperatura média diária (média aritmética de Tmax e Tmin)."""
    if temp_max_c is None or temp_min_c is None:
        return None
    return (temp_max_c + temp_min_c) / 2.0


def degree_days(
    temp_max_c: float | None,
    temp_min_c: float | None,
    profile: ThermalProfile,
) -> float | None:
    """Graus-dia de um dia segundo o perfil.

    O cálculo segue exatamente a fórmula do perfil:

    * ``limit_mode = "extremes"`` (milho, Embrapa): ``Tmax`` é limitada a
      30 °C e ``Tmin`` a 10 °C **antes** da média;
    * ``limit_mode = "mean"`` (soja, Ometto e Gilmore & Rogers): a
      temperatura média é limitada à faixa [Tb, Ts] **depois** de calculada.
    """
    if temp_max_c is None or temp_min_c is None:
        return None
    if profile.limit_mode == "extremes":
        tmax = min(temp_max_c, profile.upper_temperature_c)
        tmin = max(temp_min_c, profile.base_temperature_c)
        mean = (tmax + tmin) / 2.0
    else:
        mean = (temp_max_c + temp_min_c) / 2.0
        mean = min(max(mean, profile.base_temperature_c), profile.upper_temperature_c)
    value = mean - profile.base_temperature_c
    return value if value > 0 else 0.0


def accumulate_degree_days(
    daily_records: Sequence[dict[str, Any]],
    profile: ThermalProfile,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """Acumula graus-dia numa janela e devolve o total e a cobertura.

    O acúmulo só começa a contar a partir do **primeiro dia com temperatura
    disponível** da janela (a emergência/plantio é desconhecida — a janela
    usada é a recomendada do ZARC, não um plantio observado), e o total é
    acompanhado do número de dias efetivamente calculados.
    """
    total = 0.0
    days_used = 0
    days_expected = 0
    first_day: str | None = None
    series: list[dict[str, Any]] = []
    for record in sorted(daily_records, key=lambda r: str(r.get("date"))):
        day = str(record.get("date"))
        if start and day < start:
            continue
        if end and day > end:
            continue
        days_expected += 1
        value = degree_days(
            record.get("temp_max_c"), record.get("temp_min_c"), profile
        )
        if value is None:
            series.append({"date": day, "degree_days": None})
            continue
        if first_day is None:
            first_day = day
        total += value
        days_used += 1
        series.append({"date": day, "degree_days": value})
    return {
        "profile": profile.key,
        "degree_days_total": total if days_used else None,
        "degree_days_mean": (total / days_used) if days_used else None,
        "days_used": days_used,
        "days_expected": days_expected,
        "coverage": (days_used / days_expected) if days_expected else None,
        "first_day": first_day,
        "series": series,
    }


def sum_of_thermal_time(
    daily_records: Sequence[dict[str, Any]],
    profile: ThermalProfile,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """Soma térmica acumulada (equivalente aos graus-dia, nomenclatura EMBRAPA).

    Mantida como função separada porque a literatura de fenologia da soja
    (Gilmore & Rogers, 1958) trata "soma térmica" e "graus-dia" como
    synonyms, e o painel registra o termo usado.
    """
    result = accumulate_degree_days(daily_records, profile, start=start, end=end)
    result["indicator"] = "soma_termica_acumulada"
    return result


def heat_wave_events(
    daily_records: Sequence[dict[str, Any]],
    threshold_c: float,
    min_days: int = HEAT_WAVE_MIN_DAYS,
) -> dict[str, Any]:
    """Eventos de calor: sequências de dias com Tmax acima do limiar.

    Devolve o número de eventos, o total de dias afetados, a duração máxima
    e as datas de início.
    """
    days: list[tuple[str, float]] = []
    for record in sorted(daily_records, key=lambda r: str(r.get("date"))):
        value = record.get("temp_max_c")
        if value is None:
            continue
        days.append((str(record.get("date")), float(value)))
    events: list[list[str]] = []
    current: list[str] = []
    for day, value in days:
        if value > threshold_c:
            current.append(day)
        else:
            if len(current) >= min_days:
                events.append(current)
            current = []
    if len(current) >= min_days:
        events.append(current)
    return {
        "threshold_c": threshold_c,
        "min_days": min_days,
        "n_events": len(events),
        "total_days": sum(len(event) for event in events),
        "max_duration": max((len(event) for event in events), default=0),
        "events": [{"start": event[0], "end": event[-1], "days": len(event)} for event in events],
    }


def extreme_heat_days(
    daily_records: Sequence[dict[str, Any]],
    daily_limit_c: float = EXTREME_HEAT_DAILY_C,
    night_limit_c: float = EXTREME_HEAT_NIGHTS_C,
) -> dict[str, Any]:
    """Dias de calor extremo (Tmax alta) e noites quentes (Tmin alta)."""
    max_days = 0
    night_days = 0
    observed = 0
    for record in daily_records:
        tmax = record.get("temp_max_c")
        tmin = record.get("temp_min_c")
        if tmax is not None:
            observed += 1
            if float(tmax) > daily_limit_c:
                max_days += 1
        if tmin is not None and float(tmin) > night_limit_c:
            night_days += 1
    return {
        "daily_limit_c": daily_limit_c,
        "night_limit_c": night_limit_c,
        "extreme_heat_days": max_days,
        "warm_nights": night_days,
        "days_observed": observed,
    }


def percentile_threshold(
    values: Sequence[float], percentile: float = HEAT_WAVE_PERCENTILE
) -> float | None:
    """Percentil de uma amostra (usado no limiar climatológico de onda de calor)."""
    clean = sorted(float(v) for v in values if v is not None)
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    position = (len(clean) - 1) * (percentile / 100.0)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return clean[int(position)]
    return clean[lower] + (clean[upper] - clean[lower]) * (position - lower)
