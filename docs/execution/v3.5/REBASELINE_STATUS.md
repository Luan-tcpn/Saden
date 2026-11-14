# V3.5 — Status do rebaseline

Manifesto: `geospatial/data/manifests/v35_models.json`
Detalhe: `docs/V3_5_MODEL_REBASELINING_REPORT.md`

## Experimentos

| # | escopo | estado |
|---|---|---|
| **A** | 6 UFs (reconstituição) | ✔ reproduz a V3.4 **exatamente** |
| **B** | 7 UFs (expandido) | ✔ M0/M1/M2/M2+água reestimados |
| **C** | A × B (composição) | ✔ decomposição registrada |

## A — reconstituição

| cultura | n | M2 | M2+água | D(Sul−Cerrado) |
|---|---:|---:|---:|---:|
| milho | 7.542 | 1.661,2 | 1.651,7 | −78,3 |
| soja | 8.868 | 592,7 | 600,8 | −35,0 |
| milho 2ª | 2.897 | 1.272,3 | 1.282,7 | −22,5 |

Idênticos aos publicados na V3.4 → a cadeia de dados e o estimador continuam
consistentes; qualquer mudança em B vem da composição.

## B — expandido

| cultura | n | M0 | M1 | M2 | M2+água | M2−M1 |
|---|---:|---:|---:|---:|---:|---:|
| milho | 11.928 | 1.487,6 | 1.538,8 | **1.452,8** | 1.472,7 | −86,0 |
| soja | 12.491 | 604,7 | 573,9 | **554,7** | 571,3 | −19,2 |
| milho 2ª | 5.662 | 1.326,6 | 1.384,6 | **1.234,4** | 1.241,2 | −150,2 |

## C — o que mudou

| cultura | ganho M2−M1 em A | em B | leitura |
|---|---:|---:|---|
| milho | 175,4 | 86,0 | cai: efeito de composição (SP próximo da média nacional melhora M1) |
| soja | 18,7 | 19,2 | estável |
| milho 2ª | 230,4 | 150,2 | cai pela mesma razão |

**Nenhuma MAE absoluta é comparada entre A e B** — o conjunto de teste muda.

## Regras preservadas

| regra | estado |
|---|---|
| M2 com a mesma especificação (precip + temp + UF) | ✔ |
| M2+água idêntico ao da V3.3 | ✔ |
| M1b como diagnóstico, não baseline operacional | ✔ |
| janela corrigida (D100) | ✔ |
| equalização por célula, 25 células, 3 repetições | ✔ |
| nenhum preditor novo | ✔ |

## Transferência (treino 6 UFs → teste SP)

| cultura | MAE SP | MAE M0 | ganho |
|---|---:|---:|---:|
| milho | 1.721,2 | 1.352,1 | −27,3% |
| soja | 566,2 | 534,6 | −5,9% |
| milho 2ª | 1.200,4 | 1.251,2 | +4,1% |

O modelo depende do nível estadual estimado; não transfere automaticamente para
UF ausente do treino.

## Pendências

* MG (próxima UF) exigirá novo rebaseline de M0/M1 com 8 UFs.
* PAM nacional para representatividade produtiva — não feito.
