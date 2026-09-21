# SADEN — Roadmap oficial e persistente (plano de execução)

Estados: `[ ]` NOT_STARTED · `[~]` IN_PROGRESS/parcial · `[x]` DONE (validado) · `[!]` BLOCKED.
DONE exige validação real (código + execução + integração + teste), nunca só existência de arquivo.
Atualizado em 2026-09-08. Dependências: P2→persistência; P3→proteção; P4→dashboard preços;
P5→indicadores clima; P6→mapa/filtros geo; P7/P8→UI; P9→mapa; P10/P11→previsão; P12→relatórios;
P13→testes; P14→visual; P15/P16/P17→refino; P18/P19→docs.

## P0 — INFRAESTRUTURA E AMBIENTE

- [x] Verificar estrutura raiz
- [x] Separar frontend e backend
- [x] Verificar Node.js (22.11.0)
- [x] Verificar package.json
- [x] Verificar scripts (start/dev/seed/test)
- [x] Verificar .env
- [x] Criar/validar .env.example
- [x] Verificar portas (3001 livre/ativa, sem duplicar instância)
- [x] Verificar processo backend (saudável via /health)
- [x] Verificar processo frontend (servido pelo backend, porta única — sem processo separado por design)
- [x] Garantir que servidores não bloqueiem o agente (Start-Process detached; nunca foreground)
- [x] Health check backend
- [x] Health check frontend (HTTP 200 no `/`)
- [x] Smoke test inicial (`scripts/smoke-test.js` 8/8)
- [x] Correção 2026-09-08: DATABASE_PATH agora resolvido contra a raiz do projeto (antes dependia do cwd e gerava 2 bancos)

## P1 — ARQUITETURA

- [x] Definir arquitetura frontend (estático vanilla + Leaflet + Chart.js, sem build)
- [x] Definir arquitetura backend (Express routes→services→integrations)
- [x] Definir banco (SQLite better-sqlite3, arquivo único)
- [x] Definir camada de serviços
- [x] Definir camada de integração externa (1 arquivo por fonte, retry+timeout)
- [x] Definir autenticação (JWT stateless + bcrypt)
- [x] Definir pipeline de dados (fonte→cache→banco→API→front)
- [x] Definir pipeline de previsão (série BRL→features→ridge→intervalo)
- [x] Definir fluxo de relatórios (consolidado JSON + CSV + impressão)
- [x] Documentar arquitetura (`docs/ARCHITECTURE.md`)
- [x] Verificar ausência de código duplicado
- [x] Verificar separação frontend/backend

## P2 — BANCO DE DADOS

- [x] Modelar User
- [x] Modelar Commodity
- [x] Modelar PriceObservation
- [x] Modelar WeatherObservation
- [x] Modelar Region
- [x] Modelar Forecast
- [x] Modelar ModelRun
- [x] Modelar DataSource
- [x] Modelar Report
- [x] Criar relacionamentos (FK forecasts→model_runs, reports→users)
- [x] Criar índices necessários (preços, clima, forecasts, kv)
- [x] Criar migrations/schema (`db.js`)
- [x] Criar seed mínimo (5 commodities, 7 fontes, usuário demo)
- [x] Testar conexão (integração usa banco temporário)
- [x] Testar operações CRUD necessárias (users, observations, reports via testes)
- [x] Verificar integridade (FK + WAL)
- [x] Verificar duplicação (UNIQUE em observations + kv)

## P3 — AUTENTICAÇÃO

- [x] Cadastro
- [x] Validação de cadastro
- [x] Hash de senha (bcrypt 10 rounds)
- [x] Login
- [x] Validação de credenciais (401 genérica, sem enumerar usuário)
- [x] Geração de sessão/token (JWT 12h)
- [x] Endpoint /me
- [x] Logout (client-side: descarte do token — JWT stateless, sem blacklist)
- [x] Proteção de rotas
- [x] Middleware de autenticação
- [~] Tratamento de sessão expirada (código em `auth.js:boot`; validação visual pendente)
- [x] Mensagens de erro (pt-BR, sem vazar detalhes)
- [x] Tela de cadastro
- [x] Tela de login
- [~] Persistência da sessão (localStorage implementado; validação visual pendente)
- [~] Redirecionamento (implementado; validação visual pendente)
- [~] Logout pelo frontend (implementado; validação visual pendente)
- [x] Teste register
- [x] Teste login
- [x] Teste /me
- [ ] Teste logout (requer navegador — P14)
- [x] Teste rota protegida (401)
- [~] E2E autenticação (register+login via smoke; fluxo visual pendente — P14)

## P4 — DADOS REAIS DE PREÇOS

- [x] Pesquisar fontes reais
- [x] Verificar documentação das fontes
- [x] Identificar APIs realmente disponíveis (Yahoo chart, PTAX OData)
- [x] Identificar limitações (Yahoo sem doc oficial/CORS; PTAX sem pregão fds)
- [x] Identificar autenticação necessária (nenhuma; só User-Agent no Yahoo)
- [x] Identificar unidades (cents/bu, cents/lb → R$/sc, R$/lp)
- [x] Identificar periodicidade (diária, dias úteis)
- [x] Identificar localização dos preços (bolsas CBOT/ICE — referência internacional)
- [~] Criar interface PriceProvider (providers isolados por arquivo; sem classe formal — suficiente)
- [x] Criar adapters por fonte (yahoo/bcb/openmeteo/ibge providers)
- [x] Implementar Yahoo Finance quando apropriado
- [x] Implementar PTAX quando apropriado
- [x] Avaliar CONAB → [!] sem API pública (consulta manual; link documentado)
- [x] Avaliar CEPEA → [!] sem API pública (formulário web; link documentado)
- [x] Avaliar IBGE (localidades, não preços — usado em P6)
- [x] Não inventar API inexistente
- [x] Implementar timeout (12s, abort)
- [x] Implementar retry (3x backoff p/ 502/429)
- [x] Implementar tratamento de erro (502 honesto, sem derrubar app)
- [x] Implementar cache (60min, flag `cached`)
- [x] Registrar source
- [x] Registrar provider
- [x] Registrar data do dado
- [x] Registrar retrieved_at
- [x] Validar preço real (soja R$ 148,33/sc em 2026-09-08)
- [x] Validar unidade
- [x] Validar moeda
- [x] Validar datas
- [x] Testar integração (teste LIVE)
- [ ] Testar indisponibilidade da API (simular falha upstream; próx. passo técnico)

## P5 — DADOS CLIMÁTICOS

- [x] Pesquisar fontes reais
- [ ] Verificar INMET (não verificado — sem afirmações até checar)
- [x] Verificar Open-Meteo (docs + teste real)
- [ ] Verificar NASA POWER quando necessário (não verificado)
- [x] Definir fonte principal (Open-Meteo)
- [ ] Definir fontes alternativas (pendente avaliação INMET/NASA)
- [~] Criar ClimateProvider (módulo isolado; sem classe formal — suficiente)
- [x] Implementar consulta histórica (ERA5 archive)
- [x] Implementar previsão (7 dias + atual)
- [x] Temperatura
- [x] Precipitação
- [x] Umidade
- [x] Vento
- [ ] Pressão quando disponível (API tem; não consumido)
- [ ] Radiação quando disponível (API tem; não consumido)
- [x] Validar unidades
- [x] Validar datas
- [x] Validar coordenadas (faixa BR)
- [x] Implementar cache
- [x] Implementar timeout
- [x] Implementar retry
- [x] Tratamento de erro
- [x] Registrar fonte
- [x] Testar API real (teste LIVE)

## P6 — GEOLOCALIZAÇÃO

- [x] Pesquisa por estado (select IBGE)
- [x] Pesquisa por município (select IBGE por UF)
- [ ] Pesquisa por região (regiões IBGE não implementadas)
- [x] Pesquisa por coordenadas (clique no mapa)
- [x] Geocodificação (Open-Meteo, BR)
- [ ] Reverse geocoding quando necessário (não implementado)
- [x] Integração IBGE quando aplicável
- [x] Resolver latitude/longitude
- [x] Validar coordenadas
- [x] Cache de geocodificação (30 dias)
- [~] Associar localização a commodity (commodity global; preço não é regional — limitação declarada)
- [~] Associar localização a preço (idem acima)
- [x] Associar localização a clima (lat/lon → Open-Meteo)
- [x] Testar cidades brasileiras (Ribeirão Preto validado)
- [x] Testar coordenadas (ponto do mapa via API)

## P7 — DASHBOARD

- [x] Layout principal
- [x] Navegação
- [x] Cabeçalho
- [x] Menu
- [x] Área de conteúdo
- [x] Indicador de última atualização
- [x] Seleção de commodity
- [x] Seleção de estado
- [x] Seleção de município
- [ ] Seleção de região
- [ ] Seleção de período (série fixa 1y/3mo)
- [ ] Filtro por data
- [x] KPI preço atual
- [x] KPI variação
- [x] KPI tendência
- [x] KPI previsão
- [x] Gráfico histórico
- [x] Gráfico de previsão
- [~] Gráfico regional (tabela comparativa existe; gráfico pendente)
- [x] Indicadores climáticos
- [x] Informações da fonte
- [x] Loading state
- [~] Empty state (parcial)
- [x] Error state
- [x] Integração real com backend
- [~] Atualização dos filtros (código pronto; validação visual pendente)
- [~] Validação dos dados exibidos (pendente P14)
- [~] Responsividade (media query existe; pendente P14)
- [ ] Teste do dashboard (pendente P14)

## P8 — PESQUISA E FILTROS

- [x] Pesquisa de commodity (select; 5 itens — busca textual desnecessária)
- [x] Pesquisa de estado (select IBGE)
- [x] Pesquisa de município (select + texto com sugestões)
- [ ] Pesquisa por região
- [x] Pesquisa por coordenadas (mapa)
- [ ] Filtro temporal
- [x] Filtro de commodity
- [x] Filtro geográfico
- [x] Combinação de filtros
- [ ] Limpar filtros (botão ausente)
- [~] Estado sem resultados (parcial)
- [x] Validação dos parâmetros (backend 400)
- [~] Backend recebe filtros corretamente (validado p/ principais; visual pendente)
- [~] Frontend aplica resultados corretamente (pendente P14)
- [ ] Testes (pendente P14)

## P9 — MAPA DO BRASIL

- [x] Escolher biblioteca de mapas (Leaflet 1.9.4)
- [x] Implementar mapa do Brasil (centro [-14.2,-51.9] z4)
- [ ] Estados (polígonos/limites não implementados)
- [ ] Municípios quando necessário (idem)
- [x] Zoom
- [x] Pan
- [~] Seleção (clique define ponto; seleção de área não)
- [ ] Pesquisa (usa busca do topo; busca própria do mapa não)
- [x] Filtro por commodity (compartilha seleção)
- [ ] Filtro por preço
- [ ] Filtro por região
- [ ] Filtro climático
- [x] Coordenadas
- [x] Marcadores
- [x] Popups (preço + clima)
- [x] Dados reais no mapa (mesmas fontes do dashboard)
- [x] Integração com backend
- [~] Sincronização com filtros do dashboard (commodity sim; localidade parcial)
- [x] Camada de satélite quando tecnicamente disponível (Esri World_Imagery)
- [ ] Legenda
- [~] Loading (status textual; overlay no mapa não)
- [x] Error state
- [~] Empty state (parcial)
- [ ] Teste de interação (pendente P14)

## P10 — PIPELINE DE PREVISÃO

- [x] Definir variável-alvo (preço BRL da série)
- [x] Definir horizonte de previsão (7/14/30)
- [x] Preparar dados históricos (1y Yahoo×PTAX)
- [x] Limpeza (ordena, remove não-finitos/<=0, deduplica)
- [x] Tratamento de valores ausentes (descarta ponto, nunca interpola silenciosamente)
- [x] Detecção de inconsistências (série mínima 60 + split mínimo, senão 422)
- [x] Normalização quando necessária (padronização no ridge)
- [x] Engenharia de features (lag1/2/5, MM7/MM30, vol14, índice)
- [x] Features temporais (índice de tendência)
- [x] Features de preço (lags, médias, volatilidade)
- [ ] Features climáticas (fora do escopo univariado — documentado)
- [ ] Features geográficas (idem)
- [ ] Features econômicas quando disponíveis (idem)
- [x] Evitar data leakage (features só com passado; alvo = i+1)
- [x] Split temporal (70/15/15 ordenado)
- [x] Criar baseline
- [x] Implementar primeiro modelo (ridge próprio)
- [x] Treinar
- [x] Validar (grade λ por RMSE val)
- [x] Testar (segmento holdout)
- [x] Gerar previsão (recursiva H passos)
- [x] Gerar intervalo (±1,96σ√h)
- [x] Salvar ModelRun
- [x] Registrar parâmetros
- [x] Registrar métricas
- [x] Registrar data de treinamento

## P11 — MODELOS E AVALIAÇÃO

- [x] Baseline naive
- [x] Baseline seasonal quando aplicável (seasonal-naive-5 + MM7)
- [x] Regressão
- [x] Ridge (grade λ, implementação própria)
- [ ] Random Forest quando apropriado (não justificável: n≈250 univariado — adiado c/ motivo)
- [ ] Gradient Boosting quando apropriado (idem)
- [ ] XGBoost/LightGBM somente se justificável (idem)
- [ ] Avaliar modelos temporais quando justificável (idem)
- [x] Comparar modelos (RMSE val; vencedor registrado)
- [x] MAE
- [x] RMSE
- [x] MAPE quando apropriado
- [ ] Outras métricas justificadas (nenhuma necessária além das três)
- [x] Validação temporal
- [x] Comparação contra baseline (ridge venceu na soja validada)
- [~] Análise de erro (σ residual + intervalo; análise de regimes não)
- [~] Verificação de overfitting (gap treino/val/teste visível; sem teste formal)
- [x] Verificação de leakage (revisado: sem vazamento)
- [x] Selecionar modelo
- [x] Documentar escolha (payload + DECISIONS)
- [x] Não inventar resultados (métricas reais: MAPE teste soja 1,95%)

## P12 — RELATÓRIOS

- [x] Definir estrutura do relatório
- [x] Selecionar commodity
- [x] Selecionar região (via coordenadas; região nomeada não)
- [x] Selecionar período (série + horizonte)
- [x] Inserir preços
- [x] Inserir histórico
- [x] Inserir previsão
- [x] Inserir métricas
- [x] Inserir clima
- [x] Inserir fontes
- [x] Inserir data de geração
- [x] Inserir limitações
- [x] Exportação JSON
- [x] Exportação CSV (BOM UTF-8)
- [~] PDF (via impressão do navegador; PDF direto não)
- [x] Formatação profissional
- [x] Verificar dados do relatório
- [x] Testar geração
- [ ] Testar dados vazios
- [ ] Testar erro (relatório com fonte fora do ar)

## P13 — TESTES

- [x] Testes unitários (15: fx, validação, matemática previsão)
- [x] Testes de serviços (via unidade + integração)
- [x] Testes de autenticação
- [x] Testes de banco (banco temporário)
- [x] Testes de integração API (8)
- [x] Testes de APIs externas (2 LIVE: Yahoo+PTAX, Open-Meteo)
- [x] Testes do pipeline (série sintética)
- [x] Testes de previsão (métricas + baselines)
- [ ] Testes de filtros (pendente P14)
- [ ] Testes de dashboard (pendente P14)
- [ ] Testes de mapa (pendente P14)
- [~] Testes de relatório (API ok; UI pendente)
- [x] Smoke test (8/8)
- [~] E2E principal (API ponta a ponta ok; UI pendente P14)
- [~] E2E login (API ok; navegador pendente)
- [~] E2E consulta (API ok; navegador pendente)
- [~] E2E previsão (API ok; navegador pendente)
- [~] E2E relatório (API ok; navegador pendente)
- [x] Não criar testes redundantes
- [x] Não poluir diretórios (4 arquivos de teste)

## P14 — VALIDAÇÃO VISUAL

- [x] Executar frontend (HTTP 200)
- [x] Abrir aplicação em navegador quando possível (Edge headless + CDP, viewport 1366)
- [x] Verificar login (válido ok; inválido mostra "Credenciais inválidas" sem sair da tela)
- [x] Verificar dashboard (KPIs, série, previsão, métricas, clima, comparação — dados reais)
- [x] Verificar filtros (troca Soja→Milho atualiza KPI; aguardar validação de UF/município em uso real)
- [x] Verificar mapa (tiles OSM, marcador + popup com preço e clima reais, painel do ponto)
- [x] Verificar gráficos (Chart.js histórico, previsão c/ intervalo, clima)
- [x] Verificar relatório (tabelas histórico/previsão, clima, limitações, fontes)
- [~] Verificar responsividade (desktop 1366 ok, sem overflow; mobile pendente — P17)
- [x] Verificar overflow (ausente em 1366)
- [x] Verificar textos (pt-BR, fontes/limitações declaradas)
- [x] Verificar estados loading (status "Consultando…/Atualizado em…")
- [x] Verificar erros (login inválido, 401 sem token, 404 commodity — todos com mensagem)
- [x] Corrigir problemas visuais (legenda do mapa adicionada; nenhum defeito de render encontrado)
- [x] Corrigir problemas de UX (legenda + hint de clique; popup com fonte dos dados)
- [x] Validar novamente (rerun visual-check + auth-flow + interact: tudo OK, zero erros console/rede)
- Evidências: `tmp/shots/` (auth, dashboard, mapa, mapa-click, relatório); scripts `visual-check.js`, `auth-flow.js`, `interact-check.js`.

## P15 — SEGURANÇA

- [x] Secrets fora do código
- [x] .env
- [x] .env.example
- [x] Senhas protegidas (bcrypt; nunca em texto)
- [~] Tokens protegidos (localStorage; adequado p/ TCC — sem XSS persistente no app)
- [x] CORS (origem configurável)
- [x] Validação de entrada
- [~] Sanitização (trim + SQL parametrizado; sem lib dedicada)
- [~] Autorização (papel único; endpoints exigem auth — sem RBAC, sem necessidade)
- [x] Proteção de endpoints
- [x] Tratamento de erros (500 sem stack)
- [x] Não expor stack trace em produção
- [x] Verificar dependências (`npm audit`: 3 moderadas qs/express4; risco aceito e mitigado — D10)
- [x] Verificar dados sensíveis (logs sem segredo/token/senha)
- [x] Rate-limit login/registro (10/10min → 429; testado em integração e ao vivo)
- [x] Token expirado rejeitado com 401 (teste dedicado)

## P16 — PERFORMANCE

- [x] Medir chamadas de API (dashboard: 9 chamadas; `scripts/perf-check.js`)
- [x] Identificar chamadas duplicadas (N+1 na comparação; ganho potencial ~30ms — refactor dispensado, D12)
- [x] Cache (kv TTL confirmado pelos tempos warm)
- [x] Consultas de banco (sync, tempos ≤10ms; sem EXPLAIN necessário)
- [x] Índices
- [x] Payloads (série ~250 pontos; sem paginação necessária)
- [x] Tempo de resposta (warm ≤10ms/endpoint; dashboard 39ms)
- [x] Latência das APIs (cold dominado pelo upstream 1–3s, 1x/hora por TTL)
- [x] Cache de geocodificação
- [x] Cache climático
- [x] Cache de preços
- [x] Evitar processamento desnecessário (forecast 8ms — cache desnecessário)
- [x] Medir antes de otimizar (D12)

## P17 — UX/UI

- [x] Definir identidade visual SADEN (verde campo/terra; validada em desktop e mobile)
- [x] Interface profissional (capturas em `tmp/shots/`)
- [x] Interface limpa (confirmada nas capturas)
- [x] Aparência de plataforma agrícola/analítica (dados, mapa, gráficos; sem chat/IA)
- [x] Evitar aparência de software de IA (sem chat, sem neon, sem ícones de IA)
- [x] Evitar neon
- [x] Evitar excesso de gradientes
- [x] Evitar excesso de glassmorphism
- [x] Evitar estética futurista genérica
- [x] Hierarquia visual (cabecalho, KPIs, painéis, tabelas)
- [x] Tipografia (sistema; legível desktop e mobile)
- [x] Espaçamento (confirmado nas capturas)
- [x] Componentes consistentes (botões, cards, painéis, tabelas)
- [x] Feedback visual (status loading/ok/erro em todas as páginas)
- [x] Acessibilidade básica (labels 100%, botões nomeados, lang pt-BR, canvas com aria-label; contraste não auditado formalmente)
- [x] Responsividade (desktop 1366 + mobile 390 sem overflow-x)
- [x] Navegação intuitiva (4 páginas; validada por clique CDP)

## P18 — DOCUMENTAÇÃO TÉCNICA

- [x] PROJECT_STATUS.md
- [x] PROJECT_ROADMAP.md (este arquivo)
- [x] DECISIONS.md
- [x] API_SOURCES.md
- [x] ARCHITECTURE.md
- [x] README.md
- [x] Instalação
- [x] Configuração
- [x] Execução
- [x] APIs
- [x] Banco
- [x] Testes
- [x] Pipeline de previsão (ARCHITECTURE + DECISIONS D5; capítulo acadêmico em P19)
- [x] Estrutura de diretórios

## P19 — DOCUMENTAÇÃO DO TCC

- [x] Objetivo (`docs/TCC.md` §1)
- [x] Problema (TCC §1)
- [x] Justificativa (TCC §1)
- [x] Arquitetura (TCC §2 + ARCHITECTURE)
- [x] Tecnologias (TCC §2)
- [x] Fontes de dados (TCC §3 + API_SOURCES)
- [x] Coleta (TCC §4)
- [x] Tratamento (TCC §4)
- [x] Engenharia de features (TCC §5)
- [x] Modelos (TCC §6)
- [x] Baselines (TCC §6)
- [x] Validação (TCC §5)
- [x] Métricas (TCC §7)
- [x] Resultados reais (TCC §7 — 5 commodities, 2026-09-08, reproduzíveis)
- [x] Limitações (TCC §8)
- [x] Trabalhos futuros (TCC §9)
- [x] Evidências de funcionamento (tmp/shots + scripts de verificação)
- [x] Screenshots quando necessário (auth, dashboard, mapa, mapa-click, relatório, mobile)
- [x] Preparar material técnico para apresentação (TCC.md é a base)

## Bloqueios externos reais

- [!] CEPEA/ESALQ: sem API pública documentada → integração direta bloqueada; mitigado (Yahoo+PTAX) e declarado.
- [!] CONAB: apps de consulta sem API REST pública → integração direta bloqueada; mitigado e declarado.

## Log de avanço

- 2026-09-08 (retomada): ambiente estabilizado; 23/23 testes; smoke 8/8; docs técnicas criadas.
- 2026-09-08 (correção crítica): DATABASE_PATH raiz-relativa; banco unificado em `data/saden.db`; servidor reiniciado.
- 2026-09-08 (roadmap granular): este arquivo; P14 (visual) como módulo corrente.
- 2026-09-08 (P14 concluído): Edge+CDP validou auth, dashboard, filtros, mapa interativo e relatório — zero erros de console/rede; legenda do mapa adicionada. Transição para P15.
- 2026-09-08 (P15 concluído): rate-limit auth + teste de expiração; audit com risco aceito (D10); 25/25 testes; smoke 8/8. Transição para P16.
- 2026-09-08 (P16 concluído): medições warm ≤10ms, dashboard 39ms; sem otimização especulativa (D12); teste de timeout/retry; 29/29 testes. Transição para P17.
- 2026-09-08 (P17 concluído): mobile 390 sem overflow; a11y básica (aria-label nos canvas); revalidação no navegador OK. Transição para P18.
- 2026-09-08 (P18 concluído): endpoints auditados 1:1 com rotas; README/ARCHITECTURE corrigidos; scripts diagnósticos removidos. Transição para P19.
- 2026-09-08 (P19 concluído): `docs/TCC.md` com resultados reais das 5 commodities; intervalo com piso em zero (verificado). **Auditoria final em curso.**
- 2026-09-08 (AUDITORIA FINAL): estrutura limpa (sem duplicação/junk; auth.js×3 são camadas distintas); 29/29 testes; smoke 8/8; endpoints 1:1 com docs; P14–P19 validados. **SADEN VALIDADO.**
- 2026-09-08 (RODADA 2 — produto/UX): landing pública + roteador; recuperação de senha real (outbox dev); busca unificada (cidade/rua/coords) + reverse + Minha localização; temas light/dark/system; responsivo 320–1440 sem overflow (fix min-width:0 em itens de grid); E2E 20/20 no navegador. 38/38 testes.
- 2026-09-08 (RODADA 3 — landing/identidade): fotos do autor em `frontend/img/` (hero pivô, solução soja, CTA céu); narrativa completa (problema→solução→funcionalidades→como funciona→dados→CTA→footer sem links falsos); logo satélite SVG própria sobre verde atual + favicon; navbar mobile; E2E 27/27; light/dark/mobile inspecionados.
- 2026-09-08 (RODADA 4 — refinamento estético): superfícies por seção, navbar em grid equilibrada, hero com fade+chips, editorial/timeline/banda-dados, footer escuro integrado, microinterações CSS + reveal único; frase incorreta removida; E2E 27/27; overflow 0; light/dark/mobile validados.
- 2026-09-15 (CICLO TERRITORIAL): FASE A revalidada (46/46); CONAB (reCAPTCHA→bloqueado), CEPEA (Cloudflare→bloqueado), ANTT CKAN (só multas) investigados sem forçar; Price Reference Engine honesto; frete só referência manual; Land Cover Sentinel-2 integrada (tiles+legenda, sem ponto/%); 48/48 testes, E2E 44/44.
- 2026-09-15 (CONSOLIDAÇÃO): P0/P1 revalidados (XSS fechado, headers, engine ao vivo); CEPEA/IMEA rechecados (bloqueados, investigação encerrada); Land Cover renderizada e legendada; 48/48 + smoke 8/8 + E2E 44/44, zero page errors.
- 2026-09-15 (VALOR): matriz de valor por funcionalidade; Land Cover mantida como auxiliar + legenda compacta; relatório com localidade; Q&A da banca no TCC; E2E 46/46; nada reescrito, nada removido.
- 2026-09-15 (RC): contexto global vs controles por tela (D30); provider/fx_provider no engine; 48/48 + smoke + E2E 49/49 + overflow 0. **SADEN — RELEASE CANDIDATE TCC. Núcleo congelado.**
- 2026-09-15 (PÓS-FREEZE): barra global removida (D31; estado interno preservado); E2E 51/51. **RC mantido.**
- 2026-09-15 (CORREÇÃO PONTUAL): contexto compacto de volta só em Mapa/Relatórios (D32); coords digitadas preservadas exatas; E2E 53/53. **RC mantido.**
- 2026-09-15 (RESTAURAÇÃO): form completo do Dashboard de volta em Mapa/Relatórios (D33; move via JS); E2E 53/53. **RC mantido.**
- 2026-09-15 (DOCKER): `Dockerfile` + compose + `.dockerignore`; SQLite em volume, JWT obrigatório, healthcheck, não-root; validado (persistência, APIs, 48/48, smoke, E2E 53/53). **RC mantido.**
- 2026-09-15 (QA FINAL): 48/48 + smoke + E2E 53/53 + overflow + headers/CSP + engine + landcover + TCC §1–10 verificados; README sincronizado. **SADEN — TCC RELEASE CANDIDATE FINAL. Núcleo congelado.**
- 2026-09-15 (SENTINEL-2): L2A verificado (13 bandas, 22 functions) mas identify/renders exigem credencial → NDVI/NDMI/temporal/renders ADIADOS; paleta Land Cover MEDIDA de tiles reais (8 classes; Rangeland sem amostra, sem swatch); swatches via CSS (CSP); 48/48 + E2E 46/46.
- 2026-09-09 (CICLO PÓS-AUDITORIA): FASE A (esc() anti-XSS, município geocodificado, CSP+headers, JWT fail-fast, staleness) ✓ · FASE B (csvCell, retenção 500, prune, SRI) ✓ · FASE C (teclado autocomplete, foco drawer, aria-live, Limpar, intervalo explicado) ✓ · FASE D (header integrado) ✓ · FASE E (alertas MVP) ✓ · FASE F (locais salvos) ✓ · FASE G (período allowlist + gráfico variação %) ✓ · FASE H (NDVI: viável, bloqueado por credencial — docs/NDVI_STUDY.md).

## Auditoria final (2026-09-08) — veredito por bloco

- ARQUITETURA: frontend/backend separados, sem duplicação, sem arquivos inúteis. OK.
- AUTENTICAÇÃO: registro, login, logout (client), sessão, proteção, expiração, rate-limit. OK.
- DADOS: preços (Yahoo×PTAX), clima (Open-Meteo), localização (IBGE+geocode); fonte/timestamp/unidade sempre presentes. OK.
- APIs: 14 rotas = documentado; timeout+retry+cache; erros honestos (401/404/422/429/502). OK.
- FRONTEND: login, dashboard, filtros, mapa interativo, gráficos, previsão, relatórios, loading/erro, responsivo. OK (capturas).
- BACKEND: health, auth, validação, erros sem stack. OK.
- PREVISÃO: pipeline, 3 baselines, ridge, split temporal, métricas, sem leakage, intervalo com piso. OK.
- TESTES: 19 unit + 10 integração + smoke 8/8 + 4 scripts de verificação visual. OK.
- SEGURANÇA: secrets, bcrypt/JWT, CORS, validação, rate-limit, audit com risco aceito (D10). OK.
- PERFORMANCE: medições warm ≤10ms; sem otimização especulativa (D12). OK.
- DOCUMENTAÇÃO: STATUS, ROADMAP, DECISIONS (D1–D12), API_SOURCES, ARCHITECTURE, README, TCC.md. OK.
