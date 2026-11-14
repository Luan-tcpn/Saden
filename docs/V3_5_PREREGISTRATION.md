# V3.5 — PRÉ-REGISTRO DAS ANÁLISES DE SÃO PAULO

**Base:** `b9e7098` (V3.4). Data: 2026-11-14.

---

## 0. Divulgação obrigatória sobre a ordem de execução

O escopo da V3.5 pede o pré-registro **antes** de ver as estimativas novas. Nesta
execução, a aquisição de SP e a estimativa do contraste dentro do estado foram
feitas **antes** deste documento ser consolidado. Está registrado como **desvio
de processo**, com estas consequências:

* o teste primário **não é pré-registrado** no sentido estrito;
* ele **é**, porém, um teste em **dados que não existiam no projeto** até esta
  versão — SP nunca foi analisado na V3.1–V3.4;
* a hipótese e o desenho, por outro lado, foram definidos **depois** de ver o
  padrão exploratório da V3.4 nos seis estados.

Classificação honesta: **teste prospectivo em amostra territorial nova, com
desenho escolhido após a descoberta** — mais forte que uma reanálise dos mesmos
dados, mais fraco que um pré-registro genuíno.

As análises de **robustez** (`leave-one-year-out`, grupos alternativos) foram
especificadas e executadas depois deste documento e **são** pré-registradas nele.

## 1. Hipótese

**H1:** dentro de São Paulo, o efeito do bloco hídrico difere entre municípios da
**MRS 1** e da **MRS 3**.

**H0:** não difere.

Bilateral. A direção esperada (Sul favorecido) veio da V3.4 e não é usada para
aumentar poder.

## 2. População e classificação

* Municípios de SP com `status = paired_usable`, clima NASA POWER e janela ZARC.
* Classificação **congelada na V3.4** (MAPA/ZARC), estendida a SP pelo mesmo
  parser e mesma planilha (hash `91126b6b…7458c84`), com verificação de que as
  linhas dos seis estados não mudaram.
* **MRS 1** (RE 103, região de Itapeva/Itararé): 44 municípios.
* **MRS 3** (RE 302, oeste paulista): 168 municípios.
* **MRS 2** (RE 201/202/203): 431 municípios, **fora do contraste primário**.

## 3. Estimandos

### 3.1. Primário (preditivo, soja)

```
Δ_g = MAE(M2 + bloco hídrico | MRS g) − MAE(M2 | MRS g)
D   = Δ_MRS1 − Δ_MRS3
```

MAE no braço TE, kg/ha. **Soja é a cultura primária** porque a classificação MRS
é sojícula. D < 0 ⇒ bloco relativamente melhor em MRS 1.

### 3.2. Primário (associativo, soja)

```
y_w = b·x_w + c·(x · 1[MRS 1])_w + e
```

`x` = déficit acumulado (CAD 0–100 cm). Teste de `c = 0`, agrupamento duplo.

## 4. Família e multiplicidade

**Família confirmatória: 2 testes, soja** (D preditivo + interação associativa).
Holm, α = 0,05.

Secundários: milho e milho 2ª (rotulados como **exploração de estratificação
geográfica**, porque a MRS vem da soja — D112/§7.3).

## 5. Inferência

* Predição: bootstrap por **ano** (9 unidades) e por **município** (~170).
  O ano é a unidade do choque climático e é o que limita o poder.
* Associação: agrupamento duplo ano × município. `G` fica em 7–9 anos; isso é
  **pouco** e o resultado será classificado como inconclusivo se o IC for amplo
  demais para decidir.

## 6. Regra de decisão

| nível | condição |
|---|---|
| **A** | diferença grande, IC estreito, estável em LOO-ano, replicada em milho |
| **B** | diferença na direção esperada, IC excluindo zero, sem replicação |
| **C** | sinal instável entre anos ou dependente de poucos municípios |
| **D** | nenhuma diferença material: IC centrado em zero e pequeno vs o contraste entre estados da V3.4 |
| **E** | não identificável (cobertura insuficiente em um dos grupos) |
| **F** | inconclusivo por poder (IC amplo) |

Referência de magnitude: o contraste Sul×Cerrado da V3.4 foi **−78,3 kg/ha**
(milho). Um efeito dentro de SP de ordem muito menor não sustenta a leitura
regional.

## 7. Robustez pré-registrada

1. `leave-one-year-out` (9 exclusões);
2. agrupamentos alternativos: MRS 1 × MRS 2 e MRS 2 × MRS 3;
3. bootstrap por município (complementa o por ano).

## 8. O que não será feito

* Mudar a classificação depois de ver o resultado.
* Trocar a cultura primária (soja) por outra que dê significância.
* Chamar isto de confirmação independente.
* Reabrir a especificação hídrica (D108).
* Tratar MRS como zona agronômica do milho (D112).
