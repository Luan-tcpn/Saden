"""Validação das implementações estatísticas da V2.7 (parte 2).

Verifica, sobre o **painel real** (mesma base da V2.6):
1. equivalência *within* ↔ LSDV pela API de alto nível;
2. coerência entre ``cluster_robust_fit`` e ``cluster_vcov``;
3. determinismo do ajuste agrupado;
4. propriedades da correção de Holm;
5. sanidade dos esquemas de agrupamento e do estimador de Conley.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import robust, spatial_inference  # noqa: E402
from agroclimate.analysis import holm_correction as holm_adjust  # noqa: E402
from run_robustness import ANALYSIS_VARIABLES, load_panel, prepare  # noqa: E402

OUT = os.path.join(
    ROOT, "geospatial", "data", "manifests", "v27_stats_validation.json"
)
report: dict = {"checks": []}


def check(name: str, ok: bool, detail) -> None:
    report["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"[{'OK ' if ok else 'FALHA'}] {name}: {detail}")


rows = prepare(load_panel())
print(f"painel preparado: {len(rows)} linhas")
by_crop: dict[str, list] = {}
for row in rows:
    by_crop.setdefault(str(row.get("crop")), []).append(row)
print("por cultura:", {k: len(v) for k, v in by_crop.items()})

# ---------------------------------------------- 1. within <-> LSDV (painel real)
print()
print("=== 1. Equivalencia within <-> LSDV (painel real) ===")
for crop, subset in sorted(by_crop.items()):
    for variable in ("precip_acumulada_mm", "deficiency_total_mm"):
        res = spatial_inference.within_coefficient_matches_lsdv(
            subset, variable, crop_filter=crop
        )
        if res.get("status") != "ok":
            print(f"    {crop}/{variable}: {res.get('status')}")
            continue
        dif = res["absolute_difference"]
        print(f"    {crop:8s} {variable:22s} LSDV={res['coefficient_lsdv']:.12f} "
              f"within={res['coefficient_within']:.12f} |dif|={dif:.2e}")
        check(f"within == LSDV ({crop}, {variable})", dif < 1e-6, f"diferenca {dif:.3e}")

# ------------------------------------------ 2. cluster_robust_fit <-> cluster_vcov
print()
print("=== 2. cluster_robust_fit <-> cluster_vcov (painel real) ===")
prepared = spatial_inference.within_data(rows, "deficiency_total_mm", crop_filter="soja")
X = np.column_stack([np.ones(prepared["n"]), prepared["x"]])
y = prepared["y"]
groups = [str(g) for g in prepared["municipalities"]]
fit = robust.cluster_robust_fit(X, y, groups, coef_index=1)
print("    coef:", f"{fit['coefficient']:.10f}", "| EP:", f"{fit['std_error_clustered']:.10f}",
      "| clusters:", fit["n_clusters"], "| t:", f"{fit['t_statistic']:.4f}")
resid = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
vcov, info = robust.cluster_vcov(X, resid, groups)
se = float(np.sqrt(max(vcov[1, 1], 0.0)))
check("EP coerente entre as duas rotas", abs(se - fit["std_error_clustered"]) < 1e-10,
      f"{se:.12f} vs {fit['std_error_clustered']:.12f}")
fit2 = robust.cluster_robust_fit(X, y, groups, coef_index=1)
check("determinismo do ajuste agrupado", fit["std_error_clustered"] == fit2["std_error_clustered"],
      "duas execucoes identicas")

# ------------------------------------------------------------ 3. Holm
print()
print("=== 3. Correcao de Holm ===")
p = {"a": 0.01, "b": 0.04, "c": 0.20}
adj = holm_adjust(p)
print("    ", {k: round(v, 6) for k, v in adj.items()})
check("Holm monotonica no p", adj["a"] <= adj["b"] <= adj["c"], "ordenacao preservada")
check("Holm nao diminui o p", all(adj[k] >= v for k, v in p.items()), "p ajustado >= p bruto")
check("Holm limitado a 1", all(v <= 1.0 for v in adj.values()), "todos <= 1")

# ------------------------------------- 4. Conley e two-way sobre o painel real
print()
print("=== 4. Conley e two-way (painel real) ===")
municipalities = {}
with open(os.path.join(ROOT, "geospatial", "data", "processed", "panel_municipalities.csv"),
          encoding="utf-8-sig", newline="") as handle:
    import csv as _csv

    for m in _csv.DictReader(handle):
        municipalities[m["ibge_code"]] = (
            float(m["centroid_lat"]), float(m["centroid_lon"])
        )
coords = {
    g: municipalities.get(g, (0.0, 0.0)) for g in set(groups)
}
for cutoff in (150.0, 250.0, 400.0, 600.0):
    vc, ic = robust.conley_vcov(X, resid, groups, coords, cutoff_km=cutoff)
    se_c = float(np.sqrt(max(vc[1, 1], 0.0)))
    print(f"    Conley({int(cutoff):>3d} km): EP {se_c:.8f} | peso medio {ic['mean_weight']:.4f}")
    check(f"Conley {int(cutoff)} km -> EP finito e positivo", np.isfinite(se_c) and se_c > 0,
          f"{se_c:.8f}")

vc2, info2 = robust.two_way_cluster_vcov(X, resid, groups, [str(g) for g in prepared["years"]])
se2 = float(np.sqrt(max(vc2[1, 1], 0.0)))
print("    two-way (município x ano): EP", f"{se2:.8f}", "| info:", info2)
check("two-way -> EP finito e positivo", np.isfinite(se2) and se2 > 0, f"{se2:.8f}")

report["summary"] = {
    "n_checks": len(report["checks"]),
    "n_ok": sum(1 for c in report["checks"] if c["ok"]),
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
    json.dump(report, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print()
print(f"RESULTADO: {report['summary']['n_ok']}/{report['summary']['n_checks']} verificacoes ok -> {OUT}")
