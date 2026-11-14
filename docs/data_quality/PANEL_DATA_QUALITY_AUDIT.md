# SADEN — Auditoria de linhagem e qualidade do painel

**Data:** 2026-11-14
Manifestos: `pam_quality_audit.json`, `panel_canonical_build.json`, `v35_manifest.json`
Relacionado: `docs/data_quality/PAM_QUALITY_AUDIT.md`

---

## 1. Inventário de componentes

O painel analítico de referência é `geospatial/data/processed/v35_panel_windows.csv`
— **30.207 linhas, 81 colunas, 7 UFs, 2017–2025, três recortes de cultura**
(soja 12.517 · milho 12.013 · milho 2ª 5.677).

| componente | fonte | arquivo | unidade | resolução | período | transformação | qualidade |
|---|---|---|---|---|---|---|---|
| produtividade | IBGE/PAM SIDRA 5457 (v.8331) | `pam_panel*.csv` | kg/ha | município·ano | 2017–2025 | cópia direta | **validado** |
| produção / área | IBGE/PAM (v.214/216/112) | idem | t, ha | município·ano | 2017–2025 | consistência aritmética conferida | **validado** |
| precipitação | NASA POWER | `climate_daily*.csv` | mm/dia | município·dia | 2016-01-01–2025-12-31 | soma na janela corrigida | **validado com ressalva** |
| temperatura | NASA POWER | idem | °C | município·dia | idem | média na janela | **validado com ressalva** |
| radiação, vento, umidade, pressão | NASA POWER | idem | MJ/m², km/h, %, kPa | município·dia | idem | média na janela | **validado com ressalva** |
| ET0 | derivada (FAO-56 P-M) | idem | mm/dia | município·dia | idem | `evapotranspiration` | **validado** (replicado — §Fase 5) |
| graus-dia | derivada | idem | °C·dia | município·dia | idem | `thermal` | **validado** |
| déficit / excesso | derivada (T&M 1955) | idem | mm | município·mês | idem | `water_balance` | **validado** (replicado — §Fase 5) |
| CAD observada | Embrapa Solos GeoInfo WCS | `v30_cad_polygon.json` (1.296) + `v35_cad_polygon_sp.json` (584) | mm | polígono municipal | estático | mediana de pixels | **validado com ressalva** |
| janela agrícola | MAPA/ZARC | painel base | mês | município·cultura·safra | 2025 | `cycle.window_bounds(corrected=True)` | **validado** |
| polígonos municipais | IBGE malhas 2025 | `panel_municipalities_v35.csv` | — | município | 2025 | centróide, área, bbox | **validado com ressalva** |

### 1.1. Cobertura de CAD

| arquivo | municípios | observação |
|---|---:|---|
| `v30_cad_polygon.json` | 1.296 | 6 UFs originais |
| `v35_cad_polygon_sp.json` | 584 | São Paulo |
| **total** | **1.880** | de 2.425 municípios (77,5%) |

Os municípios sem CAD observada não entram nos cenários `cad_0_*`, mas **entram**
na exposição de referência com CAD fixa de 50 mm — que é a usada nas estimativas
principais. Isso é coerente: a CAD fixa é uma convenção declarada, não uma
medição.

## 2. Mistura de versões — achados

### 2.1. Duas fontes de clima sob a mesma chave (achado material)

`climate_daily.csv` tem **6.552.547 linhas para 1.622 municípios**, isto é
**7.306 linhas por município** quando o período tem 3.653 dias. Cada
(município, dia) aparece **duas vezes**, com fontes diferentes:

| par de fontes | pares conflitantes | valores |
|---|---:|---|
| NASA-POWER × INMET | **627.381** | **diferentes** (não é duplicata idêntica) |

Exemplo (município 2901007, 2016-01-01): NASA-POWER 27,86 °C / 0,11 mm; INMET
26,30 °C / 0,00 mm.

**Não houve mistura silenciosa no resultado publicado**: `v31_rebuild_panel.py`
linha 127 filtra `climate_source == "NASA-POWER"` antes de qualquer cálculo, e o
loader de clima (linha 162) filtra `source == "NASA-POWER"` na leitura. A
reprodução canônica confirma: com filtro explícito de fonte, o painel reconstruído
é **bit-idêntico** ao V3.5.

**Risco registrado (D123):** o filtro estava implementado, mas não era
declarado. Um leitor do arquivo de clima que deduplicasse por "primeira
ocorrência" obteria o mesmo resultado **por acidente de ordenação** — se a ordem
do arquivo mudasse, INMET entraria sem aviso. O pipeline canônico passou a
declarar `require_climate_source` na configuração e a **contar** as linhas
descartadas (`discarded_other_source_rows: {INMET: 10.229}` no teste de 14
municípios).

### 2.2. Linhas INMET com aparência de utilizáveis no painel base

| climat_source × status | linhas |
|---|---:|
| NASA-POWER × paired_usable | 19.402 |
| NASA-POWER × excluded | 16.492 |
| **INMET × paired_usable** | **2.020** |
| INMET × excluded | 3.076 |

As **2.020 linhas INMET `paired_usable`** existem no painel base e **nunca** foram
usadas: o único impedimento é o filtro da linha 127. Quem filtrar
`agroclimatic_productivity_panel.csv` por `status == "paired_usable"` sem repetir
o filtro de fonte obtém uma amostra de **duas fontes de clima misturadas**.

**Classificação:** não é erro de resultado (nenhuma estimativa publicada as usou);
é **armadilha de contrato de dados**. Corrigido no pipeline canônico (filtro
declarado em config) e registrado em D123. O painel base histórico **não foi
alterado**.

### 2.3. Duas janelas na mesma tabela

O painel tem **20 variáveis `_legacy` e 20 `_corrected` lado a lado** (81 colunas).
Isso é deliberado — é a prova da D97 — mas significa que o arquivo contém, por
linha, duas versões da mesma variável, com diferenças grandes:

| variável | legacy | corrigida | diferença |
|---|---:|---:|---:|
| precipitação acumulada | 338,3 mm | 491,4 mm | **+44,0%** |
| ET0 | 390,0 mm | 557,5 mm | **+43,5%** |
| graus-dia | 1.018,9 | 1.489,8 | **+45,5%** |
| déficit | 51,3 mm | 106,0 mm | **+23,6%** |

**Regra de uso:** toda análise usa exclusivamente sufixo `_corrected`. As colunas
`_legacy` existem apenas para reproduzir o erro e não devem entrar em modelo
algum. Verificado: os relatórios V3.1–V3.5 usam `_corrected`.

### 2.4. Recorte de milho 2ª safra

| recorte | linhas | compatibilidade semântica |
|---|---:|---|
| soja | 12.517 | boa |
| milho | 12.013 | boa |
| **milho 2ª** | **5.677** | **incompatível** (a PAM publica o total anual de milho) |

A limitação é **da fonte**, não do pipeline: a PAM não separa 1ª e 2ª safra. As
linhas `milho_2` usam o rendimento anual total com janela de 2ª safra. Qualquer
conclusão sobre milho 2ª é, portanto, de nível inferior ao milho de safra única.

## 3. Datas de referência

| campo | significado | onde |
|---|---|---|
| `acquired_at` | data de download da PAM | `pam_panel*.csv` (2026-11-12) |
| `reference_year` | ano de observação (ano da safra) | PAM |
| `harvest_year` | ano de colheita derivado da janela | painel |
| `publication_date` | data de publicação SIDRA | vazio em 100% das linhas |
| `revision` | marca de revisão | vazio em 100% das linhas |
| `generated_at` | data de geração de cada manifesto | manifests |

**Não há confusão entre data de download e data de observação.** O que **não
existe** é vintage: uma única extração, sem snapshots, logo revisões da PAM são
não mensuráveis (ver `PAM_QUALITY_AUDIT.md` §7).

## 4. Classificação de qualidade por componente

| componente | classificação |
|---|---|
| produtividade (PAM) | **validado** |
| janela corrigida (ZARC + `window_bounds`) | **validado** |
| graus-dia, dias de calor extremo, noites quentes | **validado** |
| ET0 (FAO-56 P-M) | **validado**, replicado independentemente (Fase 5) |
| balanço hídrico (T&M 1955) | **validado**, replicado independentemente (Fase 5) |
| precipitação / temperatura / radiação | **validado com ressalva** — reanálise, sem validação contra estação |
| CAD observada | **validado com ressalva** — mediana de pixels, 77,5% de cobertura |
| polígonos municipais | **validado com ressalva** — 2 unidades operacionais excluídas |
| milho 2ª safra | **incompatível** (limitação da fonte) |
| fontes INMET | **não utilizadas** (disponíveis: 627.381 registros diários) |

## 5. O que a auditoria mudou

| item | antes | depois |
|---|---|---|
| filtro de fonte de clima | implícito (ordem do arquivo + linha 127) | **declarado em config**, descarte contado |
| unidades operacionais no cadastro | presentes, sem regra | **excluídas por regra explícita** |
| caminho de construção | três scripts concorrentes | **um pipeline canônico** + legacy preservado |
| prova de equivalência | ausente | **0,0 de diferença** em 10 variáveis × 204 linhas |

## 6. Limitações desta auditoria

1. **Clima não validado contra estação**: os 627.381 registros INMET disponíveis
   seriam a forma natural de fazê-lo, e não foram usados nesta etapa.
2. **CAD sem validação de campo**: é mediana de polígono sobre produto de solo,
   não medição local.
3. **Sem vintage da PAM**: revisões não auditáveis.
4. **Amostra de verificação de 14 municípios**: prova que o pipeline canônico é
   fiel no caminho exercitado; o build completo de 2.425 municípios não foi
   executado nesta etapa (custo ~2 h) — a diferença é de escala, não de código.
5. **`_legacy` × `_corrected` coexistem no mesmo arquivo** por desenho; o risco é
   de leitura humana, não de cálculo.
