# SADEN v1.1 — Impacto no TCC (documento de apoio ao autor, 2026-09-27)

> Pertence ao projeto técnico. NÃO altera o SADEN-TCC. O autor decide o que
> levar ao relatório acadêmico. Separação estrita: FATO / INTERPRETAÇÃO /
> LIMITAÇÃO / POSSÍVEL IMPACTO.

## 1. Evoluções com possível impacto acadêmico

### 1.1 Challenger AR(p)+AIC (D35–D39, E2–E4)
- FATO: AR(p) com ordem por AIC (p∈1..8, treino) venceu a Ridge na validação
  one-step em 5/5 e no recursivo H=7/14/30 em 5/5, mesma série/split/métricas;
  implementação JS validada contra réplica Python independente (valores idênticos).
- INTERPRETAÇÃO: evidência de que estrutura autorregressiva domina o one-step
  nestas séries; NÃO prova superioridade preditiva geral.
- LIMITAÇÃO: val_n 33–35; série ~1 ano; H30 fraco nos dois; sem termos MA/sazonais.
- POSSÍVEL IMPACTO: seção de "trabalhos de evolução / challenger" na metodologia
  e resultados; reforça honestidade experimental (baselines + challenger).
- NÃO AFIRMAR: "AR é melhor que Ridge em geral", "ARIMA foi implementado",
  MAPEs futuros, superioridade multi-passo além do medido.

### 1.2 Exposição opt-in (D38/D39)
- FATO: `?model=ar` + seletor Ridge (principal) / AR (experimental); default Ridge.
- POSSÍVEL IMPACTO: demonstra transparência metodológica no produto (banca pode testar ao vivo).

### 1.3 G6 regional
- FATO: nenhuma fonte regional integrável (CONAB CAPTCHA, CEPEA R$ 11–22 mil,
  IMEA parcial-MT sob licença, B3 só futuros).
- POSSÍVEL IMPACTO: fortalece a seção de limitações + trabalhos futuros, com
  evidências datadas e portas concretas (convênio, autorização).

### 1.4 Qualidade
- FATO: 80/80, E2E 57/57, cobertura 88,5% linhas, backup operacional, smoke ao vivo.
- POSSÍVEL IMPACTO: seção de testes/validação com números comprovados.

## 2. O que NÃO muda no TCC sem decisão do autor

Metodologia oficial (Ridge champion, 70/15/15, MAE/RMSE/MAPE), resultados
da v1.0 (252 pregões, café-naive), escopo e limitações já declaradas.

## 3. Evidências a preservar para a banca

`docs/FORECAST_EVALUATION.md` (números E2/E3), `docs/REGIONAL_INVESTIGATION.md`,
logs de suíte, `model_runs` (713+ runs com métricas), commits D35–D39.

## 4. Riscos acadêmicos a evitar

Apresentar proxy como preço real; alegar conformidade WCAG; alegar
"production-ready"; transformar hipótese (MAPE futuro, ARIMA) em resultado;
usar test set como argumento de seleção (usado só para relato).
