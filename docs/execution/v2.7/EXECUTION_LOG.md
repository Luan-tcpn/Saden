# SADEN V2.7 — Log de execução

> Registro cronológico resumido. Apenas marcos e decisões relevantes.

## 2026-11-13

### 00:47 — Início da missão

Localização do repositório em
`C:\Users\luanf\OneDrive\Área de Trabalho\Saden_AgroClima` (o diretório de
trabalho do MCode já apontava para ele). Declaradas fora de escopo:
`SADEN-TCC` (acadêmico) e os diretórios de recuperação das versões
anteriores (somente leitura).

### 00:55 — Fase 0: integridade do ambiente

* `git status`: branch `v2/agroclimatic-productivity-panel` limpa e igual ao
  remoto; HEAD = `d87addb`.
* Bundle da V2.6: 14.757.015 bytes, SHA-256
  `B2D3CA8A…F81B294914C`, `git bundle verify` → **is okay** (21 refs,
  histórico completo).
* `main` = `3f7ad33` e `v1-final` = `e62a537`, ambos idênticos ao remoto.
* `pytest` não existia no `geospatial/.venv`; instalado localmente
  (pytest 9.2.0). `requirements.txt` **inalterado** — a V2.7 não adiciona
  dependências.
* **Baseline: 262/262 testes offline aprovados** (3,33 s).

### 01:00 — Fase 1: auditoria científica

Leitura dos quatro relatórios da V2.6, dos manifests
(`agroclimatic_analysis.json`, `agroclimatic_panel.json`,
`agroclimatic_analysis_inmet.json`, `panel_eligibility.json`) e das decisões
D66–D75 em `docs/DECISIONS.md`.

Reconstrução do encadeamento: seleção (D69) → janela ZARC (`agri/season.py`,
D73) → agregaçãoclimate (`agroclimate/panel.py`) → inferência
(`agroclimate/analysis.py`).

### 01:10 — Branch da V2.7 criada

`v2/agroclimatic-robustness` a partir de `d87addb`. `main` e `v1-final`
inalteradas.

### 01:15 — Módulos novos

* `geospatial/agroclimate/spatial.py` — unidade de agrupamento espacial,
  células MERRA-2, partilha empírica de valores, blocos espaciais, coloração
  de dobras com separação espacial, correlograma, verificação de vazamento.
* `geospatial/agroclimate/robust.py` — erro-padrão agrupado (CR1/CR2),
  bootstrap wild de cluster (Cameron–Gelbach–Miller, 2008), estimador
  espacial de Conley (1999), agrupamento em duas direções, e as funções de
  distribuição t/normal implementadas **sem dependência externa** (beta
  incompleta regularizada).
* `geospatial/agroclimate/spatial_inference.py` — transformação *within*,
  equivalência com a LSDV, inferência agrupada multi-esquema, Conley sobre
  *within*, bootstrap wild.
* `geospatial/run_robustness.py` — CLI da V2.7 (`dependence`, `diagnose`,
  `infer`, `spatial`, `all`).

### 01:20 — Validação das funções de distribuição

`t_sf` e `t_ppf` conferidas contra valores tabelados: t(1) = 12,706205;
t(10) = 2,228139; t(30) = 2,042272 (5%) e 2,749996 (1%); normal a 5% =
1,959964. Erro < 1e-6 em todos os casos.

### 01:25 — Refatoração de `analysis.py`

`_build_fixed_effects_design` extraído de `fixed_effects` (design de
efeitos fixos de município e ano) e `territorial_holdout` generalizado com
`group_key` (padrão `ibge_code` preserva o resultado da V2.6 **bit a bit**).
Nenhuma duplicação de implementação criada.

### 01:35 — Reprodução da V2.6

**12/12** coeficientes de efeitos fixos reproduzidos com diferença
absoluta < 1e-8 (coeficiente) e < 1e-6 (t) frente ao manifest da V2.6.

Descoberta operacional: a análise da V2.6 usou **somente** as linhas de
reanálise (NASA POWER); as linhas do INMET são um subconjunto separado
(2.020 observações utilizáveis, 157 municípios).

### 01:50 — REFUTAÇÃO DA LIMITAÇÃO "55 km"

Comparação direta das séries diárias reais (`climate_daily.csv`, a base que
gerou o painel) para municípios de uma mesma célula MERRA-2:

| Célula | Par | Dias comuns | Dias idênticos | \|ΔT\| médio |
|---|---|---:|---:|---:|
| M153_P221 | 2900108 × 2912202 | 3.653 | 0 (0,0%) | 0,80 °C |
| M153_P221 | 2900108 × 2921906 | 3.653 | 0 (0,0%) | 0,73 °C |
| M156_P227 | 2900306 × 2908606 | 3.653 | 0 (0,0%) | 1,28 °C |
| M156_P226 | 2900405 × 2901908 | 3.653 | 0 (0,0%) | 0,36 °C |
| M153_P220 | 2900504 × 2907558 | 3.653 | 0 (0,0%) | 1,90 °C |

**Conclusão:** o NASA POWER **interpola** a grade no ponto solicitado. A
afirmação da V2.6 de que "dois municípios a 30 km recebem valores climáticos
quase idênticos" é **factualmente incorreta** para a base efetivamente
usada. A célula da grade não é uma unidade de partilha de valores.

### 02:10 — MEDIÇÃO DA DEPENDÊNCIA ESPACIAL REAL

Correlograma empírico sobre 1.296 municípios do painel e 3.653 dias.
Mede-se sobre **anomalias** (retirado o climatolo diário de cada município),
porque a correlação de séries cruas é dominada pelo ciclo sazonal
compartilhado.

| Distância | Anomalia diária T | Anomalia diária P | Anomalia anual T | Anomalia anual P |
|---|---:|---:|---:|---:|
| 0–25 km | 0,9965 | 0,9773 | 0,9939 | 0,9816 |
| 50–75 km | 0,9876 | 0,9195 | 0,9801 | 0,9371 |
| 100–125 km | 0,9737 | 0,8307 | 0,9618 | 0,8713 |
| 200–225 km | 0,9417 | 0,6479 | 0,9238 | 0,7492 |
| 300–325 km | 0,9032 | 0,4911 | 0,8810 | 0,6791 |
| 400–425 km | 0,8568 | 0,3591 | 0,8339 | 0,6295 |

**Conclusão:** a dependência espacial dos regressores do painel é de
**centenas de quilômetros**. A célula MERRA-2 (~55 km) é **fina demais**
para controlá-la; agrupar por célula subestima a dependência e produz
erro-padrão otimista. A escala correta de inferência foi calibrada a
partir deste correlograma.

### 02:30 — Estrutura dos grupos (soja)

| Esquema | Grupos | Obs./grupo (média) | Maior grupo | Singletons |
|---|---:|---:|---:|---:|
| município (V2.6) | 1.225 | 7,3 | 8 | 43 |
| célula MERRA-2 | 383 | 23,2 | 144 | 9 |
| bloco espacial 250 km | 46 | 193,1 | 1.289 | 0 |
| UF | 5 | 1.776,8 | 2.966 | 0 |

Taxa de identidade de valores dentro da célula: **0,00%** (soja),
0,00% (milho), 0,17% (milho 2ª).

### 02:40 — Fase 6 (ERA5-Land nativo): bloqueio confirmado

Sem `CDS_API_KEY`, `CDSAPI_KEY`, `CDS_KEY`, `ECMWF_API_KEY`, `CDSAPI_URL`,
`CDSAPI_RETRIES` (processo, usuário e máquina), sem `~/.cdsapirc` e sem o
pacote `cdsapi`. Nenhuma credencial solicitada ou criada.

### 03:00 — Fase 4: pesquisa fenológica (Embrapa)

Fontes localizadas e lidas:

* **Soja** — Embrapa Soja / Sistemas de Produção 17: escala de Fehr &
  Caviness (1977); R1 início do florescimento, R2 pleno florescimento,
  R3 início da formação das vagens, R4 vagens desenvolvidas, **R5 início do
  enchimento de grãos**, R6 grãos cheios, R7 maturação fisiológica, R8
  maturação plena; sub-estádios R5.1–R5.5 de Ritchie et al. (1977)
  (granação de 10% a 100%); no período reprodutivo (R1–R6) a necessidade
  hídrica ideal é de **120 a 300 mm**; temperatura ótima de 20–30 °C.
  BRS 5980 IPRO (Planaltina–DF, Tb = 14 °C): VC 77,3; V3 187,4; R1 325,0;
  R6 822,0; R8 907,0 °C·dia (9; 21,5; 37,6; 93,8; 103,3 dias).
  Gilmore & Rogers (1958)/Arnold (1960)/Schneider et al. (1987) (Tb = 10 °C):
  R1 = 92,5 °C·dia e R5 = 554 °C·dia (já em D68).
* **Milho** — Embrapa Milho e Sorgo: soma térmica com Tmáx 30 °C, Tmín
  10 °C, Tb 10 °C; normais/tardias 890–1.200 °C·dia, precoces 831–890,
  superprecoces 780–830 (da emergência ao início da polinização); grupos do
  ZARC: I ≤ 780 U.C., II 780–860, III > 860 U.C.; em dias, Grupo I < 110,
  II 110–145, III > 145. Estádios reprodutivos: VT pendoamento, R1
  embonecamento/polinização, R2 grão bolha d'água, R3 grão leitoso (12–15
  dias após a polinização), R4 grão pastoso (20–25), R5 formação de dente
  (~36), R6 maturidade fisiológica (50–60 dias após a polinização).
  Documentos 258 (milho 2ª safra): ciclo total de 120–150 dias e
  2.200–3.300 °C·dia.

### 03:30 — Fase 5: CAD — fonte oficial localizada

**Embrapa Solos / GeoInfo** publica o mapa de **água disponível (AD)** do
Brasil a **90 m**, por intervalo de profundidade, em **mm/cm**:

* `geonode:aw_0_5_def`, `aw_5_15_def`, `aw_15_30_def`, `aw_30_60_def`,
  `aw_60_100_def`, `aw_100_200_def` — WCS 2.0 (`GetCoverage`, GeoTIFF) em
  `geoinfo.dados.embrapa.br/geoserver/ows`. **Acesso verificado** (506
  camadas no `GetCapabilities`).
* Vasques, G.M., Dart, R.O., Cintra, L.C., Baca, J.F.M. (2021). *Soil
  Available Water Maps for Brazil at 0-5, 5-15, 15-30, 30-60, 60-100 and
  100-200 cm Depth Intervals with 90 m Spatial Resolution.* Embrapa Solos.
* Também: mapa nacional de AD em escala 1:250.000 (Araújo Filho et al., 2022,
  BPD 282) e mapa do Mato Grosso do Sul em 1:100.000.

Isso permite substituir os perfis genéricos de CAD por valores **territoriais**
derivados de dado oficial, com método de conversão documentado
(CAD₀₋₃₀ = AD₀₋₅×5 + AD₅₋₁₅×10 + AD₁₅₋₃₀×15).

### 04:00 — Fase 2 em execução

`run_robustness.py infer` rodando: LSDV (linha de base da V2.6), erro-padrão
agrupado por município / célula MERRA-2 / bloco espacial 250 km / UF,
estimador espacial de Conley (cortes 150, 250, 400 e 600 km), bootstrap wild
de cluster (999 iterações, pesos de Rademacher, nulidade imposta) e correção
de Holm sobre a família completa.

---

## 2026-11-14 — Sessão de continuidade (retomada após interrupção)

### 00:45 — Fase 0: auditoria do estado real

* Branch `v2/agroclimatic-robustness` em `d87addb` (V2.6), **sem commits
  da V2.7**; alterações não commitadas preservadas (`analysis.py`,
  `panel.py` modificados; `robust.py`, `spatial.py`,
  `spatial_inference.py`, `run_robustness.py`, `docs/execution/` e
  3 manifests `v27_*` novos).
* Ambiente: o interpretador correto é `geospatial\.venv\Scripts\python.exe`
  (3.12.10). O erro do agente anterior era usar o Python do sistema.
  `scipy` **ausente e desnecessário** (toda a estatística é NumPy puro);
  `requirements.txt` inalterado.
* Suíte: 262/262 offline, 10/10 externos.

### 00:50 — Fase 1: regressão real no `panel.py`

O refactor do painel havia introduzido uma função aninhada `_to_float` que
**sombreava** a do módulo e chamava a si mesma → `RecursionError` em 3
testes. Corrigido usando a função do módulo. Suíte volta a **262/262**.

### 00:55 — Descoberta de defeito no bootstrap wild (D80)

Lendo `robust.py` e `spatial_inference.py`: os pesos de Rademacher eram
sorteados com `rng.choice([-1,1], size=len(grupo))` — ou seja, **um peso
por observação**, apesar de o texto do código afirmar "pesos por grupo".
Isso **não preserva** a dependência intracluster e degenera o bootstrap wild
de cluster no bootstrap wild ordinário. Corrigido para **um peso por grupo
e por replicação** (Cameron, Gelbach & Miller, 2008).

### 01:00 — Vetorização do bootstrap (1000× mais rápido)

`wild_cluster_bootstrap_fast` e `wild_cluster_bootstrap_within_fast`
resolvem todas as réplicas de uma vez (álgebra idêntica). Verificado:
p-valor e dispersão bootstrap **idênticos** à forma em laço (diferença
< 1e-15 nas estatísticas t).

### 01:05 — Calibração do bootstrap wild

`tools/calibrate_wild_bootstrap.py`: dois DGP (erro agrupado; painel
município × ano com efeitos fixos e erro AR(1) intracluster), 3 sementes,
diagnóstico por taxa de rejeição em 1%/5%/10% com incerteza de Monte Carlo.
Resultados preliminares: tamanho próximo do nominal para G ≥ 10;
**conservador com 5 grupos** (poder 46% com pesos por grupo × 88% com
pesos por observação).

### 01:10 — Fase 5: CAD — metadados oficiais confirmados

Sondagem do WCS da Embrapa Solos: 506 camadas; as 6 camadas de água
disponível confirmadas (título, **mm/cm**, 90 m, EPSG:4326, no-data
−9999), citação **Vasques et al. (2021)** e licença **CC BY-NC 3.0 BR**
extraída do registro ISO 19115. Observação registrada: o `DescribeCoverage`
declara a unidade do campo como `GRAY_INDEX` (modelo genérico do
GeoServer) — a unidade autoritativa é a do título/citação.

### 01:20 — Fase 5: amostra geográfica controlada

10 municípios: CAD de 0–100 cm entre **126,0 e 239,9 mm** (mediana
**158,9 mm**); **10/10** acima dos cenários da V2.6 (35/50/70 mm).
Módulo novo `geospatial/agroclimate/soil.py` com a integração
`Σ AW(mm/cm) × espessura(cm)`.

### 01:25 — Fase 4: experimento fenológico

`geospatial/agroclimate/phenology.py` + `tools/s27_phenology_window.py`:
84 municípios, 1.027 linhas recalculadas com o **mesmo** construtor do
painel sobre a janela de enchimento de grãos. Soja: 46 dias (ZARC: 61);
milho: 33 dias (ZARC: 61).

### 01:35 — Fase 2: inferência completa (com o bootstrap corrigido)

12 famílias de Holm (21 hipóteses cada): município 13 · célula 12 ·
bloco 250 km **4** · UF 0 · Conley 150/250/400/600 km 10/8/8/8 ·
bootstrap wild município/célula/bloco/UF 13/12/6/3.

### 01:40 — D81: política de nulidade explícita

O artigo primário de Cameron, Gelbach & Miller (2008) e o pacote CRAN
`fwildclusterboot` estão **inacessíveis** neste ambiente. Em vez de aplicar
uma regra de troca de nulidade não verificada, a V2.7 passa a **reportar os
dois** p-valores (imposta e irrestrita) e a declarar a política usada.

### 01:45 — Fase 9: suíte de testes da V2.7

`geospatial/tests/test_v27_robustness.py` com 47 testes (distribuições,
within↔LSDV, agrupado, Conley, bootstrap wild, Holm, divisões espaciais,
vazamento, fenologia, CAD, unidades, ausentes, deduplicação, persistência,
compatibilidade com a V2.6). Total: **309/309** offline, 10/10 externos.

---

## Sessão de continuidade — 2026-11-14 (auditoria e correções)

### 06:20 — Auditoria do estado real

Branch `v2/agroclimatic-robustness`, HEAD `aafb687`, sem commits após a
V2.6 que não estivessem publicados (`d87addb`). Nenhuma alteração em
arquivos rastreados (`git diff` vazio); 6 artefatos não rastreados:
`v27_spatial_validation.{json,csv}`, `v27_wild_bootstrap_calibration.json`,
`tools/{calibrate_wild_bootstrap,validate_v27_stats}.py` e
`tools/__pycache__/`.

Confronto entre documentação e realidade: a calibração **terminou** (84
casos, `updated_at` 05:29Z, `elapsed_s_total` 4.127 s), ao contrário do que
`MASTER_STATUS.md` e `NEXT_ACTIONS.md` registravam ("em curso"). A
validação P1–P4 também terminou (02:58Z), mas o relatório a citava só como
ponteiro, sem números.

### 06:22 — Checkpoint de recuperação (`ac41210`)

Commit dos artefatos não rastreados, preservando o estado numérico anterior
a qualquer correção; `.gitignore` da raiz passa a cobrir `__pycache__/`.

### 06:24 — Manifesto de dependência espacial gerado

`run_robustness.py dependence` nunca havia sido executado até o fim:
`v27_spatial_dependence.json` **não existia**, e os números do relatório
vinham de um script de sondagem em `tmp/`. Executado: 1.296 municípios,
3.653 dias (2016-01-01 a 2025-12-31). Reconciliação: os valores de
`MASTER_STATUS.md` (0,834 / 0,630 na banda 400–425 km) são os das
**anomalias anuais** e conferem; a tabela do relatório (0,8568 / 0,3591)
não correspondia a nenhum campo reproduzível e foi substituída.

### 06:30 — D85: duas falhas no caminho numérico do bootstrap

1. `se > 0` aceitava erro-padrão da ordem de 1e-19, gerando `|t| ≈ 1e18`
   que entrava na cauda como excedência. Evidência: `mean_t_boot_sd_cluster
   ≈ 8,5e14` em 9 casos da grade anterior (G = 5 e G = 10, DGP `agrupado`).
   Corrigido com piso relativo `sqrt(eps)·max(|β̂|,1)` em `robust.py` e
   `spatial_inference.py`.
2. O DGP `agrupado` **zerava a coluna 0** do design (`design[:, 0] = 0.0`
   num laço no-op), deixando posto 2 com `k = 3` declarados e distorcendo
   o multiplicador CR1. Corrigido mantendo o intercepto.

Verificado que a correção **não altera** os resultados publicados: os 105
bootstraps de `v27_robust_inference.json` usaram 999/999 réplicas, sem
nenhuma degenerada.

### 06:38 — P5 (D86): holdout espacial *e* temporal simultâneos

P1–P4 separam só o espaço; o treino contém o mesmo **ano** do teste em
outros municípios. Nova `analysis.two_way_blocked_holdout` remove do treino
os blocos de 250 km **e** os anos da dobra, e o protocolo entra em
`run_robustness.py spatial` como `P5_bloco_x_ano`.

### 06:41 — Fase 9 (revalidada): 318/318 offline

`318 passed` (309 da V2.7 + 9 novos: coerência observado × bootstrap com
peso unitário e ausência de vazamento em P5).

### 06:52 — Commit `feb309d`

Correções (D85), protocolo P5 (D86), testes novos e documentação
correspondente.

### 07:56 — Calibração recalculada (84/84 casos)

Grade completa reexecutada com o harness corrigido, `--force`:
* **9 → 0** diagnósticos degenerados (`mean_t_boot_sd_cluster` deixou de
  ter valores ~8,5e14).
* Diferença old→new **restrita a G = 5**: tamanho 0,037 → 0,047; poder
  0,468 → 0,535. Nos demais casos ≤ 0,007 (ruído Monte Carlo).
* `painel_fe` inalterado em todos os casos (o caminho *within* não foi
  afetado) — confirma que as correções foram cirúrgicas.
* Conclusão qualitativa preservada: pesos por grupo mantêm validade e
  custam poder com poucos grupos; o procedimento é **levemente**
  conservador com 5 grupos, não fortemente.

### 08:30 — Validação territorial concluída (P1–P5, 3 culturas)

* **Integridade:** 132 valores de MAE de P1–P4 comparados com o manifesto
  de `ac41210` → **0 diferenças**. As correções não tocaram os protocolos
  territoriais.
* **P5 (bloco × ano), ganho do bloco meteorológico:**
  soja +3,98% (P1) → +2,76% (P3) → **−3,30% (P5)**;
  milho +1,62% → +1,35% → **+1,21%** (hídrico **+5,40%**);
  milho 2ª +14,60% → +16,97% → **+16,92%**.
* **Resultado:** o ganho territorial da V2.6 era, em parte, efeito do
  **ano compartilhado** entre treino e teste. Para a soja ele não
  sobrevive; para o milho sobrevive apenas nas variáveis hídricas; para o
  milho 2ª safra sobrevive ao protocolo mais estrito.

### 08:35 — Fechamento

* Suíte offline **318/318**; externos opt-in **10/10**.
* `MASTER_STATUS`, `NEXT_ACTIONS`, `DATA_MANIFEST`, `EVIDENCE_MATRIX`,
  `RECOVERY` e o relatório consolidado atualizados com os números finais.
* Correção de rastreabilidade no relatório: o correlograma passou a citar
  o manifesto; a tabela antiga vinha de script em `tmp/`.
