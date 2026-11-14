# V3.5 — Auditoria de cobertura

Manifesto: `geospatial/data/manifests/v35_coverage_robustness.json`
Detalhe: `docs/V3_5_TERRITORIAL_COVERAGE_REPORT.md`

## 1. Reconciliação 1.422 × 1.425 (pendência da V3.4) — **resolvida**

| item | valor |
|---|---:|
| pares UF–município na planilha oficial (6 UFs) | 1.425 |
| pares com correspondência exata de string | 1.422 |
| diferença | 3 |

| UF | nome oficial | situação |
|---|---|---|
| MT | Poxoréo | existe como **Poxoréu** |
| MT | Santo Antônio do Leverger | existe como **Santo Antônio de Leverger** |
| PR | Vila Alta | extinto; território em **Alto Paraíso (PR)** |

**Conclusão:** variantes de nome e de estatuto municipal. Não há território
ausente; a correspondência efetiva é 1.425/1.425.

## 2. Antes e depois

| indicador | 6 UFs | 7 UFs | Δ |
|---|---:|---:|---:|
| UFs | 6 | 7 | +1 |
| municípios | 1.274 | 1.856 | +582 |
| linhas soja | 8.868 | 12.491 | +3.623 |
| linhas milho | 7.542 | 11.928 | +4.386 |
| linhas milho 2ª | 2.897 | 5.662 | +2.765 |
| total | 19.307 | 30.081 | +10.774 |

## 3. Cobertura do território indicado

| indicador | valor |
|---|---:|
| municípios com indicação de soja (21 UFs) | 4.286 |
| cobertos na V3.4 | 1.425 (33,25%) |
| **cobertos na V3.5** | **2.070 (48,3%)** |
| fora do escopo | 2.216 (51,7%) |

## 4. Representatividade — o que **não** se afirma

* **Participação na produção nacional**: não estimada (PAM cobre 7 UFs).
* **Representatividade nacional**: não atingida (48,3% do território indicado, e
  a indicação de soja não é o território agrícola total).
* **Sudeste**: SP ≠ Sudeste; nenhuma conclusão se estende a MG/RJ/ES.

## 5. Ganho qualitativo da expansão

| dimensão | efeito |
|---|---|
| variação regional dentro de UF | **nova**: SP tem MRS 1, 2 e 3 |
| diversidade agroclimática | +1 domínio (subtropical úmido) |
| nível de produtividade | SP próximo da média nacional → **reduz** o ganho aparente sobre M1 |
| séries temporais | 8–9 anos, igual aos demais |
| culturas | soja, milho e milho 2ª com volume expressivo |

## 6. Blocos espaciais

A entrada de SP **não reatribui** nenhum município histórico (0 alterações
verificadas); SP forma **5 blocos** próprios no painel de milho (11 no cadastro
completo de 2.427 municípios). Isso mantém A e B comparáveis.
