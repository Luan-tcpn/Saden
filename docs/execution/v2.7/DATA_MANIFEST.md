# SADEN V2.7 — Manifesto de dados

> Fontes, registros, períodos, hashes e **ausências** usados na V2.7.
> Artefatos grandes permanecem fora do Git (D74/D84); os manifests são
> versionados.

## 1. Fontes de entrada

| Fonte | Natureza | Uso na V2.7 | Situação |
|---|---|---|---|
| **PAM** (SIDRA 5457) | Observação oficial | Resposta (kg/ha) e área colhida | V2.6, inalterada |
| **ZARC** (portarias do MAPA) | Calendário oficial de plantio | Janela do ZARC (protocolo principal) | V2.6, inalterada |
| **NASA POWER** | Reanálise | Série diária meteorológica (base) | V2.6, inalterada |
| **INMET** | Observação de estação | Validação independente | V2.6, inalterada |
| **Embrapa Solos / GeoInfo** | Raster oficial de solo | CAD territorial (linha experimental) | **Novo na V2.7** |
| **Embrapa (Soja, Milho e Sorgo, doc. 258)** | Publicação agronômica | Parâmetros fenológicos | **Novo na V2.7** |
| **ERA5-Land (CDS)** | Reanálise | — | **Bloqueado** (D83) |
| **CHIRPS / ARCO** | Reanálise/precipitação | — | **Bloqueado** (DNS) |

## 2. Artefatos reproduzidos da V2.6 (fora do Git)

| Arquivo | Tamanho | Observação |
|---|---|---|
| `geospatial/data/processed/agroclimatic_productivity_panel.csv` | 27,3 MB | 40.990 linhas: 19.402 `paired_usable` NASA POWER + 21.422 INMET |
| `geospatial/data/processed/climate_daily.csv` | 1.076,9 MB | base diária por município (reanálise + observação) |
| `geospatial/data/processed/panel_municipalities.csv` | 0,2 MB | 1.782 municípios com centroide, bbox e elevação |
| `geospatial/data/processed/panel_station_selection.csv` | 0,24 MB | 215 estações INMET utilizadas |
| `geospatial/data/processed/pam_panel.csv` | 428,1 MB | painel PAM bruto |
| `geospatial/data/processed/zarc_panel.csv` | 2.019,9 MB | ZARC completo |

> Verificado por `git check-ignore`: os arquivos de `data/processed/` estão
> fora do Git (regra do `geospatial/.gitignore`).

## 3. Manifests da V2.7 (versionados)

| Manifest | Tamanho | Conteúdo |
|---|---|---|
| `v27_robust_inference.json` / `.csv` | ~60 KB / 31 KB | inferência por esquema, Conley, bootstrap wild e Holm |
| `v27_cluster_diagnostics.json` | 10,1 KB | 1.225 municípios, 383 células, 46 blocos de 250 km, 5 UFs; identidade de valores |
| `v27_stats_validation.json` | 1,9 KB | 16/16 verificações das implementações estatísticas |
| `v27_wild_bootstrap_calibration.json` | 252 KB | calibração Monte Carlo do bootstrap wild (2 DGP, 84 casos, 999 réplicas) — **grade recalculada após D85** |
| `v27_spatial_dependence.json` / `.csv` | 30 KB / 11 KB | correlograma de anomalias (1.296 municípios, 3.653 dias), quatro campos, bandas de 25 km até 600 km |
| `v27_spatial_validation.json` / `.csv` | 84 KB / 5,8 KB | protocolos P1–P5 de validação territorial (P5 = bloco × ano, D86) |
| `v27_cad_wcs_probe.json` | 37 KB | capabilities do WCS (506 camadas) e descrição das camadas AW |
| `v27_cad_layer_metadata.json` | 3,4 KB | título, unidade, profundidade, escala, CRS e licença por camada |
| `v27_cad_sample.json` / `.csv` | 37 KB / 2,7 KB | amostra geográfica controlada: CAD por município |
| `v27_phenology_window.json` | 17 KB | manifesto do experimento fenológico |
| `v27_phenology_window.csv` | 601 KB | indicadores recalculados por linha (janela fenológica × ZARC) |
| `v27_panel_coverage.json` / `.csv` | 1,7 KB / 546 KB | diagnóstico de cobertura nacional do painel (decisão de expansão) |

> Todos os manifests são regeneráveis por comando
> (`run_robustness.py {dependence,diagnose,infer,spatial}` e
> `tools/{calibrate_wild_bootstrap,validate_v27_stats,s27_*}.py`), com
> semente fixa. Os artefatos grandes que os originam ficam fora do Git
> (D74/D84).

## 4. Períodos

| Elemento | Período |
|---|---|
| Painel agroclimático | safras 2016/17 a 2024/25 (8 anos de colheita por cultura) |
| Base diária NASA POWER | 2016-01-01 em diante |
| Correlograma de dependência | anomalias anuais de 8 anos, 1.296 municípios, 3.653 dias |
| Correlograma diário | bandas de distância 0–25 a 400–425 km |
| Calibração Monte Carlo | simulação; sem período empírico |

## 5. Referências METEOROLÓGICAS e METADADOS online

| Item | Valor |
|---|---|
| WCS | `https://geoinfo.dados.embrapa.br/geoserver/ows` (WCS 2.0.1) |
| Camadas AW | `geonode__aw_{0_5,5_15,15_30,30_60,60_100,100_200}_def` |
| Título oficial | "Mapa de água disponível do solo (mm/cm) a 0-5 cm do Brasil na resolução espacial de 90 m - Versão 2021 [CNPS]" |
| Unidade | **mm/cm** (mm de água por cm de solo) |
| Resolução | ~90 m (0,000833° no serviço, EPSG:4326) |
| No-data | −9999 (declarado pelo serviço) |
| Extensão | −78,71 a −30,96 lon; −34,01 a 6,05 lat |
| Licença | **CC BY-NC 3.0 BR (uso não-comercial)** |
| Citação | Vasques, G.M., Dart, R.O., Cintra, L.C., Baca, J.F.M. (2021). *Soil Available Water Maps for Brazil at 0-5, 5-15, 15-30, 30-60, 60-100 and 100-200 cm Depth Intervals with 90 m Spatial Resolution*. Version 2021. Embrapa Solos, Rio de Janeiro, Brazil. |

> Observação de metadado: o `DescribeCoverage` declara a unidade do campo
> como `GRAY_INDEX`/`W.m-2.Sr-1` (modelo genérico do GeoServer). **A
> unidade autoritativa é a do título e da citação oficial** (mm/cm). Isso é
> registrado aqui porque afetaria qualquer conversão automática.

## 6. Referências agronômicas (fenologia)

| Cultura | Parâmetro | Valor | Fonte |
|---|---|---|---|
| Soja | R1 | 92,5 °C·dia | Schneider et al. (1987); Martorano et al. (2012), via Embrapa Soja |
| Soja | R5 (início do enchimento) | 554 °C·dia | Martorano et al. (2012), via Embrapa Soja |
| Soja | escala de estádios | Fehr & Caviness (1977) | Embrapa Soja |
| Milho | emergência → polinização | 780–830 / 831–890 / 890–1.200 °C·dia | Embrapa Milho e Sorgo |
| Milho | R3 / R5 / R6 após polinização | ≈20–25 / ≈36 / ≈50–60 dias | Embrapa Milho e Sorgo |
| Milho 2ª safra | ciclo total | 120–150 dias; 2.200–3.300 °C·dia | Embrapa, documento 258 |
| Soja | graus-dia (painel) | Tb = 10 °C, Ts = 30 °C | Gilmore & Rogers (1958) |

## 7. Ausências (preservadas, nunca preenchidas)

| Item | Situação |
|---|---|
| Credencial do CDS (ERA5-Land) | ausente — sem tentativa de autenticação |
| Resolução DNS de CHIRPS e ARCO | ausente — não repetido |
| Identificação de cultivar na PAM | ausente — perfis fenológicos são cenários |
| AW municipal (valor pontual por município) | inexistente — o dado é raster; usa-se a mediana de janela |
| AW fora dos pixels válidos (solos rasos, afloramentos, dunas, áreas urbanas, corpos d'água) | não excluídos pelo produtor (declarado no abstract oficial) — a ausência é mantida |
| Convenção de troca de nulidade do CGM | não verificável neste ambiente — ambas as variantes são reportadas (D81) |
