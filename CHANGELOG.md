# Changelog SADEN

## V1 final — tag `v1-final` (2026-11-11)

- Forecast: metodologia **única Ridge** (D40). `?model=ridge` permanece apenas como alias legado; qualquer outro valor (`ar`, `AR`, `arima`, vazio) retorna **HTTP 400**, sem fallback silencioso.
- Retirados do produto: `backend/src/services/arService.js`, `olsBeta` (linalg), select `#sel-model`, estado `saden_model` e parâmetro `model` no cliente HTTP do frontend.
- Histórico preservado: linhas `model_runs.model='ar(order=3)'` (5) e `'ar(order=1)'` (4) continuam no banco, sem migração, renomeação ou reinterpretação; novos runs gravam somente `ridge(lambda=…)`.
- Relatórios JSON/CSV: identificam Ridge e rejeitam `model=ar` com 400; CSV mantém proteção anti formula-injection (TAB/CR/LF).
- Segurança: gate fail-fast de `JWT_SECRET` em produção extraído para `_test.assertProductionSecret`; CSP/cabeçalhos cobertos por teste; escapes adicionais em datas/IDs; `fx_fallback_days` exposto para declarar repetição de PTAX.
- Testes: **65/65 PASS, 9 suítes** (7,06 s); smoke **9/9** local e no container; **E2E 57/57** em Edge headless/CDP com `pageErrors: []`.
- Docker validado em 2026-11-11: build, up healthy, auth, Ridge, `model=ar`→400, persistência down/up, backup (4,47 MB), imagem efêmera e não-root; fail-fast sem `JWT_SECRET` confirmado.
- Docs: D40 em `DECISIONS.md`; `FORECAST_EVALUATION.md` ganha E5 (AR encerrado, resultados mantidos como investigação); `docs/CONTEXTO_V2.md` criado (roadmap documental, sem implementação).

## v1.1.0 (2026-09-27) — consolidada (superada pela V1 final)

- Forecast: challenger AR(p)+AIC isolado (`arService.js`); opt-in por `?model=ar` (Ridge segue default); seletor Ridge (principal) / AR (experimental) no dashboard; persistência `ar(order=N)` sem migração; CSV identifica o modelo.
- Testes: 48 → 80 (`npm test`, inclui cache/TTL, 422, AR, opt-in, backup); E2E 53 → 57; cobertura medida 88,51% linhas (c8 efêmero, sem dependência nova).
- Operacional: `scripts/backup.js` (cópia online, retenção 7) + rotina documentada.
- Docs: `AI_CONTEXT_RECOVERY`, `V1_1_AUDIT`, `V1_1_DECISION_MATRIX` (D35–D39), `FORECAST_EVALUATION`, `REGIONAL_INVESTIGATION`, `V1_1_RESULT`, `V1_1_TCC_IMPACT`.
- Investigação G6: nenhuma fonte regional integrável; nada alterado no Price Reference Engine.
- Docker: validado em 2026-09-27 naquela árvore; revalidado na V1 final.

## v1.0.0 (commit `9218e01`) — MVP

Express + SQLite (14 tabelas) + frontend estático; Yahoo×PTAX; clima, geo, mapa, Ridge com baselines; auth JWT; relatórios JSON/CSV; alertas; 48/48 + E2E 53/53 (validação registrada).
