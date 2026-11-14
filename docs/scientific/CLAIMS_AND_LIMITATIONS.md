# SADEN — O que podemos e o que não podemos afirmar

**Data:** 2026-11-14
Documento de síntese. Não é um relatório novo; consolida o que já está
demonstrado nos relatórios V2.6–V3.5, na auditoria de dados e na replicação
independente.

---

## 1. As três linhas do projeto

| linha | o que é | estado |
|---|---|---|
| **A. Aplicação de preços (V1.1)** | app que projeta preços de soja e milho a partir de séries internacionais e câmbio | **congelada**, é o produto |
| **B. Pesquisa agroclimática (V2.6–V3.5)** | estudo da relação entre variáveis agroclimáticas e produtividade municipal | **concluída até V3.5**, consolidada aqui |
| **C. Integração futura** | o que da linha B poderia virar função da linha A | **avaliada, não implementada** |

Nenhuma conclusão da linha B foi incorporada à linha A. A V1.1 continua sendo a
referência do produto.

---

## 2. O que podemos afirmar

### 2.1. Validado computacionalmente

1. **A janela agrícola histórica estava errada.** O cálculo anterior (V2.6–V3.0)
   excluía **um mês inteiro** do fim de cada janela, não um dia. Todas as 20
   variáveis de janela foram contaminadas. A correção (D97) elevou a
   precipitação acumulada em **+44%**, a ET0 em **+43,5%**, os graus-dia em
   **+45,5%** e o déficit em **+23,6%**, comparando medianas.
2. **A janela corrigida reproduz exatamente.** Reprodução bit-a-bit dos números
   publicados na V3.5 (diferença 0,000 em 10 variáveis × 204 linhas).
3. **O balanço hídrico está aritmeticamente correto.** Replicação independente
   do algoritmo de Thornthwaite & Mather: 8/8 casos manuais e 90 janelas reais
   com diferença máxima de **4,3 × 10⁻⁶ mm** no déficit sazonal.
4. **A fonte de produtividade é sólida.** 43.650 células município–ano–cultura,
   **zero chaves duplicadas**, **zero alteração de código municipal** entre 2017
   e 2025, rendimento aritmeticamente consistente em **99,8%** das células.
   Apenas **27 de 30.207 linhas** analíticas (0,09%) vêm de células com algum
   flag, e todas em BA (0,35% do painel).

### 2.2. Replicado independentemente

5. **Déficit sazonal** — recalculado a partir das equações, sem chamar a função
   original, com concordância na ordem de 10⁻⁶ mm.

### 2.3. Evidência associativa

6. **Existe associação entre déficit hídrico e produtividade da soja**, dentro
   do município, controlando por ano, com erro agrupado em UF × ano:
   **−2,27 kg/ha por mm de déficit** (EP 0,40; IC95% ≈ [−3,06; −1,48]).
   O efeito observado é **duas vezes** o efeito mínimo detectável (1,14 kg/ha/mm)
   — ou seja, este resultado não é um caso de desenho sem poder.
7. **A unidade de agrupamento importa e foi corrigida.** Agrupar por bloco
   espacial de 250 km subestima o erro em 2,5–3×. Com o agrupamento correto
   (UF × ano), algumas associações sobreviveram e outras não (D104).

### 2.4. Rejeitado

8. **A tendência espacial (M3) não se justifica**: M3 − M2 = +388,1 [62,0;
   719,5] em erro, isto é, o modelo mais complexo não melhora de forma
   consistente (D101).
9. **A janela histórica é inválida** e não deve ser usada em nenhuma análise.

---

## 3. O que **não** podemos afirmar

1. **Causalidade.** Nenhum resultado é causal. Não há experimento, nem variável
   instrumental, nem desenho quasi-experimental válido. Tudo é associação
   condicional.
2. **Generalização nacional.** A cobertura é de **7 UFs** e **48,3%** do
   território sojícola indicado. Não existe resultado nacional.
3. **Contraste regional Sul × Cerrado.** **Não identificado** — Cramér's V =
   1,000: nenhum estado pertence aos dois grupos. Isso **não** é "não há
   efeito"; é "o desenho não permite estimar".
4. **Duração × intensidade do estresse.** Não separáveis com balanço mensal:
   `etr/etp` é algebricamente igual a `deficit/etp` (r = −1,000), a duração
   concentra 94% da variância e o calor correlaciona 0,84 com o déficit (D109).
5. **Vantagem preditiva do bloco hídrico.** Não demonstrada. O modelo M2
   (clima sem bloco hídrico) foi o retido (D108).
6. **Efeito da temperatura e dos graus-dia.** **Inconclusivo por poder**: o
   efeito mínimo detectável é de **203 a 433 kg/ha por °C**. Um efeito
   agronomicamente grande caberia inteiro dentro do intervalo. Ausência de
   significância aqui **não é** evidência de ausência.
7. **Heterogeneidade de inclinações por UF.** Investigada e não demonstrada
   (V3.2), mas com **poder limitado** — 48 clusters não sustentam dezenas de
   inclinações.
8. **Contraste dentro de São Paulo.** D = +7,3, p = 0,77 (V3.5): nulo, e
   inconclusivo por poder (um único estado).
9. **Preço.** Preços internacionais convertidos por PTAX **não são** preços
   recebidos pelo produtor. Prêmio portuário, frete, base local e custo de
   exportação não estão no modelo.
10. **Produtividade prevista não é preço futuro previsto.** São grandezas
    diferentes; a linha B não produz previsão de preço.
11. **Resultado exploratório não é confirmatório.** Achados de V3.2 que
    sobreviveram apenas à correção bruta (`mantida_apenas_bruta`) não devem ser
    lidos como confirmados.

---

## 4. Classificação das evidências

| categoria | o que entra aqui |
|---|---|
| **validado computacionalmente** | janela corrigida; reprodução bit-a-bit; consistência aritmética da PAM |
| **reproduzido independentemente** | déficit sazonal (T&M) |
| **validado preditivamente** | — **nada**. Não houve validação preditiva fora da amostra que tenha sido mantida |
| **associativo** | déficit × produtividade da soja; associações milho de V3.2 (exploratórias) |
| **exploratório** | família de variáveis de V3.2 que sobreviveu só à correção bruta |
| **inconclusivo** | temperatura, graus-dia, heterogeneidade por UF, contraste dentro de SP |
| **não identificado** | contraste regional; duração × intensidade |
| **rejeitado** | janela histórica; tendência espacial M3; vantagem do bloco hídrico |
| **não investigado** | validação do clima contra estação; previsão de produtividade fora da amostra; custo/preço local |

---

## 5. O que a aplicação (linha A) faz e não faz

**Faz:** projeta preço a partir de séries internacionais e câmbio; expõe
proveniência; mostra séries históricas.

**Não faz:** não usa produtividade agroclimática; não prevê safra; não conhece
preço local; não incorpora o resultado das linhas B.

**Estado:** congelada em `v1-final`, sem alteração nesta etapa.

---

## 6. Se algo for integrado ao produto (linha C)

Só se justifica com evidência adicional. O candidato mais defensável é
**contexto agroclimático descritivo** (ex.: "o déficit hídrico da janela desta
safra está no percentil X da série"), porque:

- não exige causalidade;
- não exige generalização nacional;
- tem erro conhecido e comunicável;
- não permite interpretação como previsão de preço.

O candidato **menos** defensável é qualquer "alerta de safra" baseado em
produtividade prevista: não há validação preditiva.

---

## 7. Três defeitos conhecidos que limitam leituras

1. **Excedente hídrico superestimado** (D124) na implementação de referência,
   quando a chuva recompõe o solo sem saturá-lo. O déficit não é afetado.
   Nenhuma conclusão publicada usou excedente.
2. **p-valores liberais** (D125): com 41–56 clusters, o erro tipo I observado é
   de 6% a 10% onde se declara 5%. Resultados com p entre 0,01 e 0,05 são mais
   frágeis do que aparentam.
3. **ET0 com viés de convenção**: `es(Tmean)` em vez de `es(Tmax, Tmin)` e vento
   60% subestimado. A ET0 é consistente entre municípios, mas **não é** ET0
   FAO-56 de referência para comparação externa.

---

## 8. Frase de uma linha para cada contexto

- **Para a banca:** "O trabalho demonstra uma associação robusta entre déficit
  hídrico e produtividade da soja no Sul e no Cerrado, com correção de um erro
  grave de janela agrícola, e delimita explicitamente o que o desenho não
  identifica."
- **Para um usuário do produto:** "O app projeta preço a partir do mercado
  internacional; ele não prevê safra."
- **Para quem for continuar:** "Antes de expandir, leia
  `docs/statistics/FUTURE_STUDY_DESIGN_GUIDE.md`: acrescentar municípios não
  aumenta o poder; acrescentar clusters, sim."
