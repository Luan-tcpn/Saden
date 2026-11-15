# SADEN v1.2.2 — disaster recovery e prontidão de produção

**Branch:** `release/saden-v1.2.2-disaster-recovery` · **Base:** `9f23e4b` (v1.2.1)

---

## 1. O que estava aberto na v1.2.1

| lacuna | risco |
|---|---|
| backup sem monitor próprio | processo vivo falhando há dias passava despercebido |
| healthcheck do backup | não existia; container "Up" sem backup |
| backup só no mesmo host | perda do servidor = perda de tudo |
| nenhuma prova de reconstrução | procedimento escrito, nunca executado |
| RPO/RTO | desconhecidos |

## 2. Monitoramento do backup

Canal próprio: `SADEN_BACKUP_MONITOR_PING_URL` (identificador **diferente** do
worker — são processos independentes).

Sequência: `start` antes do `VACUUM INTO` → `success` **somente** depois de
validar, calcular checksum, gravar manifesto e (se configurado) enviar ao
destino remoto → `fail` em qualquer erro. Se o processo morrer no meio, o sinal
final não chega e o serviço externo alerta por ausência.

Falha do monitor nunca interrompe o backup (5 s de timeout, sem retry, `ping`
não lança). O token fica no caminho da URL e é redigido em log.

**Healthcheck do container** (`backup-health.js`): saudável só se existir
manifesto `ok` com arquivo presente, tamanho coerente e idade ≤
`SADEN_BACKUP_MAX_AGE_HOURS` (30 h = 24 h de ciclo + 6 h). Uma tentativa que
falhou depois do último sucesso também reprova — ontem ter dado certo não
torna o serviço saudável hoje.

## 3. Backup off-site

### Comparação (modelo e capacidades; preços mudam — consulte a página oficial)

| provedor | compatível S3 | egress | imutabilidade | observação |
|---|---|---|---|---|
| Backblaze B2 | sim | cobrado, com franquia publicada | Object Lock disponível | barato para armazenar, caro para restaurar muito |
| Cloudflare R2 | sim | sem cobrança de egress (política publicada) | via bucket lock | melhor para leitura frequente |
| Amazon S3 | sim (nativo) | cobrado | Object Lock | mais recursos, custo e complexidade maiores |
| MinIO (self-hosted) | sim | local | depende do backend | ótimo para teste; não é off-site de verdade |

**Escolha:** transporte **S3-compatível** implementado no próprio projeto
(SigV4), com cifra no cliente antes do envio. Motivos: funciona com B2, R2,
MinIO e S3 sem trocar código; não adiciona binário externo nem processo de
instalação; a superfície auditável é pequena (~200 linhas).

> Restic foi avaliado e descartado **nesta etapa**: exigiria instalar um binário
> no host/container e um repositório com formato próprio, sem ganho sobre
> `VACUUM INTO` + cifra + objeto remoto para um banco único de ~200 KB. Se o
> volume crescer ou surgir necessidade de deduplicação, Restic é o próximo passo
> natural — o transporte S3 já implementado é reaproveitável.

### Criptografia

Envelope `SADENBK1`: scrypt(N=2^14) → AES-256-GCM, salt e IV aleatórios por
arquivo, tag de 16 bytes. A passphrase **nunca** é gravada com o backup nem
logada. Chave errada e arquivo alterado produzem o mesmo erro (GCM não vaza
qual dos dois ocorreu) e **nenhum arquivo parcial é gravado**.

### Integração

Opcional: sem `SADEN_OFFSITE_MODE`/credenciais, tudo fica desabilitado e o
backup local segue normal. Envio só depois do backup local validado. A cópia
local **não** é apagada. Sucesso só é declarado após `HEAD` confirmar o tamanho
remoto; retenção remota (`SADEN_OFFSITE_RETENTION`, padrão 14) roda depois.

Retenção proposta: 14 diários. Semanal/mensal não foram implementados porque o
volume atual (≈200 KB por dia) não justifica complexidade; a política é
configurável e a poda nunca roda antes da confirmação do novo objeto.

## 4. Restore drill

`restore-drill.js` roda no serviço de backup após cada ciclo: escolhe o
manifesto mais recente, copia para diretório temporário, abre, roda
`PRAGMA integrity_check`, confere tabelas e contagens, confere o checksum do
manifesto e apaga a cópia. Se o mais recente falhar, tenta os anteriores
(máximo 3) e reporta quais falharam — sem tocar no banco de produção.

## 5. Ensaio de desastre (`scripts/dr-simulation.ps1`)

Ambiente isolado (`docker compose -p saden-dr`, `tmp/dr-*`), 9 cenários, **98 s**:

| # | cenário | resultado | tempo |
|---|---|---|---|
| 0 | subir ambiente e criar dados | ok | 8,2 s |
| 1 | container web perdido | recriado, dados preservados | 16,5 s |
| 2 | worker perdido | recriado, health 200 | 4,6 s |
| 3 | container de backup perdido | novo backup íntegro | 17,2 s |
| 4 | volume de backup perdido | recuperado do off-site e decifrado | 12,5 s |
| 5 | ambiente completo perdido | reconstruído, login ok, alerta recuperado | 20,9 s |
| 6 | backup corrompido | drill rejeitou | 1,2 s |
| 7 | chave incorreta | rejeitada, nenhum arquivo gravado | 1,5 s |
| 8 | destino indisponível | backup local ok, off-site=error | 15,8 s |

**RPO observado:** ≤ 24 h (intervalo entre backups). **RTO:** 4,6–20,9 s por
componente no Docker local, com imagem já construída. Números não incluem
download real de provedor nem servidor novo.

## 6. Segurança do ciclo

- Backup: banco montado `:ro`; diretório `/app/backups` na imagem com dono
  `node` (volume nomeado herda o dono).
- Web: monta `saden-backups` **somente leitura**, apenas para ler manifestos.
- Nenhum endpoint expõe caminho, contagem de usuários ou conteúdo de backup.
- `/api/health/backup` é público e mínimo; detalhes ficam em `/api/ops/status`
  (admin).
- Tokens e passphrase entram por `.env`; nada é logado.

## 7. Auditoria adversarial

| # | pergunta | evidência |
|---|---|---|
| 1 | perder o último backup válido? | poda só após validar; falha preserva antigos (teste) |
| 2 | enviar arquivo incompleto? | `HEAD` compara tamanho; divergência = erro |
| 3 | marcar sucesso antes de validar? | ping só depois de checksum + manifesto + envio |
| 4 | monitor detecta processo morto? | modelo de heartbeat: sem sinal final, alerta |
| 5 | detecta falha com processo vivo? | `assess()` → `failed` quando a tentativa é posterior ao sucesso |
| 6 | monitor vaza token? | `redact()` + teste de descritor |
| 7 | falha externa paralisa backup? | teste com destino inacessível → local ok |
| 8 | retenção apaga tudo? | mantém os N mais recentes; nunca inclui o recém-criado |
| 9 | chave errada danifica dados? | falha antes de gravar; sem arquivo parcial |
| 10 | restaura em ambiente limpo? | cenário 5: banco restaurado, app sobe, login ok |
| 11 | banco restaurado abre na versão atual? | DDL idempotente, testado no cenário 5 |
| 12 | migração destrutiva? | só `CREATE TABLE IF NOT EXISTS` + `ALTER` guardado |
| 13 | restore sobrescreve banco válido? | drill copia para temporário; restauração manual documentada com aviso |
| 14 | monitor distingue local de remoto? | campos separados (`status` e `offsite.status`) |
| 15 | drill valida conteúdo? | integridade + tabelas + contagens + checksum |
| 16 | íntegro com escrita simultânea? | teste WAL concorrente → `integrity_check` ok |
| 17 | dois backups se sobrescrevem? | nome por carimbo de segundo; parcial separado |
| 18 | container saudável com backup atrasado? | healthcheck reprova por idade |
| 19 | recuperação preserva isolamento? | dados restaurados mantêm `user_id`; teste de isolamento existente |
| 20 | recuperação sem infra original? | cenário 5 em projeto compose novo |

---

## 8. Débitos conscientes

- **Sem ledger de migrações** — schema idempotente, versão inferida por colunas.
- **Feriado de mercado** não modelado (tolerância de frescor de 4 dias).
- **Restic** não adotado nesta etapa (justificado em §3).
- **Off-site não está ativo**: transporte implementado, sem credenciais.
- **Restore drill diário**, não semanal — custo desprezível para 200 KB.
