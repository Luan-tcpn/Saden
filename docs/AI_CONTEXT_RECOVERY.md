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

### V2 geoespacial (2026-11-11)

- Branch isolada **`v2/geospatial-foundation`** (de `v1-final`); **sem merge**
  em `main`. Tag/branch de arquivo intactas.
- PoC Sentinel-2 **executada**: 4 cenas L2A reais (jun–set/2025), NDVI/EVI/NDMI
  em grade 20 m, GeoTIFFs + CSV + PNG + manifesto.
- Fonte: Earth Search (Element 84), coleção `sentinel-2-c1-l2a`, anônima.
- Código em `geospatial/` (Python/venv isolado). Estado completo:
  `docs/V2_EXECUTION_STATUS.md`. Decisão: D41.

### V2.1 validação geoespacial (branch `v2/geospatial-validation`)

- Branch nova `v2/geospatial-validation`, derivada de
  `v2/geospatial-foundation` (`2e5b3ef`); checkpoint imutável da PoC na tag
  anotada `v2-poc-sentinel2`. Bundle de segurança verificado em
  `..\SADEN_V2_1_RECOVERY_2026-11-11\`.
- **A** — PoC reexecutada em diretório separado: mesma grade (547×557,
  EPSG:32721) e **diferença 0,0** em todas as estatísticas vs. manifesto
  anterior; auditoria radiométrica confirma `scale=0.0001`, `offset=-0.1`
  idênticos entre metadado STAC e COG, `uint16`, `nodata=0` (sem dupla
  aplicação).
- **B** — Perfil A (histórico) × Perfil B (exclui também classes 2 e 6)
  comparados em 4 cenas reais: B remove 0,10%–0,15% dos pixels e altera a
  média do NDVI em ≤ 0,18%. Decisão **D43**: Perfil A fica na reprodução da
  PoC; Perfil B é o padrão da V2.1.
- **C** — Malha oficial do IBGE (`5107925`, qualidade `maxima`, 2.689
  vértices, válida): 9.293,47 km². A bbox histórica tem **0,51 km² fora** do
  município (99,58% dentro). Decisão **D42**.
- **D** — Mosaico real `21LXG`+`21LXF` do mesmo `datatake` (2023-06-20,
  diferença temporal medida 14,53 s): regra `first_valid_wins`, 779.708 px do
  primário e 192.073 do secundário, 1.191 sem dado; NDVI na sobreposição com
  diferença absoluta média 0,00095 e correlação 0,99999. Decisão **D44**.
- **E** — Série mensal 2023–2025 em andamento/executada; seleção por fração
  obstruída sobre a AOI e lacunas explícitas (decisão **D45**).
- Suíte offline: **95/95** testes; testes de rede separados (4/4 OK, opt-in) em
  `geospatial/tests_external/` (opt-in por `SADEN_EXTERNAL_TESTS=1`).
- Relatório técnico: `docs/V2_1_VALIDATION_REPORT.md`.

## 2. Escopo congelado da V1 (D40)

- **Previsão = Ridge única** (pipeline, split 70/15/15, baselines, λ por
  validação e métricas inalterados).
- `?model=ridge` é **alias legado**; qualquer outro valor (`ar`, `AR`, `arima`,
  vazio) → **HTTP 400**, sem fallback. Vale para `/api/forecast/:key` e
  `/api/reports/:key[/csv]`.
- Removidos do produto: `backend/src/services/arService.js`, `olsBeta`,
  select `#sel-model`, estado `saden_model` e parâmetro de modelo no frontend.
- `backend/src/utils/linalg.js` contém apenas `solve` (usado pela Ridge).
- **Nada da V2 toca a V1**: código geoespacial vive em `geospatial/` (Python,
  não é importado pelo Node) e só existe na branch `v2/geospatial-foundation`.

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
| Sentinel-2 L2A / Earth Search | UTILIZADA na PoC V2 (branch `v2/geospatial-foundation`) |

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

- `docs/DECISIONS.md`: **D1–D45** (D40 = congelamento V1 e retirada do AR;
  D41 = V2 isolada e escopo da PoC Sentinel-2; D42 = geometrias separadas e
  limite municipal oficial; D43 = política de máscara SCL; D44 = regra de
  mosaico e par de tiles por datatake; D45 = seleção mensal da série 2023–2025).
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

**V2.1 concluída** no escopo de pipeline (4 cenas, 4 datas). Estado operacional,
números e pendências em `docs/V2_EXECUTION_STATUS.md`. A V2 **não** está
integrada ao produto e não produz inferência agronômica/econômica.

Próximas ações possíveis (nenhuma iniciada): ampliar janela temporal, buscar
dados observados de produtividade, revisar a PoC com orientador. Qualquer
reativação do AR ou outro challenger de preço continua exigindo decisão nova,
reavaliação e testes próprios.

Pendência externa: GitHub Release `v1-final` bloqueado por falta de
autenticação `gh` (sem token e sem login por navegador). Notas prontas em
`docs/releases/v1-final.md`; tag, `main`, `archive/v1-final` e bundle já
publicados e verificados.

## 12. Regras de trabalho que evitam regressão

1. Não apagar/renomear histórico em `model_runs` nem `forecasts`.
2. Não usar `git reset --hard`, `git clean -fd` ou force push.
3. Antes de E2E: confirmar PID/porta e versão servida (HTML atual).
4. Não declarar Docker/push/release sem execução e evidência.
5. Não inventar métricas, fontes ou prontidão de produção.
6. `SADEN-TCC` permanece intocado.
