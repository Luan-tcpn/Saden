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

## 7. Checkpoint E — série temporal 2023–2025

**FATO.** Comando:

```powershell
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py timeseries --start 2023-01 --end 2025-12
```

### 7.1 Desenho

| Parâmetro | Valor |
|---|---|
| AOI | de validação (`[-55.6309, -12.7339, -55.5709, -12.6739]`), 43,26 km² |
| Grade | EPSG:32721, 20 m, 329 × 334 px (109.886 px), transform `(20, 0, 648620, 0, −20, 8598540)` |
| Período | 36 meses (2023-01 … 2025-12) |
| Máscara | Perfil B (D43) |
| Radiometria | `DN * 0.0001 − 0.1` em todos os meses (baselines 05.09, 05.10, 05.11) |
| Tile | `MGRS-21LXG` em toda a série (comparabilidade temporal) |
| Critério de seleção | menor **fração obstruída sobre a AOI** entre até 4 candidatas do mês; desempate por nuvem do tile e depois por `item_id` |
| Limite de obstrução | 0,50 (acima disso o mês é `no_usable_observation`) |
| Nº de cenas | 1 por mês (cena única, não composição) |

### 7.2 Cobertura mensal e lacunas

**FATO.** 36 meses pesquisados; **34 com observação utilizável** e **2 sem**
(motivo registrado, sem preenchimento):

| Mês | Itens no catálogo | Itens cobrindo a AOI | Itens no tile | Melhor candidata (obstrução sobre a AOI) | Resultado |
|---|---|---|---|---|---|
| 2023-01 | 14 | 14 | 7 | `S2B_T21LXG_20230131T140226_L2A` — 84,7% obstruído | `no_usable_observation` |
| 2024-12 | 18 | 18 | 9 | `S2C_T21LXG_20241216T135729_L2A` — 86,5% obstruído | `no_usable_observation` |

Nos dois casos havia cenas no catálogo: a qualidade sobre a AOI é que era
inaceitável. Os valores de NDVI/EVI/NDMI desses meses estão **vazios** no CSV
(`status = no_usable_observation`), sem interpolação, cópia ou média.

### 7.3 Qualidade por mês (AOI de validação)

| Mês | Item | Data | Baseline | Nuvem do tile (%) | Obstrução na AOI | Cobertura válida | NDVI médio |
|---|---|---|---|---|---|---|---|
| 2023-01 | — | — | — | — | — | — | — (lacuna) |
| 2023-02 | `S2B_T21LXG_20230210T140531_L2A` | 2023-02-10 | 05.09 | 32,89 | 3,73% | 96,25% | 0,420 |
| 2023-04 | `S2A_T21LXG_20230421T140527_L2A` | 2023-04-21 | 05.09 | 65,23 | 3,16% | 96,84% | 0,829 |
| 2023-06 | `S2A_T21LXG_20230605T140010_L2A` | 2023-06-05 | 05.09 | 0,01 | 0,12% | 99,88% | 0,547 |
| 2023-08 | `S2B_T21LXG_20230819T135707_L2A` | 2023-08-19 | 05.09 | 6,55 | 0,05% | 99,95% | 0,286 |
| 2023-10 | `S2A_T21LXG_20231003T135802_L2A` | 2023-10-03 | 05.09 | 17,25 | 0,11% | 99,89% | 0,293 |
| 2023-12 | `S2A_T21LXG_20231202T135654_L2A` | 2023-12-02 | 05.09 | 49,96 | 0,09% | 99,91% | 0,789 |
| 2024-03 | `S2A_T21LXG_20240301T135702_L2A` | 2024-03-01 | 05.10 | 34,78 | 15,60% | 84,36% | 0,548 |
| 2024-06 | `S2A_T21LXG_20240609T140526_L2A` | 2024-06-09 | 05.10 | 2,39 | 0,08% | 99,88% | 0,475 |
| 2024-09 | `S2A_T21LXG_20240917T135930_L2A` | 2024-09-17 | 05.11 | 0,00 | 0,00% | 100,00% | 0,299 |
| 2024-12 | — | — | — | — | — | — | — (lacuna) |
| 2025-03 | `S2B_T21LXG_20250301T140548_L2A` | 2025-03-01 | 05.11 | 55,36 | 27,64% | 72,25% | 0,415 |
| 2025-06 | `S2B_T21LXG_20250609T140533_L2A` | 2025-06-09 | 05.11 | 0,00 | 0,07% | 99,87% | 0,560 |
| 2025-09 | `S2C_T21LXG_20250902T140110_L2A` | 2025-09-02 | 05.11 | 1,09 | 0,02% | 99,93% | 0,282 |
| 2025-12 | `S2C_T21LXG_20251211T140459_L2A` | 2025-12-11 | 05.11 | 52,13 | 3,97% | 96,01% | 0,827 |

(A tabela mostra meses alternados; os 34 meses completos estão em
`geospatial/reports/timeseries_mensal_2023-01_2025-12.csv` — uma linha por
mês × índice, com média, mediana, desvio, quantis p5/p25/p75/p95, pixels
válidos, cobertura, área válida, item, data, baseline, nuvem do tile,
obstrução na AOI e política SCL.)

**FATO.** A nuvem do **tile inteiro** e a obstrução sobre a **AOI** divergem
fortemente: em 2023-04 o tile tinha 65,23% de nuvem e a AOI apenas 3,16% de
obstrução; em 2024-11 o tile tinha 73,87% de nuvem e a AOI 0,06%. Isso
demonstra que `eo:cloud_cover` do tile não é critério de qualidade para a área
de interesse.

**FATO.** Cobertura válida por mês: de 72,25% (2025-03) a 100% (2024-09);
NDVI médio de 0,270 (2023-09) a 0,871 (2025-04).

### 7.4 Comparabilidade temporal

**FATO.** Mesma máscara, mesma grade, mesma conversão radiométrica e mesmo tile
em todos os 34 meses. Os baselines mudam ao longo do período
(**05.09** em 2023, **05.10** no primeiro semestre de 2024, **05.11** de
2024-07 em diante), mas **todos** ≥ 04.00 e todos com `scale = 0.0001` /
`offset = −0.1`: não há quebra de método dentro da série. A série é de
**cena única por mês** (não é composição temporal).

**INTERPRETAÇÃO.** O gráfico da série mostra um ciclo anual repetido
(valores mais altos entre abril–maio e dezembro, mais baixos entre
agosto–outubro). Isso é um padrão de **reflectância de vegetação na AOI**.

**LIMITAÇÃO.** O ciclo **não** pode ser lido como produtividade, ciclo de
cultura, saúde de lavoura ou previsão de safra: a AOI não tem uso do solo
identificado, a classe SCL 5 provavelmente inclui áreas cultivadas, e não há
dado independente de produção. A qualidade da série é **espacial-temporal**,
não agronômica.

Artefatos: `geospatial/reports/timeseries_mensal_2023-01_2025-12.csv`,
`geospatial/manifests/timeseries_20261111T182443Z.json`,
`geospatial/previews/timeseries/series_2023-01_2025-12.png` (lacunas visíveis
como quebra de linha e barra de cobertura zerada) e
`geospatial/artifacts/timeseries/<mês>/*.tif` (não versionados).

**FATO.** A série foi executada **duas vezes** (18:18 e 18:24 UTC) com o mesmo
resultado: mesmos 34 meses observados, mesmas 2 lacunas e **estatísticas
idênticas** — a seleção é determinística.

## 8. Metodologia radiométrica e espacial

### 8.1 Radiometria

1. Leitura direta do COG (sem cache local): `rasterio.open` sobre HTTP com
   `GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR`.
2. `rasterio.read()` devolve o **DN uint16 bruto**; `ds.scales`/`ds.offsets`
   são metadados e **não** são aplicados pelo driver.
3. Conversão aplicada **uma única vez**: `reflectance = DN * 0.0001 + (−0.1)`,
   com `DN == 0` (nodata) convertido em `NaN` **antes** da escala.
4. Auditoria por item: baseline ≥ 04.00 obrigatório; escala/offset obrigatórios
   e idênticos entre B02/B04/B08/B11; o que o COG declara é conferido contra o
   metadado STAC (evita dupla aplicação e conversão inventada).
5. Fórmulas aplicadas sobre `float64`, na mesma grade, sem clipping.

### 8.2 Spatial

1. Grade de trabalho: 20 m, `EPSG:32721` (UTM 21S), alinhada a múltiplos de
   20 m, transform idêntico entre cenas e produtos.
2. Contínuas (10 m → 20 m): `Resampling.average`; categórica (SCL, 20 m):
   `Resampling.nearest`.
3. Recorte pela AOI em EPSG:4326, convertido para o CRS do tile com
   `transform_bounds(densify_pts=21)`.
4. Mosaico: mesma grade forçada a partir do tile primário, `first_valid_wins`,
   mapa de origem por pixel.
5. Áreas: projeção de área igual `EPSG:6933` e área geodésica WGS84
   (`pyproj.Geod`).

## 9. Métricas de qualidade

| Métrica | Resultado |
|---|---|
| Reprodução da PoC | grade idêntica; **delta 0,0** em todas as estatísticas comparadas |
| Auditoria radiométrica | 4/4 itens com metadado STAC e COG concordantes (escala/offset/dtype/nodata) |
| Pixels degenerados | 0 em todas as cenas e meses (denominador protegido) |
| Pixels fora da faixa plausível (`[-1.5, 1.5]`) | 0 |
| Cobertura válida da AOI de validação | 72,25%–100% por mês (34 meses) |
| Meses com observação | 34/36 (2 lacunas justificadas por obstrução) |
| Consistência entre tiles (sobreposição) | NDVI/EVI/NDMI com correlação ≥ 0,99999 e |Δ| médio ≤ 0,001 |
| Pixels sem dado no mosaico | 1.191 de 971.781 (0,12%) — bordas dos footprints |
| Testes offline | **95/95 OK** |
| Testes externos | **4/4 OK**, separados e opt-in (`SADEN_EXTERNAL_TESTS=1`) |
| V1 | intocada; ponteiros Git e testes da V1 não alterados |

## 10. Limitações e itens não validados

1. **Não há validação com dado de campo.** Os índices não têm comparação
   independente (ground truth, reflectância de campo ou produção observada).
2. **Não há classificação de uso do solo.** A AOI não tem cultura,
   propriedade ou cobertura de solo identificada; a classe SCL 5 provavelmente
   inclui áreas cultivadas.
3. **Série curta e exploratória.** 36 meses, 34 observados, uma AOI, um tile.
   Não sustenta tendência, modelo ou previsão.
4. **Sem correção radiométrica atmosférica** (BRDF, aerossol, topografia) e
   sem diferença de mixed pixels.
5. **Máscara SCL é um classificador de cena**, não de cultura; a decisão D43
   usa evidência de 4 cenas sem nuvem e é revisável.
6. **Não processado**: município inteiro em 10/20 m (estimado, não executado),
   composição temporal multi-cena, mosaico de mais de dois tiles.
7. **Coordenadas sem datum geodésico explícito** nos rótulos dos mapas (o
   CRS está nos metadados dos rasters).
8. **QGIS**: nenhum projeto QGIS foi gerado nem revisado — a inspeção visual
   foi feita pelos PNGs gerados pelo matplotlib.
9. **Termos de uso a confirmar antes de publicação acadêmica**: a licença do
   conjunto de dados é registrada por duas fontes divergentes (STAC
   `proprietary` × AWS “free, full and open”).
10. **Pendência externa**: o objeto *GitHub Release* `v1-final` continua
    bloqueado por falta de autenticação `gh` (sem token; login por navegador
    proibido). Tag, branches e bundle estão verificados.

## 11. Como reproduzir

```powershell
# 0) ambiente (Windows, Python 3.12)
python -m venv geospatial\.venv
geospatial\.venv\Scripts\python.exe -m pip install -r geospatial\requirements.txt

# 1) suíte offline (sem internet)
geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests -t geospatial

# 2) checkpoints A–E (rede)
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py repro
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py scl --aoi historical
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py geometry
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py mosaic
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py timeseries --start 2023-01 --end 2025-12

# 3) reprodução da PoC original (Perfil A, para baseline histórica)
geospatial\.venv\Scripts\python.exe geospatial\run_poc.py
```

Cada execução real grava um manifesto em `geospatial/manifests/` com: id da
execução, data/hora UTC, commit do código, versões das dependências, catálogo
e coleção, data de acesso, IDs STAC e metadados essenciais de cada item, AOI
(fonte/versão/CRS/bbox), bandas e assets, fórmula de escala/offset com a
evidência de origem, CRS/resolução/transform/dimensões/reamostragem, regra
SCL, fórmulas e tratamento de denominador/nodata, regra de mosaico e origem
por pixel, estatísticas e cobertura, arquivos gerados com tamanho e SHA-256,
erros, avisos, lacunas e limitações.

## 12. Estado Git e integridade

| Item | Valor |
|---|---|
| Branch da missão | `v2/geospatial-validation` (derivada de `v2/geospatial-foundation` / `2e5b3ef`) |
| Commits da missão | ver `git log --oneline v2/geospatial-foundation..v2/geospatial-validation` |
| `main` / `v1-final` / `archive/v1-final` | `3f7ad33` — **inalterados** (local e remoto) |
| Tag `v1-final` | objeto `e62a5372e8bc69a87f642398681ed4df13d4fc54` — inalterada |
| Tag `v2-poc-sentinel2` | checkpoint imutável da PoC em `2e5b3ef` |
| Bundle | `..\SADEN_V2_1_RECOVERY_2026-11-11\saden-v2-1-start-2026-11-11.bundle` — 2.435.845 bytes, SHA-256 `74727C339F8A2E0D01D077E43D2551993B757D6B40D084C68C7385763F7B1274`, `git bundle verify` OK |
| Push | apenas da branch de validação; sem `--force`, sem merge em `main` |
| V1 (backend/frontend/schema/Ridge) | nenhuma alteração |

## 13. Critérios de aceite — situação

| Bloco | Situação |
|---|---|
| Integridade e segurança | **ATENDIDO** — V1 intacta, PoC recuperável (tag + bundle), branch derivada, sem segredo/banco/cache/raster pesado versionado, nenhuma alteração no produto |
| Reprodutibilidade e radiometria | **ATENDIDO** — PoC reexecutada (delta 0,0), coleção/assets/baseline/unidades verificados, escala/offset confirmados sem dupla aplicação, fórmulas e nodata testados, grades/CRS/transforms/reamostragem auditados |
| Máscara e geometria | **ATENDIDO** — A × B comparados quantitativa e visualmente, efeito das classes 2 e 6 demonstrado, decisão documentada (D43), limite municipal oficial com versão/CRS, interseção quantificada, três AOIs diferenciadas |
| Mosaico e tempo | **ATENDIDO** — caso real de dois tiles do mesmo datatake demonstrado com rasters e mapa de origem, regra documentada/testada (D44), série 2023–2025 com 2 lacunas justificadas, meses ausentes continuam ausentes, comparabilidade e baselines avaliados |
| Qualidade e entrega | **ATENDIDO** — 95/95 testes offline, testes externos separados, manifestos com metadados e hashes, relatório e instruções de reprodução atualizados, estado Git registrado, próxima missão proposta sem implementação |
| Fora de escopo (não iniciado) | V2.2 (dados observados de produtividade), V2.3 (modelagem agronômica), V2.4 (integração ao Ridge), UI/dashboard, clima no modelo |
| **BLOQUEADO** | GitHub Release `v1-final` — sem autenticação `gh`; não afeta a V2.1 |
