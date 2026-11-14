# SADEN V3.0 — Próximas ações

> A V3.0 está encerrada. P0–P3 concluídos; P4 é a pauta da V3.1.

## P0 — CAD (concluída)

- [x] Auditar o piloto e mudar a unidade de aquisição (UF em vez de município).
- [x] Validar 90 m × 450 m (correlação 0,99992) e bbox × polígono.
- [x] Adquirir a CAD para 1.296 de 1.296 municípios (0 sem dado).
- [x] Justificar a profundidade radicular com fonte (D99).

## P1 — Balanço e integração (concluída)

- [x] Reproduzir o balanço histórico (diferença máxima 1,05e-5 mm).
- [x] Corrigir o defeito da janela ZARC (D97) e quantificar o efeito.
- [x] Recalcular seis cenários de CAD na janela corrigida.
- [x] Gerar o painel integrado (`v30_panel_cad.csv`) sem sobrescrever o original.

## P2 — Modelos (concluída)

- [x] Reestimar M0/M1/M1b/M2 com cada definição de déficit (TE como referência).
- [x] Verificar o valor incremental do clima e da CAD.
- [x] Testar se a CAD explica o efeito do bloco no milho (**não** explica).

## P3 — Publicação (concluída)

- [x] Relatório `docs/V3_0_CAD_INTEGRATED_AGROCLIMATIC_REPORT.md`.
- [x] Decisões D96–D99.
- [x] Suíte **372/372**; bundle e publicação da branch.

## P4 — V3.1 (recomendações)

1. **Corrigir a janela em todas as variáveis**, não só no balanço:
   `precip_acumulada_mm`, `degree_days_total`, `extreme_heat_days`,
   `excess_total_mm`. Hoje só o balanço foi recalculado; as demais variáveis do
   painel continuam na janela histórica.
2. **Reestimar com o painel corrigido completo** e comparar com os números da
   V3.0.
3. **Investigar o bloco do milho** com tendência espacial (lat/lon), baseline de
   vizinhos históricos e interações UF×clima. Não usar efeitos fixos de bloco.
4. **Não adotar a CAD como preditor** sem ganho; mantê-la para descrição e
   balanço.
5. **Ampliar UFs** apenas após diagnóstico de representatividade por bioma e
   sistema produtivo.
6. Manter a **Ridge** como único modelo de preços.

## Bloqueios herdados

- ERA5-Land nativo: credencial CDS ausente (D83).
- CHIRPS/ARCO: sem DNS.
- Profundidade radicular por cultivar: sem fonte.
- Cobertura: 5–6 UFs de 27 — sem generalização nacional.
