# Fechamento — registro de execução

**Data:** 2026-11-14 · Branch `maintenance/final-reliability-closeout`

---

## 1. Auditoria inicial

`HEAD` = `0973b77`, árvore limpa, branch sincronizada. Referências conferidas:
`main`/`v1-final` = `3f7ad33`; V3.0 `40fd6aa`; V3.1 `345b22e`; V3.2 `3bf9360`;
V3.3 `6eff88c`; V3.4 `b9e7098`; V3.5 `32dfb88`; consolidação `0973b77`.
Suíte herdada: **482/482**. Decisões iam até D127.

## 2. Fontes climáticas

Construído `tools/audit_climate_sources.py` (duas passagens sobre 6,55 M linhas,
1,08 GB, 74 s). Resultados em `CLIMATE_SOURCE_ADJUDICATION.md`.

Construídos também `agroclimate/contracts.py` (contrato executável) e
`tools/validate_source_contract.py` (AST + runtime). Iterações do validador:

- 1ª: 10 sinalizações — 5 eram **erros de leitura BOM** (arquivos com U+FEFF) e
  1 era o próprio validador;
- 2ª: `panel.py::_build_row` sinalizado por **atribuir** `row["status"]`, não por
  comparar — falso positivo do scanner;
- 3ª: refinado para sinalizar só comparações; `s27_panel_coverage.py` entrou como
  **waiver documentado** (contador de relatório, não consumidor);
- final: **28 funções com guarda, 0 sem guarda**.

`analysis.prepare_rows` passou a exigir fonte declarada quando recebe amostra
mista (D128).

## 3. ET0 — duas correções de rumo

1. Construído `tools/validation/et0_adjudication.py` com fatorial 2×2
   reimplementando a referência. O fatorial **não reproduzia a biblioteca**
   (4,2389 vs 4,6428 mm/dia). A alegação inicial de "ET0 subestimada em 10,3%"
   era artefato do meu harness.
2. Instrumento refeito **ancorado na biblioteca**, usando a identidade
   `vento×2,5 ⇒ u2 = vento/3,6` (erro máximo 8,9e-16). Resultado correto:
   **+0,54%** líquido, com o vento sozinho valendo +11,30%.

Também corrigido o harness de `water_balance_reference.py`, que calculava o dia
juliano como `mês×30 + dia%30` (`_day_of_year` agora usa a data civil).

## 4. D124

Caso manual reproduzido (15 mm vs 5 mm), causa identificada no ramo positivo
(`storage` é limitado à CAD antes do teste), identidade de conservação
`P = ETR + EXC + ΔARM` falha na referência e vale no módulo corrigido.
`corrections.py` implementa C3.

## 5. Inferência

Construído `fast_bootstrap.py` (álgebra de somas por cluster) e
`bootstrap_calibration.py`. Correções durante a construção:

1. `x` e `y` compartilhavam o componente de cluster → 100% de rejeição sob H0;
2. WCU não recentrava a estatística → 0% de rejeição;
3. escala do regressor confundida com a do resíduo → poder 100% em qualquer MDE;
4. `icc_x` separado do ICC do erro (sem isso o EP simulado ficava 2× baixo);
5. casamento de momento do ruído com o EP observado.

Descoberto e documentado o defeito `null_imposed` com uma coluna (D129), e que
CR2 ≡ CR1 com `k = 1`.

Resultado com 5.000 réplicas: CR1 7,54–9,98%; WCR 5,26–5,96%.

## 6. Build completo

Primeiras tentativas de execução em segundo plano travaram no launcher (processo
sem CPU, sem log). Diagnóstico: o filho existia mas não progredia. Contornado com
execução em primeiro plano e **build em 6 blocos** (~101 s cada), com merge
validado. 30.207 linhas, 1.880 municípios, 0 duplicidades.

Comparação com V3.5: **37 colunas idênticas**, 11 alteradas pela física.

## 7. Determinismo

`manifest.py` implementado. Duas execuções → `content_sha256` idêntico
(`96599508…`) e SHA-256 do arquivo idêntico (`8624B904…`). Merge também
determinístico.

## 8. Erros de processo registrados

- `Set-Content`/`Get-Content` em PowerShell 5.1 corromperam acentuação duas vezes
  (mojibake). Corrigido com `[System.IO.File]::WriteAllText(..., UTF8Encoding)`
  e, depois, evitando PowerShell para conteúdo de arquivo.
- Primeira versão de `apply_calibrated_inference.py` saiu com uma expressão
  corrompida (`"t_boo**t_abs_q95"`), detectada na revisão e corrigida.
- `merge_build_chunks.py` montava o caminho sem o prefixo do bloco → `FileNotFoundError`,
  corrigido.
