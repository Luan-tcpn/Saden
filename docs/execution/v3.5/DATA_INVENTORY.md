# V3.5 — DATA INVENTORY

## Novos arquivos de SP (versionados)

| arquivo | conteúdo | linhas |
|---|---|---:|
| `geospatial/data/processed/panel_municipalities_sp.csv` | cadastro de SP com centróide, área, bbox | 645 |
| `geospatial/data/processed/municipality_region_mapping_v35.csv` | mapeamento MRS de 7 UFs | 2.065 |
| `geospatial/data/manifests/v35_cad_polygon_sp.json` | CAD por município e profundidade | 584 |
| `geospatial/data/manifests/v35_sp_acquisition.json` | status e hashes de cada etapa | — |
| `geospatial/data/manifests/v35_region_mapping.json` | distribuição de SP por MRS | — |
| `geospatial/data/manifests/v35_sp_windows.json` | contagens do build de janelas | — |
| `geospatial/data/manifests/v35_models.json` | experimentos A/B/C, dentro de SP, transferência | — |
| `geospatial/data/manifests/v35_coverage_robustness.json` | cobertura, LOO-ano, grupos alternativos | — |

## Snapshot do painel histórico (versionado)

| arquivo | papel |
|---|---|
| `geospatial/data/processed/panel_municipalities_v34.csv` | cópia congelada dos 1.782 municípios dos 6 estados |
| `geospatial/data/processed/v31_panel_windows.csv` | painel analítico de 19.402 linhas — **intocado** |
| `geospatial/data/processed/v33_water_variables.csv` | descritores de 77.608 linhas — **intocado** |

## Derivados de trabalho (fora do Git, regeneráveis)

| arquivo | tamanho aproximado | regenerado por |
|---|---|---|
| `panel_municipalities_v35.csv` | 2.427 linhas | `v35_acquire_sp.py --stage municipalities` |
| `panel_sp_v35.csv` | 19.608 linhas | `v35_acquire_sp.py --stage panel` |
| `climate_daily_sp.csv` | 2.356.185 linhas | `v35_acquire_sp.py --stage climate` |
| `pam_panel_sp.csv` | 46.440 registros | `v35_acquire_sp.py --stage productivity` |
| `zarc_panel_sp.csv` | 1.082.148 linhas | `v35_acquire_sp.py --stage zarc` |
| `v35_sp_windows.csv` / `v35_sp_water.csv` | 10.805 / 43.220 | `v35_build_windows.py` |
| `v35_panel_windows.csv` / `v35_water_variables.csv` | 30.207 / 120.828 | `v35_build_windows.py` |
| `data/external/sp_climate_cache/` | 645 JSONs | cache do clima |

## Fontes externas

| fonte | versão / acesso | hash |
|---|---|---|
| MAPA/ZARC — planilha de macrorregiões sojícolas | congelada na V3.4 | `91126b6b…7458c84` |
| IBGE — malhas municipais 2025 | 2026-11-14 | — |
| NASA POWER (comunidade AG) | 2016–2025 | — |
| IBGE/SIDRA 5457 (PAM) | 2017–2025 | — |
| MAPA/ZARC — tábua de risco | safras 2005/06–2026/27 | — |
| Embrapa Solos (WCS) | estático | CC BY-NC 3.0 BR |

## Estruturas de dependência (milho, painel expandido)

| estrutura | n |
|---|---:|
| UF×ano | 56 |
| município | 1.621 |
| bloco espacial 250 km | 51 (46 históricos + 5 de SP) |
| UF | 7 |
| linha analítica | 11.928 — **não** é observação independente |
