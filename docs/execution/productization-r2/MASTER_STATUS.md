# Release 2 — estado mestre

**Branch dev:** `product/background-monitoring-release-2` (base `08b9855`)
**Data:** 2026-11-14

## Entrega

Monitoramento automático independente do navegador, com lease persistente,
idempotência no banco, recuperação, saúde observável, Docker web+worker, CI e
métricas operacionais.

## Números

| item | valor |
|---|---|
| testes | **125, 0 falhas** (90 herdados + 26 worker unit + 9 worker integração) |
| E2E navegador (CDP) | 9 verificações verdes |
| Docker | web + worker `healthy`; evento disparado sem navegador |
| idempotência | 1 evento após 3 ciclos/restarts |
| banco real preservado | 75 usuários → 76 (só o usuário de teste) |
| novos arquivos | 7 no backend worker, 2 de teste, 1 de CI, 6 de documentação |

## O que ficou provado

- alerta dispara com o navegador fechado, se o worker estiver ativo;
- duas instâncias não executam o mesmo job;
- lease vencido é recuperado por outra instância;
- restart não duplica evento;
- interface denuncia worker parado (503 + banner).

## O que não foi feito

- deploy público (não há ambiente autorizado);
- execução do CI em runner remoto;
- e-mail/push (fora de escopo).
