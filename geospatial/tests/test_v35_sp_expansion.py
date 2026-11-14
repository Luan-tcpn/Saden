"""V3.5 — expansão de São Paulo, mapeamento e dentro do estado.

Cobre o que a conclusão depende: a integridade do cadastro de SP, a
não-regressão do painel histórico, a estabilidade dos blocos espaciais, a
aritmética do contraste por grupo e a mecânica do bootstrap.
"""

from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np
import pytest

TOOLS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
ROOT = os.path.abspath(os.path.join(TOOLS, ".."))
PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")


def _read(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _read_or_skip(name: str):
    """Painéis derivados não são versionados; sem eles o teste é pulado."""
    path = os.path.join(PROCESSED, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} não está no ambiente (derivado, fora do Git)")
    return _read(path)


def _module(name):
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    import importlib

    return importlib.import_module(name)


# --------------------------------------------------------------------------
# cadastro de SP
# --------------------------------------------------------------------------


def test_sp_registry_is_complete_and_disjoint_from_legacy():
    sp = _read(os.path.join(PROCESSED, "panel_municipalities_sp.csv"))
    legacy = _read(os.path.join(PROCESSED, "panel_municipalities_v34.csv"))
    assert len(sp) == 645
    codes = [row["ibge_code"] for row in sp]
    assert len(codes) == len(set(codes))
    assert all(code.startswith("35") for code in codes)
    assert not (set(codes) & {row["ibge_code"] for row in legacy})
    assert {row["state"] for row in sp} == {"SP"}


def test_combined_registry_is_the_union():
    combined = _read(os.path.join(PROCESSED, "panel_municipalities_v35.csv"))
    legacy = _read(os.path.join(PROCESSED, "panel_municipalities_v34.csv"))
    sp = _read(os.path.join(PROCESSED, "panel_municipalities_sp.csv"))
    assert len(combined) == len(legacy) + len(sp)
    assert {row["ibge_code"] for row in combined} == {
        row["ibge_code"] for row in legacy
    } | {row["ibge_code"] for row in sp}
    codes = [row["ibge_code"] for row in combined]
    assert codes == sorted(codes)


def test_legacy_snapshot_matches_the_live_registry():
    """O snapshot precisa ser a cópia fiel do cadastro histórico."""
    snapshot = _read(os.path.join(PROCESSED, "panel_municipalities_v34.csv"))
    live = _read(os.path.join(PROCESSED, "panel_municipalities.csv"))
    assert len(snapshot) == len(live)
    assert [row["ibge_code"] for row in snapshot] == [row["ibge_code"] for row in live]


# --------------------------------------------------------------------------
# mapeamento regional
# --------------------------------------------------------------------------


def test_mapping_extension_does_not_change_the_six_states():
    """Não regressão: as linhas da V3.4 têm de ser idênticas."""
    legacy = {
        row["ibge_code"]: row
        for row in _read(os.path.join(PROCESSED, "municipality_region_mapping.csv"))
    }
    extended = {
        row["ibge_code"]: row
        for row in _read(os.path.join(PROCESSED, "municipality_region_mapping_v35.csv"))
    }
    changed = 0
    for code, row in legacy.items():
        new = extended.get(code)
        assert new is not None, f"{code} desapareceu do mapeamento"
        if (row["macroregion"], row["edapho_region"]) != (
            new["macroregion"],
            new["edapho_region"],
        ):
            changed += 1
    assert changed == 0


def test_sp_has_both_mrs1_and_mrs3_in_the_mapping():
    rows = [
        row
        for row in _read(os.path.join(PROCESSED, "municipality_region_mapping_v35.csv"))
        if row["uf"] == "SP"
    ]
    macros = {row["macroregion"] for row in rows}
    assert {"1", "3"} <= macros
    counts = {macro: sum(1 for row in rows if row["macroregion"] == macro) for macro in macros}
    assert counts["1"] >= 40 and counts["3"] >= 100


def test_only_sp_breaks_the_region_uf_confounding():
    rows = _read(os.path.join(PROCESSED, "municipality_region_mapping_v35.csv"))
    groups: dict[str, set[str]] = {}
    for row in rows:
        macro = row["macroregion"]
        if macro in ("1", "3", "4"):
            group = "Sul" if macro == "1" else "Cerrado"
            groups.setdefault(row["uf"], set()).add(group)
    spanning = sorted(uf for uf, value in groups.items() if len(value) > 1)
    assert spanning == ["SP"]


# --------------------------------------------------------------------------
# painel
# --------------------------------------------------------------------------


def test_expanded_panel_preserves_legacy_rows_exactly():
    legacy = _read_or_skip("v31_panel_windows.csv")
    expanded = _read_or_skip("v35_panel_windows.csv")
    assert len(expanded) == len(legacy) + 10_805
    for index in range(0, len(legacy), 977):
        assert expanded[index]["ibge_code"] == legacy[index]["ibge_code"]
        assert expanded[index]["crop"] == legacy[index]["crop"]
        assert expanded[index]["safra"] == legacy[index]["safra"]


def test_sp_rows_have_unique_keys_and_valid_states():
    sp = _read_or_skip("v35_sp_windows.csv")
    keys = {(row["ibge_code"], row["crop"], row["safra"]) for row in sp}
    assert len(keys) == len(sp), "chave duplicada nas linhas de SP"
    assert {row["state"] for row in sp} == {"SP"}


def test_water_rows_cover_the_same_keys_as_the_window_rows():
    windows = _read_or_skip("v35_sp_windows.csv")
    water = _read_or_skip("v35_sp_water.csv")
    window_keys = {(row["ibge_code"], row["crop"], row["safra"]) for row in windows}
    water_keys = {(row["ibge_code"], row["crop"], row["safra"]) for row in water}
    assert window_keys == water_keys


# --------------------------------------------------------------------------
# blocos espaciais
# --------------------------------------------------------------------------


def test_spatial_blocks_of_legacy_municipalities_are_stable():
    """Se a entrada de SP reatribuísse blocos, A e B não seriam comparáveis."""
    spatial = _module("agroclimate.spatial")
    legacy = _read(os.path.join(PROCESSED, "panel_municipalities_v34.csv"))
    combined = _read(os.path.join(PROCESSED, "panel_municipalities_v35.csv"))
    before = spatial.spatial_blocks(legacy, 250.0)
    after = spatial.spatial_blocks(combined, 250.0)
    changed = [code for code in before if before[code] != after.get(code)]
    assert changed == []


# --------------------------------------------------------------------------
# aritmética do contraste
# --------------------------------------------------------------------------


def _fake(errors, codes, years, blocks=None):
    return {
        "row_abs_errors": {"TE": np.asarray(errors, dtype=float)},
        "row_codes": np.array(codes),
        "row_years": np.array(years),
        "row_states": np.array(["SP"] * len(codes)),
        "row_blocks": np.array(blocks or [f"b{i % 3}" for i in range(len(codes))]),
    }


def test_group_delta_subtracts_m2_from_water_block():
    module = _module("v35_models")
    codes = ["a"] * 40 + ["b"] * 40
    years = [str(2017 + (index % 8)) for index in range(80)]
    m2 = _fake([10.0] * 40 + [20.0] * 40, codes, years)
    wb = _fake([5.0] * 40 + [30.0] * 40, codes, years)
    rows = [
        {"ibge_code": "a", "macroregion": "1", "state": "SP"},
        {"ibge_code": "b", "macroregion": "3", "state": "SP"},
    ]
    result = module._group_delta(rows, m2, wb, "macroregion", "soja")
    assert result["1"]["delta"] == pytest.approx(-5.0)
    assert result["3"]["delta"] == pytest.approx(+10.0)


def test_bootstrap_group_D_recovers_a_known_gap():
    module = _module("v35_models")
    rng = np.random.default_rng(11)
    n = 400
    codes = [f"m{i % 40}" for i in range(n)]
    years = [str(2017 + (i % 8)) for i in range(n)]
    groups = np.array(["1"] * (n // 2) + ["3"] * (n // 2))
    error_wb = np.where(groups == "1", +5.0, -15.0) + rng.normal(0, 1.0, n)
    m2 = _fake(np.zeros(n), codes, years)
    wb = _fake(error_wb, codes, years)
    result = module._bootstrap_group_D(
        m2, wb, [], groups == "1", groups == "3", units="municipality", n_boot=300
    )
    assert result["ci95"][0] < 20 < result["ci95"][1]
    assert result["p_value"] < 0.01


def test_bootstrap_group_D_is_null_when_groups_agree():
    module = _module("v35_models")
    rng = np.random.default_rng(5)
    n = 400
    codes = [f"m{i % 40}" for i in range(n)]
    years = [str(2017 + (i % 8)) for i in range(n)]
    groups = np.array(["1"] * (n // 2) + ["3"] * (n // 2))
    error_wb = rng.normal(0, 1.0, n)
    m2 = _fake(np.zeros(n), codes, years)
    wb = _fake(error_wb, codes, years)
    result = module._bootstrap_group_D(
        m2, wb, [], groups == "1", groups == "3", units="municipality", n_boot=400
    )
    assert result["ci95"][0] < 0 < result["ci95"][1]
    assert result["p_value"] > 0.05


# --------------------------------------------------------------------------
# reconciliação e artefatos
# --------------------------------------------------------------------------


def test_reconciliation_names_are_documented():
    payload = json.load(
        open(os.path.join(MANIFESTS, "v35_coverage_robustness.json"), encoding="utf-8")
    )
    block = payload["coverage"]["reconciliation_v34"]
    text = block["explanation"]
    for token in ("Poxor", "Leverger", "Vila Alta", "Alto Para"):
        assert token in text, token
    assert block["official_pairs_six_states"] == 1425
    assert block["matched_pairs"] == 1422
    assert block["difference"] == 3


def test_within_sp_primary_result_is_reported_as_null():
    payload = json.load(open(os.path.join(MANIFESTS, "v35_models.json"), encoding="utf-8"))
    soja = payload["within_sp"]["soja"]
    low, high = soja["D_mrs1_vs_mrs3"]["year"]["ci95"]
    assert low < 0 < high, "o IC primário deveria conter zero"
    assert soja["association"]["joint_test"]["p_value"] > 0.05


def test_reproduction_of_v34_is_recorded_exactly():
    payload = json.load(open(os.path.join(MANIFESTS, "v35_models.json"), encoding="utf-8"))
    experiment = payload["experiments"]["A_six_states"]
    assert experiment["milho"]["m2"]["mae_model"] == pytest.approx(1661.2, abs=0.1)
    assert experiment["soja"]["m2"]["mae_model"] == pytest.approx(592.7, abs=0.1)
    assert experiment["milho_2"]["m2"]["mae_model"] == pytest.approx(1272.3, abs=0.1)
