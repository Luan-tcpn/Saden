# V3.4 — REGISTRO DA CLASSIFICAÇÃO REGIONAL

Registro de rastreabilidade da atribuição município → região.
Gerado a partir de `geospatial/data/manifests/v34_region_mapping.json` e
`v34_coverage_identifiability.json`.

## 1. Fonte

| campo | valor |
|---|---|
| normativo | Instrução Normativa SPA/MAPA nº 1, de 9/11/2021 |
| atualizações | Portaria SPA/MAPA 387/2023; Portaria SPA/MAPA 281/2025 |
| instituição | MAPA — Secretaria de Política Agrícola |
| formato usado | planilha oficial "municípios e suas respectivas regiões edafoclimáticas" |
| URL | `.../MacrorregioSojicolasAtualizado_2025.xlsx` (página `normativos-do-zarc`) |
| SHA-256 | `91126b6b512724cd90ab2bfc951ac418c0114bf78a697562a9c8c377f7458c84` |
| bytes | 140.020 |
| acesso | 2026-11-14 |
| finalidade original | indicação de cultivares de **soja** no ZARC |

## 2. Estrutura

5 macrorregiões (MRS 1–5) e 20 regiões edafoclimáticas (101–104, 201–204, 301–304,
401–405, 501–503). A planilha traz 4.286 pares UF–município; 1.425 nos 6 estados
do painel.

## 3. Regra de agrupamento (congelada)

| grupo | definição | justificativa |
|---|---|---|
| Sul | MRS 1 | a própria fonte a nomeia como a macrorregião do Sul sojícola |
| Cerrado | MRS 3 ∪ 4 | núcleo sojícola do Cerrado (GO, MS-RE301, MT, BA-RE405) |
| Transição | MRS 2 | faixa que cruza PR-norte e MS-centro-sul; **excluída** do contraste |
| Fora | MRS 5 e sem indicação | nordeste/norte e municípios sem soja |

## 4. Composição (municípios com indicação, por UF e MRS)

| UF | MRS1 | MRS2 | MRS3 | MRS4 | MRS5 | total |
|---|---:|---:|---:|---:|---:|---:|
| PR | 134 | 266 | — | — | — | 400 |
| RS | 497 | — | — | — | — | 497 |
| MS | — | 53 | 26 | — | — | 79 |
| GO | — | — | 119 | 127 | — | 246 |
| MT | — | — | — | 141 | — | 141 |
| BA | — | — | — | 27 | 35 | 62 |

## 5. Atribuição no painel

| item | valor |
|---|---:|
| municípios candidatos (6 UFs) | 1.782 |
| com região atribuída | 1.422 |
| sem atribuição (sem indicação de soja) | 360 |
| municípios do painel analítico (1.296) sem região | 22 |
| duplicados de código IBGE | 0 |

## 6. Regiões edafoclimáticas presentes no painel (milho)

301 (14 munis) · 302 (19) · 303 (28) · 304 (47) · 401 (84) · 404 (16) ·
202 (20) · 204 (32) · 301-MS (24) · 402 (53) · 403 (23) · 102 (48) ·
103 (84) · 201 (177) · 202-PR (82) · 101 (33) · 405 (6) · 501 (5)

## 7. Áreas de transição e casos de fronteira

* **Nenhum município é dividido** entre grupos: a fonte é discreta por município.
* **MRS 2** é a faixa de transição declarada e fica fora do contraste primário.
  Ela contém 2.298 linhas de milho (26% da cultura) e cruza dois estados.
* **MT** pertence a MRS 4 mas inclui transição amazônica — por isso existe a
  sensibilidade "Cerrado sem MT" (D = −65,9, mesmo sinal).
* **BA** tem 20 municípios sem indicação de soja (excluídos) e 5 em MRS 5
  (nordeste, fora do escopo).

## 8. Limitações registradas

1. A classificação é de **soja**; o uso para milho é aproximação declarada.
2. **MRS ≠ bioma.** MRS 4 não é "o Cerrado".
3. Não existe lista municipal oficial equivalente para milho com este nível de
   detalhe (o ZARC de milho é por safra/solo/ciclo).
4. O normativo não cobre municípios sem indicação de soja; ausência não é erro.
5. **Região aninhada em UF** — consequência registrada antes dos resultados
   (protocolo §6.1) e confirmada (Cramér's V = 1,000).

## 9. Reprodutibilidade

```
python tools/v34_region_mapping.py   # baixa, valida hash, parseia, junta
python tools/v34_coverage.py         # cruza com o painel e mede confundimento
```

O mapeamento é determinístico: mesma planilha → mesmo CSV. Nenhuma atribuição
manual, nenhum ajuste por resultado.
