# V3.2 — PRÉ-REGISTRO

**Escrito antes de qualquer estimativa de heterogeneidade.**
Commit de referência: `345b22e` (V3.1). Data: 2026-11-14.

Este documento fixa hipóteses, estimandos, especificações, métricas,
procedimentos de inferência, correção de multiplicidade e regras de decisão. Ele
não pode ser alterado depois de ver os resultados: qualquer desvio será
registrado como desvio, com a razão, e o resultado original permanece relatado.

---

## 1. Pergunta científica

A sensibilidade da produtividade às variáveis agroclimáticas difere o
suficiente entre UFs para justificar inclinações específicas por estado — e essa
diferença melhora a generalização fora da amostra?

Três fenômenos que **não** serão confundidos:

1. diferença de produtividade **média** entre UFs (intercepto estadual);
2. diferença de **distribuição** das variáveis climáticas entre UFs (suporte);
3. diferença de **inclinação** da relação clima–produtividade (o alvo).

A V3.1 já mostrou (D101) que o modelo climático é melhor que a média da UF em PR
e pior em MS/MT/RS. Isso é uma diferença de **desempenho preditivo por UF**, não
uma estimativa de inclinação. A V3.2 estima a inclinação.

## 2. Hipóteses

| id | hipótese | teste |
|---|---|---|
| H0 | as inclinações climáticas são comuns entre UFs, controlados interceptos de município e ano | teste de Wald global sobre as interações |
| H1 | ao menos uma inclinação climática difere entre UFs | idem |
| H2 | permitir inclinações heterogêneas melhora a generalização fora da amostra (TE) | diferença pareada de MAE, bootstrap de bloco |
| H3 | a heterogeneidade é específica de cultura/variável, não um padrão único | comparação entre as 6 famílias confirmatórias |

Um resultado nulo é resultado válido e será relatado como tal.

## 3. Dados e especificação primária

* Base: `geospatial/data/processed/v31_panel_windows.csv` — **somente** colunas
  `_corrected` (D100). Nenhuma variável `_legacy` entra em nenhum modelo.
* Culturas: soja, milho, milho 2ª safra (separadas, nunca agrupadas).
* Variável dependente: `yield_kg_ha` (PAM/IBGE).
* Preditores primários (a especificação climática já estabelecida na V3.1):
  `precip_acumulada_mm_corrected`, `temp_media_c_corrected`.
* Preditores secundários/exploratórios: `degree_days_total_corrected`,
  `extreme_heat_days_corrected`, `deficiency_cad_0_100` (déficit com CAD
  oficial). Classificados como **exploratórios**, não confirmatórios.
* UFs por cultura: as efetivamente presentes no painel (soja 5, milho 6,
  milho 2ª 4). Nenhuma UF será criada ou imputada.

## 4. Estimandos

### 4.1. Associação (inferência)

Modelo *within* de dois fatores (município e ano), o mesmo estimador usado na
V2.9/V3.0 para associação (`spatial_inference.within_transform` +
`robust.cluster_vcov`, CR1 agrupado por bloco espacial):

```
y_w = b · x_w + Σ_s b_s · (x · 1[UF = s])_w + e
```

`b` é a inclinação de referência (UF de referência = primeira em ordem
alfabética) e `b_s` é a **diferença de inclinação** da UF `s` em relação a ela.
Não é um coeficiente de produtividade; é kg/ha por unidade da variável
climática, líquido de município e ano.

### 4.2. Predição (generalização)

Erro absoluto médio (MAE, kg/ha) no braço **TE** do fatorial espaço × tempo,
com equalização estrita por célula, nas mesmas células e mesmas linhas para
todos os modelos. `ΔMAE = MAE(modelo) − MAE(referência)`; **negativo = modelo
melhor**. Unidade: kg/ha de erro absoluto. Não é efeito sobre produtividade.

## 5. Modelos comparados

| rótulo | definição | papel |
|---|---|---|
| M0 | média nacional | baseline |
| M1 | média da UF (treino) | baseline principal |
| M1b | média UF×ano (treino) | diagnóstico contemporâneo, não operacional |
| M1c | vizinhos históricos (V3.1) | baseline secundário |
| M2 | precipitação + temperatura corrigidas + dummies de UF | referência |
| M2-HET-FE | M2 + interações entre UF e os dois preditores | inclinações estaduais livres |
| M2-HET-PP | M2 + as mesmas interações, penalizadas por ridge em direção a zero (partial pooling) | alternativa regularizada |

`M2` tem de reproduzir a V3.1 exatamente; caso contrário, o desenho não é
comparável e a diferença será investigada antes de qualquer conclusão.

### 5.1. Partial pooling — definição operacional

Com 4–6 UFs não é possível estimar de forma confiável a variância de uma
distribuição de efeitos aleatórios. A implementação é, portanto, **ridge sobre
os desvios estaduais**, que é o estimador MAP de um prior normal centrado em
zero para `b_s`. O parâmetro de encolhimento é escolhido por validação interna
**5-fold bloqueada por bloco espacial dentro do pool de treino da célula**,
nunca no teste. A limitação (não é um modelo hierárquico completo, não há
estimativa REML da variância entre UFs) será declarada no relatório.

Grade de encolhimento: λ ∈ {0, 1, 10, 100, 1000} em unidades de variância
padronizada do preditor no treino (λ=0 = FE/MQO; λ→∞ = inclinação comum).

## 6. Protocolos de validação

1. **TE** (principal): blocos espaciais e grupos temporais do teste fora do
   treino. 5 × 5 dobras, mesmas células da V3.1, equalização estrita por célula,
   3 repetições, semente `20261114`.
2. **Territorial** (SE): outros blocos, tempo compartilhado.
3. **Temporal** (TS): outros anos, espaço compartilhado.
4. **Espacial por bloco** (SS − SE): contraste de efeito do espaço.

`SS` fica como referência interna. Nenhum ganho em SS, SE ou TS será usado como
alegação de generalização — só TE (D91).

## 7. Inferência

* Inclinações: CR1 agrupado por **bloco espacial** (unidade de dependência
  territorial); referência `t` com `G − 1` graus de liberdade para contrastes
  individuais.
* Teste global: Wald `b' V⁻¹ b` sobre o bloco de interações, convertido em
  `F = Wald / q` com `F(q, G − 1)`, usando a VCV cluster-robusta CR1.
* O número de UFs (4–6) é pequeno: a aproximação assintótica é frágil e os
  p-valores estaduais serão tratados como **descritivos**, não confirmatórios.
  O teste global também é reportado com a ressalva de que `G` é o número de
  blocos, não de UFs.
* Sempre que possível, o IC do teste global será confrontado com um
  **wild cluster bootstrap** por bloco, método já calibrado na V2.7.

## 8. Multiplicidade

| família | tamanho | procedimento |
|---|---|---|
| confirmatória: teste global de heterogeneidade | **6** (3 culturas × 2 variáveis primárias) | Holm, α = 0,05 |
| secundária: contrastes por UF | (n_UF − 1) × 2 por cultura = 8 / 10 / 6 | Holm dentro de cada cultura; reportado como descritivo |
| exploratória: variáveis adicionais (graus-dia, calor, déficit) | 3 culturas × 3 variáveis | FDR (Benjamini–Hochberg), rotulado como exploratório |

Uma tabela de coeficientes estaduais com p-valores individuais **não** é
evidência de heterogeneidade. O teste global vem primeiro; os contrastes
estaduais só são interpretados depois dele.

## 9. Regra de decisão pré-registrada (níveis A–D)

* **Nível A — heterogeneidade sustentada e útil**: teste global significativo
  após Holm **e** ganho pareado em TE com IC95% excluindo zero **e** o sinal do
  ganho sobrevive a *leave-one-UF-out* em todas as UFs removidas (o ganho não
  pode depender de uma única UF).
* **Nível B — heterogeneidade estatística sem ganho preditivo**: teste global
  significativo, mas IC do ΔMAE em TE inclui zero.
* **Nível C — ganho localizado ou instável**: ΔMAE agregado não significativo,
  mas com sinal consistente em algumas UFs, ou dependente do protocolo/λ.
* **Nível D — evidência insuficiente**: teste global não significativo, ou
  amplitudes de IC grandes, ou identificabilidade insuficiente.

**Nenhum ajuste de especificação será feito depois de ver o resultado para
promover um nível.** Se o resultado for D, a conclusão é D.

## 10. Robustez pré-especificada

1. λ ∈ grade (sensibilidade ao encolhimento), reportando o caminho completo.
2. Déficit com CAD 0–100 no lugar de precipitação (cenário físico documentado,
   D99), como verificação de que a conclusão não depende da variável hídrica.
3. Leave-one-UF-out no ΔMAE de TE.
4. Leave-one-year-out no ΔMAE de TE.
5. Exclusão de BA (n = 106) no milho.
6. Comparação com M1c nos mesmos casos, com decomposição
   vizinhos × fallback (a V3.1 não fez a comparação pareada).

## 11. O que não será feito

* Não reintroduzir tendência espacial (lat/lon) — D102.
* Não usar CAD bruta como preditor — D98.
* Não usar variáveis `_legacy`.
* Não escolher λ, variável ou subamostra pelo resultado em TE.
* Não apresentar correlação como causalidade.
* Não generalizar para o Brasil: a cobertura é de 5–6 UFs de 27.
