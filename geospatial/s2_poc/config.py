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

# Malha de maior detalhe para validação geométrica (2.689 vértices, Polygon).
# Mantida separada da URL histórica para não deslocar o AOI original.
MUNICIPALITY_MAXIMA = {
    **MUNICIPALITY,
    "quality": "maxima",
    "url": (
        "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/5107925"
        "?formato=application/vnd.geo+json&qualidade=maxima"
    ),
}

# Janela técnica dentro do município. NÃO é um talhão nem representa toda a
# produção municipal; é um recorte de 0,10° x 0,10° para a prova de conceito.
AOI_SIZE_DEG = 0.10

# AOI de validação: 0,06° centrada na faixa de sobreposição dos tiles
# 21LXG/21LXF, dentro do município de Sorriso. Não é área agrícola.
VALIDATION_AOI = {
    "size_deg": 0.06,
    "center_lon": -55.6009,
    "center_lat": -12.7039,
    "note": (
        "AOI de validação geoespacial: recorte controlado dentro do município, "
        "na sobreposição dos tiles 21LXG/21LXF. Não é talhão nem área agrícola "
        "identificada."
    ),
}

# AOI do mosaico: janela que atravessa a fronteira entre os footprints de
# 21LXG (norte) e 21LXF (sul), incluindo a faixa de sobreposição
# (lat ≈ -12,7508 a -12,6570). Serve ao Checkpoint D: sem ela, os dois tiles
# cobririam 100% da mesma área e a regra de prioridade nunca seria exercida.
MOSAIC_AOI = {
    "bbox": [-55.70, -12.78, -55.50, -12.62],
    "note": (
        "Janela de mosaico: contém área exclusiva de 21LXF, a faixa de "
        "sobreposição 21LXF/21LXG e área exclusiva de 21LXG."
    ),
}

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

# Classes SCL excluídas pela máscara histórica (Perfil A).
# 0 sem dados; 1 saturado/defeituoso; 3 sombra de nuvem; 8 nuvem prob. média;
# 9 nuvem prob. alta; 10 cirrus; 11 neve/gelo.
SCL_BAD_CLASSES = (0, 1, 3, 8, 9, 10, 11)
# 7 = "Clouds low probability / Unclassified": excluído por precaução.
SCL_UNCLASSIFIED = 7

# Semântica oficial (Copernicus Data Space / Sentinel Hub S2L2A, consultado
# em 2026-11-11). O comentário antigo da PoC chamava a classe 2 de "vegetação
# muito baixa"; a definição oficial é "Dark Area Pixels".
SCL_CLASSES = {
    0: "No data",
    1: "Saturated or defective",
    2: "Dark area pixels",
    3: "Cloud shadows",
    4: "Vegetation",
    5: "Bare soils",
    6: "Water",
    7: "Clouds low probability / Unclassified",
    8: "Clouds medium probability",
    9: "Clouds high probability",
    10: "Cirrus",
    11: "Snow / ice",
}

# Perfis de máscara comparados no Checkpoint B. Nenhum é exposto ao usuário.
SCL_PROFILES = {
    "A_historical": SCL_BAD_CLASSES + (SCL_UNCLASSIFIED,),
    "B_restrictive": tuple(sorted(set(SCL_BAD_CLASSES) | {2, 6, SCL_UNCLASSIFIED})),
}

# Classes tratadas como obstrução na seleção de cenas (nuvem/sombra/inválido).
# Classe 2 (dark area) não é nuvem; fica fora deste conjunto.
SCL_OBSTRUCTION_CLASSES = (0, 1, 3, 7, 8, 9, 10, 11)

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
