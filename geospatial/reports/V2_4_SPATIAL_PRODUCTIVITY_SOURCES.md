# SADEN V2.4 — Inventário de fontes de produtividade agrícola espacialmente mais fina

> Branch: `v2/agricultural-scale-harmonization`. Execução: 2026-11-12.
> Manifesto: `geospatial/data/manifests/conab_sutin_report.json`,
> `geospatial/data/manifests/mapbiomas_access_report.json`.

## 1. Pergunta

Existe alguma fonte **real, legítima e reproduzível** que forneça
produtividade de soja ou milho em Sorriso-MT **abaixo da escala municipal**?

## 2. Fontes investigadas (com evidência de acesso)

| Fonte | Endereço | Resultado do acesso (2026-11-12) |
|---|---|---|
| IBGE/SIDRA — PAM 5457 | `https://apisidra.ibge.gov.br/values/...` | **acessível**, mas **municipal** (N6) |
| MAPA — ZARC tábua de risco | `https://dados.agricultura.gov.br/dataset/6d3d141c-...` | **acessível** (11 safras), mas são **janelas de plantio**, não produtividade |
| MAPA — painel público do ZARC | `https://mapa-indicadores.agricultura.gov.br/publico/extensions/Zarc/Zarc.html` | acessível (200) |
| MAPA — SISZARC | `https://siszarc.agricultura.gov.br/` | **DNS não resolve** (`gaierror`) |
| CONAB — SUTIN (GeoServer) | `https://conab-map.conab.gov.br/geoserver/wfs` | **acessível**: 1.618 camadas, 17 de MT |
| CONAB — SIGS | `https://sigs.conab.gov.br/producao/` | **DNS não resolve** |
| CONAB — API | `https://api.conab.gov.br` | **DNS não resolve** |
| MapBiomas — Cobertura 10 m Col. 4 (GCS) | `https://storage.googleapis.com/mapbiomas-public/...brazil_coverage-col4_10m_YYYY.tif` | **HTTP 403 Forbidden** em 2017, 2019, 2021, 2023, 2025 |
| MapBiomas — asset GEE | `projects/mapbiomas-public/assets/brazil/lulc_10m/collection4/mapbiomas_10m_collection4_coverage_v1` | exige conta GEE (**não configurada**; não foi criada nem solicitada) |
| MapBiomas — página de downloads | `https://brasil.mapbiomas.org/downloads/` | informa *"a função de baixar mapas está temporariamente suspensa"* |
| ESA WorldCover 10 m | `https://esa-worldcover.s3.eu-central-1.amazonaws.com/` | **acessível** (2020, 2021) — classe 40 = Cropland |
| IMEA (MT) | `https://imea.com.br/` | host resolve; páginas internas retornam **HTTP 500** (conteúdo não recuperável por HTTP) |
| Embrapa Alice | `https://www.alice.cnptia.embrapa.br/handle/doc/1146640` | **acessível** — estudo **simulado** de soja/milho 2ª safra em MT |
| UFMT geoserver | `https://geoserver.ufmt.br/geoserver/` | sem resposta (DNS/TCP) |
| INPE/CAR | `https://car.gov.br/` | sem resposta (DNS/TCP) |
| dados.gov.br (CKAN) | `https://dados.gov.br/api/3/action/...` | HTTP 401 (exige autenticação) |

## 3. Matriz de disponibilidade

| Fonte | Cultura | Variável | Granularidade | Período | Natureza | Acesso | Qualidade |
|---|---|---|---|---|---|---|---|
| IBGE/PAM 5457 | soja, milho, +84 | rendimento médio, área, quantidade | **município** | 1974–2025 | **observada** | sem chave | alta (oficial, revisável) |
| MAPA/ZARC | 23 culturas em MT | janela de plantio por risco | município × solo × ciclo | 2016/17–2026/27 | **recomendação oficial** | sem chave | alta (normativa) |
| CONAB SUTIN | soja (MT 2021), cana, cobertura vegetal | **área** por feição (ha) | **submunicipal** (polígonos ~10 m) | safras various (2012–2021) | **estimada** (monitoramento por satélite) | GeoServer público | média: não cobre todas as culturas/safras |
| CONAB — Boletim de Safras | grãos, café | área, produtividade, produção | **UF** | safras 23/24–25/26 | estimada | planilhas | contextual (D46) |
| ESA WorldCover | todas | classe de cobertura (40 = Cropland) | 10 m | 2020, 2021 | **estimada** (classificação) | COG público | média-alta |
| MapBiomas Col. 4 | todas | classe de uso do solo (nível 3) | 10 m | 2017–2025 | estimada | **bloqueado** | — |
| IMEA | soja, milho, etc. | produtividade, área, custo | município/região | histórico | observada/estimada | **não recuperável** (HTTP 500) | — |
| Embrapa Alice | soja/milho 2ª | rentabilidade por época de semeadura | sistemas de produção | 2007–2020 | **simulada** | acessível | técnica, não observação |
| INCRA/SIGEF/CAR | — | geometria de propriedade | fazenda/talhão | — | cadastral | **bloqueado** (sem DNS) | geometria **não** é produção |

## 4. O que a CONAB SUTIN realmente oferece

**FATO.** O GeoServer público da CONAB expõe camadas
`wp_geote:<UF>_<CULTURA>_<SAFRA>` (17 de Mato Grosso), em EPSG:4326, com
atributos `ID`, `SIGLA_UF`, `CD_MUN` (código IBGE), `NM_MUN`, `AREA_HA` e
`bbox`. Exemplo verificado: `MT_SOJA_2021` tem **24.634 feições** no estado e
**24 feições** no recorte da bacia de Sorriso, das quais **17** têm
`CD_MUN = 5107925`.

**FATO.** **Não existe campo de produtividade (kg/ha) nas camadas.** O que há é
**área da feição**. Portanto a SUTIN é uma referência **submunicipal de área
de cultura**, não de produtividade.

**LIMITAÇÃO.** A cobertura é irregular: em MT só há soja (2021), cana e
cobertura vegetal — **não** há camada de milho nem séries anuais completas.

## 5. Conclusão da investigação

**Não existe, nas fontes oficiais acessíveis, uma referência de
produtividade (kg/ha) de soja ou milho em Sorriso abaixo da escala
municipal.**

O que existe em escala mais fina:

1. **CONAB SUTIN** — polígonos de ocorrência de cultura por município
   (soja/MT 2021, 17 feições em Sorriso) com **área**, que permitem identificar
   *onde* a cultura está, **não quanto*rende**;
2. **MapBiomas** — mapa de uso do solo 10 m 2017–2025, **bloqueado** por
   acesso (GCS 403; GEE exige conta institucional);
3. **WorldCover** — cropland 10 m em 2020 e 2021, **adquirido**;
4. **ZARC** — janelas oficiais de plantio por município/solo/ciclo
   (adquirido), que é informação **agronômica**, não de produtividade;
5. **geometrias cadastrais** (INCRA/SIGEF/CAR) — inacessíveis neste ambiente e,
   em qualquer caso, geometria não é observação de produção.

**Consequência metodológica (D56):** a incompatibilidade de escala da V2.3
**não é resolvida por uma fonte de produtividade mais fina**, porque ela não
existe publicamente em nível municipal ou inferior. Ela é resolvida — quando
resolvível — **mudando a escala do indicador geoespacial** para a do alvo
(agregação municipal), e não reduzindo o alvo.

## 6. O que depende de acesso institucional

| Necessidade | Fonte provável | Natureza do acesso |
|---|---|---|
| Mapa de uso do solo 2017–2025 (10 m) | MapBiomas Collection 4 | conta Google Earth Engine (institucional) ou permissão no bucket |
| Produtos de frequência de cultivo (Col. 11) | MapBiomas | mesma rota GEE |
| Produtividade municipal de Sorriso por safra | IMEA | portal com erros HTTP 500 nesta origem; pode funcionar em navegação manual |
| Dados por propriedade/talhão | SIGEF/INCRA | acesso institucional restrito |
| Dados de Constable/CoCoTi | MorphoSpatial (Embrapa) | a investigar em etapa própria |
