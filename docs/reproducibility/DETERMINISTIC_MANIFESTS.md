# SADEN — Manifestos determinísticos

**Data:** 2026-11-14
**Código:** `tools/pipeline/manifest.py`
**Referência:** `geospatial/data/manifests/panel_canonical_build_v2.json` (+ `.run.json`)

---

## 1. O problema

O manifesto anterior embutia `generated_at` no mesmo arquivo do conteúdo. O
SHA-256 mudava a cada execução, então o hash **não servia para verificar
integridade** — apenas registrava quando o arquivo foi escrito. O teste de clone
limpo da etapa anterior encontrou isso: números idênticos, hash diferente.

## 2. A separação

| arquivo | conteúdo | muda entre execuções? |
|---|---|---|
| `<nome>.json` | conteúdo canônico: entradas, hashes, parâmetros, contagens, resultados | **não** |
| `<nome>.json.run.json` | data, duração, host, plataforma, versão de Python, ponteiro para o hash de conteúdo | **sim** |

O hash do arquivo `.json` é agora um verificador de integridade do conteúdo. O
`.run.json` preserva a proveniência temporal que antes se perdia.

## 3. Canonicalização aplicada

| regra | implementação |
|---|---|
| ordenação de chaves | `sort_keys=True` em todos os níveis |
| ordenação de listas | **preservada** (a ordem de listas é semântica) |
| números | floats reescritos com `%.12g`; `NaN`/`Infinity` viram string |
| campos voláteis | normalizados para a string `"__volatile__"` (lista explícita) |
| nulos | `None` explícito, nunca campo omitido |
| encoding | UTF-8 sem BOM |
| finais de linha | `\n` |
| separadores | `(",", ":")` na forma compacta do hash |
| caminhos | relativos ao repositório, com `/` |

O hash de conteúdo é `sha256(canonical_json(content))`. O arquivo gravado contém
esse hash dentro de si (`content_sha256`) e é identado para leitura humana — o
hash é calculado sobre a forma compacta canônica, não sobre o arquivo indentado.

## 4. Teste executado

Duas execuções idênticas do mesmo estágio, com as mesmas entradas:

```
python tools/pipeline/build_panel.py --stage build --limit 12 --out-prefix det_run --force   (×2)
```

| verificação | resultado |
|---|---|
| `content_sha256` das duas execuções | `96599508ef6639e0…` **idêntico** |
| SHA-256 do arquivo de manifesto | `8624B904E3108D42…` **idêntico** |
| SHA-256 das saídas de dados | idêntico |
| `.run.json` | difere (timestamp e duração) — como esperado |

O merge dos blocos do build completo também é determinístico: duas execuções
produziram `a8329388f76dbb3e…` (conteúdo) e `6a95581c6bc8e43f…` (painel).

## 5. Onde ainda não é determinístico

| artefato | motivo | estado |
|---|---|---|
| `pam_quality_audit.json` | ainda usa `json.dump` com `generated_at` | **não migrado** |
| `climate_source_adjudication.json` | idem | **não migrado** |
| `independent_replication.json` | idem | **não migrado** |
| `bootstrap_calibration.json`, `applied_inference.json` | idem | **não migrado** |
| `full_build_validation.json` | idem | **não migrado** |

A infraestrutura (`manifest.write_manifest`) está pronta e é usada pelo pipeline
canônico e pelo merge. Migrar os demais é mecânico e está em `NEXT_ACTIONS.md`;
não foi feito aqui para não reescrever artefatos de auditoria já publicados nesta
mesma etapa.

## 6. Regra para artefatos novos

Todo manifesto novo usa `write_manifest`. Nenhum campo de tempo entra no
conteúdo canônico; se um campo precisar de data, ele vai para o `.run.json`.
