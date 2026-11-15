# SADEN — Runbook de recuperação de desastre (v1.2.2)

Este documento permite que **outra pessoa** recupere o SADEN sem conhecer o
histórico do projeto. Todos os comandos foram executados no ensaio
`scripts/dr-simulation.ps1` (9 cenários, ~98 s).

---

## 1. Preparação

### Requisitos

| item | valor |
|---|---|
| Node.js | **22.x** (22.23.5 usada; ABI 127) |
| Docker | 27.x com Compose v2 |
| Disco | banco + backups (backup ≈ tamanho do banco) |
| Acesso | porta 3001 (web) e escrita no volume `saden-data` |

### Variáveis obrigatórias

```env
JWT_SECRET=<segredo forte, >= 32 caracteres>
DATABASE_PATH=data/saden.db
SADEN_DATA_DIR=./data
```

### Variáveis de backup / off-site

```env
SADEN_BACKUP_RETENTION=14
SADEN_BACKUP_MAX_AGE_HOURS=30
SADEN_BACKUP_INTERVAL_SECONDS=86400
SADEN_BACKUP_MONITOR_PING_URL=https://hc-ping.com/<uuid-do-backup>
SADEN_OFFSITE_MODE=disabled|dir|s3
SADEN_OFFSITE_DIR=/app/offsite
SADEN_OFFSITE_RETENTION=14
SADEN_BACKUP_ENCRYPT=1
SADEN_BACKUP_PASSPHRASE=<passphrase >= 12 caracteres>
SADEN_S3_ENDPOINT=https://s3.us-west-004.backblazeb2.com
SADEN_S3_BUCKET=<bucket>
SADEN_S3_REGION=us-east-1
SADEN_S3_ACCESS_KEY=<chave>
SADEN_S3_SECRET_KEY=<segredo>
SADEN_S3_PREFIX=saden/backups
```

### Chave de criptografia

- Derivada por **scrypt** da `SADEN_BACKUP_PASSPHRASE`.
- **Nunca** é gravada junto ao backup nem em log.
- Guarde a passphrase fora do servidor (gerenciador de senhas / cofre físico).
- **Se a passphrase for perdida, as cópias off-site são irrecuperáveis.** O
  backup local permanece aberto e é a rede de segurança — por isso a cópia
  local não é apagada depois do envio.

### Estrutura de armazenamento

| caminho | conteúdo | acesso |
|---|---|---|
| `./data/saden.db` | banco SQLite (WAL) | web rw, worker rw, backup ro |
| volume `saden-backups` | `saden-*.db` + `saden-*.json` | backup rw, web ro |
| destino off-site | `saden-*.db.enc` | só o serviço de backup |

---

## 2. Diagnóstico rápido

```bash
curl -s localhost:3001/api/health                 # aplicação
curl -s -o /dev/null -w '%{http_code}\n' localhost:3001/api/health/worker
curl -s -o /dev/null -w '%{http_code}\n' localhost:3001/api/health/backup
docker compose ps
docker compose logs --tail=50 saden-backup
```

`/api/health/backup` → **200** = backup validado e recente; **503** = atrasado,
falhou, inválido ou ausente. Detalhe em `detail`.

---

## 3. Backup

### Executar manualmente

```bash
docker compose exec saden-backup \
  node backend/scripts/backup.js --db data/saden.db --out-dir /app/backups --retention 14
```

### Verificar

```bash
docker run --rm -v saden-backups:/b saden:1.2.3 \
  node backend/scripts/backup.js --list --out-dir /b
```

Cada backup tem um manifesto `saden-YYYYMMDD-HHMMSS.json` com `sha256`, `size`,
contagens e o resultado do envio off-site. O healthcheck confia no manifesto.

### Restore drill (não altera produção)

```bash
docker compose exec saden-backup node backend/scripts/restore-drill.js --out-dir /app/backups
```

O drill restaura o backup mais recente num diretório temporário, roda
`PRAGMA integrity_check`, confere tabelas e contagens, e apaga a cópia. Se o
mais recente falhar, tenta os anteriores e reporta.

### Investigar falha

1. `docker compose logs saden-backup | tail -20` — o log é JSON com `event`.
2. `backup_failed` traz `error` (sem dados de usuário).
3. Causas comuns: banco ausente, volume sem espaço, permissão (volume precisa
   ser escrito pelo uid 1000 — a imagem já cria `/app/backups` com dono `node`).

---

## 4. Recuperação parcial

### Web

```bash
docker compose rm -sf saden
docker compose up -d saden
curl -s localhost:3001/api/health
```

### Worker

```bash
docker compose rm -sf saden-worker
docker compose up -d saden-worker
curl -s -o /dev/null -w '%{http_code}\n' localhost:3001/api/health/worker
```

### Serviço de backup

```bash
docker compose rm -sf saden-backup
docker compose up -d saden-backup
docker compose logs --tail=5 saden-backup     # espera "backup_ok"
```

### Volume de backup perdido

```bash
# 1. baixar a cópia mais recente do destino remoto e decifrar
docker run --rm -e SADEN_OFFSITE_MODE=s3 -e SADEN_S3_ENDPOINT=... \
  -e SADEN_S3_BUCKET=... -e SADEN_S3_ACCESS_KEY=... -e SADEN_S3_SECRET_KEY=... \
  -e SADEN_BACKUP_PASSPHRASE=... -v saden-backups:/app/backups \
  -w /app/backend saden:1.2.3 node backend/scripts/restore-drill.js \
  --from-offsite saden-YYYYMMDD-HHMMSS.db.enc
```

### Banco corrompido (mantendo o resto)

```bash
docker compose stop saden saden-worker saden-backup
docker run --rm -v saden-backups:/b:ro -v saden-data:/d saden:1.2.3 \
  sh -c 'cp /b/saden-YYYYMMDD-HHMMSS.db /d/saden.db'
docker compose up -d
```

> Preserve o banco antigo antes de sobrescrever (`cp data/saden.db data/saden.db.bak`).
> Sobrescrever sem cópia é irreversível.

---

## 5. Recuperação completa (servidor perdido)

```bash
# 1. novo servidor com Docker e Node 22
# 2. clonar a versão
git clone <remote> saden && cd saden && git checkout v1.2.2

# 3. configurar .env (JWT_SECRET, passphrase, credenciais off-site)
# 4. obter o backup mais recente do destino remoto
docker run --rm -e SADEN_OFFSITE_MODE=s3 ... -v saden-backups:/app/backups \
  -w /app/backend saden:1.2.3 node backend/scripts/restore-drill.js \
  --from-offsite saden-YYYYMMDD-HHMMSS.db.enc

# 5. conferir o arquivo restaurado antes de publicar
docker run --rm -v saden-backups:/b saden:1.2.3 \
  node backend/scripts/backup.js --verify /b/restaurado.db

# 6. subir com o banco restaurado
docker compose up -d

# 7. validar
curl -s localhost:3001/api/health
curl -s -o /dev/null -w '%{http_code}\n' localhost:3001/api/health/worker
curl -s -o /dev/null -w '%{http_code}\n' localhost:3001/api/health/backup

# 8. validar dados (login com usuário real e conferir alertas/eventos)
# 9. retomar o worker e confirmar o ciclo na próxima janela (18h SP)
```

Migrações são DDL idempotente (`CREATE TABLE IF NOT EXISTS` + `ALTER` guardado)
e rodam no start do web. Não há passo destrutivo; ainda assim, **restaure sobre
uma cópia** e valide antes de apontar o tráfego.

---

## 6. Contingência

| situação | sintoma | ação |
|---|---|---|
| Chave incorreta | `falha ao decifrar: chave incorreta ou arquivo corrompido` | usar a passphrase correta; nada é gravado em falha |
| Backup corrompido | drill falha no mais recente | drill cai para os anteriores; investigar disco |
| Destino indisponível | `off-site=error [destino_indisponivel]` | backup local continua; reenviar depois |
| Banco bloqueado | `SQLITE_BUSY` | parar worker, repetir; verificar lock em `worker_locks` |
| Volume sem espaço | `VACUUM INTO falhou` / `ENOSPC` | liberar espaço; retenção reduzida |
| Falha de migração | web não sobe | restaurar backup anterior; abrir issue com o log |
| Perda total do servidor | — | seção 5 |

---

## 7. Pós-recuperação

```bash
# worker: heartbeat e última execução
curl -s localhost:3001/api/health/worker

# backup: existe cópia validada e recente?
curl -s localhost:3001/api/health/backup

# dados (com token de um usuário real)
curl -s -H "Authorization: Bearer $TOKEN" localhost:3001/api/alerts
curl -s -H "Authorization: Bearer $TOKEN" localhost:3001/api/alerts/events

# isolamento entre usuários: um token nunca deve ver alertas de outro
# monitores externos: worker e backup têm identificadores distintos
```

Confirme também o estado dos monitores externos (dois checks separados: worker
e backup). Um check "up" antigo não prova nada — verifique o último ping.

---

## 8. O que o ensaio comprovou (e o que não comprovou)

| medido | valor |
|---|---|
| RPO observado (backup a cada 24 h) | **≤ 24 h** de dados perdidos no pior caso |
| RPO com destino off-site | mesmo intervalo; a cópia remota é do mesmo instante |
| RTO — web recriado | 16,5 s |
| RTO — worker recriado e saudável | 4,6 s |
| RTO — backup recriado e novo arquivo | 17,2 s |
| RTO — volume perdido → cópia remota recuperada | 12,5 s |
| RTO — ambiente completo reconstruído | 20,9 s |
| RTO — ambiente do zero (incluindo dados) | ~98 s no total |

**Não testado:** servidor real, latência de rede real até o provedor S3, perda
física de disco, e recuperação com banco em produção sob carga. Os tempos acima
são de Docker local com a imagem já construída.
