# SADEN v1.2.1 — endurecimento, confiabilidade e release

**Branch:** `release/saden-v1.2.1-hardening` · **Base:** `ec9eb3e` (ops closeout) · **Data:** 2026-11-14

---

## 1. Base incorporada

A branch parte de `ec9eb3e` (seis commits sobre `0f93ecd`) e **confirma o CI no
commit final**: execução `43654351818`, SHA
`ec9eb3e021d1458ec60e51b8e34c1fbb349aad54`, três jobs verdes (testes, docker,
e2e). O relatório anterior citava `6a6a5d7`; a validação de `ec9eb3e` também
existe e é a que vale.

## 2. Monitoramento externo — adapter implementado

**Escolha: Healthchecks.io (modelo *dead man's switch*).**

| critério | Healthchecks.io | UptimeRobot |
|---|---|---|
| modelo | espera sinal; alerta por **ausência** | faz requisição; alerta por falha |
| worker parado | detecta sem endpoint público | exige URL pública sempre acessível |
| calendário | período/grace configurável por check | exige monitor com janela |
| token | caminho da URL (UUID) | chave de API |
| plano gratuito | checks por período (inclusive diário) | 5 min mínimo em monitores |

Motivo técnico: o worker roda em dias úteis, às 18h. Um monitor de *pull* de 5
minutoso acusaria falsamente todo fim de semana e toda madrugada. No modelo de
heartbeat, o worker avisa quando começa, quando termina e quando falha; o serviço
só reclama se o sinal esperado **não chegar** dentro do período configurado.
Também não exige expor `/api/health/worker` na internet.

### Como funciona

`GET <base>/start` antes do ciclo, `GET <base>` no sucesso, `GET <base>/fail`
quando o ciclo não avalia nada. Se o processo morrer no meio, `/start` chegou e o
final não → o Healthchecks.io alerta.

- Desabilitado quando `SADEN_MONITOR_PING_URL` está vazia.
- Timeout de 5 s (`SADEN_MONITOR_TIMEOUT_MS`), sem retry: o próximo ciclo manda outro sinal.
- **Nunca lança** — falha do monitor não altera avaliação de preço.
- O token fica no caminho da URL; `monitor.redact()` reduz a `https://host/…` antes de qualquer log.
- Nenhum dado de usuário é enviado: só um GET no caminho.

### Procedimento para ativar (depende do usuário)

1. Criar check no Healthchecks.io com **período = 1 dia**, **grace = 12 h**
   (cobre fim de semana: 6ª 18h → 2ª 18h são 72 h; com período 1 dia + grace 12 h
   haveria alerta no sábado — use **período 3 dias** e grace 6 h se quiser
   silêncio total no fim de semana; com período 1 dia aceite o aviso de sábado).
   > Recomendação: período **3 dias**, grace **6 horas**. O worker avisa todo dia
   > útil; dois dias sem sinal (sexta→segunda) ficam dentro do período.
2. Copiar a URL do check para `SADEN_MONITOR_PING_URL` no `.env`.
3. `docker compose up -d saden-worker`.
4. Teste real de falha: `docker stop saden-worker` → o check fica "late" e
   notifica após o período+grace; `docker start saden-worker` → volta a "up".
5. Teste de rede: `docker exec saden-worker node -e "fetch(process.env.SADEN_MONITOR_PING_URL)"` opcional.

**Estado:** integração pronta e testada por servidor HTTP local; **não ativa** —
depende de conta/token.

---

## 3. Backup automático

**Arquitetura:** serviço `saden-backup` no Compose (processo próprio, fora do web),
rodando `backend/scripts/backup.js` a cada 24 h (`SADEN_BACKUP_INTERVAL_SECONDS`).

Por que não `cp`: o banco roda em WAL com dois escritores. `VACUUM INTO` produz
um arquivo consistente a partir de uma leitura.

Garantias implementadas e testadas:

| garantia | como |
|---|---|
| arquivo incompleto não parece válido | grava em `.partial`, valida, só então renomeia |
| integridade | `PRAGMA integrity_check` = `ok` |
| schema esperado | tabelas `users`, `alerts`, `alert_events`, `price_observations`, `series_state` |
| contagens registradas | usuários, alertas, eventos, observações no log JSON |
| retenção | padrão **14** (`SADEN_BACKUP_RETENTION`), só poda **depois** de validar |
| falha preserva histórico | teste: origem inválida → `.partial` removido, antigos intactos |
| backup durante escrita | teste com writer concorrente em WAL → `integrity_check` ok |
| banco somente leitura | volume de dados montado `:ro` no serviço de backup |
| persistência | volume **nomeado** `saden-backups` |

Tamanho observado: **212.992 bytes** (1 usuário, 1 alerta, 1 evento, 65 observações).

**Limitação declarada:** backup no mesmo host não protege contra perda do
servidor. Off-site exige destino externo e autorização — não configurado.

---

## 4. Concorrência real (mesmo arquivo SQLite)

Experimento com dois containers, **mesmo volume nomeado, mesmo banco, mesmo alerta**:

```
conc-a: ciclo concluido status=ok series=1 ok=1 new_observations=1 events=1 duration_ms=482
conc-b: ciclo ignorado: lock em posse de outra instancia  owner=conc-a
```

- eventos no banco após os dois: **1** (trigger único);
- lock liberado no encerramento (`worker_locks` vazio);
- lease vencido injetado (`owner=worker-morto`, `expires_at` no passado) → worker
  seguinte executou o ciclo normalmente (recuperação por expiração);
- heartbeat do processo morto permanece no banco e fica obsoleto → health 503.

Isto fecha a lacuna do relatório anterior (que usava volumes separados).

---

## 5. Frescor e calendário

O que **não** foi feito: calendário oficial de feriados de bolsa. Uma tabela
manual incompleta seria pior que a ausência — feriado continua absorvido pela
tolerância de 4 dias.

O que foi feito: separar os motivos com evidência.

| `freshness_detail` | quando |
|---|---|
| `atualizado` | observação de hoje |
| `aguardando_pregao` | dia útil antes das 18h SP, dado do pregão anterior |
| `sem_pregao_esperado` | sábado/domingo (feriado entra aqui por aproximação) |
| `atrasado` | idade > `SADEN_STALE_AFTER_DAYS` (4) |
| `sem_observacao` | nenhuma observação persistida |

Regra de precedência: **atraso real vence fim de semana** e **erro de fonte vence
os dois** — uma fonte quebrada não pode se esconder atrás do sábado.
`expected_session_date` e `market_day` são expostos para auditoria. A data da
observação sempre acompanha o preço na interface; nenhum preço antigo aparece
como atual.

PTAX: a conversão mantém `fx_fallback_days` (dias em que o câmbio veio do último
dia útil). Nenhuma cotação é inventada para dia sem publicação.

---

## 6. Débitos encerrados

**`rain_above`** (legado V1.1): criação já era bloqueada; agora o registro
histórico é marcado (`legacy: true`, `supported: false`, `legacy_reason`), a
interface mostra "legado / não avaliado nesta versão" e desabilita reativar, e
`PATCH active=true` devolve **409 `unsupported_alert_kind`**. Pausar e excluir
continuam permitidos. Nenhum evento é gerado. Registros antigos **não** foram
migrados nem apagados.

**`worker_runs`**: mantido em **500** por decisão, agora configurável
(`SADEN_WORKER_RUNS_KEEP`). Justificativa: um ciclo por dia útil → ~23 meses de
histórico; ~200 B por linha → ~100 KB. Arquivar seria complexidade sem ganho.

---

## 7. Auditoria adversarial (segunda passagem)

| # | pergunta | evidência |
|---|---|---|
| 1 | backup correto com worker escrevendo? | teste de escrita concorrente em WAL → ok |
| 2 | restauração em versão limpa? | cópia isolada serviu `/api/health` 200 com contagens idênticas |
| 3 | dois workers duplicam evento? | não — 1 evento no experimento real |
| 4 | monitor recebe sucesso quando deve? | teste com servidor local: `/start`, `/`, `/fail` |
| 5 | worker parado é detectável? | `assess()` → `down`/`heartbeat_stale`; HTTP 503 |
| 6 | falso positivo no fim de semana? | 14 testes de calendário; monitor por heartbeat, não por polling |
| 7 | falha de rede no monitor interrompe o worker? | não — `ping` nunca lança; teste com porta fechada |
| 8 | falha de backup destrói backups antigos? | não — teste dedicado |
| 9 | cotação antiga parece atual? | não — `observation_date` sempre exibida + `freshness_detail` |
| 10 | `rain_above` parece ativo? | não — 409 + badge + sem avaliação |
| 11 | usuário acessa evento de outro? | não — teste de isolamento existente |
| 12 | CI verifica o commit final? | sim — verificação por SHA na API |
| 13 | aplicação reinicia após falha de banco? | **parcial** — erro de abertura é fail-fast; sem teste de corrupção real |
| 14 | volume íntegro após recriar containers? | verificado no staging (dados sobrevivem a `down`/`up`) |
| 15 | logs revelam tokens? | não — redação + nenhum segredo logado |
| 16 | funciona com fonte externa caída? | sim — `partial`/`failed` com `classifyError` |
| 17 | atualização destrói dados? | DDL idempotente; imagem nova sobre volume antigo testada |
| 18 | rollback é executável? | procedimento documentado; restauração de backup exercitada |

Itens 13 e 18 permanecem parciais por decisão: testar corrupção real exigiria
criar um banco corrompido de propósito, e o rollback depende do backup — que é
exatamente o mecanismo validado.

---

## 8. Segurança — achados desta etapa

1. **Volume do backup montado `:ro`** no serviço de backup: reduz a superfície.
2. **Token do monitor em variável de ambiente**, redigido em log.
3. **`rain_above` reativável** era um falso positivo de monitoramento — corrigido (409).
4. Nenhuma dependência nova foi adicionada (só `fetch` nativo e `better-sqlite3` já existente).
5. Rate limits, JWT, admin e isolamento por usuário inalterados.

Sem vulnerabilidades exploráveis encontradas nos pontos auditados.

---

## 9. Runbook

### Iniciar

```bash
node -v                      # precisa ser 22.x
cd backend && npm ci
cd ../backend && node scripts/preflight.js
$env:JWT_SECRET="segredo-forte"    # PowerShell
docker compose up -d
```

### Verificar saúde

```bash
curl -s localhost:3001/api/health
curl -s -o /dev/null -w "%{http_code}\n" localhost:3001/api/health/worker   # 200 vivo / 503 parado
docker compose ps
docker compose logs --tail=50 saden-worker
```

Sem Docker: `docker exec saden-worker node backend/src/worker/healthcheck.js` já é
o healthcheck; localmente, `node backend/src/worker/healthcheck.js`.

### Backup

```bash
# manual (uma vez)
docker run --rm -v saden-data:/app/data -v saden-backups:/app/backups saden:1.2.1 \
  node backend/scripts/backup.js --db /app/data/saden.db --out-dir /app/backups --retention 14

# listar
docker run --rm -v saden-backups:/app/backups saden:1.2.1 \
  node backend/scripts/backup.js --list --out-dir /app/backups

# verificar um arquivo
docker run --rm -v saden-backups:/app/backups saden:1.2.1 \
  node backend/scripts/backup.js --verify /app/backups/saden-20261114-030000.db
```

O serviço `saden-backup` já faz isso a cada 24 h.

### Restaurar

```bash
docker compose down
docker run --rm -v saden-data:/app/data -v saden-backups:/app/backups saden:1.2.1 \
  cp /app/backups/saden-YYYYMMDD-HHMMSS.db /app/data/saden.db
docker compose up -d
curl -s localhost:3001/api/health
```

### Worker parado

```bash
curl -s localhost:3001/api/health/worker      # reason: heartbeat_stale
docker compose restart saden-worker
```

Lock preso (worker morto com lease ativo): aguardar `SADEN_WORKER_LOCK_TTL_MS`
(5 min) — o próximo worker assume. Não edite a tabela manualmente.

### Atualizar / rollback

```bash
git pull && docker compose build && docker compose up -d
# rollback:
docker compose down
git checkout v1.2.1        # ou a tag anterior
docker compose build && docker compose up -d
```

Migrações são DDL idempotente (`CREATE TABLE IF NOT EXISTS` + `ALTER` guardado):
não há passo destrutivo. **Não há tabela de ledger de migrações** — a versão do
schema é inferida pelas colunas presentes.
