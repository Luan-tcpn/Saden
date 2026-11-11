"""Busca e seleção de cenas Sentinel-2 L2A via STAC (Earth Search)."""

from __future__ import annotations

from typing import Any

from pystac_client import Client

from . import config


def open_catalog(url: str = config.STAC_URL) -> Client:
    return Client.open(url)


def collection_metadata(client: Client, collection_id: str = config.COLLECTION) -> dict[str, Any]:
    col = client.get_collection(collection_id)
    return {
        "id": col.id,
        "title": col.title,
        "description": (col.description or "")[:400],
        "license": col.license,
        "providers": [
            {"name": p.name, "roles": p.roles, "url": p.url} for p in (col.providers or [])
        ],
    }


def search_items(
    client: Client,
    bbox: list[float],
    start: str,
    end: str,
    max_cloud: float = config.DEFAULT_MAX_CLOUD,
    limit: int = 100,
) -> list[Any]:
    """Busca cenas com cobertura de nuvem abaixo do limite.

    A janela usada no produto é `datetime` (inclusiva). O filtro de nuvem usa a
    extensão `query` do STAC, suportada pelo Earth Search.
    """
    result = client.search(
        collections=[config.COLLECTION],
        bbox=bbox,
        datetime=f"{start}T00:00:00Z/{end}T23:59:59Z",
        query={"eo:cloud_cover": {"lt": max_cloud}},
        limit=limit,
    )
    return list(result.items())


def _bbox_contains(outer: list[float], inner: list[float], tol: float = 1e-6) -> bool:
    return (
        outer[0] <= inner[0] + tol
        and outer[1] <= inner[1] + tol
        and outer[2] >= inner[2] - tol
        and outer[3] >= inner[3] - tol
    )


def _asset_info(item: Any, name: str) -> dict[str, Any] | None:
    asset = item.assets.get(config.ASSETS[name])
    if asset is None:
        return None
    bands = asset.extra_fields.get("raster:bands") or []
    band = bands[0] if bands else {}
    return {
        "href": asset.href,
        "scale": band.get("scale"),
        "offset": band.get("offset"),
        "nodata": band.get("nodata"),
        "spatial_resolution": band.get("spatial_resolution"),
        "data_type": band.get("data_type"),
    }


def item_provenance(item: Any, aoi_bbox: list[float]) -> dict[str, Any]:
    props = item.properties
    assets = {name: _asset_info(item, name) for name in config.ASSETS}
    return {
        "item_id": item.id,
        "collection": item.collection_id,
        "datetime": props.get("datetime"),
        "platform": props.get("platform"),
        "cloud_cover": props.get("eo:cloud_cover"),
        "tile": props.get("grid:code") or props.get("sentinel:grid_square"),
        "mgrs_utm_zone": props.get("sentinel:utm_zone"),
        "proj_epsg": props.get("proj:epsg"),
        "bbox": item.bbox,
        "aoi_fully_inside_item": bool(item.bbox and _bbox_contains(item.bbox, aoi_bbox)),
        "item_href": item.get_self_href(),
        "assets": assets,
    }


def filter_covering(items: list[Any], aoi_bbox: list[float]) -> list[Any]:
    """Mantém apenas cenas cujo bbox contém o AOI inteiro.

    Evita processar cena parcialmente sobreposta (bordas com nodata). Se nenhuma
    cena cobrir, o chamador deve decidir explicitamente o que fazer — não há
    fallback silencioso aqui.
    """
    return [it for it in items if it.bbox and _bbox_contains(it.bbox, aoi_bbox)]


def select_scenes(items: list[Any], max_scenes: int = config.DEFAULT_MAX_SCENES) -> list[Any]:
    """Uma cena por mês (a de menor nuvem), em ordem cronológica.

    A escolha é determinística: menor `eo:cloud_cover`, depois `item.id`.
    """
    by_month: dict[str, Any] = {}
    for item in items:
        dt = item.properties.get("datetime")
        if not dt:
            continue
        month = dt[:7]
        cloud = item.properties.get("eo:cloud_cover")
        cloud = float("inf") if cloud is None else float(cloud)
        current = by_month.get(month)
        if current is None:
            by_month[month] = (cloud, item.id, item)
            continue
        if (cloud, item.id) < (current[0], current[1]):
            by_month[month] = (cloud, item.id, item)
    ordered = [by_month[m][2] for m in sorted(by_month)]
    return ordered[:max_scenes]
