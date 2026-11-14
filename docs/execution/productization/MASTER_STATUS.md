# Productização — estado mestre

**Branch:** `product/price-alerts-mvp` · **Base:** `3f7ad33` (V1.1)
**Data:** 2026-11-14

## Entrega

**Monitoramento e alertas de preço por série**, implementado de ponta a ponta:
catálogo de séries com identidade estável, motor de avaliação integrado à
atualização de preços, eventos idempotentes com leitura, UI reescrita na seção
Alertas existente.

## Números

| item | valor |
|---|---|
| suíte completa | **90 testes, 0 falhas** (12 suítes) |
| testes novos | 21 unitários (16 de alertas + 5 de migração) + 4 de integração |
| séries reais no catálogo | 5 |
| endpoints novos/alterados | 6 |
| tabelas migradas | 2 (aditivas, idempotentes) |
| E2E | navegador real, 5 larguras, 0 erro de servidor |
| bugs da V1.1 corrigidos | 1 crítico (delete global de eventos) + 6 de produto |

## O que mudou no produto

- alertas deixam de ser "log de cliques" e passam a ser **regras com estado**;
- o preço passa a ser identificado por **série**, não por nome de commodity;
- a avaliação acontece **no fluxo real de atualização de preço**;
- existe **central de eventos** com leitura/não lido;
- dado desatualizado não dispara.

## O que permanece intocado

V1.1 preservada (`main`, `v1-final`, `3f7ad33`), modelo Ridge, dashboard, mapa,
relatórios, fontes, locais salvos, landing e autenticação. Pesquisa V2.6–V3.5
não foi tocada. `SADEN-TCC` não foi acessado.

## Limitação principal, dita na cara

**Não há monitoramento em segundo plano.** A avaliação ocorre quando os preços
são atualizados (consulta ao painel) ou por "Verificar agora". Com o servidor
desligado, nada dispara — e a interface diz isso.
