# SADEN V3.1 — Janelas agroclimáticas corretas e heterogeneidade espacial

**Branch:** `v3/window-spatial-generalization`
**Base:** `40fd6aa` (V3.0)
**Data:** 2026-11-14
**Protocolo de generalização:** TE (espaço e tempo separados simultaneamente)

---

## 1. Resumo executivo

A V3.0 descobriu (D97) que o painel agroclimático perdia o **último mês** da
janela ZARC em 28.282 de 40.990 linhas. A V3.1 foi encarregada de auditar essa
descoberta, reconstruir **todas** as variáveis afetadas e reavaliar os modelos.
O resultado central é que o defeito era maior do que o relatado: não afetava só
o déficit hídrico, mas **toda** variável agregada dentro da janela.

Reconstruindo as 19.402 linhas analíticas com as mesmas funções do painel:

* a janela histórica é **reproduzida até o erro de float32** (diferença máxima
  1,7e-5), então as diferenças medidas são do defeito, não do pipeline;
* restaurar o último mês aumenta a precipitação acumulada em **+44%**, a ET0 em
  **+44%**, os graus-dia em **+46%**, os dias de chuva em **+46%** e a mediana do
  déficit por linha em **+24%** (a mediana absoluta do déficit quase dobra:
  51,3 → 106,0 mm).

Toda a pesquisa agroclimática de V2.6 a V3.0 foi, portanto, conduzida com
**um mês inteiro a menos por janela** — tipicamente 17–25% do período, o que
reduzia as variáveis acumuladas em ~44%. Os resultados anteriores continuam
reproduzíveis (`_legacy`), mas nenhuma conclusão da V3.1 se apoia neles.

Com a janela corrigida, em TE e igualdade de informação com a média da UF:

| Cultura | clima histórico | clima corrigido | pareado |
|---|---:|---:|---|
| soja | −6,3 n.s. | −18,5 n.s. | −12,2 [−24,0; 4,9] n.s. |
| milho | −198,7 | **−228,5** [−403,5; −37,0] | **−29,8** [−51,5; −2,3] |
| milho 2ª safra | −267,2 | −228,4 [−374,0; −11,0] | +38,8 [−1,8; 59,7] n.s. |

O ganho do milho **não é uniforme**: é −607,4 kg/ha em PR, −131,1 em BA, −109,9
em GO e **pior** que a média da UF em MS (+261,4), MT (+85,0) e RS (+12,8). A
MAE agregada esconde essa estrutura.

Duas abordagens espaciais foram testadas:

* **tendência espacial** (lat/lon + quadráticos + UF) — **rejeitada**: no milho
  é pior que o clima por +388,1 [62,0; 719,5];
* **vizinhos históricos** (M1c) — **aprovada com ressalvas**: supera a média da
  UF na soja (−27,7 [−52,3; −3,8], cobertura 0,987) e no milho 2ª (−189,6
  [−312,5; −11,7], cobertura 1,000), mas depende do raio e da cobertura.

Nenhuma alegação nacional é feita: 5–6 UFs de 27.

---

## 2. Estado inicial (V3.0)

| item | valor |
|---|---|
| branch | `v3/cad-integrated-agroclimatic-panel` |
| commit | `40fd6aa` |
| base | `adb525f` |
| testes offline | 372 |
| bundle | 16.601.458 B, SHA-256 `2B954AC5…AE493D51`, 29 refs, *okay* |

Confirmado antes de qualquer alteração: `git status` limpo, sincronizado com
`origin`, `main` = `archive/v1-final` = tag `v1-final` = `3f7ad33`, V2.9 =
`adb525f`, V3.0 = `40fd6aa`. Suíte de referência 372/372. Bundle verificado com
`git bundle verify` e `list-heads`.

---

## 3. Branch e commits

| commit | conteúdo |
|---|---|
| `2028efc` | reconstrução de todas as variáveis ambientais da janela (D100) |

Branch criada de `40fd6aa`, publicada em `origin`. Nenhuma operação destrutiva,
nenhum force push, `SADEN-TCC/` intocado, V1 e `main` intactas.

---

## 4. Auditoria da D97

### 4.1. Causa

`cycle.window_bounds` comparava a data diária `"AAAA-MM-DD"` com o rótulo
mensal `"AAAA-MM"`. Na ordem lexicográfica, `"2017-12-01" > "2017-12"`; logo o
mês final era **inteiramente descartado**, não apenas o dia 31.

Não era erro de indexação de um dia: era **um mês por janela**. Como as janelas
ZARC têm tipicamente 4–6 meses, o viés é de 17–25% do período — e ~44% nas
variáveis acumuladas, porque o mês descartado tende a ser chuvoso e quente.

### 4.2. Alcance

A filtragem era aplicada ao conjunto de dias que alimentava **todas** as
agregações. Portanto o defeito contaminava, além do balanço hídrico:
precipitação, dias de chuva, dias secos, médias e extremos de temperatura,
radiação, umidade, vento, graus-dia, ondas de calor, dias de calor extremo,
noites quentes, ET0 e ETP.

### 4.3. Reprodução

Para provar que a reconstrução é fiel, a janela histórica foi recalculada e
comparada com o painel publicado, linha a linha (19.402 linhas):

| variável | n | exatos | diferença máxima | mediana |
|---|---:|---:|---:|---:|
| `precip_acumulada_mm` | 19.402 | 8.366 | 1,59e-5 | 1,19e-6 |
| `temp_media_c` | 19.402 | 19.402 | 3,64e-7 | 4,22e-8 |
| `degree_days_total` | 19.402 | 5.326 | 1,59e-5 | 1,98e-6 |
| `extreme_heat_days` | 19.402 | 19.402 | 0 | 0 |
| `et0_total_mm` | 19.402 | 9.798 | 7,72e-6 | 9,86e-7 |
| `deficiency_total_mm` | 19.402 | 11.978 | 1,05e-5 | 6,03e-7 |
| `excess_total_mm` | 19.402 | 11.624 | 1,72e-5 | 5,00e-7 |

As diferenças são de arredondamento de `float32` na serialização do CSV
original. O pipeline é fiel; as diferenças da janela corrigida são do defeito.

### 4.4. Contrato temporal (D100)

Uma única representação canônica:

* `corrected=True` (padrão V3.1): primeiro dia do primeiro mês → **último dia do
  último mês**, ambos inclusivos;
* meses listados em ordem cronológica; rótulos vazios são ignorados; janela
  vazia é erro;
* ano bissexto tratado por `calendar.monthrange`;
* `corrected=False` preserva a semântica histórica **exclusivamente** para
  reprodução.

A janela usada é a de **semeadura recomendada pelo ZARC**, não uma janela
fenológica observada. Isso é uma aproximação registrada: graus-dia acumulados na
janela de semeadura não são graus-dia até maturação.

---

## 5. Nova definição das janelas

| variável | janela usada | justificativa |
|---|---|---|
| precipitação, ET0, déficit, excedente, armazenamento | janela ZARC completa (meses listados) | definição agronômica do ZARC |
| graus-dia | mesmos meses, perfil térmico da cultura | aproximação declarada (§4.4) |
| calor extremo / noites quentes | mesmos meses | contagem por dia |
| médias e extremos de temperatura, radiação, umidade, vento | mesmos meses | descritivos |

Nenhuma variável recebeu janela diferente por acidente. A distinção entre janela
ZARC e janela fenológica é explícita, não implícita.

---

## 6. Variáveis ambientais reconstruídas

Vinte variáveis por linha, nas duas janelas, mais três cenários de CAD
(0–60, 0–100, 0–200 cm) na janela corrigida. A tabela abaixo reporta as
medianas das duas versões e, nas duas últimas colunas, a **mediana das
variações por linha** (relativa e o sinal) — convenção usada porque a
distribuição se desloca, e a razão entre medianas não é igual à mediana das
razões:

| variável | unidade | mediana histórica | mediana corrigida | mediana da variação relativa | linhas que aumentaram |
|---|---|---:|---:|---:|---:|
| precipitação acumulada | mm | 338,3 | 491,4 | +44,0% | 100,0% |
| ET0 acumulada | mm | 390,0 | 557,5 | +43,5% | 100,0% |
| graus-dia | °C·dia | 1.018,9 | 1.489,8 | +45,5% | 100,0% |
| dias com chuva | dias | 59 | 88 | +45,6% | 100,0% |
| noites quentes | dias | 26 | 44 | +54,3% | 94,3% |
| dias de calor extremo | dias | 4 | 8 | +5,9% | 42,2% |
| déficit hídrico | mm | 51,3 | 106,0 | +23,6% | 53,4% |
| excedente hídrico | mm | 58,4 | 91,9 | 0,0% | 29,4% |
| temperatura média | °C | 24,33 | 24,41 | +1,0% | 58,8% |

Observações obrigatórias:

* a razão entre as medianas é maior que a mediana das razões nas variáveis
  acumuladas (precipitação: 491,4/338,3 = +45,3% contra +44,0%). As duas
  descrevem a mesma mudança de distribuição sob estatísticas diferentes; a
  coluna reportada é a mediana por linha;
* **dias de calor extremo** e **excedente** têm mediana da variação relativa
  próxima de zero porque a maioria das linhas não tem nenhum dia acima do limiar
  (Tmax > 35 °C) nem excedente; a informação está na cauda (42,2% e 29,4% das
  linhas aumentam);
* **déficit** cresce muito menos em termos relativos (+23,6%) do que a
  precipitação (+44,0%) porque a ET0 também cresce: o balanço não é "mais
  chuva", é "mais demanda e mais oferta", com saldo dependente da capacidade de
  água disponível;
* a temperatura média quase não muda — o mês acrescentado não é um mês atípico
  de temperatura, o que é coerente com um viés de **cobertura**, não de seleção.

Nenhum valor histórico foi sobrescrito: o painel derivado carrega `_legacy` e
`_corrected` lado a lado.

---

## 7. Comparação com a versão histórica

A comparação é feita em três níveis:

1. **reprodução** (§4.3) — o pipeline histórico é fiel, logo a diferença é do
   defeito;
2. **variável por variável** (§6) — a magnitude do viés;
3. **modelo** (§8–§10) — o que muda na conclusão científica.

O ponto metodológico importante: a correção **não** é uma melhoria de modelo. É
uma correção de dados. Por isso o painel antigo não foi descartado: ele é a
referência contra a qual o novo é medido.

---

## 8. Painel corrigido

| item | valor |
|---|---|
| linhas analíticas | 19.402 |
| municípios | 1.296 |
| soja / milho / milho 2ª | 8.884 / 7.616 / 2.902 |
| blocos espaciais (250 km) | 46 |
| grupos temporais | 8 (soja, milho), 9 (milho 2ª) |
| UFs | 5 (soja: GO, MS, MT, PR, RS) · 6 (milho: + BA) · 4 (milho 2ª: GO, MS, MT, PR) |
| joins perdidos | 0 |
| anos sem referência | 0 |
| coordenadas ausentes | 0 |

O painel corrigido é um artefato separado (`v31_panel_windows.csv`), fora do
Git por ser derivado e regenerável por `tools/v31_rebuild_panel.py`. A
evidência versionada é o manifesto `v31_window_rebuild.json`.

---

## 9. Reprodução M0/M1/M1b/M2

Estrutura preservada:

* **M0** — média nacional;
* **M1** — média por UF (referência operacional *ex-ante*);
* **M1b** — média UF×ano (diagnóstico contemporâneo, **nunca** baseline
  operacional);
* **M2** — clima + dummies de UF.

A reprodução da V3.0 é exata, o que valida toda a cadeia de reconstrução:

| especificação (TE) | V3.0 publicado | V3.1 recalculado |
|---|---:|---:|
| soja clima | −6,3 | −6,33 |
| milho clima | −198,7 | −198,72 |
| milho 2ª clima | −267,2 | −267,16 |
| milho CAD 0–100 | −142,8 | −142,78 |
| milho CAD 0–200 | −21,7 | −21,68 |
| soja déficit 50 mm corrigido | −20,0 | −19,97 |

Desenho: 25 células (5 blocos × 5 grupos temporais), equalização estrita por
célula, **todas as 25 células no alvo** em todas as especificações, 3 repetições,
IC por bootstrap de bloco, semente `20261114`.

| Cultura | treino médio por célula | treino mínimo | células no alvo |
|---|---:|---:|---:|
| soja | 5.686 | 4.308 | 25/25 |
| milho | 4.874 | 3.514 | 25/25 |
| milho 2ª | 1.857 | 1.418 | 25/25 |

---

## 10. Valor incremental do clima

Pergunta 1 — *o clima acrescenta valor além da UF?* (M2 vs M1, TE)

| Cultura | janela histórica | janela corrigida | pareado (corrigida − histórica) |
|---|---:|---:|---|
| soja | −6,3 [−26,8; 10,4] n.s. | −18,5 [−42,7; 11,5] n.s. | −12,2 [−24,0; 4,9] n.s. |
| milho | −198,7 [−355,8; −31,3] | **−228,5** [−403,5; −37,0] | **−29,8** [−51,5; −2,3] |
| milho 2ª | −267,2 [−413,8; −35,1] | −228,4 [−374,0; −11,0] | +38,8 [−1,8; 59,7] n.s. |

Perguntas 2 e 3 — *o déficit reconstruído acrescenta valor além do clima?*

| Cultura | déficit 50 mm | CAD 0–60 | CAD 0–100 | CAD 0–200 | pareado vs clima corrigido (CAD 0–100) |
|---|---:|---:|---:|---:|---|
| soja | −20,0 n.s. | −15,5 n.s. | −10,3 n.s. | −6,9 n.s. | +8,2 [−3,7; 21,2] n.s. |
| milho | −195,2 | −181,4 | −142,8 | −21,7 n.s. | +85,7 [−13,8; 182,4] n.s. |
| milho 2ª | −24,8 n.s. | −37,7 n.s. | −35,0 n.s. | −23,2 n.s. | **+193,4** [11,0; 318,7] |

Leitura: o déficit **não supera** o clima de forma alguma; no milho 2ª é
significativamente pior. A CAD oficial continua não agregando (D98 confirmada
com dados corrigidos). Graus-dia + calor extremo também não superam o clima
(pareado: soja +11,8 [0,2; 25,9], milho +60,6 [0,0; 133,2], ambos piores).

---

## 11. Resultados por cultura

### Soja
Nenhuma especificação supera a média da UF em TE de forma significativa. A
janela corrigida move o ponto estimado de −6,3 para −18,5, mas o IC inclui zero
e o pareado é n.s. O único ganho relevante por UF é PR (−61,8). Não há base para
dizer que o clima prevê soja neste protocolo.

### Milho
O clima corrigido supera M1 (−228,5 [−403,5; −37,0]) e o pareado contra a janela
histórica é significativo (−29,8). Mas o efeito é **regionalmente concentrado**:
PR −607,4, BA −131,1, GO −109,9, MT +85,0, MS +261,4, RS +12,8.

### Milho 2ª safra
O clima supera M1 (−228,4 [−374,0; −11,0]), mas o pareado contra a janela
histórica **não** é significativo e aponta na direção contrária (+38,8): a
correção da janela não melhorou a 2ª safra. O ganho continua concentrado em PR
(−366,1). A profundidade radicular permanece cenário explícito (D99).

---

## 12. Tendência espacial (M3/M4)

Modelos: M3 = lat/lon + termos quadráticos + dummies de UF; M4 = M3 + clima
corrigido. Coordenadas centradas por **constantes fixas** (lat+20, lon+50) e
quadráticos divididos por 10 — transformações que não usam a amostra, logo sem
vazamento. Complexidade fixada **antes** da avaliação.

| Cultura | M3 vs M1 | M3 vs M2 (pareado) | M4 vs M3 (pareado) |
|---|---:|---:|---:|
| soja | +2,8 [−21,1; 29,2] n.s. | +21,3 [−16,7; 52,4] n.s. | −18,6 [−41,3; 15,0] n.s. |
| milho | +159,6 [−53,0; 364,4] n.s. | **+388,1** [62,0; 719,5] | **−175,7** [−318,2; −33,2] |
| milho 2ª | −49,7 [−175,3; 215,9] n.s. | **+178,7** [43,8; 342,7] | **−131,5** [−265,5; −39,0] |

**Rejeitada (D102).** No milho a tendência é pior que o clima: em PR, onde o
clima ganhava −607,4, M3 perde +256,9. Um plano inclinado global não descreve a
estrutura regional do milho — ela é por UF/grupo de UFs, não um gradiente.

Observação de interpretação: M4 vs M3 não deve ser lido como "o clima ajuda",
porque M3 é um modelo ruim e o ganho de M4 é apenas o retorno ao nível de M2. A
comparação que responde à pergunta científica é M2 vs M1 (§10).

---

## 13. Vizinhos históricos (M1c)

Desenho: para cada célula bloco × grupo temporal do TE, o treino exclui **o
bloco** e **o ano** do teste. A previsão de um município não observado é a média
das produtividades **de treino** dos municípios vizinhos, ponderada por
`exp(−(d/decaimento)²)`. Fallback: média da UF calculada no treino → média
global. Grade fixada antes da avaliação.

| Cultura | configuração | MAE M1c | MAE M1 | delta | cobertura | fallback |
|---|---|---:|---:|---:|---:|---:|
| soja | r200/d100/k3 | 583,0 | 610,7 | **−27,7** [−52,3; −3,8] | 0,987 | 0,013 |
| soja | r100/d50/k3 | 590,0 | 610,7 | **−20,7** [−40,9; −1,1] | 0,667 | 0,333 |
| soja | r300/d150/k3 | 589,6 | 610,7 | −21,1 [−48,2; 7,3] | 1,000 | 0,000 |
| milho | r200/d100/k3 | 1.624,5 | 1.917,1 | −292,6 [−631,0; 4,1] | 0,961 | 0,039 |
| milho | r300/d150/k3 | 1.667,3 | 1.917,1 | −249,8 [−545,4; 1,8] | 0,999 | 0,001 |
| milho | r100/d50/k3 | 1.791,3 | 1.917,1 | **−125,8** [−245,7; −10,7] | 0,454 | 0,546 |
| milho 2ª | r300/d150/k3 | 1.311,3 | 1.500,8 | **−189,6** [−312,5; −11,7] | 1,000 | 0,000 |
| milho 2ª | r200/d100/k3 | 1.306,3 | 1.500,8 | −194,5 [−377,7; 24,2] | 0,963 | 0,037 |

**Aprovado com ressalvas (D103).** O ganho existe, mas depende do raio e da
cobertura; em raios pequenos o baseline degenera na média da UF (fallback 55%
no milho com r100). A comparação com o modelo climático **não** é pareada
(conjuntos de linhas diferentes) e não é usada como evidência.

Controle de vazamento: teste dedicado que altera o `y` de **uma única linha** e
verifica que a sua previsão não muda. Também testado: cobertura nula → fallback
100%; reprodutibilidade bit a bit com a mesma semente; blocos insuficientes →
`insufficient_groups`.

---

## 14. Efeito espacial do milho

O "efeito do bloco" é o contraste **SS − SE** do fatorial (mesmo tempo, espaço
compartilhado vs espaço separado): quanto o erro piora quando o município de
teste não está no treino. É uma diferença de MAE em kg/ha, **não** um
coeficiente de regressão.

Recomputado com a janela corrigida, nas mesmas células e mesmas linhas:

| especificação (milho) | efeito do espaço (modelo) | IC95% | baseline (M1) |
|---|---:|---|---:|
| clima, janela histórica | −170,8 | [−330,6; −32,4] | −103,0 |
| clima, janela corrigida | −161,2 | [−301,4; −30,7] | −103,0 |
| déficit, CAD 0–60 | −206,6 | [−328,2; −75,1] | −103,0 |
| déficit, CAD 0–100 | **−225,4** | [−371,3; −77,8] | −103,0 |
| déficit, CAD 0–200 | **−286,1** | [−512,3; −65,0] | −103,0 |

Duas verificações importantes:

1. **CAD 0–100 (−225,4) e CAD 0–200 (−286,1) reproduzem exatamente os valores
   publicados na V3.0**, o que confirma que a cadeia de reconstrução é fiel e
   que D98 se sustenta com os dados corrigidos.
2. O valor "histórico −209,5" da tabela da V3.0 corresponde à especificação de
   **déficit histórico**, não ao clima (precipitação + temperatura), que aqui é
   −170,8. As duas linhas não devem ser fundidas.

Leitura: a correção da janela **reduz levemente** o efeito espacial do clima
(−170,8 → −161,2) e **não** altera o padrão central — o efeito do bloco
**cresce** com a profundidade da CAD. Ou seja, a CAD não explica a
heterogeneidade espacial do milho, e a janela corrigida não muda essa conclusão.

As demais culturas, para contexto:

| Cultura | clima histórico | clima corrigido | déficit CAD 0–100 |
|---|---:|---:|---:|
| soja | −6,6 [−15,2; 2,5] | −8,1 [−16,5; 2,2] | −2,4 [−9,1; 5,2] |
| milho | −170,8 [−330,6; −32,4] | −161,2 [−301,4; −30,7] | −225,4 [−371,3; −77,8] |
| milho 2ª | −42,0 [−74,0; 2,0] | −56,2 [−105,9; 4,3] | −110,6 [−212,1; 8,4] |

A decomposição por UF (§15) é a informação mais direta sobre a estrutura: a
heterogeneidade não é um "efeito de bloco" residual a ser explicado por solo —
é **diferença de relação clima–produtividade entre regiões**. A tendência
espacial não captura isso (§12); os vizinhos históricos capturam parte (§13),
porque codificam persistência regional de nível.

Isso é consistente com D98 e classifica a heterogeneidade como **não explicada
por CAD nem por gradiente geográfico suave**, e **parcialmente capturada por
persistência espacial histórica**.

---

## 15. Resultado por UF

Diferença de MAE do modelo contra a média da UF, TE (negativo = modelo melhor):

| UF | n (milho) | milho clima corrigido | milho M3 (tendência) |
|---|---:|---:|---:|
| PR | 2.966 | **−607,4** | +256,9 |
| BA | 106 | −131,1 | −133,4 |
| GO | 1.567 | −109,9 | +108,2 |
| MT | 997 | +85,0 | −37,1 |
| MS | 552 | +261,4 | +427,9 |
| RS | 1.428 | +12,8 | +69,2 |

| UF | n (soja) | soja clima corrigido |
|---|---:|---:|
| PR | 2.863 | **−61,8** |
| RS | 2.966 | −20,7 |
| MT | 911 | +17,7 |
| MS | 586 | +19,8 |
| GO | 1.558 | +29,6 |

BA tem 106 linhas — qualquer leitura por UF dessa magnitude é frágil e está
registrada como tal. Nenhuma UF é apresentada como "região validada".

---

## 16. Testes

| item | valor |
|---|---|
| testes offline | **393/393** |
| novos testes V3.1 | 21 |
| `compileall` | limpo |

Cobertura dos novos testes:

* **janela** — último mês incluído; virada dez/jan; mês único; ano bissexto
  (2020-02-29 vs 2021-02-28); janela vazia; meses em branco; determinismo;
  contagem de dias igual à soma dos meses listados; semântica histórica
  descartando o último mês;
* **agregação** — soma de precipitação; graus-dia com perfil e cobertura;
  valores ausentes não quebram a cobertura; calor extremo por dia; balanço
  sequencial limitado pela CAD; déficit maior com CAD menor; diário↔mensal;
* **espacial** — Haversine contra distância conhecida (111,19 km para 1° no
  equador); ausência de vazamento do próprio `y`; fallback 100% quando não há
  vizinho; reprodutibilidade; blocos insuficientes.

Os testes não dependem de WCS, APIs ou arquivos derivados: usam fixtures
determinísticas.

---

## 17. Fontes

| fonte | uso | situação |
|---|---|---|
| NASA POWER | clima diário | inalterada |
| IBGE/SIDRA (PAM) | produtividade municipal | inalterada |
| MAPA/ZARC | janela de semeadura, `Cod_Ciclo`, `Cod_Solo` | inalterada |
| Embrapa Solos (GeoInfo/WCS) | CAD por profundidade | adquirida na V3.0, reutilizada |
| Embrapa Soja / Milho e Sorgo | profundidade radicular (D99) | inalterada |
| FAO-56 | ET0 Penman-Monteith | inalterada |
| ERA5-Land | — | **bloqueada** (sem credencial CDS) |
| CHIRPS / ARCO | — | **bloqueada** (DNS) |

CAD: licença CC BY-NC 3.0 BR. Rasters não versionados nem redistribuídos;
apenas estatísticas derivadas, atribuição e metadados.

---

## 18. Decisões

* **D100** — contrato temporal único; janela corrigida é o padrão; semântica
  histórica preservada só para reprodução.
* **D101** — a janela corrigida fortalece o clima no milho (−29,8 pareado) e não
  resgata a soja; ganho concentrado em PR.
* **D102** — tendência espacial (M3/M4) rejeitada em TE.
* **D103** — vizinhos históricos (M1c) superam a média da UF, com cobertura e
  fallback declarados; baseline experimental, não substituto do clima.

---

## 19. Limitações

1. **Cobertura** — 5–6 UFs de 27. Nenhuma generalização nacional.
2. **Janela ZARC ≠ fenologia** — graus-dia acumulados na janela de semeadura não
   são graus-dia até maturação. Aproximação declarada, não corrigida.
3. **CAD** — a profundidade efetiva é cenário (D99), não medição. Os rasters não
   foram reprocessados com o novo recorte municipal além do que a V3.0 fez.
4. **Inclinação comum** — M0–M4 impõem a mesma inclinação climática a todas as
   UFs. A V3.1 **documenta** a heterogeneidade (§15) mas não estima um modelo
   com inclinação heterogênea. Essa é a lacuna explícita.
5. **M1c** — escolha de raio/decaimento não foi otimizada dentro do treino; a
   grade foi fixada e reportada integralmente. A comparação M1c vs M2 não é
   pareada.
6. **Multiplicidade** — as famílias de hipóteses não foram expandidas na V3.1;
   os ICs reportados são individuais. Nenhum resultado é apresentado como
   confirmatório além dos pré-registrados (M2 vs M1 por cultura).
7. **Associação, não causalidade** — em nenhum ponto um ganho preditivo é
   interpretado como efeito causal do clima sobre a produtividade.

---

## 20. Pendências

| item | estado |
|---|---|
| inclinação climática heterogênea por UF | **não testada** — prioridade 1 da V3.2 |
| seleção de vizinhança por validação interna | não feita — prioridade 2 |
| janela fenológica separada | não feita — prioridade 3 |
| expansão de cobertura | diagnóstico não solicitado — prioridade 4 |
| ERA5-Land / CHIRPS | bloqueados |
| NDVI como preditor | não reaberto |

---

## 21. Recomendações para V3.2

1. **Modelo hierárquico de inclinação** (intercepto e inclinação por UF com
   encolhimento), selecionando hiperparâmetros **somente no treino**, comparado
   de forma pareada com M1 e M2 nas mesmas linhas. É a hipótese que a V3.1
   levanta e deliberadamente não testa.
2. **Escolha da vizinhança por validação interna**, reportando a curva
   cobertura × erro; e um contraste pareado M1c vs M2.
3. **Janela fenológica como cenário**, se e quando houver datas de plantio e
   colheita observadas — sem substituir a janela ZARC.
4. **Manter** a regra de que qualquer alegação de generalização vem do TE e que
   M1b nunca é baseline operacional.

---

## Classificação das evidências

| achado | classificação |
|---|---|
| D97 é um mês inteiro por janela, não um dia | **validado** (reprodução exata + testes) |
| todas as variáveis acumuladas da janela estavam ~44% menores | **validado** (19.402 linhas, 20 variáveis) |
| janela corrigida melhora o clima no milho | **validado nos protocolos avaliados** (TE, equalização por célula) |
| ganho do milho concentrado em PR | **validado nos protocolos avaliados**, com n frágil em BA |
| janela corrigida não resgata a soja | **validado nos protocolos avaliados** (n.s. em todos os testes) |
| CAD não agrega valor preditivo | **validado nos protocolos avaliados** (D98 confirmada) |
| tendência espacial não ajuda | **validado nos protocolos avaliados** (rejeitada) |
| vizinhos históricos superam a UF | **validado nos protocolos avaliados**, dependente de cobertura |
| mecanismo da heterogeneidade do milho | **não conclusivo** — não é CAD, não é gradiente suave; é diferença regional de inclinação |
| generalização nacional | **não avaliado** — 5–6 UFs de 27 |
