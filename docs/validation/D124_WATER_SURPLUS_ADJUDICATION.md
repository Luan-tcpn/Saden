# SADEN — Adjudicação matemática do excedente hídrico (D124)

**Data:** 2026-11-14
**Código:** `geospatial/agroclimate/corrections.py` (`sequential_water_balance`),
`tools/independent_replication/water_balance_reference.py`
**Testes:** `geospatial/tests/test_consolidation.py::test_reference_overstates_excess_on_partial_refill`

---

## 1. A equação de Thornthwaite & Mather (1955)

Balanço sequencial mensal, com `P` = precipitação, `ETP` = demanda, `CAD` =
capacidade de água disponível, `ARM` = armazenamento:

```
saldo = P − ETP

se saldo ≥ 0:                          se saldo < 0:
    ETR = ETP                              disponível = ARM_anterior + P
    ARM = min(CAD, ARM_anterior + saldo)   ETR = min(ETP, disponível)
    EXC = max(0, ARM_anterior + saldo − CAD)   ARM = max(0, disponível − ETR)
    DEF = 0                                DEF = ETP − ETR
                                           EXC = 0
```

O ponto crítico é `EXC`: ele é o que **transborda**, isto é, o saldo que excede a
capacidade de reposição restante `(CAD − ARM_anterior)`.

## 2. Caso mínimo reproduzível

CAD = 50 mm. Mês 1 consome 10 mm do solo; mês 2 tem saldo positivo de 15 mm.

| etapa | P | ETP | ARM anterior | saldo | ARM final | ETR | DEF | **EXC correto** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| mês 1 | 0 | 10 | 50 | −10 | 40 | 10 | 0 | 0 |
| mês 2 | 20 | 5 | 40 | **+15** | 50 | 5 | 0 | **5** |
| **total** | | | | | | 15 | 0 | **5** |

Cálculo manual do mês 2: há 10 mm de capacidade livre (`50 − 40`). Dos 15 mm de
saldo, **10 mm repõem** o solo e **5 mm transbordam**. `EXC = 40 + 15 − 50 = 5`.

A implementação de referência devolve **15 mm** — o saldo inteiro.

## 3. Origem exata da diferença

No código de referência (`water_balance.sequential_water_balance`, ramo
`saldo >= 0`):

```python
storage = min(cad_mm, storage + balance)          # já virou 50
exc = max(0.0, storage + balance - cad_mm) ...    # condição avaliada DEPOIS
if storage >= cad_mm:                             # verdadeiro em todo mês que satura
    exc = max(0.0, balance)                       # ← saldo bruto, não o transbordo
    storage = cad_mm
```

A variável `storage` é **rebaixada para `CAD` antes** do teste `storage >= cad_mm`.
Com isso o teste fica verdadeiro em todo mês que satura — inclusive quando o solo
estava parcialmente vazio — e `exc` recebe `saldo` em vez de
`ARM_anterior + saldo − CAD`. O erro é
`CAD − ARM_anterior` (10 mm no caso acima).

## 4. Adjudicação

**A formulação correta é a do módulo independente** — não por preferência, mas
porque o excedente é definido como transbordo. A implementação de referência
satisfaz a definição apenas quando `ARM_anterior = CAD` (solo já saturado), que é
o caso em que os dois cálculos coincidem.

Verificação de consistência física na versão corrigida
(`test_balance_conserves_water`):

```
P_total = ETR_total + EXC_total + (ARM_final − ARM_inicial)
```

Essa identidade **falha** na versão de referência sempre que há reposição
parcial — prova independente de que o excedente de lá está inflado.

## 5. Alcance do defeito

| componente | afetado? |
|---|---|
| `EXC` (excedente) | **sim** — superestimado |
| `ARM` (armazenamento) | não — `min(CAD, ...)` está correto |
| `ETR` | não — `ETR = ETP` no ramo positivo |
| `DEF` (déficit) | não |
| ET0 | não |
| `deficit_total_mm`, `etr_over_etp`, `stress_share` | não |

**Frequência do gatilho:** exige um mês com saldo positivo que **sature** a CAD a
partir de `ARM < CAD`. Em 45 janelas reais verificadas na etapa anterior, **não
ocorreu nenhuma vez** — porque a janela começa com `ARM = CAD` e a chuva tropical
costuma saturar de imediato. O defeito é real, mas de magnitude não medida no
painel completo.

## 6. Dependência científica

Verificação de dependências sobre os artefatos publicados:

| artefato | usa `excess`? |
|---|---|
| V3.1 `v31_panel_windows.csv` | colunas geradas, não usadas em modelo |
| V3.3 `v33_inference_audit.json` | **sim** — `soja`, `milho`, `milho_2` testados |
| classificação na V3.3 | `mantida_apenas_bruta`, `mantida_apenas_bruta`, `sem_evidencia_em_nenhum` |
| V3.4, V3.5 | não |

**Nenhuma conclusão publicada depende do excedente**: as três variáveis já haviam
sido classificadas como não sustentadas após correção de multiplicidade. A
afirmação da etapa anterior se confirma.

## 7. Decisão

- **Não** se corrige `water_balance.py` retroativamente: isso quebraria a
  reprodução bit a bit de V2.6–V3.5.
- A formulação correta está em `agroclimate/corrections.py` e é a usada pelo
  pipeline canônico a partir desta etapa (`physics_version =
  consolidated-2026-11-14`).
- Artefatos históricos permanecem intactos.
- Qualquer uso futuro de excedente usa a versão corrigida.

## 8. Testes físicos

Cobrem solo vazio, parcialmente armazenado e saturado; chuva menor e maior que a
capacidade de reposição; ETP elevada; armazenamento esgotado; transição entre
meses; e CAD = 0. Nove casos no total, todos com resultado calculado à mão.

## 9. Limitação registrada

A magnitude agregada do erro no painel completo **não foi medida** (exigiria o
balanço mensal de todas as 30.207 janelas com a fórmula de referência, que não é
o caminho canônico). Como nenhuma análise publicada usa `excess`, a lacuna não
afeta conclusão alguma.
