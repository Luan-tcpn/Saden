# V3.4 — EXECUTION LOG

## 2026-11-14 — Fase 0: auditoria e checkpoint

* `git status --short --branch` → limpo, sincronizado; `HEAD` = `6eff88c`.
* Refs conferidas: `main` = `v1-final` = `archive/v1-final` = `3f7ad33`;
  V3.0 `40fd6aa`; V3.1 `345b22e`; V3.2 `3bf9360`; V3.3 `6eff88c` = origin.
* Tags `v1-final`, `v2-poc-sentinel2`; stash vazio; nenhuma branch `v3/regional*`.
* Bundle V3.3 verificado (16.865.810 B, `C6A863C4…BE617763D`); 14 pastas de
  recuperação presentes.
* Suíte de referência **427/427**.
* `git checkout -b v3/regional-water-block-hypothesis 6eff88c`.

## 2026-11-14 — Fase 1: classificação regional

* `web_fetch` do PDF oficial da IN SPA/MAPA nº 1/2021 → 200, texto obtido, mas o
  **download direto** (requests, curl, Invoke-WebRequest) retorna **404** nesta
  rede. Registrado como bloqueio de acesso, não como ausência da fonte.
* Alternativa encontrada na **própria página oficial de normativos do ZARC**: a
  planilha "municípios e suas respectivas regiões edafoclimáticas"
  (`MacrorregioSojicolasAtualizado_2025.xlsx`), versão legível por máquina do
  mesmo anexo. Download 200, 140.020 bytes.
* `tools/v34_region_mapping.py`: baixa (com UA/referer de navegador), calcula
  SHA-256 (`91126b6b…7458c84`), parseia 4.286 pares UF–município, normaliza nomes
  (sem acento, sem separadores) e junta aos municípios do painel.
  **1.422 de 1.782** pareados; 360 não pareados são municípios **sem indicação de
  soja** (quase todos na BA). 0 duplicados.
* Composição UF × MRS no painel: PR 134/266 (MRS1/2), RS 497 (MRS1), MS 53/26
  (MRS2/3), GO 119/127 (MRS3/4), MT 141 (MRS4), BA 27/35 (MRS4/5).
* `docs/V3_4_REGIONAL_CLASSIFICATION_PROTOCOL.md` **congelado antes de qualquer
  estimativa**, com Sul = MRS1, Cerrado = MRS3∪4, MRS2 excluída.

## 2026-11-14 — Fase 2: cobertura e identificação

* `tools/v34_coverage.py` → `v34_coverage_identifiability.json`.
* **Cramér's V = 1,000** nas três culturas; **nenhuma UF nos dois grupos** →
  região aninhada em UF. Registrado antes dos resultados.
* Suporte: déficit mediano no milho 0,97 mm (Sul) × 74,4 mm (Cerrado).
* Variação dentro de estado disponível em GO, MS, PR e BA.

## 2026-11-14 — Fase 3: pré-registro

* `docs/V3_4_REGIONAL_WATER_PREREGISTRATION.md` congelado: H1, estimandos
  (Δ por região e D = Δ_Sul − Δ_Cerrado; interação associativa), família
  confirmatória de **2 testes no milho** (Holm), regra A–F com **precedência de E
  sobre B**, e robustez obrigatória.
* Declarado explicitamente: **não existe amostra não examinada** → nenhuma
  confirmação independente é possível nesta versão.

## 2026-11-14 — Fases 4–6: estimativas

* `tools/v34_regional_contrast.py`: reproduz M2 e M2+bloco hídrico da V3.3 e
  calcula Δ por região, por UF e por UF×macrorregião, com IC por UF×ano e por
  bloco; e a interação associativa com agrupamento duplo.
* Milho: D = −78,3 [−131,7; −26,7]; interação −1.287,3 (p = 1,8×10⁻⁶, G=47).
* Soja: D = −35,0 [−80,7; +0,7]; milho 2ª: D = −22,5 [−42,2; +1,4].
* Família confirmatória: p = 0,0010 e 1,8×10⁻⁶; ambos sobrevivem ao Holm.

## 2026-11-14 — Fase 7: estabilidade e sensibilidades

* LOO-UF (milho): D de −40,3 a −150,1, **todas negativas**; LOO-ano: de −44,5 a
  −133,0, todas negativas.
* Soja: inverte em um ano (até +3,8). Milho 2ª: inverte no LOO-UF (até +47,0).
* Dentro de estado: PR MRS1×MRS2 +1.011,7 (p = 0,0022); GO 3×4 +54,4 (p = 0,735);
  MS 2×3 +222,2 (p = 0,110).
* **Erro corrigido durante a revisão:** a primeira versão da análise dentro de
  estado usou `n_space_folds=3`, protocolo diferente do principal, e produziu
  spread de 144 no PR; recomputado no mesmo protocolo (5 dobras) o spread é 20,2.
  A conclusão qualitativa (heterogeneidade dentro de estado) permanece, mas os
  números reportados são os do protocolo principal.
* **Bug corrigido:** a análise por decis mapeava déficit por `ibge_code`,
  colapsando vários anos do mesmo município numa linha arbitrária. Corrigido para
  a chave (município, ano); 0 linhas sem alinhamento após a correção. A conclusão
  anterior (decis "todos iguais") era artefato do bug.
* Sensibilidades: D negativo em **5 classificações** e **3 ponderações**; 9 de 10
  decis.

## 2026-11-14 — Fase 8: cobertura territorial

* `tools/v34_coverage_gap.py` → `v34_coverage_gap.json`.
* Denominador oficial: 4.286 municípios com indicação de soja em 21 UFs; 1.425
  nas 6 UFs do painel (**33,25%**); 2.861 fora (66,75%).
* Correspondência municipal alta (98,6–100% dos indicados).
* **SP é a única UF ausente com municípios em MRS 1 e MRS 3** (645 indicados).

## 2026-11-14 — Fases 9–12: figuras, testes, verificação, documentação

* `tools/v34_figures.py`: 6 figuras em `docs/figures/v34/` (layout de uma delas
  corrigido após inspeção visual — rótulos colidiam com o título).
* `geospatial/tests/test_v34_regional.py`: testes de mapeamento, alinhamento,
  contraste, classificação e verificação.
* `tools/v34_verify_report.py`: verificação numérica dos relatórios.
* Documentação: protocolo, pré-registro, relatório principal, diagnóstico de
  cobertura, consolidado, 8 arquivos de continuidade, decisões D112–D115.
