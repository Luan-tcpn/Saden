"""Evapotranspiração de referência (ET0) — FAO-56 e métodos alternativos.

Três métodos são implementados, cada um **identificado** na saída:

``fao56_penman_monteith``
    FAO-56 Penman-Monteith (Allen et al., 1998) — método de referência, com
    radiação, vento a 2 m, umidade e pressão. Quando o vento é observado a
    10 m, é convertido para 2 m pelo coeficiente ``0,4`` da FAO-56
    (vento a 2 m = 0,4 × vento a 10 m).

``thornthwaite_1948``
    Thornthwaite (1948), como implementado no ``BHCalc`` da Embrapa/IAC:
    índice de calor anual *I*, expoente *a* e correção de fotoperíodo. Só
    usa temperatura — método **diferente**, não equivalente ao FAO-56.

``hargreaves_samani``
    Hargreaves & Samani (1985): ETO = 0,0023 × (Tmed + 17,8) × (Tmax − Tmin)^0,5 ×
    Ra. Método de menor exigência de dados.

**Estimativas de métodos diferentes nunca são misturadas** na mesma série:
cada registro carrega ``et_method``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

# Constante de Stefan-Boltzmann (MJ K-4 m-2 dia-1).
STEFAN_BOLTZMANN = 0.000000004903
SOLAR_CONSTANT = 0.0820  # MJ m-2 min-1

#(internal pressure) = 101.3 kPa
ATMOSPHERIC_PRESSURE_KPA = 101.3

FAO56_WIND_CONVERSION_10M_TO_2M = 0.4

ET_METHODS = ("fao56_penman_monteith", "thornthwaite_1948", "hargreaves_samani")


class EvapotranspirationError(RuntimeError):
    """Falha no cálculo da evapotranspiração."""


@dataclass(frozen=True)
class ETResult:
    """Resultado diário da ET0."""

    method: str
    et0_mm: float | None
    available: bool
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "et_method": self.method,
            "et0_mm": self.et0_mm,
            "et_available": self.available,
            "et_detail": self.detail,
        }


def wind_at_2m(wind_speed_10m_kmh: float | None) -> float | None:
    """Converte vento de 10 m para 2 m (coeficiente 0,4 da FAO-56)."""
    if wind_speed_10m_kmh is None:
        return None
    return float(wind_speed_10m_kmh) * FAO56_WIND_CONVERSION_10M_TO_2M


def saturation_vapour_pressure(temp_c: float) -> float | None:
    """Pressão de vapor saturado (kPa) — FAO-56, equação 11."""
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))


def actual_vapour_pressure(
    temp_c: float | None, humidity_pct: float | None
) -> float | None:
    """Pressão de vapor atual (kPa) a partir da umidade relativa."""
    if temp_c is None or humidity_pct is None:
        return None
    es = saturation_vapour_pressure(temp_c)
    if es is None:
        return None
    return es * (float(humidity_pct) / 100.0)


def vapour_pressure_deficit(
    temp_c: float | None, humidity_pct: float | None
) -> float | None:
    """Déficit de pressão de vapor (kPa)."""
    if temp_c is None or humidity_pct is None:
        return None
    es = saturation_vapour_pressure(temp_c)
    ea = actual_vapour_pressure(temp_c, humidity_pct)
    if es is None or ea is None:
        return None
    return max(0.0, es - ea)


def extraterrestrial_radiation(
    latitude: float, day_of_year: int
) -> float | None:
    """Radiação extraterrestre diária (MJ m-2 dia-1) — FAO-56, eq. 21."""
    if day_of_year < 1 or day_of_year > 366:
        return None
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    phi = math.radians(latitude)
    declination = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    x = max(0.0, min(1.0, -math.tan(phi) * math.tan(declination)))
    ws = math.acos(x)
    ra = (
        (24 * 60 / math.pi)
        * SOLAR_CONSTANT
        * dr
        * (ws * math.sin(phi) * math.sin(declination)
           + math.cos(phi) * math.cos(declination) * math.sin(ws))
    )
    return ra


def fao56_penman_monteith(
    temp_max_c: float | None,
    temp_min_c: float | None,
    temp_mean_c: float | None,
    radiation_mj_m2: float | None,
    wind_speed_10m_kmh: float | None,
    humidity_pct: float | None,
    pressure_kpa: float | None,
    latitude: float,
    day_of_year: int,
    elevation_m: float | None = None,
) -> ETResult:
    """ET0 pelo FAO-56 Penman-Monteith (Allen et al., 1998)."""
    detail: dict[str, Any] = {}
    if temp_max_c is None or temp_min_c is None:
        return ETResult("fao56_penman_monteith", None, False, detail)
    if radiation_mj_m2 is None or wind_speed_10m_kmh is None or humidity_pct is None:
        return ETResult("fao56_penman_monteith", None, False, detail)

    tmean = temp_mean_c
    if tmean is None:
        tmean = (temp_max_c + temp_min_c) / 2.0
    u2 = wind_at_2m(wind_speed_10m_kmh)
    if u2 is None:
        return ETResult("fao56_penman_monteith", None, False, detail)
    u2 = max(0.5, u2)  # limite inferior da FAO-56
    es = saturation_vapour_pressure(tmean)
    ea = actual_vapour_pressure(tmean, humidity_pct)
    if es is None or ea is None:
        return ETResult("fao56_penman_monteith", None, False, detail)
    vpd = es - ea

    if pressure_kpa:
        p = pressure_kpa
    elif elevation_m:
        p = ATMOSPHERIC_PRESSURE_KPA * (1 - 0.0065 * elevation_m / 5.0) ** 5.26
    else:
        p = ATMOSPHERIC_PRESSURE_KPA
    gamma = 0.665e-3 * p
    delta = (4098 * es) / ((tmean + 237.3) ** 2)
    ra = extraterrestrial_radiation(latitude, day_of_year)
    if ra is None:
        return ETResult("fao56_penman_monteith", None, False, detail)

    rs = radiation_mj_m2
    if rs <= 0:
        # sem radiação utilizável: usa Ra como limite superior de Rayleigh
        rs = 0.75 * ra
    rso = 0.75 * ra
    albedo = 0.23
    # radiação de onda longa — FAO-56, equação 39
    # Rnl = sigma * ((Tmax,K^4 + Tmin,K^4)/2) * (0,34 - 0,14*ea)
    #       * (1,35*Rs/Rso - 0,35)
    net_longwave = (
        STEFAN_BOLTZMANN
        * ((temp_max_c + 273.16) ** 4 + (temp_min_c + 273.16) ** 4)
        / 2.0
        * max(0.0, 0.34 - 0.14 * ea)
        * max(0.0, 1.35 * rs / rso - 0.35)
    )
    # radiação líquida de curto comprimento de onda
    rns = (1 - albedo) * rs - net_longwave
    # FAO-56 Penman-Monteith (equação 6):
    # ET0 = [0,408*delta*(Rn-G) + gamma*900/(T+273)*u2*(es-ea)]
    #       / [delta + gamma*(1 + 0,34*u2)]
    numerator = 0.408 * delta * rns + gamma * (900 / (tmean + 273)) * u2 * vpd
    denominator = delta + gamma * (1 + 0.34 * u2)
    if denominator <= 0:
        return ETResult("fao56_penman_monteith", None, False, detail)
    et0 = max(0.0, numerator / denominator)
    detail.update(
        {
            "temp_mean_c": tmean,
            "wind_2m_ms": u2 / 3.6,
            "vpd_kpa": vpd,
            "ra_mj_m2": ra,
            "rs_mj_m2": rs,
            "rns_mj_m2": rns,
            "rnl_mj_m2": net_longwave,
            "delta_kpa_c": delta,
        }
    )
    return ETResult("fao56_penman_monteith", et0, True, detail)
    detail.update(
        {
            "temp_mean_c": tmean,
            "wind_2m_ms": u2 / 3.6,
            "vpd_kpa": vpd,
            "ra_mj_m2": ra,
            "rs_mj_m2": rs,
            "rns_mj_m2": rns,
        }
    )
    return ETResult("fao56_penman_monteith", et0, True, detail)


def thornthwaite_1948(
    temp_mean_c: float | None,
    latitude: float,
    day_of_year: int,
    daylight_hours: float | None = None,
    heat_index: float | None = None,
    exponent: float | None = None,
) -> ETResult:
    """ETP de Thornthwaite (1948), versão do BHCalc (Embrapa/IAC).

    Quando ``heat_index`` e ``exponent`` não são fornecidos, são calculados
    a partir da série anual (12 meses) — ver :func:`thornthwaite_heat_index`.
    """
    detail: dict[str, Any] = {}
    if temp_mean_c is None or heat_index is None or exponent is None:
        return ETResult("thornthwaite_1948", None, False, detail)
    if heat_index <= 0:
        return ETResult("thornthwaite_1948", None, False, detail)
    if temp_mean_c <= 0:
        return ETResult("thornthwaite_1948", 0.0, True, detail)
    base = 16 * (10 * temp_mean_c / heat_index) ** exponent
    # correção de fotoperíodo e de duração do mês (FAO/Thornthwaite)
    factor = 1.0
    if daylight_hours is not None:
        factor *= daylight_hours / 12.0
    days_in_month = _days_in_month(day_of_year)
    factor *= days_in_month / 30.0
    et0 = max(0.0, base * factor)
    detail.update(
        {"heat_index": heat_index, "exponent": exponent, "daylight_factor": factor}
    )
    return ETResult("thornthwaite_1948", et0, True, detail)


def _days_in_month(day_of_year: int) -> int:
    import calendar

    months = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    total = 0
    for length in months:
        total += length
        if day_of_year <= total:
            return length
    return 30


def thornthwaite_heat_index(monthly_means_c: Sequence[float]) -> tuple[float, float]:
    """Índice de calor anual *I* e expoente *a* de Thornthwaite (1948).

    ``I = Σ (Tmed/5)^1,514`` e
    ``a = 6,75e-7 I³ − 7,71e-5 I² + 1,791e-2 I + 0,49239``.
    """
    heat = 0.0
    for mean in monthly_means_c:
        if mean is None or mean <= 0:
            continue
        heat += (float(mean) / 5.0) ** 1.514
    if heat <= 0:
        return 0.0, 0.0
    exponent = (
        6.75e-7 * heat**3
        - 7.71e-5 * heat**2
        + 1.791e-2 * heat
        + 0.49239
    )
    return heat, exponent


def hargreaves_samani(
    temp_max_c: float | None,
    temp_min_c: float | None,
    extraterrestrial_radiation_mj_m2: float | None,
) -> ETResult:
    """ET0 de Hargreaves & Samani (1985)."""
    detail: dict[str, Any] = {}
    if (
        temp_max_c is None
        or temp_min_c is None
        or extraterrestrial_radiation_mj_m2 is None
    ):
        return ETResult("hargreaves_samani", None, False, detail)
    tmean = (temp_max_c + temp_min_c) / 2.0
    range_t = max(0.0, temp_max_c - temp_min_c)
    et0 = max(0.0, 0.0023 * (tmean + 17.8) * math.sqrt(range_t) * extraterrestrial_radiation_mj_m2)
    detail.update({"temp_mean_c": tmean, "temp_range_c": range_t})
    return ETResult("hargreaves_samani", et0, True, detail)


def daily_et0_series(
    daily_records: Sequence[dict[str, Any]],
    latitude: float,
    method: str = "fao56_penman_monteith",
    elevation_m: float | None = None,
    heat_index: float | None = None,
    exponent: float | None = None,
) -> list[dict[str, Any]]:
    """Série diária de ET0 no método escolhido."""
    from datetime import date

    out: list[dict[str, Any]] = []
    for record in sorted(daily_records, key=lambda r: str(r.get("date"))):
        day = str(record.get("date"))
        try:
            parsed = date.fromisoformat(day)
            doy = parsed.timetuple().tm_yday
        except ValueError:
            doy = 1
        if method == "fao56_penman_monteith":
            result = fao56_penman_monteith(
                record.get("temp_max_c"),
                record.get("temp_min_c"),
                record.get("temp_media_c"),
                record.get("radiacao_mj_m2"),
                record.get("vento_kmh"),
                record.get("umidade_rel_pct"),
                record.get("pressao_kpa"),
                latitude,
                doy,
                elevation_m=elevation_m,
            )
        elif method == "thornthwaite_1948":
            result = thornthwaite_1948(
                record.get("temp_media_c"),
                latitude,
                doy,
                heat_index=heat_index,
                exponent=exponent,
            )
        elif method == "hargreaves_samani":
            result = hargreaves_samani(
                record.get("temp_max_c"),
                record.get("temp_min_c"),
                extraterrestrial_radiation(latitude, doy),
            )
        else:
            raise EvapotranspirationError(f"método desconhecido: {method}")
        item = {"date": day}
        item.update(result.to_dict())
        out.append(item)
    return out
