"""Inferência com erro-padrão agrupado e correção para poucos grupos (V2.7).

Este módulo implementa a inferência estatística que a V2.6 deixou como
pendência explícita (D75): o erro-padrão agrupado por **município** não
controla a dependência espacial introduzida pela grade meteorológica.

Conteúdo:

* :func:`cluster_vcov` — matriz de covariância dos coeficientes com
  **erro-padrão agrupado** (cluster-robust), nas correções **CR1** e
  **CR2** (a CR2 exige a alavancagem média por grupo, cara em painéis com
  milhares de dummies, e é aplicada apenas quando o número de grupos é
  pequeno);
* :func:`wild_cluster_bootstrap` — bootstrap de cluster **wild** (Cameron,
  Gelbach & Miller, 2008) com pesos de Rademacher e nulidade imposta
  (restricted/null-imposed), que é o procedimento de referência quando o
  número de grupos é limitado;
* :func:`t_sf` / :func:`t_ppf` — cauda e quantil da distribuição t, calculados
  **sem dependência externa** (função beta incompleta regularizada), para
  que o módulo funcione no ambiente geospatial já validado.

As funções de distribuição são verificadas contra valores tabelados
conhecidos (1.959964 para a normal a 5%; 12.706205 e 2.228139 para a t com
1 e 10 graus de liberdade) na suíte de testes da V2.7.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Sequence

import numpy as np

# Correções de amostra pequena para o estimador agrupado.
CR1 = "CR1"
CR2 = "CR2"

# Esquemas de sorteio dos pesos de Rademacher do bootstrap wild.
#
# ``cluster`` (PADRÃO, Cameron, Gelbach & Miller, 2008, seção 4): **um** peso
# por grupo e por replicação — é o que preserva a dependência
# intracluster, que é justamente o objeto do problema espacial.
#
# ``observation``: um peso por observação (bootstrap wild "simples"). Foi o
# comportamento herdado da implementação da sessão anterior e é mantido
# **apenas** como variante de comparação, porque não preserva a estrutura
# de dependência dentro do grupo (ver D80).
WEIGHT_CLUSTER = "cluster"
WEIGHT_OBSERVATION = "observation"

# Políticas de escolha do p-valor reportado pelo bootstrap wild.
#
# O bootstrap wild admite duas hipóteses nulas de bootstrap:
#  * **imposta** — a nulidade β = 0 é imposta no DGP do bootstrap
#    (Cameron, Gelbach & Miller, 2008, seção 3);
#  * **irrestrita** — a nulidade é β = β̂ (bootstrap assintótico), mais
#    conservadora com poucos grupos.
#
# A escolha entre elas depende de uma convenção de Cameron, Gelbach &
# Miller cuja formulação não pôde ser verificada no artigo primário neste
# ambiente (sem acesso). Por isso a V2.7 **reporta as duas** e declara
# explicitamente a política usada, em vez de aplicar uma regra silenciosa
# (D81).
NULL_POLICY_IMPOSED = "imposed"
NULL_POLICY_UNRESTRICTED = "unrestricted"
NULL_POLICY_AUTO = "auto"


def select_null_policy(
    policy: str,
    p_imposed: float,
    p_unrestricted: float,
    restrict_p_threshold: float = 0.10,
) -> str:
    """Define qual p-valor do bootstrap wild é o reportado.

    * ``"imposed"`` — sempre o p-valor da nulidade imposta (teste direto
      de β = 0);
    * ``"unrestricted"`` — sempre o p-valor da nulidade irrestrita;
    * ``"auto"`` — política histórica deste repositório: quando a nulidade
      imposta **não** rejeita (p > 0,10), reporta-se a irrestrita, que é
      mais conservadora.
    """
    if policy == NULL_POLICY_IMPOSED:
        return NULL_POLICY_IMPOSED
    if policy == NULL_POLICY_UNRESTRICTED:
        return NULL_POLICY_UNRESTRICTED
    if policy != NULL_POLICY_AUTO:
        raise ValueError(f"política de nulidade desconhecida: {policy!r}")
    return (
        NULL_POLICY_UNRESTRICTED
        if p_imposed > restrict_p_threshold
        else NULL_POLICY_IMPOSED
    )


# --------------------------------------------------------------------------
# Distribuições (implementação própria: sem scipy/statsmodels).
# --------------------------------------------------------------------------
def _betacf(a: float, b: float, x: float) -> float:
    """Fração contínua de Lentz para a função beta incompleta."""
    max_iter = 300
    eps = 3.0e-16
    fpmin = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Função beta incompleta regularizada ``I_x(a, b)``."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(ln_beta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(ln_beta + b * math.log1p(-x) + a * math.log(x)) * _betacf(
        b, a, 1.0 - x
    ) / b


def normal_cdf(x: float) -> float:
    """Função de distribuição acumulada da normal padrão."""
    return 0.5 * (1.0 + math.erf(float(x) / math.sqrt(2.0)))


def normal_sf(x: float) -> float:
    """Cauda superior da normal padrão."""
    return 1.0 - normal_cdf(x)


def t_sf(t: float, df: float) -> float:
    """Probabilidade bilateral de sobrevivência da distribuição t: ``P(|T| > |t|)``."""
    if df <= 0:
        return float("nan")
    t = abs(float(t))
    if t == 0.0:
        return 1.0
    if math.isinf(t):
        return 0.0
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def t_ppf(alpha: float, df: float) -> float:
    """Quantil superior da distribuição t: ``t`` tal que ``P(|T| > t) = alpha``."""
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha fora de (0,1): {alpha}")
    if df <= 0:
        return float("nan")
    low, high = 0.0, 1.0
    while t_sf(high, df) > alpha and high < 1.0e8:
        high *= 2.0
    for _ in range(200):
        mid = 0.5 * (low + high)
        if t_sf(mid, df) > alpha:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def t_critical(alpha: float, df: float) -> float:
    """Valor crítico bilateral da t (equivalente a ``t_ppf``)."""
    return t_ppf(alpha, df)


# --------------------------------------------------------------------------
# Estimador agrupado (cluster-robust).
# --------------------------------------------------------------------------
def _group_indices(groups: Sequence[Any]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        if group in (None, ""):
            continue
        out[str(group)].append(index)
    return dict(out)


def cluster_vcov(
    design: np.ndarray,
    residuals: np.ndarray,
    groups: Sequence[Any],
    correction: str = CR1,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Matriz de covariância dos coeficientes com erro-padrão agrupado.

    ``design`` é a matriz X (n × k, **sem** coluna de intercepto separada:
    inclua-a explicitamente), ``residuals`` são os resíduos da OLS e
    ``groups`` o identificador do grupo de cada observação.

    Correções:

    * **CR1** — multiplicador ``G/(G−1) · (N−1)/(N−K)`` (White, 1980;
      Bertrand, Duflo & Mullainathan, 2004);
    * **CR2** — multiplicador ``G/(G−1) · (N−1)/(N−K) · (N−1)/(N−K₂)`` em que
      ``K₂`` é a soma das alavancagens medias do grupo. É a correção de
      viés para amostras pequenas (Bell-McCaffrey, 2002; Imbens & Kolesár,
      2016). Custa uma fatoração por grupo e só é aplicada quando
      ``G`` é pequeno.
    """
    X = np.asarray(design, dtype="float64")
    u = np.asarray(residuals, dtype="float64")
    n, k = X.shape
    index = _group_indices(groups)
    g = len(index)
    if g == 0:
        raise ValueError("nenhum grupo válido para o estimador agrupado")
    bread = np.linalg.pinv(X.T @ X)
    meat = np.zeros((k, k), dtype="float64")
    leverage_sum = 0.0
    for indices in index.values():
        block = X[indices, :]
        score = block.T @ u[indices]
        meat += np.outer(score, score)
        if correction == CR2:
            hat = bread @ block.T @ block @ bread
            leverage_sum += float(np.trace(hat))
    base = (g / (g - 1.0)) * ((n - 1.0) / (n - k)) if g > 1 else 1.0
    if correction == CR2:
        k2 = leverage_sum
        multiplier = base * ((n - 1.0) / (n - k2)) if n > k2 else base
    else:
        multiplier = base
    vcv = multiplier * (bread @ meat @ bread)
    info = {
        "n_clusters": g,
        "n_observations": n,
        "n_parameters": k,
        "correction": correction,
        "small_sample_multiplier": float(multiplier),
        "cr2_leverage_sum": float(leverage_sum) if correction == CR2 else None,
    }
    return vcv, info


def _ols_fit(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    if X.shape[0] <= X.shape[1]:
        return None
    try:
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    except np.linalg.LinAlgError:
        return None
    return beta, y - X @ beta


def cluster_robust_fit(
    design: np.ndarray,
    y: np.ndarray,
    groups: Sequence[Any],
    coef_index: int = 1,
    correction: str = CR1,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Regressão OLS com erro-padrão agrupado e teste de um coeficiente.

    O intervalo de confiança usa a distribuição t com ``G − 1`` graus de
    liberdade (Cameron & Miller, 2015), que é a escolha conservadora para
    inferência agrupada.
    """
    X = np.asarray(design, dtype="float64")
    target = np.asarray(y, dtype="float64")
    fitted = _ols_fit(X, target)
    if fitted is None:
        return {"status": "singular_design"}
    beta, residuals = fitted
    vcv, info = cluster_vcov(X, residuals, groups, correction=correction)
    se = float(math.sqrt(max(vcv[coef_index, coef_index], 0.0)))
    coefficient = float(beta[coef_index])
    df = max(info["n_clusters"] - 1, 1)
    t_stat = coefficient / se if se > 0 else None
    p_value = t_sf(t_stat, df) if t_stat is not None else None
    critical = t_critical(alpha, df)
    return {
        "status": "ok",
        "coefficient": coefficient,
        "std_error_clustered": se,
        "t_statistic": t_stat,
        "df_cluster": df,
        "p_value": p_value,
        "ci_low": coefficient - critical * se if se > 0 else None,
        "ci_high": coefficient + critical * se if se > 0 else None,
        "confidence_level": 1.0 - alpha,
        "n": info["n_observations"],
        "n_clusters": info["n_clusters"],
        "correction": info["correction"],
        "small_sample_multiplier": info["small_sample_multiplier"],
    }


def _rademacher_matrix(
    groups: Sequence[Any],
    n_boot: int,
    seed: int,
    weight_scheme: str = WEIGHT_CLUSTER,
) -> np.ndarray:
    """Matriz de pesos de Rademacher ``(n_obs, n_boot)``.

    * ``weight_scheme="cluster"`` — **um** peso por grupo e por replicação
      (Cameron, Gelbach & Miller, 2008): o mesmo peso é aplicado a todas as
      observações do grupo, o que preserva a correlação intra-cluster;
    * ``weight_scheme="observation"`` — um peso independente por observação
      (bootstrap wild sem agrupamento), comportamento herdado da versão
      anterior deste repositório, mantido apenas como variante de
      comparação (ver D80).

    A matriz é gerada de uma só vez, o que é equivalente ao sorteio dentro
    do laço de replicações e ordens de magnitude mais rápido.
    """
    index = _group_indices(groups)
    n = len(groups)
    rng = np.random.default_rng(seed)
    if weight_scheme == WEIGHT_OBSERVATION:
        return rng.choice([-1.0, 1.0], size=(n, n_boot))
    if weight_scheme != WEIGHT_CLUSTER:
        raise ValueError(f"esquema de pesos desconhecido: {weight_scheme!r}")
    group_names = sorted(index)
    position = {name: i for i, name in enumerate(group_names)}
    draws = rng.choice([-1.0, 1.0], size=(n_boot, len(group_names)))
    columns = np.fromiter(
        (position[str(group)] for group in groups), dtype="int64", count=n
    )
    return draws[:, columns].T.copy()


def wild_cluster_bootstrap(
    design: np.ndarray,
    y: np.ndarray,
    groups: Sequence[Any],
    coef_index: int = 1,
    n_boot: int = 999,
    seed: int = 20261113,
    null_imposed: bool = True,
    correction: str = CR1,
    restrict_p_threshold: float = 0.10,
    weight_scheme: str = WEIGHT_CLUSTER,
    weights: np.ndarray | None = None,
    null_policy: str = NULL_POLICY_AUTO,
) -> dict[str, Any]:
    """Bootstrap **wild** de cluster (Cameron, Gelbach & Miller, 2008).

    Com pesos de Rademacher ``±1`` sorteados **por grupo** (e não por
    observação), o procedimento preserva a estrutura de dependência dentro do
    grupo e produz um p-valor válido mesmo quando o número de grupos é
    pequeno.

    * ``null_imposed=True`` — a nulidade é imposta: os resíduos são
      ortogonalizados contra as demais colunas do design, de modo que a
      distribuição nula é imposta exatamente sobre o coeficiente de
      interesse;
    * quando o p-valor da nulidade imposta é maior que
      ``restrict_p_threshold``, aplica-se a **nulidade irrestrita** (o
      bootstrap com os resíduos não ortogonalizados), que é mais conservador
      quando a nulidade imposta é rejeitada (Cameron, Gelbach & Miller, 2008,
      seção 3).
    """
    X = np.asarray(design, dtype="float64")
    target = np.asarray(y, dtype="float64")
    index = _group_indices(groups)
    g = len(index)
    if g < 2:
        return {"status": "insufficient_clusters", "n_clusters": g}
    fitted = _ols_fit(X, target)
    if fitted is None:
        return {"status": "singular_design"}
    beta, residuals = fitted
    observed_se_fit = cluster_robust_fit(
        X, target, groups, coef_index=coef_index, correction=correction
    )
    if observed_se_fit.get("status") != "ok":
        return observed_se_fit
    observed_t = observed_se_fit["t_statistic"]

    # --- nulidade imposta: residuos restritos = M_Z y (Cameron et al., 2008)
    others = [i for i in range(X.shape[1]) if i != coef_index]
    restricted_fit = np.zeros_like(target)
    restricted_residuals = residuals.copy()
    if null_imposed and others:
        Z = X[:, others]
        z_hat = np.linalg.pinv(Z.T @ Z) @ (Z.T @ target)
        restricted_fit = Z @ z_hat
        restricted_residuals = target - restricted_fit

    # Pesos de Rademacher: um por grupo e por replicacao (CGM, 2008).
    # A matriz completa e gerada de uma vez; cada replicacao usa uma
    # coluna. Sortear os pesos uma unica vez fora do laco faria todas as
    # replicas coincidirem e o bootstrap perderia a variacao que da
    # cobertura ao p-valor.
    weight_matrix = (
        np.asarray(weights, dtype="float64")
        if weights is not None
        else _rademacher_matrix(groups, n_boot, seed, weight_scheme)
    )

    def _bootstrap(base_outcome: np.ndarray, res: np.ndarray) -> dict[str, Any]:
        exceed = 0
        t_stats: list[float] = []
        for column in range(weight_matrix.shape[1]):
            weight_vector = weight_matrix[:, column]
            y_star = base_outcome + res * weight_vector
            boot_fit = cluster_robust_fit(
                X, y_star, groups, coef_index=coef_index, correction=correction
            )
            if boot_fit.get("status") != "ok":
                continue
            t_boot = boot_fit["t_statistic"]
            if t_boot is None:
                continue
            t_stats.append(float(t_boot))
            if abs(t_boot) >= abs(observed_t):
                exceed += 1
        if not t_stats:
            return {"status": "bootstrap_failed"}
        return {
            "status": "ok",
            "p_value": float((exceed + 1) / (weight_matrix.shape[1] + 1)),
            "n_bootstrap_used": len(t_stats),
            "observed_t": float(observed_t),
            "t_boot_sd": float(np.std(t_stats, ddof=1)) if len(t_stats) > 1 else None,
            "t_boot_abs_q95": float(np.quantile(np.abs(t_stats), 0.95)),
        }

    if null_imposed:
        # Nulidade IMPOSTA: o modelo restrito (beta do coeficiente de
        # interesse = 0) e re-estimado; os valores ajustados sao
        # ``restricted_fit`` e os residuos restritos sao ``restricted_residuals``.
        result = _bootstrap(restricted_fit, restricted_residuals)
        result["null"] = "imposed"
        unrestricted = _bootstrap(target, residuals)
        unrestricted["null"] = "unrestricted"
        if result.get("status") == "ok" and unrestricted.get("status") == "ok":
            p_imposed = float(result["p_value"])
            p_unrestricted = float(unrestricted["p_value"])
            chosen = select_null_policy(
                null_policy, p_imposed, p_unrestricted, restrict_p_threshold
            )
            final = dict(result if chosen == "imposed" else unrestricted)
            final["p_value_imposed"] = p_imposed
            final["p_value_unrestricted"] = p_unrestricted
            final["null_policy"] = null_policy
            final["null"] = chosen
            return final
        return result
    result = _bootstrap(target, residuals)
    result["null"] = "unrestricted"
    return result


def _wild_t_stats_vectorized(
    design: np.ndarray,
    base_outcome: np.ndarray,
    residuals: np.ndarray,
    weights: np.ndarray,
    coef_index: int,
    groups: Sequence[Any],
) -> np.ndarray:
    """Estatísticas t do bootstrap wild, calculadas **vetorizadas**.

    Reproduz o laço de :func:`wild_cluster_bootstrap` (mesmos pesos, mesma
    álgebra), mas resolve todas as replicações de uma vez. É usado
    apenas na calibração Monte Carlo, onde o volume de simulações exige a
    versão vetorizada; a igualdade com a versão em laço é verificada por
    teste automatizado.
    """
    X = np.asarray(design, dtype="float64")
    base = np.asarray(base_outcome, dtype="float64")
    res = np.asarray(residuals, dtype="float64")
    W = np.asarray(weights, dtype="float64")
    n, k = X.shape
    n_boot = W.shape[1]
    index = _group_indices(groups)
    g = len(index)
    bread = np.linalg.pinv(X.T @ X)
    star = base[:, None] + res[:, None] * W
    betas = bread @ (X.T @ star)
    boot_residuals = star - X @ betas
    group_names = sorted(index)
    scores = np.empty((g, k, n_boot), dtype="float64")
    for gi, name in enumerate(group_names):
        idx = np.asarray(index[name], dtype=int)
        scores[gi] = X[idx].T @ boot_residuals[idx]
    meat = np.einsum("gkb,gib->bki", scores, scores)
    multiplier = (g / (g - 1.0)) * ((n - 1.0) / (n - k)) if g > 1 else 1.0
    vcv = multiplier * (bread @ meat @ bread)
    se = np.sqrt(np.maximum(vcv[:, coef_index, coef_index], 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        t_stats = np.where(se > 0, betas[coef_index] / se, np.nan)
    return t_stats


def wild_cluster_bootstrap_fast(
    design: np.ndarray,
    y: np.ndarray,
    groups: Sequence[Any],
    coef_index: int = 1,
    n_boot: int = 999,
    seed: int = 20261113,
    null_imposed: bool = True,
    correction: str = CR1,
    restrict_p_threshold: float = 0.10,
    weight_scheme: str = WEIGHT_CLUSTER,
    weights: np.ndarray | None = None,
    null_policy: str = NULL_POLICY_AUTO,
) -> dict[str, Any]:
    """Versão **vetorizada** de :func:`wild_cluster_bootstrap`.

    Mesma álgebra e mesma convenção de pesos; resolve todas as replicações
    de uma vez. Usada na calibração Monte Carlo. A equivalência com a
    versão em laço é verificada por teste automatizado.
    """
    X = np.asarray(design, dtype="float64")
    target = np.asarray(y, dtype="float64")
    index = _group_indices(groups)
    g = len(index)
    if g < 2:
        return {"status": "insufficient_clusters", "n_clusters": g}
    fitted = _ols_fit(X, target)
    if fitted is None:
        return {"status": "singular_design"}
    beta, residuals = fitted
    observed_se_fit = cluster_robust_fit(
        X, target, groups, coef_index=coef_index, correction=correction
    )
    if observed_se_fit.get("status") != "ok":
        return observed_se_fit
    observed_t = observed_se_fit["t_statistic"]

    others = [i for i in range(X.shape[1]) if i != coef_index]
    restricted_fit = np.zeros_like(target)
    restricted_residuals = residuals.copy()
    if null_imposed and others:
        Z = X[:, others]
        z_hat = np.linalg.pinv(Z.T @ Z) @ (Z.T @ target)
        restricted_fit = Z @ z_hat
        restricted_residuals = target - restricted_fit

    weight_matrix = (
        np.asarray(weights, dtype="float64")
        if weights is not None
        else _rademacher_matrix(groups, n_boot, seed, weight_scheme)
    )

    def _summarize(t_stats: np.ndarray) -> dict[str, Any]:
        valid = t_stats[np.isfinite(t_stats)]
        if valid.size == 0:
            return {"status": "bootstrap_failed"}
        exceed = int(np.sum(np.abs(valid) >= abs(observed_t)))
        return {
            "status": "ok",
            "p_value": float((exceed + 1) / (weight_matrix.shape[1] + 1)),
            "n_bootstrap_used": int(valid.size),
            "observed_t": float(observed_t),
            "t_boot_sd": float(np.std(valid, ddof=1)) if valid.size > 1 else None,
            "t_boot_abs_q95": float(np.quantile(np.abs(valid), 0.95)),
        }

    if null_imposed:
        t_stats = _wild_t_stats_vectorized(
            X, restricted_fit, restricted_residuals, weight_matrix, coef_index, groups
        )
        result = _summarize(t_stats)
        result["null"] = "imposed"
        unrestricted = _summarize(
            _wild_t_stats_vectorized(
                X, target, residuals, weight_matrix, coef_index, groups
            )
        )
        unrestricted["null"] = "unrestricted"
        if result.get("status") == "ok" and unrestricted.get("status") == "ok":
            p_imposed = float(result["p_value"])
            p_unrestricted = float(unrestricted["p_value"])
            chosen = select_null_policy(
                null_policy, p_imposed, p_unrestricted, restrict_p_threshold
            )
            final = dict(result if chosen == "imposed" else unrestricted)
            final["p_value_imposed"] = p_imposed
            final["p_value_unrestricted"] = p_unrestricted
            final["null_policy"] = null_policy
            final["null"] = chosen
            return final
        return result
    result = _summarize(
        _wild_t_stats_vectorized(
            X, target, residuals, weight_matrix, coef_index, groups
        )
    )
    result["null"] = "unrestricted"
    return result


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Correção de Holm (FWER) — reexportada de :mod:`agroclimate.analysis`.

    A implementação fica em um único lugar (``analysis.py``); este alias evita
    duplicação e mantém a família de testes explícita no código da V2.7.
    """
    from .analysis import holm_correction

    return holm_correction(p_values)


# --------------------------------------------------------------------------
# Estimador espacial de Conley (1999) e agrupamento em duas direções.
# --------------------------------------------------------------------------
def conley_vcov(
    design: np.ndarray,
    residuals: np.ndarray,
    groups: Sequence[Any],
    group_coords: dict[str, tuple[float, float]],
    cutoff_km: float,
    kernel: str = "bartlett",
) -> tuple[np.ndarray, dict[str, Any]]:
    """Matriz de covariância espacial de Conley (1999).

    O estimador de Conley relaxa a hipótese de independência e usa a
    **distância geográfica** entre as unidades, com um núcleo que se anula
    além de ``cutoff_km``. É o procedimento indicado quando a dependência é
    **contínua no espaço** — que é o caso medido na V2.7 (a correlação das
    anomalias anuais do clima permanece acima de 0,6 a 400 km).

    Eficiência: a soma dupla sobre observações é colapsada no nível da
    unidade geográfica. Para cada grupo ``m`` define-se
    ``a_m = X_m' u_m``; então

    ``meat = Σ_{m,m'} K(d(m,m')) · a_m a_m' = A' K A``

    com ``A`` (n_grupos × k). Isso torna o custo independente do número de
    observações por município.

    Núcleos: ``bartlett`` (linear, ``1 − d/cutoff``) e ``uniforme``
    (``1`` dentro do corte).
    """
    X = np.asarray(design, dtype="float64")
    u = np.asarray(residuals, dtype="float64")
    index = _group_indices(groups)
    names = sorted(index)
    if not names:
        raise ValueError("nenhum grupo válido para o estimador espacial")
    position = {name: i for i, name in enumerate(names)}
    k = X.shape[1]
    # a_m = X_m' u_m
    A = np.zeros((len(names), k), dtype="float64")
    for name, indices in index.items():
        block = X[indices, :]
        A[position[name], :] = block.T @ u[indices]
    # matriz de distâncias entre grupos (km) e núcleo
    coords = np.array(
        [group_coords.get(name, (0.0, 0.0)) for name in names], dtype="float64"
    )
    lat = np.radians(coords[:, 0])[:, None]
    lon = np.radians(coords[:, 1])[:, None]
    dlat = lat - lat.T
    dlon = lon - lon.T
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat) * np.cos(lat.T) * np.sin(dlon / 2.0) ** 2
    distance = 2.0 * 6371.0088 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    if kernel == "bartlett":
        weights = np.maximum(0.0, 1.0 - distance / float(cutoff_km))
    elif kernel == "uniform":
        weights = (distance <= float(cutoff_km)).astype("float64")
    else:
        raise ValueError(f"núcleo desconhecido: {kernel}")
    np.fill_diagonal(weights, 1.0)
    meat = A.T @ (weights @ A)
    bread = np.linalg.pinv(X.T @ X)
    vcv = bread @ meat @ bread
    info = {
        "n_groups": len(names),
        "n_observations": int(X.shape[0]),
        "n_parameters": k,
        "cutoff_km": float(cutoff_km),
        "kernel": kernel,
        "mean_weight": float(weights.mean()),
        "share_weight_beyond_cutoff": float((distance > cutoff_km).mean()),
    }
    return vcv, info


def two_way_cluster_vcov(
    design: np.ndarray,
    residuals: np.ndarray,
    clusters_a: Sequence[Any],
    clusters_b: Sequence[Any],
    correction: str = CR1,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Agrupamento em duas direções (Cameron, Gelbach & Miller, 2011).

    ``V = V_A + V_B − V_{A∩B}``, onde ``A∩B`` é o agrupamento pela
    **combinação** dos dois identificadores. É a correção-padrão para
    simultaneamente: (a) observações do mesmo município (erro intra-município)
    e (b) observações na mesma região espacial (erro espacial).

    O estimador ``V_{A∩B}`` é a identidade deCameron-Gelbach-Miller
    (``A∩B`` particiona cada par de observações do mesmo grupo em ambos os
    esquemas), o que torna a combinação exata.
    """
    X = np.asarray(design, dtype="float64")
    u = np.asarray(residuals, dtype="float64")
    v_a, info_a = cluster_vcov(X, u, clusters_a, correction=correction)
    v_b, info_b = cluster_vcov(X, u, clusters_b, correction=correction)
    combined = [
        f"{a}||{b}" for a, b in zip(clusters_a, clusters_b)
    ]
    v_ab, info_ab = cluster_vcov(X, u, combined, correction=correction)
    vcv = v_a + v_b - v_ab
    info = {
        "n_clusters_a": info_a["n_clusters"],
        "n_clusters_b": info_b["n_clusters"],
        "n_clusters_intersection": info_ab["n_clusters"],
        "correction": correction,
    }
    return vcv, info


def cluster_robust_fit_with_vcov(
    design: np.ndarray,
    y: np.ndarray,
    vcv: np.ndarray,
    coef_index: int = 1,
    df: int | None = None,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Coeficiente, erro-padrão e teste a partir de uma matriz de covariância.

    Usada para o estimador de Conley (cuja variância não é "cluster-robust"
    no sentido classical e, portanto, não tem um número de grupos natural):
    o teste usa a normal padrão, que é a aproximação usual para esse
    estimador.
    """
    X = np.asarray(design, dtype="float64")
    target = np.asarray(y, dtype="float64")
    beta, *_ = np.linalg.lstsq(X, target, rcond=None)
    se = float(math.sqrt(max(vcv[coef_index, coef_index], 0.0)))
    coefficient = float(beta[coef_index])
    if df is not None and df > 0:
        t_stat = coefficient / se if se > 0 else None
        p_value = t_sf(t_stat, df) if t_stat is not None else None
        critical = t_critical(alpha, df)
    else:
        t_stat = coefficient / se if se > 0 else None
        p_value = normal_sf(abs(t_stat)) if t_stat is not None else None
        critical = _normal_ppf(1.0 - alpha / 2.0)
    return {
        "status": "ok",
        "coefficient": coefficient,
        "std_error": se,
        "t_statistic": t_stat,
        "p_value": p_value,
        "ci_low": coefficient - critical * se if se > 0 else None,
        "ci_high": coefficient + critical * se if se > 0 else None,
        "df": df,
    }


def _normal_ppf(p: float) -> float:
    """Quantil da normal padrão (Acklam, corrigido por uma iteração de Halley)."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"p fora de (0,1): {p}")
    a = [
        -3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
        1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
        6.680131188771972e01, -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
        -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
        3.754408661907416e00,
    ]
    low, high = 0.02425, 1.0 - 0.02425
    if p < low:
        q = math.sqrt(-2.0 * math.log(p))
        x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    elif p <= high:
        q = p - 0.5
        r = q * q
        x = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
            ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0
        )
    else:
        q = math.sqrt(-2.0 * math.log1p(-p))
        x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    # uma iteração de Halley
    e = 0.5 * math.erfc(-x / math.sqrt(2.0)) - p
    u = e * math.sqrt(2.0 * math.pi) * math.exp(x * x / 2.0)
    return x - u / (1.0 + x * u / 2.0)

