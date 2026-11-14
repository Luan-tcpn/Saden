# SADEN V2.7 — Relatório de robustez estatística, validação espacial e agronomia

> Etapa V2.7 da pesquisa agroclimática do SADEN. Documento de
> consolidação: reúne o que foi recuperado da execução anterior, o que foi
> validado, corrigido e refeito, e a comparação **V2.6 × V2.7**.
>
> Decisões: `docs/execution/v2.7/DECISIONS_V2_7.md` (D76–D84).
> Evidências: `docs/execution/v2.7/EVIDENCE_MATRIX.md`.
> Dados: `docs/execution/v2.7/DATA_MANIFEST.md`.
> Retomada: `docs/execution/v2.7/RECOVERY.md`.

---

## 1. Resumo executivo

A V2.7 testou se os resultados da V2.6 sobrevivem a uma inferência que
controle a **dependência espacial real** da base meteorológica. A resposta é
**parcialmente sim, e com uma correção importante**:

1. A dependência espacial **não** termina na resolução nominal de 55 km.
   NASA POWER interpola a coordenada solicitada e a correlação das
   anomalias anuais ainda é 0,834 (temperatura) e 0,630 (precipitação) a
   400 km. A escala correta de agrupamento é o **bloco espacial de 250 km**.
2. Com esse agrupamento conservador, **4 de 21 hipóteses** sobrevivem ao
   Holm (contra 13 com o agrupamento por município da V2.6). Os **quatro
   resultados nuclearmente robustos** são: déficit hídrico e temperatura
   média na soja, temperatura média e ET0 no milho.
3. O **bootstrap wild de cluster** da execução anterior tinha **dois**
   defeitos reais: sorteava **um peso por observação** em vez de **um por
   grupo** (D80) e aceitava réplicas com erro-padrão numericamente nulo,
   que entravam na cauda como excedência espúria (D85). Corrigido,
   recalibrado e com o DGP de calibração consertado.
4. A **janela fenológica** de enchimento de grãos (requisitos térmicos
   publicados) confirma a soja e **revela** duas relações no milho que a
   janela de plantio não mostrava.
5. A **CAD oficial** (Embrapa Solos, Vasques et al., 2021) é 2 a 3 vezes
   maior que os cenários de 35/50/70 mm usados na V2.6.
6. A **validação territorial** reproduz a faixa da V2.6 (+1,35% a +6,36%)
   em P1–P3, mas o teste mais estrito — removendo **o bloco espacial e o
   ano** ao mesmo tempo (P5, D86) — mostra que o ganho:
   * **não sobrevive na soja** (−3,30% em P5, contra +2,76% em P3);
   * **sobrevive parcialmente no milho** (+1,21% no bloco meteorológico,
     **+5,40%** no hídrico);
   * **sobrevive no milho 2ª safra** (+16,92%, praticamente igual a P3).

   O ganho territorial aparente da V2.6 era, em parte, **efeito do ano
   compartilhado** entre treino e teste — e o resultado por cultura é
   heterogêneo.

---

## 2. Estado recuperado da execução anterior

| Item | Estado encontrado |
|---|---|
| Branch | `v2/agroclimatic-robustness` em `d87addb` (V2.6), **sem commits da V2.7** |
| Código | `robust.py`, `spatial.py`, `spatial_inference.py`, `run_robustness.py` novos; `analysis.py` e `panel.py` modificados |
| Checkpoints | apenas `MASTER_STATUS.md` e `EXECUTION_LOG.md` (complementados nesta sessão) |
| Manifests | `v27_robust_inference.json` (138,6 KB), `.csv`, `v27_cluster_diagnostics.json` |
| Scripts | `tmp/v27_check_grid.py`, `v27_check_series.py`, `v27_check_dependence.py`, `v27_check_dependence2.py`, `v27_smoke.py`, `v27_validate_wcb.py` + caches `.npy` |
| Pendente | `run_robustness.py spatial` (protocolos P1–P4) **nunca executado** |

**Defeito de ambiente**: o agente anterior usava o Python do sistema. O
interpretador correto é `geospatial\.venv\Scripts\python.exe` (3.12.10).
`scipy` está ausente e **não é necessário** (toda a estatística é NumPy
puro); `requirements.txt` não foi alterado.

---

## 3. Arquivos e módulos

### 3.1 Módulos novos (`geospatial/agroclimate/`)

| Módulo | Papel |
|---|---|
| `robust.py` | distribuições próprias (t e normal), `cluster_vcov` (CR1/CR2), `two_way_cluster_vcov`, `conley_vcov`, `wild_cluster_bootstrap` (+ forma vetorizada), `holm_adjust` |
| `spatial.py` | célula MERRA-2, associação município–célula, blocos espaciais, correlograma, divisões por grupo, relatório de vazamento |
| `spatial_inference.py` | transformação *within*, equivalência com LSDV, inferência agrupada, Conley e bootstrap wild sobre o estimador *within* |
| `phenology.py` | perfis fenológicos publicados e janelas de enchimento de grãos (datas aproximadas por soma térmica real) |
| `soil.py` | integração da água disponível do solo (mm/cm → mm) e comparação com os cenários da V2.6 |

### 3.2 Módulos modificados

| Arquivo | Mudança |
|---|---|
| `agroclimate/analysis.py` | exposição de `_build_fixed_effects_design` e generalização de `territorial_holdout(group_key=...)`; **resultado da V2.6 preservado bit a bit** |
| `agroclimate/panel.py` | extração de `build_climate_indicators` (reuso no experimento fenológico) e **correção da recursão infinita** introduzida no refactor |

### 3.3 Scripts (`tools/`)

`calibrate_wild_bootstrap.py` · `validate_v27_stats.py` · `s27_wcs_probe.py` ·
`s27_cad_metadata.py` · `s27_cad_sample.py` · `s27_phenology_window.py`

---

## 4. Reproduções realizadas

| Item | Resultado |
|---|---|
| 12 efeitos fixos da V2.6 | **bit a bit** — ex.: soja `deficiency_total_mm` = −1,260169893887058 (n = 8.884) |
| Equivalência *within* ↔ LSDV | diferença 3,1e-13 a 4,9e-11 (3 culturas × 2 variáveis, painel real) |
| Coerência `cluster_robust_fit` ↔ `cluster_vcov` | EP idêntico (0,079558428704) |
| Distribuições contra tabela | `t_critical` dif. máx. 5,0e-10; `normal_cdf` exato a 1e-12 |
| Holm | monotonia, p ajustado ≥ p bruto, ≤ 1 |
| Conley (150/250/400/600 km) | EP finito e positivo em todos os cortes |
| Determinismo | duas execuções idênticas |
| Forma vetorizada vs forma em laço | p-valor e dispersão bootstrap **idênticos** |

---

## 5. Resultado da inferência agrupada

Família de **21 hipóteses** (3 culturas × 7 variáveis), correção de **Holm**
(FWER) por esquema:

| Esquema | grupos | sobreviventes (Holm) |
|---|---|---|
| município | 1.225 | 13 |
| célula MERRA-2 | 383 | 12 |
| **bloco espacial 250 km** | **46** | **4** |
| UF | 5–6 | 0 |

Sobrevivem em **todos** os esquemas não degenerados:
`soja|deficiency_total_mm`, `soja|temp_media_c`, `milho|temp_media_c`,
`milho|et0_total_mm`. São **sensíveis** ao esquema: precipitação, dias de
calor extremo, graus-dia e excesso hídrico.

Erro-padrão do déficit hídrico da soja: 0,0723 (município) → 0,1233
(célula) → 0,2404 (bloco 250 km); a |t| cai de 17,4 para 5,2. O intervalo
de confiança **continua excluindo zero** no esquema conservador.

---

## 6. Resultado do Wild Cluster Bootstrap

**Defeito corrigido (D80).** A implementação herdada sorteava
`rng.choice([-1,1], size=len(grupo))` — **um peso por observação** —, o que
não preserva a dependência intracluster. A versão correta usa **um peso por
grupo e por replicação** (CGM, 2008). Efeito medido na calibração com 5
grupos: poder de **53,5%** (correto) contra **91,3%** (variante herdada) sob
efeito verdadeiro — a variante anterior **não** corrigia o problema de
poucos grupos, apenas parecia mais potente porque subestima a variância.

**Calibração (D79).** Dois DGP, 3 sementes, 999 réplicas por bootstrap,
taxas em 1%/5%/10% com incerteza de Monte Carlo explícita. Tamanho
empírico ao nível nominal de 5%:

| DGP | grupos | tamanho (pesos por grupo) | tamanho (pesos por obs.) |
|---|---|---|---|
| agrupado | 5 | 0,043 / 0,052 / 0,047 | 0,057 / 0,052 / 0,058 |
| agrupado | 10 | 0,051–0,061 | 0,052–0,063 |
| agrupado | 25 | 0,045–0,058 | 0,048–0,059 |
| agrupado | 50 | 0,046–0,057 | 0,046–0,058 |
| agrupado | 100 | 0,047–0,063 | 0,045–0,063 |
| agrupado | 200 | 0,039–0,047 | 0,042–0,054 |
| painel_fe | 10 | 0,051 / 0,066 / 0,068 | 0,048 / 0,072 / 0,077 |
| painel_fe | 25 | 0,051 / 0,062 / 0,068 | 0,050 / 0,062 / 0,066 |
| painel_fe | 46 | 0,048–0,058 | 0,049–0,056 |
| painel_fe | 100 | 0,051–0,056 | 0,050–0,056 |

Leitura: para G ≥ 10 o tamanho é compatível com o nominal dentro da
incerteza Monte Carlo (com 800–2.000 simulações, ±1,0–1,5 p.p. ao nível de
5%). Com **5 grupos** o procedimento é **levemente conservador**
(0,043–0,052) e o **poder cai para ~53%**, contra ~94% do teste t
assintótico — o custo de exigir validade com poucos grupos. O `painel_fe`
com 10 municípios e erro AR(1) é o caso mais difícil: o bootstrap reduz,
mas **não elimina**, a sobre-rejeição (0,051–0,071 contra nominal 0,05).

**Achado da auditoria (D85).** A grade anterior estava contaminada por
réplicas com erro-padrão numericamente nulo (`|t| ≈ 1e18`, contadas como
excedência) e por um DGP com coluna estruturalmente nula no design. As duas
falhas foram corrigidas e a grade foi **recalculada por inteiro**. O efeito
é restrito a G = 5: tamanho 0,037 → 0,047 e poder 0,468 → 0,535; nos demais
casos a diferença é ≤ 0,007 (ruído Monte Carlo), e os 9 diagnósticos
degenerados (`t_boot_sd ≈ 8,5e14`) desapareceram. A conclusão qualitativa
— pesos por grupo preservam a validade sob dependência e custam poder com
poucos grupos — **não** mudou; o que mudou é que o procedimento não é tão
conservador quanto a primeira grade sugeria.

**Transparência (D81).** O bootstrap é reportado nos dois ramos (nulidade
imposta e irrestrita) com a política declarada, porque a convenção de
troca de Cameron, Gelbach & Miller não pôde ser verificada no artigo
primário neste ambiente.

**Famílias com o bootstrap wild:** município 13 · célula 12 · bloco 250 km
**6** · UF 3. O bootstrap é **menos conservador** que o teste t assintótico
com o mesmo número de grupos (6 vs 4 com 46 grupos) e muito mais
informativo que o esquema por UF.

---

## 7. Resultado do Conley HAC

| Corte | EP (soja, déficit hídrico) | sobreviventes (Holm) |
|---|---|---|
| 150 km | 0,2152 | 10 |
| 250 km | 0,2609 | 8 |
| 400 km | 0,2726 | 8 |
| 600 km | 0,2559 | 8 |

O Conley **não** sofre do problema de poucos grupos e confirma o padrão
do agrupamento: entre 8 e 10 hipóteses sobrevivem. O corte de 150 km é o
mais permissivo; 250–600 km convergem.

---

## 8. Dependência espacial empírica

* NASA POWER **interpola**: a taxa de pares de municípios da mesma célula
  nominal com séries diárias idênticas é 0,0% (soja e milho) e 0,17%
  (milho 2ª safra); a diferença média de temperatura é de 0,32 a 1,90 °C.
  Portanto a célula nominal **não** representa observações iguais — a
  simplificação da V2.6 estava errada.
* Correlograma reproduzível por `run_robustness.py dependence`
  (**1.296 municípios**, 3.653 dias, 2016-01-01 a 2025-12-31), manifesto
  versionado `v27_spatial_dependence.json` / `.csv`:

| Banda (km) | 0–25 | 50–75 | 100–125 | 200–225 | 300–325 | 400–425 |
|---|---|---|---|---|---|---|
| Temperatura (anomalia anual) | 0,9939 | 0,9801 | 0,9618 | 0,9238 | 0,8810 | 0,8339 |
| Precipitação (anomalia anual) | 0,9816 | 0,9371 | 0,8713 | 0,7492 | 0,6791 | 0,6295 |
| Temperatura (anomalia diária) | 0,9940 | 0,9789 | 0,9552 | 0,8999 | 0,8350 | 0,7534 |
| Precipitação (anomalia diária) | 0,9760 | 0,9128 | 0,8138 | 0,6094 | 0,4480 | 0,3152 |

* A correlação **não** cai abaixo de 0,10 em nenhum campo até 600 km
  (`distance_below_0.10_km` nulo nos quatro campos): não há distância de
  corte em que a dependência possa ser ignorada dentro da área do painel.
  É essa constatação que justifica o bloco de 250 km como unidade de
  agrupamento, e não um valor arbitrário.
* As correlações **diárias brutas** não foram usadas como prova: o ciclo
  climático compartilhado as infla. A dependência relevante é a das
  **anomalias** (retirado o climatolo diário de cada município), e a
  divergência entre a linha diária e a anual é justamente o que mostra
  quanto do sinal diário é ciclo sazonal comum.
* **Correção de rastreabilidade:** a versão anterior desta seção trazia
  uma tabela (0,9965 / 0,8568 / 0,3591 etc.) produzida por um script de
  sondagem em `tmp/`, sem manifesto. Aqueles números **não eram
  reproduzíveis pelo comando versionado** e foram substituídos pelos do
  manifesto acima, que é agora a fonte da verdade. Os valores anuais aqui
  coincidem com os já citados em `MASTER_STATUS.md` (0,834 e 0,630 na
  banda 400–425 km).

---

## 9. Validação espacial (protocolos P1–P5)

> Resultado em `v27_spatial_validation.json` / `.csv`; comando
> `run_robustness.py spatial --block-km 250`.

Cinco protocolos, todos com a **mesma** linha de base (média do conjunto de
treino) e a **mesma** amostra de teste (a amostra completa da cultura); o
que muda é apenas a informação removida do treino. Isso torna a sequência
comparável: o ganho medido é sempre relativo à mesma referência, sob
informação decrescente.

| Protocolo | retirado do treino | soja (B) | milho (B) | milho 2ª (B) |
|---|---|---|---|---|
| P1 município (V2.6) | o município | +3,98% | +1,62% | +14,60% |
| P2 célula MERRA-2 | a célula | +3,99% | +1,47% | +14,22% |
| P3 bloco 250 km | o bloco espacial | +2,76% | +1,35% | +16,97% |
| P4 leave-one-UF-out | a UF inteira | **−1,75%** | **−3,38%** | não estimável |
| **P5 bloco × ano** | **o bloco e o ano** | **−3,30%** | **+1,21%** | **+16,92%** |

Ganho = `(MAE_média_histórica − MAE_modelo) / MAE_média_histórica`; positivo
significa que o modelo climático superou a média. `B` = bloco
meteorológico (`precip_acumulada_mm`, `temp_media_c`). Os blocos `C`
(térmico) e `D` (hídrico) estão no manifesto; o essencial:

| Cultura | P3 (bloco) B / C / D | P5 (bloco × ano) B / C / D |
|---|---|---|
| soja | +2,76 / +1,49 / +0,85 | −3,30 / −1,42 / −5,30 |
| milho | +1,35 / +5,20 / +6,30 | +1,21 / +4,33 / **+5,40** |
| milho 2ª safra | +16,97 / +13,30 / +11,16 | +16,92 / +11,98 / +10,26 |

**Leitura por cultura.**

* **Soja — não robusto.** O ganho cresce em P1/P2 (+4,0%), cai em P3
  (+2,8%), inverte em P4 (−1,8%) e permanece negativo em P5 (−3,3%). O
  ganho territorial aparente da V2.6 **não sobrevive** quando o ano deixa
  de ser compartilhado entre treino e teste. Como o mesmo encolhimento
  monotônico aparece ao remover informação espacial, a explicação mais
  parcimoniosa é que o modelo capturava estrutura regional **e** o choque
  do ano, não uma relação climática transferível.
* **Milho — parcialmente robusto, e dependente da família.** O bloco
  meteorológico mantém apenas +1,2% em P5, mas o bloco **hídrico** mantém
  **+5,4%** e o térmico +4,3%. O sinal de déficit hídrico é o que resiste
  ao protocolo mais estrito; a leitura de "ganho modesto" da V2.6 se
  sustenta apenas para as variáveis de água.
* **Milho 2ª safra — robusto no protocolo mais estrito.** +16,9% em P5,
  praticamente igual a P3. Duas ressalvas: (i) a linha de base agregada é
  particularmente fraca para a 2ª safra (MAE 1.466 kg/ha), de modo que
  parte do ganho reflete heterogeneidade regional que a média agregada não
  captura; (ii) P4 não é estimável (apenas 4 UFs para 5 dobras), e o
  esquema por UF é degenerado.

**Reprodução da V2.6.** Em P1–P3 o ganho fica entre **+1,35% e +6,36%**,
dentro da faixa de 1,7%–6,3% que a V2.6 reportou. Ou seja: o resultado
original **reproduz**, e o que a V2.7 acrescenta é o teste que ele não
fazia — a remoção do ano compartilhado e a separação por UF.

**Ressalva sobre o rótulo `media_historica`.** Nos protocolos territoriais
a linha de base é a **média do conjunto de treino** (agregada), porque o
município de teste é, por construção, não visto. Na validação temporal
(`walk_forward`) a mesma chave é a média do **próprio município** em anos
anteriores. São duas linhas de base diferentes com o mesmo nome: os MAEs
territoriais (≈621 para a soja) e o temporal da V2.6 (≈487) **não são
comparáveis**, e a diferença não é contradição.

**Integridade.** Os valores de P1–P4 são **idênticos bit a bit** aos da
execução anterior (132 valores de MAE conferidos, 0 diferenças), o que
confirma que as correções de D85 não tocaram os protocolos territoriais;
P5 é a única adição.

---

## 10. Resultado fenológico

| Item | Soja | Milho |
|---|---|---|
| Perfil | R1 = 92,5 °C·dia; R5 = 554 °C·dia (Tb = 10 °C) | 780/860/1.050 °C·dia até a polinização (Tb = 10 °C, Tmax ≤ 30 °C, Tmin ≥ 10 °C) |
| Janela | R5 → R5 + 45 dias | VT + 22,5 d (R3) → VT + 55 d (R6) |
| Duração | 46 dias (ZARC: 61) | 33 dias (ZARC: 61) |
| Amostra | 519 linhas, 71 municípios, 8 anos | 508 linhas, 73 municípios, 8 anos |
| Datas distintas | 260 (o estágio varia com o clima do ano) | 305 |

Efeitos fixos reestimados nas duas janelas (mesmo construtor de
indicadores):

| Hipótese | Coef. ZARC → fenológica | EP ZARC → fenológica | Significância |
|---|---|---|---|
| soja\|precip_acumulada_mm | 0,491 → 1,314 | 0,169 → 0,279 | sim → sim |
| soja\|temp_media_c | −125,97 → −53,05 | 32,99 → 26,18 | sim → sim |
| soja\|deficiency_total_mm | −0,879 → −3,076 | 0,312 → 0,561 | sim → sim |
| soja\|et0_total_mm | −0,185 → −3,961 | 0,280 → 0,822 | não → sim |
| soja\|excess_total_mm | 0,478 → 1,043 | 0,239 → 0,284 | sim → sim |
| milho\|precip_acumulada_mm | 0,074 → 1,749 | 0,444 → 0,694 | não → sim |
| milho\|temp_media_c | −72,09 → −303,15 | 56,00 → 83,31 | não → sim |
| milho\|deficiency_total_mm | −1,809 → −7,262 | 0,706 → 2,316 | sim → sim |
| milho\|et0_total_mm | −2,807 → −14,557 | 0,832 → 3,532 | sim → sim |
| milho\|excess_total_mm | 0,044 → 1,381 | 0,576 → 0,635 | não → sim |

> Os coeficientes **não** são comparáveis entre janelas (a exposição muda:
> 46/33 dias contra 61); o que se compara é **direção e significância**.
> A direção dos sinais é **preservada** em todos os casos — nenhum sinal
> se inverte —, o que é um teste de coerência interna do experimento.

O milho 2ª safra permanece na janela do ZARC: **não há** estágio
intermediário publicado com precisão suficiente (ausência preservada).

---

## 11. Resultado da CAD

| Item | Valor |
|---|---|
| Fonte | Embrapa Solos / GeoInfo — Vasques, G.M., Dart, R.O., Cintra, L.C. & Baca, J.F.M. (2021) |
| Camadas | 6 profundidades (0–5, 5–15, 15–30, 30–60, 60–100, 100–200 cm) a ~90 m |
| Unidade | **mm/cm** (mm de água por cm de solo) → CAD (mm) = Σ AW × espessura |
| Resolução do serviço | 0,000833° (≈92 m), EPSG:4326 |
| No-data | −9999 (preservado como ausência) |
| Licença | **CC BY-NC 3.0 BR** (uso não-comercial) |
| Cobertura da amostra | 10/10 municípios com as 6 camadas válidas (100%) |
| CAD 0–100 cm | 126,0 – 239,9 mm (mediana **158,9**, média 168,2) |
| Comparação com a V2.6 | **10/10** acima de 35, de 50 e de 70 mm |

Conclusão: os cenários de CAD da V2.6 são **conservadores** frente ao dado
oficial — aproximadamente 2 a 3 vezes menores que a água disponível real
do perfil. Isto **não** invalida a V2.6 (que era um cenário conservador
declarado), mas indica que o balanço hídrico da V2.6 **subestima** a
reserva hídrica do solo.

> Ressalva de metadado: o `DescribeCoverage` declara a unidade do campo
> como `GRAY_INDEX` (modelo genérico do GeoServer). A unidade autoritativa
> é a do **título oficial e da citação** (mm/cm) — o metadado do serviço
> não é confiável nesse campo.

---

## 12. Resultado do ERA5-Land

**Bloqueado.** O acesso nativo ao CDS exige `CDS_API_KEY` ou `~/.cdsapirc`
com o pacote `cdsapi` — **nenhum** dos três existe neste ambiente. Não foi
criada conta, não foi solicitada credencial por chat e nenhum segredo foi
gravado. NASA POWER permanece como base reanalisada e INMET como
observação independente. CHIRPS e ARCO seguem sem resolução DNS e não
foram repetidos. A ausência é **documentada como bloqueio**, não como
falha de execução.

---

## 13. Decisão sobre a expansão do painel

**Não recomendada agora** (decisão de escopo, não de viabilidade).

Justificativa:

1. a robustez estatística é a pendência científica aberta da V2.6, e ela
   **mudou** a leitura dos resultados (13 → 4 hipóteses sob o esquema
   conservador); ampliar o painel antes de fixar o método estatístico
   amplificaria a mesma ambiguidade;
2. o painel atual já cobre 1.622 municípios elegíveis em 5 UFs e 8 anos;
3. qualquer ampliação exige o **diagnóstico de cobertura** completo
   (D69: produção observada, área positiva, geometria oficial, cobertura
   meteorológica, compatibilidade ZARC, estações INMET, calendário e
   qualidade) e **preservação da comparabilidade** — a PAM não pode ser
   desagregada;
4. a V2.7 já entrega dois insumos que a expansão exigiria de qualquer
   forma: a **CAD territorial oficial** (substituindo os cenários) e a
   **janela fenológica** (substituindo a janela de plantio como
   exposição).

---

## 14. Comparação V2.6 × V2.7

| # | Pergunta | Resposta da V2.7 |
|---|---|---|
| 1 | Os 12 efeitos fixos continuam reproduzíveis? | **Sim**, bit a bit (n, municípios e anos idênticos) |
| 2 | A inferência agrupada altera a significância? | **Sim**: 13 → 4 hipóteses com o agrupamento conservador de 250 km |
| 3 | O Wild Bootstrap está calibrado? | **Sim** para ≥ 10 grupos (tamanho ≈ nominal); levemente conservador com 5 (tamanho 0,047, poder 53%); e a **implementação tinha dois defeitos reais**, corrigidos (D80, D85) |
| 4 | O Conley HAC modifica os intervalos? | **Sim**: o EP do déficit hídrico da soja sai de 0,0723 (município) para 0,215–0,273 (150–600 km); 8–10 hipóteses sobrevivem |
| 5 | A dependência espacial vai além de 55 km? | **Sim**: r(T) = 0,834 e r(P) = 0,630 a 400–425 km (anomalias anuais, manifesto reproduzível) |
| 6 | A separação por blocos altera os resultados territoriais? | **Sim**: o ganho cai de +4,0% (município) para +2,8% (bloco 250 km) na soja |
| 7 | O ganho territorial de 1,7% a 6,3% permanece? | **Reproduz em P1–P3** (+1,35% a +6,36%), mas **não sobrevive a P5** na soja; sobrevive no milho (hídrico +5,40%) e no milho 2ª safra (+16,92%) — seção 9 |
| 8 | A validação temporal continua desfavorável? | **Sim** — nenhum protocolo temporal é misturado com os territoriais |
| 9 | O refinamento fenológico melhora a representação? | **Sim**: mantém a soja e revela precipitação e temperatura no milho; nenhuma direção se inverte |
| 10 | A CAD geoespacial é viável? | **Sim**: 6 camadas oficiais a 90 m, licença livre (não-comercial), conversão documentada; os cenários da V2.6 são ~2–3× conservadores |
| 11 | O ERA5-Land foi acessível? | **Não** — bloqueio por credencial ausente (D83) |
| 12 | A expansão do painel é recomendável? | **Não agora** — ver seção 13 |

---

## 15. Limitações

1. **Associação, não causalidade.** O modelo é observacional; o
   confundimento por manejo, tecnologia e mercado permanece.
2. **CULTivar desconhecida.** Os perfis fenológicos são **cenários** por
   grupo de maturação; a PAM não identifica cultivar.
3. **Duração do enchimento da soja** é cenário (45 dias), não valor
   publicado único; a sensibilidade está declarada.
4. **Janela fenológica** é um **experimento** sobre a janela do ZARC; o
   protocolo principal permanece o ZARC.
5. **Amostra de CAD** é pequena (10 municípios) e usa a mediana de uma
   janela de 0,2° em torno do centroide — não é um valor municipal
   oficial. Não há valor de AW por município na fonte.
6. **Dependência residual.** Mesmo agrupando por blocos de 250 km, a
   correlação das anomalias anuais ainda é ~0,83 a 425 km; pode haver
   dependência além do escala considerada.
7. **Escala do painel**: 5 UFs e 8 anos limitam a generalização
   territorial; o esquema por UF é degenerado (5–6 grupos) e **não** é
   informativo.
8. **Convenção de nulidade do CGM** não verificável neste ambiente
   (D81) — reportadas as duas variantes.
9. **Metadado do WCS** declara unidade de campo incorreta (GRAY_INDEX).
10. **Poucos grupos no esquema por UF** (5–6): o teste t e o bootstrap por
    UF são degenerados ou instáveis. Com 10 grupos no `painel_fe` o
    bootstrap ainda sobre-rejeita (até 0,071 ao nominal de 0,05); nesse
    regime nenhum dos dois métodos é confiável, e o resultado deve ser
    lido como **não conclusivo**, não como "sem efeito".
11. **O ano é compartilhado entre treino e teste em P1–P4.** Os quatro
    protocolos territoriais separam apenas o espaço; por isso foi
    acrescentado P5 (D86), que remove blocos **e** anos. A comparação
    P3 × P5 é o que separa ganho territorial genuíno de ganho atribuível
    ao choque do ano, e é a leitura que deve prevalecer.
12. **Sobreposição temporal no diagnóstico de dependência**: o
    correlograma usa todas as 1.296 células com dados, não apenas os
    1.225 municípios do painel de soja; a diferença é de 6% e não altera
    a ordem de grandeza.

---

## 16. Testes efetivamente executados

| Suíte | Comando | Resultado |
|---|---|---|
| Offline | `python -m pytest geospatial/tests -q` | **318/318 OK** (262 da V2.6 + 56 da V2.7) |
| Externos opt-in | `SADEN_EXTERNAL_TESTS=1 python -m unittest discover -s geospatial/tests_external -t geospatial` | **10/10 OK** |

Cobertura da suíte nova: distribuições · within↔LSDV · cluster-robust
(CR1, coerência, determinismo, dois sentidos) · Conley (positividade,
monotonicidade do corte, pesos do kernel) · bootstrap wild (pesos por
grupo, pesos novos por replicação, equivalência vetorizado/laço, nulidade
imposta e irrestrita, políticas) · Holm · divisões espaciais e
**ausência de vazamento** · fenologia (perfis, ThermalProfile coincidente,
datas, ausência) · CAD (espessuras, integração, unidades, no-data,
perfil incompleto, comparação) · dados ausentes · deduplicação do painel ·
persistência/retomada · **compatibilidade com a V2.6** (coeficiente de
referência −1,260169893887058).

---

## 17. Arquivos criados

`geospatial/agroclimate/{robust,spatial,spatial_inference,phenology,soil}.py` ·
`geospatial/run_robustness.py` · `geospatial/tests/test_v27_robustness.py` ·
`tools/{calibrate_wild_bootstrap,validate_v27_stats,s27_wcs_probe,s27_cad_metadata,s27_cad_sample,s27_phenology_window}.py` ·
`docs/execution/v2.7/{MASTER_STATUS,EXECUTION_LOG,NEXT_ACTIONS,EVIDENCE_MATRIX,DATA_MANIFEST,DECISIONS_V2_7,RECOVERY}.md` ·
12 manifests `geospatial/data/manifests/v27_*`.

## 18. Arquivos modificados

`geospatial/agroclimate/analysis.py` · `geospatial/agroclimate/panel.py` ·
`geospatial/run_robustness.py` · `geospatial/.gitignore` ·
`docs/DECISIONS.md` · `docs/PROJECT_STATUS.md` · `docs/PROJECT_ROADMAP.md` ·
`docs/API_SOURCES.md` · `docs/CONTEXTO_V2.md` · `docs/AI_CONTEXT_RECOVERY.md` ·
`geospatial/README.md`.

## 19. Decisões D76 em diante

D76 dependência espacial além da grade · D77 esquemas pré-declarados e Holm ·
D78 janela fenológica como experimento · D79 calibração Monte Carlo ·
D80 pesos por grupo (CGM) · D81 política de nulidade explícita · D82 CAD
territorial oficial · D83 ERA5-Land bloqueado · D84 artefatos grandes fora
do Git.

> Detalhes completos em `docs/execution/v2.7/DECISIONS_V2_7.md`.

---

## 20. Branch e SHA final

| Item | Valor |
|---|---|
| Branch | `v2/agroclimatic-robustness` |
| Base | `d87addb` (V2.6) |
| Commits da V2.7 | ver seção de publicação ao final |

## 21. Bundle e hash

| Item | Valor |
|---|---|
| Diretório | `C:\Users\luanf\OneDrive\Área de Trabalho\SADEN_V2_7_RECOVERY_2026-11-14` |
| Bundle | `saden-v2-7-final-2026-11-14.bundle` |
| Tamanho / SHA-256 / `git bundle verify` | ver seção de publicação ao final |

## 22. Estado da publicação remota

Ver seção de publicação ao final.

## 23. Recomendação para a V2.8

1. **Fixar o método estatístico** (bloco de 250 km + Conley + bootstrap wild
   com pesos por grupo) como protocolo único e repetir a inferência sobre
   qualquer expansão.
2. **Substituir os cenários de CAD** pela CAD geoespacial oficial, com o
   balanço hídrico recalculado e a comparação preservada.
3. **Estratificar a fenologia por grupo de maturação** derivado do ZARC
   (o ZARC já codifica o ciclo por decend), eliminando o cenário único.
4. **Ampliar o painel** apenas após o diagnóstico de cobertura completo.
5. **Modelar a dependência além de 250 km** (correlograma estendido,
   formas de variograma) se a escala de decisão for maior que 250 km.
6. Manter a **Ridge Regression** como único modelo de preços: a V2.7 não
   toca na previsão de preços.
