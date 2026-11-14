# V3.3 — PRÉ-REGISTRO DA FORMA FUNCIONAL

**Escrito antes de qualquer estimativa de modelo da Frente A.**
Base: `3bf9360` (V3.2). Data: 2026-11-14.

Este documento fixa variáveis, formas funcionais, modelos, família confirmatória,
regra de decisão e robustez. Não pode ser alterado após ver os resultados; desvios
serão registrados como desvios.

---

## 1. Pergunta

O formato funcional usado para representar as condições agroclimáticas deixa de
capturar mecanismos relevantes — em particular o balanço hídrico e a exposição
térmica — e uma representação fisicamente coerente melhora a generalização?

Cultura primária: **milho**. Secundárias: soja e milho 2ª safra.

## 2. Origem do sinal (V3.2), verificada nos arquivos

A V3.2 reportou três rejeições exploratórias no milho após Benjamini–Hochberg
(`v32_slope_tests.json`, família de 9 testes, modelos de **uma** variável):

| variável (nome no código) | p | BH |
|---|---:|---:|
| `deficit_cad100` | 0,00024 | 0,0021 |
| `degree_days_corrected` | 0,00095 | 0,0043 |
| `heat_corrected` | 0,00608 | 0,0183 |

Os testes confirmatórios com precipitação e temperatura brutas **não** rejeitaram
(milho: precipitação 0,410; temperatura 0,045 → Holm 0,227). A V3.2 registrou que
essas três rejeições vinham de especificações de variável única e que a
colinearidade impedia identificar a variável responsável. É exatamente essa
lacuna que a V3.3 ataca.

## 3. Auditoria de dependência (medida antes de escolher a especificação)

`v33_variable_audit.json` — correlações *within* de município e ano, milho,
cenário CAD 0–60:

| par | r |
|---|---:|
| `etr_over_etp` × `deficit_over_etp` | **−1,000** |
| `deficit_total_mm` × `etr_over_etp` | −0,972 |
| `stress_share` × `max_consecutive_deficit_months` | +0,941 |
| `heat_corrected` × `deficit_total_mm` | +0,839 |
| `heat_corrected` × `temp_corrected` | +0,760 |
| `deficit_total_mm` × `stress_share` | +0,730 |
| `degree_days_corrected` × `deficit_total_mm` | +0,310 |
| `degree_days_corrected` × `temp_corrected` | +0,020 |

Consequências **obrigatórias** para o desenho:

1. `etr_over_etp` **é** `1 − deficit_over_etp` por construção (DEF = ETP − ETR).
   São a mesma variável com sinal trocado. Nunca entram juntas.
2. `deficit_total_mm` e `etr_over_etp` carregam 97% da mesma informação: a
   "intensidade relativa" é essencialmente o déficit reescalado. Escolher entre
   elas é escolher uma **escala**, não um mecanismo.
3. `stress_share` e `max_consecutive` são quase a mesma variável (0,94) porque as
   janelas têm 3–5 meses. **Duração e comprimento de evento não são separáveis
   nestes dados.** H3 fica registrada como **não testável** na resolução
   disponível, e não como hipótese "não confirmada".
4. `heat_corrected` é 0,84 com déficit e 0,76 com temperatura: com temperatura e
   déficit no modelo, o calor extremo é quase redundante. Ele entra apenas como
   **sensibilidade exploratória**, com essa colinearidade declarada.
5. `degree_days_corrected` é o único candidato térmico praticamente ortogonal
   (0,02 com temperatura, 0,31 com déficit). É o bloco térmico primário.
6. O conjunto completo tem número de condição ~5×10¹⁵ (singular). Um modelo com
   todas as variáveis é inviável e não será tentado.

## 4. Cenário físico

A profundidade radicular segue D99: **soja 0–100 cm**, **milho e milho 2ª
0–60 cm**. Cenários alternativos (CAD = 50 mm histórico; 0–200 cm) são
sensibilidade.

Motivo medido (`v33_water_variables.json`): com CAD 0–100 ou 0–200, **54% e 86%
das linhas não têm nenhum mês de estresse**. Nessas capacidades a duração do
estresse é degenerada (mediana 0) e não há variação para estimar. Com CAD 0–60 a
mediana é 1 mês de estresse e 35% das linhas não têm estresse — há variação.

## 5. Hipóteses

| id | hipótese | classificação |
|---|---|---|
| H1 | a representação do balanço hídrico acrescenta informação além de precipitação e temperatura brutas | **confirmatória** (milho) |
| H2 | a relação com o estresse hídrico não é linear na faixa observada | **confirmatória** (milho) |
| H3 | duração do estresse contém informação distinta do déficit acumulado | **não testável** — r = 0,73 com déficit e 0,94 com evento; a separação exigiria resolução sub-mensal que o balanço não tem |
| H4 | a exposição térmica acrescenta informação depois do bloco hídrico | **confirmatória** (milho) |
| H5 | o ganho aparece fora da amostra (TE) e não só no ajuste | avaliado pelas mesmas comparações de H1/H2/H4 |
| H6 | o ganho não depende de uma UF ou de um ano | **robustez obrigatória** |

H3 é declarada não testável **antes** dos resultados, com a razão medida. Não é
uma hipótese abandonada: é uma hipótese que o desenho de dados não identifica.

## 6. Variáveis

| bloco | variáveis | papel |
|---|---|---|
| referência (M2) | `precip_acumulada_mm_corrected`, `temp_media_c_corrected` | comparabilidade com V3.1/V3.2 |
| hídrico | `deficit_total_mm` (intensidade), `stress_share` (duração) | H1 |
| térmico | `degree_days_total_corrected` | H4 |
| não linear | `(deficit_total_mm/100)²`, transformação de **constante fixa** | H2 |
| exploratório | `heat_corrected`; interação `deficit × graus-dia` | sensibilidade, não confirmatório |

Todas as variáveis vêm da janela **corrigida**. Nenhuma `_legacy`.

## 7. Modelos

| rótulo | conteúdo |
|---|---|
| M1 | média da UF (treino) |
| M2 | precipitação + temperatura + dummies de UF |
| M2-WB | déficit + duração + dummies de UF (só o bloco hídrico) |
| **M2-WB+** | M2 **+** déficit + duração (incremental sobre o clima bruto) |
| M2-THERM | graus-dia + dummies de UF |
| M2-WB-THERM | déficit + duração + graus-dia + dummies de UF |
| M2-WB-NL | déficit + déficit² + duração + dummies de UF |
| M2-WB-THERM-INT | M2-WB-THERM + (déficit × graus-dia) — **exploratório** |

## 8. Estimando e protocolo

* **ΔMAE no braço TE**, em kg/ha; `Δ = MAE(modelo) − MAE(referência)`;
  **negativo = modelo melhor**. Não é efeito sobre produtividade.
* Mesmas células, mesma equalização por célula, mesma semente, **mesmas linhas de
  teste** em todos os modelos (verificado por `row_codes`/`row_years_raw`).
* 3 repetições, 1000 reamostragens.
* IC da diferença por bootstrap **duplo**: bloco espacial e UF×ano (D104).
* Todas as transformações usam constantes fixas (o `/100` do quadrático). Nenhuma
  padronização estimada nos dados → nenhum vazamento por transformação.

## 9. Família confirmatória (milho) e multiplicidade

Três comparações pareadas, todas contra o modelo que isola o mecanismo:

| # | comparação | hipótese |
|---|---|---|
| 1 | M2-WB+ vs M2 | H1 |
| 2 | M2-WB-THERM vs M2-WB+ | H4 |
| 3 | M2-WB-NL vs M2-WB+ | H2 |

Holm, α = 0,05, família de **3**. Soja e milho 2ª são **secundárias**: mesmas
comparações, reportadas separadamente, fora da família confirmatória.

## 10. Regra de decisão (níveis A–D)

* **Nível A — evidência robusta com ganho preditivo**: comparação confirmatória
  significativa após Holm **e** IC de UF×ano excluindo zero **e** sinal preservado
  em todas as exclusões de uma UF (leave-one-UF-out) **e** sinal preservado em
  todas as exclusões de um ano.
* **Nível B — associação sem ganho preditivo**: evidência inferencial (teste
  within com agrupamento adequado) significativa, mas ΔMAE em TE com IC incluindo
  zero.
* **Nível C — ganho localizado/instável**: ΔMAE agregado não significativo ou
  dependente de uma UF/ano, mesmo que o ponto estimado seja favorável.
* **Nível D — evidência insuficiente**: nenhuma das anteriores.

## 11. Robustez pré-especificada

1. Cenários de CAD: 0–60 (primário), 50 (histórico), 0–100, 0–200.
2. Forma alternativa de água: `etr_over_etp` no lugar de déficit (escala
   relativa, FAO-33), declarada como sensibilidade de escala.
3. `heat_corrected` no lugar de graus-dia (sensibilidade térmica).
4. Leave-one-UF-out e leave-one-year-out no ΔMAE.
5. Comparação em amostra comum quando qualquer variável reduzir n.

## 12. O que não será feito

* Não testar dezenas de limiares até achar significância (não há limiar livre no
  desenho; o quadrático usa constante fixa).
* Não escolher forma por p-valor.
* Não usar CAD bruta como preditor (D98).
* Não misturar `_legacy`.
* Não confundir ganho preditivo com causalidade.
* Não combinar água e temperatura numa única variável sintética.
