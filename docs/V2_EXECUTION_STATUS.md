# SADEN V2 — estado de execução (memória operacional)

> Atualizado em **2026-11-11**. Branch de trabalho: `v2/geospatial-foundation`
> (derivada de `v1-final` / `3f7ad33`). A V1 permanece congelada: `main`,
> `v1-final` e `archive/v1-final` não foram alterados.

## 1. Etapa atual

**V2.1 — PoC Sentinel-2 executada com sucesso** (4 cenas reais L2A, 4 datas,
NDVI/EVI/NDMI). O escopo é deliberadamente mínimo: sem UI, sem integração ao
produto, sem modelo de preço, sem alteração na Ridge.

## 2. Fronteira V1 × V2

| Item | Estado |
|---|---|
| `main` | `3f7ad33bc18c5a8e8e050bbc7817f5078488d625` (intacto) |
| `v1-final` | tag anotada → `3f7ad33` (intacta) |
| `archive/v1-final` | `3f7ad33` (local e remoto) |
| `v2/geospatial-foundation` | branch isolada, sem merge em `main` |
| Código V1 alterado | **nenhum**; mudanças só em `geospatial/` e `docs/` |
| `SADEN-TCC` | não tocado |

## 3. Fonte de dados (verificada em execução real)

| Item | Valor |
|---|---|
| Catálogo STAC | `https://earth-search.aws.element84.com/v1` (Earth Search / Element 84) |
| Coleção | `sentinel-2-c1-l2a` (Sentinel-2 Collection 1 Level-2A) |
| Autenticação | nenhuma (acesso público anônimo) |
| Custo | zero; dados abertos sobre AWS Open Data |
| Licença | Copernicus Sentinel Data (ver metadados da coleção) |
| Ativos usados | `blue` (B02), `red` (B04), `nir` (B08), `swir16` (B11), `scl` |

Escala/offset lidos dos metadados reais de cada ativo:
`scale = 0.0001`, `offset = -0.1`, `nodata = 0`, `dtype = uint16`
(contínuas), `uint8` (SCL).

## 4. AOI (área de estudo)

| Item | Valor |
|---|---|
| Município de referência | Sorriso-MT, IBGE `5107925` |
| Fonte da malha | `https://servicodados.ibge.gov.br/api/v3/malhas/municipios/5107925?formato=application/vnd.geo+json` |
| BBox municipal | `[-56.1167, -13.6661, -55.0851, -11.7216]` |
| AOI | janela técnica `0,10° × 0,10°` centrada no centro do bbox municipal |
| BBox do AOI | `[-55.6509, -12.74385, -55.5509, -12.64385]` |
| Centro | lon `-55.6009`, lat `-12.69385` |
| Verificação | centro confirmado dentro do polígono municipal |

**Limitação explícita:** o AOI é um recorte técnico para a PoC. Não é talhão,
fazenda, amostra representativa, nem prova de que a área é cultivada com uma
única cultura. A escolha de Sorriso-MT é técnica, não preferência declarada
pelo usuário.

## 5. Busca e cenas processadas

Janela: `2025-06-01` a `2025-09-30`, nuvem < 20%, até 5 cenas (1 por mês, a de
menor nuvem; determinístico por `eo:cloud_cover` e `item.id`).

Resultado real: **54 cenas encontradas**, **27 cobrindo o AOI inteiro**,
**4 selecionadas e processadas**.

| # | Item ID | Data | Nuvem (%) | Pixels válidos |
|---|---|---|---|---|
| 1 | `S2B_T21LXG_20250609T140533_L2A` | 2025-06-09 | 0,002827 | 304.510 / 304.679 (99,94%) |
| 2 | `S2A_T21LXG_20250726T140110_L2A` | 2025-07-26 | 0,000956 | 304.526 / 304.679 (99,95%) |
| 3 | `S2B_T21LXG_20250828T135714_L2A` | 2025-08-28 | 0,001088 | 304.558 / 304.679 (99,96%) |
| 4 | `S2B_T21LXG_20250927T135901_L2A` | 2025-09-27 | 0,026692 | 304.555 / 304.679 (99,96%) |

## 6. Processamento

| Item | Decisão |
|---|---|
| Grade comum | 20 m, 547 × 557 px (304.679 px por cena) |
| CRS | `EPSG:32721` (UTM 21S) |
| Transform | `(20, 0, 646440, 0, -20, 8601880)` — idêntico nas 4 cenas |
| Contínuas | `Resampling.average` (10 m → 20 m) |
| SCL | `Resampling.nearest` (nunca interpolação em classes) |
| Reflectância | `DN * 1e-4 + (-0.1)`; `DN == 0` vira `NaN` **antes** da escala |
| Nodata de saída | `NaN` (float32, GeoTIFF deflate) |
| Máscara SCL | exclui `0, 1, 3, 7, 8, 9, 10, 11` |
| Mantidos | `2` (vegetação muito baixa/solo), `4` (vegetação), `5` (solo exposto), `6` (água) |
| Classe 7 | excluída por precaução (política conservadora, documentada) |
| Denominador | `abs(den) <= 1e-6` → `NaN` (sem `inf`, sem clamp) |
| Estatísticas | somente sobre pixels finitos; informa validados, mascarados e degenerados |

Fórmulas implementadas:

```
NDVI = (NIR - Red) / (NIR + Red)
EVI  = 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)
NDMI = (NIR - SWIR) / (NIR + SWIR)
```

O `+1` do EVI é aplicado sobre reflectância física (0..1), não sobre DN.

## 7. Resultados reais (estatísticas por cena)

| Data | Índice | min | máx | média | mediana | p05 | p95 |
|---|---|---|---|---|---|---|---|
| 2025-06-09 | NDVI | -0,538 | 0,922 | 0,607 | 0,649 | 0,219 | 0,892 |
| 2025-06-09 | EVI | -0,085 | 0,938 | 0,379 | 0,350 | 0,115 | 0,826 |
| 2025-06-09 | NDMI | -0,469 | 0,651 | 0,046 | 0,058 | -0,331 | 0,458 |
| 2025-07-26 | NDVI | -0,515 | 0,903 | 0,371 | 0,223 | 0,166 | 0,821 |
| 2025-07-26 | EVI | -0,113 | 0,906 | 0,225 | 0,146 | 0,112 | 0,476 |
| 2025-07-26 | NDMI | -0,457 | 0,632 | -0,105 | -0,191 | -0,312 | 0,279 |
| 2025-08-28 | NDVI | -0,462 | 0,871 | 0,333 | 0,193 | 0,154 | 0,804 |
| 2025-08-28 | EVI | -0,140 | 0,905 | 0,227 | 0,139 | 0,112 | 0,547 |
| 2025-08-28 | NDMI | -0,448 | 0,542 | -0,104 | -0,197 | -0,283 | 0,319 |
| 2025-09-27 | NDVI | -0,347 | 0,860 | 0,322 | 0,182 | 0,144 | 0,814 |
| 2025-09-27 | EVI | -0,098 | 0,769 | 0,209 | 0,115 | 0,091 | 0,563 |
| 2025-09-27 | NDMI | -0,426 | 0,427 | -0,187 | -0,311 | -0,366 | 0,308 |

Todos os 12 produtos: `out_of_range_pixels = 0` e `degenerate_pixels = 0`.
Faixa dentro de `[-1, 1]`, sem `inf`, sem valores fora do esperado.

**Interpretação:** nenhuma. Os números descrevem reflectância e índices de
vegetação em uma janela técnica; não medem produtividade, não identificam
cultura e não são feature de preço.

## 8. Produtos gerados

| Tipo | Local | Versionado? |
|---|---|---|
| 12 GeoTIFFs (4 cenas × 3 índices), ~1,06–1,11 MB cada | `geospatial/artifacts/` | não (ignorado) |
| Série temporal CSV (12 linhas) | `geospatial/artifacts/series_temporal.csv` | não (ignorado) |
| Manifesto JSON com proveniência/checksums | `geospatial/artifacts/run_20261111T172832Z.json` + `latest.json` | não (ignorado) |
| 4 prévias PNG (376–488 KB) | `geospatial/previews/` | sim |
| Código, testes e README | `geospatial/` | sim |

Verificação independente após a escrita: os 12 GeoTIFFs compartilham **uma
única grade** (CRS, transform, 547×557, nodata `NaN`), e min/max/média/contagem
recalculados a partir dos arquivos coincidem com o CSV/manifesto.

## 9. Testes executados

| Suíte | Comando | Resultado |
|---|---|---|
| Geoespacial (sintético, offline) | `geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests -t geospatial` | **30/30 OK** |
| V1 backend (regressão) | `cd backend; npm test` | **65/65 OK** (~7,96 s) |
| Aquisição real (rede) | `geospatial\.venv\Scripts\python.exe geospatial\run_poc.py --check-only` | OK (54/27/4) |
| Processamento real | `geospatial\.venv\Scripts\python.exe geospatial\run_poc.py` | 4 cenas, 12 GeoTIFFs, 4 PNGs |

A suíte padrão (`unittest`) **não depende de internet**: todos os testes usam
arrays e GeoTIFFs sintéticos.

## 10. Ambiente

| Item | Versão |
|---|---|
| Python | 3.12.10 (Windows) |
| venv | `geospatial/.venv` (isolado, ignorado no Git) |
| pystac-client | 0.9.1 |
| rasterio | 1.4.3 (GDAL 3.9.3) |
| numpy | 2.5.4 |
| matplotlib | 3.11.2 |
| certifi | 2026.10.23 |

Problemas reais encontrados e contornados (documentados para reprodução):

1. `rasterio==1.5.2` (GDAL 3.12.2) **crashava** ao abrir COG remoto no Windows
   (`exit -1073740791`). Fixado em `1.4.3`.
2. GDAL/schannel recusa CA bundle em caminho com acento ("Área de Trabalho").
   `s2_poc/network.py` copia o `cacert.pem` para `%TEMP%` (ASCII) e define
   `CURL_CA_BUNDLE`/`GDAL_HTTP_CAINFO`/`SSL_CERT_FILE` antes de abrir o COG.
   Sem isso, o erro aparece mascarado como `UnicodeDecodeError`.
3. A API de malhas do IBGE responde `Content-Encoding: gzip` mesmo sem o
   cliente pedir; a descompressão é explícita em `s2_poc/aoi.py`.
4. `rasterio 1.4.3` + `numpy 2.5` emite `DeprecationWarning` interno ao ler
   janelas; suprimido localmente em `read.py` (não afeta dados).

## 11. Critérios de aceite V2.1

| Critério | Estado |
|---|---|
| Fonte/coleção gratuita e acessível | ATENDIDO (Earth Search, sem credencial) |
| AOI válido com origem documentada | ATENDIDO (malha IBGE + janela técnica) |
| ≥ 1 cena real L2A adquirida/processada | ATENDIDO (4 cenas) |
| NDVI/EVI/NDMI com bandas, escala, CRS e resolução documentados | ATENDIDO |
| Nuvem/sombra/nodata/inválidos com tratamento verificável | ATENDIDO (SCL + NaN + contagens) |
| Faixa/estatísticas plausíveis | ATENDIDO (0 fora de faixa, 0 degenerados) |
| Testes sintéticos das operações críticas | ATENDIDO (30/30) |
| Saída visual + série tabular reproduzível | ATENDIDO (4 PNG + CSV + JSON) |
| Comandos de reprodução documentados | ATENDIDO (`geospatial/README.md`) |
| V1 íntegra e testes passando | ATENDIDO (65/65; ponteiros inalterados) |

**V2.1 = concluída** no escopo de pipeline com 4 datas. Isso **não** comprova
análise sazonal, produtividade, qualidade agronômica nem melhoria de previsão.

## 12. Pendências e próxima ação

1. **GitHub Release `v1-final`**: bloqueado por falta de autenticação `gh`
   (sem `GH_TOKEN`/`GITHUB_TOKEN`, e o login por navegador foi proibido).
   Notas prontas em `docs/releases/v1-final.md`. Tag, `main`, `archive/v1-final`
   e bundle estão publicados/verificados; falta apenas o objeto Release.
2. **V2.2 (não iniciada)**: ampliar a janela temporal (ex.: 2023–2025) e/ou
   incluir segundo tile; só depois discutir integração com o produto.
3. **V2.3 (não iniciada)**: dados observados de produtividade — sem rótulos
   reais, nenhum modelo de produtividade será criado.
4. Nada de UI/dashboard/endpoint novo enquanto a PoC não for revisada.

## 13. Comandos de retomada

```powershell
git switch v2/geospatial-foundation
geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests -t geospatial
geospatial\.venv\Scripts\python.exe geospatial\run_poc.py --check-only
geospatial\.venv\Scripts\python.exe geospatial\run_poc.py
```

Antes de qualquer coisa em nova sessão: ler este arquivo,
`docs/AI_CONTEXT_RECOVERY.md` e a última decisão em `docs/DECISIONS.md`.
