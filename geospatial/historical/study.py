"""Estudo exploratório municipal (V2.3) — pareamento e estatísticas.

Escala de referência: **rendimento médio municipal do IBGE/PAM** (kg/ha),
município de Sorriso-MT (5107925). O indicador geoespacial é o NDVI da AOI de
validação (43,26 km² = 0,4654% do município) — uma **sub-região** do
município, não o município. Toda saída carrega essa limitação (D47).
"""

from __future__ import annotations

import csv
import math
import os
from typing import Any, Iterable, Sequence

import numpy as np

# culturas-piloto (D49)
PILOT_CROPS = {
    "soja": {"ibge_code": "40124", "name": "Soja"},
    "milho": {"ibge_code": "40122", "name": "Milho"},
}

YIELD_VARIABLE = "rendimento_medio_kg_ha"
QUANTITY_VARIABLE = "quantidade_produzida_t"
AREA_VARIABLE = "area_colhida_ha"


# ------------------------------------------------------------------ leituras


def load_base(path: str) -> list[dict[str, Any]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_monthly(path: str) -> list[dict[str, Any]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _to_float(value: Any) -> float | None:
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_yields(
    base_rows: Iterable[dict[str, Any]],
    municipality: str = "5107925",
) -> dict[str, dict[str, dict[str, Any]]]:
    """Rendimento/área/quantidade do IBGE por ano e cultura-piloto.

    A unidade original (kg/ha) é preservada; a normalização para kg/ha é
    **identidade** (o IBGE já publica em kg/ha) e fica registrada como tal.
    """
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for row in base_rows:
        if row.get("institution") != "IBGE":
            continue
        if str(row.get("geography_code")) != municipality:
            continue
        if row.get("crop_scope") not in (None, "", "produto"):
            continue
        code = str(row.get("crop_code"))
        crop_key = next(
            (key for key, meta in PILOT_CROPS.items() if meta["ibge_code"] == code),
            None,
        )
        if crop_key is None:
            continue
        year = str(row.get("reference_year") or "")
        if not year:
            continue
        entry = out.setdefault(crop_key, {}).setdefault(
            year,
            {
                "crop": crop_key,
                "crop_name": PILOT_CROPS[crop_key]["name"],
                "ibge_code": code,
                "year": year,
                "yield_kg_ha": None,
                "yield_unit_original": row.get("unit_original"),
                "area_harvested_ha": None,
                "quantity_produced_t": None,
                "nature": row.get("nature"),
                "source": row.get("dataset_name"),
                "source_id": row.get("dataset_id"),
                "acquired_at": row.get("acquired_at"),
            },
        )
        variable = row.get("variable_normalized")
        value = _to_float(row.get("value_normalized"))
        if variable == YIELD_VARIABLE:
            entry["yield_kg_ha"] = value
        elif variable == AREA_VARIABLE:
            entry["area_harvested_ha"] = value
        elif variable == QUANTITY_VARIABLE:
            entry["quantity_produced_t"] = value
    return out


def yearly_indicators(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Indicadores anuais do NDVI da AOI (a partir da série mensal).

    Agregação por **ano civil** (única janela defensável sem calendário
    fenológico validado — ver limitação registrada).
    """
    by_year: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("status") != "observed":
            continue
        year = str(row.get("month"))[:4]
        by_year.setdefault(year, []).append(row)

    out: dict[str, dict[str, Any]] = {}
    for year, items in sorted(by_year.items()):
        means = [float(r["ndvi_mean"]) for r in items if r.get("ndvi_mean")]
        medians = [float(r["ndvi_median"]) for r in items if r.get("ndvi_median")]
        coverages = [float(r["valid_fraction"]) for r in items if r.get("valid_fraction")]
        months = [str(r.get("month")) for r in items]
        out[year] = {
            "year": year,
            "months_observed": len(items),
            "months": sorted(months),
            "ndvi_mean_of_monthly_means": float(np.mean(means)) if means else None,
            "ndvi_median_of_monthly_medians": float(np.median(medians)) if medians else None,
            "ndvi_min_monthly_mean": float(np.min(means)) if means else None,
            "ndvi_max_monthly_mean": float(np.max(means)) if means else None,
            "ndvi_std_of_monthly_means": float(np.std(means, ddof=1)) if len(means) > 1 else None,
            "mean_valid_fraction": float(np.mean(coverages)) if coverages else None,
            "min_valid_fraction": float(np.min(coverages)) if coverages else None,
            "baselines": sorted({str(r.get("baseline")) for r in items}),
            "items": [r.get("item_id") for r in items],
            "collections": sorted({str(r.get("catalog")) for r in items}),
        }
    return out


# ---------------------------------------------------------------- pareamento


def build_dataset(
    yields: dict[str, dict[str, dict[str, Any]]],
    indicators: dict[str, dict[str, Any]],
    min_coverage: float = 0.5,
    min_months: int = 3,
) -> list[dict[str, Any]]:
    """Constrói o conjunto pareado (um registro por cultura × ano)."""
    dataset: list[dict[str, Any]] = []
    for crop_key, meta in PILOT_CROPS.items():
        years = sorted(set(yields.get(crop_key, {})) | set(indicators))
        for year in years:
            y = yields.get(crop_key, {}).get(year)
            g = indicators.get(year)
            record: dict[str, Any] = {
                "crop": crop_key,
                "crop_name": meta["name"],
                "ibge_code": meta["ibge_code"],
                "year": year,
                "yield_kg_ha": y.get("yield_kg_ha") if y else None,
                "yield_unit_normalized": "kg/ha",
                "yield_unit_original": y.get("yield_unit_original") if y else None,
                "area_harvested_ha": y.get("area_harvested_ha") if y else None,
                "quantity_produced_t": y.get("quantity_produced_t") if y else None,
                "ndvi_aoi_mean": g.get("ndvi_mean_of_monthly_means") if g else None,
                "ndvi_aoi_median": g.get("ndvi_median_of_monthly_medians") if g else None,
                "ndvi_aoi_std": g.get("ndvi_std_of_monthly_means") if g else None,
                "ndvi_aoi_min": g.get("ndvi_min_monthly_mean") if g else None,
                "ndvi_aoi_max": g.get("ndvi_max_monthly_mean") if g else None,
                "ndvi_months_observed": g.get("months_observed") if g else None,
                "ndvi_months": ";".join(g.get("months", [])) if g else None,
                "ndvi_mean_coverage": g.get("mean_valid_fraction") if g else None,
                "ndvi_min_coverage": g.get("min_valid_fraction") if g else None,
                "s2_baselines": ";".join(g.get("baselines", [])) if g else None,
                "s2_items": ";".join(str(i) for i in (g.get("items") or [])) if g else None,
                "scl_profile": "B_restrictive",
                "radiometry_profiles": "C1_harmonized|original_dn_convention",
                "aggregation_window": "ano_civil",
                "calendar_reference": "none_validated",
                "spatial_scope": "AOI de validacao (sub-regiao do municipio)",
                "source": "IBGE/SIDRA PAM 5457 + Sentinel-2 (AOI de validacao)",
                "status": "unpaired",
                "exclusion_reason": None,
                "quality_flag": None,
            }
            reasons: list[str] = []
            if y is None or record["yield_kg_ha"] is None:
                reasons.append("sem rendimento oficial (IBGE/PAM)")
            if g is None or record["ndvi_aoi_mean"] is None:
                reasons.append("sem observacao Sentinel-2 no ano")
            else:
                if (record["ndvi_months_observed"] or 0) < min_months:
                    reasons.append(
                        f"meses observados ({record['ndvi_months_observed']}) < {min_months}"
                    )
                if (record["ndvi_mean_coverage"] or 0.0) < min_coverage:
                    reasons.append(
                        f"cobertura média ({record['ndvi_mean_coverage']:.2f}) < {min_coverage}"
                    )
            if reasons:
                record["status"] = "excluded"
                record["exclusion_reason"] = "; ".join(reasons)
                record["quality_flag"] = "unusable"
            else:
                record["status"] = "paired_usable"
                record["quality_flag"] = (
                    "paired_with_caveats"
                    if (record["ndvi_months_observed"] or 0) < 6
                    or (record["ndvi_mean_coverage"] or 1.0) < 0.8
                    else "paired"
                )
            dataset.append(record)
    return dataset


# ------------------------------------------------------------- estatísticas


def pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) < 3:
        return None
    xs = np.asarray(x, dtype="float64")
    ys = np.asarray(y, dtype="float64")
    if np.std(xs) == 0 or np.std(ys) == 0:
        return None
    return float(np.corrcoef(xs, ys)[0, 1])


def _ranks(values: Sequence[float]) -> np.ndarray:
    order = np.argsort(values)
    ranks = np.empty(len(values), dtype="float64")
    ranks[order] = np.arange(1, len(values) + 1, dtype="float64")
    # média de ranks para empates
    sorted_values = np.asarray(values)[order]
    i = 0
    while i < len(sorted_values):
        j = i
        while j + 1 < len(sorted_values) and sorted_values[j + 1] == sorted_values[i]:
            j += 1
        if j > i:
            ranks[order[i : j + 1]] = ranks[order[i : j + 1]].mean()
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) < 3:
        return None
    return pearson(_ranks(x).tolist(), _ranks(y).tolist())


def linear_slope(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Coeficiente angular da reta (unidade de y por unidade de x)."""
    if len(x) < 2:
        return None
    xs = np.asarray(x, dtype="float64")
    ys = np.asarray(y, dtype="float64")
    if np.std(xs) == 0:
        return None
    slope, _ = np.polyfit(xs, ys, 1)
    return float(slope)


def detrend(values: Sequence[float], x: Sequence[float]) -> list[float]:
    """Resíduos da tendência linear (teste de confusão por tendência)."""
    if len(values) < 3:
        return list(values)
    xs = np.asarray(x, dtype="float64")
    ys = np.asarray(values, dtype="float64")
    slope, intercept = np.polyfit(xs, ys, 1)
    return (ys - (slope * xs + intercept)).tolist()


def permutation_p_value(
    x: Sequence[float],
    y: Sequence[float],
    seed: int = 20261111,
    permutations: int = 5000,
) -> float | None:
    """p-valor por permutação (bilateral) da correlação de Pearson."""
    if len(x) < 4:
        return None
    observed = pearson(x, y)
    if observed is None:
        return None
    rng = np.random.default_rng(seed)
    ys = np.asarray(y, dtype="float64")
    count = 0
    for _ in range(permutations):
        shuffled = rng.permutation(ys)
        candidate = pearson(x, shuffled.tolist())
        if candidate is not None and abs(candidate) >= abs(observed):
            count += 1
    return float((count + 1) / (permutations + 1))


def exploratory_stats(
    dataset: Sequence[dict[str, Any]],
    permutations: int = 5000,
) -> dict[str, Any]:
    """Estatísticas exploratórias por cultura (sem inferência causal)."""
    out: dict[str, Any] = {"crops": {}, "notes": []}
    for crop_key in PILOT_CROPS:
        usable = [
            row
            for row in dataset
            if row["crop"] == crop_key and row["status"] == "paired_usable"
        ]
        usable.sort(key=lambda r: r["year"])
        years = [float(r["year"]) for r in usable]
        yields = [float(r["yield_kg_ha"]) for r in usable]
        ndvi = [float(r["ndvi_aoi_mean"]) for r in usable]
        entry: dict[str, Any] = {
            "n_pairs": len(usable),
            "years": [r["year"] for r in usable],
            "yield_kg_ha_mean": float(np.mean(yields)) if yields else None,
            "yield_kg_ha_min": float(np.min(yields)) if yields else None,
            "yield_kg_ha_max": float(np.max(yields)) if yields else None,
            "ndvi_aoi_mean": float(np.mean(ndvi)) if ndvi else None,
            "ndvi_aoi_min": float(np.min(ndvi)) if ndvi else None,
            "ndvi_aoi_max": float(np.max(ndvi)) if ndvi else None,
            "pearson_r": pearson(ndvi, yields),
            "spearman_rho": spearman(ndvi, yields),
            "permutation_p": permutation_p_value(ndvi, yields, permutations=permutations),
            "yield_trend_per_year": linear_slope(years, yields) if yields else None,
            "ndvi_trend_per_year": linear_slope(years, ndvi) if ndvi else None,
        }
        if len(usable) >= 4:
            entry["pearson_r_detrended"] = pearson(
                detrend(ndvi, years), detrend(yields, years)
            )
        out["crops"][crop_key] = entry
    out["notes"].append(
        "Correlações exploratórias: n reduzido, Spatial scale mismatch "
        "(rendimento municipal x NDVI de uma sub-região de 0,4654% do "
        "município) e ausência de controle de tendências e de outras lavouras."
    )
    return out


def gate_evaluation(stats: dict[str, Any], minimum_pairs: int = 9) -> dict[str, Any]:
    """Portão estatístico: só habilita modelagem se n ≥ mínimo por cultura."""
    per_crop = {
        crop: (entry.get("n_pairs") or 0) >= minimum_pairs
        for crop, entry in stats.get("crops", {}).items()
    }
    return {
        "minimum_pairs_required": minimum_pairs,
        "per_crop_meets_minimum": per_crop,
        "modeling_gate_open": all(per_crop.values()) if per_crop else False,
        "note": (
            "Com menos de 9 pares anuais por cultura, a modelagem exploratória "
            "não é executada (critério definido na V2.2/V2.3)."
        ),
    }


def write_dataset_csv(rows: Sequence[dict[str, Any]], path: str) -> str:
    if not rows:
        return path
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fields = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def read_dataset_csv(path: str) -> list[dict[str, Any]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))
