# V3.1 — EXECUTION LOG

## 2026-11-14 — Fase 0: proteção e recuperação

* `git status` limpo em `40fd6aa`, sincronizado com `origin`.
* Integridade confirmada: `main` = `archive/v1-final` = `v1-final` =
  `3f7ad33bc18c5a8e8e050bbc7817f5078488d625`; V2.9 = `adb525f`; V3.0 =
  `40fd6aa`; tags `v1-final`, `v2-poc-sentinel2`.
* Bundle V3.0 verificado: 16.601.458 bytes, SHA-256 `2B954AC5…AE493D51`,
  29 refs, `git bundle verify` → *okay* e *complete history*.
* Suíte de referência: **372/372** em 15,9 s.
* Branch `v3/window-spatial-generalization` criada de `40fd6aa`.

## 2026-11-14 — Fase 1: auditoria da D97

* Causa confirmada em `cycle.window_bounds` (semântica histórica): comparação
  lexicográfica `"AAAA-MM-DD"` contra `"AAAA-MM"` exclui o último mês inteiro.
* Contrato único definido: `corrected=True` → primeiro dia do primeiro mês até o
  último dia do último mês; semântica histórica preservada para reprodução.
* 21 testes novos em `geospatial/tests/test_v31_window_contract.py`: último mês
  incluído, virada de ano, mês único, ano bissexto, janela vazia, meses em
  branco, determinismo, contagem de meses, balanço sequencial, graus-dia,
  calor extremo, consistência diário↔mensal.

## 2026-11-14 — Fase 2: reconstrução de todas as variáveis

* `tools/v31_rebuild_panel.py` recalcula 20 variáveis por linha nas duas
  janelas, usando as **mesmas** funções do painel
  (`thermal.accumulate_degree_days`, `thermal.heat_wave_events`,
  `thermal.extreme_heat_days`, `evapotranspiration.daily_et0_series`,
  `water_balance.*`).
* Reprodução da janela histórica contra o painel publicado (19.402 linhas):
  diferença máxima 1,7e-5; `temp_media_c` e `extreme_heat_days` exatos em todas
  as linhas. O pipeline é fiel — as diferenças são do defeito.
* Efeito de restaurar o último mês: precipitação +45,3%, ET0 +43,0%,
  graus-dia +46,2%, dias de chuva +49,2%, déficit +106,6%, excedente +57,4%.
* Manifesto `v31_window_rebuild.json`; painel derivado
  `v31_panel_windows.csv` (fora do Git, regenerável).
* Commit `2028efc`.

## 2026-11-14 — Fases 3–4: painel e modelos básicos

* `tools/v31_models.py` reproduz **exatamente** os números publicados da V3.0:
  soja −6,33, milho −198,72, milho 2ª −267,16, CAD 0–100 −142,78, CAD 0–200
  −21,68, déficit corrigido 50 mm na soja −19,97 (V3.0: −20,0).
* Janela corrigida: milho −228,5 (pareado −29,8 [−51,5; −2,3]); soja −18,5 n.s.;
  milho 2ª −228,4 (pareado +38,8 n.s.).
* `generalization.factorial_holdout` ganhou `keep_errors=True` para permitir
  comparações **pareadas** entre especificações nas mesmas linhas.

## 2026-11-14 — Fase 5: tendência espacial

* M3 (lat/lon + quadráticos + UF) e M4 (M3 + clima), centragem por constantes
  fixas (sem vazamento), complexidade fixada antes da avaliação.
* M3 é pior que M2 no milho (+388,1 [62,0; 719,5] pareado) e no milho 2ª
  (+178,7 [43,8; 342,7]). Rejeitada em D102.

## 2026-11-14 — Fase 6: vizinhos históricos

* `generalization.neighbor_holdout` implementado com o desenho TE: treino exclui
  bloco e ano do teste; fallback para a média da UF treinada, depois global.
* Grade fixada antes: raio 100/200/300 km, decaimento 50/100/150 km ou nenhum,
  mínimo de 3 ou 6 vizinhos.
* M1c supera M1 em todas as culturas em pelo menos uma configuração; o caso mais
  robusto é soja r200/d100 (−27,7 [−52,3; −3,8], cobertura 0,987).
* Teste de vazamento dedicado: alterar o `y` de uma única linha não move a
  previsão dessa linha.

## 2026-11-14 — Fase 7: efeito espacial por cultura e UF

* Contraste SS − SE recomputado com a janela corrigida: no milho o efeito do
  espaço vai de −170,8 (clima histórico) a −161,2 (clima corrigido) e cresce com
  a CAD (−206,6 em 0–60, −225,4 em 0–100, −286,1 em 0–200).
* Os valores de CAD 0–100 e 0–200 **reproduzem exatamente a V3.0**, o que
  confirma D98 com os dados corrigidos. O "histórico −209,5" da tabela da V3.0 é
  a especificação de déficit histórico, não o clima.
* Decomposição por UF: o ganho climático do milho está em PR (−607,4), BA
  (−131,1) e GO (−109,9); é negativo em MS (+261,4), MT (+85,0) e RS (+12,8).

## 2026-11-14 — Fase 9: validação e publicação

* `pytest geospatial/tests` → **393/393**; `compileall` limpo.
* Bundle de recuperação criado fora do repositório e verificado.
