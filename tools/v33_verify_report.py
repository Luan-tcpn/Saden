"""V3.3 — verificação programática dos números dos relatórios.

Compara cada número citado nos três relatórios da V3.3 contra o manifesto
correspondente. Não substitui os testes: é o controle de transcrição exigido
pela §19.4 do escopo da versão.

Sai com código 1 se qualquer verificação falhar.

Uso: python tools/v33_verify_report.py
"""

import json
import os
import statistics as statistics_mod
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
base = os.path.join(ROOT, "geospatial", "data", "manifests")
load = lambda n: json.load(open(os.path.join(base, n), encoding="utf-8"))
FF = load("v33_functional_form.json")
RB = load("v33_functional_robustness.json")
AU = load("v33_inference_audit.json")
VA = load("v33_variable_audit.json")

results = []


def chk(name, got, want, tol=0.02):
    ok = got is not None and abs(got - want) <= tol
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + f"{name}: got {got} want {want}")


def chk_rel(name, got, want, rel=0.02):
    ok = got is not None and abs(got - want) <= rel * max(abs(want), 1e-12)
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + f"{name}: got {got} want {want}")


# ---------------- Frente A: MAE ----------------
m = FF["crops"]
chk("M2 milho", m["milho"]["models"]["M2"]["mae_te"], 1688.58)
chk("M2 soja", m["soja"]["models"]["M2"]["mae_te"], 592.19)
chk("M2 milho_2", m["milho_2"]["models"]["M2"]["mae_te"], 1272.40)
chk("WB_plus milho", m["milho"]["models"]["M2_WB_plus"]["mae_te"], 1689.90)
chk("WB_plus soja", m["soja"]["models"]["M2_WB_plus"]["mae_te"], 600.38)
chk("WB_plus milho_2", m["milho_2"]["models"]["M2_WB_plus"]["mae_te"], 1282.51)
chk("NL milho", m["milho"]["models"]["M2_WB_NL"]["mae_te"], 1741.00)
chk("THERM milho", m["milho"]["models"]["M2_THERM"]["mae_te"], 1836.23)

# ---------------- Frente A: pairs ----------------
p = m["milho"]["pairs"]
chk("H1 delta", p["M2_WB_plus_vs_M2"]["delta_mae"], 1.33)
chk("H1 ci low", p["M2_WB_plus_vs_M2"]["state_year"]["ci95"][0], -47.9, 0.2)
chk("H1 ci high", p["M2_WB_plus_vs_M2"]["state_year"]["ci95"][1], 49.8, 0.2)
chk("H4 delta", p["M2_WB_THERM_vs_M2_WB_plus"]["delta_mae"], 34.13)
chk("H2 delta", p["M2_WB_NL_vs_M2_WB_plus"]["delta_mae"], 51.10)
chk("NL milho2 delta", m["milho_2"]["pairs"]["M2_WB_NL_vs_M2_WB_plus"]["delta_mae"], 194.98)
chk("NL milho2 ci low", m["milho_2"]["pairs"]["M2_WB_NL_vs_M2_WB_plus"]["state_year"]["ci95"][0], 86.5, 0.2)
chk("NL milho2 ci high", m["milho_2"]["pairs"]["M2_WB_NL_vs_M2_WB_plus"]["state_year"]["ci95"][1], 294.0, 0.3)
chk("WB so milho delta", p["M2_WB_vs_M2"]["delta_mae"], 51.97)
chk("THERM vs M2", p["M2_THERM_vs_M2"]["delta_mae"], 147.65)
chk("INT vs THERM", p["M2_WB_THERM_INT_vs_M2_WB_THERM"]["delta_mae"], 6.15)
chk("soja WB_plus delta", m["soja"]["pairs"]["M2_WB_plus_vs_M2"]["delta_mae"], 8.20)
chk("milho2 WB_plus delta", m["milho_2"]["pairs"]["M2_WB_plus_vs_M2"]["delta_mae"], 10.11)

# ---------------- Frente A: confirmatory ----------------
raw = FF["confirmatory_family"]["raw"]
chk("H1 p", raw["H1"], 0.953, 0.002)
chk("H2 p", raw["H2"], 0.101, 0.002)
chk("H4 p", raw["H4"], 0.167, 0.002)
assert FF["confirmatory_family"]["rejected"] == [], "nao deveria haver rejeicao"

# ---------------- Frente A: association ----------------
inf = FF["inference"]["milho"]
chk("agua milho p", inf["water_block_beyond_climate"]["joint_test"]["p_value"], 0.0382, 0.001)
chk("nao-linear milho p", inf["nonlinearity"]["joint_test"]["p_value"], 0.0138, 0.001)
chk("termico milho p", inf["thermal_beyond_water"]["joint_test"]["p_value"], 0.9612, 0.002)
fam = FF["association_families"]["milho"]["holm"]
chk("agua holm", fam["agua"], 0.0763, 0.001)
chk("nao-linear holm", fam["nao_linear"], 0.0414, 0.001)

# ---------------- Frente A: by UF ----------------
st = m["milho"]["models"]
for uf, want in (("PR", -33.8), ("RS", -53.1), ("MS", 4.1), ("GO", 45.7), ("MT", 94.1), ("BA", 173.5)):
    got = st["M2_WB_plus"]["by_state"][uf]["mae_model"] - st["M2"]["by_state"][uf]["mae_model"]
    chk(f"delta {uf}", got, want, 0.15)
soja = m["soja"]["models"]
for uf, want in (("PR", -4.7), ("RS", -5.2), ("MS", 49.9), ("MT", 58.2)):
    got = soja["M2_WB_plus"]["by_state"][uf]["mae_model"] - soja["M2"]["by_state"][uf]["mae_model"]
    chk(f"soja delta {uf}", got, want, 0.15)

# ---------------- Frente A: robustness ----------------
loo = RB["crops"]["milho"]["leave_one_uf_out"]
chk("LOO PR", loo["PR"]["delta_mae"], 103.49, 0.2)
chk("LOO RS", loo["RS"]["delta_mae"], 13.10, 0.2)
chk("LOO BA", loo["BA"]["delta_mae"], 43.31, 0.2)
chk("LOO GO", loo["GO"]["delta_mae"], 63.65, 0.2)
loy = RB["crops"]["milho"]["leave_one_year_out"]
chk("LOY 2021", loy["2021"]["delta_mae"], 57.75, 0.2)
chk("LOY 2019", loy["2019"]["delta_mae"], -7.25, 0.2)

# ---------------- Frente B: families ----------------
f1, f2, f3 = AU["families"]["F1_v27"], AU["families"]["F2_v30"], AU["families"]["F3_v29_interaction"]
chk("F1 hist holm", f1["historical"]["n_significant_holm"], 4, 0)
chk("F1 hist raw", f1["historical"]["n_significant_raw"], 10, 0)
chk("F1 audit holm", f1["audited"]["n_significant_holm_two_way"], 0, 0)
chk("F1 audit raw", f1["audited"]["n_significant_raw_two_way"], 4, 0)
chk("F2 hist holm", f2["historical"]["n_significant_holm"], 10, 0)
chk("F2 audit holm", f2["audited"]["n_significant_holm_two_way"], 8, 0)
chk("F2 audit raw", f2["audited"]["n_significant_raw_two_way"], 9, 0)
chk("F3 hist holm", f3["audited"]["n_significant_holm_block"], 1, 0)
chk("F3 audit raw", f3["audited"]["n_significant_raw_two_way"], 0, 0)

# reproduction
chk_rel("F1 reproducao", f1["reproduction_max_abs_diff"], 1.5e-6, 1.0)
chk_rel("F2 reproducao", f2["reproduction_max_abs_diff"], 3.55e-15, 1.0)
chk_rel("F3 reproducao", f3["reproduction_max_abs_diff"], 9.2e-8, 1.0)

# ---------------- Frente B: specific hipoteses ----------------
r1 = f1["results"]
chk("soja temp p bloco", r1["soja|temp_media_c"]["schemes"]["bloco_espacial_250km"]["p_value"], 4.3e-5, 1e-6)
chk("soja temp p 2way", r1["soja|temp_media_c"]["schemes"]["two_way"]["p_value"], 0.1849, 0.002)
chk("soja deficit p bloco", r1["soja|deficiency_total_mm"]["schemes"]["bloco_espacial_250km"]["p_value"], 4.1e-6, 1e-7)
chk("soja deficit p 2way", r1["soja|deficiency_total_mm"]["schemes"]["two_way"]["p_value"], 0.0361, 0.002)
chk("milho et0 p bloco", r1["milho|et0_total_mm"]["schemes"]["bloco_espacial_250km"]["p_value"], 2.42e-6, 1e-7)
chk("milho et0 p 2way", r1["milho|et0_total_mm"]["schemes"]["two_way"]["p_value"], 0.0214, 0.002)
chk("milho temp p 2way", r1["milho|temp_media_c"]["schemes"]["two_way"]["p_value"], 0.0606, 0.002)
chk("milho temp holm bloco", r1["milho|temp_media_c"]["p_holm_block"], 0.0069, 0.001)
chk("soja deficit holm bloco", r1["soja|deficiency_total_mm"]["p_holm_block"], 0.0001, 0.001)
chk("milho et0 holm bloco", r1["milho|et0_total_mm"]["p_holm_block"], 5.1e-5, 1e-5)
chk("soja temp holm bloco", r1["soja|temp_media_c"]["p_holm_block"], 0.0008, 0.001)

r2 = f2["results"]
chk("milho cad200 p bloco", r2["milho|deficit_cad200"]["schemes"]["bloco_espacial_250km"]["p_value"], 0.0016, 0.001)
chk("milho cad200 p 2way", r2["milho|deficit_cad200"]["schemes"]["two_way"]["p_value"], 0.0851, 0.002)
chk("soja corr50 coef", r2["soja|deficit_corr50"]["coefficient"], -2.448, 0.002)
chk("soja hist coef", r2["soja|deficit_hist"]["coefficient"], -1.260, 0.002)
chk("soja hist holm 2way", r2["soja|deficit_hist"]["p_holm_two_way"], 0.2530, 0.002)
chk("soja corr50 holm 2way", r2["soja|deficit_corr50"]["p_holm_two_way"], 0.0000, 0.001)

r3 = f3["results"]
chk("soja ciclo deficit p bloco", r3["soja|deficiency_total_mm"]["p_bloco_espacial_250km"], 0.0028, 0.001)
chk("soja ciclo deficit p 2way", r3["soja|deficiency_total_mm"]["p_two_way"], 0.173, 0.002)

# ---------------- Frente B: SE ratios ----------------
import statistics as statistics_mod

def ratios(fam):
    out = []
    for k, r in fam["results"].items():
        if r.get("status") != "ok":
            continue
        if fam is f3:
            a, b = r["se_bloco_espacial_250km"], r["se_two_way"]
        else:
            a = r["schemes"]["bloco_espacial_250km"]["std_error"]
            b = r["schemes"]["two_way"]["std_error"]
        out.append(b / a)
    return out

for fam, name, want in ((f1, "F1", (0.66, 1.64, 3.36)), (f2, "F2", (0.88, 1.65, 2.42)), (f3, "F3", (0.56, 1.23, 2.28))):
    v = ratios(fam)
    chk(f"{name} ratio min", min(v), want[0], 0.01)
    chk(f"{name} ratio med", statistics_mod.median(v), want[1], 0.01)
    chk(f"{name} ratio max", max(v), want[2], 0.01)

# ---------------- Variaveis: identidade e correlacao ----------------
soja_corr = VA["crops"]["soja"]["within_correlation"]
names = soja_corr["variables"]
i = names.index("etr_over_etp")
j = names.index("deficit_over_etp")
chk("identidade etr x def", soja_corr["matrix"][i][j], -1.0, 0.001)
milho_corr = VA["crops"]["milho"]["within_correlation"]
mn = milho_corr["variables"]
a = mn.index("heat_corrected"); b = mn.index("deficit_total_mm")
chk("heat x deficit milho", milho_corr["matrix"][a][b], 0.839, 0.005)
c = mn.index("degree_days_corrected"); d = mn.index("temp_corrected")
chk("gdd x temp milho", milho_corr["matrix"][c][d], 0.020, 0.005)

print(f"\nTOTAL: {sum(results)}/{len(results)}")
if all(results):
    print("ALL PASS")
    sys.exit(0)
print("SOME FAILED")
sys.exit(1)
