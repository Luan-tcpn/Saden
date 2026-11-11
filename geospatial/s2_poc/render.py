"""Prévias PNG estáticas dos índices (matplotlib, backend Agg)."""

from __future__ import annotations

import os
from typing import Any, Sequence

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


# Paleta fixa para classes SCL (0..11) — sem tons que sugiram condição de
# lavoura. Usada apenas para inspeção visual de máscara.
SCL_COLORS = {
    0: "#000000",
    1: "#7f7f7f",
    2: "#404040",
    3: "#8c564b",
    4: "#2ca02c",
    5: "#c8a165",
    6: "#1f77b4",
    7: "#9467bd",
    8: "#ff7f0e",
    9: "#d62728",
    10: "#e377c2",
    11: "#17becf",
}


def _scl_cmap():
    from matplotlib.colors import ListedColormap

    colors = [SCL_COLORS[i] for i in range(12)]
    cmap = ListedColormap(colors)
    cmap.set_bad(color="#f2f2f2")
    return cmap


def render_mask_comparison(
    scl: np.ndarray,
    keep_a: np.ndarray,
    keep_b: np.ndarray,
    grid: dict[str, Any],
    out_png: str,
    title: str = "",
    dpi: int = 110,
) -> str:
    """Painel: classes SCL, máscara do Perfil A, do Perfil B e a diferença."""
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    extent = _extent(grid)
    fig, axes = plt.subplots(1, 4, figsize=(15.0, 4.2), constrained_layout=True)

    scl_arr = np.asarray(scl)
    im0 = axes[0].imshow(
        scl_arr, cmap=_scl_cmap(), vmin=-0.5, vmax=11.5, extent=extent, interpolation="nearest"
    )
    axes[0].set_title("Classes SCL (código)", fontsize=10)
    fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.02, ticks=range(12))

    for ax, keep, name in (
        (axes[1], keep_a, "Perfil A (histórico)"),
        (axes[2], keep_b, "Perfil B (restritivo)"),
    ):
        valid = np.where(np.asarray(keep), 1.0, np.nan)
        im = ax.imshow(
            valid, cmap="Greens", vmin=0, vmax=1, extent=extent, interpolation="nearest"
        )
        frac = float(np.count_nonzero(keep)) / float(np.asarray(keep).size)
        ax.set_title(f"{name} — válido {100 * frac:.2f}%", fontsize=10)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02, ticks=[0, 1])

    diff = np.where(
        np.asarray(keep_a) & ~np.asarray(keep_b),
        1.0,
        np.where(~np.asarray(keep_a) & np.asarray(keep_b), -1.0, np.nan),
    )
    im3 = axes[3].imshow(
        diff, cmap="coolwarm", vmin=-1, vmax=1, extent=extent, interpolation="nearest"
    )
    axes[3].set_title("A→B (vermelho) / B→A (azul)", fontsize=10)
    fig.colorbar(im3, ax=axes[3], fraction=0.046, pad=0.02, ticks=[-1, 1])

    for ax in axes:
        ax.set_xlabel("leste (m)", fontsize=8)
        ax.tick_params(labelsize=7)
    axes[0].set_ylabel("norte (m)", fontsize=8)
    if title:
        fig.suptitle(title, fontsize=10)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_png


def render_mosaic(
    indices: dict[str, np.ndarray],
    source: np.ndarray,
    grid: dict[str, Any],
    out_png: str,
    title: str = "",
    source_names: Sequence[str] | None = None,
    dpi: int = 110,
) -> str:
    """Painel do mosaico: NDVI/EVI/NDMI + mapa de origem por pixel."""
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    extent = _extent(grid)
    names = ["NDVI", "EVI", "NDMI"]
    fig, axes = plt.subplots(1, 4, figsize=(15.0, 4.2), constrained_layout=True)
    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad(alpha=0.0)
    for ax, name in zip(axes[:3], names):
        arr = np.asarray(indices[name], dtype="float64")
        im = ax.imshow(
            np.ma.masked_invalid(arr),
            cmap=cmap,
            vmin=-1.0,
            vmax=1.0,
            extent=extent,
            interpolation="nearest",
        )
        valid = int(np.isfinite(arr).sum())
        ax.set_title(
            f"{name} — válidos {100.0 * valid / max(arr.size, 1):.1f}%", fontsize=10
        )
        ax.set_xlabel("leste (m)", fontsize=8)
        ax.tick_params(labelsize=7)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)

    src = np.asarray(source)
    im3 = axes[3].imshow(
        src, cmap="tab10", vmin=-0.5, vmax=max(0.5, float(src.max()) + 0.5),
        extent=extent, interpolation="nearest",
    )
    axes[3].set_title("Origem do pixel (tile)", fontsize=10)
    axes[3].set_xlabel("leste (m)", fontsize=8)
    axes[3].tick_params(labelsize=7)
    fig.colorbar(im3, ax=axes[3], fraction=0.046, pad=0.02)
    axes[0].set_ylabel("norte (m)", fontsize=8)
    if title:
        fig.suptitle(title, fontsize=10)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_png


def render_timeseries(
    records: Sequence[dict[str, Any]],
    out_png: str,
    title: str = "",
    dpi: int = 110,
) -> str:
    """Série temporal com lacunas visíveis (mês sem observação = quebra)."""
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    months = [r["month"] for r in records]
    x = list(range(len(months)))
    fig, axes = plt.subplots(4, 1, figsize=(11.0, 8.4), sharex=True, constrained_layout=True)

    for ax, name in zip(axes[:3], ("NDVI", "EVI", "NDMI")):
        means: list[float] = []
        lows: list[float] = []
        highs: list[float] = []
        coverage: list[float] = []
        for record in records:
            stats = record.get("indices", {}).get(name)
            if record["status"] != "observed" or not stats or stats.get("mean") is None:
                means.append(float("nan"))
                lows.append(float("nan"))
                highs.append(float("nan"))
                coverage.append(0.0)
                continue
            means.append(float(stats["mean"]))
            lows.append(float(stats.get("p25", float("nan"))))
            highs.append(float(stats.get("p75", float("nan"))))
            coverage.append(float(stats.get("valid_fraction", 0.0)))
        ax.plot(x, means, marker="o", linewidth=1.2, color="#1f77b4")
        ax.fill_between(x, lows, highs, color="#1f77b4", alpha=0.15)
        ax.set_ylabel(f"{name} (média, banda p25–p75)", fontsize=9)
        ax.grid(alpha=0.25, linewidth=0.6)
        ax.tick_params(labelsize=8)

    coverage_values: list[float] = []
    for record in records:
        if record["status"] != "observed":
            coverage_values.append(0.0)
            continue
        stats = record.get("indices", {}).get("NDVI") or {}
        coverage_values.append(float(stats.get("valid_fraction", 0.0)) * 100.0)
    axes[3].bar(x, coverage_values, color="#2ca02c", width=0.7)
    axes[3].set_ylabel("cobertura válida (%)", fontsize=9)
    axes[3].set_ylim(0, 105)
    axes[3].grid(alpha=0.25, linewidth=0.6, axis="y")
    axes[3].tick_params(labelsize=8)

    ticks = [i for i, m in enumerate(months) if m.endswith(("-01", "-04", "-07", "-10"))]
    axes[3].set_xticks(ticks)
    axes[3].set_xticklabels([months[i] for i in ticks], rotation=45, ha="right", fontsize=8)
    if title:
        fig.suptitle(title, fontsize=10)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_png


def render_geometry_map(
    municipality_coords: Sequence[Sequence[float]],
    aois: dict[str, Sequence[float]],
    out_png: str,
    title: str = "",
    dpi: int = 110,
) -> str:
    """Mapa em WGS84: limite municipal, AOI histórica e AOI de validação."""
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.0, 7.0), constrained_layout=True)
    coords = np.asarray(municipality_coords, dtype="float64")
    ax.fill(coords[:, 0], coords[:, 1], color="#e8e8e8", edgecolor="#444444",
            linewidth=1.0, label="Limite municipal (IBGE)")
    styles = {
        "historical_aoi": ("#d62728", "AOI técnica histórica (PoC)"),
        "validation_aoi": ("#1f77b4", "AOI de validação"),
    }
    for key, (color, label) in styles.items():
        bbox = aois.get(key)
        if not bbox:
            continue
        minx, miny, maxx, maxy = bbox
        ax.plot(
            [minx, maxx, maxx, minx, minx],
            [miny, miny, maxy, maxy, miny],
            color=color,
            linewidth=1.8,
            label=label,
        )
    ax.set_xlabel("longitude (graus, EPSG:4326)", fontsize=9)
    ax.set_ylabel("latitude (graus, EPSG:4326)", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(alpha=0.2, linewidth=0.6)
    if title:
        ax.set_title(title, fontsize=10)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_png
