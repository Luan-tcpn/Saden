# SADEN V2.7 — Status da execução

> Etapa: **V2.7 — Robustez estatística, validação espacial e agronomia**.
> Atualizado em: 2026-11-14 (sessão de continuidade pós-auditoria).

## Objetivo geral

Investigar se os resultados territoriais da V2.6 (ganho de 1,7% a 6,3%)
sobrevivem a uma inferência que controle a **dependência espacial real**
da base meteorológica, e se o modelo climático generaliza para municípios
não vistos ou se o ganho é favorecido por partilha de informação espacial
**e temporal**.

## Identificação da linha

| Item | Valor |
|---|---|
| Repositório | `C:\Users\luanf\OneDrive\Área de Trabalho\Saden_AgroClima` |
| Branch | `v2/agroclimatic-robustness` (base `d87addb` = V2.6) |
| Checkpoint de recuperação | `ac41210` (artefatos da execução interrompida) |
| Correções + P5 | `feb309d` |
| V1 | congelada em `3f7ad33` (tag `v1-final`) — **intacta** |
| `main` | `3f7ad33` — **intacta** |
| Ambiente | `geospatial/.venv` · Python 3.12.10 · numpy 2.5.4 · rasterio 1.4.3 · shapely 2.1.2 · pandas 2.2.3 · pytest 9.2.0 |
| `requirements.txt` | **inalterado** (a V2.7 não adiciona dependências; sem SciPy) |

## Estado das fases

| Fase | Item | Estado |
|---|---|---|
| 0 | Auditoria do estado real e do ambiente | **concluída** |
| 1 | Validação dos módulos estatísticos herdados | **concluída** — 16/16 verificações |
| 2 | Inferência espacial (agrupamento, Conley, bootstrap wild, Holm) | **concluída** |
| 3 | Calibração Monte Carlo do bootstrap wild | **concluída e recalculada** (84 casos; D85) |
| 4 | Pesquisa fenológica e experimento de janela | **concluída** (84 municípios, 1.027 linhas) |
| 5 | CAD territorial (Embrapa Solos / GeoInfo) | **concluída** (10 municípios, 100% de cobertura) |
| 6 | Fontes complementares (ERA5-Land) | **concluída — bloqueio documentado** (D83) |
| 7 | Diagnóstico de cobertura para expansão do painel | **concluída** — decisão: manter o painel atual (relatório §13) |
| 8 | Consolidação científica e documentação | **concluída** |
| 9 | Testes | **concluída** — 318/318 offline, 10/10 externos |
| 10 | Commit, bundle e publicação | **concluída** |

## Resultados centrais da V2.7

### 10.1 Dependência espacial (D76)

A limitação "55 km" da V2.6 está **refutada**: NASA POWER interpola a
coordenada solicitada (0% de séries diárias idênticas na mesma célula
nominal; 0,17% no milho 2ª safra) e a dependência espacial das anomalias
persiste muito além da grade. Correlograma reproduzível
(`v27_spatial_dependence.json`, 1.296 municípios, 3.653 dias):

| Banda (km) | 0–25 | 100–125 | 200–225 | 300–325 | 400–425 |
|---|---|---|---|---|---|
| T (anomalia anual) | 0,9939 | 0,9618 | 0,9238 | 0,8810 | **0,8339** |
| P (anomalia anual) | 0,9816 | 0,8713 | 0,7492 | 0,6791 | **0,6295** |

A correlação não cai abaixo de 0,10 até 600 km em nenhum campo. A escala
correta de agrupamento é calibrada pelo correlograma → **bloco espacial de
250 km** (46 grupos).

### 10.2 Inferência agrupada (D77)

| Esquema | grupos | hipóteses que sobrevivem a Holm (de 21) |
|---|---|---|
| município | 1.225 | 13 |
| célula MERRA-2 | 383 | 12 |
| **bloco espacial 250 km** | **46** | **4** |
| UF | 5–6 | 0 |
| Conley 150 / 250 / 400 / 600 km | — | 10 / 8 / 8 / 8 |
| bootstrap wild · município / célula / bloco / UF | — | 13 / 12 / 6 / 3 |

**Sobrevivem em todos os esquemas não degenerados:**
`soja|deficiency_total_mm`, `soja|temp_media_c`, `milho|temp_media_c`,
`milho|et0_total_mm`.
**Sensíveis ao esquema:** precipitação, dias de calor extremo, graus-dia e
excesso hídrico.

O erro-padrão do déficit hídrico da soja cresce de 0,0723 (município) para
0,1233 (célula) e 0,2404 (bloco 250 km) — a |t| cai de 17,4 para 5,2.

### 10.3 Bootstrap wild (D79–D81, D85)

* **Defeito corrigido (D80):** a implementação herdada sorteava um peso de
  Rademacher **por observação** (e não por grupo), o que não preserva a
  dependência intracluster. A versão correta usa **um peso por grupo**.
* **Defeito corrigido (D85):** `se > 0` aceitava erro-padrão da ordem de
  1e-19, gerando |t| ≈ 1e18 contado como excedência. Corrigido com piso
  relativo `sqrt(eps)·max(|β̂|,1)`; o DGP `agrupado` também tinha uma
  coluna estruturalmente nula (posto 2 com k=3), corrigida.
* A forma **vetorizada** é numericamente idêntica à forma em laço.
* O p-valor é reportado nos **dois ramos** (nulidade imposta e irrestrita),
  com a política declarada (`--null-policy`).
* Calibração Monte Carlo (84 casos, 2 DGP, 999 réplicas, 3 sementes):
  tamanho ≈ nominal para G ≥ 10 (0,039–0,068), **levemente conservador com
  5 grupos** (0,043–0,052) e poder de **53,5%** nesse regime, contra 91,3%
  da variante por observação e 94,2% do teste t.
* Diferença old→new restrita a G = 5 (tamanho 0,037 → 0,047; poder 0,468 →
  0,535); nos demais casos ≤ 0,007. Os 9 diagnósticos degenerados
  (`t_boot_sd ≈ 8,5e14`) desapareceram.

### 10.4 Janela fenológica (D78)

A janela de enchimento de grãos foi construída a partir de requisitos
térmicos **publicados** (soja R5 = 554 °C·dia; milho VT + 22,5 d a
VT + 55 d), com datas **aproximadas** pela soma térmica real.

* Soja: janela fenológica de 46 dias (ZARC: 61); 5/5 variáveis
  significativas nas duas janelas.
* Milho: janela de 33 dias (ZARC: 61); precipitação e temperatura passam
  de não significantes (ZARC) a significativas (fenológica).

Os coeficientes **não** são comparáveis entre janelas; comparam-se
**direção e significância**.

### 10.5 CAD territorial (D82)

Fonte oficial: Embrapa Solos / GeoInfo — Vasques et al. (2021), 90 m,
**CC BY-NC 3.0 BR**, unidade **mm/cm**, 6 profundidades.

Amostra controlada (10 municípios): CAD de 0–100 cm entre **126,0 e
239,9 mm** (mediana **158,9 mm**); **10/10** acima dos três cenários da
V2.6 (35/50/70 mm).

### 10.6 Fontes complementares (D83)

ERA5-Land nativo: **bloqueado** (credencial CDS ausente). NASA POWER
permanece como base reanalisada; INMET como validação independente. CHIRPS
e ARCO: sem resolução DNS. Nenhuma credencial foi criada ou gravada.

### 10.7 Validação territorial P1–P5 (D86 — resultado central)

Sequência com a **mesma** linha de base e a **mesma** amostra de teste;
muda só a informação removida do treino (ganho do bloco `B`, o
meteorológico):

| Protocolo | retirado do treino | soja | milho | milho 2ª |
|---|---|---|---|---|
| P1 município (V2.6) | o município | +3,98% | +1,62% | +14,60% |
| P2 célula MERRA-2 | a célula | +3,99% | +1,47% | +14,22% |
| P3 bloco 250 km | o bloco | +2,76% | +1,35% | +16,97% |
| P4 leave-one-UF-out | a UF | −1,75% | −3,38% | não estimável |
| **P5 bloco × ano** | **bloco e ano** | **−3,30%** | **+1,21%** | **+16,92%** |

* **Soja: não robusto.** O ganho inverte quando o ano deixa de ser
  compartilhado.
* **Milho: parcialmente robusto.** O bloco hídrico mantém **+5,40%** em
  P5; o meteorológico, apenas +1,21%.
* **Milho 2ª safra: robusto** no protocolo mais estrito (+16,92%), com a
  ressalva de que a linha de base agregada é fraca para a 2ª safra e P4
  não é estimável (4 UFs).

P1–P4 reproduzem **bit a bit** (132 valores de MAE, 0 diferenças) e a
faixa +1,35% a +6,36% confirma o resultado da V2.6.

## Testes

| Suíte | Resultado |
|---|---|
| Offline (`geospatial/tests`) | **318/318** OK (262 da V2.6 + 56 da V2.7) |
| Externos opt-in (`geospatial/tests_external`) | **10/10** OK |

## Artefatos da V2.7

**Código** — `geospatial/agroclimate/`: `robust.py`, `spatial.py`,
`spatial_inference.py`, `phenology.py`, `soil.py`; modificados:
`analysis.py` (inclui `two_way_blocked_holdout`), `panel.py`; CLI
`geospatial/run_robustness.py`.
**Scripts** — `tools/`: `calibrate_wild_bootstrap.py`,
`validate_v27_stats.py`, `s27_wcs_probe.py`, `s27_cad_metadata.py`,
`s27_cad_sample.py`, `s27_phenology_window.py`, `s27_panel_coverage.py`.
**Manifests versionados** (13): `v27_spatial_dependence.{json,csv}`,
`v27_spatial_validation.{json,csv}`, `v27_wild_bootstrap_calibration.json`,
`v27_robust_inference.{json,csv}`, `v27_cluster_diagnostics.json`,
`v27_phenology_window.{json,csv}`, `v27_cad_layer_metadata.json`,
`v27_cad_sample.{json,csv}`, `v27_cad_wcs_probe.json`,
`v27_panel_coverage.{json,csv}`, `v27_stats_validation.json`.

## Próxima ação

Nenhuma pendência da V2.7. A V2.8 (ampliação nacional do painel, CAD no
balanço hídrico, identificação de cultivar e refinamento de P5 por
cultura) está descrita em `NEXT_ACTIONS.md` (P4) e no relatório §23.

> Detalhe item a item em `NEXT_ACTIONS.md`; decisões em
> `DECISIONS_V2_7.md`; evidências em `EVIDENCE_MATRIX.md`; dados em
> `DATA_MANIFEST.md`; retomada em `RECOVERY.md`.
