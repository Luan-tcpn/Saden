"""CONAB SUTIN — polígonos de produção por município e cultura (fase 3 da V2.4).

Fonte oficial: ``https://conab-map.conab.gov.br/sutin-map-web/`` (aplicação
"Análise de Dados Espaciais" da CONAB) e seu GeoServer público
(``https://conab-map.conab.gov.br/geoserver/wfs``).

O que a base oferece (verificado em 2026-11-11):

* camadas do tipo ``wp_geote:<UF>_<CULTURA>_<SAFRA>`` (ex.:
  ``MT_SOJA_2021``, ``MT_CANA_1213``, ``MT_CV_1213``), em EPSG:4326;
* atributos: ``ID``, ``SIGLA_UF``, ``CD_MUN`` (código IBGE), ``NM_MUN``,
  ``AREA_HA`` e ``bbox``;
* polígonos de ocorrência da cultura com área por feição — granularidade
  **submunicipal** (polígonos de ~10 m).

O que a base **não** oferece: **produtividade por feição**. Os atributos não
incluem rendimento (kg/ha) — o que confirma a ausência de referência de
produtividade submunicipal e mantém a restrição D47 (não se converte área em
produtividade).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

USER_AGENT = "SADEN-V2.4/0.1 (investigacao academica; dados abertos)"
WFS = "https://conab-map.conab.gov.br/geoserver/wfs"
WMS = "https://conab-map.conab.gov.br/geoserver/wms"
APP = "https://conab-map.conab.gov.br/sutin-map-web/index.jsp"

# Propriedades observadas na resposta GeoJSON.
FEATURE_PROPERTIES = ["ID", "SIGLA_UF", "CD_MUN", "NM_MUN", "AREA_HA", "bbox"]


class SutinError(RuntimeError):
    """Falha no acesso ao GeoServer da CONAB."""


def _get(url: str, timeout: int = 120) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise SutinError(f"HTTP {exc.code} em {url}") from exc
    except Exception as exc:  # noqa: BLE001
        raise SutinError(f"falha de rede em {url}: {type(exc).__name__}") from exc


def list_layers(uf: str | None = None) -> list[dict[str, str]]:
    """Camadas publicadas no GeoServer (com filtro opcional por UF)."""
    import re

    caps = _get(f"{WMS}?service=WMS&request=GetCapabilities", timeout=180)
    pairs = re.findall(
        r"<Layer[^>]*>\s*<Name>([^<]+)</Name>\s*<Title>([^<]*)</Title>", caps
    )
    layers = []
    for name, title in pairs:
        if not name.startswith("wp_geote:"):
            continue
        if uf and not name.split(":")[-1].upper().startswith(f"{uf.upper()}_"):
            continue
        layers.append({"name": name, "title": title.strip()})
    return layers


def get_features(
    layer: str,
    bbox: list[float] | None = None,
    max_features: int = 100000,
) -> dict[str, Any]:
    """Baixa as feições de uma camada (GeoJSON), opcionalmente por bbox."""
    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": layer,
        "maxFeatures": str(max_features),
        "outputFormat": "application/json",
    }
    if bbox:
        params["bbox"] = ",".join(str(v) for v in bbox) + ",EPSG:4326"
    url = f"{WFS}?{urllib.parse.urlencode(params)}"
    raw = _get(url, timeout=300)
    payload = json.loads(raw)
    features = payload.get("features", [])
    for feature in features:
        feature.setdefault("properties", {})
        feature["properties"]["_layer"] = layer
        feature["properties"]["_source"] = WFS
        feature["properties"]["_acquired_at"] = datetime.now(timezone.utc).isoformat()
    return {
        "layer": layer,
        "url": url,
        "total_features": payload.get("totalFeatures"),
        "returned_features": len(features),
        "features": features,
        "crs": "EPSG:4326",
    }


def summarize(features: list[dict[str, Any]]) -> dict[str, Any]:
    """Resumo por município da camada baixada."""
    by_municipality: dict[str, dict[str, Any]] = {}
    for feature in features:
        props = feature.get("properties", {})
        code = str(props.get("CD_MUN"))
        entry = by_municipality.setdefault(
            code,
            {
                "CD_MUN": code,
                "NM_MUN": props.get("NM_MUN"),
                "SIGLA_UF": props.get("SIGLA_UF"),
                "features": 0,
                "area_ha": 0.0,
            },
        )
        entry["features"] += 1
        entry["area_ha"] += float(props.get("AREA_HA") or 0.0)
    for entry in by_municipality.values():
        entry["area_ha"] = round(entry["area_ha"], 2)
    return {
        "municipalities": sorted(
            by_municipality.values(), key=lambda e: -e["area_ha"]
        ),
        "total_area_ha": round(
            sum(e["area_ha"] for e in by_municipality.values()), 2
        ),
        "total_features": sum(e["features"] for e in by_municipality.values()),
    }


def write_geojson(result: dict[str, Any], path: str) -> str:
    """Grava as feições em GeoJSON (CRS EPSG:4326)."""
    import os

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    payload = {
        "type": "FeatureCollection",
        "name": result["layer"],
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": result["features"],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    return path


def write_csv(result: dict[str, Any], path: str) -> str:
    """Grava os atributos (sem geometria) em CSV."""
    import csv
    import os

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fields = FEATURE_PROPERTIES + ["_layer", "_source", "_acquired_at"]
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for feature in result["features"]:
            writer.writerow(feature.get("properties", {}))
    return path
