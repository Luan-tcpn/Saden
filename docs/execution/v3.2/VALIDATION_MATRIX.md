# V3.2 — VALIDATION MATRIX

O que foi verificado, como, e com que resultado. `✔` = executado e aprovado.

## Integridade do repositório

| verificação | método | resultado |
|---|---|---|
| branch parte da V3.1 correta | `git rev-parse HEAD` após `checkout -b` | ✔ `345b22e` |
| `main` intacta | `git rev-parse main` | ✔ `3f7ad33` |
| tag `v1-final` intacta | `git rev-parse v1-final^{commit}` | ✔ `3f7ad33` |
| V3.0 intacta | `git rev-parse v3/cad-integrated-agroclimatic-panel` | ✔ `40fd6aa` |
| V3.1 intacta | `git rev-parse v3/window-spatial-generalization` | ✔ `345b22e` |
| bundle V3.1 intacto | `Get-FileHash` | ✔ `88A66B39…406AA82` |
| `SADEN-TCC/` não tocado | nenhum comando fora do repo técnico | ✔ |
| sem force push / reset destrutivo | histórico linear, `git log` | ✔ |

## Dados

| verificação | método | resultado |
|---|---|---|
| painel disponível | leitura de `v31_panel_windows.csv` | ✔ 19.402 linhas, 79 colunas |
| nenhuma variável `_legacy` | teste `test_v32_tools_never_reference_legacy_variables` | ✔ |
| contagem por cultura × UF | `v32_coverage_diagnostics.json` | ✔ 15 células |
| joins sem perda | `v31_models.load_rows` → `dropped` | ✔ 0 em todas as categorias |

## Modelos

| verificação | método | resultado |
|---|---|---|
| M2 comum reproduz a V3.1 | MAE TE comparada ao relatório V3.1 | ✔ 592,19 / 1.688,58 / 1.272,40 |
| linhas de teste idênticas entre modelos | `row_codes`, `row_years_raw`, `test_blocks` | ✔ teste dedicado |
| λ escolhido só no treino | `select_ridge_penalty` recebe apenas o pool | ✔ por construção + teste de determinismo |
| λ = mínimo do caminho avaliado | teste de invariante | ✔ |
| ridge → inclinação comum quando λ→∞ | teste numérico | ✔ |
| ridge = MQO quando λ=0 | teste numérico | ✔ |
| encolhimento monotônico em λ | teste numérico | ✔ |
| interações alinhadas treino/teste | `interaction_states` fixo | ✔ teste de forma |
| equalização por célula completa | `cells_at_target` / `cells_below_target` | ✔ 25/25 em todas as especificações |

## Inferência

| verificação | método | resultado |
|---|---|---|
| agrupamento duplo UF×ano + município | `cluster_info` | ✔ contagens conferidas em teste |
| `F(q, G−1)` | `f_sf` contra valor conhecido | ✔ F(1,10) 5% = 4,9646 |
| Wald conjunto | teste com VCV diagonal conhecida | ✔ |
| poder do teste global | dados sintéticos com inclinações diferentes | ✔ rejeita, recupera ordem |
| ausência de falso positivo | dados sintéticos com inclinação comum | ✔ não rejeita |
| Holm na família confirmatória | `robust.holm_adjust`, 6 testes | ✔ |
| BH na família exploratória | implementação local, 9 testes | ✔ |
| bootstrap duplo (bloco e UF×ano) | ambos reportados em todo ΔMAE | ✔ |

## Robustez

| verificação | método | resultado |
|---|---|---|
| leave-one-UF-out | 6 UFs do milho | ✔ sinal inverte em 4 de 6 |
| leave-one-year-out | 8 anos | ✔ estável (−28,5 a −111,3) |
| sensibilidade a λ | λ fixos 0,1/1/10 | ✔ reportado |
| colinearidade | correlação within | ✔ −0,60 a −0,67, documentada |
| fallback do M1c decomposto | subconjuntos coberto/fallback | ✔ |

## Qualidade

| verificação | comando | resultado |
|---|---|---|
| suíte completa | `pytest geospatial/tests -q` | ✔ **410/410** |
| testes novos V3.2 | `test_v32_heterogeneity.py` | ✔ 17 |
| compilação | `compileall tools geospatial/agroclimate` | ✔ |
| manifests escritos e legíveis | `json.load` nos 5 arquivos | ✔ |
| bundle | `git bundle verify` | ✔ ver relatório §22 |
