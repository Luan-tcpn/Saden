"""V3.4 — verificação programática dos números dos relatórios.

Confere cada número citado nos três relatórios contra os manifestos. Sai com
código 1 se algo divergir.

Uso: python tools/v34_verify_report.py
"""

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
load = lambda name: json.load(open(os.path.join(MANIFESTS, name), encoding="utf-8"))

C = load("v34_regional_contrast.json")
R = load("v34_regional_robustness.json")
S = load("v34_regional_sensitivity.json")
V = load("v34_coverage_identifiability.json")
M = load("v34_region_mapping.json")
G = load("v34_coverage_gap.json")

results = []


def chk(name, got, want, tol=0.05):
    ok = got is not None and abs(got - want) <= tol
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + f"{name}: got {got} want {want}")


def chk_exact(name, got, want):
    ok = got == want
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + f"{name}: got {got} want {want}")


# ---------------- contraste principal ----------------
milho = C["crops"]["milho"]
soja = C["crops"]["soja"]
milho2 = C["crops"]["milho_2"]
chk("D milho", milho["contrast"]["D"], -78.28, 0.05)
chk("D milho CI low", milho["contrast"]["state_year"]["ci95"][0], -131.7, 0.2)
chk("D milho CI high", milho["contrast"]["state_year"]["ci95"][1], -26.7, 0.2)
chk("D milho p", milho["contrast"]["state_year"]["p_value"], 0.0010, 0.0005)
chk("D milho bloco low", milho["contrast"]["block"]["ci95"][0], -127.9, 0.2)
chk("D milho bloco high", milho["contrast"]["block"]["ci95"][1], -11.1, 0.2)
chk("Sul milho delta", milho["per_region"]["Sul"]["delta"], -45.53, 0.05)
chk("Cerrado milho delta", milho["per_region"]["Cerrado"]["delta"], 32.74, 0.05)
chk("n Sul milho", milho["per_region"]["Sul"]["n"], 2482, 0)
chk("n Cerrado milho", milho["per_region"]["Cerrado"]["n"], 2747, 0)
chk("D soja", soja["contrast"]["D"], -34.95, 0.05)
chk("D soja CI high", soja["contrast"]["state_year"]["ci95"][1], 0.7, 0.2)
chk("D milho2", milho2["contrast"]["D"], -22.50, 0.05)
chk("D milho2 CI high", milho2["contrast"]["state_year"]["ci95"][1], 1.4, 0.2)

# ---------------- por UF ----------------
for uf, want in (("RS", -68.5), ("PR", -27.5), ("MS", 7.0), ("GO", 21.4), ("MT", 55.0), ("BA", 344.0)):
    chk(f"milho UF {uf}", milho["per_uf"][uf]["delta"], want, 0.15)

# ---------------- UF x macroregião ----------------
for key, want in (
    ("RS|1", -68.5), ("PR|1", -14.5), ("PR|2", -34.7), ("MS|3", -50.3),
    ("MS|2", 31.6), ("GO|3", 13.9), ("GO|4", 29.2), ("MT|4", 55.0), ("BA|4", 324.2),
):
    chk(f"milho {key}", milho["per_uf_macroregion"][key]["delta"], want, 0.15)

# ---------------- associação ----------------
for crop, coef, p, g in (
    ("milho", -1287.3, 1.8e-06, 47),
    ("soja", -471.1, 0.0346, 39),
    ("milho_2", -1440.4, 0.0114, 27),
):
    entry = C["crops"][crop]["association"]
    chk(f"{crop} coef", entry["coefficients"]["x_sul"]["coefficient"], coef, 0.5)
    chk(f"{crop} p", entry["joint_test"]["p_value"], p, max(p * 0.1, 1e-7))
    chk(f"{crop} G", entry["joint_test"]["df2"], g, 0)
chk("milho assoc n", milho["association"]["n"], 5229, 0)

# ---------------- estabilidade ----------------
loo_uf = [v["D"] for v in R["crops"]["milho"]["leave_one_uf_out"].values()]
chk("milho LOO-UF min", min(loo_uf), -150.1, 0.2)
chk("milho LOO-UF max", max(loo_uf), -40.3, 0.2)
chk_exact("milho LOO-UF todos negativos", all(v < 0 for v in loo_uf), True)
loo_y = [v["D"] for v in R["crops"]["milho"]["leave_one_year_out"].values()]
chk("milho LOO-ano min", min(loo_y), -133.0, 0.2)
chk("milho LOO-ano max", max(loo_y), -44.5, 0.2)
chk_exact("milho LOO-ano todos negativos", all(v < 0 for v in loo_y), True)
soja_y = [v["D"] for v in R["crops"]["soja"]["leave_one_year_out"].values()]
chk("soja LOO-ano max", max(soja_y), 3.8, 0.2)
chk_exact("soja LOO-ano NAO todos negativos", all(v < 0 for v in soja_y), False)
m2_uf_all = {uf: v["D"] for uf, v in R["crops"]["milho_2"]["leave_one_uf_out"].items()}
# remover PR elimina o grupo Sul inteiro na milho 2ª (Sul = apenas PR-MRS1)
chk_exact("milho2 drop PR sem D", m2_uf_all.get("PR"), None)
m2_uf = [value for value in m2_uf_all.values() if value is not None]
chk("milho2 LOO-UF min", min(m2_uf), -9.7, 0.2)
chk("milho2 LOO-UF max", max(m2_uf), 47.0, 0.5)

# ---------------- dentro do estado ----------------
chk("PR milho coef", R["crops"]["milho"]["within_state"]["PR"]["association"]["coefficients"]["x_macro"]["coefficient"], 1011.7, 0.5)
chk("PR milho p", R["crops"]["milho"]["within_state"]["PR"]["association"]["joint_test"]["p_value"], 0.0022, 0.0005)
chk("GO milho p", R["crops"]["milho"]["within_state"]["GO"]["association"]["joint_test"]["p_value"], 0.7353, 0.001)
chk("MS milho p", R["crops"]["milho"]["within_state"]["MS"]["association"]["joint_test"]["p_value"], 0.1103, 0.001)
for uf, p in (("GO", 0.0251), ("MS", 0.0333), ("PR", 0.0020)):
    chk(f"milho2 dentro {uf} p", R["crops"]["milho_2"]["within_state"][uf]["association"]["joint_test"]["p_value"], p, 0.001)

# ---------------- sensibilidades ----------------
variants = S["crops"]["milho"]["variants"]
chk("sens primaria obs", variants["primaria"]["observation"]["D"], -78.3, 0.1)
chk("sens primaria uf", variants["primaria"]["uf"]["D"], -129.1, 0.2)
chk("sens mrs3", variants["cerrado_restrito_mrs3"]["observation"]["D"], -48.4, 0.1)
chk("sens sem MT", variants["cerrado_sem_mt"]["observation"]["D"], -65.9, 0.1)
chk("sens sul+transicao", variants["sul_com_transicao"]["observation"]["D"], -67.7, 0.1)
chk("sens edafo", variants["edafoclimatica"]["observation"]["D"], -91.4, 0.1)
deciles = S["crops"]["milho"]["deficit_deciles"]
negatives = sum(1 for v in deciles.values() if v["D"] is not None and v["D"] < 0)
present = sum(1 for v in deciles.values() if v["D"] is not None)
chk_exact("milho decis negativos", (negatives, present), (9, 10))
chk("milho decil positivo", [v["D"] for v in deciles.values() if v["D"] is not None and v["D"] > 0][0], 37.0, 0.2)

# ---------------- cobertura / identificação ----------------
chk_exact("Cramers V milho", round(V["crops"]["milho"]["confounding"]["cramers_v"], 6), 1.0)
chk_exact("nenhuma UF nos dois grupos", V["crops"]["milho"]["confounding"]["ufs_in_both_groups"], [])
chk_exact("regioes aninhadas", V["identifiability_verdict"]["regions_nested_in_uf"], True)
chk("deficit mediano Sul", V["crops"]["milho"]["groups"]["Sul"]["deficit_median"], 0.97, 0.02)
chk("deficit mediano Cerrado", V["crops"]["milho"]["groups"]["Cerrado"]["deficit_median"], 74.44, 0.05)
chk("municipios mapeados", M["join"]["matched"], 1422, 0)
chk("linhas planilha", M["coverage"]["rows_total"], 4286, 0)
chk("pares 6 estados", M["coverage"]["rows_panel_states"], 1425, 0)
chk_exact("duplicados", M["coverage"]["duplicate_state_municipality"], 0)

# ---------------- lacuna territorial ----------------
chk("total indicado", G["denominator"]["total_municipalities_with_soybean_indication"], 4286, 0)
chk("nos 6 estados", G["denominator"]["in_the_six_panel_states"], 1425, 0)
chk("share coberto", G["denominator"]["share_of_indicated_territory_covered_by_scope"], 0.3325, 0.0005)
chk("UFs ausentes", G["gap"]["n_absent_states"], 15, 0)
chk("municipios fora", G["gap"]["municipalities_with_indication_outside_scope"], 2861, 0)
chk("share fora", G["gap"]["share_of_indicated_territory_outside_scope"], 0.6675, 0.0005)
chk_exact(
    "SP e a unica que quebra o confundimento",
    [item["uf"] for item in G["would_break_confounding"]],
    ["SP"],
)
chk("SP municipios", G["would_break_confounding"][0]["municipalities"], 645, 0)

# ---------------- família confirmatória ----------------
family = C["confirmatory_family"]
chk("familia tamanho", family["size"], 2, 0)
chk("p preditivo", family["raw"]["preditivo_D"], 0.0010, 0.0005)
chk("p associativo", family["raw"]["associativo_interacao"], 1.8e-06, 1e-7)
chk_exact("ambos rejeitam", len(family["rejected"]), 2)

print(f"\nTOTAL: {sum(results)}/{len(results)}")
if all(results):
    print("ALL PASS")
    sys.exit(0)
print("SOME FAILED")
sys.exit(1)
