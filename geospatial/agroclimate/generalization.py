"""Generalização temporal-espacial (V2.8, D87).

A V2.7 usou o protocolo P5, que remove do treino **ao mesmo tempo** os blocos
espaciais e os anos da dobra. Isso deixa dois mecanismos confundidos:

* a ausência do **ano** compartilhado (a hipótese que se queria testar);
* a redução do treino (64% contra 80% do P3), que pode degradar qualquer
  modelo por si só.

Este módulo resolve o confundimento com um **fatorial 2×2 espaço × tempo**
sobre a mesma grade de dobras do P5, e com **controle de tamanho**: todas as
combinações são reamostradas para o mesmo número de linhas de treino, de modo
que a única diferença entre elas seja *qual* informação foi removida.

Braços
------
``SS`` espaço compartilhado, tempo compartilhado
    treino = todas as linhas fora do cruzamento testado;
``SE`` espaço separado, tempo compartilhado
    treino = linhas de **outros blocos** (equivale ao P3);
``TS`` espaço compartilhado, tempo separado
    treino = linhas de **outros anos**;
``TE`` espaço separado, tempo separado
    treino = linhas de outros blocos **e** outros anos (equivale ao P5).

Em todos os braços a linha de teste nunca entra no treino. O conjunto de
teste é sempre o mesmo (cada linha é prevista exatamente uma vez), portanto
as MAEs dos quatro braços são diretamente comparáveis.

Efeitos estimados
-----------------
* **efeito do espaço**, com o tempo compartilhado: ``SE − SS``;
* **efeito do tempo**, com o espaço compartilhado: ``TS − SS``;
* **efeito do tempo**, com o espaço separado: ``TE − SE``;
* **interação**: ``(TE − SE) − (TS − SS)``.

As duas estimativas do efeito do tempo usam informações diferentes sobre a
identidade do município e devem concordar se o mecanismo for de fato o canal
do ano.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np

ARMS: tuple[tuple[str, bool, bool], ...] = (
    ("SS", False, False),
    ("SE", True, False),
    ("TS", False, True),
    ("TE", True, True),
)

TARGET = "yield_kg_ha"


# --------------------------------------------------------------------------
# utilidades numéricas
# --------------------------------------------------------------------------
def _matrix(rows: Sequence[dict[str, Any]], variables: Sequence[str]) -> np.ndarray:
    """Design sem intercepto, com a mesma convenção de ``analysis.fit_predict``.

    Valores ausentes viram 0,0 — convenção herdada da V2.6, preservada para
    que a comparação com os protocolos publicados seja exata.
    """
    return np.array(
        [[float(r.get(v) or 0.0) for v in variables] for r in rows], dtype="float64"
    )


def _fit_predict(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
) -> np.ndarray | None:
    """OLS com intercepto, ajustado no treino e aplicado ao teste."""
    if x_train.shape[0] <= x_train.shape[1] + 1:
        return None
    if float(np.std(x_train, axis=0).max()) == 0.0:
        return None
    design = np.column_stack([np.ones(x_train.shape[0]), x_train])
    beta, *_ = np.linalg.lstsq(design, y_train, rcond=None)
    test_design = np.column_stack([np.ones(x_test.shape[0]), x_test])
    return test_design @ beta


def stratified_subsample(
    pools: dict[str, np.ndarray],
    target_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Amostra ``target_size`` linhas preservando a composição por bloco.

    A alocação é proporcional ao tamanho de cada bloco (maior resto para
    fechar o total). Preservar a composição espacial evita que o controle de
    tamanho introduza, ele mesmo, uma mudança de composição.
    """
    names = sorted(pools)
    sizes = np.array([len(pools[n]) for n in names], dtype="float64")
    total = int(sizes.sum())
    if target_size >= total:
        return np.concatenate([pools[n] for n in names])
    if target_size <= 0:
        return np.empty(0, dtype="int64")
    quota = sizes * (target_size / total)
    base = np.floor(quota).astype(int)
    remainder = target_size - int(base.sum())
    if remainder > 0:
        order = np.argsort(-(quota - base))
        for position in order[:remainder]:
            base[position] += 1
    pieces = []
    for name, take in zip(names, base):
        pool = pools[name]
        if take <= 0:
            continue
        if take >= len(pool):
            pieces.append(pool)
        else:
            pieces.append(rng.choice(pool, size=int(take), replace=False))
    if not pieces:
        return np.empty(0, dtype="int64")
    return np.concatenate(pieces)


def block_bootstrap_difference(
    abs_errors_a: np.ndarray,
    abs_errors_b: np.ndarray,
    blocks: np.ndarray,
    n_boot: int = 1000,
    seed: int = 20261114,
) -> dict[str, Any]:
    """IC bootstrap **por bloco** da diferença de MAE entre dois braços.

    Recebe **erros absolutos** já agregados por linha (a média sobre as
    repetições de reamostragem é feita antes), de modo que a MAE de uma
    reamostra é simplesmente ``soma/n``.

    As observações do mesmo bloco são dependentes; reamostrar linhas
    isoladamente subestimaria a incerteza. Reamostra-se o bloco inteiro, o
    que preserva a unidade de dependência espacial. Como os blocos entram com
    reposição, basta acumular somas e contagens por bloco.
    """
    names = sorted(set(blocks.tolist()))
    position = {name: i for i, name in enumerate(names)}
    codes = np.array([position[b] for b in blocks.tolist()], dtype="int64")
    sum_a = np.bincount(codes, weights=abs_errors_a, minlength=len(names))
    sum_b = np.bincount(codes, weights=abs_errors_b, minlength=len(names))
    counts = np.bincount(codes, minlength=len(names)).astype("float64")
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(names), size=(n_boot, len(names)))
    total_n = counts[picks].sum(axis=1)
    mae_a = sum_a[picks].sum(axis=1) / total_n
    mae_b = sum_b[picks].sum(axis=1) / total_n
    deltas = mae_a - mae_b
    return {
        "delta_mae": float(np.mean(abs_errors_a) - np.mean(abs_errors_b)),
        "ci95": [
            float(np.quantile(deltas, 0.025)),
            float(np.quantile(deltas, 0.975)),
        ],
        "n_blocks": len(names),
        "n_boot": n_boot,
    }


# --------------------------------------------------------------------------
# fatorial
# --------------------------------------------------------------------------
def _summarize(absolute: np.ndarray, squared: np.ndarray, relative: np.ndarray) -> dict[str, Any]:
    """Resume erros já acumulados (média sobre repetições de reamostragem).

    Guardar ``|e|``, ``e²`` e ``|e|/y`` em vez dos erros assinados permite
    combinar várias repetições da mesma linha sem inflar o n: a MAE final é a
    média das MAEs de cada repetição, e cada linha continua contando uma vez.
    """
    return {
        "mae_kg_ha": float(np.mean(absolute)),
        "rmse_kg_ha": float(np.sqrt(np.mean(squared))),
        "mape_percent": float(np.mean(relative) * 100.0),
        "n": int(absolute.size),
    }


def factorial_holdout(
    rows: Sequence[dict[str, Any]],
    variables: Sequence[str],
    n_space_folds: int = 5,
    n_time_folds: int = 5,
    seed: int = 20261113,
    size_fraction: float | None = None,
    n_repeats: int = 1,
    n_boot: int = 1000,
) -> dict[str, Any]:
    """Fatorial 2×2 espaço × tempo com controle opcional de tamanho.

    ``size_fraction`` fixa o treino de **cada** braço em
    ``size_fraction × n_linhas``, reamostrado ``n_repeats`` vezes com sementes
    distintas. ``None`` usa o treino integral de cada braço.
    """
    from . import analysis  # import tardio evita ciclo

    data = [r for r in rows if r.get(TARGET) is not None]
    if not data:
        return {"status": "insufficient_rows", "n": 0}
    x_all = _matrix(data, variables)
    y_all = np.array([float(r[TARGET]) for r in data], dtype="float64")
    block_ids = np.array([str(r.get("spatial_block") or "") for r in data])
    year_ids = np.array([str(int(r["year"])) for r in data])
    state_ids = np.array([str(r.get("state") or "") for r in data])
    municipality_ids = np.array([str(r["ibge_code"]) for r in data])

    blocks = sorted({b for b in block_ids.tolist() if b})
    years = sorted(set(year_ids.tolist()))
    if len(blocks) < n_space_folds or len(years) < 2:
        return {
            "status": "insufficient_groups",
            "n_blocks": len(blocks),
            "n_years": len(years),
        }
    rng = np.random.default_rng(seed)
    space_folds = analysis._blocked_folds(blocks, n_space_folds, rng)
    time_folds = analysis._blocked_folds(years, n_time_folds, rng)

    n = len(data)
    target_size = None if size_fraction is None else int(round(size_fraction * n))

    state_names = sorted({s for s in state_ids.tolist() if s})
    state_position = {name: i for i, name in enumerate(state_names)}
    state_codes = np.array([state_position.get(s, -1) for s in state_ids.tolist()], dtype="int64")
    year_names = sorted(set(year_ids.tolist()))
    year_position = {name: i for i, name in enumerate(year_names)}
    year_codes = np.array([year_position[y] for y in year_ids.tolist()], dtype="int64")

    predictions: dict[str, list[np.ndarray]] = {a: [] for a, _, _ in ARMS}
    baselines: dict[str, list[np.ndarray]] = {a: [] for a, _, _ in ARMS}
    train_sizes: dict[str, list[int]] = {a: [] for a, _, _ in ARMS}
    state_counts: dict[str, np.ndarray] = {
        a: np.zeros(len(state_names), dtype="float64") for a, _, _ in ARMS
    }
    year_counts: dict[str, np.ndarray] = {
        a: np.zeros(len(year_names), dtype="float64") for a, _, _ in ARMS
    }
    # erros por linha, já médios sobre as repetições (|e|, e², |e|/y)
    abs_err: dict[str, list[np.ndarray]] = {a: [] for a, _, _ in ARMS}
    sq_err: dict[str, list[np.ndarray]] = {a: [] for a, _, _ in ARMS}
    rel_err: dict[str, list[np.ndarray]] = {a: [] for a, _, _ in ARMS}
    abs_base: dict[str, list[np.ndarray]] = {a: [] for a, _, _ in ARMS}
    sq_base: dict[str, list[np.ndarray]] = {a: [] for a, _, _ in ARMS}
    rel_base: dict[str, list[np.ndarray]] = {a: [] for a, _, _ in ARMS}
    observed_parts: list[np.ndarray] = []
    block_parts: list[np.ndarray] = []
    year_parts: list[np.ndarray] = []
    for space_fold in space_folds:
        in_block = np.isin(block_ids, list(space_fold))
        for time_fold in time_folds:
            in_time = np.isin(year_ids, list(time_fold))
            test_mask = in_block & in_time
            if not test_mask.any():
                continue
            observed_cell = y_all[test_mask]
            observed_parts.append(observed_cell)
            block_parts.append(block_ids[test_mask])
            year_parts.append(year_ids[test_mask])
            x_test = x_all[test_mask]
            safe_observed = np.where(observed_cell == 0, np.nan, observed_cell)
            for arm_index, (arm, space_separated, time_separated) in enumerate(ARMS):
                pool_mask = ~test_mask
                if space_separated:
                    pool_mask &= ~in_block
                if time_separated:
                    pool_mask &= ~in_time
                pool_index = np.flatnonzero(pool_mask)
                if pool_index.size == 0:
                    continue
                # subconjuntos por bloco, calculados uma vez por célula/braço
                pool_blocks = block_ids[pool_index]
                unique_blocks = np.unique(pool_blocks)
                pools = {
                    block: pool_index[pool_blocks == block] for block in unique_blocks
                }
                cell_abs: list[np.ndarray] = []
                cell_sq: list[np.ndarray] = []
                cell_rel: list[np.ndarray] = []
                cell_abs_b: list[np.ndarray] = []
                cell_sq_b: list[np.ndarray] = []
                cell_rel_b: list[np.ndarray] = []
                cell_sizes: list[int] = []
                for repeat in range(n_repeats):
                    # semente estável: depende de braço, repetição e célula
                    draw_rng = np.random.default_rng(
                        seed
                        + 7919 * repeat
                        + 104729 * arm_index
                        + 1299709 * len(observed_parts)
                    )
                    if target_size is not None and pool_index.size > target_size:
                        chosen = stratified_subsample(pools, target_size, draw_rng)
                    else:
                        chosen = pool_index
                    fitted = _fit_predict(x_all[chosen], y_all[chosen], x_test)
                    if fitted is None:
                        continue
                    error = fitted - observed_cell
                    baseline_value = float(np.mean(y_all[chosen]))
                    base_error = np.full(observed_cell.size, baseline_value) - observed_cell
                    cell_abs.append(np.abs(error))
                    cell_sq.append(np.square(error))
                    cell_rel.append(np.abs(error) / safe_observed)
                    cell_abs_b.append(np.abs(base_error))
                    cell_sq_b.append(np.square(base_error))
                    cell_rel_b.append(np.abs(base_error) / safe_observed)
                    cell_sizes.append(int(chosen.size))
                    kept = state_codes[chosen]
                    kept = kept[kept >= 0]
                    state_counts[arm] += np.bincount(kept, minlength=len(state_names))
                    year_counts[arm] += np.bincount(
                        year_codes[chosen], minlength=len(year_names)
                    )
                if not cell_abs:
                    continue
                abs_err[arm].append(np.mean(cell_abs, axis=0))
                sq_err[arm].append(np.mean(cell_sq, axis=0))
                rel_err[arm].append(np.mean(cell_rel, axis=0))
                abs_base[arm].append(np.mean(cell_abs_b, axis=0))
                sq_base[arm].append(np.mean(cell_sq_b, axis=0))
                rel_base[arm].append(np.mean(cell_rel_b, axis=0))
                train_sizes[arm].append(int(np.mean(cell_sizes)))

    out: dict[str, Any] = {
        "status": "ok",
        "n_rows": n,
        "n_blocks": len(blocks),
        "n_years": len(years),
        "n_states": len({s for s in state_ids.tolist() if s}),
        "n_municipalities": len(set(municipality_ids.tolist())),
        "n_folds": len(space_folds) * len(time_folds),
        "size_fraction": size_fraction,
        "n_repeats": n_repeats,
        "target_train_size": target_size,
        "variables": list(variables),
        "arms": {},
    }
    if not observed_parts:
        return {"status": "no_test_rows", "n_rows": n}
    observed = np.concatenate(observed_parts)
    out["test_blocks"] = np.concatenate(block_parts)
    out["test_years"] = np.concatenate(year_parts)

    for arm, _, _ in ARMS:
        if not abs_err[arm]:
            out["arms"][arm] = {"status": "no_predictions"}
            continue
        absolute = np.concatenate(abs_err[arm])
        squared = np.concatenate(sq_err[arm])
        relative = np.concatenate(rel_err[arm])
        absolute_base = np.concatenate(abs_base[arm])
        squared_base = np.concatenate(sq_base[arm])
        relative_base = np.concatenate(rel_base[arm])
        if absolute.size != observed.size:
            out["arms"][arm] = {
                "status": "length_mismatch",
                "n_predicted": int(absolute.size),
                "n_observed": int(observed.size),
            }
            continue
        entry = {
            "status": "ok",
            "train_size_mean": float(np.mean(train_sizes[arm])),
            "train_size_min": int(np.min(train_sizes[arm])),
            "model": _summarize(absolute, squared, relative),
            "baseline": _summarize(absolute_base, squared_base, relative_base),
        }
        entry["gain_percent"] = 100.0 * (
            entry["baseline"]["mae_kg_ha"] - entry["model"]["mae_kg_ha"]
        ) / entry["baseline"]["mae_kg_ha"]
        total_state = float(state_counts[arm].sum())
        if total_state > 0:
            entry["train_state_share"] = {
                name: float(value / total_state)
                for name, value in zip(state_names, state_counts[arm])
            }
        total_year = float(year_counts[arm].sum())
        if total_year > 0:
            entry["train_year_share"] = {
                name: float(value / total_year)
                for name, value in zip(year_names, year_counts[arm])
            }
        entry["_abs"] = absolute
        entry["_abs_base"] = absolute_base
        out["arms"][arm] = entry

    # diferenças pareadas com bootstrap por bloco
    pairs = [
        ("SS", "SE", "efeito do espaco (tempo compartilhado)"),
        ("SS", "TS", "efeito do tempo (espaco compartilhado)"),
        ("SE", "TE", "efeito do tempo (espaco separado)"),
        ("TS", "TE", "efeito do espaco (tempo separado)"),
    ]
    out["paired"] = {}
    for a, b, label in pairs:
        if out["arms"].get(a, {}).get("status") != "ok":
            continue
        if out["arms"].get(b, {}).get("status") != "ok":
            continue
        out["paired"][f"{a}_minus_{b}"] = {
            "label": label,
            "model": block_bootstrap_difference(
                out["arms"][a]["_abs"],
                out["arms"][b]["_abs"],
                out["test_blocks"],
                n_boot=n_boot,
                seed=seed,
            ),
            "baseline": block_bootstrap_difference(
                out["arms"][a]["_abs_base"],
                out["arms"][b]["_abs_base"],
                out["test_blocks"],
                n_boot=n_boot,
                seed=seed,
            ),
        }

    # decomposição por ano do erro de cada braço (mecanismo)
    out["by_year"] = {}
    for arm, _, _ in ARMS:
        entry = out["arms"].get(arm, {})
        if entry.get("status") != "ok":
            continue
        errors = entry.pop("_abs")
        base_errors = entry.pop("_abs_base")
        per_year = {}
        for year in sorted(set(out["test_years"].tolist())):
            mask = out["test_years"] == year
            if not mask.any():
                continue
            per_year[year] = {
                "mae_model": float(np.mean(errors[mask])),
                "mae_baseline": float(np.mean(base_errors[mask])),
                "n": int(mask.sum()),
            }
        entry["by_year"] = per_year
        out["by_year"][arm] = per_year
    return out
