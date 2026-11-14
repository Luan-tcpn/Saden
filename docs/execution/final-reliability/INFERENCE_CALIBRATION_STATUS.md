# Fechamento — estado da calibração de inferência

**Data:** 2026-11-14 · Detalhe: `docs/statistics/WILD_CLUSTER_BOOTSTRAP_CALIBRATION.md`

## Desenho

G e tamanhos de cluster reais; ICC do erro e da exposição estimados do painel;
ruído casado por momento com o EP observado. 5.000 replicações, 999 bootstraps.

| cultura | G | m | ICC erro | ICC exposição | EP real |
|---|---:|---:|---:|---:|---:|
| soja | 48 | 260,8 | 0,280 | 0,513 | 0,400 |
| milho | 56 | 214,5 | 0,220 | 0,506 | 0,741 |
| milho 2ª | 41 | 138,5 | 0,177 | 0,429 | 1,171 |

## Erro tipo I (α = 5%, 5.000 réplicas)

| cultura | CR1 | CR2 | WCR | WCU | WCR-Webb |
|---|---:|---:|---:|---:|---:|
| soja | 7,54% | 7,54% | **5,40%** | 5,88% | 5,38% |
| milho | 7,86% | 7,86% | **5,26%** | 5,88% | 5,56% |
| milho 2ª | 9,98% | 9,98% | **5,96%** | 6,90% | 6,20% |

MC SE 0,32–0,42 pp. Intervalos de Wilson em `bootstrap_calibration.json`.

**CR2 ≡ CR1** neste desenho: com um regressor, `K2 = 1` e `(n−1)/(n−K2) = 1`.

## Cobertura do IC 95%

| cultura | CR1 | WCR |
|---|---:|---:|
| soja | 92,5% | **94,3%** |
| milho | 92,1% | **94,5%** |
| milho 2ª | 90,0% | **93,8%** |

## Poder no MDE

CR1 67–71%; WCR 60–65%. O teste calibrado é menos potente — a comparação
anterior estava otimista.

## Aplicação (18 estimandos, B = 9.999)

7 associações sustentadas sob WCR, 2 inconclusivas, 9 nulas confirmadas.
**Nenhum resultado inverteu de lado.**

## Defeito de biblioteca documentado (D129)

`robust.wild_cluster_bootstrap_fast` ignora `null_imposed` quando o desenho tem
uma única coluna — o caso de todos os modelos do SADEN. O WCR correto está em
`tools/analysis/fast_bootstrap.py` (CR1 validado a 12 casas decimais contra a
biblioteca). `null_policy="auto"` não deve ser usado: escolhe o p-valor pelo
resultado.
