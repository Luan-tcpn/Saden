# V3.3 — EXECUTION LOG

## 2026-11-14 — Fase 0: auditoria e checkpoint

* `Get-Location` → repositório técnico correto.
* `git status --short --branch` → limpo, sincronizado com `origin`.
* `git rev-parse HEAD` → `3bf9360`.
* Refs conferidas: `main` = `v1-final` = `archive/v1-final` = `3f7ad33`;
  V3.0 = `40fd6aa`; V3.1 = `345b22e`; V3.2 = `3bf9360` = `origin/v3.2`.
* Tags: `v1-final`, `v2-poc-sentinel2`. Stash vazio. Nenhuma branch `v3/water*`.
* Bundle V3.2 verificado (16.753.528 B, `E8EB3F5A…598FE9A4`); 13 pastas de
  recuperação presentes (V1 → V3.2).
* Suíte de referência: **410/410**.
* `git checkout -b v3/water-balance-inference-audit 3bf9360`.

## 2026-11-14 — Fase 1: inventário histórico

* `v27_robust_inference.json`: 3 culturas × 7 variáveis = 21 hipóteses; guarda
  coeficiente e **quatro** esquemas (município, célula, bloco, UF) e a família
  Holm de 21 com `n_significant_raw = 10` e `n_significant_holm = 4`.
* `v30_association_cad.json`: 15 hipóteses (3 × 5 definições de déficit),
  `n_survive_holm = 10`.
* `v29_cycle_interaction.json`: 9 testes de interação por grupo de ciclo.
* Painel: `v31_panel_windows.csv` tem as colunas `_legacy` necessárias para
  reproduzir V2.7 sem misturar janelas.

## 2026-11-14 — Fase 1b: descritores de estresse

* `tools/v33_water_variables.py` (reusa `v31_rebuild_panel`): déficit, duração,
  sequência, armazenamento mínimo, ETR/ETP, timing — nos quatro cenários de CAD.
* Achado de desenho: com CAD 0–100 / 0–200, **54% / 86%** das linhas não têm
  nenhum mês de estresse (mediana 0) → variáveis de duração degeneradas.
* `water_balance.stress_descriptors` criado na biblioteca (não no script), com
  limiar fixo de 1 mm declarado como não escolhido nos dados.

## 2026-11-14 — Fase 1c: auditoria de dependência

* `tools/v33_variable_audit.py` → `v33_variable_audit.json`.
* `etr_over_etp` × `deficit_over_etp` = **−1,000** (identidade DEF = ETP − ETR).
* `heat` × déficit = 0,84; `heat` × temperatura = 0,76 → calor não é bloco
  independente.
* `degree_days` é o único candidato térmico ortogonal (0,02 com temperatura).
* Número de condição do conjunto completo: ~5×10¹⁵ (singular).
* Esses números foram medidos **antes** do pré-registro e determinaram os blocos.

## 2026-11-14 — Fase 2: pré-registro

* `docs/V3_3_FUNCTIONAL_FORM_PREREGISTRATION.md`: H1–H6, especificação, modelos,
  família confirmatória de 3 testes (milho), regra A–D, robustez.
* **H3 declarada não testável antes dos resultados** (duração × intensidade,
  r = 0,73 e 0,94; balanço mensal).

## 2026-11-14 — Fases 3–7: Frente A

* `heterogeneity.joint_significance` (novo): Wald conjunto de bloco, *within* de
  município e ano, agrupamento duplo.
* `tools/v33_functional_form.py`: 7 modelos × 3 culturas, TE, 25 células, 3
  repetições, IC duplo; `--stage robustness` para leave-one-UF/ano.
* M2 reproduz a V3.1 exatamente (592,19 / 1.688,58 / 1.272,40).
* Resultado: nenhuma variante melhora. Hipótese H1/H2/H4: p = 0,953 / 0,101 /
  0,169 → Holm n.s.
* Associação: água além do clima p = 0,038 (Holm 0,076); não linearidade p = 0,014
  (Holm 0,041); térmico 0,961.
* Por UF: bloco hídrico ajuda em PR (−33,8) e RS (−53,1) e piora em MS/GO/MT/BA
  (+4,1 a +173,5) — padrão regional exploratório.
* Robustez: nenhuma exclusão de UF ou ano inverte o sinal agregado.

## 2026-11-14 — Fase 8: Frente B

* `tools/v33_inference_audit.py`: mesma especificação, mesma amostra, **só a VCV
  muda** (município, bloco, UF, UF×ano, duplo). Cenários C1/C2/C3 separados.
* Reprodução: V2.7 1,5×10⁻⁶; V3.0 3,6×10⁻¹⁵; V2.9 9,2×10⁻⁸. O Holm por bloco
  recomputado reproduz exatamente `p_adjusted` e `n_significant_holm` da V2.7.
* Resultado: V2.7 4 → **0** Holm; V3.0 10 → **8**; V2.9 1 → **0**.
* `tools/v33_write_audit_register.py` gera o registro markdown a partir do
  manifesto (sem transcrição manual).

## 2026-11-14 — Fases 13–17: testes, documentação e revisão

* `test_v33_functional_form.py`: 17 testes. Suíte **427/427**; `compileall` limpo.
* Revisão crítica: corrigidos dois erros do próprio relatório da Frente A —
  (i) a tabela por UF estava com marcadores em vez de números; (ii) eu havia
  escrito "positivo em todas as UFs" para soja, quando PR e RS são negativos — e
  esse detalhe é justamente o achado regional. Também corrigidas as razões
  mínimo/mediana/máximo de SE, que estavam erradas.
* Documentação: 3 relatórios, registro de auditoria, 6 arquivos de continuidade,
  decisões D108–D111.
* `tools/v33_verify_report.py`: 88 verificações automáticas de transcrição entre
  relatórios e manifests (exit 0). Encontrou dois números errados no próprio
  relatório da Frente A — p do H4 (0,169 → 0,167) e p de `milho|et0` sob bloco
  (3,2×10⁻⁹ → 2,42×10⁻⁶) — ambos corrigidos. Nenhum dos dois alterava conclusão.
* Verificação adicional: os **p-valores** históricos também reproduzem sob o
  esquema por bloco (log10 máx. 5,3×10⁻⁴ na V2.7), não só os coeficientes.
