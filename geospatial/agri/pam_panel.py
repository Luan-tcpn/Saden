"""PAM (SIDRA 5457) para **vários municípios** — extensão do módulo V2.2.

O módulo :mod:`agri.sidra` (V2.2) consulta a PAM para **um** município; este
módulo reutiliza as mesmas funções (sem duplicar a lógica de leitura do
SIDRA) e apenas **parametriza o conjunto de localidades**, permitindo
construir o painel multi-municipal.

Referência: tabela 5457 da SIDRA — *Produção Agrícola Municipal*:
área plantada, área colhida, quantidade produzida, rendimento médio e valor
da produção das lavouras temporárias e permanentes.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from . import config, sidra

# Produtos de interesse do painel (classificação 782 — produtos das lavouras
# temporárias e permanentes).
PAM_PRODUCTS: dict[str, str] = {
    "soja": "40124",   # Soja (em grão)
    "milho": "40122",  # Milho (em grão)
}

# Códigos IBGE das unidades federativas candidatas ao painel.
PANEL_STATES: dict[str, str] = {
    "MT": "Mato Grosso",
    "GO": "Goiás",
    "MS": "Mato Grosso do Sul",
    "PR": "Paraná",
    "RS": "Rio Grande do Sul",
    "BA": "Bahia",
}


def fetch_state_municipalities(state: str) -> list[dict[str, Any]]:
    """Lista de municípios de uma UF pela API oficial de localidades do IBGE."""
    import gzip
    import json
    import urllib.request

    url = (
        "https://servicodados.ibge.gov.br/api/v1/localidades/estados/"
        f"{state}/municipios"
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": "SADEN-V2.6/0.1 (investigacao academica)"}
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        raw = response.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    payload = json.loads(raw.decode("utf-8"))
    out: list[dict[str, Any]] = []
    for item in payload:
        region = (item.get("regiao") or {}).get("sigla")
        out.append(
            {
                "ibge_code": str(item.get("id")),
                "municipality": item.get("nome"),
                "state": state,
                "region": region,
            }
        )
    return out


def fetch_state_pam(
    state: str,
    municipalities: Sequence[dict[str, Any]],
    years: Sequence[int],
    products: Iterable[str] = ("soja", "milho"),
    variables: str = "214,216,112,8331",
    classification: int = config.PAM_CLASSIFICATION,
    timeout: int = 600,
) -> dict[str, Any]:
    """Consulta a PAM de uma UF inteira, em uma única requisição.

    Devolve o cabeçalho de metadados e as linhas normalizadas pelo mesmo
    interpretador da V2.2 (:func:`agri.sidra.rows_to_records`).
    """
    codes = ",".join(str(m["ibge_code"]) for m in municipalities)
    categories = ",".join(PAM_PRODUCTS[p] for p in products if p in PAM_PRODUCTS)
    periods = ",".join(str(year) for year in years)
    url = sidra.build_values_url(
        localities=codes,
        variables=variables,
        periods=periods,
        classification=classification,
        categories=categories,
    )
    result = sidra.fetch_values(url)
    raw_records = sidra.rows_to_records(result)
    # normalização canônica da V2.2 (mesmo interpretador do SIDRA)
    from . import normalize

    records = normalize.build_ibge_records(
        {"records": raw_records, "acquired_at": None},
        source_url=url,
        acquisition_method="sidra_api_painel",
    )
    return {
        "state": state,
        "url": url,
        "header": result["header"],
        "records": records,
        "n_records": len(records),
    }


def summarize_by_state(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Resumo por UF, cultura e ano (contagem de observações utilizáveis)."""
    from collections import Counter

    counter: Counter = Counter()
    for record in records:
        variable = record.get("variable_normalized")
        if variable != "rendimento_medio_kg_ha":
            continue
        status = record.get("observation_status") or record.get("nature")
        counter[
            (
                record.get("geography_code"),
                record.get("crop_code"),
                record.get("reference_year"),
                status,
            )
        ] += 1
    return {
        "n_records": len(records),
        "distinct_keys": len(counter),
        "keys": [list(key) for key in counter],
    }
