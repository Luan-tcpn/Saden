"""Análise exploratória do painel agroclimático × produtividade.

Todos os métodos são **simples** e reproduzíveis, sem bibliotecas de
modelagem avançada (nenhum XGBoost, Random Forest ou rede neural):

* **Baselines** (os mesmos da V2.3): média histórica, último valor e
  tendência temporal;
* **Validação temporal** (walk-forward / expanding window): treina com anos
  anteriores e testa nos anos seguintes;
* **Validação territorial** (generalização): municipalities inteiros são
  mantidos no treino ou no teste, e **anos do mesmo município não são
  distribuídos aleatoriamente** entre treino e teste;
* **Painel**: regressão com efeitos fixos de município e de ano, erros-padrão
  **agrupados por município** (as observações do mesmo município não são
  independentes).

Nenhuma seleção de variável por correlação é feita: os modelos comparados
são **pré-declarados**.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Sequence

import numpy as np

# Modelos pré-declarados (D70).
MODELS: dict[str, tuple[str, ...]] = {
    "A_baselines": (),
    "B_meteorologicos": ("precip_acumulada_mm", "temp_media_c"),
    "C_thermal": ("degree_days_total", "extreme_heat_days"),
    "D_hidricos": ("et0_total_mm", "deficiency_total_mm", "excess_total_mm"),
}

SEED = 20261112


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def prepare_rows(
    dataset: Sequence[dict[str, Any]],
    crop: str | None = None,
    status: str = "paired_usable",
) -> list[dict[str, Any]]:
    """Filtra o painel e converte os campos numéricos."""
    out: list[dict[str, Any]] = []
    for row in dataset:
        if row.get("status") != status:
            continue
        if crop and str(row.get("crop")) != crop:
            continue
        year = row.get("harvest_year") or row.get("pam_reference_year")
        yield_value = _to_float(row.get("yield_kg_ha"))
        if year is None or yield_value is None:
            continue
        item: dict[str, Any] = {
            "ibge_code": str(row.get("ibge_code")),
            "municipality": row.get("municipality"),
            "state": row.get("state"),
            "crop": str(row.get("crop")),
            "year": int(year),
            "yield_kg_ha": yield_value,
            "climate_source": row.get("climate_source"),
        }
        for key in (
            "precip_acumulada_mm",
            "precip_media_diaria_mm",
            "dias_com_chuva",
            "dias_secos",
            "temp_media_c",
            "temp_max_media_c",
            "temp_min_media_c",
            "radiacao_media_mj_m2",
            "umidade_rel_media_pct",
            "solo_umidade_media",
            "degree_days_total",
            "degree_days_mean",
            "extreme_heat_days",
            "warm_nights",
            "heat_wave_days",
            "et0_total_mm",
            "etp_total_mm",
            "etr_total_mm",
            "deficiency_total_mm",
            "excess_total_mm",
            "storage_final_mm",
            "coverage",
        ):
            item[key] = _to_float(row.get(key))
        out.append(item)
    return out


def baseline_predictions(
    train: Sequence[dict[str, Any]], target: dict[str, Any]
) -> dict[str, float]:
    """Baselines da V2.3: média histórica, último valor e tendência."""
    yields = [float(r["yield_kg_ha"]) for r in train]
    years = [float(r["year"]) for r in train]
    out = {
        "media_historica": float(np.mean(yields)),
        "ultimo_valor": yields[-1],
    }
    if len(set(years)) > 1:
        slope, intercept = np.polyfit(years, yields, 1)
        out["tendencia"] = float(slope * float(target["year"]) + intercept)
    else:
        out["tendencia"] = yields[-1]
    return out


def _ols(
    x: np.ndarray, y: np.ndarray, add_constant: bool = True
) -> tuple[np.ndarray, np.ndarray] | None:
    """Mínimos quadrados Ordinary (com ou sem intercepto)."""
    if x.shape[0] <= x.shape[1] + (1 if add_constant else 0):
        return None
    if add_constant:
        design = np.column_stack([np.ones(x.shape[0]), x])
    else:
        design = x
    try:
        beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    except np.linalg.LinAlgError:
        return None
    residuals = y - design @ beta
    return beta, residuals


def fit_predict(
    train: Sequence[dict[str, Any]],
    test: dict[str, Any],
    variables: Sequence[str],
) -> float | None:
    """Regressão linear das variáveis indicadas; devolve a previsão."""
    if not train:
        return None
    available = [
        v for v in variables
        if v in train[0] and train[0].get(v) is not None
    ]
    if not available:
        return None
    xs = np.array(
        [[float(r.get(v) or 0.0) for v in available] for r in train], dtype="float64"
    )
    ys = np.array([float(r["yield_kg_ha"]) for r in train], dtype="float64")
    if np.std(xs, axis=0).max() == 0:
        return None
    fitted = _ols(xs, ys)
    if fitted is None:
        return None
    beta, _residuals = fitted
    x_test = np.array([[float(test.get(v) or 0.0) for v in available]], dtype="float64")
    prediction = beta[0] + x_test @ beta[1:]
    return float(np.asarray(prediction).ravel()[0])


def walk_forward(
    rows: Sequence[dict[str, Any]],
    variables: Sequence[str] = (),
    min_train: int = 5,
    crop_filter: str | None = None,
) -> dict[str, Any]:
    """Validação temporal progressiva sobre o painel.

    As linhas são ordenadas por (município, ano) para que o treino use
    **apenas anos anteriores** de cada município — a validação temporal é
    simultaneamente temporal e por município (nenhuma informação do ano
    alvo entra no treino, nem de outro município).
    """
    data = [r for r in rows if crop_filter is None or r["crop"] == crop_filter]
    by_municipality: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in data:
        by_municipality[str(row["ibge_code"])].append(row)
    for municipality in by_municipality:
        by_municipality[municipality].sort(key=lambda r: r["year"])

    predictions: list[dict[str, Any]] = []
    for municipality, series in sorted(by_municipality.items()):
        for index in range(min_train, len(series)):
            train = series[:index]
            test = series[index]
            entry: dict[str, Any] = {
                "ibge_code": municipality,
                "year": test["year"],
                "observed": float(test["yield_kg_ha"]),
            }
            for name, value in baseline_predictions(train, test).items():
                entry[name] = value
            if variables:
                prediction = fit_predict(train, test, variables)
                if prediction is not None:
                    entry["modelo"] = prediction
            predictions.append(entry)
    if not predictions:
        return {"status": "insufficient_pairs", "n_predictions": 0, "models": {}}

    models: dict[str, Any] = {}
    names = ["media_historica", "ultimo_valor", "tendencia"]
    if any("modelo" in p for p in predictions):
        names.append("modelo")
    for name in names:
        usable = [p for p in predictions if name in p]
        if not usable:
            continue
        errors = [p[name] - p["observed"] for p in usable]
        observed = [p["observed"] for p in usable]
        models[name] = {
            "n_predictions": len(usable),
            "mae_kg_ha": float(np.mean(np.abs(errors))),
            "rmse_kg_ha": float(np.sqrt(np.mean(np.square(errors)))),
            "mape_percent": float(
                np.mean([abs(e / o) for e, o in zip(errors, observed)]) * 100.0
            ),
        }
    best = min(models, key=lambda k: models[k]["mae_kg_ha"]) if models else None
    return {
        "status": "ok",
        "n_predictions": len(predictions),
        "models": models,
        "best_by_mae": best,
        "predictions": predictions,
    }


def territorial_holdout(
    rows: Sequence[dict[str, Any]],
    variables: Sequence[str],
    n_folds: int = 5,
    crop_filter: str | None = None,
    seed: int = SEED,
    group_key: str = "ibge_code",
) -> dict[str, Any]:
    """Validação territorial:("*fold*") por grupos de municípios.

    Cada *fold* testa um conjunto de municípios **inteiros**; o treino usa os
    demais. Os anos do mesmo município nunca são repartidos entre treino e
    teste.

    ``group_key`` generaliza a unidade de separação (V2.7): ``ibge_code``
    reproduz o protocolo da V2.6; outros valores (célula da grade, bloco
    espacial, UF) impõem partições **mais**-separadas, em que nenhuma
    unidade compartilhando informação espacial fica em lados opostos da
    partição. O padrão mantém o resultado da V2.6 **bit a bit**.
    """
    data = [r for r in rows if crop_filter is None or r["crop"] == crop_filter]
    municipalities = sorted({str(r["ibge_code"]) for r in data})
    groups = sorted({str(r.get(group_key)) for r in data if r.get(group_key)})
    if len(groups) < n_folds:
        return {
            "status": "insufficient_municipalities",
            "n_municipalities": len(municipalities),
            "n_groups": len(groups),
            "group_key": group_key,
        }
    rng = np.random.default_rng(seed)
    shuffled = list(groups)
    rng.shuffle(shuffled)
    folds = [shuffled[i::n_folds] for i in range(n_folds)]

    predictions: list[dict[str, Any]] = []
    for fold_index, fold in enumerate(folds):
        test_groups = set(fold)
        train = [r for r in data if str(r.get(group_key)) not in test_groups]
        test = [r for r in data if str(r.get(group_key)) in test_groups]
        if not train or not test:
            continue
        for row in test:
            entry: dict[str, Any] = {
                "fold": fold_index,
                "ibge_code": row["ibge_code"],
                "year": row["year"],
                "observed": float(row["yield_kg_ha"]),
            }
            for name, value in baseline_predictions(train, row).items():
                entry[name] = value
            prediction = fit_predict(train, row, variables)
            if prediction is not None:
                entry["modelo"] = prediction
            predictions.append(entry)
    if not predictions:
        return {"status": "insufficient_pairs", "n_predictions": 0, "models": {}}
    models: dict[str, Any] = {}
    for name in ("media_historica", "ultimo_valor", "tendencia", "modelo"):
        usable = [p for p in predictions if name in p]
        if not usable:
            continue
        errors = [p[name] - p["observed"] for p in usable]
        observed = [p["observed"] for p in usable]
        models[name] = {
            "n_predictions": len(usable),
            "mae_kg_ha": float(np.mean(np.abs(errors))),
            "rmse_kg_ha": float(np.sqrt(np.mean(np.square(errors)))),
            "mape_percent": float(
                np.mean([abs(e / o) for e, o in zip(errors, observed)]) * 100.0
            ),
        }
    best = min(models, key=lambda k: models[k]["mae_kg_ha"]) if models else None
    return {
        "status": "ok",
        "n_folds": len(folds),
        "group_key": group_key,
        "n_groups": len(groups),
        "n_predictions": len(predictions),
        "models": models,
        "best_by_mae": best,
        "predictions": predictions,
    }


def _blocked_folds(values: Sequence[str], n_folds: int, rng: np.random.Generator) -> list[list[str]]:
    """Reparte ``values`` em ``n_folds`` dobras disjuntas (ordem sorteada)."""
    shuffled = list(values)
    rng.shuffle(shuffled)
    return [shuffled[i::n_folds] for i in range(n_folds)]


def _summarize_predictions(predictions: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """MAE, RMSE e MAPE por modelo, sobre as mesmas predições."""
    models: dict[str, Any] = {}
    for name in ("media_historica", "ultimo_valor", "tendencia", "modelo"):
        usable = [p for p in predictions if name in p]
        if not usable:
            continue
        errors = [p[name] - p["observed"] for p in usable]
        observed = [p["observed"] for p in usable]
        models[name] = {
            "n_predictions": len(usable),
            "mae_kg_ha": float(np.mean(np.abs(errors))),
            "rmse_kg_ha": float(np.sqrt(np.mean(np.square(errors)))),
            "mape_percent": float(
                np.mean([abs(e / o) for e, o in zip(errors, observed)]) * 100.0
            ),
        }
    best = min(models, key=lambda k: models[k]["mae_kg_ha"]) if models else None
    return {"models": models, "best_by_mae": best}


def two_way_blocked_holdout(
    rows: Sequence[dict[str, Any]],
    variables: Sequence[str],
    n_space_folds: int = 5,
    n_time_folds: int = 5,
    crop_filter: str | None = None,
    seed: int = SEED,
    group_key: str = "spatial_block_id",
    time_key: str = "year",
) -> dict[str, Any]:
    """Holdout **espacial e temporal simultâneos** (V2.7, protocolo P5).

    O holdout territorial de :func:`territorial_holdout` separa apenas o
    espaço: uma observação de teste do ano Y é prevista por um treino que
    contém o **mesmo ano** em outros municípios. Como as variáveis
    climáticas têm componente regional comum dentro do ano, o coeficiente
    ajustado pode absorver o choque daquele ano e o modelo parece
    generalizar territorialmente sem que a transferência seja genuína.

    Aqui cada dobra remove do treino, **ao mesmo tempo**, um conjunto de
    grupos espaciais e um conjunto de anos: nenhuma observação de treino
    compartilha grupo espacial nem ano com a observação de teste. O ganho
    que sobrevive a essa partição não pode ser atribuído a informação do
    próprio ano nem a vizinhança geográfica.
    """
    data = [r for r in rows if crop_filter is None or r["crop"] == crop_filter]
    groups = sorted({str(r.get(group_key)) for r in data if r.get(group_key)})
    times = sorted({str(r.get(time_key)) for r in data if r.get(time_key) is not None})
    if len(groups) < n_space_folds or len(times) < 2:
        return {
            "status": "insufficient_groups",
            "n_groups": len(groups),
            "n_times": len(times),
            "group_key": group_key,
            "time_key": time_key,
        }
    rng = np.random.default_rng(seed)
    space_folds = _blocked_folds(groups, n_space_folds, rng)
    time_folds = _blocked_folds(times, n_time_folds, rng)
    predictions: list[dict[str, Any]] = []
    n_folds_used = 0
    for space_fold in space_folds:
        space_set = set(space_fold)
        for time_fold in time_folds:
            time_set = set(time_fold)
            test = [
                r
                for r in data
                if str(r.get(group_key)) in space_set
                and str(r.get(time_key)) in time_set
            ]
            if not test:
                continue
            train = [
                r
                for r in data
                if str(r.get(group_key)) not in space_set
                and str(r.get(time_key)) not in time_set
            ]
            if not train:
                continue
            n_folds_used += 1
            for row in test:
                entry: dict[str, Any] = {
                    "ibge_code": row["ibge_code"],
                    "year": row["year"],
                    "observed": float(row["yield_kg_ha"]),
                }
                for name, value in baseline_predictions(train, row).items():
                    entry[name] = value
                if variables:
                    prediction = fit_predict(train, row, variables)
                    if prediction is not None:
                        entry["modelo"] = prediction
                predictions.append(entry)
    if not predictions:
        return {"status": "insufficient_pairs", "n_predictions": 0, "models": {}}
    summary = _summarize_predictions(predictions)
    return {
        "status": "ok",
        "n_folds": n_folds_used,
        "n_space_folds": n_space_folds,
        "n_time_folds": n_time_folds,
        "group_key": group_key,
        "time_key": time_key,
        "n_groups": len(groups),
        "n_times": len(times),
        "space_folds": space_folds,
        "time_folds": time_folds,
        "n_predictions": len(predictions),
        "models": summary["models"],
        "best_by_mae": summary["best_by_mae"],
        "predictions": predictions,
    }


def _build_fixed_effects_design(
    data: Sequence[dict[str, Any]], variable: str
) -> tuple[np.ndarray, np.ndarray, list[str], list[int], int, int, int]:
    """Monta o design de efeitos fixos de município e de ano.

    Layout do design matrix (índice 1 é a variável climática):
      0                -> intercepto
      1                -> variável climática
      2 .. k_muni      -> dummies de município (o primeiro município é a referência)
      k_muni+1 ..      -> dummies de ano (o primeiro ano é a referência)

    A montagem é extraída de :func:`fixed_effects` para que a V2.7 possa
    reaproveitar **exatamente** o mesmo design em outros esquemas de
    agrupamento, sem criar uma segunda implementação do modelo.
    """
    municipalities = sorted({str(r["ibge_code"]) for r in data})
    years = sorted({r["year"] for r in data})
    muni_index = {m: i for i, m in enumerate(municipalities)}
    year_index = {y: i for i, y in enumerate(years)}
    n = len(data)
    k_muni = len(municipalities)
    k_year = len(years)
    n_muni_dummies = k_muni - 1
    n_year_dummies = k_year - 1
    design = np.zeros((n, 2 + n_muni_dummies + n_year_dummies), dtype="float64")
    y = np.zeros(n, dtype="float64")
    for row_index, row in enumerate(data):
        m = muni_index[str(row["ibge_code"])]
        y_i = year_index[row["year"]]
        design[row_index, 0] = 1.0
        design[row_index, 1] = float(row[variable])
        if m > 0:
            design[row_index, 1 + m] = 1.0
        if y_i > 0:
            design[row_index, 1 + n_muni_dummies + y_i] = 1.0
        y[row_index] = float(row["yield_kg_ha"])
    return design, y, municipalities, years, n, k_muni, k_year


def fixed_effects(
    rows: Sequence[dict[str, Any]],
    variable: str,
    crop_filter: str | None = None,
) -> dict[str, Any]:
    """Regressão de painel com efeitos fixos de município e de ano.

    A variável climática é a única regressor; município e ano entram como
    dummies. O erro-padrão do coeficiente é **agrupado por município**
    (cluster-robust), porque as observações do mesmo município não são
    independentes.
    """
    data = [r for r in rows if crop_filter is None or r["crop"] == crop_filter]
    data = [r for r in data if r.get(variable) is not None]
    if len(data) < 20:
        return {"status": "insufficient_observations", "n": len(data)}
    municipalities = sorted({str(r["ibge_code"]) for r in data})
    years = sorted({r["year"] for r in data})
    if len(municipalities) < 3 or len(years) < 3:
        return {
            "status": "insufficient_dimensions",
            "n_municipalities": len(municipalities),
            "n_years": len(years),
        }
    design, y, municipalities, years, n, k_muni, k_year = _build_fixed_effects_design(
        data, variable
    )
    fitted = _ols(design, y, add_constant=False)
    if fitted is None:
        return {"status": "singular_design", "n": n}
    beta, residuals = fitted
    # erro-padrão agrupado por município (cluster-robust)
    meat = np.zeros((design.shape[1], design.shape[1]))
    groups: dict[str, list[int]] = defaultdict(list)
    for row_index, row in enumerate(data):
        groups[str(row["ibge_code"])].append(row_index)
    for indices in groups.values():
        if len(indices) < 2:
            continue
        block = design[indices, :]
        score = block.T @ residuals[indices]
        meat += np.outer(score, score)
    xtx_inv = np.linalg.pinv(design.T @ design)
    vcv = xtx_inv @ meat @ xtx_inv
    se = float(np.sqrt(max(vcv[1, 1], 0.0)))
    coefficient = float(beta[1])
    t_stat = coefficient / se if se > 0 else None
    return {
        "status": "ok",
        "n": n,
        "n_municipalities": k_muni,
        "n_years": k_year,
        "variable": variable,
        "coefficient": coefficient,
        "std_error_clustered": se,
        "t_statistic": t_stat,
        "r_squared_within": _r_squared(residuals, y),
        "interpretation": (
            "coeficiente da variável climática dentro dos efeitos fixos de "
            "município e de ano; erro-padrão agrupado por município"
        ),
    }


def _r_squared(residuals: np.ndarray, y: np.ndarray) -> float | None:
    total = float(np.sum((y - np.mean(y)) ** 2))
    if total <= 0:
        return None
    return float(1.0 - np.sum(residuals ** 2) / total)


def pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) < 3:
        return None
    xs = np.asarray(x, dtype="float64")
    ys = np.asarray(y, dtype="float64")
    if np.std(xs) == 0 or np.std(ys) == 0:
        return None
    return float(np.corrcoef(xs, ys)[0, 1])


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) < 3:
        return None
    return pearson(_ranks(x).tolist(), _ranks(y).tolist())


def _ranks(values: Sequence[float]) -> np.ndarray:
    array = np.asarray(values, dtype="float64")
    order = np.argsort(array)
    ranks = np.empty(len(array), dtype="float64")
    ranks[order] = np.arange(1, len(array) + 1, dtype="float64")
    ordered = array[order]
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1] == ordered[index]:
            end += 1
        if end > index:
            ranks[order[index : end + 1]] = (index + end + 2) / 2.0
        index = end + 1
    return ranks


def permutation_p(
    x: Sequence[float],
    y: Sequence[float],
    permutations: int = 5000,
    seed: int = SEED,
) -> float | None:
    """p-valor bilateral por permutação (mesmo protocolo da V2.3/V2.5)."""
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


def holm_correction(p_values: dict[str, float]) -> dict[str, float]:
    """Correção de Holm (FWER) para uma família de testes."""
    items = sorted(
        ((key, value) for key, value in p_values.items() if value is not None),
        key=lambda kv: kv[1],
    )
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
