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

**Checkpoint.** (commit da fase 0+1)
