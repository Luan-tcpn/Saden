# SADEN — Sistema de Análise, Dados e Estimativa de preços de commodities agrícolas brasileiras

Aplicação web real, integrada e executável (TCC): preços de referência em reais, clima por localidade, mapa interativo, previsão quantitativa com intervalo, relatórios e alertas — tudo com fonte e data declaradas.

## O que é

Os preços exibidos pelo SADEN são **referência internacional convertida**: contratos futuros CBOT/ICE (via Yahoo Finance) × dólar PTAX de venda (Banco Central). Isso **não** é preço físico regional, preço de porteira nem valor recebido pelo produtor — e o sistema declara esse nível em tela e nos relatórios.

Sobre CEPEA/CONAB: o CEPEA disponibiliza API mediante contratação e licenciamento, fora do escopo acadêmico deste trabalho; a CONAB opera portal de consulta sem API REST pública. Por isso nenhuma das duas está integrada automaticamente (consulta manual segue linkada nas fontes).

## Principais funcionalidades

- Landing pública + cadastro, login, recuperação de senha (token único de 1 h, outbox local sem SMTP)
- Dashboard: 5 commodities (soja, milho, café, trigo, algodão), série histórica, KPIs, previsão 7/14/30 dias com intervalo, métricas treino/val/teste, clima 7 dias, comparativo
- Mapa do Brasil (Leaflet + OSM/Esri, clique → preço e clima) + camada Sentinel-2 Land Cover (visual, com legenda)
- Busca por cidade/rua/coordenadas, reverse geocoding, "minha localização", locais salvos
- Relatórios consolidados (JSON + CSV com BOM + impressão/PDF via navegador), com fontes e limitações
- Alertas (`price_below`/`price_above`/`rain_above`) com verificação sob demanda e histórico
- Temas claro/escuro/sistema, responsivo 320–1440 px
- `GET /api/health` (usado pelo healthcheck do Docker) e `GET /api/sources` (catálogo de fontes)

## Como funciona

Filtros da tela → `GET /api/*` (JWT) → serviços → integrações (1 módulo por fonte, timeout 12 s, retry 3×, cache: preços/clima 60 min, geografia 30 dias) → SQLite → telas. Preço = futuro (cents) × PTAX × fator (saca 60 kg = 2,20462 bu; café 60 kg = 132,277 lb; algodão direto R$/libra-peso). Sem câmbio de referência, o ponto é descartado — nunca inventado. Fonte fora do ar → erro 502 honesto; a tela indica a idade do último dado.

## Fontes de dados

| Dado | Fonte | Acesso |
|---|---|---|
| Futuros (ZS=F, ZC=F, KC=F, ZW=F, CT=F) | Yahoo Finance chart | pública, via backend (Yahoo sem CORS p/ browser) |
| Câmbio PTAX venda | Banco Central (OData) | pública |
| Clima atual, 7 dias e histórico ERA5 | Open-Meteo | pública, sem chave |
| Estados/municípios | IBGE Localidades | pública |
| Ruas/endereços, reverse | Nominatim (OSM, 1 req/s, atribuição) | pública |
| Cobertura do solo 10 m | Sentinel-2 Land Cover (Esri/Impact Observatory) | tiles/legenda públicos; consulta por ponto exige credencial |
| CEPEA/ESALQ | API por contratação e licenciamento | **não integrada** (fora do escopo) |
| CONAB | portal com reCAPTCHA, sem API REST pública | **não integrada** |
| Frete ANTT | calculadora interativa/DOU, sem endpoint | sem cálculo automático (referência manual) |
| NDVI (Sentinel-2/CDSE) | exige credencial | **não implementado** (estudo em `docs/NDVI_STUDY.md`) |

## Arquitetura

Frontend estático (HTML/CSS/JS + Leaflet 1.9.4 + Chart.js 4.4.1 via CDN) servido pelo próprio backend na porta única 3001. Backend Express em camadas: rotas → serviços → integrações, utilidades transversais (HTTP, erros, validação) e middleware (auth JWT, rate-limit 10 tent./10 min). Persistência SQLite em arquivo único (`better-sqlite3`, 14 tabelas, WAL + FK). Detalhes em `docs/ARCHITECTURE.md`.

## Requisitos

- Node.js ≥ 18 (testado em **22.11.0**; `engines` exige ≥ 18)
- npm (testado 11.1.0)
- Internet (fontes externas reais, sem chave)
- Docker + Compose 2.x (opcional, só para a via container)

## Configuração

```powershell
Copy-Item .env.example .env
```

Variáveis (`backend/src/config.js`; valores após `=` são os padrões):

| Variável | Obrigatória? | Papel |
|---|---|---|
| `PORT` = 3001 | não | porta do backend+frontend |
| `JWT_SECRET` | **sim em produção** (fail-fast sem ele) | segredo das sessões; em dev há fallback local — nunca commitar segredo real (`.env` está no `.gitignore`) |
| `JWT_EXPIRES_IN` = 12h | não | duração da sessão |
| `DATABASE_PATH` = data/saden.db | não | arquivo SQLite (relativo à raiz do projeto) |
| `FRONTEND_ORIGIN` | não | origem CORS |
| `YAHOO_UA`, `HTTP_TIMEOUT_MS` = 12000 | não | identidade/timeout nas fontes |
| `CACHE_PRICES_TTL_MIN` / `CACHE_WEATHER_TTL_MIN` = 60, `CACHE_GEO_TTL_DAYS` = 30 | não | TTLs de cache |
| `SMTP_HOST/PORT/USER/PASS/MAIL_FROM` | não | sem transporte implementado: recuperação cai no outbox local `tmp/mail-outbox/` |

## Execução local (testado em 2026-09-21)

```powershell
cd backend; npm install; cd ..
Copy-Item .env.example .env   # pule se .env já existir
cd backend; npm run seed; cd ..   # cria tabelas + usuário demo (idempotente)
node backend\src\index.js     # ou: cd backend; npm start
# abra http://localhost:3001, cadastre-se e use
```

## Usuário de demonstração / Seed

`scripts/seed.js` (via `npm run seed` dentro de `backend/`) garante as 5 commodities e o usuário demo `demo@saden.local / saden123` (apropriado só para ambiente local/acadêmico). Pode rodar repetidas vezes sem duplicar. Também é possível se cadastrar pela tela — o seed não é obrigatório para usar o sistema.

## Persistência

SQLite em `data/saden.db` (WAL: `saden.db-wal`/`saden.db-shm` em execução). A pasta `data/` é criada automaticamente na primeira conexão; em instalação limpa basta iniciar o app (o seed completa as tabelas base). O banco é **runtime**: está ignorado no git (`data/*.db*`) — não baixe nem versione `saden.db`, ele é gerado localmente. Parar e iniciar preserva tudo (inclusive no Docker, via volume `./data`).

## Testes (estado real, executado em 2026-09-21)

```powershell
cd backend; npm test                  # 48/48 (7 suítes; inclui 2 testes live nas fontes)
cd ..; node scripts\smoke-test.js     # 8/8 contra servidor em execução
node scripts\e2e-round2.js            # 53/53 verificações com navegador real
```

Suíte `node --test` sem frameworks: 6 arquivos unitários (conversão, validação, matemática da previsão, HTTP/retry, coordenadas, CSV) + integração (auth, rotas, token, rate-limit, recuperação, fontes vivas, alertas, locais). 48 testes ≠ 48% de cobertura (cobertura não medida). Sem teste formal de carga — há apenas medições exploratórias locais.

## Docker

Imagem `node:22-slim`, usuário `node`, sem secrets embutidos, `HEALTHCHECK` em `/api/health`; volumes `./data` (banco) e `./tmp/mail-outbox`; `JWT_SECRET` obrigatório via ambiente.

```powershell
$env:JWT_SECRET = "troque-por-um-segredo-forte"
docker compose build
docker compose up
# http://localhost:3001
docker compose down   # o banco em ./data é preservado; nada além disso persiste
```

> Situação em 2026-09-27: `docs/` faz parte da árvore canônica e está versionado (ver `git ls-tree HEAD docs/`); com o daemon Docker ativo, o fluxo acima se aplica. Nesta máquina o daemon estava inativo, então o build não pôde ser executado aqui — pendente de ambiente com Docker. Docker não torna o sistema automaticamente pronto para produção (sem TLS, backup ou monitoramento).

## Principais endpoints

Autenticação: `POST /api/auth/register|/login`, `POST /api/auth/forgot|/reset`, `GET /api/auth/me` · Commodities: `GET /api/commodities`, `/commodities/:key/series?range=`, `/commodities/:key/latest` · Preços: `GET /api/prices/reference` · Clima: `GET /api/weather/forecast|/history` · Geo: `GET /api/geo/search|/reverse|/estados|/estados/:uf/municipios` · Previsão: `GET /api/forecast/:key?horizon=7|14|30` · Relatórios: `GET /api/reports/:key|/reports/:key/csv` · Land Cover: `GET /api/landcover/tile/:z/:x/:y.png|/info` (públicos) · Alertas: `/api/alerts`, `/api/alerts/check` · Locais: `/api/places` · Sistema: `GET /api/health`, `GET /api/sources`. Rotas públicas do app: `/`, `/login`, `/register`, `/reset`, `/dashboard`.

## Limitações e escopo atual

- Preço de referência internacional convertida, não físico regional (CEPEA/CONAB sem integração automática).
- Modelo univariado (clima/câmbio como contexto, não variáveis); série de ~1 ano; intervalo gaussiano sem cobertura empírica; datas futuras em dias corridos.
- Land Cover é camada visual (sem consulta por ponto/percentuais); sem NDVI operacional.
- Sem teste formal de carga; sem SMTP real (outbox local); instância única, sem TLS.

## Estrutura do projeto

`backend/` (Express: `src/{index,config,db,middleware,routes,services,integrations,utils}`) · `frontend/` (`index.html`, `css/`, `js/{api,auth,app,theme}.js`, `img/`) · `tests/` (`unit/` 6 arquivos, `integration/api.test.js`, `e2e/` vazio) · `scripts/` (seed, smoke, E2E, verificações) · `docs/` (ARCHITECTURE, API_SOURCES, PROJECT_STATUS, PROJECT_ROADMAP, DECISIONS, NDVI_STUDY, TCC, AI_CONTEXT_RECOVERY) · `data/` (banco runtime, ignorado no git) · `tmp/` (outbox, evidências; ignorado) · `logs/` (ignorados).

Na árvore canônica: `docs/ARCHITECTURE.md` (arquitetura e endpoints), `docs/API_SOURCES.md` (fontes), `docs/PROJECT_STATUS.md` (estado), `docs/PROJECT_ROADMAP.md` (plano oficial), `docs/DECISIONS.md` (D1–D34), `docs/NDVI_STUDY.md` (viabilidade NDVI), `docs/TCC.md` (material técnico do TCC), `docs/AI_CONTEXT_RECOVERY.md` (recuperação de contexto v1.0.0 → v1.1.x).

## Status do projeto

**Release Candidate / feature freeze**: funcional, com suíte verde (48/48 + smoke 8/8 + E2E 53/53 na última validação registrada). Novas funcionalidades fora do escopo; correções de bugs/regressões e segurança continuam possíveis. Não avaliado formalmente para produção.
