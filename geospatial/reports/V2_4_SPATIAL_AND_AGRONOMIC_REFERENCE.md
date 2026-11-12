# SADEN V2.4 — Relatório consolidado: referência espacial e agronômica

> Branch: `v2/agricultural-scale-harmonization` (derivada de
> `v2/agricultural-productivity-exploratory` / `3ff7104`). Execução: 2026-11-12.
> Relatórios companheiros: `V2_4_ZARC_CALENDAR.md`,
> `V2_4_SPATIAL_PRODUCTIVITY_SOURCES.md`, `V2_4_SPATIAL_SCALE_HARMONIZATION.md`,
> `V2_4_ADVISOR_DECISION_BRIEF.md`.

## 1. Objetivo e escopo

Investigar e adquirir referências agrícolas mais adequadas, construir um
calendário oficial e avaliar a correspondência entre indicadores Sentinel-2 e as
estatísticas oficiais do IBGE, **sem treinar modelos** e sem integrar nada ao
Ridge ou à interface.

## 2. Metodologia

1. Auditoria do repositório e da documentação (D42–D53 preservadas).
2. Investigação de fontes com aquisição real: MAPA/ZARC, CONAB (SUTIN e
   Boletim de Safras), MapBiomas (GCS e GEE), ESA WorldCover, IMEA, Embrapa,
   INCRA/SIGEF/CAR, UFMT.
3. Aquisição e normalização do calendário ZARC (11 safras).
4. Aquisição dos polígonos da CONAB (SUTIN) e verificação de atributos.
5. Construção do indicador NDVI **municipal** por blocos (escala harmonizada).
6. Testes automatizados (offline) e execução real de todos os componentes.

## 3. Dados obtidos

| Conjunto | Registros | Arquivo |
|---|---|---|
| ZARC — janelas de plantio (Sorriso, 11 safras, 23 culturas) | **1.408** | `data/processed/zarc_planting_windows.csv` |
| ZARC — relação safra × ano PAM | 148 | `data/processed/zarc_pam_year_relation.csv` |
| CONAB SUTIN — MT (17 camadas, recorte da bacia de Sorriso) | 14–34 feições por camada | `data/processed/conab_sutin/*.csv` (+ GeoJSON fora do Git) |
| ESA WorldCover — máscara agrícola municipal | 2 anos (2020, 2021) | `data/manifests/landuse_aoi_report.json` (V2.3) + `municipal_ndvi_report.json` |
| NDVI municipal sobre a área agrícola | 1 data/ano, 20 m, 16 blocos | `data/processed/municipal_ndvi_agriculture.csv` |

## 4. Resultados

1. **Calendário oficial resolvido** (D54): janelas do ZARC porSafra/cultura/
   solo/ciclo, com portaria de origem. Soja: out–dez; milho principal:
   set–dez; milho 2ª: jan–fev.
2. **Não existe produtividade submunicipal pública** (D56): a CONAB entrega
   área por feição, não rendimento; MapBiomas/IMEA/SIGS/INCRA estão bloqueados
   ou inacessíveis, com evidência.
3. **Escala municipal do indicador construída** (D57): NDVI agregado sobre a
   área agrícola do município por 16 blocos, sem materializar o raster; piloto
   2017-03 → 11.999.215 pixels agrícolas (≈4.800 km²), NDVI médio 0,5668
   (mediana 0,6237), contra 0,5282 na AOI de 43,26 km².
4. **Referência de área por cultura**: 17 feições de soja (CONAB SUTIN 2021) em
   Sorriso — identify *where*, never *how much*.

## 5. Testes

| Suíte | Resultado |
|---|---|
| Offline (`geospatial/tests`) | **181/181 OK** (165 da V2.1–V2.3 + 16 da V2.4) |
| Externos opt-in (`SADEN_EXTERNAL_TESTS=1`) | 10/10 OK (V2.1/V2.2) |

Dois bugs reais foram encontrados pelos testes e corrigidos: `NaN` entrando no
acumulador estatístico e o cálculo do topo do bloco na grade (eixo vertical
decrescente), que deslocava a leitura dos blocos.

## 6. Limitações

1. A máscara agrícola municipal só existe para 2020–2021 (WorldCover).
2. O indicador municipal usa **uma data por ano** (março), não média anual.
3. Lavoura temporária × perene depende do MapBiomas (bloqueado).
4. A regra safra→ano PAM é **derivada**; os textos das portarias não foram
   conferidos.
5. Custo de ~1,04 GB/data limita séries completas sem janela ampliada.
6. Nenhum modelo foi treinado; nenhuma integração foi feita.

## 7. Decisões desta etapa

D54 (ZARC como fonte de calendário) · D55 (referência espacial × agronômica)
· D56 (inexistência de produtividade submunicipal pública) · D57 (escala
municipal do indicador por blocos).

## 8. Veredito e próximo passo

**CAMINHO B** — referência fina indisponível, escala municipal harmonizável.
A incompatibilidade de escala da V2.3 foi removida metodologicamente e o
calendário oficial foi adquirido; falta apenas (a) acesso institucional ao
MapBiomas para a máscara anual e (b) a decisão sobre a janela do ZARC a ser
usada no indicador, que é o objeto da V2.5.
