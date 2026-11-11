"""AOI: malha municipal do IBGE + janela técnica de 0,10°.

O AOI da prova de conceito é uma janela pequena dentro do município. O município
inteiro NÃO é tratado como talhão e a janela NÃO representa toda a produção.
"""

from __future__ import annotations

import gzip
import json
import urllib.request
from typing import Any

from . import config


def fetch_municipality_geojson(url: str = config.MUNICIPALITY["url"], timeout: int = 60) -> dict[str, Any]:
    """Baixa a malha municipal do IBGE.

    A API do IBGE responde ``Content-Encoding: gzip`` mesmo quando o cliente não
    pede compressão (verificado em 2026-11-11); por isso a descompressão é
    explícita e não depende de `urllib` (que não descomprime sozinho).
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SADEN-V2-PoC/0.1 (academico)",
            "Accept": "application/vnd.geo+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:  # pragma: no cover - falha de rede real
            raise RuntimeError(f"IBGE respondeu {resp.status}")
        raw = resp.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def geometry_bbox(geometry: dict[str, Any]) -> list[float]:
    xs: list[float] = []
    ys: list[float] = []

    def walk(coords):
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            xs.append(float(coords[0]))
            ys.append(float(coords[1]))
        else:
            for child in coords:
                walk(child)

    walk(geometry["coordinates"])
    if not xs:
        raise ValueError("geometria sem coordenadas")
    return [min(xs), min(ys), max(xs), max(ys)]


def _ring_contains(ring: list[list[float]], x: float, y: float) -> bool:
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside


def geometry_contains(geometry: dict[str, Any], x: float, y: float) -> bool:
    gtype = geometry.get("type")
    if gtype == "Polygon":
        rings = geometry["coordinates"]
        if not _ring_contains(rings[0], x, y):
            return False
        return not any(_ring_contains(hole, x, y) for hole in rings[1:])
    if gtype == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            if not polygon:
                continue
            if _ring_contains(polygon[0], x, y) and not any(
                _ring_contains(hole, x, y) for hole in polygon[1:]
            ):
                return True
        return False
    raise ValueError(f"geometria não suportada: {gtype}")


def _ring_area_centroid(ring: list[list[float]]) -> tuple[float, float, float]:
    """Área (em graus²) e centroide de um anel simples, por fórmula do polígono."""
    area2 = 0.0
    cx = 0.0
    cy = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        cross = x1 * y2 - x2 * y1
        area2 += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area2) < 1e-15:
        return 0.0, ring[0][0], ring[0][1]
    area = area2 / 2.0
    return abs(area), cx / (3.0 * area2), cy / (3.0 * area2)


def geometry_centroid(geometry: dict[str, Any]) -> tuple[float, float]:
    rings: list[list[list[float]]] = []
    if geometry["type"] == "Polygon":
        rings = [geometry["coordinates"][0]]
    elif geometry["type"] == "MultiPolygon":
        rings = [p[0] for p in geometry["coordinates"] if p]
    else:  # pragma: no cover
        raise ValueError(f"geometria não suportada: {geometry['type']}")
    best_area = -1.0
    best = (0.0, 0.0)
    for ring in rings:
        area, cx, cy = _ring_area_centroid(ring)
        if area > best_area:
            best_area = area
            best = (cx, cy)
    return best


def build_aoi(geojson: dict[str, Any]) -> dict[str, Any]:
    """Constrói a janela técnica de 0,10° e confirma que o centro está no município."""
    if not geojson.get("features"):
        raise ValueError("GeoJSON do IBGE sem features")
    geometry = geojson["features"][0]["geometry"]
    muni_bbox = geometry_bbox(geometry)

    candidates = [
        ((muni_bbox[0] + muni_bbox[2]) / 2.0, (muni_bbox[1] + muni_bbox[3]) / 2.0),
        geometry_centroid(geometry),
    ]
    center = None
    for cx, cy in candidates:
        if geometry_contains(geometry, cx, cy):
            center = (cx, cy)
            break
    if center is None:  # pragma: no cover - depende da malha real
        raise RuntimeError("não foi possível posicionar o AOI dentro do município")

    half = config.AOI_SIZE_DEG / 2.0
    bbox = [center[0] - half, center[1] - half, center[0] + half, center[1] + half]
    return {
        "kind": "technical_window",
        "size_deg": config.AOI_SIZE_DEG,
        "crs": "EPSG:4326",
        "bbox": bbox,
        "center": {"lon": center[0], "lat": center[1]},
        "center_inside_municipality": True,
        "municipality": dict(config.MUNICIPALITY),
        "municipality_bbox": muni_bbox,
        "note": (
            "Recorte técnico de 0,10° x 0,10° para prova de conceito; não é um "
            "talhão, fazenda ou amostra representativa da produção municipal."
        ),
    }
