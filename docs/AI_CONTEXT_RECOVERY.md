# SADEN — AI Context Recovery (V1 FINAL congelada, 2026-11-11)

> Documento canônico de retomada. Fonte de verdade: implementação + testes +
> schema + docs desta árvore. `SADEN-TCC` é somente leitura; nada nele foi alterado.
> Registro histórico da v1.1 continua em `docs/V1_1_*.md` e `docs/DECISIONS.md`.

## 1. Onde estamos

- **V1 congelada** na branch `main`, tag anotada `v1-final` (ver `git tag`).
- Backend **65/65 PASS**, 9 suítes (`cd backend; npm test`, ~7 s).
- Smoke **9/9 PASS** local e no container.
- E2E **57/57 PASS** em Edge headless + CDP 9333, `pageErrors: []`.
- Docker **validado em 2026-11-11**: build, up healthy, auth, Ridge,
  `model=ar`→400, persistência down/up, smoke 9/9, backup 4,47 MB, imagem
  efêmera/não-root e fail-fast sem `JWT_SECRET`.
- `data/saden.db` = runtime (ignorado no git); `.env` ignorado; segredos não
  versionados. Histórico AR preservado no banco (ver §3).

## 2. Escopo congelado da V1 (D40)

- **Previsão = Ridge única** (pipeline, split 70/15/15, baselines, λ por
  validação e métricas inalterados).
- `?model=ridge` é **alias legado**; qualquer outro valor (`ar`, `AR`, `arima`,
  vazio) → **HTTP 400**, sem fallback. Vale para `/api/forecast/:key` e
  `/api/reports/:key[/csv]`.
- Removidos do produto: `backend/src/services/arService.js`, `olsBeta`,
  select `#sel-model`, estado `saden_model` e parâmetro de modelo no frontend.
- `backend/src/utils/linalg.js` contém apenas `solve` (usado pela Ridge).
- **Nada de V2 implementado**; `docs/CONTEXTO_V2.md` é somente roadmap.

## 3. Histórico experimental preservado

`model_runs` é write-only em produção e permanece intacta:

| model | linhas (2026-11-11) |
|---|---|
| `ridge(lambda=0.1)` | 861 |
| `ridge(lambda=1)` | 12 |
| `ridge(lambda=10)` | 5 |
| `ar(order=3)` | 5 |
| `ar(order=1)` | 4 |

Os números crescem a cada previsão Ridge; o histórico AR não é migrado,
renomeado nem reinterpretado. Leitura de `model_runs` não existe em produção.

## 4. Arquitetura real

- Express porta única 3001: `rotas → serviços → integrações → utils`;
  middleware `auth JWT` + `rateLimit`.
- Frontend estático puro (HTML/CSS/JS + Leaflet 1.9.4 + Chart.js 4.4.1 via
  CDN), servido pelo backend.
- SQLite `better-sqlite3`, WAL+FK, **14 tabelas**. Seed idempotente: 5
  commodities + usuário demo `demo@saden.local / saden123` (local/acadêmico).
- Cache: preços/clima 60 min, geo 30 dias (`kv_cache`); HTTP timeout 12 s
  (landcover até 25 s), retry 3× em 502/429, Nominatim throttle 1,1 s.
- Preço = futuro CBOT/ICE × PTAX venda × fator. Sem câmbio → ponto descartado;
  fonte fora do ar → 502 honesto. `fx_fallback_days` declara repetição de PTAX.

## 5. Forecast real

- Ridge própria (Gauss+pivô, padronização, intercepto não penalizado).
- Features só do passado: lag1, lag2, lag5, MM7, MM30, vol14, índice t.
  `WARMUP=30`, `MIN_POINTS=60`, série ~1 ano Yahoo×PTAX.
- Split 70/15/15; MAE/RMSE/MAPE; baselines naive, seasonal_naive_5, ma7;
  λ ∈ {0.1,1,10,100} por RMSE de validação; previsão recursiva H 7|14|30
  (default 14, dias corridos); intervalo ±1,96·σ_val·√h, lower truncado em 0.
- Patrimônio metodológico: na v1.0 (n=252 pregões), Ridge venceu a validação
  em 4/5 e o café foi vencido pelo naive no teste — registrar, não apagar.
- Clima e PTAX são contexto, não features. Land Cover é camada visual, não NDVI.
- **AR(p): investigação encerrada e fora do produto** (E2–E5). Resultados
  históricos em `docs/FORECAST_EVALUATION.md`; não descrevem a V1.

## 6. Fontes

| Fonte | Status |
|---|---|
| Yahoo Finance (futuros) | UTILIZADA |
| BCB/PTAX | UTILIZADA |
| Open-Meteo | UTILIZADA |
| IBGE | UTILIZADA |
| Nominatim | UTILIZADA (throttle+atribuição) |
| Esri/Impact Observatory Land Cover | UTILIZADA como camada visual |
| CEPEA | BLOQUEADA (API por contratação) |
| CONAB | BLOQUEADA (portal com reCAPTCHA) |
| INMET | NÃO INTEGRADA |
| ANTT/frete | REFERÊNCIA manual |
| NDVI/CDSE | ESTUDADA, bloqueada por credencial |

## 7. Segurança

- bcrypt cost 10; JWT 12h; **fail-fast** sem `JWT_SECRET` em produção
  (`config._test.assertProductionSecret`, coberto por teste); rate-limit
  10 req/10 min em auth; SQL parametrizado; reset token sha256 +
  timingSafeEqual + TTL 1h + uso único.
- XSS: `esc()` em strings de usuário/fonte externa antes de `innerHTML` (D20);
  datas/IDs também escapados; E2E cobre autocomplete, local salvo e relatório.
- CSV: anti formula-injection com TAB/CR/LF coberto por unitário.
- CSRF n/a (Bearer, sem cookies). CORS por `FRONTEND_ORIGIN`. CSP ativa.
- Erros 500 sem vazamento; `X-Powered-By` desativado.

## 8. Decisões

- `docs/DECISIONS.md`: **D1–D40** (D40 = congelamento V1 e retirada do AR).
- D38/D39 são registros históricos superados por D40, preservados.
- Segunda opinião (arquivo externo, 940 linhas): fonte de hipóteses, NÃO
  especificação. MAPE futuro (8–10%, 6–8%) é hipótese, nunca resultado.

## 9. Docker (real, 2026-11-11)

`docker compose build` → `saden:rc` (395 MB); `up -d` → `healthy`. Gates:
health, frontend 26.597 bytes sem `sel-model`, auth, Ridge 200,
`model=ar`→400, persistência down/up (861 linhas Ridge e histórico AR intactos),
smoke 9/9 no container, backup 4.472.832 bytes via host, `/app/data` vazio na
imagem e sem `.env`, processo `uid=1000(node)`, `NODE_ENV=production` sem
`JWT_SECRET` lança erro explícito.

Backups dentro do container são efêmeros; usar `node scripts/backup.js` no host.

## 10. Limitações e riscos aceitos (inalterados)

Referência internacional (não físico regional); modelo univariado; clima fora
do modelo; série ~1 ano; val_n 33–35; intervalo gaussiano sem cobertura
empírica; H30 fraco; Land Cover visual; sem teste de carga; sem SMTP real;
instância única, rate-limit em memória; sem TLS, backup automatizado ou
monitoramento. Express 4 com 3 moderadas (D10, body limit 256 kb).

## 11. Próxima etapa

V2 **não iniciada**. Critérios de entrada, escopo candidato, riscos e perguntas
abertas estão em `docs/CONTEXTO_V2.md`. Qualquer reativação do AR ou outro
challenger exige decisão nova, reavaliação e testes próprios.

## 12. Regras de trabalho que evitam regressão

1. Não apagar/renomear histórico em `model_runs` nem `forecasts`.
2. Não usar `git reset --hard`, `git clean -fd` ou force push.
3. Antes de E2E: confirmar PID/porta e versão servida (HTML atual).
4. Não declarar Docker/push/release sem execução e evidência.
5. Não inventar métricas, fontes ou prontidão de produção.
6. `SADEN-TCC` permanece intocado.
