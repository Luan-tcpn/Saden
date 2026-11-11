# SADEN V2.2 — Base observada de produtividade agrícola e compatibilidade com o Sentinel-2

> Branch: `v2/agricultural-productivity-data` (derivada de
> `v2/geospatial-validation` / `e1d7f30`). V1 congelada e intocada.
> Execuções de referência: 2026-11-11.
> Código: `geospatial/agri/`; CLI: `geospatial/run_productivity.py`;
> dados: `geospatial/data/` (raw/processed/manifests).

Este relatório é revisável **sem abrir o código**. Cada seção separa
**FATO** (observado ou calculado), **INTERPRETAÇÃO** (leitura possível) e
**LIMITAÇÃO** (o que o dado não permite concluir).

Índice:

1. [Objetivo](#1-objetivo)
2. [Fontes investigadas](#2-fontes-investigadas)
3. [Metodologia](#3-metodologia)
4. [Culturas avaliadas](#4-culturas-avaliadas)
5. [Dados adquiridos](#5-dados-adquiridos)
6. [Escalas geográficas](#6-escalas-geográficas)
7. [Compatibilidade temporal](#7-compatibilidade-temporal)
8. [Compatibilidade com o Sentinel-2](#8-compatibilidade-com-o-sentinel-2)
9. [Base observada normalizada](#9-base-observada-normalizada)
10. [Crosswalk de culturas](#10-crosswalk-de-culturas)
11. [Relatório de qualidade](#11-relatório-de-qualidade)
12. [Compatibilidade por combinação](#12-compatibilidade-por-combinação)
13. [Resultados científicos](#13-resultados-científicos)
14. [Implementação](#14-implementação)
15. [Testes](#15-testes)
16. [Limitações](#16-limitações)
17. [Decisões](#17-decisões)
18. [Portão de decisão para a V2.3](#18-portão-de-decisão-para-a-v23)
19. [Como reproduzir](#19-como-reproduzir)

---

## 1. Objetivo

**FATO.** A V2.2 investigou, adquiriu, normalizou e validou dados oficiais de
produção agrícola (IBGE/SIDRA e CONAB) e avaliou sua compatibilidade espacial,
temporal e semântica com os indicadores Sentinel-2 da V2.1 (AOI de validação de
43,26 km² em Sorriso-MT; série mensal de NDVI 2023–2025).

**FATO.** Nada foi integrado ao produto: não há alteração em `backend/`,
`frontend/`, schema SQLite, Ridge ou interface; não há modelo de produtividade
treinado; não há API nova.

**LIMITAÇÃO.** Esta etapa **não** estabelece que NDVI e produtividade sejam
relacionados. Ela estabelece **o que existe, em que escala e com que
qualidade** — e se existe base suficiente para a V2.3.

## 2. Fontes investigadas

### 2.1 IBGE/SIDRA — Produção Agrícola Municipal (PAM)

| Item | Valor verificado (2026-11-11) |
|---|---|
| Conjunto | PAM, tabela **5457** — “Área plantada ou destinada à colheita, área colhida, quantidade produzida, rendimento médio e valor da produção das lavouras temporárias e permanentes” |
| Documentação | `https://sidra.ibge.gov.br/tabela/5457` |
| API | `https://apisidra.ibge.gov.br/values/...` (documentação: `https://apisidra.ibge.gov.br/definicoes`) |
| Acesso | HTTP GET público, **sem chave e sem custo** |
| Periodicidade | anual, **1974–2025** |
| Níveis | N1 (Brasil), N2 (UF), N3, N6 (**município**), N8, N9 |
| Classificação | 782 — “Produto das lavouras temporárias e permanentes” (≈86 produtos) |
| Variáveis usadas | 8331 (área plantada, ha) · 216 (área colhida, ha) · 214 (quantidade produzida, t) · 112 (rendimento médio, kg/ha) |
| Licença | dados estatísticos oficiais de acesso público, uso livre com atribuição |

**FATO.** Município `5107925` confirmado pela API oficial de localidades:
nome **Sorriso**, UF **Mato Grosso (MT)**, região imediata *Sorriso*,
região intermediária *Sinop*, mesorregião *Norte Mato-grossense*, região
*Centro-Oeste*.

### 2.2 CONAB — Boletim de Safras

| Item | Valor verificado (2026-11-11) |
|---|---|
| Conjunto | Boletim de Safras (grãos) e Boletim da Safra de Café — planilhas oficiais `.xlsx`/`.xls` por levantamento |
| Documentação | `https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras` |
| Acesso | download HTTP direto do portal (sem chave, sem custo); **sem API pública automatizável** |
| Granularidade das planilhas | **UF (estadual) e nacional** — não há dado municipal nesses arquivos |
| Variáveis | área (mil ha), produtividade (kg/ha), produção (mil t); comparação safra corrente × anterior |
| Natureza | **estimativas de levantamento**, provisórias e revisadas a cada boletím |
| Período no portal | safras 2024/25, 2025/26 e 2026/27 (sondas para safras mais antigas retornaram 404) |

**FATO — bloqueios de acesso verificados (nenhum contornado):**

| Endpoint | Resultado | Evidência |
|---|---|---|
| `sigs.conab.gov.br/producao` (dados por município) | **DNS não resolve** | `socket.gethostbyname` → `gaierror` |
| `api.conab.gov.br` | **DNS não resolve** | `socket.gethostbyname` → `gaierror` |
| `dados.gov.br/api/3/action/package_search` (CKAN) | **HTTP 401** | exige autenticação; sem chave disponível |
| Portal de boletins (`www.gov.br/conab`) | acessível | planilhas baixadas e lidas |

**FATO.** Nenhum CAPTCHA, autenticação ou restrição contratual foi contornado.

## 3. Metodologia

1. **Inventário** (`inventory`): metadados oficiais do agregado 5457, listagem
   das planilhas da CONAB, confirmação do município e crosswalk de culturas.
2. **Aquisição** (`acquire`): consulta SIDRA para o município (2013–2025, todas
   as variáveis e todos os produtos) e download das planilhas CONAB (último
   levantamento de cada safra 2024/25 e 2025/26). Resposta bruta da API
   gravada em `data/raw/sidra/`; planilhas em `data/raw/conab/` (não versionadas).
3. **Normalização** (`normalize`): uma tabela única com **valor e unidade
   originais preservados** ao lado dos normalizados, mais identificadores de
   origem, geografia, período, natureza da informação e escopo do produto.
4. **Validação** (`validate`): 11 verificações automatizadas sobre a base.
5. **Compatibilidade** (`compat`): classificação espacial A/B/C com geometria
   real, agregação anual da série Sentinel-2 (sem interpolação) e tabela de
   correspondência cultura × período × fonte × indicador.

## 4. Culturas avaliadas

O catálogo de commodities do próprio SADEN (`backend/src/db.js`) tem cinco
commodities: soja, milho, café arábica, trigo e algodão.

| Commodity SADEN | Cód. IBGE (PAM) | Nome IBGE | Correspondência | Situação na V2.2 |
|---|---|---|---|---|
| Soja | 40124 | Soja (em grão) | **exata** | **piloto** — 2,24–2,34 Mt/ano em Sorriso |
| Milho | 40122 | Milho (em grão) | **exata** | **piloto** — 3,66–3,82 Mt/ano em Sorriso |
| Algodão | 40099 | Algodão herbáceo (em caroço) | **parcial** | piloto condicionado — SADEN referencia o *pluma* (ICE CT=F, R$/lp); a PAM publica o *caroço* |
| Café arábica | 40140 | Café (em grão) Arábica | equivalente com ressalvas | **descartado** — produção municipal **zero** em 2013–2025 |
| Trigo | 40127 | Trigo (em grão) | exata | **descartado** — produção municipal **zero** em 2013–2025 |

**FATO.** Café e trigo foram descartados porque a PAM reporta quantidade
produzida = 0 (código “-”, valor nulo) para Sorriso em todos os anos da série
adquirida: não há observação municipal que sustente qualquer análise.

**INTERPRETAÇÃO.** Soja e milho são as únicas commodities do SADEN com
produção municipal observada **e** correspondência exata de definição — são as
candidatas naturais a qualquer estudo futuro em escala municipal.

**LIMITAÇÃO.** Correspondência “parcial” de algodão significa que **não** se
pode converter rendimento de caroço em rendimento de pluma sem um fator
documentado (não convertido nesta etapa).

## 5. Dados adquiridos

| Fonte | Registros | Período | Granularidade | Arquivos |
|---|---|---|---|---|
| IBGE/SIDRA (PAM 5457) | **4.472** | 2013–2025 (13 anos) | município 5107925 | `data/raw/sidra/pam_5457_5107925_2013-2025.json` (3,7 MB) |
| CONAB (Boletim de Safras) | **444** | safras 23/24, 24/25, 25/26 | UF (MT) + Brasil | `data/raw/conab/*.xlsx` (não versionados; URL + SHA-256 no manifesto) |
| **Base normalizada** | **4.916** | — | — | `data/processed/productivity_observations.csv` (2,3 MB) |

Variáveis, unidades e natureza por fonte:

| Fonte | Variáveis | Unidades | Natureza |
|---|---|---|---|
| IBGE | área plantada, área colhida, quantidade produzida, rendimento médio | ha, t, kg/ha | **observada** (coleta municipal) |
| CONAB | área, produtividade, produção | mil ha → ha; mil t → t; kg/ha | **estimada** (levantamento, revisada) |

### 5.1 Sorriso (IBGE) — quantidades produzidas

| Produto | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|
| Soja (em grão) | 2.142 kt | 2.283 kt | 2.011 kt | 2.119 kt | **2.244 kt** | **2.085 kt** | **2.343 kt** |
| Milho (em grão) | 3.176 kt | 3.191 kt | 3.082 kt | 3.788 kt | **3.820 kt** | **3.660 kt** | **3.780 kt** |
| Algodão herbáceo (em caroço) | 179 kt | 169 kt | 150 kt | 236 kt | **269 kt** | **325 kt** | **283 kt** |

Áreas colhidas em Sorriso: soja 598.500 ha (2023), 599.000 ha (2024),
550.000 ha (2025); milho 535.000 ha, 500.000 ha, 450.000 ha.

### 5.2 Mato Grosso (CONAB) — safras

| Produto | Safra 23/24 | Safra 24/25 | Safra 25/26 |
|---|---|---|---|
| Soja — área | 12.376.100 ha | 12.738.700 ha | 13.006.200 ha |
| Soja — produção | 40.420.300 t | 51.311.500 t | 51.621.600 t |
| Soja — produtividade | 3.266 kg/ha | 4.028 kg/ha | 3.969 kg/ha |
| Milho (total) — produção | 48.795.300 t | 55.536.200 t | 58.577.100 t |
| Algodão em pluma — produção | 2.651.900 t | 2.852.100 t | 2.802.600 t |

## 6. Escalas geográficas

**FATO (geometria real, não bounding box).** Município pela malha oficial do
IBGE (mesma da V2.1, D42), área em projeção `EPSG:6933`:

| Medida | Valor |
|---|---|
| Área do município (Sorriso) | 9.293,47 km² |
| Área da AOI de validação | 43,26 km² |
| Interseção AOI × município | 43,26 km² (AOI **100%** dentro do município) |
| **AOI como fração do município** | **0,4654%** |
| Tiles Sentinel-2 da AOI | `21LXG` (área da sobreposição com `21LXF`) |

| Fonte | Granularidade | Classe para a AOI | Justificativa |
|---|---|---|---|
| IBGE/SIDRA (PAM) | município | **B — contextual** | contém a AOI, mas a estatística cobre 9.293 km²; a AOI é 0,47% disso |
| CONAB (Boletim) | UF (Mato Grosso) | **C — incompatível** | escala estadual não permite atribuição dentro da AOI |
| (hipotético) propriedade/talhão | propriedade | A — direta | **não existe** nas fontes oficiais investigate |

**INTERPRETAÇÃO.** Nenhuma fonte oficial investigada entrega observação
produtiva na escala da AOI (43 km²) ou do talhão. A melhor granularidade
disponível é a municipal.

**LIMITAÇÃO.** A produtividade de Sorriso **não** é a produtividade da AOI.
Rasterizá-la para a AOI (ou “distribuir” pelo município) seria fabricar
resolução espacial inexistente — está proibido por decisão desta etapa.

## 7. Compatibilidade temporal

**FATO.** Três eixos de tempo coexistem e **não são equivalentes**:

| Fonte | Referência temporal | Natureza |
|---|---|---|
| IBGE/PAM | ano civil (ano de referência da produção) | observada |
| CONAB | **safra** (ex.: 23/24), atravessando dois anos civis | estimada e revisada |
| Sentinel-2 (V2.1) | **mensal**, com lacunas reais | observada (radiometria medida) |

Sobreposição com a série Sentinel-2 2023–2025:

| Fonte | Períodos na janela | Quantidade |
|---|---|---|
| IBGE/PAM | 2023, 2024, 2025 | **3 observações anuais** por cultura |
| CONAB | safras 23/24, 24/25, 25/26 (anos civis 2023–2026) | 3 safras, 4 anos civis tocados |

**FATO.** A série Sentinel-2 tem 12 meses em 2025 (12/12), 11/12 em 2023
(falta 2023-01) e 11/12 em 2024 (falta 2024-12), com cobertura válida média
de 95,8% a 99,0%.

**LIMITAÇÃO — amostral.** Com **n = 3** observações anuais oficiais na janela
do Sentinel-2, qualquer correlação exploratória seria estatisticamente
indiscutível. A V2.1 já registrou que a série Sentinel-2 cobre apenas
2023–2025; ampliar a série Sentinel-2 para trás (2017+) é **pré-requisito**
para qualquer análise quantitativa (ver §18).

**LIMITAÇÃO — calendário.** Não foi adotado calendário fenológico: janelas
de plantio/colheita por cultura em Sorriso **não** foram confirmadas em fonte
oficial durante esta etapa. A função de agregação por safra existe
(`compat.s2_season_aggregation`) e **não foi executada com janelas
inventadas**.

## 8. Compatibilidade com o Sentinel-2

**FATO.** Agregação anual da série da V2.1 (NDVI, Perfil B, meses observados):

| Ano | NDVI médio ponderado por cobertura | Meses observados | Meses ausentes | Cobertura média |
|---|---|---|---|---|
| 2023 | 0,4982 | 11/12 | 2023-01 | 98,96% |
| 2024 | 0,4922 | 11/12 | 2024-12 | 98,46% |
| 2025 | 0,5579 | 12/12 | — | 95,79% |

**FATO.** Cruzamento direto (Sorriso × ano):

| Ano | NDVI da AOI | Soja (Sorriso) | Milho (Sorriso) | Algodão caroço (Sorriso) |
|---|---|---|---|---|
| 2023 | 0,4982 | 2.244 kt / 598.500 ha / 3.750 kg/ha | 3.820 kt / 535.000 ha / 7.140 kg/ha | 269 kt / 60.413 ha / 4.455 kg/ha |
| 2024 | 0,4922 | 2.085 kt / 599.000 ha / 3.480 kg/ha | 3.660 kt / 500.000 ha / 7.320 kg/ha | 325 kt / 73.460 ha / 4.425 kg/ha |
| 2025 | 0,5579 | 2.343 kt / 550.000 ha / 4.260 kg/ha | 3.780 kt / 450.000 ha / 8.400 kg/ha | 283 kt / 59.000 ha / 4.800 kg/ha |

**INTERPRETAÇÃO.** As três observações oficiais são consistentes com a
dinâmica de NDVI da AOI (soja: −7,1% em 2024 com +0,1% de área, +27,5% em
2025 com −8,2% de área e +22,5% de rendimento; milho: +5,2% de rendimento em
2025 com −10% de área). Isso é **consistência descritiva**, não evidência de
relação funcional: n = 3, sem ground truth e sem controle de outras lavouras,
solo, irrigação e manejo.

**LIMITAÇÃO.** O NDVI da AOI é um indicador **espectral e geográfico** de
uma janela de 43 km²; o rendimento municipal é uma **estatística
agropecuária** de 9.293 km², que inclui Lavoura, pastagem, solo exposto e
áreas não agrícolas. A classe SCL 5 (“bare soils”) provavelmente inclui áreas
cultivadas — o SCL **não** é identificador de lavoura.

## 9. Base observada normalizada

**FATO.** `geospatial/data/processed/productivity_observations.csv`
(4.916 registros) com 26 campos, incluindo: instituição, nome e id do
conjunto, URL de origem, método e data de aquisição, código/nome/tipo da
unidade geográfica, ano de referência, safra, código e nome original da
cultura, nome normalizado, escopo do produto, classe de correspondência,
variável original e normalizada, valor original e normalizado, unidade original
e normalizada, natureza da informação, situação da observação, data de
publicação, revisão e observações.

| Recorte | Registros |
|---|---|
| IBGE (município, observados) | 4.472 |
| CONAB (UF, estimados) | 444 |
| Correspondência exata | 228 |
| Equivalente com ressalvas | 52 |
| Parcial | 76 |
| Sem correspondência (fora do catálogo do SADEN) | 4.560 |

**FATO.** Nenhum valor original foi sobrescrito: conversões aplicadas são
apenas `mil ha → ha` (×1.000), `mil t → t` (×1.000) e `kg/ha` (inalterado),
documentadas em `normalize.CONAB_UNIT_FACTORS`.

## 10. Crosswalk de culturas

**FATO.** `agri/crosswalk.py` declara cada vínculo, com classe e ressalva:

| SADEN | IBGE (código, nome) | classe | CONAB (rótulo) | classe | ressalva principal |
|---|---|---|---|---|---|
| soja | 40124 Soja (em grão) | exata | `SOJA` | exata | — |
| milho | 40122 Milho (em grão) | exata | `MILHO TOTAL` | exata | total = 1ª + 2ª + 3ª safra |
| algodao | 40099 Algodão herbáceo (em caroço) | **parcial** | `ALGODÃO - PLUMA` / `- CAROÇO` | **parcial** | caroço ≠ pluma (fator não convertido) |
| cafe | 40140 Café (em grão) Arábica | equivalente c/ ressalvas | `CAFÉ` | equivalente c/ ressalvas | grão não torrado ≠ referência de mercado |
| trigo | 40127 Trigo (em grão) | exata | `TRIGO` | exata | produção municipal zero |

**FATO.** Produtos fora do catálogo do SADEN (arroz, feijão, girassol, sorgo,
amendoim, gergelim, mamona, café canephora, etc.) são registrados com
`match_class = none` e **não** são eliminados da base.

## 11. Relatório de qualidade

**FATO.** 11 verificações sobre 4.916 registros; **0 erros** e **19 avisos**
(5.866 achados informativos, todos detalhados em
`data/manifests/quality_findings_full.csv`, regenerável pelo mesmo comando).

| Verificação | Resultado |
|---|---|
| Duplicidade | **0** (após correção do parser — ver §14) |
| Código municipal inválido | 0 |
| Ano ausente | 0 |
| Valor nulo | 946 (informativo) — valores “..”/“...” do SIDRA |
| Unidade inconsistente | 0 |
| Área zero com produção positiva | 0 |
| Produtividade/quantidade negativa | 0 |
| Rendimento publicado × calculado | 0 divergências > 5% |
| Safra × ano civil | 360 (informativo) |
| Classificação sem correspondência | 4.560 (informativo) |
| **Revisão entre boletins CONAB** | **13 avisos** |
| **Dupla contagem agregado × componente** | **6 avisos** |

**FATO — revisões entre boletins.** A mesma safra 24/25 aparece com valores
diferentes em dois levantamentos (ex.: algodão em caroço MT: 4.049.700 t no
12º levantamento de 2024/25 e 4.070.500 t no 12º levantamento de 2025/26;
soja MT: +0,3% na produção). São **vintages** distintos, não duplicatas.

**FATO — hierarquia de produtos.** As planilhas trazem “MILHO TOTAL” **e**
“Milho 1ª/2ª Safra” simultaneamente; somar ambos duplicaria a produção.
A base mantém as duas linhas com `crop_scope` distinto (`total`,
`grupo_safra`, `componente`) e a tabela de correspondência usa apenas o
agregado ou o produto simples.

**FATO — divergência de rendimento.** Para todas as combinações com área
colhida, quantidade e rendimento publicados, o rendimento **calculado**
(quantidade/área) confere com o **publicado** dentro de 5%.

## 12. Compatibilidade por combinação

| Cultura | Fonte | Período | Unidade territorial | Produtividade | NDVI disponível | Cobertura | Classe | Observação |
|---|---|---|---|---|---|---|---|---|
| Soja | IBGE/PAM | 2023 | município (0,47% da AOI) | 2.244 kt | sim | 11/12 meses | **B** | municipal; n=1 ano |
| Soja | IBGE/PAM | 2024 | município | 2.085 kt | sim | 11/12 | **B** | idem |
| Soja | IBGE/PAM | 2025 | município | 2.343 kt | sim | 12/12 | **B** | idem |
| Milho | IBGE/PAM | 2023–2025 | município | 3.660–3.820 kt | sim | 11–12/12 | **B** | idem |
| Algodão (caroço) | IBGE/PAM | 2023–2025 | município | 269–325 kt | sim | 11–12/12 | **B + parcial** | caroço ≠ pluma |
| Soja | CONAB | 23/24 … 25/26 | UF (MT) | 40,4–51,6 Mt | parcial (2 anos por safra) | 22–23/24 meses | **C** | estadual; estimativa |
| Milho | CONAB | 23/24 … 25/26 | UF (MT) | 48,8–58,6 Mt | parcial | 22–23/24 | **C** | estadual; estimativa |
| Café | IBGE/PAM | 2013–2025 | município | **0** | — | — | **C** | sem produção: descartado |
| Trigo | IBGE/PAM | 2013–2025 | município | **0** | — | — | **C** | sem produção: descartado |

Tabela completa (80 linhas, incluindo safras e componentes): `data/manifests/correspondence_table.csv`.

## 13. Resultados científicos

**O que pode ser afirmado:**

1. Existem **dados oficiais reais** de produtividade para o município de
   Sorriso (IBGE/PAM), anuais, de 1974 a 2025, para 86 produtos, sem chave e
   sem custo.
2. Para **soja e milho**, existe correspondência **exata** entre o produto
   oficial e as commodities do SADEN, com observações anuais reais nos três
   anos da série Sentinel-2.
3. A granularidade municipal cobre a AOI (100% dentro do município), mas a
   estatística municipal cobre 9.293 km² e a AOI é 0,47% dessa área: a
   compatibilidade com a AOI é **contextual (B)**, nunca direta.
4. A CONAB oferece **estimativas estaduais** por safra, revisadas a cada
   levantamento; a compatibilidade com a AOI é **incompatível (C)**.
5. A base é rastreável: cada registro aponta para instituição, conjunto,
   consulta oficial, data/hora, arquivo e checksum.

**O que permanece incerto:**

1. Se (e como) o NDVI da AOI de 43 km² se relaciona com a produtividade
   municipal — exige n ≥ 10 anos e calendário validado; hoje são n = 3.
2. A composição do uso do solo dentro da AOI (a classe SCL 5 provavelmente
   inclui lavoura, mas não é identificador de cultura).
3. O calendário fenológico aplicável a Sorriso (não confirmado em fonte
   oficial nesta etapa).

**O que NÃO pode ser afirmado:**

1. Que o NDVI da AOI “explique” ou “preveja” a produtividade de Sorriso —
   não há teste, não há ground truth e n = 3.
2. Que a produtividade municipal valida a produtividade da AOI.
3. Que café ou trigo são crops candidatos em Sorriso (produção municipal zero).
4. Que a CONAB seja equivalente ao IBGE: mesma variável, метод e periodicidade
   diferentes (estimativa revisada × coleta municipal observada).

## 14. Implementação

**FATO — arquivos criados:**

| Arquivo | Responsabilidade |
|---|---|
| `geospatial/agri/config.py` | parâmetros, URLs oficiais, licença, commodities do SADEN, códigos de UF |
| `geospatial/agri/sidra.py` | cliente SIDRA, convenções de valor do IBGE, parsing |
| `geospatial/agri/conab.py` | listagem/download das planilhas e parser dos dois blocos (safra e culturas de inverno) |
| `geospatial/agri/crosswalk.py` | vínculos de cultura com classe de correspondência |
| `geospatial/agri/normalize.py` | esquema normalizado, conversões, CSV/JSON |
| `geospatial/agri/validate.py` | 11 verificações de qualidade |
| `geospatial/agri/compat.py` | classificação A/B/C, agregação anual do NDVI, tabela de correspondência |
| `geospatial/agri/geometry_compat.py` | malha municipal reaproveitando a V2.1 (D42) |
| `geospatial/run_productivity.py` | CLI: `inventory`, `acquire`, `normalize`, `validate`, `compat` |

**FATO — arquivos modificados:** `geospatial/requirements.txt` (openpyxl,
xlrd, pandas), `geospatial/.gitignore` (exclusão das planilhas CONAB e dos
derivados redundantes).

**FATO — estrutura de dados:**

```
geospatial/data/
  raw/sidra/    resposta bruta da API SIDRA (versionada)
  raw/conab/    planilhas oficiais (não versionadas; URL+SHA-256 no manifesto)
  processed/    base normalizada (CSV versionado; JSON regenerável)
  manifests/    inventário, manifestos de aquisição, qualidade, compatibilidade
```

**FATO — defeito real encontrado e corrigido pela validação:** o primeiro
parser da planilha CONAB tratava as linhas de tipo (“Cores”, “Preto”, “Caupi”)
como produtos independentes e herdava o rótulo do produto anterior; gerava
48 duplicidades e piorava o escopo. A correção passou a prefixar o rótulo do
pai (“FEIJÃO 1ª SAFRA - Cores”), a tratar “MILHO TOTAL” como agregado e a
reconhecer o segundo bloco da planilha (“CULTURAS DE INVERNO”, que usa **anos
civis**, não safras). As duplicidades caíram para 0.

## 15. Testes

**FATO.**

| Suíte | Comando | Resultado |
|---|---|---|
| Offline (padrão) | `geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests -t geospatial` | **137/137 OK** (95 da V2.1 + 42 novos) |
| Externos (rede, opt-in) | `$env:SADEN_EXTERNAL_TESTS="1"; … -m unittest discover -s geospatial\tests_external -t geospatial` | **10/10 OK** (4 da V2.1 + 6 novos: acesso real ao SIDRA, download real de planilha CONAB com parser, conferência dos nomes IBGE) |

Cobertura nova: convenções de valor do SIDRA (`..`, `-`, `...`, `x`), montagem
de URL, parsing dos dois formatos de resposta, classificação de produtos por
código oficial, crosswalk completo, parser da planilha CONAB (blocos, hierarquia
e escopo), normalização com preservação de valor/unidade originais, conversões
matemáticas, round-trip CSV, 7 verificações de qualidade isoladas, agregação
anual do NDVI com lacunas visíveis, sobreposição temporal e tabela de
correspondência.

**FATO.** Nenhum teste antigo foi removido; a suíte padrão continua sem rede.

## 16. Limitações

1. **Escala**: nenhuma observação oficial na escala da AOI (43 km²) — a
   melhor granularidade é municipal (B) ou estadual (C).
2. **Amostra**: n = 3 anos de sobreposição oficial × Sentinel-2; insuficiente
   para qualquer inferência quantitativa.
3. **Calendário**: janelas fenológicas não confirmadas em fonte oficial; não
   foram inventadas.
4. **Cobertura espacial do NDVI**: a AOI cobre 0,47% do município, e o SCL não
   identifica lavoura; a fração de AOI em área agrícola é desconhecida.
5. **CONAB**: acesso apenas por planilha, sem API; séries históricas de safras
   antigas não estão no portal atual (sondas retornaram 404); SIGS e
   `dados.gov.br` indisponíveis neste ambiente.
6. **Licenciamento**: os termos de uso da CONAB não foram obtidos em forma
   verificável — as planilhas ficam **fora do Git**, com URL e SHA-256 no
   manifesto (decisão D48). A pendência de licenciamento do Sentinel-2/STAC ×
   AWS (V2.1) permanece **aberta**.
7. **Revisões**: valores CONAB mudam entre levantamentos; a base guarda as
   vintages identificadas por arquivo, mas a escolha de uma vintage é decisão
   de uso, não da base.
8. Sem validação de campo, sem dado deUso do solo identificado e sem
   cobertura municipal do Sentinel-2 (processar o município inteiro segue fora
   de escopo).

## 17. Decisões

| Decisão | Assunto |
|---|---|
| **D46** | IBGE/SIDRA PAM (5457) como base observada de referência; CONAB apenas contextual |
| **D47** | Classificação de compatibilidade espacial A/B/C e proibição de rasterizar produtividade municipal |
| **D48** | Licenciamento: planilhas CONAB fora do Git (termos ambíguos); IBGE versionada |
| **D49** | Culturas-piloto: soja e milho (exatas); algodão condicionado (parcial); café e trigo descartados |

## 18. Portão de decisão para a V2.3

**Veredito: CAMINHO 2 — existem dados, mas apenas em escala municipal
(superior à AOI).**

Fundamentação:

* **não** há dados oficiais na escala da AOI nem do talhão (exclui CAMINHO 1);
* há observações oficiais reais, de qualidade verificada e rastreável, mas
  **municipais** (IBGE) ou **estaduais** (CONAB) — servindo de referência
  contextual, não de validação direta da AOI;
* **não** é o caso de dados insuficientes ou incompatíveis de forma
  inviabilizante (exclui CAMINHO 3): a base é sólida, o que falta é escala
  espacial e amostra temporal.

**Escopo recomendado para a V2.3 (se autorizada):**

1. estudo **exploratório na escala municipal** (Sorriso), com o NDVI da AOI
   tratado como **indicador de sub-região** de valor espacial limitado e
   explicitamente declarado;
2. ampliar a série Sentinel-2 para **2017–2025** (n ≥ 9 anos) antes de
   qualquer análise quantitativa — a PAM cobre 1974–2025;
3. validar o **calendário fenológico** em fonte oficial (CONAB “Calendário de
   Safras” / Embrapa) antes de agregações por safra;
4. variável-alvo fixa: **rendimento médio municipal (kg/ha)** do IBGE, com
   área colhida e quantidade publicadas;
5. protocolo com splitting temporal, sem alegar precisão não medida, e com
   declaração explícita de que a série é exploratória;
6. **não** integrar ao Ridge, ao preço nem à interface nesta etapa.

**Pré-requisitos ainda ausentes:** escala espacial mais fina; n ≥ 10;
calendário validado; decisão sobre vintage CONAB; confirmação de uso do solo
na AOI (fonte de cobertura do solo/classificador validado).

## 19. Como reproduzir

```powershell
# 0) dependências (V2.2 adiciona openpyxl, xlrd, pandas)
geospatial\.venv\Scripts\python.exe -m pip install -r geospatial\requirements.txt

# 1) inventário das fontes (rede)
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py inventory

# 2) aquisição real (SIDRA + planilhas CONAB)
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py acquire --year-start 2013 --year-end 2025 --conab-safras "2024/25,2025/26"

# 3) base normalizada, validação e compatibilidade
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py normalize
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py validate
geospatial\.venv\Scripts\python.exe geospatial\run_productivity.py compat

# 4) suíte offline (sem rede) e testes externos (opt-in)
geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests -t geospatial
$env:SADEN_EXTERNAL_TESTS = "1"
geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests_external -t geospatial
```

A base pode ser reconstruída integralmente a partir dos comandos 1–3: o
manifesto `data/manifests/manifest_sidra_pam.json` registra a URL exata da
consulta, o `manifest_conab_safras.json` registra as URLs e os SHA-256 das
planilhas, e `data/raw/sidra/` guarda a resposta bruta da API.
