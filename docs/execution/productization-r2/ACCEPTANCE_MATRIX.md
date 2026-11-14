# Release 2 — matriz de aceitação

**Data:** 2026-11-14

| # | critério | estado | evidência |
|---|---|---|---|
| 1 | worker independente | **implementado + testado** | `backend/src/worker/`, processo próprio |
| 2 | agendamento ativo | **implementado + testado** | 18h SP, dias úteis; 6 testes de agenda |
| 3 | fonte consultada na frequência certa | **implementado** | diária em dia útil, mínimo 1 h por série |
| 4 | alertas avaliados sem navegador | **validado em Docker** | evento criado após `docker restart` do worker |
| 5 | locks impedem concorrência | **testado** | 2 instâncias: 1 adquire, 1 recusa |
| 6 | lease recuperável | **testado** | lease vencido assumido por outra instância |
| 7 | eventos idempotentes | **testado + validado** | 1 evento após 3 ciclos/restarts |
| 8 | recuperação de falha | **testado** | erro de fonte registrado, alerta segue armado |
| 9 | shutdown gracioso | **testado** | SIGTERM libera lock, idempotente |
| 10 | health checks | **implementado + validado** | web 200; worker 200/503 conforme heartbeat |
| 11 | interface mostra estado real | **implementado + validado no E2E** | banner ok/degraded/down/not_started |
| 12 | rate limiting | **implementado + testado** | 429 após 20 avaliações/10 min |
| 13 | E2E no CI | **configurado** | workflow pronto; execução local verde, runner remoto pendente |
| 14 | Node 22 padronizado | **implementado** | `.nvmrc`, `engines >=22 <25`, imagem node:22-slim |
| 15 | Docker Compose web+worker | **validado** | ambos `healthy`, worker dependente do web |
| 16 | persistência comprovada | **validado** | 75 usuários preservados; alerta/evento sobrevivem a restart |
| 17 | backup e restauração testados | **validado** | `VACUUM INTO` + abertura da cópia com contagens |
| 18 | métricas operacionais | **implementado** | `worker_runs`, `runner.metrics()`, `/api/ops/status` |
| 19 | privacidade | **implementado** | agregação, sem terceiros, sem tracking individual |
| 20 | testes aprovados | **125/125** | unit + integração + worker |
| 21 | documentação | **completa** | 3 guias de produto + 8 checkpoints |

## Bloqueado / não cumprido

| # | item | estado | motivo |
|---|---|---|---|
| 22 | deploy público | **bloqueado** | sem infraestrutura autorizada |
| 23 | CI em runner remoto | **pendente** | sem push para Actions neste ambiente |
| 24 | e-mail/push | **fora de escopo** | decisão da release |

## Veredito

O critério decisivo — *alerta dispara com o navegador fechado* — foi **cumprido e
validado em container com o banco real copiado**. A versão está tecnicamente
liberada e pronta para deploy; **não** está publicamente disponível.
