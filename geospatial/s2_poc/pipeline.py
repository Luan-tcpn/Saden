"""Orquestração da prova de conceito: descoberta → leitura → índices → produtos.

Este módulo **não** é usado pela V1. Tudo é gravado em `geospatial/artifacts/`
(ignorado pelo Git); apenas prévias pequenas vão para `geospatial/previews/`.
"""

from __future__ import annotations

import csv
import json
import os
import platform
from datetime import datetime, timezone
from typing import Any

import numpy as np

from . import aoi as aoi_mod
from . import config, indices as indices_mod, network, read, render, stac_search


def _jsonable(value: Any) -> Any:
    """Converte tipos numpy/datetime para JSON estrito (NaN/inf → null)."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if hasattr(value, "item") and callable(value.item):
        try:
            value = value.item()
        except Exception:  # pragma: no cover - tipos exóticos
            return str(value)
    if isinstance(value, float):
        return value if value == value and abs(value) != float("inf") else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def library_versions() -> dict[str, str]:
    import matplotlib
    import numpy
    import pystac_client
    import rasterio

    return {
        "python": platform.python_version(),
        "pystac-client": pystac_client.__version__,
        "rasterio": rasterio.__version__,
        "gdal": rasterio.__gdal_version__,
        "numpy": numpy.__version__,
        "matplotlib": matplotlib.__version__,
    }


def resolve_aoi() -> dict[str, Any]:
    """AOI técnico derivado da malha oficial do IBGE (com proveniência)."""
    geojson = aoi_mod.fetch_municipality_geojson()
    return aoi_mod.build_aoi(geojson)


def discover(
    aoi: dict[str, Any],
    start: str = config.DEFAULT_START,
    end: str = config.DEFAULT_END,
    max_cloud: float = config.DEFAULT_MAX_CLOUD,
    max_scenes: int = config.DEFAULT_MAX_SCENES,
) -> dict[str, Any]:
    """Descobre cenas e devolve tudo que é necessário para a proveniência."""
    client = stac_search.open_catalog()
    collection = stac_search.collection_metadata(client)
    found = stac_search.search_items(
        client, aoi["bbox"], start=start, end=end, max_cloud=max_cloud
    )
    covering = stac_search.filter_covering(found, aoi["bbox"])
    selected = stac_search.select_scenes(covering, max_scenes=max_scenes)
    return {
        "catalog": {
            "url": config.STAC_URL,
            "collection": config.COLLECTION,
            "metadata": collection,
        },
        "search": {
            "datetime": f"{start}/{end}",
            "max_cloud_cover": max_cloud,
            "items_found": len(found),
            "items_covering_aoi": len(covering),
            "scenes_selected": len(selected),
        },
        "items_found": found,
        "items_covering": covering,
        "selected": selected,
        "provenance": [
            stac_search.item_provenance(it, aoi["bbox"]) for it in selected
        ],
    }


def process_scene(
    item: Any,
    aoi: dict[str, Any],
    artifacts_dir: str,
    previews_dir: str | None = None,
    write_preview: bool = True,
) -> dict[str, Any]:
    """Processa uma cena e grava GeoTIFFs (+ prévia opcional)."""
    scene = read.read_scene_bands(item, aoi["bbox"])
    result = indices_mod.compute_indices(scene)
    grid = result["grid"]

    files: dict[str, Any] = {}
    for name in ("NDVI", "EVI", "NDMI"):
        path = os.path.join(artifacts_dir, f"{item.id}_{name}.tif")
        read.write_geotiff(
            path,
            result["indices"][name],
            grid,
            tags={
                "SADEN_ITEM_ID": item.id,
                "SADEN_INDEX": name,
                "SADEN_COLLECTION": config.COLLECTION,
                "SADEN_SOURCE": config.STAC_URL,
                "SADEN_SCL_EXCLUDED": ",".join(
                    str(c) for c in config.SCL_BAD_CLASSES
                ) + f",{config.SCL_UNCLASSIFIED}",
            },
        )
        files[name] = {
            "path": path,
            "bytes": os.path.getsize(path),
            "sha256": read.sha256_file(path),
        }

    preview_path = None
    if write_preview and previews_dir:
        dt = str(item.properties.get("datetime", ""))[:10]
        preview_path = os.path.join(
            previews_dir, f"{dt}_{item.id}_indices.png"
        )
        render.render_indices(
            result["indices"],
            grid,
            preview_path,
            title=f"{item.id} — {dt} — EPSG:{str(grid['crs']).split(':')[-1]} @ {grid['res']:.0f} m",
        )

    return {
        "item_id": item.id,
        "datetime": item.properties.get("datetime"),
        "cloud_cover": item.properties.get("eo:cloud_cover"),
        "platform": item.properties.get("platform"),
        "grid": {
            "crs": str(grid["crs"]),
            "res": grid["res"],
            "width": grid["width"],
            "height": grid["height"],
            "bounds": grid["bounds"],
            "transform": list(grid["transform"])[:6],
        },
        "files": files,
        "preview": preview_path,
        "stats": result["stats"],
        "mask_summary": result["mask_summary"],
    }


CSV_COLUMNS = [
    "date",
    "item_id",
    "index",
    "total_pixels",
    "valid_pixels",
    "valid_fraction",
    "min",
    "max",
    "mean",
    "median",
    "p05",
    "p95",
    "std",
    "out_of_range_pixels",
    "degenerate_pixels",
]


def write_temporal_csv(rows: list[dict[str, Any]], path: str) -> str:
    """Série temporal tabular (uma linha por cena × índice)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in CSV_COLUMNS})
    return path


def run(
    artifacts_dir: str,
    previews_dir: str | None = None,
    start: str = config.DEFAULT_START,
    end: str = config.DEFAULT_END,
    max_cloud: float = config.DEFAULT_MAX_CLOUD,
    max_scenes: int = config.DEFAULT_MAX_SCENES,
    write_preview: bool = True,
    check_only: bool = False,
) -> dict[str, Any]:
    """Executa a PoC completa (ou apenas a descoberta, com ``check_only``)."""
    network.configure_tls()
    started = datetime.now(timezone.utc)
    aoi = resolve_aoi()
    discovery = discover(
        aoi, start=start, end=end, max_cloud=max_cloud, max_scenes=max_scenes
    )

    summary: dict[str, Any] = {
        "run_utc": started.isoformat(),
        "mode": "check-only" if check_only else "full",
        "versions": library_versions(),
        "catalog": discovery["catalog"],
        "search": discovery["search"],
        "aoi": aoi,
        "parameters": {
            "target_res_m": config.TARGET_RES_M,
            "assets": config.ASSETS,
            "scl_bad_classes": list(config.SCL_BAD_CLASSES),
            "scl_unclassified": config.SCL_UNCLASSIFIED,
            "continuous_resampling": "average",
            "categorical_resampling": "nearest",
            "reflectance_conversion": "DN * scale + offset",
            "formulas": config.FORMULAS,
            "nodata": 0,
        },
        "items": discovery["provenance"],
        "scenes": [],
        "artifacts": {"geotiffs": [], "previews": [], "csv": None, "manifest": None},
        "warnings": [],
        "limitations": [
            "AOI é uma janela técnica de 0,10° dentro do município; não é talhão, "
            "fazenda nem amostra representativa da produção municipal.",
            "Índices de vegetação não medem produtividade nem preço; nenhuma "
            "inferência agronômica ou econômica é feita nesta etapa.",
            "Máscara SCL reduz contaminação por nuvem, mas não elimina nuvem fina "
            "não classificada nem efeitos de aerossol/sombra residual.",
        ],
    }

    if not check_only and not discovery["selected"]:
        raise RuntimeError(
            "nenhuma cena cobrindo o AOI foi encontrada na janela/limite informados"
        )

    if check_only:
        summary["artifacts"]["manifest"] = None
        return summary

    os.makedirs(artifacts_dir, exist_ok=True)
    csv_rows: list[dict[str, Any]] = []
    for item in discovery["selected"]:
        scene_out = process_scene(
            item,
            aoi,
            artifacts_dir=artifacts_dir,
            previews_dir=previews_dir,
            write_preview=write_preview,
        )
        summary["scenes"].append(scene_out)
        for name in ("NDVI", "EVI", "NDMI"):
            summary["artifacts"]["geotiffs"].append(scene_out["files"][name]["path"])
            stats = scene_out["stats"][name]
            csv_rows.append(
                {
                    "date": str(scene_out["datetime"])[:10],
                    "item_id": scene_out["item_id"],
                    "index": name,
                    **{k: stats.get(k) for k in CSV_COLUMNS if k in stats},
                }
            )
        if scene_out["preview"]:
            summary["artifacts"]["previews"].append(scene_out["preview"])
        if scene_out["mask_summary"]["kept_fraction"] < 0.5:
            summary["warnings"].append(
                f"{scene_out['item_id']}: apenas "
                f"{100 * scene_out['mask_summary']['kept_fraction']:.1f}% dos pixels "
                "permaneceram válidos após as máscaras."
            )

    csv_path = os.path.join(artifacts_dir, "series_temporal.csv")
    summary["artifacts"]["csv"] = write_temporal_csv(csv_rows, csv_path)

    manifest_path = os.path.join(
        artifacts_dir, f"run_{started.strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(_jsonable(summary), fh, ensure_ascii=False, indent=2)
    # Cópia estável para consumo manual/reprodutibilidade.
    latest_path = os.path.join(artifacts_dir, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as fh:
        json.dump(_jsonable(summary), fh, ensure_ascii=False, indent=2)
    summary["artifacts"]["manifest"] = manifest_path
    summary["artifacts"]["latest"] = latest_path
    return summary
