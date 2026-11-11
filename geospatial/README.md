# SADEN V2.1 — PoC geoespacial Sentinel-2

Módulo **isolado** de prova de conceito: adquire imagens Sentinel-2 L2A de um
catálogo público, calcula NDVI/EVI/NDMI localmente e grava GeoTIFFs, série
tabular, prévias e manifesto de proveniência.

> Isto **não** é usado pela V1 e **não** está integrado ao produto. Não há
> previsão de preço, modelo de produtividade, dashboard ou endpoint novo.
> A V1 continua congelada (D40) e a V2 vive na branch
> `v2/geospatial-foundation` (D41).

## 1. O que foi executado (2026-11-11)

| Item | Resultado real |
|---|---|
| Catálogo | Earth Search / Element 84 — `https://earth-search.aws.element84.com/v1` |
| Coleção | `sentinel-2-c1-l2a` (L2A, reflectância de superfície) |
| Autenticação | nenhuma |
| AOI | Sorriso-MT (IBGE `5107925`) + janela técnica `0,10° × 0,10°` |
| BBox do AOI | `[-55.6509, -12.74385, -55.5509, -12.64385]` |
| Janela | `2025-06-01` … `2025-09-30`, nuvem < 20% |
| Cenas | 54 encontradas, 27 cobrindo o AOI, **4 processadas** |
| Grade | 20 m, `EPSG:32721`, 547 × 557 px, uma única grade para todas as cenas |
| Saída | 12 GeoTIFFs, CSV (12 linhas), 4 PNG, manifesto JSON com SHA-256 |

Cenas processadas:

| Item ID | Data | Nuvem (%) |
|---|---|---|
| `S2B_T21LXG_20250609T140533_L2A` | 2025-06-09 | 0,002827 |
| `S2A_T21LXG_20250726T140110_L2A` | 2025-07-26 | 0,000956 |
| `S2B_T21LXG_20250828T135714_L2A` | 2025-08-28 | 0,001088 |
| `S2B_T21LXG_20250927T135901_L2A` | 2025-09-27 | 0,026692 |

Números completos e limitações: `docs/V2_EXECUTION_STATUS.md`.

## 2. Estrutura

```
geospatial/
  requirements.txt       # versões pinadas do ambiente validado
  run_poc.py             # CLI (descoberta / processamento)
  s2_poc/
    config.py            # catálogo, AOI, bandas, máscara, janela
    aoi.py               # malha IBGE + janela técnica + point-in-polygon
    network.py           # correção de CA para GDAL/schannel no Windows
    stac_search.py       # busca STAC, proveniência, seleção mensal
    read.py              # grade comum, leitura remota, reamostragem, GeoTIFF
    indices.py           # escala, máscaras, NDVI/EVI/NDMI, estatísticas
    render.py            # prévias PNG (matplotlib Agg)
    pipeline.py          # orquestração + CSV + manifesto
  tests/                 # 30 testes sintéticos, offline
  previews/              # PNGs pequenos versionados
  artifacts/             # rasters/CSV/JSON grandes — IGNORADO no Git
  .venv/                 # ambiente isolado — IGNORADO no Git
```

## 3. Instalação (Windows, Python 3.12)

```powershell
cd <raiz do repositório>
python -m venv geospatial\.venv
geospatial\.venv\Scripts\python.exe -m pip install -r geospatial\requirements.txt
```

Versões validadas: Python 3.12.10, pystac-client 0.9.1, rasterio 1.4.3
(GDAL 3.9.3), numpy 2.5.4, matplotlib 3.11.2.

### Correção obrigatória de TLS

O GDAL usa schannel no Windows e **recusa** o CA bundle em caminho com acento
(“Área de Trabalho”). Sem correção, o erro aparece como `UnicodeDecodeError`
enganoso. `s2_poc/network.py` copia o `cacert.pem` do certifi para `%TEMP%`
(caminho ASCII) e define `CURL_CA_BUNDLE`, `GDAL_HTTP_CAINFO` e `SSL_CERT_FILE`
antes de abrir COGs remotos. A verificação TLS **permanece ligada**.

### Versão do rasterio

`rasterio==1.5.2` (GDAL 3.12.2) crashou ao abrir COG remoto neste ambiente
Windows (`exit -1073740791`). A versão fixada é **1.4.3**. Não “atualize” sem
testar a leitura remota de ponta a ponta.

## 4. Execução

A partir da raiz do repositório:

```powershell
# 1) descoberta (rede, sem baixar raster)
geospatial\.venv\Scripts\python.exe geospatial\run_poc.py --check-only

# 2) processamento real (baixa janelas e gera produtos)
geospatial\.venv\Scripts\python.exe geospatial\run_poc.py

# janela diferente / menos cenas
geospatial\.venv\Scripts\python.exe geospatial\run_poc.py --start 2025-06-01 --end 2025-09-30 --max-cloud 10 --max-scenes 3

# sem prévia PNG
geospatial\.venv\Scripts\python.exe geospatial\run_poc.py --no-preview
```

O CLI imprime um JSON resumido e grava o manifesto completo em
`geospatial/artifacts/`.

## 5. Testes

```powershell
geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests -t geospatial -v
```

30 testes, **sem internet**. Cobrem: escala/offset, nodata, fórmulas,
denominador zero/degenerado, máscara SCL, estatísticas, alinhamento de grade,
reamostragem `average` × `nearest`, escrita/leitura GeoTIFF, SHA-256,
seleção mensal determinística, filtro de cobertura do AOI, JSON seguro e CSV.

## 6. Fórmulas e decisões

```
NDVI = (NIR - Red) / (NIR + Red)          # B08, B04
EVI  = 2.5*(NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)   # B08, B04, B02
NDMI = (NIR - SWIR) / (NIR + SWIR)        # B08, B11
```

- Reflectância física: `DN * 0.0001 + (-0.1)` (metadados reais da coleção).
- `DN == 0` (nodata) vira `NaN` **antes** da escala.
- O `+1` do EVI é aplicado em reflectância física, não em DN.
- Contínuas: reamostragem `average` de 10 m → 20 m.
- SCL: `nearest` (nunca interpolação em classes).
- Denominador `|den| <= 1e-6` → `NaN`; nunca `inf`, nunca clamp.
- Máscara SCL exclui `0, 1, 3, 7, 8, 9, 10, 11`. As classes `2, 4, 5, 6`
  (incluindo solo exposto e água) são mantidas: máscara de qualidade **não** é
  interpretação agronômica.

## 7. Produtos

| Produto | Caminho | Git |
|---|---|---|
| GeoTIFF `<item>_NDVI.tif`, `_EVI.tif`, `_NDMI.tif` | `artifacts/` | ignorado |
| Série temporal `series_temporal.csv` (UTF-8 BOM) | `artifacts/` | ignorado |
| Manifesto `run_<UTC>.json` e `latest.json` | `artifacts/` | ignorado |
| Prévia `AAAA-MM-DD_<item>_indices.png` | `previews/` | versionado |
| Código e testes | `s2_poc/`, `tests/`, `run_poc.py` | versionado |

GeoTIFFs: `float32`, 1 banda, `nodata=NaN`, compressão deflate, CRS/transform
idênticos entre cenas. SHA-256 de cada arquivo fica no manifesto.

## 8. Limitações

- A janela de `0,10° × 0,10°` é **técnica**: não é talhão, fazenda nem amostra
  representativa da produção municipal. Município não é talhão.
- Quatro datas em uma estação **não** demonstram sazonalidade.
- NDVI/EVI/NDMI **não** medem produtividade e **não** são features de preço.
- A máscara SCL reduz nuvem/sombra, mas não elimina nuvem fina não classificada,
  aerossol ou sombra residual.
- Água e solo exposto entram nas estatísticas (por decisão explícita).
- Não há correção de BRDF, topografia ou mistura espectral.

## 9. Problemas conhecidos

| Sintoma | Causa | Solução |
|---|---|---|
| `UnicodeDecodeError: ... 0xc1` | CA em caminho com acento | usar `network.configure_tls()` antes de abrir COG |
| crash `-1073740791` ao abrir URL | rasterio 1.5.2/GDAL 3.12 | fixar `rasterio==1.4.3` |
| `Content-Encoding` inesperado no IBGE | API envia gzip sempre | `aoi.fetch_municipality_geojson` descomprime |
| `DeprecationWarning` de shape no numpy | rasterio 1.4.3 + numpy 2.5 | suprimido localmente em `read.py` |
