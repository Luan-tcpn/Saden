# SADEN V3.0 — CAD integrada, painel reconstruído e generalização territorial

> Etapa V3.0. Documento de encerramento: o que foi integrado, o que mudou em
> relação às versões anteriores e o que **não** se confirmou.
>
> Decisões: D96 (aquisição por UF com máscara de polígono), D97 (defeito da
> janela ZARC), D98 (a CAD não melhora a predição), D99 (profundidade
> radicular). Continuidade: `docs/execution/v3.0/MASTER_STATUS.md`.

---

## 1. Resumo executivo

A V3.0 fechou a lacuna de solo que a V2.9 havia deixado aberta — e, ao fechar,
encontrou um defeito de janela que afetava **todas** as variáveis ambientais do
painel e um resultado negativo que precisa ser registrado.

1. **A CAD está completa e correta geometricamente.** 1.296 de 1.296
   municípios do painel, **0 sem dado**, adquiridos em **71 s** com 36
   requisições (uma por UF e camada) e agregados pelo **polígono oficial**.
   CAD 0–100 cm: 105,1–256,9 mm (mediana 174,5).
2. **A decimação para ~450 m é inócua para as estatísticas municipais.**
   90 m vs 450 m: mediana 161,05 vs 161,03 mm, correlação **0,99992**. O bbox
   da V2.9 diferia do polígono em 0,85 mm (mediana) e até 10,3 mm.
3. **A janela ZARC do painel histórico perde o último mês** (D97): 28.282 de
   40.990 linhas; nas 19.402 analíticas, todas perdem ~31 dias. Corrigir a
   janela (mesma CAD) eleva o déficit em 23,6% (mediana) e a precipitação/ET0
   da janela em +135/+165 mm.
4. **A CAD oficial não melhora a predição** (D98). Em TE, nenhuma
   especificação com CAD oficial supera a CAD de 50 mm com janela corrigida;
   na soja, o déficit da janela histórica era **pior que a média da UF**
   (+10,6 kg/ha, IC 0,7–21,5) e a correção da janela reverte o sinal.
5. **A CAD não explica a heterogeneidade espacial do milho.** O efeito do
   bloco **cresce** de −209,5 (histórico) para −286,1 (0–200 cm): o problema
   não era representação do solo.
6. **A associação é robusta à definição de déficit.** O coeficiente da soja
   fica em −2,3 a −2,5 enquanto a média do déficit cai de 138,5 para 13,8 mm —
   a CAD reescala quase proporcionalmente e não muda a inferência.

---

## 2. Estado inicial da V2.9

Branch `v2/regional-agroclimatic-robustness` em `adb525f`, publicada, árvore
limpa. Bundle conferido por `list-heads` (27 refs), SHA-256
`7FDB0A74…38FA915`, `git bundle verify` *okay*. V1 (`v1-final` = `3f7ad33`),
`main` e V2.8 (`a36e6be`) intactas. Suíte de referência: **364/364**.

## 3. Branch e commits da V3.0

Branch `v3/cad-integrated-agroclimatic-panel`, base `adb525f`.

| Commit | Conteúdo |
|---|---|
| checkpoint 1 | aquisição por UF, validação de resolução, painel recalculado |
| checkpoint 2 | modelos com CAD, associação, síntese e publicação |

## 4. Auditoria do piloto CAD

O piloto da V2.9 (120 municípios, bbox, 450 m) foi recuperado e reexecutado em
outra unidade: **1 requisição por UF e camada** em vez de 6 por município.

| Item | V2.9 (por município) | V3.0 (por UF) |
|---|---|---|
| requisições | ≈7.800 | **36** |
| tempo | ≈5 h (estimado) | **71 s** |
| agregação | bbox | **polígono municipal** |

## 5. Comparação 90 m e 450 m

Mesma área (janela de ±0,35° em torno do centroide, restrita ao polígono),
18 municípios, 3 por UF:

| Estatística | 90 m | 450 m | dif. média | dif. absoluta mediana | correlação |
|---|---|---|---|---|---|
| mediana | 161,05 | 161,03 | +0,21 | 0,15 | **0,99992** |
| desvio-padrão | 11,81 | 11,70 | −0,02 | 0,12 | 0,99931 |
| p10 | 141,22 | 141,64 | +0,13 | 0,20 | 0,99995 |
| p90 | 172,25 | 172,38 | +0,08 | 0,24 | 0,99982 |

**Conclusão:** a decimação preserva a distribuição municipal — inclusive o
desvio-padrão, que era a preocupação legítima (perda de variabilidade). Não foi
necessário adotar resolução adaptativa.

**bbox vs polígono** (450 m, 18 municípios): diferença média −0,06 mm, mediana
absoluta 0,85 mm, máxima 10,3 mm, correlação 0,994. O bbox superestima em
municípios de forma irregular; o polígono remove esse viés.

## 6. Método de aquisição

`tools/v30_cad_acquire.py`:

* uma janela por UF (bbox de todos os municípios da UF no painel) × 6 camadas;
* `scaleFactor=0.2` (~460 m);
* máscara do polígono oficial (`rasterio.features.geometry_mask`,
  `all_touched=True`);
* CAD integrada **por pixel** em 0–60, 0–100 e 0–200 cm
  (`soil.pixel_capacity_mm`, só as camadas do perfil);
* estatísticas da distribuição municipal: média, mediana, desvio, p10, p25,
  p75, p90, mínimo, máximo, fração válida;
* retomada por UF (manifesto gravado após cada UF).

## 7. Cobertura municipal

| UF | municípios | CAD 0–100 mediana | p10 | p90 |
|---|---|---|---|---|
| MS | 77 | 138,4 | 117,3 | 154,2 |
| MT | 125 | 143,9 | 128,2 | 156,9 |
| BA | 31 | 162,6 | 145,2 | 167,2 |
| GO | 214 | 168,7 | 149,6 | 174,7 |
| PR | 394 | 177,1 | 131,8 | 198,0 |
| RS | 455 | 195,1 | 177,0 | 204,4 |
| **total** | **1.296** | **174,5** | 134,9 | 201,0 |

Nenhum município sem dado. Fração de pixels válidos: mínimo 0,605, mediana
1,000; 4 municípios abaixo de 0,90 (mantidos, com a fração registrada).

## 8. Estatísticas de CAD por profundidade

| Profundidade | mínimo | p10 | mediana | p90 | máximo |
|---|---|---|---|---|---|
| 0–60 cm | 61,1 | 80,4 | **105,2** | 122,0 | 147,1 |
| 0–100 cm | 105,1 | 134,9 | **174,5** | 201,0 | 256,9 |
| 0–200 cm | 215,5 | 271,8 | **349,8** | 398,0 | 505,1 |

## 9. Variação intra-municipal

A distribuição por pixel foi preservada em todos os níveis: o manifesto guarda
p10/p50/p90 e desvio por município e profundidade. A CAD **não** foi reduzida a
um número municipal sem registro da dispersão.

## 10. Profundidade radicular e referências (D99)

* **Soja — 0–100 cm.** Franchini et al. (Embrapa Soja, safra 2008/2009)
  avaliaram o sistema radicular até 100 cm e mediram **6–12% da área radicular
  na camada 75–100 cm** (33–56% em 0–25; 12–28% em 25–50; 11–21% em 50–75).
  Limitar o reservatório a 60 cm descartaria 17–33% do sistema radicular.
* **Milho — 40–50 cm de profundidade efetiva.** Embrapa Milho e Sorgo
  (Albuquerque & Resende, *Cultivo do Milho — Irrigação*): "A profundidade
  efetiva do sistema radicular (Z) para o milho pode ser considerada variar
  entre 40 e 50 cm". Nas camadas publicadas, 0–60 cm é o cenário mais próximo.
* **Milho 2ª safra** — sem fonte específica: mantido como **cenário** igual ao
  milho, identificado como aproximação.

Nenhuma profundidade foi atribuída por cultivar; a distinção entre
profundidade máxima de raiz isolada e profundidade efetiva de extração é
mantida.

## 11. Reprodução do balanço histórico

Método: Thornthwaite & Mather (1955), ET0 FAO-56 com a latitude do município,
mesma série, mesma janela (histórica), CAD = 50 mm.

| Verificação | Resultado |
|---|---|
| pares comparados | 19.402 |
| diferença máxima | **1,05e-5 mm** |
| mediana da diferença | 6,0e-7 mm |

A reprodução é exata dentro do erro de armazenamento (float32). O pipeline é
fiel; qualquer diferença posterior vem de mudanças declaradas.

## 12. Defeito da janela e novos cenários

**Defeito (D97).** `months[0] <= data <= months[-1]` com `months[-1]` em
`"AAAA-MM"` exclui o mês final. Confirmado em 28.282 de 40.990 linhas; nas
19.402 analíticas, todas perdem ~31 dias.

| Efeito (janela corrigida vs histórica, CAD = 50 mm) | valor |
|---|---|
| déficit: razão mediana (p10; p90) | **1,236** (1,0; 3,78) |
| precipitação da janela | +135,4 mm (mediana) |
| ET0 da janela | +165,1 mm (mediana) |

**Cenários de CAD com a janela corrigida** (razão déficit / déficit a 50 mm):

| Cenário | razão mediana | p10 | p90 | déficit eliminado |
|---|---|---|---|---|
| 0–60 cm | 0,622 | 0,0 | 0,878 | 20,3% |
| **0–100 cm** | **0,139** | 0,0 | 0,682 | **43,6%** |
| 0–200 cm | 0,000 | 0,0 | 0,208 | 82,9% |

Nenhum caso tem razão > 1 (uma CAD maior nunca aumenta o déficit) — checagem
de sanidade que passa em 100% das linhas.

## 13. Painel integrado

`geospatial/data/processed/v30_panel_cad.csv` (19.402 linhas, 39 colunas):
identificadores (IBGE, cultura, safra, ano de colheita, UF, classe de ciclo),
as duas janelas (dias, precipitação, ET0), o déficit histórico e seis cenários
corrigidos, além dos valores armazenados do painel para auditoria. O painel
original **não** foi sobrescrito.

## 14. Comparação M0 / M1 / M1b / M2

Estrutura preservada: M0 média nacional, M1 média por UF, M1b UF×ano
(diagnóstico contemporâneo, não operacional), M2 clima + dummies de UF.
A comparação de interesse continua sendo **M2 − M1**, com `TE` como referência
de generalização.

## 15. Resultados por cultura (TE, M2 − M1)

| Cultura | clima | déficit histórico | 50 mm corrigido | CAD 0–100 | CAD 0–200 |
|---|---|---|---|---|---|
| soja | −6,3 [−26,8;+10,4] | **+10,6 [+0,7;+21,5]** | −20,0 [−47,2;+19,7] | −10,3 [−30,3;+18,4] | −6,9 [−15,5;+2,1] |
| milho | **−198,7 [−355,8;−31,3]** | −167,1 [−303,8;−11,3] | −195,2 [−342,5;−18,8] | −142,8 [−261,1;−2,8] | −21,7 [−51,8;+22,6] |
| milho 2ª | **−267,2 [−413,8;−35,1]** | −38,5 n.s. | −24,8 n.s. | −35,0 n.s. | −23,2 n.s. |

Leitura: (i) na **soja** nenhuma variável hídrica supera a média da UF com
significância, e o déficit da janela histórica era significativamente **pior**;
(ii) no **milho** a família climática é a que sustenta o ganho, e a CAD enfraquece
a família hídrica conforme a profundidade cresce; (iii) no **milho 2ª safra** só
a família climática se sustenta.

## 16. Generalização TE

Toda alegação acima vem do braço `TE` (bloco e ano separados simultaneamente).
`SS`, `SE` e `TS` aparecem apenas como diagnóstico no manifesto. Nenhum
resultado é apresentado como generalização sem passar por TE.

## 17. Investigação espacial do milho

Efeito do bloco (SS−SE), `climate_plus_state`:

| Definição do déficit | SS−SE |
|---|---|
| histórico (janela truncada, 50 mm) | −209,5 |
| janela corrigida, 50 mm | −203,4 |
| CAD 0–100 cm | −225,4 |
| CAD 0–200 cm | −286,1 |

**A CAD não reduz o efeito do bloco — ele cresce.** A hipótese de que a
heterogeneidade do milho era consequência da representação incompleta da água
no solo **não se confirma**: com um reservatório maior, o modelo depende ainda
mais de conhecer o bloco, porque a informação climática local passa a explicar
menos da variação de produtividade.

Implicação: o efeito está em diferenças regionais não observadas (manejo,
tecnologia, sistema produtivo, cultivar) que os dados do SADEN não medem. Não é
atribuível a solo nem a clima.

## 18. Análise por UF

A distribuição da CAD por UF (MS 138 → RS 195) e a concentração do efeito do
bloco em PR/BA/MS (V2.9) continuam sendo o padrão dominante. A V3.0 não altera
a leitura por UF; acrescenta que a CAD não a explica.

## 19. Classes ZARC

Mantido o dicionário oficial (D94): `Cod_Ciclo` 20/21/22 = Grupo I/II/III, não
cultivar. A V2.9 já havia retirado a "inversão de sinal" da temperatura; a V3.0
**não** a reintroduz. Nenhuma diferença entre grupos sobrevive à multiplicidade.

## 20. Testes

| Suíte | Resultado |
|---|---|
| Offline (`geospatial/tests`) | **372/372** (364 da V2.9 + 8 da V3.0) |
| Externos opt-in | 10/10 (V2.8; não reexecutados) |

Novos testes: limites da janela ZARC (histórico vs corrigido, mês final, mês
único, bissexto, janela vazia).

## 21. Fontes

NASA POWER (série diária), INMET (validação, inalterada), PAM/SIDRA 5457,
ZARC/MAPA (tábua + dicionário, D94), **Embrapa Solos/GeoInfo** (Vasques et al.,
2021; CC BY-NC 3.0 BR), **Embrapa Milho e Sorgo** (Albuquerque & Resende),
**Embrapa Soja** (Franchini et al.), FAO-56, Thornthwaite & Mather (1955).

## 22. Licenças

A CAD da Embrapa Solos é **CC BY-NC 3.0 BR** (uso não-comercial). Os rasters
**não** são versionados nem redistribuídos; o repositório guarda apenas as
estatísticas municipais e a citação. Produtos derivados herdam a restrição de
uso não-comercial e estão identificados no manifesto.

## 23. Decisões novas

* **D96** — aquisição por UF com máscara de polígono municipal.
* **D97** — defeito da janela ZARC e as duas semânticas em `cycle.window_bounds`.
* **D98** — a CAD não melhora a predição nem explica o bloco; resultado negativo
  registrado.
* **D99** — profundidade radicular: soja 0–100 cm, milho 40–50 cm, milho 2ª
  safra como cenário.

## 24. Limitações

1. A comparação 90 m × 450 m foi feita em janelas locais de ±0,35°, não no
   município inteiro.
2. A CAD é um retrato estático do solo; não representa compactação, ou variação
   temporal de manejo.
3. Profundidade radicular por cultivar não foi atribuída (sem fonte).
4. Milho 2ª safra usa a profundidade do milho como cenário.
5. O painel cobre 5–6 UFs de 27: **nenhuma generalização nacional**.
6. O efeito do bloco no milho permanece sem explicação observável.
7. Nenhuma conclusão causal.

## 25. Pendências

* Reavaliar o painel com a janela corrigida em todas as variáveis (não só o
  balanço): precipitação, graus-dia, dias de calor extremo e excesso hídrico.
* Investigar o bloco do milho com variáveis espaciais explícitas (tendência,
  vizinhos históricos) — não com efeitos fixos de bloco, que não existem para
  blocos ausentes.
* Fonte cultivar-específica para profundidade radicular.
* ERA5-Land (D83) e CHIRPS/ARCO (DNS) seguem bloqueados.

## 26. Recomendações para a V3.1

1. **Adotar a janela corrigida como protocolo padrão** e rotular todo número
   anterior como "janela histórica".
2. **Não usar a CAD como variável preditiva** enquanto não houver ganho
   demonstrado; usá-la para descrição e para o balanço.
3. **Reportar sempre M2 − M1 em TE** e manter M1b como diagnóstico.
4. **Investigar o bloco do milho** com covariáveis espaciais observáveis, não
   com efeitos fixos de unidades ausentes.
5. **Ampliar UFs** só com diagnóstico de representatividade; hoje são 5–6 de 27.
6. Manter a **Ridge** como único modelo de preços.
