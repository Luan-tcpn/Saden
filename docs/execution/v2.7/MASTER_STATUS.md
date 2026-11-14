# SADEN V2.7 — Status da execução

> Etapa: **V2.7 — Robustez estatística, validação espacial e agronomia**.
> Atualizado em: 2026-11-14 (sessão de continuidade).

## Objetivo geral

Investigar se os resultados territoriais da V2.6 (ganho de 1,7% a 6,3%)
sobrevivem a uma inferência que controle a **dependência espacial real**
da base meteorológica, e se o modelo climático generaliza para municípios
não vistos ou se o ganho é favorecido por partilha de informação espacial.

## Identificação da linha

| Item | Valor |
|---|---|
| Repositório | `C:\Users\luanf\OneDrive\Área de Trabalho\Saden_AgroClima` |
| Branch | `v2/agroclimatic-robustness` (base `d87addb` = V2.6) |
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
| 3 | Calibração Monte Carlo do bootstrap wild | **em curso** (grade de 84 casos, gravada incrementalmente) |
| 4 | Pesquisa fenológica e experimento de janela | **concluída** (84 municípios, 1.027 linhas) |
| 5 | CAD territorial (Embrapa Solos / GeoInfo) | **concluída** (10 municípios, 100% de cobertura) |
| 6 | Fontes complementares (ERA5-Land) | **concluída — bloqueio documentado** (D83) |
| 7 | Diagnóstico de cobertura para expansão do painel | **pendente** (decisão: manter o painel atual) |
| 8 | Consolidação científica e documentação | **em curso** |
| 9 | Testes | **concluída** — 309/309 offline, 10/10 externos |
| 10 | Commit, bundle e publicação | **pendente** |

## Resultados centrais da V2.7

### 10.1 Dependência espacial (D76)

A limitação "55 km" da V2.6 está **refutada**: NASA POWER interpola a
coordenada solicitada (0% de dias com séries idênticas na mesma célula
nominal; ΔT média 0,32–1,90 °C) e a dependência espacial das anomalias
anuais persiste muito além da grade (r(T) = 0,834 e r(P) = 0,630 na banda
400–425 km). A escala correta de agrupamento é calibrada pelo
correlograma → **bloco espacial de 250 km** (46 grupos).

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

### 10.3 Bootstrap wild (D79–D81)

* **Defeito corrigido:** a implementação herdada sorteava um peso de
  Rademacher **por observação** (e não por grupo), o que não preserva a
  dependência intracluster. A versão correta usa **um peso por grupo**.
* A forma **vetorizada** (≈1000× mais rápida) é numericamente idêntica à
  forma em laço (p-valor e dispersão bootstrap idênticos).
* O p-valor é reportado nos **dois ramos** (nulidade imposta e irrestrita),
  com a política declarada (`--null-policy`).
* Calibração Monte Carlo (dois DGP): tamanho próximo do nominal nos
  esquemas com ≥ 10 grupos; **conservador com 5 grupos** (poder 46% pelo
  esquema correto × 88% pelo esquema herdado).

### 10.4 Janela fenológica (D78)

A janela de enchimento de grãos foi construída a partir de requisitos
térmicos **publicados** (soja R5 = 554 °C·dia; milho VT + 22,5 d a
VT + 55 d), com datas **aproximadas** pela soma térmica real.

* Soja: janela fenológica de 46 dias (ZARC: 61); 5/5 variáveis
  significativas nas duas janelas.
* Milho: janela de 33 dias (ZARC: 61); precipitação e temperatura passam
  de não significantes (ZARC) a significativas (fenológica).

Os coeficientes **não** são comparáveis entre janelas (a exposição muda);
comparam-se **direção e significância**.

### 10.5 CAD territorial (D82)

Fonte oficial: Embrapa Solos / GeoInfo — Vasques et al. (2021), 90 m,
**CC BY-NC 3.0 BR**, unidade **mm/cm**, 6 profundidades.

Amostra controlada (10 municípios): CAD de 0–100 cm entre **126,0 e
239,9 mm** (mediana **158,9 mm**); **10/10** acima dos três cenários da
V2.6 (35/50/70 mm) — os cenários são **conservadores** frente ao dado
oficial.

### 10.6 Fontes complementares (D83)

ERA5-Land nativo: **bloqueado** (credencial CDS ausente). NASA POWER
permanece como base reanalisada; INMET como validação independente. CHIRPS
e ARCO: sem resolução DNS. Nenhuma credencial foi criada, solicitada ou
gravada.

## Testes

| Suíte | Resultado |
|---|---|
| Offline (`geospatial/tests`) | **309/309** OK (262 da V2.6 + 47 novos da V2.7) |
| Externos opt-in (`geospatial/tests_external`) | **10/10** OK |

## Artefatos da V2.7

**Código** — `geospatial/agroclimate/`: `robust.py`, `spatial.py`,
`spatial_inference.py`, `phenology.py`, `soil.py`; modificados:
`analysis.py`, `panel.py`; novo CLI `geospatial/run_robustness.py`.
**Scripts** — `tools/`: `calibrate_wild_bootstrap.py`,
`validate_v27_stats.py`, `s27_wcs_probe.py`, `s27_cad_metadata.py`,
`s27_cad_sample.py`, `s27_phenology_window.py`.
**Manifests** — `geospatial/data/manifests/v27_*.json` e `.csv` (12 arquivos).

## Próxima ação

Aguardar a conclusão da calibração e da validação territorial (P1–P4),
consolidar o relatório comparativo V2.6 × V2.7, atualizar a documentação
principal, commitar por marcos e publicar o bundle.

> Detalhe item a item em `NEXT_ACTIONS.md`; decisões em
> `DECISIONS_V2_7.md`; evidências em `EVIDENCE_MATRIX.md`; dados em
> `DATA_MANIFEST.md`; retomada em `RECOVERY.md`.
