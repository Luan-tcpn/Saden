"""Mosaico determinístico de dois tiles Sentinel-2 (Checkpoint D).

Regra adotada: **primeiro válido vence** (prioridade explícita), sem média
entre tiles. Em sobreposição, o tile primário fornece o pixel; o secundário só
preenche onde o primário é nodata. Um mapa de origem por pixel é devolvido para
auditoria e para desenhar a linha de costura.

Nunca misture datas diferentes: o chamador deve provar que os dois itens são da
mesma aquisição/datatake antes de usar estas funções.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np


def _check_shapes(arrays: Sequence[np.ndarray]) -> tuple[int, ...]:
    if not arrays:
        raise ValueError("nenhum array para mosaicar")
    shape = np.asarray(arrays[0]).shape
    for i, arr in enumerate(arrays):
        if np.asarray(arr).shape != shape:
            raise ValueError(
                f"array {i} tem shape {np.asarray(arr).shape}; esperado {shape}"
            )
    return shape


def mosaic_continuous(
    arrays: Sequence[np.ndarray],
    names: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Mosaico de variáveis contínuas: primeiro valor finito vence.

    ``NaN`` marca ausência. Nenhuma média é feita entre tiles sobrepostos.
    """
    shape = _check_shapes(arrays)
    names = list(names) if names is not None else [f"tile{i}" for i in range(len(arrays))]
    if len(names) != len(arrays):
        raise ValueError("nomes e arrays têm tamanhos diferentes")

    out = np.full(shape, np.nan, dtype="float64")
    source = np.full(shape, -1, dtype="int16")
    for index, arr in enumerate(arrays):
        value = np.asarray(arr, dtype="float64")
        fill = np.isfinite(value) & (source < 0)
        out[fill] = value[fill]
        source[fill] = index

    counts = {name: int(np.count_nonzero(source == i)) for i, name in enumerate(names)}
    return {
        "data": out.astype("float32"),
        "source": source,
        "source_names": names,
        "source_pixels": counts,
        "unfilled_pixels": int(np.count_nonzero(source < 0)),
        "total_pixels": int(source.size),
        "rule": "first_valid_wins",
    }


def mosaic_categorical(
    arrays: Sequence[np.ndarray],
    names: Sequence[str] | None = None,
    nodata: int = 0,
) -> dict[str, Any]:
    """Mosaico de classes (ex.: SCL): primeiro valor != nodata vence."""
    shape = _check_shapes(arrays)
    names = list(names) if names is not None else [f"tile{i}" for i in range(len(arrays))]
    if len(names) != len(arrays):
        raise ValueError("nomes e arrays têm tamanhos diferentes")

    out = np.full(shape, nodata, dtype=np.asarray(arrays[0]).dtype)
    source = np.full(shape, -1, dtype="int16")
    for index, arr in enumerate(arrays):
        value = np.asarray(arr)
        fill = (value != nodata) & (source < 0)
        out[fill] = value[fill]
        source[fill] = index

    counts = {name: int(np.count_nonzero(source == i)) for i, name in enumerate(names)}
    return {
        "data": out,
        "source": source,
        "source_names": names,
        "source_pixels": counts,
        "unfilled_pixels": int(np.count_nonzero(source < 0)),
        "total_pixels": int(source.size),
        "rule": "first_non_nodata_wins",
        "nodata": nodata,
    }


def overlap_stats(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    """Compara dois rasters contínuos apenas onde ambos são finitos."""
    left = np.asarray(a, dtype="float64")
    right = np.asarray(b, dtype="float64")
    if left.shape != right.shape:
        raise ValueError(f"shapes diferentes: {left.shape} vs {right.shape}")
    both = np.isfinite(left) & np.isfinite(right)
    count = int(np.count_nonzero(both))
    if count == 0:
        return {"pixels": 0, "note": "nenhum pixel válido em comum"}
    x = left[both]
    y = right[both]
    diff = x - y
    abs_diff = np.abs(diff)
    corr = None
    if count > 1 and x.std() > 0 and y.std() > 0:
        corr = float(np.corrcoef(x, y)[0, 1])
    return {
        "pixels": count,
        "mean_left": float(np.mean(x)),
        "mean_right": float(np.mean(y)),
        "mean_difference_left_minus_right": float(np.mean(diff)),
        "mean_absolute_difference": float(np.mean(abs_diff)),
        "rmse": float(np.sqrt(np.mean(diff ** 2))),
        "median_absolute_difference": float(np.median(abs_diff)),
        "p95_absolute_difference": float(np.percentile(abs_diff, 95)),
        "max_absolute_difference": float(np.max(abs_diff)),
        "correlation": corr,
    }


def seam_mask(source: np.ndarray) -> np.ndarray:
    """Pixels onde a origem muda entre vizinhos (linha de costura visível)."""
    src = np.asarray(source)
    seam = np.zeros(src.shape, dtype=bool)
    seam[:, 1:] |= src[:, 1:] != src[:, :-1]
    seam[1:, :] |= src[1:, :] != src[:-1, :]
    return seam


def mosaic_grids(grids: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Confere que todos os tiles compartilham CRS, transform e dimensões."""
    if not grids:
        raise ValueError("nenhuma grade informada")
    ref = grids[0]
    for i, grid in enumerate(grids[1:], start=1):
        same = (
            str(grid["crs"]) == str(ref["crs"])
            and tuple(grid["transform"])[:6] == tuple(ref["transform"])[:6]
            and int(grid["width"]) == int(ref["width"])
            and int(grid["height"]) == int(ref["height"])
        )
        if not same:
            raise ValueError(
                f"grade {i} incompatível: {grid['crs']}, {tuple(grid['transform'])[:6]}, "
                f"{grid['width']}x{grid['height']} vs {ref['crs']}, "
                f"{tuple(ref['transform'])[:6]}, {ref['width']}x{ref['height']}"
            )
    return ref


def mosaic_index_results(
    results: Sequence[dict[str, Any]],
    index_names: Sequence[str],
    source_names: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Mosaica NDVI/EVI/NDMI e mapas de máscara de várias cenas já calculadas.

    ``results`` deve conter ``indices`` e ``grid`` (saída de
    :func:`s2_poc.indices.compute_indices`). As grades precisam ser idênticas.
    ``index_names`` são os índices a mosaicar; ``source_names`` são os rótulos
    dos tiles (prioridade = ordem da lista).
    """
    if not results:
        raise ValueError("nenhum resultado para mosaicar")
    grid = mosaic_grids([r["grid"] for r in results])
    labels = list(source_names) if source_names is not None else [
        f"tile{i}" for i in range(len(results))
    ]
    if len(labels) != len(results):
        raise ValueError("nomes de origem e resultados têm tamanhos diferentes")
    indices: dict[str, Any] = {}
    sources: dict[str, Any] = {}
    for name in index_names:
        arrays = [r["indices"][name] for r in results]
        mosaic = mosaic_continuous(arrays, labels)
        indices[name] = mosaic["data"]
        sources[name] = {
            "source": mosaic["source"],
            "source_pixels": mosaic["source_pixels"],
            "unfilled_pixels": mosaic["unfilled_pixels"],
            "rule": mosaic["rule"],
            "source_names": mosaic["source_names"],
        }
    return {"indices": indices, "grid": grid, "sources": sources}
