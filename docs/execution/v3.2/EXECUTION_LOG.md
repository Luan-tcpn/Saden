# V3.2 — EXECUTION LOG

Formato: data · fase · comando/script · arquivos · resultado · erro/correção · decisão.

## 2026-11-14 — Fase 0: auditoria e checkpoint inicial

* `Get-Location` → `C:\Users\luanf\OneDrive\Área de Trabalho\Saden_AgroClima`.
* `git status --short --branch` → limpo, `## v3/window-spatial-generalization...origin/...`.
* `git rev-parse HEAD` → `345b22e02b78447c94f0e6d5b316c3916d918283`.
* `git log --oneline -5` → `345b22e`, `7867100`, `2028efc`, `40fd6aa`, `adb525f`.
* `git branch -a` → 14 branches locais/remotas; nenhuma `v3/uf-*`.
* `git ls-remote --heads origin v3/uf-heterogeneous-climate-slopes` → vazio (branch nova).
* `git tag` → `v1-final`, `v2-poc-sentinel2`.
* `git stash list` → vazio.
* Integridade: `v1-final^{commit}` = `main` = `archive/v1-final` = `3f7ad33…`;
  V3.0 = `40fd6aa`; V3.1 = `345b22e`.
* Bundle V3.1: 16.658.052 B, SHA-256 `88A66B39F2BBEC3F69EBDF6F1DA8DFFD832BA1DACA19BD8952DA7E6CD406AA82`;
  pasta `SADEN_V3_0_RECOVERY_2026-11-14` também presente e intacta.
* Nenhuma divergência. Nenhuma operação destrutiva.
* `git checkout -b v3/uf-heterogeneous-climate-slopes 345b22e` → criada.

## 2026-11-14 — Fase 1: auditoria dos dados

* `geospatial/data/processed/v31_panel_windows.csv`: 19.402 linhas, 79 colunas,
  16,92 MB, presente no ambiente (OneDrive sincronizado).
* Distribuição por cultura × UF (linhas):

| cultura | PR | RS | GO | MT | MS | BA | total |
|---|---:|---:|---:|---:|---:|---:|---:|
| soja | 2.863 | 2.966 | 1.558 | 911 | 586 | — | 8.884 |
| milho | 2.966 | 1.428 | 1.567 | 997 | 552 | 106 | 7.616 |
| milho 2ª | 1.836 | — | 285 | 428 | 353 | — | 2.902 |

* BA (106 linhas) é a única célula claramente frágil; registrada no
  pré-registro e no diagnóstico de identificabilidade.

## 2026-11-14 — Fase 2: pré-registro

* `docs/V3_2_PREREGISTRATION.md` escrito **antes** de qualquer estimativa de
  heterogeneidade: H0–H3, estimandos, 3 famílias de multiplicidade (6
  confirmatórios, contrastes estaduais, 9 exploratórios), regra A–D.
* Ajuste de desenho **antes dos resultados**: ao medir a correlação *within*
  entre precipitação e temperatura (−0,60 a −0,67), a especificação primária
  passou a incluir as duas variáveis simultaneamente.

## 2026-11-14 — Fase 3: identificabilidade

* `coverage_diagnostics` em `heterogeneity.py`; manifesto
  `v32_coverage_diagnostics.json`.
* Classificação antes de interpretar: todas elegíveis, exceto milho 2ª/GO
  (285 linhas, 5 anos → com ressalvas) e milho/BA (106 linhas → apenas partial
  pooling). Nenhuma UF "não estimável".
* Achado de identificabilidade: variação *within* de temperatura é 17–26% em
  PR e 24–29% em RS — quase toda a dispersão é entre municípios e é descartada
  pelo *within*.

## 2026-11-14 — Fases 4–5: modelos

* `_design` e `_fit_predict` estendidos com `interaction_states` e `penalty`
  (default desligado; caminho histórico inalterado).
* `select_ridge_penalty`: 5-fold bloqueada por bloco **dentro do pool de treino
  de cada célula**; penalidade relativa à diagonal de Gram (encolhimento
  `1/(1+λ)`).
* `factorial_holdout` recebeu `interactions`/`penalty_grid` e expõe
  `penalty_selection`, `row_codes`, `row_years_raw`.
* Verificação: M2 comum reproduz a V3.1 **exatamente** (592,19 / 1.688,58 /
  1.272,40) → linhas de teste idênticas, comparação pareada.

## 2026-11-14 — Fase 7: inferência

* `heterogeneity.slope_heterogeneity`: modelo *within* de dois fatores com
  interações UF×clima, teste de Wald global por variável, contrastes por UF com
  Holm.
* **Correção de unidade (D104):** primeiro uso de agrupamento por bloco
  (herdado das versões anteriores) produziu F=8,74 (p≈0) na soja; com
  agrupamento duplo UF×ano + município, F=1,13 (p=0,36). Adicionado
  `two_way_cluster_vcov` como padrão e `cluster="block"` como sensibilidade.
* Família confirmatória: **1 de 6** rejeita após Holm (milho 2ª × temperatura).
* Nenhum contraste individual por UF sobrevive ao Holm.

## 2026-11-14 — Fase 6/9: predição e robustez

* `tools/v32_predictive.py --stage main`: M2 comum, HET-FE, HET-PP, caminho de λ,
  IC por bloco **e** por UF×ano. Resultado: milho PP −77,6 (UF×ano
  [−143,9; −4,8]; bloco [−162,7; 14,5]); soja +10,9; milho 2ª +6,1.
* `--stage robustness`: leave-one-UF-out inverte o sinal do milho em 4 de 6
  casos (reprova Nível A); leave-one-year-out estável em todos os 8 anos.
* Por UF (milho, PP): PR −206, BA −223, MT −57, GO −31, MS −20, **RS +112**.

## 2026-11-14 — Fase 10: M1c pareado

* `tools/v32_neighbors.py`: M1c e M2 previstos nas mesmas linhas, alinhados por
  (município, ano); decomposição coberto × fallback.
* M1c bate M1 (soja −27,7; milho −292,6; milho 2ª −194,5, IC UF×ano).
* M1c **não** bate M2 (IC incluem zero nas três culturas).
* Fallback é muito pior que os casos cobertos (milho r200: 2.103,5 contra
  1.604,9 kg/ha de MAE).

## 2026-11-14 — Fase 11: referências

* Três referências verificadas por busca (Cameron & Miller 2015; Cameron,
  Gelbach & Miller 2008; Hastie, Tibshirani & Friedman 2009), cada uma com URL
  persistente/DOI conferido, uso declarado e limitação aplicável.

## 2026-11-14 — Fases 13–17: testes, documentação e revisão

* `test_v32_heterogeneity.py`: 17 testes. Suíte completa **410/410**;
  `compileall` limpo.
* Revisão crítica: corrigida uma afirmação errada do relatório (a família
  exploratória **não** era toda nula — 3 variáveis do milho sobrevivem ao BH) e
  substituídos dois testes que afirmavam propriedades não garantidas pelo DGP
  por invariantes mecânicos verificáveis.
* Documentação: relatório completo, D104–D107, `KNOWN_RISKS`,
  `DATA_INVENTORY`, `VALIDATION_MATRIX`, `NEXT_ACTIONS`.
