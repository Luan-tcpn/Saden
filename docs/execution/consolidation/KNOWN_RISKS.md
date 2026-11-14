# Consolidação técnica — riscos conhecidos

**Data:** 2026-11-14 · Atualizado durante a execução.

---

## Riscos científicos

| # | risco | gravidade | estado |
|---|---|---|---|
| R1 | **p-valores liberais** (erro tipo I 6–10% para nominal 5%) | **alta** | conhecido, declarado (D125); mitigação planejada |
| R2 | ET0 fora da convenção FAO-56 (`es(Tmean)`, vento 60% menor) | média | conhecido, declarado; correção exige versão nova |
| R3 | Excedente superestimado na referência (D124) | baixa | conhecido; variáveis não sustentadas, nenhuma conclusão depende |
| R4 | Clima de reanálise não validado contra estação | **alta** | **não mitigado** — 627.381 registros INMET disponíveis e não usados |
| R5 | Milho 2ª safra usa rendimento anual (fonte não separa safras) | média | limitação da fonte; **não resolvível** com dados atuais |
| R6 | Poder insuficiente para temperatura/graus-dia | média | declarado; MDE 203–433 kg/ha por °C |
| R7 | Cobertura de 48,3% do território indicado | média | declarado; nenhuma afirmação nacional |
| R8 | ET0/déficit com viés sistemático afetam comparação com literatura | média | declarado em `INDEPENDENT_REPLICATION.md` |

## Riscos de dados

| # | risco | gravidade | estado |
|---|---|---|---|
| R9 | Revisões da PAM não auditáveis (sem vintage) | média | **não mitigado**; requer segunda extração no tempo |
| R10 | 2.020 linhas INMET `paired_usable` no painel base | média | armadilha documentada (D123) |
| R11 | Latitude exportada só para SP | baixa | contornado (centróide do cadastro) |
| R12 | 2 unidades operacionais no cadastro | baixa | **corrigido** por regra explícita (D121) |
| R13 | `_legacy` e `_corrected` no mesmo arquivo | baixa | risco de leitura humana, não de cálculo |

## Riscos de engenharia

| # | risco | gravidade | estado |
|---|---|---|---|
| R14 | `requirements.txt` sem `pytest` | **alta** (impedia rodar testes em ambiente limpo) | **corrigido** |
| R15 | Derivados de 6,3 GB fora do Git | média | documentado; `SADEN_DATA_ROOT` |
| R16 | Manifestos não bit-reprodutíveis (timestamp) | baixa | documentado; ação em `NEXT_ACTIONS.md` |
| R17 | Build completo do canônico não executado | média | provado em amostra de 14 municípios |
| R18 | `tools/__pycache__` no disco | baixa | já ignorado por `.gitignore` |

## Riscos de processo

| # | risco | gravidade | estado |
|---|---|---|---|
| R19 | Texto acadêmico pode citar resultados retratados | **alta, mas fora de escopo** | **não verificado**, por decisão explícita |
| R20 | Três caminhos históricos ainda existem | baixa | intencional; classificados em `docs/PIPELINE.md` |
| R21 | `tools/calibrate_wild_bootstrap.py` fora do fluxo | média | é a ação 1.1 |

## O risco que mais preocupa

**R4 (clima não validado).** Todos os resultados dependem de reanálise NASA
POWER. Existe no repositório uma fonte independente — 627.381 registros diários
de estações INMET — que nunca foi comparada. Enquanto isso não for feito, a
afirmação mais forte que se pode fazer é "o resultado é consistente com a
reanálise", não "o resultado é consistente com o clima observado".
