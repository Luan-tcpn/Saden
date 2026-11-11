"""Leitura de COGs remotos com recorte e reamostragem para uma grade comum."""

from __future__ import annotations

import hashlib
import math
import os
import warnings
from typing import Any

import numpy as np
import rasterio
from affine import Affine
from rasterio.enums import Resampling
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window, from_bounds

from . import config

# Evita listagem de diretórios S3 (não suportada) ao abrir COGs por HTTP.
GDAL_ENV = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"}


def target_grid(crs: Any, aoi_bbox: list[float], res: float = config.TARGET_RES_M) -> dict[str, Any]:
    """Grade alvo alinhada a múltiplos de `res` no CRS do tile."""
    minx, miny, maxx, maxy = transform_bounds("EPSG:4326", crs, *aoi_bbox, densify_pts=21)
    left = math.floor(minx / res) * res
    bottom = math.floor(miny / res) * res
    right = math.ceil(maxx / res) * res
    top = math.ceil(maxy / res) * res
    width = int(round((right - left) / res))
    height = int(round((top - bottom) / res))
    transform = Affine(res, 0.0, left, 0.0, -res, top)
    return {
        "crs": crs,
        "transform": transform,
        "width": width,
        "height": height,
        "res": res,
        "bounds": [left, bottom, right, top],
    }


def _window_for(ds, grid: dict[str, Any]) -> tuple[Window, Any]:
    bounds = rasterio.transform.array_bounds(grid["height"], grid["width"], grid["transform"])
    if str(ds.crs) != str(grid["crs"]):
        bounds = transform_bounds(grid["crs"], ds.crs, *bounds, densify_pts=21)
    win = from_bounds(*bounds, transform=ds.transform)
    col_off = max(0, int(math.floor(win.col_off)))
    row_off = max(0, int(math.floor(win.row_off)))
    col_end = min(ds.width, int(math.ceil(win.col_off + win.width)))
    row_end = min(ds.height, int(math.ceil(win.row_off + win.height)))
    if col_end <= col_off or row_end <= row_off:
        raise ValueError("AOI não intersecta a cena")
    window = Window(col_off, row_off, col_end - col_off, row_end - row_off)
    return window, ds.window_transform(window)


def read_resampled(
    href: str,
    grid: dict[str, Any],
    resampling: Resampling,
    dst_nodata: float,
    dtype: str = "float32",
) -> tuple[np.ndarray, dict[str, Any]]:
    """Lê a janela da cena e reprojeta/reamostra para a grade alvo."""
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(href) as ds:
            window, src_transform = _window_for(ds, grid)
            with warnings.catch_warnings():
                # rasterio 1.4.3 + numpy 2.5 emite DeprecationWarning interno ao
                # montar o array da janela; não afeta correção nem dados.
                warnings.filterwarnings(
                    "ignore",
                    category=DeprecationWarning,
                    message="Setting the shape on a NumPy array",
                )
                source = ds.read(1, window=window)
            destination = np.full((grid["height"], grid["width"]), dst_nodata, dtype=dtype)
            reproject(
                source=source,
                destination=destination,
                src_transform=src_transform,
                src_crs=ds.crs,
                src_nodata=ds.nodata,
                dst_transform=grid["transform"],
                dst_crs=grid["crs"],
                dst_nodata=dst_nodata,
                resampling=resampling,
                num_threads=1,
            )
            meta = {
                "href": href,
                "source_crs": str(ds.crs),
                "source_res": ds.res,
                "source_dtype": ds.dtypes[0],
                "source_nodata": ds.nodata,
                "window": {
                    "col_off": int(window.col_off),
                    "row_off": int(window.row_off),
                    "width": int(window.width),
                    "height": int(window.height),
                },
                "resampling": resampling.name,
            }
    return destination, meta


def _band_meta(asset: Any) -> tuple[float, float, float]:
    bands = asset.extra_fields.get("raster:bands") or []
    band = bands[0] if bands else {}
    scale = band.get("scale")
    offset = band.get("offset")
    nodata = band.get("nodata")
    return (
        1e-4 if scale is None else float(scale),
        0.0 if offset is None else float(offset),
        0.0 if nodata is None else float(nodata),
    )


def scene_grid(item: Any, aoi_bbox: list[float], res: float = config.TARGET_RES_M) -> dict[str, Any]:
    """Grade alvo derivada do CRS do SCL (20 m) da cena."""
    scl_asset = item.assets[config.ASSETS["scl"]]
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(scl_asset.href) as ds:
            crs = ds.crs
    return target_grid(crs, aoi_bbox, res)


def read_scl(
    item: Any,
    aoi_bbox: list[float],
    res: float = config.TARGET_RES_M,
    grid: dict[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    """Lê apenas o SCL na grade alvo (nearest), sem interpolar classes."""
    grid = grid or scene_grid(item, aoi_bbox, res)
    scl_asset = item.assets[config.ASSETS["scl"]]
    scl, meta = read_resampled(scl_asset.href, grid, Resampling.nearest, 0, "uint8")
    return scl, meta, grid


def read_scene_bands(
    item: Any,
    aoi_bbox: list[float],
    res: float = config.TARGET_RES_M,
    grid: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Lê B02/B04/B08/B11/SCL e devolve arrays na mesma grade de 20 m.

    Contínuas: média (average) na redução de 10 m → 20 m.
    SCL: vizinho mais próximo (nunca interpolação em classes).

    ``grid`` permite forçar a grade de outro tile (mosaico); sem ele, a grade é
    derivada do CRS do SCL da própria cena.
    """
    missing = [n for n in config.ASSETS if config.ASSETS[n] not in item.assets]
    if missing:
        raise ValueError(f"cena {item.id} sem ativos: {missing}")

    scl_asset = item.assets[config.ASSETS["scl"]]
    if grid is None:
        with rasterio.Env(**GDAL_ENV):
            with rasterio.open(scl_asset.href) as ds:
                crs = ds.crs
        grid = target_grid(crs, aoi_bbox, res)

    out: dict[str, Any] = {"bands": {}, "grid": grid, "meta": {}, "scales": {}}
    for name in ("blue", "red", "nir", "swir"):
        asset = item.assets[config.ASSETS[name]]
        arr, meta = read_resampled(asset.href, grid, Resampling.average, np.nan, "float32")
        scale, offset, nodata = _band_meta(asset)
        out["bands"][name] = arr
        out["meta"][name] = meta
        out["scales"][name] = {"scale": scale, "offset": offset, "nodata": nodata}

    scl, meta = read_resampled(scl_asset.href, grid, Resampling.nearest, 0, "uint8")
    out["scl"] = scl
    out["meta"]["scl"] = meta
    return out


def write_geotiff(
    path: str,
    array: np.ndarray,
    grid: dict[str, Any],
    nodata: float = np.nan,
    tags: dict[str, str] | None = None,
) -> str:
    """Escreve um raster float32 de uma banda na grade informada."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    data = np.asarray(array, dtype="float32")
    if data.shape != (grid["height"], grid["width"]):
        raise ValueError(
            f"array {data.shape} não casa com a grade "
            f"{(grid['height'], grid['width'])}"
        )
    profile = {
        "driver": "GTiff",
        "height": grid["height"],
        "width": grid["width"],
        "count": 1,
        "dtype": "float32",
        "crs": grid["crs"],
        "transform": grid["transform"],
        "nodata": nodata,
        "compress": "deflate",
        "tiled": False,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
        if tags:
            dst.update_tags(**tags)
    return path


def sha256_file(path: str, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()
