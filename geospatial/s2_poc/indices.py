"""Cálculo dos índices NDVI/EVI/NDMI sobre reflectância de superfície L2A.

Regras aplicadas (documentadas em `docs/V2_EXECUTION_STATUS.md`):

* A reflectância física é obtida de ``DN * scale + offset`` (L2A: 1e-4 e -0.1).
* ``DN == nodata`` (0) vira ``NaN`` **antes** da escala: sem isso, DN 0 viraria
  -0.1 e entraria no cálculo como pixel válido.
* O termo aditivo ``+1`` do EVI só faz sentido na reflectância física (0..1),
  por isso a escala é aplicada antes da fórmula.
* Denominador nulo/instável produz ``NaN`` (nunca ``inf`` nem clamp silencioso).
* A máscara SCL é aplicada depois do cálculo; pixels mascarados viram ``NaN``.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from . import config

# Abaixo disso o denominador é tratado como degenerado.
DENOM_EPS = 1e-6


def scale_reflectance(
    dn: np.ndarray,
    scale: float,
    offset: float,
    nodata: float | None = 0.0,
) -> np.ndarray:
    """Converte DN em reflectância física, mascarando nodata/valores não finitos."""
    arr = np.asarray(dn, dtype="float64")
    invalid = ~np.isfinite(arr)
    if nodata is not None:
        invalid |= arr == nodata
    out = arr * float(scale) + float(offset)
    out[invalid] = np.nan
    return out


def scl_keep_mask(
    scl: np.ndarray,
    bad_classes: tuple[int, ...] = config.SCL_BAD_CLASSES,
    unclassified: int | None = config.SCL_UNCLASSIFIED,
) -> np.ndarray:
    """True onde a classe SCL é aproveitável.

    Política conservadora: além das classes ruins da spec, a classe 7
    (não classificado) também é excluída. Água (6) e solo (5) são mantidos:
    máscara de qualidade **não** é interpretação agronômica.
    """
    arr = np.asarray(scl)
    keep = np.ones(arr.shape, dtype=bool)
    for cls in bad_classes:
        keep &= arr != cls
    if unclassified is not None:
        keep &= arr != unclassified
    return keep


def safe_ratio(numerator: np.ndarray, denominator: np.ndarray, eps: float = DENOM_EPS) -> np.ndarray:
    """Divisão protegida: NaN onde entrada é inválida ou denominador ~0."""
    num = np.asarray(numerator, dtype="float64")
    den = np.asarray(denominator, dtype="float64")
    if num.shape != den.shape:
        raise ValueError(f"shapes diferentes: {num.shape} vs {den.shape}")
    out = np.full(num.shape, np.nan, dtype="float64")
    ok = np.isfinite(num) & np.isfinite(den) & (np.abs(den) > eps)
    out[ok] = num[ok] / den[ok]
    return out


def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """NDVI = (NIR - Red) / (NIR + Red)."""
    return safe_ratio(np.asarray(nir) - np.asarray(red), np.asarray(nir) + np.asarray(red))


def compute_evi(nir: np.ndarray, red: np.ndarray, blue: np.ndarray) -> np.ndarray:
    """EVI = 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1).

    Reflectância já em unidade física (0..1); o ``+1`` é adimensional.
    """
    nir = np.asarray(nir)
    red = np.asarray(red)
    blue = np.asarray(blue)
    return safe_ratio(
        2.5 * (nir - red),
        nir + 6.0 * red - 7.5 * blue + 1.0,
    )


def compute_ndmi(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """NDMI = (NIR - SWIR) / (NIR + SWIR)."""
    return safe_ratio(np.asarray(nir) - np.asarray(swir), np.asarray(nir) + np.asarray(swir))


def array_stats(arr: np.ndarray, plausible_range: tuple[float, float] = config.PLAUSIBLE_RANGE) -> dict[str, Any]:
    """Estatísticas apenas sobre pixels finitos (válidos)."""
    values = np.asarray(arr, dtype="float64")
    finite = np.isfinite(values)
    flat = values[finite]
    total = int(values.size)
    valid = int(flat.size)
    if valid == 0:
        return {
            "total_pixels": total,
            "valid_pixels": 0,
            "valid_fraction": 0.0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "p05": None,
            "p95": None,
            "std": None,
            "out_of_range_pixels": 0,
        }
    low, high = plausible_range
    return {
        "total_pixels": total,
        "valid_pixels": valid,
        "valid_fraction": valid / total,
        "min": float(np.min(flat)),
        "max": float(np.max(flat)),
        "mean": float(np.mean(flat)),
        "median": float(np.median(flat)),
        "p05": float(np.percentile(flat, 5)),
        "p95": float(np.percentile(flat, 95)),
        "std": float(np.std(flat)),
        "out_of_range_pixels": int(np.count_nonzero((flat < low) | (flat > high))),
    }


def compute_indices(scene: dict[str, Any]) -> dict[str, Any]:
    """Calcula NDVI/EVI/NDMI e as máscaras de uma cena já lida.

    ``scene`` deve conter ``bands`` (blue/red/nir/swir em DN), ``scl`` e
    ``scales`` (scale/offset/nodata por banda), como devolvido por
    :func:`s2_poc.read.read_scene_bands`.
    """
    bands = scene["bands"]
    scl = scene["scl"]
    scales = scene["scales"]

    refl: dict[str, np.ndarray] = {}
    nodata_invalid = np.zeros(scl.shape, dtype=bool)
    for name in ("blue", "red", "nir", "swir"):
        meta = scales[name]
        dn = np.asarray(bands[name])
        nodata = meta.get("nodata", 0.0)
        refl[name] = scale_reflectance(
            dn,
            scale=meta.get("scale", 1e-4),
            offset=meta.get("offset", -0.1),
            nodata=nodata,
        )
        if nodata is not None:
            nodata_invalid |= np.asarray(dn) == nodata
        nodata_invalid |= ~np.isfinite(np.asarray(dn))

    scl_ok = scl_keep_mask(scl)
    # Pixels com qualquer banda contínua inválida não entram em nenhum índice.
    continuous_ok = np.ones(scl.shape, dtype=bool)
    for arr in refl.values():
        continuous_ok &= np.isfinite(arr)
    keep = continuous_ok & scl_ok

    indices = {
        "NDVI": compute_ndvi(refl["nir"], refl["red"]),
        "EVI": compute_evi(refl["nir"], refl["red"], refl["blue"]),
        "NDMI": compute_ndmi(refl["nir"], refl["swir"]),
    }
    for name in indices:
        indices[name] = np.where(keep, indices[name], np.nan).astype("float32")

    total = int(scl.size)
    stats = {name: array_stats(arr) for name, arr in indices.items()}
    for name, value in stats.items():
        value["degenerate_pixels"] = int(keep.sum() - np.count_nonzero(np.isfinite(indices[name])))

    mask_summary = {
        "total_pixels": total,
        "scl_masked_pixels": int(np.count_nonzero(~scl_ok)),
        "nodata_masked_pixels": int(np.count_nonzero(nodata_invalid)),
        "kept_pixels": int(np.count_nonzero(keep)),
        "kept_fraction": float(np.count_nonzero(keep) / total) if total else 0.0,
        "scl_excluded_classes": list(config.SCL_BAD_CLASSES) + [config.SCL_UNCLASSIFIED],
    }

    return {
        "indices": indices,
        "reflectance": {k: v.astype("float32") for k, v in refl.items()},
        "keep_mask": keep,
        "stats": stats,
        "mask_summary": mask_summary,
        "grid": scene["grid"],
    }
