# SADEN V2 — estado de execução (memória operacional)

> Atualizado em **2026-11-11**. Branch de trabalho: `v2/agricultural-productivity-exploratory`
> (derivada de `v2/agricultural-productivity-data` / `775d57b`). A V1 permanece
> congelada: `main`, `v1-final` e `archive/v1-final` continuam em `3f7ad33`.
> Relatório técnico da validação V2.1: `docs/V2_1_VALIDATION_REPORT.md`.
> Relatório técnico da V2.2: `geospatial/reports/V2_2_PRODUCTIVITY_DATA_COMPATIBILITY.md`.
> Relatório técnico da V2.3: `geospatial/reports/V2_3_EXPLORATORY_PRODUCTIVITY_STUDY.md`.
> Plano: `docs/V2_1_VALIDATION_PLAN.md`. Decisões: `docs/DECISIONS.md` (D42–D53).

## 1. Etapa atual

**V2.3 — estudo exploratório municipal de produtividade, em execução** na
branch `v2/agricultural-productivity-exploratory`: harmonização radiométrica
histórica (2017–2025) comprovada, uso do solo da AOI quantificado, conjunto
temporariamente pareado com o rendimento do IBGE/PAM e estatísticas
exploratórias sob portão amostral explícito. Sem integração ao produto, sem
modelo em produção, sem alteração na V1.

## 2. Fronteira V1 × V2

| Item | Estado |
|---|---|
| `main` | `3f7ad33bc18c5a8e8e050bbc7817f5078488d625` (intacto) |
| `v1-final` | tag anotada → `3f7ad33` (intacta) |
| `archive/v1-final` | `3f7ad33` (local e remoto) |
| `v2/geospatial-foundation` | `2e5b3ef`, base da PoC |
| `v2/geospatial-validation` | branch da V2.1; publicada (`c7842d6`) |
| `v2/agricultural-productivity-data` | branch da V2.2 (derivada da V2.1); commits `b094a37`, `94d3d19`, `b4c4bf8`; **publicada** em `origin` — SHA remoto = local (`b4c4bf8`), sem `--force`, sem merge em `main` |
| Tag `v2-poc-sentinel2` | checkpoint imutável da PoC → `2e5b3ef` |
| Bundle de segurança | `..\SADEN_V2_1_RECOVERY_2026-11-11\saden-v2-1-start-2026-11-11.bundle` (2.435.845 B, SHA-256 `74727C33…B1274`, verify OK) e `..\SADEN_V2_2_RECOVERY_2026-11-11\saden-v2-2-start-2026-11-11.bundle` (3.449.452 B, SHA-256 `E5828389…2497`, verify OK) |
| Código V1 alterado | **nenhum**; mudanças só em `geospatial/` e `docs/` |
| `SADEN-TCC` | não tocado |

## 3. Fonte de dados (verificada em execução real)

| Item | Valor |
|---|---|
| Catálogo STAC | `https://earth-search.aws.element84.com/v1` (Earth Search / Element 84) |
| Coleção | `sentinel-2-c1-l2a` (Sentinel-2 Collection 1 Level-2A) |
| Autenticação | nenhuma (acesso público anônimo) |
| Custo | zero |
| Licença | STAC declara `proprietary`; Registry of Open Data on AWS declara acesso “free, full and open” — **as duas fontes registradas** |
| Ativos | `blue` (B02), `red` (B04), `nir` (B08), `swir16` (B11), `scl` |

Metadados reais de todos os assets: `scale = 0.0001`, `offset = -0.1`,
`nodata = 0`, `uint16` (contínuas) e `uint8` (SCL). Baselines observados:
**05.09** (2023), **05.10** e **05.11** (2024–2025). Baseline < 04.00 bloqueia
o processamento do item.

## 4. Geometrias (D42)

| Geometria | Bbox | Papel |
|---|---|---|
| Município (IBGE `5107925`, qualidade `maxima`, 2.689 vértices, válida) | `[-56.1167, -13.6661, -55.0851, -11.7216]` | limite oficial; 9.293,46 km² (geodésica) / 9.293,47 km² (EPSG:6933) |
| AOI técnica histórica (PoC) | `[-55.6509, -12.74385, -55.5509, -12.64385]` | reprodução da PoC — **0,51 km² fora do município** (99,58% dentro) |
| AOI de validação | `[-55.6309, -12.7339, -55.5709, -12.6739]` | 43,26 km², ~108.140 px a 20 m, dentro do município e da sobreposição dos tiles |
| AOI de mosaico | `[-55.70, -12.78, -55.50, -12.62]` | atravessa a fronteira dos footprints `21LXG`/`21LXF` |

Custo do município inteiro (estimativa, não executado): 23.233.677 px/banda a
20 m ≈ 92,9 MB float32 por banda/data (~465 MB para 5 bandas de uma data).

## 5. Checkpoint A — reprodução e auditoria

- Reexecução em `geospatial/artifacts/repro_poc/`, 4 cenas, **29,3 s**.
- Grade 547×557 px, `EPSG:32721`, transform `(20, 0, 646440, 0, −20, 8601880)`.
- Comparação com o manifesto anterior: **grade idêntica e delta 0,0** em
  pixels válidos, fração válida, mín/máx/média/mediana do NDVI.
- Auditoria radiométrica: metadado STAC e COG concordam em escala/offset;
  `rasterio.read()` devolve DN bruto (sem dupla aplicação); `uint16`, nodata 0.
- Manifesto: `geospatial/manifests/repro_20261111T181418Z.json`;
  comparação: `geospatial/reports/repro_comparison_20261111T181418Z.json`.

## 6. Checkpoint B — máscara SCL (D43)

AOI histórica (304.679 px/cena). Composição por classe nas 4 cenas: classe 4
de 72,57% (jun) a 23,49% (set); classe 5 de 27,22% a 76,36%; classe 2 com
106–144 px; classe 6 com 173–365 px; classe 7 com 121–169 px; nenhuma
ocorrência de 0/1/3/8/9/10/11.

Efeito do Perfil B (exclui 2 e 6): −317 a −471 px (0,10%–0,15%); Δ média NDVI
+0,00025 a +0,00107 (≤ +0,18% relativo); nenhum pixel B→A.

NDVI médio por classe (2025-06-09): 4 = 0,726 · 5 = 0,295 · 2 = 0,319 ·
**6 = −0,196** (mediana −0,288).

**Decisão:** Perfil A permanece na reprodução da PoC; **Perfil B é o padrão da
V2.1** (`config.V2_1_SCL_PROFILE`). Evidência: `manifests/scl_*.json`,
`reports/scl_class_stats_*.csv`, `previews/scl/*.png`.

## 7. Checkpoint C — geometria

Executado com sucesso: malha oficial validada, interseção da bbox histórica
quantificada (120,16 km² totais; 119,65 dentro; 0,51 fora), AOI de validação
contida no município, estimativas de custo registradas e mapa PNG gerado.
Artefatos: `manifests/geometry_*.json`, `artifacts/geometry/*.geojson`,
`previews/geometry/aoi_geometry.png`.

## 8. Checkpoint D — mosaico de dois tiles (D44)

Par real: `S2B_T21LXG_20230620T135711_L2A` + `S2B_T21LXF_20230620T135711_L2A`
(mesmo `datatake_id` `GS2B_20230620T135709_032840_N05.09`, baseline 05.09,
diferença temporal medida **14,53 s**). Grade única `EPSG:32721`, 20 m,
1.092×891 px, transform `(20, 0, 641100, 0, −20, 8604540)`.

Regra `first_valid_wins` (`21LXG > 21LXF`, sem média): 779.708 px do primário,
192.073 do secundário, 1.191 sem dado, 2.185 px de costura.

Diferença na sobreposição: NDVI |Δ| médio 0,00095, RMSE 0,00138,
correlação 0,99999; reflectâncias com |Δ| médio ≤ 0,00047.

## 9. Checkpoint E — série temporal 2023–2025 (D45)

AOI de validação (43,26 km²), grade 20 m `EPSG:32721` (329 × 334 px), tile
`MGRS-21LXG` em toda a série, Perfil B, 1 cena por mês.

**36 meses pesquisados → 34 observados, 2 lacunas** (`2023-01` e `2024-12`),
ambas por obstrução > 50% sobre a AOI (84,7% e 86,5% na melhor candidata) —
com cenas presentes no catálogo. Nenhum mês foi preenchido.

Baselines: 05.09 (2023), 05.10 (1º semestre/2024), 05.11 (2º semestre/2024 em
diante) — todos com `scale = 0.0001` e `offset = −0.1`: **sem quebra de
método**. Cobertura válida por mês: 72,25% a 100%. NDVI médio: 0,270
(2023-09) a 0,871 (2025-04).

Evidência do critério de seleção: a nuvem do tile e a obstrução sobre a AOI
divergem fortemente (2023-04: tile 65,23% de nuvem, AOI 3,16% obstruído;
2024-11: tile 73,87%, AOI 0,06%).

Série executada **duas vezes** com resultados idênticos (seleção
determinística).

Artefatos: `reports/timeseries_mensal_2023-01_2025-12.csv`,
`manifests/timeseries_20261111T182443Z.json`,
`previews/timeseries/series_2023-01_2025-12.png`,
`artifacts/timeseries/<mês>/*.tif` (não versionados).

## 10. Testes

| Suíte | Comando | Resultado |
|---|---|---|
| Geoespacial offline | `geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests -t geospatial` | **95/95 OK** |
| Externos (rede, opt-in) | `$env:SADEN_EXTERNAL_TESTS="1"; … -m unittest discover -s geospatial\tests_external -t geospatial` | **4/4 OK** (separados da suíte padrão) |
| V1 backend (regressão) | `cd backend; npm test` | 65/65 (validado na missão anterior; V1 intocada) |

A suíte padrão **não depende de internet**: todos os testes usam arrays e
GeoTIFFs sintéticos.

## 11. Ambiente

| Item | Versão |
|---|---|
| Python | 3.12.10 (Windows) |
| venv | `geospatial/.venv` (isolado, ignorado no Git) |
| pystac-client | 0.9.1 |
| rasterio | 1.4.3 (GDAL 3.9.3) |
| numpy | 2.5.4 |
| matplotlib | 3.11.2 |
| shapely | 2.1.2 |
| pyproj | 3.7.2 |
| certifi | 2026.10.23 |

Problemas reais encontrados e contornados:

1. `rasterio==1.5.2` (GDAL 3.12.2) **crashava** ao abrir COG remoto no Windows
   (`exit -1073740791`). Fixado em `1.4.3`.
2. GDAL/schannel recusa CA bundle em caminho com acento ("Área de Trabalho");
   `s2_poc/network.py` resolve. Sem isso: `UnicodeDecodeError` mascarado.
3. A API de malhas do IBGE responde gzip mesmo sem `Accept-Encoding`;
   descompressão explícita em `aoi.py` e `geometry.py`.
4. `rasterio 1.4.3` + `numpy 2.5` emite `DeprecationWarning` interno ao ler
   janelas; suprimido localmente em `read.py`.
5. `Client.get_item(id, collection=...)` **não existe** nesta versão do
   pystac-client (assinatura `get_item(id, recursive)`): a auditoria usa
   `collection.get_item(id)`.
6. Tiles adjacentes têm `datetime` distintos (~15 s) apesar do mesmo
   `datatake_id`: pareamento por timestamp exato não encontra pares (D44).

## 12. Pendências e próxima ação

1. **GitHub Release `v1-final`**: bloqueado por falta de autenticação `gh`
   (sem token; login por navegador proibido). Notas prontas em
   `docs/releases/v1-final.md`. Tag, branches e bundle já verificados.
2. **Push das branches**: **feito** — `origin/v2/geospatial-validation` (V2.1) e
   `origin/v2/agricultural-productivity-data` (V2.2) publicadas, SHA remoto =
   local, usando a autenticação já existente no Git; nenhum token impresso ou
   versionado.
3. **V2.2 (não iniciada)**: compatibilidade espacial/temporal de IBGE/SIDRA e
   CONAB com a AOI e com os indicadores Sentinel-2 — antes de qualquer
   modelagem.
4. Nada de UI/dashboard/endpoint novo, integração dos índices ao Ridge ou
   modelo de produtividade enquanto a V2.1 não for revisada.

## 13. Checkpoint V2.2 — base observada de produtividade (D46–D49)

Branch: `v2/agricultural-productivity-data` (derivada de `v2/geospatial-validation`).

| Fonte | Estado | Evidência |
|---|---|---|
| IBGE/SIDRA (PAM 5457) | **acessível** | 4.472 registros reais do município 5107925 (2013–2025), `data/raw/sidra/` versionado |
| CONAB (Boletim de Safras) | **acessível** (estadual) | 444 registros de MT, safras 23/24, 24/25 e 25/26; planilhas fora do Git (D48) |
| CONAB SIGS / API / dados.gov.br | **bloqueados** | DNS não resolve / HTTP 401 — registrados, não contornados |
| Município 5107925 | **confirmado** | API oficial: Sorriso/MT, região imediata Sorriso, intermediária Sinop |

Base normalizada: **4.916 registros** (IBGE 4.472 observados + CONAB 444
estimados), 26 campos, com valor e unidade originais preservados.
Qualidade: **0 erros, 19 avisos** (13 revisões entre boletins CONAB, 6
dupla contagem agregado × componente), 5.866 achados informativos.

Compatibilidade espacial (geometria real, `EPSG:6933`): AOI 43,26 km² =
**0,4654%** do município de Sorriso (9.293,47 km²) → **IBGE = B
(contextual)**, **CONAB = C (incompatível)**; nenhuma fonte oficial alcança a
classe A (propriedade/talhão).

Compatibilidade temporal: IBGE 2023–2025 (**n = 3** observações anuais),
CONAB safras 23/24–25/26, Sentinel-2 mensal com 2 lacunas reais (2023-01,
2024-12) preservadas. Sem calendário fenológico validado: nenhuma janela
de safra foi inventada.

Culturas-piloto: **soja e milho** (correspondência exata, com produção
municipal real); **algodão** condicionado (IBGE publica caroço, SADEN
referencia pluma); **café e trigo descartados** (produção municipal zero).

Testes: **137/137 offline** (95 da V2.1 + 42 novos) e **10/10 externos**
(opt-in). Relatório: `geospatial/reports/V2_2_PRODUCTIVITY_DATA_COMPATIBILITY.md`.

## 13. Checkpoint V2.3 — estudo exploratório municipal (D50–D53)

Branch: `v2/agricultural-productivity-exploratory` (derivada de
`v2/agricultural-productivity-data` / `775d57b`); bundle da V2.3 em
`..\SADEN_V2_3_RECOVERY_2026-11-11\saden-v2-3-start-2026-11-11.bundle`
(3.718.796 B, SHA-256 `C3449A62…5B69`, verify OK).

| Item | Estado | Evidência |
|---|---|---|
| Inventário histórico Sentinel-2 | DONE | C1: 954 assets 2017–2025, `scale=0.0001`/`offset=-0.1` uniformes; original: 1.733 itens 2017–2025; lacunas de ingestão da C1 (2017: 1 data; 2022: 5 datas) |
| Harmonização radiométrica | DONE | experimento pareado C1 × original em 6 datas (2018–2025): diferença de NDVI **0,0** e correlação **1,0** (D50) |
| Uso do solo na AOI | PARCIAL | MapBiomas **bloqueado** (download suspenso; via GEE); WorldCover (ESA) adquirido: **77,6%** (2020) e **81,2%** (2021) de lavoura na AOI (D51) |
| Calendário fenológico | BLOQUEADO | SISZARC/MAPA sem DNS; página de safras da CONAB sem arquivo; Embrapa 404 → agregação por ano civil, sem janelas inventadas (D52) |
| Rendimento-alvo | DONE | IBGE/PAM `rendimento_medio_kg_ha` (kg/ha) para soja (40124) e milho (40122), preservando valor/unidade originais |
| Portão estatístico | D53 | modelagem exploratória exige **≥ 9 pares anuais por cultura**; abaixo disso, apenas descrição e correlação exploratória |
| Série histórica | DONE | **101/108 meses** observados (9 anos completos: 2017–2025); perfis C1 (69) e original (32); baselines 00.01–05.11 |
| Uso do solo | PARCIAL | MapBiomas **bloqueado** (download suspenso; via GEE); WorldCover (ESA): **77,6% (2020) / 81,2% (2021)** de lavoura na AOI (D51) |
| Conjunto pareado | DONE | 26 registros (13 anos × 2 culturas); **18 pareados e utilizáveis** (2017–2025, n = 9 por cultura) |
| Correlação exploratória | DONE | soja: r = 0,432, ρ = 0,134, **p = 0,246**; milho: r = 0,200, ρ = 0,067, **p = 0,610** (permutação, 5.000×) |
| Experimento temporal | DONE | walk-forward (4 previsões/modelo): regressão com NDVI **não** supera os baselines (soja MAE 368 vs 254 kg/ha; milho 955 vs 684) |
| Veredito | **CAMINHO B** | estudo executável com ressalvas; **sem** modelo preditivo validado e **sem** base para integrar ao Ridge |
| Testes | DONE | **165/165** offline (70 novos da V2.3) |

## 14. Checkpoint V2.4 — escala espacial, calendário ZARC e referências agrícolas (D54–D57)

Branch: `v2/agricultural-scale-harmonization` (derivada de
`v2/agricultural-productivity-exploratory` / `3ff7104`).

| Item | Estado | Evidência |
|---|---|---|
| Calendário oficial | DONE | ZARC/MAPA (`dados.agricultura.gov.br`, CC-BY): **11 safras**, **1.408 registros de Sorriso**, 23 culturas, com decêndios de risco e portaria de origem (D54) |
| Safra × ano PAM | DONE | `zarc_pam_year_relation.csv` (148 combinações) — regra **derivada** (colheita no ano civil seguinte), alternativa e confiança declaradas |
| Produtividade submunicipal | NEGATIVO (com evidência) | CONAB SUTIN: polígonos submunicipais **sem** campo de produtividade; MapBiomas GCS 403; IMEA 500; SIGS/INCRA sem DNS (D56) |
| Referência submunicipal de área | DONE | CONAB SUTIN `MT_SOJA_2021`: 17 feições em Sorriso com `AREA_HA` |
| Escala municipal do indicador | DONE | grade 5.878 × 11.008 px (20 m), 16 blocos, mosaico de dois tiles, recorte pelo polígono; ~1,04 GB/data (D57) |
| Testes | DONE | **181/181** offline (16 novos da V2.4) |

## 15. Comandos de retomada

```powershell
git switch v2/agricultural-scale-harmonization
git switch v2/agricultural-productivity-exploratory
geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests -t geospatial
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py geometry
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py mosaic
geospatial\.venv\Scripts\python.exe geospatial\run_validation.py timeseries --start 2023-01 --end 2025-12

# V2.2 — base observada de produtividade (rede)
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py inventory
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py acquire --year-start 2013 --year-end 2025 --conab-safras "2024/25,2025/26"
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py normalize
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py validate
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py compat

# V2.3 — estudo exploratório municipal
geospatial\.venv\Scripts\python.exe geospatial\run_historical.py radiometry
geospatial\.venv\Scripts\python.exe geospatial\run_historical.py series --start 2017-01 --end 2025-12
geospatial\.venv\Scripts\python.exe geospatial\run_historical.py landuse --years 2020 2021
geospatial\.venv\Scripts\python.exe geospatial\run_historical.py study

# V2.4 — escala espacial e calendário
geospatial\.venv\Scripts\python.exe geospatial\run_scale.py zarc
geospatial\.venv\Scripts\python.exe geospatial\run_scale.py relation
geospatial\.venv\Scripts\python.exe geospatial\run_scale.py sutin --uf MT
geospatial\.venv\Scripts\python.exe geospatial\run_scale.py municipal --month 03 --blocks 16
geospatial\.venv\Scripts\python.exe geospatial\run_scale.py mapbiomas
```

Antes de qualquer coisa em nova sessão: ler este arquivo,
`docs/AI_CONTEXT_RECOVERY.md`, `docs/V2_1_VALIDATION_REPORT.md` e as decisões
D42–D45 em `docs/DECISIONS.md`.
