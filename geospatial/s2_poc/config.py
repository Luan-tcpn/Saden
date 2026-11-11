"""Constantes e parâmetros da prova de conceito Sentinel-2.

Fonte: Earth Search (Element 84) sobre o Open Data Registry da AWS.
Coleção C1 L2A (Sentinel-2 Collection 1 Level-2A, reflectância de superfície).
Nada aqui é usado pelo produto V1; este pacote é isolado.
"""

STAC_URL = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-c1-l2a"

# Município usado como referência do AOI (malha oficial do IBGE).
MUNICIPALITY = {
    "ibge_code": "5107925",
    "name": "Sorriso",
    "uf": "MT",
    "source": "IBGE — Malhas Territoriais (API v3, application/vnd.geo+json)",
    "url": "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/5107925?formato=application/vnd.geo+json",
}

# Janela técnica dentro do município. NÃO é um talhão nem representa toda a
# produção municipal; é um recorte de 0,10° x 0,10° para a prova de conceito.
AOI_SIZE_DEG = 0.10

# Grade comum dos índices (B02/B04/B08 são 10 m; B11/SCL são 20 m).
TARGET_RES_M = 20.0

# Ativos STAC usados. Nomes conforme a coleção C1 L2A do Earth Search.
ASSETS = {
    "blue": "blue",     # B02, 10 m
    "red": "red",       # B04, 10 m
    "nir": "nir",       # B08, 10 m
    "swir": "swir16",   # B11, 20 m
    "scl": "scl",       # SCL, 20 m
}

# Classes SCL excluídas (política conservadora).
# 0 sem dados; 1 saturado/defeituoso; 3 sombra de nuvem; 8 nuvem prob. média;
# 9 nuvem prob. alta; 10 cirrus; 11 neve/gelo.
SCL_BAD_CLASSES = (0, 1, 3, 8, 9, 10, 11)
# 7 = não classificado: excluído por precaução (documentado, não silencioso).
SCL_UNCLASSIFIED = 7

# Classes mantidas (referência documental; a máscara é construída pela exclusão).
SCL_KEPT_REFERENCE = {
    2: "vegetação muito baixa / solo",
    4: "vegetação",
    5: "solo exposto",
    6: "água",
}

FORMULAS = {
    "NDVI": "(NIR - Red) / (NIR + Red)",
    "EVI": "2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)",
    "NDMI": "(NIR - SWIR) / (NIR + SWIR)",
}

# Faixa de plausibilidade usada apenas para relatar valores extremos; não é clamp.
PLAUSIBLE_RANGE = (-1.5, 1.5)

# Janela padrão de busca (estação seca no Cerrado; sujeita à disponibilidade real).
DEFAULT_START = "2025-06-01"
DEFAULT_END = "2025-09-30"
DEFAULT_MAX_CLOUD = 20.0
DEFAULT_MAX_SCENES = 5
