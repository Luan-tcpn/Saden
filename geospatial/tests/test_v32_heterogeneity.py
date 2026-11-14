"""V3.2 — inclinações heterogêneas por UF (D104).

Cobre: montagem do design com interações, ridge só nos desvios estaduais,
seleção de encolhimento dentro do treino, teste global de Wald, poder e
falsos positivos do teste de heterogeneidade, diagnóstico de identificabilidade
e o pareamento das comparações preditivas.

Os testes são determinísticos (sementes fixas) e não dependem de arquivos
derivados: os dados sintéticos têm estrutura conhecida, para que a asserção
seja sobre *comportamento estatístico*, não sobre um número copiado.
"""

from __future__ import annotations

import numpy as np
import pytest

from agroclimate import generalization, heterogeneity

PRIMARY = ("precip", "temp")


def _state_rows(slopes, n_municipalities=40, n_years=8, noise=1.0, seed=7):
    """Dados com inclinações conhecidas por UF, variação própria por município."""
    rng = np.random.default_rng(seed)
    rows = []
    states = sorted(slopes)
    for state_index, state in enumerate(states):
        for municipality in range(n_municipalities):
            intercept = 1000.0 * state_index + 10.0 * municipality
            for year in range(2018, 2018 + n_years):
                precip = rng.normal(0.0, 1.0)
                temp = rng.normal(0.0, 1.0)
                value = (
                    intercept
                    + slopes[state] * precip
                    + 2.0 * temp
                    + rng.normal(0.0, noise)
                )
                rows.append(
                    {
                        "ibge_code": f"{state}{municipality:03d}",
                        "state": state,
                        "year": year,
                        "spatial_block": f"{state}-{municipality % 5}",
                        "precip": precip,
                        "temp": temp,
                        "yield_kg_ha": value,
                        "latitude": -20.0 + state_index,
                        "longitude": -50.0 + municipality / 100.0,
                    }
                )
    return rows


# --------------------------------------------------------------------------
# design e regularização
# --------------------------------------------------------------------------


def test_interaction_design_adds_one_block_per_state():
    x = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    state = np.array([0, 0, 1])
    base_design, used = generalization._design(x, state, "climate_plus_state")
    wide_design, _ = generalization._design(
        x, state, "climate_plus_state", interaction_states=[1]
    )
    assert used == [1]
    # 1 intercepto + 2 climáticas + 1 dummy de UF
    assert base_design.shape[1] == 4
    # + 2 interações (uma por coluna climática)
    assert wide_design.shape[1] == 6
    assert generalization.interaction_width(2, [1, 2]) == 4


def test_interaction_columns_match_train_and_test_shapes():
    rng = np.random.default_rng(3)
    x_train = rng.normal(size=(40, 2))
    x_test = rng.normal(size=(10, 2))
    state_train = np.array([0] * 20 + [1] * 20)
    state_test = np.array([0] * 5 + [1] * 5)
    y_train = x_train[:, 0] * 3.0 + rng.normal(size=40)
    prediction = generalization._fit_predict(
        x_train,
        y_train,
        x_test,
        state_train=state_train,
        state_test=state_test,
        variant="climate_plus_state",
        interaction_states=[1],
    )
    assert prediction is not None and prediction.shape == (10,)


def test_zero_penalty_equals_ols_and_large_penalty_equals_common_slope():
    """λ=0 é MQO; λ→∞ colapsa os desvios e reproduz a inclinação comum."""
    rows = _state_rows({"A": 3.0, "B": 9.0}, n_municipalities=25, n_years=6)
    x = np.array([[r["precip"], r["temp"]] for r in rows])
    y = np.array([r["yield_kg_ha"] for r in rows])
    state = np.array([0 if r["state"] == "A" else 1 for r in rows])

    plain = generalization._fit_predict(
        x, y, x, state_train=state, state_test=state,
        variant="climate_plus_state", interaction_states=[1],
    )
    zero = generalization._fit_predict(
        x, y, x, state_train=state, state_test=state,
        variant="climate_plus_state", interaction_states=[1], penalty=0.0,
    )
    heavy = generalization._fit_predict(
        x, y, x, state_train=state, state_test=state,
        variant="climate_plus_state", interaction_states=[1], penalty=1e9,
    )
    common = generalization._fit_predict(
        x, y, x, state_train=state, state_test=state, variant="climate_plus_state",
    )
    assert np.allclose(plain, zero, atol=1e-8)
    # encolhimento extremo devolve praticamente o modelo de inclinação comum
    assert np.allclose(heavy, common, atol=1e-3)


def test_penalty_shrinks_state_deviations_monotonically():
    rows = _state_rows({"A": 3.0, "B": 9.0}, n_municipalities=30, n_years=6)
    x = np.array([[r["precip"], r["temp"]] for r in rows])
    y = np.array([r["yield_kg_ha"] for r in rows])
    state = np.array([0 if r["state"] == "A" else 1 for r in rows])
    # previsão em dois pontos que diferem só na precipitação, na UF B: a
    # diferença entre elas mede a inclinação efetiva daquela UF.
    probe = np.array([[0.5, 0.0], [-0.5, 0.0]])
    probe_state = np.array([1, 1])
    widths = []
    for penalty in (0.0, 0.1, 1.0, 10.0, 100.0):
        prediction = generalization._fit_predict(
            x, y, probe, state_train=state, state_test=probe_state,
            variant="climate_plus_state", interaction_states=[1],
            penalty=None if penalty == 0 else penalty,
        )
        widths.append(float(prediction[0] - prediction[1]))
    # a diferença de inclinação efetiva decresce com a penalidade
    assert abs(widths[0]) > abs(widths[1]) > abs(widths[2]) > abs(widths[3])


def test_select_ridge_penalty_only_sees_the_rows_given():
    rows = _state_rows({"A": 3.0, "B": 3.0}, n_municipalities=20, n_years=5)
    x = np.array([[r["precip"], r["temp"]] for r in rows])
    y = np.array([r["yield_kg_ha"] for r in rows])
    state = np.array([0 if r["state"] == "A" else 1 for r in rows])
    blocks = np.array([r["spatial_block"] for r in rows])
    first = generalization.select_ridge_penalty(
        x, y, state, blocks, [1], (0.0, 0.1, 1.0, 10.0), seed=11
    )
    second = generalization.select_ridge_penalty(
        x, y, state, blocks, [1], (0.0, 0.1, 1.0, 10.0), seed=11
    )
    assert first["status"] == "ok"
    assert first["lambda"] == second["lambda"]
    assert first["path"] == second["path"]


def test_select_ridge_penalty_returns_the_minimum_of_its_own_path():
    """Invariante mecânica: o λ escolhido é o mínimo da validação interna.

    Não se afirma que a validação interna *prefere* encolher quando não há
    heterogeneidade — isso depende do DGP. O que precisa valer é que a escolha
    é feita sobre o caminho efetivamente avaliado, e só sobre ele.
    """
    rows = _state_rows({"A": 4.0, "B": 4.0, "C": 4.0}, n_municipalities=20, n_years=5, noise=3.0)
    x = np.array([[r["precip"], r["temp"]] for r in rows])
    y = np.array([r["yield_kg_ha"] for r in rows])
    state = np.array([{"A": 0, "B": 1, "C": 2}[r["state"]] for r in rows])
    blocks = np.array([r["spatial_block"] for r in rows])
    grid = (0.0, 0.1, 1.0, 10.0, 100.0)
    selection = generalization.select_ridge_penalty(
        x, y, state, blocks, [1, 2], grid, seed=5
    )
    assert selection["status"] == "ok"
    assert set(selection["path"]) == {str(value) for value in grid}
    best = min(selection["path"], key=selection["path"].get)
    assert float(best) == selection["lambda"]


# --------------------------------------------------------------------------
# teste global
# --------------------------------------------------------------------------


def test_f_sf_matches_known_values():
    # F(1, 10) ao nível de 5% é 4,9646 → cauda 0,05
    assert heterogeneity.f_sf(4.9646, 1, 10) == pytest.approx(0.05, abs=1e-4)
    assert heterogeneity.f_sf(0.0, 3, 20) == pytest.approx(1.0)


def test_wald_test_detects_joint_departure():
    beta = np.array([1.0, 2.0, 3.0])
    vcov = np.eye(3) * 0.25
    test = heterogeneity.wald_test(beta, vcov, [1, 2], n_clusters=50)
    assert test["status"] == "ok"
    assert test["wald"] == pytest.approx((4.0 + 9.0) / 0.25)
    assert test["p_value"] < 1e-6
    none = heterogeneity.wald_test(np.zeros(3), vcov, [1, 2], n_clusters=50)
    assert none["p_value"] == pytest.approx(1.0)


def test_slope_heterogeneity_detects_true_differences():
    rows = _state_rows({"A": 2.0, "B": 9.0, "C": 4.0}, n_municipalities=40, n_years=8)
    result = heterogeneity.slope_heterogeneity(rows, ("precip",), cluster="block")
    assert result["status"] == "ok"
    test = result["global_tests"]["precip"]
    assert test["p_value"] is not None and test["p_value"] < 0.01
    recovered = result["slopes_by_state"]
    assert recovered["B"]["precip"] > recovered["C"]["precip"] > recovered["A"]["precip"]


def test_slope_heterogeneity_does_not_reject_common_slopes():
    rows = _state_rows({"A": 5.0, "B": 5.0, "C": 5.0}, n_municipalities=40, n_years=8)
    result = heterogeneity.slope_heterogeneity(rows, ("precip",), cluster="block")
    assert result["status"] == "ok"
    assert result["global_tests"]["precip"]["p_value"] > 0.05


def test_slope_heterogeneity_requires_enough_rows():
    rows = _state_rows({"A": 1.0, "B": 2.0}, n_municipalities=2, n_years=3)
    result = heterogeneity.slope_heterogeneity(rows, ("precip",), min_rows=500)
    assert result["status"] == "insufficient_rows"


def test_two_way_clustering_uses_state_year_and_municipality():
    """O esquema de agrupamento da D104 precisa ser exatamente o declarado.

    Não se testa aqui qual dos dois esquemas é "mais conservador" — isso é
    empírico e está no relatório. Testa-se que ``two_way`` agrupa por UF×ano e
    por município, e que ``block`` continua disponível para comparabilidade.
    """
    rng = np.random.default_rng(21)
    rows = []
    states = ["A", "B", "C"]
    for state_index, state in enumerate(states):
        year_shock = {year: rng.normal(0.0, 1.0) for year in range(2018, 2026)}
        for municipality in range(30):
            intercept = 1000.0 * state_index
            for year in range(2018, 2026):
                precip = year_shock[year] + rng.normal(0.0, 0.02)
                rows.append(
                    {
                        "ibge_code": f"{state}{municipality:03d}",
                        "state": state,
                        "year": year,
                        "spatial_block": f"{state}-{municipality % 6}",
                        "precip": precip,
                        "yield_kg_ha": intercept + 5.0 * precip + rng.normal(0.0, 0.5),
                    }
                )
    two_way = heterogeneity.slope_heterogeneity(rows, ("precip",), cluster="two_way")
    block = heterogeneity.slope_heterogeneity(rows, ("precip",), cluster="block")
    assert two_way["cluster_info"]["scheme"] == "two_way"
    assert two_way["cluster_info"]["n_clusters_a"] == len(states) * 8  # UF × ano
    assert two_way["cluster_info"]["n_clusters_b"] == len(states) * 30  # municípios
    assert block["cluster_info"]["scheme"] == "block"
    assert two_way["df"] == min(
        two_way["cluster_info"]["n_clusters_a"], two_way["cluster_info"]["n_clusters_b"]
    ) - 1


# --------------------------------------------------------------------------
# diagnóstico de identificabilidade
# --------------------------------------------------------------------------


def test_coverage_diagnostics_reports_within_and_between_variation():
    rows = _state_rows({"A": 3.0, "B": 3.0}, n_municipalities=10, n_years=4)
    diagnostics = heterogeneity.coverage_diagnostics(rows, ("precip",))
    entry = diagnostics["states"]["A"]
    assert entry["n_rows"] == 40
    assert entry["n_municipalities"] == 10
    assert entry["n_years"] == 4
    variable = entry["variables"]["precip"]
    assert variable["missing_share"] == pytest.approx(0.0)
    assert variable["within_municipality_sd"] > 0.0
    assert 0.0 <= variable["within_share_of_variance"] <= 1.0


# --------------------------------------------------------------------------
# pareamento das comparações preditivas
# --------------------------------------------------------------------------


def _panel_rows(seed=13, n_municipalities=12, n_years=5, heterogeneous=False):
    rng = np.random.default_rng(seed)
    rows = []
    states = ["A", "B", "C"]
    for state_index, state in enumerate(states):
        slope = 1.0 * (state_index + 1) if heterogeneous else 1.0
        for municipality in range(n_municipalities):
            intercept = 1000.0 * state_index + 20.0 * municipality
            for year in range(2018, 2018 + n_years):
                precip = rng.normal(0.0, 1.0)
                temp = rng.normal(25.0, 1.0)
                rows.append(
                    {
                        "ibge_code": f"{state}{municipality:03d}",
                        "state": state,
                        "year": year,
                        "spatial_block": f"{state}-{municipality % 4}",
                        "precip": precip,
                        "temp": temp,
                        "yield_kg_ha": intercept + slope * precip + 3.0 * temp + rng.normal(0.0, 1.0),
                        "latitude": -20.0 + state_index,
                        "longitude": -50.0 + municipality / 100.0,
                    }
                )
    return rows


def test_predictive_comparison_uses_identical_test_cases():
    rows = _panel_rows()
    common = generalization.factorial_holdout(
        rows, PRIMARY, variant="climate_plus_state", equalize="per_cell",
        n_repeats=1, n_boot=50, keep_errors=True, min_cell_train=20,
    )
    hetero = generalization.factorial_holdout(
        rows, PRIMARY, variant="climate_plus_state", equalize="per_cell",
        n_repeats=1, n_boot=50, keep_errors=True, interactions=True,
        min_cell_train=20,
    )
    # mesmas linhas, na mesma ordem → a diferença de MAE é pareada
    assert common["row_abs_errors"]["TE"].size == hetero["row_abs_errors"]["TE"].size
    assert np.array_equal(common["test_blocks"], hetero["test_blocks"])
    assert np.array_equal(common["row_codes"], hetero["row_codes"])
    assert np.array_equal(common["row_years_raw"], hetero["row_years_raw"])
    assert common["row_abs_errors"]["TE"].shape == hetero["row_abs_errors"]["TE"].shape


def test_interactions_help_when_heterogeneity_is_real():
    rows = _panel_rows(seed=17, n_municipalities=18, n_years=6, heterogeneous=True)
    common = generalization.factorial_holdout(
        rows, PRIMARY, variant="climate_plus_state", equalize="per_cell",
        n_repeats=1, n_boot=100, min_cell_train=20,
    )
    hetero = generalization.factorial_holdout(
        rows, PRIMARY, variant="climate_plus_state", equalize="per_cell",
        n_repeats=1, n_boot=100, interactions=True, min_cell_train=20,
    )
    assert hetero["arms"]["TE"]["model"]["mae_kg_ha"] < common["arms"]["TE"]["model"]["mae_kg_ha"]


def test_neighbor_holdout_exposes_fallback_flags():
    rows = _panel_rows()
    result = generalization.neighbor_holdout(rows, radius_km=1.0, min_neighbors=3)
    assert result["status"] == "ok"
    assert np.asarray(result["row_fallback"]).all()
    assert len(result["row_codes"]) == result["n"]


def test_v32_modeling_tools_never_reference_legacy_variables():
    """Guarda contra mistura silenciosa de janela histórica e corrigida.

    Vale para as ferramentas de **modelagem** da V3.2. A ferramenta de
    sensibilidade (`v32_legacy_pairing_sensitivity.py`) menciona `_legacy` de
    propósito: ela reexecuta a comparação histórica da V3.1 para verificar se as
    conclusões sobrevivem à unidade de reamostragem da D104. A exceção é
    verificada explicitamente abaixo para que não vire porta de entrada.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    modeling = ("v32_slope_tests.py", "v32_predictive.py", "v32_neighbors.py")
    for name in modeling:
        text = (root / "tools" / name).read_text(encoding="utf-8")
        assert "_legacy" not in text, name
    sensitivity = (root / "tools" / "v32_legacy_pairing_sensitivity.py").read_text(
        encoding="utf-8"
    )
    assert "legacy_climate" in sensitivity, "a ferramenta de sensibilidade deve existir"
    assert "reproduc" in sensitivity.lower() or "V3.1" in sensitivity
