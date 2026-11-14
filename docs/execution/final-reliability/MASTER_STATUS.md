# Fechamento — estado mestre

**Branch:** `maintenance/final-reliability-closeout`
**Base:** `0973b77` (consolidação técnica) · **Data:** 2026-11-14
**Natureza:** fechamento de confiabilidade. Nenhuma hipótese nova, nenhuma UF nova,
nenhuma alteração na aplicação nem no TCC.

---

## 1. As cinco pendências e o que aconteceu com cada uma

| # | pendência | estado | resultado |
|---|---|---|---|
| 1 | conflito NASA POWER × INMET | **resolvida** | 627.381 pares medidos; NASA-POWER canônica; contrato executável com 0 consumidores sem guarda |
| 2 | divergência de ET0 | **resolvida** | 2 não conformidades com a FAO-56, que **se cancelam**: net **+0,54%** |
| 3 | D124 (excedente) | **resolvida** | defeito confirmado na referência, corrigido em módulo novo; nenhuma conclusão dependia |
| 4 | wild cluster bootstrap | **calibrado** | WCR: 5,26–5,96% para nominal de 5% (CR1: 7,54–9,98%) |
| 5 | manifestos determinísticos | **implementado** | duas execuções → hash idêntico |
| 6 | build completo | **executado** | 30.207 janelas, 1.880 municípios, 120.828 linhas de água |

## 2. Números de controle

| item | valor |
|---|---|
| testes | **482 herdados + novos**, 0 falhas |
| compilação | limpa |
| municípios construídos | **1.880** de 2.425 do cadastro (**77,5%**) |
| linhas de janela | **30.207** (igual à V3.5) |
| linhas de água | **120.828** (igual à V3.5) |
| chaves duplicadas no build | **0** |
| colunas idênticas à V3.5 | **37** |
| colunas alteradas pela física | 11 (ET0, ETP, ETR, déficit, excedente, CAD) |
| erro tipo I — CR1 | 7,54% / 7,86% / 9,98% |
| erro tipo I — WCR | **5,40% / 5,26% / 5,96%** |
| significâncias que mudaram de lado | **0** de 18 |

## 3. Decisões novas

D128 a D134. A numeração anterior ia até D127.

## 4. Artefatos históricos

Nenhum artefato de V2.6–V3.5 foi reescrito. As correções de física foram
implementadas em módulo novo (`agroclimate/corrections.py`), selecionáveis por
configuração, com `physics_version` gravado em cada linha do build novo.

## 5. Fora de escopo, por decisão

`SADEN-TCC/` não foi acessada, listada, lida, pesquisada nem incluída em
qualquer artefato. A aplicação V1.1 não foi modificada.
