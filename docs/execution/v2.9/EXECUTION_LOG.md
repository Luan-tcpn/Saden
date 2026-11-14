# SADEN V2.9 — Log de execução

> Registro cronológico. Cada entrada: etapa, arquivos, comandos, resultado,
> erros/correções e commit.

## Sessão 1 — 2026-11-14

### Fase 0 — Recuperação e proteção

**Auditoria.** Diretório confirmado. HEAD `a36e6be`, branch
`v2/temporal-spatial-generalization` sincronizada com `origin`, árvore limpa.
`main` e `v1-final` em `3f7ad33`; tags `v1-final` e `v2-poc-sentinel2`
intactas; nenhum stash.

**Bundle V2.8.** `SADEN_V2_8_RECOVERY_2026-11-14\saden-v2-8-final-2026-11-14.bundle`:
15.658.603 bytes, SHA-256 `73297BABB21932C2642F6379BEA9482E89B95C41E57FA2BC9C1A718F46890AA8`,
`git bundle verify` → *okay*, **26 refs**, incluindo `refs/heads/main`,
`refs/heads/v2/agroclimatic-robustness`,
`refs/heads/v2/temporal-spatial-generalization` e `refs/tags/v1-final`.
Conferido por `list-heads`, não apenas pelo `verify`.

**Branch.** `v2/regional-agroclimatic-robustness` criada em `a36e6be` (não
existia local nem remotamente).

**Suíte de referência.** `pytest geospatial/tests -q` → **338 passed**.

### Fase 1 — auditoria da equalização da V2.8 (D90)

**Diagnóstico (sem ajustar modelos).** Para cada cultura, por célula
(bloco × ano) e braço, mediu-se o conjunto de treino disponível:

| Cultura | braço | média | mínimo | máximo | células abaixo do alvo |
|---|---|---|---|---|---|
| soja | SS | 8.529 | 8.087 | 8.742 | 0 |
| soja | SE | 7.107 | 5.747 | 7.764 | 0 |
| soja | TS | 7.107 | 6.648 | 7.770 | 0 |
| soja | **TE** | **5.686** | **4.308** | 6.792 | **11/25** |
| milho | TE | 4.874 | 3.514 | 6.323 | 13/25 |
| milho 2ª | TE | 1.857 | 1.418 | 2.318 | 10/25 |

Ou seja: a média do `TE` coincidia com o alvo (5.686), mas **11 das 25
células** ficavam abaixo dele — a média escondia a desigualdade. Nenhuma
célula tinha menos de 1.400 linhas de treino.

**Correção de implementação.** `generalization.factorial_holdout` ganhou
`equalize="global" | "per_cell"` e `min_cell_train`. No modo `per_cell` o alvo
de cada célula é o menor conjunto entre os quatro braços; células abaixo do
mínimo são descartadas de **todos** os braços. Também passou a reportar
`train_size_min/max/sd`, `cells_at_target`, `cells_below_target` e
`repeat_metrics` (MAE e RMSE **por repetição**, com dispersão entre
repetições — as repetições não são observações de teste independentes).

O caminho `global` foi preservado: `SE = P3` (612,724390) e `TE = P5`
(661,802276) continuam exatos, verificado pelos testes da V2.8 (20/20).

**Resultado da auditoria** (`tools/s29_equalization_audit.py`,
`v29_equalization_audit.json`), `climate_plus_state`, 5 repetições:

| Cultura | modo | SS | SE | TS | TE |
|---|---|---|---|---|---|
| soja | global | 552,8 | 559,4 | 588,9 | 604,3 |
| soja | **per_cell** | 552,7 | 559,0 | 589,7 | 604,4 |
| milho | global | 1.493,3 | 1.662,9 | 1.515,3 | 1.717,8 |
| milho | **per_cell** | 1.489,8 | 1.661,2 | 1.516,7 | 1.718,4 |
| milho 2ª | global | 1.165,8 | 1.205,3 | 1.177,6 | 1.234,0 |
| milho 2ª | **per_cell** | 1.164,1 | 1.209,6 | 1.179,9 | 1.233,7 |

Diferença máxima de MAE entre modos: **5,1 kg/ha** (milho 2ª, `SE`). Efeitos:

* soja: espaço −6,3 [−14,3;+3,0] (n.s.); tempo −37,0 [−47,3;−23,8] — **igual**.
* milho: espaço −171,5 [−331,6;−32,5]; tempo −26,9 [−46,2;−9,0] — **igual**.
* milho 2ª: espaço **−45,5 [−79,0;−0,8]** (era −39,6 [−68,5;+0,5], n.s.);
  tempo −15,8 [−31,8;−8,3].

**Decisão (D90):** a conclusão da V2.8 — de que a redução de amostra não
explica a inversão do P5 — **se sustenta** sob equalização estrita. A
ressalva é que uma comparação limítrofe (milho 2ª, espaço) passa a excluir
zero; isso é registrado, não corrigido narrativamente.

**Testes.** `geospatial/tests/test_v29_equalization.py` (7 testes): modo
global reporta células abaixo do alvo; modo `per_cell` iguala os quatro braços
em todas as células; conjunto de teste idêntico entre braços; células abaixo
do mínimo caem para todos; modo inválido rejeitado; métricas por repetição
coerentes com a MAE agregada. Suíte total: **345/345**.

**Checkpoint.** `3818baa`.

### Fase 2 — modelos aninhados (D91)

`tools/s29_nested_models.py`. M0 (média global) → M1 (média da UF) → M2 (UF +
clima), mesmo treino e mesmo teste, equalização por célula, 5 repetições.
`climate_only` mantido como M0b.

Valor incremental do clima (`M2 − M1`), família B:

| Cultura | SS | SE | TS | TE |
|---|---|---|---|---|
| soja | −13,3 [−25,9;−0,8] | −19,2 [−35,2;−3,9] | +1,5 n.s. | −6,3 n.s. |
| milho | −101,0 n.s. | −216,1 [−373,0;−48,2] | −69,7 n.s. | −198,7 [−355,8;−31,3] |
| milho 2ª | −169,3 | −257,4 | −161,5 | **−267,2 [−413,8;−35,1]** |

Família hídrica na soja: SS +1,7 n.s.; SE −6,6 n.s.; TS **+26,3
[+16,4;+36,6]** e TE **+20,5 [+9,6;+31,7]** — o modelo é pior que a média da
UF quando o ano é retirado.

Fallback de UF instrumentado: 0,0% em todos os braços (toda UF de teste tem
linhas no treino). A decomposição por UF (`by_state`) foi acrescentada ao
módulo.

**Checkpoint.** `a843ab0` (junto com a Fase 3).

### Fase 3 — heterogeneidade do milho e escala do bloco (D92)

`tools/s29_block_scale.py`: fatorial repetido em 150/250/400/600 km.

Efeito espacial do milho: −47,1 (150 km, 107 blocos), −170,8 (250, 49),
−152,4 (400, 26), −415,1 (600, 15). A soja é insensível em 150–400 km; o
valor de −87,0 em 600 km tem 14 blocos e não sustenta conclusão.

Efeito do bloco por UF (250 km): PR +421,4, BA +291,0, MS +170,9, GO +29,7,
MT +17,3, RS −96,7 → heterogeneidade **dentro** da UF.

### Fase 4 — CAD (D93)

Sondagem do WCS: serviço disponível (0,07 MB / 0,3 s para 0,1°). Testes de
redução de resolução: `scaleFactor=0.2` → 0,066 MB (60× menor, ~450 m);
`scaleFactor>1` aumenta a resolução (inútil aqui); `scalesize` → HTTP 404.

`tools/s29_cad_expand.py`: aquisição por bbox municipal, 6 camadas, estatística
por camada e CAD **por pixel** em 0–60/0–100/0–200 cm. Correção: a versão
inicial aplicava as seis camadas a qualquer profundidade (a "0–100" saía com
o valor de 0–200); corrigido antes de qualquer conclusão.

Piloto estratificado (18 municípios): CAD 0–100 entre 112,1 e 200,6 mm,
mediana 161,5 — compatível com a amostra da V2.7 (126–240; mediana 159).

Custo medido ~15 s/município → cobertura completa dos 1.296 exigiria ~5 h.
Optou-se por **amostra estratificada por UF e porte** (120 municípios) em
manifesto próprio (`v29_cad_stratified.json`), com o plano de cobertura
completa documentado.

### Fase 5 — ZARC (D94)

Dicionário oficial localizado no Portal de Dados Abertos do MAPA
(`dicionario-de-dados-tabua-de-risco-2026.pdf`, consultado em 2026-11-14,
CC-BY): `Cod_Ciclo` 13 Perene, 19 Semiperene, 20 Grupo I, 21 Grupo II,
22 Grupo III, 24 Grupo IV, 25 Grupo V, 26 Grupo VI; `Cod_Solo` 1/2/3 e 11–16.

Novo módulo `geospatial/agroclimate/cycle.py` (rótulos + `interaction_test`).

Teste formal de interação: soja déficit **−1,194 (t=−3,16; p=0,003)**;
soja temperatura −3,98 (t=−0,88; p=0,38); milho precipitação −1,017 (p=0,046,
marginal); demais não significativos. **Correção da V2.8:** a "inversão de
sinal" da temperatura na soja não existe — era artefato de estimar cada
classe separadamente. Nota de correção aposta em §13 do relatório da V2.8.

**Testes.** `test_v29_cycle.py` (9): rótulos, códigos desconhecidos, metadados
da fonte, detecção de diferença verdadeira, ausência de diferença sob a nula,
IC, amostra insuficiente e desenho degenerado. Suíte: **354/354**.

**Checkpoint.** `4d7af5b`.

### Fase 6 — cobertura (D95)

`tools/s29_coverage.py`: 19.402 linhas, 1.296 municípios, 46/49/30 blocos,
5–6 UFs; interseção com a CAD medida na mesma população.

### Fase 7–8 — síntese e encerramento

`docs/V2_9_REGIONAL_AGROCLIMATIC_REPORT.md`; decisões D90–D94 em
`docs/DECISIONS.md`; balanço hídrico por município e publicação da branch.

