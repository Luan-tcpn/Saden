# SADEN V3.5 — Cobertura territorial

**Data:** 2026-11-14 · Manifesto: `geospatial/data/manifests/v35_coverage_robustness.json`

---

## 1. Antes e depois de SP

| indicador | 6 UFs (V3.4) | 7 UFs (V3.5) | Δ |
|---|---:|---:|---:|
| UFs | 6 | **7** | +1 |
| municípios no painel analítico | 1.274 | **1.856** | +582 |
| anos | 8 | 8 | 0 |
| linhas utilizáveis — soja | 8.868 | **12.491** | +3.623 |
| linhas utilizáveis — milho | 7.542 | **11.928** | +4.386 |
| linhas utilizáveis — milho 2ª | 2.897 | **5.662** | +2.765 |
| **total de linhas** | **19.307** | **30.081** | **+10.774 (+55,8%)** |

SP contribui com **44% das linhas** do painel expandido e com **31% dos
municípios**. É a maior adição territorial desde a fundação do painel.

## 2. Reconciliação 1.422 × 1.425 (pendência da V3.4)

A V3.4 reportou dois números e não explicou a diferença de 3. Reconciliação:

| item | valor |
|---|---:|
| pares UF–município na planilha oficial (6 UFs) | **1.425** |
| pares que casaram com o cadastro do painel | **1.422** |
| diferença | **3** |

Os três, identificados nominalmente:

| UF | nome na lista oficial | situação no cadastro |
|---|---|---|
| MT | Poxoréo | existe como **Poxoréu** (grafia) |
| MT | Santo Antônio do Leverger | existe como **Santo Antônio de Leverger** (de/do) |
| PR | Vila Alta | município **extinto**; território hoje em **Alto Paraíso (PR)** |

**São variantes de nome e estatuto, não território ausente.** A correspondência
efetiva é 1.425/1.425; a correspondência por string exata é 1.422. Nenhuma
municipalidade ficou fora do mapeamento por falta de dados.

## 3. Denominador oficial e representatividade

| indicador | valor |
|---|---:|
| municípios com indicação de soja (MAPA/ZARC, 21 UFs) | 4.286 |
| nas 6 UFs da V3.4 | 1.425 (33,25%) |
| **nas 7 UFs da V3.5** | **2.070 (48,3%)** |
| fora do escopo | 2.216 (51,7%) |

A cobertura territorial em municípios com indicação sobe de **33,25% para 48,3%**.
Ainda não é metade do território indicado.

## 4. Participação na produção — não estimada

**Não é possível com os dados do repositório.** O painel PAM cobre as 6 UFs
históricas e agora SP; as outras 14 UFs com indicação não estão integradas. Um
percentual nacional de produção exigiria adquirir PAM para elas.

O que se pode dizer, e é mais fraco: **a cobertura em municípios subiu 15 pontos
percentuais**. Não se converte isso em toneladas.

## 5. Representatividade além da contagem

Contagem de municípios não é representatividade produtiva. O que a V3.5 mudou de
fato:

| dimensão | efeito da entrada de SP |
|---|---|
| **diversidade agroclimática** | +1 domínio (subtropical úmido com inverno seco; MRS 1 em SP é o primeiro ambiente "Sul" fora de PR/RS) |
| **variação regional dentro de UF** | **nova** — SP tem MRS 1, 2 e 3 (era zero UFs assim) |
| **nível de produtividade** | SP tem níveis próximos da média nacional, o que **reduz** o ganho aparente dos modelos sobre M1 |
| **culturas** | soja e milho bem cobertos; milho 2ª expressivo (2.775 linhas) |
| **série temporal** | 8–9 anos, igual aos demais estados |
| **área/ produção** | não medido (ver §4) |

## 6. Lacunas remanescentes

| lacuna | magnitude |
|---|---|
| 14 UFs com indicação ainda ausentes | 2.216 municípios (51,7% do indicado) |
| UFs com os dois grupos regionais (MRS 1 e MRS 3/4) | **só SP**, agora integrada |
| UFs de MRS 5 (Norte/Nordeste sojícola) | nenhuma integrada |
| ERA5-Land / CHIRPS | bloqueados (credencial / DNS) |
| participação produtiva nacional | não estimável sem PAM nacional |

## 7. O que a cobertura **não** autoriza

* Não autoriza chamar 7 UFs de "representativo do Brasil".
* Não autoriza transferir conclusões para o Sudeste: SP ≠ Sudeste.
* Não autoriza comparar MAEs absolutas com as versões anteriores (§4.1 do
  relatório de rebaseline).
* Não transforma o painel em amostra nacional — 48,3% do território indicado, e
  a indicação de soja não é o território agrícola total.

## 8. Classificação

| achado | classificação |
|---|---|
| reconciliação 1.422/1.425 | **validado** (3 variantes nominais identificadas) |
| +582 municípios, +10.774 linhas | **validado** |
| cobertura do território indicado: 33,25% → 48,3% | **validado** (denominador oficial) |
| participação na produção nacional | **não estimável** com os dados atuais |
| representatividade nacional | **não atingida** |
