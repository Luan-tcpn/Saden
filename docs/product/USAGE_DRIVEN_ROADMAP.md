# SADEN — Roadmap orientado por uso

**Data:** 2026-11-14

Backlog futuro guiado por evidência, não por vontade. Ordem de prioridade
definida por sinais que o sistema já produz.

---

## 1. Como a prioridade é decidida

| sinal | de onde vem | o que indica |
|---|---|---|
| ciclos com falha | `worker_runs.status` | fonte instável ou agenda errada |
| `series_state.consecutive_failures` | por série | qual fonte quebra |
| atraso de fonte | `series_state.last_success_at` vs agenda | publicação mudou de horário |
| eventos duplicados bloqueados | `worker_runs.duplicates_blocked` | bug de concorrência se > 0 recorrente |
| alertas que nunca disparam | `alerts` vs `alert_events` | limite mal calibrado pelo usuário ou série ruim |
| reativações | `alerts.status` histórico | alerta disparou cedo demais |
| feedback | `feedback.kind`/`message` | dor real declarada |

Nenhum desses sinais exige rastrear usuário individualmente.

## 2. Prioridade 1 — confiabilidade do que já existe

1. **Feriado de mercado**: hoje coberto por tolerância de 4 dias. Se aparecerem
   falsos "atrasado" recorrentes em janeiro/feriados prolongados, incluir
   calendário de negociação por bolsa.
2. **Fonte de backup**: se `series_state` mostrar falhas repetidas da Yahoo,
   avaliar segunda fonte para a mesma série (Stooq/Investing) — só com validação
   de que os valores são comparáveis.
3. **Observabilidade mínima**: gráfico simples de ciclos/dia e taxa de sucesso no
   painel admin (dados já existem).

## 3. Prioridade 2 — utilidade percebida

4. **Prazo de validade do alerta**: permitir "expira em X dias" — reduz alertas
   esquecidos que nunca disparam.
5. **Alerta sobre preço médio** (ex.: média de 7 dias), não só último fechamento:
   menos ruído para quem decide venda.
6. **Exportar eventos** em CSV, no padrão dos relatórios existentes.
7. **Resumo semanal interno**: uma linha por semana com o que disparou.

## 4. Prioridade 3 — somente com evidência nova

8. **Série física regional**: bloqueada por falta de API pública (CEPEA/CONAB).
   Só entra se surgir fonte oficial com URL estável.
9. **Notificação por e-mail**: só com SMTP real configurado e consentimento.
   O outbox atual é de desenvolvimento e não conta.
10. **Múltiplos canais (push/WhatsApp/Telegram)**: fora de escopo até haver
    usuários ativos pedindo.

## 5. O que NÃO entra no roadmap

- novos modelos de preço sem ganho temporal pareado (Ridge permanece);
- previsão de safra, indicadores de oferta não validados;
- integração clima × preço sem demonstração de ganho;
- analytics de terceiros, rastreamento individual, CRM.

## 6. Gatilhos de revisão

Revisar este documento quando ocorrer **qualquer** um:

- 30 dias de uso com pelo menos 3 contas ativas;
- 5 itens de feedback sobre o mesmo tema;
- taxa de sucesso dos ciclos < 90% em uma semana;
- qualquer evento duplicado observado em produção.

Sem gatilho, a prioridade continua sendo o item 1.
