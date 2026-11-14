"""Calibração do Wild Cluster Bootstrap (Cameron, Gelbach & Miller, 2008).

Objetivo científico: verificar se o p-valor produzido pelo bootstrap wild de
cluster tem **tamanho nominal** correto sob a hipótese nula, para
diferentes números de grupos, graus de desbalanceamento e correlações
intra-cluster, e qual é o seu **poder** sob efeito conhecido.

Dois processos geradores de dados (DGP) são usados:

**DGP A — ``agrupado``** (erro agrupado, modelo corretamente especificado)
    G grupos com ``m`` observações cada; erro = choque comum do grupo +
    erro idiossincrático. Estimação por OLS com intercepto e erro-padrão
    agrupado por grupo.

**DGP B — ``painel_fe``** (espelha o painel real do projeto)
    Painel município × ano com **efeitos fixos nas duas direções**
    (estimador *within*) e erro **AR(1) dentro do município**. É a
    situação clássica de Cameron & Miller (2015): poucos grupos e erro
    correlacionado no tempo, em que o bootstrap wild de cluster é o
    procedimento de referência.

Em cada caso são comparados três testes:

1. **t com erro-padrão agrupado** (assintótico, ``df = G − 1``);
2. **bootstrap wild com pesos por cluster** (CGM, 2008 — padrão);
3. **bootstrap wild com pesos por observação** (variante herdada, D80).

Diagnósticos registrados por caso:

* taxa de rejeição em **vários níveis nominais** (1%, 5%, 10%) — é o
  diagnóstico válido de tamanho, porque o p-valor do bootstrap é
  **discreto** (passos de 1/(B+1)) e não pode ser testado contra uma
  normal uniforme contínua;
* **incerteza de Monte Carlo** (erro-padrão binomial e IC 95%);
* **largura** da distribuição bootstrap (desvio-padrão das estatísticas t),
  que evidencia a diferença entre os dois esquemas de pesos;
* **quantis** do p-valor sob H0.

Resultados são gravados incrementalmente e a execução é **retomável**.

Uso:
    python tools/calibrate_wild_bootstrap.py            # retoma e completa
    python tools/calibrate_wild_bootstrap.py --force    # recalcula tudo
    python tools/calibrate_wild_bootstrap.py --quick    # grade reduzida
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import robust, spatial_inference  # noqa: E402

SEED = 20261114
OUT = os.path.join(
    ROOT, "geospatial", "data", "manifests", "v27_wild_bootstrap_calibration.json"
)
N_BOOT = 999
ALPHA = 0.05
ALPHAS = (0.01, 0.05, 0.10)


# ---------------------------------------------------------------- utilidades
def ks_uniform(p_values: np.ndarray) -> tuple[float, float]:
    """Estatística e p-valor de Kolmogorov-Smirnov contra U(0,1).

    Implementação em NumPy puro (evita dependência do SciPy); o p-valor usa
    a aproximação assintótica de Kolmogorov. **Diagnóstico secundário**:
    o p-valor do bootstrap é discreto, de modo que este teste rejeita
    uniformidade mesmo quando o tamanho do teste é adequado.
    """
    if p_values.size == 0:
        return (float("nan"), float("nan"))
    x = np.sort(np.asarray(p_values, dtype="float64"))
    n = x.size
    f = np.arange(1, n + 1) / n
    d_plus = float(np.max(f - x))
    d_minus = float(np.max(x - np.concatenate(([0.0], f[:-1]))))
    d = max(d_plus, d_minus)
    en = math.sqrt(n)
    lam = (en + 0.12 + 0.11 / en) * d
    total = 0.0
    for k in range(1, 101):
        total += (-1.0) ** (k - 1) * math.exp(-2.0 * k * k * lam * lam)
    return d, max(0.0, min(1.0, 2.0 * total))


def _mc(rate: float | None, n: int) -> tuple[float | None, list | None]:
    if rate is None or not n:
        return (None, None)
    se = math.sqrt(max(rate * (1.0 - rate), 0.0) / n)
    return (se, [max(0.0, rate - 1.96 * se), min(1.0, rate + 1.96 * se)])


def _summarize_tests(p_values: list[float], prefix: str, out: dict) -> None:
    """Registra taxas de rejeição em vários níveis e a largura bootstrap."""
    n = len(p_values)
    if not n:
        return
    arr = np.asarray(p_values, dtype="float64")
    for alpha in ALPHAS:
        rate = float(np.mean(arr <= alpha))
        se, ci = _mc(rate, n)
        tag = f"{prefix}_a{int(alpha * 100):02d}"
        out[f"rejection_rate_{tag}"] = rate
        out[f"mc_se_{tag}"] = se
        out[f"mc_ci_{tag}"] = ci
    ks_d, ks_p = ks_uniform(arr)
    out[f"ks_stat_{prefix}"] = ks_d
    out[f"ks_p_{prefix}"] = ks_p
    out[f"median_p_{prefix}"] = float(np.median(arr))
    out[f"p_quantiles_{prefix}"] = {
        str(q): float(np.quantile(arr, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)
    }


# ---------------------------------------------------------------------- DGP A
def simulate_agrupado(
    rng: np.random.Generator,
    n_clusters: int,
    obs_per_cluster: int = 8,
    imbalance: float = 0.0,
    effect: float = 0.0,
    n_covariates: int = 3,
    cluster_effect_sd: float = 1.0,
):
    """Painel com erro agrupado por cluster (modelo corretamente especificado)."""
    sizes = []
    for _ in range(n_clusters):
        if imbalance <= 0:
            sizes.append(obs_per_cluster)
        else:
            factor = int(rng.integers(1, 5))
            sizes.append(
                max(
                    1,
                    int(
                        round(
                            obs_per_cluster
                            * (1 - imbalance + imbalance * factor / 2.5)
                        )
                    ),
                )
            )
    n = int(sum(sizes))
    groups = np.concatenate([np.repeat(g, size) for g, size in enumerate(sizes)])
    design = np.ones((n, n_covariates))
    design[:, 1] = rng.normal(size=n)
    design[:, 2] = np.arange(n) / max(1, n - 1)
    for g in range(n_clusters):
        design[groups == g, 0] = 0.0
    beta = np.zeros(n_covariates)
    beta[1] = effect
    shock = rng.normal(size=n_clusters) * cluster_effect_sd
    errors = shock[groups] + rng.normal(size=n)
    return design, design @ beta + errors, groups


# ---------------------------------------------------------------------- DGP B
def simulate_painel_fe(
    rng: np.random.Generator,
    n_clusters: int,
    n_years: int = 8,
    rho: float = 0.5,
    effect: float = 0.0,
    x_sd: float = 1.0,
):
    """Painel município x ano com efeitos fixos e erro AR(1) intracluster.

    Reproduz a estrutura do painel real do SADEN: o regressor climático
    tem componente de município e de ano (absorvidos pelo estimador
    *within*) mais variação própria, e o erro é serialmente correlacionado
    dentro do município.
    """
    n = n_clusters * n_years
    mun = np.repeat(np.arange(n_clusters), n_years)
    year = np.tile(np.arange(n_years), n_clusters)
    mu = rng.normal(size=n_clusters)
    tau = rng.normal(size=n_years)
    x = mu[mun] + tau[year] + rng.normal(size=n) * x_sd
    u = np.empty(n)
    innovation = rng.normal(size=n)
    scale = math.sqrt(max(1.0 - rho**2, 1e-12))
    for c in range(n_clusters):
        idx = np.where(mun == c)[0]
        previous = 0.0
        for i in idx:
            previous = rho * previous + innovation[i]
            u[i] = previous
    u = u * scale
    y = effect * x + 0.5 * mu[mun] + 0.5 * tau[year] + u
    return x, y, mun, year


# ----------------------------------------------------------------- execução
def run_case_agrupado(
    n_clusters: int,
    n_sims: int,
    imbalance: float,
    effect: float,
    seed: int,
) -> dict:
    rng = np.random.default_rng(seed)
    p_t: list[float] = []
    p_wild = {"cluster": [], "observation": []}
    sd_wild = {"cluster": [], "observation": []}
    usable = 0
    for sim in range(n_sims):
        design, y, groups = simulate_agrupado(
            rng, n_clusters, imbalance=imbalance, effect=effect
        )
        groups_list = groups.tolist()
        fit = robust.cluster_robust_fit(design, y, groups_list, coef_index=1)
        if fit.get("status") != "ok" or fit.get("p_value") is None:
            continue
        usable += 1
        p_t.append(float(fit["p_value"]))
        for scheme in ("cluster", "observation"):
            res = robust.wild_cluster_bootstrap_fast(
                design,
                y,
                groups_list,
                coef_index=1,
                n_boot=N_BOOT,
                seed=seed + 7919 + 104729 * sim,
                weight_scheme=scheme,
            )
            if res.get("status") != "ok":
                continue
            p_wild[scheme].append(float(res["p_value"]))
            if res.get("t_boot_sd") is not None:
                sd_wild[scheme].append(float(res["t_boot_sd"]))
    out: dict = {"n_usable": usable}
    _summarize_tests(p_t, "t_clustered", out)
    for scheme in ("cluster", "observation"):
        _summarize_tests(p_wild[scheme], f"wild_{scheme}", out)
        out[f"mean_t_boot_sd_{scheme}"] = (
            float(np.mean(sd_wild[scheme])) if sd_wild[scheme] else None
        )
    return out


def run_case_painel_fe(
    n_clusters: int,
    n_years: int,
    rho: float,
    n_sims: int,
    effect: float,
    seed: int,
) -> dict:
    rng = np.random.default_rng(seed)
    p_t: list[float] = []
    p_wild = {"cluster": [], "observation": []}
    sd_wild = {"cluster": [], "observation": []}
    usable = 0
    for sim in range(n_sims):
        x, y, mun, year = simulate_painel_fe(
            rng, n_clusters, n_years=n_years, rho=rho, effect=effect
        )
        xw = spatial_inference.within_transform(x, mun, year)
        yw = spatial_inference.within_transform(y, mun, year)
        denominator = float(np.dot(xw, xw))
        if denominator <= 0:
            continue
        prepared = {"status": "ok", "x_within": xw, "y_within": yw}
        groups_list = [str(g) for g in mun]
        coefficient = float(np.dot(xw, yw) / denominator)
        se, n_groups, _ = spatial_inference._clustered_se(
            xw, yw, groups_list, correction=robust.CR1
        )
        if not se or math.isnan(se):
            continue
        usable += 1
        t_stat = coefficient / se
        p_t.append(float(robust.t_sf(t_stat, max(n_groups - 1, 1))))
        for scheme in ("cluster", "observation"):
            res = spatial_inference.wild_cluster_bootstrap_within_fast(
                prepared,
                groups_list,
                n_boot=N_BOOT,
                seed=seed + 7919 + 104729 * sim,
                weight_scheme=scheme,
            )
            if res.get("status") != "ok":
                continue
            p_wild[scheme].append(float(res["p_value"]))
            if res.get("t_boot_sd") is not None:
                sd_wild[scheme].append(float(res["t_boot_sd"]))
    out: dict = {"n_usable": usable}
    _summarize_tests(p_t, "t_clustered", out)
    for scheme in ("cluster", "observation"):
        _summarize_tests(p_wild[scheme], f"wild_{scheme}", out)
        out[f"mean_t_boot_sd_{scheme}"] = (
            float(np.mean(sd_wild[scheme])) if sd_wild[scheme] else None
        )
    return out


# ---------------------------------------------------------------------- grade
def build_grid(quick: bool = False) -> list[dict]:
    cases: list[dict] = []
    seeds = (0, 1, 2)
    if quick:
        agr = [(5, 300, 0.0), (25, 300, 0.0), (50, 300, 0.0), (50, 300, 0.8)]
        fe = [(10, 8, 0.5, 200), (46, 8, 0.5, 200)]
    else:
        agr = [
            (5, 2000, 0.0),
            (10, 2000, 0.0),
            (25, 2000, 0.0),
            (50, 2000, 0.0),
            (100, 1500, 0.0),
            (200, 1000, 0.0),
            (25, 2000, 0.8),
            (50, 2000, 0.8),
        ]
        fe = [
            (10, 8, 0.0, 800),
            (10, 8, 0.5, 800),
            (25, 8, 0.5, 800),
            (46, 8, 0.5, 1200),
            (46, 8, 0.8, 1200),
            (100, 8, 0.5, 800),
        ]
    for n_clusters, n_sims, imbalance in agr:
        for effect, tag in ((0.0, "H0"), (1.0, "efeito")):
            sims = n_sims if effect == 0.0 else max(200, n_sims // 2)
            for s in seeds:
                cases.append(
                    {
                        "dgp": "agrupado",
                        "label": (
                            f"agrupado | {tag} | G={n_clusters} | "
                            f"desbalanceamento={imbalance} | semente {s + 1}"
                        ),
                        "n_clusters": n_clusters,
                        "n_simulations": sims,
                        "imbalance": imbalance,
                        "effect": effect,
                        "seed": SEED + 1000 * len(cases),
                    }
                )
    for n_clusters, n_years, rho, n_sims in fe:
        for effect, tag in ((0.0, "H0"), (1.0, "efeito")):
            sims = n_sims if effect == 0.0 else max(150, n_sims // 2)
            for s in seeds:
                cases.append(
                    {
                        "dgp": "painel_fe",
                        "label": (
                            f"painel_fe | {tag} | G={n_clusters} | T={n_years} | "
                            f"rho={rho} | semente {s + 1}"
                        ),
                        "n_clusters": n_clusters,
                        "n_years": n_years,
                        "rho": rho,
                        "n_simulations": sims,
                        "effect": effect,
                        "seed": SEED + 1000 * len(cases),
                    }
                )
    return cases


def validate_equivalence() -> dict:
    """Confere que as versões vetorizadas reproduzem as versões em laço."""
    rng = np.random.default_rng(2026)
    # (1) OLS agrupado
    n_clusters, obs = 30, 7
    groups = np.repeat(np.arange(n_clusters), obs).tolist()
    n = len(groups)
    x = rng.normal(size=n)
    z = rng.normal(size=n_clusters)[np.array(groups)]
    design = np.column_stack([np.ones(n), x])
    y = design @ np.array([0.0, 2.0]) + z + rng.normal(size=n)
    weights = robust._rademacher_matrix(groups, 199, 4242, robust.WEIGHT_CLUSTER)
    loop = robust.wild_cluster_bootstrap(
        design, y, groups, coef_index=1, n_boot=199, weights=weights
    )
    fast = robust.wild_cluster_bootstrap_fast(
        design, y, groups, coef_index=1, n_boot=199, weights=weights
    )
    out = {
        "ols_loop_p": loop.get("p_value"),
        "ols_fast_p": fast.get("p_value"),
        "ols_p_identical": loop.get("p_value") == fast.get("p_value"),
        "ols_loop_t_sd": loop.get("t_boot_sd"),
        "ols_fast_t_sd": fast.get("t_boot_sd"),
    }
    # (2) estimador within
    G, T = 46, 8
    mun = np.repeat(np.arange(G), T)
    year = np.tile(np.arange(T), G)
    mu = rng.normal(size=G)
    tau = rng.normal(size=T)
    xx = mu[mun] + tau[year] + rng.normal(size=len(mun))
    u = np.zeros(len(mun))
    innovation = rng.normal(size=len(mun))
    for c in range(G):
        idx = np.where(mun == c)[0]
        prev = 0.0
        for i in idx:
            prev = 0.5 * prev + innovation[i]
            u[i] = prev
    yy = 2.0 * xx + u
    xw = spatial_inference.within_transform(xx, mun, year)
    yw = spatial_inference.within_transform(yy, mun, year)
    prepared = {"status": "ok", "x_within": xw, "y_within": yw}
    gl = [str(g) for g in mun]
    for scheme in ("cluster", "observation"):
        a = spatial_inference.wild_cluster_bootstrap_within(
            prepared, gl, n_boot=199, seed=77, weight_scheme=scheme
        )
        b = spatial_inference.wild_cluster_bootstrap_within_fast(
            prepared, gl, n_boot=199, seed=77, weight_scheme=scheme
        )
        out[f"within_{scheme}_loop_p"] = a.get("p_value")
        out[f"within_{scheme}_fast_p"] = b.get("p_value")
        out[f"within_{scheme}_p_identical"] = a.get("p_value") == b.get("p_value")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--only", default="")
    args = parser.parse_args()

    t0 = time.time()
    out: dict = {}
    if os.path.exists(OUT) and not args.force:
        try:
            with open(OUT, encoding="utf-8") as handle:
                out = json.load(handle)
        except (OSError, json.JSONDecodeError):
            out = {}
    out.setdefault("generated_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    out["seed"] = SEED
    out["method"] = (
        "Calibracao Monte Carlo do bootstrap wild de cluster (Cameron, "
        "Gelbach & Miller, 2008). DGP 'agrupado': erro agrupado por grupo. "
        "DGP 'painel_fe': painel municipio x ano com efeitos fixos nas duas "
        "direcoes e erro AR(1) intracluster, espelhando o painel real. "
        "Pesos de Rademacher por grupo (padrao CGM) e por observacao (variante "
        "herdada, D80). Diagnostico de tamanho por taxa de rejeicao em varios "
        "niveis nominais (o p-valor do bootstrap e discreto). Sem SciPy."
    )
    out["reference"] = {
        "nominal_levels": list(ALPHAS),
        "n_bootstrap": N_BOOT,
        "note": (
            "Sob H0 a taxa de rejeicao deve ser compativel com o nivel nominal "
            "dentro do intervalo de incerteza de Monte Carlo. O KS contra "
            "U(0,1) e apenas indicativo: o p-valor do bootstrap e discreto."
        ),
    }
    out["validation_vectorized_equals_loop"] = validate_equivalence()
    out.setdefault("cases", [])
    done = {c.get("label"): c for c in out["cases"] if c.get("label")}

    grid = build_grid(quick=args.quick)
    for spec in grid:
        label = spec["label"]
        if args.only and args.only.lower() not in label.lower():
            continue
        if label in done and not args.force:
            print(f"  [retomada] {label}", flush=True)
            continue
        t_case = time.time()
        if spec["dgp"] == "agrupado":
            result = run_case_agrupado(
                n_clusters=spec["n_clusters"],
                n_sims=spec["n_simulations"],
                imbalance=spec["imbalance"],
                effect=spec["effect"],
                seed=spec["seed"],
            )
        else:
            result = run_case_painel_fe(
                n_clusters=spec["n_clusters"],
                n_years=spec["n_years"],
                rho=spec["rho"],
                n_sims=spec["n_simulations"],
                effect=spec["effect"],
                seed=spec["seed"],
            )
        case = {k: v for k, v in spec.items() if k != "seed"}
        case.update(result)
        case["elapsed_s"] = round(time.time() - t_case, 1)
        print(
            f"  {label}: t-agrupado={result.get('rejection_rate_t_clustered_a05')} | "
            f"wild_cluster={result.get('rejection_rate_wild_cluster_a05')} | "
            f"wild_observacao={result.get('rejection_rate_wild_observation_a05')} | "
            f"sd_cluster={result.get('mean_t_boot_sd_cluster')} | "
            f"n={result['n_usable']} | {case['elapsed_s']}s",
            flush=True,
        )
        out["cases"] = [c for c in out["cases"] if c.get("label") != label] + [case]
        out["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(out, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    out["elapsed_s_total"] = round(time.time() - t0, 1)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(out, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"manifesto: {OUT} ({out['elapsed_s_total']} s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
