"""Leitor de shapefile (.shp/.dbf) em Python puro.

O ambiente do SADEN não tem ``pyshp``/``geopandas``/``fiona`` e a V2.5
fixou deliberadamente as dependências do geospatial (o ``rasterio`` foi
fixado em 1.4.3 por um crash de memória). Este módulo implementa o
mínimo necessário para ler as malhas municipais do IBGE — geometria
(Polygon/MultiPolygon) e atributos (DBF) — **sem adicionar dependências**.

Formato do shapefile (ESRI Shapefile Technical Description, 1998):
cabeçalho de 100 bytes em big-endian e registros com número, comprimento
e conteúdo; o conteúdo de um Polygon traz ``numParts``/``numPoints`` e as
coordenadas. O DBF é uma tabela dBase com cabeçalho de 32 bytes por campo
e registros de tamanho fixo.
"""

from __future__ import annotations

import struct
from typing import Any, Sequence

SHAPE_NULL = 0
SHAPE_POLYGON = 5
SHAPE_POLYLINE = 3
SHAPE_MULTIPATCH = 31


class ShapefileError(RuntimeError):
    """Falha na leitura do shapefile."""


def _read_dbf(payload: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    """Lê os campos e registros de um DBF (dBase III)."""
    if len(payload) < 32:
        raise ShapefileError("DBF truncado")
    n_records = struct.unpack("<I", payload[4:8])[0]
    header_length = struct.unpack("<H", payload[8:10])[0]
    record_length = struct.unpack("<H", payload[10:12])[0]
    fields: list[tuple[str, int]] = []
    offset = 32
    while payload[offset] != 0x0D:
        raw = payload[offset : offset + 32]
        name = raw[:11].split(b"\x00")[0].decode("latin-1").strip()
        length = raw[16]
        fields.append((name, length))
        offset += 32
    records: list[dict[str, Any]] = []
    for index in range(n_records):
        start = header_length + index * record_length
        record = payload[start : start + record_length]
        if len(record) < record_length:
            break
        if record[:1] == b"*":  # registro deletado
            continue
        values: dict[str, Any] = {}
        cursor = 1
        for name, length in fields:
            raw = record[cursor : cursor + length]
            cursor += length
            # o shapefile do IBGE declara UTF-8 no arquivo .cpg; o fallback
            # latin-1 cobre Bases legais antigas sem .cpg
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
            values[name] = text.strip()
        records.append(values)
    return [name for name, _ in fields], records


def _parse_shape(content: bytes) -> dict[str, Any]:
    """Interpreta o conteúdo de um registro de shape."""
    shape_type = struct.unpack("<i", content[:4])[0]
    if shape_type in (SHAPE_NULL,):
        return {"type": "Null", "rings": []}
    if shape_type not in (SHAPE_POLYGON, SHAPE_POLYLINE, SHAPE_MULTIPATCH):
        raise ShapefileError(f"tipo de shape nao suportado: {shape_type}")
    num_parts, num_points = struct.unpack("<ii", content[36:44])
    parts = struct.unpack(f"<{num_parts}i", content[44 : 44 + 4 * num_parts])
    points_offset = 44 + 4 * num_parts
    points = struct.unpack(
        f"<{2 * num_points}d", content[points_offset : points_offset + 16 * num_points]
    )
    rings: list[list[tuple[float, float]]] = []
    for index, start in enumerate(parts):
        end = parts[index + 1] if index + 1 < num_parts else num_points
        rings.append(
            [(points[2 * i], points[2 * i + 1]) for i in range(start, end)]
        )
    return {"type": "Polygon", "rings": rings}


def read_shapefile(shp_payload: bytes, dbf_payload: bytes) -> list[dict[str, Any]]:
    """Devolve uma lista de ``{"geometry": {...}, "properties": {...}}``."""
    if len(shp_payload) < 100:
        raise ShapefileError("SHP truncado")
    file_code = struct.unpack(">i", shp_payload[0:4])[0]
    if file_code != 9994:
        raise ShapefileError(f"codigo de arquivo invalido: {file_code}")
    offset = 100
    geometries: list[dict[str, Any]] = []
    total = len(shp_payload)
    while offset + 8 <= total:
        _number, content_words = struct.unpack(">ii", shp_payload[offset : offset + 8])
        content = shp_payload[offset + 8 : offset + 8 + content_words * 2]
        if len(content) < 4:
            break
        parsed = _parse_shape(content)
        geometries.append(parsed)
        offset += 8 + content_words * 2
    _names, records = _read_dbf(dbf_payload)
    out: list[dict[str, Any]] = []
    for index, geometry in enumerate(geometries):
        properties = records[index] if index < len(records) else {}
        out.append({"geometry": geometry, "properties": properties})
    return out


def rings_to_geojson(rings: Sequence[Sequence[tuple[float, float]]]) -> dict[str, Any]:
    """Converte anéis de shape em geometria GeoJSON (Polygon/MultiPolygon)."""
    if not rings:
        return {"type": "Polygon", "coordinates": []}
    coordinates = [[[round(x, 7), round(y, 7)] for x, y in ring] for ring in rings]
    if len(coordinates) == 1:
        return {"type": "Polygon", "coordinates": coordinates}
    return {"type": "MultiPolygon", "coordinates": [[ring] for ring in coordinates]}
