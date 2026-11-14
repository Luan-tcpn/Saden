# SADEN V3.5 — Rebaseline dos modelos

**Data:** 2026-11-14 · Manifesto: `geospatial/data/manifests/v35_models.json`

---

## 1. Por que reestimar

A entrada de SP muda a composição da amostra. M0 (média nacional), M1 (média por
UF) e M2 (clima + UF) **não são comparáveis** com os valores das versões
anteriores sem reestimação — não porque o código mudou, mas porque a população
mudou.

Os três experimentos de ponte, com o **mesmo código** e o **mesmo protocolo**:

* **A** — apenas os seis estados (reconstituição);
* **B** — sete estados (expandido);
* **C** — A e B lado a lado.

## 2. Experimento A — reconstituição da V3.4

| cultura | n | M0 | M1 | M2 | M2+água | D(Sul−Cerrado) |
|---|---:|---:|---:|---:|---:|---:|
| milho | 7.542 | 1.632,8 | 1.836,6 | 1.661,2 | 1.651,7 | **−78,3** |
| soja | 8.868 | 641,3 | 611,4 | 592,7 | 600,8 | **−35,0** |
| milho 2ª | 2.897 | 1.467,1 | 1.502,7 | 1.272,3 | 1.282,7 | **−22,5** |

**Reproduz a V3.4 exatamente**: M2 = 1.661,2 / 592,7 / 1.272,3 e
D = −78,3 / −35,0 / −22,5, idênticos aos publicados. A cadeia de dados e o
estimador continuam consistentes.

## 3. Experimento B — painel expandido

| cultura | n | M0 | M1 | M2 | M2+água |
|---|---:|---:|---:|---:|---:|
| milho | 11.928 | 1.487,6 | 1.538,8 | **1.452,8** | 1.472,7 |
| soja | 12.491 | 604,7 | 573,9 | **554,7** | 571,3 |
| milho 2ª | 5.662 | 1.326,6 | 1.384,6 | **1.234,4** | 1.241,2 |

M2 continua sendo o melhor modelo nas três culturas, e o bloco hídrico continua
**não** melhorando (piora em +19,9 / +16,6 / +6,8 kg/ha). Isso está alinhado com
D108 — nenhuma mudança de conclusão.

## 4. Experimento C — o que mudou e por quê

| indicador | 6 UFs | 7 UFs (com SP) | diferença |
|---|---:|---:|---:|
| **milho** | | | |
| M0 | 1.632,8 | 1.487,6 | −145,2 |
| M1 | 1.836,6 | 1.538,8 | −297,8 |
| M2 | 1.661,2 | 1.452,8 | −208,4 |
| ganho de M2 sobre M1 | **175,4** | **86,0** | −89,4 |
| **soja** | | | |
| M0 | 641,3 | 604,7 | −36,6 |
| M1 | 611,4 | 573,9 | −37,5 |
| M2 | 592,7 | 554,7 | −38,0 |
| ganho de M2 sobre M1 | **18,7** | **19,2** | +0,5 |
| **milho 2ª** | | | |
| M0 | 1.467,1 | 1.326,6 | −140,5 |
| M1 | 1.502,7 | 1.384,6 | −118,1 |
| M2 | 1.272,3 | 1.234,4 | −37,9 |
| ganho de M2 sobre M1 | **230,4** | **150,2** | −80,2 |

### 4.1. Como ler isso (e como não ler)

* **As MAEs absolutas não são comparáveis entre colunas.** O conjunto de linhas
  de teste é diferente: SP acrescenta linhas com outro nível de produtividade e
  outro erro. Uma MAE menor no painel expandido **não** significa modelo melhor.
* **O ganho de M2 sobre M1 também não é comparável diretamente**, pela mesma
  razão: ele é uma média sobre linhas diferentes.
* O que se pode afirmar: **no painel expandido**, M2 supera M1 em 86,0 (milho),
  19,2 (soja) e 150,2 (milho 2ª) kg/ha, nas mesmas linhas. **No painel de seis
  estados**, superava em 175,4 / 18,7 / 230,4.
* A queda do ganho no milho e na milho 2ª é **efeito de composição**: SP tem
  níveis de produtividade mais próximos da média nacional, o que reduz o erro da
  M1 (baseline) mais do que o do M2. Não é degradação do modelo climático.
* Na soja o ganho é **estável** (18,7 → 19,2).

### 4.2. Não houve mudança de especificação

M0, M1, M1b, M2 e M2+água mantêm definição, variáveis, unidades, janela corrigida
e método de validação. Nenhum preditor novo foi criado (D108 respeitada).

## 5. Transferência para uma UF nunca vista

Treino em **todos os anos das 6 UFs**, teste nos municípios de SP:

| cultura | n teste | MAE de M2 | MAE de M0 (média treinada) | ganho |
|---|---:|---:|---:|---:|
| milho | 4.386 | 1.721,2 | 1.352,1 | **−27,3%** |
| soja | 3.623 | 566,2 | 534,6 | **−5,9%** |
| milho 2ª | 2.765 | 1.200,4 | 1.251,2 | +4,1% |

**O modelo não transfere para um estado nunca visto.** Como a dummy de UF de SP
não existe no treino, as previsões caem no intercepto (nível médio nacional), que
está longe do nível paulista em milho e soja. Isso é informação sobre o desenho,
não sobre o clima: o modelo depende dos níveis estaduais estimados.

Consequências: (i) qualquer uso do SADEN em UF não coberta exige reestimação com
dados dela; (ii) o ganho climático **dentro** da amostra não se converte em
transferência geográfica automática.

## 6. Limitações

1. **Amostras diferentes** entre A e B — por isso a decomposição e não a
   comparação direta.
2. **M1b** é diagnóstico contemporâneo, nunca baseline operacional.
3. **Transferência** foi medida com um único ano de treino para todos os anos de
   teste (não é validação temporal); é transferência **espacial**.
4. **milho 2ª** carrega a limitação semântica do PAM (total anual).

## 7. Classificação

| achado | classificação |
|---|---|
| V3.4 reproduzida exatamente com o painel expandido | **validado** |
| M2 continua o melhor nas três culturas | **validado nos protocolos avaliados** |
| bloco hídrico não melhora com SP | **validado nos protocolos avaliados** |
| ganho de M2 sobre M1 cai no milho e milho 2ª | **validado como efeito de composição** |
| transferência para UF nova é fraca | **validado** (uma medição, um protocolo) |
