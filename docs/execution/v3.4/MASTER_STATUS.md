# V3.4 — MASTER STATUS

**Versão:** V3.4 — hipótese regional do bloco hídrico
**Branch:** `v3/regional-water-block-hypothesis`
**Commit-base:** `6eff88c2a00c8df5529f7e4a1c352ffe25e81b1d` (V3.3)
**Estado:** concluída

## Marcos verificados no início

| marco | valor confirmado |
|---|---|
| `main` / `archive/v1-final` / tag `v1-final` | `3f7ad33bc18c5a8e8e050bbc7817f5078488d625` |
| V3.0 / V3.1 / V3.2 | `40fd6aa` / `345b22e` / `3bf9360` |
| V3.3 | `6eff88c` = `origin/v3/water-balance-inference-audit` |
| árvore / stash | limpa, sincronizada / vazio |
| bundle V3.3 | 16.865.810 B, SHA-256 `C6A863C4…BE617763D` |
| suíte de referência | 427/427 |

## Resultado central

O contraste existe e é grande (milho: D = **−78,3 kg/ha**, IC UF×ano
[−131,7; −26,7], estável em LOO-UF e LOO-ano; interação associativa
−1.287 kg/ha/100 mm, p = 1,8×10⁻⁶). **Mas não é identificável como efeito
regional**: Cramér's V = 1,000 entre região e UF, nenhuma UF nos dois grupos.
Classificação: **Nível E**.

Além disso, a fronteira testada não organiza o fenômeno: dentro do PR, MRS 1 ×
MRS 2 difere em +1.012 kg/ha/100 mm (p = 0,0022), e MS-MRS3 (Cerrado) comporta-se
como o Sul.

## Testes

| item | valor |
|---|---|
| suíte offline | **442/442** (427 herdados + 15 novos) |
| `compileall` | limpo |
| números do relatório verificados | **86/86** (`tools/v34_verify_report.py`, exit 0) |
| figuras | 6, em `docs/figures/v34/`, inspecionadas |

## Bloqueios

* **Identificação**: exige uma UF com municípios em MRS 1 e MRS 3/4. Só SP.
* **Produção nacional**: PAM do repositório cobre 6 UFs; não se estima
  participação nacional.
* **Classificação de soja para milho**: aproximação declarada; não há lista
  municipal oficial de milho equivalente.

## Próxima ação

`NEXT_ACTIONS.md`: expansão de cobertura para **SP** (D115).
