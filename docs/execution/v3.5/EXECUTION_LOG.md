# V3.5 — EXECUTION LOG

## 2026-11-14 — Fase 0: auditoria

* `git status` limpo, sincronizado; `HEAD` = `b9e7098`; refs V1.1–V3.4 conferidas;
  tags `v1-final`, `v2-poc-sentinel2`; stash vazio.
* Bundle V3.4 verificado (17.305.790 B, `49A584F3…D33BFAA5`).
* Suíte de referência **442/442**.
* `git checkout -b v3/sp-within-state-validation b9e7098`.

## 2026-11-14 — Fase 0b: reconciliação 1.422 × 1.425

* 1.425 = pares UF–município na planilha oficial nos 6 estados;
  1.422 = pares que casaram por string exata.
* Os 3: **Poxoréo** (MT) = Poxoréu; **Santo Antônio do Leverger** (MT) = Santo
  Antônio de Leverger; **Vila Alta** (PR), extinto, hoje Alto Paraíso (PR).
* Conclusão: variantes nominais, não território ausente. Registrado no
  `COVERAGE_AUDIT.md` e no relatório de cobertura.

## 2026-11-14 — Fase 1: aquisição de SP

* `tools/v35_acquire_sp.py --stage municipalities`: 645 municípios (shapes IBGE
  2025), snapshot do painel histórico em `panel_municipalities_v34.csv`,
  `panel_municipalities_v35.csv` com 2.427.
* `--stage climate`: 645/645, **0 falhas**, 2.356.185 linhas, 430 s (4 workers),
  cache por município em `data/external/sp_climate_cache/`.
* `--stage productivity`: 46.440 registros (11.610 de rendimento), 4 lotes de 200.
* `--stage zarc`: 1.082.148 linhas de janela em 10 safras.
* CAD: `v30_cad_acquire.py` parametrizado (`--municipalities/--geojson/--panel/
  --out`) → 584 municípios, 6 camadas WCS a `scaleFactor=0.2`, 14,5 s.
* `--stage panel`: 19.608 linhas, **10.805 utilizáveis** (soja 3.633, milho 4.397,
  milho 2ª 2.775).

## 2026-11-14 — Fase 2: mapeamento e janelas

* `tools/v35_region_mapping.py`: estende o mapeamento congelado a SP com o mesmo
  parser e a mesma planilha (hash `91126b6b…`); **verifica linha a linha** que os
  6 estados não mudaram (aborta se mudarem). SP: MRS 1 = 44, MRS 2 = 431,
  MRS 3 = 168; 2.065 municípios no mapeamento.
* `tools/v35_build_windows.py`: aplica a janela corrigida (D100) e os descritores
  (V3.3) às linhas de SP, reutilizando `_aggregate` e `_descriptors`;
  `v35_panel_windows.csv` = 19.402 históricas (copiadas) + 10.805 de SP.

## 2026-11-14 — Fase 3: modelos

* `tools/v35_models.py`:
  * **A** (6 UFs): M2 = 1.661,2 / 592,7 / 1.272,3; D = −78,3 / −35,0 / −22,5 →
    reprodução **exata** da V3.4;
  * **B** (7 UFs): M0/M1/M2/M2+água reestimados;
  * **C**: comparação de composição com decomposição explícita;
  * **dentro de SP**: soja D = +7,3 [−18,8; 26,9], interação p = 0,77;
  * **transferência**: treino nas 6 UFs, teste em SP → −27,3% (milho) e −5,9%
    (soja) contra a média global.
* Verificado que a atribuição de blocos dos municípios históricos **não muda**
  com a entrada de SP (0 alterações; SP cria 11 blocos próprios).

## 2026-11-14 — Fase 4: robustez e cobertura

* `tools/v35_coverage_and_robustness.py`: cobertura antes/depois, LOO-ano,
  grupos alternativos (MRS 1×2, 2×3), reconciliação.
* Soja: D inverte entre anos (−17,8 a +13,2); grupos alternativos +1,1 e +9,0 —
  sem gradiente MRS.
* Cobertura: 6→7 UFs, 1.274→1.856 municípios, 19.307→30.081 linhas.

## 2026-11-14 — Fases 5–7: testes, verificação, documentação

* `test_v35_sp_expansion.py`: testes de integração de SP, do mapeamento, do
  pareamento e da não regressão do painel histórico.
* `tools/v35_verify_report.py`: verificação numérica dos relatórios.
* Documentação: pré-registro (com divulgação do desvio de ordem), 6 relatórios,
  9 arquivos de continuidade, decisões D116–D119.

## Erros de execução registrados

| # | erro | detecção | correção |
|---|---|---|---|
| 1 | status de aquisição sobrescrito por escrita concorrente | entrada `climate` ausente no JSON | reexecução da etapa (cache, 35 s) |
| 2 | painel de SP sem latitude → 0 linhas de janela | saída `n_window_rows: 0` | junção por `ibge_code` ao cadastro municipal |
| 3 | `Counter.add` inexistente em `v35_region_mapping` | exceção mascarada por manifesto antigo em disco | reestruturado; reexecutado com verificação de não regressão |
| 4 | primeira versão de `v35_models` calculava blocos com o cadastro de 6 UFs → SP descartada | `n_rows` idêntico entre A e B | blocos do cadastro de 7 UFs (verificado: 0 reatribuições históricas) |
