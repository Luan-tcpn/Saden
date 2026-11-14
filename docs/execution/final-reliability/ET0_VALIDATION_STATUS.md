# Fechamento — estado da validação da ET0

**Data:** 2026-11-14 · Detalhe: `docs/validation/ET0_FORMULA_ADJUDICATION.md`

## Conformidade

| elemento | FAO-56 | referência | veredito |
|---|---|---|---|
| `es` | `[e°(Tmax)+e°(Tmin)]/2` | `e°(Tmean)` | não conforme (C1) |
| `u2` | vento a 2 m em m/s | `0,4 × vento_kmh / 3,6` | não conforme (C2) |
| demais (Δ, γ, Rn, Rso, G, albedo, coeficientes) | — | iguais | conformes |

## Efeito medido (1.200 janelas)

| variante | ET0 | mediana relativa | déficit |
|---|---:|---:|---:|
| referência | 531,8 mm | — | 125,6 mm |
| só vento corrigido | 600,5 mm | **+11,30%** | 185,6 mm |
| **FAO-56 (C1+C2)** | **533,2 mm** | **+0,54%** | **124,9 mm** |

**As duas não conformidades se cancelam.** ET0 publicada = 0,5% abaixo da FAO-56;
déficit = 0,6% acima. Correlação entre déficit antigo e corrigido: **0,997**.

## Erros de ferramenta corrigidos aqui

1. O primeiro instrumento desta adjudicação **reimplementava** a referência e não
   reproduzia a biblioteca (4,2389 vs 4,6428 mm/dia), gerando a alegação falsa de
   "ET0 10,3% subestimada". Instrumento refeito ancorado na biblioteca.
2. O harness da etapa anterior calculava o dia juliano como `mês×30 + dia%30`,
   contaminando a comparação. Corrigido; o valor correto (≈ +0,5%) coincide por
   dois caminhos independentes.

## Decisão

Física corrigida é canônica (D130); implementação histórica intacta; **nenhum
artefato publicado reescrito**, porque o efeito (0,5%) não justifica nova versão
científica e as magnitudes publicadas permanecem válidas.

## Aberto

- efeito de C1 isolado não identificável por manipulação de entrada;
- sem validação contra ET0 de estação (INMET não publica ET0);
- `ea` por RH diária é aproximação da FAO-56.
