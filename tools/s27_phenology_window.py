"""Experimento da janela fenológica de enchimento de grãos (V2.7).

Compara a **janela do ZARC** (plantio, protocolo da V2.6) com a **janela
fenológica de enchimento de grãos** (derivada de requisitos térmicos
publicados), sobre uma **amostra controlada** de municípios do painel.

Para cada linha do painel (município × cultura × ano):

1. calcula-se a data aproximada do estágio fenológico (R5 na soja; VT no
   milho) acumulando a **soma térmica real** a partir da data de plantio
   da janela ZARC;
2. define-se a janela de enchimento de grãos;
3. recalculam-se os **mesmos indicadores** do painel sobre essa janela,
   usando o **mesmo** construtor (``panel.build_climate_indicators``), de
   modo que a única mudança seja a **janela**;
4. reestimam-se os efeitos fixos nas duas janelas e comparam-se
   coeficiente, erro-padrão e estatística t.

Saídas:
* ``v27_phenology_window.json`` — manifesto com a comparação;
* ``v27_phenology_window.csv`` — indicadores recalculados por linha.

O script é **retomável**: linhas já calculadas são carregadas do CSV
anterior e apenas as faltantes são refeitas.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import analysis, panel as panel_module, phenology, robust, spatial_inference, water_balance as wb  # noqa: E402
from run_robustness import load_panel, prepare  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
DAILY = os.path.join(PROCESSED, "climate_daily.csv")

# Amostra de municipios (estratifcada por grade lat/lon).
def select_municipalities(rows: list[dict], n: int) -> list[str]:
    by_cell: dict[tuple[int, int], list[str]] = {}
    for row in rows:
        try:
            lat = float(row["centroid_lat"])
            lon = float(row["centroid_lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if not (-34.0 <= lat <= 6.0 and -74.0 <= lon <= -34.0):
            continue
        key = (int((lat + 34) // 2), int((lon + 74) // 4))
        by_cell.setdefault(key, []).append(str(row["ibge_code"]))
    keys = sorted(by_cell)
    chosen: list[str] = []
    step = max(1, len(keys) // max(1, n))
    for index, key in enumerate(keys):
        if len(chosen) >= n:
            break
        if index % step:
            continue
        chosen.append(sorted(by_cell[key])[len(by_cell[key]) // 2])
    for key in keys:
        if len(chosen) >= n:
            break
        for code in by_cell[key]:
            if code not in chosen:
                chosen.append(code)
                break
    return chosen[:n]


def load_daily(codes: set[str]) -> dict[str, list[dict]]:
    """Carrega a base diária (reanálise NASA POWER) dos municípios da amostra."""
    import pandas as pd

    wanted = ["date", "ibge_code", "source_type", "temp_media_c", "temp_max_c",
              "temp_min_c", "precip_mm", "radiacao_mj_m2", "umidade_rel_pct",
              "vento_kmh"]
    out: dict[str, list[dict]] = {}
    reader = pd.read_csv(
        DAILY,
        usecols=wanted,
        chunksize=400_000,
        low_memory=False,
    )
    for chunk in reader:
        chunk = chunk[chunk["source_type"] == "reanalysis"]
        chunk = chunk[chunk["ibge_code"].astype(str).isin(codes)]
        if chunk.empty:
            continue
        for code, group in chunk.groupby(chunk["ibge_code"].astype(str)):
            records = group.drop(columns=["ibge_code"]).to_dict("records")
            out.setdefault(code, []).extend(records)
    for code in out:
        out[code].sort(key=lambda r: str(r["date"]))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=200)
    parser.add_argument("--duration-days", type=float, default=45.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    t0 = time.time()
    # O painel cru e necessario: a janela do ZARC (datas de plantio) e os
    # indicadores da V2.6 nao sobrevivem a ``prepare`` (que mantem apenas as
    # colunas analiticas).
    raw: list[dict] = []
    with io.open(
        os.path.join(PROCESSED, "agroclimatic_productivity_panel.csv"),
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        for record in csv.DictReader(handle):
            if str(record.get("climate_source")) != "NASA-POWER":
                continue
            if str(record.get("status")) != "paired_usable":
                continue
            raw.append(record)
    print(f"linhas do painel cru (reanálise, incluidas): {len(raw)}")
    municipalities = {}
    with io.open(
        os.path.join(PROCESSED, "panel_municipalities.csv"),
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        for record in csv.DictReader(handle):
            municipalities[record["ibge_code"]] = record
    for record in raw:
        meta = municipalities.get(str(record["ibge_code"]), {})
        record["centroid_lat"] = meta.get("centroid_lat")
        record["centroid_lon"] = meta.get("centroid_lon")
        record["elevation_m"] = meta.get("elevation_m")

    eligible = [r for r in raw if r.get("crop") in ("soja", "milho")]
    print(f"linhas do painel (soja+milho, incluidas): {len(eligible)}")
    codes = select_municipalities(eligible, args.sample)
    print(f"municipios da amostra: {len(codes)}")
    subset = [r for r in eligible if str(r["ibge_code"]) in set(codes)]
    print(f"linhas na amostra: {len(subset)}")

    csv_path = os.path.join(MANIFESTS, "v27_phenology_window.csv")
    done: dict[tuple[str, str, str], dict] = {}
    if os.path.exists(csv_path) and not args.force:
        with io.open(csv_path, encoding="utf-8", newline="") as handle:
            for record in csv.DictReader(handle):
                done[(record["ibge_code"], record["crop"], record["harvest_year"])] = record
        print(f"linhas ja calculadas (retomada): {len(done)}")

    print("carregando a base diaria...")
    daily = load_daily(set(codes))
    print(f"  municipios com serie diaria: {len(daily)}")

    soil = wb.default_soil_profile("tipo2_medio")
    computed: list[dict] = []
    skipped = 0
    for index, row in enumerate(subset):
        key = (str(row["ibge_code"]), str(row["crop"]), str(row["harvest_year"]))
        if key in done:
            continue
        records = daily.get(str(row["ibge_code"]))
        if not records:
            skipped += 1
            continue
        crop = str(row["crop"])
        profile = phenology.SOJA_MEDIO if crop == "soja" else phenology.MILHO_GRUPO_II
        planting = str(row.get("zarc_window_start") or "")
        if not planting:
            skipped += 1
            continue
        duration = args.duration_days if crop == "soja" else None
        window = phenology.grain_filling_window(
            records, profile, planting, duration_days=duration
        )
        if window.get("status") != "ok":
            skipped += 1
            continue
        window_records = [
            r for r in records
            if window["window_start"] <= str(r.get("date")) <= window["window_end"]
        ]
        if len(window_records) < 10:
            skipped += 1
            continue
        lat = row.get("centroid_lat")
        lon = row.get("centroid_lon")
        elevation = row.get("elevation_m")
        indicators = panel_module.build_climate_indicators(
            window_records,
            float(lat) if lat not in (None, "") else None,
            float(elevation) if elevation not in (None, "") else None,
            soil,
            str(row.get("et_method") or "fao56_penman_monteith"),
            crop,
        )
        computed.append(
            {
                "ibge_code": key[0],
                "crop": key[1],
                "harvest_year": key[2],
                "municipality": row.get("municipality"),
                "state": row.get("state"),
                "zarc_window_start": planting,
                "zarc_window_end": row.get("zarc_window_end"),
                "phenology_profile": window["phenology_profile"],
                "phenology_window_start": window["window_start"],
                "phenology_window_end": window["window_end"],
                "phenology_days": window["n_days_in_window"],
                "zarc_days": row.get("climate_days"),
                "stage_date_approx": window.get("stage_date_approx"),
                "yield_kg_ha": row.get("yield_kg_ha"),
                **{f"fen_{k}": v for k, v in indicators.items()},
                **{f"zarc_{k}": row.get(k) for k in (
                    "precip_acumulada_mm", "temp_media_c", "et0_total_mm",
                    "deficiency_total_mm", "excess_total_mm", "degree_days_total",
                    "extreme_heat_days", "coverage",
                )},
            }
        )
        if (index + 1) % 500 == 0:
            print(f"  ... {index + 1}/{len(subset)}", flush=True)

    print(f"linhas calculadas: {len(computed)} | ignoradas (sem dado): {skipped}")

    # ------------------------------------------------------------- gravacao
    os.makedirs(MANIFESTS, exist_ok=True)
    all_rows = list(done.values()) + computed
    if all_rows:
        fields: list[str] = []
        for record in all_rows:
            for key in record:
                if key not in fields:
                    fields.append(key)
        with io.open(csv_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_rows)

    # ------------------------------------------- reestimacao por janela
    def _estimate(records: list[dict], prefix: str) -> dict:
        out: dict = {}
        for variable in (
            "precip_acumulada_mm", "temp_media_c", "et0_total_mm",
            "deficiency_total_mm", "excess_total_mm",
        ):
            by_crop: dict[str, list[dict]] = {}
            for record in records:
                value = record.get(f"{prefix}_{variable}")
                if value in (None, ""):
                    continue
                by_crop.setdefault(str(record["crop"]), []).append(
                    {
                        "ibge_code": record["ibge_code"],
                        "year": record["harvest_year"],
                        "crop": record["crop"],
                        variable: float(value),
                        "yield_kg_ha": float(record["yield_kg_ha"]),
                    }
                )
            for crop, subset_rows in by_crop.items():
                if len(subset_rows) < 50:
                    continue
                result = analysis.fixed_effects(
                    subset_rows, variable, crop_filter=crop
                )
                # A V2.6 nao grava p-valor; ele e recomputado aqui com a
                # distribuicao t (df = municipios - 1), como no resto da V2.7.
                p_value = None
                if result.get("t_statistic") is not None:
                    df = max(int(result.get("n_municipalities") or 2) - 1, 1)
                    p_value = robust.t_sf(result["t_statistic"], df)
                out[f"{crop}|{variable}"] = {
                    "status": result.get("status"),
                    "n": result.get("n"),
                    "coefficient": result.get("coefficient"),
                    "std_error_clustered": result.get("std_error_clustered"),
                    "t_statistic": result.get("t_statistic"),
                    "p_value": p_value,
                    "n_municipalities": result.get("n_municipalities"),
                    "n_years": result.get("n_years"),
                }
        return out

    zarc_rows = []
    fen_rows = []
    for record in all_rows:
        base = {
            "ibge_code": record["ibge_code"],
            "harvest_year": record["harvest_year"],
            "crop": record["crop"],
            "yield_kg_ha": record["yield_kg_ha"],
        }
        zarc_rows.append(
            {**base, **{k: v for k, v in record.items() if k.startswith("zarc_")}}
        )
        fen_rows.append(
            {**base, **{k: v for k, v in record.items() if k.startswith("fen_")}}
        )

    est_zarc = _estimate(zarc_rows, "zarc")
    est_fen = _estimate(fen_rows, "fen")

    comparison = []
    for key in sorted(set(est_zarc) & set(est_fen)):
        a, b = est_zarc[key], est_fen[key]
        comparison.append(
            {
                "hypothesis": key,
                "n_zarc": a.get("n"),
                "n_fen": b.get("n"),
                "coefficient_zarc": a.get("coefficient"),
                "coefficient_fen": b.get("coefficient"),
                "std_error_zarc": a.get("std_error_clustered"),
                "std_error_fen": b.get("std_error_clustered"),
                "t_zarc": a.get("t_statistic"),
                "t_fen": b.get("t_statistic"),
                "sign_zarc": a.get("p_value") is not None and a["p_value"] < 0.05,
                "sign_fen": b.get("p_value") is not None and b["p_value"] < 0.05,
                "se_ratio": (
                    a.get("std_error_clustered") and b.get("std_error_clustered")
                    and b["std_error_clustered"] / a["std_error_clustered"]
                ),
            }
        )

    coverage = {}
    for crop in ("soja", "milho"):
        rows_crop = [r for r in all_rows if r["crop"] == crop]
        days = [float(r["phenology_days"]) for r in rows_crop if r.get("phenology_days")]
        zarc_days = [float(r["zarc_days"]) for r in rows_crop if r.get("zarc_days")]
        stages = [
            str(r["stage_date_approx"])
            for r in rows_crop
            if r.get("stage_date_approx")
        ]
        coverage[crop] = {
            "n_rows": len(rows_crop),
            "n_municipalities": len({r["ibge_code"] for r in rows_crop}),
            "n_years": len({r["harvest_year"] for r in rows_crop}),
            "phenology_window_days_median": float(np.median(days)) if days else None,
            "phenology_window_days_min": min(days) if days else None,
            "phenology_window_days_max": max(days) if days else None,
            "zarc_window_days_median": float(np.median(zarc_days)) if zarc_days else None,
            "stage_date_min": min(stages) if stages else None,
            "stage_date_max": max(stages) if stages else None,
            "stage_date_distinct": len(set(stages)),
            "n_without_stage": sum(
                1 for r in rows_crop if not r.get("stage_date_approx")
            ),
        }

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": (
            "Janela fenologica de enchimento de graos derivada de requisitos "
            "termicos publicados (Embrapa); recalculo dos indicadores com o "
            "mesmo construtor do painel; reestimacao dos efeitos fixos nas duas "
            "janelas."
        ),
        "sample": {
            "n_municipalities": len(codes),
            "n_rows_panel_sample": len(subset),
            "n_rows_computed": len(computed),
            "n_skipped": skipped,
            "duration_days_soja": args.duration_days,
        },
        "profiles": {
            key: profile.to_dict()
            for key, profile in phenology.PHENOLOGY_PROFILES.items()
        },
        "grain_filling_definitions": {
            crop: {
                "start_stage": d.start_stage,
                "start_offset_days": d.start_offset_days,
                "duration_days": d.duration_days,
                "source": d.source,
                "note": d.note,
            }
            for crop, d in phenology.GRAIN_FILLING_DEFINITIONS.items()
        },
        "coverage": coverage,
        "estimates_zarc": est_zarc,
        "estimates_phenology": est_fen,
        "comparison": comparison,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with io.open(
        os.path.join(MANIFESTS, "v27_phenology_window.json"),
        "w",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print()
    print("comparacao (janela ZARC -> janela fenologica):")
    for item in comparison:
        print(
            f"  {item['hypothesis']:36s} coef {item['coefficient_zarc']} -> "
            f"{item['coefficient_fen']} | EP {item['std_error_zarc']} -> "
            f"{item['std_error_fen']} | sign {item['sign_zarc']} -> {item['sign_fen']}"
        )
    print(f"manifesto: {os.path.join(MANIFESTS, 'v27_phenology_window.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
