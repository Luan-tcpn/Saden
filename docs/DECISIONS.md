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

