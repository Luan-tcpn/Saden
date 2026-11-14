# Fechamento — estado da determinização de manifestos

**Data:** 2026-11-14 · Detalhe: `docs/reproducibility/DETERMINISTIC_MANIFESTS.md`

## Implementado

`tools/pipeline/manifest.py`: conteúdo canônico em `<nome>.json`, metadados em
`<nome>.json.run.json`.

## Verificado

| teste | resultado |
|---|---|
| duas execuções do mesmo build | `content_sha256` **idêntico** (`96599508…`) |
| SHA-256 do arquivo de manifesto | **idêntico** (`8624B904…`) |
| SHA-256 das saídas de dados | idêntico |
| `.run.json` | difere (timestamp/duração) — esperado |
| merge de blocos executado duas vezes | hashes idênticos (`a8329388…` / `6a95581c…`) |

## Migrado

- `panel_canonical_build_v2.json` (build e merge)
- estrutura pronta para os demais

## Não migrado (mecânico, pendente)

`pam_quality_audit.json`, `climate_source_adjudication.json`,
`independent_replication.json`, `bootstrap_calibration.json`,
`applied_inference.json`, `full_build_validation.json`.

Motivo de não migrar nesta etapa: são artefatos de auditoria publicados nesta
mesma execução; reescrevê-los agora criaria duas versões do mesmo laudo. Está em
`NEXT_ACTIONS.md`.
