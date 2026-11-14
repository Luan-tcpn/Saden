# SADEN — Pipeline canônico, configuração e ferramentas históricas

**Data:** 2026-11-14
**Ponto de entrada único:** `tools/pipeline/build_panel.py`
**Configuração:** `config/panel_v35.json`

---

## 1. Por que existe um pipeline canônico

Até a V3.5 o painel era construído por **três caminhos concorrentes**:

| script | o que fazia | entrada | saída |
|---|---|---|---|
| `v31_rebuild_panel.py` | janela `legacy` **e** `corrected`, cenários de CAD, graus-dia | `agroclimatic_productivity_panel.csv` + clima | `v31_panel_windows.csv` |
| `v33_water_variables.py` | ET0 diária, balanço T&M, descritores de estresse | painel de janelas | `v33_water_variables.csv` |
| `v35_build_windows.py` | repete janela + água para SP | `panel_sp_v35.csv` + clima SP | `v35_panel_windows.csv`, `v35_water_variables.csv` |

Eles compartilham lógica, mas **cada um reimplementa a orquestração**. Não havia
ponto de entrada único, configuração declarativa, nem prova de equivalência.

O pipeline canônico resolve a orquestração **sem reimplementar cálculo**: chama
as funções já validadas (`v31_rebuild_panel._aggregate` para janela,
`v33_water_variables._descriptors` para estresse, `agroclimate.*` para física),
lendo tudo de uma configuração versionada.

Prova de equivalência: com `--codes` de 14 municípios em 7 UFs, o painel
reconstruído é **bit-idêntico** ao V3.5 — diferença máxima **0,000** em 10
variáveis × 204 linhas (`panel_canonical_build.json`).

## 2. Como usar

```bash
# valida configuração, arquivos, cadastro municipal e CAD
python tools/pipeline/build_panel.py --stage validate

# reconstrói janela + descritores hídricos (todos os municípios da config)
python tools/pipeline/build_panel.py --stage build

# subconjunto explícito (usado no teste de clone limpo)
python tools/pipeline/build_panel.py --stage build --codes 2900355,3500105

# compara com o painel de referência V3.5
python tools/pipeline/build_panel.py --stage verify

# tudo
python tools/pipeline/build_panel.py --stage all
```

Saídas: `geospatial/data/processed/panel_canonical_windows.csv` e
`panel_canonical_water.csv`, mais o manifesto
`geospatial/data/manifests/panel_canonical_build.json` (com SHA-256, contagens,
itens ignorados e tempo).

### 2.1. Dados externos

Os derivados somam **6,3 GB** e ficam **fora do Git**. Para rodar um clone limpo
sem copiá-los:

```bash
set SADEN_DATA_ROOT=C:\caminho\para\geospatial\data
python tools/pipeline/build_panel.py --stage all
```

Variável ausente = comportamento padrão (caminhos relativos ao repositório).

## 3. Configuração

`config/panel_v35.json` declara período, UFs, culturas, fontes, arquivos de
entrada, CAD por cultura, cenários de CAD, método de ET0 e **regras de
filtragem**. Nenhuma constante operacional fica espalhada em scripts.

Regras que agora são **explícitas** e não mais implícitas:

| regra | valor | por quê |
|---|---|---|
| `require_climate_source` | `NASA-POWER` | o arquivo de clima contém duas fontes sob a mesma chave |
| `exclude_municipality_name_patterns` | `Área Operacional` | duas unidades não municipais no cadastro IBGE |
| `require_status` | `paired_usable` | linhas analíticas válidas |
| `min_window_days` | 30 | janela curta não sustenta agregação |
| `coverage_reference_cad_mm` | 50,0 | CAD de referência declarada (não medida) |

## 4. Classificação das ferramentas

### CANONICAL

| arquivo | papel |
|---|---|
| `tools/pipeline/build_panel.py` | **único ponto de entrada oficial** do painel |

### VALIDATION

| arquivo | papel |
|---|---|
| `tools/audit_pam_quality.py` | auditoria de qualidade do IBGE/PAM (chaves, zeros, rendimento, extremos, crosswalk) |
| `tools/v33_verify_report.py` | confere números de relatório contra manifests |
| `tools/v34_verify_report.py`, `tools/v35_verify_report.py` | equivalentes para V3.4 e V3.5 |
| `tools/validate_v27_stats.py` | verificação dos números da V2.7 |
| `tools/analysis/statistical_power.py` | poder, MDE e calibração de erro tipo I |

### INDEPENDENT_REPLICATION

| arquivo | papel |
|---|---|
| `tools/independent_replication/water_balance_reference.py` | T&M e FAO-56 reimplementados do zero, com casos manuais |

### LEGACY_REPRODUCTION

Estes scripts **não devem ser alterados**: são a única forma de reproduzir os
artefatos publicados de cada versão.

| arquivo | versão | reproduz |
|---|---|---|
| `tools/s27_*.py`, `tools/s28_*.py`, `tools/s29_*.py` | V2.7–V2.9 | sensoriamento, CAD, fenologia, cobertura |
| `tools/v30_*.py` | V3.0 | aquisição de CAD, recálculo do painel |
| `tools/v31_rebuild_panel.py`, `v31_models.py`, `v31_neighbors.py` | V3.1 | janela legacy e corrigida, baselines de vizinhos |
| `tools/v32_*.py` | V3.2 | inclinações por UF, sensibilidade de emparelhamento |
| `tools/v33_water_variables.py`, `v33_inference_audit.py`, `v33_functional_form.py`, `v33_variable_audit.py` | V3.3 | água, auditoria de inferência |
| `tools/v34_*.py` | V3.4 | classificação regional, contraste |
| `tools/v35_build_windows.py`, `v35_models.py`, `v35_acquire_sp.py`, `v35_coverage_and_robustness.py` | V3.5 | expansão SP, rebaseline |

### EXPERIMENTAL

| arquivo | situação |
|---|---|
| `tools/calibrate_wild_bootstrap.py` | calibração de wild cluster bootstrap; **não incorporado** ao fluxo |
| `tools/v32_legacy_pairing_sensitivity.py` | análise de sensibilidade pontual |

## 5. Contrato de dados do painel

`v35_panel_windows.csv` — 30.207 linhas × 81 colunas.

- **chave:** `ibge_code` + `crop` + `safra`
- **cultura:** `soja`, `milho`, `milho_2` (este último **incompatível** com a
  fonte: a PAM não separa safras)
- **duas versões por variável:** sufixo `_legacy` (errada, só para reproduzir
  D97) e `_corrected` (usar sempre)
- **CAD:** `deficiency_cad_0_{60,100,200}` com CAD observada por município
- **latitude/longitude:** preenchidas apenas para SP (10.805 linhas); para o
  resto, use o centróide do cadastro municipal

## 6. Regras de contribuição

1. Nenhum caminho novo de construção de painel. Alterações vão no canônico.
2. Script legacy só muda com versão explicitamente identificada.
3. Toda nova regra de filtragem entra na configuração, não no código.
4. Toda saída gera manifesto com hash.
