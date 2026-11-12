# SADEN V2.4 — Resumo para decisão acadêmica

> Documento de uma página (duas) para a orientadora. Detalhes técnicos em
> `docs/V2_1_VALIDATION_REPORT.md`,
> `geospatial/reports/V2_2_PRODUCTIVITY_DATA_COMPATIBILITY.md`,
> `geospatial/reports/V2_3_EXPLORATORY_PRODUCTIVITY_STUDY.md` e
> `geospatial/reports/V2_4_*.md`. Branch: `v2/agricultural-scale-harmonization`.

## 1. O que a V2.3 demonstrou

Construímos (a) uma série Sentinel-2 **radiometricamente homogênea** de
2017–2025 (101 de 108 meses, 9 anos completos; equivalência numérica entre a
coleção harmonizada da ESA e a coleção original comprovada em 6 pares de datas:
diferença de NDVI **0,0**), (b) uma base observada de produtividade municipal do
IBGE/PAM (soja e milho, 2017–2025, com valores e unidades originais
preservados) e (c) um primeiro pareamento com 9 pares anuais por cultura.

## 2. Por que o NDVI não melhorou as previsões

Com n = 9, as correlações entre NDVI da AOI e rendimento municipal foram
**não significativas** (soja: r = 0,432, p = 0,246; milho: r = 0,200, p = 0,610).
Na validação temporal progressiva, a regressão com NDVI foi **pior** que
baselines triviais (soja: MAE 368 vs 254 kg/ha da média histórica; milho: 955
vs 684 do último valor). A correlação detrendizada foi *maior* que a bruta
(0,584 na soja) — assinatura típica de correlação espúria por tendência, e não
de relação agronômica.

## 3. A incompatibilidade espacial (o problema de fundo)

O alvo é **municipal** (Sorriso: 9.293 km²); o indicador era de uma **AOI de
43,26 km²** (0,4654% do município). A estatística municipal não descreve a
AOI, e rasterizá-la seria fabricar resolução inexistente — proibido por decisão
da V2.2.

## 4. O que foi descoberto na V2.4

1. **Calendário oficial resolvido**: o portal de dados abertos do **MAPA**
   (`dados.agricultura.gov.br` — domínio diferente do `dados.gov.br`, que exige
   autenticação) publica as **tábuas de risco do ZARC** de 2016/17 a 2026/27
   (licença CC-BY). Foram adquiridos os 11 arquivos: **1.408 registros de
   Sorriso em 23 culturas**, com janela de plantio por decêndio, solo, ciclo e
   **portaria de origem** (soja: out–dez; milho principal: set–dez; milho 2ª:
   jan–fev). Isso substitui a agregação "por ano civil" por janelas oficiais.
2. **Não existe produtividade submunicipal pública**. A CONAB publica, sim,
   polígonos de cultura **por município** (o GeoServer oficial do SUTIN), mas
   com **área** e **sem produtividade** — e só para soja 2021 em MT. MapBiomas
   (rota GCS) retorna 403 e o asset do Google Earth Engine exige conta;
   IMEA responde com erro 500; SIGS/INCRA não resolvem DNS.
3. **Alternativa metodológica construída**: em vez de reduzir o alvo, mudamos a
   **escala do indicador** — NDVI agregado sobre toda a área agrícola do
   município (máscara WorldCover classe 40 + polígono municipal), calculado por
   16 blocos com acumuladores, sem materializar o raster municipal. Assim o
   indicador passa a ter a **mesma unidade territorial** do alvo do IBGE.
4. **Referência de área por cultura**: os polígonos do SUTIN permitem
   identificar *onde* houve soja em 2021 (17 feições em Sorriso) — ainda sem
   qualquer valor de produtividade.

## 5. Alternativas testadas e por que não serviram

| Alternativa | Resultado |
|---|---|
| Rasterizar o rendimento municipal na AOI | proibido (D47) e cientificamente inválido |
| MapBiomas 10 m (GCS/GEE) | 403 / exige conta institucional |
| CONAB SIGS | sem DNS |
| IMEA (produtividade municipal de MT) | HTTP 500 (conteúdo não recuperável) |
| INCRA/SIGEF/CAR (geometria de propriedade) | sem DNS; e geometria não é produção |
| Embrapa Alice (janelas de semeadura simuladas) | referência técnica, não observação; não extrapolada |

## 6. O que ainda depende de acesso institucional

1. **Conta Google Earth Engine institucional** (MapBiomas Collection 4
   2017–2025, e os produtos de frequência de cultivo da Coleção 11) — é o que
   traria a máscara de uso do solo **anual** (hoje só há 2020 e 2021, via
   WorldCover).
2. **Portal do IMEA** navegável (o host responde; as páginas falham por HTTP
   500 nesta origem) — traria produtividade municipal de MT por safra.
3. **Textos das portarias do ZARC** para fechar a regra safra→ano da PAM.
4. Opcional: **MorphoSpatial/Constable** (Embrapa) para produtividade por
   talhão — investigar em etapa própria.

## 7. Qual metodologia é mais defensável hoje

A da **escala municipal do indicador** (item 4.3): preserva a unidade
territorial do alvo, não exige dado fino inexistente, usa máscara agrícola
oficial (ESA) e calendário oficial (MAPA), e é reprodutível. Com ela, um
estudo exploratório municipal *é* possível — a V2.4 não o executou (por
escopo), mas deixou a base pronta.

## 8. Decisões que dependem da orientação

1. Autorizar (ou não) o **acesso institucional ao MapBiomas (GEE)** — resolve a
   máscara anual e permite a distinção lavoura temporária × perene na escala
   municipal.
2. Definir se o TCC exige **produtividade por talhão** (exige nova fonte,
   hoje inexistente em bases públicas) ou aceita a **escala municipal** como
   limite declarado.
3. Autorizar a **etapa de experimentação** (V2.5) sobre a base municipal
   agora compatível, com protocolo temporal e sem promessa de desempenho.
4. Confirmar o **escopo do produto**: a V2 permanece isolada da V1 (D40/D41) —
   nenhuma integração ao Ridge ou à interface está prevista nesta fase.

## 9. Recomendação

Seguir por **CAMINHO B** (referência fina indisponível, escala municipal
harmonizável): a V2.2 já documentou a compatibilidade municipal, a V2.3
quantificou a ausência de associação e a V2.4 removeu os dois bloqueios
científicos (calendário oficial e incompatibilidade de escala). A única
pendência de acesso institucional que **muda** o resultado é o MapBiomas via
GEE — e ela não é bloqueante para um estudo municipal.
