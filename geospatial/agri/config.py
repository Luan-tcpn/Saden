"""Parâmetros da base observada de produtividade (V2.2).

Fontes oficiais investigadas e verificadas em 2026-11-11 (ver
`geospatial/reports/V2_2_PRODUCTIVITY_DATA_COMPATIBILITY.md`).
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------- município

# Município de interesse (mesmo da V2.1) — confirmado pela API de localidades
# do IBGE: nome "Sorriso", UF "Mato Grosso", região imediata "Sorriso",
# região intermediária "Sinop", mesorregião "Norte Mato-grossense".
MUNICIPALITY = {
    "ibge_code": "5107925",
    "name": "Sorriso",
    "uf_code": "51",
    "uf_name": "Mato Grosso",
    "uf_sigla": "MT",
    "immediate_region": "Sorriso",
    "intermediate_region": "Sinop",
    "mesoregion": "Norte Mato-grossense",
    "region": "Centro-Oeste",
    "region_sigla": "CO",
    "source": "IBGE — API de Localidades (servicodados.ibge.gov.br/api/v1/localidades)",
}

# ------------------------------------------------------------------- IBGE

# API SIDRA (sem chave, sem custo, acesso público).
SIDRA_BASE = "https://apisidra.ibge.gov.br/values"

# Produção Agrícola Municipal (PAM) — tabela 5457.
# "Área plantada ou destinada à colheita, área colhida, quantidade produzida,
#  rendimento médio e valor da produção das lavouras temporárias e permanentes"
PAM_TABLE = "5457"
PAM_TABLE_NAME = (
    "Área plantada ou destinada à colheita, área colhida, quantidade produzida, "
    "rendimento médio e valor da produção das lavouras temporárias e permanentes"
)
PAM_RESEARCH = "Produção Agrícola Municipal (PAM)"
PAM_CLASSIFICATION = 782  # Produto das lavouras temporárias e permanentes
PAM_LEVEL = "6"  # município (n6 na URL do SIDRA)

# Variáveis de interesse (id -> nome/unidade oficial).
PAM_VARIABLES = {
    "8331": {
        "name": "Área plantada ou destinada à colheita",
        "unit": "Hectares",
        "normalized": "area_plantada_ha",
        "normalized_unit": "ha",
    },
    "216": {
        "name": "Área colhida",
        "unit": "Hectares",
        "normalized": "area_colhida_ha",
        "normalized_unit": "ha",
    },
    "214": {
        "name": "Quantidade produzida",
        "unit": "Toneladas",
        "normalized": "quantidade_produzida_t",
        "normalized_unit": "t",
    },
    "112": {
        "name": "Rendimento médio da produção",
        "unit": "Quilogramas por Hectare",
        "normalized": "rendimento_medio_kg_ha",
        "normalized_unit": "kg/ha",
    },
}

# Metadados agregados do IBGE (documentação oficial do conjunto).
IBGE_AGGREGATE_METADATA = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/5457/metadados"
)
IBGE_MUNICIPALITY_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/municipios/5107925"
)

# Janela histórica acquireida (PAM cobre 1974–2025; aqui: 2013–2025).
PAM_YEAR_START = 2013
PAM_YEAR_END = 2025

# ------------------------------------------------------------------ CONAB

# Boletim de Safras (granéis) e Boletim da Safra de Café, no portal oficial.
CONAB_GRAINS_INDEX = (
    "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/"
    "safra-de-graos/boletim-da-safra-de-graos"
)
CONAB_COFFEE_INDEX = (
    "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/"
    "safra-de-cafe/safra-de-cafe-1"
)
CONAB_HOME = "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias"

# Portais da CONAB **não** acessíveis a partir deste ambiente (verificado em
# 2026-11-11): SIGS (dados por município) e API da CONAB não resolvem DNS.
CONAB_SIGS_URL = "https://sigs.conab.gov.br/producao/"
CONAB_API_URL = "https://api.conab.gov.br"

# --------------------------------------------------------------- unidades UF

# Sigla -> código IBGE de UF (necessário para padronizar a unidade
# territorial das planilhas da CONAB, que trazem a sigla).
UF_CODES = {
    "AC": "12", "AL": "27", "AM": "13", "AP": "16", "BA": "29", "CE": "23",
    "DF": "53", "ES": "32", "GO": "52", "MA": "21", "MG": "31", "MS": "50",
    "MT": "51", "PA": "15", "PB": "25", "PE": "26", "PI": "22", "PR": "41",
    "RJ": "33", "RN": "24", "RO": "11", "RR": "14", "RS": "43", "SC": "42",
    "SE": "28", "SP": "35", "TO": "17",
}

UF_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
    "GO": "Goiás", "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul",
    "MT": "Mato Grosso", "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco",
    "PI": "Piauí", "PR": "Paraná", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RO": "Rondônia", "RR": "Roraima", "RS": "Rio Grande do Sul", "SC": "Santa Catarina",
    "SE": "Sergipe", "SP": "São Paulo", "TO": "Tocantins",
}

# -------------------------------------------------------------- commodities

# Catálogo de commodities do próprio SADEN (backend/src/db.js, seed).
SADEN_COMMODITIES = [
    {"key": "soja", "name": "Soja", "yahoo_symbol": "ZS=F"},
    {"key": "milho", "name": "Milho", "yahoo_symbol": "ZC=F"},
    {"key": "cafe", "name": "Café arábica", "yahoo_symbol": "KC=F"},
    {"key": "trigo", "name": "Trigo", "yahoo_symbol": "ZW=F"},
    {"key": "algodao", "name": "Algodão", "yahoo_symbol": "CT=F"},
]

# ------------------------------------------------------------------- diretórios

GEO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(GEO_ROOT, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
MANIFEST_DIR = os.path.join(DATA_DIR, "manifests")

# --------------------------------------------------------------- AOI V2.1

# AOI de validação da V2.1 (mantida; não é área municipal).
VALIDATION_AOI_BBOX = [-55.6309, -12.7339, -55.5709, -12.6739]
VALIDATION_AOI_KIND = "validation_aoi"
EQUAL_AREA_CRS = "EPSG:6933"

# --------------------------------------------------------------- Sentinel-2

# Série temporal V2.1 (arquivos versionados em geospatial/reports).
S2_SERIES_CSV = os.path.join(GEO_ROOT, "reports", "timeseries_mensal_2023-01_2025-12.csv")
S2_INDEX = "NDVI"
S2_PROFILE = "B_restrictive"

# ------------------------------------------------------------- licenciamento

LICENSES = {
    "ibge_sidra": {
        "institution": "IBGE",
        "status": "public_domain_open",
        "terms_url": "https://www.ibge.gov.br/acesso-informacao/licenca-de-uso/",
        "note": (
            "Dados estatísticos oficiais de acesso público, sem chave e sem "
            "custo; reutilização permitida com atribuição à fonte (IBGE/SIDRA)."
        ),
    },
    "conab": {
        "institution": "CONAB",
        "status": "open_but_restricted_by_publication_terms",
        "terms_url": (
            "https://www.gov.br/conab/pt-br/acesso-a-informacao/termos-de-uso"
        ),
        "note": (
            "Planilhas oficiais de livre acesso no portal, sem API pública "
            "automatizável (dados.gov.br exige autenticação; SIGS não resolve "
            "DNS neste ambiente). republicação/redistribuição depende dos "
            "termos de uso vigentes — não declarada aqui como livre."
        ),
    },
}
