# V3.3 — DATA INVENTORY

## Entradas (não derivadas)

| arquivo | papel | licença | no Git |
|---|---|---|---|
| `geospatial/data/processed/climate_daily.csv` | clima diário NASA POWER (~1 GB) | aberta | não |
| `geospatial/data/processed/agroclimatic_productivity_panel.csv` | painel base | aberta | não |
| `geospatial/data/processed/panel_municipalities.csv` | centróides e UF | aberta | sim |
| `geospatial/data/manifests/v30_cad_polygon.json` | CAD por município e profundidade | CC BY-NC 3.0 BR | sim (estatísticas) |

## Derivados da V3.1 usados

| arquivo | linhas | papel |
|---|---:|---|
| `v31_panel_windows.csv` | 19.402 | fonte única de variáveis (`_corrected` e `_legacy`) |

As colunas `_legacy` são usadas **somente** pela auditoria histórica (Frente B),
para reproduzir as versões originais. As ferramentas de modelagem da Frente A só
leem `_corrected`, e há teste que falha se aparecer `_legacy` nelas.

## Derivados produzidos pela V3.3

| arquivo | conteúdo |
|---|---|
| `geospatial/data/processed/v33_water_variables.csv` | 4 cenários de CAD × 19.402 linhas: déficit, duração, sequência, armazenamento mínimo, ETR/ETP, timing |
| `geospatial/data/manifests/v33_water_variables.json` | metadados e distribuição por cenário |
| `geospatial/data/manifests/v33_variable_audit.json` | degeneração e matriz de correlação within |
| `geospatial/data/manifests/v33_functional_form.json` | 7 modelos × 3 culturas + inferência + família confirmatória |
| `geospatial/data/manifests/v33_functional_robustness.json` | leave-one-UF/ano |
| `geospatial/data/manifests/v33_inference_audit.json` | 45 hipóteses auditadas, 5 esquemas cada |
| `geospatial/data/manifests/v33_inference_audit.csv` | tabela de rastreabilidade achatada |

## Cenários de CAD e por que importam

| cenário | mediana de meses de estresse | linhas sem estresse | uso |
|---|---:|---:|---|
| 50 mm (histórico) | 2 | 18% | sensibilidade |
| 0–60 cm | 1 | 35% | **primário** (milho, D99) |
| 0–100 cm | 0 | 54% | **primário** (soja, D99); degenera para milho |
| 0–200 cm | 0 | 86% | sensibilidade; degenera |

Com CAD 0–100 ou 0–200 a duração do estresse não tem variação — não é escolha
metodológica, é consequência física dos dados.

## Estruturas de dependência (não confundir)

| estrutura | n | papel |
|---|---:|---|
| UF×ano | 31–48 | unidade da exposição climática (D104) |
| município | 505–1.225 | segunda dimensão do agrupamento duplo |
| bloco espacial 250 km | 46 | esquema histórico; diagnóstico |
| ano | 5–9 | efeito fixo |
| linha do painel | 19.402 | **não** é observação independente |
