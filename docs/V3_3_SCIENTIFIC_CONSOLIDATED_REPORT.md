# SADEN V3.3 — Relatório científico consolidado

**Forma funcional do balanço hídrico e auditoria da inferência histórica**

Branch: `v3/water-balance-inference-audit` · Base: `3bf9360` (V3.2) · 2026-11-14

---

## 1. O que esta versão perguntou

Duas perguntas independentes, respondidas com estimandos distintos:

**A.** O formato funcional das variáveis agroclimáticas está deixando de capturar
mecanismos — balanço hídrico, duração do estresse, não linearidade, exposição
térmica — e uma representação fisicamente coerente melhora a generalização?

**B.** Quais das conclusões de **associação** publicadas entre V2.7 e V3.1
sobrevivem quando a inferência usa a unidade correta de variação climática
(UF×ano)?

As duas são mantidas separadas neste documento até a seção de síntese. Nenhuma
conclusão de uma é usada como evidência da outra.

---

## 2. Resposta curta

**A — não.** Nenhuma forma funcional supera o modelo de referência. ΔMAE do
bloco hídrico incremental: **+1,3 kg/ha** (IC UF×ano [−47,9; +49,8]). As três
comparações confirmatórias no milho têm p = 0,953 / 0,101 / 0,167; após Holm,
nenhuma é significativa. M2 permanece.

**B — depende do que se afirmava.** As associações de **variáveis meteorológicas
brutas** não sobrevivem: das 4 hipóteses da V2.7 que passavam o Holm original,
**0** passam sob agrupamento correto. As associações de **déficit hídrico** da
V3.0 sobrevivem quase inteiras: **8 de 10**. A interação por grupo de ciclo da
V2.9 cai por completo.

A mediana de subestimação dos erros-padrão era **~1,6×** (máximo 3,4×).

---

## 3. Frente A — forma funcional

### 3.1. Desenho

Cultura primária: milho. Cenários de CAD conforme D99 (milho 0–60 cm, soja
0–100 cm). Sete modelos, do mais simples ao mais completo, todos em TE com
igualização estrita por célula e as mesmas linhas de teste.

### 3.2. O que determinou o desenho

A auditoria de dependência (medida **antes** de escolher a especificação) mudou o
plano de forma decisiva:

* `etr/etp` e `déficit/etp` são a **mesma variável** (r = −1,000, por construção);
* `déficit` e `etr/etp` compartilham 97% da variância within;
* `stress_share` e `max_consecutive` compartilham 94% — **duração e evento não são
  separáveis** com janelas de 3–5 meses;
* `heat` é 0,84 com déficit e 0,76 com temperatura — não é um bloco independente;
* `degree_days` é o único candidato térmico ortogonal (0,02 com temperatura).

Por isso H3 (duração × intensidade) foi declarada **não identificável antes dos
resultados**, e não "rejeitada" depois.

### 3.3. Resultado preditivo

| modelo | milho | soja | milho 2ª |
|---|---:|---:|---:|
| M1 | 1.917,1 | 610,7 | 1.500,8 |
| **M2** | **1.688,6** | **592,2** | **1.272,4** |
| M2 + bloco hídrico | 1.689,9 | 600,4 | 1.282,5 |
| M2 non-linear | 1.741,0 | 606,5 | 1.477,5 |
| M2 térmico (graus-dia) | 1.836,2 | 611,1 | 1.321,8 |

### 3.4. O achado que não estava no plano

O agregado nulo esconde **sinais opostos por região**:

| UF | Δ (milho) | Δ (soja) |
|---|---:|---:|
| PR | **−33,8** | −4,7 |
| RS | **−53,1** | −5,2 |
| MS | +4,1 | +49,9 |
| GO | +45,7 | +12,5 |
| MT | +94,1 | +58,2 |
| BA | +173,5 | — |

O bloco hídrico **ajuda no Sul e atrapalha no Cerrado**, nas duas culturas de
verão. Não foi pré-registrado, não sobrevive como ganho agregado, e por isso é
**observação exploratória** — não achado. Mas é o único sinal coerente que a
Frente A produziu e é a hipótese natural da V3.4.

### 3.5. Associação sem utilidade preditiva

O bloco hídrico tem associação com a produtividade (Wald p = 0,038 no milho;
Holm 0,076 sobre três blocos — marginal). A não linearidade sobrevive
(Holm 0,041). Nenhuma das duas melhora a previsão: a forma quadrática é +51 no
milho e **+195 (IC exclui zero) no milho 2ª**.

Esse é o ponto conceitual da versão: **associação e generalização divergem**. Um
coeficiente pode ser diferente de zero e não servir para prever municípios e anos
não observados, porque a variação temporal *within* que identifica o coeficiente
não é a variação que o modelo precisa capturar fora da amostra.

---

## 4. Frente B — auditoria da inferência

### 4.1. Desenho

Mesmo modelo, mesma amostra, mesma variável. **Só a VCV muda**: município, bloco
250 km, UF, UF×ano, e duplo (UF×ano + município). Três cenários explícitos:
C1 histórico, C2 inferência corrigida, C3 dados corrigidos — nunca fundidos.

### 4.2. Reprodução

| família | hipóteses | diferença máxima no coeficiente |
|---|---:|---:|
| V2.7 | 21 | 1,5×10⁻⁶ |
| V3.0 | 15 | 3,6×10⁻¹⁵ |
| V2.9 | 9 | 9,2×10⁻⁸ |

O Holm por bloco recomputado reproduz exatamente `p_adjusted` e
`n_significant_holm` da V2.7 — a reprodução valida o pipeline antes de qualquer
reclassificação.

### 4.3. Resultado

| família | histórico | auditado |
|---|---|---|
| V2.7 (21) | 10 brutos / **4 Holm** | 4 brutos / **0 Holm** |
| V3.0 (15) | **10 Holm** | 9 brutos / **8 Holm** |
| V2.9 (9) | 2 brutos / **1 Holm** | 0 / **0** |

As quatro que caem na V2.7: soja temperatura (SE ×3,36), soja déficit (×2,42),
milho ET0 (×2,25), milho temperatura (×1,99).

A única que cai na V3.0: `milho | deficit_cad200` (p 0,0016 → 0,085).

A que cai na V2.9: soja × déficit por grupo de ciclo (p 0,0028 → 0,173).

### 4.4. A separação que importa

| tipo de exposição | sobrevive? |
|---|---|
| temperatura média, precipitação acumulada, ET0, calor extremo, excesso | **não** |
| déficit hídrico (qualquer das cinco definições, soja e milho) | **sim** (8/10) |
| interação por grupo de ciclo | **não** |

O que era frágil era a inferência sobre variáveis **brutas**. O que era robusto
era a inferência sobre o **balanço hídrico**. Isso não é acidente: as variáveis
brutas variam com o ano em toda a UF (exposição comum), enquanto o déficit
carrega variação municipal dentro da UF×ano — parte da sua identificação vem de
uma unidade de variação mais fina, que o agrupamento por bloco não distorcia
tanto.

### 4.5. Um efeito de dados, não de inferência

`soja | déficit histórico` tem coeficiente −1,26 e cai para Holm 0,253; com a
janela corrigida o coeficiente é −2,45 e o Holm é 0,0000. A correção da janela
(D100) **fortaleceu** a associação da soja. Isso é C3 e está separado no
registro: não é a mudança de agrupamento que produziu o efeito.

---

## 5. Síntese

As duas frentes convergem para uma conclusão que nenhuma delas produziria
sozinha:

1. **O balanço hídrico é a representação correta da água** — a associação com
   déficit é a única que sobrevive a inferência correta e multiplicidade, e é a
   mais forte da V3.0.
2. **A representação correta da água não melhora a previsão fora da amostra.** O
   coeficiente é real; o ganho preditivo não existe.
3. **As associações meteorológicas brutas das versões anteriores não devem ser
   citadas como evidência confirmatória.** Eram, em boa parte, artefato de
   agrupamento por bloco.
4. **A heterogeneidade de inclinações (V3.2) e a não linearidade (V3.3) aparecem
   na associação e não na previsão** — o mesmo padrão, duas vezes. Isso sugere
   que o limite está no desenho preditivo (prever município e ano não observados
   com 8 anos de dados e 5–6 UFs), não na especificação.

O que se pode afirmar sem extrapolação: nas 5–6 UFs cobertas, com janela ZARC
corrigida e controles de município e ano, **o déficit hídrico é negativamente
associado à produtividade da soja e do milho**. Nada além disso.

---

## 6. Classificação das evidências

| achado | classificação |
|---|---|
| M2 reproduz a V3.1 exatamente | **validado** |
| bloco hídrico não melhora generalização | **validado nos protocolos avaliados** (nível D) |
| não linearidade não melhora generalização | **validado nos protocolos avaliados** |
| graus-dia não acrescenta nada ao bloco hídrico | **validado nos protocolos avaliados** |
| déficit associado à produtividade (soja e milho) | **validado nos protocolos avaliados** — sobrevive a Holm com agrupamento correto |
| associações meteorológicas brutas da V2.7 | **não sustentadas** pela inferência corrigida |
| interação por grupo de ciclo (V2.9) | **não sustentada** |
| gradiente regional do bloco hídrico | **exploratório** |
| duração × intensidade do estresse | **não identificável** |
| interação água × calor | **não conclusivo** |
| generalização nacional | **não avaliado** — 5–6 UFs de 27 |

---

## 7. Limitações transversais

1. **5–6 UFs de 27.** Nenhuma extrapolação territorial.
2. **31–48 clusters UF×ano.** A aproximação assintótica é razoável, não exata;
   milho 2ª (31) está no limite.
3. **Resolução mensal do balanço.** Duração em dias não existe no desenho atual.
4. **CR1 apenas.** Wild bootstrap multidimensional fica recomendado e não
   executado.
5. **Janela ZARC ≠ fenologia.** Graus-dia acumulados na janela de semeadura não
   são graus-dia até maturação.
6. **Associação não é causalidade.** Em nenhum ponto um coeficiente é lido como
   efeito causal.

---

## 8. O que mudou no entendimento do projeto

| afirmação anterior | estado após V3.3 |
|---|---|
| "temperatura e precipitação estão associadas à produtividade" (V2.7) | **não sustentado** |
| "o déficit hídrico está associado à produtividade" (V2.9/V3.0) | **mantido**, e mais forte com janela corrigida |
| "há interação por grupo de ciclo" (V2.9) | **não sustentado** |
| "o clima prevê produtividade melhor que a média da UF" (V3.1) | **mantido** (é preditivo, outro estimando) |
| "inclinações diferem entre UFs" (V3.2) | **não estabelecido** (D105) |
| "uma representação hídrica melhoraria a previsão" | **não sustentado** |

---

## 9. Decisões

* **D108** — M2 permanece o modelo de referência; nenhuma forma funcional
  testada melhora a generalização.
* **D109** — duração e intensidade do estresse não são identificáveis com o
  balanço mensal; a hipótese fica registrada como não testável, não como
  rejeitada.
* **D110** — as famílias de associação de V2.7 e V2.9 são supersedidas; as de
  V3.0 permanecem, com uma hipótese enfraquecida.
* **D111** — toda alegação de associação exige agrupamento na unidade de
  exposição, família declarada e Holm; p-valor por bloco é diagnóstico.

---

## 10. Recomendação para V3.4

Uma única prioridade, decorrente do único sinal coerente que sobrou: **testar a
hipótese regional do bloco hídrico** (Sul a favor, Cerrado contra) com
pré-registro próprio, contraste pareado dentro de subconjuntos definidos *a
priori* por critério agronômico publicado, e validação em TE. Se não sobreviver
a esse teste, o assunto está encerrado e o projeto deve voltar a ampliar
cobertura (que é o único caminho para responder às perguntas de generalização).

Não recomendado na V3.4: novas variáveis climáticas, novos limiares, novas formas
funcionais. A V3.3 já mostrou que a especificação não é o gargalo.
