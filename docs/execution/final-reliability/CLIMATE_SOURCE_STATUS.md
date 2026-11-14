# Fechamento — estado das fontes climáticas

**Data:** 2026-11-14 · Detalhe: `docs/data_quality/CLIMATE_SOURCE_ADJUDICATION.md`

## Situação

| item | valor |
|---|---|
| linhas NASA-POWER | 5.925.166 |
| linhas INMET | 627.381 |
| pares conflitantes na mesma chave | 627.381 |
| municípios com INMET | 215 de 1.622 |
| estações INMET | 215, todas `inside_municipality` |
| distância estação–centróide | mediana 13,5 km · máx. 95,7 km |

## Adjudicação

| variável | fonte canônica | motivo |
|---|---|---|
| precipitação, temperatura, umidade, vento, radiação, solo | **NASA-POWER** | cobertura integral; INMET cobre 13,3% dos municípios |
| validação cruzada | INMET (auxiliar) | única referência independente disponível |

Concordância NASA × INMET: temperatura média r = 0,931 (viés +0,40 °C);
precipitação r = 0,644 (MAE 3,10 mm/dia); vento r = **0,409** (pior caso).

## As 2.020 linhas INMET `paired_usable`

- 9,43% das 21.422 linhas utilizáveis do painel base;
- **nenhuma análise as consumiu** — verificado por AST em 72 arquivos (28 funções
  com guarda, **0 sem guarda**) e por auditoria de runtime;
- `analysis.prepare_rows` passou a **falhar alto** com amostra mista sem fonte
  declarada (D128);
- 1 exceção documentada: `s27_panel_coverage.py`, que conta cobertura e não
  seleciona amostra.

## O que permanece aberto

Validação da **agregação de janela** contra estação (não só do diário). É o
próximo passo de maior valor com os dados já disponíveis.
