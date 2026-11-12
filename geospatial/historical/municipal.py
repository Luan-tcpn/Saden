"""Harmonização de escala municipal: NDVI sobre a área agrícola do município.

A V2.2 proibiu atribuir produtividade municipal à AOI. A alternativa
metodológica aceitável é **mudar a escala do indicador**: agregar o NDVI do
Sentinel-2 sobre **toda a área agrícola do município de Sorriso**, produzindo
um indicador na mesma unidade territorial do alvo do IBGE.

Restrições de engenharia (V2.1): o município tem 9.293,47 km² e sua bbox cobre
~24.400 km²; em 20 m isso são ~61 milhões de pixels por banda e por data.
Processar tudo de uma vez em memória é inviável — daí o **processamento por
blocos**, com acumuladores por bloco (soma, contagem, soma de quadrados e
histograma) que nunca armazenam o raster completo.
"""

from __future__ import annotations

import json
import math
from typing import Any, Iterable

import numpy as np

from s2_poc import config, indices as indices_mod, mask as mask_mod, read

# parâmetros do indicador municipal
MUNICIPAL_RES_M = config.TARGET_RES_M
MUNICIPAL_CRS = "EPSG:32721"
HIST_BINS = 2001
HIST_MIN, HIST_MAX = -1.0, 1.0


def municipality_grid(res_m: float = MUNICIPAL_RES_M) -> dict[str, Any]:
    """Grade do município (bbox real, alinhada a múltiplos da resolução)."""
    from shapely.geometry import box

    from agri.geometry_compat import municipality_geometry

    geometry = municipality_geometry()
    minx, miny, maxx, maxy = geometry.bounds
    # bbox do tile 21LXG/21LXF em EPSG:4326 cobre o município com folga
    bbox = [minx - 0.02, miny - 0.02, maxx + 0.02, maxy + 0.02]
    grid = read.target_grid(MUNICIPAL_CRS, bbox, res_m)
    grid["municipality_bbox_wgs84"] = list(geometry.bounds)
    return grid


def grid_blocks(grid: dict[str, Any], n_blocks: int = 4) -> list[dict[str, Any]]:
    """Divide a grade em blocos (grade regular) para processamento incremental."""
    rows, cols = grid["height"], grid["width"]
    block_rows = max(1, math.ceil(rows / math.sqrt(n_blocks)))
    block_cols = max(1, math.ceil(cols / math.sqrt(n_blocks)))
    blocks = []
    for r0 in range(0, rows, block_rows):
        for c0 in range(0, cols, block_cols):
            blocks.append(
                {
                    "row_off": r0,
                    "col_off": c0,
                    "height": min(block_rows, rows - r0),
                    "width": min(block_cols, cols - c0),
                }
            )
    return blocks


def block_window(grid: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
    """Janela raster (em coordenadas do CRS) correspondente ao bloco.

    A grade tem eixo vertical decrescente (``e < 0``): o topo do bloco é
    ``f - row_off * res`` e o base fica abaixo dele.
    """
    from rasterio.windows import Window

    left = grid["transform"].c + block["col_off"] * grid["res"]
    top = grid["transform"].f - block["row_off"] * grid["res"]
    right = left + block["width"] * grid["res"]
    bottom = top - block["height"] * grid["res"]
    return {
        "window": Window(
            block["col_off"], block["row_off"], block["width"], block["height"]
        ),
        "bounds": [left, bottom, right, top],
    }


def estimate_operation(grid: dict[str, Any], n_dates: int, bands: int = 2) -> dict[str, Any]:
    """Estimativa de volume/memória/tempo do processamento municipal."""
    pixels = grid["width"] * grid["height"]
    source_pixels = pixels * 4  # 10 m -> 20 m (fator 4 linear)
    bytes_per_date = source_pixels * 2 * bands  # uint16
    return {
        "grid_pixels_20m": pixels,
        "source_pixels_10m_per_band": source_pixels,
        "download_bytes_per_date": bytes_per_date,
        "download_gb_total": bytes_per_date * n_dates / 1e9,
        "memory_note": (
            "Processamento por blocos: memória limitada ao bloco (nunca o "
            "municipério inteiro)."
        ),
        "dates": n_dates,
    }


def accumulate_ndvi(
    ndvi: np.ndarray,
    valid: np.ndarray,
    agricultural: np.ndarray,
) -> dict[str, Any]:
    """Acumula estatísticas do NDVI sobre pixels agrícolas (sem guardar o raster)."""
    mask = valid & agricultural & np.isfinite(ndvi)
    values = ndvi[mask].astype("float64")
    count = int(values.size)
    if count == 0:
        return {
            "count": 0,
            "sum": 0.0,
            "sum_sq": 0.0,
            "histogram": np.zeros(HIST_BINS, dtype="int64"),
        }
    edges = np.linspace(HIST_MIN, HIST_MAX, HIST_BINS + 1)
    histogram, _ = np.histogram(values, bins=edges)
    return {
        "count": count,
        "sum": float(values.sum()),
        "sum_sq": float(np.square(values).sum()),
        "histogram": histogram.astype("int64"),
    }


def merge_accumulators(accumulators: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Combina acumuladores de blocos em um só (soma/contagem/histograma)."""
    total_count = 0
    total_sum = 0.0
    total_sum_sq = 0.0
    histogram = np.zeros(HIST_BINS, dtype="int64")
    for acc in accumulators:
        total_count += int(acc["count"])
        total_sum += float(acc["sum"])
        total_sum_sq += float(acc["sum_sq"])
        histogram += np.asarray(acc["histogram"], dtype="int64")
    mean = (total_sum / total_count) if total_count else None
    variance = (
        (total_sum_sq / total_count - mean**2) if (total_count and mean is not None) else None
    )
    edges = np.linspace(HIST_MIN, HIST_MAX, HIST_BINS + 1)
    quantiles = {}
    if total_count:
        cumulative = np.cumsum(histogram)
        for label, fraction in (("p05", 0.05), ("p25", 0.25), ("p50", 0.50), ("p75", 0.75), ("p95", 0.95)):
            position = np.searchsorted(cumulative, fraction * total_count)
            position = min(position, HIST_BINS - 1)
            quantiles[label] = float(
                edges[position] + (edges[position + 1] - edges[position]) / 2
            )
    return {
        "count": total_count,
        "sum": total_sum,
        "sum_sq": total_sum_sq,
        "mean": mean,
        "std": float(math.sqrt(variance)) if variance and variance > 0 else (0.0 if variance == 0 else None),
        "quantiles": quantiles,
        "histogram": histogram,
    }


def read_block(
    href: str,
    grid: dict[str, Any],
    block: dict[str, Any],
    resampling: Any = None,
    nodata: float = np.nan,
    dtype: str = "float32",
) -> np.ndarray:
    """Lê apenas a janela do bloco (COG remoto) e reprojeta na grade do bloco.

    Implementação **local** (não altera `s2_poc.read`, que fica intacto na
    V2.1): abre o COG, calcula a janela correspondente ao bloco e reprojeta
    para a sub-grade do bloco.
    """
    import math

    from affine import Affine
    from rasterio.warp import reproject, transform_bounds
    from rasterio.windows import Window, from_bounds

    if resampling is None:
        from rasterio.enums import Resampling

        resampling = Resampling.average
    bounds = block_window(grid, block)["bounds"]
    transform = grid["transform"] * Affine.translation(block["col_off"], block["row_off"])
    destination = np.full((block["height"], block["width"]), nodata, dtype=dtype)
    with read.rasterio.Env(**read.GDAL_ENV):
        with read.rasterio.open(href) as ds:
            src_bounds = transform_bounds(
                grid["crs"], ds.crs, *bounds, densify_pts=21
            )
            # janela calculada manualmente e recortada ao dataset (o bloco
            # pode ultrapassar o footprint do tile: a área externa fica
            # como nodata, o que é estatisticamente correto)
            res_x = ds.transform.a
            res_y = -ds.transform.e
            col_off = int(math.floor((src_bounds[0] - ds.transform.c) / res_x))
            col_end = int(math.ceil((src_bounds[2] - ds.transform.c) / res_x))
            row_off = int(math.floor((ds.transform.f - src_bounds[3]) / res_y))
            row_end = int(math.ceil((ds.transform.f - src_bounds[1]) / res_y))
            col_off = max(0, min(col_off, ds.width))
            col_end = max(0, min(col_end, ds.width))
            row_off = max(0, min(row_off, ds.height))
            row_end = max(0, min(row_end, ds.height))
            if col_end <= col_off or row_end <= row_off:
                return destination
            src_window = Window(col_off, row_off, col_end - col_off, row_end - row_off)
            src_transform = ds.window_transform(src_window)
            source = ds.read(1, window=src_window)
            reproject(
                source,
                destination,
                src_transform=src_transform,
                src_crs=ds.crs,
                src_nodata=ds.nodata,
                dst_transform=transform,
                dst_crs=grid["crs"],
                dst_nodata=nodata,
                resampling=resampling,
                num_threads=1,
            )
    return destination


def ndvi_from_reflectance(
    red: np.ndarray,
    nir: np.ndarray,
    scale: float,
    offset: float,
    nodata: float = 0.0,
) -> np.ndarray:
    """NDVI a partir de DN (reflectância aplicada uma única vez)."""
    red_r = indices_mod.scale_reflectance(red, scale, offset, nodata)
    nir_r = indices_mod.scale_reflectance(nir, scale, offset, nodata)
    return indices_mod.compute_ndvi(nir_r, red_r)


def scl_keep(scl: np.ndarray) -> np.ndarray:
    """Máscara SCL do Perfil B (D43)."""
    return mask_mod.keep_mask(scl, "B_restrictive")
