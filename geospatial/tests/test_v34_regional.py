"""V3.4 — classificação regional e contraste Sul × Cerrado.

Cobre o que a conclusão depende: a integridade do mapeamento municipal, a regra de
agrupamento congelada, o cálculo do contraste pareado, o bootstrap e o
diagnóstico de confundimento.
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


def _tools_module(name):
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    return __import__(name)


# --------------------------------------------------------------------------
# mapeamento municipal
# --------------------------------------------------------------------------


def test_mapping_has_unique_ibge_codes_and_valid_states():
    path = os.path.join(PROCESSED, "municipality_region_mapping.csv")
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    assert rows, "mapeamento vazio"
    codes = [row["ibge_code"] for row in rows]
    assert len(codes) == len(set(codes)), "código IBGE duplicado no mapeamento"
    assert {row["uf"] for row in rows} <= {"PR", "RS", "MS", "MT", "GO", "BA"}
    # o código IBGE carrega a UF nos dois primeiros dígitos
    ibge_to_uf = {"41": "PR", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "29": "BA"}
    for row in rows:
        assert ibge_to_uf[row["ibge_code"][:2]] == row["uf"], row


def test_mapping_macroregions_are_from_the_official_set():
    path = os.path.join(PROCESSED, "municipality_region_mapping.csv")
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    assert {row["macroregion"] for row in rows} <= {"1", "2", "3", "4", "5"}
    # região edafoclimática sempre começa com o dígito da macrorregião
    for row in rows:
        assert row["edapho_region"][0] == row["macroregion"], row


def test_manifest_records_source_hash_and_coverage():
    payload = json.load(open(os.path.join(MANIFESTS, "v34_region_mapping.json"), encoding="utf-8"))
    digest = payload["source"]["xlsx_sha256"]
    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
    assert payload["join"]["matched"] > 1000
    assert payload["coverage"]["duplicate_state_municipality"] == 0


# --------------------------------------------------------------------------
# regra de agrupamento (congelada)
# --------------------------------------------------------------------------


def test_group_rule_matches_the_frozen_protocol():
    module = _tools_module("v34_regional_contrast")
    assert module.MACRO_GROUP["1"] == "Sul"
    assert module.MACRO_GROUP["2"] == "Transicao"
    assert module.MACRO_GROUP["3"] == "Cerrado"
    assert module.MACRO_GROUP["4"] == "Cerrado"
    assert module.MACRO_GROUP["5"] == "Fora"
    # MRS 2 nunca entra em Sul nem em Cerrado
    assert module.MACRO_GROUP["2"] not in ("Sul", "Cerrado")


# --------------------------------------------------------------------------
# confundimento
# --------------------------------------------------------------------------


def test_cramers_v_is_one_when_region_is_a_function_of_uf():
    module = _tools_module("v34_coverage")
    table = {("Sul", "RS"): 100, ("Sul", "PR"): 50, ("Cerrado", "GO"): 80,
             ("Cerrado", "MT"): 40}
    assert module.cramers_v(table) == pytest.approx(1.0, abs=1e-9)


def test_cramers_v_is_zero_when_groups_are_balanced_within_uf():
    module = _tools_module("v34_coverage")
    table = {("Sul", "X"): 50, ("Cerrado", "X"): 50, ("Sul", "Y"): 50,
             ("Cerrado", "Y"): 50}
    assert module.cramers_v(table) == pytest.approx(0.0, abs=1e-9)


def test_cramers_v_is_between_zero_and_one():
    module = _tools_module("v34_coverage")
    table = {("Sul", "A"): 90, ("Cerrado", "A"): 10, ("Sul", "B"): 20,
             ("Cerrado", "B"): 80}
    value = module.cramers_v(table)
    assert 0.0 < value < 1.0


def test_frozen_classification_is_nested_in_uf_in_the_real_mapping():
    """A conclusão central da V3.4 precisa valer no dado real, não só no sintético."""
    path = os.path.join(PROCESSED, "municipality_region_mapping.csv")
    module = _tools_module("v34_regional_contrast")
    groups_por_uf: dict[str, set[str]] = {}
    for row in csv.DictReader(open(path, encoding="utf-8-sig")):
        group = module.MACRO_GROUP[row["macroregion"]]
        if group in ("Sul", "Cerrado"):
            groups_por_uf.setdefault(row["uf"], set()).add(group)
    spanning = {uf: groups for uf, groups in groups_por_uf.items() if len(groups) > 1}
    assert spanning == {}, f"alguma UF passou a ter os dois grupos: {spanning}"


# --------------------------------------------------------------------------
# contraste
# --------------------------------------------------------------------------


def _fake_result(errors: np.ndarray, codes: list[str], years: list[str]):
    return {
        "row_abs_errors": {"TE": errors},
        "row_codes": np.array(codes),
        "row_years_raw": np.array(years),
        "row_blocks": np.array([f"b{i % 5}" for i in range(len(codes))]),
        "row_states": np.array(["X"] * len(codes)),
        "row_years": np.array(years),
    }


def test_per_region_delta_subtracts_m2_from_water_block():
    module = _tools_module("v34_regional_contrast")
    codes = ["a", "a", "b", "b"]
    years = ["2018", "2019", "2018", "2019"]
    m2 = _fake_result(np.array([10.0, 10.0, 20.0, 20.0]), codes, years)
    wb = _fake_result(np.array([5.0, 5.0, 30.0, 30.0]), codes, years)
    rows = [
        {"ibge_code": "a", "macroregion": "1", "group": "Sul", "state": "X"},
        {"ibge_code": "b", "macroregion": "4", "group": "Cerrado", "state": "X"},
    ]
    result = module.per_region_delta(rows, m2, wb)
    assert result["groups"]["Sul"]["delta"] == pytest.approx(-5.0)
    assert result["groups"]["Cerrado"]["delta"] == pytest.approx(+10.0)
    assert result["D"] == pytest.approx(-15.0)


def test_per_region_delta_detects_misalignment():
    module = _tools_module("v34_regional_contrast")
    codes = ["a", "b"]
    m2 = _fake_result(np.array([1.0, 2.0]), codes, ["2018", "2018"])
    wb = _fake_result(np.array([1.0]), ["a"], ["2018"])
    result = module.per_region_delta([], m2, wb)
    assert result["status"] == "unaligned"


def test_bootstrap_D_recovers_a_known_difference():
    module = _tools_module("v34_regional_contrast")
    rng = np.random.default_rng(3)
    groups = np.array(["Sul"] * 200 + ["Cerrado"] * 200)
    units = np.array([f"u{i}" for i in range(20)] * 20)
    inequality = np.concatenate([rng.normal(-10, 1, 200), rng.normal(+10, 1, 200)])
    result = module._bootstrap_D(inequality, groups, units, n_boot=400)
    # D verdadeiro = -10 - (+10) = -20
    assert result["ci95"][0] < -20 < result["ci95"][1]
    assert result["p_value"] < 0.01


def test_bootstrap_D_is_null_when_groups_are_identical():
    module = _tools_module("v34_regional_contrast")
    rng = np.random.default_rng(5)
    groups = np.array(["Sul"] * 200 + ["Cerrado"] * 200)
    units = np.array([f"u{i}" for i in range(20)] * 20)
    inequality = rng.normal(0, 1, 400)
    result = module._bootstrap_D(inequality, groups, units, n_boot=500)
    assert result["ci95"][0] < 0 < result["ci95"][1]
    assert result["p_value"] > 0.05


def test_weighted_delta_puts_equal_weight_per_unit():
    module = _tools_module("v34_regional_sensitivity")
    err_m2 = np.array([0.0, 0.0, 0.0, 0.0])
    err_wb = np.array([+1.0, +1.0, +1.0, +100.0])  # uma unidade com erro enorme
    mask = np.array([True, True, True, True])
    units = {"municipality": np.array(["a", "a", "a", "b"]), "uf": np.array(["X"] * 4)}
    result = module._weighted_delta(err_wb, err_m2, mask, mask, units)
    # por observação: (1+1+1+100)/4 = 25.75 ; por município: (1 + 100)/2 = 50.5
    assert result["observation"]["delta_a"] == pytest.approx(25.75)
    assert result["municipality"]["delta_a"] == pytest.approx(50.5)


# --------------------------------------------------------------------------
# artefatos
# --------------------------------------------------------------------------


def test_figures_exist_and_are_not_empty():
    directory = os.path.join(ROOT, "docs", "figures", "v34")
    files = [name for name in os.listdir(directory) if name.endswith(".png")]
    assert len(files) == 6
    for name in files:
        assert os.path.getsize(os.path.join(directory, name)) > 10_000, name


def test_confirmation_of_independence_flag_is_false():
    """A V3.4 declara explicitamente que não há confirmação independente."""
    payload = json.load(
        open(os.path.join(MANIFESTS, "v34_regional_contrast.json"), encoding="utf-8")
    )
    assert payload["preregistration"].endswith("V3_4_REGIONAL_WATER_PREREGISTRATION.md")
    text = open(
        os.path.join(ROOT, "docs", "V3_4_REGIONAL_WATER_PREREGISTRATION.md"),
        encoding="utf-8",
    ).read()
    assert "não pode" in text and "confirmação independente" in text
