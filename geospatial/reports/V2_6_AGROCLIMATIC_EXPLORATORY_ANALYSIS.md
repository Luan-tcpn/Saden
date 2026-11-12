# SADEN V2.6 — Análise exploratória: variáveis agroclimáticas e produtividade municipal

> Branch: `v2/agroclimatic-productivity-panel`. Execução: 2026-11-12.
> Artefatos: `geospatial/data/manifests/agroclimatic_analysis.json`,
> `geospatial/data/manifests/agroclimatic_analysis.csv`.
> Decisões: D61, D64, D70 (métodos) e D66–D72 (base).
> **Análise retrospectiva**: usa toda a safra para investigar relações; **não**
> é uma previsão operacional.

---

## 1. Protocolo (fixado antes de ver os resultados)

**D70.** Os modelos comparados são **pré-declarados** e não foram escolhidos
pelo desempenho observado:

| Modelo | Variáveis |
|---|---|
| **A — baselines** | (nenhuma) — média histórica, último valor, tendência temporal (os mesmos da V2.3) |
| **B — meteorológicos** | precipitação acumulada, temperatura média |
| **C — térmicos** | graus-dia acumulados, dias de calor extremo |
| **D — hídricos** | ET0, déficit hídrico, excedente hídrico |

Nenhum algoritmo complexo foi desenvolvido. Correção de **Holm** sobre a
família completa de testes. Permutação com 5.000 iterações e semente fixa
(20261112).

**Duas validações, experiments distintos** (D70.2):

* **Temporal (walk-forward por município)** — para cada município, o treino usa
  **apenas anos anteriores** ao ano testado. Nenhuma informação do ano alvo
  entra no treino, nem de outro município.
* **Territorial (holdout por município)** — 5 dobras; cada dobra testa um
  conjunto de municípios **inteiros**; o treino usa os demais. Anos do mesmo
  município **nunca** são distribuídos entre treino e teste.

**Painel com efeitos fixos** — município e ano como dummies, variável climática
como única regressor, **erro-padrão agrupado por município** (as observações
do mesmo município não são independentes).

---

## 2. Descritiva do painel

### 2.1 Soja (n = 8.884; 1.225 municípios; 8 anos)

| Variável | média | sd | mín | máx |
|---|---:|---:|---:|---:|
| Precipitação acumulada (mm) | 385,3 | 221,4 | 25,9 | 1.839,7 |
| Temperatura média (°C) | 23,5 | 3,5 | 15,5 | 34,5 |
| Graus-dia (°C·dia) | 1.095,6 | 393,5 | 182,0 | 2.950,0 |
| Déficit hídrico (mm) | 85,9 | 101,6 | 0,0 | 724,5 |
| Excedente hídrico (mm) | 110,5 | 147,9 | 0,0 | 1.289,2 |
| ET0 (mm) | 401,7 | 128,6 | 86,8 | 1.139,0 |

### 2.2 Milho (n = 7.616; 1.063 municípios; 8 anos)

| Variável | média | sd | mín | máx |
|---|---:|---:|---:|---:|
| Precipitação acumulada (mm) | 402,1 | 217,1 | 1,7 | 1.495,2 |
| Temperatura média (°C) | 23,8 | 3,8 | 13,2 | 34,6 |
| Graus-dia (°C·dia) | 1.119,1 | 251,1 | 147,6 | 1.815,5 |
| Déficit hídrico (mm) | 109,5 | 113,4 | 0,0 | 676,5 |
| Excedente hídrico (mm) | 120,3 | 169,3 | 0,0 | 954,8 |
| ET0 (mm) | 435,4 | 113,2 | 56,2 | 860,7 |

**INTERPRETAÇÃO.** Os valores são coerentes com a climatologia do Brasil
Central e Sul: janela de plantio de 3 meses com ~400 mm de chuva,
~1.100 °C·dia acumulados e déficit hídrico da ordem de 100 mm — magnitudes
plausíveis para soja e milho de primeira safra.

---

## 3. Correlações marginais (com Holm)

### 3.1 Soja

| Variável | n | r (Pearson) | ρ (Spearman) | p (permutação) | p (Holm) |
|---|---:|---:|---:|---:|---:|
| Precipitação acumulada | 8.884 | 0,1468 | 0,1438 | 0,0002 | **0,0036** |
| Temperatura média | 8.884 | 0,1993 | 0,1594 | 0,0002 | **0,0036** |
| Graus-dia | 8.884 | 0,2269 | 0,2285 | 0,0002 | **0,0036** |
| ET0 | 8.884 | 0,1832 | 0,2038 | 0,0002 | **0,0036** |
| Excedente hídrico | 8.884 | 0,0533 | 0,0133 | 0,0002 | **0,0036** |
| Déficit hídrico | 8.884 | 0,0139 | −0,0187 | 0,1900 | 0,1900 |

### 3.2 Milho

| Variável | n | r (Pearson) | ρ (Spearman) | p (permutação) | p (Holm) |
|---|---:|---:|---:|---:|---:|
| Precipitação acumulada | 7.616 | 0,1846 | 0,1737 | 0,0002 | **0,0036** |
| Temperatura média | 7.616 | −0,2576 | −0,2148 | 0,0002 | **0,0036** |
| Graus-dia | 7.616 | −0,1686 | −0,1941 | 0,0002 | **0,0036** |
| Déficit hídrico | 7.616 | **−0,3731** | −0,3654 | 0,0002 | **0,0036** |
| Excedente hídrico | 7.616 | 0,1422 | 0,1279 | 0,0002 | **0,0036** |
| ET0 | 7.616 | −0,2626 | −0,2864 | 0,0002 | **0,0036** |

### 3.3 Milho 2ª safra (n = 2.902; 505 municípios; 9 anos)

| Variável | r (Pearson) | ρ (Spearman) | p (Holm) |
|---|---:|---:|---:|
| Temperatura média | −0,4484 | −0,3880 | **0,0036** |
| Graus-dia | −0,4195 | −0,4501 | **0,0036** |
| ET0 | −0,4006 | −0,4284 | **0,0036** |
| Precipitação acumulada | −0,2687 | −0,2268 | **0,0036** |
| Déficit hídrico | −0,2598 | −0,2558 | **0,0036** |
| Excedente hídrico | −0,0895 | +0,0505 | **0,0036** |

**INTERPRETAÇÃO — o achado central da V2.6.**

Na V2.5, **nenhum** dos 32 testes da família foi significativo após Holm
(todos com p ajustado = 1,000). Na V2.6, **as correlações marginais das
variáveis agroclimáticas são significativas após Holm** (p = 0,0036) para
soja, milho e milho 2ª.

Isso **não** significa que o clima explique o rendimento: as magnitudes são
modestas (|r| entre 0,05 e 0,45) e a correlação marginal de um painel
municipal reflete **também** a variação de solo, manejo e tecnologia entre
municípios, que correlacionam com o clima por construção (regiões mais
quentes e mais secas tende a ter culturas diferentes). É por isso que os
modelos de **efeitos fixos** e a validação **territorial** são essenciais.

**Comparação direta com a V2.5:** o NDVI, na escala municipal e na janela
do ZARC, deu r = 0,203 (soja) e −0,396 (milho) com p ajustado = 1,000. As
variáveis agroclimáticas dão p ajustado = 0,0036. A **evidência
estatística** é substancialmente melhor — e o sinal é agronomicamente
coerente (milho: déficit hídrico negativo, precipitação positiva).

### 3.4 Validação independente com a via de observação (INMET)

**FATO.** O mesmo protocolo, aplicado ao subconjunto com série **observada**
de estação (146 municípios de soja, 137 de milho, 69 de milho 2ª — municípios
com estação **dentro** do município), reproduz o padrão:

| Cultura | Variável | r (reanálise) | r (observação INMET) | Holm (INMET) |
|---|---|---:|---:|---:|
| Soja | Temperatura média | +0,199 | **+0,243** | 0,0036 |
| Soja | Graus-dia | +0,227 | **+0,202** | 0,0036 |
| Soja | Precipitação | +0,147 | +0,100 | 0,0256 |
| Milho | Precipitação | +0,185 | **+0,167** | 0,0036 |
| Milho | Temperatura média | −0,258 | **−0,198** | 0,0036 |
| Milho | Déficit hídrico | −0,373 | **−0,202** | 0,0036 |
| Milho 2ª | Temperatura média | −0,448 | **−0,459** | 0,0036 |
| Milho 2ª | Graus-dia | −0,420 | **−0,381** | 0,0036 |

**INTERPRETAÇÃO.** O sinal **não** é artefato da reanálise: ele aparece,
com magnitude comparável, em **medições de estação**. Isso é a validação
mais forte disponível no projeto — e é a que responde à objeção de que
tudo poderia ser produto da grade do MERRA-2.

**LIMITAÇÃO.** A via de observação é menor (146 municípios de soja) e,
pelo critério de elegibilidade, cobre sobretudo os municípios com **estação
dentro do seu território** — o que introduz viés de seleção em direção a
áreas mais consolidadas.

---

## 4. Painel com efeitos fixos de município e de ano

| Cultura | Variável | β (kg/ha por unidade) | EP (agrupado) | t | R² |
|---|---|---:|---:|---:|---:|
| Milho | Precipitação acumulada | **+0,9748** | 0,0955 | **10,21** | 0,6629 |
| Milho | Graus-dia | −0,3376 | 0,1060 | −3,18 | 0,6586 |
| Milho | Déficit hídrico | **−3,0395** | 0,1767 | **−17,20** | 0,6714 |
| Milho | Temperatura média | −182,67 | 16,77 | −10,90 | 0,6628 |
| Soja | Precipitação acumulada | **+0,5806** | 0,0359 | **16,18** | 0,5059 |
| Soja | Graus-dia | +0,2461 | 0,0340 | **7,23** | 0,4960 |
| Soja | Déficit hídrico | **−1,2602** | 0,0723 | **−17,44** | 0,5052 |
| Soja | Temperatura média | −92,79 | 7,92 | **−11,71** | 0,4989 |

**INTERPRETAÇÃO.**

* **Precipitação positiva** na janela de plantio, com t entre 10 e 16, nos
  dois cultivos: mais chuva na semeadura ↔ maior rendimento.
* **Déficit hídrico negativo** e fortemente significativo (t = −17,2 no
  milho, −17,4 na soja): o déficit hídrico durante a janela de plantio é o
  fator com maior efeito individual, e o sinal é o esperado.
* **Graus-dia**: sinal **positivo** na soja (t = 7,2) e **negativo** no
  milho (t = −3,2). Isso é coerente com a agronomia: a soja de ciclo médio
  tem carência térmica a  até o fechamento, e o milho é
  sensível ao excesso de calor no enchimento de grãos — mas o sinal do milho
  deve ser lido com cautela, porque a janela de plantio não é o período de
  enchimento de grãos (ver limitação 5.3).
* **Temperatura média negativa** em ambos: reflete o efeito do déficit
  hídrico (temperatura alta e seca andam juntas).

**LIMITAÇÃO.** O erro-padrão é agrupado por **município**, mas a grade da
reanálise (~55 km) faz com que municípios vizinhos recebam valores quase
idênticos: a **independência espacial** não é garantida pelo agrupamento por
município. Os *t*-valores devem ser lidos como uma **indicação de força do
sinal**, não como um teste de significância definitivo. Um agrupamento
espacial (por célula da grade) seria o próximo passo metodológico.

---

## 5. Validação temporal (walk-forward por município)

**FATO.** Treino com anos anteriores, teste no ano seguinte, por município.

| Cultura | Modelo | n previsões | Média histórica | Último valor | Tendência | **Modelo** | Vencedor |
|---|---|---:|---:|---:|---:|---:|---|
| Milho | B — meteorológicos | 2.483 | **1.135** | 1.283 | 1.519 | 2.275 | média histórica |
| Milho | C — térmicos | 2.483 | **1.135** | 1.283 | 1.519 | 1.704 | média histórica |
| Milho | D — hídricos | 2.483 | **1.135** | 1.283 | 1.519 | 1.967 | média histórica |
| Soja | B — meteorológicos | 3.138 | **487** | 758 | 681 | 982 | média histórica |
| Soja | C — térmicos | 3.138 | **487** | 758 | 681 | 1.872 | média histórica |
| Soja | D — hídricos | 3.138 | **487** | 758 | 681 | 2.016 | média histórica |

**INTERPRETAÇÃO.** Na **previsão temporal**, a média histórica **vence** todos
os modelos climáticos, e a diferença é grande (soja: 487 contra 982–2.016).
Isso **não** contradiz o teste anterior: o yield municipal de um município tem
forte **persistência** e a variação anual do clima é pequena em relação à
heterogeneidade estrutural do sistema produtivo (solo, manejo, tecnologia,
portfolio). A regressão linear com 1–2 variáveis não captura essa estrutura e
extrapola mal no tempo.

Este é um resultado **honesto e importante**: as variáveis agroclimáticas
explicam **diferenças entre municípios**, mas **não** a variação de um mesmo
município ao longo dos anos.

---

## 6. Validação territorial (generalização para municípios não vistos)

**FATO.** 5 dobras; cada dobra testa municípios inteiros.

| Cultura | Modelo | n previsões | Média histórica | Último valor | Tendência | **Modelo** | Vencedor |
|---|---|---:|---:|---:|---:|---:|---|
| Milho | B — meteorológicos | 7.616 | 1.578 | 1.747 | 1.574 | **1.552** | **modelo** |
| Milho | C — térmicos | 7.616 | 1.578 | 1.747 | 1.574 | **1.512** | **modelo** |
| Milho | D — hídricos | 7.616 | 1.578 | 1.747 | 1.574 | **1.478** | **modelo** |
| Soja | B — meteorológicos | 8.884 | 622 | 1.034 | 618 | **597** | **modelo** |
| Soja | C — térmicos | 8.884 | 622 | 1.034 | 618 | **607** | **modelo** |
| Soja | D — hídricos | 8.884 | 622 | 1.034 | 618 | **611** | **modelo** |

**INTERPRETAÇÃO.** Na **generalização territorial**, os modelos climáticos
**vencem** a média histórica em **todas** as seis combinações:

* milho: 1.478–1.552 contra 1.578 da média histórica (ganho de 1,6% a 6,3%);
* soja: 597–611 contra 622 (ganho de 1,7% a 4,0%).

**Este é o resultado mais informativo da V2.6.** Ele mostra que a informação
climática **é transferível** entre municípios: um modelo treinado em 80% dos
municípios de soja do Sul/Centro-Oeste e testado em municípios **não vistos**
é melhor do que simplesmente prever a média histórica.

O contraste entre as duas validações é coerente e informativo:

| Experimento | O que testa | Resultado |
|---|---|---|
| Temporal | o clima explica a variação **de um** município entre anos? | **não** (média histórica vence) |
| Territorial | o clima explica **diferenças entre** municípios? | **sim** (modelo vence) |

**LIMITAÇÃO.** Os ganhos são modestos (2–6%) e o número de previsões por
dobra é grande (7.616–8.884), mas a estrutura de dobras é determinística
(semente fixa) e a validação é **espacialmente** honesta (municípios
inteiros). **Não** é uma validação preditiva operacional: o alvo é o
rendimento **médio municipal**, e o modelo não foi testado contra o rendimento
de uma safra específica em tempo real.

---

## 7. Conclusões

1. **FATO.** Variáveis agroclimáticas têm associação **estatisticamente
   significante** com o rendimento municipal de soja, milho e milho 2ª, ao
   contrário do NDVI (p ajustado = 1,000 na V2.5; 0,0036 na V2.6).
2. **FATO.** O **déficit hídrico** na janela de plantio é o sinal mais forte
   e mais consistente (t ≈ −17 em milho e soja), seguido da **precipitação**
   acumulada (t ≈ 10–16, positivo).
3. **FATO.** As variáveis climáticas são informativas **entre municípios**
   (vencem na validação territorial) e **não substituem** a persistência
   histórica na variação **dentro** do município (perdem na validação
   temporal).
4. **FATO.** A escala municipal do indicador, que na V2.5 não resolveu o
   problema do NDVI, aqui é **necessária**: é o que permite separar a
   variação transversal da temporal.
5. **FATO.** O painel (1.225 municípios de soja, 1.063 de milho) é maior
   que o alvo mínimo de 15 municípios por cultura e permite erro-padrão
   agrupado.

**Caminho da V2.6 quanto à análise: A — análise exploratória viável e
conclusiva.**

**O que NÃO se conclui:** nenhum modelo é apresentado como preditivo
validado; a validação temporal mostra que o clima **não** substitui os
baselines para prever a variação anual de um município; os ganhos territoriais
são pequenos; e a resolução da reanálise impõe pseudo-replicação espacial não
totalmente corrigida pelo agrupamento por município.

### 7.1 Uma instabilidade que precisa ser dita

**FATO.** Na validação **temporal** do milho 2ª safra, o modelo D (hídrico)
produz MAE de 16.397 kg/ha (reanálise) e 24.760 (via INMET) — muito pior que
os baselines. A causa é **extrapolação numérica**: com o sinal do déficit
hídrico negativo e uma amostra de treino pequena (5 anos por município), os
coeficientes ficam grandes e a previsão fora do intervalo de treino explode.

**INTERPRETAÇÃO.** Isso é uma limitação do **modelo linear simples** com
variáveis correlacionadas, não da variável: a mesma variável entra com
efeito negativo e significativo nos efeitos fixos. Reforça a conclusão de
que a V2.6 **não** deve integrar esses modelos ao produto sem antes tratar
a instabilidade (regularização, seleção de variável com justificativa
agronômica, ou modelo restrito).

