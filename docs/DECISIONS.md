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

## D39 - Seletor Ridge/AR no dashboard (IMPLEMENTAR, escopo mínimo, 2026-09-27)
Investigação D39 avaliou A (nada), B (seletor opt-in), C (comparação sob demanda),
D (seção resumida). Veredito: **B**. Fundamentos: valor real (transparência
champion×challenger no produto + framing honesto), custo mínimo (1 select nativo,
+1 fetch só no opt-in, sem endpoint novo, sem CSS novo, sem modal), mobile e
a11y herdados do select nativo (teclado/leitor gratuitos), reversível (remover o
select), E2E cobre (toggle + subtitle). D12 reafirmada: sem endpoint de comparação
(o 2º fetch é client-side e só no opt-in). Framing: "Ridge (principal)" default,
"AR (experimental)" + nota curta (passado ≠ futuro; H30 fraco bilateral). Sem D40
(só se surgir nova decisão técnica real).

Resultado (2026-09-27): implementado exatamente no escopo (select nativo no
topbar + `Api().forecast(key,h,model)` + subtitle/métricas/nota por modelo +
`localStorage saden_model` + reset no Limpar; sem CSS novo, sem endpoint novo,
relatórios inalterados). E2E 57/57 (53 + 4 checks D39) em Edge headless.
Incidente: servidor órfão pré-edit sobrevivendo entre sessões serviu HTML
obsoleto e quebrou 3 checks — causa identificada (Start-Process sobrevive a
`Remove-Job`; doravante verificar versão servida + matar por PID). Sem D40.

## D40 — V1 congelada: metodologia única (Ridge) e AR retirado do produto (2026-11-11)

Contexto: a v1.1 expôs o challenger AR(p)+AIC por `?model=ar` (D38) e um
seletor Ridge/AR no dashboard (D39). A avaliação experimental permanece
registrada em `docs/FORECAST_EVALUATION.md`, mas o produto não deve oferecer
duas metodologias com suporte implícito nem sugerir que o AR é uma opção
estável de operação.

Decisão (escopo congelado da V1):
- A única metodologia operacional de previsão é a **Ridge original**, com o
  mesmo pipeline, split temporal, baselines e métricas já validados. Nenhum
  parâmetro novo de modelo.
- `?model=ridge` é aceito apenas como **alias legado explícito**; qualquer
  outro valor (`ar`, `AR`, `arima`, vazio, desconhecido) retorna **HTTP 400**
  com mensagem honesta, sem fallback silencioso.
- `arService.js`, `olsBeta` e o select `#sel-model` foram removidos;
  `backend/src/utils/linalg.js` mantém apenas `solve` (usado pela Ridge).
- O histórico persistido **não é apagado, renomeado nem reinterpretado**:
  linhas `model_runs.model='ar(order=N)'` continuam legíveis como registro
  histórico do experimento; novos runs gravam apenas `ridge(lambda=…)`.
- UI, relatórios JSON/CSV, smoke e E2E refletem a metodologia única.
- Segurança: gate fail-fast de `JWT_SECRET` em produção extraído para função
  testável (`_test.assertProductionSecret`); escapes adicionais em campos de
  data/ID; `fx_fallback_days` exposto em `getLatest` para declarar repetição
  de PTAX na UI.

Consequências: superfície menor (uma metodologia), contrato explícito para
parâmetros legados e histórico auditável preservado. **D38 e D39 passam a ser
registros históricos superados por esta decisão; não são apagados.**

## D41 — V1 congelada e V2 geoespacial isolada; escopo da PoC Sentinel-2 (2026-11-11)

Contexto: a V1 está encerrada (D40) e precisa continuar recuperável enquanto a
V2 explora uma nova dimensão agronômica/geoespacial. Misturar as duas na mesma
branch/tag tornaria a V1 refém de experimentos e dificultaria auditoria.

Decisão:

1. **Fronteira de código e histórico.** `main`, a tag `v1-final` e a branch
   `archive/v1-final` permanecem em `3f7ad33`. Todo o trabalho da V2 vive na
   branch `v2/geospatial-foundation`, derivada de `v1-final`, e **não** é
   integrado à V1 nesta missão.
2. **A V1 não muda de comportamento.** Nenhum arquivo de backend/frontend,
   endpoint, método de previsão ou schema é alterado pela V2. A Ridge continua
   sendo a única metodologia operacional.
3. **PoC V2.1 = Sentinel-2 L2A apenas.** Escopo: descoberta STAC, leitura de
   COG remoto com recorte, cálculo local de NDVI/EVI/NDMI, máscara SCL,
   GeoTIFFs, série tabular, prévia PNG, testes sintéticos e manifesto de
   proveniência. Ficam fora: UI/dashboard, integração ao produto, modelo de
   preço, modelo de produtividade, outros satélites e serviços pagos.
4. **Fontes.** Somente dados públicos e gratuitos, sem cartão, trial ou
   credencial privada. Fonte escolhida e verificada em execução real: Earth
   Search (Element 84), coleção `sentinel-2-c1-l2a`, acesso anônimo.
5. **AOI.** Malha municipal oficial do IBGE (Sorriso-MT, `5107925`) e uma
   janela técnica de `0,10° × 0,10°` dentro do município. A janela **não** é
   talhão, fazenda ou amostra representativa; o município não é tratado como
   uma lavoura única.
6. **Honestidade de resultado.** Índices não são produtividade nem preço.
   Nenhuma inferência agronômica/econômica será feita sem dados observados e
   protocolo próprio. Ausência de dados reais não será preenchida com valores
   sintéticos apresentados como reais.
7. **Reprodutibilidade.** Ambiente Python isolado (`geospatial/.venv`) com
   versões pinadas; suíte padrão offline com rasters sintéticos; teste de rede
   separado; artefatos grandes fora do Git.

Alternativas descartadas: (a) implementar V2 em `main` — risco direto à V1
congelada; (b) usar CDSE/Sentinel Hub — exige credencial; (c) usar serviço
comercial (ex.: EOSDA) — custo/cartão e dependência externa; (d) partir para
série longa e múltiplas fontes — escopo excessivo para a primeira prova.

Critério de aceite da V2.1: fonte pública acessível, AOI com origem
documentada, ≥1 cena real processada, três índices com bandas/escala/CRS
documentados, máscara verificável, estatísticas plausíveis, testes sintéticos,
saída visual e série tabular reproduzível. Resultado real registrado em
`docs/V2_EXECUTION_STATUS.md`.

Consequências: V1 recuperável e congelada; V2 começa pequena, auditável e
descartável, sem prometer produção, produtividade ou melhoria de preço.

## D42 — Três geometrias separadas e limite municipal oficial (2026-11-11)

Contexto: a PoC usava uma bbox técnica de `0,10° × 0,10°` e provava apenas que
o **centroide** estava dentro de Sorriso-MT. Isso não permite afirmar que a
área é municipal. Sem geometria oficial, qualquer número espacial da V2 seria
ambíguo.

Decisão:

1. **Malha oficial do IBGE** (`5107925`, Sorriso-MT), qualidade `maxima`
   (2.689 vértices, Polygon, topologicamente válida), CRS de origem
   `EPSG:4326`. Área: 9.293,46 km² (geodésica WGS84) e 9.293,47 km² em
   projeção de área igual `EPSG:6933`. Fonte, URL e data de acesso ficam no
   manifesto de execução.
2. **Três geometrias, três papéis** — e nunca misturados:
   - `municipality`: limite oficial (referência territorial);
   - `historical_aoi`: bbox `[-55.6509, -12.74385, -55.5509, -12.64385]`,
     preservada **sem alteração** para reprodução da PoC;
   - `validation_aoi`: recorte de `0,06°` dentro do município e da faixa de
     sobreposição dos tiles `21LXG`/`21LXF` (43,26 km²; ~108.140 px a 20 m).
3. **Interseção quantificada**: a bbox histórica tem 120,16 km²; 119,65 km²
   (99,58%) estão dentro do município e **0,51 km² estão fora**. Portanto a
   bbox histórica **não** é área municipal e passa a ser tratada como recorte
   técnico parcial; a análise municipal usa o polígono oficial.
4. **Custo do município inteiro é estimado, não executado**: 9.293 km² a 20 m
   ≈ 23,2 milhões de px/banda (≈ 93 MB float32 por banda e por data; ≈ 465 MB
   para as 5 bandas de uma data). A missão usa AOIs controladas; o município
   inteiro fica para uma fase própria, com janelas/blocos.
5. Nenhuma AOI é declarada como talhão, fazenda, lavoura ou amostra
   representativa da produção municipal.

Alternativas descartadas: (a) manter a bbox e chamá-la de "área municipal" —
contradição com a medição; (b) derivar o limite por geocodificação de nome —
proibido, perde precisão e não é oficial; (c) processar o município inteiro
para "fechar" a área — desproporcional ao objetivo e ao custo estimado.

Consequências: qualquer estatística espacial da V2 declara qual geometria
usou; a reprodução da PoC continua bit a bit idêntica; aclaims de
"município de Sorriso" passam a exigir recorte por polígono.

## D43 — Política de máscara SCL: Perfil A preservado, Perfil B como padrão da V2.1 (2026-11-11)

Contexto: o checkpoint B comparou, em 4 cenas reais (jun–set/2025, AOI
histórica, 304.679 px/cena), a máscara histórica (**Perfil A**: exclui
`0,1,3,7,8,9,10,11`) com uma máscara restritiva (**Perfil B**: A + classes
`2` e `6`). O comentário antigo do código chamava a classe 2 de "vegetação
muito baixa"; a tabela oficial (Copernicus Data Space / Sentinel Hub S2L2A,
consultada em 2026-11-11) define `2 = Dark Area Pixels` e `6 = Water`.

Fatos medidos (cena 2025-06-09, demais idênticos em tendência):

| Classe | Pixels | % da cena | NDVI médio | NDVI mediana |
|---|---|---|---|---|
| 2 — Dark area pixels | 106 | 0,035% | 0,319 | 0,322 |
| 4 — Vegetation | 221.105 | 72,57% | 0,726 | 0,780 |
| 5 — Bare soils | 82.934 | 27,22% | 0,295 | 0,303 |
| 6 — Water | 365 | 0,120% | **−0,196** | **−0,288** |
| 7 — Clouds low prob./Unclassified | 169 | 0,055% | 0,241 | 0,238 |

Efeito do Perfil B sobre o NDVI da AOI: −317 a −471 px (0,10%–0,15% do
total), média da cena +0,00025 a +0,00107 (≤ +0,18% relativo), mediana
+0,00004 a +0,00068. Nenhum pixel passa de inválido (A) para válido (B).

Decisão:

1. **A semântica vence a conveniência.** Água (NDVI médio −0,196) e dark area
   (heterogênea, p25 0,028 / p75 0,662) não são sinal de vegetação; incluí-los
   em uma estatística de índice de vegetação mistura superfícies diferentes e
   injeta valores negativos que podem ser lidos como "estresse" sem base.
2. **Perfil A permanece** como regra da reprodução da PoC (`run_poc.py` e
   `pipeline.run`), para que a baseline histórica continue exatamente
   reproduzível (delta 0,0 em todas as estatísticas, ver
   `docs/V2_1_VALIDATION_REPORT.md`).
3. **Perfil B passa a ser o padrão da V2.1** (`config.V2_1_SCL_PROFILE`) nos
   produtos novos (mosaico e série temporal), por ser semanticamente correto
   para índices de vegetação com custo de cobertura desprezível (≤ 0,18% de
   mudança na média).
4. A mudança é **explícita e versionada** (esta decisão), não silenciosa; os
   perfis permanecem parâmetros internos de processamento — não há seletor na
   interface do produto.
5. **Limitações que mantêm a decisão revisável**: (a) a evidência vem de 4
   cenas sem nuvem em uma única AOI e uma estação; (b) a classe 2 pode conter
   vegetação genuinamente escura, então excluí-la pode remover pixels
   válidos; (c) a classe 5 ("bare soils") provavelmente inclui áreas
   cultivadas — o SCL não é classificador de cultura —, e ela **continua
   válida** nas duas máscaras, de modo que as médias da AOI ainda misturam
   superfícies diferentes.

Alternativas descartadas: (a) manter A por compatibilidade e registrar a
inconclusão — a evidência quantitativa e semântica é suficiente para decidir;
(b) adotar B também na PoC — quebraria a reprodução exata da baseline.

Consequências: a máscara padrão da V2.1 é reproduzível e auditável; a PoC
segue reproduzível; a decisão pode ser reaberta com mais cenas (inclusive
com nuvem), onde a classe 2/3 pesa mais.

## D44 — Mosaico de dois tiles: primeiro válido vence, par definido por datatake (2026-11-11)

Contexto: a PoC nunca demonstrou continuidade entre tiles. Tiles adjacentes
`21LXG` (norte) e `21LXF` (sul) têm **tempos de sensoriamento próprios**
(diferença medida de 14,53 s na aquisição usada), embora pertençam ao mesmo
`datatake` — agrupar por timestamp exato perderia todos os pares.

Decisão:

1. **Critério de par**: mesmo `s2:datatake_id` (mesma passagem de aquisição) e
   mesmo `grid:code` distinto (`21LXG`/`21LXF`). A diferença temporal
   medida é **registrada no manifesto**; nenhuma cena de data diferente é
   combinada.
2. **Regra de mosaico**: `first_valid_wins` com prioridade explícita
   `21LXG > 21LXF`, sem média entre tiles sobrepostos. O mapa de origem por
   pixel é gravado em GeoTIFF (`0=21LXG`, `1=21LXF`, `-1=sem dado`).
3. **Grade única e forçada**: a grade vem do tile primário e é reaplicada ao
   secundário, garantindo alinhamento exato de pixel; grades divergentes
   geram erro explícito (`mosaic.mosaic_grids`).
4. **AOI de mosaico** (`[-55.70, -12.78, -55.50, -12.62]`) foi definida para
   conter área exclusiva de cada tile **e** a faixa de sobreposição — sem
   isso a regra de prioridade nunca seria exercida (com 100% de sobreposição
   o secundário nunca contribui).
5. A diferença de reflectância na sobreposição é **quantificada antes** da
   regra (médias, RMSE e correlação por banda e por índice) e não é
   "diluída" por média.

Alternativas descartadas: (a) média na sobreposição — mistura origens e
esconde a diferença entre tiles; (b) pareamento por `datetime` exato — não
existe para tiles adjacentes; (c) unir tiles de datas diferentes — proibido
sem justificativa temporal explícita.

Consequências: a continuidade espacial é demonstrável e auditável; o custo é
uma diferença de reprocessamento entre tiles pequena e **declarada**, não
oculta.

## D45 — Série mensal 2023–2025: seleção por qualidade sobre a AOI e lacunas explícitas (2026-11-11)

Contexto: a PoC tinha 4 datas de uma estação. Uma série exploratória de 36
meses exige critério de seleção explícito; `eo:cloud_cover` descreve o **tile
inteiro** e não a área de interesse. Meses sem observação não podem ser
preenchidos (seria fabricar dado científico).

Decisão:

1. **Unidade e escopo**: 1 cena por mês sobre a AOI de validação
   (`0,06°`, 43,26 km²), grade única de 20 m em `EPSG:32721`
   (329 × 334 px), tile `MGRS-21LXG` em toda a série (comparabilidade), Perfil B
   de máscara (D43) e conversão radiométrica idêntica em todos os meses.
2. **Critério de seleção**: menor **fração obstruída sobre a AOI** (classes SCL
   de nuvem/sombra/saturado/nodata — 0, 1, 3, 7, 8, 9, 10, 11), avaliada
   lendo o SCL real da cena; desempate por `eo:cloud_cover` do tile e depois
   por `item_id` (seleção determinística). Até 4 candidatas por mês são
   avaliadas.
3. **Limite de qualidade**: obstrução > 0,50 → mês marcado
   `no_usable_observation` **com o motivo e a melhor candidata registrada**.
4. **Sem preenchimento**: meses sem observação ficam vazios no CSV e no
   gráfico (quebra de linha e cobertura zerada). Não há interpolação, cópia
   do mês anterior, média nem composição rotulada como aquisição única.
5. **Registro por mês**: item STAC, data/hora real, baseline, nuvem do tile,
   obstrução na AOI, pixels válidos, cobertura, área válida, média, mediana,
   desvio e quantis p5/p25/p75/p95 por índice.
6. **Comparabilidade**: a série registra a mudança de baseline
   (05.09 → 05.10 → 05.11). Todos os baselines têm `scale = 0.0001` e
   `offset = −0.1`, portanto **não há quebra de método**; se um baseline
   incompatível aparecer, o item é bloqueado e o mês vira lacuna.
7. **Sem leitura agronômica**: a série é espacial-temporal. Sazonalidade de
   índice não é produtividade, saúde de lavoura ou previsão de safra sem uso
   do solo identificado e dado independente.

Alternativas descartadas: (a) selecionar só por `eo:cloud_cover` do tile —
demonstradamente inadequado (em 2023-04 o tile tinha 65% de nuvem e a AOI
apenas 3% de obstrução); (b) preencher meses com médias/análise harmônica —
fabricaria observações; (c) composição multi-cena por mês — aumenta a
complexidade e mascara a data real da observação; (d) variar de tile entre
meses — quebraria a comparabilidade radiométrica e espacial da série.

Consequências: a série 2023–2025 é reproduzível, auditável e honesta nas suas
lacunas; ela ainda **não** sustenta nenhuma afirmação agronômica.

## D46 — IBGE/SIDRA (PAM 5457) como base observada de referência; CONAB como contexto (2026-11-11)

Contexto: a V2.2 precisava de dados **observados** de produtividade para
relacionar com os indicadores Sentinel-2 da V2.1. Duas instituições foram
investigadas diretamente (sem serviço pago, sem credencial, sem contorno de
bloqueio).

Fatos verificados em 2026-11-11:

| | IBGE/SIDRA (PAM 5457) | CONAB (Boletim de Safras) |
|---|---|---|
| Acesso | API pública, sem chave, HTTP GET | planilhas oficiais no portal; sem API |
| Granularidade | **município** (N6) | **UF** e nacional |
| Periodicidade | anual, **1974–2025** | por **safra**, ~2 safras por boletim |
| Variáveis | área plantada/colhida, quantidade, rendimento médio, valor | área, produtividade, produção |
| Natureza | **observada** (coleta municipal) | **estimada** (levantamento, revisada) |
| Cobertura municipal de Sorriso | soja, milho, algodão (café e trigo = 0) | — (estadual) |

Decisão:

1. **A base observada de referência é o IBGE/SIDRA**, tabela 5457 (PAM),
   acquired por consulta reproduzível, com resposta bruta versionada,
   manifesto com URL/parâmetros/checksum e convenções de valor do IBGE
   (`..` ausente, `-` zero, `...` não aplicável, `x` suprimido).
2. **A CONAB entra como camada de contexto estadual e safras**, com origem
   (levantamento) e revisão registradas em cada linha. Ela **não** substitui
   o IBGE: mesma variável com Periodicidade, método e natureza diferentes.
3. Nenhuma fonte foi rasterizada, interpolada ou reescalada para a AOI.

Alternativas descartadas: (a) usar CONAB como base principal — granularidade
estadual e estimativas revisadas; (b) usar a base do IBGE/SIDRA em outro
nível geográfico — municipal é o mais fino disponível e é o que contém a AOI;
(c) comprar base privada com resolução de talhão — proibido nesta missão.

Consequências: existe uma base real, observada, rastreável e reproduzível;
suas limitações são de **escala e tempo**, não de acesso.

## D47 — Compatibilidade espacial classificada em A/B/C; proibido atribuir produtividade municipal à AOI (2026-11-11)

Contexto: a AOI de validação tem 43,26 km² e está 100% dentro do município de
Sorriso (9.293,47 km²), ou seja, **0,4654%** da área municipal (medido com
geometria real e projeção `EPSG:6933`, como na V2.1/D42).

Decisão:

1. Classificação de compatibilidade espacial, aplicada a **cada combinação**
   (fonte × cultura × período × unidade territorial):
   - **A — direta**: observação na mesma unidade espacial do indicador
     geoespacial (propriedade/talhão);
   - **B — contextual**: unidade territorial maior que contém a AOI (município),
     útil como contexto municipal;
   - **C — incompatível**: escala que impede associação válida na AOI.
2. Resultado aplicado: **IBGE/PAM = B** (municipal) e **CONAB = C** (estadual)
   para a AOI. **Nenhuma fonte oficial investigada atinge a classe A.**
3. É **proibido** rasterizar a produtividade municipal para a AOI, "distribuir"
   o valor municipal pelos pixels da AOI ou apresentar estatística municipal
   como *ground truth* da AOI.
4. A geometria oficial do município e a AOI de validação permanecem as da
   V2.1 (D42); a compatibilidade é calculada por interseção real, não por
   bounding box.

Consequências: o estudo futuro, se autorizado, é na escala que os dados
suportam; a escala fina (AOI/talhão) permanece explicitamente em aberto.

## D48 — Licenciamento: planilhas da CONAB fora do Git; dados do IBGE versionados (2026-11-11)

Contexto: os termos de uso da CONAB não foram obtidos em forma verificável
nesta etapa, e o acesso oficial é por planilha publicada no portal (sem API
automatizável). A pendência anterior sobre a divergência entre o `license:
proprietary` do catálogo STAC da Earth Search e o "free, full and open" do
Registry of Open Data on AWS **continua aberta** e não é tratada como
resolvida.

Decisão:

1. Dados do **IBGE/SIDRA** (domínio público, sem chave) são **versionados**:
   resposta bruta da API, base normalizada e manifestos.
2. **Planilhas da CONAB não são versionadas**: ficam em `data/raw/conab/`
   (ignorado pelo Git). O manifesto registra **URL exata, tamanho e SHA-256**
   de cada arquivo, garantindo reprodução e verificação de integridade sem
   redistribuir o material sob termos não verificados.
3. A pendência de licenciamento é registrada como **aberta**; nenhuma
   afirmação de "livre para redistribuir" é feita para CONAB ou Sentinel-2.

Consequências: reprodutibilidade preservada sem redistribuição indevida; a
questão de termos de uso permanece na lista de pendências.

## D49 — Culturas-piloto: soja e milho; algodão condicionado; café e trigo descartados (2026-11-11)

Contexto: o catálogo do SADEN tem cinco commodities (soja, milho, café arábica,
trigo, algodão). A escolha da cultura-piloto precisa de disponibilidade real,
não de semelhança de nome.

Decisão:

| Commodity | Correspondência IBGE | Correspondência CONAB | Decisão |
|---|---|---|---|
| Soja | **exata** (40124 Soja em grão) | exata (`SOJA`) | **piloto** |
| Milho | **exata** (40122 Milho em grão) | exata (`MILHO TOTAL`) | **piloto** |
| Algodão | **parcial** (40099 em **caroço**) | **parcial** (pluma e caroço) | piloto **condicionado**: só com o pluma (referência do SADEN) ou conversão documentada |
| Café arábica | equivalente c/ ressalvas (grão não torrado) | equivalente c/ ressalvas | **descartado**: produção municipal zero em 2013–2025 |
| Trigo | exata | exata | **descartado**: produção municipal zero em 2013–2025 |

Regras aplicadas:

1. Correspondência declarada por **código oficial** (IBGE) e por **rótulo
   exato** (CONAB) — nunca por semelhança textual.
2. Cada vínculo carrega a classe (`exact`, `equivalent_with_caveats`,
   `partial`, `none`) e a ressalva técnica.
3. Culturas sem produção municipal observada não entram como piloto, ainda
   que constem do catálogo do SADEN.
4. Produtos fora do catálogo do SADEN permanecem na base com
   `match_class = none` (não são eliminados).

Consequências: duas culturas com observação municipal real e correspondência
exata são o ponto de partida de qualquer estudo futuro; a exclusão de café e
trigo fica documentada com o dado que a sustenta.

## D50 — Perfil radiométrico histórico: C1 harmonizada + coleção original com convenção de DN verificada (2026-11-11)

Contexto: a V2.1 usa `DN * 0.0001 - 0.1` (baseline ≥ 04.00). Para estender a
série a 2017–2025 era preciso provar comparabilidade radiométrica entre
produtos de baselines diferentes, **sem** inventar transformações.

Fatos verificados em 2026-11-11:

1. **Coleção C1** (`sentinel-2-l2a` → `sentinel-2-c1-l2a`, Earth Search):
   reprocessamento harmonizado da ESA; **todos** os assets declaram
   `scale = 0.0001`, `offset = -0.1`, independentemente do baseline
   (05.00 para 2017–2021; 05.09/05.10/05.11 de 2022 em diante). Cobertura
   2017–2025 com **lacunas de ingestão**: 2017 com 1 data e 2022 com 5 datas.
2. **Coleção original** (`sentinel-2-l2a`): cobertura completa 2017–2025
   (56 itens em 2017, 170 em 2018, 145 em 2022, 206 em 2025). O catálogo
   declara `offset = -0.1` para todos, **mas** o DN armazenado é exatamente
   **1000 unidades menor** (0,1 de reflectância) do que o offset declara —
   inconsistência de catálogo comprovada por leitura direta dos COGs.
3. **Experimento pareado** (6 datas, 2018–2025, mesma grade, ~109.700 pixels
   válidos por par): aplicando `DN * 0.0001` aos produtos originais e
   `DN * 0.0001 - 0.1` à C1, a diferença de NDVI é **0,0** e a correlação é
   **1,0** em todos os pares.

Decisão:

1. O pipeline da **V2.1 permanece intocado** (Perfil A/B, máscara SCL, mosaico,
   série 2023–2025, manifests). O tratamento histórico é um **perfil
   separado**, com manifesto e testes próprios (`geospatial/historical/`).
2. Perfil **C1 harmonizada**: `DN * 0.0001 - 0.1`, uniforme.
3. Perfil **original (convenção de DN verificada)**: `DN * 0.0001`, para todo o
   arquivo — comportamento idêntico ao da C1, comprovado pelo experimento
   pareado. A divergência entre o offset declarado e o dado real é registrada em
   cada linha (`offset_source`, `offset_warning`).
4. A regra de bloqueio por baseline da V2.1 **não é removida**: ela continua
   valendo para o pipeline da V2.1; o perfil histórico tem autorização
   própria, com base na equivalência numérica demonstrada.
5. **Não** se aplica regressão arbitrária, fator empírico ou correção
   "visual" de descontinuidade: a conversão é a que o produto declara e a
   equivalência com a coleção harmonizada é medida.

Alternativas descartadas: (a) misturar produtos com offsets diferentes sem
verificação — produziria descontinuidade de 0,1 na reflectância (medido: NDVI
com |Δ| mediano de 0,15 e máximo de 6489 quando o offset declarado era
aplicado aos produtos originais); (b) usar o Planetary Computer (COGs
completos 2017–2025) — a assinatura SAS pública do endpoint retornou HTTP 429
de forma persistente neste ambiente; (c) inventar um fator de correção — vedado.

Consequências: a série histórica 2017–2025 é radiometricamente comparável com
a série da V2.1 (valores idênticos por construção), o que torna o
emparelhamento 2018–2025 com a PAM tecnicamente defensável.

## D51 — Uso do solo: MapBiomas bloqueado, WorldCover (ESA) como camada de lavoura (2026-11-11)

Contexto: a V2.2 mostrou que não existe observação oficial de
produtividade na escala da AOI; é preciso verificar se a AOI contém área
agrícola e, em caso positivo, calcular o NDVI sobre ela.

Fatos verificados em 2026-11-11:

* **MapBiomas**: a página oficial informa que *"a função de baixar mapas está
  temporariamente suspensa"* e que o acesso passa pelos assets do Google Earth
  Engine (exige conta). Os endereços públicos testados (GCS/S3) retornaram
  **404**. As **legendas oficiais** são públicas e foram obtidas e conferidas
  (Coleção 4 10 m: 3.2.1 Lavoura Temporária, 3.2.2 Lavoura Perene, 3.1
  Pastagem, 3.4 Mosaico de Usos, 1.1 Formação Florestal, 1.3 Formação Savânica,
  4 Área não vegetada, 5 Corpo D'água; Coleção 11 CSV: 3, 4, 15, 21, 25).
* **ESA WorldCover 10 m** (v200/2021 e v100/2020): COGs públicos, sem chave,
  classe oficial 40 = *Cropland* — acquisitions **realizadas** para a AOI.

Decisão:

1. A camada de uso do solo da V2.3 é o **WorldCover (ESA)**, com licença
   CC BY 4.0, usado para **quantificar a fração agrícola da AOI** e para
   calcular o indicador de NDVI sobre pixels de lavoura em 2020 e 2021.
2. O **bloqueio do MapBiomas é registrado** (motivo, tentativas e evidência),
   sem contorno e sem substituto silencioso.
3. **Nomenclatura obrigatória**: o indicador é `ndvi_cropland_worldcover`
   (ou `agricultura_temporaria` apenas com fonte que separe temporária de
   perene). **Não** se usa `ndvi_soja`/`ndvi_milho`: WorldCover não identifica
   cultura, e a classe SCL 5 não é identificação de lavoura.
4. Onde não há máscara de uso do solo (2017–2019 e 2022–2025), o indicador
   reportado é o da **AOI inteira**, com a limitação declarada — não se
   substitui por uma máscara inventada.

Consequências: a AOI pode ser avaliada quanto à sua vocação agrícola para
2020–2021; a série de uso do solo anual completa não está disponível e isso
fica explícito.

## D52 — Sem calendário fenológico validado: agregação por ano civil (2026-11-11)

Contexto: comparar NDVI mensal com rendimento anual exige janelas de
plantio/desenvolvimento/colheita. A V2.2 não conseguiu fixá-las e o
SISZARC/MAPA **não resolveu DNS** neste ambiente (verificado em 2026-11-11);
a página do calendário de safras da CONAB não expõe arquivo; as páginas da
Embrapa testadas retornaram 404.

Decisão:

1. **Nenhuma janela fenológica é inventada.** A agregação do indicador
   geoespacial é por **ano civil**, e a diferença entre o ano de referência
   da PAM (ano civil) e o ano-safra da cultura é declarada como limitação
   explícita em cada registro e no relatório.
2. A função de agregação por janelas safrais permanece disponível
   (`compat.s2_season_aggregation`), mas **não é executada** sem calendário
   validado.
3. A série de segunda safra do milho (1ª/2ª) não é misturada com "milho total"
   nas estatísticas: a PAM publica o total do ano, que é declarado como
   agregação anual.

Consequências: a comparação é anual e exploratória; qualquer refinamento
exige um calendário oficial obtido em etapa própria.

## D53 — Portão estatístico da V2.3: modelagem exploratória exige ≥ 9 pares anuais por cultura (2026-11-11)

Contexto: a V2.2 estabeleceu (D46–D49) que o estudo só seria viável com
amostra suficiente. Com a série histórica agora disponível, é preciso um
critério explícito para decidir se a modelagem é executada.

Decisão:

1. **Critério**: são necessários **≥ 9 pares anuais válidos por cultura**
   (rendimento municipal + indicador geoespacial do mesmo ano).
2. Abaixo do critério: **nenhuma modelagem** (nem regressão, nem baseline
   preditivo). São produzidos apenas descrição, comparação de distribuições e
   correlações **exploratórias**, com tamanho de amostra, p-valor por
   permutação e teste de tendência (resíduos) — sempre rotulados como
   exploratórios.
3. Acima do critério, ainda assim: modelos simples apenas (média histórica,
   último valor, tendência linear, regressão com o indicador), validação
   **temporal progressiva** (expanding window), sem divisão aleatória, e
   Ridge apenas como experimento estatístico isolado — **jamais** o Ridge de
   preços do produto.
4. A diferença de escala (rendimento municipal × NDVI de uma sub-região de
   0,4654% do município) consta de **todas** as saídas, mesmo quando há
   ganho estatístico.

Consequências: a V2.3 não pode "forçar" resultado; ela estabelece o que é
sustentável com a amostra efetivamente obtida.

## D54 — Calendário oficial: ZARC do MAPA como fonte primária (2026-11-12)

Contexto: a V2.2 agregou por ano civil porque o SISZARC não resolvia DNS (D52). A
V2.4 verificou o portal de dados abertos do **MAPA**
(`dados.agricultura.gov.br`), que é domínio distinto do `dados.gov.br` (que
exige autenticação) e **não** é bloqueado.

Fatos verificados em 2026-11-12:

* conjunto *Zoneamento Agrícola de Risco Climático (Zarc) — Tábua de Risco*,
  licença **Creative Commons Atribuição**, 11 safras (2016/2017 … 2026/2027) em
  CSV + dicionário de dados oficial;
* **1.408 registros** de Sorriso-MT (`5107925`) em **23 culturas**, com ciclo,
  solo, risco por decêndio e **portaria de origem**;
* janelas observadas: soja decêndios 29–36 (out–dez), milho principal 27–36
  (set–dez), milho 2ª safra 1–5 (jan–fev);
* a coluna `Produtividade` do ZARC é um **código de classe**, não kg/ha.

Decisão:

1. **O ZARC do MAPA é a fonte primária do calendário agrícola** do SADEN,
   acquired por consulta HTTP reproduzível (bruto fora do Git com URL, tamanho e
   SHA-256; recorte de Sorriso versionado).
2. O ZARC é tratado como **recomendação oficial de plantio por condição de
   risco** — **não** como data de plantio observada, e **não** como
   produtividade.
3. Todas as combinações oficiais (ciclo × solo × safra) são preservadas;
   nenhuma é arbitrada para "simplificar".
4. A relação **safra → ano de referência da PAM** é registrada como **regra
   derivada** (colheita no ano civil seguinte), com alternativa preservada e
   confiança declarada, devendo ser confrontada com o texto das portarias.
5. ZARC e **calendário de semeadura** (normativo, vazio sanitário) permanecem
   conceitos distintos e não são misturados.

Consequências: a pendência de D52 (calendário) é **resolvida na parte
agronômica**; a agregação por ano civil da V2.3 passa a ter alternativa
oficial, ainda não aplicada aos indicadores (a V2.4 não retreina modelos).

## D55 — Referência espacial separada da referência agronômica (2026-11-12)

Contexto: o ZARC é municipal (por solo/ciclo), a CONAB SUTIN é submunicipal
(por feição, mas **sem produtividade**) e o Sentinel-2 é raster.

Decisão:

1. A base passa a ter **duas tabelas conceitualmente distintas**:
   **referência espacial** (geometrias, máscaras de uso do solo, pixels e
   indicadores de vegetação) e **referência agronômica** (cultura, safra,
   calendário, rendimento oficial).
2. A tabela pareada só é construída quando existe justificativa **espacial,
   temporal e semântica** simultânea; caso contrário, as tabelas permanecem
   separadas e a ausência de pareamento é declarada.
3. Nenhuma linha anual é criada quando existem múltiplas combinações oficiais
   (grupo/solo/risco): as alternativas permanecem em estrutura própria, com
   identificadores de relacionamento.

Consequências: a base é auditável sem forçar junções artificiais.

## D56 — Não existe produtividade submunicipal pública: a escala do indicador é que deve mudar (2026-11-12)

Contexto: a V2.3 mostrou que a incompatibilidade de escala (rendimento
municipal × NDVI de 43 km²) é o obstáculo determinante. A V2.4 investigou
amplamente fontes com granularidade inferior à municipal.

Fatos verificados em 2026-11-12:

* **CONAB SUTIN** (GeoServer público): 1.618 camadas; 17 de MT; a camada
  `MT_SOJA_2021` tem 24.634 feições no estado e 17 em Sorriso — com atributos
  `CD_MUN`, `NM_MUN` e **`AREA_HA`**, **sem** campo de produtividade;
* **MapBiomas Col. 4**: rota GCS oficial retorna **HTTP 403** (2017–2025);
  asset GEE exige conta não configurada; página de downloads informa suspensão
  temporária do download de GeoTIFF;
* **IMEA**: host responde, páginas internas retornam **HTTP 500**;
* **INCRA/SIGEF/CAR**: sem resposta (DNS/TCP);
* **WorldCover**: cropland (classe 40) em 10 m para 2020 e 2021, acquired;
* **ZARC**: janelas de plantio, sem produtividade.

Decisão:

1. **Não existe fonte oficial pública e reproduzível de produtividade
   (kg/ha) de soja/milho em Sorriso abaixo da escala municipal.** A
   incompatibilidade de escala da V2.3 **não** se resolve com fonte de
   produtividade mais fina — resolve-se **mudando a escala do indicador
   geoespacial** para a unidade do alvo.
2. A geometria cadastral (INCRA/SIGEF/CAR), mesmo quando acessível, **não** é
   observação de produção e não pode ser usada como rótulo.
3. A CONAB SUTIN passa a ser a **referência submunicipal de área de cultura**
   (soja/MT 2021), útil para mascarar NDVI por cultura **nesse ano**, e não
   como referência de produtividade.
4. Os bloqueios (MapBiomas/GEE, IMEA, SIGS, INCRA) são registrados como
   **necessidades de acesso institucional**, com procedimento manual legítimo
   documentado.

Consequências: a V2.3 permanece válida como estudo exploratório de
referência; a V2.4 constrói a escala municipal do indicador, que é a
alternativa metodologicamente defensável.

## D57 — Escala municipal do indicador: agregação por blocos sobre a área agrícola do município (2026-11-12)

Contexto: para comparar o indicador geoespacial com o alvo municipal, o
indicador deve ser agregado na **mesma unidade territorial** do alvo.

Fatos de engenharia verificados:

* grade municipal em `EPSG:32721`, 20 m, **5.878 × 11.008 px** (64,7 M px na
  bbox de ~24.400 km², que contém os 9.293 km² do polígono);
* o município atravessa **dois tiles** (`21LXG` ao norte, `21LXF` ao sul) —
  o mosaico determinístico `first_valid_wins` (D44) é reaplicado;
* custo medido: ~1,04 GB de download por data (2 bandas de 10 m) e ~9,3 GB
  para 9 datas;
* processamento por **16 blocos**, com acumuladores por bloco (soma,
  contagem, soma de quadrados e histograma de 2.001 bins) — o raster
  municipal **nunca** é materializado em memória;
* recorte territorial: só entram centros de célula **dentro do polígono**
  municipal (a bbox inclui ~15.000 km² de fora).

Decisão:

1. O indicador municipal é calculado **por blocos**, sobre a máscara agrícola
   (WorldCover, classe 40) **e** o polígono do município.
2. O processamento produz **estatísticas agregadas**, não rasters municipais
   (a prioridade é a estatística, conforme a restrição da V2.1).
3. Os nomes são **genéricos**: `ndvi_all_cropland` (toda a área agrícola) e
   `ndvi_temporary_cropland` quando a máscara permitir separar temporária de
   perene. **Não** se usa `ndvi_soja`/`ndvi_milho` sem identificação de
   cultura por produto específico — a referência de cultura disponível é a
   CONAB SUTIN, válida apenas para 2021 em MT.
4. A comparação AOI × município é feita como **medida quantitativa de
   representatividade** (diferença e estabilidade por ano), e **não** como
   validação de produtividade.

Consequências: o SADEN passa a ter um indicador na mesma escala do alvo
(IBGE municipal), eliminando a incompatibilidade de escala — mas ainda sem
relação causal ou preditiva demonstrada.

## D58 — Calendário: regra oficial de decêndios e janelas por safra, solo, ciclo e risco (2026-11-12)

Contexto: a V2.4 converteu decêndios em datas por uma aproximação linear de
10 dias. O MAPA define **três decêndios por mês** (dias 1–10, 11–20 e
21–último dia), com fevereiro de 28 ou 29 dias.

Decisão:

1. A conversão passa a seguir a regra oficial (`agri/season.py`): mês =
   ⌈decêndio/3⌉ e segmento = 1 (1–10), 2 (11–20) ou 3 (21–fim do mês); os
   36 decêndios do ano são cobertos por testes, incluindo fevereiro e anos
   bissextos.
2. As janelas são calculadas **por nível de risco** (10/20/30/40) e preservam
   todas as combinações oficiais de solo e ciclo; **nenhuma** combinação é
   descartada por arbitragem.
3. Nível de risco da análise principal: **20 (baixo)**, justificado pela
   finalidade da recomendação oficial — não pela correlação obtida. Os demais
   níveis são cenários de sensibilidade.
4. Como o ZARC é **recomendação de risco**, e não plantio observado, toda
   janela é rotulada como tal; nenhuma data de plantio é afirmada.

Consequências: as janelas por ano civil usadas na V2.3 passam a ter
alternativa oficial, verificável e auditável por portaria.

## D59 — Máscara agrícola municipal em quatro variantes, com a "estável" como principal (2026-11-12)

Contexto: o ESA WorldCover só tem mapas de **2020 e 2021**; a V2.4 aplicou a
máscara de 2020 a todos os anos, inclusive anteriores.

Decisão:

1. Quatro máscaras são derivadas da **mesma** leitura (uma por ano):
   `wc2020`, `wc2021`, `stable` (interseção 2020∩2021) e `broad` (união).
2. A **análise principal** usa `stable` — a interseção é a opção mais
   conservadora para uma análise retrospectiva entre 2017 e 2025 (só entram
   áreas classificadas como lavoura nos dois anos). As demais são sensibilidade.
3. Toda linha do conjunto pareado carrega `mask_year` e a marca
   `mask_retrospective` quando o ano da cena difere do(s) mapa(s) usado(s): a
   máscara é **proxy espacial**, não informação histórica de uso do solo.
4. A limitação é explícita: sem mapa anual (MapBiomas bloqueado, D56) não há
   informação de uso do solo de cada ano.

Consequências: a sensibilidade à máscara pode ser medida, e nenhuma máscara é
apresentada como informação histórica.

## D60 — Milho: safras separadas, alvo municipal agregado incompatível por construção (2026-11-12)

Contexto: a PAM publica o **rendimento total** do milho do ano (1ª + 2ª
safras); o ZARC distingue janelas distintas para milho principal e 2ª safra.

Decisão:

1. As janelas de milho principal e de milho 2ª safra são construídas e
   **mantidas separadas**.
2. O rendimento municipal total é comparado com cada janela apenas como
   **análise de sensibilidade**, com a incompatibilidade declarada no registro
   (`semantic_compatibility`).
3. Como não há desagregação de área por safra na PAM (verificado: só há
   "Milho (em grão)" total), **não** se constrói indicador ponderado por
   participação de área — usar áreas de safras diferentes para pesar seria
   incorreto.
4. O n efetivo é o número de **anos com rendimento** por cultura; as várias
   janelas são cenários, não observações independentes.

Consequências: o estudo de milho é exploratório e fica marcado como
incompatível em granularidade de safra.

## D61 — Protocolo estatístico da V2.5 (análise principal pré-declarada) (2026-11-12)

Decisão:

1. **Análise principal** (fixada antes de ver resultados): indicador
   `ndvi_municipal_mean` (máscara `stable`, janela modal do ZARC) × rendimento
   municipal do IBGE/PAM, por cultura (soja e milho).
2. **Sensibilidade**: máscaras `wc2020`/`wc2021`/`broad` e o indicador da AOI
   (mesma janela, mesma escala temporal).
3. Métodos idênticos aos da V2.3 (Pearson, Spearman, permutação com 5.000
   iterações e semente fixa, correlação detrendizada, walk-forward com
   média histórica / último valor / tendência / OLS com o indicador),
   acrescidos de IC por *bootstrap* e **correção de Holm** para a família de
   testes.
4. A análise é **retrospectiva**: usa toda a safra para investigar relações e
   **não** pode ser apresentada como previsão operacional.
5. Critério de ganho: o indicador só é considerado promissor se **superar de
   forma consistente** os baselines na validação temporal; mesmo que supere,
   a conclusão será "evidência exploratória inicial", nunca capacidade
   preditiva validada.

Consequências: a comparação entre a V2.3 e a V2.5 é feita em condições
equivalentes (mesmos métodos, mesmos anos de teste, mesmo alvo).

## D62 — Correção da âncora de ano dos decêndios do ZARC (2026-11-12)

Contexto: a ingestão da V2.4 converteu todos os decêndios de uma safra usando
o **primeiro** ano (`SafraIni`) e uma aproximação linear de dez dias. Dois
erros foram encontrados na auditoria da V2.5:

1. o campo `decendios_com_risco` do conjunto normalizado guarda o risco por
   **rótulo textual** (`muito_baixo`/`baixo`/`medio`/`alto`), e não por código
   numérico — a leitura ingênua produzia janelas **vazias**;
2. a âncora de ano estava errada para os decêndios de janeiro–abril.

Decisão:

1. A conversão passa a usar a **âncora dupla**: os decêndios 1–12
   (janeiro–abril) pertencem ao **segundo** ano da safra (`safra_fin`) e os
   decêndios 13–36 (maio–dezembro) ao **primeiro** (`safra_ini`).
2. A regra é **verificável** por um critério externo e objetivo: a portaria
   que publica a recomendação tem de **preceder** o início da janela
   recomendada. Com a regra antiga há **165 violações** nas culturas-piloto
   (soja, milho 1ª, milho 2ª); com a regra nova há **zero**.
3. A data da portaria passa a ser extraída do identificador e registrada.
4. As janelas são calculadas a partir de datas **absolutas** (`YYYY-MM`),
   sem deslocamento único de ano.

Consequências: a 2ª safra do milho passa a ser corretamente associada a
janeiro–fevereiro do **segundo** ano da safra (antes deslocada um ano), o que
alinha a janela ZARC com o ano de colheita da PAM. O número de registros
disponíveis por safra e o conteúdo de `zarc_planting_windows.csv` **não** são
alterados — a correção é da camada de janelas (`agri/season.py`).

## D63 — Janela recomendada do ZARC = risco muito baixo ou baixo; modalidade por safra (2026-11-12)

Decisão:

1. A **janela recomendada** é a dos decêndios com risco **≤ 20%** (muito
   baixo ou baixo) — exatamente o critério oficial do MAPA, e **não** uma
   faixa escolhida por correlação. As extensões ≤ 30% e ≤ 40% são cenários
   de sensibilidade.
2. Quando há várias janelas oficiais na mesma safra (variação por tipo de
   solo e grupo de ciclo), a análise principal usa a **modal** — a que
   aparece em mais combinações oficiais. As demais permanecem na base como
   cenários.
3. A escolha é determinística e **independente** do rendimento observado: o
   desempate é pela data de início mais tardia entre janelas com o mesmo
   número de combinações.

Consequências: nenhuma linha da base é descartada e o n efetivo continua
sendo o número de **anos com rendimento**, não o número de combinações ZARC.

## D64 — Decomposição da comparação V2.3 x V2.5: duas fatias de pareamento (2026-11-12)

Contexto: a V2.3 usou a AOI (0,4655% do município) com agregação por **ano
civil**. A V2.5 muda **escala** (município) e **janela** (ZARC) ao mesmo tempo,
o que impediria atribuir qualquer diferença a uma das mudanças.

Decisão:

1. O conjunto pareado tem **duas fatias**, com `pairing_mode` explícito:
   * `zarc_sazonal` — janela de plantio do ZARC (modal da safra) x ano de
     colheita da PAM;
   * `ano_civil_v23` — agregação por ano civil, com os **mesmos critérios de
     exclusão** da V2.3 (`min_months=3`, `min_coverage=0,5` sobre a AOI).
2. A fatia `ano_civil_v23` é a **réplica** da V2.3 e serve de controle: a
   replicação é verificada par a par (diferença máxima observada: 1,1e-16,
   ou seja, arredondamento de ponto flutuante).
3. A comparação V2.3 x V2.5 passa a ser lida como: *réplica* -> *mesma
   janela, escala municipal* -> *janela ZARC, escala municipal*.

Consequências: qualquer diferença observada pode ser atribuída ao fator
escala ou ao fator janela, e não à combinação dos dois.

## D65 — Equalização numérica do paralelismo do processamento municipal (2026-11-12)

Decisão:

1. Os blocos de um mês são processados em **paralelo** (`--workers`, padrão 4),
   por serem operações limitadas por I/O remoto (COG do Sentinel-2).
2. A acumulação é feita **na ordem dos blocos** (o executor devolve os
   resultados na ordem de submissão), de modo que o resultado numérico é
   **idêntico** ao sequencial — verificado: `stable` = 0,3440721895 nas duas
   execuções, com ganho de 3,7x (116 s -> 31 s por mês).
3. A cena principal de cada mês é o **item exato** auditado na série de
   referência da V2.3 (busca por `item_id`), e o tile complementar 21LXF é
   procurado na mesma data com o **mesmo índice de reprocessamento**.

Consequências: reprodutibilidade bit a bit da série municipal, com o custo de
processamento viável para os 47 meses das janelas agrícolas.

## D66 — Encerramento da linha do NDVI como variável de produtividade (2026-11-12)

Contexto: a V2.5 refutou a hipótese de que a incompatibilidade de escala e a
janela anual explicavam a ausência de relação entre NDVI e rendimento
municipal (soja: r = 0,432 na réplica da V2.3 → 0,203 com escala municipal e
janela do ZARC; milho: 0,200 → −0,396). Nenhum dos 32 testes da família foi
significativo após Holm, e o modelo com NDVI não superou a média histórica
em nenhuma das 8 configurações de validação temporal alinhada.

Decisão:

1. A hipótese do NDVI como **variável principal** de produtividade é
   **encerrada**. Nenhum indicador de vegetação será otimizado, integrado ao
   Ridge de preços ou à interface.
2. Os indicadores Sentinel-2 **não são excluídos**: a série municipal
   (`municipal_ndvi_monthly.csv`), os manifests e os experimentos anteriores
   permanecem como **material de pesquisa** e **referência geoespacial**
   (comparador histórico na análise da V2.6).
3. O processamento Sentinel-2 não é descontinuado; o pipeline continua
   disponível e reprodutível.

Consequências: a V2.6 abre uma linha **agroclimática** (variáveis
climáticas diretas) e um **painel multi-municipal**, mantendo a V2.5 como
evidência contrária documentada.

## D67 — Fontes meteorológicas: INMET, ERA5-Land, ERA5 e NASA POWER, com tipo de fonte explícito (2026-11-12)

Decisão:

1. Cada observação climática carrega `source_type`:
   * `station_observation` — estação do INMET (medição pontual);
   * `reanalysis` — ERA5-Land, ERA5 e NASA POWER (reanálises);
   * `gridded_precipitation` — Reserved para precipitação de produtos
     grillados (CHIRPS), hoje **bloqueado** (sem resolução DNS).
2. **Prioridade de aquisição**: INMET (observação) como base independente; a
   reanálise espacialmente consistente como base do painel.
3. **Acesso ao ERA5-Land**: a API do CDS da Copernicus exige uma chave de
   conta (não configurada neste ambiente) e o espelho ARCO não resolve DNS.
   O ERA5-Land **não é declarado indisponível**: ele é obtido pela API
   histórica do Open-Meteo (`models=era5_land`), que entrega temperatura do
   ar, umidade, ponto de orvalho, temperatura do solo e **umidade do solo**
   (camadas 0–7 e 7–28 cm) de 1950 ao presente. As variáveis acumuladas
   (precipitação, radiação) e de vento/pressão **não** estão disponíveis
   nesse acesso e são obtidas do **ERA5** (0,25°), com o par de fontes
   identificado por variável.
4. **NASA POWER** (MERRA-2 + CERES, comunidade AG) entra como terceira
   reanálise, usada como **verificação independente** e fonte completa
   (precipitação, radiação, vento, pressão, temperatura do solo).
5. **CHIRPS** fica registrado como **bloqueio** (o host `chc.ucf.edu` não
   resolve DNS neste ambiente); a precipitação grillada é suprida por ERA5.
6. A **leitura dos arquivos anuais do INMET** é feita por **HTTP Range**
   (leitor de ZIP remoto próprio): apenas o CSV da estação necessária é
   transferido — 808 kB lidos (7 requisições, 3,2 MB) em vez de 102 MB
   por ano e por estação.

Consequências: o painel distingue permanentemente **observação** de
**reanálise**; a comparação entre as duas é feita e reportada (D71), sem
correções empíricas.

## D68 — Graus-dia, soma térmica e balanço hídrico: perfis metodológicos por cultura (2026-11-12)

Decisão:

1. **Não há temperatura-base universal.** Cada cultura tem perfis
   documentados (fonte, fórmula, grupo de cultivar, limitações):
   * `soja_ometto` — Ometto (1981), aplicado no Centro-Norte de MT:
     Tb = 14 °C, Tmed limitada a 36 °C;
   * `soja_gilmore` — Gilmore & Rogers (1958) / Arnold (1960) / Schneider et
     al. (1987): Tb = 10 °C, Tmed limitada a 30 °C; emergência = 92,5 °C·dia
     e R5 = 554 °C·dia (Martorano et al., 2012);
   * `milho_embrapa` — Embrapa Milho e Sorgo (AgenTec): Tmax ≤ 30 °C,
     Tmin ≥ 10 °C, Tb = 10 °C; exigências de 780–830 °C·dia
     (superprecoces), 831–890 (precoces) e 890–1.200 (normais).
2. O **modo de limite** é explícito no perfil: a soja limita a temperatura
   **média**; o milho limita os **extremos**.
3. **Balanço hídrico**: método de **Thornthwaite & Mather (1955)**
   sequencial, com ETP de Thornthwaite (1948) — é o método da ferramenta
   BHCalc (Embrapa/IAC) e da planilha BHNorm (Rolim et al.).
4. **CAD**: entra como parâmetro explícito, com perfis de solo documentados
   (tipo 2 do MAPA = 50 mm como principal; tipos 1 e 3 como cenários). Não
   se atribui CAD específica de município sem fonte de solos.
5. **ET0**: três métodos implementados e **identificados** na saída — FAO-56
   Penman-Monteith (com a conversão de vento de 10 m para 2 m pelo coeficiente
   0,4), Thornthwaite (1948) e Hargreaves-Samani (1985). Estimativas de
   métodos diferentes **nunca** são misturadas na mesma série.
6. **Balanço hídrico de cultivo** (com Kc e estádios fenológicos) **não** é
   construído: os parâmetros por cultivar não são conhecidos.

Consequências: os indicadores térmicos e hídricos do painel têm
metodologia rastreável, e as incertezas (temperatura-base, CAD) são
tratadas como **cenários**, não como medidas.

## D69 — Critérios de elegibilidade do painel, fixados antes da análise (2026-11-12)

Decisão: um município entra no painel se, **para a cultura**:

1. tiver rendimento médio **observado** (PAM) positivo em pelo menos **7**
   dos 9 anos de 2017–2025;
2. tiver área colhida positiva em pelo menos um ano;
3. tiver geometria municipal oficial disponível;
4. tiver pelo menos uma estação do INMET dentro do município ou a até 80 km
   (para a via observacional).

Os critérios **não** dependem de clima nem de correlação com o
rendimento. Cada exclusão é registrada com o motivo. A seleção da estação
por município segue três níveis, na ordem: dentro do município → mais
próxima dentro de 80 km → sem estação (lacuna preservada).

Consequências: o n do painel é definido **antes** de qualquer correlação,
e a seleção de municípios não pode ser enviesada pelo desempenho
estatístico.

## D70 — Modelos pré-declarados e validações separadas (2026-11-12)

Decisão:

1. Os modelos comparados são **fixados antes** da análise:
   * **A — baselines**: média histórica, último valor, tendência temporal
     (os mesmos da V2.3);
   * **B — meteorológicos**: precipitação acumulada e temperatura média;
   * **C — térmicos**: graus-dia acumulados e dias de calor extremo;
   * **D — hídricos**: ET0, déficit hídrico e excedente hídrico;
   * **E — combinados**: apenas combinações com justificativa agronômica.
2. **Validação temporal** (walk-forward por município: treino com anos
   anteriores, teste nos anos seguintes) e **validação territorial**
   (municípios inteiros no treino ou no teste) são experimentos
   **distintos**, reportados separadamente; anos do mesmo município nunca
   são distribuídos aleatoriamente entre treino e teste.
3. **Nenhum** algoritmo complexo (XGBoost, Random Forest, redes neurais,
   ensembles) é desenvolvido nesta etapa.
4. Análises de painel usam **efeitos fixos de município e de ano**, com
   **erro-padrão agrupado por município** — as linhas município-ano **não**
   são tratadas como observações independentes.
5. Correção de **Holm** sobre a família de testes.

Consequências: a comparação com os baselines da V2.3 é feita em condições
equivalentes, e a significância reportada e familiar (FWER).

## D71 — Comparação INMET × reanálise: diferença de escala, não erro (2026-11-12)

Decisão:

1. Quando uma estação tem série suficiente, ela é comparada com a
   reanálise **na localização da estação**: viés (bias), MAE, RMSE e
   correlação, para precipitação e temperatura, além das somas acumuladas.
2. **Não se espera equivalência** entre uma medição pontual e uma célula de
   ~9 km (ERA5-Land) ou 0,25° (ERA5): as diferenças são de **escala**, e
   isso é declarado.
3. **Nenhuma correção empírica** (bias adjustment) é aplicada sem registro
   explícito do procedimento; na V2.6 nenhuma correção é aplicada.

Consequências: o painel usa a reanálise como base espacialmente
consistente, e o INMET permanece como verificação independente.

## D72 — Ausência nunca é zero; a máscara do ZARC é proxy (2026-11-12)

Decisão:

1. Valor ausente (`-9999` do INMET, `None`) **nunca** é convertido em zero.
   Precipitação realmente zero é uma observação e é preservada como tal.
2. A qualidade é auditada (faixas físicas, datas duplicadas,
   descontinuidades) e os valores fora da faixa são **marcados**, nunca
   corrigidos nem substituídos.
3. A janela do ZARC é uma **recomendação oficial de risco**, não um
   plantio observado: toda linha do painel carrega os decêndios, o solo, o
   ciclo, o nível de risco e a portaria de origem, e a compatibilidade
   semântica do milho 2ª safra é declarada em cada linha.

Consequências: o painel preserva a diferença entre "zero" e "sem
informação", e nenhuma janela agrícola é apresentada como data de plantio.

## D73 — Janela descontígua: bloco contíguo principal (2026-11-12)

Contexto: com a âncora dupla de decêndios (D62), as janelas oficiais das
culturas de **ciclo curto do Nordeste** (soja e milho da Bahia, com janelas em
março–junho **ou** outubro–dezembro) caíam em **dois blocos de calendário
separados**: `[mai–jun de Y]` e `[mar–abr de Y+1]`. Agregar os meses dos dois
blocos misturaria períodos e poderia incorporar meses **posteriores** ao ano
de colheita.

Decisão:

1. Usa-se o **bloco contíguo de maior duração** da janela oficial (desempate:
   o de início mais antigo) — o período de plantio principal.
2. Os meses do bloco secundário são **descartados**, não agregados, e ficam
   registrados em `zarc_window_discarded_months` (com
   `zarc_window_blocks` contando os blocos originais).
3. O critério é aplicado a **todas** as culturas e UFs, não apenas ao caso
   diagnóstico da Bahia.

Consequências: nenhuma janela utilizável do painel permanece descontígua
(10 linhas com meses descartados, 0 descontíguas). A perda de cobertura de
culturas de ciclo curto (Bahia) é preservada como limitação declarada.

## D74 — Artefatos grandes e regeráveis fora do Git (2026-11-12)

Contexto: a base da V2.6 produz artefatos de centenas de MB a gigabytes
(série diária climática: ~835 MB; ZARC multi-municipal: ~2,0 GB; PAM
multi-municipal: ~428 MB; malhas municipais: ~158 MB). Versioná-los faria o
repositório crescer em gigabytes sem acrescentar informação (são **regeríveis**
pelos comandos de `run_agroclimate.py`).

Decisão:

1. Os artefatos grandes ficam **fora do Git** (`.gitignore` do `geospatial/`),
   com os **manifestos** correspondentes versionados
   (`agroclimatic_panel.json`, `climate_quality.json`, `zarc_panel.json`,
   `pam_panel.json`, `panel_eligibility.json`).
2. O **painel final** (`agroclimatic_productivity_panel.csv`, ~24 MB) é
   versionado: é o produto principal e é pequeno o bastante.
3. O crescimento do repositório foi verificado: `.git` caiu de 587 MB para
   13,6 MB quando os blobs grandes foram removidos do histórico local
   (a branch ainda não havia sido publicada).

Consequências: a reprodutibilidade passa a depender da reexecução dos
comandos, e não do versionamento de gigabytes — que é o padrão já adotado
para os CSVs brutos do ZARC (D48).

## D75 — Comparação INMET × reanálise: diferença de escala, não erro (2026-11-12)

Contexto: o INMET mede em um ponto; a reanálise descreve uma célula de ~9 km
(ERA5-Land) a ~55 km (MERRA-2/NASA POWER). Não se espera equivalência.

Decisão:

1. A comparação é feita na **localização da estação**, com viés (bias), MAE,
   RMSE, correlação e somas acumuladas de precipitação e temperatura.
2. As diferenças são interpretadas como **diferença de escala**; nenhuma
   correção empírica (bias adjustment) é aplicada na V2.6.
3. A base do painel usa a **reanálise** (consistência espacial entre
   municípios); o INMET permanece como **verificação independente** e base
   da via observacional.

Consequências: a resolucao espacial da reanálise é registrada como limitação
principal do painel (pseudo-replicação espacial entre municípios vizinhos),
e o erro-padrão é agrupado por município — agrupamento espacial por célula
da grade fica como melhoria metodológica pendente.


---

## D76 - A dependência espacial excede a resolução nominal da grade (2026-11-14)

Contexto: a V2.6 agrupou o erro-padrão por município e registrou a resolução
nominal de 55 km (MERRA-2) como limitação. A auditoria da V2.7 mostrou que
NASA POWER **interpola** a coordenada solicitada (0% de dias com séries
idênticas entre municípios da mesma célula; diferença média de temperatura
de 0,32 a 1,90 °C) e que a correlação das anomalias anuais ainda é 0,834
(temperatura) e 0,630 (precipitação) na banda de 400-425 km.

Decisão: a célula nominal de 55 km **não** é a unidade de agrupamento
adequada; a escala de dependência é calibrada pelo correlograma e fixada em
**blocos espaciais de 250 km** (46 grupos), usada como esquema conservador
de referência. A inferência é reportada em quatro esquemas (município,
célula, bloco, UF) e por Conley, sem escolha *a posteriori*.

Consequências: o erro-padrão do déficit hídrico da soja cresce de 0,0723
(município) para 0,2404 (bloco 250 km) e o número de hipóteses que
sobrevivem a Holm cai de 13 para 4. Detalhes em
`docs/execution/v2.7/DECISIONS_V2_7.md`.

## D77 - Esquemas de inferência pré-declarados e Holm sobre a família completa (2026-11-14)

Decisão: família de **21 hipóteses** (3 culturas × 7 variáveis) com correção
de **Holm** (FWER) aplicada separadamente a cada esquema; Conley e bootstrap
wild são procedimentos **alternativos**, não combináveis. Nenhum critério,
banda ou esquema é ajustado para obter significância.

Consequências: 12 famílias reportadas no manifesto `v27_robust_inference.json`
(município 13 · célula 12 · bloco 250 km 4 · UF 0 · Conley 150/250/400/600 km
10/8/8/8 · bootstrap wild 13/12/6/3).

## D78 - Janela fenológica é experimento, com requisitos térmicos publicados (2026-11-14)

Decisão: o ZARC é janela de plantio por risco, não calendário fenológico. A
janela de enchimento de grãos é construída com requisitos térmicos
publicados (soja R1 = 92,5 e R5 = 554 °C·dia; milho 780/860/1.050 °C·dia até
a polinização; janelas de 45 dias na soja e de VT+22,5 d a VT+55 d no
milho) e datas aproximadas pela soma térmica real. O milho 2ª safra, sem
estágio publicado com precisão suficiente, permanece na janela do ZARC.

Consequências: em 84 municípios e 1.027 linhas, a janela fenológica mantém
5/5 variáveis significativas na soja e torna precipitação e temperatura
significativas no milho (que não eram na janela do ZARC). Coeficientes não
são comparáveis entre janelas (a exposição muda).

## D79 - Calibração do bootstrap wild por Monte Carlo (2026-11-14)

Decisão: o bootstrap wild só pode ser usado se o seu tamanho nominal for
demonstrado. A V2.7 calibra com dois DGP (erro agrupado; painel município ×
ano com efeitos fixos e erro AR(1) intracluster), 3 sementes e taxas de
rejeição em 1%/5%/10% com incerteza de Monte Carlo.

Consequências: tamanho próximo do nominal para ≥ 10 grupos; com 5 grupos o
procedimento é levemente conservador (0,043–0,052) e o poder cai para 53,5%
(contra 91,3% da variante por observação) — valores da grade **recalculada**
após D85; a primeira grade, contaminada, indicava 46%.

## D80 - Correção dos pesos do bootstrap wild: um peso por grupo (2026-11-14)

Decisão: o bootstrap wild usa **um peso de Rademacher por grupo e por
replicação** (Cameron, Gelbach & Miller, 2008). A implementação herdada da
sessão anterior sorteava um peso **por observação**, apesar de o texto
afirmar o contrário, o que não preserva a dependência intracluster.

Consequências: p-valores do bootstrap recalculados; a forma vetorizada
(≈1000× mais rápida) foi verificada como numericamente idêntica à forma em
laço; a variante por observação foi mantida apenas para comparação.

## D81 - Política de nulidade do bootstrap declarada, não implícita (2026-11-14)

Decisão: reportar **os dois** p-valores do bootstrap (nulidade imposta e
irrestrita) e declarar a política usada (`--null-policy`), porque a
convenção de troca entre as duas não pôde ser verificada no artigo primário
neste ambiente.

Consequências: o manifesto grava `p_value_imposed` e
`p_value_unrestricted` em cada resultado.

## D82 - CAD territorial geoespacial da Embrapa Solos (2026-11-14)

Decisão: a CAD pode ser derivada de fonte oficial (Embrapa Solos/GeoInfo;
Vasques et al., 2021; 90 m; **CC BY-NC 3.0 BR**). As camadas são declaradas
em **mm/cm**; a CAD do perfil em mm é a **integração**
`Σ AW(mm/cm) × espessura(cm)` — nunca uma multiplicação direta. Ausência de
dado válido permanece ausência.

Consequências: em 10 municípios, a CAD de 0-100 cm fica entre 126,0 e
239,9 mm (mediana 158,9) — os cenários da V2.6 (35/50/70 mm) são
**conservadores** frente ao dado oficial. A CAD entra como linha
experimental.

## D83 - ERA5-Land permanece bloqueado; NASA POWER é a base (2026-11-14)

Decisão: o acesso nativo ao CDS exige credencial não configurada. Não se
cria conta, não se pede credencial por chat, não se guarda segredo no Git. O
bloqueio é documentado e a V2.7 prossegue com NASA POWER (reanálise) e INMET
(observação independente). CHIRPS e ARCO seguem sem resolução DNS.

## D84 - Artefatos grandes fora do Git; manifests versionados (2026-11-14)

Decisão: estendida de D74. A base diária (1,07 GB), o painel (27,3 MB) e a
resposta bruta do WCS (2,5 MB) ficam fora do Git e são regeneráveis por
comando; os manifests `v27_*` são versionados. Os scripts de sondagem da
sessão anterior (`tmp/v27_*.py`) permanecem fora do Git até a consolidação
final.

## D85 - Réplica com erro-padrão nulo é descartada, não contada (2026-11-14)

Decisão: uma réplica do bootstrap cuja variância agrupada se anula por
arredondamento (`se` positivo da ordem de 1e-19) é descartada em vez de
contada como excedência. O critério é relativo à magnitude do coeficiente
(`se <= sqrt(eps) * max(|β̂|, 1)`, a tolerância de posto do `lstsq`) e vale
para o bootstrap OLS e para o bootstrap *within*.

Evidência: a calibração da sessão anterior registrou
`mean_t_boot_sd_cluster ≈ 8,5e14` em 9 casos (G = 5 e G = 10, DGP
`agrupado`). A causa era `se > 0` aceitando erro-padrão numericamente nulo,
o que produzia `|t| ≈ 1e18` e o contava como excedência.

Alcance: nos resultados publicados não havia réplica degenerada (os 105
bootstraps de `v27_robust_inference.json` usaram 999/999 réplicas), de modo
que nenhum p-valor já reportado muda.

## D86 - Holdout espacial e temporal simultâneos (P5) (2026-11-14)

Decisão: os protocolos territoriais P1–P4 separam apenas o espaço; o treino
contém o mesmo ano da observação de teste em outros municípios, e o
coeficiente ajustado pode absorver o choque do ano. O protocolo P5 remove do
treino, ao mesmo tempo, os blocos espaciais e os anos da dobra.

Consequência: o ganho que sobrevive a P5 não é atribuível a vizinhança
geográfica nem a informação do próprio ano. Se o ganho existir em P1–P3 e
desaparecer em P5, isso deve ser reportado como limitação, não corrigido.

## D87 - Fatorial espaço × tempo com controle de tamanho (2026-11-14)

Decisão: a separação espacial e a temporal são investigadas num fatorial 2×2
sobre a mesma grade de dobras do P5 — ``SS`` (nada removido), ``SE`` (bloco
removido, equivale ao P3), ``TS`` (ano removido) e ``TE`` (ambos, equivale ao
P5) — e **todo** braço é reamostrado para o mesmo número de linhas de treino,
estratificado por bloco espacial, com repetições.

Motivo: o P5 removeu o ano **e** ~20% do treino do P3 ao mesmo tempo. Sem
equalizar o tamanho, não é possível atribuir a degradação ao ano.

Consequência: o braço `SE` reproduz o P3 (612,724390) e o `TE` reproduz o P5
(661,802276) exatamente, o que garante que o fatorial lê os protocolos
publicados e não cria um protocolo novo.

Resultado: tamanho equalizado desloca a MAE em ≤ 1 kg/ha — a hipótese de
tamanho está refutada. O espaço custa −3,6 na soja (n.s.) e −93,7 no milho;
o tempo custa −39,8 na soja (significativo) e −6,9 no milho (n.s.).

## D88 - CAD: unidade validada, CAD de perfil não é CAD efetiva (2026-11-14)

Decisão: a unidade `mm/cm` é aceita porque é **verificada numericamente** — o
maior valor amostrado é 2,59 e a leitura volumétrica (cm³/cm³) exigiria ≤ 1,0.
A CAD integrada é a soma `AW(mm/cm) × espessura(cm)` por camada. A CAD do
perfil **não** é a CAD efetiva de uma cultura: atribuir profundidade radicular
exige fonte cultivar-específica e não é feito.

Consequência: o déficit anual mediano cai 18,6% com a CAD de 0–100 cm e 42,3%
com a de 0–200 cm, enquanto a faixa 35/50/70 mm da V2.6 o move em ±3%. Os
cenários da V2.6 **não eram uma análise de sensibilidade significativa**: a
50 mm corresponde a ~23 cm de solo, mais rasa que qualquer zona radicular de
cultura.

Cobertura: apenas 5 dos 1.296 municípios do painel têm CAD (0,39%). A
integração ao painel exige extração WCS massiva e fica condicionada ao
diagnóstico de cobertura (missão §12), como item de V2.9.

Nota metodológica: por ser regressor, um reescalonamento **uniforme** da CAD
não altera o teste t. O que altera a inferência é a heterogeneidade entre
municípios (126–240 mm, razão 1,9) — que não pode ser simulada por um fator
único.

## D89 - `zarc_cycle` é classe de ciclo, não cultivar (2026-11-14)

Decisão: o campo `zarc_cycle` do painel é a classe `Cod_Ciclo` da portaria
ZARC. Ele **não** identifica cultivar e **não** recebe rótulo
("precoce/médio/tardio") porque a correspondência não está documentada nos
artefatos adquiridos — o dicionário de dados do ZARC é um PDF não coletado.
As classes são citadas por código.

Consequência: a estratificação por classe é um teste de **estabilidade da
associação**, não uma comparação de materiais genéticos. Resultado: na soja a
temperatura **inverte de sinal** na classe 21 (+182,7; t=+4,38) contra a
classe 22 (−65,0; t=−3,18), que concentra 89% das linhas; no milho o déficit é
negativo nas três classes; no milho 2ª safra nenhuma associação sobrevive
dentro das classes. A duração modal da janela ZARC difere por classe, o que
mostra que colapsar as classes numa janela modal mistura calendários.

## D90 - Equalização de treino é por célula, não apenas na média (2026-11-14)

Decisão: quando o desenho compara braços com informação diferente, a
igualdade de tamanho de treino deve ser garantida **em cada célula** (espaço ×
ano), e não apenas pela média. O alvo de cada célula é o menor conjunto
disponível entre os braços; células abaixo de um mínimo viável são descartadas
de **todos** os braços, com a perda registrada.

Motivo: a equalização da V2.8 usava um alvo único. No painel real, o braço
``TE`` ficou em 5.401 linhas em média (alvo 5.686), com **11 de 25 células**
abaixo do alvo e mínimo de 4.308 — a média escondia a desigualdade.

Consequência: refeita a comparação com equalização estrita (25/25 células no
alvo nos quatro braços), as MAEs mudam em ≤ 5,1 kg/ha e os efeitos permanecem
nos mesmos intervalos: soja −6,3 [−14,3;+3,0] (espaço) e −37,0 [−47,3;−23,8]
(tempo); milho −171,5 [−331,6;−32,5] e −26,9 [−46,2;−9,0]. A conclusão da
V2.8 se sustenta.

Ressalva registrada: no milho 2ª safra o efeito espacial passa de
−39,6 [−68,5;+0,5] (não significativo) para −45,5 [−79,0;−0,8] (exclui zero).

Regra de relato: MAE e RMSE calculados **por repetição** e agregados, com a
dispersão entre repetições. Repetições de treino não são observações de teste
independentes e não entram como réplicas no bootstrap.

## D91 - Modelos aninhados M0 → M1 → M2 como referência (2026-11-14)

Decisão: a pergunta "o clima acrescenta valor?" é respondida por modelos
aninhados com o **mesmo** conjunto de treino e de teste:

* **M0** — média global do treino;
* **M1** — média por UF do treino (fallback global para UF ausente);
* **M2** — UF + variáveis agroclimáticas (``climate_plus_state``).

A estatística de interesse é ``M2 − M1``: o valor incremental do clima
**dentro** da UF. ``M1b`` (média UF×ano) permanece apenas como diagnóstico
contemporâneo, nunca como referência operacional. ``M0b`` (``climate_only``)
é mantido para a comparação histórica com a V2.6/V2.7.

Consequência: na soja, ``M2 − M1`` é significativo apenas nos braços com o
ano compartilhado (B: −13,3 em SS e −19,2 em SE) e **não** no braço mais
estrito (TE: −6,3 [−26,8;+10,4]); o modelo hídrico **piora** quando o ano é
retirado (+20,5 [+9,6;+31,7]). No milho 2ª safra, ``M2 − M1`` é significativo
nos quatro braços para a família meteorológica (TE: −267,2 [−413,8;−35,1]).

O fallback de UF foi instrumentado: 0,0% das linhas de teste em todos os
braços deste desenho — ele só seria acionado num leave-one-UF-out.

## D92 - A escala do bloco é uma escolha de desenho, não de ganho (2026-11-14)

Decisão: o efeito do bloco é reportado em 150, 250, 400 e 600 km, com o
número de blocos de cada escala explícito. A escala de 250 km **não** é
reotimizada em função do resultado; nenhuma escala é escolhida por produzir
maior ganho.

Consequência: no milho o efeito espacial é −47,1 (150 km, 107 blocos),
−170,8 (250 km, 49), −152,4 (400 km, 26) e −415,1 (600 km, 15). Há efeito a
partir de 250 km; a 150 km o bloco é pequeno demais para remover informação
útil. Em 600 km o poder cai (14–15 blocos) e o valor não deve ser lido como
estimativa estável. Na soja o efeito é ~0 em 150/250/400 km.

A decomposição por UF mostra que o efeito do bloco no milho está concentrado
em PR (+421,4), BA (+291,0) e MS (+170,9), é ~0 em GO e MT e negativo em RS:
é heterogeneidade **dentro** da UF, não um gradiente nacional.

## D94 - Dicionário oficial do ZARC e correção da leitura por classe (2026-11-14)

Decisão: os códigos do ZARC são documentados pela fonte oficial e a
heterogeneidade por classe é testada por **interação**, não pela comparação
de dois coeficientes estimados em separado.

Fonte: *Dicionário de Dados — Tábua de Risco (ZARC)*, MAPA/CGRA-DEGER-SPA,
versão `dicionario-de-dados-tabua-de-risco-2026.pdf`, consultado em
2026-11-14, licença CC-BY.
`Cod_Ciclo`: 13 Perene, 19 Semiperene, 20 Grupo I, 21 Grupo II, 22 Grupo III,
24 Grupo IV, 25 Grupo V, 26 Grupo VI.
`Cod_Solo`: 1 Arenoso, 2 Textura Média, 3 Argiloso, 11–16 AD1–AD6.
**Grupo de ciclo não é cultivar**, e o documento **não** rotula os grupos
como precoce/médio/tardio.

Teste: ``y_w = b1·x_w + b2·(x·I_grupo)_w``, transformação within por
município e ano, erro agrupado por bloco (CR1), ``b2`` = diferença de
inclinação entre grupos.

Consequência — **correção da V2.8**: a afirmação de que a temperatura da soja
"inverte de sinal" entre as classes 21 e 22 **não se sustenta**. Estimadas em
separado, as inclinações eram +182,7 (t=+4,38) e −65,0 (t=−3,18); no teste
formal a diferença é −3,98 (t=−0,88; p=0,38). O contraste anterior era
artefato de estimar cada classe com a sua própria transformação within.
Resultados do teste formal: soja déficit −1,194 (t=−3,16; p=0,003); soja
temperatura e precipitação não significativos; milho precipitação −1,017
(t=−2,05; p=0,046, marginal e não ajustado para 9 testes); demais não
significativos. Após multiplicidade, nenhuma diferença entre grupos
sobrevive.

Regra derivada: não declarar dois coeficientes diferentes com base em um ser
significativo e o outro não; usar interação com erro-padrão próprio.

## D96 - Aquisição da CAD por UF com máscara de polígono municipal (2026-11-14)

Decisão: a CAD é adquirida **uma requisição por UF e por camada** (6 UFs × 6
camadas = 36 janelas) e agregada **pelo polígono oficial do município**, não
pelo bbox.

Motivo: a extração municipal da V2.9 exigia ~7.800 requisições (~5 h) e
agregava por bbox. A varredura por UF é 200× mais rápida e, com o raster
alinhado, permite mascarar o limite municipal.

Consequência medida: 1.296 de 1.296 municípios do painel cobertos, **0 sem
dado**, em **71 s** e 610 MB transferidos. CAD 0–100 cm entre 105,1 e 256,9 mm
(mediana 174,5); por UF de 138,4 (MS) a 195,1 (RS). Fração de pixels válidos
por município: mínimo 0,605, mediana 1,000; apenas 4 municípios abaixo de 0,90.

Validação de geometria (18 municípios, mesma área): mediana por polígono vs
bbox difere em 0,85 mm (máx. 10,3 mm; correlação 0,994). O bbox da V2.9 era
uma aproximação aceitável, mas o polígono remove o viés de forma.

## D97 - A janela ZARC do painel histórico perde o último mês (2026-11-14)

Decisão: corrigir a seleção de dias da janela e manter as duas semânticas em
`cycle.window_bounds`.

Defeito: o painel comparava `months[0] <= data <= months[-1]` com
`months[-1]` no formato `"AAAA-MM"`. Como `"2017-12-01" > "2017-12"` na ordem
lexicográfica, o **mês final era inteiramente excluído**; e o início era
aceito a partir do dia 1º, incluindo dias anteriores ao início real da janela.
Em **28.282 de 40.990 linhas** (69%) o número de meses usados difere do número
listado; nas 19.402 linhas analíticas, **todas** perdem ~31 dias.

Consequência: com a janela corrigida e a mesma CAD (50 mm), o déficit cresce
(razão mediana 1,236; p90 3,78) e a precipitação e a ET0 da janela sobem
(medianas +135,4 mm e +165,1 mm). A reprodução da janela histórica é exata
(19.402 pares; diferença máxima 1,05e-5 mm, resíduo de float32).

Regra: qualquer número de versões anteriores passa a ser identificado como
"janela histórica"; o novo painel usa a janela corrigida e as duas nunca são
misturadas sem rótulo.

## D98 - A CAD oficial não melhora a predição e não explica o efeito do bloco (2026-11-14)

Decisão: usar a CAD oficial como representação **preferida** do solo para
descrição e associação, mas **não** adotá-la como variável preditiva sem
ganho demonstrado, e registrar o resultado negativo.

Evidência (TE, `M2 − M1`, diferença de MAE; negativo = modelo melhor):

| Cultura | clima | déficit hist. | déficit 50 mm corrigido | CAD 0–100 | CAD 0–200 |
|---|---|---|---|---|---|
| soja | −6,3 n.s. | **+10,6 [0,7;21,5]** | −20,0 n.s. | −10,3 n.s. | −6,9 n.s. |
| milho | −198,7 | −167,1 | −195,2 | −142,8 | −21,7 n.s. |
| milho 2ª | −267,2 | n.s. | n.s. | n.s. | n.s. |

Ou seja: (i) na soja o déficit da janela histórica era **pior que a média da
UF** e a correção da janela reverte isso; (ii) em nenhuma cultura a CAD
oficial melhora a predição em relação à CAD de 50 mm com a janela correta;
(iii) no milho o efeito do bloco (SS−SE) **cresce** com a CAD (−209 hist →
−225 em 0–100 → −286 em 0–200), logo a heterogeneidade espacial não era
deficiência de representação do solo.

Associação (within, EP agrupado por bloco, 15 hipóteses, Holm): o coeficiente
do déficit da soja vai de −1,26 (histórico) a −2,45 (janela corrigida) e
permanece em −2,32/−2,29 com a CAD oficial, enquanto a média do déficit cai de
138,5 para 13,8 mm — a CAD reescala o déficit quase proporcionalmente e não
altera a associação. 10 de 15 hipóteses sobrevivem ao Holm.

## D99 - Profundidade radicular: 0–100 cm na soja, 40–50 cm no milho (2026-11-14)

Decisão: os cenários de perfil passam a ter justificativa publicada, e não
apenas a escada 0–60/0–100/0–200 cm.

* **Soja** — Franchini et al. (Embrapa Soja, safra 2008/2009) avaliaram o
  sistema radicular até 100 cm e mediram 6–12% da área radicular na camada
  75–100 cm. Limitar o reservatório a 60 cm descartaria 17–33% do sistema
  radicular; **0–100 cm** é o cenário de referência.
* **Milho** — Embrapa Milho e Sorgo (Albuquerque & Resende, *Cultivo do
  Milho — Irrigação*) declara profundidade efetiva do sistema radicular
  **Z = 40–50 cm** para manejo de irrigação. O cenário **0–60 cm** é o mais
  próximo disponível nas camadas publicadas.
* **Milho 2ª safra** — sem fonte específica; mantido como **cenário** igual ao
  milho, explicitamente identificado como aproximação.

Nenhuma profundidade foi atribuída por cultivar. A distinção entre
profundidade máxima de raiz isolada e profundidade efetiva de extração é
mantida.

## D100 - Contrato temporal da janela ZARC: meses completos, com semântica histórica preservada (2026-11-14)

Decisão: `cycle.window_bounds(months, corrected=True)` é o **protocolo padrão**
da V3.1. Ele devolve o primeiro dia do primeiro mês e o **último dia do último
mês**. A semântica histórica (`corrected=False`) continua disponível e é usada
para reproduzir o painel V2.6/V3.0, nunca para produzir variável nova.

Causa confirmada (D97): a consulta comparava a data diária `"AAAA-MM-DD"` com o
rótulo mensal `"AAAA-MM"`. Como `"2017-12-01" > "2017-12"` na ordem
lexicográfica, o último mês era **inteiramente excluído**. Não era um erro de
índice de um único dia: era um mês inteiro por janela.

O defeito não afetava só o déficit. Afetava toda variável agregada na janela.
Reconstruindo as 19.402 linhas analíticas com as mesmas funções do painel, as
medianas passam de (a última coluna é a **mediana da variação relativa por
linha**, não a razão entre medianas):

| variável | janela histórica | janela corrigida | mediana da variação relativa |
|---|---:|---:|---:|
| precipitação acumulada | 338,3 mm | 491,4 mm | +44,0% |
| ET0 acumulada | 390,0 mm | 557,5 mm | +43,5% |
| graus-dia | 1.018,9 | 1.489,8 | +45,5% |
| dias com chuva | 59 | 88 | +45,6% |
| noites quentes | 26 | 44 | +54,3% |
| déficit hídrico | 51,3 mm | 106,0 mm | +23,6% |
| excedente hídrico | 58,4 mm | 91,9 mm | 0,0% |
| temperatura média | 24,33 °C | 24,41 °C | +1,0% |

Logo: toda a pesquisa agroclimática da V2.6 a V3.0 foi conduzida com **um mês
inteiro a menos por janela** (tipicamente 17–25% do período), o que reduzia as
variáveis acumuladas em ~44%. Os resultados anteriores permanecem registrados e
reproduzíveis (`_legacy`), mas **nenhuma conclusão da V3.1 se apoia neles**. A
reprodução da janela histórica contra o painel publicado confere até o erro de
float32 (diferença máxima 1,7e-5 em 19.402 linhas; `temp_media_c` e
`extreme_heat_days` exatos), o que mostra que as diferenças observadas são do
defeito, e não do pipeline.

Consequência de engenharia: o painel derivado `v31_panel_windows.csv` carrega
as **duas** semânticas lado a lado (`_legacy` e `_corrected`) e as três
profundidades de CAD na janela corrigida. A janela histórica nunca é
sobrescrita.

## D101 - A janela corrigida fortalece o clima no milho e não resgata a soja (2026-11-14)

Decisão: a correção da janela **não** transforma o clima em preditor útil da
soja; no milho ela melhora de forma mensurável o modelo climático. Nenhuma
alegação de generalização é feita fora do braço TE.

TE, `climate_plus_state` contra a média da UF, equalização estrita por célula,
IC por bootstrap de bloco (250 km), mesma especificação e mesmas linhas:

| Cultura | janela histórica | janela corrigida | pareado (corrigida − histórica) |
|---|---:|---:|---|
| soja | −6,3 n.s. | −18,5 n.s. | −12,2 [−24,0; 4,9] n.s. |
| milho | −198,7 | **−228,5** [−403,5; −37,0] | **−29,8** [−51,5; −2,3] |
| milho 2ª | −267,2 | −228,4 | +38,8 [−1,8; 59,7] n.s. |

O ganho no milho **não** é uniforme entre UFs. Diferença de MAE do clima
corrigido contra a média da UF, por UF:

| UF | milho | soja | milho 2ª |
|---|---:|---:|---:|
| PR | **−607,4** | **−61,8** | **−366,1** |
| BA | −131,1 | — | — |
| GO | −109,9 | +29,6 | +13,8 |
| MT | +85,0 | +17,7 | −28,2 |
| MS | +261,4 | +19,8 | +35,8 |
| RS | +12,8 | −20,7 | — |

Ou seja: o valor climático do milho está concentrado em **PR**, com contribuição
moderada de BA e GO, e o modelo climático é **pior** que a média da UF em MS,
MT e RS. A MAE agregada esconde essa heterogeneidade; ela não pode ser
apresentada como "o clima explica o milho". Na soja o único ganho relevante
também é de PR, e o agregado continua não significativo.

## D102 - Tendência espacial (M3/M4) rejeitada no protocolo TE (2026-11-14)

Decisão: latitude/longitude com termos quadráticos (centragem por constantes
fixas, sem vazamento) **não** substitui nem complementa a média da UF.

| Cultura | M3 (tendência + UF) vs M1 | M3 vs M2 (pareado) | M4 vs M3 (pareado) |
|---|---:|---:|---:|
| soja | +2,8 n.s. | +21,3 n.s. | −18,6 n.s. |
| milho | +159,6 n.s. | **+388,1** [62,0; 719,5] | **−175,7** [−318,2; −33,2] |
| milho 2ª | −49,7 n.s. | **+178,7** [43,8; 342,7] | **−131,5** [−265,5; −39,0] |

No milho a tendência espacial é **pior** que o clima (pareado, IC exclui zero) e
destrói exatamente o ganho que o clima tinha em PR. A leitura correta é que um
gradiente suave global não descreve a estrutura regional do milho: a
heterogeneidade é por UF/grupo de UFs, não um plano inclinado. A comparação
M4 vs M3 não deve ser lida como "clima ajuda" isoladamente, porque M3 é um
modelo ruim; a comparação relevante é M2 vs M1 (D101).

A complexidade dos termos espaciais foi fixada antes da avaliação (quadrático
completo); não foi escolhida por TE. O modelo espacial nunca é apresentado como
definitivo.

## D103 - Vizinhos históricos (M1c) superam a média da UF, com cobertura declarada (2026-11-14)

Decisão: a média das produtividades **já observadas no treino** dos municípios
vizinhos é um baseline experimental válido e melhor que a média da UF, no
protocolo TE. Ele **não** substitui o modelo climático e não é comparado a ele
de forma pareada (conjuntos de linhas diferentes).

Desenho: o treino de cada célula exclui o bloco espacial e o grupo temporal do
teste; a previsão usa apenas médias de municípios de **outros blocos** e
**outros anos**; fallback para a média da UF calculada no treino, depois para a
média global. Grade de parâmetros fixada antes da avaliação.

| Cultura | configuração | MAE M1c | MAE M1 | delta | cobertura direta | fallback |
|---|---|---:|---:|---:|---:|---:|
| soja | r200/d100/k3 | 583,0 | 610,7 | **−27,7** [−52,3; −3,8] | 0,987 | 0,013 |
| soja | r100/d50/k3 | 590,0 | 610,7 | **−20,7** [−40,9; −1,1] | 0,667 | 0,333 |
| milho | r200/d100/k3 | 1.624,5 | 1.917,1 | −292,6 [−631,0; 4,1] | 0,961 | 0,039 |
| milho | r100/d50/k3 | 1.791,3 | 1.917,1 | **−125,8** [−245,7; −10,7] | 0,454 | 0,546 |
| milho 2ª | r300/d150/k3 | 1.311,3 | 1.500,8 | **−189,6** [−312,5; −11,7] | 1,000 | 0,000 |

Ressalvas mantidas: (i) o ganho depende do raio e do decaimento, e a única
configuração com IC excluindo zero **e** boa cobertura para o milho é r300;
(ii) em raios pequenos a cobertura cai muito e o baseline degenera na média da
UF; (iii) o ponto estimado de M1c para o milho é menor que o do clima corrigido,
mas a comparação não é pareada e não é usada como evidência.

Leitura científica: a persistência espacial da produtividade entre anos
diferentes carrega informação sobre municípios não observados — mais do que a
média da UF. Isso é consistente com a V3.0 (a CAD não explicava o efeito do
bloco) e com D102 (não é um gradiente suave). Não é evidência causal.

## D104 - A unidade de inferência das inclinações climáticas é UF×ano, não bloco espacial (2026-11-14)

Decisão: testes de inclinação climática passam a usar **agrupamento duplo**
(`two_way_cluster_vcov`) por **UF×ano** e por **município**. O agrupamento por
bloco espacial fica disponível apenas como sensibilidade histórica.

Motivo: a anomalia climática de um ano é essencialmente a mesma para todos os
municípios de uma UF. Um bloco de 250 km é **menor** que a UF, então agrupar por
bloco trata milhares de linhas praticamente independentes como se fossem
observações distintas e produz erros-padrão otimistas. A unidade que varia de
fato é o par UF×ano.

Efeito medido no painel (mesmo modelo, mesmos dados, só o agrupamento muda):

| cultura | variável | F (bloco) | p (bloco) | F (UF×ano + município) | p |
|---|---|---:|---:|---:|---:|
| soja | precipitação | 8,74 | 0,0000 | 1,13 | 0,3565 |
| soja | temperatura | 10,33 | 0,0000 | 1,89 | 0,1308 |
| milho | precipitação | 2,28 | 0,0614 | 1,03 | 0,4099 |
| milho | temperatura | 4,89 | 0,0011 | 2,47 | 0,0454 |
| milho 2ª | precipitação | 3,30 | 0,0342 | 2,77 | 0,0584 |
| milho 2ª | temperatura | 10,05 | 0,0001 | 6,27 | 0,0019 |

A razão entre os erros-padrão é de ~2,5–3×. **Consequência retroativa:** os
p-valores de associação reportados na V2.7–V3.1 com agrupamento por bloco são
otimistas e não devem ser citados como evidência confirmatória.

Verificação feita (não presumida): as comparações **preditivas** da V3.1 foram
recalculadas com os dois esquemas de reamostragem
(`v32_v31_resampling_sensitivity.json`). O efeito pareado da correção da janela
no milho sobrevive (−29,78; bloco [−51,5; −2,3]; UF×ano [−52,5; −2,6]). Mas a
conclusão sobre milho 2ª **muda**: +38,75 era não significativo por bloco
([−1,8; 59,7]) e passa a significativo por UF×ano ([2,4; 71,9]) — isto é, a
correção da janela piora a 2ª safra de forma detectável, não apenas sugestiva.
Registrado como correção da leitura da V3.1, não como novo achado.

## D105 - A heterogeneidade de inclinações NÃO está estabelecida (2026-11-14)

Decisão: os desníveis de desempenho por UF da V3.1 (PR −607,4; MS +261,4; …)
**não** são evidência de inclinações climáticas diferentes. São diferenças de
erro preditivo, e a estimação direta das inclinações não sustenta a leitura
mecanicista.

Família confirmatória: 6 testes globais (3 culturas × 2 variáveis primárias),
Holm. Somente **milho 2ª × temperatura** sobrevive (p = 0,0019; Holm = 0,0113).
Os demais: soja precipitação 0,357 (Holm 0,713); soja temperatura 0,131 (0,392);
milho precipitação 0,410 (0,713); milho temperatura 0,045 (0,227); milho 2ª
precipitação 0,058 (0,234).

Nenhum contraste individual por UF sobrevive ao Holm em nenhuma cultura
(p_holm ≥ 0,195 em todos). Em soja, os quatro contrastes de temperatura têm
p individual entre 0,029 e 0,050 com IC95 excluindo zero, e **todos** deixam de
ser significativos após Holm — o exemplo didático de por que não se lê uma
tabela de p-valores estaduais como evidência.

Registrado também: a inclinação de referência de milho 2ª em GO para
temperatura (+856 kg/ha/°C) é implausível e vem de 5 anos e 285 linhas. É
justamente o tipo de estimativa que o partial pooling existe para evitar, e um
sinal de que aquele contraste não é interpretável.

## D106 - Partial pooling implementado como ridge sobre os desvios estaduais (2026-11-14)

Decisão: `M2-HET-PP` é implementado como **ridge sobre os desvios estaduais**
em direção à inclinação comum, com λ escolhido por validação interna 5-fold
**bloqueada por bloco espacial dentro do pool de treino de cada célula**. A
penalidade é relativa à diagonal de Gram, de modo que o encolhimento de cada
desvio é `1/(1+λ)`, independente de escala e de n.

Com 4–6 UFs não é possível estimar de forma confiável a variância de uma
distribuição de efeitos aleatórios. O estimador implementado é o MAP de um prior
normal centrado em zero, não um modelo hierárquico completo: **não há estimativa
REML da variância entre UFs nem intervalos que incorporem a incerteza do
encolhimento**. Essa limitação é declarada em todo resultado que use o modelo.

Resultado do partial pooling em TE (ΔMAE contra a inclinação comum; negativo =
melhor): soja +10,9; milho **−77,6** [−143,9; −4,8] (bootstrap UF×ano) e
[−162,7; 14,5] (bloco); milho 2ª +6,1. Ver D105 e o relatório: o ganho do milho
é instável (ver D107 e a análise leave-one-UF-out).

## D107 - M1c não substitui M1 nem M2 (2026-11-14)

Decisão: os vizinhos históricos continuam como **baseline secundário**. A V3.2
fez a comparação pareada que faltava (mesmas linhas, alinhadas por município e
ano) e decompôs cobertura × fallback:

* **M1c bate M1** de forma consistente no protocolo TE, em todas as culturas, com
  bootstrap por UF×ano: soja −27,7 [−46,2; −8,1]; milho −292,6 [−401,2; −169,3];
  milho 2ª −194,5 [−311,5; −63,9] (raio 200 km, decaimento 100 km, 3 vizinhos).
* **M1c não bate M2**: soja −9,2 [−49,2; 25,6]; milho −64,1 [−146,1; 2,9];
  milho 2ª +33,9 [−85,6; 162,4]. Nenhum IC exclui zero. Não há base para trocar
  o modelo climático pelo baseline de vizinhos.
* O **fallback não é neutro**: os casos atendidos por vizinhos vão muito melhor
  que os casos que caem na média da UF (milho: 1.604,9 contra 2.103,5 kg/ha de
  MAE). Relatar a cobertura agregada esconderia que o baseline degenera
  exatamente onde não há vizinho — em raio de 100 km no milho isso é 45% das
  linhas.


