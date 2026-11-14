# SADEN V3.0 — Log de execução

> Registro cronológico: etapa, arquivos, comandos, resultado, erros e commit.

## Sessão 1 — 2026-11-14

### Fase 0 — Recuperação e proteção

Auditoria: HEAD `adb525f`, branch `v2/regional-agroclimatic-robustness`
sincronizada, árvore limpa. `main` e `v1-final` em `3f7ad33`; V2.8 em
`a36e6be`; V2.9 em `adb525f`. Bundle da V2.9 conferido por `list-heads`
(27 refs), SHA-256 `7FDB0A74…38FA915`, *okay*. Suíte de referência **364/364**.

Branch `v3/cad-integrated-agroclimatic-panel` criada em `adb525f` (não existia
local nem remotamente).

### Fase 1 — Auditoria da aquisição

**Mudança de estratégia.** A V2.9 baixava 6 camadas por município (~7.800
requisições, ~5 h). Sondagem mostrou que o WCS aceita uma janela **por UF**:
MS 16,8 MB em 2,4 s; MT 37,8 MB em 4,0 s; PR 8,4 MB em 1,2 s. Com 36
requisições (6 UFs × 6 camadas) cobre-se o mesmo território — e, com o raster
alinhado, é possível mascarar o **polígono municipal** (D96).

Geometria disponível: `panel_municipalities.geojson` (158 MB, 1.782 feições
com `ibge_code`), fora do Git.

### Fase 2 — Validação de resolução e geometria

`tools/v30_cad_resolution_check.py` (18 municípios, mesma janela de ±0,35° e
mesma máscara):

* 90 m × 450 m — mediana 161,05 × 161,03 mm; diferença absoluta mediana
  0,15 mm; correlação **0,99992**; desvio-padrão 11,81 × 11,70 (corr 0,9993).
  A decimação **preserva** as estatísticas municipais.
* bbox × polígono (450 m) — diferença mediana 0,85 mm, máxima 10,3 mm,
  correlação 0,994. O bbox era aceitável, mas tem viés de forma.

### Fase 3 — Aquisição completa

`tools/v30_cad_acquire.py` (retomável por UF, escrita incremental):

```
BA 31 · GO 214 · MS 77 · MT 125 · PR 394 · RS 455 = 1.296 municípios
71,3 s · 610,3 MB · 0 municípios sem dado
```

CAD 0–100 cm: 105,1–256,9 mm (mediana 174,5). Por UF: MS 138,4 · MT 143,9 ·
BA 162,6 · GO 168,7 · PR 177,1 · RS 195,1. Fração válida mín. 0,605, mediana
1,000; 4 municípios abaixo de 0,90.

### Fase 4 — Profundidade radicular (D99)

Fontes obtidas na íntegra:

* **Embrapa Milho e Sorgo** — Albuquerque & Resende, *Cultivo do Milho —
  Irrigação*: "A profundidade efetiva do sistema radicular (Z) para o milho
  pode ser considerada variar entre **40 e 50 cm**".
* **Embrapa Soja** — Franchini et al., *Desenvolvimento radicular da soja
  visando tolerância à seca*: raízes avaliadas até **100 cm**, com **6–12% da
  área radicular na camada 75–100 cm** (33–56% em 0–25, 12–28% em 25–50,
  11–21% em 50–75).

Decisão: soja 0–100 cm; milho 0–60 cm (mais próximo de 40–50 cm nas camadas
publicadas); milho 2ª safra como cenário explicitamente identificado.

### Fase 5 — Balanço hídrico e defeito da janela (D97)

**Defeito encontrado.** O painel compara `months[0] <= data <= months[-1]` com
`months[-1] = "AAAA-MM"`; como `"2017-12-01" > "2017-12"`, o mês final é
excluído. Confirmado: **28.282 de 40.990 linhas** com `len(months) !=
balance_months`; nas 19.402 linhas analíticas, todas perdem ~31 dias.

`tools/v30_recalculate_panel.py` recalcula as duas janelas e seis cenários de
CAD:

* reprodução da janela histórica com CAD=50: **19.402 pares**, diferença
  máxima **1,05e-5 mm** (resíduo de float32) — pipeline fiel;
* janela corrigida vs histórica (mesma CAD): déficit razão mediana **1,236**
  (p10 1,0; p90 3,78); precipitação +135,4 mm e ET0 +165,1 mm medianos;
* CAD oficial com janela corrigida: déficit razão mediana 0,622 (0–60),
  **0,139 (0–100)** e 0,000 (0–200); 20,3% / 43,6% / 82,9% dos casos com
  déficit eliminado; **nenhum** caso com razão > 1.

### Fase 6 — Reestimação dos modelos (D98)

`tools/v30_models_cad.py`, `climate_plus_state`, equalização por célula,
3 repetições, TE como referência:

| Cultura | clima | déficit hist. | 50 mm corrigido | CAD 0–100 | CAD 0–200 |
|---|---|---|---|---|---|
| soja (TE, M2−M1) | −6,3 n.s. | **+10,6 [0,7;21,5]** | −20,0 n.s. | −10,3 n.s. | −6,9 n.s. |
| milho | −198,7 | −167,1 | −195,2 | −142,8 | −21,7 n.s. |
| milho 2ª | −267,2 | n.s. | n.s. | n.s. | n.s. |

Nenhuma especificação com CAD oficial melhora a predição. Na soja, o déficit
da janela histórica era **pior que a média da UF** e a correção da janela
reverte o sinal.

`tools/v30_association_cad.py` (within, EP por bloco, 15 hipóteses, Holm):

| Cultura | hist | corr 50 | 0–60 | 0–100 | 0–200 |
|---|---|---|---|---|---|
| soja | −1,26 | −2,45 | −2,40 | −2,32 | −2,29 |
| milho | −3,04 | −2,44 | −2,60 | −2,78 | −2,01 |
| milho 2ª | n.s. | n.s. | n.s. | n.s. | n.s. |

10 de 15 sobrevivem ao Holm. O coeficiente da soja fica estável enquanto a
média do déficit cai de 138,5 para 13,8 mm — a CAD reescala quase
proporcionalmente.

### Fase 7 — Mecanismo espacial do milho

Efeito do bloco (SS−SE) no milho: −209,5 (déficit histórico) → −203,4
(50 mm corrigido) → −225,4 (CAD 0–100) → −286,1 (CAD 0–200). A
heterogeneidade espacial **cresce** com a CAD oficial: não era deficiência de
representação do solo.

### Fase 8–9 — Síntese e encerramento

`docs/V3_0_CAD_INTEGRATED_AGROCLIMATIC_REPORT.md`; decisões D96–D99; suíte
**372/372**; bundle e publicação.
