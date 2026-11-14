"""Inclinações climáticas heterogêneas por UF (V3.2, D104).

Duas perguntas distintas, estimadores distintos:

1. **Associação** — a inclinação climática difere entre UFs? Estimador
   *within* de dois fatores (município e ano) com interações UF × clima, erro
   agrupado por bloco espacial (CR1). É o mesmo estimador usado em
   ``cycle.interaction_test`` (D94) para diferença de inclinação entre grupos;
   aqui generalizado para várias UFs e testado primeiro de forma **global**.
2. **Generalização** — permitir inclinações heterogêneas melhora a previsão
   fora da amostra? Isso vive em ``generalization.factorial_holdout`` com
   ``interactions=True`` (e ``penalty_grid`` para partial pooling).

Manter os dois separados é deliberado: um coeficiente pode diferir sem melhorar
a previsão, e um modelo pode prever melhor sem coeficientes estaduais precisos.

O teste global vem antes de qualquer contraste estadual: uma tabela de
p-valores por UF não é evidência de heterogeneidade.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from . import robust, spatial_inference


def f_sf(statistic: float, df1: float, df2: float) -> float:
    """Cauda superior da distribuição F (via beta incompleta regularizada)."""
    if statistic is None or not np.isfinite(statistic) or statistic <= 0.0:
        return 1.0
    if df1 <= 0 or df2 <= 0:
        return 1.0
    argument = df2 / (df2 + df1 * float(statistic))
    return float(robust.betainc(df2 / 2.0, df1 / 2.0, argument))


def wald_test(
    coefficients: np.ndarray,
    vcov: np.ndarray,
    indices: Sequence[int],
    n_clusters: int,
) -> dict[str, Any]:
    """Teste de Wald conjunto de que os coeficientes em ``indices`` são zero.

    A VCV já vem com a correção CR1 (``G/(G−1) · (N−1)/(N−K)``). O qui-quadrado
    de Wald é convertido em ``F = Wald/q`` com referência ``F(q, G−1)``, que é a
    aproximação usual com poucos agrupamentos e evita superconfiança.
    """
    indices = [int(i) for i in indices]
    if not indices:
        return {"status": "empty", "statistic": None, "p_value": None}
    block = np.asarray(coefficients)[indices]
    sub = np.asarray(vcov)[np.ix_(indices, indices)]
    if not np.all(np.isfinite(sub)):
        return {"status": "non_finite_vcov", "statistic": None, "p_value": None}
    try:
        solved = np.linalg.solve(sub, block)
    except np.linalg.LinAlgError:
        solved = np.linalg.pinv(sub) @ block
    wald = float(block @ solved)
    q = len(indices)
    if not np.isfinite(wald) or wald < 0:
        return {"status": "degenerate", "statistic": None, "p_value": None}
    statistic = wald / q
    degrees = max(int(n_clusters) - 1, 1)
    return {
        "status": "ok",
        "wald": wald,
        "statistic": statistic,
        "df1": q,
        "df2": degrees,
        "p_value": f_sf(statistic, q, degrees),
        "n_restrictions": q,
    }


def slope_heterogeneity(
    rows: Sequence[dict[str, Any]],
    variables: Sequence[str],
    target: str = "yield_kg_ha",
    state_key: str = "state",
    block_key: str = "spatial_block",
    municipality_key: str = "ibge_code",
    year_key: str = "year",
    min_rows: int = 400,
    min_rows_per_state: int = 60,
    cluster: str = "two_way",
) -> dict[str, Any]:
    """Testa H0 (inclinações comuns entre UFs) e reporta contrastes por UF.

    Modelo, após transformação *within* de município e ano::

        y_w = Σ_j b_j · x_jw + Σ_s Σ_j d_sj · (x_j · 1[UF = s])_w + e

    ``b_j`` é a inclinação da UF de referência e ``d_sj`` a **diferença** de
    inclinação da UF ``s`` em relação a ela. O teste global de cada variável
    ``j`` é ``d_·j = 0`` conjuntamente.

    ``cluster`` escolhe a unidade independente:

    * ``"two_way"`` (padrão V3.2) — agrupamento duplo por **UF×ano** e por
      **município**. É o correto aqui: a anomalia climática é essencialmente
      a mesma para todos os municípios de uma UF no mesmo ano, então agrupar
      por bloco espacial (que é menor que a UF) trataria milhares de linhas
      como quase independentes e produziria p-valores otimistas.
    * ``"block"`` — agrupamento por bloco espacial, como nas versões
      anteriores; mantido para comparabilidade e reportado como sensibilidade.

    UFs com menos de ``min_rows_per_state`` linhas continuam no teste global
    (omitir uma UF do conjunto de interações mudaria a hipótese nula), mas são
    marcadas como não interpretáveis no contraste individual.
    """
    usable = [
        row
        for row in rows
        if row.get(target) is not None
        and all(row.get(v) is not None for v in variables)
        and row.get(state_key)
        and row.get(block_key)
    ]
    if len(usable) < min_rows:
        return {"status": "insufficient_rows", "n": len(usable)}

    municipalities = [str(row[municipality_key]) for row in usable]
    years = [row[year_key] for row in usable]
    states = [str(row[state_key]) for row in usable]
    blocks = [str(row[block_key]) for row in usable]

    y = np.array([float(row[target]) for row in usable], dtype="float64")
    columns = {
        variable: np.array([float(row[variable]) for row in usable], dtype="float64")
        for variable in variables
    }
    y_within = spatial_inference.within_transform(y, municipalities, years)
    x_within = {
        variable: spatial_inference.within_transform(
            columns[variable], municipalities, years
        )
        for variable in variables
    }

    state_names = sorted(set(states))
    reference = state_names[0]
    contrasts = state_names[1:]

    design_parts: list[np.ndarray] = []
    labels: list[tuple[str, str]] = []
    for variable in variables:
        design_parts.append(x_within[variable])
        labels.append((variable, reference))
    for state in contrasts:
        indicator = np.array([1.0 if s == state else 0.0 for s in states])
        for variable in variables:
            product = spatial_inference.within_transform(
                columns[variable] * indicator, municipalities, years
            )
            design_parts.append(product)
            labels.append((variable, state))
    design = np.column_stack(design_parts)

    if float(np.std(design, axis=0).max()) == 0.0:
        return {"status": "degenerate_design", "n": len(usable)}
    if design.shape[0] <= design.shape[1]:
        return {"status": "not_identified", "n": len(usable), "k": design.shape[1]}

    beta, *_ = np.linalg.lstsq(design, y_within, rcond=None)
    residuals = y_within - design @ beta
    if cluster == "two_way":
        state_year = [f"{s}||{y}" for s, y in zip(states, years)]
        vcv, info = robust.two_way_cluster_vcov(
            design, residuals, state_year, municipalities, correction=robust.CR1
        )
        n_clusters = min(info["n_clusters_a"], info["n_clusters_b"])
        cluster_info = {
            "scheme": "two_way",
            "clusters_a": "UF x ano",
            "clusters_b": "municipio",
            "n_clusters_a": info["n_clusters_a"],
            "n_clusters_b": info["n_clusters_b"],
        }
    elif cluster == "block":
        vcv, info = robust.cluster_vcov(design, residuals, blocks, correction=robust.CR1)
        n_clusters = int(info["n_clusters"])
        cluster_info = {"scheme": "block", "clusters_a": "bloco espacial", "n_clusters_a": n_clusters}
    else:
        raise ValueError(f"esquema de agrupamento desconhecido: {cluster!r}")
    degrees = max(int(n_clusters) - 1, 1)

    # --- teste global por variável -----------------------------------------
    global_tests: dict[str, Any] = {}
    for variable in variables:
        indices = [i for i, (v, _) in enumerate(labels) if v == variable and _ != reference]
        test = wald_test(beta, vcv, indices, n_clusters)
        test["reference_state"] = reference
        test["reference_slope"] = float(beta[labels.index((variable, reference))])
        global_tests[variable] = test

    # --- contrastes por UF (secundários/descritivos) ------------------------
    counts: dict[str, int] = {}
    for state in states:
        counts[state] = int(sum(1 for s in states if s == state))
    raw_p: dict[str, float] = {}
    entries: dict[str, dict[str, Any]] = {}
    for variable in variables:
        reference_index = labels.index((variable, reference))
        for state in contrasts:
            index = labels.index((variable, state))
            coefficient = float(beta[index])
            std_error = float(np.sqrt(max(vcv[index, index], 0.0)))
            if robust.degenerate_std_error(coefficient, std_error):
                statistic, p_value = None, None
            else:
                statistic = coefficient / std_error
                p_value = robust.t_sf(statistic, degrees)
            critical = robust.t_critical(0.05, degrees)
            key = f"{variable}|{state}"
            entries[key] = {
                "variable": variable,
                "state": state,
                "reference_state": reference,
                "difference": coefficient,
                "std_error": std_error,
                "t_statistic": statistic,
                "p_value": p_value,
                "ci95": [
                    coefficient - critical * std_error,
                    coefficient + critical * std_error,
                ],
                "n_rows_state": counts[state],
                "identified": counts[state] >= min_rows_per_state,
            }
            if p_value is not None:
                raw_p[key] = p_value
    adjusted = robust.holm_adjust(raw_p) if raw_p else {}
    for key, value in entries.items():
        value["p_holm"] = adjusted.get(key)

    # inclinações implícitas por UF (independentes da escolha da referência):
    # facilitam a leitura e não alteram nenhuma inferência.
    slopes_by_state: dict[str, dict[str, float]] = {}
    for state in state_names:
        slopes_by_state[state] = {}
        for variable in variables:
            reference_slope = float(beta[labels.index((variable, reference))])
            if state == reference:
                slopes_by_state[state][variable] = reference_slope
            else:
                difference = entries[f"{variable}|{state}"]["difference"]
                slopes_by_state[state][variable] = reference_slope + difference

    return {
        "status": "ok",
        "n": len(usable),
        "n_clusters": int(n_clusters),
        "cluster_info": cluster_info,
        "df": degrees,
        "states": state_names,
        "reference_state": reference,
        "variables": list(variables),
        "common_slopes": {
            variable: float(beta[labels.index((variable, reference))]) for variable in variables
        },
        "slopes_by_state": slopes_by_state,
        "global_tests": global_tests,
        "contrasts": entries,
        "multiplicity": {
            "family": "contrastes por UF × variável dentro da cultura",
            "size": len(entries),
            "procedure": "Holm",
        },
    }


def coverage_diagnostics(
    rows: Sequence[dict[str, Any]],
    variables: Sequence[str],
    target: str = "yield_kg_ha",
    state_key: str = "state",
    block_key: str = "spatial_block",
    municipality_key: str = "ibge_code",
    year_key: str = "year",
) -> dict[str, Any]:
    """Diagnóstico de identificabilidade por UF (Fase 3 do roadmap V3.2).

    Antes de estimar inclinações estaduais é preciso saber se há variação
    suficiente. Reporta, por UF: linhas, municípios, anos, blocos, ausências,
    dispersão de cada preditor, **variação dentro do município** (a que
    identifica a inclinação no modelo *within*) e o número de valores únicos.
    """
    summaries: dict[str, Any] = {}
    for state in sorted({str(row.get(state_key)) for row in rows if row.get(state_key)}):
        subset = [row for row in rows if str(row.get(state_key)) == state]
        municipalities = [str(row.get(municipality_key)) for row in subset]
        years = [row.get(year_key) for row in subset]
        entry: dict[str, Any] = {
            "n_rows": len(subset),
            "n_municipalities": len(set(municipalities)),
            "n_years": len(set(years)),
            "n_blocks": len({str(row.get(block_key)) for row in subset if row.get(block_key)}),
            "yield_mean": None,
            "yield_sd": None,
            "variables": {},
        }
        values = [
            float(row[target])
            for row in subset
            if row.get(target) is not None
        ]
        if values:
            entry["yield_mean"] = float(np.mean(values))
            entry["yield_sd"] = float(np.std(values))
        for variable in variables:
            column = np.array(
                [float(row[variable]) if row.get(variable) is not None else np.nan for row in subset],
                dtype="float64",
            )
            observed = np.isfinite(column)
            if not observed.any():
                entry["variables"][variable] = {"missing_share": 1.0}
                continue
            filled = np.where(observed, column, np.nan)
            presence = observed.astype("float64")
            # média por município, ignorando ausentes
            municipality_means: dict[str, list[float]] = {}
            for index, municipality in enumerate(municipalities):
                if observed[index]:
                    municipality_means.setdefault(municipality, []).append(float(column[index]))
            between = np.array([np.mean(v) for v in municipality_means.values()])
            deviations = []
            for index, municipality in enumerate(municipalities):
                if observed[index] and municipality in municipality_means:
                    deviations.append(
                        float(column[index]) - float(np.mean(municipality_means[municipality]))
                    )
            within = np.array(deviations, dtype="float64") if deviations else np.array([0.0])
            entry["variables"][variable] = {
                "missing_share": float(1.0 - presence.mean()),
                "mean": float(np.nanmean(filled)),
                "sd": float(np.nanstd(filled)),
                "unique_values": int(len(set(np.round(filled[observed], 6).tolist()))),
                "between_municipality_sd": float(np.std(between)) if between.size else 0.0,
                "within_municipality_sd": float(np.std(within)) if within.size else 0.0,
                "within_share_of_variance": (
                    float(np.var(within) / (np.var(within) + np.var(between)))
                    if within.size and between.size and (np.var(within) + np.var(between)) > 0
                    else None
                ),
            }
        summaries[state] = entry
    return {"states": summaries}
