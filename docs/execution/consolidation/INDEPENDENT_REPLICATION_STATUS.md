# Consolidação — estado da replicação independente

**Data:** 2026-11-14
Código: `tools/independent_replication/water_balance_reference.py`
Relatório: `docs/statistics/INDEPENDENT_REPLICATION.md`

---

## O que existia antes

Apenas **verificadores de transcrição**: `v33_verify_report.py` e sucessores
comparam números do relatório com os manifests. Isto detecta erro de cópia, não
erro de cálculo. Se a fórmula estivesse errada e o manifesto registrasse o valor
errado, a verificação passaria.

## O que existe agora

Reimplementação independente de:

| cálculo | equação | independência |
|---|---|---|
| balanço sequencial | Thornthwaite & Mather (1955) | não importa `agroclimate.water_balance` |
| ET0 diária | FAO-56, Allen et al. (1998) eq. 6 | não chama `fao56_penman_monteith` |

## Resultados

| verificação | resultado |
|---|---|
| casos manuais calculados à mão | **8/8** |
| janelas reais comparadas | **90** |
| diferença máxima no déficit | **4,3 × 10⁻⁶ mm** |
| diferença mediana | 9,8 × 10⁻⁷ mm |
| diferença relativa máxima | ~10⁻⁸ |
| divergência de ET0 (mediana) | −1,1% (p05 −7,7%, p95 +6,7%) |
| reproduzido em clone limpo | sim (36 janelas, 6,3 × 10⁻⁶ mm) |

**Interpretação:** o déficit sazonal publicado é aritmeticamente correto. A
diferença residual é ordem de soma em ponto flutuante sobre dados `float32`.

## Defeito encontrado — D124

O excedente é **superestimado** quando um mês de saldo positivo satura a CAD a
partir de armazenamento parcial.

| mês | P | ETP | ARM anterior | ARM final | EXC correto | EXC da referência |
|---|---:|---:|---:|---:|---:|---:|
| 2020-01 | 0 | 10 | 50 | 40 | 0 | 0 |
| 2020-02 | 20 | 5 | 40 | 50 | **5** | **15** |

**Alcance:** déficit, armazenamento, ETR e ET0 **não** afetados. Gatilho não
ocorreu em 45 janelas reais verificadas. As variáveis de excedente já haviam
sido classificadas como não sustentadas na V3.3.

**Decisão:** não corrigir a biblioteca (quebraria a reprodução bit-a-bit da
V3.5). A formulação correta está implementada e testada no módulo independente.

## Divergência de ET0 — não é erro de aritmética

Duas diferenças de convenção:

1. `es(Tmean)` (referência) vs `es(Tmax,Tmin)` (FAO-56 eq. 12).
2. Vento: a referência aplica fator 0,4 a um dado que já está a 2 m, deixando
   `u2` 60% menor.

**Consequência:** a ET0 absoluta não deve ser comparada com valores de outras
fontes; como exposição relativa, permanece consistente.

## O que a replicação **não** valida

1. A fonte (NASA POWER) — verifica a transformação, não o dado de entrada.
2. A adequação agronômica do método T&M com CAD fixa de 50 mm.
3. A ET0: foi usada a da referência como insumo, de propósito, para isolar o
   balanço.
