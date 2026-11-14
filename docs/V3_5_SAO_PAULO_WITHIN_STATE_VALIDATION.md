# SADEN V3.5 — Validação dentro de São Paulo

**A pergunta:** a diferença entre MRS 1 e MRS 3 sobrevive quando as duas estão no
mesmo estado?

**A resposta:** **não.** No teste primário (soja), D = **+7,3 kg/ha**, IC de ano
[−18,8; 26,9], e a interação associativa tem p = 0,77. O sinal inverte entre
anos. O contraste Sul×Cerrado da V3.4 (−78,3 no milho) **não se reproduz dentro
de SP**.

---

## 1. Por que SP importa

Na V3.4, a classificação regional era **perfeitamente determinada pela UF**
(Cramér's V = 1,000; nenhuma UF com municípios nos dois grupos), o que tornava o
contraste Sul×Cerrado não identificável como efeito regional (D113).

SP é a única UF ausente com municípios em **MRS 1 e MRS 3**:

| grupo | macrorregião | municípios | RE |
|---|---|---:|---|
| MRS 1 | Sul | **44** | 103 (Itapeva/Itararé) |
| MRS 2 | transição | 431 | 201, 202, 203 |
| MRS 3 | Cerrado | **168** | 302 (oeste paulista) |

Isso quebra o confundimento **para esta comparação**. Não quebra os demais
confundidores (municipal, climático, de composição).

## 2. Cobertura efetiva em SP

| etapa | municípios |
|---|---:|
| com geometria IBGE | 645 |
| com classificação MRS | 643 |
| com painel utilizável (`paired_usable`) | 582 |

Linhas utilizáveis por cultura e grupo:

| cultura | MRS 1 | MRS 2 | MRS 3 |
|---|---:|---:|---:|
| soja | 178 | 2.272 | 1.173 |
| milho | 296 | 2.785 | 1.305 |
| milho 2ª | 180 | 1.776 | 809 |

MRS 1 é pequena: 178 linhas de soja em ~9 anos, ~20 municípios com série. É o
lado frágil do desenho.

## 3. Teste primário — soja

ΔMAE por grupo (negativo = bloco hídrico melhor), kg/ha:

| grupo | n | MAE M2 | Δ |
|---|---:|---:|---:|
| **MRS 1** | 178 | — | **+2,5** |
| MRS 2 | 2.272 | — | +16,4 |
| **MRS 3** | 1.173 | — | **−4,8** |

**D = Δ_MRS1 − Δ_MRS3 = +7,3 kg/ha.**

| IC | faixa | p |
|---|---|---:|
| por ano (9 unidades) | [−18,8; +26,9] | 0,539 |
| por município | [−9,8; +23,6] | — |

**Interação associativa** (bloco hídrico × MRS 1, *within* de município e ano,
agrupamento duplo ano × município): coeficiente **+54,0 kg/ha por 100 mm**,
p = **0,770**, G = 7 anos.

Conclusão: nenhuma diferença material, e o IC é estreito o suficiente para
**descartar** um efeito da ordem do contraste entre estados (−78,3). Não é
"inconclusivo por poder" no que importa: o intervalo não contém efeitos grandes.

## 4. Culturas secundárias (exploratórias)

A MRS deriva do zoneamento **sojícola**; para milho e milho 2ª os resultados são
**estratificação geográfica exploratória**, não evidência de zonas de milho
(D112).

| cultura | Δ MRS 1 | Δ MRS 3 | D | IC ano | p |
|---|---:|---:|---:|---|---:|
| milho | +1,5 | +20,1 | −18,6 | [−51,2; 7,4] | 0,191 |
| milho 2ª | −34,5 | −5,7 | −28,8 | [−71,5; 8,3] | 0,184 |

Nenhum significativo. O milho 2ª tem sinal favorável a MRS 1, mas G = 4 anos no
teste de interação — precisão insuficiente para qualquer conclusão.

## 5. Robustez

**Leave-one-year-out** (D por ano excluído):

| cultura | faixa de D | sinal estável? |
|---|---|---|
| soja (primária) | −17,8 a **+13,2** | **não — inverte** |
| milho | −42,3 a −12,3 | sim, mas sempre n.s. |
| milho 2ª | −92,0 a −36,7 | sim, mas sempre n.s. |

**Grupos alternativos** dentro de SP (D por ano):

| cultura | MRS 1 × MRS 2 | MRS 2 × MRS 3 |
|---|---:|---:|
| soja | +1,1 | +9,0 |
| milho | −8,9 | −8,7 |
| milho 2ª | −21,2 | +24,4 |

Não há gradiente monotônico MRS 1 → 2 → 3 em nenhuma cultura. Se a MRS
organizasse o efeito, esperar-se-ia ordenação; não há.

## 6. O que permanece identificável

* **Inclinações** por grupo: identificadas (a interação vem da co-movimentação
  temporal dentro do município), mas com **7 anos** de exposição — precisão
  baixa.
* **Nível** por grupo: **não** identificado — efeitos fixos de município o
  absorvem. Não se testa "MRS 1 tem produtividade diferente".

## 7. Leitura

O padrão da V3.4 (Sul a favor, Cerrado contra) era **descritivo entre grupos de
estados**. A primeira oportunidade real de testá-lo dentro de um estado mostra
que ele **não aparece**. Isso é consistente com D114 (a fronteira não organiza o
fenômeno) e reforça que a heterogeneidade observada em 2025 é de **estado**, não
de região agronômica.

Não se está dizendo que a água não importa em SP. Está-se dizendo que **importa
de forma semelhante em MRS 1 e MRS 3**.

## 8. Limitações

1. **MRS 1 tem 178 linhas de soja** (~20 municípios) — o braço pequeno limita o
   poder para efeitos menores que ~20 kg/ha.
2. **7 anos** de exposição no teste associativo; `G` = 7 é pouco.
3. **MRS é classificação de soja**; milho é exploração, não confirmação.
4. **Desenho escolhido após a V3.4** (ver pré-registro §0): teste prospectivo em
   dados novos, não pré-registro genuíno.
5. **Suporte climático difere entre os grupos** (MRS 1 é mais frio e chuvoso);
   isso não invalida o teste, mas impede generalizar para "regiões" em geral.

## 9. Classificação

**Nível D — hipótese não sustentada dentro de SP**, para a cultura primária
(soja). O IC descarta efeitos grandes; o sinal é instável entre anos.

Para milho e milho 2ª: **exploratório**, sem conclusão.
