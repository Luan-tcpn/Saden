# SADEN V2.5 — Resumo para a orientadora

> Documento de síntese para a decisão acadêmica. Detalhes técnicos em
> `geospatial/reports/V2_5_SEASONAL_SPATIAL_PAIRING.md` e
> `geospatial/reports/V2_3_EXPLORATORY_PRODUCTIVITY_STUDY.md`.
> Branch: `v2/seasonal-spatial-pairing`. Execução: 2026-11-12.

---

## 1. O que a V2.5 se propôs a fazer

A V2.3 mostrou que o NDVI **não** melhorou as previsões de produtividade
municipal. A V2.4 identificou **dois** motivos possíveis para isso e deixou a
base pronta, sem executar a análise:

1. **Incompatibilidade de escala** — o alvo era o rendimento do município
   inteiro (9.293 km²) e o indicador vinha de uma AOI de 43 km² (0,47% do
   município);
2. **Janela inadequada** — o indicador era a média do ano civil, sem qualquer
   calendário agronômico validado.

A V2.5=testou essas duas hipóteses ao mesmo tempo: construiu a série do NDVI
**na escala municipal**, **dentro das janelas oficiais de plantio do MAPA**,
e reavaliou tudo com os mesmos métodos da V2.3.

**A pergunta era se a relação melhoraria. Ela não melhorou.**

---

## 2. O que foi feito

### 2.1 A série municipal foi concluída

O NDVI foi calculado sobre **toda a área agrícola do município** de Sorriso
(máscara oficial ESA WorldCover, classe 40, recortada pelo polígono
municipal), em grade de 20 m, por 16 blocos, **sem materializar o raster
municipal**. Foram gerados os **47 meses** que as janelas agrícolas exigem
(2017–2025), com 4 variantes de máscara, num total de 188 registros com
proveniência completa (cena, tile, perfil radiométrico, cobertura, fração
obstruída).

O processamento foi reprodutido com **SHA-256 idêntico** e **zero
duplicatas**.

### 2.2 O calendário foi auditado — e corrigido

A auditoria encontrou **dois erros reais** na ingestão do ZARC da V2.4:

* o campo de risco por decêndio é **textual** (`baixo`, `medio`, `alto`), e
  estava sendo lido como numérico — o que produzia janelas **vazias**;
* a âncora de ano dos decêndios estava errada para o **milho 2ª safra**.

A correção foi verificada por um critério objetivo e externo: **a portaria
que publica a recomendação tem de preceder a janela recomendada**. Com a regra
anterior havia **165 violações**; com a regra corrigida, **zero**. O milho 2ª
safra passou a ser corretamente associado a janeiro–fevereiro do segundo ano
da safra.

### 2.3 O pareamento foi construído em duas fatias

Para que a comparação com a V2.3 fosse honesta, o conjunto tem duas fatias:
a **janela ZARC** (nova) e o **ano civil** (réplica exata da V2.3). A réplica
foi verificada par a par: **diferença máxima de 1,1·10⁻¹⁶** — ou seja,
reprodução bit a bit da implementação auditada da V2.3. Isso permite separar
o efeito **escala** do efeito **janela**.

### 2.4 O milho foi tratado como o caso difícil que é

A PAM publica o **rendimento total do milho do ano** (1ª + 2ª safras), sem
desagregação. As janelas do milho principal e da 2ª safra foram mantidas
**separadas**, e a 2ª ficou com **n = 3** — declarado como **não avaliável**.
Não foi construído indicador ponderado por área de safra, porque não há área
por safra: seria incorreto.

---

## 3. O que foi encontrado

### 3.1 A escala municipal **não** era o gargalo

| Configuração | Soja (r) | Milho (r) | n |
|---|---:|---:|---:|
| Réplica da V2.3 — AOI + ano civil | 0,432 | 0,200 | 9 |
| Só muda a **escala** — municipal + ano civil | 0,302 | −0,015 | 9 |
| Só muda a **janela** — AOI + janela ZARC | 0,372 | −0,455 | 8 |
| Muda **as duas** — municipal + janela ZARC | **0,203** | **−0,396** | 8 |

A escala municipal **não** melhorou nada: na soja, r caiu de 0,432 para
0,302; no milho, a correlação praticamente **desapareceu** (0,200 → −0,015).
A janela ZARC também não melhorou — no milho, **inverteu** o sinal.

### 3.2 Nenhuma configuração teve significância

Com 32 testes na família e correção de Holm, **todos** os p-valores ajustados
são 1,000. O menor p-valor da família (0,242) é o **da própria V2.3** — ou
seja, o resultado da V2.3 também não sobrevive à correção para múltiplas
comparações. Os intervalos de confiança bootstrap da análise principal da
soja vão de −0,58 a +0,78: nenhum sinal.

### 3.3 Na validação temporal, o NDVI não supera os baselines

Com **os mesmos anos de teste** (2023–2025) em todas as configurações:

| Série | Com NDVI | Média histórica | O NDVI vence? |
|---|---:|---:|---|
| soja · janela ZARC · municipal | 402 kg/ha | **315 kg/ha** | não |
| soja · ano civil · AOI (réplica V2.3) | 324 kg/ha | **320 kg/ha** | não |
| milho · janela ZARC · municipal | 1.075 kg/ha | **936 kg/ha** | não |
| milho · ano civil · municipal | 941 kg/ha | **852 kg/ha** | não |

Em **nenhuma** das 8 configurações testadas o modelo com NDVI supera a média
histórica. A referência da V2.3 (soja 368 vs 254; milho 955 vs 684) é
confirmada pela réplica.

### 3.4 A AOI não é representativa do município — e agora está quantificado

Mensalmente, a AOI subestima o NDVI municipal em **+0,037** (desvio-padrão
0,053; mínimo −0,083; máximo +0,141). A diferença média **anual** varia de
−0,0002 (2018) a +0,0775 (2022). Isso confirma de forma independente a
estimativa da V2.4 (+0,039).

**A sensibilidade à máscara é desprezível**: as 4 variantes (2020, 2021,
interseção, união) dão resultados praticamente idênticos.

---

## 4. Conclusão da V2.5

**CAMINHO B — base pareada válida, mas sem ganho do NDVI.**

Os dados foram corretamente alinhados, o calendário é oficial e auditado, os
indicadores municipais foram construídos, a amostra existe (n = 8) e o NDVI
**não** explica o rendimento municipal de soja nem de milho.

**Isto é uma descoberta científica válida, e não uma falha do trabalho.** A
hipótese que a V2.4 había levantado — "a incompatibilidade de escala e a
janela anual explicavam a ausência de relação" — está **refutada**. O que
restou é a explicação mais simples: **o NDVI de Sentinel-2 sobre a área
agrícola de Sorriso, por mais bem alinhado que esteja, não contém informação
sobre a produtividade municipal**.

---

## 5. O que a V2.5 **não** fez (e por quê)

* **Não** treinou modelos de produtividade. O gate metodológico da V2.3
  (D53) só permite integrar um indicador que **superasse de forma
  consistente** os baselines em validação temporal. Não superou.
* **Não** integrou nada ao Ridge de preços, à interface ou à API.
* **Não** rasterizou produtividade municipal, nem inventou janelas, nem
  escolheu a janela de maior correlação, nem inflou o n.
* **Não** conseguiu a máscara **anual** de uso do solo (MapBiomas exige conta
  institucional) — segue sendo a maior limitação.

---

## 6. Limitações honestas

1. **n = 8** por cultura (soja e milho): é um tamanho de amostra que só
   permite **exploração**. Nenhum resultado é conclusivo — nem positivo, nem
   negativo definitivo.
2. **A máscara é retrospectiva**: só existem mapas de uso do solo de 2020 e
   2021, aplicados a todos os anos. Em 7 dos 8 anos analisados, a máscara é
   de um ano diferente do da cena.
3. **Janela de plantio ≠ ciclo da cultura**: sem duração de ciclo oficial por
   cultivar para Sorriso, o indicador mede o comportamento espectral durante
   o período recomendado, **não** a biomassa acumulada.
4. **Milho 2ª safra**: n = 3 e incompatibilidade semântica com o alvo
   agregado — não avaliável.
5. **Cobertura de nuvem** varia de 0,27 a 0,99; 4 meses ficaram abaixo de
   0,50 e foram excluídos por critério declarado.

---

## 7. Decisões que dependem da orientação

1. **Encerrar ou redirecionar a linha de produtividade com NDVI?** A
   recomendação técnica é **encerrar**: o indicador não acrescenta nada,
   depois de corrigidas a escala e a janela. Investir mais em modelagem do
   mesmo sinal tem custo alto e retorno esperado baixo.
2. **Ampliar para painel de municípios?** A restrição de n = 8 é
   **estrutural** em um município e não se resolve com melhor modelagem. Se o
   objetivo for produto, o caminho é treinar em **vários municípios**
   (o modelo de preço do SADEN já opera em painel regional).
3. **Autorizar o acesso institucional ao MapBiomas (GEE)?** É a pendência que
   **mais** muda o resultado: traria a máscara anual de uso do solo e permitiria
   separar lavoura temporária de perente na escala municipal, além de testar
   se a qualidade do sinal agrícola muda. **Recomendação: não é bloqueante
   para encerrar a linha, mas vale como reavaliação única se a conta for
   obtida.**
4. **Perseguir variáveis agroclimáticas diretas** (INMET, graus-dia, balanço
   hídrico) em lugar do NDVI? Recomendação: **sim** — são as variáveis que
   têm conteúdo agronômico direto para a produtividade.

---

## 8. Recomendação final

**Seguir por CAMINHO B**, com três consequências práticas:

1. **Não integrar** o indicador geoespacial ao Ridge de preços nem à
   interface. A V2.5 fecha a investigação com evidência, não com
   otimismo.
2. **Reaproveitar** a base pareada e a série municipal como evidência
   reproduzível e como base para reavaliações futuras (inclusive se o
   MapBiomas for aprovado).
3. **Direcionar os recursos** para variáveis agroclimáticas com conteúdo
   agronômico direto e, se o objetivo for produto, para a **ampliação do
   painel de municípios** — que resolve a limitação de n, ao contrário de
   qualquer melhoria no tratamento do NDVI.

O resultado negativo da V2.5 **é** o produto científico da versão: ele
elimina uma hipótese com rigor metodológico (réplica verificada da V2.3,
decisão dupla de escala e janela, controle de vazamento temporal, correção
de múltiplas comparações) e aponta com clareza para onde está o caminho.
