# SADEN — registro de implantação de produção

**Status: PREPARADO, NÃO IMPLANTADO.**
Nenhum servidor foi contratado, nenhum domínio foi comprado, nenhum DNS foi
alterado e nenhuma conta externa foi criada. Este documento registra o que está
pronto, o que foi validado e exatamente o que falta.

**Candidato a produção:** `db78eab` (tag `v1.2.3`).
**main:** `8c7028e` = tag + 1 commit de documentação. Nenhuma diferença de código.

---

## 1. Auditoria pré-deployment

| verificação | resultado |
|---|---|
| Node.js | 22.23.5 (ABI 127), `engines >=22 <25` |
| `npm ci` limpo | ok |
| suíte | **198 testes** (192 passam, 6 LIVE opt-in, 0 falhas) |
| `better-sqlite3` | carrega e opera |
| Dockerfile | Node 22 slim, usuário `node`, diretórios de runtime com dono |
| `docker compose config` (dev e prod) | válido |
| worker / backup / restore drill | exercitados em staging |
| `/api/health`, `/api/health/worker`, `/api/health/backup` | implementados e testados |
| rate limits, JWT, admin, isolamento | inalterados desde a auditoria |

**Gate E2E:** flutuou uma vez no mesmo SHA (timeout de navegador). Registrado na
auditoria; a execução final em `main` foi verde. Tratado como gate informativo.

---

## 2. Hospedagem — comparação com preços oficiais

Consulta em **2026-11-14** nas páginas oficiais de preço. Valores em USD/mês,
plano mais barato que atende ao SADEN (Docker + volume persistente).

| provedor | plano | vCPU/RAM/disco | transferência | preço | região Brasil |
|---|---|---|---|---|---|
| **DigitalOcean** | Basic | 1 vCPU / 1 GB / 25 GB SSD | 1 TB | **$6** | ❌ (NYC, AMS, LON, FRA, SGP, SYD…) |
| **Vultr** | Regular Performance | 1 vCPU / 1 GB / 25 GB SSD | 1 TB | **$5** | verificar São Paulo no painel |
| **AWS Lightsail** | Linux/Unix | 2 vCPU / 1 GB / 40 GB SSD | 2 TB (½ em SP) | **$7** | ✅ **South America (São Paulo)** |

Notas oficiais coletadas:
- DigitalOcean: Basic 512 MB = $4; 1 GB = $6; 2 GB = $12. Backup do provedor =
  +20 % (semanal) ou +30 % (diário). **Não há região na América do Sul.**
- Vultr: Regular 1 GB = $5; High Performance 1 GB = $6; 2 GB = $10.
- Lightsail: $5 (512 MB), $7 (1 GB), $12 (2 GB); **São Paulo existe e tem metade
  da franquia de transferência**.

### Recomendação

**Principal: AWS Lightsail $7/mês, região São Paulo.** É o único com região
brasileira entre os três — o SADEN é um produto agroclimático brasileiro e a
latência para o usuário final importa mais que os $2 de diferença.

**Alternativa: Vultr Regular $5/mês** (ou DigitalOcean $6), se São Paulo não
estiver disponível ou se o custo for determinante. Nesse caso a latência para o
Brasil será maior, sem impacto funcional.

**Dimensionamento:** a stack completa (web + worker + backup + proxy) foi
limitada a 384 MB + 320 MB + 256 MB. O banco atual tem ~200 KB por backup. 1 GB
de RAM e 25–40 GB de disco são adequados; não há medição de carga real de
produção — é estimativa fundamentada no tamanho do banco e no perfil de uso
(poucos usuários, sem picos).

**Custo adicional previsto:** backup off-site (B2/R2) na casa de centavos por
mês para <1 GB; domínio ~R$ 40/ano; TLS gratuito (Let's Encrypt).

---

## 3. Arquitetura de produção

```
internet ── 80/443 ──▶ caddy (TLS, HSTS, limite de corpo)
                          │ rede interna
                          ▼
                        saden :3001  ──▶ volume saden-data (SQLite)
                        saden-worker ──▶ mesmo volume (leitura/escrita)
                        saden-backup ──▶ saden-data (ro) + saden-backups
```

- **Somente o Caddy publica portas.** Web, worker e backup não têm portas
  publicadas.
- `saden-data` e `saden-backups` são **volumes nomeados** (não bind mount), o que
  elimina o problema de UID/GID encontrado no CI.
- O banco **nunca** é exposto à rede.
- Limites de memória por serviço e log rotacionado (10 MB × 3).

Arquivos: `deploy/docker-compose.prod.yml`, `deploy/Caddyfile`,
`deploy/setup-server.sh`, `deploy/.env.production.example`.

---

## 4. Imagem imutável

A produção usa `${SADEN_IMAGE}` com **tag + digest**:

```bash
# no notebook/servidor de build
docker build -t saden:1.2.3 .
docker push <registry>/saden:1.2.3
docker buildx imagetools inspect <registry>/saden:1.2.3   # copie o digest
# no .env:
SADEN_IMAGE=<registry>/saden:1.2.3@sha256:<64 hex>
```

Sem registry configurado, a alternativa é construir no próprio servidor a partir
do commit `db78eab` — pior para rastreabilidade, melhor que usar `latest`.

---

## 5. Segredos

| segredo | como gerar | onde guardar |
|---|---|---|
| `JWT_SECRET` | `openssl rand -base64 48` | `/srv/saden/.env` (chmod 600) |
| `SADEN_BACKUP_PASSPHRASE` | gerenciador de senhas, ≥ 20 caracteres | **fora do servidor** |
| credenciais S3 | painel do provedor | `/srv/saden/.env` |
| URLs de monitor | Healthchecks.io | `/srv/saden/.env` |

Regras: `.env` com `chmod 600`, dono do usuário de deploy; nunca em Git; nunca em
log; nunca em imagem Docker. **Perder a passphrase = perder as cópias remotas.**

---

## 6. Ativação do off-site (procedimento)

```bash
# 1. preencher no .env: SADEN_OFFSITE_MODE=s3, endpoint, bucket, região, chaves,
#    SADEN_BACKUP_PASSPHRASE (valor forte, guardado fora do servidor)

# 2. teste completo ANTES de habilitar o ciclo (não toca no banco de produção)
docker compose --env-file .env -f docker-compose.prod.yml exec saden-backup \
  node backend/scripts/offsite-verify.js --db data/saden.db
```

O verificador prova, em sequência: backup local válido → upload → download →
checksum do envelope → decifra → restauração com contagens → rejeição de chave
errada → rejeição de checksum divergente → rejeição de objeto inexistente.
**Só depois de `"ok": true` o off-site pode ser considerado validado.**

Teste local já executado (transporte `dir`): **8/8 etapas ok**, exit 0.

---

## 7. Ativação dos monitores (Healthchecks.io)

| check | período | grace | motivo |
|---|---|---|---|
| worker | **3 dias** | 6 h | o worker roda só em dias úteis; 1 dia acusaria fim de semana |
| backup | **1 dia** | 6 h | ciclo de 24 h; grace cobre atraso de execução |

Passos: criar os dois checks, copiar as URLs para `SADEN_MONITOR_PING_URL` e
`SADEN_BACKUP_MONITOR_PING_URL`, subir a stack, e **testar a notificação**:
`docker compose stop saden-worker` → aguardar período+grace → confirmar e-mail;
`start` → confirmar recuperação. Sem esse teste, o monitor não está ativo.

---

## 8. Implantação (quando o servidor existir)

```bash
# 1. servidor Ubuntu 24.04 recém-criado
scp -r deploy/ usuario@host:/srv/saden/
ssh usuario@host 'sudo bash /srv/saden/setup-server.sh'

# 2. .env
cp /srv/saden/.env.production.example /srv/saden/.env
chmod 600 /srv/saden/.env      # preencher (nunca por chat)
cd /srv/saden && docker compose --env-file .env -f docker-compose.prod.yml up -d

# 3. verificação
docker compose ps
curl -fsS https://SEU_DOMINIO/api/health
curl -s -o /dev/null -w '%{http_code}\n' https://SEU_DOMINIO/api/health/worker
curl -s -o /dev/null -w '%{http_code}\n' https://SEU_DOMINIO/api/health/backup
```

DNS: registro `A` (e `AAAA` se houver IPv6) apontando para o IP do servidor,
antes de subir o Caddy (o ACME precisa resolver).

## 9. Smoke tests pós-implantação (baixo risco)

1. `https://DOMINIO` responde 200 e redireciona de HTTP.
2. Login e registro com conta de teste `smoke+<data>@dominio`.
3. Dashboard e séries carregam.
4. Criar 1 alerta de teste com limite absurdo (nunca dispara).
5. `/api/health` 200 · `/api/health/worker` 200 · `/api/health/backup` 200.
6. Reiniciar o web: `docker compose restart saden` → dado persiste.
7. Confirmar que `/api/ops/status` devolve **403** para usuário comum.
8. `docker compose logs | grep -i "secret\|passphrase"` → vazio.

## 10. Rollback

```bash
# no .env, voltar SADEN_IMAGE para a tag/digest anterior
docker compose --env-file .env -f docker-compose.prod.yml up -d
# se o banco precisou ser restaurado:
docker compose stop saden saden-worker saden-backup
docker run --rm -v saden_saden-backups:/b:ro -v saden_saden-data:/d <imagem> \
  sh -c 'cp /b/<backup>.db /d/saden.db'
docker compose --env-file .env -f docker-compose.prod.yml up -d
```

## 11. Checklist mensal

- [ ] `docker compose ps` — os quatro serviços `Up`
- [ ] `/api/health/worker` e `/api/health/backup` = 200
- [ ] Healthchecks.io: os dois checks sem incidentes no mês
- [ ] `ls /var/lib/docker/volumes/*saden-backups*/_data` — 14 backups recentes
- [ ] Restore drill do mês: `node backend/scripts/restore-drill.js` → `ok: true`
- [ ] Off-site: `offsite-verify.js` → `ok: true`
- [ ] Disco: `df -h` com > 20 % livre
- [ ] Atualizações de segurança aplicadas (`unattended-upgrades` ativo)
- [ ] Certificado TLS válido (`curl -vI https://DOMINIO` > 14 dias)
- [ ] Revisar logs de erro do mês

---

## 12. O que foi validado e o que não foi

| item | estado |
|---|---|
| Suíte, Docker build, compose (dev e prod) | validado localmente |
| Offsite ponta a ponta (transporte `dir`) | validado, 8/8 |
| Assinatura SigV4 | validada contra vetor oficial AWS |
| Provedor S3 real | **não validado** — sem conta |
| Reverse proxy / TLS | **não executado** — imagem `caddy` indisponível (registry bloqueado) |
| Servidor real | **não provisionado** |
| DNS / domínio | **não configurado** |
| Monitores externos | **não ativados** |
| Smoke tests em produção | **não executados** |
