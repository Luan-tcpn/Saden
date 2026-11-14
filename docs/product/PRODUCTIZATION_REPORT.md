# SADEN — Relatório de productização (release 1)

**Data:** 2026-11-14
**Branch:** `product/price-alerts-mvp` · **Base:** `3f7ad33` (V1.1)
**Funcionalidade:** monitoramento e alertas de preço por série

---

## 1. Estado anterior

A V1.1 é uma aplicação Node.js 22 + Express + SQLite (`better-sqlite3`) com
frontend estático (HTML/CSS/JS, Leaflet, Chart.js) servido pelo próprio backend.
Cinco commodities, preços de futuros (Yahoo) convertidos por PTAX (BCB),
previsão Ridge, clima (Open-Meteo), mapa, relatórios, locais salvos e um
**esboço** de alertas por commodity.

## 2. Auditoria

| Funcionalidade | Estado na V1.1 | Ação nesta release |
|---|---|---|
| Landing page | completa | preservada |
| Login / cadastro / recuperação | completo | preservado |
| Dashboard (preço, previsão, clima) | funcional com limitações (dado diário, sem regional) | preservado |
| Mapa (OSM/satélite/cobertura) | funcional | preservado |
| Relatórios JSON/CSV/impressão | completo | preservado |
| Fontes e metodologia | completo | preservado |
| **Alertas** | **parcialmente implementado e defeituoso** | **reescrito e integrado** |
| Notificações | inexistente | **central de eventos interna** |
| Lista de séries | inexistente (só `commodity_key`) | **catálogo com identidade estável** |

Defeitos confirmados nos alertas da V1.1: sem identidade de série, avaliação
apenas manual, evento gravado a cada clique (sem idempotência), sem estado de
disparo, sem frescor, sem leitura/não lido e um `DELETE` de eventos **global**
que apagava registros de outros usuários.

## 3. Arquitetura da entrega

```
backend/src/
  services/seriesService.js   catálogo + identidade estável + frescor
  services/alertEngine.js     condição, idempotência, estado, gancho pós-preço
  routes/series.js            GET /api/series, GET /api/series/:id
  routes/alerts.js            CRUD + avaliação + eventos + leitura
  db.js                       migração aditiva (upgradeAlerts)
frontend/
  index.html (#page-alertas)  nova UI de alertas
  js/app.js                   fluxo completo
  js/api.js                   novos métodos
  css/styles.css              pills, badge, séries, rolagem de tabela
```

O motor é chamado em **um único ponto de integração**: logo após
`priceService.persistObservations`, dentro de `getSeries`. Toda consulta de preço
que traz dados novos avalia os alertas daquela série.

## 4. Banco de dados

Migração **aditiva e idempotente** (`PRAGMA table_info` + `ALTER TABLE`),
executada no `migrate()`:

`alerts` recebeu: `series_id`, `condition`, `currency`, `unit`, `instrument`,
`market`, `source`, `price_type`, `status`, `last_evaluated_at`, `triggered_at`,
`last_price`, `last_observation_date`, `updated_at`.

`alert_events` recebeu: `event_type` (`trigger` | `evaluation`),
`observation_date`, `observed_price`, `read_at`.

Backfill: `condition ← kind`, `status ← active`, `series_id` derivado da
commodity. Índices novos, incluindo a **chave de idempotência**:

```sql
CREATE UNIQUE INDEX idx_alert_events_unique
  ON alert_events(alert_id, event_type, observation_date);
```

Nada foi removido ou renomeado: a V1.1 continua lendo `commodity_key` e `active`.

## 5. API

| Método | Rota | Função |
|---|---|---|
| GET | `/api/series` | catálogo (5 séries) com mercado, fonte, unidade, última observação e frescor |
| GET | `/api/series/:id` | uma série; 404 se não existir |
| GET | `/api/alerts` | regras + contagem de eventos não lidos + condições |
| POST | `/api/alerts` | cria (aceita `series_id`+`condition` ou `commodity_key`+`kind`) |
| PATCH | `/api/alerts/:id` | pausar / reativar (`active` ou `status`) |
| DELETE | `/api/alerts/:id` | exclui |
| POST | `/api/alerts/check` | avaliação manual (contrato V1.1 preservado) |
| POST | `/api/alerts/evaluate` | avalia todas as séries com alertas ativos do usuário |
| GET | `/api/alerts/events` | feed de disparos (`?unread=1`) |
| POST | `/api/alerts/events/read` | marca lidos (todos ou `ids[]`) |
| GET | `/api/alerts/:id/events` | eventos de um alerta |

Todas exigem `Authorization: Bearer`. `user_id` vem **do token**, nunca do corpo.

## 6. Frontend

Seção **Alertas** reescrita, mantendo navegação, cores, cartões e tipografia:

- seletor de **série** (5 opções reais, com mercado e unidade no rótulo);
- painel da série: `series_id`, mercado, instrumento, fonte, última observação,
  preço do último dado e situação (`atualizada` / `desatualizada` / `sem observação`);
- condição e limite, com a **unidade da série** no rótulo;
- aviso explícito (confirmação) quando a última observação **já satisfaz** a condição;
- lista de alertas com estado (`ativo`, `pausado`, `disparado`), último preço e ações;
- central de eventos com marcação de não lido e botão "marcar como lidos";
- contador de não lidos no título da seção.

## 7. Dados reais

Consulta real executada na validação E2E (Yahoo + PTAX, sem fixture):

| item | valor |
|---|---|
| série | `yahoo:CT=F:brl:lp` (algodão, ICE) |
| última observação | **2026-11-13** · R$ 4,45/lp |
| situação | atualizada |
| série usada no alerta de teste | `yahoo:ZS=F:brl:sc60` · R$ 154,88/sc 60kg em 2026-11-13 |

## 8. Frequência de atualização e funcionamento com o app fechado

- **Fonte**: fechamentos diários em dias úteis.
- **Avaliação**: ocorre quando `getSeries` persiste observações (isto é, ao
  consultar preços com cache expirado) e em "Verificar agora".
- **Com o servidor desligado, nada é avaliado.** Não há cron, fila nem worker.
  A interface diz isso explicitamente na seção de eventos.
- Cache de preços: 60 min por padrão (`CACHE_PRICES_TTL_MIN`).

## 9. Segurança

| item | estado |
|---|---|
| XSS | todo texto interpolado passa por `esc()`; IDs/valores vindos da API também |
| SQL | sempre parametrizado (`prepare().run/all`) |
| Autorização | `user_id` extraído do JWT; toda query filtra por usuário |
| Acesso cruzado | testado em integração (alerta e eventos de terceiros: 404 / 0 linhas) |
| Validação | série existente, condição suportada, limite numérico, moeda/unidade compatíveis |
| Headers/CSP | herdados da V1.1 (sem enfraquecimento) |
| Rate limit | herdado do login (não aplicado a alertas) |
| Regressão de segurança | **corrigido**: o `DELETE` global de eventos da V1.1 foi removido |

## 10. Testes

| nível | arquivo | resultado |
|---|---|---|
| unitário | `tests/unit/alerts.test.js` (novo) | **16/16** |
| integração | `tests/integration/api.test.js` (4 casos novos + todos os da V1.1) | **36/36** |
| suíte completa | `npm test` (11 suítes) | **85 passam, 0 falham** |
| E2E | navegador real (agent-browser + Chrome), fluxo completo | ver §11 |

## 11. Validação end-to-end (navegador real)

Executado em `http://127.0.0.1:3100`, servidor Node 22 com banco dedicado:

1. landing → "Criar conta" → cadastro → app carregado;
2. Dashboard buscou preços reais (Yahoo + PTAX) e persistiu observações;
3. Alertas → série de algodão exibiu **R$ 4,45/lp em 2026-11-13, "atualizada"**;
4. criou alerta em soja (`≥ 1`): a confirmação mostrou
   *"A última observação já satisfaz a condição: Soja: R$ 154,88 R$/sc 60kg em
   2026-11-13…"*;
5. "Verificar agora" → **1 avaliado, 1 evento novo**;
6. lista mostrou estado **disparado**; feed mostrou o evento como **novo**;
7. "Marcar eventos como lidos" → badge desapareceu, evento como **lido**;
8. console do servidor: **0 erros**;
9. responsividade: 320/390/414/768/1024 px **sem overflow horizontal**.

**Defeito encontrado e corrigido no E2E**: em 390/414 px a página de alertas
transbordava (tabela de 560 px). Corrigido com rolagem interna do bloco
(`overflow-x:auto`), preservando tabela e colunas.

## 12. Instruções

```bash
cd backend
npm install          # Node 18+; validado em 22.14.0
npm start            # http://localhost:3001
npm test             # 85 testes

# Docker (arquivos da V1.1 preservados)
docker compose up --build
```

Migração roda no primeiro `connect()`; bancos existentes são atualizados sem
perda de dados. **Faça backup de `data/saden.db` antes de subir em produção.**

## 13. Limitações

1. Sem monitoramento em segundo plano (ver §8).
2. Série é referência internacional convertida; não é preço local.
3. Sem e-mail/push; notificação apenas interna.
4. Frescor fixo em 7 dias para todas as séries (fonte diária).
5. Alerta de chuva (`rain_above`) da V1.1 **não é mais criável**; alertas
   existentes desse tipo permanecem visíveis mas não são avaliados.
6. Não há simulador de "e se o preço chegar a X" nem projeção de quando o limite
   seria atingido — deliberadamente fora do escopo desta release.
