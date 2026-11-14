# V3.1 — MASTER STATUS

**Branch:** `v3/window-spatial-generalization`
**Base:** `40fd6aa` (V3.0, `v3/cad-integrated-agroclimatic-panel`)
**Objetivo:** corrigir integralmente a construção das janelas ZARC (D97/D100),
reconstruir todas as variáveis ambientais afetadas (um mês inteiro a menos por
janela: variáveis acumuladas ~44% menores), separar o painel corrigido do
histórico e investigar a heterogeneidade espacial do milho com validação TE
(tendência espacial e vizinhos históricos).

**Fase atual:** concluída (fases 0–9 do roadmap).

## Estado

| item | valor |
|---|---|
| testes offline | **393/393** (`pytest geospatial/tests`) |
| suíte de referência V3.0 | 372/372 confirmada antes de abrir a branch |
| `compileall` | limpo (`tools` + `geospatial/agroclimate`) |
| linhas analíticas reconstruídas | 19.402 (1.296 municípios) |
| culturas | soja 8.884 · milho 7.616 · milho 2ª 2.902 |
| blocos espaciais | 46 (raio 250 km) |
| variáveis reconstruídas | 20 por janela × 2 janelas + 3 cenários de CAD |
| histórico V1/`main` | intacto em `3f7ad33` / tag `v1-final` |

## Fases

| # | fase | estado |
|---|---|---|
| 0 | proteção e recuperação (Git, bundle V3.0, 372 testes) | concluída |
| 1 | auditoria da D97 e contrato temporal (D100) | concluída |
| 2 | reconstrução de todas as variáveis ambientais | concluída |
| 3 | painel corrigido separado do histórico | concluída |
| 4 | reestimação M0/M1/M1b/M2 em TE | concluída |
| 5 | tendência espacial M3/M4 (D102) | concluída — rejeitada |
| 6 | vizinhos históricos M1c (D103) | concluída — aprovado com ressalvas |
| 7 | análise por cultura e UF | concluída |
| 8 | síntese científica e decisões D100–D103 | concluída |
| 9 | validação, bundle e publicação | concluída |

## Resultados principais (TE, `M2 − M1`, ΔMAE; negativo = modelo melhor)

| Cultura | clima histórico | clima corrigido | pareado |
|---|---:|---:|---|
| soja | −6,3 n.s. | −18,5 n.s. | −12,2 [−24,0; 4,9] n.s. |
| milho | −198,7 | **−228,5** [−403,5; −37,0] | **−29,8** [−51,5; −2,3] |
| milho 2ª | −267,2 | −228,4 [−374,0; −11,0] | +38,8 [−1,8; 59,7] n.s. |

O efeito do milho é **concentrado em PR** (−607,4) e negativo em MS (+261,4) e
MT (+85,0): a MAE agregada não descreve o fenômeno.

## Bloqueios

* ERA5-Land (sem credencial CDS) e CHIRPS/ARCO (DNS) — inalterados.
* Nenhuma generalização nacional: 5–6 UFs de 27.
* CAD permanece não preditora (D98); usada apenas como parâmetro físico.

## Próxima ação

Ver `NEXT_ACTIONS.md` — a recomendação é testar **inclinação climática
heterogênea por UF** (modelo hierárquico/por região), que é a hipótese que a
análise por UF da V3.1 levanta e que a V3.1 deliberadamente não testou.
