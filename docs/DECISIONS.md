# SADEN — Decisões de arquitetura (ADR resumido)

## D1 — Backend Node.js + Express + SQLite (better-sqlite3)
Deploy único, zero-config de banco (arquivo `data/saden.db`), ideal para TCC executável no Windows.
Sem ORM: SQL direto, schema versionado em `backend/src/db.js`.

## D2 — Frontend estático servido pelo backend (porta única 3001)
Vanilla HTML/CSS/JS + Leaflet + Chart.js via CDN. Sem build step.
Motivo: Yahoo Finance não envia CORS → proxy obrigatório via backend de qualquer forma;
porta única elimina problema de CORS do próprio app.

## D3 — Preços = Yahoo futuros + PTAX (referência internacional)
CEPEA e CONAB **não possuem API pública** (verificado em 2026-09-08) → não integráveis sem scraping
frágil/não-autorizado. Alternativa real e testável: futuros CBOT/ICE (Yahoo) × dólar PTAX (BCB).
Limitação declarada em UI, relatórios e `API_SOURCES.md`.

## D4 — Clima = Open-Meteo; localidades = IBGE + geocoding Open-Meteo
Todas públicas, sem chave, verificadas por teste real. Fuso fixo `America/Sao_Paulo`.

## D5 — Previsão = pipeline próprio (ridge + baselines), sem LLM
Features só com passado (lags 1/2/5, MM7/MM30, vol 14, índice). Split temporal 70/15/15.
Grade λ ∈ {0.1, 1, 10, 100} com seleção por RMSE de validação. Intervalo ±1,96σ (alarga √h).
Série mínima de 60 pontos; caso contrário HTTP 422 honesto.

## D6 — Auth JWT + bcrypt; rotas `/api/*` protegidas (exceto health/sources)
Token `Bearer`, expiração 12h. Sem segredo no frontend (`.env` + `.env.example`).

## D7 — Cache em SQLite (`kv_cache`) com TTL
Preços/clima 60min; geografia 30 dias. Toda resposta indica `cached: true/false`.

## D8 — Relatórios: JSON + CSV + impressão (PDF via navegador)
Sem dependência pesada de PDF; CSV com BOM UTF-8 abre no Excel. XLSX adiado (sem necessidade real).

## D9 — Testes: `node --test` sem dependências extras
Unitários (fx, validação, matemática da previsão com série sintética) + integração
(auth, proteção, expiração de token, rate-limit, commodities, fontes + 2 testes live Yahoo/Open-Meteo).

## D10 — Auditoria de dependências (2026-09-08)
`npm audit`: 3 moderadas na cadeia qs→body-parser→express 4. Correção exige major
breaking (Express 5). Decisão: **risco aceito e mitigado** — `express.json({limit:'256kb'})`
reduz a superfície de DoS; app acadêmico local sem exposição pública. Reavaliar se publicar.

## D11 — Rate-limit de auth em memória (2026-09-08)
10 tent./10min por IP em `/login` e `/register` → 429. Suficiente para instância única;
se escalar para múltiplas instâncias, migrar para store compartilhado (ex.: Redis).

## D12 — Performance medida, sem otimização especulativa (2026-09-08)
`scripts/perf-check.js`: warm ≤10ms por endpoint; fluxo dashboard = 9 chamadas em 39ms;
forecast recalcula em ~8ms (série em cache). Cold (1x/hora): dominado pelo upstream (1–3s).
Decisão: **não** criar endpoint único de comparação nem cache de forecast — ganho seria
marginal (~30ms) e adicionaria complexidade. Reavaliar se o uso real mostrar lentidão.

## D13 — Landing + roteador público (rodada 2)
`/` landing, `/login`, `/register`, `/reset`, `/dashboard`; backend serve `index.html`
em todas (fallback já existia); assets com caminho absoluto. Autenticado em rota
pública vai ao app. Ilustração da landing em SVG local (sem dependência externa instável).

## D14 — Recuperação de senha com outbox dev (rodada 2)
Tabela `password_resets` (hash SHA-256, expiração 1h, uso único + invalidação global),
resposta sempre genérica. Sem SMTP configurado, mensagem vai para `tmp/mail-outbox/`
(documentado; `sendViaSmtp` lança 501 até haver provedor). Nenhum e-mail real é alegado.

## D15 — Geocodificação dupla (rodada 2)
Open-Meteo (lugares) + Nominatim (ruas/endereços/reverse, 1 req/s, atribuição OSM),
merge com dedupe por proximidade e ancoragem IBGE. Entrada com cara de coordenada
vai direto ao reverse. Cache 30 dias; valida faixas lat/lon com erro claro.

## D16 — Temas por variáveis CSS (rodada 2)
`data-theme` em `<html>` + `localStorage saden_theme` (light/dark/system via matchMedia).
Dark em verde-grafite (sem neon/preto puro). Gráficos seguem `Chart.defaults` no apply.

## D17 — Fotografia da landing (rodada 3, 2026-09-08)
Imagens fornecidas pelo autor do TCC, copiadas para `frontend/img/` (ativos locais,
sem dependência externa): `hero-pivo.jpg` (pivô + estação meteorológica — hero),
`solucao-soja.jpg` (seção solução), `cta-ceu.jpg` (fundo do CTA com overlay).
Escolha pelo critério "funciona no layout": a do pivô narra monitoramento+dados;
a de céu dramático só com overlay escuro. Hortaliças/colinas dispensada (menos
brasileira/commodity). Origem: acervo do autor — rever licença antes de publicar.

## D18 — Logo satélite (rodada 3, 2026-09-08)
Reinterpretação própria em SVG do satélite orbital (corpo + painéis + antena),
branco sobre o verde atual #2c5f3a (fundo preservado). Sem sparkles/estrelas da
referência. Arquivo único `frontend/img/logo.svg` usado em navbar, auth, sidebar,
landing e como favicon — sem versões divergentes.

## D19 — Refinamento estético da landing (rodada 4, 2026-09-08)
Ritmo por superfícies (tokens --band/--band-warm/--band-deep), sem pintar tudo de
verde: hero → problema (sage + editorial com filete) → solução (warm + foto) →
funcionalidades (card destaque + ícones de linha) → passos (timeline horizontal) →
dados (banda verde-escura) → CTA foto → footer escuro integrado (fade do CTA).
Navbar em grid 1fr/auto/1fr (logo/nav/ações). Microinterações só CSS + reveal único
por IntersectionObserver (respeita reduced-motion). Frase "Sem cartão…" removida.

## D20 — Pós-auditoria FASE A (ciclo autônomo)
XSS: helper `esc()` em todo `innerHTML` do frontend (input, APIs, OSM, erros) —
sem novas dependências. Município: UF+município agora geocodifica de verdade
(com guarda anti-resposta-defasada). Segurança: `X-Powered-By` off, nosniff,
referrer restrito, `frame-ancestors 'self'` e CSP estrita (CDNs allowlist; sem
`unsafe-inline` após extrair tema para `js/theme.js`). JWT: fail-fast em produção
sem segredo. Staleness: "Último dado disponível há N dias" discreto no dashboard.

## D21 — Pós-auditoria FASE B (robustez)
CSV: `csvCell()` anti formula-injection (prefixo TAB + quoting; números/datas
intactos). Reports: GET mantido (sem regressão no frontend/E2E) + retenção dos
500 mais recentes; limpeza de kv expirado, resets +7d e outbox +7d no `connect()`.
SRI calculado dos bytes reais dos CDNs (Leaflet 1.9.4, Chart.js 4.4.1) + crossorigin.

## D22 — Pós-auditoria FASE C (a11y/UX)
Autocomplete com teclado (setas + Enter + Esc + `aria-activedescendant`);
Enter sem sugestão dispara Consultar. Drawer devolve foco ao fechar. Regiões de
status com `aria-live="polite"`. Botão Limpar filtros (restaura padrão + refresh).
Texto explicando o intervalo 95% sob a previsão. Toasts: dispensados de propósito
— status inline contextuais e persistentes já cobrem os fluxos, sem sistema novo.

## D23 — Pós-auditoria FASE D (header integrado)
`.landing-top` transparente no topo e superfície translúcida sutil com blur de 8px
após 24px de scroll (fallback sólido sem `color-mix`). Validado sobre seções
claras, banda verde-escura, foto do CTA e footer — legível em todos.

## D24 — Alertas MVP (FASE E)
Tabelas `alerts` + `alert_events`; kinds `price_below/price_above/rain_above`;
avaliação sob demanda (`POST /check`) com histórico (retenção 500). Sem SMTP real:
notificação = estado DISPARADO na UI + eventos (outbox existente não é e-mail).
Isolamento por usuário testado. Chuva usa a localidade atual do dashboard.

## D25 — Locais salvos + período + variação (FASES F/G)
`user_places` (CRUD por usuário, máx. 50 listados); painel na página do mapa com
salvar/usar/excluir — sem página nova, sem multi-tenant. Período do histórico via
`range` allowlist (1mo/3mo/6mo/1y) no backend; previsão segue com 1y (necessita
histórico mínimo). Comparação em gráfico de barras só da variação % (adimensional;
preços absolutos têm unidades distintas e seriam enganosos em barra única).

## D26 — Preço regional, frete e Land Cover (ciclo territorial, 2026-09-15)
Regional: CONAB (reCAPTCHA — proibido contornar), PGPAF (403/WAF), CEPEA
(Cloudflare), ANTT CKAN (só multas) — nenhuma fonte regional automatizável.
Price Reference Engine implementado com hierarquia honesta (hoje só `nacional`
populado; municipal→região retornam `unavailable` explícito). Frete: sem cálculo
automático (sem fonte estruturada); referência manual ANTT na tabela de fontes.
Land Cover: tiles + legenda + catálogo do ImageServer oficial verificados e
integrados (proxy same-origin com cache); `identify` pixel retorna NoData anônimo
→ sem consulta por ponto e sem estatísticas de área (regra: sem cálculo, sem %).

## D27 — Consolidação (2026-09-15, sem reescrita)
Revalidados: 48/48 testes, XSS fechado (tudo via `textContent`/`esc()`),
headers+CSP, engine honesto ao vivo (milho/MT → nacional com fallback declarado),
CEPEA ainda bloqueada (403 Cloudflare), IMEA sem API pública (axios interno sem
docs → não integrar). Land Cover renderiza (Amazônia/Cerrado/Sul legíveis).
Mantidos: arquitetura, modelo ridge, temas, fluxos. Nada reescrito.

## D28 — Auditoria de valor (2026-09-15, só alto-valor/baixo-esforço)
Land Cover mantida como camada auxiliar (veredito: visualiza contexto real, mas
sem identify não vira análise) + legenda compacta expansível. Relatório agora
traz o nome da localidade (ponte território→documento). TCC.md ganhou Q&A da
banca. Mantidos sem mexer: modelo, temas, fluxos, landing. Adiados de novo:
NDVI, frete automático, RF/GBM, app nativo, microsserviços, RBAC, chatbot.

## D29 — Ecossistema Sentinel-2/Esri (investigação, 2026-09-15)
Serviço L2A (`sentinel.arcgis.com/.../Sentinel2/ImageServer`, 13 bandas, 22
raster functions) responde, mas `identify` e renders com `renderingRule`
retornam NoData/branco anônimos → NDVI/NDMI pontual, perfil temporal e toggles
de render: ADIADOS (exigem credencial). Land Cover: paleta MEDIDA de tiles reais
(8 classes verificadas em âncoras inequívocas; Rangeland sem amostra → sem
swatch, com nota). Swatches via classes CSS (style inline quebraria o CSP).
Nada de change detection, nada de % inventadas.

## D30 — Contexto global vs controles por tela (RC, 2026-09-15)
O form de consulta vivia no topo global e aparecia em Aparência/Fontes/Alertas.
Decisão: barra fina global só-leitura (commodity • local • coords) +
formulário completo só no Dashboard; Alertas/Relatórios ganharam notas de
contexto ("ajuste no Dashboard"). Nenhuma funcionalidade removida, só
realocada. Corrigido de quebra um `provider`/`fx_provider` ausente no payload
do Price Reference Engine (cards mostravam "fonte: ·").

## D31 — Pós-freeze: exibir contexto só onde agrega (2026-09-15)
A barra global foi removida por completo: estado interno continua compartilhado,
mas cada tela mostra só seu próprio contexto. Aprendido: falha do harness E2E
era seletor com nome de classe (`#coord-line` vs id real `#coord-label`) — app
intacto; cache-buster `?e2e=` adotado nos scripts CDP contra 304 falsos.

## D32 — Correção pontual: contexto em Mapa/Relatórios + coords exatas (2026-09-15)
`#map-context` e `#report-context` (compactos: commodity • local • coords) só
nessas telas. Achado real no caminho: reverse geocoding deslocava coords
digitadas (~70 m); agora a análise usa os valores exatos digitados e o rótulo
do reverse serve só para exibição.

## D33 — Restauração do contexto completo (RC final, 2026-09-15)
Decisão revista: linha compacta removida; o MESMO formulário do dashboard é
exibido em Mapa e Relatórios (movido via JS para antes da página ativa —
preserva listeners, valores e estado). Aparência/Fontes/Alertas/Locais seguem
sem form. Estáticos com `no-store` (fim dos 304 falsos/JS obsoleto em dev).
Harness E2E com aba dedicada + cache-buster (nunca mais anexar a aba obsoleta).

## D34 — Dockerização da RC (2026-09-15, só empacotamento)
`node:22-slim`, `npm ci --omit=dev`, usuário `node`, sem secrets na imagem,
`HEALTHCHECK` no `/api/health`, volume `./data:/app/data` (SQLite preservado,
seed não-destrutivo) + `./tmp/mail-outbox` (E2E de recuperação idêntico ao
local). `JWT_SECRET` obrigatório via ambiente (fail-fast). SQLite/Postgres/
Redis/Nginx: nada trocado, nada adicionado. Limitações declaradas: instância
única, sem TLS, sem alta disponibilidade.

## D35 — Champion/Challenger do forecast (regras do jogo, 2026-09-27)
Champion = Ridge v1.0 (travada: features, λ-grade, split 70/15/15, métricas).
Todo challenger (ARIMA, SARIMA, ETS, multivariada) usa MESMA série, MESMO
período, MESMO horizonte, MESMA divisão, MESMAS métricas e MESMA regra
temporal — sem teste na seleção (test só após lock). Gate de leakage para
cada feature exógena: "estaria disponível na origem da previsão?" Se não,
não entra. Ensemble proibido até ≥1 challenger validado individualmente, e
então só com pesos vindos de validação (nunca 0.4/0.3/0.3 arbitrário).
Resultado negativo (challenger pior) é válido e será registrado. Números de
MAPE vindos de fora do projeto são hipótese, nunca meta nem resultado.

## D36 — Correção README/docs obsoletos (2026-09-27, sem reescrita)
`docs/` voltou a fazer parte da árvore versionada (8 arquivos em HEAD), logo
as notas do README sobre "docs ausente" e "build falha por docs ausente"
foram removidas/atualizadas; causa do `COPY docs` eliminada por restauração,
não por remoção da instrução. Criados `docs/AI_CONTEXT_RECOVERY.md` (estado
recuperado, baseline, pendências) e `docs/V1_1_DECISION_MATRIX.md`
(classificação da segunda opinião). Docker build segue pendente de ambiente
com daemon ativo. Nada de funcionalidade alterado.

## D37 - GO condicional ao challenger AR(p) (investigacao E2, 2026-09-27)
Evidencia: AR(p)+AIC vence Ridge na validacao one-step em 5/5 commodities
(margem 16-37%), mesma serie, mesmo split, mesmas metricas; teste so relatado
(ver `docs/FORECAST_EVALUATION.md`). Decisao: implementar AR(p) como challenger
isolado no pipeline JS, SEM substituir Ridge. Gates: (1) mesma serie viva e
mesmo split da Ridge; (2) avaliacao one-step + recursiva H=7/14/30 com intervalo;
(3) sem ensemble; (4) resultado negativo mantem Ridge e e registrado. ARIMA com
termos MA/sazonalidade continua nao testado. Script da investigacao em `tmp/`
(nao versionado); metodo reproduzivel documentado no FORECAST_EVALUATION.md.

Resultado E3 (2026-09-27): challenger implementado (`arService.js` + `linalg.js`,
Ridge com comportamento inalterado) e avaliado em dados reais — AR vence Ridge
no one-step E no recursivo H=7/14/30 nas 5 commodities (ver FORECAST_EVALUATION.md).
Veredito: AR APROVADO como challenger; Ridge CONTINUA champion; exposicao em
rota/persistencia = proxima decisao (D38). Sem ensemble. ARIMA segue nao testado.

## D38 - Exposicao do AR challenger: parametro opt-in (investigacao, 2026-09-27)
Contexto: E3 aprovou AR(p)+AIC como challenger; Ridge segue champion; sem rota.
Alternativas avaliadas: (A) manter interno; (B) `?model=ar` opt-in no endpoint
existente; (C) endpoint `/compare`; (D) seletor no dashboard. Decisao: **B**,
com Ridge como default. Fundamentos: menor superficie (query param aditivo,
contrato atual preservado); mesmo formato de payload (`model` distingue);
persistencia sem migracao (`model_runs.model='ar(order=N)'`, tabela ja
generica e write-only); reversivel (remover o parametro); sem UI nesta etapa
(evita redesenho e E2E prematuro; UI comparativa = decisao futura).
Limites honestos mantidos: H30 fraco bilateral, val_n pequeno, historico nao
garante futuro; CSV passa a identificar o modelo em vez de `lambda` fixo.
Implementacao, testes e numero de suíte ficam para o ciclo seguinte; nada de
codigo alterado nesta investigacao. ARIMA/ensemble seguem fora.

Resultado E4 (2026-09-27): implementado `runFor` (fonte única; Ridge default),
persistência partilhada `persistRun` (Ridge byte-idêntica), CSV por modelo,
7 testes de rota/persistência/CSV + 1 unitário (suíte 77/77). Default
provado idêntico (`model=ridge` deep-equal à ausência). Sem frontend.
