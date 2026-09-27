# SADEN — AI Context Recovery (v1.0.0 → v1.1.x)

> Gerado em 2026-09-27 pelo agente de continuidade, após auditoria completa da árvore real.
> Fonte canônica: implementação + testes + schema + docs. SADEN-TCC = somente leitura.

## 1. Onde estamos

- **Baseline v1.0.0 congelado e VERDE** (commit único `9218e01 v1.0.0`, branch `main`, `origin https://github.com/Luan-tcpn/Saden.git`, working tree limpo).
- Backend **48/48 PASS** (`node --test`, 7 suítes, inclui 2 testes live nas fontes) — revalidado em 2026-09-27.
- Smoke **8/8 PASS** contra servidor live em 2026-09-27 (soja R$ 151,18 real, clima real, previsão `modelo=ridge`, relatório OK).
- `docs/` **PRESENTE e versionado** (8 arquivos, `git ls-tree HEAD docs/` confirma) — a nota do README que dizia "docs ausente nesta cópia" está **obsoleta** (era verdadeira numa árvore anterior, não nesta).
- Docker **não validável neste ambiente** (daemon Docker Desktop inativo em 2026-09-27); `Dockerfile` + `compose` íntegros por inspeção, `COPY docs ./docs` agora consistente porque `docs/` existe.
- `data/saden.db` = runtime (4,1 MB, WAL ativo), ignorado no git (`data/*.db*`). `.env` ignorado. Segredos não commitados.

## 2. Arquitetura real (confirmada no código)

- Backend Express porta única 3001: `rotas → serviços → integrações → utils`, middleware `auth JWT + rateLimit`.
  32 arquivos em `backend/src`: core (config, db, index), 2 middleware, 6 integrações (yahoo, bcb/PTAX, openmeteo, nominatim, ibge, landcover), 7 serviços (fx, price, priceReference, weather, geo, forecast, mail), 10 rotas, 4 utils.
- Frontend estático puro (HTML/CSS/JS + Leaflet 1.9.4 + Chart.js 4.4.1 via CDN), servido pelo backend. 10 arquivos.
- Banco SQLite `better-sqlite3`, WAL+FK, **14 tabelas** (users, data_sources, commodities, regions, price_observations, weather_observations, model_runs, forecasts, reports, password_resets, kv_cache, alerts, alert_events, user_places). Seed idempotente: 5 commodities + usuário demo `demo@saden.local / saden123` (local/acadêmico).
- Cache: preços/clima 60 min, geo 30 dias (`kv_cache`); landcover memória 100 + 30d. HTTP: timeout 12 s (landcover até 25 s), retry 3× linear 600 ms só em 502/429, Nominatim throttle 1,1 s.
- Preço = futuro CBOT/ICE (cents) × PTAX venda × fator (saca 60 kg = 2,20462 bu; café = 132,277 lb; algodão direto). Sem câmbio → ponto descartado. Fonte fora do ar → 502 honesto.

## 3. Forecast real (confirmado em `forecastService.js`)

- **Champion = Ridge própria** (sem deps, Gauss+pivô, padronização, intercepto não penalizado).
- Features só do passado (sem leakage): lag1, lag2, lag5, MM7, MM30, vol14 (dp log-returns 14d), índice t. `WARMUP=30`, `MIN_POINTS=60`, série 1a Yahoo×PTAX.
- Divisão temporal **70/15/15**, métricas MAE/RMSE/MAPE. Baselines val one-step: naive, seasonal_naive_5, ma7. Grade λ {0.1,1,10,100}, seleção por menor RMSE val. Previsão recursiva H 7|14|30 (default 14, dias corridos), intervalo ±1,96·σ_val·√h, lower truncado em 0.
- Resultado TCC (n=252 pregões, 5 commodities): Ridge vence val em 4/5; **café = naive vence no teste** (choque 1,7→2,5→1,9 mil) — patrimônio metodológico, não apagar.
- Clima e PTAX são **contexto, não features** do modelo. Land Cover é **camada visual**, não NDVI.

## 4. Fontes (classificação real)

| Fonte | Status |
|---|---|
| Yahoo Finance (futuros) | UTILIZADA |
| BCB/PTAX | UTILIZADA |
| Open-Meteo | UTILIZADA |
| IBGE | UTILIZADA |
| Nominatim | UTILIZADA (throttle+atribuição) |
| Esri/Impact Observatory Land Cover | UTILIZADA como camada visual |
| CEPEA | BLOQUEADA (API por contratação, fora do escopo) |
| CONAB | BLOQUEADA (portal com reCAPTCHA, sem REST pública) |
| INMET | NÃO INTEGRADA |
| ANTT/frete | REFERÊNCIA manual |
| NDVI/CDSE | ESTUDADA (`NDVI_STUDY.md`), bloqueada por credencial |

## 5. Segurança (auditada em 2026-09-27)

- bcrypt cost 10, JWT 12h com fail-fast sem `JWT_SECRET` em produção, rate-limit 10 req/10min em auth, SQL parametrizado (`better-sqlite3`), reset token sha256 + timingSafeEqual + TTL 1h + uso único, CSV com anti-formula-injection, erro 500 sem vazamento.
- XSS: `esc()` aplicado a strings de usuário/fonte externa antes de `innerHTML` (D20); 157 interpolações restantes são numéricas (`toFixed`/`fmtBRL`/datas) ou constantes internas — padrão aceito, sem `insertAdjacentHTML` inseguro.
- CSRF: n/a (auth via `Authorization: Bearer`, sem cookies). CORS: `FRONTEND_ORIGIN` configurável. CSP ativa no backend.

## 6. Decisões recuperadas

- `docs/DECISIONS.md`: **D1–D34** (última = D34 Docker RC). Maior D existente = **D34** → próxima decisão nova = **D35**.
- Segunda opinião (`segunda opnião.txt`, 940 linhas): fonte de hipóteses, NÃO especificação. Números de MAPE futuro (8–10%, 6–8%) são hipóteses, não resultados.

## 7. Discrepâncias encontradas e corrigidas

1. README dizia "`docs/` ausente nesta cópia" + "`docker compose build` falha nesta árvore" — **obsoleto**: docs presente e versionado; build não testável aqui por daemon inativo, mas causa citada (docs ausente) não existe mais. → corrigido no README nesta sessão.
2. Nenhuma outra divergência entre README, docs e código (TTLs, timeouts, tabelas, endpoints, seed, credenciais demo — tudo confere).

## 8. O que foi feito (nesta sessão, 2026-09-27)

- [x] FASE 1: inspeção raiz + Saden_AgroClima + SADEN-TCC (leitura) + git/remoto + docs + código + testes + schema + data + README.
- [x] Baseline executado: backend 48/48 + smoke 8/8 (live). Docker daemon inativo — build pendente de ambiente com Docker.
- [x] Este arquivo `AI_CONTEXT_RECOVERY.md` criado.
- [x] README: removidas notas obsoletas sobre docs ausente / build falhando.

## 9. O que falta (próximo passo)

- [ ] `docs/V1_1_AUDIT.md` — auditoria formal (bugs, gaps, riscos, oportunidades).
- [ ] `docs/V1_1_DECISION_MATRIX.md` — classificar sugestões da segunda opinião (IMPLEMENTAR/INVESTIGAR/ADIAR/REJEITAR/JÁ IMPLEMENTADO).
- [ ] D35: Champion/Challenger (regras do jogo forecast) — sem trocar Ridge antes de comparação.
- [ ] Investigação regionalização (CONAB/CEPEA/acesso legítimo) — sem proxy rotulado de preço real.
- [ ] Challengers Ridge (ARIMA/SARIMA/ETS/multivariada) sob protocolo train/val/test travado — sem ensemble antes de validar individuais.
- [ ] Docker build+up+health+down/up num ambiente com daemon ativo.
- [ ] E2E 53/53 (navegador real) quando ambiente permitir.

## 10. Decisões ativas / hipóteses em investigação

- Ativas: v1.0.0 = baseline imutável; acrescentar-não-destruir; preço = referência internacional declarada; Ridge = champion; café-naive = evidência de que baselines importam.
- Em investigação: challengers forecast; preço regional real; NDVI (bloqueado por credencial); OpenAPI; teste de carga; cobertura c8.
- Rejeitado por ora: LSTM/RF/XGBoost (dados curtos, sem justificativa); ensemble (antes de validar individuais); CSRF (sem cookies); Python (sem benefício demonstrado).
