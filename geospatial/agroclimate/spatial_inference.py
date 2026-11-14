"""Inferência espacialmente robusta do painel agroclimático (V2.7).

A V2.6 reportou significância com erro-padrão agrupado por **município** e
declarou (D75) que a dependência espacial introduzida pela grade
meteorológica não estava controlada. A V2.7 mede essa dependência e constrói
a inferência sobre a escala correta.

Estratégia computacional
-------------------------
A regressão de efeitos fixos de município **e** de ano tem ~1.250 colunas de
dummies. Regressar assim em cada iteração de um bootstrap seria caro. Este
módulo usa o **estimador within** (transformação dedemean em duas direções),
que é matematicamente equivalente à regressão de dummies para o coeficiente
de interesse (FWL): o coeficiente estimado é o mesmo, e apenas o estimador
da variância muda na correção de amostra pequena.

Todos os esquemas de agrupamento e o estimador de Conley são aplicados sobre
os dados *within*, o que torna a inferência espacialmente robusta viável em
tempo razoável. A equivalência do coeficiente com a LSDV da V2.6 é
**verificada numericamente** em :func:`within_coefficient_matches_lsdv`.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Sequence

import numpy as np

from . import robust

# Nomes dos esquemas de agrupamento suportados.
SCHEME_MUNICIPALITY = "municipio"
SCHEME_GRID_CELL = "celula_grade"
SCHEME_SPATIAL_BLOCK = "bloco_espacial"
SCHEME_STATE = "uf"


# --------------------------------------------------------------------------
# Transformação within (dummies de município e de ano).
# --------------------------------------------------------------------------
def within_transform(
    values: np.ndarray,
    group_a: Sequence[Any],
    group_b: Sequence[Any],
    tol: float = 1e-12,
    max_iter: int = 200,
) -> np.ndarray:
    """Demean em duas direções (município e ano) por projeções alternadas.

    Para painéis desbalanceados o demeaning simultâneo exato não existe em
    forma fechada; as projeções alternadas convergem para a solução dos
    mínimos quadrados do demeaning duplo (o estimador within).
    """
    x = np.asarray(values, dtype="float64").copy()
    codes_a: dict[Any, int] = {}
    codes_b: dict[Any, int] = {}
    for index, value in enumerate(group_a):
        codes_a.setdefault(value, len(codes_a))
    for index, value in enumerate(group_b):
        codes_b.setdefault(value, len(codes_b))
    idx_a = np.array([codes_a[v] for v in group_a], dtype="int64")
    idx_b = np.array([codes_b[v] for v in group_b], dtype="int64")
    n_a = len(codes_a)
    n_b = len(codes_b)
    count_a = np.bincount(idx_a, minlength=n_a).astype("float64")
    count_b = np.bincount(idx_b, minlength=n_b).astype("float64")
    sum_a = np.bincount(idx_a, weights=x, minlength=n_a)
    sum_b = np.bincount(idx_b, weights=x, minlength=n_b)
    previous = x.copy()
    for _ in range(max_iter):
        x = x - sum_a[idx_a] / count_a[idx_a]
        sum_b = np.bincount(idx_b, weights=x, minlength=n_b)
        x = x - sum_b[idx_b] / count_b[idx_b]
        sum_a = np.bincount(idx_a, weights=x, minlength=n_a)
        delta = float(np.max(np.abs(x - previous)))
        previous = x.copy()
        if delta < tol:
            break
    return x


def _group_codes(values: Sequence[Any]) -> list[str]:
    out: list[str] = []
    seen: dict[Any, str] = {}
    for value in values:
        if value not in seen:
            seen[value] = f"g{len(seen):06d}"
        out.append(seen[value])
    return out


def within_data(
    rows: Sequence[dict[str, Any]],
    variable: str,
    crop_filter: str | None = None,
) -> dict[str, Any]:
    """Prepara os dados *within* (x, y, grupos) do painel."""
    data = [r for r in rows if crop_filter is None or r["crop"] == crop_filter]
    data = [r for r in data if r.get(variable) is not None]
    if len(data) < 20:
        return {"status": "insufficient_observations", "n": len(data)}
    municipalities = [str(r["ibge_code"]) for r in data]
    years = [r["year"] for r in data]
    if len(set(municipalities)) < 3 or len(set(years)) < 3:
        return {
            "status": "insufficient_dimensions",
            "n_municipalities": len(set(municipalities)),
            "n_years": len(set(years)),
        }
    x = np.array([float(r[variable]) for r in data], dtype="float64")
    y = np.array([float(r["yield_kg_ha"]) for r in data], dtype="float64")
    x_w = within_transform(x, municipalities, years)
    y_w = within_transform(y, municipalities, years)
    return {
        "status": "ok",
        "rows": data,
        "n": len(data),
        "x": x,
        "y": y,
        "x_within": x_w,
        "y_within": y_w,
        "municipalities": municipalities,
        "years": years,
        "n_municipalities": len(set(municipalities)),
        "n_years": len(set(years)),
        "variable": variable,
    }


def within_coefficient_matches_lsdv(
    rows: Sequence[dict[str, Any]],
    variable: str,
    crop_filter: str | None = None,
    tolerance: float = 1e-6,
) -> dict[str, Any]:
    """Verifica que o estimador within reproduz o coeficiente da LSDV.

    A equivalência é a base da escolha computacional do módulo: se o
    coeficiente coincide, a inferência espacial pode ser calculada sobre os
    dados *within* sem alterar o ponto estimado.
    """
    from .analysis import _build_fixed_effects_design, _ols

    prepared = within_data(rows, variable, crop_filter)
    if prepared.get("status") != "ok":
        return prepared
    data = prepared["rows"]
    design, y, municipalities, years, n, k_muni, k_year = _build_fixed_effects_design(
        data, variable
    )
    fitted = _ols(design, y, add_constant=False)
    if fitted is None:
        return {"status": "singular_design"}
    beta_lsdv = float(fitted[0][1])
    x_w = prepared["x_within"]
    y_w = prepared["y_within"]
    denominator = float(np.dot(x_w, x_w))
    if denominator <= 0:
        return {"status": "degenerate_within"}
    beta_within = float(np.dot(x_w, y_w) / denominator)
    difference = abs(beta_within - beta_lsdv)
    scale = max(abs(beta_lsdv), 1.0)
    return {
        "status": "ok",
        "variable": variable,
        "crop": crop_filter,
        "n": n,
        "coefficient_lsdv": beta_lsdv,
        "coefficient_within": beta_within,
        "absolute_difference": difference,
        "relative_difference": difference / scale,
        "matches": difference / scale <= tolerance,
        "tolerance": tolerance,
    }


# --------------------------------------------------------------------------
# Inferência agrupada sobre os dados within.
# --------------------------------------------------------------------------
def _clustered_se(
    x: np.ndarray,
    y: np.ndarray,
    groups: Sequence[str],
    correction: str = robust.CR1,
) -> tuple[float, int, dict[str, Any]]:
    """Erro-padrão agrupado do modelo within (uma regressor + intercepto)."""
    n = len(x)
    groups_list = list(groups)
    unique = sorted(set(groups_list))
    if len(unique) < 2:
        return float("nan"), len(unique), {}
    index: dict[str, list[int]] = defaultdict(list)
    for position, group in enumerate(groups_list):
        index[group].append(position)
    design = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    residuals = y - design @ beta
    vcv, info = robust.cluster_vcov(design, residuals, groups_list, correction=correction)
    se = float(math.sqrt(max(vcv[1, 1], 0.0)))
    return se, info["n_clusters"], info


def clustered_within_inference(
    prepared: dict[str, Any],
    scheme_groups: dict[str, Sequence[str]],
    alpha: float = 0.05,
    correction: str = robust.CR1,
) -> dict[str, Any]:
    """Coeficiente e erro-padrão sob vários esquemas de agrupamento.

    Todos os esquemas usam o **mesmo** ponto estimado (o do estimador
    within); o que muda é o estimador da variância. Assim, a comparação
    entre esquemas é uma comparação de **precisão da inferência**, e não de
    estimadores diferentes.
    """
    if prepared.get("status") != "ok":
        return prepared
    x = prepared["x_within"]
    y = prepared["y_within"]
    denominator = float(np.dot(x, x))
    if denominator <= 0:
        return {"status": "degenerate_within"}
    coefficient = float(np.dot(x, y) / denominator)
    out: dict[str, Any] = {
        "status": "ok",
        "variable": prepared["variable"],
        "n": prepared["n"],
        "n_municipalities": prepared["n_municipalities"],
        "n_years": prepared["n_years"],
        "coefficient": coefficient,
        "schemes": {},
    }
    for name, groups in scheme_groups.items():
        se, n_clusters, info = _clustered_se(x, y, list(groups), correction=correction)
        if not se or math.isnan(se):
            out["schemes"][name] = {"status": "insufficient_clusters"}
            continue
        t_stat = coefficient / se
        df = max(n_clusters - 1, 1)
        p_value = robust.t_sf(t_stat, df)
        critical = robust.t_critical(alpha, df)
        out["schemes"][name] = {
            "status": "ok",
            "n_clusters": n_clusters,
            "std_error": se,
            "t_statistic": t_stat,
            "df": df,
            "p_value": p_value,
            "ci_low": coefficient - critical * se,
            "ci_high": coefficient + critical * se,
            "correction": correction,
            "small_sample_multiplier": info.get("small_sample_multiplier"),
        }
    return out


def conley_within_inference(
    prepared: dict[str, Any],
    group_coords: dict[str, tuple[float, float]],
    cutoffs_km: Sequence[float] = (150.0, 250.0, 400.0, 600.0),
    kernel: str = "bartlett",
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Inferência espacial de Conley (1999) sobre os dados *within*."""
    if prepared.get("status") != "ok":
        return prepared
    x = prepared["x_within"]
    y = prepared["y_within"]
    municipalities = prepared["municipalities"]
    coefficient = float(np.dot(x, y) / np.dot(x, x))
    # No estimador *within* a regressao e y_w = b1 * x_w (sem intercepto:
    # as duas series foram dedemeanadas). O design tem uma unica coluna.
    design = x.reshape(-1, 1)
    residuals = y - coefficient * x
    out: dict[str, Any] = {
        "status": "ok",
        "variable": prepared["variable"],
        "coefficient": coefficient,
        "kernel": kernel,
        "cutoffs": {},
    }
    for cutoff in cutoffs_km:
        vcv, info = robust.conley_vcov(
            design, residuals, municipalities, group_coords, cutoff, kernel=kernel
        )
        se = float(math.sqrt(max(vcv[0, 0], 0.0)))
        degenerate = robust.degenerate_std_error(coefficient, se)
        t_stat = None if degenerate else coefficient / se
        p_value = robust.normal_sf(abs(t_stat)) if t_stat is not None else None
        critical = robust._normal_ppf(1.0 - alpha / 2.0)
        out["cutoffs"][f"{int(cutoff)}km"] = {
            "status": "ok",
            "cutoff_km": float(cutoff),
            "std_error": se,
            "t_statistic": t_stat,
            "p_value": p_value,
            "ci_low": coefficient - critical * se if not degenerate else None,
            "ci_high": coefficient + critical * se if not degenerate else None,
            "n_groups": info["n_groups"],
            "mean_weight": info["mean_weight"],
        }
    return out


def wild_cluster_bootstrap_within(
    prepared: dict[str, Any],
    groups: Sequence[str],
    n_boot: int = 999,
    seed: int = 20261113,
    null_imposed: bool = True,
    correction: str = robust.CR1,
    weight_scheme: str = robust.WEIGHT_CLUSTER,
    null_policy: str = robust.NULL_POLICY_AUTO,
) -> dict[str, Any]:
    """Bootstrap **wild** de cluster (Cameron, Gelbach & Miller, 2008).

    Aplicado sobre o estimador *within*: a nulidade imposta é obtida
    drenando de ``y`` a componente explicada pelo próprio ``x`` (a
    restrição β = 0), e os pesos de Rademacher são sorteados **por grupo**.

    ``weight_scheme`` admite ``"cluster"`` (padrão CGM: um peso por grupo)
    e ``"observation"`` (um peso por observação), mantida apenas para
    comparação de calibração (D80).
    """
    if prepared.get("status") != "ok":
        return prepared
    x = prepared["x_within"]
    y = prepared["y_within"]
    groups_list = list(groups)
    unique = sorted(set(groups_list))
    if len(unique) < 2:
        return {"status": "insufficient_clusters", "n_clusters": len(unique)}
    denominator = float(np.dot(x, x))
    if denominator <= 0:
        return {"status": "degenerate_within"}
    coefficient = float(np.dot(x, y) / denominator)
    residuals = y - coefficient * x
    se, n_clusters, _ = _clustered_se(x, y, groups_list, correction=correction)
    if not se or math.isnan(se):
        return {"status": "insufficient_clusters"}
    observed_t = coefficient / se
    index: dict[str, list[int]] = defaultdict(list)
    for position, group in enumerate(groups_list):
        index[group].append(position)
    group_names = sorted(index)
    group_position = {name: i for i, name in enumerate(group_names)}
    obs_position = np.fromiter(
        (group_position[group] for group in groups_list),
        dtype="int64",
        count=len(groups_list),
    )

    def _draws() -> np.ndarray:
        """Pesos de Rademacher: uma coluna por replicacao."""
        rng_boot = np.random.default_rng(seed)
        if weight_scheme == robust.WEIGHT_OBSERVATION:
            return rng_boot.choice([-1.0, 1.0], size=(n_boot, len(y)))
        return rng_boot.choice([-1.0, 1.0], size=(n_boot, len(group_names)))

    def _run(base: np.ndarray, boot_residuals: np.ndarray, draws: np.ndarray) -> dict[str, Any]:
        exceed = 0
        t_stats: list[float] = []
        for column in range(n_boot):
            if weight_scheme == robust.WEIGHT_OBSERVATION:
                weights = draws[column]
            else:
                weights = draws[column][obs_position]
            y_star = base + boot_residuals * weights
            beta_star = float(np.dot(x, y_star) / denominator)
            resid_star = y_star - beta_star * x
            meat = 0.0
            for indices in index.values():
                score = float(np.dot(x[indices], resid_star[indices]))
                meat += score * score
            n = len(x)
            k = 2
            g = len(index)
            multiplier = (g / (g - 1.0)) * ((n - 1.0) / (n - k)) if g > 1 else 1.0
            variance = multiplier * meat / (denominator * denominator)
            se_star = math.sqrt(max(variance, 0.0))
            if robust.degenerate_std_error(beta_star, se_star):
                continue
            t_star = beta_star / se_star
            t_stats.append(float(t_star))
            if abs(t_star) >= abs(observed_t):
                exceed += 1
        if not t_stats:
            return {"status": "bootstrap_failed"}
        return {
            "status": "ok",
            "p_value": float((exceed + 1) / (n_boot + 1)),
            "n_bootstrap_used": len(t_stats),
            "t_boot_sd": float(np.std(t_stats, ddof=1)),
            "t_boot_abs_q95": float(np.quantile(np.abs(t_stats), 0.95)),
        }

    summary = {
        "status": "ok",
        "n_clusters": n_clusters,
        "n_bootstrap": n_boot,
        "observed_t": float(observed_t),
        "observed_se": float(se),
        "weight_scheme": weight_scheme,
        "null_policy": null_policy,
        "interpretation": (
            "p-valor do bootstrap wild de cluster; valido mesmo com poucos "
            "grupos (Cameron, Gelbach & Miller, 2008)"
        ),
    }
    # Os MESMOS pesos sao usados nas duas ramificacoes (imposta e
    # irrestrita), de modo que a comparacao entre elas seja consistente.
    draws = _draws()
    if null_imposed:
        # Nulidade IMPOSTA (Cameron, Gelbach & Miller, 2008, secao 3): o
        # modelo restrito tem beta = 0, logo os valores ajustados sao zero e
        # os residuos restritos sao a propria resposta (y ja dedemeanada).
        restricted = _run(np.zeros_like(y), y, draws)
        restricted["null"] = "imposed"
        unrestricted = _run(coefficient * x, residuals, draws)
        unrestricted["null"] = "unrestricted"
        if restricted.get("status") == "ok" and unrestricted.get("status") == "ok":
            p_imposed = float(restricted["p_value"])
            p_unrestricted = float(unrestricted["p_value"])
            chosen = robust.select_null_policy(
                null_policy, p_imposed, p_unrestricted
            )
            if chosen == "imposed":
                result = dict(restricted)
            else:
                result = dict(unrestricted)
                result["note"] = (
                    "p-valor reportado conforme a politica de nulidade "
                    f"'{null_policy}'"
                )
            result["p_value_imposed"] = p_imposed
            result["p_value_unrestricted"] = p_unrestricted
            result["null_policy"] = null_policy
            result["null"] = chosen
            result.update(summary)
            result["null"] = chosen
            return result
        restricted.update(summary)
        return restricted
    unrestricted = _run(coefficient * x, residuals, draws)
    unrestricted["null"] = "unrestricted"
    unrestricted.update(summary)
    return unrestricted


def _within_wild_t_stats(
    x: np.ndarray,
    base: np.ndarray,
    boot_residuals: np.ndarray,
    draws: np.ndarray,
    obs_position: np.ndarray,
    group_index: list[np.ndarray],
    denominator: float,
    multiplier: float,
    observation_weights: bool,
) -> np.ndarray:
    """Estatísticas t do bootstrap wild *within*, vetorizadas.

    Reproduz o laço de :func:`wild_cluster_bootstrap_within` (mesmos pesos,
    mesma álgebra) resolvendo todas as replicações de uma vez.
    """
    if observation_weights:
        # (n_boot, n) -> (n, n_boot) para manter a mesma orientação
        y_star = (base[None, :] + boot_residuals[None, :] * draws).T
    else:
        weights = draws[:, obs_position].T  # (n, n_boot)
        y_star = base[:, None] + boot_residuals[:, None] * weights
    beta_star = (x @ y_star) / denominator
    resid_star = y_star - np.outer(x, beta_star)
    weighted = x[:, None] * resid_star
    scores = np.empty((len(group_index), y_star.shape[1]), dtype="float64")
    for gi, idx in enumerate(group_index):
        scores[gi] = weighted[idx].sum(axis=0)
    meat = np.sum(scores**2, axis=0)
    variance = multiplier * meat / (denominator * denominator)
    se = np.sqrt(np.maximum(variance, 0.0))
    usable = np.isfinite(se) & (
        se > robust._SE_RELATIVE_FLOOR * np.maximum(np.abs(beta_star), 1.0)
    )
    safe_se = np.where(usable, se, 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        t_stats = np.where(usable, beta_star / safe_se, np.nan)
    return t_stats


def wild_cluster_bootstrap_within_fast(
    prepared: dict[str, Any],
    groups: Sequence[str],
    n_boot: int = 999,
    seed: int = 20261113,
    null_imposed: bool = True,
    correction: str = robust.CR1,
    weight_scheme: str = robust.WEIGHT_CLUSTER,
    null_policy: str = robust.NULL_POLICY_AUTO,
) -> dict[str, Any]:
    """Versão **vetorizada** de :func:`wild_cluster_bootstrap_within`."""
    if prepared.get("status") != "ok":
        return prepared
    x = prepared["x_within"]
    y = prepared["y_within"]
    groups_list = list(groups)
    unique = sorted(set(groups_list))
    if len(unique) < 2:
        return {"status": "insufficient_clusters", "n_clusters": len(unique)}
    denominator = float(np.dot(x, x))
    if denominator <= 0:
        return {"status": "degenerate_within"}
    coefficient = float(np.dot(x, y) / denominator)
    residuals = y - coefficient * x
    se, n_clusters, _ = _clustered_se(x, y, groups_list, correction=correction)
    if not se or math.isnan(se):
        return {"status": "insufficient_clusters"}
    observed_t = coefficient / se
    index: dict[str, list[int]] = defaultdict(list)
    for position, group in enumerate(groups_list):
        index[group].append(position)
    group_names = sorted(index)
    group_position = {name: i for i, name in enumerate(group_names)}
    obs_position = np.fromiter(
        (group_position[group] for group in groups_list),
        dtype="int64",
        count=len(groups_list),
    )
    group_index = [
        np.asarray(index[name], dtype=int) for name in group_names
    ]
    rng_boot = np.random.default_rng(seed)
    if weight_scheme == robust.WEIGHT_OBSERVATION:
        draws = rng_boot.choice([-1.0, 1.0], size=(n_boot, len(y)))
    else:
        draws = rng_boot.choice([-1.0, 1.0], size=(n_boot, len(group_names)))
    n = len(x)
    k = 2
    g = len(index)
    multiplier = (g / (g - 1.0)) * ((n - 1.0) / (n - k)) if g > 1 else 1.0

    def _summarize(t_stats: np.ndarray) -> dict[str, Any]:
        valid = t_stats[np.isfinite(t_stats)]
        if valid.size == 0:
            return {"status": "bootstrap_failed"}
        exceed = int(np.sum(np.abs(valid) >= abs(observed_t)))
        return {
            "status": "ok",
            "p_value": float((exceed + 1) / (n_boot + 1)),
            "n_bootstrap_used": int(valid.size),
            "observed_t": float(observed_t),
            "t_boot_sd": float(np.std(valid, ddof=1)) if valid.size > 1 else None,
            "t_boot_abs_q95": float(np.quantile(np.abs(valid), 0.95)),
        }

    observation_weights = weight_scheme == robust.WEIGHT_OBSERVATION
    common = {
        "n_clusters": n_clusters,
        "n_bootstrap": n_boot,
        "observed_t": float(observed_t),
        "observed_se": float(se),
        "weight_scheme": weight_scheme,
        "null_policy": null_policy,
    }
    if null_imposed:
        restricted = _summarize(
            _within_wild_t_stats(
                x,
                np.zeros_like(y),
                y,
                draws,
                obs_position,
                group_index,
                denominator,
                multiplier,
                observation_weights,
            )
        )
        restricted["null"] = "imposed"
        unrestricted = _summarize(
            _within_wild_t_stats(
                x,
                coefficient * x,
                residuals,
                draws,
                obs_position,
                group_index,
                denominator,
                multiplier,
                observation_weights,
            )
        )
        unrestricted["null"] = "unrestricted"
        if restricted.get("status") == "ok" and unrestricted.get("status") == "ok":
            p_imposed = float(restricted["p_value"])
            p_unrestricted = float(unrestricted["p_value"])
            chosen = robust.select_null_policy(
                null_policy, p_imposed, p_unrestricted
            )
            result = dict(restricted if chosen == "imposed" else unrestricted)
            result["p_value_imposed"] = p_imposed
            result["p_value_unrestricted"] = p_unrestricted
            result["null_policy"] = null_policy
            result["null"] = chosen
            result.update(common)
            result["null"] = chosen
            return result
        restricted.update(common)
        return restricted
    result = _summarize(
        _within_wild_t_stats(
            x,
            coefficient * x,
            residuals,
            draws,
            obs_position,
            group_index,
            denominator,
            multiplier,
            observation_weights,
        )
    )
    result["null"] = "unrestricted"
    result.update(common)
    return result


def effective_sample_size(
    n: int, n_clusters: int, mean_correlation: float
) -> float:
    """Tamanho de amostra efetivo sob correlação intragrupo média.

    ``n_eff = n / (1 + (m − 1) · ρ̄)``, com ``m`` o tamanho médio do grupo
    e ``ρ̄`` a correlação média dentro do grupo. É a aproximação de
    Kish (1965) para o desenho de grupos.
    """
    if n_clusters <= 0 or n <= 0:
        return float(n)
    m = n / n_clusters
    denominator = 1.0 + (m - 1.0) * mean_correlation
    if denominator <= 0:
        return float(n)
    return float(n / denominator)
