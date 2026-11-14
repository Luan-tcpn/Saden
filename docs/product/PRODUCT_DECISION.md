# SADEN — Decisão de produto: alertas de preço

**Data:** 2026-11-14 · Branch `product/price-alerts-mvp` · Base `3f7ad33` (V1.1)

---

## 1. Problema

O usuário do SADEN já consulta preço de referência, mas **só descobre que o preço
mudou se abrir o app e olhar**. A V1.1 tinha um esboço de alertas que não
resolvia isso:

| Defeito encontrado na auditoria | Consequência |
|---|---|
| alerta preso a `commodity_key` | não identifica contrato, moeda nem unidade |
| `check` só por botão manual | nada é avaliado quando o preço é atualizado |
| evento gravado a cada clique | histórico poluído, sem idempotência |
| sem estado | "ativo/inativo" apenas; sem "disparado" nem rearme |
| sem frescor | dado de 30 dias dispara como se fosse de hoje |
| `DELETE` global de eventos | **apagava eventos de outros usuários** (bug real) |
| sem leitura/não lido | impossível saber o que é novo |

## 2. Alternativas avaliadas

| alternativa | veredito |
|---|---|
| **Alertas de preço por série, com motor integrado** | **escolhida** — resolve a dor, usa dados existentes |
| Lista de acompanhamento (watchlist) | útil, mas é o mesmo dado sem ação; não justifica a versão |
| Alerta de chuva (existente na V1.1) | `rain_above` depende de previsão de 7 dias, não de observação; pouco acionável e não é preço |
| Alerta de preço físico regional (CEPEA/CONAB) | **inviável**: sem API pública (fontes `blocked`) |
| Notificação por e-mail | fora de escopo: não há infraestrutura real; o outbox é de desenvolvimento |

## 3. Funcionalidade escolhida

**Monitoramento e alertas de preço por série, com avaliação integrada à
atualização de preços e central de eventos interna.**

Fluxo: escolher série → condição → limite → salvar → o motor avalia cada
observação nova → evento na central → marcar como lido → pausar/reativar/excluir.

## 4. Justificativa

1. **Usa o que existe**: as séries reais (`commodities` + Yahoo + PTAX) já são
   buscadas e persistidas em `price_observations` em cada consulta de preço.
2. **Sem infraestrutura nova**: a avaliação acontece onde o preço já é
   persistido; não exige cron, fila ou serviço externo.
3. **Acionável**: o valor do alerta é o evento, não a tela.
4. **Honesto**: identifica instrumento, fonte, moeda, unidade e limitações, e
   bloqueia disparo com dado desatualizado.

## 5. Valor prático

O usuário deixa de precisar abrir o app para saber se o preço cruzou o limite:
o alerta é avaliado quando o preço é atualizado (consulta ao painel) e em
"Verificar agora", e o evento fica registrado com preço, data e série.

## 6. Dependências

- `price_observations` (persistência já existente);
- `seriesService` (novo): identidade estável da série;
- `alertEngine` (novo): condição, frescor, idempotência, estado;
- `alerts` / `alert_events` (migração aditiva das tabelas da V1.1);
- frontend: seção Alertas (já existia, foi reescrita).

## 7. Limitações (declaradas na interface)

1. **Não há monitoramento em segundo plano.** A avaliação ocorre quando os
   preços são efetivamente atualizados (consulta ao painel) ou em "Verificar
   agora". Com o servidor desligado, **nada dispara**.
2. **Série é referência internacional convertida** (futuro × PTAX), **não** o
   preço recebido pelo produtor.
3. **Não existe série física regional** (CEPEA/CONAB sem API pública).
4. Frescor: observação com mais de **7 dias** não dispara.
5. Disparo **único** por padrão; rearme é manual.
6. Notificação **interna** apenas — sem e-mail nem push.

## 8. Critérios de aceitação

- [x] usuário escolhe série real e vê mercado, fonte, unidade, moeda e data;
- [x] cria alerta com condição acima/abaixo e limite;
- [x] última observação já satisfazendo a condição é explicada **antes** de criar;
- [x] evento criado uma única vez por observação (idempotência);
- [x] alerta passa a "disparado" e pode ser reativado;
- [x] dado desatualizado não dispara;
- [x] eventos com leitura/não lido;
- [x] isolamento entre usuários testado;
- [x] validação rejeita série inexistente, moeda/unidade incompatível e condição inválida;
- [x] responsividade 320–1024 px sem overflow horizontal.
