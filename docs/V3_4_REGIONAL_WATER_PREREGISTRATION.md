# V3.4 — PRÉ-REGISTRO DA HIPÓTESE REGIONAL

**Congelado em 2026-11-14, antes de qualquer estimativa do contraste regional.**
Base: `6eff88c` (V3.3). Classificação: `docs/V3_4_REGIONAL_CLASSIFICATION_PROTOCOL.md` (congelada antes deste documento).

---

## 0. Status de independência — declarado antes dos resultados

A hipótese nasceu de um padrão **exploratório** observado na V3.3, que usou
**todos os anos (2017/18–2025) e todos os municípios** do painel. Não existe,
portanto, amostra não examinada para o mesmo período e território.

Consequência, fixada agora:

* a V3.4 **não pode** produzir confirmação independente;
* a execução é classificada como **reanálise protocolada de um achado
  exploratório**;
* um p-valor pequeno aqui **não** é confirmação definitiva; é evidência
  condicional ao mesmo conjunto de dados que gerou a hipótese;
* qualquer alegação de confirmação exigiria período ou território externo, o que
  a V3.4 não possui.

Isso está registrado **antes** de ver o resultado do contraste.

## 1. Hipótese

**H1:** o efeito do bloco hídrico — no desempenho preditivo e/ou na inclinação
associativa — difere entre as regiões agronômicas **Sul** (MRS 1) e **Cerrado**
(MRS 3 ∪ MRS 4).

**H0:** não há diferença sistemática entre as duas regiões.

Teste **bilateral**: a direção (Sul favorecido) foi observada na V3.3, e um teste
unilateral usaria essa informação para aumentar artificialmente o poder.

## 2. Classificação (congelada, ver protocolo)

* **Sul** = MRS 1 → RS (todas) + PR nas RE 102/103.
* **Cerrado** = MRS 3 ∪ 4 → GO, MS (RE 301), MT, BA (RE 405).
* **Transição** = MRS 2 → **excluída** do contraste primário (reportada à parte).
* **Fora** = MRS 5 e municípios sem indicação de soja.

## 3. Estimandos

### 3.1. Primário preditivo (milho)

```
Δ_g = MAE(M2 + bloco hídrico | região g) − MAE(M2 | região g)
D   = Δ_Sul − Δ_Cerrado
```

* MAE em kg/ha, braço **TE**, mesma métrica da V3.3.
* Δ negativo = bloco hídrico reduz o erro; Δ positivo = aumenta.
* **D < 0** ⇒ bloco relativamente melhor no Sul; **D > 0** ⇒ relativamente melhor
  no Cerrado.
* Comparação **pareada**: cada linha é prevista uma vez por modelo, e o contraste
  usa os mesmos casos de teste nos dois modelos (verificado por `row_codes`).

### 3.2. Primário associativo (milho)

Modelo *within* de município e ano:

```
y_w = b·x_w + c·(x · 1[Sul])_w + e
```

`x` = déficit acumulado (cenário CAD 0–60), o mesmo bloco da V3.3. O **teste
primário** é H0: `c = 0` (Wald de 1 restrição), com agrupamento duplo UF×ano +
município (D104/D111).

Nota de identificação: o **nível** regional é absorvido pelos efeitos fixos de
município; só a **inclinação** é identificável. Não se testa "região tem
produtividade diferente".

### 3.3. Secundários (não confirmatórios)

* mesma comparação preditiva para **soja** (replicação);
* mesma comparação para **milho 2ª** (com a ressalva de que o Sul é só PR e
  n=388);
* interação associativa para soja e milho 2ª;
* contraste restrito a **MRS 3** (Cerrado sul) no lugar de MRS 3∪4;
* contraste **Sul ∪ MRS 2** vs Cerrado (pior caso de má atribuição);
* contraste **excluindo MT** do Cerrado.

## 4. Família confirmatória e multiplicidade

**Família confirmatória: 2 testes, milho apenas** (preditivo D + associativo c).
Holm, α = 0,05. Tamanho 2, declarado.

Motivo: milho é a cultura primária desde a V3.3 e é onde o padrão apareceu com
maior magnitude. Soja entra como replicação **secundária**; milho 2ª como
secundário.

Todas as demais comparações são **exploratórias** e vão para uma tabela separada,
com FDR de Benjamini–Hochberg quando fizer sentido agrupá-las, e são rotuladas
como tal em todo o texto.

## 5. Inferência

### 5.1. Predição

* IC por **bootstrap de UF×ano** (unidade da exposição climática, D104).
* IC por **bootstrap de bloco espacial** como sensibilidade (convenção V2.7–V3.3).
* **Limitação do nível de tratamento, declarada:** a região é atribuída no nível
  da UF e está perfeitamente aninhada nela (Cramér's V = 1,000). Nenhuma UF
  contribui para os dois grupos. Logo, o número de unidades independentes do
  *tratamento* é 2 vs 4 UFs, e **nenhum bootstrap de linhas ou de UF×ano
  representa essa incerteza**. Por isso:
  * o IC de UF×ano é reportado como **descritivo da amostra**, não como IC do
    efeito regional;
  * é obrigatório o **leave-one-UF-out** (6 exclusões), que é a única medida
    honesta de quanto o contraste depende de uma UF;
  * se o sinal de D depender de uma UF, a classificação é no máximo Nível C.

### 5.2. Associação

Agrupamento duplo UF×ano + município, CR1, `t(G−1)`. `G` = número de clusters
UF×ano (16 no Sul, 32 no Cerrado no milho). **Não se agrupa por região**: com
duas categorias não há clusters suficientes para inferência convencional.

## 6. Regra de decisão (congelada)

| nível | condição |
|---|---|
| **A** | evidência regional robusta **com validação independente** — **impossível nesta versão** (nenhuma amostra não examinada) |
| **B** | contraste preditivo e associativo consistentes e na direção esperada, estáveis em leave-one-UF-out, **mas sem validação independente** |
| **C** | padrão presente, porém dependente de UF, de ano ou de subgrupo |
| **D** | contraste desaparece, muda de sinal ou não é estável |
| **E** | não identificável: região aninhada em UF sem variação interna, cobertura insuficiente ou clusters insuficientes |
| **F** | inconclusivo por poder: IC amplo demais para decidir; registrar o que seria necessário |

Regras de precedência, fixadas agora:

1. **E tem precedência sobre B**: se não houver nenhuma UF com municípios nos dois
   grupos, a alegação de "efeito regional independente de estado" é
   **não identificável**, mesmo que D seja grande. Nesse caso D pode ser
   reportado apenas como **contraste entre grupos de estados**.
2. **C sobrescreve B** se o sinal de D mudar em qualquer leave-one-UF-out.
3. **Nunca A** nesta versão.
4. Um resultado com D na direção oposta à da V3.3 é resultado válido e será
   relatado como refutação do padrão exploratório.

## 7. Robustez obrigatória

1. leave-one-UF-out (6);
2. leave-one-year-out (8–9);
3. **testes dentro do mesmo estado**, onde a macrorregião varia e a UF não:
   GO (MRS 3 × 4), MS (MRS 2 × 3), PR (MRS 1 × 2). Se o efeito variar dentro do
   estado na mesma magnitude do contraste regional, a leitura "fronteira
   regional" está refutada;
4. **suporte climático**: reestimar D restringindo a linhas com déficit dentro de
   uma faixa comum às duas regiões (o déficit mediano do milho é 0,97 mm no Sul
   e 74,4 mm no Cerrado — as distribuições quase não se sobrepõem na mediana);
5. classificações alternativas do protocolo (§8);
6. ponderação: por observação (padrão), por município, por UF;
7. equalização amostral por região.

## 8. O que não será feito

* Não reabrir a especificação hídrica (D108).
* Não criar variáveis de duração (D109).
* Não trocar a métrica (MAE) nem o braço (TE).
* Não testar classificações até uma dar significância.
* Não chamar de confirmação independente.
* Não interpretar como causal.
