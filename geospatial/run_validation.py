#!/usr/bin/env python
"""CLI de validação geoespacial SADEN V2.1 (checkpoints A–E).

A partir da raiz do repositório (Windows):

    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_validation.py repro
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_validation.py scl
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_validation.py geometry
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_validation.py mosaic
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_validation.py timeseries

Os subcomandos ``scl``, ``mosaic`` e ``timeseries`` usam a **rede** (STAC +
COGs reais). A suíte de testes offline (``geospatial/tests``) é independente
deles. Rasters vão para ``geospatial/artifacts/`` (ignorado pelo Git);
manifestos e relatórios leves vão para ``geospatial/manifests/`` e
``geospatial/reports/``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import rasterio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s2_poc import config  # noqa: E402
from s2_poc import geometry as geometry_mod  # noqa: E402
from s2_poc import indices as indices_mod  # noqa: E402
from s2_poc import mask as mask_mod  # noqa: E402
from s2_poc import mosaic as mosaic_mod  # noqa: E402
from s2_poc import network  # noqa: E402
from s2_poc import pipeline  # noqa: E402
from s2_poc import radiometry  # noqa: E402
from s2_poc import read as read_mod  # noqa: E402
from s2_poc import render  # noqa: E402
from s2_poc import stac_search  # noqa: E402
from s2_poc import timeseries as ts_mod  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS = os.path.join(HERE, "artifacts")
MANIFESTS = os.path.join(HERE, "manifests")
REPORTS = os.path.join(HERE, "reports")
PREVIEWS = os.path.join(HERE, "previews")

# Área de um pixel na grade de trabalho (20 m em EPSG:32721).
PIXEL_AREA_KM2 = (config.TARGET_RES_M ** 2) / 1e6


# ---------------------------------------------------------------- utilidades


def _ensure_dirs() -> None:
    for path in (ARTIFACTS, MANIFESTS, REPORTS, PREVIEWS):
        os.makedirs(path, exist_ok=True)


def git_commit() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=HERE,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.stdout.strip() or None
    except Exception:  # pragma: no cover - git pode não estar disponível
        return None


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def base_manifest(run: str, purpose: str) -> dict[str, Any]:
    return {
        "run_id": run,
        "purpose": purpose,
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "code_commit": git_commit(),
        "versions": pipeline.library_versions(),
        "catalog": {
            "url": config.STAC_URL,
            "collection": config.COLLECTION,
            "access": "acesso anônimo, sem credencial, sem custo",
        },
        "parameters": {
            "target_res_m": config.TARGET_RES_M,
            "assets": dict(config.ASSETS),
            "scl_profiles": {k: list(v) for k, v in config.SCL_PROFILES.items()},
            "scl_class_semantics": dict(config.SCL_CLASSES),
            "continuous_resampling": "average (10 m -> 20 m)",
            "categorical_resampling": "nearest (SCL)",
            "reflectance_conversion": "DN * scale + offset; DN == nodata -> NaN antes da escala",
            "formulas": dict(config.FORMULAS),
            "denominator_rule": "|den| <= 1e-6 -> NaN (nunca inf, nunca clamp)",
            "nodata_output": "NaN (float32)",
        },
        "limitations": [
            "Índices de vegetação não medem produtividade, uso do solo nem preço.",
            "AOI é recorte geográfico de validação, não talhão agrícola.",
            "Sem correção de BRDF, topografia ou mistura espectral.",
        ],
    }


def write_manifest(manifest: dict[str, Any], name: str) -> str:
    _ensure_dirs()
    path = os.path.join(MANIFESTS, f"{name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(pipeline._jsonable(manifest), fh, ensure_ascii=False, indent=2)
    return path


def write_json(data: Any, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(pipeline._jsonable(data), fh, ensure_ascii=False, indent=2)
    return path


def _stats_with_degenerate(values: np.ndarray, keep: np.ndarray) -> dict[str, Any]:
    stats = indices_mod.array_stats(values)
    stats["degenerate_pixels"] = int(
        np.count_nonzero(keep) - np.count_nonzero(np.isfinite(values))
    )
    return stats


def item_metadata(item: Any) -> dict[str, Any]:
    props = item.properties
    return {
        "item_id": item.id,
        "collection": item.collection_id,
        "datetime": props.get("datetime"),
        "platform": props.get("platform"),
        "tile": props.get("grid:code"),
        "baseline": props.get("s2:processing_baseline"),
        "datatake_id": props.get("s2:datatake_id"),
        "datastrip_id": props.get("s2:datastrip_id"),
        "orbit": props.get("s2:orbit"),
        "cloud_cover_tile_pct": props.get("eo:cloud_cover"),
        "proj_epsg": props.get("proj:epsg"),
        "bbox": item.bbox,
        "item_href": item.get_self_href(),
    }


# --------------------------------------------------------------- checkpoint A


def cmd_repro(args: argparse.Namespace) -> dict[str, Any]:
    """Reexecuta a PoC original em diretório separado e audita a radiometria."""
    network.configure_tls()
    run = run_id()
    artifacts = os.path.join(ARTIFACTS, "repro_poc")
    previews = os.path.join(PREVIEWS, "repro")
    os.makedirs(artifacts, exist_ok=True)
    os.makedirs(previews, exist_ok=True)

    started = time.time()
    summary = pipeline.run(
        artifacts_dir=artifacts,
        previews_dir=previews,
        start=args.start,
        end=args.end,
        max_cloud=args.max_cloud,
        max_scenes=args.max_scenes,
        write_preview=True,
    )
    elapsed = time.time() - started

    # Auditoria radiométrica por item (metadado STAC x COG real).
    client = stac_search.open_catalog()
    audits: list[dict[str, Any]] = []
    for provenance in summary["items"]:
        item = client.get_item(provenance["item_id"], collection=config.COLLECTION)
        try:
            declared = radiometry.assert_supported_item(item, ("blue", "red", "nir", "swir"))
        except radiometry.UnsupportedProductError as exc:
            audits.append({"item_id": item.id, "supported": False, "reason": str(exc)})
            continue
        red_asset = item.assets[config.ASSETS["red"]]
        with rasterio.Env(**read_mod.GDAL_ENV):
            with rasterio.open(red_asset.href) as ds:
                file_meta = radiometry.file_radiometry(ds)
        audits.append(
            {
                "item_id": item.id,
                "supported": True,
                "declared": declared,
                "file": file_meta,
                "consistency": radiometry.check_file_matches_asset(file_meta, declared),
            }
        )

    reference = _compare_with_reference(summary, args.reference)

    manifest = base_manifest(run, "checkpoint_A_repro")
    manifest.update(
        {
            "aoi": summary["aoi"],
            "search": summary["search"],
            "items": summary["items"],
            "scenes": [
                {
                    "item_id": s["item_id"],
                    "datetime": s["datetime"],
                    "grid": s["grid"],
                    "mask_summary": s["mask_summary"],
                    "stats": s["stats"],
                    "files": {k: v["path"] for k, v in s["files"].items()},
                    "file_sha256": {k: v["sha256"] for k, v in s["files"].items()},
                    "preview": s["preview"],
                }
                for s in summary["scenes"]
            ],
            "radiometry_audit": audits,
            "elapsed_seconds": round(elapsed, 1),
            "artifacts_dir": artifacts,
            "comparison_with_reference": reference,
            "warnings": summary["warnings"],
        }
    )
    manifest_path = write_manifest(manifest, f"repro_{run}")
    report_path = write_json(reference, os.path.join(REPORTS, f"repro_comparison_{run}.json"))
    return {
        "ok": True,
        "run_id": run,
        "manifest": manifest_path,
        "report": report_path,
        "elapsed_seconds": round(elapsed, 1),
        "scenes": [
            {
                "item_id": s["item_id"],
                "datetime": s["datetime"],
                "grid": s["grid"],
                "kept_fraction": s["mask_summary"]["kept_fraction"],
            }
            for s in summary["scenes"]
        ],
        "radiometry_audit": audits,
        "comparison_with_reference": reference,
    }


def _compare_with_reference(summary: dict[str, Any], reference_path: str | None) -> dict[str, Any]:
    """Compara a reexecução com um manifesto anterior (se disponível)."""
    path = reference_path
    if path is None:
        default = os.path.join(ARTIFACTS, "latest.json")
        path = default if os.path.exists(default) else None
    if path is None or not os.path.exists(path):
        return {"status": "sem_referencia", "note": "nenhum manifesto anterior encontrado"}

    with open(path, "r", encoding="utf-8") as fh:
        reference = json.load(fh)
    ref_scenes = {s["item_id"]: s for s in reference.get("scenes", [])}
    new_scenes = {s["item_id"]: s for s in summary.get("scenes", [])}

    rows = []
    for item_id, new_scene in sorted(new_scenes.items()):
        old_scene = ref_scenes.get(item_id)
        if old_scene is None:
            rows.append({"item_id": item_id, "status": "ausente_no_manifesto_anterior"})
            continue
        entry: dict[str, Any] = {
            "item_id": item_id,
            "grid_identical": old_scene.get("grid") == new_scene.get("grid"),
            "grid_reference": old_scene.get("grid"),
            "grid_new": new_scene.get("grid"),
            "stats": {},
        }
        for name, stats in new_scene.get("stats", {}).items():
            old_stats = (old_scene.get("stats") or {}).get(name, {})
            entry["stats"][name] = {
                key: {
                    "old": old_stats.get(key),
                    "new": stats.get(key),
                    "delta": (
                        None
                        if old_stats.get(key) is None or stats.get(key) is None
                        else round(float(stats[key]) - float(old_stats[key]), 6)
                    ),
                }
                for key in ("valid_pixels", "valid_fraction", "min", "max", "mean", "median")
            }
        rows.append(entry)
    return {
        "status": "comparado",
        "reference_manifest": path,
        "reference_run_utc": reference.get("run_utc"),
        "scenes": rows,
    }


# --------------------------------------------------------------- checkpoint B


def cmd_scl(args: argparse.Namespace) -> dict[str, Any]:
    """Compara os perfis de máscara SCL (A histórico × B restritivo)."""
    network.configure_tls()
    run = run_id()
    aoi_bbox = (
        geometry_mod.historical_aoi_bbox()
        if args.aoi == "historical"
        else geometry_mod.validation_aoi_bbox()
    )
    client = stac_search.open_catalog()
    items = stac_search.search_items(
        client, aoi_bbox, start=args.start, end=args.end, max_cloud=args.max_cloud
    )
    covering = stac_search.filter_covering(items, aoi_bbox)
    selected = stac_search.select_scenes(covering, max_scenes=args.max_scenes)
    if not selected:
        raise RuntimeError("nenhuma cena cobrindo a AOI encontrada para a comparação SCL")

    preview_dir = os.path.join(PREVIEWS, "scl")
    os.makedirs(preview_dir, exist_ok=True)
    scenes: list[dict[str, Any]] = []
    class_rows: list[dict[str, Any]] = []

    for item in selected:
        scene = read_mod.read_scene_bands(item, aoi_bbox)
        grid = scene["grid"]
        scl = scene["scl"]
        raw = indices_mod.compute_indices(
            scene, keep_override=np.ones(scl.shape, dtype=bool)
        )
        keep_a = mask_mod.keep_mask(scl, "A_historical")
        keep_b = mask_mod.keep_mask(scl, "B_restrictive")

        stats = {}
        for name, values in raw["indices"].items():
            masked_a = mask_mod.masked_index(values, keep_a)
            masked_b = mask_mod.masked_index(values, keep_b)
            stats[name] = {
                "A_historical": _stats_with_degenerate(masked_a, keep_a),
                "B_restrictive": _stats_with_degenerate(masked_b, keep_b),
                "delta": {},
            }
            a = stats[name]["A_historical"]
            b = stats[name]["B_restrictive"]
            for key in ("mean", "median", "std", "min", "max", "p05", "p25", "p75", "p95"):
                va, vb = a.get(key), b.get(key)
                stats[name]["delta"][key] = (
                    None if va is None or vb is None else round(vb - va, 6)
                )
            stats[name]["delta"]["relative_mean"] = (
                None
                if not a.get("mean") or b.get("mean") is None
                else round((b["mean"] - a["mean"]) / a["mean"], 6)
            )
            stats[name]["delta"]["valid_pixels"] = (
                b["valid_pixels"] - a["valid_pixels"]
            )
            stats[name]["delta"]["valid_fraction"] = round(
                b["valid_fraction"] - a["valid_fraction"], 6
            )

        counts = mask_mod.class_counts(scl)
        comparison = mask_mod.compare_profiles(scl)
        per_class = mask_mod.class_index_stats(scl, raw["indices"])

        for entry in counts["classes"]:
            row = {
                "item_id": item.id,
                "datetime": item.properties.get("datetime"),
                "class": entry["class"],
                "class_name": entry["name"],
                "pixels": entry["pixels"],
                "fraction": entry["fraction"],
                "kept_by_A": entry["kept_by_A"],
                "kept_by_B": entry["kept_by_B"],
                "area_km2": entry["pixels"] * PIXEL_AREA_KM2,
            }
            for name, per in per_class.items():
                match = next((p for p in per if p["class"] == entry["class"]), None)
                row[f"{name}_mean"] = match.get("mean") if match else None
                row[f"{name}_median"] = match.get("median") if match else None
                row[f"{name}_p25"] = match.get("p25") if match else None
                row[f"{name}_p75"] = match.get("p75") if match else None
                row[f"{name}_valid_pixels"] = match.get("valid_pixels") if match else 0
            class_rows.append(row)

        date = str(item.properties.get("datetime", ""))[:10]
        png = os.path.join(preview_dir, f"{date}_{item.id}_scl_profiles.png")
        render.render_mask_comparison(
            scl,
            keep_a,
            keep_b,
            grid,
            png,
            title=(
                f"{item.id} — {date} — máscaras SCL A/B "
                f"(EPSG:{str(grid['crs']).split(':')[-1]} @ {grid['res']:.0f} m)"
            ),
        )
        scenes.append(
            {
                "item": item_metadata(item),
                "grid": {
                    "crs": str(grid["crs"]),
                    "res": grid["res"],
                    "width": grid["width"],
                    "height": grid["height"],
                    "transform": list(grid["transform"])[:6],
                },
                "total_pixels": int(scl.size),
                "pixel_area_km2": PIXEL_AREA_KM2,
                "scl_class_counts": counts,
                "profile_comparison": comparison,
                "stats": stats,
                "per_class_index_stats": per_class,
                "preview": png,
            }
        )

    csv_path = os.path.join(REPORTS, f"scl_class_stats_{run}.csv")
    fieldnames = [
        "item_id", "datetime", "class", "class_name", "pixels", "fraction",
        "kept_by_A", "kept_by_B", "area_km2",
    ]
    for name in ("NDVI", "EVI", "NDMI"):
        fieldnames += [
            f"{name}_mean", f"{name}_median", f"{name}_p25", f"{name}_p75",
            f"{name}_valid_pixels",
        ]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in class_rows:
            writer.writerow(row)

    manifest = base_manifest(run, "checkpoint_B_scl_profiles")
    manifest.update(
        {
            "aoi_bbox": aoi_bbox,
            "aoi_kind": args.aoi,
            "search": {
                "datetime": f"{args.start}/{args.end}",
                "max_cloud_cover": args.max_cloud,
                "items_found": len(items),
                "items_covering_aoi": len(covering),
                "scenes_processed": len(selected),
            },
            "profiles": {
                "A_historical": {
                    "excluded_classes": list(mask_mod.profile_classes("A_historical")),
                    "meaning": "regra histórica da PoC (mantém 2, 4, 5, 6)",
                },
                "B_restrictive": {
                    "excluded_classes": list(mask_mod.profile_classes("B_restrictive")),
                    "meaning": "A + exclusão das classes 2 (dark area) e 6 (água)",
                },
                "C_diagnostic": {
                    "meaning": (
                        "Diagnóstico por classe: contagem e estatísticas de cada "
                        "classe SCL separadamente (não é um produto final)."
                    ),
                },
            },
            "scenes": scenes,
            "class_stats_csv": csv_path,
            "decision_note": (
                "Comparação quantitativa e visual produzida; a decisão de política "
                "deixará o Perfil A como referência até que a evidência justifique "
                "mudança explícita."
            ),
        }
    )
    manifest_path = write_manifest(manifest, f"scl_{run}")
    return {
        "ok": True,
        "run_id": run,
        "manifest": manifest_path,
        "class_stats_csv": csv_path,
        "scenes": [
            {
                "item_id": s["item"]["item_id"],
                "datetime": s["item"]["datetime"],
                "valid_A": s["profile_comparison"]["profiles"][0]["valid_fraction"],
                "valid_B": s["profile_comparison"]["profiles"][1]["valid_fraction"],
                "changed_pixels": s["profile_comparison"]["transitions"].get("changed_pixels"),
                "ndvi_mean_A": s["stats"]["NDVI"]["A_historical"]["mean"],
                "ndvi_mean_B": s["stats"]["NDVI"]["B_restrictive"]["mean"],
                "preview": s["preview"],
            }
            for s in scenes
        ],
    }


# --------------------------------------------------------------- checkpoint C


def cmd_geometry(args: argparse.Namespace) -> dict[str, Any]:
    """Valida a geometria municipal oficial e as três AOIs da missão."""
    run = run_id()
    municipality = geometry_mod.load_municipality("maxima")
    geom = municipality["geometry"]

    historical = geometry_mod.historical_aoi_bbox()
    validation = geometry_mod.validation_aoi_bbox()
    mosaic = list(config.MOSAIC_AOI["bbox"])

    hist_report = geometry_mod.bbox_report(geom, historical)
    val_report = geometry_mod.validation_aoi(geom)
    mosaic_report = geometry_mod.bbox_report(geom, mosaic)
    estimate = geometry_mod.operational_estimate(geom)

    geo_dir = os.path.join(ARTIFACTS, "geometry")
    os.makedirs(geo_dir, exist_ok=True)
    from shapely.geometry import mapping

    paths = {}
    paths["municipality"] = write_json(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": municipality["municipality"],
                    "geometry": mapping(geom),
                }
            ],
        },
        os.path.join(geo_dir, "municipality_ibge_5107925.geojson"),
    )
    aois = {
        "historical_aoi": historical,
        "validation_aoi": validation,
        "mosaic_aoi": mosaic,
    }
    paths["aois"] = write_json(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "kind": key,
                        "bbox": bbox,
                        "crs": "EPSG:4326",
                        "note": (
                            config.MOSAIC_AOI["note"]
                            if key == "mosaic_aoi"
                            else (
                                config.VALIDATION_AOI["note"]
                                if key == "validation_aoi"
                                else "AOI técnica histórica da PoC (reprodução)"
                            )
                        ),
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [bbox[0], bbox[1]],
                                [bbox[2], bbox[1]],
                                [bbox[2], bbox[3]],
                                [bbox[0], bbox[3]],
                                [bbox[0], bbox[1]],
                            ]
                        ],
                    },
                }
                for key, bbox in aois.items()
            ],
        },
        os.path.join(geo_dir, "aois.geojson"),
    )

    exterior = list(geom.exterior.coords) if geom.geom_type == "Polygon" else []
    png = os.path.join(PREVIEWS, "geometry", "aoi_geometry.png")
    os.makedirs(os.path.dirname(png), exist_ok=True)
    render.render_geometry_map(
        exterior,
        {"historical_aoi": historical, "validation_aoi": validation},
        png,
        title=(
            "Sorriso-MT (IBGE 5107925) — limite municipal, AOI técnica histórica "
            "e AOI de validação (EPSG:4326)"
        ),
    )

    manifest = base_manifest(run, "checkpoint_C_geometry")
    manifest.update(
        {
            "municipality": {
                k: v for k, v in municipality.items() if k != "geometry"
            },
            "geometries": {
                "historical_aoi": {
                    "kind": "AOI técnica histórica (PoC)",
                    "bbox": historical,
                    "report": hist_report,
                },
                "validation_aoi": {
                    "kind": "AOI de validação",
                    "bbox": validation,
                    "report": val_report,
                },
                "mosaic_aoi": {
                    "kind": "AOI de mosaico (dois tiles)",
                    "bbox": mosaic,
                    "report": mosaic_report,
                    "note": config.MOSAIC_AOI["note"],
                },
            },
            "operational_estimate": estimate,
            "geojson": paths,
            "preview": png,
            "notes": [
                "A bbox histórica NÃO está integralmente dentro do município: "
                f"{100 * (1 - hist_report['inside_fraction']):.2f}% da área fica fora.",
                "Nenhuma das AOIs representa talhão, fazenda ou lavoura.",
                "O município inteiro em 20 m não é processado nesta missão.",
            ],
        }
    )
    manifest_path = write_manifest(manifest, f"geometry_{run}")
    return {
        "ok": True,
        "run_id": run,
        "manifest": manifest_path,
        "municipality": {
            "is_valid": municipality["is_valid"],
            "vertex_count": municipality["vertex_count"],
            "area_km2_geodesic": round(municipality["area_km2_geodesic"], 2),
            "area_km2_equal_area": round(municipality["area_km2_equal_area"], 2),
            "accessed_utc": municipality["accessed_utc"],
        },
        "historical_aoi_intersection": {
            "total_km2": round(hist_report["bbox_area_km2"], 2),
            "inside_km2": round(hist_report["inside_municipality_km2"], 2),
            "outside_km2": round(hist_report["outside_municipality_km2"], 2),
            "inside_fraction": round(hist_report["inside_fraction"], 6),
            "fully_inside": hist_report["fully_inside"],
        },
        "validation_aoi": {
            "area_km2": round(val_report["area_km2_equal_area"], 2),
            "pixels_20m": val_report["pixels_20m_estimate"],
            "inside_municipality": val_report["inside_municipality"],
        },
        "operational_estimate": estimate,
        "preview": png,
    }


# --------------------------------------------------------------- checkpoint D


def _find_tile_pair(items: list[Any]) -> tuple[Any, Any, list[dict[str, Any]]]:
    """Encontra um par de tiles (21LXG/21LXF) da mesma aquisição."""
    by_datetime: dict[str, dict[str, Any]] = {}
    for item in items:
        dt = item.properties.get("datetime")
        tile = item.properties.get("grid:code")
        if not dt or not tile:
            continue
        by_datetime.setdefault(dt, {})[tile] = item
    candidates = []
    for dt, tiles in by_datetime.items():
        if "MGRS-21LXG" in tiles and "MGRS-21LXF" in tiles:
            xg, xf = tiles["MGRS-21LXG"], tiles["MGRS-21LXF"]
            cloud = sum(
                float(x.properties.get("eo:cloud_cover") or 0.0) for x in (xg, xf)
            )
            candidates.append(
                {
                    "datetime": dt,
                    "cloud_sum": cloud,
                    "items": {"MGRS-21LXG": xg, "MGRS-21LXF": xf},
                    "datatake_match": (
                        xg.properties.get("s2:datatake_id")
                        == xf.properties.get("s2:datatake_id")
                    ),
                }
            )
    candidates.sort(key=lambda c: (c["cloud_sum"], c["datetime"]))
    if not candidates:
        raise RuntimeError(
            "nenhum par de tiles 21LXG/21LXF com a mesma data/hora foi encontrado"
        )
    best = candidates[0]
    return best["items"]["MGRS-21LXG"], best["items"]["MGRS-21LXF"], candidates


def cmd_mosaic(args: argparse.Namespace) -> dict[str, Any]:
    """Mosaico real de dois tiles da mesma aquisição (Checkpoint D)."""
    network.configure_tls()
    run = run_id()
    bbox = list(config.MOSAIC_AOI["bbox"])
    client = stac_search.open_catalog()
    items = stac_search.search_items(
        client, bbox, start=args.start, end=args.end, max_cloud=args.max_cloud
    )
    xg, xf, candidates = _find_tile_pair(items)
    if args.datetime:
        matches = [c for c in candidates if c["datetime"].startswith(args.datetime)]
        if not matches:
            raise RuntimeError(f"nenhum par de tiles em {args.datetime}")
        best = matches[0]
        xg, xf = best["items"]["MGRS-21LXG"], best["items"]["MGRS-21LXF"]

    grid = read_mod.scene_grid(xg, bbox)
    scene_xg = read_mod.read_scene_bands(xg, bbox, grid=grid)
    scene_xf = read_mod.read_scene_bands(xf, bbox, grid=grid)

    res_xg = indices_mod.compute_indices(scene_xg)
    res_xf = indices_mod.compute_indices(scene_xf)

    overlap = {}
    for name in ("blue", "red", "nir", "swir"):
        overlap[f"reflectance_{name}"] = mosaic_mod.overlap_stats(
            res_xg["reflectance"][name], res_xf["reflectance"][name]
        )
    for name in ("NDVI", "EVI", "NDMI"):
        overlap[name] = mosaic_mod.overlap_stats(
            res_xg["indices"][name], res_xf["indices"][name]
        )

    mosaic = mosaic_mod.mosaic_index_results(
        [res_xg, res_xf],
        ["NDVI", "EVI", "NDMI"],
        ["MGRS-21LXG", "MGRS-21LXF"],
    )
    scl_mosaic = mosaic_mod.mosaic_categorical(
        [scene_xg["scl"], scene_xf["scl"]], ["MGRS-21LXG", "MGRS-21LXF"], nodata=0
    )
    seam = mosaic_mod.seam_mask(mosaic["sources"]["NDVI"]["source"])

    out_dir = os.path.join(ARTIFACTS, "mosaic")
    os.makedirs(out_dir, exist_ok=True)
    files: dict[str, Any] = {}
    for name in ("NDVI", "EVI", "NDMI"):
        path = os.path.join(out_dir, f"mosaic_{name}.tif")
        read_mod.write_geotiff(
            path,
            mosaic["indices"][name],
            mosaic["grid"],
            tags={
                "SADEN_RULE": "first_valid_wins (21LXG > 21LXF)",
                "SADEN_ITEMS": f"{xg.id},{xf.id}",
                "SADEN_DATETIME": str(xg.properties.get("datetime")),
                "SADEN_COLLECTION": config.COLLECTION,
                "SADEN_SOURCE": config.STAC_URL,
            },
        )
        files[name] = {
            "path": path,
            "bytes": os.path.getsize(path),
            "sha256": read_mod.sha256_file(path),
        }
    source_path = os.path.join(out_dir, "mosaic_source.tif")
    read_mod.write_geotiff(
        source_path,
        mosaic["sources"]["NDVI"]["source"].astype("float32"),
        mosaic["grid"],
        tags={"SADEN_RULE": "0=21LXG, 1=21LXF, -1=sem dado"},
    )
    files["source_map"] = {
        "path": source_path,
        "bytes": os.path.getsize(source_path),
        "sha256": read_mod.sha256_file(source_path),
    }
    scl_path = os.path.join(out_dir, "mosaic_scl.tif")
    read_mod.write_geotiff(
        scl_path, scl_mosaic["data"].astype("float32"), mosaic["grid"], nodata=0.0
    )
    files["scl"] = {
        "path": scl_path,
        "bytes": os.path.getsize(scl_path),
        "sha256": read_mod.sha256_file(scl_path),
    }

    png = os.path.join(PREVIEWS, "mosaic", f"mosaic_{str(xg.properties.get('datetime'))[:10]}.png")
    os.makedirs(os.path.dirname(png), exist_ok=True)
    render.render_mosaic(
        mosaic["indices"],
        mosaic["sources"]["NDVI"]["source"],
        mosaic["grid"],
        png,
        title=(
            f"Mosaico 21LXG + 21LXF — {str(xg.properties.get('datetime'))[:10]} — "
            "regra: primeiro válido vence (21LXG > 21LXF)"
        ),
        source_names=["MGRS-21LXG", "MGRS-21LXF"],
    )

    grid_info = {
        "crs": str(mosaic["grid"]["crs"]),
        "res": mosaic["grid"]["res"],
        "width": mosaic["grid"]["width"],
        "height": mosaic["grid"]["height"],
        "transform": list(mosaic["grid"]["transform"])[:6],
        "bounds": list(mosaic["grid"]["bounds"]),
    }
    manifest = base_manifest(run, "checkpoint_D_mosaic")
    manifest.update(
        {
            "aoi_bbox": bbox,
            "aoi_note": config.MOSAIC_AOI["note"],
            "search": {
                "datetime": f"{args.start}/{args.end}",
                "items_found": len(items),
                "tile_pairs_found": len(candidates),
                "pairs": [
                    {
                        "datetime": c["datetime"],
                        "items": {k: v.id for k, v in c["items"].items()},
                        "datatake_match": c["datatake_match"],
                        "cloud_sum_pct": c["cloud_sum"],
                    }
                    for c in candidates[:20]
                ],
            },
            "items": {
                "MGRS-21LXG": item_metadata(xg),
                "MGRS-21LXF": item_metadata(xf),
            },
            "same_acquisition": {
                "datetime_equal": xg.properties.get("datetime") == xf.properties.get("datetime"),
                "datatake_id_equal": (
                    xg.properties.get("s2:datatake_id")
                    == xf.properties.get("s2:datatake_id")
                ),
                "baseline_equal": (
                    xg.properties.get("s2:processing_baseline")
                    == xf.properties.get("s2:processing_baseline")
                ),
            },
            "grid": grid_info,
            "rule": {
                "name": "first_valid_wins",
                "priority": ["MGRS-21LXG", "MGRS-21LXF"],
                "averaging": False,
                "note": "não há média entre tiles sobrepostos",
            },
            "source_pixels": mosaic["sources"]["NDVI"]["source_pixels"],
            "unfilled_pixels": mosaic["sources"]["NDVI"]["unfilled_pixels"],
            "seam_pixels": int(np.count_nonzero(seam)),
            "overlap_comparison": overlap,
            "files": files,
            "preview": png,
            "limitations": [
                "A diferença entre tiles na faixa de sobreposição é da ordem de "
                "reprocessamento/orbital, não de mudança de cena.",
                "Não é validado aqui o erro absoluto dos índices Sentinel-2.",
            ],
        }
    )
    manifest_path = write_manifest(manifest, f"mosaic_{run}")
    return {
        "ok": True,
        "run_id": run,
        "manifest": manifest_path,
        "items": {k: v["item_id"] for k, v in manifest["items"].items()},
        "datetime": xg.properties.get("datetime"),
        "same_acquisition": manifest["same_acquisition"],
        "grid": grid_info,
        "source_pixels": manifest["source_pixels"],
        "unfilled_pixels": manifest["unfilled_pixels"],
        "seam_pixels": manifest["seam_pixels"],
        "overlap": {
            name: {
                "pixels": stats.get("pixels"),
                "mean_abs_diff": stats.get("mean_absolute_difference"),
                "rmse": stats.get("rmse"),
                "correlation": stats.get("correlation"),
            }
            for name, stats in overlap.items()
        },
        "preview": png,
    }


# --------------------------------------------------------------- checkpoint E


def cmd_timeseries(args: argparse.Namespace) -> dict[str, Any]:
    """Série mensal exploratória 2023–2025 sobre a AOI de validação."""
    network.configure_tls()
    run = run_id()
    bbox = geometry_mod.validation_aoi_bbox()
    client = stac_search.open_catalog()
    months = ts_mod.month_range(args.start, args.end)

    records: list[dict[str, Any]] = []
    monthly_search: list[dict[str, Any]] = []

    for month in months:
        year, mon = int(month[:4]), int(month[5:7])
        next_month = f"{year + 1}-01-01" if mon == 12 else f"{year}-{mon + 1:02d}-01"
        begin = f"{month}-01T00:00:00Z"
        end = f"{next_month}T00:00:00Z"
        search = client.search(
            collections=[config.COLLECTION],
            bbox=bbox,
            datetime=f"{begin}/{end}",
            limit=100,
        )
        found = list(search.items())
        covering = stac_search.filter_covering(found, bbox)
        tile_items = [
            it
            for it in covering
            if it.properties.get("grid:code") == args.tile
        ] or covering
        tile_items.sort(
            key=lambda it: (
                float(it.properties.get("eo:cloud_cover") or 999.0),
                it.id,
            )
        )
        monthly_search.append(
            {
                "month": month,
                "items_found": len(found),
                "items_covering_aoi": len(covering),
                "items_in_tile": len(tile_items),
                "candidate_item_ids": [it.id for it in tile_items[: args.max_candidates]],
            }
        )

        if not tile_items:
            records.append(ts_mod.missing_month_record(month, ts_mod.REASON_NO_SCENE))
            continue

        candidates = []
        for item in tile_items[: args.max_candidates]:
            try:
                scl, _, _ = read_mod.read_scl(item, bbox)
            except Exception as exc:  # pragma: no cover - falha de rede real
                monthly_search[-1].setdefault("errors", []).append(
                    f"{item.id}: {type(exc).__name__}"
                )
                continue
            obstruction = ts_mod.obstruction_fraction(scl)
            candidates.append(
                {
                    "item_id": item.id,
                    "item": item,
                    "obstruction_fraction": obstruction["obstruction_fraction"],
                    "obstructed_pixels": obstruction["obstructed_pixels"],
                    "cloud_cover": item.properties.get("eo:cloud_cover"),
                    "tile": item.properties.get("grid:code"),
                    "datetime": item.properties.get("datetime"),
                    "baseline": item.properties.get("s2:processing_baseline"),
                }
            )
        monthly_search[-1]["candidates"] = [
            {
                "item_id": c["item_id"],
                "obstruction_fraction": round(c["obstruction_fraction"], 6),
                "cloud_cover_tile_pct": c["cloud_cover"],
            }
            for c in candidates
        ]

        best, reason = ts_mod.choose_best_candidate(candidates)
        if best is None:
            records.append(
                ts_mod.missing_month_record(month, ts_mod.REASON_NO_SCENE, len(candidates))
            )
            continue
        if best["obstruction_fraction"] > args.max_obstruction:
            record = ts_mod.missing_month_record(
                month, ts_mod.REASON_ALL_CLOUDY, len(candidates)
            )
            record["best_candidate"] = {
                "item_id": best["item_id"],
                "obstruction_fraction": best["obstruction_fraction"],
            }
            records.append(record)
            continue

        item = best["item"]
        try:
            radiometry.assert_supported_item(item, ("blue", "red", "nir", "swir"))
        except radiometry.UnsupportedProductError as exc:
            record = ts_mod.missing_month_record(month, ts_mod.REASON_UNSUPPORTED, len(candidates))
            record["reason_detail"] = str(exc)
            records.append(record)
            continue

        scene = read_mod.read_scene_bands(item, bbox)
        result = indices_mod.compute_indices(scene)
        stats = {}
        for name, values in result["indices"].items():
            stats[name] = indices_mod.array_stats(values)
            stats[name]["degenerate_pixels"] = int(
                np.count_nonzero(result["keep_mask"])
                - np.count_nonzero(np.isfinite(values))
            )
        out_dir = os.path.join(ARTIFACTS, "timeseries", month)
        os.makedirs(out_dir, exist_ok=True)
        for name in ("NDVI", "EVI", "NDMI"):
            path = os.path.join(out_dir, f"{month}_{name}.tif")
            read_mod.write_geotiff(
                path,
                result["indices"][name],
                result["grid"],
                tags={
                    "SADEN_ITEM_ID": item.id,
                    "SADEN_INDEX": name,
                    "SADEN_MONTH": month,
                    "SADEN_COLLECTION": config.COLLECTION,
                    "SADEN_SOURCE": config.STAC_URL,
                },
            )
        records.append(
            ts_mod.observed_month_record(
                month=month,
                item_id=item.id,
                datetime_iso=str(item.properties.get("datetime")),
                tile=item.properties.get("grid:code"),
                baseline=item.properties.get("s2:processing_baseline"),
                cloud_cover=item.properties.get("eo:cloud_cover"),
                obstruction=best["obstruction_fraction"],
                profile="A_historical",
                indices=stats,
                scene_count=1,
                extra={
                    "grid": {
                        "crs": str(result["grid"]["crs"]),
                        "res": result["grid"]["res"],
                        "width": result["grid"]["width"],
                        "height": result["grid"]["height"],
                        "transform": list(result["grid"]["transform"])[:6],
                    },
                    "mask_summary": result["mask_summary"],
                    "tile_chosen": args.tile,
                },
            )
        )

    rows = ts_mod.series_rows(records, area_per_pixel_km2=PIXEL_AREA_KM2)
    csv_path = os.path.join(REPORTS, f"timeseries_mensal_{args.start}_{args.end}.csv")
    ts_mod.write_series_csv(rows, csv_path)
    png = os.path.join(
        PREVIEWS, "timeseries", f"series_{args.start}_{args.end}.png"
    )
    os.makedirs(os.path.dirname(png), exist_ok=True)
    render.render_timeseries(
        records,
        png,
        title=(
            f"Série Sentinel-2 {args.start} … {args.end} — AOI de validação "
            f"({args.tile}) — lacunas são meses sem observação utilizável"
        ),
    )

    summary = ts_mod.series_summary(records)
    manifest = base_manifest(run, "checkpoint_E_timeseries")
    manifest.update(
        {
            "aoi": {
                "kind": "validation_aoi",
                "bbox": bbox,
                "note": config.VALIDATION_AOI["note"],
            },
            "period": {"start": args.start, "end": args.end, "months": len(months)},
            "selection": {
                "tile_preference": args.tile,
                "criterion": (
                    "menor fração obstruída sobre a AOI (classes SCL de "
                    "nuvem/sombra/saturado/nodata); desempate por nuvem do tile "
                    "e depois por item_id"
                ),
                "max_obstruction": args.max_obstruction,
                "max_candidates_per_month": args.max_candidates,
                "cloud_cover_field": (
                    "eo:cloud_cover é percentual do tile inteiro (0–100), não "
                    "fração; usado apenas como critério de desempate"
                ),
                "mask_profile": "A_historical",
            },
            "monthly_search": monthly_search,
            "summary": summary,
            "records": records,
            "csv": csv_path,
            "preview": png,
            "rasters_dir": os.path.join(ARTIFACTS, "timeseries"),
            "notes": [
                "Meses sem observação permanecem vazios: nenhum valor foi "
                "interpolado, repetido ou preenchido.",
                "A cobertura da AOI é total em todas as cenas processadas (o AOI "
                "está dentro do footprint do tile);-scenes parciais não entram.",
                "Comparabilidade: mesma máscara, mesma grade e mesma conversão "
                "radiométrica em todos os meses; baselines 05.09/05.10/05.11 "
                "com scale 0.0001 e offset -0.1.",
            ],
        }
    )
    manifest_path = write_manifest(manifest, f"timeseries_{run}")
    return {
        "ok": True,
        "run_id": run,
        "manifest": manifest_path,
        "csv": csv_path,
        "preview": png,
        "summary": summary,
    }


# ------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SADEN V2.1 — validação geoespacial (checkpoints A–E)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_repro = sub.add_parser("repro", help="Checkpoint A: reexecuta e audita a PoC")
    p_repro.add_argument("--start", default=config.DEFAULT_START)
    p_repro.add_argument("--end", default=config.DEFAULT_END)
    p_repro.add_argument("--max-cloud", type=float, default=config.DEFAULT_MAX_CLOUD)
    p_repro.add_argument("--max-scenes", type=int, default=config.DEFAULT_MAX_SCENES)
    p_repro.add_argument("--reference", default=None, help="manifesto anterior para comparar")
    p_repro.set_defaults(func=cmd_repro)

    p_scl = sub.add_parser("scl", help="Checkpoint B: comparação de máscaras SCL")
    p_scl.add_argument("--aoi", choices=["historical", "validation"], default="historical")
    p_scl.add_argument("--start", default=config.DEFAULT_START)
    p_scl.add_argument("--end", default=config.DEFAULT_END)
    p_scl.add_argument("--max-cloud", type=float, default=config.DEFAULT_MAX_CLOUD)
    p_scl.add_argument("--max-scenes", type=int, default=config.DEFAULT_MAX_SCENES)
    p_scl.set_defaults(func=cmd_scl)

    p_geom = sub.add_parser("geometry", help="Checkpoint C: geometria municipal e AOIs")
    p_geom.set_defaults(func=cmd_geometry)

    p_mosaic = sub.add_parser("mosaic", help="Checkpoint D: mosaico de dois tiles")
    p_mosaic.add_argument("--start", default="2023-01-01")
    p_mosaic.add_argument("--end", default="2025-12-31")
    p_mosaic.add_argument("--max-cloud", type=float, default=100.0)
    p_mosaic.add_argument("--datetime", default=None, help="filtra o par de tiles por data")
    p_mosaic.set_defaults(func=cmd_mosaic)

    p_series = sub.add_parser("timeseries", help="Checkpoint E: série mensal 2023–2025")
    p_series.add_argument("--start", default="2023-01")
    p_series.add_argument("--end", default="2025-12")
    p_series.add_argument("--tile", default="MGRS-21LXG")
    p_series.add_argument("--max-obstruction", type=float, default=0.5)
    p_series.add_argument("--max-candidates", type=int, default=4)
    p_series.set_defaults(func=cmd_timeseries)

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
