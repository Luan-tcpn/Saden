# Changelog SADEN

## v1.1.0 (2026-09-27) — consolidada

- Forecast: challenger AR(p)+AIC isolado (`arService.js`); opt-in por `?model=ar` (Ridge segue default); seletor Ridge (principal) / AR (experimental) no dashboard; persistência `ar(order=N)` sem migração; CSV identifica o modelo.
- Testes: 48 → 80 (`npm test`, inclui cache/TTL, 422, AR, opt-in, backup); E2E 53 → 57; cobertura medida 88,51% linhas (c8 efêmero, sem dependência nova).
- Operacional: `scripts/backup.js` (cópia online, retenção 7) + rotina documentada.
- Docs: `AI_CONTEXT_RECOVERY`, `V1_1_AUDIT`, `V1_1_DECISION_MATRIX` (D35–D39), `FORECAST_EVALUATION`, `REGIONAL_INVESTIGATION`, `V1_1_RESULT`, `V1_1_TCC_IMPACT`.
- Investigação G6: nenhuma fonte regional integrável; nada alterado no Price Reference Engine.
- Não validado neste ambiente: Docker build/up (daemon indisponível).

## v1.0.0 (commit `9218e01`) — MVP

Express + SQLite (14 tabelas) + frontend estático; Yahoo×PTAX; clima, geo, mapa, Ridge com baselines; auth JWT; relatórios JSON/CSV; alertas; 48/48 + E2E 53/53 (validação registrada).
