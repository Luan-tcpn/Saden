# SADEN — Adjudicação das fontes climáticas (NASA POWER × INMET)

**Data:** 2026-11-14
**Código:** `tools/audit_climate_sources.py`, `tools/validate_source_contract.py`,
`geospatial/agroclimate/contracts.py`
**Manifestos:** `climate_source_adjudication.json`, `source_contract_validation.json`
**Tabelas:** `docs/data_quality/climate/`

---

## 1. O que existe no arquivo

`climate_daily.csv` — 35 colunas, 6.552.547 linhas, 1.077 MB.

| fonte | `source_type` | linhas | municípios |
|---|---|---:|---:|
| NASA-POWER | `reanalysis` | 5.925.166 | 1.622 |
| INMET | `station_observation` | **627.381** | **215** |

As duas fontes ocupam **a mesma chave** `(ibge_code, date)` em 627.381 pares.
Não são duplicatas: os valores diferem.

## 2. Natureza da diferença

Não é erro de gravação nem duplicação de carga. São **produtos distintos**:

| aspecto | NASA-POWER | INMET |
|---|---|---|
| natureza | reanálise em grade (~0,5°), interpolada ao centróide | observação de estação automática |
| cobertura | 1.622 municípios, integral | 215 municípios, mediana de 3.557 de 3.653 dias |
| localização física | centróide do município | estação **dentro** do município (`inside_municipality`) |
| distância estação–centróide | — | mediana 13,5 km · p90 34,8 km · máx. 95,7 km |
| agregação diária | dia solar do produto | 24 observações horárias (`*_n_obs = 24`), radiação com 13 |
| campos exclusivos | solo (`solo_temp_0_7_c`, `solo_temp_7_28_c`) | estação, vento máx./direção, contagem de observações |

**Consequência:** não existe "o mesmo dado em duas versões". Existe uma grade
com cobertura completa e uma amostra de estações com cobertura parcial. Tratá-las
como equivalentes seria um erro de definição, e foi o que o contrato passou a
impedir.

## 3. Comparação nos 627.381 pares

Limites de divergência definidos por **critério agronômico**, não estatístico —
a diferença a partir da qual a decisão de janela, graus-dia ou balanço mudaria
de forma material.

| variável | n | viés (NASA−INMET) | MAE | RMSE | r | % acima do limite | limite |
|---|---:|---:|---:|---:|---:|---:|---:|
| precipitação | 489.703 | −0,291 mm | **3,095 mm** | 8,033 | 0,644 | **16,9%** | 5 mm |
| temperatura média | 536.930 | +0,400 °C | 1,421 | 1,857 | **0,931** | 10,1% | 3 °C |
| temperatura máxima | 536.421 | +0,245 °C | 1,948 | 2,493 | 0,899 | **21,1%** | 3 °C |
| temperatura mínima | 536.415 | +0,082 °C | 1,567 | 2,108 | 0,907 | 13,2% | 3 °C |
| umidade relativa | 525.422 | −0,022 pp | 7,668 | 10,135 | 0,796 | 5,4% | 20 pp |
| vento a 2 m | 521.081 | **+2,526 km/h** | 4,500 | 5,711 | **0,409** | 7,8% | 10 km/h |
| radiação | 530.287 | +1,174 MJ/m² | 2,449 | 4,296 | 0,817 | 4,8% | 8 MJ/m² |

**Leitura:** o **viés é pequeno** (0,4 °C na temperatura média; −0,3 mm na
precipitação diária) e a **correlação é alta** para temperatura e radiação. O que
é grande é o **erro aleatório**: MAE de 3,1 mm/dia na chuva e ~1,5 °C nas
temperaturas. O vento é o pior caso (r = 0,409, viés +2,5 km/h) — estação a 10 m
convertida, rugosidade local e exposição explicam parte disso.

**Isso não invalida nenhuma das fontes**: quantifica a incerteza da exposição.
Um erro de 1,4 °C/dia, agregado em janela de 4–8 meses, tende a se cancelar
(erro-padrão ∝ 1/√n) — o que a comparação **não** faz é provar que a agregação
ancance o valor verdadeiro; isso exigiria validação externa.

## 4. As 2.020 linhas INMET "utilizáveis"

| status | NASA-POWER | INMET |
|---|---:|---:|
| `paired_usable` | 19.402 | **2.020** |
| `excluded` | 16.492 | 3.076 |

**Rastreamento completo.** As 2.020 linhas são 9,43% das 21.422 linhas
`paired_usable` do painel base. Foram investigadas por análise estática (AST) de
todo o código e por auditoria de runtime:

| consumidor | filtra a fonte? | veredito |
|---|---|---|
| `run_agroclimate.py` (V2.6) | sim — `--climate-source` com padrão **NASA-POWER** | não contaminou |
| `run_robustness.py` (V2.7) | sim — `prepare(rows, climate_source="NASA-POWER")` | não contaminou |
| `v30_recalculate_panel.py`, `v30_association_cad.py`, `v30_models_cad.py` | sim | não contaminou |
| `v31_rebuild_panel.py`, `v35_build_windows.py` | sim (status **e** fonte) | não contaminou |
| `s27_phenology_window.py`, `s28_cycle_stratification.py`, `s29_*`, `v34_*` | sim | não contaminou |
| `s27_panel_coverage.py` | **não** — contador de cobertura | **waiver documentado** |

**Resultado da varredura:** 72 arquivos, **28 funções com guarda de fonte,
0 sem guarda** (1 exceção documentada). Nenhuma análise consumiu as 2.020 linhas.

**Onde estava o risco real:** `analysis.prepare_rows` filtrava só por `status`.
Nenhum chamador produzia amostra mista (ambos pré-filtram a fonte), mas a regra
não era verificável. Passou a **falhar alto** quando recebe fontes misturadas sem
declaração (D128).

## 5. Decisão: fonte canônica por variável

| variável | fonte canônica | motivo |
|---|---|---|
| precipitação | **NASA-POWER** | cobertura integral; INMET cobre 215/1.622 municípios e tem MAE de 3,1 mm/dia |
| temperatura (máx., mín., média) | **NASA-POWER** | cobertura integral; viés de 0,4 °C com r = 0,93 |
| umidade relativa | **NASA-POWER** | cobertura integral |
| vento a 2 m | **NASA-POWER** | INMET tem r = 0,409 e viés de +2,5 km/h; pior concordância do conjunto |
| radiação | **NASA-POWER** | INMET tem 13 de 24 horas de observação em média |
| solo (`solo_temp_*`) | **NASA-POWER** | exclusivo da reanálise |
| validação cruzada | **INMET (auxiliar)** | usada só como referência de comparação, nunca em modelo |

**Por que não INMET como principal:** a cobertura é 215 de 1.622 municípios
(13,3%) e sem estação dentro do município não há observação. Usar INMET mudaria
a população do estudo, não só a fonte — e criaria um painel com cobertura
geográfica definida pela rede de estações.

**O que a INMET passa a ser:** a única referência independente disponível para
medir a incerteza da reanálise. Isso tem valor próprio e está registrado como
próximo passo (validar a agregação de janela, não só o diário).

## 6. Contrato explícito

`geospatial/agroclimate/contracts.py` define, de forma executável:

| item | definição |
|---|---|
| `CANONICAL_CLIMATE_SOURCE` | `NASA-POWER` |
| `AUXILIARY_CLIMATE_SOURCE` | `INMET` |
| `is_canonical_row(row)` | status `paired_usable` **e** fonte `NASA-POWER` |
| `select_canonical(rows)` | filtro + contagem de descarte por motivo |
| `assert_source_declared(source)` | falha alto se o consumidor não declara a fonte |
| `audit_mixture(rows)` | detecta linhas utilizáveis de fonte não canônica |

O pipeline canônico declara `rules.require_climate_source` na configuração e
**conta** o descarte (`discarded_other_source_rows`). Nenhuma seleção depende da
ordem do arquivo.

## 7. Preservação dos dados originais

Nada foi apagado. `climate_daily.csv` permanece com as duas fontes; os derivados
não mudaram. A decisão é de **seleção declarada**, não de edição de dados.

## 8. Diferenças que permanecem sem explicação

1. **Vento.** r = 0,409 é baixo demais para ser só diferença de altura de
   medição. Parte pode ser hora da observação vs média diária; não foi
   investigado a fundo.
2. **Precipitação em 16,9% dos dias acima de 5 mm.** Chuva convectiva é
   localizada: a estação mede o ponto, a grade mede a célula. Nenhuma das duas é
   "a chuva do município".
3. **Temperatura máxima com 21,1% acima de 3 °C.** A reanálise suaviza extremos
   por construção; a estação os registra. Isso afeta `extreme_heat_days` e deve
   entrar na leitura de qualquer resultado que use esse indicador.

## 9. Classificação

| item | classificação |
|---|---|
| coexistência das duas fontes | **investigada** |
| pares conflitantes | **medidos** (627.381, 7 variáveis) |
| fonte canônica por variável | **decidida e justificada** |
| 2.020 linhas INMET | **rastreadas** — nenhuma análise as consumiu |
| contrato de fonte | **implementado e testado** (0 funções sem guarda) |
| dados originais | **preservados** |
| validação da agregação de janela contra estação | **não feita** (registrada) |
