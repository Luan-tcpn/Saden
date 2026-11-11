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

> **Pendência de licenciamento (aberta).** O catálogo STAC da Earth Search
> declara `license: proprietary` para a coleção `sentinel-2-c1-l2a`, enquanto o
> Registry of Open Data on AWS declara acesso “free, full and open”. A questão
> **não está resolvida**: nenhum termo de uso foi obtido em forma verificável.
> Da mesma forma, os termos de uso da CONAB não foram lidos: as planilhas são
> obtidas por acesso público, mas ficam **fora do Git** (decisão D48), com URL
> e SHA-256 registrados no manifesto.

## Consequência metodológica

Os preços do SADEN são **referência internacional convertida** (futuro CBOT/ICE × PTAX venda), não o preço físico regional.
Fatores: saca 60kg = 2,20462 bu (grãos); café 60kg = 132,277 lb; algodão direto R$/libra-peso.
Toda tela e todo relatório exibem fonte, data do dado e `retrieved_at`.
