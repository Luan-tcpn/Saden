"""V3.4 — figuras do contraste regional (reprodutíveis).

Gera seis figuras em `docs/figures/v34/`. Todas com unidade, orientação da
métrica e tamanho de amostra no rótulo/eixo.

Uso: python tools/v34_figures.py
"""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUTDIR = os.path.join(ROOT, "docs", "figures", "v34")

GROUP_COLOR = {"Sul": "#1f77b4", "Cerrado": "#d62728", "Transicao": "#7f7f7f", "Fora": "#bcbd22"}


def _load(name):
    return json.load(open(os.path.join(MANIFESTS, name), encoding="utf-8"))


def _municipalities(crop):
    path = os.path.join(MANIFESTS, "v34_municipality_delta", f"{crop}.csv")
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "code": row["ibge_code"],
                    "uf": row["uf"],
                    "group": row["group"],
                    "macro": row["macroregion"],
                    "n": int(row["n"]),
                    "delta": float(row["delta"]),
                }
            )
    return rows


def fig_municipality_distribution(crop="milho"):
    rows = _municipalities(crop)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bins = np.linspace(-400, 400, 61)
    for group in ("Sul", "Cerrado", "Transicao"):
        values = [r["delta"] for r in rows if r["group"] == group]
        if not values:
            continue
        ax.hist(values, bins=bins, alpha=0.55, label=f"{group} (n={len(values)} municípios)",
                color=GROUP_COLOR[group])
    ax.axvline(0, color="black", linewidth=1)
    ax.set_xlabel("ΔMAE por município, kg/ha (bloco hídrico − M2; negativo = bloco melhor)")
    ax.set_ylabel("número de municípios")
    ax.set_title(f"{crop}: distribuição municipal do efeito do bloco hídrico (TE)")
    ax.legend(frameon=False)
    ax.set_xlim(-400, 400)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTDIR, f"f1_municipality_delta_{crop}.png"), dpi=160)
    plt.close(fig)


def fig_by_uf(crop="milho"):
    payload = _load("v34_regional_contrast.json")
    per_uf = payload["crops"][crop]["per_uf"]
    ufs = list(per_uf)
    values = [per_uf[uf]["delta"] for uf in ufs]
    ns = [per_uf[uf]["n"] for uf in ufs]
    groups = []
    pair = payload["crops"][crop]["per_uf_macroregion"]
    for uf in ufs:
        macro_groups = [k.split("|")[1] for k in pair if k.startswith(uf + "|")]
        # UF é Sul se todos os seus pares estão em MRS 1
        groups.append("Sul" if set(macro_groups) <= {"1"} else "Cerrado")
    fig, ax = plt.subplots(figsize=(7, 4))
    colors = [GROUP_COLOR[g] for g in groups]
    ax.bar(ufs, values, color=colors)
    for index, (value, n) in enumerate(zip(values, ns)):
        ax.text(index, value + (8 if value >= 0 else -18), f"n={n}", ha="center", fontsize=7)
    ax.axhline(0, color="black", linewidth=1)
    ax.set_ylabel("ΔMAE, kg/ha (negativo = bloco hídrico melhor)")
    ax.set_title(f"{crop}: efeito do bloco hídrico por UF (TE), linhas de teste")
    fig.tight_layout()
    fig.savefig(os.path.join(OUTDIR, f"f2_by_uf_{crop}.png"), dpi=160)
    plt.close(fig)


def fig_regional_contrast():
    payload = _load("v34_regional_contrast.json")
    crops = [c for c in ("milho", "soja", "milho_2") if c in payload["crops"]]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    width = 0.36
    positions = np.arange(len(crops))
    sul = [payload["crops"][c]["per_region"]["Sul"]["delta"] for c in crops]
    cerrado = [payload["crops"][c]["per_region"]["Cerrado"]["delta"] for c in crops]
    ax.bar(positions - width / 2, sul, width, label="Sul (MRS 1)", color=GROUP_COLOR["Sul"])
    ax.bar(positions + width / 2, cerrado, width, label="Cerrado (MRS 3∪4)",
           color=GROUP_COLOR["Cerrado"])
    top = max(max(sul), max(cerrado))
    bottom = min(min(sul), min(cerrado))
    margin = (top - bottom) * 0.45 or 20.0
    for index, crop in enumerate(crops):
        d = payload["crops"][crop]["contrast"]["D"]
        low, high = payload["crops"][crop]["contrast"]["state_year"]["ci95"]
        y = top + margin * 0.35
        ax.plot([index - width, index + width], [y, y], color="black", linewidth=1)
        ax.text(index, y + margin * 0.12, f"D={d:+.0f}\n[{low:.0f}; {high:.0f}]",
                ha="center", va="bottom", fontsize=7.5)
    ax.axhline(0, color="black", linewidth=1)
    ax.set_ylim(bottom - margin * 0.15, top + margin)
    ax.set_xticks(positions)
    ax.set_xticklabels(["milho", "soja", "milho 2ª"])
    ax.set_ylabel("ΔMAE por região, kg/ha\n(negativo = bloco hídrico melhor)")
    ax.set_title("ΔMAE do bloco hídrico por região (D e IC de UF×ano)", fontsize=10)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(os.path.join(OUTDIR, "f3_regional_contrast.png"), dpi=160)
    plt.close(fig)


def fig_loo():
    payload = _load("v34_regional_robustness.json")
    crops = [c for c in ("milho", "soja", "milho_2") if c in payload["crops"]]
    fig, axes = plt.subplots(1, len(crops), figsize=(4.2 * len(crops), 3.8), sharey=True)
    if len(crops) == 1:
        axes = [axes]
    for ax, crop in zip(axes, crops):
        entry = payload["crops"][crop]
        labels = list(entry["leave_one_uf_out"])
        values = [entry["leave_one_uf_out"][uf]["D"] for uf in labels]
        ax.axhline(entry["baseline_D"], color="black", linewidth=1, label="D completo")
        ax.scatter(range(len(labels)), values, color=GROUP_COLOR["Sul"], zorder=3)
        ax.axhline(0, color="red", linewidth=0.8, linestyle="--")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_title(crop, fontsize=9)
        ax.set_xlabel("UF removida")
        if ax is axes[0]:
            ax.set_ylabel("D (ΔMAE Sul − Cerrado), kg/ha")
    fig.suptitle("Estabilidade do contraste regional: leave-one-UF-out", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTDIR, "f4_leave_one_uf_out.png"), dpi=160)
    plt.close(fig)


def fig_support():
    coverage = _load("v34_coverage_identifiability.json")
    sensitivity = _load("v34_regional_sensitivity.json")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    ax = axes[0]
    crops = [c for c in ("milho", "soja", "milho_2") if c in coverage["crops"]]
    for crop in crops:
        item = coverage["crops"][crop]["groups"]
        for group in ("Sul", "Cerrado"):
            if group not in item:
                continue
            ax.scatter(
                item[group]["deficit_median"], item[group]["yield_median"],
                color=GROUP_COLOR[group], s=60,
                marker="o" if crop == "milho" else ("s" if crop == "soja" else "^"),
            )
        ax.annotate(crop, (item["Cerrado"]["deficit_median"], item["Cerrado"]["yield_median"]),
                    fontsize=7, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("déficit mediano por região, mm")
    ax.set_ylabel("produtividade mediana, kg/ha")
    ax.set_title("Suporte: déficit × produtividade por região", fontsize=9)
    ax.scatter([], [], color=GROUP_COLOR["Sul"], label="Sul")
    ax.scatter([], [], color=GROUP_COLOR["Cerrado"], label="Cerrado")
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1]
    deciles = sensitivity["crops"]["milho"]["deficit_deciles"]
    keys = list(deciles)
    values = [deciles[k]["D"] for k in keys]
    labels = [f"{deciles[k]['range_mm'][0]*100:.0f}–{deciles[k]['range_mm'][1]*100:.0f}" for k in keys]
    ax.bar(range(len(keys)), [v if v is not None else 0 for v in values],
           color=["#1f77b4" if (v is not None and v < 0) else "#d62728" for v in values])
    ax.axhline(0, color="black", linewidth=1)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(labels, rotation=45, fontsize=7)
    ax.set_xlabel("decil do déficit agrupado, mm")
    ax.set_ylabel("D (ΔMAE Sul − Cerrado), kg/ha")
    ax.set_title("D por decil de déficit (milho): a diferença não é só suporte", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTDIR, "f5_support.png"), dpi=160)
    plt.close(fig)


def fig_influence():
    payload = _load("v34_regional_contrast.json")
    sensitivity = _load("v34_regional_sensitivity.json")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    ax = axes[0]
    pair = payload["crops"]["milho"]["per_uf_macroregion"]
    keys = list(pair)
    values = [pair[k]["delta"] for k in keys]
    ns = [pair[k]["n"] for k in keys]
    colors = [GROUP_COLOR["Sul"] if ("|1" in k) else GROUP_COLOR["Cerrado"] for k in keys]
    ax.barh(range(len(keys)), values, color=colors)
    for index, (value, n) in enumerate(zip(values, ns)):
        ax.text(value + (6 if value >= 0 else -6), index, f"n={n}", va="center",
                ha="left" if value >= 0 else "right", fontsize=7)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels(keys, fontsize=8)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_xlabel("ΔMAE, kg/ha")
    ax.set_title("milho: UF × macrorregião (mesmo protocolo)", fontsize=9)
    ax.invert_yaxis()

    ax = axes[1]
    variants = sensitivity["crops"]["milho"]["variants"]
    labels = list(variants)
    obs = [variants[v]["observation"]["D"] for v in labels]
    uf = [variants[v]["uf"]["D"] for v in labels]
    positions = np.arange(len(labels))
    ax.barh(positions - 0.2, obs, 0.4, label="peso por observação", color="#1f77b4")
    ax.barh(positions + 0.2, uf, 0.4, label="peso por UF", color="#d62728")
    ax.axvline(0, color="black", linewidth=1)
    ax.set_yticks(positions)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("D (ΔMAE Sul − Cerrado), kg/ha")
    ax.set_title("milho: classificações e ponderações alternativas", fontsize=9)
    ax.legend(frameon=False, fontsize=7)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(os.path.join(OUTDIR, "f6_influence.png"), dpi=160)
    plt.close(fig)


def main() -> int:
    os.makedirs(OUTDIR, exist_ok=True)
    fig_municipality_distribution("milho")
    fig_by_uf("milho")
    fig_regional_contrast()
    fig_loo()
    fig_support()
    fig_influence()
    files = sorted(os.listdir(OUTDIR))
    print("figuras geradas:")
    for name in files:
        print("  ", name, os.path.getsize(os.path.join(OUTDIR, name)), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
