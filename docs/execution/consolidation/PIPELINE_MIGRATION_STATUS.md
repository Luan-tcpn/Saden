# Consolidação — estado da migração do pipeline

**Data:** 2026-11-14 · Detalhe: `docs/PIPELINE.md`

---

## Situação antes

Três caminhos concorrentes construíam o mesmo painel, cada um com sua própria
orquestração:

| caminho | entrada | saída |
|---|---|---|
| `tools/v31_rebuild_panel.py` | painel base 6 UFs | `v31_panel_windows.csv` |
| `tools/v33_water_variables.py` | painel de janelas | `v33_water_variables.csv` |
| `tools/v35_build_windows.py` | painel SP | `v35_panel_{windows,water}.csv` |

Não havia ponto de entrada único, configuração declarativa, nem prova de que os
três concordavam.

## Situação depois

| item | estado |
|---|---|
| **ponto de entrada único** | `tools/pipeline/build_panel.py` |
| **configuração declarativa** | `config/panel_v35.json` |
| **reimplementação de cálculo** | **nenhuma** (chama as funções validadas) |
| **etapas** | validate → build → verify |
| **manifesto** | SHA-256 das saídas, contagens, itens ignorados, tempo |
| **dados externos** | `SADEN_DATA_ROOT` resolve os 6,3 GB fora do repositório |
| **scripts históricos** | preservados, não convertidos em wrappers |

## Prova de equivalência

14 municípios, 7 UFs, 204 linhas de janela e 816 de água:

| variável | diferença máxima |
|---|---:|
| precipitação acumulada | **0,000** |
| temperatura média | **0,000** |
| graus-dia | **0,000** |
| dias de calor extremo | **0,000** |
| ET0 acumulada | **0,000** |
| déficit | **0,000** |
| excedente | **0,000** |
| déficit com CAD 60/100/200 | **0,000** |

2.040 comparações numéricas, todas exatas.

## O que mudou de comportamento

| regra | antes | depois |
|---|---|---|
| fonte de clima | filtro implícito na leitura | `require_climate_source` na config; descarte contado |
| unidades operacionais | entravam no cadastro | excluídas por padrão de nome |
| janela mínima | espalhada nos scripts | `min_window_days` na config |
| CAD de referência | constante no código | `coverage_reference_cad_mm` na config |
| perfil de solo | constante por script | `soil_profile` na config |

Nenhum **resultado** mudou: a equivalência é bit-a-bit.

## Pendência

O build completo (2.425 municípios, ~2 h) não foi executado. A diferença em
relação à amostra é de escala, não de código — mas não foi medida ponta a ponta.
Registrado como R17 e como ação 1.3.
