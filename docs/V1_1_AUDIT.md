# SADEN v1.1 — Auditoria (FASE 2)

> Data: 2026-09-27. Método: inspeção de código + execução (testes, smoke, cobertura) + git. Sem mocks de produção.

## A1. Baseline executado

| Verificação | Resultado |
|---|---|
| `npm test` (backend) | 69/69 PASS, 12 suítes (2026-09-27; E3 adicionou 16 unitários AR + 2 integração) |
| `scripts/smoke-test.js` (live) | 8/8 PASS (soja R$ 151,18 real, clima real, `modelo=ridge`) |
| Cobertura (c8 efêmero via npx, sem dependência nova) | **88,51% linhas · 74,75% branches · 86,91% funcs** (suíte completa) |
| E2E navegador (53/53) | Não reexecutado (requer harness CDP + Edge; última validação registrada vale) |
| Docker build/up | Não executável aqui (daemon inativo); `COPY docs` consistente (docs versionado) |
| Git | `main` limpo, 3 commits (`v1.0.0` + 2 de docs locais ainda não enviados ao remoto), sem segredos |

## A2. Cobertura por área (c8, suíte completa)

- 100%: fxService, priceReferenceService, validate, coords, auth/rateLimit middleware, prices route.
- ≥90%: forecastService 97,8 · priceService 98,4 · yahoo 94,6 · commodities/places/landcover/alerts/auth routes 89–96.
- Atenção (sem impor meta): weatherService 53,6 (ramos de history/error), reports.js 54, http.js 72,3, geo.js 75,6, weather.js route 72. Quedas concentram-se em ramos de erro upstream e history — candidatos naturais a testes de timeout/fonte fora do ar (já classificados como INVESTIGAR na matriz).
- Veredito: sugestão "cobertura 70%+" da segunda opinião **superada sem adicionar dependência** (c8 via npx pontual; não incluído no `package.json` pelo dependency gate).

## A3. Gaps confirmados (viram itens INVESTIGAR, não bugs)

1. ~~Teste dedicado de cache hit/miss/TTL — ausente~~ → **FECHADO em E1** (2026-09-27): `cache kv: miss → hit → expiração/TTL → sobrescrita` + hit de rota via `latest` (51/51).
2. Teste de fonte lenta/fora do ar com 502 honesto — parcial (http.test cobre timeout unitário; rota com upstream morto exigiria injeção de dependência em produção — rejeitado; registrado como NOT RUN, §A6).
3. ~~Teste de série insuficiente (422) e commodity inexistente~~ → **FECHADO em E1**: 422 via cache semeado com série curta (sem mock) + rota propaga 422; commodity inexistente já coberta (404 em commodities/alerts/prices).
4. Logging atual não auditado (pino/winston só após auditoria).
5. LICENSE ausente (decisão do autor, não técnica).
6. Rotina de backup `data/saden.db` não documentada.
7. Docker não revalidado nesta máquina (pendente de ambiente com daemon).

## A6. Validações NOT RUN (explicitamente não executadas)
- E2E navegador 53/53: harness CDP + Edge indisponível aqui — como executar: `node scripts\e2e-round2.js` com servidor em execução.
- Docker build/up/health: daemon inativo — como executar: `docker compose build && docker compose up` com `JWT_SECRET` no ambiente.
- 502 de rota com upstream morto: sem seam de injeção (proposital, sem DI em produção); coberto em nível unitário (http.test).

## A7. E2 — investigação AR challenger (2026-09-27, D37)

Método: `tmp/ar-challenger.py` (só leitura; réplica numpy de `buildRows`/`splitRows`/`fitRidge`
validada contra `model_runs`: divergência ≤15% por janelas distintas). Evidência em
`docs/FORECAST_EVALUATION.md`: AR(p)+AIC vence Ridge na validação one-step em 5/5
(soja 1,67 vs 2,13; milho 0,76 vs 0,91; café 102,9 vs 164,5; trigo 1,47 vs 2,16;
algodão 0,0695 vs 0,0907). Limites: one-step ≠ recursivo multi-passo (uso operacional);
val_n 33–35; sem termos MA/sazonais. Veredito: GO condicional à implementação do
challenger no JS (E3); Ridge permanece champion.

## A8. E3 — AR challenger implementado e avaliado (2026-09-27, D37)

Implementação: `utils/linalg.js` + `services/arService.js`; Ridge com
comportamento inalterado (só import + export aditivo). Testes 69/69
(16 unitários AR incl. gate de leakage + 2 integração). Evidência em
`docs/FORECAST_EVALUATION.md` (E3): AR vence Ridge no one-step e no
recursivo H=7/14/30 nas 5 commodities; H30 absoluto fraco nos dois.
Veredito: challenger APROVADO; champion inalterado; exposição = D38.

## A9. D38 — investigação de exposição (2026-09-27, sem código)

Contrato mapeado: dashboard usa `GET /api/forecast/:key` (gráfico + `model_selected`
+ métricas + limitações); relatórios usam `forecastService.run` (JSON + CSV com
`lambda` no cabeçalho); `model_runs`/`forecasts` são genéricas e write-only
(nenhuma leitura em produção) — AR persiste sem migração (`model='ar(order=N)'`).
Matriz das alternativas (B vence por parsimônia): A interna/custo-0/valor-0;
B opt-in/aditiva/reversível/testável sem E2E; C dobra payload e custo; D exige
UI+E2E prematuramente. Testes mapeados para a implementação: param
ausente/ridge/ar/inválido(400), payload, CSV por modelo, persistência,
regressão do default. E2E só quando houver UI. Veredito: **EXPOR via B**;
implementação no próximo ciclo. Framing futuro: "Ridge (principal)" /
"AR (experimental)", com caveat H30.

## A4. Não-bugs (verificado, sem ação)

- XSS: `esc()` em strings externas; restante numérico/constantes — padrão D20 íntegro.
- CSRF: não aplicável (Bearer, sem cookies). `/api/sources` público por decisão.
- Timeout 12 s: testes live passam; 15 s rejeitado.
- joi/zod: validate.js cobre; rejeitado.
- Ensemble/pesos: rejeitado até challenger válido (D35).
- MAPE futuros da segunda opinião: hipótese, nunca meta (D35).

## A5. Riscos aceitos herdados (inalterados)

- Express 4 com 3 moderadas (D10, mitigado por body limit 256kb).
- Rate-limit em memória (instância única; D11).
- Intervalo ±1,96σ sem cobertura empírica (limitação declarada).
- Previsão em dias corridos; descarte de pregão sem PTAX (limitações declaradas).
