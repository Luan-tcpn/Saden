# SADEN V3.5 — Priorização dos próximos estados

**Data:** 2026-11-14 · Fonte de contagens: planilha oficial MAPA/ZARC (4.286
municípios com indicação de soja, 21 UFs) + gap analysis da V3.4.

---

## 1. Critério

Não se escolhe o próximo estado por proximidade geográfica nem por conveniência
de resultado. Os critérios, em ordem:

1. **Quebra o confundimento região × UF?** — tem municípios em MRS 1 **e** em
   MRS 3/4?
2. **Quanto território indicado acrescenta?** — municípios com indicação.
3. **Que diversidade agroclimática traz?** — macrorregião e região edafoclimática
   ainda não cobertas.
4. **Custo de integração** — clima, PAM, CAD, ZARC, geometria (todos já
   automatizados para uma UF; o custo é homogêneo).

## 2. Situação após SP

Das 21 UFs com indicação de soja, **7 estão integradas**: PR, RS, MS, MT, GO, BA
e SP. Cobrem MRS 1, 2, 3 e 4. **MRS 5 (Norte/Nordeste sojícola) não tem
representação** além de 35 municípios da BA.

## 3. Ranking

| # | UF | municípios indicados | MRS | quebra confundimento? | por quê |
|---|---|---:|---|---|---|
| **1** | **MG** | **852** | 2, 3 | **não** | maior território não coberto; 852 municípios em MRS 2 e 3 permitiriam testar **transição × Cerrado dentro da UF**; diversidade edafoclimática ampla (RE 203, 302, 303, 304) |
| 2 | SC | 295 | 1 | não | aprofunda o grupo Sul (hoje RS + PR-sul + SP-MRS1); MRS 1 em três estados |
| 3 | TO | 139 | 4, 5 | não | primeira UF de **MRS 5** com Cerrado; amplia o Norte |
| 4 | PI | 224 | 5 | não | MRS 5 com 224 municípios |
| 5 | MA | 217 | 5 | não | MRS 5; contíguo a TO/PI |
| 6 | PA | 132 | 5 | não | MRS 5; diversidade amazônica |
| 7 | RJ | 92 | 2, 3 | não | dentro do Sudeste, mas pequeno |
| 8 | DF | 1 | 3 | não | irrelevante em volume; útil apenas como caso urbano |
| 9 | AL / SE | 86 / 73 | 5 | não | MRS 5, pequenos |
| 10 | AC / RO / RR / AP | 22–52 | 4, 5 | não | volume pequeno |

## 4. Por que MG é a próxima

* **852 municípios** com indicação — o maior bloco não integrado.
* MRS **2 e 3** dentro do mesmo estado: permite testar *transição × Cerrado*
  dentro de UF, o mesmo tipo de teste que SP tornou possível para *Sul × Cerrado*
  — e que **falhou** em SP. Se falhar também em MG, a leitura regional fica
  duplamente refutada; se funcionar, há um caso onde a MRS organiza algo.
* Múltiplas regiões edafoclimáticas (203, 302, 303, 304), o que amplia a
  diversidade de solo/clima mais do que qualquer outra UF restante.
* Contígua ao Cerrado já coberto (GO/MT/MS), o que dá suporte climático comum
  para comparações.

## 5. O que **não** justifica escolha

* Proximidade de estados onde o bloco hídrico "funcionou" (PR/RS) — isso seria
  escolher pelo resultado (D111 proíbe).
* Ser o maior rebanho/área de milho, se não houver lista municipal de
  classificação.
* Ter boa cobertura de PAM apenas.

## 6. Recomendação para V3.6

**Integrar MG**, com os mesmos critérios de aceitação da V3.4/V3.5 (PAM com série
≥ 8 anos, malha municipal, clima NASA POWER na janela corrigida, CAD por polígono,
lista ZARC). Reestimar M0/M1/M2 e reportar como painel de 8 UFs — sem chamar de
representativo nacional.

Alternativa de menor custo e menor ganho: SC (295 municípios, MRS 1), que apenas
reforça o grupo Sul.

## 7. Limitações do ranking

1. As contagens vêm da lista de **indicação de soja**, não do território agrícola
   total: UFs com agricultura relevante e pouca soja aparecem sub-representadas.
2. Não há informação de produção nacional no repositório (§4 do relatório de
   cobertura); o ranking é **territorial**, não produtivo.
3. O custo de integração foi tratado como homogêneo; pode variar com geografia
   (Amazônia tem mais nuvens e menos estações, mas o clima vem de reanálise).
