"""ZARC (MAPA) por município — aquisição em streaming para o painel.

Os CSVs anuais da *Tábua de Risco* do ZARC são **nacionais** (~200 MB por
safra). Este módulo baixa cada safra em **streaming** (linha a linha, sem
gravar o bruto em disco) e retém apenas as linhas dos municípios solicitados,
identificados pelo **geocódigo IBGE** (coluna ``geocodigo``) — filtro exato,
sem os falsos positivos do filtro por nome usado na V2.4.

A normalização reaproveita :func:`agri.zarc.normalize_rows` (V2.4), de modo
que o formato de saída é idêntico ao da base de Sorriso.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import tempfile
import urllib.request
from typing import Any, Iterable, Sequence

from . import zarc

USER_AGENT = "SADEN-V2.6/0.1 (investigacao academica; dados abertos)"
CKAN_PACKAGE = (
    "https://dados.agricultura.gov.br/api/3/action/package_show"
    "?id=6d3d141c-885e-41a4-ab7f-dc8ff323b96f"
)

# Safras publicadas no conjunto (rótulo do recurso -> safra).
SAFRA_LABELS = [
    "2016/2017",
    "2017/2018",
    "2018/2019",
    "2019/2020",
    "2020/2021",
    "2021/2022",
    "2022/2023",
    "2023/2024",
    "2024/2025",
    "2025/2026",
    "2026/2027",
]


def _fetch(url: str, timeout: int = 300) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw


def package_resources(timeout: int = 120) -> list[dict[str, Any]]:
    """Recursos CSV do conjunto ZARC (uma tábua por safra)."""
    payload = _fetch(CKAN_PACKAGE, timeout=timeout)
    package = json.loads(payload.decode("utf-8"))["result"]
    return [
        resource
        for resource in package.get("resources", [])
        if (resource.get("format") or "").lower() == "csv"
    ]


def resource_for_safra(
    resources: Sequence[dict[str, Any]], safra: str
) -> dict[str, Any] | None:
    """Localiza o recurso CSV de uma safra (rótulo ``Safra 2024/2025``)."""
    wanted = f"Safra {safra}"
    for resource in resources:
        name = str(resource.get("name") or "")
        if wanted.lower() in name.lower():
            return resource
    return None


def fetch_safra_for_municipalities(
    resource: dict[str, Any],
    geocodes: Iterable[str],
    timeout: int = 1800,
) -> list[dict[str, str]]:
    """Baixa a tábua de uma safra em streaming e retém os municípios pedidos.

    O arquivo bruto **não** é gravado em disco; apenas as linhas dos
    geocódigos solicitados são mantidas em memória.
    """
    wanted = {str(code).strip() for code in geocodes if str(code).strip()}
    if not wanted:
        return []
    url = resource.get("url")
    if not url:
        return []
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    kept: list[dict[str, str]] = []
    with urllib.request.urlopen(request, timeout=timeout) as response:
        stream = io.TextIOWrapper(response, encoding="utf-8-sig", newline="")
        reader = csv.DictReader(stream, delimiter=";")
        for row in reader:
            code = str(row.get("geocodigo") or "").strip()
            if code in wanted:
                kept.append(row)
    return kept


def normalize_rows_for_panel(
    raw_rows: Sequence[dict[str, str]],
    resource: dict[str, Any],
) -> list[dict[str, Any]]:
    """Normaliza as linhas brutas com o interpretador da V2.4.

    O interpretador da V2.4 lê de um arquivo; as linhas filtradas são gravadas
    num arquivo temporário (descartado ao final) para que a **mesma** lógica
    seja usada — sem duplicar a normalização.
    """
    if not raw_rows:
        return []
    metadata = {
        "id": "6d3d141c-885e-41a4-ab7f-dc8ff323b96f",
        "license_title": "Creative Commons Atribuição",
    }
    with tempfile.NamedTemporaryFile(
        "w", suffix=".csv", delete=False, encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(raw_rows[0].keys()), delimiter=";"
        )
        writer.writeheader()
        for row in raw_rows:
            writer.writerow(row)
        temp_path = handle.name
    try:
        return zarc.normalize_rows(temp_path, resource, metadata)
    finally:
        os.unlink(temp_path)


def fetch_panel(
    geocodes: Iterable[str],
    safras: Sequence[str] = tuple(SAFRA_LABELS),
    timeout: int = 1800,
    progress: Any = None,
) -> list[dict[str, Any]]:
    """ZARC normalizado de todos os municípios solicitados, em todas as safras."""
    codes = [str(code).strip() for code in geocodes if str(code).strip()]
    if not codes:
        return []
    resources = package_resources()
    out: list[dict[str, Any]] = []
    for safra in safras:
        resource = resource_for_safra(resources, safra)
        if resource is None:
            continue
        if progress is not None:
            progress(f"ZARC {safra}: baixando a tabela nacional...")
        raw = fetch_safra_for_municipalities(resource, codes, timeout=timeout)
        if progress is not None:
            progress(f"ZARC {safra}: {len(raw)} linhas de {len(codes)} municípios")
        out.extend(normalize_rows_for_panel(raw, resource))
    return out
