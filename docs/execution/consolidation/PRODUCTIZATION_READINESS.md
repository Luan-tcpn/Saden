# Consolidação — prontidão para o produto

**Data:** 2026-11-14
Documento completo: `docs/product/PRODUCTIZATION_READINESS.md`

---

## Estado

| item | valor |
|---|---|
| aplicação alterada | **não** |
| frontend / backend / banco | inalterados |
| merge em `main` | não realizado |
| V1.1 | intacta (`v1-final` = `3f7ad33`) |

## Candidatos avaliados

| candidato | veredito |
|---|---|
| contexto agroclimático descritivo (percentil do déficit) | **prioridade 1** |
| informação territorial (MRS, CAD, área) | prioridade 2 |
| explicação das previsões de preço (Ridge) | prioridade 3 |
| relatórios exportáveis | prioridade 4 |
| indicador de oferta | **não fazer** |
| alerta de safra | **não fazer** |

## Por que "indicador de oferta" e "alerta de safra" estão fora

Não há **nenhuma** validação preditiva de produtividade fora da amostra. A
linha de pesquisa produz associação, não previsão. Exibir produtividade esperada
como expectativa de safra seria transformar um resultado associativo em promessa
preditiva — exatamente o que a disciplina do projeto evitou até aqui.

## Condições antes de implementar qualquer coisa

1. Redação do texto exato do contexto agroclimático, revisada criticamente.
2. Verificação de que a série 2025 está completa para os municípios exibidos.
3. Escopo e autorização próprios, em branch separada.

## Veredito

A linha de pesquisa **não supera** a V1.1 como aplicação: não tem interface, não
tem validação preditiva e cobre 48,3% do território. É insumo potencial para uma
V2.0 que ainda não existe e não foi autorizada.
