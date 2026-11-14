# SADEN V2.7 — Próximas ações

> Ordem de prioridade. Itens **em andamento** no momento da última
> atualização estão marcados com `[~]`; concluídos, com `[x]`.

## P0 — Concluir a execução em curso

- [~] **Calibração Monte Carlo do bootstrap wild** (`v27_wild_bootstrap_calibration.json`)
  — processo em segundo plano; casos gravados incrementalmente; grade de
  84 casos (DGP `agrupado` e `painel_fe`; 3 sementes; 1% / 5% / 10%).
  *Ação*: aguardar a conclusão, ler as taxas por nível nominal e
  consolidar no relatório.
- [~] **Inferência com bootstrap em todos os esquemas**
  (`v27_robust_inference.json`) — gravada por cultura; ao final, conferir
  `multiplicity` para os 4 esquemas de bootstrap.
- [~] **Validação territorial por blocos espaciais** (P1–P4)
  (`v27_spatial_validation.json`) — holdout por município, por célula
  MERRA-2, por bloco de 250 km e leave-one-UF-out.
- [ ] **Recalcular a inferência** se a calibração indicar ajuste de
  política de nulidade (D81) — os p-valores ficam registrados nos dois
  ramos, então o recálculo é opcional e deve ser justificado.

## P1 — Consolidação científica

- [ ] Consolidar a **comparação V2.6 × V2.7** respondendo as 12 perguntas
  do item 12 do plano (fase de consolidação).
- [ ] Atualizar `docs/DECISIONS.md` com D76–D84 (mirror de
  `DECISIONS_V2_7.md`).
- [ ] Atualizar `docs/PROJECT_STATUS.md`, `docs/PROJECT_ROADMAP.md`,
  `docs/API_SOURCES.md`, `docs/CONTEXTO_V2.md`,
  `docs/AI_CONTEXT_RECOVERY.md` e o README de `geospatial/`.
- [ ] Escrever os relatórios da V2.7 em `docs/` (inferência espacial,
  fenologia, CAD, calibração).

## P2 — Testes e reprodutibilidade

- [x] Suíte nova `geospatial/tests/test_v27_robustness.py` (47 testes).
- [x] Suíte completa: **309/309** offline; 10/10 externos opt-in.
- [ ] Rodar novamente a suíte **após** a consolidação (a documentação não
  altera código, mas o commit final deve registrar o número exato).

## P3 — Git, bundle e publicação

- [ ] Commitar por marcos científicos:
  1. `fix(v2.7): bootstrap wild com pesos por grupo (CGM) e forma vetorizada`
  2. `feat(v2.7): inferencia espacial por esquema, Conley e Holm`
  3. `feat(v2.7): modulo fenologico e experimento de janela`
  4. `feat(v2.7): CAD territorial da Embrapa Solos`
  5. `docs(v2.7): consolidacao, decisoes D76-D84 e manifests`
- [ ] Bundle: `saden-v2-7-final-2026-11-14.bundle` em
  `C:\Users\luanf\OneDrive\Área de Trabalho\SADEN_V2_7_RECOVERY_2026-11-14`
  (registrar tamanho, SHA-256 e `git bundle verify`).
- [ ] Publicar `v2/agroclimatic-robustness` no remoto (sem force push,
  sem merge em `main`).

## P4 — V2.8 (recomendações, fora do escopo da V2.7)

- [ ] **Ampliação nacional do painel**: o diagnóstico de cobertura é
  obrigatório antes de qualquer aquisição massiva (critérios de D69).
- [ ] **CAD no balanço hídrico**: substituir os cenários 35/50/70 mm pela
  CAD geoespacial, em **linha experimental** com comparação explícita.
- [ ] **Identificação de cultivar** (ou estratificação por grupo de
  maturação a partir do ZARC) para eliminar o cenário fenológico.
- [ ] **Validação do ganho territorial** com o modelo climatico sob
  dependência espacial corrigida: se o ganho não sobreviver, isso deve ser
  reportado, não corrigido.

## Pendências bloqueadas (não bloqueiam a V2.7)

- [ ] ERA5-Land nativo: requer `CDS_API_KEY` ou `~/.cdsapirc`. **Não** criar
  conta nem solicitar credencial por chat (D83).
- [ ] CHIRPS/ARCO: sem resolução DNS. Não repetir sem mudança de rede.
