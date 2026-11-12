"""Calendário agrícola oficial do ZARC (MAPA) — aquisição e normalização.

Fonte: portal de dados abertos do MAPA,
``https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-dc8ff323b96f``
(Zoneamento Agrícola de Risco Climático — Tábua de Risco), licença
**Creative Commons Atribuição**. Domínio diferente do ``dados.gov.br``
(que exige autenticação) — o bloqueio HTTP 401 observado na V2.2 **não** se
aplica a esta base.

O CSV traz, por município, cultura, ciclo, solo, clima e o **risco de cada
decêndio** (``dec1`` … ``dec36``) da janela de plantio, além da **portaria**
de origem. O campo ``Produtividade`` é um **código de classe de
produtividade do ZARC** (não é kg/ha e não é produtividade observada).

O ZARC expressa **períodos recomendados de plantio sob condição de risco** —
não datas em que os produtores plantaram de fato.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Iterable

USER_AGENT = "SADEN-V2.4/0.1 (investigacao academica; dados abertos)"
CKAN_PACKAGE = (
    "https://dados.agricultura.gov.br/api/3/action/package_show"
    "?id=6d3d141c-885e-41a4-ab7f-dc8ff323b96f"
)

# Safras publicadas no conjunto (rótulos do catálogo).
SAFRAS = {
    "2016/2017": "2016-2017",
    "2017/2018": "2017-2018",
    "2018/2019": "2018-2019",
    "2019/2020": "2019-2020",
    "2020/2021": "2020-2021",
    "2021/2022": "2021-2022",
    "2022/2023": "2022-2023",
    "2023/2024": "2023-2024",
    "2024/2025": "2024-2025",
    "2025/2026": "2025-2026",
    "2026/2027": "2026-2027",
}

# Classes de risco codificadas nos decêndios (0 = fora da janela).
RISK_CLASSES = {
    0: "fora_da_janela",
    10: "muito_baixo",
    20: "baixo",
    30: "medio",
    40: "alto",
}

# recommendation thresholds (used to derive the recommended window)
RISK_RECOMMENDED = (10, 20)  # very low / low

NORMALIZED_FIELDS = [
    "institution",
    "dataset_name",
    "dataset_id",
    "resource_id",
    "resource_url",
    "acquired_at",
    "resource_last_modified",
    "license",
    "safra",
    "safra_ini",
    "safra_fin",
    "cultura",
    "cod_cultura",
    "ciclo",
    "cod_ciclo",
    "solo",
    "cod_solo",
    "clima",
    "cod_clima",
    "outros_manejos",
    "cod_outros_manejos",
    "municipio",
    "uf",
    "geocodigo",
    "cod_nm",
    "cod_munic",
    "cod_meso",
    "cod_micro",
    "portaria",
    "zarc_produtividade_codigo",
    "decendios_com_risco",
    "janela_inicio_decendio",
    "janela_fim_decendio",
    "janela_inicio_data",
    "janela_fim_data",
    "janela_base",
    "natureza",
    "observacao",
]


class ZarcError(RuntimeError):
    """Falha na aquisição dos dados do ZARC."""


def _fetch(url: str, timeout: int = 600) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise ZarcError(f"HTTP {exc.code} em {url}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ZarcError(f"falha de rede em {url}: {type(exc).__name__}") from exc


def package_metadata(timeout: int = 120) -> dict[str, Any]:
    """Metadados do conjunto no CKAN do MAPA (recursos, licença, atualização)."""
    raw = _fetch(CKAN_PACKAGE, timeout=timeout)
    payload = json.loads(raw.decode("utf-8"))
    pkg = payload["result"]
    return {
        "id": pkg.get("id"),
        "name": pkg.get("name"),
        "title": pkg.get("title"),
        "license_title": pkg.get("license_title"),
        "license_id": pkg.get("license_id"),
        "metadata_modified": pkg.get("metadata_modified"),
        "notes": (pkg.get("notes") or "")[:600],
        "resources": [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "format": r.get("format"),
                "url": r.get("url"),
                "last_modified": r.get("last_modified"),
                "created": r.get("created"),
                "size": r.get("size"),
            }
            for r in pkg.get("resources", [])
        ],
        "source_url": CKAN_PACKAGE,
        "dataset_page": (
            "https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-dc8ff323b96f"
        ),
    }


def resource_for_safra(metadata: dict[str, Any], safra: str) -> dict[str, Any] | None:
    """Localiza o recurso CSV de uma safra pelo rótulo do catálogo."""
    label = f"Safra {safra}"
    for resource in metadata.get("resources", []):
        name = str(resource.get("name") or "")
        if label.lower() in name.lower() and (resource.get("format") or "").lower() == "csv":
            return resource
    return None


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_and_filter(
    resource: dict[str, Any],
    raw_path: str,
    filtered_path: str,
    municipality: str = "Sorriso",
    uf: str = "MT",
    chunk_size: int = 1 << 20,
) -> dict[str, Any]:
    """Baixa o CSV da safra e grava (a) o bruto e (b) o recorte do município.

    O arquivo bruto tem centenas de MB (todo o Brasil) e **não** é versionado;
    o recorte é a evidência versionada. URL, tamanho e SHA-256 ficam no
    manifesto.
    """
    os.makedirs(os.path.dirname(os.path.abspath(raw_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(filtered_path)), exist_ok=True)
    request = urllib.request.Request(resource["url"], headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    total = 0
    kept = 0
    header: list[str] | None = None
    with urllib.request.urlopen(request, timeout=900) as response:
        with open(raw_path, "wb") as raw_handle, open(
            filtered_path, "w", newline="", encoding="utf-8"
        ) as filtered:
            writer = csv.writer(filtered, delimiter=";")
            buffer = b""
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
                total += len(chunk)
                raw_handle.write(chunk)
                buffer += chunk
                while True:
                    index = buffer.find(b"\n")
                    if index < 0:
                        break
                    line = buffer[:index]
                    buffer = buffer[index + 1 :]
                    text = line.decode("utf-8-sig", "replace").rstrip("\r")
                    if header is None:
                        header = text.split(";")
                        writer.writerow(header)
                        continue
                    if uf in text and municipality in text:
                        writer.writerow(text.split(";"))
                        kept += 1
            if buffer:
                text = buffer.decode("utf-8-sig", "replace").rstrip("\r")
                if header is None:
                    header = text.split(";")
                    writer.writerow(header)
                elif uf in text and municipality in text:
                    writer.writerow(text.split(";"))
                    kept += 1
    return {
        "resource_id": resource.get("id"),
        "resource_name": resource.get("name"),
        "url": resource.get("url"),
        "last_modified": resource.get("last_modified"),
        "bytes": total,
        "sha256": digest.hexdigest(),
        "raw_path": raw_path,
        "filtered_path": filtered_path,
        "records_total_estimate": None,
        "records_kept": kept,
        "columns": header or [],
        "acquired_at": datetime.now(timezone.utc).isoformat(),
    }


def _decend_value(raw: str | None) -> int:
    if raw is None:
        return 0
    text = str(raw).strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _decend_to_dates(year: int, decend: int) -> tuple[str, str]:
    """Datas aproximadas de início e fim de um decêndio (10 dias)."""
    start_day = (decend - 1) * 10 + 1
    end_day = start_day + 9
    start = datetime(year, 1, 1)
    from datetime import timedelta

    return (
        (start + timedelta(days=start_day - 1)).date().isoformat(),
        (start + timedelta(days=end_day - 1)).date().isoformat(),
    )


def normalize_rows(
    csv_path: str,
    resource: dict[str, Any],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    """Normaliza o recorte do município para a base do calendário."""
    rows: list[dict[str, Any]] = []
    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for raw in reader:
            decendios = {
                key: _decend_value(raw.get(key))
                for key in (f"dec{i}" for i in range(1, 37))
                if raw.get(key) not in (None, "")
            }
            risky = {int(k[3:]): v for k, v in decendios.items() if v}
            recommended = sorted(
                d for d, v in risky.items() if v in RISK_RECOMMENDED
            )
            if recommended:
                first, last = recommended[0], recommended[-1]
                year = int(raw.get("SafraIni") or 0)
                start_date, _ = _decend_to_dates(year, first)
                _, end_date = _decend_to_dates(year, last)
                janela = f"decêndios {first}-{last}"
            else:
                first = last = None
                start_date = end_date = None
                janela = None
            rows.append(
                {
                    "institution": "MAPA",
                    "dataset_name": "Zoneamento Agrícola de Risco Climático (Zarc) — Tábua de Risco",
                    "dataset_id": f"CKAN:{metadata.get('id')}",
                    "resource_id": resource.get("id"),
                    "resource_url": resource.get("url"),
                    "acquired_at": datetime.now(timezone.utc).isoformat(),
                    "resource_last_modified": resource.get("last_modified"),
                    "license": metadata.get("license_title"),
                    "safra": f"{raw.get('SafraIni')}/{str(raw.get('SafraFin'))[-2:]}",
                    "safra_ini": raw.get("SafraIni"),
                    "safra_fin": raw.get("SafraFin"),
                    "cultura": raw.get("Nome_cultura"),
                    "cod_cultura": raw.get("Cod_Cultura"),
                    "ciclo": raw.get("Cod_Ciclo"),
                    "cod_ciclo": raw.get("Cod_Ciclo"),
                    "solo": raw.get("Cod_Solo"),
                    "cod_solo": raw.get("Cod_Solo"),
                    "clima": raw.get("Nome_Clima"),
                    "cod_clima": raw.get("Cod_Clima"),
                    "outros_manejos": raw.get("Nome_Outros_Manejos"),
                    "cod_outros_manejos": raw.get("Cod_Outros_Manejos"),
                    "municipio": raw.get("municipio"),
                    "uf": raw.get("UF"),
                    "geocodigo": raw.get("geocodigo"),
                    "cod_nm": raw.get("Cod_NM"),
                    "cod_munic": raw.get("Cod_Munic"),
                    "cod_meso": raw.get("Cod_Meso"),
                    "cod_micro": raw.get("Cod_Micro"),
                    "portaria": raw.get("Portaria"),
                    "zarc_produtividade_codigo": raw.get("Produtividade"),
                    "decendios_com_risco": ";".join(
                        f"{d}:{RISK_CLASSES.get(v, v)}" for d, v in sorted(risky.items())
                    ),
                    "janela_inicio_decendio": first,
                    "janela_fim_decendio": last,
                    "janela_inicio_data": start_date,
                    "janela_fim_data": end_date,
                    "janela_base": janela,
                    "natureza": "recomendacao_oficial_de_plantio_por_risco",
                    "observacao": (
                        "Janela recomendada do ZARC (decêndios com risco muito baixo "
                        "ou baixo); não é observação de plantio nem produtividade."
                    ),
                    "_raw_decendios": risky,
                }
            )
    return rows


def write_normalized(rows: Iterable[dict[str, Any]], path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fields = [f for f in NORMALIZED_FIELDS]
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def read_normalized(path: str) -> list[dict[str, Any]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))
