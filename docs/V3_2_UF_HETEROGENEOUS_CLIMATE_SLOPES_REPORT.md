# SADEN V3.2 — Inclinações climáticas heterogêneas por UF

**Branch:** `v3/uf-heterogeneous-climate-slopes`
**Base:** `345b22e` (V3.1)
**Data:** 2026-11-14
**Protocolo de generalização:** TE (espaço e tempo separados simultaneamente)

---

## 1. Resumo executivo

Pergunta: a sensibilidade da produtividade às variáveis agroclimáticas difere o
suficiente entre UFs para justificar inclinações por estado — e isso melhora a
generalização?

**Resposta curta: não, com uma exceção frágil, e uma correção metodológica
importante no caminho.**

1. A heterogeneidade de inclinações **não está estabelecida**. Na família
   confirmatória de 6 testes globais (3 culturas × 2 variáveis, Holm), apenas
   **milho 2ª × temperatura** sobrevive (p = 0,0019; Holm = 0,0113). Sobra 1 de
   6. Nenhum contraste individual por UF sobrevive ao Holm em nenhuma cultura.
2. O achado metodológico mais importante: **a inferência por bloco espacial
   usada nas versões anteriores é otimista**. A anomalia climática varia na
   unidade UF×ano, não no bloco de 250 km. Trocando o agrupamento para
   UF×ano + município, a estatística F da soja cai de 8,74 (p ≈ 0) para 1,13
   (p = 0,36) — erros-padrão ~2,8× maiores. Isso **qualifica
   retroativamente** os p-valores de associação da V2.7–V3.1 (D104).
3. Os desníveis por UF da V3.1 (PR −607,4; MS +261,4) **não** são inclinações
   diferentes. São diferenças de erro preditivo. A leitura mecanicista deles não
   se sustenta (D105).
4. Ganho preditivo: só no **milho** e só com partial pooling (−77,6 kg/ha de
   MAE, IC UF×ano [−143,9; −4,8]; IC por bloco [−162,7; 14,5]). Mas o ganho é
   **localizado** — forte em PR (−206) e BA (−223), e **negativo em RS**
   (+112) — e o sinal se inverte em 5 de 6 análises leave-one-UF-out. Classificado
   como **Nível C** (D107, §16).
5. Soja: **Nível D**. Milho 2ª: **Nível B** (heterogeneidade estatística, sem
   ganho preditivo).
6. M1c (vizinhos históricos) bate M1, mas **não** bate M2 em nenhuma cultura
   com pareamento por município-ano. Continua baseline secundário.

---

## 2. Pergunta científica

Três fenômenos que não foram confundidos:

| # | fenômeno | como foi medido |
|---|---|---|
| 1 | produtividade média diferente entre UFs | intercepto estadual (M1, M2) |
| 2 | distribuição climática diferente entre UFs | suporte e dispersão por UF (§6) |
| 3 | **inclinação clima–produtividade diferente** | interações UF × clima (§9) |

Uma UF pode ter produtividade média menor sem maior sensibilidade ao clima. A
V3.1 mediu (1) e o desempenho preditivo por UF; **não** mediu (3). A V3.2 mede
(3).

---

## 3. Histórico do projeto

* V1/V1.1 — previsão de preços (Ridge, Node/Express), congelada em `3f7ad33`.
* V2.2–V2.9 — painel agroclimático, protocolos de validação espacial e temporal,
  equalização amostral, CAD, inferência robusta.
* V3.0 — CAD completa (1.296 municípios) e descoberta da falha de janela (D97).
* V3.1 — reconstrução de **todas** as variáveis de janela: o painel perdia **um
  mês inteiro** por janela, não um dia; as variáveis acumuladas eram ~44%
  menores (D100). Resultado em TE: milho −228,5; soja n.s.; milho 2ª −228,4.
  Tendência espacial rejeitada (D102); vizinhos históricos promissores (D103).
* V3.2 (esta) — investiga a hipótese deixada como prioridade 1 da V3.1:
  inclinações heterogêneas por UF.

## 4. Correção temporal utilizada

Todas as análises usam **somente** colunas `_corrected` (D100): meses completos,
primeiro dia do primeiro mês ao último dia do último mês. Nenhuma variável
`_legacy` entra em nenhum modelo — há um teste de regressão que falha se o texto
das ferramentas V3.2 mencionar `_legacy`.

A auditoria confirmou que as 20 variáveis por janela usam o contrato corrigido; a
reprodução da semântica histórica continua disponível apenas para comparação
(V3.1, §4.3 daquele relatório).

## 5. Dados e fontes

| fonte | uso | versão |
|---|---|---|
| NASA POWER | clima diário | inalterada |
| IBGE/SIDRA (PAM) | produtividade municipal | inalterada |
| MAPA/ZARC | janela de semeadura, `Cod_Ciclo`, `Cod_Solo` | inalterada |
| Embrapa Solos (GeoInfo/WCS) | CAD por profundidade | adquirida na V3.0 |
| Embrapa Soja / Milho e Sorgo | profundidade radicular (D99) | inalterada |
| FAO-56 | ET0 Penman-Monteith | inalterada |
| ERA5-Land | — | **bloqueada** (sem credencial CDS) |
| CHIRPS/ARCO | — | **bloqueada** (DNS) |

Painel: 19.402 linhas, 1.296 municípios, 5–6 UFs, 46 blocos espaciais (250 km).

## 6. Cobertura e identificabilidade por cultura e UF

Diagnóstico completo em `v32_coverage_diagnostics.json`. Resumo:

| cultura | UF | linhas | municípios | anos | blocos | sd precip | variação within (precip) | sd temp | within (temp) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| soja | GO | 1.558 | 210 | 8 | 11 | 161,2 | 89% | 1,67 | 57% |
| soja | MS | 586 | 77 | 8 | 9 | 137,4 | 62% | 1,90 | 51% |
| soja | MT | 911 | 120 | 8 | 17 | 237,1 | 78% | 1,57 | 51% |
| soja | PR | 2.863 | 389 | 8 | 7 | 192,9 | 74% | 2,33 | 17% |
| soja | RS | 2.966 | 429 | 8 | 8 | 284,6 | 84% | 1,36 | 24% |
| milho | BA | 106 | 31 | 8 | 8 | 162,0 | 56% | 1,13 | 56% |
| milho | GO | 1.567 | 208 | 8 | 11 | 138,9 | 89% | 1,66 | 56% |
| milho | MS | 552 | 76 | 8 | 9 | 147,1 | 77% | 2,12 | 49% |
| milho | MT | 997 | 125 | 8 | 17 | 194,3 | 78% | 1,79 | 65% |
| milho | PR | 2.966 | 391 | 8 | 7 | 170,3 | 71% | 2,37 | 23% |
| milho | RS | 1.428 | 232 | 8 | 5 | 330,6 | 84% | 1,43 | 29% |
| milho 2ª | GO | 285 | 57 | **5** | 7 | 112,5 | 88% | 0,98 | 63% |
| milho 2ª | MS | 428 | 73 | 9 | 9 | 172,5 | 58% | 1,67 | 50% |
| milho 2ª | MT | 353 | 69 | 9 | 14 | 116,6 | 65% | 1,18 | 51% |
| milho 2ª | PR | 1.836 | 306 | 9 | 6 | 140,5 | 58% | 1,78 | 26% |

Classificação adotada **antes** de interpretar (critérios: linhas, anos,
municípios, fração within):

| classe | critério | UFs |
|---|---|---|
| elegível | n ≥ 400, ≥ 6 anos, ≥ 50 municípios, within ≥ 30% | todas as demais |
| elegível com ressalvas | n < 400 ou anos < 6 | milho 2ª **GO** (285 linhas, 5 anos) |
| apenas partial pooling | n < 200 | milho **BA** (106 linhas) |
| não estimável | n < 100 ou anos < 3 ou within < 5% | nenhuma |

Observações relevantes: a variação within de temperatura em PR é apenas 17–26%
da variância total — quase toda a dispersão de temperatura em PR é **entre**
municípios, e o modelo *within* descarta essa parte. Isso reduz drasticamente a
informação disponível para estimar a inclinação de temperatura em PR, o que
importa para ler os resultados de §9.

## 7. Pré-registro

`docs/V3_2_PREREGISTRATION.md`, escrito antes de qualquer estimativa, fixa:
hipóteses H0–H3, especificação primária (a mesma da V3.1: precipitação +
temperatura corrigidas + dummies de UF), estimandos, protocolos, esquema de
inferência, as três famílias de multiplicidade, a grade de encolhimento, a
robustez pré-especificada e **a regra de decisão dos níveis A–D**.

Nenhum desvio foi necessário. Um ajuste de desenho foi feito **antes** de ver
qualquer resultado de heterogeneidade, ao constatar que as anomalias de
precipitação e temperatura são correlacionadas (−0,60 a −0,67 within): a
especificação primária passou a incluir **as duas variáveis simultaneamente**
em vez de uma por vez. Uma variável sozinha capturaria o efeito da outra. Os
modelos com uma variável por vez são reportados como sensibilidade e mostram
exatamente esse confundimento (§9.3).

## 8. Estimandos

**Associação.** Modelo *within* de dois fatores (município e ano), o mesmo da
V2.9/V3.0:

```
y_w = Σ_j b_j · x_jw + Σ_s Σ_j d_sj · (x_j · 1[UF = s])_w + e
```

`b_j` é a inclinação da UF de referência; `d_sj` é a **diferença** de inclinação
da UF `s`. Unidade: kg/ha por unidade da variável climática, líquido de
município e ano. **Não é** efeito causal.

**Predição.** MAE (kg/ha) no braço TE; `ΔMAE = MAE(modelo) − MAE(M2 comum)`;
negativo = modelo melhor. **Não é** efeito sobre produtividade.

## 9. Especificações e modelos comparados

| modelo | definição | papel |
|---|---|---|
| M0 | média nacional | baseline |
| M1 | média da UF (treino) | baseline principal |
| M1b | média UF×ano | diagnóstico, não operacional |
| M1c | vizinhos históricos | baseline secundário |
| M2 | precipitação + temperatura + dummies de UF | referência |
| M2-HET-FE | M2 + interações UF × clima, MQO | inclinações livres |
| M2-HET-PP | idem com ridge sobre os desvios estaduais | partial pooling |

Todos com `equalize="per_cell"`, 25 células (5 blocos × 5 grupos temporais), 3
repetições, semente `20261114`. **M2 comum reproduz a V3.1 exatamente** — soja
592,19, milho 1.688,58, milho 2ª 1.272,40 — o que prova que as linhas de teste
são as mesmas e a comparação é pareada.

### 9.1. Partial pooling (D106)

Ridge sobre os desvios estaduais, penalidade relativa à diagonal de Gram
(encolhimento `1/(1+λ)`), λ escolhido por validação interna 5-fold **bloqueada
por bloco, dentro do pool de treino de cada célula**. Com 4–6 UFs, um modelo
hierárquico completo não é identificável; isto é o MAP de um prior normal
centrado em zero, e **não** fornece IC que incorporem a incerteza do
encolhimento. Limitação declarada.

### 9.2. Seleção de complexidade sem vazamento

A complexidade é a escolha de λ, feita dentro do treino. O caminho completo de λ
é reportado (§13). Nenhuma especificação foi escolhida pelo resultado em TE.

### 9.3. Sensibilidade à colinearidade

| cultura | corr within (precip, temp) |
|---|---:|
| soja | −0,602 |
| milho | −0,670 |
| milho 2ª | −0,668 |

Consequência: no modelo com **uma** variável, a temperatura funciona como proxy
de água. Exemplo (soja): precipitação sozinha p = 0,968; temperatura sozinha
p = 0,820; as duas juntas p = 0,357 e 0,131. Nenhuma conclusão da V3.2 se apoia
em modelo de variável única.

## 10. Validação

| protocolo | papel | configuração |
|---|---|---|
| **TE** | referência de generalização | bloco e grupo temporal do teste fora do treino |
| SE (territorial) | diagnóstico | outros blocos, tempo compartilhado |
| TS (temporal) | diagnóstico | outros anos, espaço compartilhado |
| SS | referência interna | nada separado |
| equalização | obrigatória | por célula, todas as células no alvo |

Nenhum ganho em SS/SE/TS é usado como alegação de generalização (D91).

## 11. Inferência

Agrupamento **duplo** (D104): **UF×ano** e **município**, CR1, `F(q, G−1)` no
teste global e `t` com `G−1` nos contrastes. `G` é 32–48 clusters UF×ano, não o
número de UFs: **4–6 UFs não são clusters suficientes** para qualquer
aproximação assintótica no nível estadual, e é por isso que o teste global é
sobre as interações (com dezenas de clusters UF×ano), não sobre "diferenças entre
estados" tratadas como sorteio de estados.

Para as diferenças de MAE, o IC usa bootstrap de bloco **e** bootstrap por
UF×ano; os dois são reportados sempre.

## 12. Multiplicidade

| família | tamanho | procedimento | resultado |
|---|---:|---|---|
| confirmatória (teste global) | 6 | Holm, α = 0,05 | **1 rejeição** |
| secundária (contrastes por UF) | 8 / 10 / 6 | Holm na cultura | **0 rejeições** |
| exploratória (graus-dia, calor, déficit CAD) | 9 | Benjamini–Hochberg | **3 rejeições, todas em milho** |

Exploratória, detalhe (modelos de **uma** variável, ver a ressalva abaixo):

| cultura | variável | p | BH | |
|---|---|---:|---:|---|
| milho | déficit CAD 0–100 | 0,00024 | **0,0021** | rejeita |
| milho | graus-dia | 0,00095 | **0,0043** | rejeita |
| milho | calor extremo | 0,00608 | **0,0183** | rejeita |
| milho 2ª | calor extremo | 0,03401 | 0,0765 | n.s. |
| milho 2ª | graus-dia | 0,13732 | 0,2123 | n.s. |
| milho 2ª | déficit CAD 0–100 | 0,58708 | 0,5871 | n.s. |
| soja | graus-dia | 0,14155 | 0,2123 | n.s. |
| soja | calor extremo | 0,21132 | 0,2717 | n.s. |
| soja | déficit CAD 0–100 | 0,29859 | 0,3359 | n.s. |

**Ressalva obrigatória:** cada linha dessa família vem de um modelo com **uma
única** variável climática. Como as anomalias são correlacionadas (§9.3), essas
rejeições não são independentes das de precipitação/temperatura e não
estabelecem heterogeneidade *daquela* variável. O padrão — milho rejeita em
déficit, graus-dia e calor, mas não em precipitação/temperatura bruta — é
sugestivo de que a forma funcional importa mais que a variável bruta, e fica
registrado como hipótese para a V3.3, não como achado.

## 13. Resultados globais

### 13.1. Teste de heterogeneidade (família confirmatória)

| cultura | variável | F | df | p | **Holm** | decisão |
|---|---|---:|---|---:|---:|---|
| soja | precipitação | 1,13 | (4; 39) | 0,357 | 0,713 | n.s. |
| soja | temperatura | 1,89 | (4; 39) | 0,131 | 0,392 | n.s. |
| milho | precipitação | 1,03 | (5; 47) | 0,410 | 0,713 | n.s. |
| milho | temperatura | 2,47 | (5; 47) | 0,045 | 0,227 | n.s. |
| milho 2ª | precipitação | 2,77 | (3; 31) | 0,058 | 0,234 | n.s. |
| milho 2ª | temperatura | 6,27 | (3; 31) | **0,0019** | **0,0113** | **rejeita H0** |

### 13.2. O mesmo teste sob agrupamento por bloco (sensibilidade, D104)

| cultura | variável | F (bloco) | p (bloco) | p (UF×ano) |
|---|---|---:|---:|---:|
| soja | precipitação | 8,74 | 0,0000 | 0,357 |
| soja | temperatura | 10,33 | 0,0000 | 0,131 |
| milho | precipitação | 2,28 | 0,061 | 0,410 |
| milho | temperatura | 4,89 | 0,001 | 0,045 |
| milho 2ª | precipitação | 3,30 | 0,034 | 0,058 |
| milho 2ª | temperatura | 10,05 | 0,0001 | 0,0019 |

Se a V3.2 tivesse mantido o agrupamento histórico, teria concluído
"heterogeneidade confirmada em 5 de 6 casos". A conclusão correta é 1 de 6.

### 13.3. Comparação preditiva em TE

| cultura | M1 | M2 comum | M2-HET-FE | M2-HET-PP | PP − comum (bloco) | PP − comum (UF×ano) |
|---|---:|---:|---:|---:|---|---|
| soja | 610,7 | **592,2** | 599,0 | 603,1 | +10,9 [−3,9; 30,6] | +10,9 [−9,2; 36,2] |
| milho | 1.917,1 | 1.688,6 | **1.578,3** | 1.610,9 | −77,6 [−162,7; 14,5] | **−77,6 [−143,9; −4,8]** |
| milho 2ª | 1.500,8 | **1.272,4** | 1.285,0 | 1.278,5 | +6,1 [−11,1; 21,6] | +6,1 [−10,7; 24,0] |

Todas as MAE em kg/ha. Leitura: em soja e milho 2ª o modelo com inclinações
comuns é o melhor. Em milho, o partial pooling ganha, mas só sob o bootstrap
UF×ano e com IC por bloco incluindo zero.

## 14. Resultados por cultura

### 14.1. Soja — Nível D

Nenhum teste global sobrevive. Nenhuma especificação heterogênea melhora a
previsão: FE +6,9, PP +10,9. Os quatro contrastes de temperatura por UF têm
p individual entre 0,029 e 0,050 (MS −248,8; MT −199,6; PR −234,8; RS −362,1) e
**todos** caem após Holm (0,23–0,29). É o caso que ilustra por que uma tabela de
p-valores estaduais não é evidência: quatro "significâncias" individuais que
nenhuma correção de multiplicidade sustenta.

Exploratório (BH, modelos de uma variável): em soja nenhuma das três variáveis
rejeita. Em milho, **déficit com CAD 0–100 (BH 0,0021), graus-dia (0,0043) e
calor extremo (0,0183)** rejeitam. Em milho 2ª, nenhuma sobrevive. Como são
especificações de variável única e as anomalias climáticas são correlacionadas,
essas rejeições **não** identificam a variável responsável — apenas mostram que
no milho a heterogeneidade aparece mais claramente em variáveis derivadas
(hídrica e térmica acumulada) que nas brutas. Hipótese para a V3.3, não achado.

### 14.2. Milho — Nível C

Teste global: precipitação 0,410; temperatura 0,045 → Holm 0,227. **Não** se
estabelece heterogeneidade de inclinação. Ainda assim, o partial pooling melhora
a previsão em TE (−77,6; IC UF×ano exclui zero), e o ganho é **localizado**:

| UF | M2 comum | M2-HET-FE | M2-HET-PP | ΔMAE (PP) |
|---|---:|---:|---:|---:|
| PR | 1.862,7 | 1.522,5 | 1.656,3 | **−206,4** |
| BA | 3.642,6 | 3.323,8 | 3.419,4 | **−223,2** |
| MT | 1.042,0 | 982,9 | 985,2 | −56,8 |
| GO | 1.046,9 | 1.006,0 | 1.016,0 | −30,9 |
| MS | 1.578,7 | 1.555,7 | 1.559,2 | −19,5 |
| RS | 2.380,0 | 2.617,0 | 2.492,3 | **+112,3** |

Ganha em cinco UFs e **perde** em RS. Não é um ganho geral; é um ganho regional
com uma perda regional. A leitura correta é "as inclinações não são iguais o
bastante para a inclinação comum ser ótima em toda parte", não "o clima afeta o
milho de forma diferente por UF, causalmente".

### 14.3. Milho 2ª safra — Nível B

Única rejeição confirmatória (temperatura, Holm 0,0113), mas **sem ganho
preditivo**: FE +12,6, PP +6,1, pior em GO/MT/MS e neutro em PR. As inclinações
estimadas são implausíveis em magnitude (GO +856 kg/ha/°C, referência com 285
linhas e 5 anos) e os contrastes individuais não sobrevivem (p_holm ≥ 0,195).

Heterogeneidade estatística aparente + ausência de utilidade preditiva = Nível B,
com a ressalva de que a estimativa é frágil e GO está no limite de
identificabilidade.

## 15. Resultados por UF

Inclinações implícitas (modelo conjunto, *within* de município e ano):

**Soja — precipitação (kg/ha por mm):** GO 1,76 · RS 0,92 · MT 0,70 · PR 0,38 ·
MS 0,10. **Temperatura (kg/ha por °C):** GO +70,3 · MT −129,3 · PR −164,5 ·
MS −178,6 · RS −291,9.

**Milho — precipitação:** PR 0,77 · RS 0,73 · BA 0,62 · MT 0,41 · MS −1,67 ·
GO −1,82. **Temperatura:** MT −5,7 · BA −23,7 · RS −62,9 · PR −227,1 ·
MS −382,2 · GO −382,8.

**Milho 2ª — precipitação:** GO 9,02 · MT 0,56 · MS 0,00 · PR −1,37.
**Temperatura:** GO +856,4 · MT +194,8 · MS −138,5 · PR −299,7.

Nenhum contraste individual sobrevive ao Holm. As magnitudes de milho
2ª/temperatura são implausíveis e devem ser lidas como imprecisão, não como
mecanismo. Note também que os sinais de precipitação em milho (MS e GO negativos)
contrariam a expectativa agronômica — mais um sinal de que estes coeficientes
*within* capturam, em boa parte, anos atípicos comuns, não uma resposta
agronômica estável.

## 16. Robustez

### 16.1. Leave-one-UF-out (ΔMAE PP − comum, milho)

| UF removida | ΔMAE | sinal |
|---|---:|---|
| BA | +36,3 | inverte |
| GO | −14,8 | mantém (fraco) |
| MS | +5,2 | inverte |
| MT | +2,9 | inverte |
| PR | +74,2 | inverte |
| RS | −46,8 | mantém |

O ganho agregado de −77,6 **não** sobrevive à remoção de uma UF em 4 de 6 casos.
Isso reprova o critério pré-registrado para o Nível A e é a razão principal da
classificação em Nível C.

### 16.2. Leave-one-year-out (milho)

ΔMAE entre −28,5 e −111,3 em todos os 8 anos: o ganho **não** depende de um ano
específico. É a única dimensão em que ele é estável.

### 16.3. Caminho de λ (milho, TE)

| λ fixo | ΔMAE |
|---|---:|
| 0,1 | −15,4 |
| 1,0 | −3,4 |
| 10,0 | −0,4 |
| por célula (PP) | −77,6 |

O caminho não é monótono em relação ao PP porque a seleção por célula escolhe
λ = 0 em 18 de 25 células e λ = 100 em 4. A seleção é empírica e o resultado é
sensível a ela — reportado como instabilidade, não como descoberta.

### 16.4. Composição da amostra

O diagnóstico de identificabilidade (§6) já mostra o problema de composição: PR
tem 17–26% de variação *within* de temperatura e 389–391 municípios, enquanto BA
tem 106 linhas. Excluir BA do milho **aumenta** o ganho aparente (+36,3 quando
removida — ou seja, BA puxa o ganho para cima), o que reforça que o resultado é
sensível à composição territorial.

## 17. Comparação com M1c

Pareamento por (município, ano), todos os casos:

| cultura | cobertura | MAE M1c | MAE M1 | M1c − M1 (UF×ano) | MAE M2 | M1c − M2 (UF×ano) |
|---|---:|---:|---:|---|---:|---|
| soja | 0,987 | 583,0 | 610,7 | **−27,7 [−46,2; −8,1]** | 592,2 | −9,2 [−49,2; 25,6] |
| milho | 0,961 | 1.624,4 | 1.917,1 | **−292,6 [−401,2; −169,3]** | 1.688,6 | −64,1 [−146,1; 2,9] |
| milho 2ª | 0,963 | 1.306,3 | 1.500,8 | **−194,5 [−311,5; −63,9]** | 1.272,4 | +33,9 [−85,6; 162,4] |

Decomposição cobertura × fallback (milho, raio 200 km):

| subconjunto | n | MAE M1c | MAE M1 (no subconjunto) |
|---|---:|---:|---:|
| atendido por vizinhos | 7.318 | 1.604,9 | 1.909,5 |
| caiu no fallback (média da UF) | 298 | 2.103,5 | — |
| raio 100 km: fallback | 4.156 (55%) | 2.018,2 | — |

Conclusões: M1c bate M1 consistentemente; **não** bate M2 em nenhuma cultura; e
o fallback atende casos muito mais difíceis — a cobertura agregada esconde isso.
Escolher raio pequeno "melhora" a cobertura declarada e degrada o baseline.

## 18. Limitações

1. **4–6 UFs.** Não é possível estimar variância entre efeitos aleatórios nem
   tratar os estados como amostra de uma população de estados. O teste global
   usa clusters UF×ano; contrastes estaduais são descritivos.
2. **Partial pooling é ridge, não hierárquico completo.** Sem REML, sem IC que
   propaguem a incerteza de λ.
3. **Cobertura territorial** de 5–6 UFs de 27; nenhuma generalização nacional.
4. **Variância within baixa para temperatura em PR/RS** (17–29%): parte da
   informação sobre temperatura é descartada pelo *within*, o que pode explicar
   por que a heterogeneidade de temperatura é mais difícil de estimar do que
   aparenta nos testes.
5. **Coeficientes within não são causais** e, para o milho, alguns sinais
   contrariam a agronomia — provável contaminação por anos atípicos comuns.
6. **Janela ZARC ≠ fenologia** (mantido da V3.1): graus-dia na janela de
   semeadura não é graus-dia até maturação.
7. **Multiplicidade**: apenas 6 testes confirmatórios; as famílias secundária e
   exploratória são exploratórias por definição.

## 19. Decisões

* **D104** — unidade de inferência de inclinações climáticas é UF×ano +
  município (agrupamento duplo), não bloco espacial; p-valores de associação
  anteriores são otimistas.
* **D105** — heterogeneidade de inclinações **não** está estabelecida; os
  desníveis por UF da V3.1 não são inclinações.
* **D106** — partial pooling = ridge sobre desvios estaduais, λ por célula no
  treino; limitações declaradas.
* **D107** — M1c não substitui M1 nem M2; fallback não é neutro.

## 20. Conclusão

A hipótese que a V3.1 deixou como prioridade 1 **não se sustenta** nos dados
disponíveis. A sensibilidade da produtividade às variáveis agroclimáticas não
difere entre UFs de forma estabelecida: 1 de 6 testes confirmatórios sobrevive à
correção de multiplicidade, nenhum contraste estadual sobrevive, e o único ganho
preditivo relevante (milho, partial pooling) é localizado, se inverte quando uma
UF é removida e não aparece sob o agrupamento histórico.

O resultado mais durável desta versão não é sobre o milho: é que **a inferência
por bloco espacial estava otimista para regressores que variam em UF×ano**. Isso
muda a força das alegações de associação de todas as versões anteriores, sem
mudar as alegações preditivas. O modelo com inclinações comuns (M2) continua
sendo a melhor escolha para soja e milho 2ª, e a escolha defensável para milho
quando se exige estabilidade.

## 21. Referências metodológicas

Adotadas efetivamente no desenho (não ornamentais):

1. **Cameron, A. C., & Miller, D. L. (2015).** *A Practitioner's Guide to
   Cluster-Robust Inference.* Journal of Human Resources, 50(2), 317–372.
   <https://jhr.uwpress.org/content/50/2/317>
   — Usado para: escolha do nível de agrupamento e advertência sobre poucos
   clusters. Aplicação no SADEN: motivou a D104; o guia trata explicitamente de
   regressores que variam no nível do cluster (aqui, UF×ano).
2. **Cameron, A. C., Gelbach, J. B., & Miller, D. L. (2008).**
   *Bootstrap-Based Improvements for Inference with Clustered Errors.* Review of
   Economics and Statistics, 90(3), 414–427.
   <https://direct.mit.edu/rest/article/90/3/414/57731>
   — Usado para: justificar o bootstrap por bloco/UF×ano como alternativa aos
   p-valores assintóticos com poucos clusters (já implementado na V2.7 como
   wild cluster bootstrap).
3. **Hastie, T., Tibshirani, R., & Friedman, J. (2009).** *The Elements of
   Statistical Learning* (2nd ed.). Springer.
   <https://doi.org/10.1007/978-0-387-84858-7>
   — Usado para: equivalência entre ridge e penalização de desvios, e a
   interpretação de λ como encolhimento; base da implementação de D106.

Nenhuma dessas referências é usada como evidência empírica sobre o SADEN. Elas
fundamentam o desenho; os números vêm do painel.

## 22. Reprodutibilidade

| artefato | caminho |
|---|---|
| diagnósticos de cobertura | `geospatial/data/manifests/v32_coverage_diagnostics.json` |
| testes de inclinação | `geospatial/data/manifests/v32_slope_tests.json` |
| comparação preditiva | `geospatial/data/manifests/v32_predictive.json` |
| robustez | `geospatial/data/manifests/v32_robustness.json` |
| M1c pareado | `geospatial/data/manifests/v32_neighbors_paired.json` |
| ferramentas | `tools/v32_slope_tests.py`, `tools/v32_predictive.py`, `tools/v32_neighbors.py` |
| módulo | `geospatial/agroclimate/heterogeneity.py` |
| testes | `geospatial/tests/test_v32_heterogeneity.py` |

Comandos:

```
python tools/v32_slope_tests.py
python tools/v32_predictive.py --stage main
python tools/v32_predictive.py --stage robustness
python tools/v32_neighbors.py
pytest geospatial/tests -q
```

Sementes: `20261114` (estimador), `20261114 + offsets` (por célula/braço, estáveis
por construção). Nenhum resultado depende de estado global mutável.

## 23. Classificação das evidências

| achado | classificação |
|---|---|
| painel corrigido usado em todas as análises, sem mistura com `_legacy` | **validado** (teste de regressão dedicado) |
| M2 comum reproduz a V3.1 exatamente; comparações pareadas | **validado** (592,19 / 1.688,58 / 1.272,40) |
| agrupamento por bloco é otimista para regressores UF×ano | **validado nos dados** (F 8,74 → 1,13 na soja) |
| heterogeneidade de inclinações em soja | **não conclusivo / nível D** |
| heterogeneidade de inclinações em milho | **não conclusivo** (Holm 0,227) |
| ganho preditivo do partial pooling em milho | **nível C** — localizado e instável |
| heterogeneidade em milho 2ª (temperatura) | **nível B** — estatística, sem ganho preditivo |
| M1c bate M1 / não bate M2 | **validado nos protocolos avaliados** |
| fallback do M1c é substancialmente pior | **validado** (decomposição) |
| mecanismo agronômico da heterogeneidade | **não testado** — nenhum mecanismo é proposto |
| generalização nacional | **não avaliado** — 5–6 UFs de 27 |

## 24. Desvios do pré-registro

Nenhum. O único ajuste (especificação conjunta das duas variáveis) foi feito
antes de observar qualquer resultado de heterogeneidade e está registrado em §7.
