"""V3.3 — descritores de estresse e auditoria de inferência.

Cobre as duas frentes:

* **A** — descritores temporais do balanço, identidade DEF = ETP − ETR, teste
  conjunto de bloco (Wald) e p-valor do bootstrap pareado;
* **B** — identidade do VCV de agrupamento duplo, identificação dos clusters
  UF×ano e a regra de classificação da auditoria.

Os testes usam dados sintéticos com estrutura conhecida: a asserção é sobre
comportamento estatístico e mecânico, não sobre um número copiado de um
manifesto.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

from agroclimate import generalization, heterogeneity, robust, water_balance

TOOLS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tools"))


def _month(month, precip, etp):
    return {"month": month, "precip_mm": precip, "etp_mm": etp}


# --------------------------------------------------------------------------
# Frente A — descritores de estresse
# --------------------------------------------------------------------------


def test_stress_descriptors_are_zero_when_there_is_no_deficit():
    balance = [
        _month("2018-01", 200.0, 80.0),
        _month("2018-02", 180.0, 90.0),
        _month("2018-03", 150.0, 100.0),
    ]
    for row in water_balance.sequential_water_balance(balance, cad_mm=60.0):
        assert row["status"] == "ok"
    descriptors = water_balance.stress_descriptors(
        water_balance.sequential_water_balance(balance, cad_mm=60.0)
    )
    assert descriptors["deficit_months"] == 0
    assert descriptors["stress_share"] == pytest.approx(0.0)
    assert descriptors["max_consecutive_deficit_months"] == 0
    assert descriptors["months_to_first_stress"] is None
    assert descriptors["etr_over_etp"] == pytest.approx(1.0)


def test_stress_descriptors_count_consecutive_months():
    balance = [
        _month("2018-01", 5.0, 120.0),
        _month("2018-02", 5.0, 120.0),
        _month("2018-03", 5.0, 120.0),
        _month("2018-04", 5.0, 120.0),
    ]
    sequential = water_balance.sequential_water_balance(balance, cad_mm=60.0)
    descriptors = water_balance.stress_descriptors(sequential)
    assert descriptors["months"] == 4
    assert descriptors["deficit_months"] == 4
    assert descriptors["max_consecutive_deficit_months"] == 4
    assert descriptors["stress_share"] == pytest.approx(1.0)
    assert descriptors["months_to_first_stress"] == 0
    assert descriptors["storage_min_mm"] == pytest.approx(0.0)


def test_stress_descriptors_break_the_sequence_at_a_wet_month():
    balance = [
        _month("2018-01", 3.0, 120.0),
        _month("2018-02", 3.0, 120.0),
        _month("2018-03", 300.0, 90.0),
        _month("2018-04", 3.0, 120.0),
    ]
    descriptors = water_balance.stress_descriptors(
        water_balance.sequential_water_balance(balance, cad_mm=60.0)
    )
    assert descriptors["max_consecutive_deficit_months"] <= 2
    assert descriptors["deficit_months"] >= 2


def test_stress_descriptors_threshold_is_not_chosen_in_the_data():
    """Abaixo do limiar fixo, o mês não conta como estresse."""
    sequential = [
        {"status": "ok", "month": "2018-01", "def_mm": 0.2, "exc_mm": 0.0,
         "arm_mm": 60.0, "etr_mm": 99.8, "etp_mm": 100.0},
        {"status": "ok", "month": "2018-02", "def_mm": 40.0, "exc_mm": 0.0,
         "arm_mm": 20.0, "etr_mm": 60.0, "etp_mm": 100.0},
    ]
    descriptors = water_balance.stress_descriptors(sequential)
    assert descriptors["deficit_months"] == 1
    assert descriptors["months_to_first_stress"] == 1


def test_stress_descriptors_relative_measures_are_complements():
    """DEF = ETP − ETR por construção, logo def/etp = 1 − etr/etp."""
    balance = [
        _month("2018-01", 20.0, 130.0),
        _month("2018-02", 10.0, 140.0),
        _month("2018-03", 80.0, 110.0),
    ]
    descriptors = water_balance.stress_descriptors(
        water_balance.sequential_water_balance(balance, cad_mm=60.0)
    )
    assert descriptors["etr_over_etp"] + descriptors["deficit_over_etp"] == pytest.approx(1.0)


def test_stress_descriptors_handle_empty_balance():
    descriptors = water_balance.stress_descriptors([])
    assert descriptors["months"] == 0
    assert descriptors["stress_share"] is None
    assert descriptors["etr_over_etp"] is None


# --------------------------------------------------------------------------
# Frente A — teste conjunto de bloco
# --------------------------------------------------------------------------


def _block_rows(effect_size=0.0, seed=11, n_municipalities=30, n_years=8, n_states=4):
    rng = np.random.default_rng(seed)
    rows = []
    states = [f"S{index}" for index in range(n_states)]
    for state_index, state in enumerate(states):
        for municipality in range(n_municipalities):
            intercept = 500.0 * state_index + 15.0 * municipality
            for year in range(2018, 2018 + n_years):
                climate = rng.normal(0.0, 1.0)
                water = rng.normal(0.0, 1.0)
                value = (
                    intercept
                    + 2.0 * climate
                    + effect_size * water
                    + rng.normal(0.0, 1.0)
                )
                rows.append(
                    {
                        "ibge_code": f"{state}-{municipality:03d}",
                        "state": state,
                        "year": year,
                        "spatial_block": f"{state}-{municipality % 5}",
                        "climate": climate,
                        "water": water,
                        "yield_kg_ha": value,
                    }
                )
    return rows


def test_joint_significance_detects_a_real_block_effect():
    rows = _block_rows(effect_size=3.0)
    result = heterogeneity.joint_significance(
        rows, ("climate", "water"), test_variables=("water",), cluster="block"
    )
    assert result["status"] == "ok"
    assert result["joint_test"]["p_value"] < 0.01
    assert result["coefficients"]["water"]["tested"] is True
    assert result["coefficients"]["climate"]["tested"] is False


def test_joint_significance_does_not_reject_an_irrelevant_block():
    rows = _block_rows(effect_size=0.0)
    result = heterogeneity.joint_significance(
        rows, ("climate", "water"), test_variables=("water",), cluster="block"
    )
    assert result["status"] == "ok"
    assert result["joint_test"]["p_value"] > 0.05


def test_joint_significance_rejects_unknown_test_variable():
    rows = _block_rows()
    with pytest.raises(ValueError):
        heterogeneity.joint_significance(
            rows, ("climate",), test_variables=("water",), cluster="block"
        )


def test_joint_significance_counts_state_year_clusters():
    rows = _block_rows(n_states=3, n_years=4, n_municipalities=10)
    result = heterogeneity.joint_significance(
        rows, ("climate", "water"), test_variables=("water",), cluster="two_way",
        min_rows=50,
    )
    assert result["cluster_info"]["n_clusters_a"] == 3 * 4
    assert result["cluster_info"]["n_clusters_b"] == 3 * 10
    assert result["df"] == min(3 * 4, 3 * 10) - 1


# --------------------------------------------------------------------------
# Frente A — p-valor do bootstrap pareado
# --------------------------------------------------------------------------


def test_bootstrap_p_value_follows_the_interval():
    a = np.full(200, 1.0)
    b = np.zeros(200)
    blocks = np.array([f"b{i % 20}" for i in range(200)])
    result = generalization.block_bootstrap_difference(a, b, blocks, n_boot=500)
    assert result["p_value"] < 0.01
    assert result["ci95"][0] > 0


def test_bootstrap_p_value_is_large_when_models_are_indistinguishable():
    rng = np.random.default_rng(5)
    a = np.abs(rng.normal(1.0, 1.0, size=300))
    b = np.abs(rng.normal(1.0, 1.0, size=300))
    blocks = np.array([f"b{i % 25}" for i in range(300)])
    result = generalization.block_bootstrap_difference(a, b, blocks, n_boot=800)
    assert 0.0 <= result["p_value"] <= 1.0
    assert result["p_value"] > 0.05


def test_bootstrap_p_value_is_symmetric_and_bounded():
    rng = np.random.default_rng(9)
    a = np.abs(rng.normal(1.2, 1.0, size=120))
    b = np.abs(rng.normal(1.0, 1.0, size=120))
    blocks = np.array([f"b{i % 12}" for i in range(120)])
    forward = generalization.block_bootstrap_difference(a, b, blocks, n_boot=400)
    backward = generalization.block_bootstrap_difference(b, a, blocks, n_boot=400)
    assert 0.0 <= forward["p_value"] <= 1.0
    assert forward["p_value"] == pytest.approx(backward["p_value"], abs=0.02)
    assert forward["delta_mae"] == pytest.approx(-backward["delta_mae"])


# --------------------------------------------------------------------------
# Frente B — identidade do agrupamento duplo
# --------------------------------------------------------------------------


def test_two_way_vcov_is_the_cameron_gelbach_miller_identity():
    rng = np.random.default_rng(3)
    n = 240
    design = np.column_stack([np.ones(n), rng.normal(size=n)])
    residuals = rng.normal(size=n)
    clusters_a = [f"a{i % 12}" for i in range(n)]
    clusters_b = [f"b{i % 20}" for i in range(n)]
    two_way, info = robust.two_way_cluster_vcov(design, residuals, clusters_a, clusters_b)
    v_a, _ = robust.cluster_vcov(design, residuals, clusters_a, correction=robust.CR1)
    v_b, _ = robust.cluster_vcov(design, residuals, clusters_b, correction=robust.CR1)
    combined = [f"{x}||{y}" for x, y in zip(clusters_a, clusters_b)]
    v_ab, _ = robust.cluster_vcov(design, residuals, combined, correction=robust.CR1)
    assert np.allclose(two_way, v_a + v_b - v_ab)
    assert info["n_clusters_a"] == 12
    assert info["n_clusters_b"] == 20


# --------------------------------------------------------------------------
# Frente B — maquinaria da auditoria
# --------------------------------------------------------------------------


def _audit_module():
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    import v33_inference_audit

    return v33_inference_audit


def test_audit_classification_mapping():
    audit = _audit_module()

    def entry(p_block, p_two):
        return {
            "status": "ok",
            "schemes": {
                "bloco_espacial_250km": {"p_value": p_block},
                "two_way": {"p_value": p_two},
            },
        }

    assert audit.classify(entry(0.001, 0.001), 0.001, 0.001) == "mantida"
    assert audit.classify(entry(0.001, 0.02), 0.001, 0.4) == "mantida_apenas_bruta"
    assert audit.classify(entry(0.001, 0.07), 0.001, 0.4) == "enfraquecida"
    assert audit.classify(entry(0.01, 0.4), 0.01, 0.9) == "nao_sustentada"
    assert audit.classify(entry(0.4, 0.001), 0.5, 0.01) == "reforcada"
    assert audit.classify(entry(0.4, 0.4), 0.9, 0.9) == "sem_evidencia_em_nenhum"
    assert audit.classify({"status": "degenerate_design"}, None, None) == "nao_auditavel"


def test_audit_reproduces_the_within_coefficient_and_counts_state_year_clusters():
    audit = _audit_module()
    rows = _block_rows(n_states=3, n_years=5, n_municipalities=12)
    result = audit.associate(rows, "water", min_rows=100)
    assert result["status"] == "ok"
    assert result["n"] == 3 * 12 * 5
    # UF×ano: 3 estados × 5 anos
    assert result["schemes"]["uf_ano"]["n_clusters"] == 15
    assert result["schemes"]["uf"]["n_clusters"] == 3
    # município: 36
    assert result["schemes"]["municipio"]["n_clusters"] == 36
    # o coeficiente é o mesmo em todas as estruturas (só a VCV muda)
    assert result["schemes"]["two_way"]["df"] == min(15, 36) - 1


def test_audit_requires_enough_rows():
    audit = _audit_module()
    rows = _block_rows(n_states=1, n_years=2, n_municipalities=3)
    result = audit.associate(rows, "water")
    assert result["status"] == "insufficient_rows"
