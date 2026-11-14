# SADEN — Relatório de consolidação técnica

**Branch:** `maintenance/technical-consolidation`
**Base:** `32dfb88` (V3.5) · **Data:** 2026-11-14
**Natureza:** consolidação. Nenhuma hipótese agroclimática nova, nenhuma UF nova,
nenhum modelo novo.

---

## 1. Resumo executivo

O projeto tinha resultados científicos, mas três caminhos concorrentes para
construir o painel, um filtro de fonte de clima implícito e nenhuma prova de que
pudesse ser reproduzido por outra pessoa. Esta etapa fechou essas lacunas.

**O que ficou demonstrado:**

- o painel atual é reconstruído por **um caminho único**, com configuração
  declarativa, e a reconstrução é **bit-idêntica** à V3.5 (diferença 0,000 em
  2.040 comparações numéricas);
- a fonte de produtividade é **sólida**: 43.650 células, zero duplicidades, zero
  alteração de código municipal, rendimento consistente em 99,8%; apenas 0,09%
  das linhas analíticas têm qualquer flag;
- o **déficit hídrico** foi **replicado independentemente** a partir das
  equações (diferença máxima 4,3 × 10⁻⁶ mm em 90 janelas);
- o projeto é **reproduzível em clone limpo**: 479 testes passam, o painel é
  reconstruído e a replicação científica é reexecutada sem o ambiente original.

**O que ficou exposto:**

- o **excedente hídrico é superestimado** na implementação de referência (D124),
  sem afetar nenhuma conclusão publicada;
- os **p-valores são liberais**: erro tipo I observado de 6% a 10% para nominal
  de 5% (D125);
- **acrescentar municípios praticamente não aumenta o poder** — dobrar os
  municípios reduz o erro-padrão em 0,2% (D126). A expansão de cobertura feita
  até aqui comprou território, não precisão;
- `requirements.txt` não declarava `pytest`: **o projeto não conseguia rodar a
  própria suíte em ambiente limpo**. Corrigido.

## 2. Estado anterior

| versão | commit | estado |
|---|---|---|
| V1.1 / `main` / `v1-final` | `3f7ad33` | congelada, intacta |
| V3.0 | `40fd6aa` | intacta |
| V3.1 | `345b22e` | intacta |
| V3.2 | `3bf9360` | intacta |
| V3.3 | `6eff88c` | intacta |
| V3.4 | `b9e7098` | intacta |
| V3.5 | `32dfb88` | base desta etapa |

Suíte herdada: 458/458. Bundle V3.5 verificado por SHA-256.

## 3. Auditoria PAM

Ver `docs/data_quality/PAM_QUALITY_AUDIT.md`.

| item | resultado |
|---|---|
| células município–ano–cultura | 43.650 |
| chaves duplicadas | **0** |
| série completa (9 anos) | 2.425 de 2.425 |
| alteração de código municipal | **0** |
| rendimento = produção/área (±1%) | 99,8% |
| divergências > 1% | 66 (mediana 1,75%) |
| extremos por MAD | 99 |
| impacto no painel | 27 de 30.207 linhas (0,09%), todas em BA |

Nenhum zero foi convertido em nulo nem nulo em zero. `sem_area` (7.507) e
`plantado_sem_colheita` (85) são informação, não erro. Nada foi excluído (D122).

## 4. Qualidade do painel

Ver `docs/data_quality/PANEL_DATA_QUALITY_AUDIT.md`.

**Achado material:** `climate_daily.csv` contém **duas fontes sob a mesma chave**
— NASA-POWER e INMET — com **627.381 pares conflitantes** e valores diferentes.
O filtro existia, mas era implícito. Passou a ser declarado (D123).

**Segundo achado:** **2.020 linhas** do painel base são `INMET` **e**
`paired_usable`. Nunca foram usadas, mas quem filtrar só por `status` obtém duas
fontes misturadas.

**Terceiro:** latitude só é exportada para SP (10.805 de 30.207 linhas).

**Quarto:** `4300001`/`4300002` são Áreas Operacionais do IBGE, não municípios.
Excluídas por regra explícita (D121); zero linhas no painel.

## 5. Unificação do pipeline

Ver `docs/PIPELINE.md`.

`tools/pipeline/build_panel.py` + `config/panel_v35.json`. Não reimplementa
cálculo: chama `v31_rebuild_panel._aggregate`, `v33_water_variables._descriptors`
e `agroclimate.*`. Os três caminhos históricos continuam existindo e **não**
foram convertidos em wrappers, para preservar a reprodução dos artefatos de cada
versão (D127).

## 6. Reprodução em clone limpo

Ver `docs/execution/consolidation/CLEAN_CLONE_STATUS.md`.

| nível | resultado |
|---|---|
| 1 — código | **atingido**: 479 testes passam, 3 pulam por dados ausentes |
| 2 — dados | **atingido por documentação** (aquisição, hash, licença) |
| 3 — pipeline | **atingido (amostra)**: 14 municípios, diferença 0,000 |
| 4 — ciência | **atingido**: replicação independente reexecutada |

## 7. Replicação independente

Ver `docs/statistics/INDEPENDENT_REPLICATION.md`.

| item | resultado |
|---|---|
| casos manuais | **8/8** |
| janelas reais | 90 |
| diferença máxima no déficit | **4,3 × 10⁻⁶ mm** |
| defeito D124 | **encontrado** (excedente 15 mm vs 5 mm) |
| ET0 | divergência de convenção de −1,1% mediana |

## 8. Análise de poder

Ver `docs/statistics/STATISTICAL_POWER_AND_MDE_REPORT.md`.

| cultura | clusters | MDE déficit | erro tipo I | poder no MDE |
|---|---:|---:|---:|---:|
| soja | 48 | 1,14 kg/ha/mm | 7,8% | 88% |
| milho | 56 | 2,11 | 6,0% | 92% |
| milho 2ª | 41 | 3,36 | 10,3% | 94% |

Efeito de desenho: dobrar municípios → SE × 0,996; anos 9→15 → SE × 0,775.

## 9. Conclusões defensáveis

Ver `docs/scientific/CLAIMS_AND_LIMITATIONS.md`. Em resumo:

**Podemos afirmar:** a janela histórica estava errada em um mês inteiro; o
painel corrigido reproduz; o déficit é aritmeticamente correto; existe associação
entre déficit e produtividade da soja (−2,27 kg/ha/mm, EP 0,40).

**Não podemos afirmar:** causalidade; generalização nacional; contraste regional
(não identificado); duração × intensidade (não identificável); vantagem preditiva
do bloco hídrico; efeito de temperatura (inconclusivo por poder); preço local.

## 10. Prontidão para o produto

Ver `docs/product/PRODUCTIZATION_READINESS.md`. Nada foi implementado. O único
candidato defensável é **contexto agroclimático descritivo**. Alerta de safra e
indicador de oferta estão fora: não há validação preditiva.

## 11. Limitações

1. Clima de reanálise **não validado contra estação** — 627.381 registros INMET
   disponíveis e não usados. É a maior lacuna.
2. Sem vintage da PAM: revisões não auditáveis.
3. Build completo do canônico não executado (amostra de 14 municípios).
4. Manifestos não bit-reprodutíveis (`generated_at`).
5. ET0 fora da convenção FAO-56.
6. Milho 2ª safra usa rendimento anual por limitação da fonte.
7. Cobertura de 48,3% do território indicado.
8. `SADEN-TCC` **não foi verificado** (fora de escopo por decisão).

## 12. Decisões

D120 a D127 (D116–D119 já estavam ocupadas pela V3.5):

| # | decisão |
|---|---|
| D120 | a etapa é consolidação, não expansão |
| D121 | Áreas Operacionais excluídas por regra explícita |
| D122 | flags da PAM não geram exclusão |
| D123 | fonte de clima declarada na configuração |
| D124 | excedente superestimado; não corrigido retroativamente |
| D125 | p-valores liberais com 41–56 clusters |
| D126 | mais municípios não aumenta o poder; mais clusters sim |
| D127 | ponto de entrada único, legacy preservado |

## 13. Testes

| item | valor |
|---|---|
| total | **482** (458 herdados + 24 novos) |
| falhas | 0 |
| compilação | limpa |
| em clone limpo | 479 passaram, 3 pularam |

Novos testes cobrem: casos manuais da replicação, conservação de água, D124,
ET0 contra valor de referência, agregação mensal, MDE, quantil t, cenários de
desenho, decomposição de variância, configuração do pipeline, exclusão de
unidades operacionais, `SADEN_DATA_ROOT` e classificação da PAM.

## 14. Bundle

`SADEN_TECHNICAL_CONSOLIDATION_2026-11-14` — ver `BUNDLE_INFO.txt` ao lado do
arquivo. Inclui código, configuração, testes, relatórios, decisões e
documentação de recuperação. **Não** inclui os 6,3 GB de derivados, dados de
terceiros não redistribuíveis, `SADEN-TCC`, credenciais ou caches.

## 15. Próximos passos

Por ordem de risco/custo (`NEXT_ACTIONS.md`):

1. **wild cluster bootstrap** no fluxo oficial (corrige R1);
2. manifestos determinísticos (corrige R16);
3. build completo do pipeline canônico (fecha R17);
4. **validar o clima contra INMET** (corrige R4 — o maior risco aberto);
5. só depois, MG (D119), por acrescentar *clusters*.

Não recomendado: nova hipótese de temperatura com o desenho atual, mais
municípios nas UFs existentes, novo contraste regional sem variação interna.
