# Release 2 — estado do deploy

**Data:** 2026-11-14

## Classificação

| item | estado |
|---|---|
| versão tecnicamente liberada | **sim** (125 testes, E2E, Docker) |
| staging local (Docker, cópia do banco real) | **executado e validado** |
| ambiente público / produção | **não existe** — sem host, domínio ou autorização |
| publicação | **não publicada** |

## Auditoria de hospedagem

Não há configuração de produção neste repositório: nenhum `Dockerfile` de
plataforma, nenhum manifesto de PaaS, nenhuma credencial de deploy, nenhum
domínio. O que existe é o compose local (`docker compose up`). Não foi contratado
nem provisionado nada.

## O que está pronto para deploy

- imagem `saden:r2` (Node 22-slim), web + worker;
- compose com health checks, dependência ordenada, restart policy;
- volume único para SQLite;
- backup e restauração testados;
- health endpoints e painel admin;
- procedimento de rollback documentado.

## O que falta para publicar

| # | pendência | observação |
|---|---|---|
| 1 | host com Docker e volume persistente | um host só (SQLite local) |
| 2 | `JWT_SECRET` de produção | obrigatório; o app falha sem ele |
| 3 | `SADEN_ADMIN_EMAILS` | para o painel operacional |
| 4 | DNS/TLS | não alterado sem autorização |
| 5 | rotina de backup externa | o script existe; falta agendamento |
| 6 | alerta de worker parado | hoje é passivo (health); falta notificação ao operador |

## Staging executado — evidência

Com `SADEN_DATA_DIR=./tmp/r2data` (cópia do banco real):

- `saden` e `saden-worker` **healthy**;
- 12 execuções registradas em `worker_runs`;
- alerta criado → evento disparado **apenas pelo worker** (R$ 154,88 em 2026-11-13);
- 3 restarts do worker → **1 evento**, sem duplicidade;
- 75 usuários preservados (76 com o usuário de teste);
- migration aplicada sobre dados reais sem perda.

## Rollback

Ver `docs/product/PRODUCTIZATION_RELEASE_2_REPORT.md` §22. Migrations são
aditivas; voltar o código não exige reverter schema.
