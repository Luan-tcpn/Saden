"""Auditoria de qualidade das séries meteorológicas.

Regras aplicadas (todas registradas no relatório de qualidade):

* **valores ausentes** (``-9999`` do INMET, ``None``) **nunca** viram zero;
* **precipitação zero** (chuva registrada igual a zero) é preservada como
  zero — é uma observação;
* **temperaturas impossíveis** (Tmin > Tmax, Tmax fora de [−50, 60] °C,
  Tmin fora de [−50, 45] °C) são marcadas como inválidas, não corrigidas;
* **precipitação negativa** é inválida;
* **umidade relativa** fora de [0, 100] % é inválida;
* **radiação negativa** é inválida;
* **pressão** fora de [70, 110] kPa é inválida;
* **datas duplicadas** e **horários repetidos** são contabilizados;
* **descontinuidade** (lacuna ≥ N dias) é registrada.

A auditoria **não** substitui nem interpola: o valor original é preservado e
a flag de qualidade acompanha o registro.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

# Faixas físicas de aceitação.
TEMP_MAX_MIN_C = -50.0
TEMP_MAX_MAX_C = 60.0
TEMP_MIN_MIN_C = -50.0
TEMP_MIN_MAX_C = 45.0
PRESSURE_MIN_KPA = 70.0
PRESSURE_MAX_KPA = 110.0
HUMIDITY_MIN_PCT = 0.0
HUMIDITY_MAX_PCT = 100.0
WIND_MAX_KMH = 200.0
RADIATION_MAX_MJ_M2 = 45.0

# Lacuna (dias) que caracteriza descontinuidade.
DISCONTINUITY_GAP_DAYS = 5

# Cobertura mínima (fração de dias com observação) aceita para um período.
MIN_COVERAGE = 0.70

PHYSICAL_RANGES = {
    "temp_max_c": (TEMP_MAX_MIN_C, TEMP_MAX_MAX_C),
    "temp_min_c": (TEMP_MIN_MIN_C, TEMP_MIN_MAX_C),
    "temp_media_c": (TEMP_MAX_MIN_C, TEMP_MAX_MAX_C),
    "umidade_rel_pct": (HUMIDITY_MIN_PCT, HUMIDITY_MAX_PCT),
    "pressao_kpa": (PRESSURE_MIN_KPA, PRESSURE_MAX_KPA),
    "vento_kmh": (0.0, WIND_MAX_KMH),
    "radiacao_mj_m2": (0.0, RADIATION_MAX_MJ_M2),
}


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def audit_series(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Audita uma série diária e devolve o relatório e os registros corrigidos.

    Nenhum valor é substituído: as observações fora da faixa física são
    marcadas com ``invalid_<variavel>`` e o valor original é preservado em
    ``raw_<variavel>``.
    """
    from datetime import date

    ordered = sorted(records, key=lambda r: str(r.get("date")))
    seen_dates: dict[str, int] = {}
    duplicates = 0
    invalid: dict[str, int] = {}
    missing: dict[str, int] = {}
    present: dict[str, int] = {}
    gaps: list[dict[str, Any]] = []
    previous: date | None = None
    cleaned: list[dict[str, Any]] = []

    for record in ordered:
        item = dict(record)
        day_text = str(item.get("date") or "")
        try:
            day = date.fromisoformat(day_text)
        except ValueError:
            item["quality_status"] = "invalid_date"
            cleaned.append(item)
            continue
        if day_text in seen_dates:
            duplicates += 1
            item["quality_status"] = "duplicate_date"
            cleaned.append(item)
            continue
        seen_dates[day_text] = 1
        if previous is not None:
            delta = (day - previous).days
            if delta > DISCONTINUITY_GAP_DAYS:
                gaps.append(
                    {
                        "from": previous.isoformat(),
                        "to": day.isoformat(),
                        "days": delta - 1,
                    }
                )
        previous = day

        flags: list[str] = []
        for variable, (low, high) in PHYSICAL_RANGES.items():
            value = _to_float(item.get(variable))
            if value is None:
                missing[variable] = missing.get(variable, 0) + 1
                continue
            present[variable] = present.get(variable, 0) + 1
            if value < low or value > high:
                flags.append(f"invalid_{variable}")
                invalid[variable] = invalid.get(variable, 0) + 1
                item[f"raw_{variable}"] = value
                item[variable] = None
        precip = _to_float(item.get("precip_mm"))
        if precip is not None:
            present["precip_mm"] = present.get("precip_mm", 0) + 1
            if precip < 0:
                flags.append("invalid_precip_mm")
                invalid["precip_mm"] = invalid.get("precip_mm", 0) + 1
                item["raw_precip_mm"] = precip
                item["precip_mm"] = None
        else:
            missing["precip_mm"] = missing.get("precip_mm", 0) + 1
        tmax = _to_float(item.get("temp_max_c"))
        tmin = _to_float(item.get("temp_min_c"))
        if tmax is not None and tmin is not None and tmin > tmax:
            flags.append("inconsistent_temp_range")
            invalid["temp_range"] = invalid.get("temp_range", 0) + 1
        item["quality_flags"] = ";".join(flags) if flags else ""
        item["quality_status"] = "ok" if not flags else "flagged"
        cleaned.append(item)

    total_days = len(seen_dates)
    coverage = {
        variable: (present.get(variable, 0) / total_days if total_days else 0.0)
        for variable in sorted(set(list(present) + list(missing)))
    }
    return {
        "n_records": len(ordered),
        "n_unique_days": total_days,
        "duplicate_dates": duplicates,
        "invalid_counts": invalid,
        "missing_counts": missing,
        "coverage": coverage,
        "discontinuities": gaps,
        "n_discontinuities": len(gaps),
        "records": cleaned,
    }


def period_coverage(
    records: Sequence[dict[str, Any]], start: str, end: str
) -> dict[str, Any]:
    """Cobertura de um período (dias observados / dias do intervalo)."""
    from datetime import date

    try:
        begin = date.fromisoformat(start)
        finish = date.fromisoformat(end)
    except ValueError:
        return {"days_expected": 0, "days_observed": 0, "coverage": None}
    expected = (finish - begin).days + 1
    observed = 0
    for record in records:
        day = str(record.get("date"))
        if start <= day <= end:
            observed += 1
    return {
        "days_expected": max(0, expected),
        "days_observed": observed,
        "coverage": (observed / expected) if expected > 0 else None,
    }


def is_usable_period(coverage: float | None, minimum: float = MIN_COVERAGE) -> bool:
    """Critério de cobertura mínima de um período."""
    return coverage is not None and coverage >= minimum
