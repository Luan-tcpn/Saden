# V3.2 — NEXT ACTIONS

## Concluído

* Auditoria de integridade (V1.1, `main`, V3.0, V3.1, bundles) antes de qualquer
  alteração.
* Pré-registro completo, com famílias de multiplicidade e regra de decisão
  A–D fixadas antes das estimativas.
* Diagnóstico de identificabilidade por cultura × UF, com classificação de
  elegibilidade definida antes de interpretar.
* Implementação de `M2-HET-FE` e `M2-HET-PP` no mesmo estimador da V3.1
  (células, equalização e linhas de teste idênticas); M2 comum reproduz a V3.1
  exatamente.
* Família confirmatória (6 testes globais, Holm): **1 rejeição**
  (milho 2ª × temperatura, p=0,0019 → 0,0113).
* Nenhum contraste individual por UF sobrevive ao Holm em nenhuma cultura.
* Descoberta metodológica: agrupamento por bloco espacial é otimista para
  regressores que variam em UF×ano (D104). F da soja: 8,74 → 1,13.
* Comparação preditiva pareada com dois esquemas de reamostragem.
* Robustez: leave-one-UF-out reprova o critério de Nível A para o milho;
  leave-one-year-out é estável.
* M1c reavaliado com pareamento por município-ano e decomposição de fallback.
* 17 testes novos; 410/410 na suíte.

## Inconclusivo

* **Heterogeneidade de inclinações em milho.** O teste global não rejeita após
  Holm (0,227), mas três variáveis derivadas (déficit com CAD, graus-dia, calor
  extremo) rejeitam no exploratório, em especificações de variável única. Não é
  possível separar a variável responsável por causa da colinearidade.
* **Magnitude das inclinações estaduais.** Os contrastes individuais têm
  intervalos amplos; a inclinação de referência de milho 2ª em GO
  (+856 kg/ha/°C) é implausível e não deve ser interpretada.

## Rejeitado

* **Tendência espacial (lat/lon quadrática)** — D102, não reaberta.
* **Modelo de inclinações comuns como pior opção para o milho** — falso: M2
  comum é a escolha estável; o ganho do PP é localizado (D107/§16).
* **Substituir M2 por M1c** — M1c não supera M2 com pareamento (D107).
* **Interpretar os desníveis por UF da V3.1 como inclinações** — D105.

## Hipóteses ainda plausíveis (para V3.3)

1. **A heterogeneidade está na forma funcional, não na variável bruta.** O
   padrão do milho (rejeita em déficit/graus-dia/calor, não em
   precipitação/temperatura) sugere que variáveis derivadas — que combinam
   oferta e demanda hídrica — capturam melhor o fenômeno. Teste pré-registrado
   necessário: especificação **conjunta** com déficit + graus-dia, e teste global
   de heterogeneidade nessa forma, antes de qualquer alegação.
2. **A heterogeneidade é entre grupos de UFs, não entre UFs.** Com 4–6 UFs não há
   como estimar variância entre estados; uma partição a priori (ex.: Sul vs
   Cerrado, definida por critério agronômico publicado) reduziria os graus de
   liberdade do teste. Só faz sentido com justificativa externa, não com os
   dados.
3. **A inclinação de temperatura é não identificável em PR/RS** porque só
   17–29% da variância é *within*. Um desenho com médias móveis ou anomalias
   relativas a normais climáticas poderia recuperar informação — mas exigiria
   normais de período longo, que o painel (2017–2025) não tem.

## Limitações que dependem de novos dados

* **4–6 UFs.** Qualquer teste de heterogeneidade entre estados como população
  exige mais UFs; a expansão exige diagnóstico de PAM, geometria, clima, solo e
  ZARC (V3.1, §15), não é um passo automático.
* **ERA5-Land / CHIRPS** continuam bloqueados (credencial / DNS). Sem eles, a
  janela depende de uma única fonte de clima.
* **Janela fenológica.** Datas observadas de plantio/colheita não existem no
  painel; enquanto isso, graus-dia continuam acumulados na janela ZARC de
  semeadura.

## Prioridades recomendadas para V3.3

1. **Teste conjunto da forma funcional hídrica** (déficit + graus-dia) com teste
   global de heterogeneidade pré-registrado — é a continuação natural do único
   sinal exploratório consistente.
2. **Corrigir a base inferencial de todas as alegações de associação
   anteriores** (D104): revisar quais p-valores publicados na V2.7–V3.1
   sobrevivem ao agrupamento UF×ano, e registrar quais não sobrevivem. Isso é
   mais importante que uma nova modelagem.
3. **Não** expandir cobertura territorial antes de (1) e (2).
