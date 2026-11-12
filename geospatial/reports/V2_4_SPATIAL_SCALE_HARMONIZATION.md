# SADEN V2.4 — Harmonização de escala espacial: do indicador da AOI para o indicador municipal

> Branch: `v2/agricultural-scale-harmonization`. Execução: 2026-11-12.
> Artefatos: `geospatial/data/processed/municipal_ndvi_agriculture.csv`,
> `geospatial/data/manifests/municipal_ndvi_report.json`,
> `geospatial/data/manifests/municipal_operation_estimate.json`.

## 1. Problema

Na V2.3 o alvo é o **rendimento médio municipal** (IBGE/PAM, 9.293,47 km²) e o
indicador geoespacial era o NDVI de uma **AOI de 43,26 km²** (0,4654% do
município). Essa incompatibilidade de escala é o obstáculo determinante (D47):
a estatística municipal não descreve a AOI, e atribuí-la à AOI é proibido.

A alternativa metodológica adotada (D57) é **mudar a escala do indicador** para
a unidade do alvo — sem criar produtividade observada por pixel.

## 2. Geometria de referência

| Item | Valor |
|---|---|
| Município | Sorriso-MT, IBGE `5107925` (malha oficial IBGE, qualidade `maxima`) |
| Área do polígono | 9.293,47 km² (`EPSG:6933`) |
| Bbox do polígono | `[-56.1167, -13.6661, -55.0851, -11.7216]` |
| Área da bbox | ~24.400 km² (2,6× o polígono — o município é alongado na diagonal) |
| Grade de trabalho | `EPSG:32721`, 20 m, **5.878 × 11.008 px** (64,7 M px na bbox) |
| Recorte territorial | centros de célula **dentro do polígono** (não da bbox) |

**FATO.** A divergência de área entre a AOI da V2.2 (43,26 km²) e a da V2.3
(43,36 km²) vem do **procedimento de medição**, não de geometria diferente: a
V2.2 mediu a área da AOI com projeção de área igual e a V2.3 mediu a área
*coberta pela janela raster* do WorldCover (leitura por janela, que inclui
pixels de borda). As geometrias e as janelas são as mesmas.

## 3. Máscara agrícola

| Fonte | Classe | Uso |
|---|---|---|
| ESA WorldCover 10 m (v200/2020, v100/2021) | **40 = Cropland** | máscara agrícola (D51) |
| WorldCover 10 m | 10/20/30/50/60/70/80/90/95/100 | demais classes, preservadas no relatório por bloco |
| CONAB SUTIN `MT_SOJA_2021` | polígonos de soja (17 feições em Sorriso) | referência **de área** por cultura (2021) — sem produtividade |

**FATO — validação da máscara (método por centros de célula × contagem de
área):**

| Recorte | Classe 40 por contagem de área | Máscara (centros) |
|---|---|---|
| AOI 43,26 km² (V2.3) | 77,63% | 76,38% |
| Bloco municipal 1 (norte) | 61,3% | 61,22% |
| Bloco municipal 10 (sul) | 73,7% | 73,82% |

**INTERPRETAÇÃO.** As duas formas de contagem concordam dentro de ~1,3 p.p. na
AOI e ~0,1 p.p. nos blocos — a máscara é consistente com a contagem de área
usada na V2.3.

**LIMITAÇÃO.** A máscara existe apenas para **2020 e 2021** (WorldCover). Para
2017–2019 e 2022–2025 o mesmo shapefile é reaplicado, o que é uma aproximação
declarada: as classes de uso do solo mudam no tempo (expansão agrícola,
colheita, pousio). O MapBiomas (2017–2025) seria a correção — hoje bloqueado
(D56).

## 4. Estratégia de processamento (estimativa antes da execução)

| Item | Valor |
|---|---|
| Pixels da grade (20 m) | 64,7 M |
| Pixels da fonte (10 m) por banda | ~259 M |
| Download por data (B04 + B08 + SCL) | ~1,04 GB |
| Total para 9 datas | ~9,3 GB |
| Memória | limitada ao bloco (nunca o município inteiro) |
| Blocos | 16 (4 × 4) |
| Tiles | **dois**: `21LXG` (norte) e `21LXF` (sul) — mosaico `first_valid_wins` (D44) |

**FATO.** O município de Sorriso **atravessa os dois tiles** MGRS; processar só
`21LXG` deixaria a metade sul do município sem dado. O mosaico de dois tiles da
V2.1 (D44) é reaplicado, com a mesma regra determinística.

**FATO.** O raster municipal **não é materializado**: cada bloco é lido,
processado e descartado; os acumuladores (soma, contagem, soma de quadrados e
histograma de 2.001 bins) são combinados ao final, o que dá média, desvio e
quantis p05/p25/p50/p75/p95 **sem** armazenar o raster.

## 5. Indicadores produzidos

| Indicador | Nome normalizado | Unidade territorial | Identificação de cultura |
|---|---|---|---|
| A — AOI inteira | `ndvi_aoi_all` (V2.3) | AOI 43,26 km² (sub-região) | nenhuma |
| B — Área agrícola municipal | **`ndvi_all_cropland`** | **município (9.293 km²)** | nenhuma (classe 40) |
| C — Lavoura temporária municipal | `ndvi_temporary_cropland` | município | só com máscara que separe temporária/perene (MapBiomas) — **pendente** |
| D — Soja (CONAB SUTIN 2021) | `ndvi_soja_sutin_2021` | sub-região (feições) | **soja, 2021** (área, sem produtividade) |

**FATO.** O nome **não** é `ndvi_soja` nem `ndvi_milho`: WorldCover e SCL não
identificam cultura, e a única fonte com identificação de cultura (SUTIN)
cobre soja/MT apenas em 2021 e não traz produtividade (D56).

## 6. Resultado (piloto verificado — 2017-03)

| Métrica | Valor |
|---|---|
| Data / item | 2017-03 · `S2A_21LXG_20170308_0_L2A` (baseline 00.01, perfil `original_pre_04_no_offset`) |
| Pixels agrícolas válidos (20 m) | **11.999.215** |
| Área agrícola equivalente | ~4.800 km² (52% do município) |
| NDVI médio | **0,5668** |
| NDVI mediana | 0,6237 |
| Desvio-padrão | 0,2601 |
| Quantis | p05 0,1629 · p25 0,3018 · p50 0,6237 · p75 0,8156 · p95 0,8846 |
| Blocos | 16 |

**FATO — comparação AOI × município (março/2017):**

| Recorte | NDVI médio | Cobertura |
|---|---|---|
| AOI 43,26 km² (V2.3, série histórica) | 0,5282 | 11/12 meses do ano |
| Área agrícola municipal (V2.4) | 0,5668 | 12,0 M pixels (20 m) |

**INTERPRETAÇÃO.** A AOI é **um pouco menos verde** que a média agrícola
municipal em março/2017 (Δ ≈ −0,039). A diferença é pequena e comparável à
variação entre meses, o que indica **representatividade razoável** da AOI como
sub-região agrícola do município — mas com uma ressalva: a AOI ocupa 43 km² de
9.293 km² e o indicador municipal agrega toda a área agrícola, incluindo
áreas de pastagem e solo exposto dentro das fazendas.

**LIMITAÇÃO.** Uma diferença de ~0,04 de NDVI entre uma amostra de 0,47% da
área e a média municipal **não** valida produtividade: os dois números
medem coisas diferentes (vegetação por pixel × área agrícola). A comparação serve
apenas para caracterizar a representatividade espacial da AOI.

## 7. Mosaico de referência espacial × agronômica (D55)

A V2.4 mantém **duas tabelas distintas**:

* **Referência espacial** — geometrias (município, AOI, feições SUTIN), máscaras
  de uso do solo, pixels e indicadores de vegetação
  (`municipal_ndvi_agriculture.csv`, `conab_sutin/*.csv|geojson`);
* **Referência agronômica** — cultura, safra, janelas do ZARC, portarias e
  rendimento oficial do IBGE (`zarc_planting_windows.csv`,
  `zarc_pam_year_relation.csv`, `productivity_observations.csv`).

A tabela pareada **não** foi construída nesta etapa: seria necessário decidir
qual janela do ZARC (12 combinações por safra e cultura para soja) entra no
cálculo do indicador — decisão metodológica que cabe à próxima fase, com o
calendário agora disponível.

## 8. Limitações

1. Máscara agrícola só para 2020–2021 (WorldCover); reaplicada nos demais anos.
2. O indicador municipal usa **uma data por ano** (março, o primeiro mês com
   9/9 anos de cobertura) — não é uma média anual.
3. A máscara de lavoura **temporária** (vs perene) depende do MapBiomas,
   bloqueado.
4. A área agrícola da máscara (WorldCover 10 m) é reamostrada para 20 m por
   centros —o sistema é determinístico, mas perde detalhe.
5. O download de ~9,3 GB para 9 datas limita a expansão a séries anuais
   completas sem janela de processamento ampliada.

## 9. Como reproduzir

```powershell
geospatial\.venv\Scripts\python.exe geospatial\run_scale.py municipal --month 03 --blocks 16 --mask-years 2020 2021
```

O CSV `data/processed/municipal_ndvi_agriculture.csv` é escrito **a cada data
concluída** (persistência incremental), e o manifesto
`data/manifests/municipal_ndvi_report.json` registra grade, blocos, estimativa
de custo, máscara usada e limitações.
