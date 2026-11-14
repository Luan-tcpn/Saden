# SADEN V2.8 — Generalização temporal-espacial e linha de base

> Etapa V2.8. Documento de encerramento: o que foi reproduzido, o que foi
> decomposto, o que muda nas conclusões e o que fica pendente.
>
> Decisões: D87 (fatorial espaço × tempo), D88 (CAD no balanço hídrico),
> D89 (classes de ciclo do ZARC). Continuidade:
> `docs/execution/v2.8/MASTER_STATUS.md`.

---

## 1. Resumo executivo

A V2.7 concluiu que "parte do ganho territorial dependia do ano compartilhado".
A V2.8 mostra que **essa conclusão estava incompleta em dois sentidos** e que a
comparação publicada era **injusta nos dois lados**.

1. **O tamanho da amostra não é a causa.** O fatorial com controle de tamanho
   (treino equalizado em 5.686 linhas) reproduz as MAEs integrais com
   diferença ≤ 1 kg/ha. A inversão da soja não vem da redução de 36% do P5.
2. **O mecanismo difere por cultura.** Com o treino controlado, separar o ano
   custa −39,8 kg/ha na soja (IC95 −54,4 a −22,2) e apenas −6,9 no milho
   (IC95 −24,8 a +12,0, não significativo); separar o bloco custa −93,7 no
   milho e −3,6 na soja (não significativo). **A soja depende do ano; o milho
   depende do bloco.**
3. **A linha de base publicada é fraca e a comparação era injusta.** O modelo
   da V2.6/V2.7 não tem termo regional e era comparado à média **nacional**.
   Contra a média **da UF**, ele perde na soja (+43,2 kg/ha, IC95 +4,2 a +84,7).
   Contra a média nacional, o ganho da soja é **−17,0 kg/ha com IC incluindo
   zero**: o "+2,70%" publicado **não é estatisticamente distinguível de zero**
   quando a dependência espacial é respeitada.
4. **Com informação igualada, o clima acrescenta — mas pouco na soja.** Um
   modelo com clima **e dummies de UF** supera a média da UF em −13,1 kg/ha na
   soja (IC95 −25,7 a −0,6; ≈2,3%), por margem apertada; no milho 2ª safra
   supera em −165,8 a −267,2 kg/ha em todos os braços.
5. **A CAD da V2.6 não era uma análise de sensibilidade.** Os cenários
   35/50/70 mm movem o déficit anual em ±3%; a CAD oficial (0–100 cm) o reduz
   em **18,6%** e a de 0–200 cm em **42,3%** — a faixa real é uma ordem de
   grandeza maior.
6. **A associação agroclimática não é estável por classe de ciclo na soja**
   — *leitura corrigida na V2.9 (D94)*. As inclinações estimadas em separado
   diferiam muito (+182,7 na classe 21 contra −65,0 na classe 22), mas o
   **teste formal de interação** não confirma diferença para a temperatura
   (p=0,38); para o déficit hídrico a diferença é real (p=0,003). Ver §13.

**Conclusão defensável:** o ganho territorial da soja **não é sustentável** em
nenhuma das formulações testadas (nem contra a média nacional, nem contra a
média regional, com ou sem o ano compartilhado); o do milho **é parcial e
dependente da família de variáveis**; o do milho 2ª safra **é amplo e resiste a
todas as linhas de base**, embora a linha de base agregada seja fraca para essa
cultura. Nenhuma leitura causal é feita.

---

## 2. Estado inicial da V2.7 (recuperado)

Branch `v2/agroclimatic-robustness` em `36bf5d7`, publicada, árvore limpa.
Bundle da V2.7 conferido por `list-heads` (23 refs, 11 branches, 2 tags,
HEAD `36bf5d7`), SHA-256 `0AB3CDF2…04B9C9`, `git bundle verify` *okay*.
Suíte de referência: **318/318** offline. V1 (`v1-final` = `3f7ad33`) e `main`
intactas.

## 3. Branch e commits da V2.8

| Item | Valor |
|---|---|
| Branch | `v2/temporal-spatial-generalization` (base `36bf5d7`) |
| `8f49092` | abertura, auditoria, bundle conferido, suíte de referência |
| `1ca7a95` | fatorial espaço × tempo (D87) |
| `1307ad8` | linhas de base comparáveis + CAD no balanço hídrico (D88) |
| commit de encerramento | documentação, síntese e publicação |

## 4. Estado final do repositório

Árvore limpa, branch publicada em `origin`, `v1-final` e `main` inalteradas,
V2.7 preservada e recuperável em `v2/agroclimatic-robustness`.

## 5. Reprodução dos protocolos anteriores

| Verificação | Resultado |
|---|---|
| Braço `SE` vs P3 (soja, família B) | **612,724390**, idêntico ao publicado |
| Braço `TE` vs P5 (soja, família B) | **661,802276**, idêntico ao publicado |
| P1–P4 (V2.7, 132 valores de MAE) | reproduzidos bit a bit na V2.7; não alterados |
| Fórmula do ganho | `100 × (MAE_base − MAE_modelo) / MAE_base`, preservada |

A equivalência `SE = P3` e `TE = P5` é o que garante que o fatorial **é** uma
leitura fatorial dos protocolos publicados, e não um protocolo novo. Ela está
coberta por teste automatizado.

## 6. Decomposição do resultado P5

Fatorial 2×2 (espaço × tempo) sobre a mesma grade de dobras do P5; teste
idêntico nos quatro braços; treino equalizado por reamostragem estratificada
por bloco (5 repetições); IC por bootstrap de bloco inteiro.

Ganho vs média do treino (família B, equal-size):

| Cultura | SS | SE (=P3) | TS | TE (=P5) | efeito espaço (SS−SE) | efeito tempo (SS−TS) |
|---|---|---|---|---|---|---|
| soja | 609,2 | 612,7 | 649,0 | 661,7 | −3,6 [−13,5;+7,2] | **−39,8 [−54,4;−22,2]** |
| milho | 1583,7 | 1677,4 | 1590,6 | 1696,7 | **−93,7 [−178,6;−13,8]** | −6,9 [−24,8;+12,0] |
| milho 2ª | 1179,7 | 1197,7 | 1188,5 | 1218,2 | −18,0 [−28,9;−1,1] | −8,8 [−18,7;−3,0] |

Com dummies de UF no modelo (informação regional igualada):

| Cultura | SS | SE | TS | TE | efeito espaço | efeito tempo |
|---|---|---|---|---|---|---|
| soja | 552,8 | 559,4 | 588,9 | 604,3 | −6,5 [−14,6;+3,6] | **−36,1 [−46,2;−23,2]** |
| milho | 1493,3 | 1662,9 | 1515,3 | 1717,8 | **−169,7 [−332,5;−27,2]** | −22,1 [−40,1;−5,8] |
| milho 2ª | 1165,8 | 1205,3 | 1177,6 | 1234,0 | −39,6 [−68,5;+0,5] | −11,9 [−28,5;−3,9] |

**Leitura.** Os dois fatores não são intercambiáveis: a soja perde informação
de **ano** e é insensível ao bloco; o milho perde informação de **bloco** e é
quase insensível ao ano. Tratar "dependência espacial" e "dependência temporal"
como o mesmo problema era o erro de enquadramento da V2.7.

## 7. Análise específica da soja

* **Tamanho**: equalizar o treino em 5.686 linhas (o tamanho do P5) não desloca
  a MAE (661,8 → 661,7). A hipótese "amostra menor" está **refutada**.
* **Ano**: efeito grande e significativo em ambos os braços (+36 a +49 kg/ha).
* **Composição**: a fração de linhas por UF e por ano é estável entre braços
  (`train_state_share`, `train_year_share` no manifesto); a reamostragem é
  estratificada por bloco, então a mudança de composição não explica o efeito.
* **Linha de base**: contra a média da UF o modelo **piora** (+43,2; IC exclui
  zero); contra a média nacional o ganho **não é significativo** (−17,0; IC
  inclui zero). Com dummies de UF, o ganho sobre a média da UF é −13,1 kg/ha
  (≈2,3%), no limite da significância.
* **Ciclo**: na classe 21 (9% das linhas) a associação de temperatura **inverte
  de sinal** (t=+4,38) em relação à classe 22 (t=−3,18).

Classificação: **não robusto** como ganho territorial; a associação
déficit→produtividade é robusta em sinal na classe dominante, mas **sensível à
estratificação por ciclo** no caso da temperatura.

## 8. Análise específica do milho

* **Bloco**: efeito grande (−93,7 sem dummies; −169,7 com dummies de UF). O
  bloco carrega informação além da UF — há estrutura espacial intra-estadual.
* **Ano**: efeito pequeno (−6,9) e não significativo sem dummies; pequeno
  (−22,1) com dummies.
* **Linha de base**: com dummies de UF, o modelo supera a média da UF no braço
  espacialmente separado (−215,1; IC exclui zero) e é inconclusivo no braço
  compartilhado (−99,4; IC inclui zero).
* **Ciclo**: o déficit é negativo nas três classes (−1,38; −3,99; −5,30, todos
  |t| ≥ 2,27) — sinal estável.

Classificação: **parcialmente robusto**, dependente da família de variáveis
(hídrica sustenta mais que a meteorológica) e do braço espacial.

## 9. Análise específica do milho 2ª safra

* Ganho de +14,5% a +17,0% contra a média nacional, **preservado** no P5 e no
  controle de tamanho.
* Contra a média da UF, o modelo com dummies regionais supera em −163,7 a
  −267,2 kg/ha nos quatro braços (SS −165,8; SE −262,2; TS −163,7; TE −267,2).
  **Resiste a todas as linhas de base.**
* Ressalva: a média agregada é particularmente fraca para a 2ª safra
  (MAE ≈ 1,47 t/ha), então parte do ganho é heterogeneidade regional que a
  média nacional não captura.
* **Ciclo**: nenhuma associação sobrevive dentro das classes 21 e 20 — o sinal
  agregado do milho 2ª safra **não se reproduz por estrato**.

Classificação: **robusto como ganho preditivo**, **não conclusivo** como
associação agronômica.

## 10. Comparação dos baselines

Ganho percentual do modelo sobre cada referência (soja, equal-size):

| Modelo | vs média nacional | vs média da UF | vs média UF×ano |
|---|---|---|---|
| `climate_only` (publicado) | +2,7% (n.s.) | **−7,6%** | **−26,9%** |
| `climate_plus_state` | +11,7% | **+2,3%** | **−15,1%** |

Notas de disponibilidade, que mudam a interpretação:
* **média nacional**: sempre disponível, ignora região — foi a referência da
  V2.6/V2.7;
* **média da UF**: disponível *ex ante* (histórico de outros municípios da UF),
  é a referência justa para um protocolo territorial;
* **média UF×ano**: usa produtividade do **mesmo ano** em outros municípios;
  **não é disponível antes da colheita**. Serve como diagnóstico de quanto do
  "sinal" é efeito região-ano, não como competidor operacional. Nos braços que
  removem o ano, ela colapsa exatamente na média da UF (verificado por teste).

## 11. Métricas e incerteza

MAE e RMSE sem ponderação; MAPE apenas descritivo. Ganho definido como
`100 × (MAE_base − MAE_modelo) / MAE_base`, a mesma convenção da V2.6.
Incerteza por **bootstrap de bloco espacial inteiro** (1.000 réplicas), porque
observações do mesmo bloco são dependentes; reamostrar linhas isoladamente
subestimaria a incerteza. Nenhuma diferença é tratada como relevante apenas por
ser positiva: todas as comparações vêm com IC95.

## 12. Resultados da CAD

Unidade validada **numericamente**: o maior valor amostrado é 2,59; a leitura
volumétrica (cm³/cm³) exigiria ≤ 1,0, logo é impossível. `mm/cm` confirmado.

Balanço hídrico anual (Thornthwaite & Mather, ET0 FAO-56) para os 9 municípios
com CAD e série diária (o 10º, `2905800`, não está na base):

| Capacidade | Déficit mediano (mm) | Δ vs 50 mm |
|---|---|---|
| 35 mm (cenário V2.6) | 811,8 | +3,5% |
| **50 mm (referência V2.6)** | 784,2 | — |
| 70 mm (cenário V2.6) | 764,2 | −2,6% |
| CAD oficial 0–60 cm | 707,3 | −9,8% |
| **CAD oficial 0–100 cm** | 638,7 | **−18,6%** |
| CAD oficial 0–200 cm | 452,3 | −42,3% |

33 dos 90 município-anos mudam mais de 25% com a CAD 0–100 cm. A 50 mm
corresponde a **~23 cm** de solo com AW ≈ 2,2 mm/cm — mais rasa que qualquer
zona radicular de cultura; o valor veio de uma referência de textura média do
MAPA, não de um cálculo de zona radicular.

**Integração ao painel: bloqueada por cobertura.** Apenas **5 dos 1.296**
municípios do painel têm CAD amostrada (0,39% dos municípios, 82 de 19.402
linhas, 0,42%). Levar a CAD a todo o painel exige extração WCS em ~1.296
janelas × 6 camadas — aquisição massiva que a missão condiciona ao diagnóstico
de cobertura. Fica como item de V2.9, com a decisão de escopo registrada.

**Ponto metodológico importante:** como o déficit entra como regressor, um
reescalonamento **uniforme** da CAD não altera o teste t (a variável é
multiplicada por uma constante). O que altera a inferência é a
**heterogeneidade** da CAD entre municípios — e ela é grande (126 a 240 mm,
razão 1,9). Por isso a integração importa, e por isso ela não pode ser
simulada por um fator único.

## 13. Resultados fenológicos / ciclo (D89)

O painel carrega `zarc_cycle` (classe `Cod_Ciclo` do ZARC), **não cultivar**.
A correspondência entre os códigos 20/21/22 e "precoce/médio/tardio" **não está
documentada nos artefatos adquiridos** — o dicionário de dados do ZARC é um PDF
não coletado. Por isso as classes são citadas por código, sem rótulo inventado.

| Cultura | classe 22 | classe 21 | classe 20 |
|---|---|---|---|
| soja (linhas) | 7.893 (89%) | 784 (9%) | 207 (2%) |
| milho | 6.055 (79%) | 1.238 (16%) | 323 (4%) |
| milho 2ª | 14 (0,5%) | 1.790 (62%) | 1.098 (38%) |

Déficit hídrico (coeficiente within, EP agrupado por bloco):

| Cultura | classe 22 | classe 21 | classe 20 |
|---|---|---|---|
| soja | −0,876 (t=−3,89) | **+0,691 (t=+0,74)** | não estimável (n=207) |
| milho | −1,380 (t=−3,68) | −3,989 (t=−3,12) | −5,299 (t=−2,27) |
| milho 2ª | — | −0,503 (t=−0,64) | +0,387 (t=+0,46) |

Temperatura média:

| Cultura | classe 22 | classe 21 | classe 20 |
|---|---|---|---|
| soja | −65,0 (t=−3,18) | **+182,7 (t=+4,38)** | — |
| milho | −76,2 (t=−1,83) | −122,7 (t=−0,43) | −195,3 (t=−0,89) |
| milho 2ª | — | +23,9 (t=+0,25) | −271,8 (t=−2,21) |

A duração da janela ZARC **difere por classe** (modal: soja 3 meses na classe
22 e 4 na 21; milho 3 na 22 e 6 na 21; milho 2ª 2 na 21 e 3 na 20), o que
mostra que colapsar todas as classes numa janela modal mistura calendários.

A janela fenológica da V2.7 (R5 = 554 °C·dia; 46 dias na soja) permanece um
**cenário térmico**; ela não é comparável ao calendário ZARC por classe, e os
coeficientes de janelas distintas seguem mantidos separados.

> **Correção da V2.9 (D94) — a inversão de sinal não se sustenta.**
> As tabelas acima vêm de regressões estimadas **separadamente** por classe.
> No teste formal de interação — `y_w = b1·x_w + b2·(x·I_grupo)_w`, efeitos
> fixos de município e ano, erro agrupado por bloco — a diferença de
> inclinação entre as classes 22 e 21 é:
>
> | Cultura | déficit hídrico | temperatura | precipitação |
> |---|---|---|---|
> | soja | −1,194 (t=−3,16; **p=0,003**) | −3,98 (t=−0,88; p=0,38) | −0,075 (p=0,65) |
> | milho | −2,612 (t=−1,39; p=0,17) | −22,9 (t=−1,60; p=0,12) | −1,017 (p=0,046) |
> | milho 2ª | −0,727 (p=0,21) | +0,50 (p=0,91) | +0,161 (p=0,66) |
>
> Portanto: (i) a **temperatura da soja não difere** entre as classes — o
> +182,7 vs −65,0 era artefato de estimar cada classe com a sua própria
> transformação *within*; (ii) o **déficit hídrico da soja difere** (a
> inclinação é mais negativa no Grupo II); (iii) no milho, só a precipitação
> é marginal (p=0,046, sem ajuste para 9 testes). Após multiplicidade,
> nenhuma diferença entre grupos sobrevive. A leitura de "inversão de sinal"
> fica **retirada**.
>
> O dicionário oficial do ZARC (MAPA, `dicionario-de-dados-tabua-de-risco-2026.pdf`,
> consultado em 2026-11-14) define `Cod_Ciclo` como **grupo de ciclo**
> (20 = Grupo I, 21 = Grupo II, 22 = Grupo III) — não cultivar, e sem rótulo
> "precoce/médio/tardio".

## 14. Diagnóstico territorial (cobertura)

Reaproveitando `v27_panel_coverage.json` (V2.7): 3.564 pares
município-cultura avaliados; **2.281 elegíveis**, 739 elegíveis com ressalvas,
542 com dados insuficientes, 2 não elegíveis. A decisão de **não ampliar
agora** foi mantida.

Novas lacunas medidas na V2.8:
* **CAD**: 5 de 1.296 municípios do painel (0,39%); 82 de 19.402 linhas.
* **Ciclo**: apenas 3 classes por cultura e forte concentração (89% da soja em
  uma classe), o que limita a estratificação.
* **UF**: 5 (soja), 6 (milho), 4 (milho 2ª) — o `leave-one-UF-out` continua
  degenerado (5–6 grupos).

Nenhuma expansão é proposta: as lacunas que limitam as conclusões são de
**CAD** e de **estrutura de ciclo**, não de número de municípios.

## 15. Testes

| Suíte | Resultado |
|---|---|
| Offline (`geospatial/tests`) | **338/338** (318 da V2.7 + 20 da V2.8) |
| Externos opt-in | 10/10 (V2.7; não reexecutados nesta etapa) |

Novos testes: partição das dobras; ausência de vazamento; **igualdade
`SE = P3`** e **`TE = P5`**; controle de tamanho por braço; estratificação da
reamostragem por bloco; bootstrap com erros idênticos (diferença nula e IC
degenerado); valores e quedas das linhas de base; `state_year = state` quando o
ano é removido; dummies de UF (categoria de referência e UF não vista);
reprodutibilidade por semente.

## 16. Decisões novas

* **D87** — fatorial espaço × tempo com controle de tamanho obrigatório.
* **D88** — CAD: unidade `mm/cm` validada numericamente; CAD de perfil não é
  CAD efetiva de cultura; integração ao painel condicionada à cobertura.
* **D89** — `zarc_cycle` é classe de ciclo, não cultivar; estratificação por
  classe é teste de estabilidade; códigos sem rótulo documentado.

## 17. Fontes

NASA POWER (série diária, base do painel), INMET (validação independente,
inalterada), PAM/SIDRA 5457, ZARC/MAPA (`Cod_Ciclo`, `Cod_Solo`, decêndios),
Embrapa Solos/GeoInfo (Vasques et al., 2021; CC BY-NC 3.0 BR), FAO-56,
Thornthwaite & Mather (1955). Nenhuma fonte nova foi adquirida; nenhuma
credencial foi criada.

## 18. Limitações

1. A média UF×ano usa informação contemporânea e **não** é uma referência
   operacional; serve como diagnóstico.
2. A linha de base da UF fica instável nos braços que removem o bloco (o bloco
   é atípico dentro da UF para o milho: 1.877 vs 1.701 kg/ha).
3. A CAD cobre 0,39% dos municípios do painel; o efeito medido (−18,6%) é
   real nos 9 municípios amostrados, mas não pode ser extrapolado sem a
   extração completa.
4. Profundidade radicular efetiva por cultura **não foi atribuída**: exigiria
   fonte cultivar-específica. Foram usados perfis publicados (0–60/0–100/0–200).
5. Os códigos `Cod_Ciclo` não têm rótulo documentado nos artefatos; nenhum
   rótulo foi inventado.
6. Nenhuma conclusão causal. Associação, generalização e previsão são
   perguntas distintas e foram mantidas separadas.
7. O `leave-one-UF-out` segue não conclusivo (4–6 grupos).

## 19. Pendências

* Extração WCS da CAD para os 1.296 municípios do painel (condicionada ao
  diagnóstico de cobertura e à decisão de escopo).
* Dicionário de dados do ZARC (PDF) para rotular as classes de ciclo.
* Profundidade radicular por cultura, com fonte agronômica verificável.
* Reavaliar a inferência com a CAD geoespacial por município (a
  heterogeneidade é o que altera o teste t).
* ERA5-Land permanece bloqueado (D83); CHIRPS/ARCO sem DNS.

## 20. Recomendações para a V2.9

1. **Adotar `climate_plus_state` como modelo de referência** dos protocolos
   territoriais: o modelo sem termo regional estava estruturalmente
   desfavorecido e produzia conclusões enganosas nos dois sentidos.
2. **Reportar sempre as duas referências**: média nacional (convenção
   histórica) e média da UF (referência justa ex ante), com IC por bloco.
3. **Completar a CAD** para o painel, com a heterogeneidade preservada, e
   reestimar os coeficientes de déficit.
4. **Rotular as classes de ciclo** e reestimar a associação por classe apenas
   onde houver ≥ 300 linhas; declarar não conclusivo nos demais estratos.
5. **Investigar o efeito do bloco no milho**: é o fator dominante dessa cultura
   e não está explicado por UF nem por ano.
6. Manter a **Ridge** como único modelo de preços; a V2.8 não toca na previsão
   de preços.
