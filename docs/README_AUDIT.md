# README — relatório de auditoria (2026-09-21)

## O que foi auditado
README.md × projeto real: `backend/` (código, rotas, serviços, `package.json`),
`frontend/`, `tests/`, `scripts/seed.js`, `.env.example`, `.gitignore`,
`Dockerfile`, `docker-compose.yml`, `data/`, `tmp/`, `logs/`.
Comandos executados de verdade: `npm test`, `npm run seed`, `node backend/src/index.js`,
`GET /api/health`, `/`, `POST /api/auth/login`, `GET /api/commodities/soja/latest`,
`docker compose config`, `docker compose build`.

## O que estava desatualizado
- Testes: "19 unitários + 10 integração" contradizia "48/48" no Docker → real: **48/48** (7 suítes, inclui 2 live).
- CEPEA/CONAB: "não oferecem API pública" impreciso para o CEPEA (API por contratação/licenciamento).
- Faltavam: requisitos npm, tabela de variáveis (JWT_SECRET fail-fast, SMTP/outbox), seed idempotente + demo, persistência/data/.gitignore, fontes completas (Nominatim, Land Cover, frete, NDVI), funcionalidades, limitações, arquitetura, estrutura, endpoints verificados, status RC, segurança, health.

## O que foi atualizado
README.md reescrito (137 linhas) só com fatos verificados; nada inventado.

## Comandos testados (todos OK, salvo Docker)
`npm test` 48/48 · `npm run seed` · servidor + `/api/health` ok + `/` 200 +
login demo + `/commodities/soja/latest` ao vivo (R$ 149,43 em 2026-09-21) ·
`docker compose config` OK. `scripts/smoke-test.js` 8/8 (register, login, 401,
preço, clima, geo, previsão ridge, relatório). `scripts/e2e-round2.js` 53/53
PASS, pageErrors [].

## Números confirmados
Node 22.11.0 · npm 11.1.0 · Express 4.21.2 · better-sqlite3 11.10.0 · Leaflet 1.9.4 ·
Chart.js 4.4.1 · JWT 12 h · bcrypt 10 · rate-limit 10/10 min · TTLs 60 min/30 d ·
timeout 12 s · porta 3001 · 14 tabelas · 6 unit + 1 integração · smoke 8 · E2E 53.

## Pendências (não alteradas nesta tarefa documental)
1. `docs/` (ARCHITECTURE, API_SOURCES, PROJECT_STATUS, PROJECT_ROADMAP, DECISIONS,
   NDVI_STUDY, TCC) ausente nesta árvore — README e `Dockerfile` (`COPY docs`)
   pressupõem a árvore canônica. Só este arquivo foi recriado aqui.
2. `docker compose build` falha nesta árvore por (1): `COPY docs ./docs` → "/docs: not found".
3. `tests/e2e/` vazio no disco (E2E vive em `scripts/e2e-round2.js`).
4. Nenhum bug funcional corrigido (fora do escopo); nada a registrar contra o README.
