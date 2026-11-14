"""Testes da etapa de consolidação técnica (pipeline canônico, replicação, poder)."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, os.path.join(ROOT, "tools", "independent_replication"))
sys.path.insert(0, os.path.join(ROOT, "tools", "analysis"))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, relative))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------ replicação


@pytest.fixture(scope="module")
def replication():
    return _load("water_balance_reference", "tools/independent_replication/water_balance_reference.py")


def test_manual_cases_all_pass(replication):
    result = replication.run_manual_cases()
    assert result["n_cases"] == 8
    assert result["failures"] == []
    assert result["n_passed"] == 8


def test_balance_conserves_water(replication):
    monthly = [
        {"month": "2020-01", "precip_mm": 120.0, "et0_mm": 90.0},
        {"month": "2020-02", "precip_mm": 10.0, "et0_mm": 110.0},
        {"month": "2020-03", "precip_mm": 60.0, "et0_mm": 70.0},
    ]
    series = replication.thornthwaite_mather(monthly, cad_mm=50.0, initial_storage_mm=50.0)
    total_precip = sum(row["precip_mm"] for row in series)
    total_etr = sum(row["etr_mm"] for row in series)
    total_excess = sum(row["excess_mm"] for row in series)
    storage_end = series[-1]["storage_mm"]
    # P = ETR + EXC + (ARM_final - ARM_inicial)
    assert total_precip == pytest.approx(total_etr + total_excess + storage_end - 50.0)


def test_deficit_never_exceeds_demand(replication):
    monthly = [{"month": "2020-01", "precip_mm": 0.0, "et0_mm": 25.0}]
    series = replication.thornthwaite_mather(monthly, cad_mm=50.0, initial_storage_mm=10.0)
    row = series[0]
    assert 0.0 <= row["deficit_mm"] <= row["et0_mm"]
    assert row["etr_mm"] + row["deficit_mm"] == pytest.approx(row["et0_mm"])


def test_storage_bounded_by_cad(replication):
    monthly = [{"month": "2020-01", "precip_mm": 500.0, "et0_mm": 1.0}]
    series = replication.thornthwaite_mather(monthly, cad_mm=37.5, initial_storage_mm=0.0)
    assert series[0]["storage_mm"] == pytest.approx(37.5)
    assert series[0]["excess_mm"] == pytest.approx(500.0 - 1.0 - 37.5)


def test_reference_overstates_excess_on_partial_refill(replication):
    """D124: a implementação de referência soma o saldo inteiro como excedente."""
    from agroclimate import water_balance as library

    monthly = [
        {"month": "2020-01", "precip_mm": 0.0, "etp_mm": 10.0},
        {"month": "2020-02", "precip_mm": 20.0, "etp_mm": 5.0},
    ]
    reference = library.sequential_water_balance(monthly, cad_mm=50.0)
    independent = replication.thornthwaite_mather(
        [{"month": row["month"], "precip_mm": row["precip_mm"], "et0_mm": row["etp_mm"]} for row in monthly],
        cad_mm=50.0,
    )
    assert sum(row["excess_mm"] for row in independent) == pytest.approx(5.0)
    assert sum(float(row["exc_mm"]) for row in reference) == pytest.approx(15.0)
    assert sum(float(row["def_mm"]) for row in reference) == pytest.approx(
        sum(row["deficit_mm"] for row in independent)
    )


def test_excess_scenario_reported(replication):
    result = replication.partial_refill_check()
    assert result["excess_independent"] == pytest.approx(5.0)
    assert result["excess_overstated_by_library"] == pytest.approx(10.0)
    assert result["deficit_diff"] == pytest.approx(0.0)


def test_et0_matches_fao56_reference_value(replication):
    """Dia claro de verão em latitude 0: ET0 na faixa esperada pela FAO-56."""
    value = replication.et0_fao56(
        temp_max_c=32.0, temp_min_c=22.0, temp_mean_c=27.0,
        radiation_mj_m2=24.0, wind_kmh_at_2m=7.2, humidity_pct=65.0,
        pressure_kpa=101.3, latitude_deg=0.0, day_of_year=80,
    )
    assert 4.0 < value < 7.5


def test_monthly_aggregate_sums_not_averages(replication):
    days = [
        {"date": "2020-01-01", "precip_mm": 10.0, "et0_mm": 4.0},
        {"date": "2020-01-02", "precip_mm": 5.0, "et0_mm": 4.0},
        {"date": "2020-02-01", "precip_mm": 1.0, "et0_mm": 3.0},
    ]
    monthly = replication.monthly_aggregate(days)
    assert [row["month"] for row in monthly] == ["2020-01", "2020-02"]
    assert monthly[0]["precip_mm"] == pytest.approx(15.0)
    assert monthly[0]["et0_mm"] == pytest.approx(8.0)


# --------------------------------------------------------------- poder


@pytest.fixture(scope="module")
def power():
    return _load("statistical_power", "tools/analysis/statistical_power.py")


def test_mde_increases_with_standard_error(power):
    assert power.mde(1.0, 50) < power.mde(2.0, 50)


def test_mde_90_above_mde_80(power):
    assert power.mde(1.0, 50, 0.90) > power.mde(1.0, 50, 0.80)


def test_mde_uses_t_quantile_consistently(power):
    df = 47
    critical = power.robust.t_critical(0.05, df)
    assert power._t_quantile(0.975, df) == pytest.approx(critical, rel=1e-3)
    assert power._t_quantile(0.80, df) == pytest.approx(0.849, abs=5e-3)


def test_design_scenarios_adding_clusters_beats_adding_units(power):
    scenarios = power.design_scenarios(mean_size=200.0, n_clusters=50, icc=0.25)["scenarios"]
    assert scenarios["anos_9_para_15"]["se_factor"] < scenarios["municipios_x2"]["se_factor"]
    assert scenarios["ufs_7_para_10"]["se_factor"] < scenarios["municipios_x5"]["se_factor"]


def test_design_scenarios_high_icc_makes_units_worthless(power):
    scenarios = power.design_scenarios(mean_size=200.0, n_clusters=50, icc=0.5)["scenarios"]
    assert scenarios["municipios_x5"]["se_factor"] > 0.98


def test_variance_components_recover_icc(power):
    import numpy as np

    generator = np.random.default_rng(7)
    labels = []
    values = []
    for cluster in range(80):
        level = generator.normal(0.0, 10.0)
        for _ in range(40):
            labels.append(f"c{cluster}")
            values.append(level + generator.normal(0.0, 10.0))
    components = power.cluster_variance_components(np.array(values), labels)
    assert 0.3 < components["icc"] < 0.7
    assert components["mean_cluster_size"] == pytest.approx(40.0)


# ------------------------------------------------------------ pipeline


@pytest.fixture(scope="module")
def pipeline():
    return _load("build_panel", "tools/pipeline/build_panel.py")


def test_pipeline_config_is_declarative_and_complete(pipeline):
    config = pipeline.load_config()
    for key in ("period", "states", "crops", "sources", "inputs", "rules", "reference_outputs"):
        assert key in config
    assert config["rules"]["require_climate_source"] == "NASA-POWER"
    assert len(config["states"]) == 7


def test_pipeline_rejects_operational_areas(pipeline):
    config = pipeline.load_config()
    registry = pipeline.load_registry(config)
    assert "4300001" not in registry
    assert "4300002" not in registry
    assert len(registry) == 2425


def test_pipeline_abs_respects_data_root(pipeline, monkeypatch, tmp_path):
    monkeypatch.setenv("SADEN_DATA_ROOT", str(tmp_path))
    resolved = pipeline._abs("geospatial/data/processed/x.csv")
    assert resolved == os.path.join(str(tmp_path), "processed", "x.csv")
    monkeypatch.delenv("SADEN_DATA_ROOT")
    assert pipeline._abs("geospatial/data/processed/x.csv").startswith(pipeline.ROOT)


def test_pipeline_validate_reports_excluded_units(pipeline):
    report = pipeline.validate(pipeline.load_config())
    assert report["registry"]["n_excluded"] == 2
    assert report["registry"]["duplicates"] == []


def test_pipeline_profiles_cover_all_crops(pipeline):
    for crop in pipeline.load_config()["crops"]:
        assert crop in pipeline.PROFILE_BY_CROP


# --------------------------------------------------------------- PAM


@pytest.fixture(scope="module")
def pam_audit():
    return _load("audit_pam_quality", "tools/audit_pam_quality.py")


def _cell(**overrides):
    entry = {
        "ibge_code": "4100103",
        "year": "2020",
        "crop": "soja",
        "uf": "PR",
        "values": {
            "area_plantada_ha": 100.0,
            "area_colhida_ha": 100.0,
            "quantidade_produzida_t": 320.0,
            "rendimento_medio_kg_ha": 3200.0,
        },
    }
    entry["values"].update(overrides)
    return entry


def test_pam_classify_clean_cell(pam_audit):
    cell = pam_audit.classify(_cell())
    assert cell["flags"] == []
    assert cell["yield_relative_gap"] == pytest.approx(0.0)


def test_pam_classify_no_area_is_not_an_error(pam_audit):
    cell = pam_audit.classify(_cell(area_plantada_ha=0.0, area_colhida_ha=0.0, quantidade_produzida_t=0.0, rendimento_medio_kg_ha=0.0))
    assert "sem_area" in cell["flags"]


def test_pam_classify_planted_not_harvested(pam_audit):
    cell = pam_audit.classify(_cell(area_plantada_ha=100.0, area_colhida_ha=0.0, quantidade_produzida_t=0.0, rendimento_medio_kg_ha=0.0))
    assert "plantado_sem_colheita" in cell["flags"]


def test_pam_classify_detects_yield_divergence(pam_audit):
    cell = pam_audit.classify(_cell(rendimento_medio_kg_ha=3600.0))
    assert "rendimento_divergente" in cell["flags"]
    assert cell["yield_relative_gap"] > 0.01


def test_pam_to_wide_keeps_first_value_and_counts_duplicates(pam_audit):
    rows = [
        {"geography_code": "4100103", "reference_year": "2020", "crop_code": "40124",
         "variable_normalized": "area_colhida_ha", "value_normalized": "100", "observation_status": "observed",
         "geography_name": "Abatiá (PR)"},
        {"geography_code": "4100103", "reference_year": "2020", "crop_code": "40124",
         "variable_normalized": "area_colhida_ha", "value_normalized": "999", "observation_status": "observed",
         "geography_name": "Abatiá (PR)"},
    ]
    wide, info = pam_audit.to_wide(rows)
    assert info["duplicates"] == 1
    assert wide[("4100103", "2020", "soja")]["values"]["area_colhida_ha"] == 100.0
