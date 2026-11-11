# SADEN — Contexto e roadmap da V2 (documento, não implementação)

> Status: **PLANEJAMENTO DOCUMENTAL**. Nada descrito aqui foi implementado,
> medido ou validado. Este arquivo existe para registrar critérios, riscos e
> perguntas antes de qualquer código. A V1 permanece congelada (D40).
> Data: 2026-11-11.

## 1. Ponto de partida real (V1)

- Previsão com metodologia única **Ridge**; `?model=ridge` é apenas alias
  legado e qualquer outro valor retorna HTTP 400.
- AR(p) foi avaliado como challenger e **retirado do produto**; resultados
  históricos permanecem em `docs/FORECAST_EVALUATION.md`.
- Histórico experimental em `model_runs` preservado, sem migração.
- Gates da V1: 65/65 testes, smoke 9/9, E2E 57/57, Docker validado.
- Limitações vigentes: referência internacional (não preço físico regional),
  modelo univariado, série ~1 ano, intervalo gaussiano sem cobertura empírica,
  sem TLS/SMTP real/monitoramento/teste de carga, instância única.

## 2. Regra de entrada na V2

A V2 só começa se **todas** as condições abaixo forem verdadeiras:

1. Existe uma decisão nova registrada em `docs/DECISIONS.md` (D41+), com
   problema, alternativas, custo e critério de aceite.
2. A V1 está reproduzível: `npm test`, smoke e E2E verdes na árvore limpa.
3. O escopo escolhido tem evidência de valor (uso real, banca/orientador ou
   requisito técnico concreto), não apenas desejo de novidade.
4. Há tempo e ambiente para validar de verdade (Docker, navegador, fonte
   externa) — sem declarar concluído o que não foi executado.
5. `SADEN-TCC` continua intocado; mudanças ficam neste repositório.

## 3. Trilhas candidatas (prioridade proposta, não compromisso)

### T1 — Robustez operacional (maior valor por risco)
- TLS/reverse proxy, backup automatizado com verificação, logs com retenção,
  healthcheck externo e alerta de falha.
- Critério de aceite: reinício sem perda, restauração testada, health monitorado.
- Risco: ambiente de deploy inexistente; exige decisão de hospedagem.
- Dependência: definição do alvo (máquina local, VPS, serviço gerenciado).

### T2 — Observabilidade e desempenho
- Medir latência real por endpoint e custo de forecast sob carga; cache de
  forecast **somente se** a medição justificar (D12).
- Critério de aceite: números antes/depois, sem regressão funcional.
- Risco: otimização prematura; benchmark mal desenhado.
- Dependência: script de carga reproduzível e ambiente estável.

### T3 — Dados regionais (alto valor acadêmico, alta dependência externa)
- CEPEA (contratação), CONAB (CAPTCHA), IMEA (licença parcial-MT), B3 (futuros).
- Critério de aceite: contrato/autorização + fonte documentada + série
  comparável + declaração de nível (nacional/regional).
- Risco: custo, licença e instabilidade; scraping não autorizado é proibido.
- Dependência: convênio ou autorização formal; sem isso, trilha bloqueada.

### T4 — Modelagem (somente com protocolo experimental)
- Reavaliar challengers (SARIMA/ETS/ensemble) **fora do produto**, com mesmo
  split, mesmas métricas, teste intocado e decisão explícita de entrada.
- Critério de aceite: ganho consistente e reprodutível, com validação
  multi-horizonte e limite de complexidade.
- Risco: overfitting em ~1 ano de série; `val_n` pequeno; comparação injusta.
- Dependência: mais dados históricos e/ou fonte regional (T3).

### T5 — Experiência e acessibilidade
- Auditoria WCAG básica, navegação por teclado, contraste, estados de erro.
- Critério de aceite: checklist verificável + E2E ampliado.
- Risco: alegações de conformidade sem auditoria formal (evitar).
- Dependência: escopo e ferramenta de auditoria definidos.

## 4. Fora de escopo por padrão

- Reescrever a arquitetura (microsserviços, Python, ORM) sem necessidade medida.
- Trocar a metodologia do produto sem decisão e sem avaliação.
- Scraping de CEPEA/CONAB ou proxy de dados não autorizados.
- Prometer MAPE futuro, "production-ready" ou cobertura do intervalo.
- Apagar histórico de experimentos (`model_runs`/`forecasts`).

## 5. Critérios de saída (definition of done)

Uma trilha só é considerada concluída quando:

- implementação revisada e sem segredos no diff;
- testes novos cobrindo o comportamento (sem reduzir a suíte existente);
- smoke/E2E executados quando houver superfície de UI/API;
- Docker revalidado quando o artefato mudar;
- documentação atualizada com números reais e limitações honestas;
- tag/release apenas com push e evidência confirmados.

## 6. Perguntas abertas

1. Qual é o alvo real de execução (local, VPS, PaaS)? Sem isso, T1 fica abstrata.
2. Existe orçamento/convênio para CEPEA ou autorização IMEA? Se não, T3 para.
3. Há série histórica maior disponível para reduzir o risco de T4? De onde?
4. Qual nível de disponibilidade é exigido pela banca/uso real?
5. Quem opera backup/restauração e com qual frequência?
6. A acessibilidade precisa de laudo formal ou de checklist técnico?
7. Qual o critério objetivo para "V2 pronta" (data, demonstração, publicação)?

## 7. Riscos transversais

| Risco | Impacto | Mitigação |
|---|---|---|
| Escopo inflado | V2 nunca fecha | uma trilha por vez, com critério de aceite |
| Fonte externa instável | dados faltando | cache, 502 honesto, fallback declarado |
| Série curta | modelo frágil | não prometer precisão; avaliar fora do produto |
| Deploy sem TLS | credenciais expostas | T1 antes de qualquer uso real |
| Histórico perdido | perda de auditabilidade | backups + proibição de migração destrutiva |
| Docs divergirem do código | perda de confiança | atualizar docs no mesmo commit |

## 8. Regras de honestidade (herdadas da V1)

- Nada de números inventados, fontes fictícias ou resultados extrapolados.
- Docker/push/release só com execução real e evidência.
- Separar sempre FATO / INTERPRETAÇÃO / LIMITAÇÃO / POSSÍVEL IMPACTO.
- `SADEN-TCC` é somente leitura; o autor decide o que levar ao texto acadêmico.

## 9. Primeiro passo sugerido (quando autorizado)

Escolher **uma** trilha, escrever D41 com problema/alternativas/custo/critério,
e só então abrir branch. Sem decisão registrada, a V2 permanece não iniciada.
