# V3.5 — VALIDATION MATRIX

## Integridade

| verificação | método | resultado |
|---|---|---|
| branch parte da V3.4 | `git rev-parse` após `checkout -b` | ✔ `b9e7098` |
| `main` / `v1-final` | `git rev-parse` | ✔ `3f7ad33` |
| V3.0–V3.3 | `git rev-parse` | ✔ `40fd6aa` / `345b22e` / `3bf9360` / `6eff88c` |
| bundle V3.4 | `Get-FileHash` | ✔ `49A584F3…D33BFAA5` |
| `SADEN-TCC/` intocado | nenhum comando fora do repo | ✔ |
| sem force push / reset / reescrita | histórico linear | ✔ |

## Dados de SP

| verificação | método | resultado |
|---|---|---|
| códigos IBGE únicos, prefixo 35, sem colisão | teste `test_sp_registry_is_complete_and_disjoint_from_legacy` | ✔ 645 |
| união = históricos + SP | `test_combined_registry_is_the_union` | ✔ 2.427 |
| snapshot fiel do cadastro histórico | `test_legacy_snapshot_matches_the_live_registry` | ✔ |
| clima completo | manifesto: 645/645, 0 falhas | ✔ |
| janela corrigida aplicada | `v35_build_windows` usa `cycle.window_bounds(corrected=True)` | ✔ |
| descritores da V3.3 | mesma função `_descriptors` | ✔ |
| chaves únicas nas linhas de SP | `test_sp_rows_have_unique_keys_and_valid_states` | ✔ |
| água cobre as mesmas chaves | `test_water_rows_cover_the_same_keys_as_the_window_rows` | ✔ |
| nenhum dado sintético | revisão dos scripts + manifesto | ✔ |

## Painel e classificação

| verificação | método | resultado |
|---|---|---|
| painel histórico preservado | `test_expanded_panel_preserves_legacy_rows_exactly` | ✔ 19.402 + 10.805 |
| `v31_panel_windows.csv` intocado | hash e commit | ✔ |
| seis estados inalterados no mapeamento | `test_mapping_extension_does_not_change_the_six_states` | ✔ 0 divergências |
| SP tem MRS 1 e MRS 3 | `test_sp_has_both_mrs1_and_mrs3_in_the_mapping` | ✔ 44 / 168 |
| só SP quebra o confundimento | `test_only_sp_breaks_the_region_uf_confounding` | ✔ `["SP"]` |
| blocos históricos estáveis | `test_spatial_blocks_of_legacy_municipalities_are_stable` | ✔ 0 reatribuições |

## Modelos

| verificação | método | resultado |
|---|---|---|
| V3.4 reproduzida exatamente | Experimento A | ✔ 1.661,2 / 592,7 / 1.272,3 |
| M0/M1/M2 reestimados | Experimento B | ✔ |
| amostras não comparadas diretamente | nota em cada tabela + Experimento C | ✔ |
| M2+água com a especificação da V3.3 | mesmo `MODELS` importado | ✔ |
| nenhum preditor novo | revisão do código | ✔ |

## Inferência

| verificação | método | resultado |
|---|---|---|
| bootstrap por ano e por município | dois `_bootstrap_group_D` | ✔ |
| contraste por grupo exato | `test_group_delta_subtracts_m2_from_water_block` | ✔ |
| bootstrap recupera diferença conhecida | teste com D = +20 | ✔ |
| bootstrap é nulo sem diferença | teste sob H0 | ✔ |
| clusters informados | `G` reportado (7 anos; 4–7 nos demais) | ✔ |
| resultados n.s. não superinterpretados | relatórios classificam como exploratório / n.s. | ✔ |

## Qualidade

| verificação | comando | resultado |
|---|---|---|
| suíte | `pytest geospatial/tests -q` | ✔ **458/458** (442 + 16) |
| compilação | `compileall tools geospatial/agroclimate` | ✔ |
| números dos relatórios | `tools/v35_verify_report.py` | ✔ **72/72**, exit 0 |
| bundle | `git bundle verify` | ✔ ver relatório final |

## Erros encontrados e corrigidos nesta versão

| # | erro | detecção | correção |
|---|---|---|---|
| 1 | status de aquisição sobrescrito por escrita concorrente | entrada `climate` ausente | reexecução da etapa (cache) |
| 2 | painel de SP sem latitude → 0 linhas de janela | `n_window_rows: 0` | junção por `ibge_code` |
| 3 | `Counter.add` inexistente no mapeamento | exceção mascarada por manifesto antigo | reestruturado e reexecutado |
| 4 | blocos calculados com cadastro de 6 UFs descartavam SP | `n_rows` igual entre A e B | cadastro de 7 UFs; verificado 0 reatribuições |
| 5 | teste com import pontilhado e fixture < 30 linhas | falha na suíte | `importlib` e 40 linhas por grupo |
