"""Janela fenológica de enchimento de grãos (V2.7).

O **ZARC é uma janela de plantio por risco climático**, não um calendário
fenológico: ele delimita *quando se pode semear* com risco aceitável, e não
*quando a lavoura floresce ou enche grãos*. Este módulo constrói, a partir de
parâmetros **publicados** (Embrapa), a janela de **enchimento de grãos** de
cada cultura, para usá-la como **experimento** sobre a janela de plantio.

Princípios (D78):

* a janela original do ZARC **é preservada** e continua sendo o protocolo
  principal; a janela fenológica é uma **linha experimental**;
* todo parâmetro tem **fonte explícita**; o módulo **não** inventa datas
  municipais: usa **requisitos térmicos** (graus-dia) publicados, convertidos
  em datas **aproximadas** pela série de graus-dia observada;
* quando a bibliografia fornece **intervalo** (não valor único), o ponto
  médio é usado e o intervalo é preservado na documentação;
* cultivars não identificadas geram **cenários** (perfil por grupo de
  maturação), não uma afirmação única.

Referências (lidas na fase de pesquisa fenológica da V2.7):

* **Soja** — Embrapa Soja, *Sistemas de Produção*, escala de Fehr &
  Caviness (1977): R1 início do florescimento, R5 início do enchimento de
  grãos, R6 grãos cheios, R7 maturação fisiológica, R8 maturação. Requisito
  térmico com Tb = 10 °C (Gilmore & Rogers, 1958; Schneider et al., 1987;
  Martorano et al., 2012): **R1 = 92,5 °C·dia** e **R5 = 554 °C·dia**.
* **Milho** — Embrapa Milho e Sorgo: soma térmica com Tmax ≤ 30 °C,
  Tmin ≥ 10 °C, Tb = 10 °C; da **emergência** ao **início da polinização**:
  780–830 °C·dia (superprecoces), 831–890 °C·dia (precoces), 890–1.200 °C·dia
  (normais/tardias). Após a polinização: **R3 (estádio-leiteoso, início do
  enchimento de grãos) ≈ 20–25 dias**, **R5 (dente de milho) ≈ 36 dias** e
  **R6 (maturidade fisiológica) ≈ 50–60 dias**.
* **Milho 2ª safra** — Embrapa (documento 258): ciclo total de 120–150 dias e
  2.200–3.300 °C·dia. Não há estágio intermediário publicado com suficiente
  precisão para a V2.7; a cultura permanece na janela do ZARC (ausência
  preservada).

O cálculo da data é **invertido**: a partir da data de plantio (janela ZARC),
acumula-se a soma térmica **real observada** até atingir o requisito do
estádio. A data passa a depender do clima do ano — que é exatamente a
exposição térmica real do ciclo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

# --------------------------------------------------------------------- perfis


@dataclass(frozen=True)
class PhenologicalStage:
    """Estádio fenológico com o seu requisito térmico."""

    key: str
    label: str
    degree_days: float
    source: str
    note: str = ""


@dataclass(frozen=True)
class PhenologyProfile:
    """Perfil fenológico de uma cultura."""

    key: str
    crop: str
    label: str
    base_temperature_c: float
    upper_temperature_c: float
    stages: tuple[PhenologicalStage, ...]
    source: str
    limitations: str
    # Perfil de graus-dia da V2.6 usado no cálculo: a data fenológica é
    # derivada da MESMA soma térmica do painel (aritmética idêntica).
    thermal_profile_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "phenology_profile": self.key,
            "crop": self.crop,
            "label": self.label,
            "base_temperature_c": self.base_temperature_c,
            "upper_temperature_c": self.upper_temperature_c,
            "thermal_profile_key": self.thermal_profile_key,
            "stages": [
                {
                    "key": s.key,
                    "label": s.label,
                    "degree_days": s.degree_days,
                    "source": s.source,
                    "note": s.note,
                }
                for s in self.stages
            ],
            "source": self.source,
            "limitations": self.limitations,
        }


def _stage(
    key: str, label: str, dd: float, source: str, note: str = ""
) -> PhenologicalStage:
    return PhenologicalStage(key=key, label=label, degree_days=dd, source=source, note=note)


SOJA_MEDIO = PhenologyProfile(
    key="soja_medio",
    crop="soja",
    label="Soja — perfil de maturação média (R1 → R5)",
    base_temperature_c=10.0,
    upper_temperature_c=30.0,
    stages=(
        _stage(
            "R1",
            "Início do florescimento (R1)",
            92.5,
            "Schneider et al. (1987) / Martorano et al. (2012), via Embrapa Soja",
            "Soma térmica desde a emergência com Tb = 10 °C",
        ),
        _stage(
            "R5",
            "Início do enchimento de grãos (R5)",
            554.0,
            "Martorano et al. (2012), via Embrapa Soja",
            "Soma térmica desde a emergência com Tb = 10 °C",
        ),
    ),
    source=(
        "Embrapa Soja — Sistemas de Produção (escala de Fehr & Caviness, 1977); "
        "requisitos térmicos de Schneider et al. (1987) e Martorano et al. (2012)"
    ),
    limitations=(
        "Perfil de maturação média; sem identificação de cultivar na PAM, é um "
        "cenário. O valor de 554 °C·dia é específico do conjunto de referência."
    ),
    thermal_profile_key="soja_gilmore",
)

_MILHO_SOURCE = (
    "Embrapa Milho e Sorgo — exigências térmicas por grupo de maturação: "
    "Tmax ≤ 30 °C, Tmin ≥ 10 °C, Tb = 10 °C; 780–830 °C·dia (superprecoces), "
    "831–890 (precoces), 890–1.200 (normais)"
)

MILHO_GRUPO_I = PhenologyProfile(
    key="milho_grupo_i",
    crop="milho",
    label="Milho — grupo I (superprecoce), 780 °C·dia até a polinização",
    base_temperature_c=10.0,
    upper_temperature_c=30.0,
    stages=(
        _stage(
            "VT",
            "Pendoamento (VT) / início da polinização",
            780.0,
            "Embrapa Milho e Sorgo — exigências térmicas por grupo",
            "Emergence → início da polinização",
        ),
    ),
    thermal_profile_key="milho_embrapa",
    source=_MILHO_SOURCE,
    limitations="Grupo I do ZARC (superprecoce); sem identificação de cultivar.",
)

MILHO_GRUPO_II = PhenologyProfile(
    key="milho_grupo_ii",
    crop="milho",
    label="Milho — grupo II (precoce), 860 °C·dia até a polinização",
    base_temperature_c=10.0,
    upper_temperature_c=30.0,
    stages=(
        _stage(
            "VT",
            "Pendoamento (VT) / início da polinização",
            860.0,
            "Embrapa Milho e Sorgo — exigências térmicas por grupo",
            "Ponto médio do intervalo 831–890 °C·dia do grupo II",
        ),
    ),
    thermal_profile_key="milho_embrapa",
    source=_MILHO_SOURCE,
    limitations="Ponto médio do grupo II (precoce); sem identificação de cultivar.",
)

MILHO_GRUPO_III = PhenologyProfile(
    key="milho_grupo_iii",
    crop="milho",
    label="Milho — grupo III (normal/tardio), 1.050 °C·dia até a polinização",
    base_temperature_c=10.0,
    upper_temperature_c=30.0,
    stages=(
        _stage(
            "VT",
            "Pendoamento (VT) / início da polinização",
            1050.0,
            "Embrapa Milho e Sorgo — exigências térmicas por grupo",
            "Ponto médio do intervalo 890–1.200 °C·dia do grupo III",
        ),
    ),
    thermal_profile_key="milho_embrapa",
    source=_MILHO_SOURCE,
    limitations="Ponto médio do grupo III (normal/tardio); sem identificação de cultivar.",
)

MILHO_2_SAFRA = PhenologyProfile(
    key="milho_2_safra",
    crop="milho_2",
    label="Milho 2ª safra — ciclo total de 2.500 °C·dia",
    base_temperature_c=10.0,
    upper_temperature_c=30.0,
    stages=(
        _stage(
            "ciclo_total",
            "Ciclo total (emergência → maturação fisiológica)",
            2500.0,
            "Embrapa (documento 258, milho 2ª safra): 2.200–3.300 °C·dia",
            "Ponto médio do intervalo publicado",
        ),
    ),
    thermal_profile_key="milho_embrapa",
    source=(
        "Embrapa — documento 258 (milho 2ª safra): ciclo total de 120–150 dias e "
        "2.200–3.300 °C·dia"
    ),
    limitations=(
        "Valor pontual no meio do intervalo publicado; refere-se ao ciclo total, "
        "não a um subrange específico."
    ),
)

PHENOLOGY_PROFILES: dict[str, PhenologyProfile] = {
    p.key: p
    for p in (SOJA_MEDIO, MILHO_GRUPO_I, MILHO_GRUPO_II, MILHO_GRUPO_III, MILHO_2_SAFRA)
}

PROFILES_BY_CROP: dict[str, list[PhenologyProfile]] = {}
for _profile in PHENOLOGY_PROFILES.values():
    PROFILES_BY_CROP.setdefault(_profile.crop, []).append(_profile)


# --------------------------------------------------- definição do enchimento
@dataclass(frozen=True)
class GrainFillingDefinition:
    """Como a janela de enchimento de grãos é derivada do perfil."""

    crop: str
    start_stage: str
    start_offset_days: float
    duration_days: float
    source: str
    note: str


# A **soja** tem o início do enchimento definido por um estágio publicado
# (R5 = 554 °C·dia) e a **duração** como cenário explícito (o material
# consultado não fixa um único valor; a sensibilidade é medida).
# O **milho** tem início e fim em dias após a polinização, conforme a
# Embrapa (R3 ≈ 20–25 d; R6 ≈ 50–60 d) — ponto médio dos intervalos.
GRAIN_FILLING_DEFINITIONS: dict[str, GrainFillingDefinition] = {
    "soja": GrainFillingDefinition(
        crop="soja",
        start_stage="R5",
        start_offset_days=0.0,
        duration_days=45.0,
        source=(
            "Embrapa Soja (escala de Fehr & Caviness, 1977; requisitos térmicos "
            "de Martorano et al., 2012)"
        ),
        note=(
            "Início = R5 (554 °C·dia, publicado). Duração de 45 dias é um "
            "cenário explícito (o material consultado apresenta faixa de "
            "aproximadamente 40–60 dias entre R5 e R8); a sensibilidade é "
            "medida com 30/45/60 dias."
        ),
    ),
    "milho": GrainFillingDefinition(
        crop="milho",
        start_stage="VT",
        start_offset_days=22.5,
        duration_days=32.5,
        source="Embrapa Milho e Sorgo (estádios R1–R6 após a polinização)",
        note=(
            "Início = R3 (estádio-leiteoso), ≈20–25 dias após a polinização "
            "(ponto médio 22,5); fim = R6 (maturidade fisiológica), ≈50–60 "
            "dias após a polinização (ponto médio 55)."
        ),
    ),
}


# ------------------------------------------------------------------ cálculo
def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def daily_degree_days(
    daily_records: Sequence[dict[str, Any]],
    profile: PhenologyProfile,
    start: str | None = None,
    end: str | None = None,
) -> list[tuple[str, float]]:
    """Soma térmica diária (graus-dia) dentro do intervalo.

    Usa o mesmo núcleo de :mod:`agroclimate.thermal` (Tb e Ts do perfil),
    de modo que o cálculo da V2.7 e o do painel da V2.6 sejam idênticos.
    """
    from .thermal import PROFILES, degree_days

    thermal_profile = PROFILES[profile.thermal_profile_key]
    out: list[tuple[str, float]] = []
    for record in sorted(daily_records, key=lambda r: str(r.get("date"))):
        day = str(record.get("date"))
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        value = degree_days(
            _to_float(record.get("temp_max_c")),
            _to_float(record.get("temp_min_c")),
            thermal_profile,
        )
        out.append((day, float(value) if value is not None else 0.0))
    return out


def stage_dates(
    daily_records: Sequence[dict[str, Any]],
    profile: PhenologyProfile,
    planting_start: str,
    max_days: int = 300,
) -> dict[str, Any]:
    """Datas **aproximadas** dos estágios a partir da soma térmica real.

    A partir da data de plantio, acumula-se a soma térmica observada até
    atingir o requisito de cada estágio. As datas dependem do clima do ano
    e do perfil de maturação adotado (cenário).
    """
    series = daily_degree_days(daily_records, profile, planting_start)
    if not series:
        return {
            "status": "sem_dados",
            "phenology_profile": profile.key,
            "planting_start": planting_start,
            "n_days": 0,
            "stages": {},
        }
    series = series[:max_days]
    cumulative = 0.0
    reached: dict[str, dict[str, Any]] = {}
    stage_index = 0
    stages = sorted(profile.stages, key=lambda s: s.degree_days)
    for day, value in series:
        cumulative += value
        while stage_index < len(stages) and cumulative >= stages[stage_index].degree_days:
            stage = stages[stage_index]
            reached[stage.key] = {
                "label": stage.label,
                "degree_days_required": stage.degree_days,
                "date_approx": day,
                "achieved_degree_days": round(cumulative, 1),
                "source": stage.source,
                "note": stage.note,
            }
            stage_index += 1
    for stage in stages:
        if stage.key not in reached:
            reached[stage.key] = {
                "label": stage.label,
                "degree_days_required": stage.degree_days,
                "date_approx": None,
                "achieved_degree_days": round(cumulative, 1),
                "source": stage.source,
                "note": stage.note,
                "status": "estadio_nao_alcancado",
            }
    return {
        "status": "ok",
        "phenology_profile": profile.key,
        "planting_start": planting_start,
        "n_days_used": len(series),
        "total_degree_days": round(cumulative, 1),
        "stages": reached,
        "caveat": (
            "Datas aproximadas por soma térmica real; dependem do clima do ano "
            "e do perfil de maturação adotado (cenário sem identificação de "
            "cultivar)."
        ),
    }


def _add_days(day: str, days: float) -> str:
    import datetime as _dt

    base = _dt.date.fromisoformat(day)
    return (base + _dt.timedelta(days=float(days))).isoformat()


def grain_filling_window(
    daily_records: Sequence[dict[str, Any]],
    profile: PhenologyProfile,
    planting_start: str,
    definition: GrainFillingDefinition | None = None,
    duration_days: float | None = None,
) -> dict[str, Any]:
    """Janela de enchimento de grãos (aproximada) para um ano e uma cultura.

    Devolve a janela em datas ISO, o número de dias efetivamente
    disponíveis e a rastreabilidade dos parâmetros usados.
    """
    definition = definition or GRAIN_FILLING_DEFINITIONS.get(profile.crop)
    if definition is None:
        return {
            "status": "sem_definicao_publicada",
            "phenology_profile": profile.key,
            "crop": profile.crop,
            "note": (
                "Não há definição publicada suficiente para a janela de "
                "enchimento de grãos desta cultura; a janela do ZARC é mantida."
            ),
        }
    stages = stage_dates(daily_records, profile, planting_start)
    if stages.get("status") != "ok":
        return dict(stages, crop=profile.crop)
    stage = stages["stages"].get(definition.start_stage) or {}
    start = stage.get("date_approx")
    if not start:
        return {
            "status": "estadio_nao_alcancado",
            "crop": profile.crop,
            "phenology_profile": profile.key,
            "stages": stages["stages"],
        }
    start = _add_days(start, definition.start_offset_days)
    duration = definition.duration_days if duration_days is None else float(duration_days)
    end = _add_days(start, duration)
    available = [
        str(r.get("date"))
        for r in daily_records
        if start <= str(r.get("date")) <= end
    ]
    return {
        "status": "ok",
        "crop": profile.crop,
        "phenology_profile": profile.key,
        "planting_start": planting_start,
        "window_start": start,
        "window_end": end,
        "n_days_in_window": len(available),
        "duration_days": duration,
        "start_stage": definition.start_stage,
        "stage_date_approx": stage.get("date_approx"),
        "source": definition.source,
        "note": definition.note,
        "stages": stages["stages"],
    }
