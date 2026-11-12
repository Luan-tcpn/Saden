# SADEN V2.6 — Resumo para a orientadora

> Documento de síntese para a decisão acadêmica. Detalhes técnicos em
> `geospatial/reports/V2_6_AGROCLIMATIC_DATA_FOUNDATION.md`,
> `V2_6_MULTIMUNICIPAL_PANEL.md` e `V2_6_AGROCLIMATIC_EXPLORATORY_ANALYSIS.md`.
> Branch: `v2/agroclimatic-productivity-panel`. Execução: 2026-11-12.

---

## 1. A mudança de metodologia, em uma frase

A V2.5 mostrou que o **NDVI** não explica o rendimento municipal, mesmo
depois de corrigir a escala e a janela. A V2.6 trocou o **sinal** (de
características espectrais da vegetação para **condições climáticas**) e o
**universo** (de 1 município para **1.225**), e o resultado é
**qualitativamente diferente**.

---

## 2. O que a V2.5 deixou como herança

* A **decisão de não integrar** nada ao produto — mantida. Nenhuma variável
  agroclimática entrou no Ridge de preços, na API ou na interface.
* A **disciplina metodológica**: protocolo pré-declarado, Holm para múltiplas
  comparações, validação temporal sem vazamento, replicação verificada da
  análise anterior como controle.
* O **calendário do ZARC** com a âncora de decêndios corrigida — reaproveitado
  e estendido a 1.622 municípios.
* Os **indicadores Sentinel-2**, preservados como material de pesquisa e
  referência geoespacial. Nada foi apagado.

---

## 3. O que foi construído

### 3.1 Base agroclimática

| Fonte | Papel | Acesso |
|---|---|---|
| **INMET** (668 estações) | **observação** — base independente de validação | ok |
| **NASA POWER** (MERRA-2 + CERES) | **reanálise** — base do painel | ok |
| **ERA5-Land** (via Open-Meteo) | **reanálise** — variáveis térmicas e de solo | parcial (limite de taxa) |
| **ERA5** (via Open-Meteo) | **reanálise** — precipitação, radiação, vento | parcial (limite de taxa) |
| **CHIRPS** | precipitação grillada | **bloqueado** (sem DNS) |

A limitação do ERA5-Land **não** é da fonte: é da **via de acesso** (o CDS
exige chave de conta; o ARCO não resolve DNS neste ambiente). E o NASA POWER
cobre o conjunto completo de variáveis.

### 3.2 Painel multi-municipal

**19.402 observações** (município × cultura × ano) em **5 estados**, sobre a
janela de plantio **oficial do ZARC** de cada município:

| Cultura | Observações | Municípios | Anos |
|---|---:|---:|---:|
| Soja | 8.884 | 1.225 | 8 |
| Milho | 7.616 | 1.063 | 8 |
| Milho 2ª | 2.902 | 505 | 9 |

Os critérios de inclusão (produção real em ≥ 7 dos 9 anos, área colhida
positiva, geometria oficial, estação do INMET a até 80 km) foram **fixados
antes** da análise e não dependem de clima nem de desempenho estatístico.

---

## 4. O que foi encontrado

### 4.1 As variáveis agroclimáticas têm evidência estatística; o NDVI não

| | NDVI (V2.5) | Agroclimáticas (V2.6) |
|---|---|---|
| p ajustado (Holm) | **1,000** (32 testes) | **0,0036** |
| Soja | r = 0,203 | até r = 0,227 (graus-dia) |
| Milho | r = −0,396 | até r = −0,373 (déficit hídrico) |

**INTERPRETAÇÃO.** O contraste é nítido: enquanto nenhuma combinação de NDVI
sobreviveu à correção para múltiplas comparações, **todas** as variáveis
agroclimáticas principais a sobrevivem. Os sinais são **agronomicamente
coerentes**: mais chuva na semeadura e menor déficit hídrico ↔ maior
rendimento.

### 4.2 Mas o resultado é nuançado, e é assim que deve ser lido

O painel permite separar duas perguntas que a V2.5 não conseguia separar:

| Experimento | Pergunta | Resultado |
|---|---|---|
| **Temporal** (walk-forward por município) | o clima explica a variação **de um** município entre anos? | **Não** — a média histórica vence (soja: 487 contra 982–2.016 kg/ha) |
| **Territorial** (municípios inteiros no teste) | o clima explica **diferenças entre** municípios? | **Sim** — o modelo com clima vence a média histórica nas **6** combinações (ganho de 1,7% a 6,3%) |

**INTERPRETAÇÃO.** O clima é **informativo sobre a geografia da produtividade**
(transferível a municípios não vistos) e **não substitui** a persistência
histórica na variação **intra**-municipal. É um resultado real e importante — e
é o oposto do que a V2.3/V2.5 sugeriam sobre a variável climática: o problema
do NDVI não era a escala, era o **sinal**.

### 4.3 O balanço hídrico é o sinal mais forte

Nos efeitos fixos de município e ano (erro-padrão agrupado por município):

| Variável | Milho | Soja |
|---|---|---|
| **Déficit hídrico** | β = −3,04, t = **−17,2** | β = −1,26, t = **−17,4** |
| **Precipitação acumulada** | β = +0,97, t = **10,2** | β = +0,58, t = **16,2** |
| Graus-dia | β = −0,34, t = −3,2 | β = +0,25, t = 7,2 |
| Temperatura média | β = −183, t = −10,9 | β = −93, t = −11,7 |

---

## 5. Limitações honestas

1. **A janela do ZARC é proxy** — recomendação oficial de plantio, não
   plantio observado. A exposição real da lavoura ao clima é aproximada.
2. **Resolução da reanálise**: ~55 km. Municípios vizinhos recebem valores
   quase idênticos → há **pseudo-replicação espacial** que o agrupamento por
   município não corrige por completo.
3. **A validação temporal é negativa** — o clima não melhora a previsão da
   variação anual de um município.
4. **Ganhos territoriais modestos** (2–6%) e sobre um alvo que é o rendimento
   **médio** municipal, não a safra.
5. **Bahia fora** do painel: o ZARC de ciclo curto não cobriu a janela de
   plantio com dados suficientes.
6. **Milho agregado na PAM** — o alvo é o total do ano; a incompatibilidade
   com a janela da 2ª safra está declarada em cada linha.
7. **Sem máscara anual de uso do solo** (MapBiomas segue bloqueado).

---

## 6. O que mudou de verdade

| | V2.5 | V2.6 |
|---|---|---|
| Sinal | NDVI (vegetação) | Clima, térmico e hídrico |
| Universo | 1 município, 8 anos | 1.225 municípios, 8–9 anos |
| n efetivo | 8 por cultura | 8.884 (soja) / 7.616 (milho) |
| Correlação com o alvo | r = 0,203 (soja), p Holm = 1,000 | p Holm = 0,0036 |
| Validação temporal | baselines vencem | baselines vencem |
| Validação territorial | não testada | **modelo climático vence** |

**O caminho metodológico do projeto mudou de direção de forma fundamentada:** a
V2.6 mostra que a limitação não era a escala do alvo, e sim a escolha do
**sinal**.

---

## 7. Decisões que dependem da orientação

1. **Ampliar o painel** para o Nordeste e para mais municípios do
   Centro-Oeste, mantendo o protocolo? O ganho previsível é mais
   municipalities por estrato e melhor controle da variação regional.
2. **Corrigir a pseudo-replicação espacial** com erro-padrão agrupado por
   **célula da grade** (e não por município), e/ou com reanálise de resolução
   maior (ERA5-Land a ~9 km, se o acesso for destravado)? É a limitação
   estatística mais relevante que resta.
3. **Ampliar a janela de exposição**: hoje é a janela de **plantio**; o
   período de **enchimento de grãos** (em que o milho é sensível ao calor) não
   é coberto, e as portarias do ZARC dão a base para construí-lo.
4. **Usar dados de solo** (Embrapa Solos) para replace o cenário de CAD por
   um valor **por município**, com textura e profundidade documentadas.
5. **Testar a hipótese de preço**: se o clima explica a geografia da
   produtividade, há uma cadeia plausível clima → produtividade → oferta →
   preço. Isso é uma **hipótese para a V2.7**, não uma conclusão: a redução
   de produtividade não implica aumento proporcional de preço (estoques,
   exportações, câmbio, demanda, políticas e logística pesam mais).
6. **Manter a integração com o Ridge fora do escopo.** A V2.6 mostra que o
   clima é informativo **entre** municípios, mas **não** melhora a previsão
   temporal de um município — condição que, sozinha, **não** justifica
   integrar nada ao produto de preço.

---

## 8. Recomendação

**Seguir por CAMINHO A** (painel agroclimático viável e análise exploratória
conclusiva), com três consequências:

1. **A linha do NDVI permanece encerrada** (D66) — mas os indicadores
   Sentinel-2 e o painel municipal da V2.5 ficam preservados como referência
   geoespacial e material de pesquisa.
2. **A base agroclimática é o novo ativo do projeto**: é reproduzível, tem
   procedência por linha e resolve a limitação de amostragem que impedia
   qualquer conclusão na V2.5.
3. **Não integrar ao Ridge ainda.** O ganho territorial é real mas pequeno, e a
   validação temporal é negativa. A integração só se justifica depois de
   (a) corrigir a dependência espacial, (b) ampliar a janela de exposição e
   (c) demonstrar ganho **temporal** — que hoje não existe.
