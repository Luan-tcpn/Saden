# SADEN — Productization Release 2: monitoramento automático

**Data:** 2026-11-14 · Branch `product/background-monitoring-release-2` · Base `08b9855` (R1)

---

## 1. Resumo

A Release 1 entregou alertas de preço funcionais, mas **avaliados apenas quando o
usuário consultava preços**. A Release 2 resolve isso com um **worker
independente**: processo separado do web, agendado, com lease persistente,
idempotência no banco, recuperação de falhas e saúde observável.

O que mudou de fato, em uma frase: **o alerta dispara sem ninguém abrir a
página** — desde que o worker esteja rodando.

## 2. Arquitetura

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  web (API)  │────▶│  SQLite      │◀────│    worker    │
│  Express    │     │  (volume     │     │  agendado    │
│  + frontend │     │   local)     │     │  + lease     │
└─────────────┘     └──────────────┘     └──────────────┘
        │                                        │
        └────────── Yahoo Finance / PTAX ────────┘
                 (cada um consulta quando precisa)
```

- **web**: atende usuários; é o dono das migrations.
- **worker**: avalia séries com alertas ativos; não expõe HTTP.
- **SQLite**: fonte única; `worker_locks`, `worker_runs`, `series_state`,
  `worker_heartbeat` foram adicionadas.

O worker **não chama a própria API**: usa `priceService` e `alertEngine`
diretamente.

## 3. Worker

`backend/src/worker/`:

| arquivo | responsabilidade |
|---|---|
| `config.js` | agenda, TTL de lock, retries, intervalo mínimo por série |
| `scheduler.js` | próxima execução (dia útil, 18h `America/Sao_Paulo`, pula fim de semana) |
| `locks.js` | lease atômico (`INSERT … ON CONFLICT … WHERE expired OR mine`) |
| `runner.js` | um ciclo: séries devidas → consulta → persiste → avalia → registra |
| `health.js` | estado consolidado (heartbeat + execuções) e saúde por fonte |
| `healthcheck.js` | healthcheck do container |
| `index.js` | processo: heartbeat, agenda, shutdown gracioso |

## 4. Agendamento

- Frequência real da fonte: **fechamento diário em dias úteis**.
- Execução às **18h locais** (após Chicago e PTAX), de segunda a sexta.
- Fim de semana não gera ciclo — mercado fechado não é falha.
- `SADEN_WORKER_MIN_SERIES_MS` (1 h) impede consultar a mesma série repetidamente.
- No start, um ciclo inicial roda imediatamente (`SADEN_WORKER_RUN_ON_START=1`).

## 5. Locks e concorrência

Uma linha por job em `worker_locks`. A aquisição é **um único statement**:

```sql
INSERT INTO worker_locks(...) VALUES(...)
ON CONFLICT(job_key) DO UPDATE SET owner = excluded.owner, ...
WHERE worker_locks.expires_at <= :now OR worker_locks.owner = :owner
```

Depois, confirma-se que a linha é nossa. Sem janela entre checar e escrever.

- **lease**: 5 min; renovado por heartbeat de 20 s e por um renovador durante o
  ciclo.
- **recuperação**: se o processo morre, o lease expira e outra instância assume.
- **encerramento**: SIGTERM/SIGINT libera o lock imediatamente (não espera TTL).

Testado com duas instâncias: uma adquire, a outra recusa; lease expirado é
assumido.

## 6. Idempotência

Mantido o índice único da Release 1:

```sql
UNIQUE (alert_id, event_type, observation_date)
```

O evento nasce de `INSERT OR IGNORE`; a contagem de linhas afetadas decide se o
alerta muda para `triggered`. Restart, retry, timeout ou execução duplicada não
geram segundo evento — **garantido no banco**, não em JavaScript.

## 7. Fontes por série

| item | valor |
|---|---|
| fonte | Yahoo Finance (futuros) + PTAX/BCB |
| instrumento | contrato futuro (vencimento mais líquido) |
| moeda/unidade | BRL · R$/sc 60kg ou R$/lp |
| frequência | diária em dias úteis |
| frescor | **4 dias corridos** (cobre fim de semana + feriado) |
| erro de fonte | classificado em `timeout`, `rate_limited`, `auth_error`, `source_unavailable`, `insufficient_data` |

Estado por série em `series_state`: última tentativa, último sucesso, último
erro, falhas consecutivas, última observação e último preço.

## 8. Frescor e estados

Substituída a regra fixa de 7 dias por política por série (`SADEN_STALE_AFTER_DAYS`,
padrão 4). Estados expostos:

`updated` · `late` · `awaiting` (sem observação) · `source_error` · worker
`ok/degraded/down/not_started`.

**Ausência de cotação nova não é erro**; fim de semana não é atraso.

## 9. Saúde

| endpoint | acesso | conteúdo |
|---|---|---|
| `GET /api/health` | público | web vivo |
| `GET /api/health/worker` | público | worker vivo, última execução, próxima, idade do heartbeat (503 se parado) |
| `GET /api/ops/status` | **admin** (`SADEN_ADMIN_EMAILS`) | execuções, fontes, métricas, produto |
| `healthcheck.js` | container | heartbeat + ao menos uma execução |

A interface mostra um banner com o estado real: ativo, com falhas, indisponível
ou não iniciado — e a última verificação.

## 10. Frontend

- Banner de monitoramento na página de Alertas, atualizado a cada 60 s.
- Situação do dado por série (`atualizado` / `atrasado` / `aguardando` / `erro na fonte`).
- Bloco de retorno do usuário (feedback) na mesma página.
- Sem redesign: mesma navegação, cores e componentes.

## 11. APIs

Novas: `GET /api/health/worker`, `GET /api/ops/status`, `GET /api/feedback/kinds`,
`POST /api/feedback`.

Rate limiting por usuário adicionado a: criação de alerta (30/10 min), avaliação
manual (20/10 min), leitura de eventos (120/10 min).

Contratos da R1 preservados.

## 12. Banco e 13. Migrations

Aditivas e idempotentes (`CREATE TABLE IF NOT EXISTS` + `ALTER TABLE` guardado):
`worker_locks`, `worker_runs`, `series_state`, `worker_heartbeat`, `feedback`.

Testadas contra: banco vazio; banco V1.1 (formato original); banco já migrado pela
R1 **com dados reais** (75 usuários, 1.490 observações) — sem perda.

## 14. Segurança

- `user_id` sempre do token; nenhuma rota aceita identidade do corpo.
- `/api/ops/status` exige admin configurado; padrão = ninguém.
- O usuário **não** consegue forçar avaliação global de séries.
- Erros não expõem stack trace; logs não registram segredos.
- SQL sempre parametrizado; frontend escapa toda interpolação.
- Nenhuma configuração de segurança foi enfraquecida.

## 15. CI

`.github/workflows/ci.yml` com três jobs: `test` (Node 22 + suíte completa),
`e2e` (Chrome headless + `tests/e2e/alerts.e2e.mjs`), `docker` (build, compose
web+worker, health, persistência/idempotência após restart).

**Não executado neste ambiente** (sem runner remoto); os mesmos comandos foram
executados localmente.

## 16. Testes

| grupo | quantidade |
|---|---|
| herdados (V1.1 + R1) | 90 |
| worker unitário (agenda, locks, saúde, ciclo, idempotência, shutdown) | 26 |
| worker integração (browser fechado, restart, concorrência, rate limit, isolamento) | 9 |
| **total** | **125, 0 falhas** |
| E2E navegador (CDP) | 9 verificações, todas verdes |

## 17. Staging

Executado em Docker com **cópia do banco real** (`tmp/r2data`), web + worker:

- ambos `healthy`;
- ciclo inicial do worker: 12 execuções registradas;
- alerta criado → **evento disparado só pelo worker** (preço real R$ 154,88);
- restart do worker → **sem duplicidade**;
- dados antigos preservados (75 → 76 usuários).

## 18. Produção

**Não há ambiente público configurado e autorizado neste repositório.** O que
existe: imagem Docker validada, compose web+worker, health checks, backup e
restauração testados. A versão está **pronta para deploy**, não publicada.

## 19. Métricas

`worker_runs` guarda por ciclo: duração, séries, falhas, observações novas,
alertas avaliados, eventos criados, duplicados bloqueados. `runner.metrics()`
agrega 7 dias. Nenhuma métrica individual de usuário é coletada para terceiros.

## 20. Feedback

`POST /api/feedback` (autenticado, 4 tipos, até 1.000 caracteres) + bloco na
página de Alertas. Sem serviço externo, sem CRM, sem dado pessoal adicional.

## 21. Limitações

1. **Depende do worker estar rodando.** Sem ele, nada é avaliado (e o banner diz).
2. Série é referência internacional convertida — não é preço local.
3. Sem e-mail/push; notificação apenas interna.
4. Feriados de mercado não modelados (cobertos pela tolerância de 4 dias).
5. Um host com volume local; SQLite em rede não é suportado.
6. `worker_runs` retém as 500 execuções mais recentes.
7. CI configurado, não executado aqui.
8. Alerta de chuva legado segue sem avaliação.

## 22. Rollback

```bash
# 1. parar
docker compose down
# 2. restaurar o banco anterior (backup consistente já gerado)
cp tmp/backups/saden-r1-<timestamp>.db data/saden.db
# 3. voltar ao commit anterior
git checkout v1-final        # ou o commit da Release 1
docker compose up -d         # somente o serviço web
```

As migrations são **aditivas**: voltar o código não exige reverter o schema (as
colunas/tabelas novas ficam inertes). Restauração do backup foi testada abrindo
a cópia e conferindo contagens.
