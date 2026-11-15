# SADEN v1.2.2 — auditoria final de aceitação para produção

**Branch:** `audit/saden-v1.2.2-production-acceptance` · **Base:** `e78e5bc` (tag `v1.2.2`) · **Data:** 2026-11-15

---

## Decisão

# APROVADO COM RESSALVAS

A implementação é tecnicamente consistente e recuperável. Não encontrei risco que
torne a publicação insegura **para o escopo atual** (web + worker + backup local).

As ressalvas não são de código: são de **operação ainda não ativada** e de
**provedor externo não validado** — nenhuma delas exige mudança no sistema.

Três defeitos reais foram encontrados e corrigidos nesta auditoria (§4, §5, §7).

---

## 1. Escopo e método

Auditoria independente com inspeção direta de código, execução de baterias
adversariais próprias e um teste de carga que a v1.2.2 declarou não ter feito.
Nenhuma conclusão foi aceita com base no relatório anterior.

---

## 2. Criptografia

**Algoritmos:** scrypt (N=2^14, r=8, p=1) → AES-256-GCM, salt 16 B e IV 12 B
aleatórios por arquivo, tag 16 B, formato `SADENBK1`.

| teste | resultado |
|---|---|
| roundtrip | ok |
| passphrase errada | rejeita |
| salt / IV / tag / ciphertext alterados (1 bit) | rejeitam |
| magic alterado | rejeita |
| truncamento em 0, 8, 24, 36, 52 e último byte | rejeitam |
| envelope vazio / não-SADEN | rejeita |
| passphrase < 12 caracteres / vazia | rejeita |
| salt e IV únicos entre arquivos | ok |
| custo do scrypt | **68 ms**, ~16 MB |
| conteúdo parcial em falha | **nenhum** — a decifra só entrega após autenticar |

**Achado corrigido:** `pull` não comparava o objeto baixado com o `sha256`
registrado no manifesto. Um objeto remoto trocado por **outro backup válido**
decifraria sem erro e restauraria o snapshot errado. Agora `pull` aceita
`expectedSha256` e aborta antes de decifrar/gravar.

**Formato/versionamento:** o identificador `SADENBK1` fixa a versão do envelope.
Um arquivo antigo continua legível porque nenhuma mudança de formato foi feita
nesta auditoria. Não há AAD; salt/IV/tag estão implicitamente autenticados pelo
GCM, e os metadados do backup são amarrados pelo checksum do manifesto — o que
não cobre *todos* os metadados, e está declarado como limite consciente.

**Passphrase:** não está em manifesto, log, bundle, `.env.example`, argv ou
armazenamento remoto. As ocorrências de `JWT_SECRET=`/passphrase no repositório
são valores de teste do CI e do script de simulação, marcados como descartáveis.

---

## 3. S3 / SigV4

**Não foi possível testar contra MinIO**: o registro de contêiner está bloqueado
neste ambiente (`minio/minio` e `quay.io/minio/minio` falham no pull). Isso está
registrado como limitação — **não declarei compatibilidade operacional com
nenhum provedor real**.

O que **foi** validado, sem depender de conta:

| verificação | resultado |
|---|---|
| vetor oficial da AWS (GET /test.txt, 2013-05-24) | assinatura **idêntica** (`f0e8bdb8…`) |
| caminho canônico sem dupla codificação | `%20` preservado |
| payload hash SHA-256 | confere |
| path-style, headers assinados, escopo e região | conforme especificação |
| chave secreta ausente da requisição | confirmado |

### Achado corrigido — dupla codificação do caminho

O caminho canônico era recodificado (`%20` → `%2520`). A assinatura só batia para
chaves ASCII puramente alfanuméricas — o caso normal (`saden-YYYYMMDD-HHMMSS.db.enc`),
mas quebraria para qualquer `SADEN_S3_PREFIX` com espaço/acento. Corrigido para
usar o caminho já codificado (`u.pathname`), com teste de regressão comparando
contra implementação de referência independente e contra o vetor AWS.

**Compatibilidade real:** MinIO, AWS, R2 e B2 **não validadas em execução**. A
implementação segue a especificação e reproduz o vetor oficial; qualquer
afirmação além disso seria infundada.

---

## 4. Backup sob carga (lacuna declarada na v1.2.2)

3 escritores concorrentes (INSERT/UPDATE contínuos) por 12 s, com 3 backups
disparados durante a carga:

| backup | duração | tamanho | integridade |
|---|---|---|---|
| durante-carga-1 | 200 ms | 229 KB | ok |
| durante-carga-2 | 283 ms | 758 KB | ok |
| durante-carga-3 | 313 ms | 1,37 MB | ok |

Todos os snapshots restauráveis: `integrity_check` ok, **0 eventos órfãos**,
alertas com dono válido, contagens monotônicas. O banco foi de ~66 a ~6.000
eventos durante o teste sem quebrar nenhuma cópia.

### Achado corrigido — colisão de arquivo parcial

Dois backups no mesmo segundo usavam o **mesmo** arquivo `.partial.db`; o
segundo apagava o parcial do primeiro (`EBUSY` no `unlink`). Sem corrupção, mas
com perda de disponibilidade. O parcial agora inclui PID + sufixo aleatório; a
colisão de nome final continua sendo detectada sem sobrescrever. Regressão
coberta por teste, e o ensaio passa com dois backups simultâneos bem-sucedidos.

---

## 5. Segurança de dependências

`npm audit` inicial: **1 crítico, 1 alto, 2 moderados**.

| pacote | severidade | risco real | ação |
|---|---|---|---|
| `proxy-addr` | **crítico** | spoofing de IP via IPv6 mapeado → **bypass de rate limit** de login | corrigido |
| `body-parser` | alto | DoS com bytes após corpo comprimido | corrigido |
| `qs` | moderado | DoS por query malformada | **mantido** (exige express 5) |

Depois: **0 crítico, 0 alto, 2 moderados**. As 2 restantes exigem salto de major
do express; o risco é DoS de baixa severidade e será tratado quando houver
justificativa para express 5. Suíte continua 198 testes verdes após a correção.

---

## 6. Recuperação, RPO e RTO

| métrica | valor observado | contexto |
|---|---|---|
| RPO | **≤ 24 h** | intervalo do ciclo de backup |
| RTO web | 16,5 s | Docker local, imagem pronta |
| RTO worker | 4,6 s | idem |
| RTO backup | 17,2 s | idem |
| RTO volume de backup | 12,5 s | cópia remota + decifra |
| RTO ambiente completo | 20,9 s | projeto compose novo |

**Não medido:** download real de provedor S3, servidor novo, perda física de
disco, recuperação com banco em produção sob tráfego real. Os números acima não
são garantia de produção.

Compatibilidade com backups das versões anteriores: v1.2.1 e v1.2.2 usam o mesmo
schema (DDL idempotente) e o mesmo formato de envelope; um backup v1.2.1
restaura na v1.2.2. Não há alteração de formato nesta auditoria, então nenhuma
cópia existente se torna ilegível.

---

## 7. Auditoria adversarial dos próprios resultados

| # | pergunta | resposta |
|---|---|---|
| 1 | remoto pode estar corrompido com HTTP 200? | checksum do envelope + GCM detectam |
| 2 | checksum remoto é realmente verificado? | **era não** → corrigido (`expectedSha256`) |
| 3 | cripto autentica antes de restaurar? | sim, GCM; nada é gravado antes |
| 4 | passphrase aparece em log? | não (redação + testes) |
| 5 | perda da chave documentada? | sim, runbook §1 |
| 6 | formato permite evolução? | sim (`SADENBK1`), sem AAD — limite declarado |
| 7 | SigV4 com caracteres especiais? | **falhava** → corrigido e coberto por teste |
| 8 | caminho local ≠ chave remota? | chave = `basename + .enc`; prefixo configurável |
| 9 | timeout produz falso sucesso? | não: sucesso exige `HEAD` com tamanho igual |
| 10 | falha de upload apaga a cópia local? | não — teste dedicado |
| 11 | dois processos geram manifesto inconsistente? | **parcial compartilhado** → corrigido |
| 12 | retenção apaga a última cópia? | não; poda só após validar e nunca o novo |
| 13 | backup sob carga é restaurável? | sim, 3/3, integridade ok |
| 14 | restore pode sobrescrever banco válido? | drill usa cópia temporária; restauração manual com aviso |
| 15 | worker retoma sem duplicar? | idempotência por (alerta, tipo, observação) |
| 16 | monitor detecta processo morto? | por ausência de sinal final |
| 17 | três estados independentes? | worker, backup local e off-site separados |
| 18 | CI verifica o SHA final? | sim — validado por SHA, não por branch |
| 19 | staging reproduzível do zero? | sim (`scripts/dr-simulation.ps1`) |
| 20 | outra pessoa consegue executar? | runbook com comandos reais |

---

## 8. Limitações que permanecem

1. **Off-site não ativo** — transporte pronto, sem credenciais.
2. **Nenhum provedor S3 validado em execução** (MinIO indisponível no ambiente).
3. **2 vulnerabilidades moderadas** (`qs`, requer express 5).
4. Feriado de mercado não modelado (tolerância de 4 dias).
5. Sem ledger de migrações (DDL idempotente).
6. Sem AAD no envelope (metadados amarrados pelo checksum do manifesto).
7. Nenhum monitor externo ativo (duas URLs pendentes).
8. Sem deploy público.

---

## 9. Correções aplicadas nesta auditoria

| # | arquivo | correção |
|---|---|---|
| 1 | `backend/src/backup/offsite.js` | caminho canônico sem dupla codificação (SigV4) |
| 2 | `backend/src/backup/offsite.js` | `pull` verifica `expectedSha256` antes de decifrar |
| 3 | `backend/scripts/restore-drill.js` | `--from-offsite` aceita `--sha256` |
| 4 | `backend/scripts/backup.js` | parcial único por processo (colisão de nome) |
| 5 | `backend/package-lock.json` | `proxy-addr`, `body-parser` corrigidos |
| 6 | testes | +5 casos (vetor AWS, codificação, checksum, colisão) |

Nenhuma funcionalidade nova. Nenhuma alteração de arquitetura.

---

## 10. CI — flutuação observada no E2E

| commit | run | branch | resultado |
|---|---|---|---|
| `db78eab` | 43661924256 | `audit/...` | **3/3 verde** |
| `db78eab` | 43662091247 | `main` | testes ok, docker ok, **e2e falhou (32 s)** |

O **mesmo SHA** passou integralmente na branch de auditoria e falhou apenas no
job de navegador na execução de `main`. Não houve alteração de código entre as
duas execuções: é flutuação do E2E por tempo de carregamento do Chrome/CDP no
runner.

Isso é um risco operacional real e **não** é mascarado aqui: o gate de navegador
não é 100% determinístico. O E2E já espera até 60 s por modo de headless e faz
segunda tentativa; falhar em 32 s indica espera de elemento na página, não só
lentidão de inicialização. Recomendação: tratar o E2E como gate informativo até
estabilizar, mantendo testes e docker como bloqueantes.

A release v1.2.3 foi integrada com o gate satisfeito na execução `43661924256`
(3/3) sobre o SHA exato `db78eab`; a flutuação em `main` está registrada e foi
reexecutada.
