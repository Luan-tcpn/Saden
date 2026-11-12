"""Aquisição e normalização dos dados meteorológicos históricos do INMET.

Os arquivos anuais (``https://portal.inmet.gov.br/uploads/dadoshistoricos/<ano>.zip``)
são lidos **parcialmente** por HTTP *Range* (:mod:`agroclimate.remote_zip`):
apenas o CSV da estação necessária é transferido, sem gravar o arquivo bruto
em disco.

Os CSVs do INMET trazem um cabeçalho de metadados (REGIÃO, UF, ESTAÇÃO, CÓDIGO
WMO, LATITUDE, LONGITUDE, ALTITUDE, INÍCIO, FIM) seguido do cabeçalho de
variáveis e dos registros **horários** (fuso horário do INMET: UTC−3).

Este módulo converte os registros horários em série **diária**, preservando
a distinção entre *ausente* (``-9999``) e *zero* (precipitação realmente zero).
"""

from __future__ import annotations

import csv
import io
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

from . import remote_zip

ARCHIVE_URL = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip"
USER_AGENT = remote_zip.DEFAULT_USER_AGENT

# Sentinela de valor ausente nos arquivos do INMET.
MISSING_SENTINELS = {-9999.0, -9999}

# Variáveis normalizadas: padrão de busca no cabeçalho, unidade de origem,
# fator de conversão para a unidade normalizada e agregação diária.
# A busca é por expressão regular sobre o cabeçalho em maiúsculas, tolerante
# às diferenças entre estações automáticas (nomes longos, prefixo AUT) e
# convencionais (nomes curtos).
COLUMN_SPECS: dict[str, dict[str, Any]] = {
    "temp_media_c": {
        "patterns": (
            r"TEMPERATURA DO AR\s*-\s*BULBO SECO",
            r"TEMPERATURA\s+MEDIA",
            r"TEMP\s*MEDIA",
        ),
        "source_unit": "°C",
        "factor": 1.0,
        "daily": "mean",
    },
    "temp_max_c": {
        "patterns": (r"TEMPERATURA\s+M[ÁA]XIMA", r"TEMP\s*MAX"),
        "source_unit": "°C",
        "factor": 1.0,
        "daily": "max",
    },
    "temp_min_c": {
        "patterns": (r"TEMPERATURA\s+M[ÍI]NIMA", r"TEMP\s*MIN"),
        "source_unit": "°C",
        "factor": 1.0,
        "daily": "min",
    },
    "temp_orvalho_c": {
        "patterns": (r"TEMPERATURA DO PONTO DE ORVALHO",),
        "source_unit": "°C",
        "factor": 1.0,
        "daily": "mean",
    },
    "umidade_rel_pct": {
        "patterns": (r"UMIDADE RELATIVA DO AR", r"UMID\s*REL"),
        "source_unit": "%",
        "factor": 1.0,
        "daily": "mean",
    },
    "precip_mm": {
        "patterns": (r"PRECIPITA[ÇC][ÃA]O TOTAL", r"^CHUVA$", r"CHUVA"),
        "source_unit": "mm",
        "factor": 1.0,
        "daily": "sum",
    },
    "pressao_kpa": {
        "patterns": (
            r"PRESS[AÃ]O ATMOSF[ÉE]RICA AO NIVEL DA ESTACAO",
            r"PRESS[AÃ]O",
        ),
        "source_unit": "mB",
        "factor": 0.1,
        "daily": "mean",
    },
    "vento_kmh": {
        "patterns": (r"VENTO,\s*VELOCIDADE HOR[ÁA]RIA", r"VELOC\s*VENTO"),
        "source_unit": "m/s",
        "factor": 3.6,
        "daily": "mean",
    },
    "vento_max_kmh": {
        "patterns": (r"VENTO,\s*RAJADA MAXIMA", r"VENTO\s*MAX"),
        "source_unit": "m/s",
        "factor": 3.6,
        "daily": "max",
    },
    "vento_dir_deg": {
        "patterns": (r"VENTO,\s*DIRE[ÇC][ÃA]O HOR[ÁA]RIA", r"DIRE[ÇC][ÃA]O VENTO"),
        "source_unit": "graus",
        "factor": 1.0,
        "daily": "mean",
    },
    "radiacao_mj_m2": {
        "patterns": (r"RADIACAO GLOBAL", r"RADIA[ÇC][ÃA]O"),
        "source_unit": "kJ/m²",
        "factor": 0.001,
        "daily": "sum",
    },
}


class InmetError(RuntimeError):
    """Falha na aquisição de dados do INMET."""


@dataclass
class StationFile:
    """Um CSV de estação extraído do ZIP anual."""

    year: int
    station_code: str
    member: str
    metadata: dict[str, str]
    header: list[str]
    rows: list[list[str]]


def _normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().upper())


def _is_variable_header(parts: Sequence[str]) -> bool:
    """Reconhece a linha de cabeçalho de variáveis do INMET.

    A primeira coluna começa por ``DATA`` e a segunda por ``HORA``. O teste
    é estrito porque o INMET também emite linhas de metadados como
    ``DATA DE FUNDAÇÃO (YYYY-MM-DD):;16/12/02``, que não são cabeçalho.
    """
    if len(parts) < 2:
        return False
    first = _normalize_key(parts[0])
    second = _normalize_key(parts[1])
    return bool(re.match(r"^DATA(\s*\(.*\))?$", first)) and bool(
        re.match(r"^HORA", second)
    )


def _match_column(header: Sequence[str], patterns: Sequence[str]) -> int | None:
    """Índice da primeira coluna que casa com um dos padrões (regex)."""
    for pattern in patterns:
        compiled = re.compile(pattern, re.IGNORECASE)
        for index, name in enumerate(header):
            if compiled.search(_normalize_key(name)):
                return index
    return None


def _to_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    if number in MISSING_SENTINELS:
        return None
    return number


def _normalize_date(text: str) -> str:
    """Normaliza a data do INMET (``YYYY/MM/DD``) para ``YYYY-MM-DD``."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    raw = raw.split(" ")[0]
    match = re.match(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$", raw)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$", raw)
    if match:
        return f"{match.group(3)}-{int(match.group(2)):02d}-{int(match.group(1)):02d}"
    return raw


def _normalize_hour(text: str) -> str:
    """Normaliza a hora (``0000 UTC`` / ``00:00``) para ``HH:MM``."""
    raw = str(text or "").strip().upper().replace("UTC", "").strip()
    if not raw:
        return ""
    if ":" in raw:
        parts = raw.split(":")
        try:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        except ValueError:
            return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 4:
        return f"{int(digits[:2]):02d}:{int(digits[2:4]):02d}"
    return ""


def parse_station_csv(year: int, member: str, payload: bytes) -> StationFile:
    """Interpreta o CSV de uma estação (metadados + variáveis + horários)."""
    text = payload.decode("latin-1")
    lines = text.splitlines()
    metadata: dict[str, str] = {}
    index = 0
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        parts = line.split(";")
        key = parts[0].strip().rstrip(":").upper()
        if key in {"REGIÃO", "REGIAO", "UF", "ESTACAO", "ESTACAO", "CODIGO (WMO)",
                   "CODIGO (WMO)", "LATITUDE", "LONGITUDE", "ALTITUDE",
                   "INICIO", "FIM"}:
            metadata[key] = parts[1].strip() if len(parts) > 1 else ""
            continue
        if ";" in line and _is_variable_header(parts):
            header = parts
            index += 1
            break
    else:
        header = []
        index = len(lines)
    rows = [line.split(";") for line in lines[index:] if line.strip()]
    return StationFile(
        year=year,
        station_code=metadata.get("CODIGO (WMO)", "").strip(),
        member=member,
        metadata=metadata,
        header=header,
        rows=rows,
    )


def _extract_hour(rows: Sequence[Sequence[str]], header: Sequence[str]) -> str:
    index_date = _match_column(header, ("DATA",))
    index_hour = _match_column(header, ("HORA", "HORA UTC", "HORARIO"))
    if index_date is None or index_hour is None:
        return ""
    for row in rows:
        if len(row) <= max(index_date, index_hour):
            continue
        date_part = str(row[index_date]).strip()
        hour_part = str(row[index_hour]).strip()
        if not date_part or not hour_part:
            continue
        return f"{date_part}T{hour_part}"
    return ""


def to_daily_records(
    station_file: StationFile,
) -> list[dict[str, Any]]:
    """Converte os registros horários em uma série diária por estação.

    O fuso horário do INMET é UTC−3 (``America/Campo_Grande``) e os arquivos
    automatizados registram a **hora UTC**; a data civil local corresponde ao
    dia da hora UTC registrado no arquivo (a hora local 00:00 corresponde a
    03:00 UTC do mesmo dia civil). A data é preservada sem deslocamento.
    """
    header = station_file.header
    index_date = _match_column(header, (r"^DATA", r"^DATA/HORA$"))
    index_hour = _match_column(header, (r"^HORA", r"HORA UTC", r"HOR[ÁA]RIO"))
    if index_date is None or index_hour is None:
        raise InmetError(f"CSV sem colunas DATA/HORA: {station_file.member}")
    columns: dict[str, int] = {}
    for normalized, spec in COLUMN_SPECS.items():
        found = _match_column(header, spec["patterns"])
        if found is not None:
            columns[normalized] = found

    buckets: dict[str, dict[str, list[float]]] = {}
    for row in station_file.rows:
        if len(row) <= max(index_date, index_hour):
            continue
        day = _normalize_date(row[index_date])
        if not day or day.startswith(("DATA", "Data")):
            continue
        values: dict[str, list[float]] = {}
        for normalized, column in columns.items():
            if column >= len(row):
                continue
            number = _to_float(row[column])
            if number is None:
                continue
            factor = float(COLUMN_SPECS[normalized]["factor"])
            values.setdefault(normalized, []).append(number * factor)
        bucket = buckets.setdefault(day, {})
        for normalized, series in values.items():
            bucket.setdefault(normalized, []).extend(series)

    out: list[dict[str, Any]] = []
    for day in sorted(buckets):
        record: dict[str, Any] = {
            "date": day,
            "year": station_file.year,
            "station_code": station_file.station_code,
            "source": "INMET",
            "source_type": "station_observation",
        }
        for normalized, spec in COLUMN_SPECS.items():
            series = buckets[day].get(normalized)
            if not series:
                record[normalized] = None
                record[f"{normalized}_n_obs"] = 0
                continue
            aggregation = spec["daily"]
            if aggregation == "sum":
                record[normalized] = float(sum(series))
            elif aggregation == "max":
                record[normalized] = float(max(series))
            elif aggregation == "min":
                record[normalized] = float(min(series))
            else:
                record[normalized] = float(sum(series) / len(series))
            record[f"{normalized}_n_obs"] = len(series)
        out.append(record)
    return out


def year_archive_url(year: int) -> str:
    return ARCHIVE_URL.format(year=year)


def list_year_members(year: int, timeout: int = 180) -> dict[str, Any]:
    """Índice dos membros do ZIP de um ano (sem baixar conteúdo)."""
    return remote_zip.zip_members(year_archive_url(year), timeout=timeout)


def find_member(members: Iterable[str], station_code: str) -> str | None:
    """Localiza o membro da estação pelo código WMO (ex.: ``A904``).

    O nome do arquivo segue o padrão
    ``<ano>/INMET_<tipo>_<UF>_<código>_<nome>_<início>_A_<fim>.CSV``; o código
    WMO é localizado por expressão regular para não depender da posição.
    """
    code = station_code.strip().upper()
    pattern = re.compile(rf"(?:^|_)({re.escape(code)})(?:_|\.)", re.IGNORECASE)
    for name in members:
        base = os.path.basename(name)
        if pattern.search(base):
            return name
    return None


def fetch_station_year(
    year: int,
    station_code: str,
    members: dict[str, Any] | None = None,
    timeout: int = 180,
) -> StationFile | None:
    """Extrai e interpreta o CSV de uma estação em um ano."""
    if members is None:
        members = list_year_members(year, timeout=timeout)
    member = find_member(members.keys(), station_code)
    if member is None:
        return None
    payload = remote_zip.read_member(
        year_archive_url(year), member, timeout=timeout
    )
    return parse_station_csv(year, member, payload)


def fetch_station_range(
    years: Sequence[int],
    station_code: str,
    timeout: int = 180,
) -> list[dict[str, Any]]:
    """Série diária de uma estação entre anos (reentrante e retomável)."""
    records: list[dict[str, Any]] = []
    for year in years:
        station_file = fetch_station_year(year, station_code, timeout=timeout)
        if station_file is None:
            continue
        records.extend(to_daily_records(station_file))
    return records


def write_daily_csv(
    records: Iterable[dict[str, Any]], path: str
) -> str:
    records = list(records)
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
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))
