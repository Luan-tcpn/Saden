# V3.3 — VALIDATION MATRIX

## Integridade do repositório

| verificação | método | resultado |
|---|---|---|
| branch parte da V3.2 correta | `git rev-parse HEAD` após `checkout -b` | ✔ `3bf9360` |
| `main` e `v1-final` intactas | `git rev-parse` | ✔ `3f7ad33` |
| V3.0 / V3.1 / V3.2 intactas | `git rev-parse` das três branches | ✔ `40fd6aa` / `345b22e` / `3bf9360` |
| bundle V3.2 intacto | `Get-FileHash` | ✔ `E8EB3F5A…598FE9A4` |
| `SADEN-TCC/` não tocado | nenhum comando fora do repo técnico | ✔ |
| sem force push / reset / reescrita | histórico linear | ✔ |
| tag não sobrescrita | `git tag` | ✔ |

## Dados

| verificação | método | resultado |
|---|---|---|
| painel disponível | leitura do CSV | ✔ 19.402 linhas |
| descritores de estresse gerados | `v33_water_variables.json` | ✔ 4 cenários × 19.402 |
| nenhuma variável `_legacy` na modelagem | teste `test_v33_*` + revisão dos imports | ✔ |
| identidade DEF = ETP − ETR | teste `etr/etp + def/etp ≈ 1` | ✔ |
| limiar de estresse fixo | teste de limiar (0,2 mm não conta) | ✔ |

## Frente A

| verificação | método | resultado |
|---|---|---|
| M2 reproduz a V3.1 | MAE TE | ✔ 592,19 / 1.688,58 / 1.272,40 |
| mesmas linhas de teste entre modelos | `row_codes`, `row_years_raw` | ✔ |
| igualização por célula completa | `cells_at_target` | ✔ 25/25 em todos |
| transformações sem dados de teste | constantes fixas (÷100, ÷1000) | ✔ por construção |
| teste conjunto de bloco | poder e falso-positivo em dados sintéticos | ✔ |
| bootstrap pareado tem p válido | simetria, limites, coerência com IC | ✔ |
| dependência entre candidatos medida antes | `v33_variable_audit.json` | ✔ |

## Frente B

| verificação | método | resultado |
|---|---|---|
| reprodução dos coeficientes | comparação com os manifests originais | ✔ 1,5e-6 / 3,6e-15 / 9,2e-8 |
| reprodução dos p-valores históricos | `log10(p_mine/p_hist)` | ✔ máx. 5,3e-4 (V2.7) / 6,8e-4 (V3.0) |
| reprodução do Holm histórico | `p_adjusted` da V2.7 | ✔ idêntico; contagens 10/4 idênticas |
| identidade do VCV duplo | `V_A + V_B − V_A∩B` | ✔ teste dedicado |
| identificação dos clusters | contagem UF×ano e municípios | ✔ teste em dados sintéticos |
| regra de classificação | 7 casos canônicos | ✔ |
| famílias não rearranjadas | 21 / 15 / 9, como no original | ✔ |
| cenários C1/C2/C3 separados | manifesto + registro | ✔ |

## Qualidade

| verificação | comando | resultado |
|---|---|---|
| suíte completa | `pytest geospatial/tests -q` | ✔ **427/427** |
| testes novos | `test_v33_functional_form.py` | ✔ 17 |
| compilação | `compileall tools geospatial/agroclimate` | ✔ |
| manifests legíveis | `json.load` nos 7 arquivos | ✔ |
| números do relatório conferidos | `tools/v33_verify_report.py` | ✔ **88/88**, exit 0 |
| bundle | `git bundle verify` | ✔ ver relatório final |
