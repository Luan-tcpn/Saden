# Fechamento — estado do balanço hídrico (D124)

**Data:** 2026-11-14 · Detalhe: `docs/validation/D124_WATER_SURPLUS_ADJUDICATION.md`

## Adjudicação

O excedente correto é o **transbordo**: `EXC = ARM_anterior + (P − ETP) − CAD`,
limitado a zero. A implementação de referência usa o saldo bruto quando o mês
satura a CAD, porque o teste `storage >= cad` é feito **depois** de `storage` já
ter sido limitado à CAD.

Caso de prova (CAD 50; ARM 40; P 20; ETP 5):

| | excedente | armazenamento | déficit | ETR |
|---|---:|---:|---:|---:|
| correto | **5 mm** | 50 | 0 | 5 |
| referência | **15 mm** | 50 | 0 | 5 |

## Alcance

| componente | afetado |
|---|---|
| excedente | **sim** (superestimado) |
| armazenamento, ETR, déficit, ET0 | não |

Gatilho: mês com saldo positivo que satura a CAD partindo de `ARM < CAD`.
Não ocorreu em 30 janelas reais verificadas nesta etapa (nem em 45 na anterior).

## Dependência científica

A V3.3 testou `excess` para as três culturas e classificou todas como
`mantida_apenas_bruta` / `sem_evidencia_em_nenhum` — **nenhuma conclusão
publicada depende do excedente**.

## Decisão

Correção implementada em `agroclimate/corrections.py` (C3), usada pelo pipeline
canônico. `water_balance.py` **não** foi alterado, para preservar a reprodução
bit a bit de V2.6–V3.5 (D131).

## Aberto

Magnitude agregada do erro no painel completo não medida (exigiria rodar o
balanço de referência em 30.207 janelas). Como nada publicado usa excedente, a
lacuna não afeta conclusão.
