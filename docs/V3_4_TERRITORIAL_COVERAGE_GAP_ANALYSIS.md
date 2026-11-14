# SADEN V3.4 — Diagnóstico da lacuna de cobertura territorial

**Data:** 2026-11-14 · Manifesto: `geospatial/data/manifests/v34_coverage_gap.json`

Este documento não integra dados novos. Ele mede o problema, como o escopo da
V3.4 exige, e conclui o que a V3.5 deveria adquirir — com base na evidência desta
versão.

---

## 1. Cobertura atual

O SADEN cobre **6 UFs de 27**: MT, GO, MS, PR, RS e BA.

Denominador disponível: a planilha oficial do MAPA lista **4.286 municípios com
indicação de soja em 21 UFs**. Desses, **1.425 estão nas 6 UFs do painel —
33,25%**.

| UF | municípios indicados | no painel | mapeados para região | cobertura dos indicados | linhas soja / milho / milho 2ª |
|---|---:|---:|---:|---:|---|
| RS | 497 | 455 | 497 | 100,0% | 2.966 / 1.428 / 0 |
| PR | 400 | 394 | 399 | 99,8% | 2.863 / 2.966 / 1.836 |
| GO | 246 | 214 | 246 | 100,0% | 1.558 / 1.567 / 285 |
| MT | 141 | 125 | 139 | 98,6% | 911 / 997 / 353 |
| MS | 79 | 77 | 79 | 100,0% | 586 / 552 / 428 |
| BA | 62 | 31 | 62 | 100,0% | 0 / 106 / 0 |

Duas leituras, ambas necessárias:

* **A correspondência municipal é quase completa** (98,6–100% dos municípios
  indicados foram mapeados). O problema não é o mapeamento.
* **O painel usa uma fração menor**: BA traz 31 dos 62 municípios indicados, GO
  214 de 246, RS 455 de 497. A cobertura do *painel* é menor que a cobertura do
  *mapeamento*.

## 2. O que não pode ser medido com o que existe

**Participação na produção nacional** e **área agrícola** não são reportadas.

Motivo: o painel PAM do repositório (`pam_panel.json`) cobre **apenas as 6 UFs já
integradas** — 128.160 registros. Qualquer percentual de produção nacional
exigiria adquirir PAM para as outras 15 UFs com indicação. Estimar esse
percentual sem os dados seria inventar.

Consequência: a lacuna é quantificada em **municípios** e em **macrorregiões**,
não em toneladas. É uma medida territorial, mais fraca que uma medida de
produção — e está declarada como tal.

## 3. A lacuna

| item | valor |
|---|---:|
| UFs com indicação de soja | 21 |
| UFs cobertas | 6 |
| **UFs ausentes** | **15** |
| municípios indicados fora do escopo | **2.861** |
| fração do território indicado fora do escopo | **66,75%** |

UFs ausentes: AC, AL, AP, DF, MA, MG, PA, PI, RJ, RO, RR, SC, SE, SP, TO.

## 4. Por que "mais UFs" não é o critério suficiente

A conclusão central da V3.4 é que o contraste regional **não é identificável
porque região está aninhada em UF** (Cramér's V = 1,000; nenhuma UF tem
municípios nos dois grupos). Adicionar UFs que só reforçam os mesmos grupos não
resolve isso — aumentaria a amostra sem aumentar a identificação.

O critério correto é: **qual UF ausente tem municípios nos dois grupos do
contraste primário** (Sul = MRS 1; Cerrado = MRS 3∪4)?

| UF ausente | municípios indicados | macrorregiões | quebra o confundimento? |
|---|---:|---|---|
| **SP** | **645** | MRS 1, 2 e 3 | **SIM — a única** |
| MG | 852 | MRS 2 e 3 | não (não tem MRS 1) |
| SC | 295 | MRS 1 | não (só Sul) |
| RJ | 92 | MRS 2 e 3 | não |
| TO | 139 | MRS 4 e 5 | não |
| PI, MA, PA, AL, SE | 73–224 | MRS 5 | não |

**São Paulo é a única UF que permitiria comparar Sul e Cerrado dentro do mesmo
estado**: a região de Itapeva/Itararé é MRS 1 (RE 103) e o oeste paulista é
MRS 3. É, portanto, a aquisição de maior valor científico por unidade de esforço.

## 5. Prioridade de expansão (evidência, não conveniência)

| ordem | UF | por quê | ganho esperado |
|---|---|---|---|
| 1 | **SP** | única com MRS 1 e MRS 3; 645 municípios indicados | **identificação** do contraste Sul×Cerrado dentro de UF |
| 2 | MG | 852 municípios em MRS 2 e 3 | separa transição de Cerrado dentro de UF; segundo maior |
| 3 | SC | 295 municípios em MRS 1 | aprofunda o grupo Sul (hoje só RS + PR parcial) |
| 4 | TO | 139 em MRS 4 e 5 | primeira UF de MRS 5 com Cerrado |
| 5 | PI/MA | 224/217 em MRS 5 | diversidade do Norte/Nordeste |

Ordem **não** escolhida por proximidade dos estados com efeito negativo — seria
o erro que o escopo proíbe. É escolhida por capacidade de identificação e por
tamanho do território indicado.

## 6. Fontes potenciais (documentadas, não adquiridas)

| fonte | variável | abrangência | resolução | período | licença | limitação |
|---|---|---|---|---|---|---|
| IBGE/SIDRA — PAM | produtividade e área municipal | nacional | municipal | 1974– | aberta | exige baixar por UF; consistência de culturas |
| NASA POWER | clima diário | nacional | ~0,5° | 1981– | aberta | já integrado; mesma fonte para novas UFs |
| MAPA/ZARC | calendário e regiões | nacional | municipal | anual | aberta | já integrado (janela) |
| Embrapa Solos (GeoInfo/WCS) | CAD por profundidade | nacional | 90 m | estático | **CC BY-NC 3.0 BR** | não redistribuir rasters |
| IBGE — malhas municipais | geometria | nacional | municipal | anual | aberta | já integrado |

Nenhuma foi adquirida nesta versão.

## 7. Critérios de aceitação para a expansão (V3.5)

Uma UF só entra se:

1. tiver PAM com série compatível (≥ 8 anos no período 2017–2025);
2. tiver malha municipal e centróide;
3. tiver cobertura NASA POWER completa na janela ZARC;
4. tiver CAD disponível ou cenário declarado;
5. tiver municípios na lista oficial de indicação (para a classificação);
6. passar pelos mesmos testes de qualidade das 6 UFs atuais;
7. e, **para o objetivo de identificação**, adicionar variação regional **dentro**
   de UF — SP é o caso que satisfaz isso.

## 8. Riscos da expansão

* **Heterogeneidade de qualidade**: PAM varia em confiabilidade entre UFs; um
  painel maior pode ser mais ruidoso.
* **Mudança de composição**: adicionar UFs muda os baselines nacionais (M0/M1) e
  torna os resultados da V3.0–V3.3 não comparáveis sem reestimação.
* **Custo de reconstrução**: a janela corrigida (D100) exige reprocessar todo o
  clima diário para as novas UFs.
* **Não resolve nada se for escolhida por conveniência**: só SP (e MG em menor
  grau) atacam o problema de identificação.

## 9. O que este diagnóstico conclui

1. A cobertura é **33,25%** do território com indicação de soja, em municípios.
2. A correspondência municipal é boa; o que falta é **território**, não
   mapeamento.
3. A lacuna relevante para a ciência do SADEN **não é genérica**: é a ausência de
   uma UF que contenha os dois grupos regionais. **SP é a única candidata.**
4. Enquanto isso não acontecer, qualquer afirmação "regional" do SADEN permanece
   não identificável — e é assim que a V3.4 a registra.
