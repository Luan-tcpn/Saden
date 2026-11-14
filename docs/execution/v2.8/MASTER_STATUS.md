# SADEN V2.8 — Status da execução

> Etapa: **V2.8 — Generalização temporal-espacial, linha de base e integração
> agroclimática**. Atualizado em: 2026-11-14 (sessão única).

## Objetivo

**Os resultados agroclimáticos da V2.6/V2.7 representam generalização real
para municípios e anos não observados, ou parte do desempenho depende da
composição dos dados, da construção da linha de base e de informação
compartilhada entre treino e teste?**

## Identificação da linha

| Item | Valor |
|---|---|
| Repositório | `C:\Users\luanf\OneDrive\Área de Trabalho\Saden_AgroClima` |
| Branch | `v2/temporal-spatial-generalization` (base `36bf5d7` = V2.7) |
| V2.7 preservada | `v2/agroclimatic-robustness` em `36bf5d7`, publicada |
| Bundle V2.7 | `..\SADEN_V2_7_RECOVERY_2026-11-14\`, SHA-256 `0AB3CDF2…04B9C9`, *okay* |
| V1 / `main` | `3f7ad33` (tag `v1-final`) — intactas |
| Ambiente | `geospatial\.venv\Scripts\python.exe` (3.12.10), sem SciPy |
| Suíte | **338/338** offline (318 da V2.7 + 20 da V2.8) |

## Estado das fases

| Fase | Item | Estado |
|---|---|---|
| 0 | Auditoria, bundle, branch, suíte de referência | **concluída** |
| 1 | Auditoria e reprodução de P1/P3/P5 | **concluída** — `SE = P3`, `TE = P5` exatos |
| 2 | Decomposição espaço × tempo com controle de tamanho | **concluída** (D87) |
| 3 | Linhas de base e comparação justa | **concluída** (3 baselines + 2 variantes) |
| 4 | CAD e balanço hídrico | **concluída com cobertura limitada** (D88) |
| 5 | Fenologia, ZARC e ciclos | **concluída parcialmente** (D89) |
| 6 | Diagnóstico de cobertura | **concluída** (CAD 0,39%; ciclo concentrado) |
| 7 | Síntese científica | **concluída** — `docs/V2_8_GENERALIZATION_REPORT.md` |
| 8 | Validação final, bundle e publicação | **concluída** |

## Achados centrais

1. **Tamanho de amostra refutado.** Equalizar o treino em 5.686 linhas desloca
   a MAE em ≤ 1 kg/ha. A inversão do P5 não vem da redução de 36%.
2. **Mecanismos distintos por cultura.** Soja paga pelo **ano** (−39,8;
   IC95 −54,4 a −22,2) e não pelo **bloco** (−3,6; n.s.). Milho paga pelo
   **bloco** (−93,7) e não pelo ano (−6,9; n.s.).
3. **A comparação publicada era injusta.** O modelo não tinha termo regional e
   era comparado à média nacional. Contra a média da UF ele **perde** na soja
   (+43,2; IC95 +4,2 a +84,7). Contra a média nacional o ganho é −17,0 com IC
   incluindo zero: o "+2,70%" **não é significativo** sob dependência espacial.
4. **Com informação igualada o clima acrescenta pouco na soja** (−13,1; IC95
   −25,7 a −0,6; ≈2,3%) e muito no milho 2ª safra (−165,8 a −267,2 em todos os
   braços).
5. **A CAD da V2.6 não era análise de sensibilidade.** 35/50/70 mm movem o
   déficit em ±3%; a CAD oficial 0–100 cm o reduz em 18,6% e 0–200 cm em 42,3%.
6. **Associação não estável por classe de ciclo na soja**: temperatura inverte
   de sinal na classe 21 (+182,7; t=+4,38 vs −65,0; t=−3,18).

## Classificação das conclusões

| Conclusão | Status |
|---|---|
| P1–P5 reproduzidos; fatorial reproduz P3 e P5 | **validado** |
| Tamanho de amostra não explica a inversão | **validado nos cenários examinados** |
| Soja: ganho territorial | **não robusto** (nenhuma linha de base sustenta) |
| Soja: associação déficit→produtividade | **parcialmente robusto** (sólido na classe dominante) |
| Soja: associação temperatura→produtividade | **sensível à estratificação por ciclo** |
| Milho: ganho territorial | **parcialmente robusto** (família hídrica) |
| Milho: associação déficit | **robusto em sinal** nas 3 classes |
| Milho 2ª: ganho territorial | **robusto** contra todas as linhas de base |
| Milho 2ª: associação agronômica | **não conclusivo** (não sobrevive por classe) |
| CAD: efeito no balanço | **validado em 9 municípios (~19% no déficit)** |
| CAD no painel completo | **bloqueado por cobertura** (5/1.296 municípios) |
| Classes de ciclo rotuladas (precoce/médio/tardio) | **não realizado** — sem dicionário de dados |

## Artefatos

**Código** — `geospatial/agroclimate/generalization.py` (fatorial, baselines,
bootstrap de bloco); `geospatial/tests/test_v28_generalization.py` (20 testes).
**Scripts** — `tools/s28_factorial.py`, `tools/s28_cad_balance.py`,
`tools/s28_cycle_stratification.py`.
**Manifests** — `v28_factorial.{json,csv}`, `v28_cad_balance.{json,csv}`,
`v28_cycle_stratification.json`.
**Relatório** — `docs/V2_8_GENERALIZATION_REPORT.md`.

## Próxima ação executável

Nada pendente na V2.8. V2.9: adotar `climate_plus_state` como referência;
completar a CAD (1.296 municípios) mantendo a heterogeneidade; obter o
dicionário de dados do ZARC para rotular as classes; investigar o efeito do
bloco no milho.

## Bloqueios

- CAD em escala de painel: exige extração WCS massiva + decisão de escopo.
- Rótulo das classes de ciclo: PDF do dicionário de dados do ZARC não coletado.
- ERA5-Land: credencial CDS ausente (D83). CHIRPS/ARCO: sem DNS.
