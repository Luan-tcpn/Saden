# SADEN V1 final

Congelamento da V1 com **metodologia única de previsão: Ridge Regression**.

## O que está validado

- **Ridge** é o único método operacional de previsão. Pipeline, split temporal
  70/15/15, baselines, seleção de λ por validação, intervalo e métricas
  permanecem os mesmos da V1 validada.
- **AR(p) foi retirado do produto** (D40): `arService.js`, `olsBeta`, o seletor
  `#sel-model` e o estado de modelo no frontend não existem mais.
- `?model=ridge` é aceito apenas como **alias legado**. Qualquer outro valor
  (`ar`, `AR`, `arima`, vazio ou desconhecido) retorna **HTTP 400**, sem
  fallback silencioso.
- O **histórico experimental** em `model_runs` foi preservado, sem migração,
  renomeação ou reinterpretação: `ar(order=3)` = 5 linhas e
  `ar(order=1)` = 4 linhas continuam legíveis como registro do experimento.
- Gates executados e registrados no relatório de encerramento:
  `npm test` **65/65** (9 suítes), smoke **9/9** (local e container),
  E2E **57/57** em Edge headless/CDP com `pageErrors: []`, e Docker validado
  (build, up healthy, auth, Ridge, `model=ar` → 400, persistência down/up,
  smoke no container).

## Commit e tag

- Commit: `3f7ad33bc18c5a8e8e050bbc7817f5078488d625`
- Tag anotada: `v1-final` → objeto `e62a5372e8bc69a87f642398681ed4df13d4fc54`
  → commit acima
- Branch de arquivo: `archive/v1-final` (mesmo commit)
- Bundle Git e backup SQLite: documentados em `docs/V1_RECOVERY.md`

## Limitações importantes

Esta release **não declara a V1 pronta para produção pública**. Continuam
pendentes:

- TLS / reverse proxy;
- SMTP real para recuperação de senha (hoje existe apenas outbox de
  desenvolvimento);
- backup automatizado com verificação e retenção;
- monitoramento/healthcheck externo e alertas;
- teste de carga e avaliação de capacidade.

Também permanecem como limitações conhecidas: preço de referência
internacional (não preço físico regional), modelo univariado, série de
aproximadamente um ano, intervalo gaussiano sem cobertura empírica e instância
única com rate-limit em memória.

## Escopo congelado

Nenhuma funcionalidade da V2 está incluída nesta release. O desenvolvimento
geoespacial da V2 ocorre em branch separada (`v2/geospatial-foundation`) e não
altera `main` nem a tag `v1-final`.
