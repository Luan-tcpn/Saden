# SADEN V2.5 — Pareamento sazonal, integração espacial e reavaliação estatística da produtividade agrícola

> Branch: `v2/seasonal-spatial-pairing`. Execução: 2026-11-12.
> Artefatos: `geospatial/data/processed/municipal_ndvi_monthly.csv`,
> `geospatial/data/processed/municipal_seasonal_productivity_dataset.csv`,
> `geospatial/data/manifests/reevaluation.json`,
> `geospatial/data/manifests/reevaluation_summary.csv`,
> `geospatial/data/manifests/municipal_ndvi_series.json`,
> `geospatial/data/manifests/seasonal_pairing_manifest.json`.
> Decisões: D58–D65 em `docs/DECISIONS.md`.

---

## 1. Estado inicial

**FATO.** A V2.4 encerrou com a base pronta, mas **sem a série municipal
completa**: o único registro verificado era o piloto de março de 2017
(11.999.215 pixels agrícolas, NDVI médio 0,5668, mediana 0,6237, P05 0,1629,
P95 0,8846; NDVI da AOI 0,5282). A V2.4 deixou o piloto
`geospatial/data/processed/municipal_ndvi_agriculture.csv` com 5 registros
mensais e manifesto próprio.

**FATO.** O pareamento V2.3 existia apenas sobre a **AOI** (43,246 km² =
0,4655% do município) e com agregação por **ano civil** — declaradamente sem
calendário validado. A incompatibilidade de escala (D47) era, portanto, o
bloqueio determinante.

**FATO.** O ZARC estava adquirido e normalizado: 1.408 registros de Sorriso,
11 safras (2016/17 a 2026/27), 23 culturas, com risco por decêndio, solo,
ciclo e portaria de origem. A base de relação safra↔ano PAM tinha 148
combinações, **derivadas** e não verificadas.

**FATO.** Não existe produtividade submunicipal pública (D56, reconfirmado na
V2.4): MapBiomas retorna 403 no GCS e exige conta no GEE; a CONAB publica
polígonos de cultura por município com **área** e **sem produtividade**.

---

## 2. Série municipal concluída

**FATO.** A série municipal mensal foi concluída para os **47 meses** das
janelas agrícolas presentes na série de referência (101 de 108 meses
observados na AOI; 47 de 54 meses candidatos — jan/fev/set/out/nov/dez de
2017–2025). Os 7 meses ausentes são os que a série da V2.3 classificou como
`all_candidates_exceed_max_obstruction` (2017-02, 2018-12, 2019-11, 2021-02,
2021-12, 2023-01, 2024-12) — **não foram inventados nem interpolados**.

**FATO.** Entregável: `municipal_ndvi_monthly.csv`, 188 linhas = 47 meses ×
4 variantes de máscara. Cada linha registra mês, ano, `item_id`, catálogo,
baseline, **perfil radiométrico**, tiles usados, variante e ano da máscara,
pixels agrícolas, pixels válidos, **cobertura válida**, NDVI médio, mediana,
desvio-padrão, P05, P95, fração obstruída, nº de cenas, nº de blocos e o
manifesto de origem.

**FATO.** Cobertura espacial (máscara `stable`, 12.498.721 pixels de 20 m =
4.999,5 km²):

| Variante | Pixels (20 m) | Área | Cobertura média da série |
|---|---:|---:|---:|
| `wc2020` | 12.783.916 | 5.113,6 km² | 0,704 |
| `wc2021` | 12.831.858 | 5.132,7 km² | 0,704 |
| **`stable`** (principal) | **12.498.721** | **4.999,5 km²** | **0,704** |
| `broad` | 13.117.053 | 5.246,8 km² | 0,704 |

**FATO.** Distribuição da cobertura válida mensal (`stable`): 4 meses abaixo
de 0,50; 5 entre 0,50 e 0,70; 11 entre 0,70 e 0,90; 8 iguais ou acima de
0,90. Os meses de **novembro** são sistematicamente os piores (2017-11: 0,430;
2018-11: 0,368; 2021-11: 0,443; 2023-11: 0,508; 2024-11: 0,449) — é a
estação de plantio com maior nuvem no Brasil Central.

**FATO.** Cobertura de tiles: **todos** os 47 meses usaram os dois tiles
(`MGRS-21LXG` e `MGRS-21LXF`), com mosaico `first_valid_wins` (D44). O tile
21LXF é lido apenas nos blocos abaixo de −12,657° de latitude, evitando
leitura fora do footprint.

**FATO.** Radiometria: 60 registros com perfil `original_pre_04_no_offset` e
52 com `C1_harmonized`, cada linha identificada — nenhuma mistura
silenciosa de perfis. A cena principal de cada mês é o **item exato** auditado
na série de referência da V2.3 (busca por `item_id`); o tile complementar é
procurado na **mesma data** e com o **mesmo índice de reprocessamento**.

**INTERPRETAÇÃO.** O perfil radiométrico herdado da V2.3 foi preservado
integralmente: a série municipal usa exatamente as mesmas cenas e os mesmos
offsets da série cuja equivalência numérica já fora demonstrada na V2.1.

**FATO (reprodutibilidade).** A segunda execução do mecanismo incremental
produziu **SHA-256 idêntico** (`AEF4D4DD88BB680BA3665DB2D3CC4F80462AB02881B6B4EA926E3F63CD0B2B5A`),
188 linhas e **zero duplicatas** de (mês, variante). O processamento paralelo
não altera o resultado numérico (D65).

**LIMITAÇÃO.** A série cobre **apenas as janelas agrícolas**, e não os 101
meses observados. Meses de março–agosto não são necessários para nenhuma das
janelas ZARC e permaneceram por processar — o mecanismo é retomável
(`run_scale.py municipal-series`).

---

## 3. Auditoria da máscara

**FATO.** O ESA WorldCover publica mapas anuais apenas de **2020** e **2021**.
A V2.4 aplicou a máscara de 2020 a todos os anos. A V2.5 derivou **quatro
variantes da mesma leitura** (uma por ano), sem novo download:

* `wc2020` — cropland (classe 40) de 2020;
* `wc2021` — cropland (classe 40) de 2021;
* `stable` — **interseção** 2020 ∩ 2021 (análise principal);
* `broad` — **união** 2020 ∪ 2021.

**FATO.** A interseção `stable` remove 285.195 pixels (114,1 km²) da máscara
de 2020 e remove 333.137 pixels (133,3 km²) da de 2021 — ou seja, ~2,2% da
área classificada como lavoura em um dos anos não é lavoura no outro. A
variação anual do uso do solo é, portanto, **pequena mas real**, e a máscara
`stable` é a opção conservadora para uma análise retrospectiva.

**FATO.** Correção de engenharia: `read_worldcover_block` ajustava o
`transform` ao **dataset inteiro**, e não à **janela recortada** — o
mapeamento célula→pixel do WorldCover errava e as máscaras saíam **vazias**
(o que zerava todas as estatísticas). O transform passou a ser o da janela, e a
leitura passou a ser repetida quando o servidor devolve janela parcial.

**FATO.** O recorte usa centros de célula do WorldCover projetados na grade
de 20 m, com o critério de ≥ 50% de lavoura por célula — o mesmo método
validado contra contagem de área na V2.4.

**LIMITAÇÃO (mask_retrospective).** Para 2017–2019 e 2022–2025 a máscara é
**proxy espacial retrospectivo**: não há mapa anual de uso do solo. Todo
registro do conjunto pareado carrega `mask_year` e a marca
`mask_retrospective` quando o ano da cena difere do ano do mapa. As linhas
com `mask_year` = 2020/2021 **não** significam que os pixels eram agrícolas
naquele ano — significam que o mapa de 2020/2021 os classificou como tal.

---

## 4. Limitações temporais

**FATO.** Quatro correções metodológicas foram feitas na camada de janelas do
ZARC (`agri/season.py`), sem alterar `zarc_planting_windows.csv`:

1. **Risco textual.** O campo `decendios_com_risco` guarda rótulos
   (`muito_baixo`/`baixo`/`medio`/`alto`), não códigos numéricos. A leitura
   ingênua produzia janelas **vazias**.
2. **Âncora de ano.** Os decêndios 1–12 (jan–abr) pertencem ao **segundo**
   ano da safra; os decêndios 13–36 (mai–dez) ao **primeiro**.
3. **Regra oficial de decêndios.** Três decêndios por mês (1–10, 11–20,
   21–último), com fevereiro de 28/29 dias — antes a conversão era linear
   (10 dias).
4. **Janela recomendada = risco ≤ 20%** (muito baixo ou baixo), que é o
   critério oficial do MAPA.

**FATO (critério de verificação).** A âncora é validável por um critério
externo e objetivo: **a portaria que publica a recomendação tem de preceder o
início da janela recomendada**. Com a âncora antiga (tudo em `SafraIni`) há
**165 violações** nas culturas-piloto (soja 2022/23 em diante; milho 2ª safra em
todas as safras); com a âncora corrigida há **zero**. Exemplo: a portaria da
milho 2ª safra 2016/17 é de 09-12-2016 e sua janela é de janeiro a fevereiro —
 logo, de **2017**, não de 2016.

**INTERPRETAÇÃO.** A correção desloca a janela do milho 2ª safra em um ano e
alinha a janela ZARC ao ano de colheita da PAM — o que a V2.4 já fazia na
relação safra→PAM, mas **não** na data da janela. Era uma inconsistência
interna real do conjunto.

**FATO.** O número de registros, safras, culturas e portarias **não** mudou:
1.408 registros, 11 safras, 23 culturas. Nenhuma linha foi descartada.

**LIMITAÇÃO.** O ZARC é **recomendação de risco**, não observação de plantio:
nenhuma data de plantio é afirmada. A correspondência com o ano de colheita
da PAM é **derivada** (grau de confiança `media_alta` para soja, `media` para
milho), com a alternativa registrada em cada linha.

---

## 5. ZARC — inventário das janelas de Sorriso

**FATO.** 1.408 registros, 23 culturas, 11 safras, portaria de origem em
100% deles. As três culturas-piloto e suas janelas recomendadas (risco ≤ 20%):

| Cultura | Safras | Combinações por safra | Janelas distintas por safra | Meses cobertos |
|---|---:|---:|---:|---|
| Soja | 2017/18 a 2026/27 | 9 a 18 | 1 a 5 | out–dez (2017/18–2021/22); out–fev (2022/23–2023/24); out–jan (2024/25–2026/27) |
| Milho 1ª | 2017/18 a 2026/27 | 9 a 18 | 2 a 3 | set–dez (2017/18–2019/20); out–dez (2020/21–2026/27) |
| Milho 2ª | 2016/17 a 2026/27 | 6 a 12 | 4 a 5 | jan–fev |

**FATO.** A variação entre janelas **é real e vem do solo e do ciclo**: no
milho 2017/18, o solo 1 dá decêndios 28–36 e o solo 3 dá 27–36. Nenhuma
combinação foi descartada por arbitragem: a análise principal usa a **modal**
(mais combinações oficiais), e as demais permanecem na base como cenários.

**FATO.** A janela da soja **muda de tamanho** ao longo da série: out–dez
(2017/18–2021/22) → out–fev (2022/23–2023/24) → out–jan (2024/25–2026/27).
As safras 2022/23 em diante têm **duas** janelas oficiais por combinação de
solo (a "cauda" de janeiro/fevereiro entra no conjunto modal a partir de
2024/25). Isso é um efeito da portaria, não uma escolha do analista.

**LIMITAÇÃO.** O ZARC é municipal e **não** distingue talhões: a janela
recomendada não é a janela efetivamente plantada, e as condições locais de
solo (1, 2, 3) e de ciclo (20, 21, 22) não estão identificadas para os
produtores de Sorriso — por isso o uso da janela modal como regra principal
é uma **aproximação declarada**, e não uma descrição da lavoura.

---

## 6. Metodologia das janelas

**Protocolo fixado antes de ver qualquer resultado** (D61, D63):

| Elemento | Escolha | Justificativa |
|---|---|---|
| Fonte | ZARC/MAPA, tábua de risco | único calendário oficial disponível |
| Nível de risco | ≤ 20% (muito baixo ou baixo) | critério oficial do MAPA; não escolhido por correlação |
| Combinações | todas preservadas; usa-se a **modal** | não se descarta variação oficial por conveniência |
| Janela por safra | datas absolutas `YYYY-MM` | evita deslocamentos de ano |
| Indicador 1 | NDVI médio da **janela de plantio** | comportamento espectral durante o período recomendado |
| Indicador 2 | — | **não construído**: não há duração de ciclo oficial por cultivar em Sorriso |
| Indicador 3 | — | **não construído**: exigiria identificação de cultura por produto |
| Indicador 4 | NDVI do **ano civil** | mantido como referência da V2.3 |

**FATO.** O indicador sazonal é **genérico**: `ndvi_all_cropland`
(`ndvi_mean` no conjunto pareado). Não há `ndvi_soja` nem `ndvi_milho` — a
máscara é de toda a área agrícola do município, sem identificação de cultura
(D49). Os polígonos do SUTIN (17 feições de soja em 2021) **não** foram usados
como máscara: só cobrem 2021 e são um subconjunto do município.

**LIMITAÇÃO.** Uma janela de semeadura **não** é uma janela de desenvolvimento
vegetativo. Sem duração de ciclo oficial por cultivar para Sorriso, o
indicador mede o estado espectral da área durante o período recomendado, e
**não** a biomassa acumulada da cultura. Essa é a limitação mais importante
do estudo.

---

## 7. Pareamento safra ↔ PAM

**FATO.** A regra principal é: **ano PAM = ano de colheita = segundo ano da
safra** (`safra_fin`), para as três culturas. Com a âncora corrigida, a
janela do milho 2ª safra (jan–fev) cai no mesmo ano civil do seu ano de
colheita — as três janelas ficam coerentes com o alvo.

| Safra | Janela (datas absolutas) | Ano PAM | Rendimento (kg/ha) |
|---|---|---:|---:|
| Soja 2017/18 | 2017-10-08 a 2017-12-26 | 2018 | 3.720 |
| Soja 2022/23 | 2022-10 a 2023-02 | 2023 | 3.750 |
| Soja 2024/25 | 2024-10 a 2025-01 | 2025 | 4.260 |
| Milho 2017/18 | 2017-09 a 2017-12 | 2018 | 6.600 |
| Milho 2ª 2024/25 | 2025-01 a 2025-02 | 2025 | 8.400 (total do ano) |

**FATO.** Cada linha do conjunto pareado carrega `pam_year_confidence`
(`media_alta` soja, `media` milho, `media` milho 2ª), `pam_year_alternative` e
`pam_year_ambiguity`. A alternativa é o ano de plantio.

**LIMITAÇÃO.** A correspondência é **derivada**, não documental: os textos das
portarias não foram obtidos (continua pendente, como na V2.4). O critério
usado — a portaria precede a janela — valida a **consistência interna** do
calendário, mas não confirma a equivalence com o ano estatístico da PAM.

---

## 8. Milho principal e milho 2ª safra

**FATO.** A PAM publica **"Milho (em grão)"** — o total do ano, 1ª + 2ª safras
somados. Não há desagregação por safra em nenhuma variável
(`rendimento_medio_kg_ha`, `area_colhida_ha`, `area_plantada_ha`,
`quantidade_produzida_t` — 1.118 registros de milho em 52 variáveis × 13
anos, todos do produto agregado).

**Decisão (D60).** Como não há áreas por safra, **não** foi construído
indicador ponderado por participação de área: usar áreas de safras
diferentes para pesar seria incorreto. As janelas de milho principal e de
milho 2ª são mantidas **separadas** e cada uma é comparada com o rendimento
anual total apenas como **análise de sensibilidade**, com a incompatibilidade
declarada no campo `semantic_compatibility`.

**FATO.** O pareamento do milho 2ª ficou com **n = 3** (2022, 2024, 2025) —
porque a janela de apenas janeiro (safra 2016/17 a 2019/20) exige dois meses
com NDVI e a série só tem um mês por safra naquele período. Com n = 3 não há
teste de permutação válido (mínimo de 4 pares); os valores de correlação
(r = 0,857 municipal; 0,937 AOI) são **registrados sem inferência** e não
entram na família de testes com p-valor.

**INTERPRETAÇÃO.** O milho 2ª é, na prática, **não avaliável** com este
conjunto: é o caso mais claro da incompatibilidade semântica entre o alvo
(agregado) e a janela (safra específica).

---

## 9. Dataset pareado

**FATO.** `municipal_seasonal_productivity_dataset.csv`, 228 linhas =
31 pares (cultura × safra) × 4 máscaras (safra) + 26 pares (cultura × ano) ×
4 máscaras (ano civil). Estrutura em três blocos:

* **Identificação**: município, código IBGE, cultura, código do produto IBGE,
  safra, ano de referência PAM;
* **Calendário**: safra inicial/final, meses e datas da janela, decêndios,
  solo, ciclo, nível de risco, portaria, nº de combinações oficiais, nº de
  janelas distintas na safra;
* **Geoespacial**: variante e ano da máscara, `mask_retrospective`, perfil
  radiométrico, tiles, nº de meses, cobertura média, NDVI médio e mediano
  (municipal e da AOI), dispersão, nº de pixels;
* **Agronômico**: rendimento original e em kg/ha, área colhida, quantidade
  produzida, unidade original, natureza da observação, fonte e id da fonte;
* **Qualidade**: compatibilidade temporal, espacial e semântica, grau de
  confiança, situação de utilização (`paired_usable`/`excluded`) e motivo de
  exclusão.

**FATO — n efetivo (a parte que mais importa).**

| Fatia | Cultura | n | Anos |
|---|---|---:|---|
| `zarc_sazonal` | soja | **8** | 2018–2025 |
| `zarc_sazonal` | milho | **8** | 2018–2025 |
| `zarc_sazonal` | milho 2ª | 3 | 2022, 2024, 2025 |
| `ano_civil_v23` | soja | **9** | 2017–2025 |
| `ano_civil_v23` | milho | **9** | 2017–2025 |

O n efetivo é o número de **anos com rendimento**, não o número de
combinações ZARC: uma safra com 18 combinações de solo/ciclo e 5 janelas
distintas continua sendo **uma** observação.

**FATO.** O critério de exclusão é: sem rendimento PAM; menos de 2 meses com
NDVI municipal; ou **cobertura média da janela < 0,50** (critério de qualidade
de cena, fixado antes da análise). As exclusões effective são poucas e
transparentes: soja/milho 2025/26 e 2026/27 (sem PAM para 2026 e 2027);
milho 2ª 2016/17–2022/23 (um único mês na janela).

**FATO — CONTROLE DE REPLICAÇÃO.** A fatia `ano_civil_v23` reproduz a V2.3
**par a par**: para os 18 pares (9 soja + 9 milho) de 2017–2025, a diferença
máxima entre o `ndvi_aoi_mean` da V2.3 e o da V2.5 é **1,1·10⁻¹⁶**
(arredondamento de ponto flutuante). Isso valida a cadeia de leitura,
agregação e pareamento da V2.5 contra a implementação auditada da V2.3.

---

## 10. Análise estatística

**Protocolo.** Mesmos métodos da V2.3 — Pearson, Spearman, permutação com
5.000 iterações e semente fixa (20261112), correlação detrendizada e
walk-forward com os mesmos baselines (média histórica, último valor, tendência
linear, OLS com o indicador) — acrescidos de **IC 95% por bootstrap** (2.000
iterações) e **correção de Holm** sobre a família completa (32 testes).

**FATO — análise principal (pre-declarada: soja, máscara `stable`, janela
modal do ZARC, escala municipal):**

| Série | n | r (Pearson) | ρ (Spearman) | p (permutação) | p (Holm) | IC 95% (r) | r detrendizado |
|---|---:|---:|---:|---:|---:|---|---:|
| **soja · sazonal · municipal** | 8 | **0,2028** | 0,0838 | 0,6491 | 1,000 | [−0,576; 0,775] | 0,2097 |
| soja · sazonal · AOI | 8 | 0,3725 | 0,6108 | 0,3413 | 1,000 | [−0,557; 0,985] | 0,4983 |
| milho · sazonal · municipal | 8 | −0,3964 | −0,1190 | 0,3501 | 1,000 | [−0,868; 0,603] | −0,2703 |
| milho · sazonal · AOI | 8 | −0,4545 | −0,2857 | 0,2791 | 1,000 | [−0,931; 0,629] | −0,0915 |

**FATO — réplicas e controles (ano civil):**

| Série | n | r | ρ | p | r detrendizado |
|---|---:|---:|---:|---:|---:|
| soja · ano civil · AOI (**réplica da V2.3**) | 9 | 0,4318 | 0,1345 | 0,2422 | 0,5837 |
| soja · ano civil · municipal | 9 | 0,3024 | 0,0840 | 0,4263 | 0,3457 |
| milho · ano civil · AOI (**réplica da V2.3**) | 9 | 0,2003 | 0,0667 | 0,6071 | 0,3542 |
| milho · ano civil · municipal | 9 | −0,0154 | 0,0000 | 0,9704 | −0,0016 |

**FATO.** A réplica da V2.3 reproduz **exatamente** os números publicados:
soja r = 0,432 / ρ = 0,134 / p = 0,246 / r detrendizado 0,584; milho
r = 0,200 / ρ = 0,067 / p = 0,610 / r detrendizado 0,354 (a diferença no
p-valor — 0,2422 vs 0,2456 — vem da semente e do número de iterações; a
diferença é de 0,0034 e está dentro da resolução do teste de permutação).

**FATO.** Nenhum dos 32 testes da família é significativo após a correção de
Holm (todos com p ajustado = 1,000). O p-valor mais baixo da família é
0,2422 (réplica da V2.3 na soja) — ou seja, **o próprio resultado da V2.3
não sobrevive à correção para múltiplas comparações**.

**INTERPRETAÇÃO.** A mudança de escala **não** produziu uma associação mais
consistente. Na soja, o indicador municipal sazonal (r = 0,203) é **mais
fraco** que o da AOI na mesma janela (r = 0,372) e mais fraco que a réplica
da V2.3 (r = 0,432). No milho, o sinal **inverte** e se torna negativo
(r = −0,396), sem Significance.

**LIMITAÇÃO.** Com n = 8, os intervalos de confiança bootstrap são larguíssimos
([−0,58; 0,78] na análise principal da soja) e encompassam zero e valores
negativos. **Nenhum** dos resultados permite afirmar relação.

---

## 11. Representatividade AOI × município

**FATO (47 meses comuns, máscara `stable`).** AOI e município estão
fortemente correlacionados no tempo (**r = 0,9724**, ρ = 0,9392), mas a AOI
**subestima** sistematicamente o NDVI municipal:

| Métrica | Valor |
|---|---:|
| NDVI municipal (média) | 0,5020 |
| NDVI da AOI (média) | 0,4646 |
| **Diferença média (municipal − AOI)** | **+0,0375** |
| Desvio-padrão da diferença | 0,0527 |
| Diferença mínima / máxima | −0,0832 / +0,1412 |
| Diferença média entre as médias anuais | +0,0377 |
| Desvio-padrão da diferença média anual | 0,0233 |

**FATO.** A diferença média anual varia de **−0,0002 (2018)** a **+0,0775
(2022)** — a AOI é praticamente igual ao município em 2018 e subestima em
~0,08 em 2022. A representatividade da AOI **não é estável**.

**INTERPRETAÇÃO.** O valor de +0,0375 confirma de forma independente a
estimativa da V2.4 (+0,039 entre o piloto municipal e a AOI em março de 2017)
— a AOI subestima a estatística municipal porque cobre uma sub-região com
composição de uso do solo diferente da média do município. **A AOI não é
representativa do município**, e a medida da não representatividade é da
ordem de 0,04 em NDVI e chega a 0,14 em meses individuais.

**LIMITAÇÃO.** A diferença **não** é um erro da AOI: é a consequência de ela
ser uma sub-região. A representatividade não valida produtividade — apenas
quantifica o quanto o indicador de sub-região se afasta do indicador
municipal.

**FATO.** A sensibilidade à máscara é desprezível: a diferença média é
+0,03725 (`wc2020`), +0,03737 (`wc2021`), +0,03747 (`stable`) e +0,03715
(`broad`), e a correlação AOI–municipal varia entre 0,9723 e 0,9725. **As
quatro máscaras produzem praticamente o mesmo resultado** — a escolha da
variante não é um factor determinante.

---

## 12. Comparação com a V2.3

**FATO — decomposição.** O conjunto tem duas fatias que permitem separar o
efeito **escala** do efeito **janela**, com o controle da réplica:

| # | Configuração | Soja (r) | Milho (r) | n |
|---|---|---:|---:|---:|
| 1 | **Réplica da V2.3** — AOI + ano civil | 0,432 | 0,200 | 9 |
| 2 | **Só muda a escala** — municipal + ano civil | 0,302 | −0,015 | 9 |
| 3 | **Só muda a janela** — AOI + janela ZARC | 0,372 | −0,455 | 8 |
| 4 | **Muda os dois** — municipal + janela ZARC | 0,203 | −0,396 | 8 |

**INTERPRETAÇÃO.** Nenhuma das três mudanças melhora a associação. Na soja,
mudar a escala **reduz** r de 0,432 para 0,302; mudar a janela também
(0,432 → 0,372); mudar as duas coisas piora (0,203). No milho, a mudança de
escala **anula** a correlação (0,200 → −0,015) e a mudança de janela **inverte
o sinal** (0,200 → −0,455). A hipótese central da V2.5 — que a incompatibilidade
de escala e a janela anual explicavam a ausência de relação — **não se
confirma**.

**FATO — validação temporal alinhada.** Para que a comparação seja
equivalente, o walk-forward foi recomputado com **os mesmos anos de teste**
(2023, 2024 e 2025 — os anos com treino suficiente em todas as fatias) e os
mesmos baselines:

| Série | OLS com NDVI | Média histórica | Último valor | Tendência | O NDVI vence? |
|---|---:|---:|---:|---:|---|
| soja · sazonal · municipal | 402,4 | **315,1** | 420,0 | 387,1 | **não** |
| soja · sazonal · AOI | 564,2 | **315,1** | 420,0 | 387,1 | **não** |
| soja · ano civil · municipal | 360,0 | **320,4** | 420,0 | 354,6 | **não** |
| soja · ano civil · AOI | 323,8 | **320,4** | 420,0 | 354,6 | **não** |
| milho · sazonal · municipal | 1.075,2 | **936,3** | 440,0 | 721,4 | **não** |
| milho · sazonal · AOI | 1.306,9 | **936,3** | 440,0 | 721,4 | **não** |
| milho · ano civil · municipal | 940,8 | **851,8** | 440,0 | 945,6 | **não** |
| milho · ano civil · AOI | 908,9 | **851,8** | 440,0 | 945,6 | **não** |

**FATO.** Em **nenhuma** das 8 configurações o modelo com NDVI supera a
média histórica. Na soja, a piora chega a 87,7 kg/ha (402,4 vs 315,1). No
milho, a piora chega a 370,6 kg/ha.

**FATO.** A referência da V2.3 (soja: MAE 368 com NDVI vs 254 da média
histórica; milho: 955 vs 684 do último valor) é **confirmada** pela réplica
da V2.5 no ano civil com a AOI (soja: 323,8 vs 320,4; milho: 908,9 vs 851,8
na mesma Configuration alinhada) — o quadro da V2.3 se reproduz.

**INTERPRETAÇÃO.** O NDVI, na escala municipal e em janelas agronômicas
adequadamente documentadas, **não acrescenta informação** ao rendimento
municipal. A escala do indicador não era o gargalo.

---

## 13. Testes e reprodutibilidade

**FATO.** Suíte offline: **213/213** testes aprovados (33 novos da V2.5 em
`geospatial/tests/test_seasonal.py`), incluindo a regra oficial de decêndios
(os 36 decêndios, fevereiro e anos bissextos), a âncora de ano, o rótulo
textual de risco, a janela modal, a separação milho 1ª/2ª, a marcação de
máscara retrospectiva, a exclusão por ausência de rendimento, a correção de
Holm, o determinismo da permutação, a ausência de vazamento no walk-forward
e **o uso do rendimento (e não do indicador) nos baselines** (regressão do bug
corrigido nesta versão).

**FATO.** Testes externos (opt-in, `SADEN_EXTERNAL_TESTS=1`): ver seção 16.

**FATO — reprodutibilidade.** Reexecução integral do mecanismo incremental →
SHA-256 **idêntico**, 188 linhas, 0 duplicatas. Paralelismo validado
(resultado numérico idêntico ao sequencial). A fatia `ano_civil_v23`
reproduz a V2.3 com diferença máxima de 1,1·10⁻¹⁶.

**FATO — correções de engenharia encontradas na auditoria (todas reais):**

1. `mask_variants` comparava máscaras booleanas com `== 40`, zerando todas as
   máscaras;
2. `read_worldcover_year`/`read_worldcover_block` não ajustavam o `transform`
   à janela recortada (mapear célula→pixel errava);
3. leitura do WorldCover sem validação: o servidor devolvia janelas vazias e
   a máscara ficava zerada;
4. `_cells_bbox` do bloco: o topo do bloco (grade com eixo vertical
   decrescente);
5. `NaN` no acumulador de NDVI;
6. `decendios_com_risco` com risco textual (janelas vazias);
7. âncora de ano dos decêndios (165 violações da cronologia das portarias);
8. `walk_forward` calculava os baselines sobre o **indicador** em vez do
   **rendimento** (MAE ~3.800 kg/ha em vez de ~315).

---

## 14. Limitações

1. **Máscara retrospectiva**: só existem mapas de uso do solo de 2020 e
   2021; 7 dos 8 anos analisados usam máscara de anos diferentes do da cena.
2. **n efetivo de 8** (soja e milho): nenhum resultado é significativo e os
   IC bootstrap são larguíssimos.
3. **Milho agregado**: a PAM publica o total do ano; a janela de 2ª safra é
   incompatível com o alvo (n = 3, não avaliável).
4. **Janela ≠ ciclo**: não há duração de ciclo oficial por cultivar para
   Sorriso; o indicador mede o espectro durante o período recomendado, não a
   biomassa da cultura.
5. **Combinações ZARC não identificadas**: solo e ciclo predominantes em
   Sorriso não são conhecidos; a janela modal é aproximação.
6. **Cobertura de nuvem** entre 0,27 e 0,99, com 4 meses abaixo de 0,50; a
   cobertura média é usada como critério de exclusão, mas a seleção
  a seleção dos pixels válidos **enviesa** a média (pixel sem nuvem em
   época úmida tende a ter NDVI mais alto).
7. **Série parcial**: 47 dos 101 meses observados (só os das janelas
   agrícolas).
8. **Correlação não é causalidade** e **9 pares não sustentam capacidade
   preditiva**.

---

## 15. Resultados e caminho final

**FATO.** A pergunta central da V2.5 era: *"quando comparamos o rendimento
agrícola municipal com indicadores de vegetação calculados na mesma escala
territorial e em períodos agronômicos mais adequados, encontramos uma relação
estatística mais consistente do que a observada na V2.3?"*

**RESPOSTA: NÃO.**

| Critério | Verificado |
|---|---|
| Série municipal concluída | **sim** — 47/47 meses das janelas, 188 linhas, reprodutível |
| Máscara adequadamente caracterizada | **sim** — 4 variantes, quantificadas, com a limitação temporal declarada |
| Calendário documentado | **sim** — ZARC com regra oficial de decêndios, âncora verificada, portarias |
| Relação safra–PAM justificada | **parcial** — derivada e internamente consistente; textos das portarias ainda pendentes |
| Base temporal pareada construída | **sim** — 228 linhas, 2 fatias, n efetivo contabilizado |
| Análise com cobertura aceitável | **sim**, com critério declarado (≥ 0,50) e 5 exclusões transparentes |
| Resultados reproduzíveis | **sim** — SHA-256 idêntico; réplica da V2.3 com 1,1·10⁻¹⁶ |
| Associação mais consistente que a V2.3 | **não** — r menor em todas as configurações |

**CAMINHO FINAL: B — base pareada válida, mas sem ganho do NDVI.**

Os dados foram corretamente alinhados, o calendário é válido, os indicadores
municipais foram construídos, a amostra está disponível (n = 8) e **o NDVI
não supera os baselines** — em nenhuma das 8 configurações testadas, sob
validação temporal alinhada. Essa é uma descoberta científica válida: a
incompatibilidade de escala e a janela anual **não** eram a causa da ausência
de relação observada na V2.3.

**Nada foi integrado** ao Ridge de preços, à interface ou à API (D40/D41). A
análise é **retrospectiva** (usa toda a safra para investigar relações) e
**não** é uma previsão operacional.

---

## 16. Decisões e o que permanece

**Decisões registradas na V2.5:** D58–D61 (protocolo) e D62–D65 (correções e
decomposição). As D42–D57 não foram alteradas.

**Pendências que continuam abertas:**

1. **MapBiomas (GEE, conta institucional)** — traria a máscara **anual** de
   uso do solo (2017–2025), eliminando a maior limitação metodológica
   (máscara retrospectiva). É a pendência que **mais** muda o resultado.
2. **Textos das portarias do ZARC** — fechariam a regra safra→ano da PAM
   documentalmente.
3. **Duração de ciclo por cultivar** (EMBRAPA) — permitiria o indicador de
   desenvolvimento vegetativo (Indicador 2/3 do protocolo), hoje não
   construído.
4. **Produtividade submunicipal** — continua inexistente em fonte pública
   reproduzível (D56).
5. **Série municipal completa** — os 54 meses restantes (mar–ago) podem ser
   gerados pelo mesmo mecanismo retomável, para permitir o indicador de ano
   civil **municipal** com 12 meses por ano (hoje usa 4–6 meses por ano,
   porque só os meses das janelas foram processados).

---

## 17. Recomendação para a V2.6

**Não investir em novos modelos de produtividade baseados em NDVI.** A V2.5
fez o que a V2.4 havia deixado pendente — scale harmonization, calendário
oficial, janelas agronômicas documentadas, pareamento espacial e temporal,
reavaliação estatística com controle de vazamento e replicação verificada — e
o resultado é **negativo e consistente**: o NDVI, calculado na escala
municipal e em janelas de plantio oficiais, não explica o rendimento
municipal de soja nem de milho em Sorriso.

**Direcionar os recursos para:**

1. **Variáveis com conteúdo agronômico direto** para o modelo de preço:
   balanço hídrico, graus-dia, radiação, vento, e outros, que são as
   variáveis que de fato explicam a variabilidade da produtividade — e que
   estão disponíveis em fontes públicas (INMET, MapBiomas, agroclimáticos).
2. **Ampliar o universo de municípios**, se o objetivo for produto: a
   limitação de n = 8 é estrutural em um município e não se resolve com
   melhor modelagem; resolve-se com **mais municípios** (o PIB do agronegócio
   brasileiro é municipal, e o modelo de preço pode ser treinado em painel).
3. **Manter a série e a base pareada** como evidência do caminho percorrido
   e como base reproduzível para reavaliações futuras (inclusive se o
   MapBiomas institucional for aprovado).

**O SADEN não deve integrar o indicador geoespacial ao Ridge de preços.**
