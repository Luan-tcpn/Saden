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


def mask_variants(crop2020: np.ndarray, crop2021: np.ndarray) -> dict[str, np.ndarray]:
    """Quatro máscaras agrícolas a partir de dois mapas de lavoura (booleanos).

    ``crop2020``/``crop2021`` são máscaras de *cropland* (classe 40 do WorldCover)
    já reamostradas para a grade de trabalho — não as classes brutas.
    """
    crop20 = np.asarray(crop2020, dtype=bool)
    crop21 = np.asarray(crop2021, dtype=bool)
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


def processing_index(item_id: str) -> str | None:
    """Índice de reprocessamento do identificador (``..._0_L2A`` → ``0``)."""
    parts = str(item_id or "").split("_")
    for part in parts:
        if part.isdigit():
            return part
    return None


def find_item_by_id(client: Any, item_id: str) -> tuple[Any | None, str | None]:
    """Busca o item exato pelo identificador (nas coleções C1 e original)."""
    for collection in ("sentinel-2-c1-l2a", "sentinel-2-l2a"):
        found = list(
            client.search(collections=[collection], ids=[str(item_id)], limit=5).items()
        )
        if found:
            return found[0], collection
    return None, None


def find_complementary_item(
    client: Any,
    date: str,
    tile: str,
    reference_item_id: str | None = None,
) -> Any | None:
    """Item do tile complementar na mesma data, com reprocessamento pareado.

    Quando o item de referência existe (``..._0_L2A``), procura-se o item do
    outro tile **com o mesmo índice de reprocessamento** — assim as cenas do
    mosaico pertencem à mesma passagem e ao mesmo processamento.
    """
    wanted = processing_index(reference_item_id) if reference_item_id else None
    for collection in ("sentinel-2-c1-l2a", "sentinel-2-l2a"):
        candidates = [
            candidate
            for candidate in client.search(
                collections=[collection],
                bbox=grid_bbox_municipality(),
                datetime=f"{date}T00:00:00Z/{date}T23:59:59Z",
                limit=30,
            ).items()
            if pcatalog.tile_code(candidate) == tile
        ]
        if not candidates:
            continue
        if wanted is not None:
            for candidate in candidates:
                if processing_index(candidate.id) == wanted:
                    return candidate
        return candidates[0]
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


def _process_block(
    grid: dict[str, Any],
    block: dict[str, Any],
    masks: dict[str, np.ndarray],
    item_xg: Any,
    item_xf: Any | None,
    profile: dict[str, Any],
    municipality_cells: np.ndarray,
) -> dict[str, Any]:
    """Processa um bloco: NDVI, contagem agrícola e obstrução."""
    union = masks["broad"]
    box = _cells_bbox(union)
    if box is None:
        return {"empty": True}
    sub = _sub_block(block, box)
    lat_min, _lat_max = _block_lat_range(grid, sub)
    need_xf = lat_min < TILE_XF_MAX_LAT
    red, nir, scl, used = _read_mosaic(
        grid, sub, item_xg, item_xf if need_xf else None
    )
    if red is None or np.all(np.isnan(red)):
        return {"empty": True, "tiles": used}
    ndvi = muni.ndvi_from_reflectance(
        red, nir, float(profile["scale"]), float(profile["offset"])
    )
    valid = muni.scl_keep(scl) & np.isfinite(ndvi)
    inside = municipality_cells[
        sub["row_off"] : sub["row_off"] + sub["height"],
        sub["col_off"] : sub["col_off"] + sub["width"],
    ]
    from s2_poc.timeseries import obstruction_fraction

    block_obstruction = obstruction_fraction(scl)
    per_variant: dict[str, dict[str, Any]] = {}
    agricultural_counts: dict[str, int] = {}
    for variant in MASK_VARIANTS:
        variant_mask = masks[variant][
            box[0] : box[0] + box[2], box[1] : box[1] + box[3]
        ]
        agricultural = variant_mask & inside
        agricultural_counts[variant] = int(agricultural.sum())
        per_variant[variant] = muni.accumulate_ndvi(ndvi, valid, agricultural)
    return {
        "empty": False,
        "tiles": used,
        "per_variant": per_variant,
        "agricultural_counts": agricultural_counts,
        "obstruction_fraction": float(block_obstruction["obstruction_fraction"]),
        "inside_count": int(inside.sum()),
    }


def process_month(
    grid: dict[str, Any],
    blocks: list[dict[str, Any]],
    item_xg: Any,
    item_xf: Any | None,
    profile: dict[str, Any],
    variant_masks: dict[str, dict[tuple[int, int], np.ndarray]],
    municipality_cells: np.ndarray,
    workers: int = 4,
) -> dict[str, Any]:
    """Processa um mês: NDVI sobre a área agrícola, por variante de máscara.

    Para cada variante são acumulados: as estatísticas do NDVI válido, o total
    de pixels agrícolas (denominador da **cobertura**) e a fração obstruída
    ponderada pela área agrícola de cada bloco.

    Os blocos são processados em paralelo (``workers`` threads): a leitura de
    COG remoto é limitada por I/O, não por CPU. A ordem de acumulação é a
    ordem dos blocos, de modo que o resultado numérico é idêntico ao
    sequencial.
    """
    from concurrent.futures import ThreadPoolExecutor

    accumulators: dict[str, list[dict[str, Any]]] = {v: [] for v in MASK_VARIANTS}
    agricultural_counts: dict[str, int] = {v: 0 for v in MASK_VARIANTS}
    obstruction_weighted: list[tuple[float, int]] = []
    tiles_used: set[str] = set()

    todo: list[tuple[dict[str, Any], dict[str, np.ndarray]]] = []
    for block in blocks:
        masks = variant_masks.get((block["row_off"], block["col_off"]))
        if masks is None:
            continue
        todo.append((block, masks))

    def work(item):
        block, masks = item
        return _process_block(
            grid,
            block,
            masks,
            item_xg,
            item_xf,
            profile,
            municipality_cells,
        )

    if workers > 1 and len(todo) > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(work, todo))
    else:
        results = [work(item) for item in todo]

    for result in results:
        tiles_used.update(result.get("tiles") or [])
        if result.get("empty"):
            continue
        for variant in MASK_VARIANTS:
            accumulators[variant].append(result["per_variant"][variant])
            agricultural_counts[variant] += result["agricultural_counts"][variant]
        obstruction_weighted.append(
            (result["obstruction_fraction"], result["inside_count"])
        )

    total_obstruction_weight = sum(weight for _frac, weight in obstruction_weighted)
    results: dict[str, Any] = {"tiles_used": sorted(tiles_used), "variants": {}}
    for variant, accs in accumulators.items():
        merged = muni.merge_accumulators(accs)
        total_agricultural = agricultural_counts[variant]
        merged["agricultural_pixels"] = total_agricultural
        merged["valid_fraction"] = (
            merged["count"] / total_agricultural if total_agricultural else None
        )
        merged["obstruction_fraction"] = (
            float(
                sum(frac * weight for frac, weight in obstruction_weighted)
                / total_obstruction_weight
            )
            if total_obstruction_weight
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
