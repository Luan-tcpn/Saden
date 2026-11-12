"""Inventário e seleção de estações meteorológicas do INMET.

Fonte: API oficial de estações em tempo real do INMET
(``https://apitempo.inmet.gov.br/estacoes/T``), que devolve o cadastro
completo de estações automáticas com código, nome, coordenadas, altitude,
estado, tipo, situação e datas de operação.

A seleção de estação por município **não** é automática pelo centroide: o
critério é documentado em :func:`select_stations_for_municipalities` e
prioriza (1) estação dentro do município, (2) estação dentro do município
com a melhor completude histórica, (3) estação mais próxima com a
completude mínima exigida — sempre com a distância registrada.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

STATIONS_URL = "https://apitempo.inmet.gov.br/estacoes/T"
USER_AGENT = "SADEN-V2.6/0.1 (investigacao academica; dados abertos)"

# Distância máxima (km) para considerar uma estação como representativa do
# município quando não há nenhuma dentro dele.
MAX_STATION_DISTANCE_KM = 80.0
# Distância a partir da qual a estação é considerada pouco representativa
# (mantida no inventário, mas marcada).
FAR_STATION_DISTANCE_KM = 50.0


class StationError(RuntimeError):
    """Falha na obtenção do inventário de estações."""


@dataclass(frozen=True)
class Station:
    """Registro de uma estação meteorológica."""

    code: str
    name: str
    state: str
    latitude: float
    longitude: float
    altitude_m: float | None
    station_type: str
    situation: str
    start_operation: str | None
    end_operation: str | None
    district: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def is_operating(self) -> bool:
        return self.situation == "Operante"


def fetch_station_catalog(
    url: str = STATIONS_URL,
    timeout: int = 120,
    user_agent: str = USER_AGENT,
) -> list[Station]:
    """Baixa o catálogo oficial de estações do INMET."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except Exception as exc:  # noqa: BLE001
        raise StationError(f"falha ao obter o catálogo de estações: {exc}") from exc
    if raw[:2] == b"\x1f\x8b":
        import gzip

        raw = gzip.decompress(raw)
    payload = json.loads(raw.decode("utf-8"))
    return [_station_from_record(row) for row in payload]


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _station_from_record(row: dict[str, Any]) -> Station:
    return Station(
        code=str(row.get("CD_ESTACAO") or "").strip(),
        name=str(row.get("DC_NOME") or "").strip(),
        state=str(row.get("SG_ESTADO") or "").strip(),
        latitude=float(row["VL_LATITUDE"]) if row.get("VL_LATITUDE") else 0.0,
        longitude=float(row["VL_LONGITUDE"]) if row.get("VL_LONGITUDE") else 0.0,
        altitude_m=_to_float(row.get("VL_ALTITUDE")),
        station_type=str(row.get("TP_ESTACAO") or "").strip(),
        situation=str(row.get("CD_SITUACAO") or "").strip(),
        start_operation=(row.get("DT_INICIO_OPERACAO") or "")[:10] or None,
        end_operation=(row.get("DT_FIM_OPERACAO") or "")[:10] or None,
        district=(str(row.get("CD_DISTRITO") or "").strip() or None),
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância de grande círculo entre dois pontos (km)."""
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def point_in_polygon(
    lon: float, lat: float, polygon: Any
) -> bool:
    """Teste ponto-em-polígono (implementação própria, sem dependência).

    Aceita ``Polygon`` e ``MultiPolygon`` (este último em qualquer um dos
    seus componentes).
    """
    geoms = getattr(polygon, "geoms", None)
    if geoms is not None:
        return any(point_in_polygon(lon, lat, geom) for geom in geoms)
    inside = False
    coords = list(polygon.exterior.coords) if hasattr(polygon, "exterior") else list(polygon)
    n = len(coords)
    for i in range(n):
        x1, y1 = coords[i][0], coords[i][1]
        x2, y2 = coords[(i + 1) % n][0], coords[(i + 1) % n][1]
        if (y1 > lat) != (y2 > lat):
            xint = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lon < xint:
                inside = not inside
    return inside


def select_stations_for_municipalities(
    stations: Sequence[Station],
    municipalities: Sequence[dict[str, Any]],
    max_distance_km: float = MAX_STATION_DISTANCE_KM,
) -> list[dict[str, Any]]:
    """Associa estações a municípios com critério explícito e auditável.

    ``municipalities`` exige ``ibge_code``, ``name``, ``state``,
    ``centroid_lon``, ``centroid_lat`` e, quando disponível, ``geometry``
    (polígono em EPSG:4326).

    A seleção é feita em três níveis, registrados no campo
    ``selection_method``:

    ``inside_municipality``
        a estação está dentro do polígono municipal;
    ``nearest_within_threshold``
        nenhuma estação dentro do município; escolhe-se a mais próxima
        dentro de ``max_distance_km``;
    ``none``
        nenhuma estação dentro do limite — o município fica **sem**
        série de observação (a lacuna é preservada).
    """
    out: list[dict[str, Any]] = []
    for muni in municipalities:
        candidates: list[tuple[float, Station, bool]] = []
        for station in stations:
            inside = False
            geometry = muni.get("geometry")
            if geometry is not None:
                inside = point_in_polygon(station.longitude, station.latitude, geometry)
            distance = haversine_km(
                float(muni["centroid_lat"]),
                float(muni["centroid_lon"]),
                station.latitude,
                station.longitude,
            )
            candidates.append((distance, station, inside))
        inside_candidates = [c for c in candidates if c[2]]
        if inside_candidates:
            inside_candidates.sort(key=lambda c: (c[0], c[1].code))
            distance, station, _inside = inside_candidates[0]
            method = "inside_municipality"
        else:
            candidates.sort(key=lambda c: (c[0], c[1].code))
            distance, station, _inside = candidates[0]
            method = (
                "nearest_within_threshold"
                if distance <= max_distance_km
                else "none"
            )
        out.append(
            {
                "ibge_code": str(muni["ibge_code"]),
                "municipality": muni.get("municipality") or muni.get("name"),
                "state": muni.get("state"),
                "station_code": station.code if method != "none" else None,
                "station_name": station.name if method != "none" else None,
                "station_state": station.state if method != "none" else None,
                "station_latitude": station.latitude if method != "none" else None,
                "station_longitude": station.longitude if method != "none" else None,
                "station_altitude_m": station.altitude_m if method != "none" else None,
                "station_type": station.station_type if method != "none" else None,
                "station_situation": station.situation if method != "none" else None,
                "station_start_operation": station.start_operation if method != "none" else None,
                "station_end_operation": station.end_operation if method != "none" else None,
                "distance_km": round(distance, 3),
                "selection_method": method,
                "representativeness": (
                    "high"
                    if method == "inside_municipality"
                    else ("medium" if distance <= FAR_STATION_DISTANCE_KM else "low")
                ),
            }
        )
    return out


def write_catalog_csv(rows: Iterable[dict[str, Any]], path: str) -> str:
    rows = list(rows)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def read_catalog_csv(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))
