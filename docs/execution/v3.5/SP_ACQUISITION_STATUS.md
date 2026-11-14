# V3.5 — Status da aquisição de São Paulo

Manifesto: `geospatial/data/manifests/v35_sp_acquisition.json`
Detalhe: `docs/V3_5_SAO_PAULO_DATA_ACQUISITION_REPORT.md`

## Etapas

| # | etapa | estado | resultado | hash (início) |
|---|---|---|---:|---|
| 1 | municípios (geometria IBGE) | ✔ | 645 | `8a1c1486` |
| 2 | clima NASA POWER 2016–2025 | ✔ | 645/645, 0 falhas, 2.356.185 linhas | `3b0f874f` |
| 3 | PAM/SIDRA 5457 (2017–2025) | ✔ | 46.440 registros (11.610 rendimento) | `da10560a` |
| 4 | ZARC (janelas) | ✔ | 1.082.148 linhas, 10 safras | `2e00bf54` |
| 5 | CAD (WCS, polígono, 460 m) | ✔ | 584 municípios | `v35_cad_polygon_sp.json` |
| 6 | painel base | ✔ | 19.608 linhas / 10.805 utilizáveis | — |
| 7 | mapeamento MRS | ✔ | 643 de 645 classificados | `v35_region_mapping.json` |
| 8 | janela corrigida + descritores | ✔ | 10.805 linhas / 43.220 de água | `v35_sp_windows.json` |

## Qualidade por etapa

| verificação | resultado |
|---|---|
| códigos IBGE únicos e iniciando em `35` | ✔ 645, 0 duplicados, 0 colisões com os 6 estados |
| dias de clima por município | ✔ 3.653 em todos |
| falhas de clima | ✔ 0 |
| unidade de produtividade | ✔ kg/ha (mesma do painel), original preservada |
| área usada no rendimento | ✔ área colhida |
| janela ZARC | ✔ contrato corrigido (D100), sem janela genérica |
| CAD | ✔ 584 de 582 utilizáveis (2 sem linha analítica) |
| dados sintéticos | ✔ nenhum |

## Funil

| etapa | municípios |
|---|---:|
| IBGE | 645 |
| MRS | 643 |
| CAD | 584 |
| painel utilizável | 582 |

Linhas excluídas no painel de SP: 8.803 — 4.569 sem rendimento PAM, 4.150 sem
janela ZARC aplicável (dias na janela = 0), 156 por cobertura climática < 0,60.

## Pendências de aquisição

| item | estado |
|---|---|
| CAD para os 61 municípios restantes | não necessário: não têm linha analítica |
| ERA5-Land | bloqueado (credencial CDS) |
| CHIRPS / ARCO | bloqueado (DNS) |
| PAM das 14 UFs restantes | necessário para representatividade produtiva; **não** feito |
