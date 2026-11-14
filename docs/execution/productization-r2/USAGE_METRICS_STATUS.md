# Release 2 — métricas e uso

**Data:** 2026-11-14

## O que é coletado

| dado | onde | para quê |
|---|---|---|
| ciclos (início, fim, status, duração) | `worker_runs` | saber se o monitoramento funciona |
| séries tentadas/ok/falhas por ciclo | `worker_runs` | dimensionar o trabalho |
| observações novas, alertas avaliados, eventos criados | `worker_runs` | medir o efeito real |
| duplicados bloqueados | `worker_runs` | detectar bug de concorrência |
| falhas por série e último erro | `series_state` | diagnosticar a fonte |
| alertas por estado | `alerts` | uso agregado do recurso |
| eventos, lidos/não lidos | `alert_events` | uso real do aviso |
| feedback (tipo + texto) | `feedback` | dor declarada |

## O que NÃO é coletado

- senha, token, conteúdo de sessão;
- comportamento de navegação, cliques, tempo de tela;
- qualquer dado enviado a terceiros (não há analytics externo);
- identificação individual em métricas de produto (agregação apenas).

## Retenção

| dado | retenção |
|---|---|
| `worker_runs` | 500 execuções |
| `worker_locks` vencidos | removidos no boot |
| alertas, eventos, séries | permanentes |
| feedback | permanente (sem expurgo automático — decisão manual) |

## Como consultar

- **Usuário**: banner de monitoramento + eventos na página de Alertas.
- **Operador**: `GET /api/ops/status` (admin) — worker, fontes, métricas de 7
  dias, últimas 10 execuções, contagens de produto.
- **SQL direto**: `runner.metrics({windowDays})`.

## Interpretação honesta

- **quantidade de alertas não é satisfação**; um alerta criado e nunca reativado
  pode indicar limite mal calibrado.
- **zero eventos** numa semana pode ser saudável (preço não cruzou o limite) ou
  sintoma (worker parado) — por isso a métrica de ciclos acompanha a de eventos.
- **taxa de sucesso dos ciclos** é a métrica de confiabilidade que importa; hoje
  não há volume real para publicar números.

## Estado atual

Não há uso real registrado além dos testes. Nenhum número de uso é apresentado
aqui — seria inventar. As estruturas estão prontas e o painel mostrará os dados
quando existirem.
