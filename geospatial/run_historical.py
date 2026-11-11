#!/usr/bin/env python
"""CLI da V2.3 — estudo exploratório municipal de produtividade.

    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_historical.py radiometry
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_historical.py series
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_historical.py landuse
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_historical.py study

Os subcomandos usam rede (STAC, COGs, MapBiomas). A suíte offline
(`geospatial/tests`) é independente.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from historical import pcatalog  # noqa: E402
from historical import radiometry as radio  # noqa: E402
from historical import series as series_mod  # noqa: E402
from s2_poc import config, indices as indices_mod, network, read  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
MANIFEST_DIR = os.path.join(DATA_DIR, "manifests")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
ARTIFACTS_DIR = os.path.join(HERE, "artifacts", "historical")

BBOX = [-55.6309, -12.7339, -55.5709, -12.6739]
TILE = "MGRS-21LXG"


def _write_json(data: Any, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, default=str)
    return path


def _catalog():
    from pystac_client import Client

    network.configure_tls()
    return Client.open(config.STAC_URL)


def _items_for(client, collection: str, start: str, end: str):
    search = client.search(
        collections=[collection],
        bbox=BBOX,
        datetime=f"{start}T00:00:00Z/{end}T23:59:59Z",
        limit=100,
    )
    return list(search.items())


# ------------------------------------------------------------- radiometria


def cmd_radiometry(args: argparse.Namespace) -> dict[str, Any]:
    """Experimento radiométrico: C1 (harmonizada) × original (regra ESA)."""
    from pystac_client import Client

    network.configure_tls()
    earth = Client.open(config.STAC_URL)
    grid = read.target_grid("EPSG:32721", BBOX, config.TARGET_RES_M)

    def table(client, collection, declared):
        out: dict[str, list[Any]] = {}
        for year in range(args.start_year, args.end_year + 1):
            try:
                items = list(
                    client.search(
                        collections=[collection],
                        bbox=BBOX,
                        datetime=f"{year}-01-01T00:00:00Z/{year}-12-31T23:59:59Z",
                        limit=100,
                    ).items()
                )
            except Exception:  # noqa: BLE001 - rede
                continue
            for item in items:
                if pcatalog.tile_code(item) != TILE:
                    continue
                if not pcatalog.covers(item, BBOX):
                    continue
                date = str(item.properties.get("datetime"))[:10]
                out.setdefault(date, []).append((item, declared))
        return out

    c1_by_date = table(earth, radio.COLLECTION_C1, True)
    pc_by_date = table(earth, radio.COLLECTION_ORIGINAL, True)
    paired = sorted(set(c1_by_date) & set(pc_by_date))

    def cloud(item) -> float:
        value = item.properties.get("eo:cloud_cover")
        return 999.0 if value is None else float(value)

    paired = [
        date
        for date in paired
        if cloud(c1_by_date[date][0][0]) <= args.max_cloud
        and cloud(pc_by_date[date][0][0]) <= args.max_cloud
    ]
    paired.sort(key=lambda date: (cloud(c1_by_date[date][0][0]), date))
    paired = paired[: args.max_pairs]

    results: list[dict[str, Any]] = []
    for date in paired:
        c1_item = c1_by_date[date][0][0]
        pc_item = pc_by_date[date][0][0]
        c1_profile = radio.item_radiometry(c1_item, radio.COLLECTION_C1)
        pc_profile = radio.item_radiometry(pc_item, radio.COLLECTION_ORIGINAL)
        radio.assert_usable(c1_profile)
        radio.assert_usable(pc_profile)

        c1_ndvi, c1_valid, _ = series_mod.read_ndvi(c1_item, grid, c1_profile)
        pc_ndvi, pc_valid, _ = series_mod.read_ndvi(pc_item, grid, pc_profile)
        common = c1_valid & pc_valid
        n = int(np.count_nonzero(common))
        entry: dict[str, Any] = {
            "date": date,
            "c1_item": c1_item.id,
            "original_item": pc_item.id,
            "c1_profile": c1_profile["profile"],
            "c1_baseline": c1_profile["baseline_raw"],
            "c1_formula": c1_profile["formula"],
            "original_profile": pc_profile["profile"],
            "original_baseline": pc_profile["baseline_raw"],
            "original_formula": pc_profile["formula"],
            "original_offset_source": pc_profile.get("offset_source"),
            "c1_cloud_cover_tile_pct": c1_item.properties.get("eo:cloud_cover"),
            "original_cloud_cover_tile_pct": pc_item.properties.get("eo:cloud_cover"),
            "common_pixels": n,
        }
        if n > 100:
            diff = c1_ndvi[common].astype("float64") - pc_ndvi[common].astype("float64")
            entry.update(
                {
                    "ndvi_mean_c1": float(np.nanmean(c1_ndvi[common])),
                    "ndvi_mean_original": float(np.nanmean(pc_ndvi[common])),
                    "ndvi_mean_difference": float(np.nanmean(diff)),
                    "ndvi_median_absolute_difference": float(np.nanmedian(np.abs(diff))),
                    "ndvi_p95_absolute_difference": float(np.nanpercentile(np.abs(diff), 95)),
                    "ndvi_correlation": (
                        float(np.corrcoef(c1_ndvi[common], pc_ndvi[common])[0, 1])
                        if np.nanstd(c1_ndvi[common]) > 0
                        and np.nanstd(pc_ndvi[common]) > 0
                        else None
                    ),
                }
            )
        results.append(entry)

    # metadados no arquivo (sem aplicar escala) de uma cena antiga e uma recente
    file_checks = []
    for item, collection, declared in (
        (c1_by_date[paired[0]][0][0] if paired else None, radio.COLLECTION_C1, True),
        (pc_by_date[paired[0]][0][0] if paired else None, radio.COLLECTION_ORIGINAL, True),
    ):
        if item is None:
            continue
        href = item.assets["red"].href
        with read.rasterio.Env(**read.GDAL_ENV):
            with read.rasterio.open(href) as ds:
                file_meta = radio.file_radiometry(ds)
        declared_meta = radio.item_radiometry(item, collection, declared=declared)
        file_checks.append(
            {
                "item_id": item.id,
                "collection": collection,
                "datetime": item.properties.get("datetime"),
                "baseline": declared_meta["baseline_raw"],
                "declared_scale": declared_meta["scale"],
                "declared_offset": declared_meta["offset"],
                "offset_source": declared_meta.get("offset_source"),
                "file_scales": list(file_meta["scales"]),
                "file_offsets": list(file_meta["offsets"]),
                "file_dtype": file_meta["dtype"],
                "file_nodata": file_meta["nodata"],
                "read_returns_raw_dn": True,
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aoi_bbox": BBOX,
        "grid": {
            "crs": str(grid["crs"]),
            "res": grid["res"],
            "width": grid["width"],
            "height": grid["height"],
        },
        "window": {"start_year": args.start_year, "end_year": args.end_year},
        "paired_dates": len(results),
        "paired_comparison": results,
        "file_level_checks": file_checks,
        "profiles": radio.PROFILE_DESCRIPTIONS,
        "note": (
            "A coleção C1 harmonizada (Earth Search) e os produtos originais "
            "(Planetary Computer) são comparados na mesma data e sobre a mesma "
            "grade. A conversão de cada um usa o offset declarado (C1) ou a "
            "regra oficial da ESA baseada no processing baseline (originais)."
        ),
    }
    path = _write_json(
        payload, os.path.join(MANIFEST_DIR, "sentinel2_radiometry_experiment.json")
    )
    return {"ok": True, "report": path, "paired_dates": len(results), "results": results}


# ----------------------------------------------------------------- série


def cmd_series(args: argparse.Namespace) -> dict[str, Any]:
    """Constrói a série histórica mensal 2017–2025."""
    out_dir = ARTIFACTS_DIR
    os.makedirs(out_dir, exist_ok=True)
    result = series_mod.build_monthly_series(
        start=args.start,
        end=args.end,
        bbox=BBOX,
        out_dir=out_dir,
        max_obstruction=args.max_obstruction,
        max_candidates=args.max_candidates,
        write_rasters=not args.no_rasters,
    )
    csv_path = os.path.join(PROCESSED_DIR, "sentinel2_historical_monthly.csv")
    series_mod.write_monthly_csv(result["rows"], csv_path)
    manifest = series_mod.manifest_payload(
        result["rows"], result["grid"], args.start, args.end
    )
    manifest["csv"] = os.path.relpath(csv_path, HERE).replace("\\", "/")
    manifest["rasters_dir"] = os.path.relpath(out_dir, HERE).replace("\\", "/")
    manifest_path = _write_json(
        manifest, os.path.join(MANIFEST_DIR, "sentinel2_historical_series.json")
    )
    return {
        "ok": True,
        "csv": csv_path,
        "manifest": manifest_path,
        "months_observed": manifest["months_observed"],
        "months_missing": manifest["months_missing"],
        "collections_used": manifest["collections_used"],
        "baselines_used": manifest["baselines_used"],
        "profiles_used": manifest["profiles_used"],
    }


# ----------------------------------------------------------------- uso do solo


def cmd_landuse(args: argparse.Namespace) -> dict[str, Any]:
    """Quantifica o uso do solo na AOI (WorldCover) e registra o bloqueio MapBiomas."""
    from historical import landuse as lu

    out_dir = ARTIFACTS_DIR
    os.makedirs(out_dir, exist_ok=True)
    grid = read.target_grid("EPSG:32721", BBOX, config.TARGET_RES_M)
    results: list[dict[str, Any]] = []
    mask_path = os.path.join(out_dir, "worldcover_cropland_masks.npz")
    masks: dict[str, np.ndarray] = {}
    for year in args.years:
        try:
            payload = lu.read_worldcover_year(year, BBOX)
        except Exception as exc:  # noqa: BLE001 - rede
            results.append({"year": year, "status": "erro", "error": f"{type(exc).__name__}: {exc}"})
            continue
        data = payload["data"]
        meta = payload["meta"]
        lon_res = meta["res"][0]
        lat_res = meta["res"][1]
        lat_max = meta["transform"][5]
        lat_min = lat_max - data.shape[0] * lat_res
        report = lu.class_areas(data, lon_res, lat_res, lat_min, lat_max)
        grid_mask = lu.cropland_grid_mask(data, meta, grid)
        masks[f"y{year}"] = grid_mask
        crop_cells = int(np.count_nonzero(grid_mask))
        results.append(
            {
                "year": year,
                "status": "ok",
                "source": "ESA WorldCover 10m (v200/v100)",
                "url": meta["url"],
                "tile": lu.worldcover_tile_name(BBOX),
                "crs": meta["crs"],
                "resolution_m": list(meta["res"]),
                "shape": list(data.shape),
                "total_area_km2": report["total_area_km2"],
                "classes": report["classes"],
                "cropland_fraction": report["classes"].get(
                    str(lu.WORLDCOVER_CROPLAND), {}
                ).get("fraction"),
                "cropland_cells_20m": crop_cells,
                "cropland_fraction_grid": (
                    crop_cells / (grid["width"] * grid["height"])
                    if grid["width"] * grid["height"]
                    else None
                ),
            }
        )
    if masks:
        np.savez_compressed(mask_path, **{f"y{year}": mask for year, mask in masks.items()})

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aoi_bbox": BBOX,
        "mapbiomas": {
            "status": "bloqueado",
            "reason": (
                "A página oficial informa que a função de download de mapas "
                "(GeoTIFF) está temporariamente suspensa e que o acesso passa "
                "pelos assets do Google Earth Engine (requer conta). Os endereços "
                "públicos testados retornaram 404."
            ),
            "legend_obtained": True,
            "legend": lu.MAPBIOMAS_LEGEND,
        },
        "worldcover": {
            "license": "CC BY 4.0 (ESA WorldCover)",
            "url_template": "https://esa-worldcover.s3.eu-central-1.amazonaws.com/",
            "classes": lu.WORLDCOVER_CLASSES,
            "note": (
                "Cropland (40) na classe oficial; WorldCover não separa "
                "temporária de perene nem identifica soja/milho."
            ),
        },
        "years": results,
        "mask_file": os.path.relpath(mask_path, HERE).replace("\\", "/") if masks else None,
    }
    path = _write_json(payload, os.path.join(MANIFEST_DIR, "landuse_aoi_report.json"))
    return {
        "ok": True,
        "report": path,
        "years": [
            {
                "year": r["year"],
                "status": r["status"],
                "cropland_fraction": r.get("cropland_fraction"),
                "total_area_km2": r.get("total_area_km2"),
            }
            for r in results
        ],
    }


# --------------------------------------------------------------------- estudo


def cmd_study(args: argparse.Namespace) -> dict[str, Any]:
    """Monta o conjunto pareado e as estatísticas exploratórias."""
    from historical import study as study_mod

    monthly_csv = os.path.join(PROCESSED_DIR, "sentinel2_historical_monthly.csv")
    base_csv = os.path.join(PROCESSED_DIR, "productivity_observations.csv")
    if not os.path.exists(monthly_csv):
        return {"ok": False, "error": f"série histórica ausente: {monthly_csv}"}

    monthly = study_mod.load_monthly(monthly_csv)
    base = study_mod.load_base(base_csv)
    yields = study_mod.extract_yields(base)
    indicators = study_mod.yearly_indicators(monthly)
    dataset = study_mod.build_dataset(yields, indicators)
    dataset_path = study_mod.write_dataset_csv(
        dataset, os.path.join(PROCESSED_DIR, "productivity_exploratory_dataset.csv")
    )
    stats = study_mod.exploratory_stats(dataset, permutations=args.permutations)
    gate = study_mod.gate_evaluation(stats, minimum_pairs=args.minimum_pairs)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": "IBGE/PAM rendimento médio municipal (kg/ha) — município 5107925",
        "indicator": "NDVI da AOI de validação (sub-região, 0,4654% do município)",
        "dataset_csv": os.path.relpath(dataset_path, HERE).replace("\\", "/"),
        "records": len(dataset),
        "paired_usable": sum(1 for r in dataset if r["status"] == "paired_usable"),
        "excluded": sum(1 for r in dataset if r["status"] == "excluded"),
        "exclusion_reasons": sorted(
            {r["exclusion_reason"] for r in dataset if r["exclusion_reason"]}
        ),
        "statistics": stats,
        "gate": gate,
        "limitations": [
            "Escala espacial divergente: o alvo é municipal; o indicador é de uma AOI de 43,26 km².",
            "Não há identificação de cultura na AOI: os indicadores não são 'soja'/'milho'.",
            "Calendário fenológico não validado: a agregação é por ano civil.",
            "Série curta e n pequeno: as correlações são exploratórias.",
        ],
    }
    path = _write_json(payload, os.path.join(MANIFEST_DIR, "exploratory_study.json"))
    return {
        "ok": True,
        "report": path,
        "dataset_csv": payload["dataset_csv"],
        "records": payload["records"],
        "paired_usable": payload["paired_usable"],
        "excluded": payload["excluded"],
        "statistics": {
            crop: {
                "n_pairs": entry["n_pairs"],
                "years": entry["years"],
                "pearson_r": entry["pearson_r"],
                "spearman_rho": entry["spearman_rho"],
                "permutation_p": entry["permutation_p"],
                "pearson_r_detrended": entry.get("pearson_r_detrended"),
            }
            for crop, entry in stats["crops"].items()
        },
        "gate": gate,
    }


# --------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SADEN V2.3 — estudo exploratório municipal de produtividade"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_rad = sub.add_parser("radiometry", help="experimento radiométrico C1 × original")
    p_rad.add_argument("--start-year", type=int, default=2018)
    p_rad.add_argument("--end-year", type=int, default=2024)
    p_rad.add_argument("--max-pairs", type=int, default=5)
    p_rad.add_argument("--max-cloud", type=float, default=25.0)
    p_rad.set_defaults(func=cmd_radiometry)

    p_ser = sub.add_parser("series", help="série histórica mensal 2017–2025")
    p_ser.add_argument("--start", default="2017-01")
    p_ser.add_argument("--end", default="2025-12")
    p_ser.add_argument("--max-obstruction", type=float, default=0.5)
    p_ser.add_argument("--max-candidates", type=int, default=3)
    p_ser.add_argument("--no-rasters", action="store_true")
    p_ser.set_defaults(func=cmd_series)

    p_lu = sub.add_parser("landuse", help="uso do solo na AOI (WorldCover)")
    p_lu.add_argument("--years", type=int, nargs="+", default=[2020, 2021])
    p_lu.set_defaults(func=cmd_landuse)

    p_st = sub.add_parser("study", help="conjunto pareado + estatísticas exploratórias")
    p_st.add_argument("--permutations", type=int, default=5000)
    p_st.add_argument("--minimum-pairs", type=int, default=9)
    p_st.set_defaults(func=cmd_study)

    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except Exception as exc:  # noqa: BLE001 - CLI falha com mensagem clara
        print(
            json.dumps(
                {"ok": False, "error": type(exc).__name__, "message": str(exc)},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
