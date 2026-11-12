# SADEN V2.4 — Calendário agrícola oficial (ZARC/MAPA) para Sorriso-MT

> Branch: `v2/agricultural-scale-harmonization` (derivada de
> `v2/agricultural-productivity-exploratory` / `3ff7104`). Execução: 2026-11-12.
> Dados: `geospatial/data/processed/zarc_planting_windows.csv` (1.408 registros) e
> `geospatial/data/processed/zarc_pam_year_relation.csv` (148 combinações).
> Manifesto: `geospatial/data/manifests/zarc_calendar_manifest.json`.

## 1. Fonte

| Item | Valor |
|---|---|
| Instituição | **MAPA** — Ministério da Agricultura, Pecuária e Abastecimento |
| Conjunto | *Zoneamento Agrícola de Risco Climático (Zarc) — Tábua de Risco* |
| Catálogo | `https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-dc8ff323b96f` |
| Licença | **Creative Commons Atribuição** |
| Atualização do catálogo | 2026-11-11 |
| Recursos CSV | safras **2016/2017 a 2026/2027** (11) + *Perene, Olerícola e Sem Safra* |
| Dicionário de dados | PDF oficial do conjunto (`dicionario-de-dados-tabua-de-risco-2026.pdf`) |
| Schema real | `;` como delimitador, UTF-8 com BOM, colunas `Nome_cultura, SafraIni, SafraFin, Cod_Cultura, Cod_Ciclo, Cod_Solo, geocodigo, UF, municipio, Cod_Clima, Nome_Clima, Cod_Outros_Manejos, Nome_Outros_Manejos, Produtividade, Cod_NM, Cod_Munic, Cod_Meso, Cod_Micro, Portaria, dec1..dec36` |

**FATO.** O bloqueio HTTP 401 observado na V2.2 vale para `dados.gov.br`
(catalogo CKAN com autenticação) e **não** para `dados.agricultura.gov.br`,
que é o portal do próprio MAPA. Os 11 CSVs foram baixados de fato
(~180 MB cada; o bruto fica fora do Git, com URL, tamanho e SHA-256 no
manifesto; o recorte de Sorriso é versionado).

**FATO.** O campo `Produtividade` do ZARC é um **código de classe de
produtividade** (ex.: `025535`), **não** kg/ha e **não** produtividade
observada.

## 2. Cobertura adquirida (Sorriso-MT, `5107925`)

| Métrica | Valor |
|---|---|
| Safras | 11 (2016/2017 … 2026/2027) |
| Registros de Sorriso | **1.408** |
| Culturas | 23 (Soja 126 · Milho 63 · Milho 1ª Safra 36 · Milho 2ª Safra 84 · Trigo 56 · Algodão Herbáceo 48 · Arroz 27 · Feijão 57 · Sorgo Granífero 63 …) |
| Combinações por cultura/safra | ciclo × solo (1 a 3 solos por cultura, 3 ciclos) |

**FATO.** O ZARC **não** usa "1ª safra"/"2ª safra" para o milho de forma
uniforme: aparecem `Milho` (safra principal), `Milho 1ª Safra` e
`Milho 2ª Safra`, além de consórcios com braquiária. A tabela de
correspondência (seção 5) mantém essa distinção.

## 3. Janelas de plantio observadas (Sorriso)

| Cultura | Safra 2018/19 | Janela (decêndios) | Datas aproximadas | Portaria |
|---|---|---|---|---|
| Soja | 2018/19 | 29–36 | 08/10 – 26/12 (2018) | `port.140_20-07-2018` |
| Soja | 2019/20 | 29–36 | 08/10 – 26/12 (2019) | `port.63_19-07-2019` |
| Milho (principal) | 2018/19 | 27–36 | 18/09 – 26/12 (2018) | `Port.113_12-07-2018` |
| Milho 2ª Safra | 2018/19 | 1–5 | 01/01 – 19/02 (2019) | `port.247_08-11-2018` |
| Milho 2ª Safra | 2017/18 | 1–5 | 01/01 – 19/02 (2018) | `port.212_23-10_2017` |

**FATO.** As janelas são as **recomendadas** (decêndios com risco *muito
baixo* ou *baixo*, classes 10 e 20 do ZARC). Todas as combinações oficiais
(ciclo × solo) são preservadas na base; nada foi arbitrado.

**FATO.** Cada linha carrega a **portaria de origem** (número e data), o que
permite rastreabilidade até o ato normativo.

## 4. Portarias

Portarias identificadas para soja e milho em Sorriso (amostra):
`port.65_31-07-2017`, `port.13_20-07-2017`, `port.212_23-10_2017`,
`Port.113_12-07-2018`, `port.140_20-07-2018`, `port.247_08-11-2018`,
`port.63_19-07-2019`, `port.227_09-12_2016`.

**LIMITAÇÃO.** As portarias foram **identificadas** pelo próprio conjunto de
dados (campo `Portaria`), mas os textos integrais não foram conferidos nesta
etapa: exigem download e leitura de PDFs do diário oficial. Retificações e
revogações não foram verificadas.

## 5. Safra × ano de referência da PAM

**FATO.** O ZARC expressa safras (ano de plantio + ano de colheita); a PAM
expressa **ano civil** de referência da produção. A tabela
`zarc_pam_year_relation.csv` registra, para cada (safra, cultura): janela de
plantio, ano de plantio, **ano de colheita estimado**, candidato principal e
alternativo para a PAM e nível de confiança.

Regra **derivada** (não é afirmação do IBGE): a safra `Y/Y+1` de soja e milho
1ª tem plantio entre outubro e dezembro de `Y` e colheita entre janeiro e
fevereiro de `Y+1`; o milho 2ª safra tem plantio em janeiro–fevereiro de
`Y+1` e colheita em maio–junho de `Y+1`. Em ambos os casos a colheita ocorre
no ano civil `Y+1` → **candidato principal para a PAM: `Y+1`**; o ano de
plantio (`Y`) é preservado como alternativa.

| Safra | Soja (plantio) | Milho 1ª (plantio) | Milho 2ª (plantio) | Ano PAM candidato |
|---|---|---|---|---|
| 2019/20 | out–dez 2019 | set–dez 2019 | jan–fev 2020 | **2020** (alt. 2019) |
| 2020/21 | out–dez 2020 | set–dez 2020 | jan–fev 2021 | **2021** (alt. 2020) |
| 2024/25 | out–dez 2024 | set–dez 2024 | jan–fev 2025 | **2025** (alt. 2024) |

**LIMITAÇÃO.** A regra é uma **inferência metodológica** derivada do
calendário ZARC e do ciclo das culturas; deve ser confrontada com o texto da
portaria e com o calendário de semeadura antes de uso analítico definitivo.
Alternativas são preservadas na tabela.

## 6. ZARC × calendário de semeadura (conceitos distintos)

**FATO.** O ZARC indica **janela recomendada de plantio por condição de
risco**; não é o calendário de semeadura nem o vazio sanitário da soja, que
têm finalidade normativa própria (INDEA/MT). Os dois conceitos **não** foram
misturados: a base da V2.4 usa apenas janelas do ZARC.

**LIMITAÇÃO.** O calendário de semeadura aplicável a Sorriso **não** foi
obtido nesta etapa: os portarias do calendário de semeadura da soja não foram
localizados em acesso automatizável.

## 7. Referência complementar (Embrapa)

**FATO.** O trabalho *"Impacto da época de semeadura na viabilidade econômica
de dois sistemas soja-milho segunda safra em Mato Grosso"*
(Alice/Embrapa, handle 1146640) é uma **referência técnica** de simulação
(2007–2020) sobre janelas de semeadura e rentabilidade. Foi acessado e
registrado como complementar.

**LIMITAÇÃO.** Resultados **simulados** de 2007–2020 **não** foram
extrapolados para safras posteriores e **não** foram usados como janelas.

## 8. Lacunas

1. Textos integrais das portarias não conferidos (só o identificador, vindo do
   próprio conjunto).
2. Retificações/revogações não verificadas.
3. Calendário de semeadura (normativo) não obtido.
4. A coluna `Nome_Clima` e `Cod_Outros_Manejos` vêm vazias para Sorriso nas
   safras analisadas (o risco foi definido por solo/ciclo).
5. As janelas são **recomendadas**, não observadas.

## 9. Uso no SADEN

O calendário do ZARC entra como **referência agronômica** (D54), separada da
referência espacial (D55). Ele permite, em princípio, substituir a agregação
"por ano civil" da V2.3 (D52) por janelas oficiais de plantio — o que **não**
foi executado nesta etapa (a V2.4 não retreina modelos), mas fica
documentado e reproduzível.
