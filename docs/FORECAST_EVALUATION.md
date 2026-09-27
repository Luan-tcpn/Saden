# SADEN — Avaliação de Forecast E2: AR(p) challenger vs Ridge (investigação)

> Data: 2026-09-27. Hipótese vinda da matriz V1_1 (ARIMA como challenger).
> Regras: D35 (mesma série, mesmo split, mesmas métricas, sem shuffle, sem leakage, teste só para relato).
> Script reproduzível: `tmp/ar-challenger.py` (somente leitura em `data/saden.db`; `tmp/` não versionado — procedimento abaixo permite repetição).

## Hipótese

Séries de preço BRL têm ACF1 0,94–0,98 (alta persistência). Um AR(p) com ordem
selecionada por AIC no treino pode superar a Ridge one-step na validação,
porque captura persistência de nível diretamente, sem as features de
tendência/volatilidade da Ridge.

## Dados

`price_observations` reais (`data/saden.db`): soja 265, milho/café/trigo/algodão
257 pontos, 2025-09-08–2026-09-25. Colunas: `data_date, price_brl`, ordenado.

## Protocolo (idêntico para os dois modelos)

- Split: WARMUP=30 → linhas `[30, n-2]`, 70/15/15 sem shuffle (réplica exata de `buildRows`/`splitRows`).
- Alvos de validação idênticos; previsão **one-step-ahead com lags observados** (mesmo protocolo da avaliação Ridge em `forecastService.js:204-219`).
- Seleção: Ridge por grade λ {0.1,1,10,100} no treino; AR por AIC p∈1..8 no treino. Validação decide; teste só relatado.
- Métrica de decisão: RMSE de validação.

## Sanidade da réplica

Ridge replicada em numpy vs `model_runs` persistidos (janelas de série
ligeiramente distintas — Yahoo ao vivo vs observações persistidas):

| commodity | réplica val | armazenado val |
|---|---|---|
| soja | 2,13 (λ=0.1) | 2,21 |
| milho | 0,91 (λ=0.1) | 1,05 |
| café | 164,5 (λ=0.1) | 158,0 |
| trigo | 2,16 (λ=0.1) | 1,90 |
| algodão | 0,0907 (λ=10) | 0,0900 |

Divergências ≤15%, compatíveis com janelas distintas. Réplica aceita como base justa
(ambos os modelos, a partir daqui, usam EXATAMENTE a mesma série).

## Resultado (RMSE; val = decisão, test = relato)

| commodity | val_n | Ridge val | AR val (p) | test Ridge | test AR |
|---|---|---|---|---|---|
| soja | 35 | 2,135 | **1,671 (p=3)** | 3,671 | 2,103 |
| milho | 33 | 0,911 | **0,765 (p=7)** | 1,934 | 1,069 |
| café | 33 | 164,5 | **102,9 (p=8)** | 192,9 | 68,4 |
| trigo | 33 | 2,158 | **1,470 (p=8)** | 3,914 | 1,930 |
| algodão | 33 | 0,0907 | **0,0695 (p=1)** | 0,1553 | 0,0823 |

AR vence na validação em **5/5** (margem 16–37%). ACF confirma persistência
(ACF1 ≥0,94; café ACF20 ainda 0,71 — memória longa / choque lento).

## Interpretação

- Evidência suficiente para **implementar AR(p) como challenger no pipeline JS** (mesma série viva, mesmo split, mesmas métricas, mais avaliação recursiva H=7/14/30 e intervalo).
- NÃO é evidência para substituir Ridge: (a) comparação é one-step, mas o produto usa previsão **recursiva** multi-passo — desempenho multi-passo do AR é desconhecido; (b) AR sem regularização com p até 8 e val_n≈34 tem estimativa ruidosa; (c) sem termos MA/sazonais — "ARIMA" próprio continua não testado.
- Sem ensemble: só após o challenger existir no pipeline e com erros complementares demonstrados.

## Limitações

- Série de ~1 ano; val_n 33–35 (poder estatístico limitado).
- Série = observações persistidas (com fallback de FX), não o Yahoo-ao-vivo exato de cada run.
- Script em `tmp/` (não versionado); reprodução exige o mesmo `data/saden.db` ou re-extração.

## Conclusão

**GO condicional**: implementar `AR(p)+AIC` como challenger isolado no backend,
sob os gates da D37. Ridge permanece champion até o challenger provar valor
também no horizonte recursivo.
