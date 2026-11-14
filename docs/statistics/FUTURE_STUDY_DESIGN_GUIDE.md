# SADEN — Guia de desenho para estudos futuros

**Data:** 2026-11-14 · Base: `STATISTICAL_POWER_AND_MDE_REPORT.md`

Este guia responde a uma pergunta prática: **para qual pergunta vale a pena
gastar esforço de coleta daqui para frente, e para qual não vale.**

---

## 1. Regra de bolso

Antes de qualquer expansão, calcule:

```
MDE ≈ 2,85 × SE(β)      (80% de poder, α = 5%, ~50 clusters)
```

e compare com o efeito que se espera encontrar. Se `efeito plausível < MDE`, o
estudo não é informativo, **qualquer que seja o N de municípios**.

## 2. O que não compra poder

| ação | ganho no erro-padrão | veredito |
|---|---:|---|
| dobrar municípios nas 7 UFs | −0,2% | **não fazer por poder** |
| quintuplicar municípios nas 7 UFs | −0,4% a −1,3% | **não fazer por poder** |
| refinar o clima (mais variáveis, mesma estrutura) | 0% | útil só para outra pergunta |

Motivo: os 41–56 clusters já contêm 139–261 municípios. Com ICC de 0,18–0,28, a
informação nova por município é quase nula para exposição que varia em UF × ano.

## 3. O que compra poder

| ação | ganho | custo | quando usar |
|---|---:|---|---|
| mais **anos** (9 → 15) | −22% no SE | alto (dados até 2031) | séries longas, efeito climático |
| mais **UFs** (7 → 10) | −16% no SE | médio | **MG é a escolha certa (D119)** |
| mais clusters dentro da UF (ex.: regiões homogêneas declaradas) | depende do ICC | baixo | quando a exposição varia *dentro* da UF |

## 4. Por pergunta

### 4.1. Déficit hídrico × produtividade (soja)
MDE atual 1,14 kg/ha/mm; efeito observado −2,27. **Já identificado.** Para
publicar como associação basta a inferência calibrada (§6). Não precisa de mais
dados; precisa de p-valor honesto.

### 4.2. Déficit × milho e milho 2ª
MDE 2,11 e 3,36. O efeito observado está no limite. **Acrescentar UFs** (MG) é o
que reduz o erro. Para milho 2ª, a limitação real é a **fonte** (a PAM não separa
safras) — nenhuma quantidade de dados resolve isso.

### 4.3. Temperatura e graus-dia
MDE de 203 a 433 kg/ha por °C. **Não identificável neste desenho.** Para atacar
temperatura seria preciso outro desenho: exposição em escala sub-municipal
(grade), eventos discretos (geada, calor extremo em janela curta) ou painel de
municípios com clima realmente contrastante no *within*. Não adianta coletar
mais municípios.

### 4.4. Heterogeneidade de inclinações por UF
Com 48 clusters, cada inclinação por UF consome graus de liberdade que o desenho
não tem. Um teste de heterogeneidade informativo exigiria **mais clusters por
UF** (séries mais longas) ou **menos parâmetros** (agrupar UFs por critério
declarado antes da estimação — o que a V3.4 tentou e a V3.5 encerrou).

### 4.5. Contraste regional Sul × Cerrado
**Não é problema de poder, é de identificação.** Cramér's V = 1,000: nenhum
estado pertence aos dois grupos. Mais dados não resolvem. Só um desenho com
variação dentro da unidade (municípios de fronteira, faixas de transição
definidas a priori) permitiria.

### 4.6. Previsão (não associação)
Nenhuma análise de poder foi feita para **diferença de erro fora da amostra**.
Se o objetivo for previsão, o critério é outro: comparar RMSE sob validação
espacial e temporal, com intervalo por bootstrap. MDE não se aplica.

## 5. Checklist antes de abrir uma nova versão

1. Qual é o estimando? (associação, previsão, contraste)
2. Qual é a unidade de exposição e qual o cluster? (D104)
3. Qual é o MDE desse desenho, em unidade interpretável?
4. O efeito plausível é maior que o MDE?
5. Quantas hipóteses na família? Correção declarada antes (D111)?
6. O p-valor é nominal de 5% ou está corrigido pela liberalidade observada?
7. Qual é a fonte de identificação? Se não há variação dentro da unidade, é
   **não identificado** — e isso se declara, não se testa.

## 6. Recomendação de inferência

Como o erro tipo I observado é de 6% a 10% com 41–56 clusters, qualquer
resultado futuro deve reportar:

- o p-valor **cluster-robusto CR1** (como hoje);
- o p-valor por **wild cluster bootstrap** (recomendado com G < 50);
- a conclusão só quando **os dois** concordarem.

O repositório já contém um calibrador de bootstrap (`tools/calibrate_wild_bootstrap.py`),
ainda não incorporado ao fluxo oficial. Essa é a lacuna metodológica mais
concreta e mais barata de fechar.
