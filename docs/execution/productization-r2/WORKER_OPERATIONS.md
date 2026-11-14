# Release 2 — operação do worker

**Data:** 2026-11-14
Complemento operacional: `docs/product/OPERATIONS_AND_MONITORING_GUIDE.md`.

---

## Ciclo de vida

| etapa | o que acontece |
|---|---|
| boot | conecta no banco, valida migrations, registra heartbeat, remove locks vencidos |
| ciclo inicial | roda imediatamente se `SADEN_WORKER_RUN_ON_START=1` |
| agenda | próxima execução às 18h SP em dia útil |
| ciclo | adquire lease → consulta séries devidas → persiste → avalia → registra → libera |
| heartbeat | a cada 20 s, atualiza `worker_heartbeat` |
| shutdown | SIGTERM/SIGINT: para a agenda, libera o lock, registra e sai |

## Tabelas

| tabela | conteúdo | retenção |
|---|---|---|
| `worker_locks` | uma linha por job; lease com `expires_at` | linha viva; vencidas removidas no boot |
| `worker_runs` | histórico de ciclos e contadores | **500** mais recentes |
| `series_state` | saúde por série (falhas, última tentativa) | permanente |
| `worker_heartbeat` | sinal de vida (uma linha) | permanente |

## Parâmetros

| variável | padrão | nota |
|---|---|---|
| `SADEN_WORKER_HOUR` | 18 | hora local (SP) |
| `SADEN_WORKER_INTERVAL_MS` | 900000 | reserva quando a agenda diária não se aplica |
| `SADEN_WORKER_MIN_SERIES_MS` | 3600000 | proteção do provedor |
| `SADEN_WORKER_LOCK_TTL_MS` | 300000 | maior que a duração normal de um ciclo |
| `SADEN_WORKER_HEARTBEAT_MS` | 20000 | renovação do lease |
| `SADEN_WORKER_RETRIES` | 2 | backoff exponencial 1,5 s × 2ⁿ |
| `SADEN_STALE_AFTER_DAYS` | 4 | tolerância de frescor |

## Diagnóstico rápido

```bash
curl http://localhost:3001/api/health/worker     # 200 ok / 503 parado
docker compose logs --tail=50 saden-worker
```

Últimos ciclos:

```bash
docker exec <web> node -e "const db=require('/app/backend/src/db');db.connect();console.table(db.connect().prepare('SELECT id,status,series_ok,series_failed,observations_new,events_created,duration_ms FROM worker_runs ORDER BY id DESC LIMIT 10').all())"
```

## Cenários testados

| cenário | resultado |
|---|---|
| duas instâncias simultâneas | uma executa, a outra registra "lock em posse de outra instancia" |
| morte no meio do ciclo | lease expira em ≤ 5 min; próxima assume |
| restart do container | ciclo inicial novo; eventos não duplicam |
| fonte indisponível | `series_failed`, `series_state.last_error`, alerta segue ativo |
| fim de semana | nenhum ciclo; não é falha |
| shutdown | lock liberado; nova instância não espera TTL |
