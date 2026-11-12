"""Fontes de dados climáticos grillados (reanálises) para o painel.

Três acessos são suportados, todos **sem autenticação** e com
identificação explícita da fonte:

``era5_land`` (Open-Meteo Historical Weather API)
    Reanálise ERA5-Land do Copernicus (ECMWF), resolução ~9 km. Entrega
    temperatura do ar, umidade relativa, ponto de orvalho, temperatura do solo
    e **umidade do solo** (camadas 0–7 cm e 7–28 cm). As variáveis
    acumuladas (precipitação, radiação) e de vento/pressão **não** estão
    disponíveis nesse acesso público.

``era5`` (Open-Meteo Historical Weather API)
    Reanálise ERA5 (0,25°). Entrega o conjunto completo: precipitação,
    radiação, vento, pressão, umidade e temperatura.

``nasa_power`` (NASA POWER, comunidade AG)
    Reanálise MERRA-2 com radiação CERES, ~0,5° × 0,625°,拳头 agroclimática:
    precipitação, temperatura, umidade, radiação, vento, pressão e
    temperatura do solo.

O acesso **nativo** ao ERA5-Land (CDS da Copernicus) exige uma chave de
conta e o espelho ARCO não é resolvido por DNS neste ambiente — a limitação
está registrada em D66 e **não** significa que a fonte ERA5-Land seja
indisponível (ela é usada via `era5_land`).
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Sequence

USER_AGENT = "SADEN-V2.6/0.1 (investigacao academica; dados abertos)"

OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
NASA_POWER_POINT = "https://power.larc.nasa.gov/api/temporal/daily/point"

# --------------------------------------------------------------------------
# Mapeamento das variáveis Open-Meteo -> nomes normalizados do painel.
OPEN_METEO_VARIABLES: dict[str, tuple[str, ...]] = {
    # ERA5-Land
    "temp_media_c": ("temperature_2m_mean",),
    "temp_max_c": ("temperature_2m_max",),
    "temp_min_c": ("temperature_2m_min",),
    "umidade_rel_pct": ("relative_humidity_2m_mean",),
    "temp_orvalho_c": ("dew_point_2m_mean",),
    "solo_temp_0_7_c": ("soil_temperature_0_to_7cm_mean",),
    "solo_temp_7_28_c": ("soil_temperature_7_to_28cm_mean",),
    "solo_umidade_0_7": ("soil_moisture_0_to_7cm_mean",),
    "solo_umidade_7_28": ("soil_moisture_7_to_28cm_mean",),
    # ERA5 (completas)
    "precip_mm": ("precipitation_sum",),
    "radiacao_mj_m2": ("shortwave_radiation_sum",),
    "vento_kmh": ("wind_speed_10m_max",),
    "vento_dir_deg": ("wind_direction_10m_dominant",),
    "pressao_kpa": ("surface_pressure_mean",),
}

# Conversões de unidade (Open-Meteo -> unidade do painel).
OPEN_METEO_FACTORS: dict[str, float] = {
    "radiacao_mj_m2": 1.0,   # já em MJ/m²
    "pressao_kpa": 0.1,      # hPa -> kPa
    "vento_kmh": 1.0,        # já em km/h
    "solo_umidade_0_7": 1.0,  # m³/m³
    "solo_umidade_7_28": 1.0,
}

NASA_POWER_VARIABLES: dict[str, str] = {
    "temp_media_c": "T2M",
    "temp_max_c": "T2M_MAX",
    "temp_min_c": "T2M_MIN",
    "precip_mm": "PRECTOTCORR",
    "radiacao_mj_m2": "ALLSKY_SFC_SW_DWN",
    "umidade_rel_pct": "RH2M",
    "vento_kmh": "WS10M",
    "pressao_kpa": "PS",
    "solo_temp_0_7_c": "TSOIL1",
    "solo_temp_7_28_c": "TSOIL2",
    "temp_orvalho_c": "T2MDEW",
}

NASA_POWER_FACTORS: dict[str, float] = {
    "vento_kmh": 3.6,       # m/s -> km/h
    "pressao_kpa": 1.0,     # kPa
    "radiacao_mj_m2": 1.0,  # MJ/m²/dia
}


class ClimateSourceError(RuntimeError):
    """Falha ao obter dados climáticos grillados."""


@dataclass
class GriddedPoint:
    """Série diária de uma fonte grillada para um ponto."""

    latitude: float
    longitude: float
    source: str
    source_type: str
    records: list[dict[str, Any]]


def _http_json(url: str, timeout: int = 300, retries: int = 3) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
            if raw[:2] == b"\x1f\x8b":
                import gzip

                raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (429, 500, 502, 503, 504):
                break
        except Exception as exc:  # noqa: BLE001
            last = exc
        import time

        time.sleep(2.0 * (attempt + 1))
    raise ClimateSourceError(f"falha ao obter {url}: {last}")


def _chunk_dates(start: str, end: str, max_days: int = 366) -> list[tuple[str, str]]:
    """Divide o intervalo em blocos (a API aceita anos completos)."""
    from datetime import date, timedelta

    begin = date.fromisoformat(start)
    finish = date.fromisoformat(end)
    out: list[tuple[str, str]] = []
    cursor = begin
    while cursor <= finish:
        block_end = min(cursor + timedelta(days=max_days - 1), finish)
        out.append((cursor.isoformat(), block_end.isoformat()))
        cursor = block_end + timedelta(days=1)
    return out


def fetch_open_meteo(
    latitude: float,
    longitude: float,
    start: str,
    end: str,
    model: str = "era5_land",
    variables: Sequence[str] | None = None,
    timezone: str = "UTC",
    timeout: int = 300,
) -> list[dict[str, Any]]:
    """Série diária do Open-Meteo Historical Weather API (ERA5 ou ERA5-Land)."""
    names = list(variables) if variables else [
        "temperature_2m_mean",
        "temperature_2m_max",
        "temperature_2m_min",
        "relative_humidity_2m_mean",
        "dew_point_2m_mean",
        "soil_temperature_0_to_7cm_mean",
        "soil_temperature_7_to_28cm_mean",
        "soil_moisture_0_to_7cm_mean",
        "soil_moisture_7_to_28cm_mean",
        "precipitation_sum",
        "shortwave_radiation_sum",
        "wind_speed_10m_max",
        "wind_direction_10m_dominant",
        "surface_pressure_mean",
    ]
    records: dict[str, dict[str, Any]] = {}
    for begin, finish in _chunk_dates(start, end):
        params = (
            f"latitude={latitude}&longitude={longitude}"
            f"&start_date={begin}&end_date={finish}"
            f"&timezone={timezone}&models={model}"
            "&daily=" + ",".join(names)
        )
        payload = _http_json(f"{OPEN_METEO_ARCHIVE}?{params}", timeout=timeout)
        daily = payload.get("daily") or {}
        times = daily.get("time") or []
        for index, day in enumerate(times):
            record = records.setdefault(day, {"date": day})
            for name in names:
                series = daily.get(name)
                if not series or index >= len(series):
                    continue
                value = series[index]
                if value is None:
                    continue
                record[name] = value
    return [records[day] for day in sorted(records)]


def fetch_nasa_power(
    latitude: float,
    longitude: float,
    start: str,
    end: str,
    timeout: int = 300,
) -> list[dict[str, Any]]:
    """Série diária do NASA POWER (comunidade AG, MERRA-2 + CERES)."""
    params = ",".join(sorted(set(NASA_POWER_VARIABLES.values())))
    start_compact = start.replace("-", "")
    end_compact = end.replace("-", "")
    url = (
        f"{NASA_POWER_POINT}?parameters={params}&community=AG"
        f"&longitude={longitude}&latitude={latitude}"
        f"&start={start_compact}&end={end_compact}&format=JSON"
    )
    payload = _http_json(url, timeout=timeout)
    parameter = (payload.get("properties") or {}).get("parameter") or {}
    # a API do POWER devolve, por variável, um dicionário {AAAAMMDD: valor}
    days: set[str] = set()
    for series in parameter.values():
        if isinstance(series, dict):
            days.update(series.keys())
    records: list[dict[str, Any]] = []
    for day in sorted(days):
        record: dict[str, Any] = {"date": f"{day[:4]}-{day[4:6]}-{day[6:8]}"}
        for normalized, code in NASA_POWER_VARIABLES.items():
            series = parameter.get(code)
            if not isinstance(series, dict):
                continue
            value = series.get(day)
            if value is None:
                continue
            if isinstance(value, list):
                value = value[0] if value else None
            if value is None or float(value) <= -900:
                continue
            record[normalized] = float(value) * NASA_POWER_FACTORS.get(normalized, 1.0)
        records.append(record)
    return records


def normalize_open_meteo(
    records: Sequence[dict[str, Any]], source: str, source_type: str,
    latitude: float, longitude: float,
) -> list[dict[str, Any]]:
    """Converte a saída do Open-Meteo no esquema normalizado do painel."""
    out: list[dict[str, Any]] = []
    for record in records:
        item: dict[str, Any] = {
            "date": record.get("date"),
            "source": source,
            "source_type": source_type,
            "latitude": latitude,
            "longitude": longitude,
        }
        for normalized, names in OPEN_METEO_VARIABLES.items():
            value = None
            for name in names:
                if record.get(name) is not None:
                    value = record[name]
                    break
            if value is None:
                item[normalized] = None
                continue
            item[normalized] = float(value) * OPEN_METEO_FACTORS.get(normalized, 1.0)
        out.append(item)
    return out


def normalize_nasa_power(
    records: Sequence[dict[str, Any]], latitude: float, longitude: float
) -> list[dict[str, Any]]:
    """Converte a saída do NASA POWER no esquema normalizado do painel."""
    out: list[dict[str, Any]] = []
    for record in records:
        item: dict[str, Any] = {
            "date": record.get("date"),
            "source": "NASA-POWER",
            "source_type": "reanalysis",
            "latitude": latitude,
            "longitude": longitude,
        }
        for normalized in NASA_POWER_VARIABLES:
            item[normalized] = record.get(normalized)
        out.append(item)
    return out


def fetch_point(
    latitude: float,
    longitude: float,
    start: str,
    end: str,
    source: str = "era5_land",
    timeout: int = 300,
) -> list[dict[str, Any]]:
    """Série diária normalizada de uma fonte grillada."""
    if source == "era5_land":
        records = fetch_open_meteo(
            latitude, longitude, start, end, model="era5_land", timeout=timeout
        )
        return normalize_open_meteo(
            records, "ERA5-Land", "reanalysis", latitude, longitude
        )
    if source == "era5":
        records = fetch_open_meteo(
            latitude, longitude, start, end, model="era5", timeout=timeout
        )
        return normalize_open_meteo(
            records, "ERA5", "reanalysis", latitude, longitude
        )
    if source == "nasa_power":
        records = fetch_nasa_power(
            latitude, longitude, start, end, timeout=timeout
        )
        return normalize_nasa_power(records, latitude, longitude)
    raise ClimateSourceError(f"fonte desconhecida: {source}")


def write_daily_csv(records: Sequence[dict[str, Any]], path: str) -> str:
    import csv
    import os

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fields: list[str] = []
    for row in records:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in records:
            writer.writerow(row)
    return path


def read_daily_csv(path: str) -> list[dict[str, Any]]:
    import csv
    import os

    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))
