# SADEN V2.1 — Fundação geoespacial Sentinel-2

Módulo **isolado** de prova de conceito e validação: adquire imagens Sentinel-2
L2A de um catálogo público, calcula NDVI/EVI/NDMI localmente e grava GeoTIFFs,
séries tabulares, prévias e manifestos de proveniência auditáveis.

> Isto **não** é usado pela V1 e **não** está integrado ao produto. Não há
> previsão de preço, modelo de produtividade, dashboard ou endpoint novo.
> A V1 continua congelada (D40); a V2 vive nas branches
> `v2/geospatial-foundation` (PoC, D41) e `v2/geospatial-validation`
> (validação, D42–D45).

## 1. Fonte de dados

| Item | Valor |
|---|---|
| Catálogo | Earth Search / Element 84 — `https://earth-search.aws.element84.com/v1` |
| Coleção | `sentinel-2-c1-l2a` (L2A, reflectância de superfície) |
| Autenticação | nenhuma (acesso público anônimo) |
| Custo | zero |
| Licença | a coleção declara `license: proprietary`; o Registry of Open Data on AWS declara acesso “free, full and open”. **As duas informações são registradas** (fonte #1 e fonte #2); não se afirma licença única. |
| Ativos | `blue` (B02), `red` (B04), `nir` (B08), `swir16` (B11), `scl` |
| Radiometria | `scale = 0.0001`, `offset = -0.1`, `nodata = 0`, `uint16` |

## 2. AOIs (três geometrias, nunca misturadas — D42)

| Geometria | Bbox | Papel |
|---|---|---|
| Limite municipal (IBGE `5107925`, Sorriso-MT) | `[-56.1167, -13.6661, -55.0851, -11.7216]` | referência territorial oficial (9.293,47 km²) |
| AOI técnica histórica (PoC) | `[-55.6509, -12.74385, -55.5509, -12.64385]` | reprodução da PoC — **0,51 km² (0,42%) ficam fora do município** |
| AOI de validação | `[-55.6309, -12.7339, -55.5709, -12.6739]` | recorte controlado (43,26 km²; ~108.140 px a 20 m) dentro do município e na sobreposição `21LXG`/`21LXF` |
| AOI de mosaico | `[-55.70, -12.78, -55.50, -12.62]` | janela que atravessa a fronteira entre os footprints dos dois tiles |

Nenhuma delas é talhão, fazenda, lavoura ou amostra representativa da produção
municipal.

## 3. Estrutura

```
geospatial/
  requirements.txt       # versões pinadas do ambiente validado
  run_poc.py             # CLI da PoC (reprodução da baseline histórica)
  run_validation.py      # CLI de validação (checkpoints A–E)
  run_productivity.py    # CLI da base observada de produtividade (V2.2)
  s2_poc/
    config.py            # catálogo, AOIs, bandas, perfis SCL, parâmetros
    aoi.py               # malha IBGE + janela técnica (PoC) + point-in-polygon
    geometry.py          # malha oficial, interseção bbox×município, AOIs, custo
    network.py           # correção de CA para GDAL/schannel no Windows
    stac_search.py       # busca STAC, proveniência, seleção mensal
    read.py              # grade comum, leitura remota, reamostragem, GeoTIFF
    radiometry.py        # auditoria baseline/scale/offset + bloqueio de produto
    mask.py              # perfis SCL A/B, contagem por classe, comparação
    indices.py           # escala, máscaras, NDVI/EVI/NDMI, estatísticas
    mosaic.py            # mosaico determinístico + mapa de origem + seam
    timeseries.py        # seleção mensal, lacunas explícitas, CSV da série
    render.py            # prévias PNG (índices, máscaras, mosaico, série, mapa)
    pipeline.py          # orquestração da PoC + CSV + manifesto
  agri/                  # base observada de produtividade (V2.2)
    config.py            # URLs oficiais, variáveis, licença, commodities
    sidra.py             # cliente da API SIDRA (PAM 5457) + convenções de valor
    conab.py             # listagem/download/parser das planilhas de safras
    crosswalk.py         # vínculos SADEN ↔ IBGE ↔ CONAB com classe
    normalize.py         # base normalizada (CSV/JSON), conversões de unidade
    validate.py          # 11 verificações de qualidade
    compat.py            # classes A/B/C, agregação anual do NDVI, correspondência
    geometry_compat.py   # malha municipal reaproveitada da V2.1 (D42)
  tests/                 # suíte offline (unittest), sem internet
  tests_external/        # testes de REDE, opt-in (SADEN_EXTERNAL_TESTS=1)
  data/                  # V2.2: raw/ processed/ manifests/
  manifests/             # manifestos de execução (JSON, versionados, leves)
  reports/               # relatórios/tabelas de validação (CSV/JSON)
  previews/              # PNGs pequenos versionados
  artifacts/             # rasters/CSV grandes — IGNORADO no Git
  .venv/                 # ambiente isolado — IGNORADO no Git
```

## 4. Instalação (Windows, Python 3.12)

```powershell
cd <raiz do repositório>
python -m venv geospatial\.venv
geospatial\.venv\Scripts\python.exe -m pip install -r geospatial\requirements.txt
```

Versões validadas: Python 3.12.10, pystac-client 0.9.1, rasterio 1.4.3
(GDAL 3.9.3), numpy 2.5.4, matplotlib 3.11.2, shapely 2.1.2, pyproj 3.7.2.

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

## 5. Execução

### 5.1 Reprodução da PoC (baseline histórica, Perfil A)

```powershell
geospatial\.venv\Scripts\python.exe geospatial\run_poc.py --check-only
geospatial\.venv\Scripts\python.exe geospatial\run_poc.py
```

### 5.2 Validação V2.1 (checkpoints A–E)

```powershell
# A — reexecuta a PoC em diretório separado + auditoria radiométrica
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py repro

# B — comparação de máscaras SCL (A histórico × B restritivo)
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py scl --aoi historical

# C — geometria municipal oficial, interseção e estimativas de custo
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py geometry

# D — mosaico real de dois tiles do mesmo datatake
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py mosaic

# E — série mensal exploratória 2023–2025
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py timeseries --start 2023-01 --end 2025-12
```

Os subcomandos `scl`, `mosaic` e `timeseries` usam a **rede** (STAC + COGs
reais). A suíte de testes offline é independente deles.

### 5.3 Base observada de produtividade (V2.2)

```powershell
# inventário das fontes oficiais (metadados, catálogo, acessos bloqueados)
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py inventory

# aquisição real (SIDRA municipal + planilhas da CONAB)
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py acquire --year-start 2013 --year-end 2025 --conab-safras "2024/25,2025/26"

# base normalizada, validação de qualidade e compatibilidade com o Sentinel-2
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py normalize
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py validate
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py compat
```

| Fonte | Conjunto | Granularidade | Natureza |
|---|---|---|---|
| IBGE/SIDRA | PAM, tabela 5457 (1974–2025) | **município** | observada |
| CONAB | Boletim de Safras (planilhas) | **UF** | estimada (revisada por levantamento) |

Relatório: `geospatial/reports/V2_2_PRODUCTIVITY_DATA_COMPATIBILITY.md`.
Compatibilidade espacial apurada: **IBGE = B (contextual)**, **CONAB = C**
(ver D47). As planilhas da CONAB ficam **fora do Git** (D48); URL e SHA-256 no
manifesto.

## 6. Testes

```powershell
# suíte padrão, 100% offline
geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests -t geospatial

# testes externos (rede) — opt-in explícito
$env:SADEN_EXTERNAL_TESTS = "1"
geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests_external -t geospatial
```

A suíte offline (95/95) e a suíte externa (4/4, opt-in) cobrem: escala/offset e DN→reflectância, detecção de metadados
ausentes/incompatíveis, bloqueio de baseline não suportado, nodata/NaN/inf e
denominador degenerado, fórmulas NDVI/EVI/NDMI, perfis SCL A/B e contagem por
classe, estatísticas com quantis p5/p25/p75/p95, alinhamento de grade,
reamostragem `average` × `nearest`, recorte/intersecção com polígono municipal,
bbox parcialmente fora do município, mosaico sintético com sobreposição
conhecida, seamline e nodata, meses sem observação, manifesto/SHA-256 e
reprodutibilidade dos metadados.

## 7. Fórmulas e decisões metodológicas

```
NDVI = (NIR - Red) / (NIR + Red)          # B08, B04
EVI  = 2.5*(NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)   # B08, B04, B02
NDMI = (NIR - SWIR) / (NIR + SWIR)        # B08, B11
```

- Reflectância física: `DN * 0.0001 + (-0.1)` (metadados reais da coleção);
  `rasterio.read()` devolve o DN bruto — a escala **não** é aplicada
  automaticamente, e a auditoria confirma que o COG declara os mesmos
  metadados (sem dupla aplicação).
- `DN == 0` (nodata) vira `NaN` **antes** da escala.
- O `+1` do EVI é aplicado em reflectância física, não em DN.
- Contínuas: reamostragem `average` de 10 m → 20 m. SCL: `nearest`.
- Denominador `|den| <= 1e-6` → `NaN`; nunca `inf`, nunca clamp.
- **Máscara SCL** (D43): Perfil A (histórico, reprodução da PoC) exclui
  `0,1,3,7,8,9,10,11`; Perfil B (padrão da V2.1) exclui também `2` (dark area)
  e `6` (água). Efeito medido: ≤ 0,18% de mudança na média do NDVI.
- **Mosaico** (D44): `first_valid_wins`, prioridade `21LXG > 21LXF`, sem média;
  par de tiles definido por mesmo `datatake_id` (diferença temporal medida e
  registrada); mapa de origem por pixel gravado em GeoTIFF.
- **Série mensal** (D45): seleção pela menor fração obstruída sobre a AOI
  (classes SCL de nuvem/sombra/saturado/nodata); meses sem observação
  utilizável ficam **vazios**, com o motivo registrado.

## 8. Produtos

| Produto | Caminho | Git |
|---|---|---|
| GeoTIFFs da PoC (`<item>_NDVI.tif`, …) | `artifacts/` | ignorado |
| GeoTIFFs do mosaico + mapa de origem + SCL | `artifacts/mosaic/` | ignorado |
| GeoTIFFs mensais da série | `artifacts/timeseries/<mês>/` | ignorado |
| Reprodução da PoC (CSV + JSON) | `artifacts/repro_poc/` | ignorado |
| Manifestos de execução (JSON) | `manifests/` | versionado |
| Tabelas de validação (CSV/JSON) | `reports/` | versionado |
| Prévias PNG | `previews/` | versionado |
| Código e testes | `s2_poc/`, `tests/`, `tests_external/`, `run_*.py` | versionado |

GeoTIFFs: `float32`, 1 banda, `nodata=NaN`, compressão deflate, CRS/transform
idênticos entre cenas. SHA-256 de cada arquivo fica no manifesto.

## 9. Limitações

- AOI é **geográfico**, não agrícola: nada aqui identifica cultura, talhão,
  lavoura, produtividade ou preço.
- A classe SCL 5 (“bare soils”) provavelmente inclui áreas cultivadas — o SCL
  não é classificador de uso do solo.
- Não há correção de BRDF, topografia, aerossol ou mistura espectral; não há
  validação com campo (ground truth) nem com dado de produtividade.
- A série 2023–2025 é exploratória: meses sem observação são lacunas reais.
- Um único par de tiles demonstra continuidade espacial local, não global.

## 10. Problemas conhecidos

| Sintoma | Causa | Solução |
|---|---|---|
| `UnicodeDecodeError: ... 0xc1` | CA em caminho com acento | usar `network.configure_tls()` antes de abrir COG |
| crash `-1073740791` ao abrir URL | rasterio 1.5.2/GDAL 3.12 | fixar `rasterio==1.4.3` |
| `Content-Encoding` inesperado no IBGE | API envia gzip sempre | descompressão explícita em `aoi.py`/`geometry.py` |
| `DeprecationWarning` de shape no numpy | rasterio 1.4.3 + numpy 2.5 | suprimido localmente em `read.py` |
