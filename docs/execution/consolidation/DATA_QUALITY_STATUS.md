# Consolidação — estado da qualidade de dados

**Data:** 2026-11-14
Detalhe: `docs/data_quality/PAM_QUALITY_AUDIT.md`, `docs/data_quality/PANEL_DATA_QUALITY_AUDIT.md`

---

## PAM (produtividade)

| verificação | resultado | estado |
|---|---|---|
| células município–ano–cultura | 43.650 | auditado |
| municípios | 2.425 | auditado |
| chaves duplicadas | **0** | auditado |
| série completa nos 9 anos | 2.425 de 2.425 | auditado |
| criação/extinção de município na série | **0** | auditado |
| rendimento = produção/área (±1%) | 99,8% | auditado |
| divergências > 1% | 66 (mediana 1,75%, máx. 16,7%) | flag, sem exclusão |
| extremos por MAD | 99 | flag, sem exclusão |
| `sem_area` | 7.507 | **não é erro** |
| `plantado_sem_colheita` | 85 | informação válida |
| códigos só no cadastro IBGE | 2 (Áreas Operacionais) | **corrigido** no pipeline |
| revisões históricas | **não mensuráveis** (sem vintage) | limitação |
| validação contra fonte externa | **não feita** | pendente |

**Impacto no painel:** 27 de 30.207 linhas (0,09%), todas em BA (106 linhas).
**Conclusão:** a fonte de produtividade não ameaça os resultados publicados.

## Painel (variáveis ambientais)

| componente | classificação |
|---|---|
| produtividade (PAM) | validado |
| janela corrigida (ZARC) | validado |
| graus-dia, calor extremo, noites quentes | validado |
| ET0 (FAO-56) | validado com ressalva (convenção divergente) |
| balanço hídrico — déficit | **replicado independentemente** |
| balanço hídrico — excedente | **defeito identificado** (D124) |
| precipitação / temperatura / radiação | validado com ressalva (não comparado a estação) |
| CAD observada | validado com ressalva (77,5% de cobertura) |
| polígonos municipais | validado com ressalva (2 unidades operacionais) |
| milho 2ª safra | **incompatível** com a fonte |
| fontes INMET | **não utilizadas** |

## Achados que exigiram correção de código

1. Fonte de clima implícita → declarada em configuração (D123).
2. Unidades operacionais no cadastro → excluídas por regra (D121).
3. `requirements.txt` sem `pytest` → declarado (R14).

## Achados que ficaram como limitação, sem correção

1. Sem vintage da PAM.
2. Clima não validado contra estação.
3. Manifestos não bit-reprodutíveis.
4. `_legacy` e `_corrected` coexistem no mesmo arquivo.
