# V3.4 — DATA INVENTORY

## Fontes externas usadas nesta versão

| fonte | arquivo | tamanho | hash | no Git |
|---|---|---:|---|---|
| MAPA/ZARC — planilha oficial de macrorregiões sojícolas | `geospatial/data/external/MacrorregioSojicolasAtualizado_2025.xlsx` | 140.020 B | SHA-256 `91126b6b512724cd90ab2bfc951ac418c0114bf78a697562a9c8c377f7458c84` | **não** (arquivo de terceiro) |

O download é reprodutível por `tools/v34_region_mapping.py` (URL oficial,
UA de navegador e referer). O PDF do mesmo normativo foi consultado; nesta rede
o download programático retorna 404 (ver `KNOWN_RISKS.md` R8).

## Derivados produzidos

| arquivo | conteúdo | no Git |
|---|---|---|
| `geospatial/data/processed/municipality_region_mapping.csv` | código IBGE → UF, região edafoclimática, macrorregião | **sim** |
| `geospatial/data/manifests/v34_region_mapping_long.csv` | pares UF–município dos 6 estados | **sim** |
| `geospatial/data/manifests/v34_region_mapping.json` | hash, cobertura, limitações | **sim** |
| `geospatial/data/manifests/v34_coverage_identifiability.json` | cobertura, suporte, confundimento, variação dentro de estado | **sim** |
| `geospatial/data/manifests/v34_regional_contrast.json` | Δ por região/UF/UF×macro, D, IC, interação | **sim** |
| `geospatial/data/manifests/v34_regional_robustness.json` | LOO-UF, LOO-ano, dentro de estado | **sim** |
| `geospatial/data/manifests/v34_regional_sensitivity.json` | 5 classificações, 3 ponderações, decis | **sim** |
| `geospatial/data/manifests/v34_coverage_gap.json` | denominador oficial, lacuna, prioridades | **sim** |
| `geospatial/data/manifests/v34_municipality_delta/*.csv` | Δ por município (3 culturas) | **sim** |
| `docs/figures/v34/*.png` | 6 figuras | **sim** |

## Entradas herdadas (não alteradas)

| arquivo | papel |
|---|---|
| `geospatial/data/processed/v31_panel_windows.csv` | 19.402 linhas; `_corrected` e `_legacy` |
| `geospatial/data/processed/v33_water_variables.csv` | descritores de estresse por cenário de CAD |
| `geospatial/data/processed/panel_municipalities.csv` | 1.782 municípios dos 6 estados, com centróide |
| `geospatial/data/manifests/v30_cad_polygon.json` | CAD por município (CC BY-NC 3.0 BR) |
| `geospatial/data/manifests/pam_panel.json` | **apenas as 6 UFs** — limita o diagnóstico de produção |

## Licenças

* **MAPA/ZARC**: ato normativo público; a planilha é redistribuída pelo próprio
  governo. O repositório guarda o **derivado** (mapeamento municipal) + hash, não
  o arquivo.
* **Embrapa Solos (CAD)**: CC BY-NC 3.0 BR — rasters **não** versionados nem
  redistribuídos; somente estatísticas.
* **NASA POWER / IBGE / PAM**: abertas.

## Estruturas de dependência (não confundir)

| estrutura | n (milho) | papel |
|---|---:|---|
| UF×ano | 48 (Sul+Cerrado) | unidade da exposição climática (D104) |
| município | 1.036 | segunda dimensão do agrupamento duplo |
| bloco espacial 250 km | 46 | esquema histórico; sensibilidade |
| **UF** | **6** | unidade do *tratamento* regional — o gargalo |
| região (Sul/Cerrado) | **2** | tratamento; aninhado em UF |
