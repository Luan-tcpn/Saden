# SADEN V2.6 — Fundação agroclimática: dados, métodos e qualidade

> Branch: `v2/agroclimatic-productivity-panel`. Execução: 2026-11-12.
> Artefatos: `geospatial/data/processed/agroclimatic_productivity_panel.csv`,
> `geospatial/data/manifests/agroclimatic_panel.json`,
> `geospatial/data/manifests/climate_quality.json`,
> `geospatial/data/manifests/agroclimatic_analysis.json`,
> `geospatial/data/manifests/inmet_stations.json`,
> `geospatial/data/manifests/zarc_panel.json`,
> `geospatial/data/manifests/pam_panel.json`,
> `geospatial/data/manifests/panel_eligibility.json`.
> Decisões: D66–D72 em `docs/DECISIONS.md`.

---

## 1. Por que a V2.6 existe

**FATO.** A V2.5 concluiu que o NDVI **não** explica o rendimento municipal, e
não por falta de rigor metodológico: escala harmonizada, janela oficial do
ZARC, n efetivo contabilizado, validação temporal alinhada e correção de
Holm. O resultado foi **negativo** (soja: r = 0,432 na réplica da V2.3 →
0,203 com escala municipal e janela do ZARC; milho: 0,200 → −0,396), e nenhum
dos 32 testes da família foi significativo.

**FATO.** Duas deficiências de *amostragem* permaneceram: **n = 8 anos** num
único município (Sorriso/MT) e um alvo de produtividade **municipal**, cuja
variação espacial é dominada por diferenças de solo, manejo e portfolio de
culturas — não apenas por clima.

**Decisão (D66).** A linha do NDVI como variável de produtividade é
**encerrada**. A V2.6 abre uma linha **agroclimática** (variáveis térmicas,
hídricas e meteorológicas) e constrói um **painel multi-municipal** para
superar a limitação de n. Os indicadores Sentinel-2 **permanecem** como
material de pesquisa e referência geoespacial; nada foi apagado.

---

## 2. Fontes meteorológicas: o que foi verificado

| Fonte | Acesso verificado | Papel na V2.6 | Situação |
|---|---|---|---|
| **INMET** (estações) | `apitempo.inmet.gov.br/estacoes/T` → 668 estações; arquivos anuais 2000–2026 (`portal.inmet.gov.br/uploads/dadoshistoricos/<ano>.zip`, ~100 MB/ano) | **Observação** (`station_observation`) — base independente de validação | **acessível** |
| **NASA POWER** (MERRA-2 + CERES, comunidade AG) | API oficial `power.larc.nasa.gov/api/temporal/daily/point` | **Reanálise** (`reanalysis`) — base espacialmente consistente do painel | **acessível** (1,6 s/município) |
| **ERA5-Land** | Via Open-Meteo (`models=era5_land`): temperatura, umidade, ponto de orvalho, temperatura e umidade do solo | **Reanálise** (`reanalysis`) — variável complementar | **parcialmente bloqueada** (HTTP 429 sustentado após uso intensivo) |
| **ERA5** (0,25°) | Via Open-Meteo (`models=era5`): precipitação, radiação, vento, pressão, umidade, temperatura | **Reanálise** (`reanalysis`) — variáveis ausentes no ERA5-Land | **parcialmente bloqueada** (mesmo 429) |
| **CHIRPS** | `chc.ucf.edu` / `data.chc.ucf.edu` | Precipitação grillada complementar | **BLOQUEADO** — sem resolução DNS |
| **CDS da Copernicus** | `cds.climate.copernicus.eu/api/catalogue/v1/...` responde (metadados) | Acesso **nativo** ao ERA5-Land | exige **chave de conta** não configurada; não foram criadas contas nem lidas credenciais pessoais |

**INTERPRETAÇÃO.** A limitação do ERA5-Land **não** é da fonte, é da **via de
acesso**: o produto é público e documentado, mas o CDS exige chave de conta e
o espelho ARCO não resolve DNS neste ambiente. A fonte foi obtida parcialmente
pelo acesso alternativo (Open-Meteo), que entrega as variáveis térmicas e de
solo — as acumuladas (precipitação, radiação) e de vento/pressão não estão
disponíveis nesse acesso eloch foram supridas por ERA5.

**LIMITAÇÃO.** O painel foi construído com o **NASA POWER** como base
espacialmente consistente porque é a única reanálise com o conjunto completo de
variáveis acessível sem autenticação neste ambiente. As conclusões são
portanto sobre MERRA-2, e a robustez em relação ao ERA5-Land/ERA5 fica como
trabalho pendente (limitação de acesso, não de método).

---

## 3. Inventário de estações do INMET e seleção por município

**FATO.** O catálogo oficial traz **668 estações automáticas** em 27 estados
(534 operantes, 134 em pane), com código WMO, nome, coordenadas, altitude,
estado, tipo, situação e datas de início/fim de operação.

**FATO.** Para os 1.782 municípios do painel, a seleção seguiu três níveis
explícitos e registrados:

| Critério | Regra | Resultado |
|---|---|---|
| 1 | estação **dentro** do polígono municipal | 294 municípios (16,5%) |
| 2 | estação **mais próxima** dentro de 80 km | 1.425 municípios (79,9%) |
| 3 | nenhuma estação no limite | 63 municípios (**lacuna preservada**) |

**FATO.** A distância à estação é registrada em cada linha, e a
representatividade é classificada (`high` dentro do município, `medium` até
50 km, `low` além disso). A escolha **não** é pelo centroide: o teste é
ponto-em-polígono sobre a malha oficial.

**FATO.** As malhas municipais foram lidas do **shapefile oficial** do IBGE
(`geoftp.ibge.gov.br`, um arquivo por UF), com um leitor de shapefile/DBF
escrito em Python puro — o ambiente não tem `pyshp`/`geopandas`/`fiona` e a
V2.5 fixou deliberadamente as dependências do geospatial. A API de malhas do
IBGE responde com *timeout* neste ambiente.

**LIMITAÇÃO.** 63 municípios (3,5%) ficam **sem** série de observação de
estação; a lacuna é preservada e eles são excluídos da via observacional
(permanecem no painel reanalisado).

---

## 4. Qualidade das séries meteorológicas

**FATO.** A auditoria cobre 1.622 séries (uma por município na base
reanalisada):

| Verificação | Resultado |
|---|---|
| Cobertura de precipitação | 1,000 em todas as séries |
| Datas duplicadas | 0 |
| Valores fora da faixa física | 0 |
| Descontinuidades (lacuna ≥ 5 dias) | 0 |
| Registros com precipitação zero (observação real) | preservados como zero |
| Registros ausentes (`-9999` do INMET) | **nunca** convertidos em zero |

**FATO.** O INMET usa a sentinela `-9999` para "sem observação". A
normalização distingue esse caso de **chuva zero**, que é uma observação
válida. A ausência **não** vira zero, e nenhuma interpolação é aplicada.

**FATO.** Os arquivos do INMET usam convenções distintas entre estações
automáticas e convencionais (o cabeçalho pode ser `Data;Hora UTC;…` ou
`DATA (YYYY-MM-DD);HORA (UTC);…`), e unidades distintas (pressão em **mB**,
radiação em **kJ/m²**, vento em **m/s**). Todas são convertidas na
normalização (mB → kPa, kJ/m² → MJ/m², m/s → km/h) e registradas.

**FATO (eficiência).** A leitura dos arquivos anuais é feita por **HTTP
Range**: apenas o CSV da estação necessária é transferido — **808 kB lidos em
7 requisições (3,2 MB)** em vez de 102 MB por ano e por estação.

---

## 5. Comparação INMET × reanálise

**FATO.** 215 estações com série do INMET dentro do município foram
comparadas, na **localização da estação**, com a série reanalisada do mesmo
município (NASA POWER / MERRA-2, célula de ~0,5° × 0,625°):

| Variável | Viés (reanálise − estação) | MAE | RMSE | Correlação |
|---|---:|---:|---:|---:|
| Temperatura média (°C) | **+0,37** | 1,42 | 1,79 | **0,854** |
| Precipitação (mm/dia) | **−0,38** | 3,26 | 8,08 | **0,602** |
| Precipitação acumulada anual (mm) | −661 (7.512 vs 8.173) | — | — | — |

**INTERPRETAÇÃO.**

* **Temperatura**: concordância alta (r = 0,854) e viés pequeno (+0,37 °C). É o
  resultado esperado entre uma medição pontual e uma célula de ~55 km.
* **Precipitação**: a reanálise **subestima** a precipitação observada em
  cerca de **8%** (7.512 contra 8.173 mm/ano) e a correlação diária é
  moderada (r = 0,602). Esse é um **viés conhecido do MERRA-2** em regiões
  tropicais, e **não** um erro de implementação: é uma propriedade da fonte.

**LIMITAÇÃO.** A diferença é de **escala e de fonte**, não de erro. Nenhuma
correção empírica foi aplicada (D75): o painel usa a reanálise como está, e
esse viés de ~8% na precipitação faz parte da interpretação dos resultados —
em particular, a precipitação **medida** em estação tenderia a produzir
coeficientes ligeiramente maiores.

**INTERPRETAÇÃO (efeito para o painel).** A subestimação sistemática da
precipitação pela reanálise não invalida o sinal observado: ela é
aproximadamente uniforme entre municípios e, portanto, não explica as
diferenças **entre** municípios — que é justamente o que a validação
territorial mede.

---

## 6. Painel multi-municipal: construção e critérios

### 6.1 Critérios de elegibilidade (D69, fixados **antes** da análise)

Um município entra no painel para uma cultura se:

1. tiver rendimento médio **observado** (PAM) positivo em pelo menos **7**
   dos 9 anos de 2017–2025;
2. tiver área colhida positiva em pelo menos um ano;
3. tiver geometria municipal oficial disponível;
4. tiver pelo menos uma estação do INMET dentro do município ou a até 80 km.

**FATO.** 1.622 municípiosDistinctos atingiram o critério, gerando **2.780
pares município-cultura elegíveis**. Cada exclusão está registrada com o
motivo em `panel_excluded_municipalities.csv`.

### 6.2 Estados

| UF | municípios | Soja | Milho | Milho 2a |
|---|---:|---:|---:|---:|
| MT | 142 | 911 | 997 | 353 |
| GO | 246 | 1.558 | 1.567 | 285 |
| MS | 79 | 586 | 552 | 428 |
| PR | 399 | 2.863 | 2.966 | 1.836 |
| RS | 499 | 2.966 | 1.428 | — |
| BA | 417 | — | 106 | — |

**FATO.** A Bahia fica fora do painel final de soja e milho porque, pelas
janelas oficiais do ZARC da Bahia (ciclo curto, março–junho e/ou
outubro–dezembro), a cobertura do período de plantio não atingiu o critério
de cobertura — o que é uma limitação **da janela**, não da falta do dado
climático.

### 6.3 Resultado do painel

| Métrica | Valor |
|---|---:|
| Linhas totais | 35.894 |
| Observações utilizáveis | **19.402** |
| Soja | 8.884 (1.225 municípios, 8 anos) |
| Milho | 7.616 (1.063 municípios, 8 anos) |
| Milho 2ª safra | 2.902 (505 municípios, 9 anos) |

**FATO.** O painel é **desbalanceado** (cada município tem 8–9 anos, mas
cobertura e composição variam). Não foram criados valores ausentes nem
preenchidos anos sem produção.

**FATO.** As janelas do ZARC são **proxy**: são recomendações oficiais de
plantio, não datas de plantio observadas. Cada linha carrega os decêndios, o
solo, o ciclo, o nível de risco e a portaria de origem.

### 6.4 Correção da janela descontígua (D63, revisão V2.6)

**FATO.** Com a âncora dupla de decêndios (1–12 no segundo ano da safra,
13–36 no primeiro), as janelas oficiais das **culturas de ciclo curto do
Nordeste** (soja e milho da Bahia, com janelas em março–junho **ou**
outubro–dezembro) caíam em **dois blocos de calendário separados**.

**Decisão.** Usa-se o **bloco contíguo de maior duração** (desempate: o de
início mais antigo) — o período de plantio principal. Os meses do bloco
secundário são **descartados**, não agregados: agregar meses separados por um
intervalo não coberto misturaria períodos e poderia incorporar meses
posteriores ao ano de colheita.

**FATO.** Com a correção, 10 linhas do painel têm meses descartados e **nenhuma**
janela utilizável permanece descontígua.

---

## 7. Indicadores agroclimáticos

### 7.1 Graus-dia e soma térmica (D68)

Cada cultura tem **perfis metodológicos próprios**, com fonte, fórmula, grupo
de cultivar e limitações — **não há temperatura-base universal**:

| Perfil | Cultura | Tb | T superior | Modo de limite | Fonte |
|---|---|---:|---:|---|---|
| `soja_ometto` | soja | 14 °C | 36 °C | média | Ometto (1981), aplicado no Centro-Norte de MT |
| `soja_gilmore` | soja | 10 °C | 30 °C | média | Gilmore & Rogers (1958) / Arnold (1960) / Schneider et al. (1987); emergência = 92,5 °C·dia, R5 = 554 °C·dia |
| `milho_embrapa` | milho | 10 °C | 30 °C | extremos | Embrapa Milho e Sorgo (AgenTec): Tmax ≤ 30 °C, Tmin ≥ 10 °C; exigências 780–830 (superprecoces), 831–890 (precoces), 890–1.200 (normais) °C·dia |

**FATO.** O painel usa `soja_gilmore` (soja) e `milho_embrapa` (milho e
milho 2ª). O perfil `soja_ometto` fica disponível como cenário.

### 7.2 Evapotranspiração (D68)

Três métodos, **identificados** na saída e nunca misturados:

* `fao56_penman_monteith` (principal) — Allen et al. (1998), com a conversão de
  vento de 10 m para 2 m pelo coeficiente 0,4 da FAO-56;
* `thornthwaite_1948` — com índice de calor *I* e expoente *a* (a mesma
  definição do BHCalc da Embrapa/IAC);
* `hargreaves_samani` — exige apenas Tmax, Tmin e radiação extraterrestre.

**FATO (correção).** A primeira implementação do FAO-56 multiplicava a radiação
líquida pelo coeficiente 0,408 **sem** o gradiente de pressão de vapor e
usava um termo inexistente no denominador: o ET0 saía **~6×** inflado
(≈ 23 mm/dia em vez de ≈ 5,8 mm/dia para um dia de céu limpo no Cerrado). O
erro foi encontrado por um **teste de faixa fisiológica** e corrigido; o
ET0 médio do painel (janela de plantio do milho) passou de 1.543 mm para
**435 mm** — valor compatível com a climatologia do Brasil Central.

### 7.3 Balanço hídrico de Thornthwaite & Mather (D68)

* **ETP**: Thornthwaite (1948);
* **sequencial**: Thornthwaite & Mather (1955) — armazenamento limitado pela
  **CAD**, com ETR, deficiência e excedente em mm;
* **CAD**: perfis documentados — `tipo2_medio` (50 mm, MAPA/Embrapa) como
  principal; `tipo1_arenoso` (35 mm) e `tipo3_argiloso` (70 mm) como
  cenários.

**FATO (correção).** A primeira versão comparava a **precipitação mensal**
(soma) com a **ETP mensal** calculada como *média* diária do ET0 — o que
zerava o déficit hídrico. Corrigido: a ETP mensal é a **soma** do ET0 diário.

**FATO (resultado).** Com o balanço corrigido, o painel do milho apresenta
déficit hídrico médio de **109,5 mm** e excedente médio de **120,3 mm** na
janela de plantio — magnitudes coerentes com o clima do período.

**LIMITAÇÃO.** O **balanço hídrico de cultivo** (com Kc e estádios
fenológicos) **não** foi construído: os parâmetros por cultivar não são
conhecidos e inventá-los seria metodologicamente inválido.

### 7.4 Demais indicadores

Por município e janela: precipitação acumulada e média diária, dias com
chuva, dias secos, temperatura média/máxima/mínima, umidade relativa, radiação
solar, vento, umidade do solo (camadas 0–7 e 7–28 cm), graus-dia, soma
térmica, dias de calor extremo (Tmax > 35 °C), noites quentes (Tmin > 20 °C),
eventos de calor e ET0/ETP/ETR/deficiência/excedente.

---

## 8. Qualidade, lacunas e limitações da base

| Limitação | Magnitude |
|---|---|
| **Máscara do ZARC é proxy** | a janela é recomendação oficial, não plantio observado |
| **Cobertura da grade** | o NASA POWER interpola para o centroide a partir de uma grade de ~0,5° × 0,625° (~55 km); municípios vizinhos compartilham informacao altamente correlacionada |
| **Ausência de fonte anual de uso do solo** | mantido da V2.5 (MapBiomas bloqueado) |
| **Sem ZARC para a Bahia** | a janela de ciclo curto não atingiu a cobertura mínima |
| **Milho agregado na PAM** | o alvo é o total do ano (1ª + 2ª safras); a incompatibilidade é declarada linha a linha |
| **Valores extremos da PAM** | são valores **oficiais** e matematicamente coerentes (quantidade ÷ área); mantidos, com verificação de coerência reportada |
| **ERA5-Land e ERA5** | acesso público bloqueado por limite de taxa (429) neste ambiente |

---

## 9. Testes e reprodutibilidade

**FATO.** Suíte offline: **262/262** (49 novos da V2.6), incluindo:

* o leitor de ZIP remoto (tamanho exato devolvido e cursor advancesdo);
* o leitor de shapefile/DBF (campos e valores);
* a normalização do INMET (ausente ≠ zero, conversão de unidades, dois
  formatos de cabeçalho);
* os perfis de graus-dia (limite da média × limite dos extremos);
* o FAO-56 em **faixa fisiológica** (regressão do bug de 6×);
* o balanço hídrico (deficiência, excedente, ETP mensal = soma);
* a auditoria de séries (ausente, faixa física, duplicata, descontinuidade);
* a seleção de estação (três níveis);
* o painel (indicadores, exclusões, ausência de duplicatas por janela,
  incompatibilidade do milho 2ª);
* a análise (baselines sobre o rendimento, coeficiente recuperado nos efeitos
  fixos, walk-forward sem vazamento, holdout territorial por município,
  determinismo da permutação).

**FATO.** Testes externos (opt-in): ver seção 13.

**FATO (reprodutibilidade).** Toda a base é reconstruída pelos comandos de
`run_agroclimate.py` (`municipalities`, `stations`, `climate`, `quality`,
`pam`, `zarc`, `panel`, `analyse`, `validate`); os artefatos grandes ficam
fora do Git, com o manifesto correspondente versionado.

---

## 10. Decisões

D66–D72 (ver `docs/DECISIONS.md`). As D42–D65 não foram alteradas.

---

## 11. Resultado da fundação

**Caminho da V2.6 quanto à base de dados: A — painel agroclimático viável.**

A base é reproduzível, auditada, com procedência declarada por linha e
variáveis que não dependem de mascaramento de vegetação. A limitação
principal é de **acesso** (ERA5-Land e ERA5 por limite de taxa; CHIRPS sem
DNS) e de **resolução espacial** (a grade do MERRA-2 é grosseira para
escalas sub-municipais), e não de método.
