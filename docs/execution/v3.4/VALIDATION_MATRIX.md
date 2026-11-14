# V3.4 — VALIDATION MATRIX

## Integridade

| verificação | método | resultado |
|---|---|---|
| branch parte da V3.3 | `git rev-parse HEAD` após `checkout -b` | ✔ `6eff88c` |
| `main` / `v1-final` intactas | `git rev-parse` | ✔ `3f7ad33` |
| V3.0 / V3.1 / V3.2 / V3.3 intactas | `git rev-parse` | ✔ `40fd6aa` / `345b22e` / `3bf9360` / `6eff88c` |
| bundle V3.3 | `Get-FileHash` | ✔ `C6A863C4…BE617763D` |
| `SADEN-TCC/` não tocado | nenhum comando fora do repo | ✔ |
| sem force push / reset / reescrita | histórico linear | ✔ |

## Classificação regional

| verificação | método | resultado |
|---|---|---|
| hash da planilha oficial | SHA-256 no manifesto | ✔ `91126b6b…7458c84` |
| parse sem transcrição manual | `v34_region_mapping.py` | ✔ 4.286 pares |
| códigos IBGE únicos no mapeamento | contagem de duplicados | ✔ 0 |
| correspondência com a lista de municípios | join por nome normalizado | ✔ 1.422/1.782; 360 são sem indicação de soja |
| classificação congela antes das estimativas | ordem de commits e datas nos documentos | ✔ protocolo e pré-registro datados antes |
| MRS 2 fora do contraste | código (`MACRO_GROUP`) | ✔ `Transicao` excluída |
| nenhuma mudança de grupo após resultado | revisão do `MACRO_GROUP` e do protocolo | ✔ |

## Identificação

| verificação | método | resultado |
|---|---|---|
| confundimento região × UF | Cramér's V por cultura | ✔ 1,000 nas três |
| UFs nos dois grupos | crosstab | ✔ nenhuma |
| clusters UF×ano informados | `df2` dos testes | ✔ 47 (milho, pós-df), 39 (soja), 27 (milho 2ª) |
| variação dentro de estado disponível | `within_state_variation` | ✔ GO, MS, PR, BA |
| suporte climático comparado | mediana e p10–p90 por grupo | ✔ reportado (0,97 × 74,4 mm no milho) |

## Modelos e comparação

| verificação | método | resultado |
|---|---|---|
| M2 reproduz a V3.3 | MAE nacional | ✔ diferença apenas por amostra (74 linhas sem região) |
| mesmas linhas de teste entre modelos | `row_codes` | ✔ pareamento por `row_codes` |
| Δ por região calculado nas mesmas linhas | máscara por grupo sobre o mesmo vetor | ✔ |
| Δ por UF e por UF×macrorregião no mesmo protocolo | `per_uf`, `per_uf_macroregion` | ✔ |
| alinhamento (município, ano) nos decis | chave composta; contagem de ausentes | ✔ 0 sem alinhamento (após correção) |

## Inferência

| verificação | método | resultado |
|---|---|---|
| agrupamento duplo UF×ano + município | `two_way_cluster_vcov` | ✔ teste dedicado (identidade V_A+V_B−V_A∩B) |
| dois bootstraps para D | UF×ano e bloco | ✔ ambos reportados |
| família confirmatória de 2, Holm | `robust.holm_adjust` | ✔ declarada antes |
| precedência de E sobre B | regra no pré-registro | ✔ aplicada |

## Robustez

| verificação | método | resultado |
|---|---|---|
| leave-one-UF-out | 6 exclusões | ✔ milho estável; milho 2ª inverte |
| leave-one-ano-out | 8–9 exclusões | ✔ milho estável; soja inverte em 1 |
| dentro de estado | GO, MS, PR, BA | ✔ PR significativo (p=0,0022) |
| 5 classificações | sensibilidade | ✔ D negativo em todas |
| 3 ponderações | observação, município, UF | ✔ D negativo em todas |
| suporte comum (decis) | 10 decis | ✔ 9/10 negativos no milho |

## Qualidade

| verificação | comando | resultado |
|---|---|---|
| suíte | `pytest geospatial/tests -q` | ✔ **442/442** |
| testes novos | `test_v34_regional.py` | ✔ 15 |
| compilação | `compileall tools geospatial/agroclimate` | ✔ |
| figuras inspecionadas | leitura das imagens | ✔ 1 layout corrigido |
| números do relatório | `tools/v34_verify_report.py` | ✔ **86/86**, exit 0 |
| bundle | `git bundle verify` | ✔ ver relatório final |

## Erros encontrados e corrigidos nesta versão

| # | erro | detecção | correção |
|---|---|---|---|
| 1 | déficit mapeado por `ibge_code` (colapsava anos) na análise por decis | revisão da chave de junção | chave (município, ano); 0 ausentes |
| 2 | análise dentro de estado com 3 dobras (protocolo diferente) | comparação com o resultado principal | recomputado com 5 dobras; spread do PR 144 → 20 |
| 3 | rótulos de D colidindo com o título na figura 3 | inspeção visual da imagem | layout refeito |
