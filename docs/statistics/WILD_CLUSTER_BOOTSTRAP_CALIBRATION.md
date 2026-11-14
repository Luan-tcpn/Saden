# SADEN — Calibração da inferência (wild cluster bootstrap)

**Data:** 2026-11-14
**Código:** `tools/analysis/fast_bootstrap.py`, `tools/analysis/bootstrap_calibration.py`,
`tools/analysis/apply_calibrated_inference.py`
**Manifestos:** `bootstrap_calibration.json`, `applied_inference.json`

---

## 1. O problema

A etapa anterior mediu erro tipo I de 6% a 10% para nominal de 5% com CR1
agrupado em UF × ano (D125). Este é o fechamento: quatro procedimentos medidos no
**desenho real**, com 5.000 replicações e bootstrap de 999 replicações.

## 2. Estrutura preservada

Nada foi reduzido nem idealizado. Os parâmetros vêm do painel:

| cultura | G (UF×ano) | m médio | ICC do erro | ICC da exposição | EP CR1 real |
|---|---:|---:|---:|---:|---:|
| soja | 48 | 260,8 | 0,280 | 0,513 | 0,400 |
| milho | 56 | 214,5 | 0,220 | 0,506 | 0,741 |
| milho 2ª | 41 | 138,5 | 0,177 | 0,429 | 1,171 |

Duas correções de fidelidade foram necessárias e estão registradas:

1. **Escala do ruído casada por momento** — sem isso o EP simulado ficava 21–37%
   abaixo do real e o poder aparecia inflado. O fator aplicado é reportado
   (`noise_scale`: 1,27 / 1,29 / 1,58).
2. **ICC da exposição separado do ICC do erro** — a exposição climática é quase
   toda UF×ano (icc_x ≈ 0,43–0,51); usar o mesmo valor do erro subestimava a
   inflação do EP em ~2×.

## 3. Métodos comparados

| rótulo | definição |
|---|---|
| `cr1` | t com erro agrupado CR1 e `df = G − 1` |
| `cr2` | correção de Bell–McCaffrey |
| `wcr` | wild cluster bootstrap-t, **H0 imposta** (resíduos restritos), Rademacher por cluster, estatística studentizada, `p = (1+excedências)/(B+1)` |
| `wcu` | idem com resíduos irrestritos, estatística recentrada |
| `wcr_webb` | WCR com os seis pesos de Webb |

**CR2 não é um método distinto aqui.** Com um único regressor,
`K2 = tr(alavancagem agregada) = 1` e o fator `(n−1)/(n−K2)` vale 1 — CR2
degenera exatamente em CR1. Isso é demonstrado numericamente: as taxas de CR2
são idênticas às de CR1 em todas as configurações.

## 4. Erro tipo I a 5% (5.000 replicações)

| cultura | CR1 | CR2 | WCR | WCU | WCR-Webb |
|---|---:|---:|---:|---:|---:|
| soja | 7,54% | 7,54% | **5,40%** | 5,88% | 5,38% |
| milho | 7,86% | 7,86% | **5,26%** | 5,88% | 5,56% |
| milho 2ª | 9,98% | 9,98% | **5,96%** | 6,90% | 6,20% |

Erro-padrão Monte Carlo: 0,32–0,42 pontos percentuais.

Intervalos de Wilson 95% para a taxa:

| cultura | CR1 | WCR |
|---|---|---|
| soja | [6,84; 8,30] | **[4,81; 6,06]** |
| milho | [7,15; 8,64] | **[4,67; 5,91]** |
| milho 2ª | [9,18; 10,84] | **[5,34; 6,65]** |

**Critério de calibração:** o intervalo precisa conter o nível nominal.
- **CR1 reprovado** nos três (intervalo inteiro acima de 5%).
- **WCR aprovado** em soja e milho; em milho 2ª o limite inferior é 5,34% e o
  superior 6,65% — a taxa está levemente acima, mas o método reduz o erro pela
  metade (9,98% → 5,96%).
- **WCU reprovado** em milho 2ª ([6,23; 7,64]).
- **Webb** marginalmente reprovado em milho 2ª ([5,56; 6,90]) e aprovado nos
  outros dois.

Em α = 1% (soja): CR1 = 1,76% (76% acima do nominal) contra WCR = 0,98%.

## 5. Cobertura do intervalo de 95%

| cultura | CR1 | WCR |
|---|---:|---:|
| soja | 92,5% | **94,3%** |
| milho | 92,1% | **94,5%** |
| milho 2ª | 90,0% | **93,8%** |

Largura média: CR1 1,8–5,3 kg/ha; WCR 1,9–6,2 kg/ha (cerca de 10% mais largo).
Ou seja: o intervalo honesto é **mais largo** — o preço de corrigir a
anti-conservadoridade.

## 6. Poder

Na magnitude do MDE calculado na etapa anterior (α = 5%):

| cultura | MDE | CR1 | WCR |
|---|---:|---:|---:|
| soja | 1,14 kg/ha/mm | 67,8% | 63,8% |
| milho | 2,11 | 70,5% | 64,7% |
| milho 2ª | 3,36 | 67,4% | 59,7% |

O poder do WCR é 3–8 pontos menor. Isso é esperado: um teste com tamanho correto
é menos potente que um teste liberal. **A comparação anterior de poder estava
otimista** por usar CR1.

## 7. Defeito encontrado na biblioteca (D129)

`robust.wild_cluster_bootstrap_fast` declara `null_imposed=True`, mas a restrição
só é aplicada quando o desenho tem **outra coluna** além da testada:

```python
others = [i for i in range(X.shape[1]) if i != coef_index]
if null_imposed and others:      # ← com k = 1, `others` é vazio
```

Com um único regressor — o caso de **todos** os modelos do SADEN — a hipótese
nula era silenciosamente ignorada e o bootstrap usava resíduos irrestritos
(WCU), não o WCR que o nome promete.

**Não foi corrigido na biblioteca** para não alterar artefatos; a versão correta
está em `tools/analysis/fast_bootstrap.py`, com `cr1_fit` validado contra
`cluster_robust_fit` a **12 casas decimais**.

Também se documenta que `select_null_policy(..., "auto")` escolhe entre o p-valor
imposto e o irrestrito **com base no p observado** (troca para o irrestrito
quando o imposto não rejeita). Um p-valor cuja regra depende do resultado não tem
nível nominal coerente; por isso a calibração mede as duas variantes
separadamente e não usa `auto`.

## 8. Aplicação aos estimandos reais

`wcr` aplicado a **todos** os 18 estimandos, sem seleção (B = 9.999):

| estimando | β | p CR1 | p WCR | classificação |
|---|---:|---:|---:|---|
| soja \| déficit | −2,274 | <0,0001 | **0,0001** | sustentada |
| soja \| precipitação | +0,890 | 0,0001 | **0,0053** | sustentada |
| soja \| calor extremo | −12,11 | 0,0059 | **0,0121** | sustentada |
| soja \| temperatura | −262,1 | 0,0006 | **0,0011** | sustentada |
| milho \| déficit | −1,794 | 0,0188 | **0,0195** | sustentada |
| milho \| ET0 | −2,031 | 0,0313 | **0,0249** | sustentada |
| milho \| calor extremo | −12,91 | 0,0378 | **0,0389** | sustentada |
| soja \| ET0 | −0,936 | 0,0505 | 0,0447 | inconclusiva |
| milho \| temperatura | −210,3 | 0,0529 | 0,0529 | inconclusiva |
| milho \| graus-dia | −0,615 | 0,0951 | 0,1011 | nula confirmada |
| milho \| precipitação | +0,849 | 0,1120 | 0,1445 | nula confirmada |
| demais 7 | — | > 0,20 | > 0,20 | nula confirmada |

**Nenhuma conclusão inverteu.** Os sete resultados que rejeitavam sob CR1
continuam rejeitando sob WCR; os que não rejeitavam continuam não rejeitando. A
liberalidade do CR1 **não** produziu falso positivo em nenhum dos 18 estimandos
deste painel — o que é uma notícia, e não uma licença para voltar a usá-lo.

## 9. Recomendação

1. **Reportar WCR como padrão** e CR1 como referência histórica.
2. **Concluir apenas quando os dois concordarem**; quando divergirem, o WCR
   prevalece por ser o calibrado.
3. **α = 5% com WCR** é o nível utilizável; α = 1% exige mais clusters.
4. **Não usar `null_policy="auto"`** em nenhuma análise nova.
5. Para milho 2ª, com G = 41, declarar que a taxa observada (5,96%) ainda está
   acima do nominal.

## 10. Limitações

1. A calibração usa um DGP com heterocedasticidade homogênea e sem dependência
   espacial explícita; clusters reais podem ter correlação espacial residual.
2. `Conley HAC` foi considerado e **não implementado** — a exposição varia em
   UF×ano, e o WCR responde a essa dimensão; a sensibilidade espacial fica como
   pendência.
3. Um único regressor por modelo; modelos multivariados exigem nova calibração.
4. Não foi implementado bootstrap para agrupamento **bidimensional**
   (UF×ano e município): com efeitos fixos de município, a dimensão municipal é
   absorvida; a afirmação vale para esse estimador, não em geral.
