# SADEN V2.1 — Relatório técnico de validação geoespacial

> Branch de trabalho: `v2/geospatial-validation` (derivada de
> `v2/geospatial-foundation`, commit `2e5b3ef`). Checkpoint imutável da PoC:
> tag anotada `v2-poc-sentinel2`. V1 intocada (`3f7ad33`, tag `v1-final`).
> Bundle de segurança: `..\SADEN_V2_1_RECOVERY_2026-11-11\saden-v2-1-start-2026-11-11.bundle`
> (2.435.845 bytes, SHA-256 `74727C33…B1274`, `git bundle verify` OK).
> Execuções de referência: 2026-11-11.

Este relatório é revisável **sem abrir o código**. Cada seção separa
**FATO** (observado/calculado), **INTERPRETAÇÃO** (leitura possível) e
**LIMITAÇÃO** (o que o dado não permite concluir).

Índice:

1. [Objetivo e escopo](#1-objetivo-e-escopo)
2. [Fonte e identificação das cenas](#2-fonte-e-identificação-das-cenas)
3. [Checkpoint A — reprodução e auditoria da PoC](#3-checkpoint-a--reprodução-e-auditoria-da-poc)
4. [Checkpoint B — comparação da máscara SCL](#4-checkpoint-b--comparação-da-máscara-scl)
5. [Checkpoint C — geometria municipal e AOIs](#5-checkpoint-c--geometria-municipal-e-aois)
6. [Checkpoint D — mosaico de dois tiles](#6-checkpoint-d--mosaico-de-dois-tiles)
7. [Checkpoint E — série temporal 2023–2025](#7-checkpoint-e--série-temporal-20232025)
8. [Metodologia radiométrica e espacial](#8-metodologia-radiométrica-e-espacial)
9. [Métricas de qualidade](#9-métricas-de-qualidade)
10. [Limitações e itens não validados](#10-limitações-e-itens-não-validados)
11. [Como reproduzir](#11-como-reproduzir)
12. [Estado Git e integridade](#12-estado-git-e-integridade)

---

## 1. Objetivo e escopo

**FATO.** A missão transformou a PoC Sentinel-2 (4 cenas, jun–set/2025) em uma
base geoespacial reproduzível e auditável, com cinco checkpoints: (A)
reprodução e auditoria radiométrica, (B) comparação de máscaras SCL, (C)
geometria municipal oficial e AOIs diferenciadas, (D) mosaico real de dois
tiles e (E) série temporal exploratória 2023–2025.

**FATO.** Fora de escopo e não executado: modelos de produtividade, integração
dos índices à previsão de preços (Ridge), integração ao dashboard, novas
fontes climáticas, qualquer alteração em `frontend/`, `backend/`, schema
SQLite ou na Ridge da V1.

**LIMITAÇÃO.** Nada neste relatório mede produtividade, saúde de lavoura,
uso do solo ou preço. Os índices descrevem reflectância de superfície e
classificação de cena em recortes geográficos.

## 2. Fonte e identificação das cenas

**FATO.** Catálogo: Earth Search / Element 84
(`https://earth-search.aws.element84.com/v1`), coleção `sentinel-2-c1-l2a`
(Sentinel-2 Collection 1 Level-2A), acesso **anônimo**, sem credencial e sem
custo.

| Fonte | Informação registrada |
|---|---|
| Earth Search (STAC) | coleção declara `license: proprietary` |
| Registry of Open Data on AWS | “Access to Sentinel data is free, full and open” |

**FATO.** Assets e radiometria verificados item a item: `blue` (B02, 10 m),
`red` (B04, 10 m), `nir` (B08, 10 m), `swir16` (B11, 20 m), `scl` (20 m);
`scale = 0.0001`, `offset = -0.1`, `nodata = 0`, `dtype = uint16` (contínuas)
e `uint8` (SCL).

**FATO.** Semântica oficial das classes SCL (Copernicus Data Space /
Sentinel Hub, tabela S2L2A, consultada em 2026-11-11):

| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| No data | Saturated/defective | **Dark area pixels** | Cloud shadows | Vegetation | Bare soils | Water | Clouds low prob./Unclassified | Clouds medium prob. | Clouds high prob. | Cirrus | Snow/ice |

**LIMITAÇÃO.** A coleção declara licença `proprietary` no STAC enquanto o
registro da AWS descreve acesso livre e aberto; ambas as fontes ficam
registradas e nenhuma licença única é afirmada.

## 3. Checkpoint A — reprodução e auditoria da PoC

### 3.1 Reexecução limpa

**FATO.** Comando real:

```powershell
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py repro
```

A PoC foi reexecutada em diretório **separado** (`geospatial/artifacts/repro_poc/`),
sem reaproveitar rasters antigos: as janelas dos COGs foram lidas da rede.
Duração registrada: **29,3 s** para 4 cenas (5 assets cada).

| Item | Data | Nuvem do tile (%) | Baseline | Grade | Pixels válidos (Perfil A) |
|---|---|---|---|---|---|
| `S2B_T21LXG_20250609T140533_L2A` | 2025-06-09 | 0,002827 | 05.11 | 547×557, EPSG:32721 | 304.510 / 304.679 (99,94%) |
| `S2A_T21LXG_20250726T140110_L2A` | 2025-07-26 | 0,000956 | 05.11 | 547×557, EPSG:32721 | 304.526 / 304.679 (99,95%) |
| `S2B_T21LXG_20250828T135714_L2A` | 2025-08-28 | 0,001088 | 05.11 | 547×557, EPSG:32721 | 304.558 / 304.679 (99,96%) |
| `S2B_T21LXG_20250927T135901_L2A` | 2025-09-27 | 0,026692 | 05.11 | 547×557, EPSG:32721 | 304.555 / 304.679 (99,96%) |

**FATO.** Comparação com o manifesto anterior (`artifacts/latest.json`,
execução de 2026-11-11T17:28:32Z): **grade idêntica** e **diferença 0,0 em
todas as estatísticas** comparadas (píxeis válidos, fração válida, mínimo,
máximo, média e mediana do NDVI). A PoC é, portanto, **reproduzível bit a bit**
com os comandos documentados.

### 3.2 Auditoria radiométrica (o ponto crítico)

**FATO.** Para as 4 cenas, o metadado STAC e o COG real concordam:

| Verificação | Resultado |
|---|---|
| `s2:processing_baseline` | 05.11 (≥ 04.00 → com `BOA_ADD_OFFSET`) |
| `raster:bands[0].scale` / `offset` (STAC) | 0.0001 / −0.1 |
| `ds.scales` / `ds.offsets` (COG aberto via rasterio) | 0.0001 / −0.1 — **coincidem** |
| `rasterio.read()` devolve DN bruto | sim (uint16); a escala **não** é aplicada pelo driver |
| `dtype` / `nodata` do arquivo | uint16 / 0 |
| Conversão aplicada | `DN * 0.0001 − 0.1`, com `DN == 0 → NaN` **antes** da escala |

**FATO.** O código bloqueia (não processa) qualquer item com baseline
ausente ou < 04.00, escala/offset ausentes, dtype inesperado ou radiometria
inconsistente entre bandas (`s2_poc/radiometry.py`, coberto por testes).

**INTERPRETAÇÃO.** Não há dupla aplicação de escala/offset: a auditoria
compara o metadado do item com o que o driver realmente declara no arquivo e
confere a aplicação manual única.

### 3.3 Fórmulas e grade

**FATO.** Fórmulas implementadas e testadas com valores conhecidos:

```
NDVI = (B08 − B04) / (B08 + B04)
EVI  = 2.5 × (B08 − B04) / (B08 + 6×B04 − 7.5×B02 + 1)
NDMI = (B08 − B11) / (B08 + B11)
```

- Bandas na mesma unidade radiométrica e na **mesma grade** antes da operação;
  conversão em `float64` antes das fórmulas (sem overflow de `uint16`).
- Denominador `|den| ≤ 1e-6` → `NaN`; `NaN`/`inf` de entrada propagam;
  **nenhum clipping** é aplicado (o EVI não é limitado a `[-1, 1]`).
- `DN == 0` vira `NaN` antes da escala; `+1` do EVI aplicado sobre reflectância
  física, não sobre DN.
- Reamostragem: `average` para B02/B04/B08 (10 m → 20 m) e `nearest` para SCL
  (nunca interpolação em classes). Transform único
  `(20, 0, 646440, 0, −20, 8601880)` idêntico nas 4 cenas.

**FATO.** Nenhuma diferença relevante foi encontrada entre a reexecução e a
PoC reportada; nada foi "atualizado em silêncio".

## 4. Checkpoint B — comparação da máscara SCL

**FATO.** Comando:

```powershell
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py scl --aoi historical
```

Mesmas 4 cenas da PoC, AOI histórica (304.679 px/cena; 0,0004 km² por pixel em
`EPSG:32721`, ou seja, 121,8 km² válidos por cena no Perfil A).

- **Perfil A (histórico)**: exclui `0, 1, 3, 7, 8, 9, 10, 11`.
- **Perfil B (restritivo)**: A + classes `2` (dark area) e `6` (água).
- **Perfil C (diagnóstico)**: contagem e estatísticas de **cada classe** SCL
  separadamente (não é produto final).

### 4.1 Composição da cena por classe SCL

| Classe | 2025-06-09 | 2025-07-26 | 2025-08-28 | 2025-09-27 |
|---|---|---|---|---|
| 2 — Dark area pixels | 106 (0,035%) | 112 (0,037%) | 116 (0,038%) | 144 (0,047%) |
| 4 — Vegetation | 221.105 (72,57%) | 92.123 (30,24%) | 72.897 (23,93%) | 71.583 (23,49%) |
| 5 — Bare soils | 82.934 (27,22%) | 211.934 (69,56%) | 231.231 (75,89%) | 232.655 (76,36%) |
| 6 — Water | 365 (0,120%) | 357 (0,117%) | 314 (0,103%) | 173 (0,057%) |
| 7 — Clouds low prob./Unclassified | 169 (0,055%) | 153 (0,050%) | 121 (0,040%) | 124 (0,041%) |
| 0, 1, 3, 8, 9, 10, 11 | 0 | 0 | 0 | 0 |

### 4.2 Efeito das classes 2 e 6 sobre os índices (cena 2025-06-09)

| Classe | NDVI médio | NDVI mediana | NDVI p25 | NDVI p75 | EVI médio | NDMI médio |
|---|---|---|---|---|---|---|
| 4 — Vegetation | 0,726 | 0,780 | 0,599 | 0,844 | — | — |
| 5 — Bare soils | 0,295 | 0,303 | 0,246 | 0,355 | — | — |
| 2 — Dark area | 0,319 | 0,322 | 0,028 | 0,662 | 0,124 | 0,060 |
| 6 — Water | **−0,196** | **−0,288** | −0,401 | −0,021 | −0,020 | −0,096 |

### 4.3 Cobertura e estatísticas por perfil

| Cena | Perfil A válidos | Perfil B válidos | Pixels A→B | B→A | Δ média NDVI | Δ relativa |
|---|---|---|---|---|---|---|
| 2025-06-09 | 304.510 (99,94%) | 304.039 (99,79%) | 471 (0,155%) | 0 | +0,001065 | +0,175% |
| 2025-07-26 | 304.526 (99,95%) | 304.057 (99,80%) | 469 (0,154%) | 0 | +0,000671 | +0,181% |
| 2025-08-28 | 304.558 (99,96%) | 304.128 (99,82%) | 430 (0,141%) | 0 | +0,000482 | +0,145% |
| 2025-09-27 | 304.555 (99,96%) | 304.238 (99,86%) | 317 (0,104%) | 0 | +0,000245 | +0,076% |

Distribuição do NDVI no Perfil A (cena 2025-06-09): média 0,6072; mediana
0,6494; desvio 0,2332; mínimo −0,5378; máximo 0,9218; p05 0,2186; p25
0,3879; p75 0,8184; p95 0,8917.

**FATO.** A mudança de política remove no máximo 0,155% dos pixels e altera a
média do NDVI em no máximo 0,18% (relativo). Nenhum pixel muda de inválido
(Perfil A) para válido (Perfil B).

**INTERPRETAÇÃO.** A classe 6 (água) apresenta NDVI médio negativo
(−0,196) e, se mantida, desloca a média da AOI para baixo e injeta valores
negativos em uma estatística de índice de vegetação. A classe 2 é
heterogênea (p25 0,028 a p75 0,662), compatível com sombra/terreno escuro
misturado a vegetação escura. Como o objetivo do máscara é a qualidade de
pixels **para índices de vegetação**, o Perfil B é semanticamente mais correto,
a um custo de cobertura desprezível.

**DECISÃO (D43).** O Perfil A permanece como regra da **reprodução da PoC**
(`run_poc.py` / `pipeline.run`), para manter a baseline histórica exatamente
reproduzível. O **Perfil B** passa a ser o padrão da **V2.1**
(`config.V2_1_SCL_PROFILE`) nos produtos novos (mosaico e série temporal).
A mudança é explícita, versionada e não é exposta como opção ao usuário final.

**LIMITAÇÃO.** A evidência vem de 4 cenas **sem nuvem** em uma única AOI e em
uma estação. (a) A classe 2 pode conter vegetação genuinamente escura, que
passaria a ser excluída; (b) a classe 5 ("bare soils") provavelmente inclui
áreas cultivadas — o SCL não é classificador de cultura — e ela **continua
válida** nas duas máscaras, de modo que as médias da AOI ainda misturam
superfícies diferentes; (c) em cenas com nuvem, a distinção entre classes 2 e
3 merece reavaliação. A decisão é revisável.

Artefatos: `geospatial/manifests/scl_20261111T181342Z.json`,
`geospatial/reports/scl_class_stats_20261111T181342Z.csv` e prévias
`geospatial/previews/scl/*.png` (SCL, Perfil A, Perfil B e mapa de diferença).

## 5. Checkpoint C — geometria municipal e AOIs

**FATO.** Comando:

```powershell
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py geometry
```

| Item | Valor |
|---|---|
| Fonte | IBGE — Malhas Territoriais, API v3 (`formato=application/vnd.geo+json&qualidade=maxima`) |
| Código / nome / UF | `5107925` / Sorriso / MT |
| Versão da malha | qualidade `maxima` (2.689 vértices) — consultada em 2026-11-11 |
| Tipo / validade | `Polygon`, topologicamente válida, não vazia |
| CRS de origem | EPSG:4326 |
| Área geodésica (WGS84) | 9.293,46 km² |
| Área em projeção de área igual (EPSG:6933) | 9.293,47 km² |
| Bbox municipal | `[-56.1167, -13.6661, -55.0851, -11.7216]` |

### 5.1 Interseção da AOI técnica histórica com o município

| Métrica | Valor |
|---|---|
| Área total da bbox | 120,16 km² |
| Dentro do município | 119,65 km² (99,58%) |
| **Fora do município** | **0,51 km² (0,42%)** |
| Totalmente contida? | **não** |

**FATO.** A bbox histórica **não** é área municipal. Ela é preservada como
recorte técnico para reprodução da PoC; qualquer análise municipal usa o
polígono oficial.

### 5.2 AOI de validação

| Métrica | Valor |
|---|---|
| Bbox | `[-55.6309, -12.7339, -55.5709, -12.6739]` (0,06°) |
| Área (EPSG:6933) | 43,26 km² |
| Pixels a 20 m | ~108.140 |
| Dentro do município | sim |
| Dentro da sobreposição `21LXG`/`21LXF` | sim |

### 5.3 Custo operacional (estimativa, não execução)

| Item | Valor |
|---|---|
| Município inteiro a 20 m | 23.233.677 px/banda |
| Memória (float32) por banda e por data | 92,9 MB |
| 5 bandas de uma data | ~465 MB |
| Decisão | processar **apenas AOIs controladas** nesta missão |

**INTERPRETAÇÃO.** Processar o município inteiro em 20 m para 36 meses exigiria
decenas de gigabytes de raster e não responde a nenhuma pergunta desta
missão.

**LIMITAÇÃO.** Nenhuma AOI representa lavoura. A identificação de áreas
agrícolas depende de fonte/classificador validado e é etapa própria.

Artefatos: `geospatial/manifests/geometry_20261111T181327Z.json`,
`geospatial/artifacts/geometry/*.geojson` (município + AOIs) e
`geospatial/previews/geometry/aoi_geometry.png`.

## 6. Checkpoint D — mosaico de dois tiles

**FATO.** Comando:

```powershell
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py mosaic
```

### 6.1 Caso real identificado

| Item | Valor |
|---|---|
| Tile primário | `S2B_T21LXG_20230620T135711_L2A` (`MGRS-21LXG`) |
| Tile secundário | `S2B_T21LXF_20230620T135711_L2A` (`MGRS-21LXF`) |
| Critério de par | **mesmo `s2:datatake_id`** (`GS2B_20230620T135709_032840_N05.09`) |
| `datetime` XG / XF | 2023-06-20T14:06:00.946Z / 2023-06-20T14:06:15.476Z |
| Diferença temporal medida | **14,53 s** (registrada, não ignorada) |
| Baseline | 05.09 / 05.09 (iguais) |
| Nuvem do tile | 0,001111% / 0,000916% |
| Busca | 492 itens na AOI; **238 pares** de tiles do mesmo datatake |
| AOI do mosaico | `[-55.70, -12.78, -55.50, -12.62]` |

**FATO.** Tiles adjacentes têm tempos de sensoriamento próprios; agrupar por
`datetime` exato perderia todos os pares. O agrupamento por `datatake_id`
(documented em D44) é o critério correto, e a tolerância temporal é medida e
registrada no manifesto. Nenhuma cena de data diferente foi combinada.

### 6.2 Grade, regra e cobertura

| Métrica | Valor |
|---|---|
| Grade comum | EPSG:32721, 20 m, 1.092 × 891 px |
| Transform | `(20, 0, 641100, 0, −20, 8604540)` |
| Regra | `first_valid_wins`, prioridade `21LXG > 21LXF`, **sem média** |
| Pixels de origem `21LXG` | 779.708 |
| Pixels de origem `21LXF` | 192.073 |
| Pixels sem dado | 1.191 (bordas dos footprints) |
| Pixels de costura (seam) | 2.185 |

### 6.3 Diferença entre tiles na faixa de sobreposição (antes da regra)

| Grandeza | Pixels comuns | Diferença absoluta média | RMSE | Correlação |
|---|---|---|---|---|
| Reflectância B02 | 535.080 | 0,000143 | 0,000297 | 0,99991 |
| Reflectância B04 | 535.080 | 0,000243 | 0,000606 | 0,99994 |
| Reflectância B08 | 535.080 | 0,000465 | 0,001063 | 0,99993 |
| Reflectância B11 | 533.988 | 0,000406 | 0,000614 | 0,99998 |
| NDVI | 532.940 | 0,000951 | 0,001375 | 0,99999 |
| EVI | 532.940 | 0,000753 | 0,001072 | 0,99999 |
| NDMI | 532.940 | 0,000788 | 0,001077 | 0,99999 |

**FATO.** A diferença entre os dois tiles na sobreposição é de ~10⁻³ nos
índices, com correlação ≥ 0,9999: a continuidade espacial é consistente, e a
diferença é de reprocessamento/orbital, não de cena diferente.

**INTERPRETAÇÃO.** A regra `first_valid_wins` com prioridade explícita é
preferível à média: mantém a proveniência de cada pixel, evita “suavizar”
uma diferença real de tiles e torna o seamline auditável por mapa de origem.

**LIMITAÇÃO.** A diferença medida é uma comparação **interna** entre tiles do
mesmo datatake; ela **não** valida o erro absoluto dos índices Sentinel-2
(seria necessário dado de campo/ground truth).

Artefatos: `geospatial/manifests/mosaic_*.json`,
`geospatial/artifacts/mosaic/*.tif` (índices, mapa de origem, SCL) e
`geospatial/previews/mosaic/mosaic_2023-06-20.png`.

<!-- SECAO-E -->
