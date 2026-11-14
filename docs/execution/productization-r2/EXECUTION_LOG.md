# Release 2 — registro de execução

**Data:** 2026-11-14

## 1. Auditoria inicial

`HEAD` = `08b9855` (R1) confirmado; `main`/`v1-final` = `3f7ad33`; bundle R1 com
SHA-256 conferido. Suíte herdada: **90/90**. Docker daemon ativo.

## 2. Implementação

Ordem: schema → frescor por série → locks → agendador → runner → saúde →
rotas → frontend → Docker → CI → docs.

Decisões registradas:

1. **Worker usa os serviços**, não a própria API HTTP.
2. `priceService.getSeries` ganhou `evaluateAlerts:false` e `bypassCache:true`
   para o worker contar observações/eventos sem avaliação dupla.
3. Idempotência permanece **no banco** (índice único da R1).
4. `worker_heartbeat` em tabela própria (uma linha) — sinal de vida separado do
   histórico de execuções.
5. Admin por `SADEN_ADMIN_EMAILS`, padrão negar.
6. `SADEN_DATA_DIR` no compose para testar cópia do banco sem tocar no real.

## 3. Erros encontrados e corrigidos

| # | problema | correção |
|---|---|---|
| 1 | `classifyError` ignorava status 401/403 (só texto) | classificador passa a olhar status HTTP |
| 2 | rota de saúde montada em `/api/ops/health/worker` (404) | router montado em `/api` |
| 3 | **worker encerrava após o ciclo inicial** (`unref()` nos timers) — pego no Docker | timers sem `unref`; processo permanece vivo |
| 4 | PowerShell expandiu `${...}` ao editar o rate limit | chaves reescritas com `keyOf(req, scope)` via editor |
| 5 | compose corrompido por round-trip do PowerShell (mojibake) | arquivo reescrito por ferramenta de escrita |
| 6 | E2E clicava no menu antes do app autenticar | espera por `view-app` visível + filtros carregados |
| 7 | E2E falhava em 503 do health (worker parado) | filtro documentado: 503 é resposta correta |

## 4. Validação

- suíte: **125/125**;
- E2E navegador: cadastro, série, criação, evento, leitura, banner, 390 px,
  console — 9/9;
- Docker staging com **cópia do banco real**: web+worker healthy, evento
  disparado só pelo worker (R$ 154,88, observação 2026-11-13), sem duplicidade
  após 3 restarts, 75 usuários preservados;
- backup do banco real: `VACUUM INTO` → 4.034.560 bytes, contagens conferidas.

## 5. Publicação

Commits na branch de desenvolvimento; merge para `release/saden-productization-r2`
e promoção para `main` conforme os gates (ver `DEPLOYMENT_STATUS.md`).
