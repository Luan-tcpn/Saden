"""Aquisição e leitura da API SIDRA (IBGE) — Produção Agrícola Municipal.

Documentação oficial: https://apisidra.ibge.gov.br/definicoes
Consulta de valores: https://apisidra.ibge.gov.br/values/t/{tabela}/n{nivel}/
{localidades}/v{variáveis}/p{período}/c{classificação}/{categorias}

Sem chave, sem custo, acesso público. O formato de resposta é uma lista em que
o primeiro elemento é o cabeçalho (descrição dos campos) e os demais são as
linhas de dados.
"""

from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Iterable

from . import config

USER_AGENT = "SADEN-V2.2/0.1 (investigacao academica; sem chave)"

# Convenção de valores do SIDRA (documentada pelo IBGE).
SIDRA_MISSING = ".."      # dado não disponível
SIDRA_NIL = "-"           # valor zero (nil)
SIDRA_NOT_APPLICABLE = "..."  # não aplicável
SIDRA_SUPPRESSED = "x"    # valor suprimido


class SidraError(RuntimeError):
    """Falha na consulta à API SIDRA."""


def _request(url: str, timeout: int = 120) -> Any:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise SidraError(f"HTTP {exc.code} em {url}") from exc
    except Exception as exc:  # noqa: BLE001
        raise SidraError(f"falha de rede em {url}: {type(exc).__name__}") from exc
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def build_values_url(
    table: str = config.PAM_TABLE,
    level: str = config.PAM_LEVEL,
    localities: str = "all",
    variables: str = "all",
    periods: str = "all",
    classification: int | None = config.PAM_CLASSIFICATION,
    categories: str = "all",
) -> str:
    """Monta a URL de consulta de valores do SIDRA."""
    url = f"{config.SIDRA_BASE}/t/{table}/n{level}/{localities}/v/{variables}/p/{periods}"
    if classification is not None:
        url += f"/c{classification}/{categories}"
    return url


def fetch_values(url: str) -> dict[str, Any]:
    """Executa a consulta e devolve cabeçalho + linhas normalizadas.

    O SIDRA pode responder em dois formatos: dicionário com ``header``/``data``
    ou lista cujo primeiro item é o cabeçalho. Ambos são suportados.
    """
    payload = _request(url)
    if isinstance(payload, dict):
        header = payload.get("header") or []
        rows = payload.get("data") or []
        status = payload.get("status")
    elif isinstance(payload, list):
        if not payload:
            return {"header": {}, "rows": [], "status": None, "url": url}
        header = payload[0]
        rows = payload[1:]
        status = 200
    else:  # pragma: no cover - formato inesperado
        raise SidraError(f"formato inesperado na resposta de {url}")

    fields = header.get("fields") if isinstance(header, dict) else None
    if not fields:
        # Formato-lista: o cabeçalho é um dict plano com as chaves D1C, D2C...
        fields = [
            {"id": key, "name": value}
            for key, value in header.items()
            if isinstance(value, str) and (key.startswith("D") or key in {"V", "MN", "MC", "NN", "NC"})
        ]
    return {
        "header": {f["id"]: f.get("name") for f in fields},
        "rows": rows,
        "status": status,
        "url": url,
    }


def parse_value(raw: Any) -> tuple[float | None, str]:
    """Converte o valor textual do SIDRA em número + sinalizador de status.

    Retorna ``(valor, status)`` onde status é um de: ``observed``,
    ``missing`` (``..``), ``zero`` (``-``), ``not_applicable`` (``...``),
    ``suppressed`` (``x``).
    """
    if raw is None:
        return None, "missing"
    text = str(raw).strip()
    if text == "":
        return None, "missing"
    if text == SIDRA_MISSING:
        return None, "missing"
    if text == SIDRA_NIL:
        return 0.0, "zero"
    if text == SIDRA_NOT_APPLICABLE:
        return None, "not_applicable"
    if text.lower() == SIDRA_SUPPRESSED:
        return None, "suppressed"
    try:
        return float(text.replace(",", ".")), "observed"
    except ValueError:
        return None, "missing"


def rows_to_records(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Achata as linhas do SIDRA em registros com campos semânticos."""
    records: list[dict[str, Any]] = []
    for row in result.get("rows", []):
        if not isinstance(row, dict):
            continue
        value, status = parse_value(row.get("V"))
        records.append(
            {
                "level_code": row.get("NC"),
                "level_name": row.get("NN"),
                "unit_code": row.get("MC"),
                "unit_name": row.get("MN"),
                "value_raw": row.get("V"),
                "value": value,
                "value_status": status,
                "locality_code": row.get("D1C"),
                "locality_name": row.get("D1N"),
                "variable_code": row.get("D2C"),
                "variable_name": row.get("D2N"),
                "period_code": row.get("D3C"),
                "period_name": row.get("D3N"),
                "product_code": row.get("D4C"),
                "product_name": row.get("D4N"),
            }
        )
    return records


def fetch_pam(
    locality: str = config.MUNICIPALITY["ibge_code"],
    years: Iterable[int] | None = None,
    variables: str = "214,216,112,8331",
    classification: int | None = config.PAM_CLASSIFICATION,
    categories: str = "all",
) -> dict[str, Any]:
    """Consulta a PAM (tabela 5457) para um município.

    ``years`` é uma lista de anos; a API aceita ``p/2023,2024,2025`` e também
    ``p/2023`` (ou ``all``).
    """
    if years is None:
        periods = f"{config.PAM_YEAR_START},{config.PAM_YEAR_END}"
    else:
        periods = ",".join(str(y) for y in years)
    url = build_values_url(
        localities=locality,
        variables=variables,
        periods=periods,
        classification=classification,
        categories=categories,
    )
    result = fetch_values(url)
    result["records"] = rows_to_records(result)
    result["acquired_at"] = datetime.now(timezone.utc).isoformat()
    return result


def fetch_aggregate_metadata(table: str = config.PAM_TABLE) -> dict[str, Any]:
    """Metadados oficiais do agregado (variáveis, classificações, periodicidade)."""
    url = f"https://servicodados.ibge.gov.br/api/v3/agregados/{table}/metadados"
    return _request(url)


def fetch_municipality_metadata(code: str = config.MUNICIPALITY["ibge_code"]) -> dict[str, Any]:
    """Confirma nome/UF do município pela API oficial de localidades."""
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/municipios/{code}"
    return _request(url)
