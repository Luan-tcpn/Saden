# SADEN V2.3 — Estudo exploratório municipal de produtividade agrícola, harmonização Sentinel-2 e validação do potencial preditivo

> Branch: `v2/agricultural-productivity-exploratory` (derivada de
> `v2/agricultural-productivity-data` / `775d57b`). V1 congelada e intocada.
> Execuções de referência: 2026-11-11.
> Código: `geospatial/historical/`; CLI: `geospatial/run_historical.py`;
> dados: `geospatial/data/{processed,manifests}/`.

**Veredito final: CAMINHO B — estudo executável com ressalvas.** Não há modelo
preditivo validado: a associação entre o NDVI da AOI e o rendimento municipal
**não é significativa** e o modelo com NDVI **não melhora** os baselines
triviais na validação temporal progressiva.

---

## 1. Objetivo

Estabelecer se existe base temporal e metodológica consistente para investigar
relações entre vegetação (Sentinel-2) e produtividade (IBGE/PAM) no município
de **Sorriso-MT (5107925)**, mantendo a AOI de validação da V2.1 (43,26 km²) e o
rendimento médio municipal como **única** variável-alvo (kg/ha).

## 2. Estado inicial

| Item | Valor |
|---|---|
| Branch de partida | `v2/agricultural-productivity-data` @ `775d57b` |
| Baseline V1 | `3f7ad33` (intocada, local e remoto) |
| Tags | `v1-final` (`e62a5372…`), `v2-poc-sentinel2` (`2e5b3ef`) |
| Bundle da V2.3 | `..\SADEN_V2_3_RECOVERY_2026-11-11\saden-v2-3-start-2026-11-11.bundle` (3.718.796 B, SHA-256 `C3449A62…5B69`, verify OK) |
| Testes no início | 137/137 offline; reexecutados nesta missão |

## 3. Fontes utilizadas

| Fonte | Uso | Estado |
|---|---|---|
| Earth Search — `sentinel-2-c1-l2a` (C1 harmonizada) | série histórica principal | acessível |
| Earth Search — `sentinel-2-l2a` (originais) | preenchimento das lacunas de ingestão da C1 | acessível |
| ESA WorldCover 10 m (v200/2021, v100/2020) | uso do solo da AOI | acessível (COG público) |
| IBGE/SIDRA — PAM 5457 | rendimento, área e quantidade municipais | acessível (sem chave) |
| MapBiomas Cobertura 10 m | uso do solo (pretendido) | **BLOQUEADO** |
| Copernicus Data Space (STAC) | verificação de catálogo | acessível (itens em JP2/S3) |
| Planetary Computer | alternativa de COG | **BLOQUEADO** (SAS 429) |
| SISZARC/MAPA (ZARC) | calendário de plantio | **BLOQUEADO** (DNS) |

## 4. Harmonização histórica (D50)

**FATO.** A coleção C1 declara `scale = 0.0001` e `offset = −0.1` em **954
assets** de 2017–2025, independentemente do baseline. A coleção original declara
`offset = −0.1`, mas o DN armazenado é **exatamente 1000 unidades menor**
(0,1 de reflectância) — inconsistência de catálogo medida por leitura direta
dos COGs.

**FATO — experimento pareado (6 datas, 2018–2025, mesma grade, ~109.700 pixels
válidos por par):**

| Data | Perfil C1 | Perfil original | Pixels comuns | Δ NDVI médio | \|Δ\| mediano | Correlação |
|---|---|---|---|---|---|---|
| 2018-09-04 | `DN*1e-4 − 0.1` | `DN*1e-4` | 109.776 | **0,0** | 0,0 | **1,0** |
| 2019-07-31 | idem | idem | 109.735 | **0,0** | 0,0 | **1,0** |
| 2019-08-30 | idem | idem | 109.782 | **0,0** | 0,0 | **1,0** |
| 2021-06-30 | idem | idem | 109.720 | **0,0** | 0,0 | **1,0** |
| 2023-07-30 | idem | idem | 109.766 | **0,0** | 0,0 | **1,0** |
| 2025-07-26 | idem | idem | 109.734 | **0,0** | 0,0 | **1,0** |

**FATO.** O pipeline da V2.1 **não foi alterado**: o tratamento histórico é um
perfil separado (`geospatial/historical/radiometry.py`), com manifesto e testes
próprios. Nenhuma regressão, fator empírico ou correção "visual" foi usada.

**LIMITAÇÃO.** A equivalência foi verificada em 6 pares; a garantia
estatística de equivalência radiométrica para todo o arquivo não é feita.

## 5. Série histórica 2017–2025

**FATO.** Grade 20 m `EPSG:32721` (329 × 334 px), máscara SCL **Perfil B**,
seleção pela fração obstruída sobre a AOI, tile `MGRS-21LXG`, lacunas
preservadas.

| Ano | Meses observados | Perfil C1 | Perfil original | Baselines |
|---|---|---|---|---|
| 2017 | 11 | 4 | 7 | 05.00, 00.01 |
| 2018 | 11 | 11 | 0 | 05.00 |
| 2019 | 11 | 11 | 0 | 05.00 |
| 2020 | 12 | 11 | 1 | 05.00, 00.01 |
| 2021 | 10 | 10 | 0 | 05.00 |
| 2022 | 12 | 1 | 11 | 04.00, 05.00 |
| 2023 | 11 | 11 | 0 | 05.09/05.10/05.11 |
| 2024 | 11 | 11 | 0 | 05.10/05.11 |
| 2025 | 12 | 12 | 0 | 05.11 |
| **Total** | **101/108** | 69 | 32 | 00.01 … 05.11 |

**FATO.** A cobertura anual é de 10–12 meses em **9 anos consecutivos**
(2017–2025) — o mínimo de 9 pares anuais por cultura (D53) é alcançável.

## 6. Uso do solo na AOI (D51)

**FATO — bloqueio:** a página oficial do MapBiomas informa que *“a função de
baixar mapas está temporariamente suspensa”* e que o acesso passa pelos assets
do Google Earth Engine (exige conta). Endereços públicos testados retornaram
404; o PC exigiu SAS (HTTP 429). As **legendas oficiais** foram obtidas e
conferidas (Coleção 4 10 m: 3.2.1 Lavoura Temporária, 3.2.2 Lavoura Perene,
3.1 Pastagem, 3.4 Mosaico de Usos, 1.1 Formação Florestal, 1.3 Formação
Savânica, 4 Área não vegetada, 5 Corpo D'água; Coleção 11 CSV: 3, 4, 15, 21, 25).

**FATO — ESA WorldCover (10 m, classe oficial 40 = Cropland):**

| Ano | Área total da AOI | Lavoura (40) | Fração agrícola |
|---|---|---|---|
| 2020 | 43,36 km² | 33,68 km² | **77,63%** |
| 2021 | 43,36 km² | 35,19 km² | **81,16%** |

**INTERPRETAÇÃO.** A AOI de validação **é predominantemente agrícola** — a
premissa geométrica do estudo se confirma com fonte oficial.

**LIMITAÇÃO.** WorldCover **não** separa lavoura temporária de perene e **não**
identifica soja/milho; não há máscara MapBiomas por pixel nem série anual de
uso do solo 2017–2025. O indicador de NDVI sobre lavoura existe apenas para
2020–2021.

## 7. Calendário agrícola (D52)

**BLOQUEADO.** SISZARC/MAPA não resolve DNS; a página de safras da CONAB não
expõe arquivo; as páginas da Embrapa testadas retornaram 404. **Nenhuma janela
fenológica foi inventada**: a agregação é por **ano civil**, com a ressalva
declarada de que o ano de referência da PAM é o ano civil da produção e não o
ano-safra. Milho 1ª/2ª safra e "milho total" não foram misturados: a PAM
publica o total do ano, tratado como agregação anual.

## 8. Variável-alvo

**FATO.** `rendimento_medio_kg_ha` (variável 112 da tabela 5457) do IBGE/PAM
para o município 5107925, culturas 40124 (Soja em grão) e 40122 (Milho em
grão), 2017–2025. Valor e unidade originais preservados; a normalização para
kg/ha é **identidade** (o IBGE já publica em kg/ha) e está registrada como tal.
Área colhida e quantidade produzida são mantidas como variáveis de controle
(não substituem o rendimento).

## 9. Conjunto temporariamente pareado

`geospatial/data/processed/productivity_exploratory_dataset.csv` — 18 registros
(2 culturas × 9 anos), todos com estado `paired_usable`.

| Ano | Soja (kg/ha) | Milho (kg/ha) | NDVI AOI (média das médias mensais) | Meses observados | Cobertura média |
|---|---|---|---|---|---|
| 2017 | 3.480 | 7.258 | 0,5282 | 11 | 97,5% |
| 2018 | 3.720 | 6.600 | 0,5130 | 11 | 99,1% |
| 2019 | 3.540 | 6.777 | 0,4945 | 11 | 92,8% |
| 2020 | 3.870 | 6.840 | 0,4887 | 12 | 89,7% |
| 2021 | 3.360 | 5.666 | 0,5061 | 10 | 93,8% |
| 2022 | 3.540 | 7.080 | 0,4312 | 12 | 97,2% |
| 2023 | 3.750 | 7.140 | 0,4910 | 11 | 91,1% |
| 2024 | 3.480 | 7.320 | 0,4654 | 11 | 95,8% |
| 2025 | 4.260 | 8.400 | 0,5419 | 12 | 95,6% |

**FATO.** O conjunto tem 26 registros (13 anos × 2 culturas): **18 pareados e
utilizáveis** (2017–2025) e 8 excluídos (2013–2016, sem observação Sentinel-2 na
série histórica).

**FATO — comparação com a série da V2.1:** para 2023–2025 o NDVI anual desta
série (0,4910 / 0,4654 / 0,5419) **não é idêntico** ao da V2.1 (0,4982 /
0,4922 / 0,5579). A radiometria é equivalente (D50, Δ = 0,0); a diferença vem do
**conjunto de candidatas** usado na seleção (a série histórica avalia as duas
coleções e pode escolher uma cena menos obstruída que a da V2.1, que usava
apenas a C1). Nenhum resultado da V2.1 foi alterado.

## 10. Análise exploratória

**FATO — correlações (n = 9 por cultura; p por permutação bilateral, 5.000
permutações):**

| Cultura | n | Pearson r | Spearman ρ | p (permutação) | r após remover tendência |
|---|---|---|---|---|---|
| Soja | 9 | 0,432 | 0,134 | **0,246** | 0,584 |
| Milho | 9 | 0,200 | 0,067 | **0,610** | 0,354 |

**FATO — experimentos com validação temporal progressiva** (treino mínimo 5
anos, 4 previsões por modelo, sem divisão aleatória):

| Cultura | Modelo | MAE (kg/ha) | RMSE (kg/ha) | MAPE (%) |
|---|---|---|---|---|
| Soja | média histórica | **253,8** | 350,8 | **6,32** |
| Soja | último valor | 360,0 | 435,3 | 9,19 |
| Soja | tendência linear | 272,7 | 368,9 | 6,82 |
| Soja | regressão com NDVI | 368,2 | 430,4 | 9,56 |
| Milho | média histórica | 751,8 | 887,5 | 9,67 |
| Milho | último valor | **683,5** | 894,7 | **9,03** |
| Milho | tendência linear | 1.043,0 | 1.096,0 | 13,85 |
| Milho | regressão com NDVI | 955,1 | 1.117,7 | 12,40 |

**INTERPRETAÇÃO.** (a) As correlações não são significativas (p = 0,25 e 0,61);
com n = 9, mesmo um r de 0,58 (após remover a tendência) não permitiria
conclusões. (b) A regressão com NDVI **não melhora** os baselines triviais em
nenhuma das culturas — o critério de ganho (D53) **não é atendido**. (c) A
correlação detrendizada maior que a correlação bruta em soja mostra que
tendências temporais opostas (rendimento e NDVI) se cancelam parcialmente: é o
assinatura clássica de risco de correlação espúria por tendência, e reforça
que a correlação observada não deve ser interpretada como relação.

**LIMITAÇÃO.** Escala espacial divergente (rendimento municipal × NDVI de uma
sub-região de 0,4654% do município); sem calendário validado; sem controle de
outras lavouras, solo, irrigação ou manejo; SCL 5 e WorldCover não identificam
soja/milho; n = 9.

## 11. Conclusão científica

**O que pode ser afirmado:**

1. Existe uma série Sentinel-2 **radiometricamente homogênea** de 2017–2025
   sobre a AOI (101/108 meses, 9 anos completos), cuja equivalência entre a
   coleção harmonizada e a original foi medida (Δ NDVI = 0,0).
2. A AOI de validação é **predominantemente agrícola** (77,6%–81,2% de
   lavoura, ESA WorldCover) — o estudo tem base espacial pertinente.
3. O alvo municipal do IBGE/PAM tem **9 anos** utilizáveis para soja e milho,
   com cultura e unidade conferidas.
4. **Não** há evidência de relação detectável entre o NDVI da AOI e o
   rendimento médio municipal (p = 0,25 e 0,61), e o uso do NDVI **não**
   melhora a previsão temporal frente a baselines triviais.

**O que permanece incerto:** magnitude real de uma eventual relação (n = 9);
composição do uso do solo da AOI por cultura; efeito de manejo e clima;
compatibilidade fina entre a janela do Sentinel-2 e o ciclo da cultura.

**O que não pode ser afirmado:** que o NDVI não tem relação com produtividade
(seria extrapolar além da amostra); que o estudo prova ausência de relação
causal; qualquer capacidade preditiva em produção.

## 12. Portão de decisão (D53)

| Condição | Situação |
|---|---|
| Série radiometricamente consistente | **atendida** (D50) |
| AOI com área agrícola identificada | **atendida** (77,6%–81,2%) |
| Cobertura temporal suficiente | **atendida** (9 anos, 101/108 meses) |
| Calendário de referência documentado | **NÃO atendida** (D52) |
| Rendimento IBGE disponível | **atendida** (9 anos × 2 culturas) |
| ≥ 9 pares anuais por cultura | **atendida** (n = 9) |
| Ausência de vazamento temporal | **atendida** (divisão walk-forward) |
| Ganho consistente do modelo com NDVI | **NÃO atendida** (pior que os baselines) |

**Classificação: CAMINHO B — estudo executável com ressalvas.** Análise
descritiva e associações exploratórias são compatíveis com as limitações;
**não** há modelo preditivo validado e **não** há base para integrar o indicador
ao produto ou ao Ridge.

## 13. Testes e reprodutibilidade

| Suíte | Comando | Resultado |
|---|---|---|
| Offline | `… -m unittest discover -s geospatial\tests -t geospatial` | **165/165 OK** (137 da V2.1/V2.2 + 28 novos da V2.3) |
| Externos (rede, opt-in) | `$env:SADEN_EXTERNAL_TESTS="1" …` | 10/10 OK (V2.1/V2.2) |

**FATO.** A série histórica foi reprocessada com `--resume` após a correção do
reconhecimento do tile MGRS dos itens com nomenclatura Sentinel Hub — as
observações iniciais (64 meses) foram substituídas por 101 meses, e a correção
está coberta por teste unitário (`tile_code`).

## 14. Limitações

1. Escala espacial divergente entre alvo e indicador (D47).
2. n = 9 anos — limiar de viabilidade, não de suficiência estatística.
3. Sem calendário fenológico validado (D52).
4. Identificação de cultura na AOI **inexistente** com as fontes acessíveis.
5. Série de uso do solo anual indisponível (MapBiomas bloqueado); máscara de
   lavoura só para 2020–2021.
6. Equivalência radiométrica verificada em 6 pares de datas.
7. Lacunas mensais preservadas (7 de 108) e registradas.
8. Nenhuma validação de campo, nenhum dado de produtividade por talhão.

## 15. Decisões

**D50** perfil radiométrico histórico · **D51** uso do solo (WorldCover;
MapBiomas bloqueado) · **D52** calendário não validado, agregação por ano
civil · **D53** portão estatístico (≥ 9 pares; ganho exigido para chamar um
modelo de promissor).

## 16. Próximo passo recomendado

**Não iniciar a V2.4 (integração ao Ridge) nem um modelo de produtividade.**
Próximo passo único: **revisar com o orientador o escopo municipal exploratório**, e decidir se vale (a)
obter acesso a uma base espacialmente mais fina (MapBiomas via GEE com conta
institucional; SIGS da CONAB quando acessível) e (b) construir o calendário
oficial (ZARC/Embrapa) para permitir janelas de safra. Sem esses dois insumos,
ampliar a amostra não resolve a limitação de escala, que hoje é a limitação
determinante.

## 17. Como reproduzir

```powershell
geospatial\.venv\Scripts\python.exe geospatial\run_historical.py radiometry
geospatial\.venv\Scripts\python.exe geospatial\run_historical.py series --start 2017-01 --end 2025-12
geospatial\.venv\Scripts\python.exe geospatial\run_historical.py landuse --years 2020 2021
geospatial\.venv\Scripts\python.exe geospatial\run_historical.py study
```

Manifestos: `geospatial/data/manifests/{sentinel2_historical_inventory,
sentinel2_original_collection_inventory,sentinel2_radiometry_experiment,
sentinel2_historical_series,landuse_aoi_report,exploratory_study}.json`.
