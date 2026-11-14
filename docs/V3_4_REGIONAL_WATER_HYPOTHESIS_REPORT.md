# SADEN V3.4 — Hipótese regional do bloco hídrico

**Branch:** `v3/regional-water-block-hypothesis` · **Base:** `6eff88c` (V3.3) · 2026-11-14

Classificação regional: `docs/V3_4_REGIONAL_CLASSIFICATION_PROTOCOL.md` (congelada antes das estimativas).
Pré-registro: `docs/V3_4_REGIONAL_WATER_PREREGISTRATION.md` (congelado antes das estimativas).

---

## 1. Resumo executivo

**A hipótese regional não é identificável com este painel — e, além disso, a
fronteira testada não organiza o fenômeno.**

Três resultados, em ordem de importância:

1. **O contraste existe e é grande.** No milho, ΔMAE do bloco hídrico é −45,5
   kg/ha no Sul e +32,7 no Cerrado: **D = −78,3 kg/ha**, IC UF×ano [−131,7;
   −26,7], estável nas 6 exclusões de UF (−40,3 a −150,1) e nas 8 de ano
   (−44,5 a −133,0). A interação associativa é −1.287 kg/ha por 100 mm
   (p = 1,8×10⁻⁶, 47 clusters UF×ano).

2. **Isso não é um efeito regional.** A classificação agronômica é perfeitamente
   determinada pela UF (Cramér's V = 1,000; **nenhuma UF tem municípios nos dois
   grupos**). O contraste é, na prática, {RS, PR-sul/oeste} contra {GO,
   MS-norte, MT, BA-oeste}. Por regra pré-registrada, **E tem precedência sobre
   B**: a alegação de efeito regional independente de estado é **não
   identificável** (Nível E), mesmo com D grande.

3. **A fronteira testada está refutada como explicação.** Onde é possível
   comparar macroregiões **dentro do mesmo estado**, a diferença entre MRS 1 e
   MRS 2 no Paraná é significativa (+1.012 kg/ha/100 mm, p = 0,0022) e de
   magnitude comparável ao contraste Sul×Cerrado; e MS-MRS3 (Cerrado) se comporta
   como o Sul (Δ = −50,3). O grupo "Cerrado" não é internamente homogêneo.

**Decisão: nenhum modelo regional é adotado. M2 permanece (reforça D108).** A
prioridade científica passa a ser cobertura territorial (D115).

Nível final: **E** (não identificável), com a descrição quantitativa reportada
como descritiva, nunca como efeito regional.

---

## 2. Pergunta científica

O efeito do bloco hídrico — preditivo e/ou associativo — difere entre as regiões
agronômicas Sul e Cerrado?

Distinções mantidas em todo o relatório:

| # | coisa | como é medida aqui |
|---|---|---|
| 1 | diferença de erro preditivo por região | ΔMAE dentro de cada região |
| 2 | diferença de inclinação | interação bloco × região no modelo *within* |
| 3 | diferença entre estados | mesma medida, agregada por UF |
| 4 | efeito regional independente de estado | **não identificável** (§8) |

Uma região ter erro menor não prova que a água importa mais nela. Uma inclinação
diferente não prova ganho preditivo. Uma diferença entre estados não prova efeito
regional.

## 3. Histórico da hipótese

V3.3 (§13 e §16) reportou, como **exploratório**, que o bloco hídrico melhorava
em PR (−33,8) e RS (−53,1) e piorava em MS, GO, MT e BA (+4,1 a +173,5), com o
mesmo sinal na soja. Não houve ganho agregado. A hipótese regional foi registrada
como a única linha viva para a V3.4.

**Status de independência, declarado antes dos resultados:** a descoberta usou
todos os anos e municípios do painel. **Não existe amostra não examinada.** Logo
esta versão é uma **reanálise protocolada de achado exploratório**, não uma
confirmação independente — e nenhum resultado aqui é chamado de confirmação.

## 4. Classificação regional (fonte oficial, congelada)

**Fonte:** Instrução Normativa SPA/MAPA nº 1/2021, anexo atualizado pelas
Portarias 387/2023 e 281/2025 — macrorregiões sojícolas e regiões
edafoclimáticas, em **planilha oficial municipal** (4.286 pares UF–município;
SHA-256 `91126b6b…7458c84`).

| grupo | definição | composição no painel |
|---|---|---|
| **Sul** | MRS 1 | RS (todas) + PR (RE 102/103) |
| **Cerrado** | MRS 3 ∪ 4 | GO, MS (RE 301), MT, BA (RE 405) |
| **Transição** | MRS 2 | PR (RE 201/202) + MS (RE 202/204) — **excluída do contraste** |
| Fora | MRS 5 e sem indicação | BA (RE 501), 20 municípios da BA sem soja |

**Limitação da fonte:** a finalidade original é indicação de cultivares de
**soja**. O uso é como classificação agroclimática do território; a extensão ao
milho é **aproximação declarada**. MRS 4 **não** é sinônimo de bioma Cerrado
(inclui MT com transição amazônica).

Cobertura (linhas do painel):

| cultura | Sul | Cerrado | Transição | fora |
|---|---:|---:|---:|---:|
| milho | 2.482 | 2.747 | 2.298 | 89 |
| soja | 3.943 | 2.647 | 2.278 | 16 |
| milho 2ª | 388 | 743 | 1.766 | 5 |

Municípios: milho 364 Sul / 381 Cerrado; soja 556 / 353; milho 2ª 72 / 149.

## 5. Dados e modelos

Modelos **idênticos aos da V3.3**, sem qualquer alteração:

* M2 = precipitação e temperatura corrigidas + dummies de UF;
* M2 + bloco hídrico = M2 + déficit acumulado (÷100) + fração da janela em
  estresse;
* cenário de CAD por cultura (D99): milho e milho 2ª 0–60 cm; soja 0–100 cm;
* braço **TE**, igualização estrita por célula, 25 células, 3 repetições, semente
  `20261114`; MAE em kg/ha.

Reprodução: M2 nacional reproduz a V3.3 dentro de 0,02 kg/ha no milho (1.661,21
com 7.542 linhas vs 1.688,58 com 7.616 — a diferença é a exclusão das 74 linhas
sem região). O Δ nacional é −9,47 aqui e +1,33 na V3.3 pela mesma razão de
amostra; **nenhuma comparação entre regiões depende disso**.

## 6. Identificação — o resultado que decide a classificação

| indicador | milho | soja | milho 2ª |
|---|---|---|---|
| Cramér's V (região × UF) | **1,000** | **1,000** | **1,000** |
| UFs com municípios nos dois grupos | **nenhuma** | **nenhuma** | **nenhuma** |
| clusters UF×ano (Sul / Cerrado) | 16 / 32 | 16 / 24 | 9 / 19 |
| municípios (Sul / Cerrado) | 364 / 381 | 556 / 353 | 72 / 149 |

**Consequência:** o nível regional é absorvido por efeitos de município e não é
separável de um contraste entre estados. O que continua identificado é a
**inclinação** (a interação vem da co-varição temporal dentro do município), mas
"região" é, nestes dados, apenas um nome para um conjunto de estados.

Suporte climático também difere muito: déficit mediano no milho é **0,97 mm** no
Sul e **74,4 mm** no Cerrado (razão 77×).

## 7. Resultados preditivos

ΔMAE por região (negativo = bloco hídrico melhor), kg/ha:

| cultura | Sul | Cerrado | Transição | **D** | IC UF×ano | IC bloco |
|---|---:|---:|---:|---:|---|---|
| **milho** | **−45,5** | **+32,7** | −23,6 | **−78,3** | [−131,7; −26,7] | [−127,9; −11,1] |
| soja | −6,8 | +28,2 | +10,6 | −35,0 | [−80,7; +0,7] | [−60,9; −19,2] |
| milho 2ª | −8,8 | +13,7 | +13,3 | −22,5 | [−42,2; +1,4] | [−37,2; −0,5] |

p (bootstrap UF×ano): milho 0,0010; soja 0,059; milho 2ª 0,061.

**Benefício vs. prejuízo (§9.3 do escopo).** No milho: o bloco **melhora** no Sul
(−45,5, com M2 = 2.255,0 → 2.209,5) e **piora** no Cerrado (+32,7). Não é
"menos prejudicial" no Sul: é benéfico em termos absolutos lá e prejudicial aqui.

**Por UF (milho):** RS −68,5 · PR −27,5 · MS +7,0 · GO +21,4 · MT +55,0 · BA
+344,0.

**Por UF × macrorregião (mesmo protocolo):** RS|1 −68,5 · PR|1 −14,5 · PR|2 −34,7
· MS|3 −50,3 · MS|2 +31,6 · GO|3 +13,9 · GO|4 +29,2 · MT|4 +55,0 · BA|4 +324,2.

O detalhe desmonta a leitura regional: **MS-MRS3 (Cerrado) tem Δ = −50,3**,
comportando-se como o Sul, enquanto MS-MRS2 (transição) tem +31,6. E dentro do
GO, as duas macrorregiões do Cerrado diferem (+13,9 vs +29,2).

## 8. Resultados associativos

Modelo *within* de município e ano, agrupamento duplo UF×ano + município:

| cultura | coeficiente da interação (Sul) | EP | p | clusters | n |
|---|---:|---:|---:|---:|---:|
| **milho** | **−1.287,3** | 236 | **1,8×10⁻⁶** | 47 | 5.229 |
| soja | −471,1 | 215 | 0,035 | 39 | 6.590 |
| milho 2ª | −1.440,4 | 530 | 0,011 | 27 | 1.131 |

Unidade: kg/ha por 100 mm de déficit acumulado. Sinal negativo = inclinação mais
negativa no Sul.

**Testes dentro do mesmo estado** (onde a macrorregião varia e a UF não):

| estado | comparação | coeficiente | p |
|---|---|---:|---:|
| PR | MRS 1 × MRS 2 (milho) | **+1.011,7** | **0,0022** |
| MS | MRS 2 × MRS 3 (milho) | +222,2 | 0,110 |
| GO | MRS 3 × MRS 4 (milho) | +54,4 | 0,735 |
| GO | MRS 3 × MRS 4 (milho 2ª) | +3.123,6 | 0,025 |
| MS | MRS 2 × MRS 3 (milho 2ª) | +626,8 | 0,033 |
| PR | MRS 1 × MRS 2 (milho 2ª) | +1.181,7 | 0,002 |

A diferença dentro do PR (+1.012) tem magnitude comparável ao contraste
Sul×Cerrado (−1.287). Ou seja: **existe heterogeneidade de inclinação real, mas
ela não segue a fronteira Sul/Cerrado** — ela aparece também dentro de um único
estado, entre macrorregiões contíguas.

## 9. Estabilidade

| cultura | leave-one-UF-out (6) | leave-one-ano-out (8–9) |
|---|---|---|
| **milho** | **todas negativas**: −40,3 a −150,1 | **todas negativas**: −44,5 a −133,0 |
| soja | todas negativas: −67,0 a −25,9 | **uma positiva** (+3,8) |
| milho 2ª | **signo inverte**: −9,7 a +47,0 | **signo inverte**: −49,6 a +30,9 |

Só o milho é estável nas duas dimensões. A soja e a milho 2ª **não sustentam** a
estabilidade necessária, e isso está registrado mesmo sendo desfavorável.

Na milho 2ª, a exclusão de PR elimina o grupo Sul inteiro (o Sul é apenas PR-MRS1,
388 linhas): o contraste não é estimável sem ele.

## 10. Sensibilidades

D no milho (peso por observação / município / UF):

| variante | D obs | D município | D UF |
|---|---:|---:|---:|
| **primária** (Sul=MRS1, Cerrado=MRS3∪4) | −78,3 | −80,2 | −129,1 |
| Cerrado restrito a MRS 3 | −48,4 | −42,8 | −23,3 |
| Cerrado sem MT | −65,9 | −66,7 | −139,9 |
| Sul ∪ transição | −67,7 | −61,9 | −109,1 |
| agrupamento por região edafoclimática | −91,4 | −97,4 | −85,3 |

Todas negativas, todas na mesma ordem de grandeza. **A descrição é robusta à
classificação** — o que ela não é, é identificável como efeito regional.

**Suporte comum (decis de déficit, milho):** D é negativo em 9 dos 10 decis
(−19,3 a −608,2); o único positivo é +37,0 no decil 1,0–1,5 mm. Portanto a
diferença **não** é apenas composição de suporte.

**Soja:** o oposto. D é −8,2 nos decis baixos, **+4,7 e +23,2** nos decis
intermediários, e −27,0/−369,8 nos dois últimos (este com apenas 37 linhas no
Sul). Ou seja, o agregado da soja é sustentado por uma cauda pequena: **a
replicação na soja não é robusta**.

## 11. Classificação final da hipótese

**Nível E — não identificável.**

Justificativa, pela regra 1 do pré-registro (§6): "se não houver nenhuma UF com
municípios nos dois grupos, a alegação de efeito regional independente de estado
é não identificável, mesmo que D seja grande". Cramér's V = 1,000 nas três
culturas.

O que **não** se está dizendo: que não há diferença. Há, e é grande. O que se
está dizendo é que **não é possível atribuí-la à região em vez do estado**, e que
a própria fronteira não organiza o fenômeno (§8, §10).

Categorias descartadas, com motivo:

* **A** — impossível: não existe amostra não examinada (§3).
* **B** — bloqueada pela precedência de E (regra 1).
* **C/D** — não se aplicam ao milho (estável); aplicar-se-iam à soja e à
  milho 2ª, que por isso ficam como secundárias não sustentadas.
* **F** — não: o IC do milho é estreito e informativo; o problema é identificação,
  não poder.

## 12. Decisão sobre a linha de modelagem

* **M2 permanece o modelo de referência** (reforça D108).
* **Nenhum modelo regional é adotado.** Não há condição territorial de uso a
  definir porque não há efeito regional identificado.
* **Não** se cria interação regional regularizada, nem modelo por UF, nem limiar.
* A linha de **especificação hídrica** está encerrada com a base atual: a V3.3
  mostrou que a forma funcional não melhora a previsão e a V3.4 mostra que a
  heterogeneidade que resta não é regional nem identificável.
* A prioridade passa a ser **cobertura territorial** —
  `docs/V3_4_TERRITORIAL_COVERAGE_GAP_ANALYSIS.md`.

## 13. Limitações

1. **Região aninhada em UF** — a limitação central, não contornável com estes
   dados.
2. **Sem validação independente** — a hipótese nasceu nos mesmos dados.
3. **Classificação de soja aplicada ao milho** — aproximação declarada; não há
   lista municipal oficial equivalente para milho.
4. **MRS 4 ≠ Cerrado** — inclui MT com transição amazônica; a sensibilidade "sem
   MT" está reportada.
5. **2 vs 4 UFs** — nenhum bootstrap de linhas ou de UF×ano representa a
   incerteza do *tratamento*; por isso o leave-one-UF-out é a medida honesta.
6. **Grupos internamente heterogêneos** (MS-MRS3 como exceção).
7. **Associação ≠ causalidade**; e associação ≠ ganho preditivo (§8 vs §7).

## 14. Referências

1. **MAPA (2021/2025).** *Instrução Normativa SPA/MAPA nº 1, de 9 de novembro de
   2021*, anexo atualizado pelas Portarias SPA/MAPA nº 387/2023 e nº 281/2025.
   Macrorregiões sojícolas e regiões edafoclimáticas.
   <https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/programa-nacional-de-zoneamento-agricola-de-risco-climatico/normativos-do-zarc>
   — Usado para: classificação municipal primária. **Limitação:** finalidade é
   indicação de cultivares de soja.
2. **Cameron, A. C., Gelbach, J. B., & Miller, D. L. (2011).** *Robust Inference
   With Multiway Clustering.* JBES, 29(2), 238–249.
   <https://doi.org/10.1198/jbes.2010.07136> — Usado para: agrupamento duplo.
3. **Cameron, A. C., & Miller, D. L. (2015).** *A Practitioner's Guide to
   Cluster-Robust Inference.* JHR, 50(2), 317–372.
   <https://jhr.uwpress.org/content/50/2/317> — Usado para: unidade de
   agrupamento e advertência sobre poucos clusters (aqui, 2 vs 4 UFs no nível do
   tratamento).
4. **Doorenbos, J., & Kassam, A. H. (1979).** *Yield Response to Water.* FAO
   Irrigation and Drainage Paper 33. — Usado para: escala relativa do déficit
   (herdado da V3.3).

## 15. Reprodutibilidade

```
python tools/v34_region_mapping.py      # baixa e parseia a planilha oficial
python tools/v34_coverage.py            # cobertura, suporte, confundimento
python tools/v34_regional_contrast.py --stage main
python tools/v34_regional_contrast.py --stage robustness
python tools/v34_regional_sensitivity.py
python tools/v34_figures.py
pytest geospatial/tests -q
```

| artefato | caminho |
|---|---|
| mapeamento municipal | `geospatial/data/processed/municipality_region_mapping.csv` |
| manifesto do mapeamento (hash, cobertura) | `geospatial/data/manifests/v34_region_mapping.json` |
| cobertura e identificabilidade | `geospatial/data/manifests/v34_coverage_identifiability.json` |
| contraste principal | `geospatial/data/manifests/v34_regional_contrast.json` |
| robustez | `geospatial/data/manifests/v34_regional_robustness.json` |
| sensibilidades | `geospatial/data/manifests/v34_regional_sensitivity.json` |
| Δ por município | `geospatial/data/manifests/v34_municipality_delta/*.csv` |
| figuras | `docs/figures/v34/*.png` |

## 16. Classificação das evidências

| achado | classificação |
|---|---|
| mapeamento municipal da fonte oficial, sem transcrição manual | **validado** (hash + 1.422/1.782 correspondências, 0 duplicados) |
| M2 reproduz a V3.3 | **validado** (diferença só por amostra) |
| D = −78,3 no milho, estável em LOO-UF e LOO-ano | **validado nos protocolos avaliados** (descritivo) |
| diferença de inclinação Sul×Cerrado no milho (p = 1,8×10⁻⁶) | **validado nos protocolos avaliados** |
| descrição robusta a 5 classificações e 3 ponderações | **validado** |
| diferença **não** é só suporte climático (9/10 decis) | **validado** |
| efeito **regional** independente de estado | **não identificável** (Nível E) |
| fronteira Sul/Cerrado como explicação | **não sustentada** (heterogeneidade dentro de estado, MS-MRS3 como exceção) |
| replicação na soja | **não sustentada** (instável por ano e por suporte) |
| replicação na milho 2ª | **não sustentada** (sinal inverte no LOO) |
| confirmação independente | **impossível** — nenhuma amostra não examinada |
| generalização nacional | **não avaliado** — 6 UFs de 27 |
