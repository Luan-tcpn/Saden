# SADEN V3.3 — Auditoria da inferência de associação (V2.7–V3.1)

**Frente B.** Base: `3bf9360` (V3.2). Data: 2026-11-14.
Registro completo, linha a linha: `docs/execution/v3.3/INFERENCE_AUDIT_REGISTER.md`.

---

## 1. Resumo executivo

A V3.2 descobriu (D104) que a unidade de variação dos choques climáticos é
**UF×ano**, não o bloco espacial de 250 km, e que agrupar por bloco produz
erros-padrão otimistas. A V3.3 aplica essa correção a **tudo** que foi publicado
como inferência de associação entre V2.7 e V3.0, mantendo modelo, amostra e
variável idênticos e mudando **apenas** a VCV.

| família | hipóteses | histórico (bloco) | auditado (UF×ano + município) |
|---|---:|---|---|
| **V2.7** — 7 variáveis meteorológicas | 21 | 10 brutos / **4 Holm** | 4 brutos / **0 Holm** |
| **V3.0** — déficit, 5 definições | 15 | **10 Holm** | 9 brutos / **8 Holm** |
| **V2.9** — interação por grupo de ciclo | 9 | 2 brutos / **1 Holm** | 0 brutos / **0 Holm** |

Reprodução dos coeficientes históricos: diferença máxima **1,5×10⁻⁶** (V2.7),
**3,6×10⁻¹⁵** (V3.0) e **9,2×10⁻⁸** (V2.9). Os **p-valores** sob o esquema
histórico também reproduzem: diferença máxima de **5,3×10⁻⁴** e **6,8×10⁻⁴** em
`log10` (≈0,1%) nas duas famílias. O que muda é só a precisão sob o agrupamento
novo.

**Três conclusões:**

1. **As associações meteorológicas da V2.7 não sobrevivem.** Nenhuma das 4 que
   passavam o Holm da própria V2.7 passa sob agrupamento correto.
2. **As associações de déficit da V3.0 sobrevivem quase inteiras** (8 de 10),
   incluindo todas as da soja com janela corrigida. O que cai é uma
   (`milho|deficit_cad200`, enfraquecida).
3. **A interação por grupo de ciclo da V2.9 cai por completo** — inclusive o
   p = 0,0028 da soja, que já era tratado com cautela.

A leitura científica é consistente e não é trivial: o que era frágil era a
inferência sobre variáveis meteorológicas **brutas**; o que era robusto era a
inferência sobre o **balanço hídrico**.

## 2. Histórico da questão

V2.7 (D76–D84) montou o arsenal de inferência robusta — CR1, CR2, Conley HAC,
wild cluster bootstrap, blocos espaciais — e reportou uma família de 21 testes
com Holm. V2.9 acrescentou o teste formal de interação por grupo de ciclo (D94).
V3.0 reestimou o déficit sob cinco definições com Holm sobre 15 testes.

Em todas, o agrupamento padrão foi o **bloco espacial de 250 km**. A V3.2 mostrou
que, para variáveis cuja exposição é essencialmente a mesma em toda a UF no mesmo
ano, esse agrupamento trata milhares de linhas correlacionadas como quase
independentes.

## 3. D104 — a decisão que motiva a auditoria

Mesmo modelo, mesmos dados, só o agrupamento muda (V3.2):

| teste | F bloco | F UF×ano + município |
|---|---:|---:|
| soja precipitação | 8,74 (p ≈ 0) | 1,13 (p = 0,36) |
| soja temperatura | 10,33 | 1,89 (p = 0,13) |

Razão de erros-padrão: 2,5–3×

## 4. Estrutura de dependência

Quatro dependências distintas, que um único método não resolve:

| # | fonte | tratamento |
|---|---|---|
| 1 | choque climático compartilhado na UF×ano | agrupamento por UF×ano |
| 2 | observações repetidas do município | agrupamento por município |
| 3 | dependência residual espacial | Conley HAC (sensibilidade, V2.7) |
| 4 | dependência temporal | efeitos fixos de ano |

A estrutura adotada é o **agrupamento duplo** de Cameron, Gelbach & Miller (2011):
`V = V_A + V_B − V_{A∩B}`, com A = UF×ano e B = município. Ela cobre (1) e (2)
simultaneamente. (3) e (4) são tratados por desenho: o *within* de ano remove o
choque nacional e o Conley já tinha sido reportado na V2.7 como sensibilidade.

`n_clusters` na auditoria: 31–48 UF×ano e 505–1.225 municípios. O `df` efetivo
é `min(n_A, n_B) − 1`, dominado pelos UF×ano.

## 5. Método de inferência

Para cada hipótese:

1. mesma variável, mesma amostra, mesmo modelo *within* (município + ano) da
   versão original;
2. OLS do `y_w` em `x_w`;
3. VCV CR1 sob cinco esquemas: município, bloco 250 km, UF, UF×ano, duplo;
4. `t` com `G − 1`, IC95%;
5. Holm sobre a **família original** da versão (21, 15, 9), sem rearranjo.

Nenhuma escolha de esquema foi feita olhando o p-valor: o esquema primário é o
duplo, definido pela estrutura de dependência em §4.

## 6. Resultados inventariados e classificação

| classe | V2.7 | V3.0 | V2.9 |
|---|---:|---:|---:|
| A — associação primária | 10 | 15 | 3 |
| B — associação secundária | 0 | 0 | 0 |
| C — exploratório | 11 | 0 | 6 |
| D — descritivo | — | — | — |
| E — preditivo | — | — | — |
| F — não auditável | 0 | 0 | 0 |

A distinção A/C segue o relatório original: em V2.7 as 21 hipóteses eram uma
família única de testes de efeito fixo; as 11 que já não eram significativas
entram como C por não terem sustentado conclusão. Em V2.9, as 3 interações de
déficit foram tratadas como hipótese principal e as outras 6 como secundárias.

## 7. V2.7 — as quatro que caem

| hipótese | p bloco | p UF×ano | Holm bloco | Holm duplo | razão de SE | classificação |
|---|---:|---:|---:|---:|---:|---|
| soja · temperatura | 4,3×10⁻⁵ | 0,185 | **0,0008** | 1,000 | 3,36 | **não sustentada** |
| soja · déficit | 4,1×10⁻⁶ | 0,036 | **0,0001** | 0,651 | 2,42 | só bruta |
| milho · ET0 | 2,42×10⁻⁶ | 0,021 | **5,1×10⁻⁵** | 0,406 | 2,25 | só bruta |
| milho · temperatura | 3,9×10⁻⁴ | 0,061 | **0,0069** | 1,000 | 1,99 | enfraquecida |

As quatro tinham Holm < 0,01 sob bloco. Aumento de SE de 2,0 a 3,4×.

Outras mudanças relevantes:

| hipótese | p bloco | p duplo | classificação |
|---|---:|---:|---|
| soja · precipitação | 0,0050 | 0,071 | enfraquecida |
| soja · calor extremo | 0,0138 | 0,378 | não sustentada |
| milho · precipitação | 0,0076 | 0,107 | não sustentada |
| milho · excesso | 0,0253 | 0,245 | não sustentada |
| milho · calor extremo | 0,0046 | 0,017 | só bruta |
| milho · déficit | 0,0047 | 0,0033 | só bruta (SE caiu 4%) |

Observação técnica: em duas hipóteses da V2.7 o SE sob duplo é menor
(`milho_2` graus-dia 0,66×; milho déficit 0,96×), e na V3.0 são quatro (0,88–0,98×).
A agregação por UF×ano não é uniformemente mais conservadora — é *mais correta*.
O critério não é "o p subiu", é "a unidade está certa".

## 8. V3.0 — o que permanece

| hipótese | coef. | p bloco | p duplo | Holm duplo | classificação |
|---|---:|---:|---:|---:|---|
| soja · déficit 50 mm corrigido | −2,448 | 1,2×10⁻¹⁰ | 4×10⁻⁶ | **0,0000** | mantida |
| soja · CAD 0–60 | −2,404 | 3,5×10⁻¹⁰ | 1×10⁻⁵ | **0,0001** | mantida |
| soja · CAD 0–100 | −2,318 | 6,1×10⁻¹⁰ | 0,0002 | **0,0023** | mantida |
| soja · CAD 0–200 | −2,285 | 3,8×10⁻⁷ | 0,0032 | **0,0330** | mantida |
| milho · CAD 0–100 | −2,781 | 0,0052 | 0,0046 | **0,0367** | mantida |
| milho · CAD 0–60 | −2,605 | 0,0061 | 0,0030 | **0,0330** | mantida |
| milho · déficit 50 mm corrigido | −2,437 | 0,0069 | 0,0024 | **0,0294** | mantida |
| milho · déficit histórico | −3,040 | 0,0047 | 0,0033 | **0,0330** | mantida |
| milho · CAD 0–200 | −2,010 | 0,0016 | 0,085 | 0,510 | **enfraquecida** |
| soja · déficit histórico | −1,260 | 4,1×10⁻⁶ | 0,036 | 0,253 | só bruta |
| milho 2ª (5 definições) | −0,16 a −0,74 | 0,10–0,75 | 0,47–0,86 | 1,000 | sem evidência |

Dois pontos:

* A associação do déficit é **estável** e não é artefato de agrupamento.
* **A janela corrigida é o que sustenta a associação da soja.** Com a janela
  histórica (`deficit_hist`, coef. −1,26), a associação cai para Holm 0,253; com
  a janela corrigida (coef. −2,45) ela é a mais forte da família (Holm 0,0000).
  Isso é C3 (correção de dados), não C2 (correção de inferência), e está separado
  no registro.

## 9. V2.9 — a interação cai

| hipótese | diferença | p bloco | p duplo | p histórico |
|---|---:|---:|---:|---:|
| soja · déficit (Grupo III vs II) | −1,194 | **0,0028** | 0,173 | 0,0028 |
| milho · precipitação (III vs II) | −1,017 | **0,0456** | 0,075 | 0,0456 |
| demais 7 | — | 0,12–0,91 | 0,14–0,84 | idem |

A interação de déficit na soja — a única que sobrevivia ao Holm da V2.9 — passa
de p = 0,0028 para 0,173. A V2.9 já havia registrado que "nada sobrevivia à
multiplicidade" e retratado a inversão de temperatura; a V3.3 mostra que **nem o
p bruto** se sustenta. D94 permanece correta na conclusão (não usar a interação),
por razões agora mais fortes.

## 10. V2.7, V2.8, V3.1 — o que não é auditável como associação

* **V2.8** produziu apenas comparações preditivas (fatorial 2×2, MAE). Classe E.
  Não há p-valor de regressão para reclassificar, e converter MAE em p-valor
  seria inventar um teste que não existia.
* **V3.1** não estimou família de associação própria: reexecutou as
  especificações de déficit da V3.0 (cobertas aqui em F2) e dedicou-se a
  comparações preditivas e à heterogeneidade de inclinações, que a **V3.2** já
  auditou (D104/D105). Repetir aqui seria duplicar.
* **V3.0** tem também inferência preditiva (efeito do bloco, M2−M1); essa parte é
  classe E e foi reexaminada na V3.2 sob os dois esquemas de reamostragem.

## 11. Comparação de erros-padrão

Razão SE(duplo)/SE(bloco), por família (todas as hipóteses, não só as
significativas):

| família | n | mínimo | mediana | máximo |
|---|---:|---:|---:|---:|
| V2.7 | 21 | 0,66 | 1,64 | 3,36 |
| V3.0 | 15 | 0,88 | 1,65 | 2,42 |
| V2.9 | 9 | 0,56 | 1,23 | 2,28 |

A mediana de ~1,6× nas duas famílias grandes é o número que deve ser lembrado:
**os erros-padrão publicados estavam subestimados por um fator de ~1,6**, com
extremos de 3,4×.

O agrupamento duplo **não** é uniformemente mais conservador: sete hipóteses têm
SE menor (até 0,56×, em `milho_2` graus-dia e `milho_2` temperatura na
interação). Isso é esperado — o CR1 por bloco *superestima* quando o bloco
agrega municípios com escores residuais de sinais opostos. O critério de escolha
é a **estrutura de dependência**, não o efeito sobre o p-valor.

## 12. Multiplicidade

| família | método | tamanho | histórico | auditado |
|---|---|---:|---|---|
| V2.7 | Holm (FWER) | 21 | 4 significativas | **0** |
| V3.0 | Holm (FWER) | 15 | 10 significativas | **8** |
| V2.9 | Holm (FWER) | 3 déficit + 6 secundárias | 1 | **0** |

Famílias mantidas **como no original**. Nenhuma família foi redefinida para
favorecer um resultado.

## 13. Conclusões mantidas

1. O déficit hídrico é negativamente associado à produtividade da soja e do
   milho, líquido de município e ano, e isso **não** é artefato de agrupamento
   (8 de 15 hipóteses da V3.0 sobrevivem ao Holm correto; a soja é o caso mais
   forte).
2. A ordenação das definições de déficit se mantém: as versões com janela
   corrigida têm associação mais forte que a histórica na soja.
3. A conclusão da V2.9 de **não** usar interação por grupo de ciclo permanece —
   agora com evidência mais forte de que não há interação detectável.

## 14. Conclusões enfraquecidas ou não sustentadas

1. **Todas as associações meteorológicas brutas da V2.7** (temperatura,
   precipitação, calor extremo, ET0, excesso) perdem significância após Holm.
   Nenhuma deve ser citada como evidência confirmatória.
2. A associação do déficit histórico na soja (janela antiga) cai para n.s.
3. `milho | deficit_cad200` fica em 0,085 — enfraquecida, não sustentada.
4. A interação soja × déficit por grupo de ciclo deixa de ter qualquer evidência.

## 15. Resultados inconclusivos

* **Milho 2ª safra**: as cinco definições de déficit nunca foram significativas
  (p duplo 0,47–0,86). Não é "evidência de ausência"; com 2.902 linhas e 31
  clusters UF×ano, o teste tem poder limitado para efeitos pequenos.
* **Calor extremo e excesso hídrico** no milho: p duplo 0,017 e 0,245. O primeiro
  é sugestivo, mas não sobrevive ao Holm da família de 21 e não foi
  pré-registrado como hipótese própria. Permanece como sinal a testar.

## 16. Limitações

1. **Isolamento do agrupamento.** A auditoria muda só a VCV. Onde a janela também
   mudou (V3.1), o efeito está em C3 e é reportado separadamente.
2. **`G` = 31–48 clusters UF×ano.** A aproximação `t(G−1)` é razoável, não exata.
   Com `G` < 30 o método fica frágil; milho 2ª (31) está no limite.
3. **CR1 apenas.** Não foi implementado CR2 nem wild cluster bootstrap
   multidimensional nesta rodada; o CR1 com duplo agrupamento é o padrão da
   literatura para este desenho. Uma verificação por wild bootstrap
   bidimensional fica como recomendação.
4. **Dependência espacial residual** não foi re-testada; o Conley da V2.7 é a
   referência disponível.
5. **Não há reanálise causal.** Nada aqui muda a interpretação associativa.

## 17. Decisões

* **D110** — as famílias de associação de V2.7 e V2.9 são **supersedidas**; as de
  V3.0 permanecem, com uma hipótese enfraquecida.
* **D111** — toda alegação de associação passa a exigir agrupamento na unidade de
  exposição e Holm na família declarada; p-valores por bloco ficam como
  diagnóstico, nunca como evidência confirmatória.

## 18. Referências

1. **Cameron, A. C., Gelbach, J. B., & Miller, D. L. (2011).** *Robust Inference
   With Multiway Clustering.* Journal of Business & Economic Statistics, 29(2),
   238–249. <https://doi.org/10.1198/jbes.2010.07136> — Usado para: a identidade
   `V = V_A + V_B − V_{A∩B}` e a escolha das duas dimensões.
2. **Cameron, A. C., & Miller, D. L. (2015).** *A Practitioner's Guide to
   Cluster-Robust Inference.* Journal of Human Resources, 50(2), 317–372.
   <https://jhr.uwpress.org/content/50/2/317> — Usado para: definição da unidade
   de agrupamento a partir da variação do regressor e advertência sobre poucos
   clusters.
3. **Cameron, A. C., Gelbach, J. B., & Miller, D. L. (2008).** *Bootstrap-Based
   Improvements for Inference with Clustered Errors.* Review of Economics and
   Statistics, 90(3), 414–427.
   <https://direct.mit.edu/rest/article/90/3/414/57731> — Recomendação de
   wild bootstrap para poucos clusters (não executada aqui; ver §16.3).

## 19. Reprodutibilidade

```
python tools/v33_inference_audit.py
python tools/v33_write_audit_register.py
```

| artefato | caminho |
|---|---|
| manifesto completo | `geospatial/data/manifests/v33_inference_audit.json` |
| tabela de rastreabilidade | `geospatial/data/manifests/v33_inference_audit.csv` |
| registro em markdown | `docs/execution/v3.3/INFERENCE_AUDIT_REGISTER.md` |
| testes | `geospatial/tests/test_v33_functional_form.py` |

Verificações de reprodução embutidas: o coeficiente histórico é recomputado e
comparado ao publicado em cada uma das 45 hipóteses (diferença máxima 1,5×10⁻⁶);
o Holm por bloco recomputado reproduz exatamente `p_adjusted` e
`n_significant_holm` da V2.7.
