# SADEN — Estado do projeto

Atualizado em **2026-09-08**. Legenda: DONE · PARTIAL · BROKEN · BLOCKED · NOT_STARTED.

## Funcionalidades

| Item | Estado | Evidência |
|---|---|---|
| App inicia (backend+frontend porta 3001) | DONE | `GET /api/health` → ok; PID ativo |
| Arquitetura limpa (frontend↔backend separados) | DONE | `docs/ARCHITECTURE.md` |
| Banco SQLite + schema + seed | DONE | `backend/src/db.js`; tabelas criadas em `data/saden.db` |
| Auth (registro/login/sessão/proteção/logout) | DONE | testes integração 8/8; validado via curl |
| Preços reais (Yahoo + PTAX, cache, rastreio) | DONE | soja R$ 148,33/sc em 2026-09-08; teste LIVE passa |
| Clima real (Open-Meteo 7d + histórico) | DONE | teste LIVE passa; 7 dias Ribeirão Preto |
| Localização (IBGE + geocoding + âncora IBGE) | DONE | "Ribeirão Preto" → lat/lon + ibge 3543402 |
| Dashboard (filtros reais, histórico, métricas, comparação) | DONE | validado no navegador: KPIs, gráficos e troca de commodity funcionam |
| Mapa do Brasil (Leaflet OSM + Esri satélite, clique → dados) | DONE | validado: marcador + popup + painel com preço e clima reais; legenda adicionada |
| Pipeline previsão (ridge + 3 baselines, split temporal, intervalo) | DONE | soja: MAPE teste 1,95%, ridge vence baselines |
| Avaliação de modelos (MAE/RMSE/MAPE treino/val/teste) | DONE | tabela no dashboard + payload |
| Relatórios (JSON + CSV + impressão/PDF) | DONE | validado via curl (265 linhas CSV milho) |
| Testes (21 unit + 12 integração) | DONE | `npm test` verde (46/46), smoke 8/8, E2E 41/41 |
| Segurança (bcrypt, JWT, validação, CORS, rate-limit, sem segredo no front) | DONE | 25/25 testes; audit: 3 moderadas com risco aceito (D10) |
| Performance/cache | DONE | warm ≤10ms/endpoint, dashboard 39ms; sem otimização especulativa (D12) |
| Refinamento visual | DONE | identidade agro validada desktop+mobile; a11y básica ok |
| Doc TCC (fontes, metodologia, limitações) | DONE | `docs/TCC.md` com resultados reais das 5 commodities |
| Landing pública + roteador (/login /register /reset) | DONE | E2E navegador: landing→cadastro→app→logout; ilustração SVG local |
| Recuperação de senha | DONE | token uso único 1h, resposta genérica, outbox dev; SMTP documentado como pendência externa |
| Localização robusta | DONE | cidade/rua/coords + autocomplete aplicável + reverse + Minha localização; E2E 20/20 |
| Aparência (light/dark/system) | DONE | persistente, gráficos adaptados, validado com reload |
| Responsividade 320–1440 | DONE | drawer mobile, tabelas com scroll, mapa e filtros adaptados; overflow 0 medido |
| Landing profissional (foto + narrativa + footer) | DONE | hero pivô/meteorologia, 7 seções, footer completo sem links falsos; light/dark/mobile validados |
| Logo satélite + favicon | DONE | SVG próprio (verde #2c5f3a preservado) em navbar/auth/app/landing/favicon |
| Refinamento estético landing | DONE | ritmo por superfícies, navbar centralizada, hero com fade, timeline, banda dados, footer integrado; frase removida |
| Segurança pós-auditoria (FASE A) | DONE | esc() anti-XSS global, CSP+headers, JWT fail-fast prod, município geocodificado, staleness discreto |
| Robustez (FASE B) | DONE | csvCell anti-fórmula, retenção reports/eventos 500, prune, SRI nos CDNs |
| A11y/UX (FASE C) | DONE | teclado no autocomplete, foco drawer, aria-live, Limpar filtros, intervalo explicado |
| Header integrado (FASE D) | DONE | transparente no topo, superfície sutil no scroll; validado claro/escuro/foto |
| Alertas MVP (FASE E) | DONE | price_below/above + rain_above, CRUD, check sob demanda, histórico, isolamento; E2E |
| Locais salvos + período + variação (F/G) | DONE | user_places no mapa, range allowlist, gráfico de variação %; E2E |
| NDVI (FASE H) | ESTUDO | viável via Sentinel-2/CDSE, bloqueado por credencial — docs/NDVI_STUDY.md |
| Testes | DONE | 48/48 (`npm test`), smoke 8/8, E2E navegador 44/44 |
| Preço territorial (engine + fallback) | DONE | hierarquia honesta (nacional populado; regional `unavailable` explícito); badge no dashboard |
| Frete | REFERÊNCIA | sem fonte estruturada; sem cálculo automático; link/manual na tabela de fontes |
| Mapa agrícola Land Cover | DONE | camada Sentinel-2 10m opcional + legenda PT + atribuição; sem ponto/% (identify exige credencial) |
| Consolidação (revalidação completa) | DONE | 48/48, smoke 8/8, E2E 44/44; XSS/headers/engine revalidados; CEPEA/IMEA rechecados e mantidos bloqueados |
| Valor (legenda compacta, relatório c/ local, Q&A banca) | DONE | E2E 46/46; Land Cover como auxiliar; nada reescrito |
| Contexto por tela (RC) | DONE | form completo em Dashboard/Mapa/Relatórios; resto limpo; coords exatas; E2E 53/53; overflow 0 |
| Roadmap granular | DONE | `docs/PROJECT_ROADMAP.md` é o plano oficial de execução |
| Auditoria final (P14→P19) | DONE | 29/29 testes, smoke 8/8, visual sem erros, docs coerentes — ver roadmap |

## Problemas conhecidos

1. Servidor roda como processo manual (`Start-Process`, PID volátil) — sem serviço/systemd.
2. `priceService` descarta pregões sem PTAX correspondente (raro; fim de semana) — comportamento intencional, contado em `fx_fallback_days`.
3. Previsão usa datas futuras em dias corridos (não só dias úteis) — declarado em `limitations`.
4. Validação visual P14 concluída (Edge headless + CDP): auth, dashboard, filtros, mapa interativo, relatório — zero erros console/rede. Evidências em `tmp/shots/`.
5. Comparação do dashboard dispara N chamadas `latest` (N+1) — candidato a endpoint único (P16).
6. Forecast recalcula a cada chamada (sem cache) — candidato a cache (P16).

## APIs

Ver `docs/API_SOURCES.md` e `GET /api/sources`. CEPEA/CONAB: BLOCKED (sem API pública).

## Ambiente

Node 22, `backend/node_modules` instalado, `.env` a partir de `.env.example`, banco em `data/saden.db`.
Servidor: `node backend/src/index.js` (ou `npm start` em `backend/`). Testes: `npm test` em `backend/`.
Smoke E2E: `node scripts/smoke-test.js`.

## Próximas prioridades (ver roadmap oficial)

1. Uso real de demonstração (apresentar; coletar feedback de orientador).
2. Endpoint único de comparação e cache de forecast somente se o uso justificar (D12).
3. Convênio de dados para preço físico regional (CEPEA/CONAB) como trabalho futuro.
