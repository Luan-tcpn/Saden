# SADEN V2.8 — Log de execução

> Registro cronológico. Cada entrada: etapa, arquivos, comandos, resultado,
> erros/correções e commit.

## Sessão 1 — 2026-11-14

### Fase 0 — Proteção e preparação

**Auditoria.** Diretório confirmado. HEAD `36bf5d7`, branch
`v2/agroclimatic-robustness` sincronizada com `origin`. Árvore limpa exceto
`.commandcode/` (metadados de ferramenta, não versionados). Tags `v1-final`
(e62a5372 → 3f7ad33) e `v2-poc-sentinel2` intactas.

**Bundle V2.7.** `SADEN_V2_7_RECOVERY_2026-11-14\saden-v2-7-final-2026-11-14.bundle`:
15.253.577 bytes, SHA-256 `0AB3CDF2A0D17E6FE5A4B74D564682CFEBE5647EECAD55EE041D8E6AC704B9C9`,
`git bundle verify` → *okay*, 23 refs (11 branches locais, 11 de `origin`, 2
tags, `HEAD`). Conferido por `list-heads`, não apenas pelo `verify`.

**Branch.** `v2/temporal-spatial-generalization` criada em `36bf5d7` (não
existia local nem remotamente).

**Suíte de referência.** `pytest geospatial/tests -q` → **318 passed**
(14,2 s). Base de partida confirmada.

**Docs.** `docs/execution/v2.8/{MASTER_STATUS,EXECUTION_LOG}.md` criados.

**Checkpoint.** `8f49092`.

### Fase 1 — auditoria e reprodução de P1/P3/P5

**Estrutura medida** (painel NASA-POWER, 19.402 linhas):
soja 8.884 linhas / 1.225 municípios / 46 blocos / 5 UFs / 8 anos;
milho 7.616 / 1.063 / 49 / 6 / 8; milho 2ª 2.902 / 505 / 30 / 4 / 9.

Ponto decisivo: **os três protocolos preveem cada linha exatamente uma vez** —
os conjuntos de teste são idênticos (8.884 linhas em P1, P3 e P5). Logo as
MAEs são comparáveis, e a diferença entre protocolos é só de treino. O P5
treina em 64,0% das linhas e o P3 em 80% — a "redução de 36%" é relativa ao
total; **relativa ao P3 é 20%**.

**Fórmula do ganho confirmada**: `100 × (MAE_base − MAE_modelo) / MAE_base`
em `run_robustness.py::cmd_spatial`.

### Fase 2 — fatorial espaço × tempo (D87)

`geospatial/agroclimate/generalization.py` + `tools/s28_factorial.py`.
Braços SS/SE/TS/TE sobre a grade do P5, reamostragem estratificada por bloco
com 5 repetições para igualar o treino, IC por bootstrap de bloco.

**Validação do desenho:** `SE` = P3 (612,724390) e `TE` = P5 (661,802276),
idênticos ao publicado — coberto por teste.

**Resultado (equal-size, família B):** soja 609,2/612,7/649,0/661,7;
milho 1583,7/1677,4/1590,6/1696,7; milho 2ª 1179,7/1197,7/1188,5/1218,2.
Efeito espaço (SS−SE): −3,6 n.s. (soja), −93,7 (milho), −18,0 (milho 2ª).
Efeito tempo (SS−TS): −39,8 (soja), −6,9 n.s. (milho), −8,8 (milho 2ª).

**Hipótese de tamanho refutada:** MAE integral e equalizada diferem ≤ 1 kg/ha.

**Checkpoint.** `1ca7a95`.

### Fase 3 — linhas de base e comparação justa

Três referências do mesmo treino (`global`, `state`, `state_year`) e duas
variantes de modelo (`climate_only`, `climate_plus_state`).

Achado que muda a leitura publicada: `climate_only` vs média da UF = **+43,2
kg/ha (pior)** na soja; vs média nacional = −17,0 com IC95 [−44,9; +3,0], isto
é, **o ganho publicado não é significativo** sob dependência espacial. Com
dummies de UF, o modelo supera a média da UF em −13,1 [−25,7; −0,6].

Ressalva de disponibilidade: a média UF×ano usa produtividade contemporânea e
**não** é referência operacional; nos braços que removem o ano ela colapsa
exatamente na média da UF (verificado por teste).

### Fase 4 — CAD no balanço hídrico (D88)

`tools/s28_cad_balance.py`. Unidade validada numericamente (AW máx. 2,59 > 1,0
descarta cm³/cm³). Balanço anual (Thornthwaite & Mather, ET0 FAO-56) em 9
municípios (o 10º não está na base diária).

Déficit mediano: 50 mm = 784,2; 35 mm +3,5%; 70 mm −2,6%;
0–60 cm −9,8%; **0–100 cm −18,6%**; 0–200 cm −42,3%. 33 de 90 município-anos
mudam > 25%. Cobertura no painel: **5 de 1.296 municípios** (0,39%; 82 de
19.402 linhas). Integração em escala bloqueada por cobertura.

### Fase 5 — ciclo do ZARC (D89)

`tools/s28_cycle_stratification.py`. `zarc_cycle` não é carregado por
`analysis.prepare_rows`; a junção por `(ibge_code, crop, ano de colheita)`
sobre o painel bruto deu 0 duplicatas e 0 não correspondidos.

Composição: soja 89% classe 22; milho 79% classe 22; milho 2ª 62% classe 21.
Déficit por classe: soja −0,876 (t=−3,89) na 22 e +0,691 (t=0,74) na 21;
milho negativo nas três; milho 2ª sem associação. Temperatura na soja
**inverte**: −65,0 (t=−3,18) vs +182,7 (t=+4,38). Duração modal da janela ZARC
difere por classe. Rótulo "precoce/médio/tardio" **não** foi atribuído: o
dicionário de dados do ZARC não está nos artefatos.

**Checkpoint.** `1307ad8` (baselines + CAD).

### Fase 6 — cobertura

Reaproveitado `v27_panel_coverage.json` (3.564 pares; 2.281 elegíveis; decisão
de não ampliar mantida). Lacunas novas medidas: CAD 0,39% dos municípios;
3 classes de ciclo com forte concentração; 4–6 UFs (P4 degenerado).

### Fase 7–8 — síntese e encerramento

`docs/V2_8_GENERALIZATION_REPORT.md` (20 seções), decisões D87–D89 em
`docs/DECISIONS.md`, suíte **338/338**, bundle e publicação da branch.

