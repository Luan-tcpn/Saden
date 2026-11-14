# Productização — registro de execução

**Data:** 2026-11-14 · Branch `product/price-alerts-mvp`

---

## 1. Auditoria inicial

`main`/`v1-final` = `3f7ad33` confirmados. Branch criada a partir de `3f7ad33`.
Arquitetura confirmada por leitura de código (não por documentação): Express +
better-sqlite3 + frontend estático, 5 commodities, preços Yahoo×PTAX.

Inventário de funcionalidades e classificação em
`docs/product/PRODUCTIZATION_REPORT.md` §2.

**Achado principal**: já existia `backend/src/routes/alerts.js` (133 linhas), mas
era um esboço: `commodity_key` em vez de série, avaliação só manual, evento por
clique, sem estado, sem frescor e um `DELETE` de eventos **global** que apagava
eventos de outros usuários.

## 2. Decisão

Alternativas e justificativa em `docs/product/PRODUCT_DECISION.md`.
Escolhida: **alertas de preço por série com motor integrado** (em vez de
watchlist ou alerta de chuva).

## 3. Ambiente

O `better-sqlite3` instalado foi compilado para Node 22 (`NODE_MODULE_VERSION`
127) e o Node do PATH é 26 (147) → `ERR_DLOPEN_FAILED`. Em vez de recompilar
(mudaria o binário da V1.1), baixei o **Node 22.14.0 oficial** para `tmp/` e usei
esse runtime para servidor e testes. `tmp/` é ignorado pelo Git.

## 4. Implementação

Ordem: `seriesService` → `alertEngine` → migração → rotas → frontend → testes.

**Decisões de implementação registradas:**

1. **Não criar tabelas novas.** Migração aditiva em `alerts`/`alert_events`,
   com backfill, para não duplicar sistema nem perder dados da V1.1.
2. **Um único ponto de integração**: `alertEngine.runAfterPriceRefresh` chamado
   dentro de `getSeries`, imediatamente após `persistObservations`.
3. **Idempotência no banco**, não no código: índice único
   `(alert_id, event_type, observation_date)` + `INSERT OR IGNORE`.
4. **`event_type`** separa disparo (`trigger`) de log de avaliação
   (`evaluation`), preservando o contrato antigo de `/check` sem poluir a central.
5. **`rain_above` bloqueado na criação** (400 com explicação) em vez de manter
   um alerta que nunca avaliaria; registros antigos continuam visíveis.
6. **Confirmação antes de criar** alerta cuja condição já está satisfeita.
7. **Compatibilidade**: `POST /api/alerts` aceita `commodity_key`+`kind` e
   resolve para a série; `PATCH {active}` continua funcionando.

## 5. Erros encontrados e corrigidos durante a execução

| # | problema | correção |
|---|---|---|
| 1 | ciclo de `require` (`db.js` → `seriesService` → `db.js`) | helper de slug inlined em `db.js` |
| 2 | `alerts` sem `condition` quebrava o motor | backfill `condition ← kind` na migração |
| 3 | tabela de alertas (560 px) estourava a viewport em 390/414 px | `overflow-x:auto` nos blocos de tabela |
| 4 | rótulo "Limite ( R$/lp )" quebrava em 3 linhas | unidade movida para um `span` com `white-space:nowrap` |
| 5 | teste unitário com fixture usada como módulo (`FixtureFunctionDefinition`) | helper recebe o módulo explicitamente |

## 6. Verificação

- `npm test`: **85 passam, 0 falham**, 11 suítes (todas as da V1.1 incluídas).
- E2E no navegador (agent-browser + Chrome): cadastro → dashboard com preço real
  → alertas → criação com confirmação → avaliação → evento → leitura.
- Servidor: **0 linhas de erro** no log durante todo o E2E.
- Responsividade: 320/390/414/768/1024 px, **sem overflow horizontal**.

## 7. Publicação

Commit único na branch `product/price-alerts-mvp`. Sem merge em `main`, sem
force push, sem alteração de tags ou de branches anteriores.
