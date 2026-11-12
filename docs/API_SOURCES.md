# SADEN — Fontes de APIs externas

Verificado em **2026-09-08** por teste real de endpoint. Status atualizado em `data_sources` (tabela do banco, endpoint `GET /api/sources`).

## Ativas (integradas)

| Nome | URL base | Documentação | Propósito no SADEN | Autenticação | Limites | Campos consumidos | Status |
|---|---|---|---|---|---|---|---|
| Yahoo Finance (chart) | `https://query1.finance.yahoo.com` | Sem doc oficial pública (endpoint `…/v8/finance/chart/{SYM}?interval=1d&range=1y`) | Futuros: soja `ZS=F`, milho `ZC=F`, café `KC=F`, trigo `ZW=F`, algodão `CT=F` | Sem chave; exige `User-Agent` browser | Não publicado; usamos cache 60min + 1 chamada/dia por commodity | `timestamp[]`, `indicators.quote[0].close[]`, `meta` | active |
| BCB PTAX (OData) | `https://olinda.bcb.gov.br` | https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/documentacao | Dólar PTAX venda p/ conversão BRL | Sem chave | Não publicado | `cotacaoVenda`, `dataHoraCotacao` (`CotacaoDolarDia`, `CotacaoDolarPeriodo`) | active |
| Open-Meteo Forecast | `https://api.open-meteo.com` | https://open-meteo.com/en/docs | Previsão 7 dias + atual | Sem chave | ~10 mil req/dia (não-comercial) | `current.*`, `daily.(t_max,t_min,t_mean,precipitation,humidity,wind,weather_code)` | active |
| Open-Meteo Archive | `https://archive-api.open-meteo.com` | https://open-meteo.com/en/docs/historical-weather-api | Histórico climático (ERA5) | Sem chave | idem | mesmos `daily.*` por `start_date/end_date` | active |
| Open-Meteo Geocoding | `https://geocoding-api.open-meteo.com` | https://open-meteo.com/en/docs/geocoding-api | Busca de lugares/cidades | Sem chave | idem | `name,latitude,longitude,admin1,admin2,country` | active |
| Nominatim (OSM) | `https://nominatim.openstreetmap.org` | https://nominatim.org/release-docs/develop/api/Overview/ | Ruas/endereços + reverse | Sem chave; 1 req/s, UA identificável, atribuição OSM | Política de uso OSM | `display_name,address.*,lat,lon` | active |
| Sentinel-2 Land Cover (Esri/Impact Observatory) | `https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer` | (o próprio endpoint REST serve `?f=html`) | Camada de cobertura do solo 10m (tiles) + legenda + catálogo | Sem chave p/ tiles/legenda/catálogo | Esri MLA; obra CC BY 4.0 c/ atribuição | tiles PNG, 9 classes, anos 2017–2025 | active |
| Nominatim (OSM) | `https://nominatim.openstreetmap.org` | https://nominatim.org/release-docs/develop/api/Overview/ | Ruas/endereços + reverse | Sem chave; 1 req/s, UA identificável, atribuição OSM | Política de uso OSM | `display_name,address.*,lat,lon` | active |
| IBGE Localidades | `https://servicodados.ibge.gov.br` | https://servicodados.ibge.gov.br/api/docs/localidades | Estados, municípios, código IBGE | Sem chave | Não publicado | `id,nome,sigla,microrregiao.mesorregiao.UF` | active |
| IBGE SIDRA — PAM (tabela 5457) | `https://apisidra.ibge.gov.br` | https://apisidra.ibge.gov.br/definicoes | Produção Agrícola Municipal (município): área plantada/colhida, quantidade produzida, rendimento médio, valor da produção | Sem chave; sem custo | Não publicado; uso público com atribuição | `V`, `D1C/D1N` (município), `D2C/D2N` (variável), `D3C` (ano), `D4C/D4N` (produto, classificação 782) | active (V2.2, branch `v2/agricultural-productivity-data`) |
| IBGE Agregados — metadados | `https://servicodados.ibge.gov.br/api/v3/agregados` | https://servicodados.ibge.gov.br/api/docs/agregados | Metadados oficiais do agregado (variáveis, classificações, periodicidade, níveis) | Sem chave | Não publicado | `variaveis[]`, `classificacoes[]`, `periodicidade`, `nivelTerritorial` | active (V2.2) |
| CONAB — Boletim de Safras (planilhas) | `https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras` | idem (páginas de levantamento) | Estimativas de safra por UF: área, produtividade, produção | Sem chave; download HTTP de `.xlsx`/`.xls` | Sem API pública; sem limite publicado | planilha por levantamento (aba por UF) | active (V2.2, **contextual/estadual**) |
| MAPA — ZARC tábua de risco (dados abertos) | `https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-dc8ff323b96f` | idem (página do conjunto + dicionário de dados em PDF) | Janelas oficiais de plantio por município, cultura, ciclo, solo e risco (2016/17–2026/27) | Sem chave | Sem limite publicado; ~180 MB por safra | `Nome_cultura, SafraIni, SafraFin, Cod_Ciclo, Cod_Solo, geocodigo, UF, municipio, Portaria, dec1..dec36` | active (V2.4) |
| CONAB — SUTIN (GeoServer/WFS público) | `https://conab-map.conab.gov.br/geoserver/wfs` | `https://conab-map.conab.gov.br/sutin-map-web/index.jsp` | Polígonos de ocorrência de cultura por município (área por feição) | Sem chave | Sem limite publicado | `ID, SIGLA_UF, CD_MUN, NM_MUN, AREA_HA, bbox` + geometria | active (V2.4, **sem produtividade**) |
| ESA WorldCover 10 m | `https://esa-worldcover.s3.eu-central-1.amazonaws.com/` | `https://esa-worldcover.org/` | Classe de cobertura do solo (40 = Cropland), 2020 e 2021 | Sem chave | Sem limite publicado | raster uint8, classes 10..100 | active (V2.3/V2.4) |

## Bloqueadas (sem API pública — NÃO integradas, NÃO inventadas)

| Nome | Consulta manual | Motivo |
|---|---|---|
| CEPEA/ESALQ | https://cepea.org.br/br/consultas-ao-banco-de-dados-do-site.aspx | Sem API pública documentada; consulta via formulário web (gera Excel) sob Cloudflare (sem resposta automatizável — reverificado 2026-09-15). |
| CONAB Preços Agropecuários | https://consultaprecosdemercado.conab.gov.br/ | Portal Angular com reCAPTCHA (verificado 2026-09-15) — contornar é proibido; PGPAF responde 403 via WAF. Sem API REST pública. Não integrado. |
| ANTT Frete (piso mínimo) | https://calculadorafrete.antt.gov.br/ (calculadora interativa) | Portal de dados abertos CKAN verificado: só datasets de multas, sem tabela de coeficientes. Coeficientes em portarias DOU + calculadora sem endpoint. Sem cálculo automático no SADEN; referência manual. |
| IMEA (MT) | site com axios interno, sem API pública documentada | Avaliado 2026-09-15; sem interface oficial estruturada. Não integrado. |
| CONAB — dados por município (SIGS) | `https://sigs.conab.gov.br/producao/` | Verificado em 2026-11-11: o host **não resolve DNS** neste ambiente (`socket.gethostbyname` → `gaierror`). Seria a via granular para produtividade municipal; não contornado. Registrado como bloqueio real. |
| CONAB — catálogo dados.gov.br (CKAN) | `https://dados.gov.br/api/3/action/package_search` | Verificado em 2026-11-11: responde **HTTP 401** (exige autenticação); sem credencial disponível. O portal de boletins continua acessível. |
| CONAB — API própria | `https://api.conab.gov.br` | Verificado em 2026-11-11: **não resolve DNS**. |
| CONAB — SIGS (dados por município) | `https://sigs.conab.gov.br/producao/` | Verificado em 2026-11-11: **não resolve DNS** neste ambiente. A via **pública e acessível** da CONAB é o GeoServer do SUTIN (`conab-map.conab.gov.br/geoserver/wfs`), que entrega **área** por feição de cultura, **sem produtividade** (V2.4, D56). |
| MAPA — SISZARC (aplicação) | `https://siszarc.agricultura.gov.br/` | Verificado em 2026-11-11: **não resolve DNS**; não contornado. A via alternativa **acessível** é o portal de dados abertos do MAPA (`dados.agricultura.gov.br`), usado na V2.4 (D54). |
| IMEA (MT) | `https://imea.com.br/` | Host resolve e responde, mas as páginas internas retornam **HTTP 500** — conteúdo não recuperável por HTTP nesta origem (V2.4). |
| MapBiomas — Cobertura 10 m (GCS / GEE) | `https://storage.googleapis.com/mapbiomas-public/...brazil_coverage-col4_10m_YYYY.tif` · `projects/mapbiomas-public/assets/brazil/lulc_10m/collection4/mapbiomas_10m_collection4_coverage_v1` | Verificado em 2026-11-12: rota GCS retorna **HTTP 403** (2017–2025) e o asset GEE exige conta não configurada. Bloqueio de acesso registrado (V2.4). |

> **Pendência de licenciamento (aberta).** O catálogo STAC da Earth Search
> declara `license: proprietary` para a coleção `sentinel-2-c1-l2a`, enquanto o
> Registry of Open Data on AWS declara acesso “free, full and open”. A questão
> **não está resolvida**: nenhum termo de uso foi obtido em forma verificável.
> Da mesma forma, os termos de uso da CONAB não foram lidos: as planilhas são
> obtidas por acesso público, mas ficam **fora do Git** (decisão D48), com URL
> e SHA-256 registrados no manifesto.

## V2.5 — fontes efetivamente usadas (2026-11-12)

| Fonte | Endpoint / recurso | Uso na V2.5 | Verificação |
|---|---|---|---|
| ESA WorldCover 10 m | `https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2020/map/ESA_WorldCover_10m_2020_v200_N36W056_Map.tif` (e equivalente 2021/v100) | máscara agrícola (classe 40) em 4 variantes: `wc2020`, `wc2021`, `stable` (interseção) e `broad` (união) | leitura remota por janela, com repetição quando o servidor devolve janela parcial; `transform` da janela corrigido (D59) |
| MAPA — ZARC, tábua de risco | `https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-dc8ff323b96f/resource/0bb6188d-8b6a-4ab6-9d77-2e88dc889313/download/dados-abertos-tabua-de-risco-safra-2016-2017.csv` (11 safras) | janelas de plantio por cultura × safra × solo × ciclo × nível de risco; portaria de origem | reuso da base normalizada da V2.4 (`zarc_planting_windows.csv`); **âncora de ano e risco textual corrigidos** na camada de janelas (D62) |
| Sentinel-2 L2A (COG) | `https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/...` e `sentinel-2-c1-l2a-cogs/...` (Earth Search) | série municipal mensal: 47 meses × 2 tiles (`21LXG` + `21LXF`) | cena principal = `item_id` **exato** da série de referência da V2.3; tile complementar na mesma data e com o mesmo índice de reprocessamento |
| IBGE — PAM (SIDRA 5457) | `https://apisidra.ibge.gov.br/values` | rendimento médio, área colhida, área plantada e quantidade produzida por município e ano | base da V2.2, reusada sem alteração; 4.916 observações, 1.118 do milho (produto **agregado** do ano) |
| CONAB — SUTIN (GeoServer WFS) | `https://conab-map.conab.gov.br/geoserver/wfs` | camada `MT_SOJA_2021` (17 feições em Sorriso) — **não** usada como máscara | verificado: só há **área** (`AREA_HA`), **sem produtividade**;Polígono único de 2021 não generalizável (D56, D49) |
| MapBiomas — Cobertura 10 m | GCS / GEE | **não disponível** | HTTP 403 no GCS; asset GEE exige conta institucional (D56). A máscara **anual** de uso do solo permanece a maior limitação da V2.5 |

> **Nenhuma fonte nova foi introduzida na V2.5.** A versão reusa exclusivamente
> as fontes já declaradas e verificadas nas V2.2–V2.4, o que preserva a
> rastreabilidade e o regime de licenciamento (D48).

## V2.6 — fontes meteorológicas efetivamente usadas (2026-11-12)

| Fonte | Endpoint / recurso | Uso na V2.6 | Verificação |
|---|---|---|---|
| **INMET — catálogo de estações** | `https://apitempo.inmet.gov.br/estacoes/T` | inventário de 668 estações automáticas (código WMO, coordenadas, altitude, estado, tipo, situação, datas de operação) | **200**, 668 registros, leitura em 0,6 s |
| **INMET — dados históricos** | `https://portal.inmet.gov.br/uploads/dadoshistoricos/<ano>.zip` (2000–2026) | série **diária** por estação (temperatura, umidade, precipitação, pressão, radiação, vento) | **200**, ~100 MB/ano; extração parcial por **HTTP Range** (808 kB por estação/ano) |
| **NASA POWER** (MERRA-2 + CERES, comunidade AG) | `https://power.larc.nasa.gov/api/temporal/daily/point?parameters=…&community=AG` | base **reanalisada** do painel (precipitação, temperatura, radiação, umidade, vento, pressão, temperatura do solo) | **200**, 3.653 dias por município, 1,6 s por ponto |
| **ERA5-Land** (Copernicus) | via `https://archive-api.open-meteo.com/v1/archive?models=era5_land` (acesso público sem chave) | variáveis térmicas e de solo (complementares) | parcial: **HTTP 429** sob uso intensivo; acesso **nativo** do CDS exige chave de conta não configurada |
| **ERA5** (Copernicus) | via `https://archive-api.open-meteo.com/v1/archive?models=era5` (0,25°) | precipitação, radiação, vento e pressão (ausentes no acesso público do ERA5-Land) | parcial: mesmo **HTTP 429** |
| **CDS da Copernicus** | `https://cds.climate.copernicus.eu/api/catalogue/v1/collections/reanalysis-era5-land-timeseries` | acesso **nativo** ao ERA5-Land | metadados **200**; a execução exige **chave de conta** (não criada, não lida de credenciais pessoais) |
| **ARCO (espelho ERA5)** | `https://data.lhncbc.ucsb.edu/ARCO/…` | espelho Zarr do ERA5-Land | **sem resolução DNS** neste ambiente |
| **CHIRPS** | `https://chc.ucf.edu/`, `https://data.chc.ucf.edu/` | precipitação grillada complementar | **sem resolução DNS** — bloqueio registrado |
| **IBGE — malhas municipais** | `https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_<ano>/UFs/<UF>/<UF>_Municipios_<ano>.zip` | geometria oficial dos municípios (centroide e teste ponto-em-polígono) | **200**; a API `servicodados…/malhas` responde com **timeout** neste ambiente |
| **IBGE — localidades** | `https://servicodados.ibge.gov.br/api/v1/localidades/estados/<UF>/municipios` | lista de municípios por UF | **200**, 0,2 s por UF |
| **MAPA — ZARC** | `https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-dc8ff323b96f` (11 safras) | janela de plantio por município × safra × cultura × solo × ciclo × risco | **200**; tabelas nacionais (~200 MB/safra) lidas em **streaming** e filtradas pelo geocódigo IBGE |
| **IBGE — PAM (SIDRA 5457)** | `https://apisidra.ibge.gov.br/values/t/5457/n6/<códigos>/v/214,216,112,8331/p/2017..2025/c782/40124,40122` | produtividade municipal (rendimento, área colhida, área plantada, quantidade produzida) | **200**; 1.782 municípios em uma requisição por UF |

> **Comparação entre fontes (V2.6, D75).** Em 215 estações com série do INMET
> dentro do município, a reanálise (NASA POWER) apresenta, contra a estação:
> temperatura — viés **+0,37 °C**, MAE 1,42 °C, RMSE 1,79 °C, **r = 0,854**;
> precipitação — viés **−0,38 mm/dia**, MAE 3,26 mm/dia, **r = 0,602**, total
> anual 7.512 contra 8.173 mm (**−8%**). A subestimação da precipitação é um
> viés conhecido do MERRA-2 em regiões tropicais, **não** um erro de
> implementação. Nenhuma correção empírica foi aplicada.

> **Nenhuma fonte foi inventada, autenticada por conta alheia ou contornada.**
> As fontes inacessíveis (CDS sem chave, ARCO, CHIRPS) foram registradas como
> bloqueio, e o trabalho seguiu com as fontes legítimas acessíveis.

## Consequência metodológica

Os preços do SADEN são **referência internacional convertida** (futuro CBOT/ICE × PTAX venda), não o preço físico regional.
Fatores: saca 60kg = 2,20462 bu (grãos); café 60kg = 132,277 lb; algodão direto R$/libra-peso.
Toda tela e todo relatório exibem fonte, data do dado e `retrieved_at`.
