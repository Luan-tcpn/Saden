"""V3.5 — verificação programática dos números dos relatórios.

Confere os valores citados nos relatórios de SP, rebaseline e cobertura contra os
manifestos. Sai com código 1 se algo divergir.

Uso: python tools/v35_verify_report.py
"""

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
load = lambda name: json.load(open(os.path.join(MANIFESTS, name), encoding="utf-8"))

ACQ = load("v35_sp_acquisition.json")
MOD = load("v35_models.json")
COV = load("v35_coverage_robustness.json")
MAP = load("v35_region_mapping.json")

results = []


def chk(name, got, want, tol=0.06):
    ok = got is not None and abs(got - want) <= tol
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + f"{name}: got {got} want {want}")


def chk_exact(name, got, want):
    ok = got == want
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + f"{name}: got {got} want {want}")


# ---------------- aquisição ----------------
stages = ACQ["stages"]
chk_exact("municípios SP", stages["municipalities"]["sp_municipalities"], 645)
chk_exact("municípios combinados", stages["municipalities"]["combined_municipalities"], 2427)
chk_exact("clima: municípios", stages["climate"]["municipalities_with_climate"], 645)
chk_exact("clima: falhas", stages["climate"]["n_failures"], 0)
chk_exact("clima: linhas", stages["climate"]["n_rows"], 2356185)
chk_exact("PAM: registros", stages["productivity"]["n_records"], 46440)
chk_exact("PAM: rendimento", stages["productivity"]["n_yield_records"], 11610)
chk_exact("ZARC: linhas", stages["zarc"]["n_rows"], 1082148)
chk_exact("painel SP: linhas", stages["panel"]["n_rows"], 19608)
chk_exact("painel SP: utilizáveis", stages["panel"]["n_paired_usable"], 10805)
chk_exact("painel SP: soja", stages["panel"]["by_crop_paired_usable"]["soja"], 3633)
chk_exact("painel SP: milho", stages["panel"]["by_crop_paired_usable"]["milho"], 4397)
chk_exact("painel SP: milho 2ª", stages["panel"]["by_crop_paired_usable"]["milho_2"], 2775)

# ---------------- mapeamento ----------------
chk_exact("SP no mapeamento", MAP["sp"]["n_municipalities"], 643)
chk_exact("SP MRS 1", MAP["sp"]["by_macroregion"]["1"], 44)
chk_exact("SP MRS 2", MAP["sp"]["by_macroregion"]["2"], 431)
chk_exact("SP MRS 3", MAP["sp"]["by_macroregion"]["3"], 168)
chk_exact("mapeamento total", MAP["joined"]["n"], 2065)
chk_exact("seis estados inalterados", MAP["legacy_six_states_unchanged"], True)

# ---------------- experimento A (reprodução da V3.4) ----------------
A = MOD["experiments"]["A_six_states"]
chk("A milho M2", A["milho"]["m2"]["mae_model"], 1661.2)
chk("A soja M2", A["soja"]["m2"]["mae_model"], 592.7)
chk("A milho2 M2", A["milho_2"]["m2"]["mae_model"], 1272.3)
chk("A milho D", A["milho"]["D_sul_vs_cerrado"]["D"], -78.3, 0.3)
chk("A soja D", A["soja"]["D_sul_vs_cerrado"]["D"], -35.0, 0.3)
chk("A milho2 D", A["milho_2"]["D_sul_vs_cerrado"]["D"], -22.5, 0.3)
chk_exact("A milho n", A["milho"]["n_rows"], 7542)
chk_exact("A soja n", A["soja"]["n_rows"], 8868)
chk_exact("A milho2 n", A["milho_2"]["n_rows"], 2897)

# ---------------- experimento B (expandido) ----------------
B = MOD["experiments"]["B_expanded"]
for crop, m0, m1, m2, wb in (
    ("milho", 1487.6, 1538.8, 1452.8, 1472.7),
    ("soja", 604.7, 573.9, 554.7, 571.3),
    ("milho_2", 1326.6, 1384.6, 1234.4, 1241.2),
):
    chk(f"B {crop} M0", B[crop]["m2"]["mae_m0"], m0)
    chk(f"B {crop} M1", B[crop]["m2"]["mae_m1"], m1)
    chk(f"B {crop} M2", B[crop]["m2"]["mae_model"], m2)
    chk(f"B {crop} WB", B[crop]["wb"]["mae_model"], wb)
chk_exact("B milho n", B["milho"]["n_rows"], 11928)
chk_exact("B soja n", B["soja"]["n_rows"], 12491)
chk_exact("B milho2 n", B["milho_2"]["n_rows"], 5662)

# ---------------- dentro de SP ----------------
S = MOD["within_sp"]
chk_exact("SP soja n", S["soja"]["n_rows_sp"], 3623)
chk("SP soja MRS1 delta", S["soja"]["per_group"]["1"]["delta"], 2.5, 0.1)
chk("SP soja MRS3 delta", S["soja"]["per_group"]["3"]["delta"], -4.8, 0.1)
chk("SP soja D", S["soja"]["D_mrs1_vs_mrs3"]["year"]["D"], 7.26, 0.05)
chk("SP soja CI low", S["soja"]["D_mrs1_vs_mrs3"]["year"]["ci95"][0], -18.8, 0.3)
chk("SP soja CI high", S["soja"]["D_mrs1_vs_mrs3"]["year"]["ci95"][1], 26.9, 0.3)
chk("SP soja p", S["soja"]["D_mrs1_vs_mrs3"]["year"]["p_value"], 0.539, 0.01)
chk("SP soja interação p", S["soja"]["association"]["joint_test"]["p_value"], 0.7701, 0.002)
chk("SP milho D", S["milho"]["D_mrs1_vs_mrs3"]["year"]["D"], -18.58, 0.1)
chk("SP milho2 D", S["milho_2"]["D_mrs1_vs_mrs3"]["year"]["D"], -28.77, 0.1)

# ---------------- transferência ----------------
T = MOD["transfer"]
chk("transfer milho MAE", T["milho"]["mae_m2_trained_on_legacy"], 1721.15, 0.2)
chk("transfer milho ganho%", T["milho"]["gain_percent"], -27.3, 0.2)
chk("transfer soja ganho%", T["soja"]["gain_percent"], -5.9, 0.2)
chk("transfer milho2 ganho%", T["milho_2"]["gain_percent"], 4.06, 0.2)

# ---------------- cobertura ----------------
C = COV["coverage"]
chk_exact("legacy UFs", C["legacy"]["n_states"], 6)
chk_exact("legacy municípios", C["legacy"]["n_municipalities"], 1274)
chk_exact("legacy linhas", C["legacy"]["total_rows"], 19307)
chk_exact("expandido UFs", C["expanded"]["n_states"], 7)
chk_exact("expandido municípios", C["expanded"]["n_municipalities"], 1856)
chk_exact("expandido linhas", C["expanded"]["total_rows"], 30081)
chk_exact("reconciliação 1425", C["reconciliation_v34"]["official_pairs_six_states"], 1425)
chk_exact("reconciliação 1422", C["reconciliation_v34"]["matched_pairs"], 1422)
chk_exact("diferença 3", C["reconciliation_v34"]["difference"], 3)
chk_exact("SP com geometria", C["sp_funnel"]["sp_municipalities_with_geometry"], 645)
chk_exact("SP utilizáveis", C["sp_funnel"]["sp_municipalities_in_panel_usable"], 582)

# ---------------- robustez ----------------
R = COV["within_sp_robustness"]
soja_years = [v["D"] for v in R["soja"]["leave_one_year_out"].values() if v["D"] is not None]
chk("LOO soja min", min(soja_years), -17.8, 0.3)
chk("LOO soja max", max(soja_years), 13.2, 0.3)
chk("alt soja MRS1-2", R["soja"]["alternative_groups"]["MRS1_vs_MRS2"]["D_year"]["D"], 1.1, 0.2)
chk("alt soja MRS2-3", R["soja"]["alternative_groups"]["MRS2_vs_MRS3"]["D_year"]["D"], 9.0, 0.2)

print(f"\nTOTAL: {sum(results)}/{len(results)}")
if all(results):
    print("ALL PASS")
    sys.exit(0)
print("SOME FAILED")
sys.exit(1)
