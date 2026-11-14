# V3.3 — MASTER STATUS

**Versão:** V3.3 — forma funcional do balanço hídrico e auditoria da inferência
**Branch:** `v3/water-balance-inference-audit`
**Commit-base:** `3bf9360df205752d70b930ebe495d2bcf533fac4` (V3.2)
**Estado:** concluída

## Marcos verificados no início

| marco | valor confirmado |
|---|---|
| `main` / `archive/v1-final` / tag `v1-final` | `3f7ad33bc18c5a8e8e050bbc7817f5078488d625` |
| V3.0 | `40fd6aa226d1374964c8804adf614cf4747094d3` |
| V3.1 | `345b22e02b78447c94f0e6d5b316c3916d918283` |
| V3.2 | `3bf9360df205752d70b930ebe495d2bcf533fac4` |
| árvore / stash | limpa, sincronizada / vazio |
| bundle V3.2 | 16.753.528 B, SHA-256 `E8EB3F5A…598FE9A4` |
| suíte de referência | 410/410 |

## Resultado central

**Frente A — forma funcional.** Nenhuma especificação supera M2. Família
confirmatória (milho, 3 testes, Holm): p = 0,953 / 0,169 / 0,101 — nenhuma
rejeição. ΔMAE do bloco hídrico incremental: **+1,33 kg/ha** [−47,9; 49,8].
Nível **D** para ganho de generalização; **B** para a construção hídrica
(associação marginal, Holm 0,076, sem utilidade preditiva).

**Frente B — inferência histórica.**

| família | histórico | auditado (UF×ano + município) |
|---|---|---|
| V2.7 (21 hipóteses) | 4 Holm | **0 Holm** |
| V3.0 (15) | 10 Holm | **8 Holm** |
| V2.9 (9) | 1 Holm | **0 Holm** |

O que sobrevive é a associação do **déficit hídrico**; o que cai é a das
variáveis meteorológicas **brutas** e a interação por grupo de ciclo.

## Testes

| item | valor |
|---|---|
| suíte offline | **427/427** |
| novos testes V3.3 | 17 |
| `compileall` | limpo |
| números do relatório conferidos | **88/88** (`tools/v33_verify_report.py`, exit 0) |
| reprodução dos coeficientes históricos | dif. máx. 1,5×10⁻⁶ (V2.7) / 3,6×10⁻¹⁵ (V3.0) / 9,2×10⁻⁸ (V2.9) |
| reprodução dos p-valores históricos | `log10` máx. 5,3×10⁻⁴ (V2.7) / 6,8×10⁻⁴ (V3.0) |

## Bloqueios

* 5–6 UFs de 27 — nenhuma generalização nacional.
* Balanço **mensal**: duração em dias não existe (D109).
* ERA5-Land / CHIRPS seguem bloqueados (sem credencial / DNS).

## Próxima ação

`NEXT_ACTIONS.md`: prioridade única é testar a hipótese regional do bloco hídrico
(Sul a favor, Cerrado contra) com pré-registro próprio.
