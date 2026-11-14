# SADEN — Poder estatístico e efeito mínimo detectável

**Data:** 2026-11-14
**Código:** `tools/analysis/statistical_power.py`
**Manifesto:** `geospatial/data/manifests/statistical_power.json`

---

## 1. Método

O MDE foi calculado **sobre o erro-padrão agrupado realmente estimado**, não
sobre o número de linhas. Estimador dos relatórios V2.7–V3.5: transformação
*within* (município e ano) com erro CR1 agrupado em **UF × ano** (D104/D111).

`MDE(p) = (t_{1−α/2, df} + t_{p, df}) × SE(β)`, com `df = G − 1` e `G` = número
de clusters UF × ano.

O N bruto **não** foi usado como independência em nenhum ponto. O desenho real:

| cultura | linhas | municípios | anos | clusters UF×ano | obs/cluster |
|---|---:|---:|---:|---:|---:|
| soja | 12.517 | 1.732 | 8 | **48** | 260,8 |
| milho | 12.013 | 1.645 | 8 | **56** | 214,5 |
| milho 2ª | 5.677 | 1.071 | 9 | **41** | 138,5 |

## 2. MDE em unidade interpretável (kg/ha por unidade da exposição)

| exposição | soja | milho | milho 2ª | unidade |
|---|---:|---:|---:|---|
| déficit hídrico | **1,14** | **2,11** | **3,36** | kg/ha por mm |
| precipitação acumulada | **0,60** | **1,50** | **3,21** | kg/ha por mm |
| ET0 acumulada | **1,33** | **2,62** | **3,71** | kg/ha por mm |
| graus-dia | **0,49** | **1,03** | **0,92** | kg/ha por °C·dia |
| dias de calor extremo | **12,02** | **17,30** | **22,25** | kg/ha por dia |
| temperatura média | **202,8** | **303,1** | **433,5** | kg/ha por °C |

MDE a 90% está no manifesto (cerca de 16% acima do MDE a 80%).

## 3. O teste é liberal com este número de clusters

Monte Carlo de 400 réplicas por cultura, com a estrutura de dependência
observada (componente de cluster + idiossincrático, ICC 0,18–0,28):

| cultura | erro tipo I observado (α = 5%) | poder no MDE 80% |
|---|---:|---:|
| soja | **7,8%** | 88,3% |
| milho | **6,0%** | 91,5% |
| milho 2ª | **10,3%** | 94,0% |

**O erro tipo I nominal de 5% não é atingido.** Com 41–56 clusters, a correção
CR1 é conhecida por rejeitar em excesso. Consequência: os p-valores publicados
são **anti-conservadores** em algum grau. Um p-valor de 0,03 não equivale a 5%
de evidência falsa; equivale a algo mais próximo de 8–10%. A ordem de grandeza
das conclusões não muda (os efeitos que sobreviveram o fizeram com margem), mas
a calibração está errada — D125.

## 4. O que o desenho **não** consegue ver

Comparar o MDE com a magnitude dos efeitos plausíveis separa três situações:

| exposição | β observado | MDE 80% | leitura |
|---|---:|---:|---|
| déficit × soja | −2,27 kg/ha/mm | 1,14 | **bem identificado**: efeito 2× o MDE |
| déficit × milho | −1,79 | 2,11 | no limite: efeito 0,85× o MDE |
| déficit × milho 2ª | −1,30 | 3,36 | **pouco identificado** |
| precipitação × soja | +0,89 | 0,60 | identificado |
| temperatura × soja | −262 | **203** | **não identificável** |
| temperatura × milho 2ª | −86 | **433** | **não identificável** |
| graus-dia × soja | +0,11 | 0,49 | inconclusivo |

**Resultado central:** a variação *within* de temperatura média é pequena
demais, em relação ao ruído, para este desenho. Um efeito de 50 kg/ha por °C —
agronomicamente grande — está dentro do intervalo de confiança de zero. Logo:

> os resultados nulos de temperatura e graus-dia **não são evidência de
> ausência de efeito**; são **inconclusivos por poder**. Já os nulos de
> precipitação/ET0 em milho 2ª são limites razoavelmente informativos.

## 5. Cenários de desenho: onde investir

`Var(β) ∝ σ²/(K·m) × [1 + (m−1)·ρ]`, com `K` clusters, `m` observações por
cluster e `ρ` = ICC observado. Fator aplicado ao erro-padrão atual:

| cenário | soja | milho | milho 2ª |
|---|---:|---:|---:|
| estado atual | 1,000 | 1,000 | 1,000 |
| **dobrar municípios** | **0,998** | **0,996** | **0,992** |
| **quintuplicar municípios** | **0,996** | **0,993** | **0,987** |
| anos 9 → 15 | **0,775** | 0,776 | 0,776 |
| UFs 7 → 10 | 0,840 | **0,837** | 0,841 |
| municípios ×2 + anos 15 | 0,773 | 0,773 | 0,770 |

**Este é o resultado mais importante da análise.** Os clusters já têm 139–261
municípios cada. Com ICC de 0,18–0,28, acrescentar municípios **dentro das UFs
atuais reduz o erro-padrão em menos de 1%** — é dinheiro quase perdido, e é
exatamente o que a expansão de cobertura feita até aqui vinha fazendo.

O que reduz erro é acrescentar **clusters**: mais anos (22%) ou mais UFs (16%).
A expansão para MG, na forma planejada (D119), acrescenta **clusters novos** —
é a única dimensão que ainda compra precisão para as hipóteses de exposição
UF×ano.

## 6. Reclassificação exigida pelo §9.8

Não se reclassifica resultado retrospectivamente só pelo MDE. O protocolo
original de cada versão continua valendo. O que muda é a **leitura das
ausências**:

| resultado anterior | leitura correta à luz do poder |
|---|---|
| V3.2: inclinações heterogêneas por UF não demonstradas | **inconclusivo por poder** — 48 clusters, heterogeneidade de inclinação consome muitos graus de liberdade |
| V3.3: bloco hídrico sem ganho preditivo | **inconclusivo** para modelos maiores; os limites são largos |
| V3.4: contraste regional não identificado | **não identificação** (Cramér's V = 1,000) — não é falta de poder, é falta de variação |
| V3.5: contraste dentro de SP nulo (p = 0,77) | **inconclusivo por poder** — SP é um único estado, poucos clusters |
| temperatura/graus-dia nulos | **inconclusivo por poder**, com MDE proibitivo |
| déficit × soja significativo | **evidência de associação**, não causal, e com p-valor liberal (§3) |

## 7. Limitações

1. O MDE depende do erro-padrão **de um modelo específico** (uma exposição por
   vez). Modelos multivariados têm MDE diferente.
2. O Monte Carlo simula ruído gaussiano; a cauda real da produtividade pode ser
   mais pesada, o que aumentaria ainda mais o erro tipo I.
3. `df = G − 1` é a aproximação usual; com G pequeno, a distribuição exata é
   incerta.
4. Os cenários de desenho usam a fórmula de efeito de desenho com ICC constante;
   clusters desiguais alteram o resultado na segunda casa.
5. Não se avaliou poder para **previsão** (diferença de erro fora da amostra),
   apenas para **associação**. Previsão tem outra métrica de poder.
