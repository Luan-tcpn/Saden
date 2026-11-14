"""Análise de poder e efeito mínimo detectável (MDE) do desenho SADEN.

Não estima hipóteses novas: caracteriza o **poder do desenho já utilizado**.
Trabalha com o mesmo estimador dos relatórios V2.7â€“V3.5 — transformação *within*
(município e ano) com erro-padrão agrupado em UF × ano (D104/D111) — e produz:

* MDE a 80% e 90% em kg/ha para cada exposição já investigada;
* taxa de erro tipo I sob H0 por Monte Carlo, respeitando os clusters reais;
* poder observado na magnitude do MDE;
* cenários de desenho: mais municípios, mais anos, mais UFs.

O MDE **não** usa o N bruto: parte do erro-padrão agrupado efetivamente
estimado, que já contém a dependência municipal e a exposição compartilhada em
UF × ano.

Uso: python tools/analysis/statistical_power.py [--simulations 400]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Sequence

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import robust, spatial_inference  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
OUT_JSON = os.path.join(ROOT, "geospatial", "data", "manifests", "statistical_power.json")

CROPS = ("soja", "milho", "milho_2")
EXPOSURES = {
    "deficit": "deficiency_total_mm_corrected",
    "precipitacao": "precip_acumulada_mm_corrected",
    "et0": "et0_total_mm_corrected",
    "graus_dia": "degree_days_total_corrected",
    "calor_extremo": "extreme_heat_days_corrected",
    "temperature": "temp_media_c_corrected",
}
ALPHA = 0.05


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_panel() -> dict[str, list[dict[str, Any]]]:
    panel: dict[str, list[dict[str, Any]]] = {crop: [] for crop in CROPS}
    path = os.path.join(PROCESSED, "v35_panel_windows.csv")
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            crop = str(row.get("crop"))
            if crop not in panel:
                continue
            panel[crop].append(
                {
                    "ibge_code": str(row["ibge_code"]),
                    "state": str(row["state"]),
                    "year": str(row.get("harvest_year")),
                    "yield_kg_ha": _num(row.get("yield_kg_ha")),
                }
                | {key: _num(row.get(column)) for key, column in EXPOSURES.items()}
            )
    return panel


def design_arrays(rows: Sequence[dict[str, Any]], exposure: str):
    usable = [
        row
        for row in rows
        if row.get(exposure) is not None and row.get("yield_kg_ha") is not None
    ]
    municipalities = [row["ibge_code"] for row in usable]
    years = [row["year"] for row in usable]
    state_years = [f"{row['state']}||{row['year']}" for row in usable]
    y = np.array([row["yield_kg_ha"] for row in usable], dtype="float64")
    x = np.array([row[exposure] for row in usable], dtype="float64")
    return usable, municipalities, years, state_years, y, x


def fit_within(y: np.ndarray, x: np.ndarray, municipalities, years, state_years):
    """Estimador dos relatórios: within + erro agrupado em UF × ano."""
    y_within = spatial_inference.within_transform(y, municipalities, years)
    x_within = spatial_inference.within_transform(x, municipalities, years)
    design = x_within.reshape(-1, 1)
    if float(np.std(design)) == 0.0:
        return None
    beta = float(np.linalg.lstsq(design, y_within, rcond=None)[0][0])
    residuals = y_within - x_within * beta
    vcv, info = robust.cluster_vcov(design, residuals, state_years, correction=robust.CR1)
    std_error = float(np.sqrt(max(vcv[0, 0], 0.0)))
    n_clusters = int(info["n_clusters"])
    return {
        "beta": beta,
        "se": std_error,
        "residuals": residuals,
        "x_within": x_within,
        "y_within": y_within,
        "n_clusters": n_clusters,
        "df": max(n_clusters - 1, 1),
        "n": len(y_within),
    }


def mde(std_error: float, df: int, power: float = 0.80, alpha: float = ALPHA) -> float:
    """MDE = (t_{1−α/2,df} + t_{power,df}) × SE — válido para o teste t usado."""
    return (robust.t_critical(alpha, df) + _t_quantile(power, df)) * std_error


def _t_quantile(p: float, df: int) -> float:
    """Quantil t por bisseção sobre a função de sobrevivência já existente."""
    low, high = 0.0, 12.0
    for _ in range(120):
        middle = (low + high) / 2.0
        # t_sf devolve P(T > t) para teste bilateral normalizado; ajustamos
        survival = robust.t_sf(middle, df) / 2.0 if middle > 0 else 0.5
        if survival > 1.0 - p:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def monte_carlo(design, simulations: int, seed: int, effect: float) -> dict[str, Any]:
    """Simula y sob H0 e sob a alternativa, refitando o mesmo estimador.

    O ruído é gerado **por cluster** (UF × ano), preservando a correlação
    intra-agrupamento que o erro robusto precisa absorver.
    """
    labels = design["cluster_labels"]
    unique = list(dict.fromkeys(labels))
    position_of = {label: index for index, label in enumerate(unique)}
    positions = np.array([position_of[label] for label in labels])
    n_clusters = len(unique)

    def rejection(rate_signal: float, replicates: int) -> float:
        total = 0.0
        local = np.random.default_rng(seed + 1)
        for _ in range(replicates):
            # o componente de cluster é sorteado de novo em cada réplica: se
            # fosse fixo, a correlação amostral dele com x_within viraria um
            # viés constante e nunca se anularia entre réplicas
            cluster_draw = local.normal(0.0, design["cluster_sd"], size=n_clusters)[positions]
            idiosyncratic = local.normal(0.0, design["idiosyncratic_sd"], size=design["n"])
            y = cluster_draw + idiosyncratic + rate_signal * design["x_within"]
            y = y - y.mean()
            beta = float(np.linalg.lstsq(design["x_design"], y, rcond=None)[0][0])
            residuals = y - design["x_within"] * beta
            vcv, _info = robust.cluster_vcov(
                design["x_design"], residuals, labels, correction=robust.CR1
            )
            se = float(np.sqrt(max(vcv[0, 0], 0.0)))
            if se <= 0:
                continue
            p_value = robust.t_sf(beta / se, design["df"])
            if p_value is not None and p_value < ALPHA:
                total += 1.0
        return total / max(replicates, 1)

    return {
        "type_i_error": rejection(0.0, simulations),
        "power_at_mde": rejection(effect, simulations),
        "simulations": simulations,
        "cluster_sd": design["cluster_sd"],
        "idiosyncratic_sd": design["idiosyncratic_sd"],
    }


def cluster_variance_components(residuals: np.ndarray, labels: Sequence[str]):
    """Decomposição entre e dentro de UF × ano."""
    groups: dict[str, list[float]] = defaultdict(list)
    for value, label in zip(residuals, labels):
        groups[label].append(float(value))
    sizes = np.array([len(values) for values in groups.values()], dtype="float64")
    means = np.array([float(np.mean(values)) for values in groups.values()], dtype="float64")
    grand = float(np.mean(residuals))
    between = float(np.sum(sizes * (means - grand) ** 2) / max(len(residuals) - len(sizes), 1))
    within = float(
        np.sum([np.sum((np.array(values) - np.mean(values)) ** 2) for values in groups.values()])
        / max(len(residuals) - len(sizes), 1)
    )
    m = float(np.mean(sizes)) if len(sizes) else 0.0
    icc = between / (between + within) if (between + within) > 0 else 0.0
    return {"between_var": between, "within_var": within, "mean_cluster_size": m, "icc": icc}


def design_scenarios(mean_size: float, n_clusters: int, icc: float) -> dict[str, Any]:
    """MDE sob cenários de desenho, com o efeito de desenho intragrupo.

    ``Var(beta) proporcional a sigma2/(K*m) * [1 + (m-1)*rho]``: acrescentar
    municípios dentro da mesma UF x ano ajuda menos quanto maior for rho;
    acrescentar **clusters** é o que reduz o erro de forma sustentada.
    """
    base = (1.0 + (mean_size - 1.0) * icc) / (n_clusters * mean_size)

    def relative(k: int, m: float) -> float:
        factor = (1.0 + (m - 1.0) * icc) / (k * m)
        return math.sqrt(factor / base) if base > 0 else float("nan")

    return {
        "icc": icc,
        "mean_cluster_size": mean_size,
        "n_clusters": n_clusters,
        "scenarios": {
            "municipios_x2": {"n_clusters": n_clusters, "mean_size": mean_size * 2, "se_factor": relative(n_clusters, mean_size * 2)},
            "municipios_x5": {"n_clusters": n_clusters, "mean_size": mean_size * 5, "se_factor": relative(n_clusters, mean_size * 5)},
            "anos_9_para_15": {"n_clusters": int(n_clusters * 15 / 9), "mean_size": mean_size, "se_factor": relative(int(n_clusters * 15 / 9), mean_size)},
            "ufs_7_para_10": {"n_clusters": int(n_clusters * 10 / 7), "mean_size": mean_size, "se_factor": relative(int(n_clusters * 10 / 7), mean_size)},
            "municipios_x2_e_anos_15": {"n_clusters": int(n_clusters * 15 / 9), "mean_size": mean_size * 2, "se_factor": relative(int(n_clusters * 15 / 9), mean_size * 2)},
            "se_atual": {"n_clusters": n_clusters, "mean_size": mean_size, "se_factor": 1.0},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20261114)
    args = parser.parse_args()

    started = time.time()
    panel = load_panel()
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "alpha": ALPHA,
        "estimator": "within(municipio, ano) + CR1 agrupado em UF x ano",
        "design_inventory": {},
        "mde": {},
        "monte_carlo": {},
        "design_scenarios": {},
    }

    for crop in CROPS:
        rows = panel[crop]
        usable, municipalities, years, state_years, y, x = design_arrays(rows, "deficit")
        clusters = len(set(state_years))
        report["design_inventory"][crop] = {
            "rows": len(rows),
            "rows_usable": len(usable),
            "municipalities": len(set(municipalities)),
            "years": len(set(years)),
            "uf_year_clusters": clusters,
            "mean_cluster_size": round(len(usable) / clusters, 2) if clusters else None,
            "naive_rows_if_assumed_independent": len(usable),
        }
        print(crop, report["design_inventory"][crop])

    for crop in CROPS:
        for name, column in EXPOSURES.items():
            usable, municipalities, years, state_years, y, x = design_arrays(panel[crop], name)
            if len(usable) < 400:
                continue
            fit = fit_within(y, x, municipalities, years, state_years)
            if fit is None or fit["se"] <= 0:
                continue
            entry = {
                "n": fit["n"],
                "n_clusters": fit["n_clusters"],
                "df": fit["df"],
                "beta": fit["beta"],
                "se": fit["se"],
                "mde_80": mde(fit["se"], fit["df"], 0.80),
                "mde_90": mde(fit["se"], fit["df"], 0.90),
                "ci95_half_width": robust.t_critical(ALPHA, fit["df"]) * fit["se"],
                "unit": "kg/ha por unidade da exposição",
            }
            report["mde"][f"{crop}|{name}"] = entry
            if name == "deficit":
                components = cluster_variance_components(fit["residuals"], state_years)
                report["design_scenarios"][crop] = design_scenarios(
                    components["mean_cluster_size"], fit["n_clusters"], components["icc"]
                )
                report["design_scenarios"][crop]["variance_components"] = components
                design = {
                    "x_design": fit["x_within"].reshape(-1, 1),
                    "x_within": fit["x_within"],
                    "y_within": fit["y_within"],
                    "cluster_labels": state_years,
                    "df": fit["df"],
                    "n": fit["n"],
                    "cluster_sd": math.sqrt(max(components["between_var"], 0.0)),
                    "idiosyncratic_sd": math.sqrt(max(components["within_var"], 0.0)),
                }
                report["monte_carlo"][crop] = monte_carlo(
                    design, args.simulations, args.seed, entry["mde_80"]
                )
                print(crop, "MDE80 %.1f kg/ha" % entry["mde_80"], "MC", report["monte_carlo"][crop])

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print("elapsed_s", round(time.time() - started, 1))
    print("manifesto:", OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
