# V3.5 — MASTER STATUS

**Versão:** V3.5 — expansão de SP, identificação dentro da UF e rebaseline
**Branch:** `v3/sp-within-state-validation`
**Commit-base:** `b9e7098db32b7b108dab5aa92f9d2cb08a1f1362` (V3.4)
**Estado:** concluída

## Marcos verificados no início

| marco | valor |
|---|---|
| `main` / `archive/v1-final` / tag `v1-final` | `3f7ad33` |
| V3.0 / V3.1 / V3.2 / V3.3 / V3.4 | `40fd6aa` / `345b22e` / `3bf9360` / `6eff88c` / `b9e7098` |
| árvore / stash | limpa, sincronizada / vazio |
| bundle V3.4 | 17.305.790 B, SHA-256 `49A584F3…D33BFAA5` |
| suíte de referência | 442/442 |

## Resultado central

SP entrou com **645 municípios** (582 com painel utilizável), somando **10.774
linhas** ao painel (+55,8%). Pela primeira vez há uma UF com **MRS 1 (44) e MRS 3
(168)**. O contraste regional, testado pela primeira vez dentro de um estado,
**não aparece**: soja D = **+7,3 kg/ha** [−18,8; 26,9], interação p = 0,77.

Reprodução da V3.4: **exata** (M2 = 1.661,2 / 592,7 / 1.272,3; D = −78,3 / −35,0
/ −22,5).

## Números do painel

| indicador | V3.4 | V3.5 |
|---|---:|---:|
| UFs | 6 | 7 |
| municípios | 1.274 | 1.856 |
| linhas | 19.307 | 30.081 |
| % do território indicado | 33,25% | 48,3% |

## Testes

| item | valor |
|---|---|
| suíte offline | **458/458** (442 herdados + 16 novos) |
| `compileall` | limpo |
| números verificados | **72/72** (`tools/v35_verify_report.py`, exit 0) |

## Bloqueios

* MRS 1 em SP: 178 linhas de soja (~20 municípios) e 7 anos — poder limitado.
* Produção nacional não estimável (PAM cobre 7 UFs).
* Milho 2ª: PAM publica total anual (limitação herdada).

## Próxima ação

`NEXT_ACTIONS.md`: integrar **MG** (852 municípios, MRS 2 e 3).
