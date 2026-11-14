# V3.2 — DATA INVENTORY

## Dados de entrada (não derivados)

| arquivo | linhas | tamanho | fonte | licença | no Git? |
|---|---:|---:|---|---|---|
| `geospatial/data/processed/climate_daily.csv` | ~4,7 M | ~1 GB | NASA POWER | aberta | não (derivado) |
| `geospatial/data/processed/agroclimatic_productivity_panel.csv` | 19.402 | ~30 MB | NASA POWER + PAM/IBGE + ZARC | aberta | não (derivado) |
| `geospatial/data/processed/panel_municipalities.csv` | 1.296 | ~200 KB | IBGE | aberta | sim |
| `geospatial/data/manifests/v30_cad_polygon.json` | 1.296 municípios | ~1 MB | Embrapa Solos (WCS) | **CC BY-NC 3.0 BR** | sim (estatísticas) |

Os rasters CAD **não** são versionados nem redistribuídos (licença). Apenas
estatísticas derivadas por município e profundidade.

## Dados derivados da V3.1 usados na V3.2

| arquivo | linhas | colunas | papel |
|---|---:|---:|---|
| `geospatial/data/processed/v31_panel_windows.csv` | 19.402 | 79 | **única fonte de variáveis** da V3.2 (colunas `_corrected`) |

Colunas usadas: `precip_acumulada_mm_corrected`, `temp_media_c_corrected`,
`degree_days_total_corrected`, `extreme_heat_days_corrected`,
`deficiency_cad_0_100`, `yield_kg_ha`, `state`, `harvest_year`, `safra`,
`ibge_code`, `crop`, `zarc_cycle`.

**Nenhuma coluna `_legacy` é lida por qualquer ferramenta da V3.2** (garantido
por teste de regressão).

## Manifests produzidos pela V3.2

| arquivo | conteúdo |
|---|---|
| `v32_coverage_diagnostics.json` | identificabilidade por cultura × UF |
| `v32_slope_tests.json` | testes globais, contrastes, multiplicidade |
| `v32_predictive.json` | M2 / HET-FE / HET-PP em TE + caminho de λ |
| `v32_robustness.json` | leave-one-UF-out e leave-one-year-out |
| `v32_neighbors_paired.json` | M1c pareado + decomposição de fallback |

## Independentes / não confundir

* **UF×ano** (32–48 clusters): unidade de dependência territorial da D104.
* **bloco espacial** (46, raio 250 km): unidade de reamostragem das versões
  anteriores; mantida só como sensibilidade.
* **município** (1.296): segundo eixo do agrupamento duplo.
* **linhas do painel** (19.402): **não** são observações independentes.
