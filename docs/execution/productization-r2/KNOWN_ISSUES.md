# Release 2 — problemas conhecidos

**Data:** 2026-11-14

## Funcionais

| # | problema | impacto | estado |
|---|---|---|---|
| K1 | Monitoramento exige o worker rodando | alto | por desenho; banner denuncia e health retorna 503 |
| K2 | Sem e-mail/push | médio | fora de escopo |
| K3 | Série é referência internacional convertida | alto para decisão comercial | declarado em UI e guias |
| K4 | Sem série física regional (CEPEA/CONAB) | alto | fontes `blocked` |
| K5 | Feriado de mercado não modelado | baixo | coberto pela tolerância de 4 dias |
| K6 | `rain_above` legado sem avaliação | baixo | listado, não criável, não avaliado |
| K7 | Fuso: agenda em SP, UI no fuso do navegador | baixo | cosmético |

## Técnicos

| # | problema | impacto | estado |
|---|---|---|---|
| K8 | Node do PATH pode ser 26 (módulo nativo exige 22) | médio | `.nvmrc` + `engines` + imagem node:22 |
| K9 | CI não executado em runner remoto | médio | workflow pronto; comandos validados localmente |
| K10 | SQLite compartilhado só em host local | alto se ignorado | documentado no compose e no guia |
| K11 | `worker_runs` limitado a 500 linhas | baixo | poda automática |
| K12 | CSP bloqueia style inline de Chart.js/Leaflet (existia na V1.1) | cosmético | filtrado no E2E; não enfraquecido |

## O risco que importa

**K1.** Um usuário pode criar um alerta e esperar ser avisado enquanto o worker
está parado. Mitigação implementada: `/api/health/worker` responde 503, o banner
mostra "monitoramento temporariamente indisponível" e o healthcheck do container
marca o serviço como unhealthy. Ainda assim, isso depende de alguém olhar — não
há alerta externo de worker parado. É o primeiro item de operação a resolver.
