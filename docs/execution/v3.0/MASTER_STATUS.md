# SADEN V3.0 — Status da execução

> Etapa: **V3.0 — CAD integrada, reconstrução do painel agroclimático e
> validação da generalização territorial**. Atualizado em: 2026-11-14.

## Objetivo

Concluir a integração da informação oficial de solo, recalcular o balanço
hídrico com representação realista da CAD e reavaliar os modelos
agroclimáticos, investigando se a heterogeneidade espacial do milho era
consequência da representação incompleta da água no solo.

## Identificação da linha

| Item | Valor |
|---|---|
| Repositório | `C:\Users\luanf\OneDrive\Área de Trabalho\Saden_AgroClima` |
| Branch | `v3/cad-integrated-agroclimatic-panel` (base `adb525f` = V2.9) |
| V2.9 preservada | `v2/regional-agroclimatic-robustness` em `adb525f`, publicada |
| Bundle V2.9 | `..\SADEN_V2_9_RECOVERY_2026-11-14\`, SHA-256 `7FDB0A74…38FA915`, *okay*, 27 refs |
| V1 / `main` | `3f7ad33` (tag `v1-final`) — intactas |
| Suíte de referência | **364/364** ao abrir a V3.0 |
| Suíte atual | **372/372** |

## Estado das fases

| Fase | Item | Estado |
|---|---|---|
| 0 | Auditoria, bundle, branch, suíte de referência | **concluída** |
| 1 | Auditoria da CAD e do plano de aquisição | **concluída** (D96) |
| 2 | Comparação 90 m × 450 m e bbox × polígono | **concluída** |
| 3 | Aquisição da CAD (1.296 municípios) | **concluída** — 0 sem dado |
| 4 | Profundidade radicular e CAD efetiva | **concluída** (D99) |
| 5 | Balanço hídrico e integração ao painel | **concluída** (D97) |
| 6 | Reestimação M0/M1/M1b/M2 | **concluída** (D98) |
| 7 | Mecanismo espacial do milho | **concluída** |
| 8 | Síntese científica | **concluída** |
| 9 | Validação e publicação | **em curso** |

## Cobertura da CAD

| Item | Valor |
|---|---|
| Municípios solicitados | **1.296** (universo do painel analítico) |
| Concluídos | **1.296** |
| Sem dado | **0** |
| Requisições | 36 (6 UFs × 6 camadas) |
| Tempo / volume | 71 s / 610 MB |
| CAD 0–100 cm | 105,1 – 256,9 mm (mediana 174,5) |
| Fração válida | mín. 0,605; mediana 1,000; 4 municípios < 0,90 |

## Achados centrais

1. **A janela ZARC do painel histórico perde o último mês** (D97): 28.282 de
   40.990 linhas; nas 19.402 analíticas, todas perdem ~31 dias. Com CAD=50, o
   déficit cresce (razão mediana 1,236) e precipitação/ET0 sobem (+135,4 /
   +165,1 mm medianos).
2. **A CAD oficial está integrada** (D96): 1.296/1.296 municípios, por
   polígono, com distribuição municipal preservada.
3. **A CAD não melhora a predição** (D98) e **não explica o efeito do bloco no
   milho** — que cresce de −209 (histórico) para −286 (0–200 cm) em SS−SE.
4. **A associação é robusta** à definição de déficit: coeficiente da soja
   −1,26 → −2,45 → −2,29 com a CAD, enquanto a média do déficit cai 10×.
5. **Profundidade radicular justificada** (D99): soja 0–100 cm (Franchini et
   al., Embrapa Soja); milho 40–50 cm (Embrapa Milho e Sorgo).

## Manifestos

`v30_cad_polygon.json` (+ csv) · `v30_cad_resolution_check.json` ·
`v30_balance_recalc.json` (+ `v30_panel_cad.csv`) ·
`v30_models_cad.json` · `v30_association_cad.json`.

## Próxima ação executável

Nada pendente na V3.0. V3.1: usar a janela corrigida como protocolo padrão,
reavaliar o painel INMET, e investigar o bloco do milho com variáveis
espaciais explícitas.

## Bloqueios

- Profundidade radicular por cultivar: sem fonte cultivar-específica.
- ERA5-Land: credencial CDS ausente (D83). CHIRPS/ARCO: sem DNS.
- Cobertura territorial: 5–6 UFs de 27 — sem generalização nacional.
