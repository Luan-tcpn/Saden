"""Geometria oficial do município para a V2.2 (reaproveita a V2.1, D42).

A malha é a mesma já validada na V2.1: IBGE API de malhas, qualidade
``maxima``, código 5107925. O carregamento é feito uma vez por processo.
"""

from __future__ import annotations

from typing import Any

_CACHE: dict[str, Any] = {}


def municipality_geometry(quality: str = "maxima") -> Any:
    """Devolve a geometria (shapely) do município 5107925."""
    if quality not in _CACHE:
        from s2_poc import geometry as s2_geometry

        municipality = s2_geometry.load_municipality(quality)
        _CACHE[quality] = municipality
    return _CACHE[quality]["geometry"]


def municipality_metadata(quality: str = "maxima") -> dict[str, Any]:
    """Metadados da malha (área, validade, vértices, URL, data de acesso)."""
    if quality not in _CACHE:
        municipality_geometry(quality)
    payload = _CACHE[quality]
    return {key: value for key, value in payload.items() if key != "geometry"}
