"""Geometria municipal oficial (IBGE) e AOIs da validação.

Três geometrias são mantidas **separadas**:

1. ``municipality`` — polígono oficial do IBGE (referência territorial);
2. ``historical_aoi`` — bbox da PoC original (preservada para reprodução);
3. ``validation_aoi`` — recorte de 0,06° dentro do município, na sobreposição
   dos tiles 21LXG/21LXF.

Nenhuma delas é talhão, fazenda ou amostra de lavoura.
"""

from __future__ import annotations

import gzip
import json
import urllib.request
from datetime import datetime, timezone
from typing import Any

from pyproj import Geod, Transformer
from shapely.geometry import box, shape
from shapely.ops import transform as shapely_transform

from . import config

# Projeção de área igual (igual-área global) para métricas de área.
EQUAL_AREA_CRS = "EPSG:6933"
_GEOD = Geod(ellps="WGS84")
_TO_EQUAL_AREA = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)


def _fetch_json(url: str, timeout: int = 90) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SADEN-V2.1/0.2 (validacao academica)",
            "Accept": "application/vnd.geo+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:  # pragma: no cover - falha de rede real
            raise RuntimeError(f"HTTP {resp.status} em {url}")
        raw = resp.read()
    if raw[:2] == b"\x1f\x8b":  # API do IBGE envia gzip mesmo sem pedir
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def _vertex_count(geometry) -> int:
    total = 0
    geoms = geometry.geoms if hasattr(geometry, "geoms") else [geometry]
    for g in geoms:
        exterior = getattr(g, "exterior", None)
        if exterior is not None:
            total += len(exterior.coords)
        for interior in getattr(g, "interiors", []):
            total += len(interior.coords)
    return total


def load_municipality(quality: str = "maxima") -> dict[str, Any]:
    """Baixa e valida a malha municipal oficial do IBGE."""
    if quality == "maxima":
        meta = config.MUNICIPALITY_MAXIMA
    elif quality == "historica":
        meta = config.MUNICIPALITY
    else:  # pragma: no cover - uso interno
        raise ValueError(f"qualidade não suportada: {quality}")

    geojson = _fetch_json(meta["url"])
    features = geojson.get("features") or []
    if len(features) != 1:
        raise RuntimeError(f"malha IBGE inesperada: {len(features)} features")
    geometry = shape(features[0]["geometry"])

    equal_area = shapely_transform(_TO_EQUAL_AREA.transform, geometry)
    geodesic_area_m2 = abs(_GEOD.geometry_area_perimeter(geometry)[0])
    return {
        "geometry": geometry,
        "geometry_type": geometry.geom_type,
        "is_valid": bool(geometry.is_valid),
        "is_empty": bool(geometry.is_empty),
        "vertex_count": _vertex_count(geometry),
        "bbox": list(geometry.bounds),
        "area_km2_geodesic": geodesic_area_m2 / 1e6,
        "area_km2_equal_area": equal_area.area / 1e6,
        "crs": "EPSG:4326 (malha IBGE)",
        "municipality": {
            "ibge_code": meta["ibge_code"],
            "name": meta["name"],
            "uf": meta["uf"],
            "quality": quality,
            "source": meta["source"],
            "url": meta["url"],
        },
        "accessed_utc": datetime.now(timezone.utc).isoformat(),
        "license": "Malhas territoriais do IBGE — dados públicos (ver termos do IBGE)",
    }


def bbox_polygon(bbox: list[float]):
    if len(bbox) != 4:
        raise ValueError(f"bbox deve ter 4 valores: {bbox}")
    minx, miny, maxx, maxy = bbox
    return box(minx, miny, maxx, maxy)


def _equal_area_km2(geometry) -> float:
    return shapely_transform(_TO_EQUAL_AREA.transform, geometry).area / 1e6


def bbox_report(municipality_geometry, bbox: list[float]) -> dict[str, Any]:
    """Quantifica bbox × município (não usa centroide como prova)."""
    bbox_geom = bbox_polygon(bbox)
    intersection = municipality_geometry.intersection(bbox_geom)
    total = _equal_area_km2(bbox_geom)
    inside = _equal_area_km2(intersection) if not intersection.is_empty else 0.0
    outside = max(0.0, total - inside)
    return {
        "bbox": bbox,
        "bbox_area_km2": total,
        "inside_municipality_km2": inside,
        "outside_municipality_km2": outside,
        "inside_fraction": (inside / total) if total else 0.0,
        "fully_inside": bool(municipality_geometry.covers(bbox_geom)),
        "centroid_inside": bool(municipality_geometry.contains(bbox_geom.centroid)),
        "projection_for_area": EQUAL_AREA_CRS,
    }


def historical_aoi_bbox() -> list[float]:
    """Bbox exata da PoC original (não alterar: é registro histórico)."""
    lat = -12.69385
    lon = -55.6009
    half = config.AOI_SIZE_DEG / 2.0
    return [lon - half, lat - half, lon + half, lat + half]


def validation_aoi_bbox() -> list[float]:
    """AOI de validação de 0,06° (config), dentro do município e dos dois tiles."""
    half = config.VALIDATION_AOI["size_deg"] / 2.0
    lon = config.VALIDATION_AOI["center_lon"]
    lat = config.VALIDATION_AOI["center_lat"]
    return [lon - half, lat - half, lon + half, lat + half]


def validation_aoi(municipality_geometry) -> dict[str, Any]:
    bbox = validation_aoi_bbox()
    geom = bbox_polygon(bbox)
    if not municipality_geometry.covers(geom):
        raise RuntimeError("AOI de validação não está contida no município")
    return {
        "kind": "validation_aoi",
        "bbox": bbox,
        "area_km2_equal_area": _equal_area_km2(geom),
        "inside_municipality": True,
        "center": {
            "lon": config.VALIDATION_AOI["center_lon"],
            "lat": config.VALIDATION_AOI["center_lat"],
        },
        "size_deg": config.VALIDATION_AOI["size_deg"],
        "pixels_20m_estimate": round(_equal_area_km2(geom) * 1e6 / (config.TARGET_RES_M ** 2)),
        "note": config.VALIDATION_AOI["note"],
    }


def operational_estimate(municipality_geometry, res_m: float = config.TARGET_RES_M) -> dict[str, Any]:
    """Estimativa de custo para processar o município inteiro (não executado)."""
    area_km2 = municipality_geometry.area if False else _equal_area_km2(municipality_geometry)
    pixels = area_km2 * 1e6 / (res_m ** 2)
    bytes_per_band = pixels * 4  # float32
    return {
        "municipality_area_km2": area_km2,
        "resolution_m": res_m,
        "pixels_per_band": int(round(pixels)),
        "float32_mb_per_band": round(bytes_per_band / 1e6, 1),
        "bands_used": len(config.ASSETS),
        "float32_mb_all_bands": round(bytes_per_band * len(config.ASSETS) / 1e6, 1),
        "note": (
            "Estimativa para uma data. Processar o município inteiro em 20 m em "
            "36 meses não é feito nesta missão; usa-se AOI de validação."
        ),
    }
