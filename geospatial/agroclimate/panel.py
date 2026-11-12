"""Construção do painel agroclimático × produtividade (V2.6).

Uma linha do painel corresponde a uma **observação** de
(município × cultura × safra × ano de referência × fonte climática).

Regras metodológicas fixas **antes** da análise estatística:

* o **n efetivo** é o número de observações município-ano-cultura **com
  rendimento e clima**; as janelas do ZARC de um mesmo município-ano **não**
  criam observações independentes;
* a fonte climática é identificada por linha (``climate_source``,
  ``climate_source_type``): observação de estação (``station_observation``),
  reanálise (``reanalysis``);
* a máscara do ZARC é **proxy**: a janela é a **recomendação oficial** de
  plantio, não um plantio observado;
* ausências nunca viram zero — a ausência é preservada e a linha é marcada
  como excluída com o motivo;
* o milho 2ª safra é separado do milho principal e a incompatibilidade com
  o alvo agregado (rendimento total do ano) é declarada em cada linha.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from typing import Any, Iterable, Sequence

from agri import pam_panel, season

from . import evapotranspiration as et_module
from . import thermal
from . import water_balance as wb_module

# Termo de cultura -> codigo do produto do IBGE (SIDRA 5457, classificacao 782).
CROP_PRODUCTS = pam_panel.PAM_PRODUCTS

# Safras do painel: Y/Y+1 (soja, milho 1ª) e a 2ª safra de milho.
SEASON_LABELS = [
    f"{year}/{str(year + 1)[-2:]}" for year in range(2016, 2027)
]


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pam_index(records: Sequence[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Índice (município, cultura, ano) → observação da PAM.

    Só entram observações com estado ``observed`` e rendimento positivo: um
    rendimento zero **não** é uma observação de produtividade (a área não foi
    efetivamente colhida) e é preservado na base com o status ``zero``.
    """
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        if record.get("variable_normalized") != "rendimento_medio_kg_ha":
            continue
        code = str(record.get("geography_code") or "")
        crop = str(record.get("crop_code") or "")
        year = str(record.get("reference_year") or "")
        status = record.get("observation_status")
        if status != "observed":
            continue
        value = _to_float(record.get("value_normalized"))
        if value is None or value <= 0:
            continue
        key = (code, crop, year)
        entry = index.setdefault(
            key,
            {
                "yield_kg_ha": value,
                "yield_unit_original": record.get("unit_original"),
                "area_harvested_ha": None,
                "quantity_produced_t": None,
                "source": record.get("dataset_name"),
                "source_id": record.get("dataset_id"),
                "observation_nature": record.get("nature"),
                "acquired_at": record.get("acquired_at"),
            },
        )
        if record.get("variable_normalized") == "rendimento_medio_kg_ha":
            entry["yield_kg_ha"] = value
    return index


def pam_details(records: Sequence[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Índice (município, cultura, ano) → área colhida, quantidade e valor."""
    details: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        code = str(record.get("geography_code") or "")
        crop = str(record.get("crop_code") or "")
        year = str(record.get("reference_year") or "")
        variable = record.get("variable_normalized")
        if variable not in (
            "area_colhida_ha",
            "area_plantada_ha",
            "quantidade_produzida_t",
        ):
            continue
        if record.get("observation_status") != "observed":
            continue
        value = _to_float(record.get("value_normalized"))
        if value is None:
            continue
        entry = details.setdefault((code, crop, year), {})
        entry[variable] = value
    return details


def zarc_windows_by_municipality(
    zarc_rows: Sequence[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Janelas do ZARC por (município, cultura)."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in zarc_rows:
        code = str(row.get("geocodigo") or "")
        culture = str(row.get("cultura") or "")
        grouped[(code, culture)].append(row)
    return grouped


def crop_label_to_key(culture: str) -> str | None:
    """Rótulo do ZARC → chave de cultura do painel."""
    for key, labels in season.CROP_LABELS.items():
        if culture in labels:
            return key
    return None


def build_panel(
    pam_records: Sequence[dict[str, Any]],
    zarc_rows: Sequence[dict[str, Any]],
    climate_series: dict[tuple[str, str], list[dict[str, Any]]],
    municipalities: dict[str, dict[str, Any]],
    soil_profile_key: str = "tipo2_medio",
    et_method: str = "fao56_penman_monteith",
    min_coverage: float = 0.60,
    min_days: int = 30,
    max_risk: int = season.PRIMARY_MAX_RISK,
) -> list[dict[str, Any]]:
    """Monta o painel agroclimático.

    ``climate_series`` é indexado por (geocódigo do município, fonte
    climática) e contém a série **diária** já normalizada.
    """
    yields = pam_index(pam_records)
    details = pam_details(pam_records)
    windows = zarc_windows_by_municipality(zarc_rows)
    soil = wb_module.default_soil_profile(soil_profile_key)
    panel: list[dict[str, Any]] = []

    for (municipality_code, culture), rows in sorted(windows.items()):
        crop = crop_label_to_key(culture)
        if crop is None:
            continue
        by_safra: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_safra[str(row.get("safra"))].append(row)
        for safra, group in sorted(by_safra.items()):
            built = season.build_windows(group, crop, max_risk=max_risk)
            if not built:
                continue
            window = _modal_window(built)
            if window is None:
                continue
            relation = season.pam_year_candidates(safra, crop)
            pam_year = relation.get("primary")
            if pam_year is None:
                continue
            product_code = CROP_PRODUCTS.get("milho" if crop == "milho_2" else crop)
            pam_key = (municipality_code, product_code, str(pam_year))
            pam = yields.get(pam_key)
            months = list(window["months"])
            if not months:
                continue
            start, end = months[0], months[-1]

            for source_key, series in sorted(climate_series.items()):
                code, source_name = source_key
                if code != municipality_code:
                    continue
                daily = [
                    row for row in series
                    if start <= str(row.get("date")) <= end
                ]
                if len(daily) < min_days:
                    panel.append(
                        _empty_row(
                            municipality_code, municipalities, crop, safra,
                            pam_year, source_name, window, months, pam,
                            details.get(pam_key),
                            f"dias climáticos na janela ({len(daily)}) < {min_days}",
                            soil, et_method,
                        )
                    )
                    continue
                row = _build_row(
                    municipality_code, municipalities, crop, safra, pam_year,
                    source_name, daily, window, months, pam, details.get(pam_key),
                    soil, et_method, min_coverage,
                )
                panel.append(row)
    return panel


def _modal_window(windows: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    counts: dict[tuple[int, ...], int] = defaultdict(int)
    for window in windows:
        counts[tuple(window.get("decends") or [])] += 1
    if not counts:
        return None
    best = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    candidates = [w for w in windows if tuple(w.get("decends") or []) == best[0]]
    candidates.sort(key=lambda w: str(w.get("start_date")))
    chosen = dict(candidates[-1])
    chosen["official_combinations"] = best[1]
    chosen["distinct_windows"] = len(counts)
    return chosen


def _empty_row(
    municipality_code: str,
    municipalities: dict[str, dict[str, Any]],
    crop: str,
    safra: str,
    pam_year: int | None,
    source: str,
    window: dict[str, Any],
    months: Sequence[str],
    pam: dict[str, Any] | None,
    detail: dict[str, Any] | None,
    reason: str,
    soil: Any,
    et_method: str,
) -> dict[str, Any]:
    municipality = municipalities.get(municipality_code, {})
    return {
        "ibge_code": municipality_code,
        "municipality": municipality.get("municipality"),
        "state": municipality.get("state"),
        "region": municipality.get("region"),
        "crop": crop,
        "crop_code": CROP_PRODUCTS.get("milho" if crop == "milho_2" else crop),
        "safra": safra,
        "harvest_year": pam_year,
        "yield_kg_ha": (pam or {}).get("yield_kg_ha"),
        "yield_unit_original": (pam or {}).get("yield_unit_original"),
        "area_harvested_ha": (detail or {}).get("area_colhida_ha"),
        "quantity_produced_t": (detail or {}).get("quantidade_produzida_t"),
        "pam_source": (pam or {}).get("source"),
        "pam_source_id": (pam or {}).get("source_id"),
        "pam_observation_nature": (pam or {}).get("observation_nature"),
        "climate_source": source,
        "climate_source_type": None,
        "zarc_window_months": ";".join(months),
        "zarc_window_start": window.get("start_date"),
        "zarc_window_end": window.get("end_date"),
        "zarc_decends": ";".join(str(d) for d in window.get("decends", [])),
        "zarc_soil": window.get("cod_solo"),
        "zarc_cycle": window.get("cod_ciclo"),
        "zarc_risk_max": window.get("max_risk"),
        "zarc_portaria": window.get("portaria"),
        "zarc_official_combinations": window.get("official_combinations"),
        "zarc_distinct_windows": window.get("distinct_windows"),
        "et_method": et_method,
        "soil_profile": soil.key,
        "cad_mm": soil.cad_mm,
        "status": "excluded",
        "exclusion_reason": reason,
    }


def _build_row(
    municipality_code: str,
    municipalities: dict[str, dict[str, Any]],
    crop: str,
    safra: str,
    pam_year: int | None,
    source: str,
    daily: Sequence[dict[str, Any]],
    window: dict[str, Any],
    months: Sequence[str],
    pam: dict[str, Any] | None,
    detail: dict[str, Any] | None,
    soil: Any,
    et_method: str,
    min_coverage: float,
) -> dict[str, Any]:
    municipality = municipalities.get(municipality_code, {})
    latitude = municipality.get("centroid_lat")
    longitude = municipality.get("centroid_lon")
    elevation = municipality.get("elevation_m")

    row = _empty_row(
        municipality_code, municipalities, crop, safra, pam_year, source,
        window, months, pam, detail, "", soil, et_method,
    )
    row["climate_source_type"] = (
        daily[0].get("source_type") if daily else None
    )
    row["station_code"] = daily[0].get("station_code") if daily else None
    row["climate_days"] = len(daily)

    precip = [d.get("precip_mm") for d in daily if d.get("precip_mm") is not None]
    tmax = [d.get("temp_max_c") for d in daily if d.get("temp_max_c") is not None]
    tmin = [d.get("temp_min_c") for d in daily if d.get("temp_min_c") is not None]
    tmean = [d.get("temp_media_c") for d in daily if d.get("temp_media_c") is not None]
    rad = [d.get("radiacao_mj_m2") for d in daily if d.get("radiacao_mj_m2") is not None]
    humidity = [d.get("umidade_rel_pct") for d in daily if d.get("umidade_rel_pct") is not None]
    wind = [d.get("vento_kmh") for d in daily if d.get("vento_kmh") is not None]
    soil_moist = [
        d.get("solo_umidade_0_7")
        for d in daily
        if d.get("solo_umidade_0_7") is not None
    ]

    def mean(values: Sequence[float]) -> float | None:
        return sum(values) / len(values) if values else None

    row["precip_acumulada_mm"] = sum(precip) if precip else None
    row["precip_media_diaria_mm"] = mean(precip)
    row["dias_com_chuva"] = sum(1 for value in precip if value > 0)
    row["dias_secos"] = sum(1 for value in precip if value == 0)
    row["temp_media_c"] = mean(tmean)
    row["temp_max_media_c"] = mean(tmax)
    row["temp_min_media_c"] = mean(tmin)
    row["temp_max_abs_c"] = max(tmax) if tmax else None
    row["temp_min_abs_c"] = min(tmin) if tmin else None
    row["radiacao_media_mj_m2"] = mean(rad)
    row["umidade_rel_media_pct"] = mean(humidity)
    row["vento_media_kmh"] = mean(wind)
    row["solo_umidade_media"] = mean(soil_moist)

    # --- graus-dia (perfil da cultura) -------------------------------------
    profile_key = {
        "soja": "soja_gilmore",
        "milho": "milho_embrapa",
        "milho_2": "milho_embrapa",
    }.get(crop)
    if profile_key:
        profile = thermal.PROFILES[profile_key]
        gdd = thermal.accumulate_degree_days(daily, profile)
        row["thermal_profile"] = profile.key
        row["thermal_profile_label"] = profile.label
        row["degree_days_total"] = gdd["degree_days_total"]
        row["degree_days_mean"] = gdd["degree_days_mean"]
        row["degree_days_days_used"] = gdd["days_used"]
        row["degree_days_coverage"] = gdd["coverage"]
        row["base_temperature_c"] = profile.base_temperature_c
        row["upper_temperature_c"] = profile.upper_temperature_c
        heat = thermal.heat_wave_events(daily, threshold_c=35.0)
        row["heat_wave_events"] = heat["n_events"]
        row["heat_wave_days"] = heat["total_days"]
        extreme = thermal.extreme_heat_days(daily)
        row["extreme_heat_days"] = extreme["extreme_heat_days"]
        row["warm_nights"] = extreme["warm_nights"]

    # --- evapotranspiração e balanço hídrico --------------------------------
    if latitude is not None:
        et_series = et_module.daily_et0_series(
            daily,
            float(latitude),
            method=et_method,
            elevation_m=elevation,
        )
        et_values = [
            item["et0_mm"] for item in et_series if item.get("et0_mm") is not None
        ]
        row["et0_total_mm"] = sum(et_values) if et_values else None
        row["et0_days"] = len(et_values)
        row["et0_mean_mm_dia"] = mean(et_values)
        monthly = wb_module.daily_to_monthly(et_series)
        balance = wb_module.sequential_water_balance(
            monthly, cad_mm=soil.cad_mm, et_method=et_method
        )
        totals = wb_module.aggregate_water_balance(balance)
        row["etp_total_mm"] = totals["etp_total_mm"]
        row["etr_total_mm"] = totals["etr_total_mm"]
        row["deficiency_total_mm"] = totals["deficiency_total_mm"]
        row["excess_total_mm"] = totals["excess_total_mm"]
        row["storage_final_mm"] = totals["storage_final_mm"]
        row["balance_months"] = totals["months"]

    coverage = len(daily) / max(1, len(months) * 30)
    row["coverage"] = coverage
    reasons: list[str] = []
    if pam is None:
        reasons.append("sem rendimento observado do IBGE/PAM")
    if coverage < min_coverage:
        reasons.append(f"cobertura climática ({coverage:.2f}) < {min_coverage}")
    if row.get("degree_days_total") is None:
        reasons.append("sem graus-dia calculável")
    if reasons:
        row["status"] = "excluded"
        row["exclusion_reason"] = "; ".join(reasons)
    else:
        row["status"] = "paired_usable"
        row["exclusion_reason"] = ""
        row["quality_flag"] = (
            "retrospective_mask" if crop == "milho_2" else "paired"
        )
        if crop == "milho_2":
            row["semantic_compatibility"] = (
                "incompativel (PAM publica o total anual de milho, 1a + 2a safras)"
            )
        else:
            row["semantic_compatibility"] = "boa (mesma cultura, mesma area, mesmo ano)"
    return row


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


def read_csv(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))
