# SADEN — Operação e monitoramento

Guia do operador: como subir, acompanhar, diagnosticar, fazer backup e restaurar.

---

## 1. Requisito de runtime

**Node 22** (`.nvmrc` = `22.14.0`, `engines: >=22 <25`). O `better-sqlite3` é
módulo nativo: em Node 26 falha com `NODE_MODULE_VERSION`. Use `nvm use` ou o
Node 22 do sistema.

## 2. Subir com Docker (recomendado)

```bash
$env:JWT_SECRET = "segredo-forte-aqui"     # PowerShell
docker compose build
docker compose up -d
docker compose ps
```

Dois serviços:

| serviço | papel | healthcheck |
|---|---|---|
| `saden` | API + frontend; **roda as migrations** | `GET /api/health` |
| `saden-worker` | monitoramento automático | `healthcheck.js` (heartbeat + 1 execução) |

Ordem garantida: o worker espera o web ficar `healthy` — não há migração
concorrente.

Variáveis úteis:

| variável | padrão | efeito |
|---|---|---|
| `JWT_SECRET` | — | obrigatório |
| `SADEN_DATA_DIR` | `./data` | diretório do SQLite (use cópia para testar) |
| `SADEN_WORKER_HOUR` | `18` | hora local da execução |
| `SADEN_WORKER_MIN_SERIES_MS` | `3600000` | intervalo mínimo por série |
| `SADEN_STALE_AFTER_DAYS` | `4` | tolerância de frescor |
| `SADEN_ADMIN_EMAILS` | vazio | quem acessa `/api/ops/status` |

## 3. Subir sem Docker

```bash
# terminal 1 — web
node backend/src/index.js

# terminal 2 — worker
node backend/src/worker/index.js
```

Os dois compartilham `DATABASE_PATH` (padrão `data/saden.db`).

## 4. Saúde

```bash
curl http://localhost:3001/api/health          # web
curl http://localhost:3001/api/health/worker   # worker (503 = parado)
```

`/api/health/worker` devolve `status`: `ok`, `degraded` (vivo, mas última
execução falhou), `down` (heartbeat antigo), `not_started`.

Interpretação:

| status | significado | ação |
|---|---|---|
| `ok` | monitoramento funcionando | nenhuma |
| `degraded` | ciclo recente falhou (fonte) | ver logs e `series_state` |
| `down` | processo sem heartbeat | reiniciar o worker |
| `not_started` | nunca rodou neste banco | iniciar o worker |

**Um alerta "ativo" não prova que o worker está rodando.** O banner na página de
Alertas mostra o estado real.

## 5. Painel operacional (admin)

```bash
# defina SADEN_ADMIN_EMAILS=voce@dominio no ambiente do web
curl -H "Authorization: Bearer <token>" http://localhost:3001/api/ops/status
```

Traz: worker, fontes (por série), métricas de 7 dias, últimas execuções e
contagens do produto (usuários, alertas por estado, eventos, feedback).

## 6. Logs

Ambos os processos escrevem JSON por linha:

```bash
docker compose logs -f saden
docker compose logs -f saden-worker
```

Eventos do worker: `worker iniciado`, `proxima execucao agendada`,
`ciclo concluido`, `ciclo ignorado: lock em posse de outra instancia`,
`lease perdido durante o ciclo`, `encerrando`.

Nenhum log contém senha, token ou conteúdo privado.

## 7. Falhas comuns

| sintoma | causa provável | o que fazer |
|---|---|---|
| worker `Restarting` logo após subir | processo encerrando por timer sem referência | não deve ocorrer (corrigido); verifique a versão |
| `ciclo ignorado: lock em posse de outra instancia` | duas instâncias | normal: só uma executa. Confirme `docker compose ps` |
| `source_error` em todas as séries | Yahoo/BCB indisponível | aguardar; o alerta segue armado |
| alerta não dispara | worker parado, dado desatualizado ou condição não atingida | ver banner, `series_state` e o preço atual |
| `503` em `/api/health/worker` | worker parado | iniciar/reiniciar |

## 8. Restart e recuperação

```bash
docker compose restart saden-worker
```

O worker: reexecuta um ciclo inicial, adquire o lease (respeitando TTL de 5 min
se outro morreu há pouco) e retoma. Eventos já gravados **não** se repetem.

Se o worker for morto no meio de um ciclo, o lease expira em até 5 minutos e a
próxima instância assume.

## 9. Backup

Sempre pelo SQLite, nunca copiando o arquivo com o banco aberto:

```bash
node backend/backup-db.js data/saden.db tmp/backups/saden-$(date +%Y%m%d-%H%M%S).db
```

O script usa `VACUUM INTO` (arquivo único e consistente) e imprime as contagens
de usuários, alertas, eventos e observações.

## 10. Restauração

```bash
docker compose down
cp tmp/backups/saden-<data>.db data/saden.db
docker compose up -d
curl http://localhost:3001/api/health
```

As migrations são **aditivas**: restaurar um banco antigo em código novo apenas
recria as colunas/tabelas que faltarem, sem apagar dados.

## 11. Manutenção

- `worker_runs` guarda as **500** execuções mais recentes (poda automática).
- `worker_locks` remove leases vencidos no início do worker.
- Alertas, eventos e séries **não** são podados.
- Para limpar feedback antigo, faça-o manualmente com `DELETE` por data —
  não há rotina automática (proposital: retenção curta precisa de decisão).

## 12. Checklist de deploy

1. backup do banco atual;
2. `docker compose build`;
3. `docker compose up -d`;
4. `GET /api/health` = 200;
5. `GET /api/health/worker` = 200 e `status: ok`;
6. criar um alerta de teste e reiniciar o worker para ver um evento;
7. conferir `docker compose logs` sem erro;
8. registrar a versão implantada.
