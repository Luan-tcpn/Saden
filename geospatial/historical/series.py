"""Construção da série histórica Sentinel-2 2017–2025 (AOI de validação).

Regras (herdadas da V2.1/D45, sem alteração):

* grade de 20 m em ``EPSG:32721``, alinhada entre meses;
* máscaras SCL: **Perfil B** (D43) — exclui 0, 1, 2, 3, 6, 7, 8, 9, 10, 11;
* seleção mensal pela **fração obstruída sobre a AOI** (não pela nuvem do tile);
* meses sem observação utilizável ficam **vazios** (sem interpolação);
* prefixo do tile: ``MGRS-21LXG`` (consistente com a série da V2.1).

Diferenças em relação à V2.1 (decisão D50):

* as fontes podem ser a coleção **C1 harmonizada** (Earth Search) ou os
  produtos **originais** do Planetary Computer, com perfil radiométrico
  derivado dos metadados de cada item ou, na ausência deles, da regra
  oficial da ESA baseada no ``processing baseline``;
* o pipeline da V2.1 (`s2_poc`) permanece **intacto**.
"""

from __future__ import annotations

import csv
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Iterable

import numpy as np

from s2_poc import config, indices as indices_mod, mask as mask_mod, network, read
from s2_poc.timeseries import choose_best_candidate, month_range
from . import pcatalog, radiometry as radio

DEFAULT_COLLECTIONS = (radio.COLLECTION_C1, radio.COLLECTION_ORIGINAL)
TILE = "MGRS-21LXG"

MONTHLY_COLUMNS = [
    "month",
    "status",
    "reason",
    "item_id",
    "collection",
    "catalog",
    "datetime",
    "tile",
    "baseline",
    "radiometry_profile",
    "offset_source",
    "scale",
    "offset",
    "formula",
    "candidates_evaluated",
    "obstruction_fraction",
    "cloud_cover_tile_pct",
    "total_pixels",
    "valid_pixels",
    "valid_fraction",
    "ndvi_mean",
    "ndvi_median",
    "ndvi_std",
    "ndvi_min",
    "ndvi_max",
    "ndvi_p05",
    "ndvi_p25",
    "ndvi_p75",
    "ndvi_p95",
    "out_of_range_pixels",
    "degenerate_pixels",
]


def month_list(start: str, end: str) -> list[str]:
    return month_range(start, end)


def _search(client: Any, collection: str, bbox: list[float], month: str) -> list[Any]:
    year, mon = int(month[:4]), int(month[5:7])
    next_month = f"{year + 1}-01-01" if mon == 12 else f"{year}-{mon + 1:02d}-01"
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            search = client.search(
                collections=[collection],
                bbox=bbox,
                datetime=f"{month}-01T00:00:00Z/{next_month}T00:00:00Z",
                limit=100,
            )
            return list(search.items())
        except Exception as exc:  # noqa: BLE001 - indisponibilidade do catálogo
            last_error = exc
            time.sleep(3.0 * (attempt + 1))
    raise RuntimeError(f"busca STAC falhou para {collection} {month}: {last_error}")


def covers(item: Any, bbox: list[float]) -> bool:
    return pcatalog.covers(item, bbox)


def select_month_scene(
    candidates: list[dict[str, Any]],
    max_obstruction: float = 0.5,
) -> tuple[dict[str, Any] | None, str]:
    """Escolhe a cena do mês pela menor obstrução sobre a AOI."""
    if not candidates:
        return None, "no_covering_scene_in_catalog"
    best, reason = choose_best_candidate(candidates)
    if best is None:
        return None, reason
    if best["obstruction_fraction"] > max_obstruction:
        return None, "all_candidates_exceed_max_obstruction"
    return best, "selected"


# Nomes de assets variam entre itens do mesmo catálogo (convenção Sentinel Hub
# — "red"/"nir"/"scl" — e convenção ESA — "B04"/"B08"/"SCL").
ASSET_ALIASES = {
    "red": ("red", "B04"),
    "nir": ("nir", "B08"),
    "scl": ("scl", "SCL"),
}


def asset_href_for(item: Any, role: str) -> str:
    """URL do asset para 'red'/'nir'/'scl', aceitando as duas convenções."""
    for name in ASSET_ALIASES[role]:
        asset = item.assets.get(name)
        if asset is not None:
            return asset.href
    raise KeyError(
        f"{item.id}: nenhum asset para {role} ({ASSET_ALIASES[role]})"
    )


def read_ndvi(
    item: Any,
    grid: dict[str, Any],
    profile: dict[str, Any],
    hrefs: dict[str, str] | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Lê B04/B08/SCL na grade e devolve (NDVI, máscara válida, metadados).

    A reflectância usa a escala/offset do **perfil escolhido** (metadado do
    item ou regra do baseline), nunca uma transformação arbitrária.
    ``hrefs`` permite apontar para assets assinados (Planetary Computer).
    """
    if hrefs is None:
        red_href = asset_href_for(item, "red")
        nir_href = asset_href_for(item, "nir")
        scl_href = asset_href_for(item, "scl")
    else:
        red_href = hrefs["red"]
        nir_href = hrefs["nir"]
        scl_href = hrefs["scl"]

    red, red_meta = read.read_resampled(
        red_href, grid, read.Resampling.average, np.nan, "float32"
    )
    nir, nir_meta = read.read_resampled(
        nir_href, grid, read.Resampling.average, np.nan, "float32"
    )
    scl, scl_meta = read.read_resampled(
        scl_href, grid, read.Resampling.nearest, 0, "uint8"
    )

    scale = float(profile["scale"])
    offset = float(profile["offset"])
    nodata = profile.get("nodata") or 0
    red_r = indices_mod.scale_reflectance(red, scale, offset, nodata)
    nir_r = indices_mod.scale_reflectance(nir, scale, offset, nodata)

    ndvi = indices_mod.compute_ndvi(nir_r, red_r)
    keep = mask_mod.keep_mask(scl, "B_restrictive")
    valid = keep & np.isfinite(ndvi)
    ndvi = np.where(valid, ndvi, np.nan).astype("float32")
    meta = {
        "red": red_meta,
        "nir": nir_meta,
        "scl": scl_meta,
        "scale": scale,
        "offset": offset,
        "nodata": nodata,
    }
    return ndvi, valid, meta


def read_scl_masked(
    item: Any,
    grid: dict[str, Any],
    hrefs: dict[str, str] | None = None,
) -> np.ndarray:
    """SCL da cena na grade (vizinho mais próximo)."""
    href = hrefs["scl"] if hrefs else asset_href_for(item, "scl")
    scl, _ = read.read_resampled(
        href, grid, read.Resampling.nearest, 0, "uint8"
    )
    return scl


def obstruction_of_scl(scl: np.ndarray) -> dict[str, Any]:
    from s2_poc import timeseries as ts_mod

    return ts_mod.obstruction_fraction(scl)


def _candidate_hrefs(item: Any, collection: str) -> dict[str, str] | None:
    """URLs dos assets (Earth Search usa URL pública; PC exigiria assinatura)."""
    if collection in (radio.COLLECTION_C1, radio.COLLECTION_ORIGINAL):
        return None
    return {
        "red": pcatalog.asset_href(item, "red", sign=True),
        "nir": pcatalog.asset_href(item, "nir", sign=True),
        "scl": pcatalog.asset_href(item, "scl", sign=True),
    }


def collect_candidates(
    client: Any,
    collection: str,
    bbox: list[float],
    month: str,
    catalog_label: str,
    declared_metadata: bool = True,
) -> list[dict[str, Any]]:
    """Cenas do mês que cobrem a AOI, com perfil radiométrico resolvido."""
    try:
        items = _search(client, collection, bbox, month)
    except Exception:  # noqa: BLE001 - rede
        return []
    candidates: list[dict[str, Any]] = []
    for item in items:
        if pcatalog.tile_code(item) != TILE:
            continue
        if not covers(item, bbox):
            continue
        profile = radio.item_radiometry(item, collection, declared=declared_metadata)
        if profile.get("profile") is None:
            continue
        candidates.append(
            {
                "item": item,
                "item_id": item.id,
                "collection": collection,
                "catalog": catalog_label,
                "profile": profile,
                "cloud_cover": item.properties.get("eo:cloud_cover"),
            }
        )
    return candidates


def build_monthly_series(
    start: str,
    end: str,
    bbox: list[float],
    out_dir: str,
    max_obstruction: float = 0.5,
    max_candidates: int = 3,
    sources: Iterable[tuple[str, str, bool]] | None = None,
    write_rasters: bool = True,
    progress: bool = True,
) -> dict[str, Any]:
    """Processa mês a mês e devolve as linhas da série histórica.

    ``sources`` = [(coleção, rótulo do catálogo, metadado declarado?)]. Por
    padrão: Collection 1 (Earth Search) e originais (Planetary Computer).
    """
    network.configure_tls()
    from pystac_client import Client

    earth = Client.open(config.STAC_URL)
    pc = pcatalog.open_catalog()
    if sources is None:
        sources = (
            (radio.COLLECTION_ORIGINAL, "earth-search", True),
            (radio.COLLECTION_C1, "earth-search", True),
        )

    months = month_list(start, end)
    os.makedirs(out_dir, exist_ok=True)
    grid = read.target_grid("EPSG:32721", bbox, config.TARGET_RES_M)
    rows: list[dict[str, Any]] = []
    rasters_dir = os.path.join(out_dir, "rasters")
    if write_rasters:
        os.makedirs(rasters_dir, exist_ok=True)

    for month in months:
        pool: list[dict[str, Any]] = []
        for collection, label, declared in sources:
            client = earth if collection == radio.COLLECTION_C1 else pc
            coll_name = collection if collection != "pc" else pcatalog.COLLECTION
            pool.extend(
                collect_candidates(
                    client, coll_name, bbox, month, label, declared_metadata=declared
                )
            )
        # ordena por nuvem do tile (para limitar quantas são avaliadas)
        pool.sort(
            key=lambda c: (
                float(c["cloud_cover"]) if c["cloud_cover"] is not None else 999.0,
                c["item_id"],
            )
        )
        scored: list[dict[str, Any]] = []
        for candidate in pool[:max_candidates]:
            hrefs = _candidate_hrefs(candidate["item"], candidate["collection"])
            try:
                scl = read_scl_masked(candidate["item"], grid, hrefs)
            except Exception as exc:  # noqa: BLE001 - rede
                if progress:
                    print(f"[{month}] SCL falhou ({candidate['item_id']}): {exc}")
                continue
            obstruction = obstruction_of_scl(scl)
            scored.append(
                {
                    **candidate,
                    "obstruction_fraction": obstruction["obstruction_fraction"],
                    "hrefs": hrefs,
                }
            )
        best, reason = select_month_scene(scored, max_obstruction=max_obstruction)
        if best is None:
            rows.append(
                {
                    "month": month,
                    "status": "no_usable_observation",
                    "reason": reason,
                    "candidates_evaluated": len(scored),
                }
            )
            if progress:
                print(f"[{month}] sem observação utilizável ({reason})")
            continue

        ndvi, valid, _ = read_ndvi(
            best["item"], grid, best["profile"], best.get("hrefs")
        )
        stats = indices_mod.array_stats(ndvi)
        props = best["item"].properties
        profile = best["profile"]
        rows.append(
            {
                "month": month,
                "status": "observed",
                "reason": None,
                "item_id": best["item_id"],
                "collection": best["collection"],
                "catalog": best["catalog"],
                "datetime": props.get("datetime"),
                "tile": pcatalog.tile_code(best["item"]),
                "baseline": profile["baseline_raw"],
                "radiometry_profile": profile["profile"],
                "offset_source": profile.get("offset_source"),
                "scale": profile["scale"],
                "offset": profile["offset"],
                "formula": profile["formula"],
                "candidates_evaluated": len(scored),
                "obstruction_fraction": best["obstruction_fraction"],
                "cloud_cover_tile_pct": props.get("eo:cloud_cover"),
                "total_pixels": stats["total_pixels"],
                "valid_pixels": stats["valid_pixels"],
                "valid_fraction": stats["valid_fraction"],
                "ndvi_mean": stats["mean"],
                "ndvi_median": stats["median"],
                "ndvi_std": stats["std"],
                "ndvi_min": stats["min"],
                "ndvi_max": stats["max"],
                "ndvi_p05": stats["p05"],
                "ndvi_p25": stats["p25"],
                "ndvi_p75": stats["p75"],
                "ndvi_p95": stats["p95"],
                "out_of_range_pixels": stats["out_of_range_pixels"],
                "degenerate_pixels": int(
                    np.count_nonzero(valid) - np.count_nonzero(np.isfinite(ndvi))
                ),
            }
        )
        if write_rasters:
            np.savez_compressed(
                os.path.join(rasters_dir, f"{month}_ndvi.npz"),
                ndvi=ndvi,
                valid=valid,
                grid=json.dumps(
                    {
                        "crs": str(grid["crs"]),
                        "transform": list(grid["transform"])[:6],
                        "width": grid["width"],
                        "height": grid["height"],
                        "bounds": grid["bounds"],
                    }
                ),
            )
        if progress:
            print(
                f"[{month}] {best['item_id']} ({best['catalog']}, "
                f"baseline {profile['baseline_raw']}, {profile['profile']}) "
                f"NDVI={stats['mean']} cobertura={stats['valid_fraction']:.3f}"
            )
    return {"rows": rows, "grid": grid, "months": months}


def write_monthly_csv(rows: list[dict[str, Any]], path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=MONTHLY_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in MONTHLY_COLUMNS})
    return path


def read_monthly_csv(path: str) -> list[dict[str, Any]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def manifest_payload(
    rows: list[dict[str, Any]],
    grid: dict[str, Any],
    start: str,
    end: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observed = [r for r in rows if r.get("status") == "observed"]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": {"start": start, "end": end, "months": len(rows)},
        "grid": {
            "crs": str(grid["crs"]),
            "res": grid["res"],
            "width": grid["width"],
            "height": grid["height"],
            "transform": list(grid["transform"])[:6],
            "bounds": grid["bounds"],
        },
        "scl_profile": "B_restrictive",
        "tile_preference": TILE,
        "selection_criterion": (
            "menor fração obstruída sobre a AOI (classes SCL de nuvem/sombra/"
            "saturado/nodata); desempate por nuvem do tile e depois por item_id"
        ),
        "radiometry_profiles": dict(radio.PROFILE_DESCRIPTIONS),
        "months_observed": len(observed),
        "months_missing": [r["month"] for r in rows if r.get("status") != "observed"],
        "catalogs_used": sorted({r.get("catalog") for r in observed if r.get("catalog")}),
        "baselines_used": sorted({str(r.get("baseline")) for r in observed if r.get("baseline")}),
        "profiles_used": sorted(
            {r.get("radiometry_profile") for r in observed if r.get("radiometry_profile")}
        ),
        "items": [
            {
                "month": r["month"],
                "item_id": r["item_id"],
                "catalog": r.get("catalog"),
                "collection": r["collection"],
                "datetime": r["datetime"],
                "baseline": r["baseline"],
                "profile": r["radiometry_profile"],
                "offset_source": r.get("offset_source"),
                "formula": r["formula"],
                "valid_fraction": r["valid_fraction"],
                "ndvi_mean": r["ndvi_mean"],
            }
            for r in observed
        ],
    }
    if extra:
        payload.update(extra)
    return payload
