# SADEN V2.8 — Status da execução

> Etapa: **V2.8 — Generalização temporal-espacial, linha de base e integração agroclimática**.
> Atualizado em: 2026-11-14 (sessão 1).

## Objetivo

Responder: **os resultados agroclimáticos da V2.6/V2.7 representam capacidade
real de generalização para municípios e anos não observados, ou parte do
desempenho depende da composição dos dados, da construção da linha de base e
de informação compartilhada entre treino e teste?**

A pergunta operacional mais concreta herda uma fragilidade da V2.7: o
protocolo P5 reduziu o treino em ~36% **ao mesmo tempo** em que removeu o ano
compartilhado. Portanto **não está demonstrado que a inversão da soja
(−3,30%) foi causada pelo ano** — pode ser tamanho de amostra ou composição.
Separar esses mecanismos é a prioridade nº 1.

## Identificação da linha

| Item | Valor |
|---|---|
| Repositório | `C:\Users\luanf\OneDrive\Área de Trabalho\Saden_AgroClima` |
| Branch | `v2/temporal-spatial-generalization` (base `36bf5d7` = V2.7) |
| V2.7 preservada | `v2/agroclimatic-robustness` em `36bf5d7`, publicada em `origin` |
| Bundle V2.7 | `..\SADEN_V2_7_RECOVERY_2026-11-14\`, SHA-256 `0AB3CDF2…04B9C9`, verify *okay* |
| V1 | `3f7ad33` (tag `v1-final`) — intacta |
| `main` | `3f7ad33` — intacta |
| Ambiente | `geospatial\.venv\Scripts\python.exe` (3.12.10); sem SciPy |
| Suíte de referência | **318/318** offline (confirmada nesta sessão) |

## Estado das fases

| Fase | Item | Estado |
|---|---|---|
| 0 | Proteção, auditoria e criação da branch | **concluída** |
| 1 | Auditoria e reprodução de P1/P3/P5 | **em curso** |
| 2 | Decomposição temporal-espacial (fatorial + controle de tamanho) | pendente |
| 3 | Linha de base e benchmarks | pendente |
| 4 | CAD e balanço hídrico | pendente |
| 5 | Fenologia, ZARC e ciclos | pendente |
| 6 | Diagnóstico de cobertura | pendente |
| 7 | Síntese científica | pendente |
| 8 | Validação final, bundle e publicação | pendente |

## Próxima ação executável

Fase 1: mapear `analysis.territorial_holdout`, `analysis.two_way_blocked_holdout`
e `run_robustness.py spatial`; registrar exatamente unidades de separação,
anos compartilhados, tamanhos de treino/teste por dobra e a fórmula do ganho;
reproduzir os números de `v27_spatial_validation.json`.

## Decisões da V2.8

(registrar em `docs/DECISIONS.md`, a partir de D87)

## Bloqueios conhecidos

- ERA5-Land nativo: credencial CDS ausente (D83). Não criar conta.
- CHIRPS/ARCO: sem DNS.
