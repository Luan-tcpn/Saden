"""CLI da V2.7 — robustez estatística, inferência espacial e validação.

Comandos
--------
``dependence``
    Mede a dependência espacial real da base meteorológica (correlograma
    empírico sobre anomalias diárias e anuais) e calibra a escala espacial
    usada na inferência e na partilha dos experimentos.
``diagnose``
    Estrutura dos grupos de agrupamento (município, célula da grade, bloco
    espacial, UF) e verificação de partilha de informação.
``infer``
    Efeitos fixos de município e ano com erro-padrão agrupado em vários
    esquemas, estimador espacial de Conley, bootstrap wild de cluster e
    correção de Holm.
``spatial``
    Protocolos de validação territorial: holdout por município (linha de
    base da V2.6), grouped por célula, grouped por bloco espacial e
    leave-one-UF-out, com verificação de vazamento.
``all``
    Executa todos, em sequência, persistindo cada etapa.

Todos os artefatos são escritos em ``data/manifests/`` e os resultados
intermediários são **persistidos incrementalmente**: uma interrupção não
exige reexecutar as etapas anteriores.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DATA = os.path.join(HERE, "data")
PROCESSED = os.path.join(DATA, "processed")
MANIFESTS = os.path.join(DATA, "manifests")

from agroclimate import analysis, robust, spatial, spatial_inference  # noqa: E402

SEED = 20261113

# Variáveis do painel usadas na inferência (mesmas da V2.6).
ANALYSIS_VARIABLES = (
    "precip_acumulada_mm",
    "temp_media_c",
    "degree_days_total",
    "extreme_heat_days",
    "et0_total_mm",
    "deficiency_total_mm",
    "excess_total_mm",
)

# Modelos pré-declarados da V2.6 (D70).
MODELS: dict[str, tuple[str, ...]] = {
    "B_meteorologicos": ("precip_acumulada_mm", "temp_media_c"),
    "C_thermal": ("degree_days_total", "extreme_heat_days"),
    "D_hidricos": ("et0_total_mm", "deficiency_total_mm", "excess_total_mm"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_csv(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_csv(rows, path: str) -> str:
    rows = list(rows)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not rows:
        return path
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _write_json(payload: Any, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    return path


# --------------------------------------------------------------------------
# Carregamento do painel
# --------------------------------------------------------------------------
def load_panel() -> list[dict[str, Any]]:
    """Painel agroclimático da V2.6 (versão versionada)."""
    return _read_csv(
        os.path.join(PROCESSED, "agroclimatic_productivity_panel.csv")
    )


def load_municipalities() -> list[dict[str, Any]]:
    return _read_csv(os.path.join(PROCESSED, "panel_municipalities.csv"))


def prepare(
    rows: list[dict[str, Any]], climate_source: str | None = "NASA-POWER"
) -> list[dict[str, Any]]:
    """Prepara as linhas analíticas e acrescenta as unidades de agrupamento."""
    subset = [
        r
        for r in rows
        if climate_source is None or str(r.get("climate_source")) == climate_source
    ]
    prepared = analysis.prepare_rows(subset)
    municipalities = load_municipalities()
    cells = spatial.municipality_cells(municipalities)
    block_km = float(os.environ.get("SADEN_V27_BLOCK_KM", "250"))
    blocks = spatial.spatial_blocks(municipalities, block_km)
    for row in prepared:
        code = str(row["ibge_code"])
        cell = cells.get(code)
        row["grid_cell_id"] = cell["grid_cell_id"] if cell else None
        row["spatial_block"] = blocks.get(code)
        row["state"] = row.get("state")
        row["cluster_id"] = row["grid_cell_id"]
    return prepared


def build_schemes(
    rows: list[dict[str, Any]], block_km: float
) -> dict[str, list[str]]:
    """Vetores de agrupamento por esquema, alinhados à ordem das linhas."""
    municipalities = load_municipalities()
    cells = spatial.municipality_cells(municipalities)
    blocks = spatial.spatial_blocks(municipalities, block_km)
    codes = [str(r["ibge_code"]) for r in rows]
    schemes: dict[str, list[str]] = {
        "municipio": codes,
        "celula_grade": [
            (cells.get(code, {}) or {}).get("grid_cell_id") or f"__sem_celula_{code}"
            for code in codes
        ],
        f"bloco_espacial_{int(block_km)}km": [
            blocks.get(code) or f"__sem_bloco_{code}" for code in codes
        ],
        "uf": [str(r.get("state") or "__sem_uf") for r in rows],
    }
    return schemes


# --------------------------------------------------------------------------
# Comando: dependência espacial
# --------------------------------------------------------------------------
def cmd_dependence(args: argparse.Namespace) -> dict[str, Any]:
    """Correlograma empírico da base meteorológica (a base do painel)."""
    from agroclimate import gridded  # noqa: F401  (mantém o import explícito)

    climate_path = os.path.join(PROCESSED, "climate_daily.csv")
    if not os.path.exists(climate_path):
        return {
            "ok": False,
            "error": (
                "climate_daily.csv ausente; rode 'run_agroclimate.py climate' "
                "para reconstruir a base"
            ),
        }
    municipalities = load_municipalities()
    cells = spatial.municipality_cells(municipalities)
    panel_codes = sorted(
        {
            str(r["ibge_code"])
            for r in load_panel()
            if r["status"] == "paired_usable"
            and r["climate_source"] == "NASA-POWER"
        }
    )
    index = {code: i for i, code in enumerate(panel_codes)}
    n = len(panel_codes)
    dates: list[str] = []
    day_index: dict[str, int] = {}
    temp = np.full((n, 4000), np.nan)
    precip = np.full((n, 4000), np.nan)
    with open(climate_path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            code = str(row.get("ibge_code") or "")
            if code not in index or str(row.get("source")) != "NASA-POWER":
                continue
            day = str(row.get("date"))
            if day not in day_index:
                day_index[day] = len(dates)
                dates.append(day)
            j = day_index[day]
            value = row.get("temp_media_c")
            if value not in (None, ""):
                temp[index[code], j] = float(value)
            value = row.get("precip_mm")
            if value not in (None, ""):
                precip[index[code], j] = float(value)
    n_days = len(dates)
    temp = temp[:, :n_days]
    precip = precip[:, :n_days]
    doy = np.array([int(d[5:7]) * 31 + int(d[8:10]) for d in dates])

    def climatology(matrix: np.ndarray) -> np.ndarray:
        out = np.empty_like(matrix)
        for value in np.unique(doy):
            mask = doy == value
            out[:, mask] = matrix[:, mask].mean(axis=1, keepdims=True)
        return out

    def corr_rows(matrix: np.ndarray) -> np.ndarray:
        filled = np.where(np.isnan(matrix), np.nanmean(matrix, axis=1, keepdims=True), matrix)
        filled = filled - filled.mean(axis=1, keepdims=True)
        norm = np.linalg.norm(filled, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        unit = filled / norm
        return unit @ unit.T

    anom_temp = temp - climatology(temp)
    anom_precip = precip - climatology(precip)
    years = sorted({int(d[:4]) for d in dates})
    ann_temp = np.zeros((n, len(years)))
    ann_precip = np.zeros((n, len(years)))
    for j, year in enumerate(years):
        mask = np.array([int(d[:4]) == year for d in dates])
        ann_temp[:, j] = temp[:, mask].mean(axis=1)
        ann_precip[:, j] = precip[:, mask].sum(axis=1)
    ann_temp -= ann_temp.mean(axis=1, keepdims=True)
    ann_precip -= ann_precip.mean(axis=1, keepdims=True)

    lat = np.array([cells[c]["centroid_lat"] for c in panel_codes])
    lon = np.array([cells[c]["centroid_lon"] for c in panel_codes])
    distances: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            distances.append(spatial.haversine_km(lat[i], lon[i], lat[j], lon[j]))

    fields = {
        "anomalia_diaria_temp": corr_rows(anom_temp),
        "anomalia_diaria_precip": corr_rows(anom_precip),
        "anomalia_anual_temp": corr_rows(ann_temp),
        "anomalia_anual_precip": corr_rows(ann_precip),
    }
    iu = np.triu_indices(n, k=1)
    out: dict[str, Any] = {
        "generated_at": _now(),
        "n_municipalities": n,
        "n_days": n_days,
        "period": [dates[0], dates[-1]],
        "source": "NASA-POWER (MERRA-2) via climate_daily.csv",
        "note": (
            "A correlacao de series CRUAS e dominada pelo ciclo sazonal "
            "compartilhado; o dependencia espacial relevante e medida sobre "
            "ANOMALIAS (retirado o climatolo diario de cada municipio)."
        ),
        "correlograms": {},
        "cutoffs": {},
    }
    rows_csv: list[dict[str, Any]] = []
    for name, matrix in fields.items():
        values = matrix[iu]
        bands = spatial.correlogram(distances, values, 25.0, 600.0)
        out["correlograms"][name] = bands
        cutoff = spatial.dependence_threshold_distance(
            distances, values, threshold=0.10, max_distance_km=600.0
        )
        out["cutoffs"][name] = {
            "distance_below_0.10_km": cutoff,
            "mean_correlation_0_100km": next(
                (
                    b["mean_correlation"]
                    for b in bands
                    if b["distance_min_km"] == 0
                ),
                None,
            ),
            "mean_correlation_0_400km": next(
                (
                    b["mean_correlation"]
                    for b in bands
                    if b["distance_min_km"] == 400
                ),
                None,
            ),
        }
        for band in bands:
            row = {"campo": name}
            row.update(band)
            rows_csv.append(row)
    _write_csv(rows_csv, os.path.join(MANIFESTS, "v27_spatial_dependence.csv"))
    path = _write_json(out, os.path.join(MANIFESTS, "v27_spatial_dependence.json"))
    return {"ok": True, "manifest": path, "n_municipalities": n}


# --------------------------------------------------------------------------
# Comando: diagnóstico dos grupos
# --------------------------------------------------------------------------
def cmd_diagnose(args: argparse.Namespace) -> dict[str, Any]:
    """Estrutura dos grupos de agrupamento e partilha de informação."""
    municipalities = load_municipalities()
    cells = spatial.municipality_cells(municipalities)
    rows = prepare(load_panel())
    out: dict[str, Any] = {
        "generated_at": _now(),
        "block_km": args.block_km,
        "crops": {},
        "findings": [],
    }
    for crop in ("soja", "milho", "milho_2"):
        subset = [r for r in rows if r["crop"] == crop]
        if not subset:
            continue
        schemes = build_schemes(subset, args.block_km)
        entry: dict[str, Any] = {
            "n_observations": len(subset),
            "n_municipalities": len({r["ibge_code"] for r in subset}),
            "schemes": {},
        }
        for name, groups in schemes.items():
            summary = spatial.cluster_summary(
                [{"cluster_id": g} for g in groups]
            )
            entry["schemes"][name] = summary
        diagnostics = spatial.cluster_diagnostics(
            subset,
            cells,
            cluster_key="grid_cell_id",
        )
        entry["diagnostics_celula_grade"] = diagnostics
        out["crops"][crop] = entry
    # partilha empirica de valores climaticos (fora da janela?)
    values = [r for r in rows if r["crop"] == "soja"][:4000]
    groups = spatial.shared_value_groups(values)
    out["shared_value_groups_sample"] = {
        "n_groups": len(groups),
        "n_rows_sampled": len(values),
        "interpretation": (
            "Grupos de linhas com valores climaticos EXATAMENTE iguais. A "
            "contagem pequena mostra que o NASA POWER INTERPOLA a grade: "
            "municipios da mesma celula nao compartilham valores identicos, "
            "embora as series sejam fortemente correlacionadas."
        ),
    }
    path = _write_json(out, os.path.join(MANIFESTS, "v27_cluster_diagnostics.json"))
    return {"ok": True, "manifest": path}


# --------------------------------------------------------------------------
# Comando: inferencia robusta
# --------------------------------------------------------------------------
def cmd_infer(args: argparse.Namespace) -> dict[str, Any]:
    """Efeitos fixos com vários esquemas de agrupamento, Conley e WCB."""
    municipalities = load_municipalities()
    cells = spatial.municipality_cells(municipalities)
    coords = {
        code: (cell["centroid_lat"], cell["centroid_lon"])
        for code, cell in cells.items()
    }
    rows = prepare(load_panel())
    out: dict[str, Any] = {
        "generated_at": _now(),
        "seed": SEED,
        "climate_source": "NASA-POWER (reanalysis)",
        "block_km": args.block_km,
        "conley_cutoffs_km": list(args.conley_cutoffs),
        "wild_cluster_bootstrap_iterations": args.bootstrap,
        "family": (
            "efeitos fixos de municipio e ano: uma hipotese por (cultura, "
            "variavel); ajuste de Holm sobre a familia completa"
        ),
        "notes": [
            "D80: o bootstrap wild usa UM peso de Rademacher por grupo e por "
            "replicacao (Cameron, Gelbach & Miller, 2008). A implementacao "
            "herdada da sessao anterior sorteava um peso por observacao, o "
            "que nao preserva a dependencia intra-cluster.",
            "O bootstrap e calculado na forma vetorizada, numericamente "
            "equivalente a forma em laco (verificada por teste).",
            "D81: sao reportados os p-valores das duas hipoteses nulas "
            "(imposta e irrestrita); a politica de reporte e explicita "
            f"(--null-policy={args.null_policy}).",
            "O bootstrap wild e aplicado a TODOS os esquemas de agrupamento; "
            "o esquema com menos grupos (UF) e o caso severo.",
            "Os efeitos fixos sao reproduzidos bit a bit em relacao a V2.6; "
            "apenas os p-valores do bootstrap wild foram recalculados.",
        ],
        "null_policy": args.null_policy,
        "crops": {},
    }
    csv_rows: list[dict[str, Any]] = []
    for crop in ("soja", "milho", "milho_2"):
        subset = [r for r in rows if r["crop"] == crop]
        if len(subset) < 50:
            continue
        schemes = build_schemes(subset, args.block_km)
        crop_entry: dict[str, Any] = {"variables": {}, "checks": {}}
        # equivalencia within x LSDV (validacao da escolha computacional)
        equivalence = spatial_inference.within_coefficient_matches_lsdv(
            subset, "precip_acumulada_mm"
        )
        crop_entry["checks"]["within_equals_lsdv"] = equivalence
        for variable in ANALYSIS_VARIABLES:
            prepared = spatial_inference.within_data(subset, variable)
            if prepared.get("status") != "ok":
                crop_entry["variables"][variable] = prepared
                continue
            lsdv = analysis.fixed_effects(rows, variable, crop_filter=crop)
            clustered = spatial_inference.clustered_within_inference(
                prepared, schemes
            )
            conley = spatial_inference.conley_within_inference(
                prepared, coords, cutoffs_km=args.conley_cutoffs
            )
            # Bootstrap wild em TODOS os esquemas de agrupamento. O esquema
            # com menos grupos (UF) e o caso severo (poucos grupos); o bloco
            # espacial de 250 km e o esquema conservador alinhado a
            # dependencia medida.
            group_counts = {
                name: len(set(groups)) for name, groups in schemes.items()
            }
            wcb_by_scheme: dict[str, Any] = {}
            for scheme_name, scheme_groups in schemes.items():
                # A versao vetorizada e numericamente equivalente a versao em
                # laco (verificada por teste automatizado).
                wcb = spatial_inference.wild_cluster_bootstrap_within_fast(
                    prepared,
                    scheme_groups,
                    n_boot=args.bootstrap,
                    seed=SEED,
                    null_policy=args.null_policy,
                )
                wcb["scheme"] = scheme_name
                wcb_by_scheme[scheme_name] = wcb
            most_conservative = min(group_counts, key=lambda k: group_counts[k])
            wcb = wcb_by_scheme[most_conservative]
            entry = {
                "v26_lsdv_municipality_clustered": lsdv,
                "within_clustered": clustered,
                "conley": conley,
                "wild_cluster_bootstrap": wcb,
                "wild_cluster_bootstrap_by_scheme": wcb_by_scheme,
                "n_clusters_by_scheme": group_counts,
            }
            crop_entry["variables"][variable] = entry
            for scheme_name, scheme_result in clustered.get("schemes", {}).items():
                if scheme_result.get("status") != "ok":
                    continue
                csv_rows.append(
                    {
                        "crop": crop,
                        "variable": variable,
                        "scheme": scheme_name,
                        "coefficient": clustered["coefficient"],
                        "std_error": scheme_result["std_error"],
                        "t_statistic": scheme_result["t_statistic"],
                        "df": scheme_result["df"],
                        "p_value": scheme_result["p_value"],
                        "ci_low": scheme_result["ci_low"],
                        "ci_high": scheme_result["ci_high"],
                        "n_clusters": scheme_result["n_clusters"],
                    }
                )
            for cutoff_key, cutoff_result in conley.get("cutoffs", {}).items():
                csv_rows.append(
                    {
                        "crop": crop,
                        "variable": variable,
                        "scheme": f"conley_{cutoff_key}",
                        "coefficient": conley["coefficient"],
                        "std_error": cutoff_result["std_error"],
                        "t_statistic": cutoff_result["t_statistic"],
                        "df": None,
                        "p_value": cutoff_result["p_value"],
                        "ci_low": cutoff_result["ci_low"],
                        "ci_high": cutoff_result["ci_high"],
                        "n_clusters": None,
                    }
                )
            for scheme_name, scheme_wcb in wcb_by_scheme.items():
                csv_rows.append(
                    {
                        "crop": crop,
                        "variable": variable,
                        "scheme": f"wild_bootstrap_{scheme_name}",
                        "coefficient": clustered["coefficient"],
                        "std_error": scheme_wcb.get("observed_se"),
                        "t_statistic": scheme_wcb.get("observed_t"),
                        "df": None,
                        "p_value": scheme_wcb.get("p_value"),
                        "ci_low": None,
                        "ci_high": None,
                        "n_clusters": scheme_wcb.get("n_clusters"),
                    }
                )
        out["crops"][crop] = crop_entry
        # persistencia incremental por cultura
        _write_json(out, os.path.join(MANIFESTS, "v27_robust_inference.json"))

    # correcao de Holm sobre a familia completa (por esquema)
    family_summary: dict[str, Any] = {}
    for scheme in sorted({row["scheme"] for row in csv_rows}):
        subset_rows = [row for row in csv_rows if row["scheme"] == scheme]
        p_values = {
            f"{row['crop']}|{row['variable']}": row["p_value"]
            for row in subset_rows
            if row.get("p_value") is not None
        }
        adjusted = robust.holm_adjust(p_values)
        family_summary[scheme] = {
            "n_hypotheses": len(p_values),
            "method": "Holm (FWER)",
            "p_values": p_values,
            "p_adjusted": adjusted,
            "n_significant_raw": sum(1 for v in p_values.values() if v < 0.05),
            "n_significant_holm": sum(1 for v in adjusted.values() if v is not None and v < 0.05),
        }
        for row in subset_rows:
            key = f"{row['crop']}|{row['variable']}"
            row["p_holm"] = adjusted.get(key)
    out["multiplicity"] = family_summary
    _write_csv(csv_rows, os.path.join(MANIFESTS, "v27_robust_inference.csv"))
    path = _write_json(out, os.path.join(MANIFESTS, "v27_robust_inference.json"))
    return {"ok": True, "manifest": path, "rows": len(csv_rows)}


# --------------------------------------------------------------------------
# Comando: validacao espacial
# --------------------------------------------------------------------------
def cmd_spatial(args: argparse.Namespace) -> dict[str, Any]:
    """Protocolos de generalizacao territorial, com verificacao de vazamento."""
    municipalities = load_municipalities()
    cells = spatial.municipality_cells(municipalities)
    blocks = spatial.spatial_blocks(municipalities, args.block_km)
    rows = prepare(load_panel())
    out: dict[str, Any] = {
        "generated_at": _now(),
        "seed": SEED,
        "block_km": args.block_km,
        "protocols": {},
        "crops": {},
    }
    csv_rows: list[dict[str, Any]] = []
    for crop in ("soja", "milho", "milho_2"):
        subset = [r for r in rows if r["crop"] == crop]
        if len(subset) < 50:
            continue
        for row in subset:
            code = str(row["ibge_code"])
            row["spatial_block_id"] = blocks.get(code)
        protocols: dict[str, Any] = {
            "P1_municipio_v26": {
                "description": (
                    "Holdout por municipio (protocolo da V2.6): dobras de "
                    "municipios inteiros, sem vazar anos entre treino e teste."
                ),
                "group_key": "ibge_code",
            },
            "P2_celula_grade": {
                "description": (
                    "Grouped por celula MERRA-2: todos os municipios de uma "
                    "célula ficam na mesma dobra (nenhum par compartilha a "
                    "célula entre treino e teste)."
                ),
                "group_key": "grid_cell_id",
            },
            "P3_bloco_espacial": {
                "description": (
                    "Grouped por bloco espacial: blocos de "
                    f"{int(args.block_km)} km; a dobra é unitária, de modo que "
                    "vizinhos imediatos ficam em dobras distintas."
                ),
                "group_key": "spatial_block_id",
            },
            "P4_leave_one_uf_out": {
                "description": (
                    "Leave-one-UF-out: uma UF inteira e testada por vez."
                ),
                "group_key": "state",
            },
        }
        crop_out: dict[str, Any] = {}
        for protocol_name, protocol in protocols.items():
            group_key = protocol["group_key"]
            key = "state" if group_key == "state" else group_key
            entry: dict[str, Any] = {
                "description": protocol["description"],
                "group_key": group_key,
                "n_groups": len({str(r.get(key)) for r in subset if r.get(key)}),
                "models": {},
            }
            for model_name, variables in MODELS.items():
                result = analysis.territorial_holdout(
                    subset,
                    variables,
                    n_folds=5,
                    crop_filter=crop,
                    seed=SEED,
                    group_key=key,
                )
                result.pop("predictions", None)
                entry["models"][model_name] = result
                models = result.get("models", {})
                baseline = models.get("media_historica", {})
                model = models.get("modelo", {})
                if baseline.get("mae_kg_ha") and model.get("mae_kg_ha"):
                    gain = (
                        baseline["mae_kg_ha"] - model["mae_kg_ha"]
                    ) / baseline["mae_kg_ha"]
                    entry.setdefault("gains_vs_media_historica", {})[model_name] = {
                        "gain_percent": 100.0 * gain,
                        "mae_modelo": model["mae_kg_ha"],
                        "mae_media_historica": baseline["mae_kg_ha"],
                        "n_predictions": model.get("n_predictions"),
                    }
                    csv_rows.append(
                        {
                            "crop": crop,
                            "protocol": protocol_name,
                            "model": model_name,
                            "n_predictions": model.get("n_predictions"),
                            "mae_modelo": model.get("mae_kg_ha"),
                            "mae_media_historica": baseline.get("mae_kg_ha"),
                            "gain_percent": 100.0 * gain,
                            "mae_ultimo_valor": models.get("ultimo_valor", {}).get(
                                "mae_kg_ha"
                            ),
                            "mae_tendencia": models.get("tendencia", {}).get("mae_kg_ha"),
                        }
                    )
            crop_out[protocol_name] = entry
        out["crops"][crop] = crop_out
        _write_json(out, os.path.join(MANIFESTS, "v27_spatial_validation.json"))
    _write_csv(csv_rows, os.path.join(MANIFESTS, "v27_spatial_validation.csv"))
    path = _write_json(out, os.path.join(MANIFESTS, "v27_spatial_validation.json"))
    return {"ok": True, "manifest": path, "rows": len(csv_rows)}


# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("dependence", "diagnose", "infer", "spatial", "all"),
    )
    parser.add_argument("--block-km", type=float, default=250.0)
    parser.add_argument(
        "--conley-cutoffs", type=float, nargs="+", default=(150.0, 250.0, 400.0, 600.0)
    )
    parser.add_argument("--bootstrap", type=int, default=999)
    parser.add_argument(
        "--null-policy",
        choices=("auto", "imposed", "unrestricted"),
        default="auto",
        help=(
            "politica de reporte do p-valor do bootstrap wild: 'imposed' "
            "(nulidade beta=0 imposta), 'unrestricted' (nulidade beta=betahat) "
            "ou 'auto' (regra historica: usa a irrestrita quando a imposta nao "
            "rejeita). As duas variantes sao sempre gravadas no manifesto."
        ),
    )
    args = parser.parse_args()

    commands = {
        "dependence": cmd_dependence,
        "diagnose": cmd_diagnose,
        "infer": cmd_infer,
        "spatial": cmd_spatial,
    }
    if args.command == "all":
        for name in ("dependence", "diagnose", "infer", "spatial"):
            print(f"=== {name} ===")
            result = commands[name](args)
            print(json.dumps(result, ensure_ascii=False, default=str))
        return 0
    result = commands[args.command](args)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
