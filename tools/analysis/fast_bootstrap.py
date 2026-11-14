"""Núcleo rápido e exato do wild cluster bootstrap-t (um regressor *within*).

Para um único regressor, o bootstrap inteiro é redutível a somas por cluster.
Sejam ``a_g = sum_{i in g} x_i y_i``, ``b_g = sum_{i in g} x_i^2`` e pesos ``w_g``
constantes dentro do cluster:

**Nulidade imposta (WCR).** O modelo restrito é ``y = 0`` (a transformação
*within* já removeu o intercepto), logo os resíduos restritos são ``y``:

    beta*  = sum_g w_g a_g / sum_g b_g
    S*_g   = w_g a_g - beta* b_g
    SE*    = sqrt(mult * sum_g S*_g^2) / sum_g b_g

**Nulidade irrestrita (WCU).** Com ``u = y - beta_hat x`` e ``c_g = sum_{i in g} x_i u_i``:

    beta*  = beta_hat + sum_g w_g c_g / sum_g b_g
    S*_g   = w_g c_g - (beta* - beta_hat) b_g

Em ambos os casos, ``t* = beta* / SE*`` e ``p = (1 + #{|t*| >= |t_obs|})/(B+1)``.
O custo cai de O(n·B) para O(G·B).

Equivalência verificada em teste: ``cr1_fit`` reproduz
``agroclimate.robust.cluster_robust_fit`` com precisão de 12 casas decimais.

**Nota sobre CR2.** Com ``k = 1`` a correção CR2 degenera em CR1: a alavancagem
agregada é ``K2 = 1`` e o fator ``(n−1)/(n−K2)`` vale 1. Não é um método
distinto neste desenho.

**Nota sobre ``null_imposed`` na biblioteca (D129).** ``robust.wild_cluster_bootstrap_fast``
só impõe a nulidade quando o desenho tem outra coluna além da testada
(``if null_imposed and others:``). Com um único regressor — o caso de todos os
modelos do SADEN — a restrição é silenciosamente ignorada e o bootstrap usa
resíduos irrestritos. Este módulo implementa as duas variantes de forma
explícita.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np


def group_codes(labels: Sequence[str]) -> tuple[np.ndarray, int]:
    unique = list(dict.fromkeys(labels))
    position = {label: index for index, label in enumerate(unique)}
    return np.array([position[label] for label in labels], dtype="int64"), len(unique)


def cr1_multiplier(n: int, n_groups: int, k: int = 1) -> float:
    return (n_groups / (n_groups - 1.0)) * ((n - 1.0) / (n - k))


def _cluster_sums(x: np.ndarray, z: np.ndarray, codes: np.ndarray, n_groups: int):
    return np.bincount(codes, weights=x * z, minlength=n_groups)


def cr1_fit(
    x: np.ndarray, y: np.ndarray, codes: np.ndarray, n_groups: int, k: int = 1
) -> dict[str, Any]:
    """β, EP agrupado CR1, t, p e crítico — mesma álgebra de ``cluster_vcov``."""
    b = np.bincount(codes, weights=x * x, minlength=n_groups)
    denominator = float(b.sum())
    if denominator <= 0:
        return {"status": "degenerate"}
    a = _cluster_sums(x, y, codes, n_groups)
    beta = float(a.sum() / denominator)
    residuals = y - x * beta
    scores = _cluster_sums(x, residuals, codes, n_groups)
    multiplier = cr1_multiplier(x.size, n_groups, k)
    variance = multiplier * float(np.sum(scores**2)) / denominator**2
    if variance <= 0:
        return {"status": "degenerate"}
    se = math.sqrt(variance)
    t_stat = beta / se
    df = max(n_groups - 1, 1)
    from agroclimate import robust

    return {
        "status": "ok",
        "beta": beta,
        "se": se,
        "t": t_stat,
        "df": df,
        "p": robust.t_sf(t_stat, df),
        "critical": robust.t_critical(0.05, df),
        "n_clusters": n_groups,
        "multiplier": multiplier,
    }


def wild_p(
    x: np.ndarray,
    y: np.ndarray,
    codes: np.ndarray,
    n_groups: int,
    weights: np.ndarray,
    observed_t: float,
    restricted: bool = True,
    observed_beta: float = 0.0,
    k: int = 1,
) -> dict[str, Any]:
    """p-valor do wild cluster bootstrap-t via somas de cluster.

    ``weights`` tem forma ``(n_groups, n_boot)``; ``restricted=True`` impõe H0.
    """
    b = np.bincount(codes, weights=x * x, minlength=n_groups)
    denominator = float(b.sum())
    if denominator <= 0:
        return {"status": "degenerate"}
    if restricted:
        source = y
        shift = 0.0
    else:
        source = y - x * observed_beta
        shift = float(observed_beta)
    sums = _cluster_sums(x, source, codes, n_groups)      # (G,)
    weighted = weights * sums[:, None]                    # (G, B)
    delta = weighted.sum(axis=0) / denominator            # (B,)
    beta_boot = shift + delta
    scores = weighted - delta[None, :] * b[:, None]
    multiplier = cr1_multiplier(x.size, n_groups, k)
    variance = multiplier * np.sum(scores**2, axis=0) / denominator**2
    with np.errstate(divide="ignore", invalid="ignore"):
        se_boot = np.sqrt(variance)
        # sob nulidade irrestrita a distribuição é centrada em beta_hat, então a
        # estatística tem de ser recentrada; sob nulidade imposta já está em 0
        centred = beta_boot - shift if not restricted else beta_boot
        t_boot = np.where(se_boot > 0, centred / se_boot, np.nan)
    valid = t_boot[np.isfinite(t_boot)]
    if valid.size == 0:
        return {"status": "bootstrap_failed"}
    exceed = int(np.sum(np.abs(valid) >= abs(observed_t)))
    return {
        "status": "ok",
        "p_value": float((exceed + 1) / (weights.shape[1] + 1)),
        "n_bootstrap_used": int(valid.size),
        "t_boot_abs_q95": float(np.quantile(np.abs(valid), 0.95)),
        "exceed": exceed,
        "variant": "WCR" if restricted else "WCU",
    }
