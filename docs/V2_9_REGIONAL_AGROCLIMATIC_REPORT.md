# SADEN V2.9 — Regionalização agroclimática, heterogeneidade e CAD

> Etapa V2.9. Documento de encerramento: o que foi auditado, o que mudou em
> relação à V2.8, o que se sustenta e o que fica pendente.
>
> Decisões: D90 (equalização por célula), D91 (modelos aninhados), D92 (escala
> do bloco), D93 (CAD), D94 (dicionário ZARC e correção por classe).
> Continuidade: `docs/execution/v2.9/MASTER_STATUS.md`.

---

## 1. Resumo executivo

A V2.9 teve três resultados que mudam a leitura das versões anteriores.

1. **A conclusão da V2.8 sobre tamanho de amostra se sustenta — mas por um
   motivo que precisou ser auditado.** A equalização da V2.8 era *global*, não
   por célula: o braço `TE` treinava com 5.401 linhas em média (alvo 5.686) e
   ficava abaixo do alvo em **11 de 25** células. Refeita a comparação com
   equalização **estrita por célula** (25/25 células no alvo nos quatro
   braços), as MAEs mudam em ≤ 5,1 kg/ha e os efeitos permanecem nos mesmos
   intervalos. A conclusão sobrevive; uma comparação limítrofe muda de status.

2. **O valor incremental do clima, medido além da região, é bem menor do que
   o "ganho territorial" publicado e depende do ano.** Com modelos aninhados
   M0 (média nacional) → M1 (média da UF) → M2 (UF + clima), na soja o clima
   só acrescenta quando o ano é compartilhado entre treino e teste
   (`M2−M1` = −13,3 em SS e −19,2 em SE); no protocolo mais estrito (bloco e
   ano separados) o efeito é −6,3 [−26,8;+10,4] para a família meteorológica e
   o modelo hídrico **piora** (+20,5 [+9,6;+31,7]). No milho 2ª safra o clima
   acrescenta nos quatro braços (−267,2 [−413,8;−35,1] em TE).

3. **A heterogeneidade por classe de ciclo que a V2.8 reportou como inversão
   de sinal não se sustenta.** O dicionário oficial do ZARC foi localizado
   (MAPA): `Cod_Ciclo` 20/21/22 são **Grupo I/II/III**, não cultivar. No teste
   formal de interação, a temperatura da soja **não difere** entre grupos
   (p=0,38); o déficit hídrico difere (p=0,003). O +182,7 vs −65,0 era
   artefato de estimar cada classe com a sua própria transformação *within*.

Além disso: a **CAD foi ampliada** com uma estratégia de aquisição validada
(escala WCS 0,2 → ~450 m, volume 60× menor), e a sensibilidade do balanço
hídrico à CAD por município foi medida: o déficit anual cai em média ~19% com
a CAD de 0–100 cm, mas a razão **não é uniforme** entre municípios — que é o
que importa para a inferência.

---

## 2. Estado inicial da V2.8

Branch `v2/temporal-spatial-generalization` em `a36e6be`, publicada, árvore
limpa. Bundle `SADEN_V2_8_RECOVERY_2026-11-14` conferido por `list-heads`
(26 refs), SHA-256 `73297BAB…46890AA8`, `git bundle verify` *okay*. V1
(`v1-final` = `3f7ad33`) e `main` intactas. Suíte de referência: **338/338**.

## 3. Branch e commits da V2.9

| Commit | Conteúdo |
|---|---|
| `3818baa` | equalização estrita por célula e métricas por repetição (D90) |
| `a843ab0` | modelos aninhados M0/M1/M2 e escala do bloco (D91, D92) |
| `4d7af5b` | dicionário ZARC, teste de interação e cobertura (D94, D95) |
| commit final | CAD estratificada, balanço hídrico, síntese e publicação |

Branch `v2/regional-agroclimatic-robustness`, base `a36e6be`.

## 4. Auditoria da equalização (D90)

Diagnóstico por célula (bloco × ano), sem ajustar modelos:

| Cultura | braço | média | mínimo | máximo | células abaixo do alvo |
|---|---|---|---|---|---|
| soja | SS/SE/TS | 5.686 | — | — | 0 |
| soja | **TE** | **5.401** | **4.308** | 6.792 | **11/25** |
| milho | TE | 4.874 | 3.514 | 6.323 | 13/25 |
| milho 2ª | TE | 1.857 | 1.418 | 2.318 | 10/25 |

A média do `TE` coincidia com o alvo; **11 das 25 células** ficavam abaixo
dele. Nenhuma célula tinha menos de 1.400 linhas.

Equalização estrita por célula (`equalize="per_cell"`; alvo = menor conjunto
entre os quatro braços), `climate_plus_state`, 5 repetições:

| Cultura | modo | SS | SE | TS | TE |
|---|---|---|---|---|---|
| soja | global | 552,8 | 559,4 | 588,9 | 604,3 |
| soja | **per_cell** | 552,7 | 559,0 | 589,7 | 604,4 |
| milho | global | 1.493,3 | 1.662,9 | 1.515,3 | 1.717,8 |
| milho | **per_cell** | 1.489,8 | 1.661,2 | 1.516,7 | 1.718,4 |
| milho 2ª | global | 1.165,8 | 1.205,3 | 1.177,6 | 1.234,0 |
| milho 2ª | **per_cell** | 1.164,1 | 1.209,6 | 1.179,9 | 1.233,7 |

Diferença máxima: **5,1 kg/ha**. Efeitos (per_cell):

| Cultura | espaço (SS−SE) | tempo (SS−TS) |
|---|---|---|
| soja | −6,3 [−14,3;+3,0] n.s. | −37,0 [−47,3;−23,8] |
| milho | −171,5 [−331,6;−32,5] | −26,9 [−46,2;−9,0] |
| milho 2ª | **−45,5 [−79,0;−0,8]** | −15,8 [−31,8;−8,3] |

**Conclusão:** a interpretação da V2.8 (a redução de amostra não explica a
inversão) **se sustenta**. Ressalva registrada: no milho 2ª safra o efeito
espacial passa de não significativo para marginalmente significativo.

Métricas por repetição passaram a ser reportadas separadamente (as repetições
de treino **não** são observações de teste independentes); a MAE agregada
coincide com a média das MAEs por repetição.

## 5. Estado do modelo regional

`climate_plus_state` (M2) é o modelo de referência: `y ~ 1 + clima + dummies
de UF`, dummies construídas **só** com o treino, categoria de referência
estável (primeira UF em ordem), UF ausente cai no intercepto. O fallback foi
instrumentado e é **0,0%** em todos os braços deste desenho — ele só seria
acionado num leave-one-UF-out. `climate_only` (M0b) permanece para a
comparação histórica com a V2.6/V2.7.

## 6. Comparação de baselines

| Referência | O que é | Disponibilidade |
|---|---|---|
| **M0** média nacional | média do treino | sempre; ignora região |
| **M1** média da UF | média por UF do treino | **ex ante** (histórico de outras municípios da UF) |
| M1b média UF×ano | média por UF e ano do treino | contemporânea — **diagnóstico**, não operacional |

Nenhuma usa produtividade do teste. Nenhuma usa informação posterior à data
da previsão.

## 7. Valor incremental do clima (M2 − M1)

Igualdade de informação (mesmo treino, mesmos casos de teste), equalização por
célula, IC por bootstrap de bloco:

| Cultura | família | SS | SE | TS | TE |
|---|---|---|---|---|---|
| soja | B | −13,3 [−25,9;−0,8] | −19,2 [−35,2;−3,9] | +1,5 [−13,3;+13,2] | −6,3 [−26,8;+10,4] |
| soja | D | +1,7 [−6,6;+9,4] | −6,6 [−13,4;+0,6] | **+26,3 [+16,4;+36,6]** | **+20,5 [+9,6;+31,7]** |
| milho | B | −101,0 [−217,8;+15,3] | **−216,1 [−373,0;−48,2]** | −69,7 [−176,6;+34,1] | **−198,7 [−355,8;−31,3]** |
| milho_2 | B | **−169,3 [−285,7;−19,6]** | **−257,4 [−402,0;−31,5]** | **−161,5 [−279,4;−17,4]** | **−267,2 [−413,8;−35,1]** |

Leitura:

* **soja** — o clima acrescenta **apenas enquanto o ano é compartilhado**. No
  braço mais estrito (TE) nenhuma família é significativa e a família hídrica
  é significativamente **pior** que a média da UF. Para a soja, o "ganho
  territorial" das versões anteriores era, em boa parte, informação do ano.
* **milho** — acrescenta de forma heterogênea: significativo em SE e TE para a
  família meteorológica, não significativo em SS/TS.
* **milho 2ª safra** — a família meteorológica acrescenta **nos quatro
  braços**, inclusive no mais estrito; as famílias térmica e hídrica não.

Por UF (exemplo, milho B, SS), o delta M2−M1 vai de −278,8 (PR) a +156,3 (MS):
a resposta climática **não é homogênea** entre UFs.

## 8. Heterogeneidade espacial do milho

O efeito do bloco no milho (250 km, `climate_plus_state`) é −170,8
[−330,6;−32,4]. A decomposição por UF mostra que ele **não é nacional**:

| UF | MAE bloco compartilhado | MAE bloco removido | Δ |
|---|---|---|---|
| PR | 1.477,3 | 1.898,7 | **+421,4** |
| BA | 3.127,0 | 3.417,9 | +291,0 |
| MS | 1.428,0 | 1.598,9 | +170,9 |
| GO | 1.003,6 | 1.033,4 | +29,7 |
| MT | 932,6 | 949,9 | +17,3 |
| RS | 2.344,3 | 2.247,6 | −96,7 |

Como o modelo já contém dummies de UF, o efeito medido é **heterogeneidade
dentro da UF**: remover um bloco de PR custa 421 kg/ha, enquanto em GO/MT é
quase nulo. A hipótese de um gradiente nacional não é sustentada pelos dados;
a de heterogeneidade regional concentrada nos maiores produtores, sim.

## 9. Sensibilidade à escala do bloco (D92)

Efeito espacial (SS−SE) por escala, `climate_plus_state`, sem reotimizar a
escolha de 250 km:

| Escala | blocos (soja/milho/milho 2ª) | soja | milho | milho 2ª |
|---|---|---|---|---|
| 150 km | 107/106/65 | +4,4 [−1,5;+10,5] | −47,1 [−99,4;−7,5] | +6,6 [−12,6;+22,4] |
| **250 km** | **46/49/30** | −6,6 [−15,2;+2,5] | −170,8 [−330,6;−32,4] | −42,0 [−74,0;+1,9] |
| 400 km | 23/26/18 | +2,7 [−7,5;+11,5] | −152,4 [−266,7;−47,8] | +22,6 [0,0;+39,5] |
| 600 km | 14/15/9 | −87,0 [−122,8;−14,7] | −415,1 [−694,8;−34,4] | −19,3 [−114,3;+40,5] |

O efeito do milho aparece a partir de 250 km e é pequeno a 150 km — bloco
pequeno demais para remover informação útil. Em 600 km restam 14–15 blocos: o
valor **não é estimativa estável** (poder baixo, treino muito reduzido) e é
reportado apenas como limite superior. A soja é insensível à escala em
150–400 km.

## 10. Expansão da CAD (D93)

**Estratégia validada.** O WCS 2.0.1 do GeoInfo aceita a extensão de escala:
`scaleFactor=0.2` devolve a mesma camada a ~450 m e reduz o volume em ~60×
(medido: 4,195 MB → 0,066 MB por janela de 0,5°; 0,3 s por requisição).
`scaleFactor` > 1 **aumenta** a resolução (não serve para reduzir), e
`scalesize` não é suportado (HTTP 404).

**Validação.** Piloto estratificado por UF (18 municípios): CAD 0–100 cm entre
**112,1 e 200,6 mm**, mediana **161,5** — compatível com a amostra da V2.7 em
resolução nativa (126–240 mm, mediana 159). A agregação em 450 m reproduz a
de 90 m para fins de mediana municipal.

**Custo medido.** ~15 s por município (6 camadas sequenciais). A cobertura dos
1.296 municípios do painel custaria ~5 h; por isso a V2.9 entrega uma
**amostra estratificada por UF e por porte de área** (120 municípios) e
registra o plano para a cobertura completa (retomável, com cache local).

**Correção durante a implementação.** A CAD por pixel usava inicialmente
todas as seis camadas para qualquer profundidade, o que atribuía à "0–100 cm"
o valor de 0–200 cm. Corrigido: cada profundidade usa apenas as suas camadas,
e a distribuição por pixel passou a ser calculada por profundidade.

**Agregação.** Por bbox municipal (não pelo polígono), com mediana, p10, p90,
fração válida e distribuição **por pixel**. A limitação é explícita: o bbox
inclui área vizinha em municípios de forma irregular; a mediana é robusta a
uma minoria de pixels vizinhos, não a todos.

**Licença.** CC BY-NC 3.0 BR (uso não-comercial). Os dados ficam fora do Git e
não são redistribuídos; o manifesto guarda a citação e a licença.

## 11. Resultados do balanço hídrico

Método: balanço anual sequencial (Thornthwaite & Mather, 1955), ET0 FAO-56,
mesma implementação do painel; compara-se CAD = 50 mm (referência da V2.6)
com a **CAD oficial do próprio município** (0–100 cm, mediana por pixel).

<!-- RESULTADOS_CAD_BALANCO -->

## 12. Profundidade radicular (não conclusivo)

Não foi atribuída profundidade radicular por cultura: exigiria fonte
cultivar-específica, e inventá-la violaria a regra de procedência. Foram
usados **perfis publicados** (0–60, 0–100, 0–200 cm) como cenários
explicitamente identificados.

Observação quantitativa que dispensa a atribuição de uma raiz específica: com
AW ≈ 2,2 mm/cm, os 50 mm da V2.6 correspondem a **~23 cm** de solo — mais
raso que qualquer zona radicular de soja ou milho. O cenário da V2.6 não é
"conservador": é agronomicamente implausível como capacidade de zona
radicular, e a sua coincidência com uma referência do MAPA para textura média
não resolve essa diferença.

## 13. Documentação do ZARC (D94)

O dicionário oficial foi localizado no Portal de Dados Abertos do MAPA
(`dicionario-de-dados-tabua-de-risco-2026.pdf`, consultado em 2026-11-14,
licença CC-BY):

* `Cod_Ciclo`: 13 Perene · 19 Semiperene · **20 Grupo I · 21 Grupo II ·
  22 Grupo III** · 24 Grupo IV · 25 Grupo V · 26 Grupo VI.
* `Cod_Solo`: 1 Arenoso · 2 Textura Média · 3 Argiloso · 11–16 AD1–AD6.

**Grupo de ciclo não é cultivar**, e o documento **não** rotula os grupos como
precoce/médio/tardio — esse rótulo não foi atribuído. A distribuição no painel
é concentrada: soja 89% Grupo III; milho 79% Grupo III; milho 2ª 62% Grupo II
e 38% Grupo I.

## 14. Resultados por classe de ciclo

Teste formal de interação (`y_w = b1·x_w + b2·(x·I_grupo)_w`, within por
município e ano, erro agrupado por bloco, `b2` = diferença de inclinação):

| Cultura | déficit hídrico | temperatura | precipitação |
|---|---|---|---|
| soja | **−1,194 (t=−3,16; p=0,003)** | −3,98 (t=−0,88; p=0,38) | −0,075 (p=0,65) |
| milho | −2,612 (t=−1,39; p=0,17) | −22,9 (t=−1,60; p=0,12) | −1,017 (t=−2,05; **p=0,046**) |
| milho 2ª | −0,727 (p=0,21) | +0,50 (p=0,91) | +0,161 (p=0,66) |

**Correção da V2.8:** a "inversão de sinal" da temperatura na soja **não
existe**. O contraste entre +182,7 (t=+4,38, Grupo II) e −65,0 (t=−3,18,
Grupo III), estimados separadamente, vinha de cada classe ter a sua própria
transformação *within* e a sua própria amostra. O teste formal mostra
diferença não significativa. O déficit hídrico da soja difere de forma
robusta. No milho, só a precipitação é marginal (p=0,046 sem ajuste para 9
testes); após multiplicidade, **nenhuma diferença entre grupos sobrevive**.

## 15. Diagnóstico territorial (cobertura)

Na mesma população (linhas `paired_usable` de NASA POWER): **19.402 linhas**,
**1.296 municípios**, 46 (soja) / 49 (milho) / 30 (milho 2ª) blocos de 250 km,
5–6 UFs, 8–9 anos.

<!-- RESULTADOS_COBERTURA -->

Nenhuma expansão do painel é proposta: as lacunas que limitam as conclusões
são de **CAD**, de **estrutura de ciclo** (3 grupos, um deles com 89% das
linhas) e de **número de UFs** — não de quantidade de linhas.

## 16. Testes

| Suíte | Resultado |
|---|---|
| Offline (`geospatial/tests`) | **354/354** (338 da V2.8 + 16 da V2.9) |
| Externos opt-in | 10/10 (V2.8; não reexecutados) |

Novos testes: equalização estrita por célula (quatro braços com o mesmo
tamanho em todas as células; células abaixo do mínimo caídas para todos;
conjunto de teste idêntico), métricas por repetição, dicionário do ZARC
(rótulos e códigos desconhecidos) e teste de interação (detecta diferença
verdadeira, não inventa sob a nula, EP, IC e casos degenerados).

## 17. Fontes

NASA POWER (série diária), INMET (validação, inalterada), PAM/SIDRA 5457,
ZARC/MAPA (Tábua de Risco + dicionário de dados oficial), Embrapa
Solos/GeoInfo (Vasques et al., 2021; CC BY-NC 3.0 BR), FAO-56, Thornthwaite &
Mather (1955). Nenhuma credencial criada; ERA5-Land segue bloqueado (D83).

## 18. Decisões metodológicas

D90 equalização por célula · D91 modelos aninhados M0→M1→M2 · D92 escala do
bloco é escolha de desenho · D93 CAD (unidade, profundidade, cobertura,
licença) · D94 dicionário ZARC e correção da leitura por classe.

## 19. Limitações

1. A média UF×ano é contemporânea: diagnóstico, nunca referência operacional.
2. O fallback de UF não é exercitado neste desenho (0,0%); só um
   leave-one-UF-out o acionaria.
3. A CAD cobre uma amostra estratificada, não o painel inteiro; a agregação é
   por bbox, não pelo polígono.
4. Profundidade radicular por cultura não foi atribuída (sem fonte
   cultivar-específica).
5. Em 600 km restam 14–15 blocos: os valores dessa escala têm poder baixo.
6. Nenhuma conclusão causal; associação, previsão e generalização permanecem
   separadas.
7. O painel cobre 5–6 UFs: **não** há base para generalização nacional.

## 20. Pendências

* Concluir a extração da CAD para os 1.296 municípios (plano validado; ~5 h).
* Integrar a CAD por município ao déficit do painel e reestimar os
  coeficientes (a heterogeneidade da razão é o que altera a inferência).
* Obter fonte cultivar-específica para profundidade radicular.
* Investigar o mecanismo da heterogeneidade dentro da UF no milho (PR/MS).
* ERA5-Land (D83) e CHIRPS/ARCO (sem DNS) seguem bloqueados.

## 21. Recomendações para a V3.0

1. **Reportar sempre M0 e M1** e o incremento M2−M1; o "ganho contra a média
   nacional" não descreve valor incremental do clima.
2. **Não usar o ano compartilhado como capacidade preditiva**: qualquer
   alegação de generalização deve vir do braço TE.
3. **Concluir a CAD** e reestimar com a heterogeneidade preservada.
4. **Tratar o bloco como dimensão de desenho** e reportar 250/400 km, com o
   número de blocos; 600 km só com poder declarado.
5. **Manter o ZARC como grupo de ciclo**, sem rótulo de cultivar.
6. Manter a **Ridge** como único modelo de preços; a V2.9 não toca nela.
