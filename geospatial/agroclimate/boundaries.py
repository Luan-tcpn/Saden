"""Malhas municipais oficiais do IBGE — leitura a partir do shapefile.

A API de malhas do IBGE (``servicodados.ibge.gov.br/api/v1/malhas/...``)
responde com *timeout* neste ambiente. A fonte **oficial** equivalente está
no servidor de FTP do IBGE
(``geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/``),
que publica um shapefile por UF e por ano. Este módulo baixa o shapefile da
UF, extrai geometria e centroide por município e grava um GeoJSON.

A geometria é usada apenas para (a) calcular o centroide e (b) verificar se
uma estação meteorológica está **dentro** do município — não para
rasterizar nada.
"""

from __future__ import annotations

import io
import json
import os
import urllib.request
import zipfile
from typing import Any, Iterable, Sequence

USER_AGENT = "SADEN-V2.6/0.1 (investigacao academica; dados abertos)"
BASE = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
    "malhas_municipais/municipio_{year}/UFs/{uf}/{uf}_Municipios_{year}.zip"
)

# Campo de código do município no shapefile (coluna CD_MUN).
CODE_FIELD = "CD_MUN"
NAME_FIELD = "NM_MUN"


def municipality_shapefile_url(uf: str, year: int = 2022) -> str:
    return BASE.format(year=year, uf=uf)


def download_municipality_shapefile(
    uf: str, year: int = 2022, timeout: int = 600
) -> bytes:
    """Baixa o shapefile municipal da UF (zip) em memória."""
    url = municipality_shapefile_url(uf, year)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _read_shapefile(payload: bytes) -> tuple[Any, list[str], list[Any]]:
    """Lê o shapefile do zip com o leitor em Python puro (:mod:`shapefile`)."""
    from . import shapefile as shp_reader

    archive = zipfile.ZipFile(io.BytesIO(payload))
    names = archive.namelist()
    shp_name = next(name for name in names if name.endswith(".shp"))
    dbf_name = next(name for name in names if name.endswith(".dbf"))
    entries = shp_reader.read_shapefile(
        archive.read(shp_name), archive.read(dbf_name)
    )
    geometries = []
    fields: list[str] = []
    records: list[dict[str, Any]] = []
    for entry in entries:
        geometry = shp_reader.rings_to_geojson(entry["geometry"]["rings"])
        geometries.append(geometry)
        properties = entry["properties"]
        if not fields:
            fields = list(properties.keys())
        records.append(properties)
    return geometries, fields, records


def municipality_features(
    uf: str, year: int = 2022, timeout: int = 600
) -> list[dict[str, Any]]:
    """GeoJSON features dos municípios de uma UF."""
    payload = download_municipality_shapefile(uf, year, timeout=timeout)
    geometries, fields, records = _read_shapefile(payload)
    features: list[dict[str, Any]] = []
    for geometry, record in zip(geometries, records):
        item = dict(record)
        code = str(item.get(CODE_FIELD) or "").strip()
        name = str(item.get(NAME_FIELD) or "").strip()
        if not code:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "ibge_code": code,
                    "municipality": name,
                    "state": uf,
                },
                "geometry": geometry,
            }
        )
    return features


def write_geojson(features: Sequence[dict[str, Any]], path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"type": "FeatureCollection", "features": list(features)},
                  handle, ensure_ascii=False)
    return path


def read_geojson(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return json.load(handle).get("features", [])
