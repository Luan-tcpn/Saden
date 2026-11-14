# SADEN V2.7 — Próximas ações

> Ordem de prioridade. A V2.7 está **encerrada**; os itens P0–P3 foram
> concluídos nesta sessão de continuidade. P4 é a pauta da V2.8.

## P0 — Execução em curso (concluída)

- [x] **Calibração Monte Carlo do bootstrap wild** — 84 casos concluídos,
  **recalculados** após as correções D85 (anterior contaminado por
  réplicas com erro-padrão nulo e por DGP com coluna nula).
- [x] **Inferência com bootstrap em todos os esquemas** —
  `v27_robust_inference.json`, 105 bootstraps, 999/999 réplicas cada.
- [x] **Validação territorial P1–P4** — reproduzida bit a bit.
- [x] **P5 (bloco × ano)** — novo protocolo (D86), incluído em
  `v27_spatial_validation.json`.
- [x] **Manifesto de dependência espacial** — `run_robustness.py
  dependence` executado; `v27_spatial_dependence.{json,csv}` versionados.
- [x] Recalcular a inferência após D85: **desnecessário** — verificado que
  nenhuma réplica degenerada existia nos resultados publicados.

## P1 — Consolidação científica (concluída)

- [x] Comparação V2.6 × V2.7 no relatório (§14) e resumo executivo (§1).
- [x] `docs/DECISIONS.md` com D76–D86.
- [x] Relatório `docs/V2_7_ROBUSTNESS_REPORT.md` com números de P1–P5 e da
  calibração corrigida.
- [x] `MASTER_STATUS.md`, `EXECUTION_LOG.md`, `DECISIONS_V2_7.md`
  atualizados.
- [x] Correção de rastreabilidade: a tabela do correlograma agora vem do
  manifesto, não de script em `tmp/`.

## P2 — Testes e reprodutibilidade (concluída)

- [x] `geospatial/tests/test_v27_robustness.py`: 56 testes da V2.7.
- [x] Suíte completa: **318/318** offline; 10/10 externos opt-in.
- [x] Novos invariantes: réplica com pesos +1 reproduz a estatística
  observada (OLS e within) e ausência de vazamento em P5.

## P3 — Git, bundle e publicação (concluída)

- [x] `chore(v2.7)`: checkpoint de recuperação dos artefatos (`ac41210`).
- [x] `fix(v2.7)`: SE degenerado, DGP da calibração e protocolo P5
  (`feb309d`).
- [x] Commits de consolidação (manifests + documentação).
- [x] Bundle `saden-v2-7-final-2026-11-14.bundle` em
  `SADEN_V2_7_RECOVERY_2026-11-14`, com `git bundle verify` e SHA-256.
- [x] Publicação de `v2/agroclimatic-robustness` no remoto (sem force
  push, sem merge em `main`).

## P4 — V2.8 (recomendações, fora do escopo da V2.7)

- [ ] **P5 por cultura e por família**: a soja inverte de sinal em P5 e o
  milho 2ª safra não se move. Investigar por que — provável diferença de
  escala de heterogeneidade regional entre as culturas — antes de qualquer
  alegação de ganho territorial.
- [ ] **Linha de base territorial mais forte**: comparar com média
  municipal quando disponível em esquemas que preserve algum histórico, e
  com efeitos fixos de município, para não depender da média agregada.
- [ ] **P4 com poucos grupos**: 5–6 UFs tornam o leave-one-UF-out não
  conclusivo; usar agrupamento por macrorregião ou descartar o protocolo.
- [ ] **Ampliação nacional do painel**: o diagnóstico de cobertura é
  obrigatório antes de qualquer aquisição massiva (critérios de D69).
- [ ] **CAD no balanço hídrico**: substituir os cenários 35/50/70 mm pela
  CAD geoespacial, em linha experimental com comparação explícita.
- [ ] **Identificação de cultivar** (ou estratificação por grupo de
  maturação do ZARC) para eliminar o cenário fenológico.
- [ ] **Wireup na aplicação**: o painel agroclimático e os métodos de
  inferência são pesquisa; nenhum deles entra na previsão de preços da V1
  (Ridge) sem ganho preditivo temporal demonstrado.

## Pendências bloqueadas (não bloqueiam a V2.7)

- [ ] ERA5-Land nativo: requer `CDS_API_KEY` ou `~/.cdsapirc`. **Não**
  criar conta nem solicitar credencial por chat (D83).
- [ ] CHIRPS/ARCO: sem resolução DNS. Não repetir sem mudança de rede.
