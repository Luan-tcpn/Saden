"""Reavaliação estatística (V2.5) — mesmos métodos da V2.3, base ampliada.

Mantém-se o protocolo da V2.3 (Pearson, Spearman, permutação com semente
fixa, correlação detrendizada e validação temporal progressiva com os mesmos
baselines) para que a comparação seja **equivalente**, e acrescentam-se:

* intervalos de confiança por *bootstrap* dos anos;
* correção de Holm para a família de comparações;
* distinção explícita entre **análise principal** (pré-declarada) e
  **análises de sensibilidade** (máscaras, janelas, riscos).
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Sequence

import numpy as np


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    ordered = np.asarray(values)[order]
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[i]:
            j += 1
        if j > i:
            ranks[order[i : j + 1]] = ranks[order[i : j + 1]].mean()
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) < 3:
        return None
    return pearson(_ranks(x).tolist(), _ranks(y).tolist())


def permutation_p(
    x: Sequence[float],
    y: Sequence[float],
    seed: int = 20261112,
    permutations: int = 5000,
) -> float | None:
    if len(x) < 4:
        return None
    observed = pearson(x, y)
    if observed is None:
        return None
    rng = np.random.default_rng(seed)
    ys = np.asarray(y, dtype="float64")
    count = 0
    for _ in range(permutations):
        candidate = pearson(x, rng.permutation(ys).tolist())
        if candidate is not None and abs(candidate) >= abs(observed):
            count += 1
    return float((count + 1) / (permutations + 1))


def bootstrap_ci(
    x: Sequence[float],
    y: Sequence[float],
    seed: int = 20261112,
    iterations: int = 2000,
    alpha: float = 0.05,
) -> tuple[float | None, float | None]:
    """IC do coeficiente de Pearson por bootstrap dos pares (anos)."""
    if len(x) < 4:
        return None, None
    rng = np.random.default_rng(seed)
    xs = np.asarray(x, dtype="float64")
    ys = np.asarray(y, dtype="float64")
    values = []
    n = len(xs)
    for _ in range(iterations):
        index = rng.integers(0, n, n)
        value = pearson(xs[index].tolist(), ys[index].tolist())
        if value is not None:
            values.append(value)
    if len(values) < 50:
        return None, None
    values.sort()
    low = values[int((alpha / 2) * len(values))]
    high = values[min(len(values) - 1, int((1 - alpha / 2) * len(values)))]
    return float(low), float(high)


def detrend(values: Sequence[float], x: Sequence[float]) -> list[float]:
    if len(values) < 3:
        return list(values)
    xs = np.asarray(x, dtype="float64")
    ys = np.asarray(values, dtype="float64")
    slope, intercept = np.polyfit(xs, ys, 1)
    return (ys - (slope * xs + intercept)).tolist()


def holm_correction(p_values: dict[str, float]) -> dict[str, float]:
    """Correção de Holm (FWER) para uma família de testes."""
    items = sorted(((key, value) for key, value in p_values.items() if value is not None),
                   key=lambda kv: kv[1])
    m = len(items)
    adjusted: dict[str, float] = {}
    running = 0.0
    for index, (key, value) in enumerate(items):
        candidate = min(1.0, (m - index) * value)
        running = max(running, candidate)
        adjusted[key] = running
    for key, value in p_values.items():
        if value is None:
            adjusted[key] = None
    return adjusted


def analyze_pairs(
    pairs: Sequence[dict[str, Any]],
    x_field: str,
    y_field: str = "yield_kg_ha",
    seed: int = 20261112,
    permutations: int = 5000,
) -> dict[str, Any]:
    """Análise de um conjunto de pares (x = indicador, y = rendimento)."""
    rows = []
    for row in pairs:
        x = _to_float(row.get(x_field))
        y = _to_float(row.get(y_field))
        if x is None or y is None:
            continue
        year = row.get("pam_reference_year") or row.get("year") or 0
        rows.append((float(year), x, y))
    rows.sort(key=lambda r: r[0])
    years = [r[0] for r in rows]
    xs = [r[1] for r in rows]
    ys = [r[2] for r in rows]
    low, high = bootstrap_ci(xs, ys, seed=seed)
    return {
        "n": len(rows),
        "years": [int(y) for y in years],
        "pearson_r": pearson(xs, ys),
        "spearman_rho": spearman(xs, ys),
        "permutation_p": permutation_p(xs, ys, seed=seed, permutations=permutations),
        "bootstrap_ci95": [low, high],
        "pearson_r_detrended": pearson(
            detrend(xs, years), detrend(ys, years)
        ) if len(rows) >= 4 else None,
        "yield_mean": float(np.mean(ys)) if ys else None,
        "indicator_mean": float(np.mean(xs)) if xs else None,
        "indicator_sd": float(np.std(xs, ddof=1)) if len(xs) > 1 else None,
        "yield_sd": float(np.std(ys, ddof=1)) if len(ys) > 1 else None,
    }


def walk_forward(
    pairs: Sequence[dict[str, Any]],
    x_field: str,
    y_field: str = "yield_kg_ha",
    min_train: int = 5,
    test_years: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Validação temporal progressiva (mesmos baselines da V2.3).

    ``test_years`` fixa o conjunto de anos de teste (com treino = todos os
    anos anteriores a cada um deles). É o que permite comparar fatias com
    n diferentes **nos mesmos anos de teste**, como exige a comparação
    equivalente com a V2.3.
    """
    rows = []
    for row in pairs:
        x = _to_float(row.get(x_field))
        y = _to_float(row.get(y_field))
        if x is None or y is None:
            continue
        year = row.get("pam_reference_year") or row.get("year") or 0
        rows.append((float(year), x, y))
    rows.sort(key=lambda r: r[0])
    if len(rows) <= min_train:
        return {"status": "insufficient_pairs", "n": len(rows), "models": {}}

    predictions: dict[str, list[dict[str, Any]]] = {
        "media_historica": [],
        "ultimo_valor": [],
        "tendencia": [],
        "ols_com_ndvi": [],
    }
    wanted = set(int(y) for y in test_years) if test_years else None
    for index in range(min_train, len(rows)):
        train = rows[:index]
        test = rows[index]
        if wanted is not None and int(test[0]) not in wanted:
            continue
        train_years = [r[0] for r in train]
        # as tuplas são (ano, indicador, rendimento): o alvo é o índice 2
        train_y = [r[2] for r in train]
        train_x = [r[1] for r in train]
        target = test[2]
        models = {
            "media_historica": float(np.mean(train_y)),
            "ultimo_valor": float(train_y[-1]),
        }
        if len(set(train_years)) > 1:
            slope, intercept = np.polyfit(train_years, train_y, 1)
            models["tendencia"] = float(slope * test[0] + intercept)
        else:
            models["tendencia"] = float(train_y[-1])
        if len(set(train_x)) > 1:
            slope, intercept = np.polyfit(train_x, train_y, 1)
            models["ols_com_ndvi"] = float(slope * test[1] + intercept)
        else:
            models["ols_com_ndvi"] = float(train_y[-1])
        for name, prediction in models.items():
            predictions[name].append(
                {
                    "year": int(test[0]),
                    "predicted": prediction,
                    "observed": float(target),
                    "error": float(prediction - target),
                }
            )

    metrics: dict[str, Any] = {}
    for name, rows in predictions.items():
        if not rows:
            continue
        errors = [r["error"] for r in rows]
        observed = [r["observed"] for r in rows]
        metrics[name] = {
            "n_predictions": len(rows),
            "mae_kg_ha": float(np.mean(np.abs(errors))),
            "rmse_kg_ha": float(np.sqrt(np.mean(np.square(errors)))),
            "mape_percent": float(
                np.mean([abs(e / o) for e, o in zip(errors, observed)]) * 100.0
            ),
            "years": [r["year"] for r in rows],
        }
    best = min(metrics, key=lambda k: metrics[k]["mae_kg_ha"]) if metrics else None
    return {
        "status": "ok",
        "n_pairs": len(rows),
        "min_train": min_train,
        "test_years": sorted({int(r["year"]) for r in predictions["media_historica"]}),
        "models": metrics,
        "best_by_mae": best,
        "ndvi_beats_baselines": (
            bool(
                best
                and best == "ols_com_ndvi"
                and metrics["ols_com_ndvi"]["mae_kg_ha"]
                < min(
                    metrics["media_historica"]["mae_kg_ha"],
                    metrics["ultimo_valor"]["mae_kg_ha"],
                    metrics["tendencia"]["mae_kg_ha"],
                )
            )
            if metrics
            else False
        ),
        "predictions": predictions,
    }


def group_pairs(
    dataset: Sequence[dict[str, Any]],
    status: str = "paired_usable",
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Agrupa os pares por (cultura, variante de máscara)."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in dataset:
        if row.get("status") != status:
            continue
        groups[(str(row.get("crop")), str(row.get("mask_variant")))].append(row)
    return groups


def group_pairs_by_mode(
    dataset: Sequence[dict[str, Any]],
    mode: str,
    status: str = "paired_usable",
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Agrupa os pares de uma fatia de pareamento por (cultura, máscara)."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in dataset:
        if row.get("status") != status:
            continue
        if str(row.get("pairing_mode")) != mode:
            continue
        groups[(str(row.get("crop")), str(row.get("mask_variant")))].append(row)
    return groups


def representativity(
    municipal_rows: Sequence[dict[str, Any]],
    aoi_rows: Sequence[dict[str, Any]],
    mask_variant: str = "stable",
) -> dict[str, Any]:
    """Representatividade da AOI em relação ao município (Fase 2, §4.6).

    Compara, mês a mês, o NDVI agrícola **municipal** (máscara `mask_variant`)
    com o NDVI da **AOI** da V2.3, e mede a estabilidade dessa diferença ao
    longo de 2017–2025. A conclusão fica restrita ao que os dados mostram: a
    AOI é uma sub-região (0,4654% da área municipal) e o seu NDVI **não**
    representa a estatística municipal.
    """
    municipal: dict[str, float] = {}
    for row in municipal_rows:
        if str(row.get("mask_variant")) != mask_variant:
            continue
        value = _to_float(row.get("ndvi_mean"))
        month = str(row.get("month"))
        if value is not None and month:
            municipal[month] = value

    aoi: dict[str, float] = {}
    aoi_coverage: dict[str, float] = {}
    for row in aoi_rows:
        if str(row.get("status")) != "observed":
            continue
        value = _to_float(row.get("ndvi_mean"))
        month = str(row.get("month"))
        if value is not None and month:
            aoi[month] = value
            coverage = _to_float(row.get("valid_fraction"))
            aoi_coverage[month] = coverage if coverage is not None else 0.0

    common = sorted(set(municipal) & set(aoi))
    if not common:
        return {"status": "sem meses comuns", "n_months": 0}
    diffs = [municipal[m] - aoi[m] for m in common]
    years = sorted({m[:4] for m in common})
    by_year: dict[str, dict[str, float]] = {}
    for year in years:
        months = [m for m in common if m.startswith(year)]
        year_diffs = [municipal[m] - aoi[m] for m in months]
        by_year[year] = {
            "n_months": len(months),
            "municipal_mean": float(np.mean([municipal[m] for m in months])),
            "aoi_mean": float(np.mean([aoi[m] for m in months])),
            "mean_difference": float(np.mean(year_diffs)),
            "max_abs_difference": float(np.max(np.abs(year_diffs))),
        }
    return {
        "status": "ok",
        "n_months": len(common),
        "months": common,
        "municipal_mean": float(np.mean([municipal[m] for m in common])),
        "aoi_mean": float(np.mean([aoi[m] for m in common])),
        "mean_difference": float(np.mean(diffs)),
        "sd_difference": float(np.std(diffs, ddof=1)) if len(diffs) > 1 else None,
        "min_difference": float(np.min(diffs)),
        "max_difference": float(np.max(diffs)),
        "pearson_r": pearson(
            [municipal[m] for m in common], [aoi[m] for m in common]
        ),
        "spearman_rho": spearman(
            [municipal[m] for m in common], [aoi[m] for m in common]
        ),
        "by_year": by_year,
        "mean_yearly_difference": float(
            np.mean([v["mean_difference"] for v in by_year.values()])
        ),
        "sd_yearly_difference": (
            float(np.std([v["mean_difference"] for v in by_year.values()], ddof=1))
            if len(by_year) > 1
            else None
        ),
        "note": (
            "A AOI cobre 0,4654% da área do município; a diferença média "
            "mensal e sua estabilidade por ano medem a representatividade — "
            "não validam produtividade."
        ),
    }
