"""Testes do fechamento de confiabilidade (D128–D134)."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, os.path.join(ROOT, "tools", "analysis"))
sys.path.insert(0, os.path.join(ROOT, "tools", "pipeline"))


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, relative))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------- contrato de fonte


@pytest.fixture(scope="module")
def contracts():
    from agroclimate import contracts as module

    return module


def test_canonical_source_declared(contracts):
    assert contracts.canonical_source() == "NASA-POWER"


def test_offsource_usable_row_is_not_canonical(contracts):
    row = {"status": "paired_usable", "climate_source": "INMET"}
    assert contracts.is_canonical_row(row) is False


def test_canonical_row_accepted(contracts):
    row = {"status": "paired_usable", "climate_source": "NASA-POWER"}
    assert contracts.is_canonical_row(row) is True


def test_select_canonical_counts_discard_by_reason(contracts):
    rows = [
        {"status": "paired_usable", "climate_source": "NASA-POWER"},
        {"status": "paired_usable", "climate_source": "INMET"},
        {"status": "excluded", "climate_source": "NASA-POWER"},
        {"status": "paired_usable", "source": "NASA-POWER"},
    ]
    kept, info = contracts.select_canonical(rows)
    assert len(kept) == 2
    assert info["discarded"]["fonte:INMET"] == 1
    assert info["discarded"]["status"] == 1


def test_select_canonical_requires_declared_source(contracts):
    with pytest.raises(contracts.ClimateContractError):
        contracts.select_canonical([{"status": "paired_usable"}], required_source=None)


def test_audit_mixture_detects_the_2020_pattern(contracts):
    rows = [{"status": "paired_usable", "climate_source": "INMET"}] * 3
    rows += [{"status": "paired_usable", "climate_source": "NASA-POWER"}] * 7
    report = contracts.audit_mixture(rows)
    assert report["usable_offsource_count"] == 3
    assert report["mixed_sample"] is True


def test_prepare_rows_rejects_mixed_sources():
    from agroclimate import analysis

    rows = [
        {"status": "paired_usable", "climate_source": "NASA-POWER", "harvest_year": 2020,
         "yield_kg_ha": 3000.0},
        {"status": "paired_usable", "climate_source": "INMET", "harvest_year": 2020,
         "yield_kg_ha": 2800.0},
    ]
    with pytest.raises(ValueError):
        analysis.prepare_rows(rows)


def test_prepare_rows_accepts_declared_source():
    from agroclimate import analysis

    rows = [
        {"status": "paired_usable", "climate_source": "NASA-POWER", "harvest_year": 2020,
         "yield_kg_ha": 3000.0},
        {"status": "paired_usable", "climate_source": "INMET", "harvest_year": 2020,
         "yield_kg_ha": 2800.0},
    ]
    prepared = analysis.prepare_rows(rows, climate_source="NASA-POWER")
    assert len(prepared) == 1


# ----------------------------------------------------------------- correções


@pytest.fixture(scope="module")
def corrections():
    from agroclimate import corrections as module

    return module


def test_wind_identity_holds_in_library(corrections):
    """vento×2,5 na entrada da biblioteca ⇒ u2 = vento/3,6 (usado na adjudicação)."""
    from agroclimate import evapotranspiration as reference

    wind = 8.5
    result = reference.fao56_penman_monteith(
        30.0, 20.0, 25.0, 20.0, wind * 2.5, 60.0, 98.0, -15.0, 100
    )
    assert result.detail["wind_2m_ms"] == pytest.approx(wind / 3.6, rel=1e-12)


def test_corrected_et0_is_close_to_reference_panel(corrections):
    """O efeito líquido das duas correções é pequeno (~0,5%)."""
    from agroclimate import evapotranspiration as reference

    advice = []
    for day in (60, 180, 300):
        corrected = corrections.et0_daily(32.0, 21.0, 26.5, 22.0, 8.0, 65.0, 98.0, -15.0, day)
        base = reference.fao56_penman_monteith(32.0, 21.0, 26.5, 22.0, 8.0, 65.0, 98.0, -15.0, day)
        advice.append(corrected / base.et0_mm)
    assert all(0.9 < ratio < 1.15 for ratio in advice)


def test_corrected_balance_conserves_water(corrections):
    monthly = [
        {"month": "2020-01", "precip_mm": 120.0, "etp_mm": 90.0},
        {"month": "2020-02", "precip_mm": 10.0, "etp_mm": 110.0},
        {"month": "2020-03", "precip_mm": 60.0, "etp_mm": 70.0},
    ]
    series = corrections.sequential_water_balance(monthly, cad_mm=50.0, initial_storage_mm=50.0)
    total_precip = sum(row["precip_mm"] for row in series)
    total_etr = sum(row["etr_mm"] for row in series)
    total_excess = sum(row["exc_mm"] for row in series)
    assert total_precip == pytest.approx(total_etr + total_excess + series[-1]["arm_mm"] - 50.0)


def test_corrected_excess_is_only_the_overflow(corrections):
    monthly = [
        {"month": "2020-01", "precip_mm": 0.0, "etp_mm": 10.0},
        {"month": "2020-02", "precip_mm": 20.0, "etp_mm": 5.0},
    ]
    series = corrections.sequential_water_balance(monthly, cad_mm=50.0)
    assert sum(row["exc_mm"] for row in series) == pytest.approx(5.0)
    assert series[-1]["arm_mm"] == pytest.approx(50.0)


def test_corrected_storage_never_exceeds_cad(corrections):
    monthly = [{"month": "2020-01", "precip_mm": 500.0, "etp_mm": 1.0}]
    series = corrections.sequential_water_balance(monthly, cad_mm=37.5, initial_storage_mm=0.0)
    assert series[0]["arm_mm"] == pytest.approx(37.5)
    assert series[0]["exc_mm"] == pytest.approx(500.0 - 1.0 - 37.5)


# ------------------------------------------------------------ bootstrap rápido


@pytest.fixture(scope="module")
def fast_bootstrap():
    return _load("fast_bootstrap", "tools/analysis/fast_bootstrap.py")


def _synthetic(module, seed: int = 5, clusters: int = 12, size: int = 25):
    rng = np.random.default_rng(seed)
    n = clusters * size
    labels = [f"c{g}" for g in range(clusters) for _ in range(size)]
    x = rng.normal(size=n) + np.repeat(rng.normal(size=clusters) * 1.5, size)
    x -= x.mean()
    y = 0.7 * x + np.repeat(rng.normal(size=clusters) * 2.0, size) + rng.normal(size=n)
    y -= y.mean()
    codes, n_groups = module.group_codes(labels)
    return x, y, codes, n_groups, labels


def test_cr1_fit_matches_library(fast_bootstrap):
    from agroclimate import robust

    x, y, codes, n_groups, labels = _synthetic(fast_bootstrap)
    fit = fast_bootstrap.cr1_fit(x, y, codes, n_groups)
    library = robust.cluster_robust_fit(x.reshape(-1, 1), y, labels, coef_index=0, correction=robust.CR1)
    assert fit["beta"] == pytest.approx(library["coefficient"], rel=1e-12)
    assert fit["se"] == pytest.approx(library["std_error_clustered"], rel=1e-10)
    assert fit["t"] == pytest.approx(library["t_statistic"], rel=1e-10)


def test_wild_p_is_a_probability(fast_bootstrap):
    x, y, codes, n_groups, _ = _synthetic(fast_bootstrap)
    fit = fast_bootstrap.cr1_fit(x, y, codes, n_groups)
    weights = np.random.default_rng(1).choice([-1.0, 1.0], size=(n_groups, 499))
    result = fast_bootstrap.wild_p(x, y, codes, n_groups, weights, fit["t"], restricted=True)
    assert 0.0 < result["p_value"] <= 1.0
    assert result["variant"] == "WCR"


def test_wild_restricted_and_unrestricted_differ(fast_bootstrap):
    x, y, codes, n_groups, _ = _synthetic(fast_bootstrap)
    fit = fast_bootstrap.cr1_fit(x, y, codes, n_groups)
    weights = np.random.default_rng(2).choice([-1.0, 1.0], size=(n_groups, 999))
    restricted = fast_bootstrap.wild_p(x, y, codes, n_groups, weights, fit["t"], restricted=True)
    unrestricted = fast_bootstrap.wild_p(
        x, y, codes, n_groups, weights, fit["t"], restricted=False, observed_beta=fit["beta"]
    )
    assert restricted["variant"] == "WCR"
    assert unrestricted["variant"] == "WCU"
    assert restricted["p_value"] != unrestricted["p_value"]


def test_wild_rejects_strong_effect(fast_bootstrap):
    rng = np.random.default_rng(3)
    clusters, size = 15, 30
    n = clusters * size
    labels = [f"c{g}" for g in range(clusters) for _ in range(size)]
    x = rng.normal(size=n)
    x -= x.mean()
    y = 5.0 * x + rng.normal(size=n)
    y -= y.mean()
    codes, n_groups = fast_bootstrap.group_codes(labels)
    fit = fast_bootstrap.cr1_fit(x, y, codes, n_groups)
    weights = rng.choice([-1.0, 1.0], size=(n_groups, 999))
    result = fast_bootstrap.wild_p(x, y, codes, n_groups, weights, fit["t"], restricted=True)
    assert result["p_value"] < 0.01


# ------------------------------------------------------------ manifestos


@pytest.fixture(scope="module")
def manifests():
    return _load("pipeline_manifest", "tools/pipeline/manifest.py")


def test_canonical_json_is_key_sorted(manifests):
    text = manifests.canonical_json({"b": 1, "a": 2})
    assert text == '{"a":2,"b":1}'


def test_content_hash_ignores_generated_at(manifests):
    first = {"rows": 10, "generated_at": "2026-01-01T00:00:00Z"}
    second = {"rows": 10, "generated_at": "2026-11-14T12:00:00Z"}
    assert manifests.content_hash(first) == manifests.content_hash(second)


def test_content_hash_changes_with_content(manifests):
    assert manifests.content_hash({"rows": 10}) != manifests.content_hash({"rows": 11})


def test_content_hash_stable_for_float_representation(manifests):
    assert manifests.content_hash({"v": 0.1 + 0.2}) == manifests.content_hash({"v": 0.3})


def test_write_manifest_separates_run_metadata(tmp_path, manifests):
    path = tmp_path / "m.json"
    written = manifests.write_manifest(str(path), {"rows": 3}, {"stage": "test"})
    content = json.loads(path.read_text(encoding="utf-8"))
    assert content["rows"] == 3
    assert content["content_sha256"] == written["content_sha256"]
    run = json.loads((tmp_path / "m.json.run.json").read_text(encoding="utf-8"))
    assert run["content_sha256"] == written["content_sha256"]
    assert "generated_at" in run
    assert "generated_at" not in content


def test_manifest_hash_reproducible_across_writes(tmp_path, manifests):
    first = manifests.write_manifest(str(tmp_path / "a.json"), {"rows": 3, "x": [1, 2]})
    second = manifests.write_manifest(str(tmp_path / "b.json"), {"rows": 3, "x": [1, 2]})
    assert first["content_sha256"] == second["content_sha256"]
