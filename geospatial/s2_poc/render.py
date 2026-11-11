"""Prévias PNG estáticas dos índices (matplotlib, backend Agg)."""

from __future__ import annotations

import os
from typing import Any

import numpy as np

# Backend não interativo: nunca abre janela.
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _extent(grid: dict[str, Any]) -> list[float]:
    left, bottom, right, top = grid["bounds"]
    # imshow espera [left, right, bottom, top]
    return [left, right, bottom, top]


def render_indices(
    indices: dict[str, np.ndarray],
    grid: dict[str, Any],
    out_png: str,
    title: str = "",
    vmin: float = -1.0,
    vmax: float = 1.0,
    dpi: int = 110,
) -> str:
    """Salva um painel NDVI/EVI/NDMI com escala fixa e fundo transparente no NaN."""
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    names = ["NDVI", "EVI", "NDMI"]
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 4.2), constrained_layout=True)
    extent = _extent(grid)
    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad(alpha=0.0)

    for ax, name in zip(axes, names):
        arr = np.asarray(indices[name], dtype="float64")
        masked = np.ma.masked_invalid(arr)
        im = ax.imshow(
            masked,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            extent=extent,
            interpolation="nearest",
        )
        valid = int(np.isfinite(arr).sum())
        total = int(arr.size)
        ax.set_title(f"{name} — válidos {100.0 * valid / total:.1f}%" if total else name, fontsize=10)
        ax.set_xlabel("leste (m, EPSG:%s)" % str(grid["crs"]).split(":")[-1], fontsize=8)
        ax.tick_params(labelsize=7)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)

    axes[0].set_ylabel("norte (m)", fontsize=8)
    if title:
        fig.suptitle(title, fontsize=10)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_png
