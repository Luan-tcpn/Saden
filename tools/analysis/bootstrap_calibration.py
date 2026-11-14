"""Calibração de inferência cluster-robusta sob a estrutura real do SADEN.

Mede, no desenho efetivamente usado pelos relatórios (G = 41â€“56 clusters UF × ano,
tamanhos de cluster reais, ICC real), quatro procedimentos:

1. ``cr1``  — t com erro agrupado CR1 (o que os relatórios usaram);
2. ``cr2``  — correção de amostras pequenas (Bellâ€“McCaffrey). **Degenera em CR1**
   com um único regressor: ``K2 = 1`` â‡’ ``(n−1)/(n−K2) = 1``. Reportado para
   documentar o fato, não como alternativa;
3. ``wcr``  — wild cluster bootstrap-t com H0 **imposta** (resíduos restritos),
   pesos de Rademacher por cluster, estatística studentizada;
4. ``wcu``  — o mesmo com resíduos **irrestritos** (WCU);
5. ``wcr_webb`` — WCR com os seis pesos de Webb.

Nada é reduzido: os tamanhos de cluster simulados são os reais, e o bootstrap é
calculado pelo núcleo exato de somas por cluster (``fast_bootstrap``), validado
contra a biblioteca.

Incerteza Monte Carlo: erro-padrão binomial e intervalo de Wilson por taxa.

Saídas: ``geospatial/data/manifests/bootstrap_calibration.json``
Uso: python tools/analysis/bootstrap_calibration.py [--simulations 5000] [--boot 999]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Sequence

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, HERE)

import fast_bootstrap as FB  # noqa: E402
from agroclimate import spatial_inference  # noqa: E402

_DATA_ROOT = os.environ.get("SADEN_DATA_ROOT") or os.path.join(ROOT, "geospatial", "data")
PROCESSED = os.path.join(_DATA_ROOT, "processed")
OUT_JSON = os.path.join(ROOT, "geospatial", "data", "manifests", "bootstrap_calibration.json")

ALPHA_LEVELS = (0.01, 0.05, 0.10)
WEBB = np.array([-math.sqrt(1.5), -1.0, -math.sqrt(0.5), math.sqrt(0.5), 1.0, math.sqrt(1.5)])
METHODS = ("cr1", "cr2", "wcr", "wcu", "wcr_webb")


def real_design() -> dict[str, Any]:
    """G, tamanhos de cluster e ICC observados no painel, por cultura."""
    path = os.path.join(PROCESSED, "v35_panel_windows.csv")
    by_crop: dict[str, list[dict[str, str]]] = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            by_crop.setdefault(str(row.get("crop")), []).append(row)

    out: dict[str, Any] = {}
    for crop, rows in sorted(by_crop.items()):
        usable = [
            row
            for row in rows
            if row.get("deficiency_total_mm_corrected") not in (None, "")
            and row.get("yield_kg_ha") not in (None, "")
        ]
        if len(usable) < 400:
            continue
        municipalities = [str(row["ibge_code"]) for row in usable]
        years = [str(row.get("harvest_year")) for row in usable]
        state_years = [f"{row.get('state')}||{row.get('harvest_year')}" for row in usable]
        y = np.array([float(row["yield_kg_ha"]) for row in usable])
        x = np.array([float(row["deficiency_total_mm_corrected"]) for row in usable])
        y_within = spatial_inference.within_transform(y, municipalities, years)
        x_within = spatial_inference.within_transform(x, municipalities, years)
        beta = float(np.dot(x_within, y_within) / np.dot(x_within, x_within))
        residuals = y_within - x_within * beta
        sizes = Counter(state_years)
        groups: dict[str, list[float]] = {}
        for value, label in zip(residuals, state_years):
            groups.setdefault(label, []).append(float(value))
        means = np.array([float(np.mean(v)) for v in groups.values()])
        grand = float(np.mean(residuals))
        denominator = max(len(residuals) - len(means), 1)
        between = float(
            np.sum([len(v) * (np.mean(v) - grand) ** 2 for v in groups.values()]) / denominator
        )
        within = float(
            np.sum([np.sum((np.array(v) - np.mean(v)) ** 2) for v in groups.values()]) / denominator
        )
        out[crop] = {
            "rows": len(usable),
            "n_clusters": len(sizes),
            "cluster_sizes": sorted(sizes.values()),
            "mean_cluster_size": float(np.mean(list(sizes.values()))),
            "icc": between / (between + within) if (between + within) > 0 else 0.0,
            "icc_x": _between_share(x_within, state_years),
            "between_var": between,
            "within_var": within,
            "x_sd_within": float(np.std(x_within)),
            "y_sd_within": float(np.std(y_within)),
            "residual_sd": float(np.std(residuals)),
            "se_cr1": _se_of(x_within, residuals, state_years),
            "beta": beta,
        }
    return out


def _between_share(values: np.ndarray, labels: Sequence[str]) -> float:
    """Fração da variância que é comum ao cluster (análogo do ICC)."""
    groups: dict[str, list[float]] = {}
    for value, label in zip(values, labels):
        groups.setdefault(label, []).append(float(value))
    sizes = np.array([len(v) for v in groups.values()], dtype="float64")
    means = np.array([float(np.mean(v)) for v in groups.values()], dtype="float64")
    grand = float(np.mean(values))
    denominator = max(len(values) - len(sizes), 1)
    between = float(np.sum(sizes * (means - grand) ** 2) / denominator)
    within = float(
        np.sum([np.sum((np.array(v) - np.mean(v)) ** 2) for v in groups.values()]) / denominator
    )
    total = between + within
    return between / total if total > 0 else 0.0


def _se_of(x: np.ndarray, residuals: np.ndarray, labels: Sequence[str]) -> float:
    """EP agrupado CR1 observado — usado para validar a simulação."""
    codes, n_groups = FB.group_codes(labels)
    b = np.bincount(codes, weights=x * x, minlength=n_groups)
    denominator = float(b.sum())
    scores = np.bincount(codes, weights=x * residuals, minlength=n_groups)
    multiplier = FB.cr1_multiplier(x.size, n_groups, 1)
    variance = multiplier * float(np.sum(scores**2)) / denominator**2
    return math.sqrt(variance) if variance > 0 else float("nan")


def simulate(
    rng: np.random.Generator,
    cluster_sizes: Sequence[int],
    icc: float,
    effect: float,
    x_sd: float,
    residual_sd: float = 1.0,
    x_icc: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, float]:
    """Painel *within* com componente de cluster e idiossincrático.

    O ICC controla a fração da variância do erro comum ao cluster UF × ano — a
    dependência que o agrupamento precisa absorver. ``residual_sd`` é o desvio
    real dos resíduos *within*, para que o efeito e o ruído fiquem na mesma
    unidade (kg/ha).
    """
    sizes = np.asarray(cluster_sizes, dtype="int64")
    codes = np.repeat(np.arange(sizes.size), sizes)
    n_groups = sizes.size
    n = int(sizes.sum())
    if x_icc is None:
        x_icc = icc
    # o regressor tem a escala observada (x_sd) e o erro a escala dos resíduos
    # reais (residual_sd); as duas escalas não se confundem. A fração de
    # variância comum ao cluster é estimada **separadamente** para o regressor
    # (icc_x) e para o erro (icc): a exposição climática é quase toda UF × ano,
    # o erro não.
    share_cluster_x = math.sqrt(x_icc)
    share_idio_x = math.sqrt(max(1.0 - x_icc, 1e-12))
    share_cluster = math.sqrt(icc)
    share_idio = math.sqrt(max(1.0 - icc, 1e-12))
    x = (
        rng.standard_normal(n_groups)[codes] * share_cluster_x
        + rng.standard_normal(n) * share_idio_x
    )
    x = (x - x.mean()) * x_sd
    noise = (
        rng.standard_normal(n_groups)[codes] * share_cluster
        + rng.standard_normal(n) * share_idio
    ) * residual_sd
    y = effect * x + noise
    y -= y.mean()
    return x, y, codes, n_groups, float(effect)


def wilson(count: int, n: int) -> list[float] | None:
    if n <= 0:
        return None
    z = 1.959963984540054
    phat = count / n
    denominator = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denominator
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denominator
    return [max(0.0, centre - half), min(1.0, centre + half)]


def calibrate_noise_scale(config: dict[str, Any], draws: int = 40, seed: int = 99) -> dict[str, Any]:
    """Ajusta o ruído para que o EP agrupado simulado reproduza o observado.

    Os testes sob H0 são invariantes à escala, mas o **poder** não: se o EP
    simulado for menor que o real, o poder aparece inflado. Aqui a escala do
    ruído é multiplicada pelo fator que iguala o EP mediano simulado ao EP CR1
    observado no painel (``se_cr1``). É casamento de momento, declarado.
    """
    rng = np.random.default_rng(seed)
    sizes = config["cluster_sizes"]
    observed = config["se_cr1"]
    simulated: list[float] = []
    for _ in range(draws):
        x, y, codes, n_groups, _ = simulate(
            rng, sizes, config["icc"], 0.0, config["x_sd_within"],
            config["residual_sd"], config.get("icc_x"),
        )
        fit = FB.cr1_fit(x, y, codes, n_groups)
        if fit.get("status") == "ok":
            simulated.append(fit["se"])
    median = float(np.median(simulated)) if simulated else float("nan")
    factor = observed / median if median and median > 0 else 1.0
    return {
        "observed_se": observed,
        "simulated_se_median": median,
        "noise_scale": factor,
        "residual_sd_calibrated": config["residual_sd"] * factor,
    }


def run_scenario(
    crop: str,
    config: dict[str, Any],
    simulations: int,
    n_boot: int,
    seed: int,
    effect_scale: float = 0.0,
    label: str = "",
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    sizes = config["cluster_sizes"]
    x_sd = config["x_sd_within"] or 1.0
    residual_sd = config.get("residual_sd_calibrated") or config.get("residual_sd") or 1.0
    effect = float(effect_scale)
    rejections = {name: {alpha: 0 for alpha in ALPHA_LEVELS} for name in METHODS}
    coverage = {name: {"covered": 0, "width": 0.0, "n": 0} for name in ("cr1", "wcr")}
    usable = 0
    started = time.time()

    for sim in range(simulations):
        x, y, codes, n_groups, true_beta = simulate(
            rng, sizes, config["icc"], effect, x_sd, residual_sd, config.get("icc_x")
        )
        fit = FB.cr1_fit(x, y, codes, n_groups)
        if fit.get("status") != "ok":
            continue
        usable += 1
        local = np.random.default_rng(seed * 1000003 + sim)
        rademacher = local.choice([-1.0, 1.0], size=(n_groups, n_boot))
        webb = local.choice(WEBB, size=(n_groups, n_boot))

        p_wcr = FB.wild_p(x, y, codes, n_groups, rademacher, fit["t"], restricted=True)
        p_wcu = FB.wild_p(x, y, codes, n_groups, rademacher, fit["t"], restricted=False,
                          observed_beta=fit["beta"])
        p_webb = FB.wild_p(x, y, codes, n_groups, webb, fit["t"], restricted=True)

        values = {
            "cr1": fit["p"],
            "cr2": fit["p"],           # k = 1 â‡’ CR2 â‰¡ CR1 (documentado)
            "wcr": p_wcr.get("p_value"),
            "wcu": p_wcu.get("p_value"),
            "wcr_webb": p_webb.get("p_value"),
        }
        for name, p_value in values.items():
            if p_value is None:
                continue
            for alpha in ALPHA_LEVELS:
                if p_value < alpha:
                    rejections[name][alpha] += 1

        half_cr1 = fit["critical"] * fit["se"]
        coverage["cr1"]["n"] += 1
        coverage["cr1"]["width"] += 2 * half_cr1
        if fit["beta"] - half_cr1 <= true_beta <= fit["beta"] + half_cr1:
            coverage["cr1"]["covered"] += 1
        quartile = p_wcr.get("t_boot_abs_q95")
        if quartile:
            half_wcr = float(quartile) * fit["se"]
            coverage["wcr"]["n"] += 1
            coverage["wcr"]["width"] += 2 * half_wcr
            if fit["beta"] - half_wcr <= true_beta <= fit["beta"] + half_wcr:
                coverage["wcr"]["covered"] += 1

    result: dict[str, Any] = {
        "label": label or f"{crop} | efeito {effect_scale:g}",
        "crop": crop,
        "n_clusters": config["n_clusters"],
        "mean_cluster_size": config["mean_cluster_size"],
        "icc": config["icc"],
        "effect_kg_ha_per_mm": effect,
        "n_simulations": simulations,
        "n_usable": usable,
        "n_boot": n_boot,
        "elapsed_s": round(time.time() - started, 1),
        "rejection": {},
        "coverage_95": {},
    }
    for name, counts in rejections.items():
        result["rejection"][name] = {}
        for alpha, count in counts.items():
            rate = count / usable if usable else None
            result["rejection"][name][f"alpha_{alpha}"] = {
                "rate": rate,
                "n_rejected": count,
                "mc_se": math.sqrt(rate * (1 - rate) / usable) if rate is not None and usable else None,
                "wilson95": wilson(count, usable),
            }
    for name, data in coverage.items():
        if not data["n"]:
            continue
        rate = data["covered"] / data["n"]
        result["coverage_95"][name] = {
            "rate": rate,
            "n": data["n"],
            "mean_width_kg_ha": data["width"] / data["n"],
            "wilson95": wilson(data["covered"], data["n"]),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=5000)
    parser.add_argument("--boot", type=int, default=999)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    simulations = 300 if args.quick else args.simulations

    designs = real_design()
    print("desenho real:")
    for crop, config in designs.items():
        scaling = calibrate_noise_scale(config)
        config.update(scaling)
        print(
            f"  {crop:8} G={config['n_clusters']:2d} m={config['mean_cluster_size']:6.1f} "
            f"icc={config['icc']:.3f} icc_x={config['icc_x']:.3f} beta={config['beta']:+.3f} "
            f"EP real={config['se_cr1']:.3f} (sim {scaling['simulated_se_median']:.3f} × "
            f"{scaling['noise_scale']:.2f})"
        )

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "design": designs,
        "settings": {
            "n_boot": args.boot,
            "alpha_levels": list(ALPHA_LEVELS),
            "simulations": simulations,
            "seed": args.seed,
            "structure": "G e tamanhos de cluster reais; ICC real; sem redução",
            "methods": {
                "cr1": "t agrupado CR1",
                "cr2": "CR2 — degenera em CR1 com k=1",
                "wcr": "wild cluster bootstrap-t, H0 imposta, Rademacher por cluster",
                "wcu": "wild cluster bootstrap-t, resíduos irrestritos",
                "wcr_webb": "WCR com pesos de Webb",
            },
        },
        "null_scenarios": [],
        "power_scenarios": [],
    }

    for crop, config in designs.items():
        scenario = run_scenario(crop, config, simulations, args.boot, args.seed,
                                label=f"{crop} | H0 | G={config['n_clusters']}")
        report["null_scenarios"].append(scenario)
        line = " ".join(
            f"{name}={scenario['rejection'][name]['alpha_0.05']['rate']:.4f}"
            for name in METHODS
        )
        print(f"{crop:8} H0 5%: {line}")

    mde = {"soja": 1.14, "milho": 2.11, "milho_2": 3.36}
    for crop, config in designs.items():
        if crop not in mde:
            continue
        scenario = run_scenario(
            crop, config, max(400, simulations // 4), args.boot, args.seed + 7,
            effect_scale=mde[crop],
            label=f"{crop} | MDE {mde[crop]} kg/ha/mm",
        )
        report["power_scenarios"].append(scenario)
        line = " ".join(
            f"{name}={scenario['rejection'][name]['alpha_0.05']['rate']:.3f}"
            for name in METHODS
        )
        print(f"{crop:8} poder@MDE: {line}")

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print("manifesto:", OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
