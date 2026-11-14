# SADEN V3.3 — Forma funcional do balanço hídrico e exposição térmica

**Frente A.** Base: `3bf9360` (V3.2). Data: 2026-11-14.
Pré-registro: `docs/V3_3_FUNCTIONAL_FORM_PREREGISTRATION.md`.

---

## 1. Resumo

A hipótese era que o formato funcional incompleto — precipitação e temperatura
brutas — estaria deixando de capturar mecanismos do balanço hídrico e da
exposição térmica, e que uma representação fisicamente coerente melhoraria a
generalização.

**Resultado: não melhora.** Nenhuma especificação funcional supera M2 fora da
amostra. As três comparações confirmatórias no milho (H1, H2, H4) têm p de
bootstrap de 0,953 / 0,101 / 0,169; após Holm, nenhuma é significativa. O ΔMAE
do bloco hídrico incremental é **+1,3 kg/ha** (IC UF×ano [−47,9; +49,8]) — ou
seja, nada.

O lado **inferencial** é diferente e igualmente informativo: o bloco hídrico tem
associação com a produtividade (Wald p = 0,038 no milho), mas essa associação
**não se converte em ganho preditivo**. Após Holm sobre os três blocos, a
associação hídrica fica em 0,076 (n.s.) e apenas o termo **não linear** sobrevive
(0,041).

Classificação: **Nível B** para a construção hídrica (associação marginal, sem
ganho preditivo); **Nível D** para o ganho de generalização. M2 permanece o
modelo de referência (D108).

---

## 2. Pergunta científica

O formato funcional das variáveis agroclimáticas representa adequadamente os
mecanismos físicos envolvidos? Especificamente: intensidade acumulada de déficit
é suficiente, ou duração, não linearidade e exposição térmica carregam informação
que a forma linear em precipitação/temperatura perde?

Origem do sinal (V3.2, verificado em `v32_slope_tests.json`): no milho, três
variáveis exploratórias sobreviveram a Benjamini–Hochberg — `deficit_cad100`
(p = 0,00024), `degree_days_corrected` (0,00095) e `heat_corrected` (0,00608) —
enquanto precipitação e temperatura brutas não rejeitaram (0,410 e 0,045 →
Holm 0,227). A V3.2 registrou que aquelas rejeições vinham de modelos de **uma**
variável e não identificavam a variável responsável.

## 3. Dados

Painel da V3.1 (19.402 linhas, janela corrigida), mais os descritores de estresse
construídos nesta versão (`v33_water_variables.csv`, gerado por
`tools/v33_water_variables.py` a partir dos mesmos dados diários).

| cultura | linhas | cenário de CAD (D99) | meses medianos na janela |
|---|---:|---|---:|
| milho | 7.616 | 0–60 cm | 3 |
| soja | 8.884 | 0–100 cm | 3 |
| milho 2ª | 2.902 | 0–60 cm | 3 |

## 4. Variáveis

| variável | definição | unidade | origem |
|---|---|---|---|
| `precip_acumulada_mm_corrected` | soma na janela | mm | NASA POWER |
| `temp_media_c_corrected` | média na janela | °C | NASA POWER |
| `deficit_total_mm` | DEF acumulado do balanço | mm | Thornthwaite–Mather + CAD |
| `stress_share` | meses com DEF > 1 mm / meses da janela | fração | idem |
| `max_consecutive_deficit_months` | maior sequência contínua | meses | idem |
| `etr_over_etp` | ETR/ETP acumulados | razão | idem |
| `degree_days_total_corrected` | graus-dia acumulados | °C·dia | perfil térmico |
| `heat_corrected` | dias com Tmax > 35 °C | dias | idem |

**Auditoria de dependência** (`v33_variable_audit.json`, correlação *within* de
município e ano, milho, CAD 0–60):

| par | r | consequência |
|---|---:|---|
| `etr_over_etp` × `deficit_over_etp` | −1,000 | são a mesma variável (DEF = ETP − ETR) |
| `deficit_total_mm` × `etr_over_etp` | −0,972 | intensidade relativa ≈ déficit reescalado |
| `stress_share` × `max_consecutive` | +0,941 | duração e evento não separáveis |
| `heat_corrected` × `deficit_total_mm` | +0,839 | calor e seca vêm juntos |
| `heat_corrected` × `temp_corrected` | +0,760 | calor não é independente da temperatura |
| `deficit_total_mm` × `stress_share` | +0,730 | intensidade e duração compartilham 53% |
| `degree_days_corrected` × `temp_corrected` | +0,020 | **ortogonal** |
| `degree_days_corrected` × `deficit_total_mm` | +0,310 | quase ortogonal |

Essas correlações **determinaram** o desenho: `degree_days` é o único bloco
térmico não redundante; `heat` entra só como sensibilidade; o conjunto completo
tem número de condição ~5×10¹⁵ e não é estimável.

## 5. Pré-registro

`docs/V3_3_FUNCTIONAL_FORM_PREREGISTRATION.md`, escrito antes das estimativas.
Fixo: H1–H6, especificação, modelos, família confirmatória de 3 testes no milho,
regra A–D, robustez. H3 (duração × intensidade) foi declarada **não testável**
antes dos resultados, com a razão medida (r = 0,73 e 0,94).

**Desvio registrado:** o pré-registro fixou a família confirmatória *preditiva*
(3 testes). Não fixou a família dos testes de associação (Wald). Para não ler
p-valores brutos como evidência, apliquei Holm aos 3 blocos dentro de cada
cultura. Isso está rotulado como limite no manifesto
(`association_families[*].preregistered = false` para soja e milho 2ª) e não como
família pré-registrada.

## 6. Justificativa física

* **Balanço hídrico**: Thornthwaite–Mather sequencial, com CAD como capacidade de
  armazenamento e profundidade radicular de D99. O déficit acumulado é a
  intensidade; `stress_share` é a duração; `etr/etp` é o atendimento relativo da
  demanda, que é a escala em que a relação produtividade–água é formulada na
  literatura (Doorenbos & Kassam, 1979; FAO-66).
* **Exposição térmica**: graus-dia acumulam exposição; calor extremo conta dias
  acima de limiar. São conceitos distintos e, nos dados, `heat` é 0,84
  correlacionado com déficit — o que reforça a decisão de não tratá-los como
  independentes.
* **Não linearidade**: um limiar exigiria fonte compatível com cultura, unidade e
  escala; não foi encontrado um limiar defensável para déficit acumulado em mm
  nessas janelas. Por isso a forma não linear pré-registrada é o **quadrático com
  escala fixa** (`(DEF/100)²`), e não um limiar escolhido nos dados.
* **Interação água × calor**: a literatura sobre extremos compostos
  (Nature Reviews Earth & Environment, 2022) e sobre sensibilidade do milho à
  seca (Lobell et al., 2014) sustenta o mecanismo, mas a colinearidade
  (0,84) faz a interação ser fracamente identificada. Registrada como
  **exploratória**.

## 7. Especificação

```
M1                média da UF
M2                precipitação + temperatura + UF        (referência)
M2_WB             déficit + duração + UF
M2_WB_plus        M2 + déficit + duração                 (incremental)
M2_THERM          graus-dia + UF
M2_WB_THERM       déficit + duração + graus-dia + UF
M2_WB_NL          déficit + déficit² + duração + UF
M2_WB_THERM_INT   M2_WB_THERM + (déficit × graus-dia)    (exploratório)
```

Transformações usam **constantes fixas** (÷100, ÷1000). Nenhuma padronização
estimada nos dados → nenhum vazamento por transformação. `wb_deficit_sq` é
exatamente `(deficit/100)²`.

## 8. Validação

Braço **TE** (blocos espaciais e grupos temporais do teste fora do treino), 25
células, equalização estrita por célula (**todas as 25 no alvo** em todos os
modelos), 3 repetições, 1000 reamostragens, semente `20261114`. Mesmas linhas de
teste em todos os modelos (verificado por `row_codes`/`row_years_raw`).

## 9. Inferência

Teste de Wald conjunto do bloco, após transformação *within* de município e ano,
com agrupamento **duplo** por UF×ano e município (D104). Para as diferenças de
MAE, bootstrap pareado com os dois esquemas (bloco e UF×ano) e p-valor de sinal
por bootstrap.

## 10. Resultados preditivos (TE, MAE em kg/ha)

| modelo | milho | soja | milho 2ª |
|---|---:|---:|---:|
| M1 | 1.917,1 | 610,7 | 1.500,8 |
| **M2** | **1.688,6** | **592,2** | **1.272,4** |
| M2_WB | 1.740,6 | 606,2 | 1.467,9 |
| M2_WB_plus | 1.689,9 | 600,4 | 1.282,5 |
| M2_THERM | 1.836,2 | 611,1 | 1.321,8 |
| M2_WB_THERM | 1.724,0 | 607,7 | 1.332,8 |
| M2_WB_NL | 1.741,0 | 606,5 | 1.477,5 |
| M2_WB_THERM_INT | 1.730,2 | 618,0 | 1.334,7 |

M2 é o melhor em todas as culturas. Qualquer bloco adicionado piora.

## 11. Comparações pareadas

ΔMAE = MAE(modelo) − MAE(referência); **negativo = melhor**.

### 11.1. Milho — família confirmatória

| # | comparação | ΔMAE | IC bloco | IC UF×ano | p (UF×ano) | Holm |
|---|---|---:|---|---|---:|---:|
| H1 | M2_WB_plus − M2 | +1,33 | [−28,1; 43,9] | [−47,9; 49,8] | 0,953 | 0,953 |
| H4 | M2_WB_THERM − M2_WB_plus | +34,13 | [−34,7; 100,3] | [−16,1; 77,8] | 0,167 | 0,334 |
| H2 | M2_WB_NL − M2_WB_plus | +51,10 | [−36,5; 129,4] | [−10,8; 103,8] | 0,101 | 0,303 |

**Nenhuma rejeita.** Não há ganho de generalização.

### 11.2. Comparações secundárias

| cultura | comparação | ΔMAE | IC UF×ano |
|---|---|---:|---|
| soja | M2_WB_plus − M2 | +8,20 | [−6,5; 27,5] |
| soja | M2_WB_NL − M2_WB_plus | +6,11 | [−14,4; 26,0] |
| milho 2ª | M2_WB_plus − M2 | +10,11 | [−3,2; 26,5] |
| milho 2ª | M2_WB_NL − M2_WB_plus | +194,98 | [86,5; 294,0] |
| milho | M2_WB − M2 | +51,97 | [−22,3; 130,1] |
| milho | M2_THERM − M2 | +147,65 | [45,4; 221,6] |
| milho | INT − M2_WB_THERM | +6,15 | [0,3; 12,6] |

Duas leituras: (i) o bloco hídrico **sozinho** é pior que o clima bruto (M2_WB −
M2 = +52 no milho); (ii) no milho 2ª a não linearidade é **significativamente
pior** (+195, IC exclui zero) — o termo quadrático superajusta.

## 12. Resultados inferenciais (within, UF×ano + município)

| cultura | bloco | Wald/gl | p | p Holm (3 blocos) |
|---|---|---|---:|---:|
| milho | água além do clima | 3,50 | 0,0382 | 0,0763 |
| milho | térmico além da água | 0,00 | 0,9612 | 0,9612 |
| milho | não linearidade | 6,54 | 0,0138 | **0,0414** |
| soja | água além do clima | 3,06 | 0,0584 | 0,1167 |
| soja | não linearidade | 5,91 | 0,0198 | 0,0593 |
| milho 2ª | água além do clima | 3,21 | 0,0539 | 0,1617 |
| milho 2ª | não linearidade | 2,76 | 0,1067 | 0,2134 |

Só a **não linearidade no milho** sobrevive ao Holm. Mas essa mesma não
linearidade **piora** a previsão em +51,1 (IC inclui zero) e +195 no milho 2ª
(IC exclui zero). Associação e utilidade preditiva divergem — e a associação não
autoriza uso preditivo.

## 13. Resultados por UF

ΔMAE de `M2_WB_plus` contra `M2`, por UF (TE, kg/ha; negativo = bloco hídrico
melhor):

| UF | milho M2 | milho M2_WB_plus | Δ milho | Δ soja | Δ milho 2ª |
|---|---:|---:|---:|---:|---:|
| PR | 1.862,7 | 1.828,9 | **−33,8** | −4,7 | +5,4 |
| RS | 2.380,0 | 2.326,9 | **−53,1** | −5,2 | — |
| MS | 1.578,7 | 1.582,8 | +4,1 | +49,9 | +27,7 |
| GO | 1.046,9 | 1.092,6 | +45,7 | +12,5 | +19,4 |
| MT | 1.042,0 | 1.136,1 | +94,1 | +58,2 | +6,0 |
| BA | 3.642,6 | 3.816,1 | +173,5 | — | — |

**O efeito líquido nulo esconde sinais opostos.** O bloco hídrico melhora a
previsão nos dois estados do Sul (PR −33,8; RS −53,1) e piora em todo o Cerrado,
de forma crescente (MS +4,1 → BA +173,5). Isso é consistente com o
leave-one-UF-out: remover PR eleva o Δ agregado para +103,5 e remover RS para
+13,1, ou seja, esses dois estados são os que sustentam a parte negativa.

A leitura correta não é "o bloco hídrico é inútil em toda parte", e sim "ele
reproduz uma relação que existe no Sul e não no Cerrado, sem ganho líquido". Como
o agregado não melhora e o padrão não foi pré-registrado como hipótese regional,
isso fica como **observação exploratória** (§19), não como achado.

## 14. Estabilidade (H6)

ΔMAE de M2_WB_plus − M2, milho:

| UF removida | ΔMAE | | Ano removido | ΔMAE |
|---|---:|---|---|---:|
| BA | +43,3 | | 2018 | −0,1 |
| GO | +63,7 | | 2019 | −7,3 |
| MS | +14,4 | | 2020 | +19,8 |
| MT | +14,1 | | 2021 | +57,8 |
| PR | +103,5 | | 2022 | +37,8 |
| RS | +13,1 | | 2023 | +45,8 |
| | | | 2024 | +17,1 |
| | | | 2025 | +8,7 |

Nenhuma UF invertida em favor do bloco hídrico no agregado: em todas as 6
exclusões o Δ continua positivo. Em 6 dos 8 anos o bloco piora; nos dois
restantes a diferença é ≈ 0 (−0,1 e −7,3 kg/ha). H6 não chega a ser testada no
sentido de "estabilidade do ganho", porque **não há ganho líquido** — apenas o
padrão regional de §13 (Sul a favor, Cerrado contra).

Soja repete o mesmo padrão regional, em escala menor: negativo em PR (−4,7) e RS
(−5,2), positivo em GO (+12,5), MS (+49,9) e MT (+58,2). Milho 2ª é positivo em
todas as quatro UFs. O sinal regional Sul-versus-Cerrado aparece nas duas
culturas de verão, o que reforça que **não é ruído** — mas continua sendo um
padrão observado, não um ganho agregado.

## 15. Limitações

1. **Resolução mensal.** O balanço sequencial é mensal; duração em dias não
   existe. H3 (duração × intensidade) é **não identificável**, não "rejeitada".
2. **Colinearidade estrutural.** Água, calor e temperatura compartilham 0,71–0,84.
   Nenhum desenho observacional separa esses mecanismos com este painel.
3. **CAD é cenário.** 0–60/0–100 cm vêm de D99; a CAD 0–100 e 0–200 deixa 54% e
   86% das linhas sem nenhum mês de estresse, o que degenera as variáveis de
   duração.
4. **Não linearidade testada só na forma quadrática.** Splines ou limiares não
   foram testados por falta de limiar defensável; o resultado negativo vale para
   a forma testada.
5. **Cobertura de 5–6 UFs de 27.** Nenhuma generalização nacional.
6. **Associação ≠ causalidade.** Nenhum coeficiente here é interpretado como
   efeito causal.

## 16. Conclusão

A forma funcional testada **não** melhora a representação preditiva da relação
clima–produtividade. M2 permanece o melhor modelo nas três culturas. Há
associação entre o bloco hídrico e a produtividade (marginal após multiplicidade)
e evidência de não linearidade no milho, mas nenhuma das duas se converte em
generalização. O pré-registro previa esse desfecho como válido: manter M2.

O único padrão que merece continuidade é o **gradiente regional** de §13: o bloco
hídrico ajuda em PR e RS e atrapalha no Cerrado, nas duas culturas de verão. Ele
não foi pré-registrado, não sobrevive como ganho agregado e não autoriza mudança
de modelo. Fica registrado como hipótese para a V3.4, a ser testada com
pré-registro próprio — não como achado desta versão.

## 17. Referências

1. **Doorenbos, J., & Kassam, A. H. (1979).** *Yield Response to Water.* FAO
   Irrigation and Drainage Paper 33, Roma.
   <https://www.fao.org/4/i2800e/i2800e02.pdf> (FAO-66, que retoma e atualiza o
   procedimento). — Usado para: escala relativa ETR/ETP como forma fisicamente
   motivada da relação produtividade–água.
2. **Steduto, P., Hsiao, T. C., Fereres, E., & Raes, D. (2012).** *Crop Yield
   Response to Water* (FAO-66). — Base do conceito de resposta relativa usado em
   §6.
3. **Lobell, D. B., Roberts, M. J., Schlenker, W., Costa-Roberts, N., & Ortmans,
   B. (2014).** *Greater Sensitivity to Drought Accompanies Maize Yield Increase
   in the U.S. Midwest.* Science, 344(6183), 516–519.
   <https://doi.org/10.1126/science.1251423> — Usado para: sensibilidade do milho
   à seca como hipótese plausível, não como evidência para o SADEN.
4. **Nature Reviews Earth & Environment (2022).** *Compound heat and moisture
   extreme impacts on global crop yields.*
   <https://doi.org/10.1038/s43017-022-00368-8> — Usado para: justificar a
   hipótese de interação água × calor (registrada como exploratória).

Nenhuma referência é usada como evidência empírica do SADEN. Os números vêm do
painel.

## 18. Reprodutibilidade

```
python tools/v33_water_variables.py
python tools/v33_variable_audit.py
python tools/v33_functional_form.py --stage main
python tools/v33_functional_form.py --stage robustness
```

| artefato | caminho |
|---|---|
| descritores de estresse | `geospatial/data/processed/v33_water_variables.csv` |
| metadados dos descritores | `geospatial/data/manifests/v33_water_variables.json` |
| auditoria de dependência | `geospatial/data/manifests/v33_variable_audit.json` |
| modelos e inferência | `geospatial/data/manifests/v33_functional_form.json` |
| robustez | `geospatial/data/manifests/v33_functional_robustness.json` |
| testes | `geospatial/tests/test_v33_functional_form.py` |

## 19. Classificação

| achado | classificação |
|---|---|
| M2 reproduz a V3.1 (592,19 / 1.688,58 / 1.272,40) | **validado** |
| bloco hídrico não melhora a previsão em TE | **validado nos protocolos avaliados** |
| não linearidade não melhora a previsão | **validado nos protocolos avaliados** |
| exposição térmica (graus-dia) não acrescenta | **validado nos protocolos avaliados** |
| bloco hídrico tem associação (Holm 0,076, n.s.) | **não conclusivo** |
| não linearidade tem associação no milho (Holm 0,041) | **validado nos protocolos avaliados**, sem utilidade preditiva |
| duração × intensidade | **não identificável** (resolução mensal) |
| interação água × calor | **não conclusivo** (colinearidade 0,84) |
| gradiente regional do bloco hídrico (Sul a favor, Cerrado contra) | **exploratório** — observado nas duas culturas de verão, não pré-registrado, sem ganho agregado |
| ganho de generalização | **não sustentado** — Nível D |
