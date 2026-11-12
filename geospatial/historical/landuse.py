"""Uso do solo na AOI de validação — Checkpoint B.

Fontes avaliadas em 2026-11-11:

* **MapBiomas** (Brasil/INPE, CC-BY-SA): a página oficial informa que *“a
  função de baixar mapas está temporariamente suspensa”* e que o acesso
  passou a ser pelos assets do Google Earth Engine (exige conta). O download
  de GeoTIFF da Coleção 4 (10 m) **não** foi possível neste ambiente — os
  endereços públicos testados retornam 404 e a assinatura do PC/COG exigiu
  credencial. As **legendas oficiais** (PDF/CSV) são públicas e foram
  obtidas e conferidas (ver ``MAPBIOMAS_LEGEND``).
* **ESA WorldCover 10 m v200 (2021) e v100 (2020)**: COGs públicos, sem
  chave, na AWS — acessíveis e usados como camada **cropland** (classe 40)
  para 2020 e 2021.

Limites que valem para todas as conclusões:

* WorldCover **não** separa lavoura temporária de perene e **não** identifica
  soja/milho;
* MapBiomas não pôde ser acquired, portanto não há máscara MapBiomas por
  pixel nem série anual de uso do solo;
* a classe SCL 5 (“solo exposto”) **não** é identificação de lavoura.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import numpy as np

# --------------------------------------------------------------- legendas

# Legenda oficial MapBiomas 10 m (Coleção 4), conferida no PDF publicado
# (Descricao-detalhada-de-legenda-Cobertura-10m-Col4.pdf), 2026-11-11.
MAPBIOMAS_LEGEND = {
    "source": (
        "MapBiomas Brasil — Cobertura 10m Coleção 4 (legenda oficial em PDF); "
        "https://brasil.mapbiomas.org/downloads/codigos-de-legenda/"
    ),
    "level3": {
        "1.1": "Formação Florestal",
        "1.3": "Formação Savânica",
        "3.1": "Pastagem",
        "3.2.1": "Lavoura Temporária",
        "3.2.2": "Lavoura Perene",
        "3.4": "Mosaico de Usos",
        "4": "Área não vegetada",
        "5": "Corpo D'água",
    },
    "level1_2_collection11": {
        "3": "Formação Florestal",
        "4": "Formação Savânica",
        "15": "Pastagem",
        "21": "Mosaico de Usos",
        "25": "Outras áreas não vegetadas",
    },
    "collection4_n3_temporary_crop_code": 19,
    "note": (
        "A Coleção 4 (10 m) usa o código 19 para 'Lavoura Temporária' "
        "(3.2.1). A camada não pôde ser adquirida neste ambiente; a legenda "
        "foi conferida e fica registrada para uso futuro."
    ),
}

# ESA WorldCover 10 m — classes oficiais (PUM v2.0).
WORLDCOVER_CLASSES = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Barren / sparse vegetation",
    70: "Snow and ice",
    80: "Open water",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
}
WORLDCOVER_CROPLAND = 40
WORLDCOVER_URLS = {
    2021: (
        "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
        "ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
    ),
    2020: (
        "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v100/2020/map/"
        "ESA_WorldCover_10m_2020_v100_{tile}_Map.tif"
    ),
}


def worldcover_tile_name(bbox: list[float]) -> str:
    """Nome da tesela WorldCover (3° × 3°) que contém a bbox."""
    lat_min, lat_max = bbox[1], bbox[3]
    lon_min, lon_max = bbox[0], bbox[2]
    lat_band = int(np.floor(lat_min / 3.0) * 3)
    lon_band = int(np.floor(lon_min / 3.0) * 3)
    lat_prefix = "N" if lat_band >= 0 else "S"
    lon_prefix = "E" if lon_band >= 0 else "W"
    return f"{lat_prefix}{abs(lat_band):02d}{lon_prefix}{abs(lon_band):03d}"


def read_worldcover_year(
    year: int,
    bbox: list[float],
    tile: str | None = None,
) -> dict[str, Any]:
    """Lê a classe WorldCover da bbox (janela remota, sem baixar o tile inteiro)."""
    import rasterio
    from rasterio.windows import from_bounds

    from s2_poc import network

    network.configure_tls()
    tile = tile or worldcover_tile_name(bbox)
    url = WORLDCOVER_URLS[year].format(tile=tile)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(url) as ds:
            window = from_bounds(*bbox, transform=ds.transform)
            data = ds.read(1, window=window)
            meta = {
                "url": url,
                "crs": str(ds.crs),
                # o transform deve ser o da JANELA recortada (não o do
                # dataset inteiro) — sem isso o mapeamento célula→pixel erra
                "transform": list(window_transform(ds.transform, window))[:6],
                "res": ds.res,
                "width": ds.width,
                "height": ds.height,
                "nodata": ds.nodata,
            }
    return {"year": year, "data": data, "meta": meta}


def row_cell_areas(
    lon_res: float,
    lat_res: float,
    lat_min: float,
    lat_max: float,
    n_rows: int,
) -> np.ndarray:
    """Área (m²) de cada célula da grade, por linha (cálculo geodésico)."""
    from pyproj import Geod

    geod = Geod(ellps="WGS84")
    areas = np.zeros(n_rows, dtype="float64")
    for row in range(n_rows):
        lat_top = lat_max - row * lat_res
        lat_bottom = lat_top - lat_res
        lons = [0.0, lon_res, lon_res, 0.0]
        lats = [lat_bottom, lat_bottom, lat_top, lat_top]
        area, _ = geod.polygon_area_perimeter(lons, lats)
        areas[row] = abs(area)
    return areas


def class_areas(
    data: np.ndarray,
    lon_res: float,
    lat_res: float,
    lat_min: float,
    lat_max: float,
) -> dict[str, Any]:
    """Área por classe (km²) com a área de célula calculada por faixa de linha."""
    rows, cols = data.shape
    areas = row_cell_areas(lon_res, lat_res, lat_min, lat_max, rows)
    row_area = np.repeat(areas[:, None], cols, axis=1)
    total = float(row_area.sum()) / 1e6
    report: dict[str, Any] = {
        "total_area_km2": total,
        "pixels": int(data.size),
        "classes": {},
    }
    for code in sorted(WORLDCOVER_CLASSES):
        mask = data == code
        count = int(np.count_nonzero(mask))
        if count == 0:
            continue
        area_km2 = float(row_area[mask].sum()) / 1e6
        report["classes"][str(code)] = {
            "name": WORLDCOVER_CLASSES[code],
            "pixels": count,
            "area_km2": area_km2,
            "fraction": (area_km2 / total) if total else 0.0,
        }
    other = int(np.count_nonzero(~np.isin(data, list(WORLDCOVER_CLASSES))))
    if other:
        area_km2 = float(row_area[~np.isin(data, list(WORLDCOVER_CLASSES))].sum()) / 1e6
        report["classes"]["other"] = {
            "name": "Outras (não classificadas)",
            "pixels": other,
            "area_km2": area_km2,
            "fraction": (area_km2 / total) if total else 0.0,
        }
    return report


def cropland_mask(data: np.ndarray) -> np.ndarray:
    """Máscara de lavoura (classe 40 — Cropland) do WorldCover."""
    return data == WORLDCOVER_CROPLAND


def cropland_grid_mask(
    wc_data: np.ndarray,
    wc_meta: dict[str, Any],
    grid: dict[str, Any],
) -> np.ndarray:
    """Máscara de lavoura (WorldCover classe 40) na grade-alvo (EPSG:32721).

    Para cada célula da grade-alvo são amostrados os 4 pixels de 10 m do
    WorldCover que o compõem (centros e vértices médios), e o célula é
    classificado como lavoura quando **pelo menos 50%** deles são lavoura.
    """
    import rasterio.transform as rtransform

    from affine import Affine

    wc_transform = Affine(*wc_meta["transform"])
    grid_transform = Affine(*grid["transform"][:6])
    height, width = grid["height"], grid["width"]
    rows, cols = np.mgrid[0:height, 0:width]
    xs, ys = rtransform.xy(grid_transform, rows, cols, offset="center")
    xs = np.asarray(xs, dtype="float64").reshape(height, width)
    ys = np.asarray(ys, dtype="float64").reshape(height, width)

    # os centros das células estão no CRS da grade (UTM); o WorldCover está
    # em EPSG:4326 — é preciso reprojetar os centros antes de indexar
    if str(grid.get("crs")) != str(wc_meta.get("crs")):
        from rasterio.warp import transform as warp_transform

        xs, ys = warp_transform(
            grid["crs"], wc_meta["crs"], xs.ravel().tolist(), ys.ravel().tolist()
        )
        xs = np.asarray(xs, dtype="float64").reshape(height, width)
        ys = np.asarray(ys, dtype="float64").reshape(height, width)

    mask = np.zeros((height, width), dtype=bool)
    # offsets de sub-amostra (centro e cantos médios) em coordenadas de pixel
    offsets = [(0.5, 0.5), (0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
    hits = np.zeros((height, width), dtype="int16")
    for dx, dy in offsets:
        col = np.floor((np.asarray(xs) + (dx - 0.5) * wc_meta["res"][0] - wc_transform.c) / wc_transform.a)
        row = np.floor((wc_transform.f - (np.asarray(ys) + (dy - 0.5) * wc_meta["res"][1])) / -wc_transform.e)
        col = col.astype("int64")
        row = row.astype("int64")
        valid = (
            (col >= 0) & (col < wc_data.shape[1]) & (row >= 0) & (row < wc_data.shape[0])
        )
        safe_col = np.clip(col, 0, wc_data.shape[1] - 1)
        safe_row = np.clip(row, 0, wc_data.shape[0] - 1)
        value = np.zeros((height, width), dtype="uint8")
        value[valid] = wc_data[safe_row[valid], safe_col[valid]]
        hits += (value == WORLDCOVER_CROPLAND) & valid
    mask = hits >= 3  # 5 amostras: maioria estrita
    return mask


def read_worldcover_block(
    year: int,
    bbox: list[float],
    tile: str | None = None,
    retries: int = 3,
) -> dict[str, Any]:
    """Lê a classe WorldCover de uma janela (usado no processamento por blocos).

    A leitura é remota e pode devolver janela vazia/parcial em falha
    transitória; por isso o resultado é validado (classe 10..100 presente) e
    refeito até ``retries`` vezes.
    """
    import rasterio
    from rasterio.windows import from_bounds

    from s2_poc import network

    network.configure_tls()
    tile = tile or worldcover_tile_name(bbox)
    url = WORLDCOVER_URLS[year].format(tile=tile)
    last: dict[str, Any] = {}
    for attempt in range(retries):
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
            with rasterio.open(url) as ds:
                window = from_bounds(*bbox, transform=ds.transform)
                data = ds.read(1, window=window)
                meta = {
                    "url": url,
                    "crs": str(ds.crs),
                    # o transform deve ser o da JANELA recortada (não o do
                    # dataset inteiro) — sem isso o mapeamento célula→pixel erra
                    "transform": list(window_transform(ds.transform, window))[:6],
                    "res": ds.res,
                    "width": ds.width,
                    "height": ds.height,
                    "nodata": ds.nodata,
                }
        last = {"year": year, "data": data, "meta": meta}
        if data.size and np.unique(data).size > 1 and int(data.max()) > 0:
            return last
        time.sleep(2.0 * (attempt + 1))
    return last


def window_transform(transform: Any, window: Any) -> Any:
    """Transform do recorte de janela (reexportado do rasterio)."""
    from rasterio.windows import transform as window_transform_

    return window_transform_(window, transform)


def block_subgrid(grid: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
    """Sub-grade (transform, altura e largura) de um bloco da grade."""
    from affine import Affine

    transform = grid["transform"] * Affine.translation(block["col_off"], block["row_off"])
    return {
        "crs": grid["crs"],
        "transform": transform,
        "height": block["height"],
        "width": block["width"],
        "res": grid["res"],
        "bounds": grid["transform"] * Affine.translation(block["col_off"], block["row_off"]),
    }


def block_bounds_wgs84(grid: dict[str, Any], block: dict[str, Any]) -> list[float]:
    """Bounds (lon/lat) de um bloco, a partir da grade em EPSG:32721.

    O eixo vertical da grade é decrescente: o topo do bloco é
    ``f - row_off * res`` e o base fica abaixo dele.
    """
    from rasterio.warp import transform_bounds

    left = grid["transform"].c + block["col_off"] * grid["res"]
    top = grid["transform"].f - block["row_off"] * grid["res"]
    right = left + block["width"] * grid["res"]
    bottom = top - block["height"] * grid["res"]
    return list(
        transform_bounds(grid["crs"], "EPSG:4326", left, bottom, right, top, densify_pts=21)
    )


def mask_to_grid(
    mask: np.ndarray,
    target_shape: tuple[int, int],
    threshold: float = 0.5,
) -> np.ndarray:
    """Converte máscara 10 m em máscara na grade-alvo (20 m) por fração coberta.

    Cada pixel da grade-alvo recebe ``True`` quando a fração de pixels de 10 m
   _TRUE_ dentro dele é ≥ ``threshold`` (regra determinística).
    """
    rows, cols = mask.shape
    target_rows, target_cols = target_shape
    if rows % target_rows or cols % target_cols:
        # blocos não divisíveis: agregação por média simples
        block_rows = rows / target_rows
        block_cols = cols / target_cols
        out = np.zeros(target_shape, dtype=bool)
        for r in range(target_rows):
            for c in range(target_cols):
                r0, r1 = int(r * block_rows), int((r + 1) * block_rows)
                c0, c1 = int(c * block_cols), int((c + 1) * block_cols)
                out[r, c] = mask[r0:r1, c0:c1].mean() >= threshold
        return out
    block_r, block_c = rows // target_rows, cols // target_cols
    reshaped = mask.reshape(target_rows, block_r, target_cols, block_c)
    return reshaped.mean(axis=(1, 3)) >= threshold
