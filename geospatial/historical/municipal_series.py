"""Série municipal mensal de NDVI sobre a área agrícola (V2.5).

Mudanças em relação à V2.4 (busca de eficiência e de qualidade):

1. **Máscaras em variantes**: a mesma leitura do ESA WorldCover (2020 e 2021)
   gera quatro máscaras — ``wc2020``, ``wc2021``, ``stable`` (interseção) e
   ``broad`` (união) — enabling análise de sensibilidade sem novo download.
2. **Leitura só da janela agrícola**: dentro de cada bloco, o Sentinel-2 é lido
   apenas no *bounding box* dos pixels agrícolas (economiza ~50% da banda) e
   apenas do tile que cobre aquele bloco (``21LXF`` só onde a latitude exige).
3. **Processamento retomável**: meses já concluídos são identified no CSV e
   não são reprocessados; cada mês é persistido ao final.
4. **Rastreabilidade por mês**: item, tile, perfil radiométrico, versão da
   máscara, cobertura e fração obstruída ficam registrados.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from typing import Any, Iterable

import numpy as np

from s2_poc import config, indices as indices_mod, mask as mask_mod, network, read
from . import landuse as lu
from . import municipal as muni
from . import pcatalog, radiometry as radio, series as series_mod

MASK_VARIANTS = ("wc2020", "wc2021", "stable", "broad")

# Cobertura dos tiles MGRS (latitudes de borda) — define qual tile ler.
TILE_XG_MIN_LAT = -12.750833
TILE_XF_MAX_LAT = -12.657006
TILE_XG = "MGRS-21LXG"
TILE_XF = "MGRS-21LXF"

MONTHLY_FIELDS = [
    "month",
    "year",
    "item_id",
    "catalog",
    "baseline",
    "radiometry_profile",
    "tiles_used",
    "mask_variant",
    "mask_year",
    "agricultural_pixels",
    "valid_pixels",
    "valid_fraction",
    "ndvi_mean",
    "ndvi_median",
    "ndvi_std",
    "ndvi_p05",
    "ndvi_p95",
    "obstruction_fraction",
    "scenes",
    "blocks",
    "source_manifest",
]


def mask_variants(wc2020: np.ndarray, wc2021: np.ndarray) -> dict[str, np.ndarray]:
    """Quatro máscaras agrícolas a partir das duas classificações anuais."""
    crop20 = wc2020 == lu.WORLDCOVER_CROPLAND
    crop21 = wc2021 == lu.WORLDCOVER_CROPLAND
    return {
        "wc2020": crop20,
        "wc2021": crop21,
        "stable": crop20 & crop21,
        "broad": crop20 | crop21,
    }


def _cells_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """Bounding box (row0, col0, rows, cols) dos pixels verdadeiros."""
    if not mask.any():
        return None
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    row0, row1 = int(rows[0]), int(rows[-1]) + 1
    col0, col1 = int(cols[0]), int(cols[-1]) + 1
    return row0, col0, row1 - row0, col1 - col0


def _sub_block(block: dict[str, Any], box: tuple[int, int, int, int]) -> dict[str, Any]:
    row0, col0, rows, cols = box
    return {
        "row_off": block["row_off"] + row0,
        "col_off": block["col_off"] + col0,
        "height": rows,
        "width": cols,
    }


def _block_lat_range(grid: dict[str, Any], block: dict[str, Any]) -> tuple[float, float]:
    from rasterio.warp import transform_bounds

    bounds = muni.block_window(grid, block)["bounds"]
    lat_bounds = transform_bounds(
        grid["crs"], "EPSG:4326", *bounds, densify_pts=21
    )
    return float(lat_bounds[1]), float(lat_bounds[3])


def find_tile_item(client: Any, collection: str, date: str, tile: str) -> Any | None:
    """Localiza o item de um tile numa data de aquisição."""
    for candidate in client.search(
        collections=[collection],
        bbox=grid_bbox_municipality(),
        datetime=f"{date}T00:00:00Z/{date}T23:59:59Z",
        limit=30,
    ).items():
        if pcatalog.tile_code(candidate) == tile:
            return candidate
    return None


def grid_bbox_municipality() -> list[float]:
    return [-56.1167, -13.6661, -55.0851, -11.7216]


def _read_mosaic(
    grid: dict[str, Any],
    sub: dict[str, Any],
    item_xg: Any | None,
    item_xf: Any | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Lê B04/B08/SCL do(s) tile(s) e monta o NDVI (first_valid_wins)."""
    red = nir = scl = None
    tiles_used: list[str] = []
    for item, tile in ((item_xg, TILE_XG), (item_xf, TILE_XF)):
        if item is None:
            continue
        red_i = muni.read_block(
            series_mod.asset_href_for(item, "red"),
            grid,
            sub,
            resampling=read.Resampling.average,
            nodata=np.nan,
            dtype="float32",
        )
        nir_i = muni.read_block(
            series_mod.asset_href_for(item, "nir"),
            grid,
            sub,
            resampling=read.Resampling.average,
            nodata=np.nan,
            dtype="float32",
        )
        scl_i = muni.read_block(
            series_mod.asset_href_for(item, "scl"),
            grid,
            sub,
            resampling=read.Resampling.nearest,
            nodata=0,
            dtype="uint8",
        )
        if red is None:
            red, nir, scl = red_i, nir_i, scl_i
            tiles_used.append(tile)
        else:
            gap = ~np.isfinite(red) | (scl == 0)
            red = np.where(gap, red_i, red)
            nir = np.where(gap, nir_i, nir)
            scl = np.where(gap, scl_i, scl)
            tiles_used.append(tile)
    if red is None:
        shape = (sub["height"], sub["width"])
        return (
            np.full(shape, np.nan, dtype="float32"),
            np.full(shape, np.nan, dtype="float32"),
            np.zeros(shape, dtype="uint8"),
            [],
        )
    return red, nir, scl, tiles_used


def process_month(
    grid: dict[str, Any],
    blocks: list[dict[str, Any]],
    item_xg: Any,
    item_xf: Any | None,
    profile: dict[str, Any],
    variant_masks: dict[str, dict[tuple[int, int], np.ndarray]],
    municipality_cells: np.ndarray,
) -> dict[str, Any]:
    """Processa um mês: NDVI sobre a área agrícola, por variante de máscara."""
    accumulators: dict[str, list[dict[str, Any]]] = {v: [] for v in MASK_VARIANTS}
    obstruction_acc: list[dict[str, Any]] = []
    tiles_used: set[str] = set()

    for block in blocks:
        masks = variant_masks.get((block["row_off"], block["col_off"]))
        if masks is None:
            continue
        union = masks["broad"]
        box = _cells_bbox(union)
        if box is None:
            continue
        sub = _sub_block(block, box)
        lat_min, _lat_max = _block_lat_range(grid, sub)
        need_xf = lat_min < TILE_XF_MAX_LAT
        red, nir, scl, used = _read_mosaic(
            grid, sub, item_xg, item_xf if need_xf else None
        )
        tiles_used.update(used)
        if red is None or np.all(np.isnan(red)):
            continue
        ndvi = muni.ndvi_from_reflectance(
            red, nir, float(profile["scale"]), float(profile["offset"])
        )
        valid = muni.scl_keep(scl) & np.isfinite(ndvi)
        inside = municipality_cells[
            sub["row_off"] : sub["row_off"] + sub["height"],
            sub["col_off"] : sub["col_off"] + sub["width"],
        ]
        from s2_poc.timeseries import obstruction_fraction

        obstruction_acc.append(obstruction_fraction(scl))
        for variant in MASK_VARIANTS:
            variant_mask = masks[variant][
                box[0] : box[0] + box[2], box[1] : box[1] + box[3]
            ]
            accumulators[variant].append(
                muni.accumulate_ndvi(ndvi, valid, variant_mask & inside)
            )

    results: dict[str, Any] = {"tiles_used": sorted(tiles_used), "variants": {}}
    for variant, accs in accumulators.items():
        merged = muni.merge_accumulators(accs)
        merged["obstruction_fraction"] = (
            float(np.mean([o["obstruction_fraction"] for o in obstruction_acc]))
            if obstruction_acc
            else None
        )
        results["variants"][variant] = merged
    return results


def load_completed(csv_path: str) -> set[tuple[str, str]]:
    """Meses (mês, variante) já concluídos — base da retomada."""
    done: set[tuple[str, str]] = set()
    if not os.path.exists(csv_path):
        return done
    with open(csv_path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            done.add((str(row.get("month")), str(row.get("mask_variant"))))
    return done


def write_rows(rows: list[dict[str, Any]], path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=MONTHLY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path
