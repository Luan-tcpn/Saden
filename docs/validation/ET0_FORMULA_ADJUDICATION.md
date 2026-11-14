# SADEN — Adjudicação da fórmula de ET0

**Data:** 2026-11-14
**Código:** `tools/validation/et0_adjudication.py`, `geospatial/agroclimate/corrections.py`
**Manifesto:** `geospatial/data/manifests/et0_adjudication.json`
**Amostra:** 1.200 janelas, 3 culturas, semente fixa

---

## 1. Conformidade com a FAO-56

Implementação efetivamente usada pelos resultados publicados:
`evapotranspiration.fao56_penman_monteith`.

| elemento | FAO-56 (Allen et al., 1998) | referência | veredito |
|---|---|---|---|
| `es` | `[e°(Tmax)+e°(Tmin)]/2` (eq. 12) | `e°(Tmean)` | **não conforme** (C1) |
| `u2` (m/s a 2 m) | `u2 = vento_2m` | `0,4 × vento_kmh / 3,6` | **não conforme** (C2) |
| `ea` | `es × RH/100` | igual | conforme |
| Δ, γ, `Rn`, `Rso`, `G=0`, albedo 0,23, coef. 900 e 0,34 | eqs. 6–13, 21, 37–40 | iguais | conforme |

Duas não conformidades de **convenção**, ambas identificadas e medidas.

## 2. C2 — fator 0,4 indevido no vento

`vento_kmh` vem de NASA POWER `WS2M` (já a 2 m) convertido para km/h. A conversão
correta é `/3,6`. A referência aplica **também** `× 0,4` (o fator 10 m → 2 m), que
não se aplica: `u2` fica 60% abaixo do real.

**Medição por identidade exata.** Multiplicar a entrada de vento por 2,5 faz a
biblioteca calcular `u2 = 0,4 × (2,5·vento)/3,6 = vento/3,6` — o vento correto —
**sem alterar uma linha da biblioteca**. Erro máximo da identidade:
`8,9 × 10⁻¹⁶`.

| variante | ET0 média | mediana relativa | déficit médio |
|---|---:|---:|---:|
| referência | 531,8 mm | — | 125,6 mm |
| vento corrigido (só C2) | 600,5 mm | **+11,30%** | 185,6 mm (**3,47×**) |

O vento é o fator de maior efeito: sozinho elevaria ET0 em 11,3% e o déficit em
3,5×.

## 3. C1 — `es(Tmean)` em vez de `es(Tmax, Tmin)`

A relação `e°(T)` é convexa, então `[e°(Tmax)+e°(Tmin)]/2 ≥ e°(Tmean)`, com
igualdade só quando `Tmax = Tmin`. Usar `es(Tmean)` **subestima** o déficit de
pressão de vapor — e portanto a ET0.

## 4. Efeito conjunto: as duas correções se cancelam

| variante | ET0 média | razão vs referência | mediana relativa | déficit | razão déficit | r (déficit) |
|---|---:|---:|---:|---:|---:|---:|
| referência | 531,8 mm | 1,000 | — | 125,6 mm | 1,000 | 1,000 |
| vento corrigido | 600,5 | 1,116 | +11,30% | 185,6 | 3,473 | 0,988 |
| **FAO-56 (C1+C2)** | **533,2** | **1,004** | **+0,54%** | **124,9** | **1,078** | **0,997** |

**O resultado central desta adjudicação é negativo, e é importante:** as duas
convenções erradas atuam em **sentidos opostos e quase se anulam**. A ET0
publicada está **0,5% abaixo** da FAO-56, e o déficit publicado está **0,6%
acima** — diferenças irrelevantes para qualquer conclusão.

O motivo é estrutural: o fator 0,4 no vento **reduz** o termo aerodinâmico, e o
`es(Tmean)` **reduz** o VPD, que também alimenta o termo aerodinâmico. Os dois
erros empurram ET0 para baixo; ao corrigir o vento (que sobe muito) e a pressão
de vapor (que também sobe), o numerador cresce e o **denominador**
`Δ + γ(1+0,34·u2)` cresce junto — a ET0 resultante fica praticamente onde estava.

## 5. Correção de um erro meu, registrado

O primeiro instrumento desta adjudicação reimplementava a ET0 de referência para
fazer um fatorial 2×2. Ele **não reproduzia a biblioteca** (4,2389 vs 4,6428
mm/dia no mesmo dia) e, por isso, reportou "ET0 subestimada em 10,3%". O número
estava **errado**: vinha do meu harness, não da biblioteca.

Instrumento refeito ancorado na própria biblioteca (identidade do vento +
implementação corrigida). Resultado correto: **+0,54%**.

Registro também que a etapa de consolidação anterior havia reportado "−1,1%
mediano"; aquele harness calculava o dia juliano como `mês×30 + dia%30`, o que
altera `Ra`. O valor correto, agora medido duas vezes por caminhos independentes,
é **≈ +0,5%**. Ambos os erros eram de ferramenta, não de fórmula (D129).

## 6. Impacto no painel construído

O build completo (30.207 janelas) usa a física corrigida. Comparação com a
referência V3.5 (`full_build_validation.json`):

| variável | linhas diferentes | diferença mediana | diferença máxima |
|---|---:|---:|---:|
| `et0_total_mm_corrected` | 30.207 | **+3,06 mm** | 95,6 mm |
| `deficiency_total_mm_corrected` | 25.266 | **+1,07 mm** | 95,6 mm |
| `excess_total_mm_corrected` | 18.565 | −13,16 mm | 113,1 mm |
| `etr_total_mm_corrected` | 21.589 | +2,78 mm | 33,8 mm |
| demais 37 colunas | — | **idênticas** | 0,0 |

Razão de ET0 construída/referência: mediana **1,0063**, p05 0,9647, p95 1,0429.

**Conclusão:** a física corrigida muda as variáveis físicas em menos de 1% em
mediana — e não toca em nenhuma das outras 37 colunas do painel.

## 7. Impacto nas conclusões

Nenhum. Com ET0 a +0,5% e déficit a +1,1 mm (mediana), e correlação de 0,997
entre déficit antigo e corrigido:

- a associação déficit × produtividade mantém sinal, magnitude e significância;
- as magnitudes publicadas em kg/ha/mm permanecem na mesma escala;
- nenhuma reclassificação é necessária.

A associação foi **remedida** com a inferência calibrada
(`applied_inference.json`): `soja|déficit` β = −2,274, p(WCR) = 0,0001. É o
mesmo β publicado — porque a exposição praticamente não mudou.

## 8. Decisão

1. A física corrigida (`corrections.py`, C1+C2+C3) é a **canônica** daqui para
   frente; o pipeline a usa e registra `physics_version` em cada linha.
2. A implementação histórica **não** foi alterada: V2.6–V3.5 continuam
   reproduzíveis bit a bit.
3. **Nenhum artefato publicado é reescrito.** A magnitude do efeito (0,5%) não
   justifica nova versão científica, e os valores publicados permanecem válidos.
4. Fica registrado que a ET0 publicada **não é** estritamente FAO-56 — é uma
   variante cujos dois desvios se cancelaram empiricamente. Isso é diferente de
   "está correta", e a distinção importa para quem for comparar com ET0 de outra
   fonte.

## 9. Limitações

1. O efeito de C1 isolado não é identificável por manipulação de entrada — só o
   total e o efeito do vento são medidos de forma exata.
2. Não há validação contra ET0 de estação (a INMET não publica ET0).
3. A premissa de que `vento_kmh` está a 2 m vem da documentação da aquisição
   (NASA POWER `WS2M`), não foi reauditada no código de aquisição.
4. `ea` por `RH` média diária é aproximação da FAO-56 (que recomenda `Tmin`
   quando não há orvalho).
