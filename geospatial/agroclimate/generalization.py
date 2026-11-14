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

# Linhas de base alternativas, todas construídas **do mesmo conjunto de
# treino** que o modelo:
#
# ``global``     média de todo o treino (convenção da V2.6/V2.7);
# ``state``      média por UF; cai para a global quando a UF está ausente
#                (é o caso do leave-one-UF-out);
# ``state_year`` média por UF e ano, que absorve o choque regional do ano;
#                cai para a média da UF e depois para a global.
#
# A comparação com ``state_year`` é a mais exigente: se o modelo não supera
# essa referência, o ganho atribuído ao clima é, na prática, a recuperação de
# um efeito de região-e-ano que a média agregada não captura.
BASELINES: tuple[str, ...] = ("global", "state", "state_year")

# Variantes do modelo, para que a comparação com as linhas de base seja justa:
#
# ``climate_only``        ``y ~ 1 + clima`` (é o modelo da V2.6/V2.7);
# ``climate_plus_state``  ``y ~ 1 + clima + dummies de UF``. Sem o termo
#                         regional o modelo é estruturalmente incapaz de
#                         reproduzir o nível de produtividade da UF, e perde
#                         para a média da UF por construção — não porque o
#                         clima não ajude, mas porque falta informação.
#
# A pergunta correta é se o clima acrescenta algo **além da região**, e para
# isso o modelo precisa receber a mesma informação que a linha de base.
MODEL_VARIANTS: tuple[str, ...] = ("climate_only", "climate_plus_state")

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


def _design(
    x_climate: np.ndarray,
    state: np.ndarray | None,
    variant: str,
    columns: Sequence[int] | None = None,
) -> tuple[np.ndarray, list[int]]:
    """Monta o design com intercepto e, opcionalmente, dummies de UF.

    ``columns`` são os códigos de UF que viram colunas. Devolve o design e a
    lista de colunas efetivamente usada, para que o teste seja transformado
    com exatamente as mesmas colunas do treino. Estados ausentes do treino
    ficam com todas as dummies em zero e caem no intercepto — o análogo da
    queda para a média global nas linhas de base.
    """
    pieces = [np.ones((x_climate.shape[0], 1))]
    if x_climate.shape[1] > 0:
        pieces.append(x_climate)
    used: list[int] = []
    if variant == "climate_plus_state" and state is not None:
        if columns is None:
            present = sorted({int(s) for s in state.tolist() if s >= 0})
            # a primeira UF é a referência (evita colinearidade com o intercepto)
            used = present[1:]
        else:
            used = list(columns)
        for code in used:
            pieces.append((state == code).astype("float64").reshape(-1, 1))
    elif columns is not None:
        used = []
    return np.hstack(pieces), used


def _fit_predict(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    state_train: np.ndarray | None = None,
    state_test: np.ndarray | None = None,
    variant: str = "climate_only",
) -> np.ndarray | None:
    """OLS com intercepto, ajustado no treino e aplicado ao teste."""
    if variant not in MODEL_VARIANTS:
        raise ValueError(f"variante de modelo desconhecida: {variant!r}")
    train_design, columns = _design(x_train, state_train, variant)
    if train_design.shape[0] <= train_design.shape[1]:
        return None
    if float(np.std(x_train, axis=0).max() if x_train.size else 0.0) == 0.0:
        return None
    beta, *_ = np.linalg.lstsq(train_design, y_train, rcond=None)
    test_design, _ = _design(x_test, state_test, variant, columns=columns)
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


def _baseline_predictions(
    y_train: np.ndarray,
    state_train: np.ndarray,
    year_train: np.ndarray,
    state_test: np.ndarray,
    year_test: np.ndarray,
    n_states: int,
    n_years: int,
) -> dict[str, np.ndarray]:
    """Linhas de base construídas **apenas** com o conjunto de treino.

    A UF e o ano do registro de teste são atributos conhecidos no momento da
    previsão (não são o alvo), por isso podem ser usados para consultar a
    média correspondente no treino. Quando a célula não existe no treino, cai
    para a média da UF e, se necessário, para a média global — nunca para
    informação do teste.
    """
    global_mean = float(np.mean(y_train))
    valid_state = state_train >= 0
    counts = np.bincount(state_train[valid_state], minlength=n_states).astype("float64")
    sums = np.bincount(
        state_train[valid_state], weights=y_train[valid_state], minlength=n_states
    )
    state_mean = np.where(counts > 0, sums / np.maximum(counts, 1.0), global_mean)
    n_cells = n_states * n_years
    combined_train = state_train * n_years + year_train
    counts_cell = np.bincount(combined_train[valid_state], minlength=n_cells).astype(
        "float64"
    )
    sums_cell = np.bincount(
        combined_train[valid_state], weights=y_train[valid_state], minlength=n_cells
    )
    cell_mean = np.where(
        counts_cell > 0,
        sums_cell / np.maximum(counts_cell, 1.0),
        np.repeat(state_mean, n_years),
    )
    state_prediction = np.where(
        state_test >= 0, state_mean[np.maximum(state_test, 0)], global_mean
    )
    combined_test = np.maximum(state_test, 0) * n_years + year_test
    cell_prediction = np.where(state_test >= 0, cell_mean[combined_test], global_mean)
    return {
        "global": np.full(state_test.size, global_mean),
        "state": state_prediction,
        "state_year": cell_prediction,
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
    variant: str = "climate_only",
    equalize: str = "global",
    min_cell_train: int = 200,
    keep_errors: bool = False,
) -> dict[str, Any]:
    """Fatorial 2×2 espaço × tempo com controle opcional de tamanho.

    ``equalize`` define **o que** é equalizado:

    * ``"global"`` (padrão histórico) — um alvo único
      ``size_fraction × n_linhas``; quando o conjunto disponível de um braço
      é menor que o alvo, ele é usado integralmente. Isso **não** equaliza
      por célula: braços com menos material ficam com menos linhas naquelas
      células.
    * ``"per_cell"`` — o alvo de cada célula é o **menor** conjunto
      disponível entre os quatro braços; todos são reamostrados exatamente
      para esse tamanho. Células cujo alvo fique abaixo de
      ``min_cell_train`` são descartadas de **todos** os braços e a perda é
      registrada.

    ``size_fraction`` limita o alvo (``None`` usa o conjunto integral no modo
    global, ou o mínimo por célula no modo ``per_cell``).

    ``variant`` escolhe o modelo: ``climate_only`` (o da V2.6/V2.7) ou
    ``climate_plus_state`` (com dummies de UF, para comparar com a média da
    UF em igualdade de informação).

    ``keep_errors=True`` acrescenta ``row_abs_errors`` e ``row_blocks`` — os
    erros absolutos por linha, na ordem determinística de teste — para que
    duas especificações possam ser comparadas de forma **pareada** (mesmas
    linhas) e não apenas pelas MAEs agregadas.
    """
    if equalize not in ("global", "per_cell"):
        raise ValueError(f"modo de equalizacao desconhecido: {equalize!r}")
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
    abs_base: dict[tuple[str, str], list[np.ndarray]] = {
        (a, name): [] for a, _, _ in ARMS for name in BASELINES
    }
    sq_base: dict[tuple[str, str], list[np.ndarray]] = {
        (a, name): [] for a, _, _ in ARMS for name in BASELINES
    }
    rel_base: dict[tuple[str, str], list[np.ndarray]] = {
        (a, name): [] for a, _, _ in ARMS for name in BASELINES
    }
    observed_parts: list[np.ndarray] = []
    block_parts: list[np.ndarray] = []
    year_parts: list[np.ndarray] = []
    state_parts: list[np.ndarray] = []
    fallback_rows: dict[str, int] = {a: 0 for a, _, _ in ARMS}
    test_rows: dict[str, int] = {a: 0 for a, _, _ in ARMS}
    # --- preparação das células e dos alvos de treino -----------------------
    cells: list[dict[str, Any]] = []
    for space_fold in space_folds:
        in_block = np.isin(block_ids, list(space_fold))
        for time_fold in time_folds:
            in_time = np.isin(year_ids, list(time_fold))
            test_mask = in_block & in_time
            if not test_mask.any():
                continue
            pool_indices: dict[str, np.ndarray] = {}
            for arm, space_separated, time_separated in ARMS:
                mask = ~test_mask
                if space_separated:
                    mask &= ~in_block
                if time_separated:
                    mask &= ~in_time
                pool_indices[arm] = np.flatnonzero(mask)
            cells.append(
                {
                    "test_mask": test_mask,
                    "pools": pool_indices,
                    "min_pool": min(int(v.size) for v in pool_indices.values()),
                }
            )
    kept_cells: list[dict[str, Any]] = []
    dropped_cells = 0
    for cell in cells:
        if equalize == "per_cell":
            target = cell["min_pool"]
            if target_size is not None:
                target = min(target, target_size)
            if target < min_cell_train:
                dropped_cells += 1
                continue
            cell["target"] = int(target)
        kept_cells.append(cell)

    # MAE/RMSE por repetição (as repetições NÃO são observações de teste
    # independentes; guardamos a variação entre elas em separado)
    rep_abs_sum: dict[str, np.ndarray] = {
        a: np.zeros(n_repeats, dtype="float64") for a, _, _ in ARMS
    }
    rep_sq_sum: dict[str, np.ndarray] = {
        a: np.zeros(n_repeats, dtype="float64") for a, _, _ in ARMS
    }
    rep_count: dict[str, np.ndarray] = {
        a: np.zeros(n_repeats, dtype="float64") for a, _, _ in ARMS
    }
    cells_below_target: dict[str, int] = {a: 0 for a, _, _ in ARMS}
    cells_at_target: dict[str, int] = {a: 0 for a, _, _ in ARMS}

    for cell in kept_cells:
        test_mask = cell["test_mask"]
        observed_cell = y_all[test_mask]
        observed_parts.append(observed_cell)
        block_parts.append(block_ids[test_mask])
        year_parts.append(year_ids[test_mask])
        state_parts.append(state_ids[test_mask])
        x_test = x_all[test_mask]
        state_test = state_codes[test_mask]
        year_test = year_codes[test_mask]
        safe_observed = np.where(observed_cell == 0, np.nan, observed_cell)
        for arm_index, (arm, _, _) in enumerate(ARMS):
            pool_index = cell["pools"][arm]
            if pool_index.size == 0:
                continue
            # subconjuntos por bloco, calculados uma vez por célula/braço
            pool_blocks = block_ids[pool_index]
            unique_blocks = np.unique(pool_blocks)
            pools = {
                block: pool_index[pool_blocks == block] for block in unique_blocks
            }
            if equalize == "per_cell":
                target = int(cell["target"])
            else:
                target = target_size
            if target is not None and pool_index.size >= target:
                cells_at_target[arm] += 1
            else:
                cells_below_target[arm] += 1
            cell_abs: list[np.ndarray] = []
            cell_sq: list[np.ndarray] = []
            cell_rel: list[np.ndarray] = []
            cell_base: dict[str, dict[str, list[np.ndarray]]] = {
                name: {"abs": [], "sq": [], "rel": []} for name in BASELINES
            }
            cell_sizes: list[int] = []
            for repeat in range(n_repeats):
                # semente estável: depende de braço, repetição e célula
                draw_rng = np.random.default_rng(
                    seed
                    + 7919 * repeat
                    + 104729 * arm_index
                    + 1299709 * len(observed_parts)
                )
                if target is not None and pool_index.size > target:
                    chosen = stratified_subsample(pools, target, draw_rng)
                else:
                    chosen = pool_index
                # diagnóstico de fallback: UF do teste sem nenhuma linha no treino
                chosen_states = state_codes[chosen]
                chosen_states = chosen_states[chosen_states >= 0]
                counts_train = np.bincount(
                    chosen_states, minlength=len(state_names)
                )
                known = state_test >= 0
                unknown_count = int((~known).sum())
                zero_count = int(
                    np.sum(counts_train[np.maximum(state_test[known], 0)] == 0)
                ) if known.any() else 0
                fallback_rows[arm] += unknown_count + zero_count
                test_rows[arm] += int(state_test.size)
                fitted = _fit_predict(
                    x_all[chosen],
                    y_all[chosen],
                    x_test,
                    state_train=state_codes[chosen],
                    state_test=state_test,
                    variant=variant,
                )
                if fitted is None:
                    continue
                error = fitted - observed_cell
                cell_abs.append(np.abs(error))
                cell_sq.append(np.square(error))
                cell_rel.append(np.abs(error) / safe_observed)
                rep_abs_sum[arm][repeat] += float(np.sum(np.abs(error)))
                rep_sq_sum[arm][repeat] += float(np.sum(np.square(error)))
                rep_count[arm][repeat] += float(error.size)
                baseline_values = _baseline_predictions(
                    y_all[chosen],
                    state_codes[chosen],
                    year_codes[chosen],
                    state_test,
                    year_test,
                    len(state_names),
                    len(year_names),
                )
                for name, values in baseline_values.items():
                    base_error = values - observed_cell
                    cell_base[name]["abs"].append(np.abs(base_error))
                    cell_base[name]["sq"].append(np.square(base_error))
                    cell_base[name]["rel"].append(np.abs(base_error) / safe_observed)
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
            for name in BASELINES:
                abs_base[(arm, name)].append(np.mean(cell_base[name]["abs"], axis=0))
                sq_base[(arm, name)].append(np.mean(cell_base[name]["sq"], axis=0))
                rel_base[(arm, name)].append(np.mean(cell_base[name]["rel"], axis=0))
            train_sizes[arm].append(int(np.mean(cell_sizes)))

    out: dict[str, Any] = {
        "status": "ok",
        "n_rows": n,
        "n_blocks": len(blocks),
        "n_years": len(years),
        "n_states": len({s for s in state_ids.tolist() if s}),
        "n_municipalities": len(set(municipality_ids.tolist())),
        "n_folds": len(space_folds) * len(time_folds),
        "equalize": equalize,
        "min_cell_train": min_cell_train,
        "cells_total": len(cells),
        "cells_used": len(kept_cells),
        "cells_dropped": dropped_cells,
        "size_fraction": size_fraction,
        "n_repeats": n_repeats,
        "target_train_size": target_size,
        "variables": list(variables),
        "arms": {},
    }
    if not observed_parts:
        return {
            "status": "no_test_rows",
            "n_rows": n,
            "equalize": equalize,
            "min_cell_train": min_cell_train,
            "cells_total": len(cells),
            "cells_used": 0,
            "cells_dropped": dropped_cells,
        }
    observed = np.concatenate(observed_parts)
    out["test_blocks"] = np.concatenate(block_parts)
    out["test_years"] = np.concatenate(year_parts)
    out["test_states"] = np.concatenate(state_parts)

    for arm, _, _ in ARMS:
        if not abs_err[arm]:
            out["arms"][arm] = {"status": "no_predictions"}
            continue
        absolute = np.concatenate(abs_err[arm])
        squared = np.concatenate(sq_err[arm])
        relative = np.concatenate(rel_err[arm])
        if absolute.size != observed.size:
            out["arms"][arm] = {
                "status": "length_mismatch",
                "n_predicted": int(absolute.size),
                "n_observed": int(observed.size),
            }
            continue
        model = _summarize(absolute, squared, relative)
        baseline_entries: dict[str, Any] = {}
        for name in BASELINES:
            if not abs_base[(arm, name)]:
                continue
            entry = _summarize(
                np.concatenate(abs_base[(arm, name)]),
                np.concatenate(sq_base[(arm, name)]),
                np.concatenate(rel_base[(arm, name)]),
            )
            entry["gain_percent"] = 100.0 * (
                entry["mae_kg_ha"] - model["mae_kg_ha"]
            ) / entry["mae_kg_ha"]
            baseline_entries[name] = entry
        entry = {
            "status": "ok",
            "train_size_mean": float(np.mean(train_sizes[arm])),
            "train_size_min": int(np.min(train_sizes[arm])),
            "train_size_max": int(np.max(train_sizes[arm])),
            "train_size_sd": float(np.std(train_sizes[arm], ddof=1))
            if len(train_sizes[arm]) > 1
            else 0.0,
            "cells_at_target": cells_at_target[arm],
            "cells_below_target": cells_below_target[arm],
            "model": model,
            "baselines": baseline_entries,
            # compatibilidade com a convenção publicada (média global)
            "baseline": baseline_entries.get("global", {}),
        }
        counts = rep_count[arm]
        valid = counts > 0
        if int(valid.sum()) > 0:
            safe_counts = np.maximum(counts, 1.0)
            mae_r = rep_abs_sum[arm] / safe_counts
            rmse_r = np.sqrt(rep_sq_sum[arm] / safe_counts)
            entry["repeat_metrics"] = {
                "n_repeats_with_predictions": int(valid.sum()),
                "mae_per_repeat": [
                    float(v) if ok else None for v, ok in zip(mae_r, valid)
                ],
                "mae_mean": float(np.mean(mae_r[valid])),
                "mae_sd": float(np.std(mae_r[valid], ddof=1))
                if int(valid.sum()) > 1
                else 0.0,
                "rmse_per_repeat": [
                    float(v) if ok else None for v, ok in zip(rmse_r, valid)
                ],
                "rmse_mean": float(np.mean(rmse_r[valid])),
                "rmse_sd": float(np.std(rmse_r[valid], ddof=1))
                if int(valid.sum()) > 1
                else 0.0,
            }
        if "global" in baseline_entries:
            entry["gain_percent"] = baseline_entries["global"]["gain_percent"]
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
        entry["_abs_base"] = np.concatenate(abs_base[(arm, "global")])
        entry["_abs_baselines"] = {
            name: np.concatenate(abs_base[(arm, name)])
            for name in BASELINES
            if abs_base[(arm, name)]
        }
        if test_rows[arm] > 0:
            entry["state_fallback_share"] = float(
                fallback_rows[arm] / (test_rows[arm] * max(n_repeats, 1))
            )
            entry["state_fallback_rows"] = int(
                round(fallback_rows[arm] / max(n_repeats, 1))
            )
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

    # o modelo supera cada linha de base? (mesmos casos, IC por bloco)
    out["model_vs_baseline"] = {}
    for arm, _, _ in ARMS:
        entry = out["arms"].get(arm, {})
        if entry.get("status") != "ok":
            continue
        for name, values in entry["_abs_baselines"].items():
            out["model_vs_baseline"][f"{arm}_vs_{name}"] = block_bootstrap_difference(
                entry["_abs"], values, out["test_blocks"], n_boot=n_boot, seed=seed
            )

    # comparações entre as próprias linhas de base (aninhamento M0→M1→M1×ano)
    out["baseline_pairs"] = {}
    for arm, _, _ in ARMS:
        entry = out["arms"].get(arm, {})
        if entry.get("status") != "ok":
            continue
        base = entry["_abs_baselines"]
        for left, right in (("state", "global"), ("state_year", "state")):
            if left in base and right in base:
                out["baseline_pairs"][f"{arm}_{left}_minus_{right}"] = (
                    block_bootstrap_difference(
                        base[left],
                        base[right],
                        out["test_blocks"],
                        n_boot=n_boot,
                        seed=seed,
                    )
                )

    # decomposição por UF: modelo vs média da UF (valor incremental do clima
    # dentro de cada UF, que é a granularidade da pergunta da V2.9)
    out["by_state"] = {}
    for arm, _, _ in ARMS:
        entry = out["arms"].get(arm, {})
        if entry.get("status") != "ok":
            continue
        errors = entry["_abs"]
        state_base = entry["_abs_baselines"].get("state")
        per_state: dict[str, Any] = {}
        for state in sorted(set(out["test_states"].tolist())):
            if not state:
                continue
            mask = out["test_states"] == state
            if not mask.any():
                continue
            item = {
                "n": int(mask.sum()),
                "mae_model": float(np.mean(errors[mask])),
            }
            if state_base is not None:
                item["mae_state_baseline"] = float(np.mean(state_base[mask]))
                item["delta_model_minus_state"] = item["mae_model"] - item[
                    "mae_state_baseline"
                ]
            per_state[state] = item
        out["by_state"][arm] = per_state

    # decomposição por ano do erro de cada braço (mecanismo)
    out["by_year"] = {}
    kept_errors: dict[str, np.ndarray] = {}
    for arm, _, _ in ARMS:
        entry = out["arms"].get(arm, {})
        if entry.get("status") != "ok":
            continue
        errors = entry.pop("_abs")
        kept_errors[arm] = errors
        base_errors = entry.pop("_abs_base")
        entry.pop("_abs_baselines", None)
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
    if keep_errors:
        out["row_abs_errors"] = dict(kept_errors)
        out["row_blocks"] = out["test_blocks"]
        out["row_years"] = out["test_years"]
        out["row_states"] = out["test_states"]
    return out


def _haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Distância em km, tratando latitude/longitude como ângulos (não como plano)."""
    radius = 6371.0088
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = phi2 - phi1
    dlambda = np.radians(lon2 - lon1)
    a = (
        np.sin(dphi / 2.0) ** 2
        + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2
    )
    return 2.0 * radius * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def neighbor_holdout(
    rows: Sequence[dict[str, Any]],
    radius_km: float = 200.0,
    min_neighbors: int = 3,
    decay_km: float | None = 100.0,
    n_space_folds: int = 5,
    n_time_folds: int = 5,
    seed: int = 20261114,
    n_boot: int = 1000,
) -> dict[str, Any]:
    """Baseline de **vizinhos históricos** (M1c) no braço TE.

    Para cada célula (bloco espacial × grupo temporal) do protocolo TE, o
    treino contém apenas linhas de **outros blocos** e **outros anos**. A
    previsão de um município de teste é a média das produtividades **já
    observadas no treino** dos municípios vizinhos, ponderada pela distância.

    Não há vazamento porque:

    * o próprio bloco do teste está fora do treino (nenhum vizinho do bloco);
    * o ano de teste está fora do treino (nenhuma produtividade contemporânea);
    * a UF do teste pode estar no treino em outros anos — o fallback para a
      média da UF usa **somente treino**, e é reportado separadamente.

    ``decay_km=None`` usa média simples dos vizinhos; caso contrário os pesos
    são ``exp(-(d/decay)^2)``. O raio, o número mínimo de vizinhos e o
    decaimento são **fixados antes** da avaliação (não escolhidos por TE).

    Devolve MAE de M1c, MAE de M1 (mesmas linhas), IC bootstrap por bloco da
    diferença e cobertura.
    """
    data = [r for r in rows if r.get(TARGET) is not None]
    if not data:
        return {"status": "insufficient_rows"}
    from . import analysis  # import tardio evita ciclo

    y = np.array([float(r[TARGET]) for r in data], dtype="float64")
    blocks = np.array([str(r.get("spatial_block") or "") for r in data])
    years = np.array([str(int(r["year"])) for r in data])
    states = np.array([str(r.get("state") or "") for r in data])
    codes = np.array([str(r["ibge_code"]) for r in data])
    lat = np.array([float(r["latitude"]) for r in data], dtype="float64")
    lon = np.array([float(r["longitude"]) for r in data], dtype="float64")

    block_names = sorted({b for b in blocks.tolist() if b})
    year_names = sorted(set(years.tolist()))
    if len(block_names) < n_space_folds or len(year_names) < 2:
        return {
            "status": "insufficient_groups",
            "n_blocks": len(block_names),
            "n_years": len(year_names),
        }

    # coordenada e município por código (constantes, não dependem do split)
    unique_codes = sorted(set(codes.tolist()))
    code_position = {code: i for i, code in enumerate(unique_codes)}
    code_lat = np.zeros(len(unique_codes))
    code_lon = np.zeros(len(unique_codes))
    code_state = [""] * len(unique_codes)
    for i, code in enumerate(codes.tolist()):
        p = code_position[code]
        code_lat[p] = lat[i]
        code_lon[p] = lon[i]
        code_state[p] = states[i]
    row_code = np.array([code_position[c] for c in codes.tolist()], dtype="int64")

    distances = _haversine_km(
        code_lat[:, None], code_lon[:, None], code_lat[None, :], code_lon[None, :]
    )

    rng = np.random.default_rng(seed)
    space_folds = analysis._blocked_folds(block_names, n_space_folds, rng)
    time_folds = analysis._blocked_folds(year_names, n_time_folds, rng)

    predictions = np.full(len(data), np.nan)
    fallback_state = np.zeros(len(data), dtype=bool)
    fallback_global = np.zeros(len(data), dtype=bool)
    neighbor_counts = np.zeros(len(data), dtype="int64")
    min_distances = np.full(len(data), np.nan)

    for fold_space in space_folds:
        for fold_time in time_folds:
            in_space = np.isin(blocks, list(fold_space))
            in_time = np.isin(years, list(fold_time))
            test_mask = in_space & in_time
            train_mask = ~in_space & ~in_time
            if not test_mask.any():
                continue
            train_rows = np.flatnonzero(train_mask)
            if train_rows.size == 0:
                continue
            # média treinada por município (somente treino)
            muni_mean = np.full(len(unique_codes), np.nan)
            for position in np.unique(row_code[train_rows]).tolist():
                selected = train_rows[row_code[train_rows] == position]
                muni_mean[position] = float(np.mean(y[selected]))
            state_mean: dict[str, float] = {}
            for state in set(states[train_rows].tolist()):
                selected = train_rows[states[train_rows] == state]
                state_mean[state] = float(np.mean(y[selected]))
            global_mean = float(np.mean(y[train_rows]))

            available = np.flatnonzero(np.isfinite(muni_mean))
            for row in np.flatnonzero(test_mask).tolist():
                origin = row_code[row]
                # vizinhos = municípios com média de treino, fora do bloco de teste
                candidate = available[available != origin]
                if candidate.size == 0:
                    predictions[row] = state_mean.get(states[row], global_mean)
                    fallback_state[row] = True
                    continue
                dist = distances[origin, candidate]
                inside = dist <= radius_km
                chosen = candidate[inside]
                neighbor_counts[row] = int(chosen.size)
                if chosen.size:
                    min_distances[row] = float(dist[inside].min())
                if chosen.size < min_neighbors:
                    predictions[row] = state_mean.get(states[row], global_mean)
                    fallback_state[row] = True
                    continue
                weights = np.ones(chosen.size)
                if decay_km:
                    weights = np.exp(-((dist[inside] / decay_km) ** 2))
                values = muni_mean[chosen]
                total = float(weights.sum())
                predictions[row] = (
                    float(np.dot(weights, values) / total) if total > 0 else float(np.mean(values))
                )

    if np.isnan(predictions).any():
        # linhas nunca testadas (não deveria ocorrer com 5×5 dobras em grade)
        missing = np.isnan(predictions)
        global_mean = float(np.mean(y))
        predictions[missing] = global_mean
        fallback_global[missing] = True

    errors_neighbor = np.abs(predictions - y)
    state_pred = np.zeros(len(data))
    state_available = np.zeros(len(data), dtype=bool)
    for fold_space in space_folds:
        for fold_time in time_folds:
            in_space = np.isin(blocks, list(fold_space))
            in_time = np.isin(years, list(fold_time))
            test_mask = in_space & in_time
            train_mask = ~in_space & ~in_time
            if not test_mask.any() or not train_mask.any():
                continue
            fallback = float(np.mean(y[train_mask]))
            for state in set(states[test_mask].tolist()):
                selected = train_mask & (states == state)
                value = float(np.mean(y[selected])) if selected.any() else fallback
                rows_state = test_mask & (states == state)
                state_pred[rows_state] = value
                state_available[rows_state] = True
    if not state_available.all():
        state_pred[~state_available] = float(np.mean(y))
    errors_state = np.abs(state_pred - y)

    interval = block_bootstrap_difference(
        errors_neighbor, errors_state, blocks, n_boot=n_boot, seed=seed
    )
    state_alignment = errors_neighbor - errors_state
    covered = neighbor_counts >= min_neighbors
    return {
        "status": "ok",
        "n": int(len(data)),
        "n_blocks": len(block_names),
        "n_years": len(year_names),
        "n_municipalities": len(unique_codes),
        "radius_km": radius_km,
        "min_neighbors": min_neighbors,
        "decay_km": decay_km,
        "mae": float(np.mean(errors_neighbor)),
        "mae_baseline_state": float(np.mean(errors_state)),
        "delta_mae": interval["delta_mae"],
        "ci95": interval["ci95"],
        "n_boot": n_boot,
        "coverage_direct": float(np.mean(covered)),
        "fallback_state_share": float(np.mean(fallback_state)),
        "fallback_global_share": float(np.mean(fallback_global)),
        "neighbor_count_median": float(np.median(neighbor_counts)),
        "neighbor_count_p10": float(np.quantile(neighbor_counts, 0.10)),
        "min_distance_median_km": (
            float(np.median(min_distances[np.isfinite(min_distances)]))
            if np.isfinite(min_distances).any()
            else None
        ),
        "worse_rows_share": float(np.mean(state_alignment > 0)),
        "row_predictions": predictions,
        "row_abs_errors": errors_neighbor,
        "row_abs_baseline": errors_state,
        "row_blocks": blocks,
        "row_codes": codes,
    }
