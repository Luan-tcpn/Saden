# SADEN V2.7 — Matriz de evidências

> Cada afirmação da V2.7 com a evidência correspondente. Fontes primárias
> quando existem (manifests, saídas de scripts, literatura); ausências são
> declaradas como ausência.

| # | Afirmação | Evidência | Onde verificar |
|---|---|---|---|
| E01 | Os 12 efeitos fixos da V2.6 são reproduzidos bit a bit | Coeficiente da soja `deficiency_total_mm` = −1,260169893887058 (n = 8.884, 1.225 municípios, 8 anos), idêntico ao manifesto da V2.6 | `geospatial/tests/test_v27_robustness.py::V26CompatibilityTest::test_fixed_effects_keep_known_result`; `v27_robust_inference.json` (bloco `v26_lsdv_municipality_clustered`) |
| E02 | O estimador *within* equivale ao LSDV | Diferença absoluta entre 3,1e-13 e 4,9e-11 nas 3 culturas × 2 variáveis do painel real | `tools/validate_v27_stats.py` → `v27_stats_validation.json` (16/16 verificações OK) |
| E03 | As funções de distribuição conferem com valores tabelados | `t_critical` dif. máx. 5,0e-10 (df = 1, 10, 30); `normal_cdf(1,9599639845) = 0,975` | `tools/validate_v27_stats.py`; `geospatial/tests/test_v27_robustness.py::DistributionTest` |
| E04 | O bootstrap wild usava pesos **por observação** (defeito) | O código sorteava `rng.choice([-1,1], size=len(grupo))` — um peso por observação — em `robust.py` e `spatial_inference.py` | Diff da correção (D80); `geospatial/tests/test_v27_robustness.py::WildBootstrapTest::test_weights_are_constant_within_cluster` |
| E05 | A versão corrigida usa **um peso por grupo** | Peso constante dentro de cada grupo em todas as réplicas (teste automatizado) | `test_weights_are_constant_within_cluster` |
| E06 | A forma vetorizada reproduz a forma em laço | p-valor idêntico (imposta e irrestrita) e `t_boot_sd` idêntico em ambos os bootstraps | `test_vectorized_equals_loop`, `test_ols_vectorized_equals_loop`; `validate_fast_against_loop` em `v27_wild_bootstrap_calibration.json` |
| E07 | A dependência espacial excede a grade nominal de 55 km | Anomalias anuais: r(T) = 0,8339 e r(P) = 0,6295 na banda 400–425 km; a correlação não cai abaixo de 0,10 até 600 km | `run_robustness.py dependence` → `v27_spatial_dependence.json` / `.csv` |
| E08 | NASA POWER interpola a coordenada solicitada | Taxa de pares de municípios da mesma célula com séries diárias idênticas: 0,0% (soja, milho) e 0,17% (milho 2ª); ΔT média 0,32–1,90 °C | `v27_cluster_diagnostics.json` → `diagnostics_celula_grade.cell_pair_identity_rate` |
| E09 | 4 de 21 hipóteses sobrevivem ao Holm no esquema conservador (bloco 250 km) | `milho|et0_total_mm` (p_adj 5,1e-05), `soja|deficiency_total_mm` (8,2e-05), `soja|temp_media_c` (8,2e-04), `milho|temp_media_c` (6,9e-03) | `v27_robust_inference.json` → `multiplicity.bloco_espacial_250km` |
| E10 | A significância depende do esquema de agrupamento | Holm: 4/21 (bloco 250 km) · 12/21 (célula MERRA-2, 383 grupos) · 8/21 (Conley 250–600 km) · 13/21 (município) | `v27_robust_inference.json` → `multiplicity` |
| E11 | O erro-padrão cresce ao agrupar espacialmente | soja `deficiency_total_mm`: EP 0,0723 (município) → 0,1233 (célula) → 0,2404 (bloco 250 km) | `v27_robust_inference.json` → `within_clustered.schemes` |
| E12 | O bootstrap wild paga poder com poucos grupos | G = 5: poder **53,5%** (pesos por grupo) vs **91,3%** (pesos por observação) vs 94,2% (t agrupado); G ≥ 10: poder ≈ 100% | `v27_wild_bootstrap_calibration.json` (DGP `agrupado`, casos `efeito`) |
| E13 | O bootstrap wild tem tamanho próximo do nominal | G = 5: 0,043/0,052/0,047; G = 10: 0,051–0,061; G = 25: 0,045–0,058; G = 50: 0,046–0,057; G = 100: 0,047–0,063; G = 200: 0,039–0,047; `painel_fe` 10: 0,051–0,071 (MC SE ≈ 0,005) | `v27_wild_bootstrap_calibration.json` (grade recalculada, D85) |
| E14 | A CAD pode vir de fonte oficial geoespacial | 6 camadas `aw_*` (mm/cm) a ~90 m, EPSG:4326, no-data −9999, licença **CC BY-NC 3.0 BR**, citação Vasques et al. (2021) | `tools/s27_cad_metadata.py` → `v27_cad_layer_metadata.json`; `v27_cad_wcs_probe.json` |
| E15 | A CAD oficial é ~2–3× maior que os cenários da V2.6 | CAD 0–100 cm: 126,0–239,9 mm (mediana 158,9); 10/10 municípios acima de 35, 50 e 70 mm | `tools/s27_cad_sample.py` → `v27_cad_sample.json` |
| E16 | A janela fenológica muda a representação e os resultados | Soja: janela 46 dias (fenológica) vs 61 dias (ZARC); 5/5 variáveis significativas em ambas as janelas; milho: precipitação e temperatura passam de não-significantes a significativas | `tools/s27_phenology_window.py` → `v27_phenology_window.json` |
| E17 | A base do ERA5-Land nativo exige credencial ausente | Sem `CDS_API_KEY`, sem `~/.cdsapirc`, sem pacote `cdsapi`; bloqueio documentado | `docs/execution/v2.7/MASTER_STATUS.md` (D83) |
| E18 | A suíte completa passa | **318/318** testes offline (262 da V2.6 + 56 da V2.7) e 10/10 externos opt-in | `geospatial/tests/`, `geospatial/tests_external/` |
| E19 | Não há vazamento entre treino e teste nas divisões espaciais | `split_by_groups` recusa sobreposição; `leakage_report` por `ibge_code` e `cluster_id` | `geospatial/tests/test_v27_robustness.py::SpatialSplitTest` |
| E20 | A duplicação de observações do painel é zero | Varredura completa do painel: 0 duplicatas por (município, cultura, fonte, ano de colheita) | `test_panel_has_no_duplicate_observations` |
| E21 | Réplicas do bootstrap com erro-padrão nulo não são contadas como excedência | Piso relativo `sqrt(eps)·max(\|β̂\|,1)`; réplica com pesos +1 reproduz exatamente o `t` observado (OLS e *within*) | `robust.degenerate_std_error`; `test_ols_bootstrap_unit_weights_reproduce_observed_statistics`, `test_within_bootstrap_unit_weights_reproduce_observed_se`; `test_degenerate_std_error_helper` |
| E22 | Os resultados publicados não continham réplica degenerada | 105 bootstraps de `v27_robust_inference.json` usaram `n_bootstrap_used = 999` de 999; nenhum `\|t_boot_sd\| > 100` | `v27_robust_inference.json`; verificação registrada em `EXECUTION_LOG.md` |
| E23 | O DGP da calibração tinha coluna estruturalmente nula | `design[:,0]` zerada por laço no-op → posto 2 com `k = 3`; recalculado com intercepto (posto 3) | `tools/calibrate_wild_bootstrap.py::simulate_agrupado`; diff de `ac41210` → `feb309d` |
| E24 | O holdout territorial não separa o ano | Em P1–P4 o treino contém o mesmo ano da observação de teste em outros municípios, o que permite absorver o choque do ano | `analysis.territorial_holdout`; seção 9 e limitação 11 do relatório |
| E25 | P5 remove bloco **e** ano do treino | `TwoWayHoldoutTest` verifica, para cada cruzamento de dobras, que treino e teste não compartilham bloco nem ano, e que as predições cobrem todas as células usáveis | `analysis.two_way_blocked_holdout`; `geospatial/tests/test_v27_robustness.py::TwoWayHoldoutTest` |
| E26 | O ganho territorial depende do ano compartilhado | Ganho do bloco `B`: soja +3,98% (P1) → +2,76% (P3) → **−3,30% (P5)**; milho +1,35% → **+1,21%** (hídrico **+5,40%**); milho 2ª +16,97% → **+16,92%** | `v27_spatial_validation.json` → `crops.*.P5_bloco_x_ano.gains_vs_media_historica` |
| E27 | P1–P4 foram reproduzidos sem alteração pelas correções | 132 valores de MAE comparados com o manifesto de `ac41210`: 0 diferenças | verificação registrada em `EXECUTION_LOG.md` (sessão de continuidade) |

## Ausências declaradas (não são falhas)

| Item | Situação |
|---|---|
| ERA5-Land via CDS | **Ausência de credencial** — não houve aquisição nem tentativa de autenticação (D83) |
| CHIRPS / ARCO | **Ausência de resolução DNS** — não repetidos |
| Identificação de cultivar | **Ausente na PAM** — os perfis fenológicos são **cenários** por grupo de maturação |
| Estágio fenológico intermediário do milho 2ª safra | **Não publicado com precisão suficiente** — a cultura permanece na janela do ZARC |
| Licença em linguagem natural da CAD | **Obtida do registro ISO 19115**: CC BY-NC 3.0 BR (uso não-comercial) |
| Valores do quantum de água no solo (AW) por município | **Não existem**: o dado é raster a 90 m; a amostra usa a mediana de uma janela em torno do centroide, declarada como tal |
| Convenção de troca de nulidade do CGM | **Não verificável** neste ambiente → as duas variantes são reportadas (D81) |
