# SADEN v1.2.0 — fechamento operacional

**Data:** 2026-11-14 · **Branch:** `ops/v1.2.0-operational-closeout` · **Base:** `0f93ecd` (main, tag `v1.2.0`)

---

## 1. Estado inicial encontrado

| item | valor |
|---|---|
| branch | `main` em `0f93ecd`, tag `v1.2.0` → `0f93ecd`, `v1-final` → `3f7ad33` |
| suíte local | 125 testes verdes |
| Node no PATH da máquina | **22.23.5** (ABI 127) — o erro relatado (v26/ABI 147) não se reproduz aqui |
| `better-sqlite3` | carrega e opera normalmente |
| Docker | web + worker funcionais |
| CI remoto | **1 execução, falhando** (job `testes`) |

## 2. Diagnóstico do erro Node.js

O erro `ERR_DLOPEN_FAILED` / `NODE_MODULE_VERSION 147` relatado acontece quando o
`npm start` roda com **Node 26** enquanto o binário nativo do `better-sqlite3` foi
compilado para **Node 22 (ABI 127)**. Não é bug de código: é ABI.

A máquina passou a ter Node 22.23.5 (`C:\Program Files\nodejs`), ABI 127, e o
backend inicia normalmente. Para impedir que o problema volte como erro cru,
foi adicionado um **preflight** (ver §3).

**Comandos exatos para quem ainda estiver em Node 26:**

```powershell
nvm use            # lê o .nvmrc (22.14.0)
cd backend
npm ci             # reinstala o binário para a ABI correta
npm start
```

Não rode `npm rebuild` com o Node errado: isso recompila o binário para a ABI
errada e piora o estado.

## 3. Correções aplicadas

| # | correção | arquivo | motivo |
|---|---|---|---|
| 1 | preflight de runtime em `prestart`/`predev`/`pretest` | `backend/scripts/preflight.js` | transforma erro de ABI em diagnóstico + comando |
| 2 | versão 1.1.0 → 1.2.0 | `backend/package.json`, `backend/package-lock.json` | estava defasada em relação à release |
| 3 | `assess()` puro para a saúde do worker | `backend/src/worker/health.js` | separa "processo vivo" de "worker operacional"; testável |
| 4 | novos campos no health público | `backend/src/routes/ops.js` | `reason`, `consecutive_failures`, `since_last_success_ms` |
| 5 | testes LIVE opt-in + fixture de preço | `tests/integration/api.test.js` | CI não pode depender de Yahoo/Open-Meteo/Nominatim |
| 6 | +10 testes (preflight, `assess`, calendário) | `tests/unit/worker.test.js` | cobre as lacunas acima |
| 7 | CI: docker explícito, e2e resiliente, diagnóstico | `.github/workflows/ci.yml` | ver §5 |
| 8 | modelo de ambiente com variáveis do worker | `.env.example` | operação sem adivinhação |

**Mantido sem alteração:** arquitetura, autenticação, SQLite e migrações,
dashboard, mapa, alertas, worker, Dockerfile. Nenhuma funcionalidade foi
reescrita.

## 4. Saúde do worker — o que significa "operacional"

`GET /api/health/worker` (público, sem dados sensíveis):

| campo | significado |
|---|---|
| `status` | `ok` / `degraded` / `down` / `not_started` |
| `alive` | heartbeat dentro do prazo (processo vivo) |
| `reason` | `running`, `heartbeat_stale`, `no_heartbeat`, `last_run_failed` |
| `last_success_at`, `since_last_success_ms` | quando o último ciclo concluiu |
| `consecutive_failures` | falhas seguidas desde o último sucesso |
| `next_run_at` | próxima execução prevista (dia útil, 18h SP) |
| `heartbeat_age_ms` | idade do sinal de vida |

**Códigos HTTP:** 200 para `ok` e `degraded`; **503** para `down` e
`not_started`. Um monitor externo deve alertar pelo código — é o mesmo que o
healthcheck do container usa.

**Calendário:** fim de semana não é falha. O agendador só escolhe dias úteis
(testado: sexta 19h → segunda 18h; sábado nunca é escolhido).

## 5. CI remoto — validado

`gh` não está autenticado nesta máquina, mas a API pública do GitHub permitiu
acompanhar as execuções do repositório público.

| execução | commit | resultado |
|---|---|---|
| 43650754428 | `0f93ecd` (main) | **failure** — job `testes` |
| 43652934014 | `ca5f71b` | failure — job `docker` (imagem `saden:ci` ≠ `saden:r2` do worker) |
| 43653080782 | `055653c` | failure — `docker compose build` sem `JWT_SECRET` |
| 43653261540 | `4e71f5b` | failure — compose up no runner e e2e |
| 43653572656 | `95fde67` | failure — `sobe web` estourou 121 s (bind mount sem permissão) |
| **43653916111** | **`6a6a5d7`** | **success** — 3 jobs verdes |

Resultado final: `testes (Node 22)` 16 s · `docker (web + worker)` 88 s ·
`e2e (Chrome headless)` 58 s.

**Duas causas reais encontradas pelo CI (e corrigidas):**
1. a suíte dependia de provedores externos → tornou-se determinística com
   fixture de preço e testes LIVE opt-in;
2. o container web não conseguia escrever no diretório montado pelo runner
   (uid 1000 dentro × uid 1001 fora) → **volume nomeado** em vez de bind mount.

## 6. Docker staging — ensaio local

| # | verificação | resultado |
|---|---|---|
| 1 | build limpo da imagem | ok (`saden:r2`) |
| 2 | web + worker sobem | ok |
| 3 | ordem: web roda migrations antes do worker | ok (`depends_on: service_healthy`) |
| 4 | health de ambos | `healthy` / `healthy` |
| 5 | conexão ao banco | ok |
| 6 | persistência | ok |
| 7 | worker sem navegador | ok |
| 8 | criação de alerta | ok |
| 9 | avaliação automática | ok (evento criado por ciclo do worker) |
| 10 | evento persistido | ok |
| 11 | idempotência após restart | ok (2 restarts → 1 evento) |
| 12 | lock com duas instâncias | **provado por teste automatizado** (2 instâncias: 1 adquire; lease vencido recuperado). O ensaio ad-hoc usou volume separado e não é evidência de contenção |
| 13 | recuperação após parada | ok |
| 14 | backup | ok — `VACUUM INTO`, 212.992 bytes, 1 usuário / 1 alerta / 1 evento / 65 observações |
| 15 | restauração isolada | ok — cópia serviu `/api/health` 200 e manteve as contagens |
| 16 | encerramento controlado | ok (`docker compose down`) |

## 7. Segurança — auditoria objetiva

| item | estado |
|---|---|
| `JWT_SECRET` | obrigatório em produção (o app falha sem ele) |
| `/api/ops/status` | exige admin (`SADEN_ADMIN_EMAILS`); padrão = ninguém |
| rate limits | criação (30/10 min), avaliação (20/10 min), leitura (120/10 min), login |
| CORS/headers/CSP | inalterados desde a V1.1; nenhuma permissão ampliada |
| erros | sem stack trace para o usuário |
| logs | sem senha, token ou conteúdo privado |
| isolamento | `user_id` sempre do token; testado entre usuários |
| migrations | aditivas e idempotentes; testadas sobre banco real |
| backup/rollback | documentados e exercitados (§6 e §8) |

Nenhuma biblioteca de segurança foi adicionada — a proteção necessária já existia.

## 8. Implantação

**Classificação: preparado para implantação, não implantado.**

Pronto: imagem, compose web+worker, health checks, variáveis documentadas
(`.env.example`), migrations, backup, restauração, rollback, monitoramento.

Falta para publicar: host com Docker e volume persistente, domínio/TLS,
`JWT_SECRET` de produção, `SADEN_ADMIN_EMAILS`, agendamento de backup e um
**monitor externo ativo** (§9). Nada disso foi feito aqui — exige autorização.

### Rollback

```bash
docker compose down
cp tmp/backups/<backup>.db data/saden.db
git checkout v1.2.0     # ou o commit anterior
docker compose up -d
```

## 9. Monitoramento externo — preparado, não ativado

O endpoint a monitorar é **`GET /api/health/worker`**: 200 = vivo, **503 =
parado/sem heartbeat**. Compatível com qualquer monitor de disponibilidade que
alerte por código HTTP.

Procedimento (requer conta do usuário — não criada aqui):

1. criar um monitor HTTP em UptimeRobot, Healthchecks.io ou equivalente;
2. URL: `https://<seu-dominio>/api/health/worker`;
3. intervalo: **5 minutos** (o worker bate heartbeat a cada 20 s; 5 min evita
   falso positivo sem demorar demais);
4. condição de alerta: **status ≠ 200** por **2 verificações consecutivas**
   (tolera um restart curto);
5. canal: e-mail do operador (ou webhook, se disponível);
6. teste: `docker stop saden-worker` → alerta em até ~10 min →
   `docker start saden-worker` → recuperação confirmada.

**Como o usuário será avisado hoje:** pela faixa da página de Alertas
("monitoramento temporariamente indisponível") e pelo healthcheck do container.
**Fora do app, ninguém é avisado** — é exatamente a lacuna que o passo acima
fecha. Enquanto o monitor externo não for cadastrado, a resposta honesta é:
o SADEN **detecta**, mas não **notifica** o operador.

## 10. Testes

| grupo | resultado |
|---|---|
| suíte local (Node 22) | **135 testes**: 129 passam, 6 pulados (LIVE), 0 falhas |
| CI remoto `testes` | success |
| CI remoto `e2e` | success (Chrome headless, 9 verificações) |
| CI remoto `docker` | success (web + worker + evento sem navegador + idempotência) |
| E2E local | 9/9 |

Os 6 testes pulados são os que consultam Yahoo/Open-Meteo/Nominatim/Esri; rodam
com `SADEN_LIVE_TESTS=1 npm test`.

## 11. Limitações remanescentes

1. **Sem monitor externo ativo** — depende de conta do usuário (§9).
2. **Sem deploy público** — não há infraestrutura autorizada.
3. Feriado de mercado não modelado (coberto pela tolerância de 4 dias).
4. `worker_runs` retém 500 execuções.
5. Node 26 continua presente em algumas máquinas; o preflight orienta, não
   instala.
6. Alerta de chuva legado (`rain_above`) segue visível e não avaliado.
