# SADEN V2.9 — Status da execução

> Etapa: **V2.9 — Regionalização agroclimática, heterogeneidade espacial do
> milho, CAD e classes de ciclo**. Atualizado em: 2026-11-14.

## Objetivo

Determinar **quanto da capacidade explicativa e preditiva vem das variáveis
agroclimáticas, quanto vem das diferenças regionais e espaciais, e em quais
culturas o resultado é generalizável**.

## Identificação da linha

| Item | Valor |
|---|---|
| Repositório | `C:\Users\luanf\OneDrive\Área de Trabalho\Saden_AgroClima` |
| Branch | `v2/regional-agroclimatic-robustness` (base `a36e6be` = V2.8) |
| V2.8 preservada | `v2/temporal-spatial-generalization` em `a36e6be`, publicada |
| Bundle V2.8 | `..\SADEN_V2_8_RECOVERY_2026-11-14\`, SHA-256 `73297BAB…46890AA8`, *okay*, 26 refs |
| V1 / `main` | `3f7ad33` (tag `v1-final`) — intactas |
| Suíte de referência | **338/338** ao abrir a V2.9 |
| Suíte atual | **345/345** |

## Estado das fases

| Fase | Item | Estado |
|---|---|---|
| 0 | Auditoria, bundle, branch, suíte de referência | **concluída** |
| 1 | Auditoria da equalização da V2.8 | **concluída** (D90) |
| 2 | Modelo regional de referência e valor incremental do clima | pendente |
| 3 | Heterogeneidade espacial do milho | pendente |
| 4 | CAD e balanço hídrico | pendente |
| 5 | Dicionário e classes de ciclo do ZARC | pendente |
| 6 | Cobertura territorial | pendente |
| 7 | Síntese científica | pendente |
| 8 | Validação e publicação | pendente |

## Resultado da Fase 1 (D90)

A equalização da V2.8 era **global**, não por célula. Medido no painel real:

| Cultura | braço | alvo | média | mínimo | células abaixo do alvo |
|---|---|---|---|---|---|
| soja | SS/SE/TS | 5.686 | 5.686 | — | 0 |
| soja | **TE** | 5.686 | **5.401** | **4.308** | **11/25** |
| milho | TE | 4.874 | 4.874 | 3.514 | 13/25 |
| milho 2ª | TE | 1.857 | 1.857 | 1.418 | 10/25 |

Com **equalização estrita por célula** (alvo = menor conjunto entre os quatro
braços, 25/25 células atingindo o alvo), as MAEs mudam em ≤ 5 kg/ha e todos os
efeitos permanecem dentro do mesmo IC — **a conclusão da V2.8 se sustenta**.
Uma única comparação limítrofe muda de status: milho 2ª, `SS−SE` passa de
−39,6 [−68,5;+0,5] para −45,5 [−79,0;−0,8] (deixa de incluir zero).

## Próxima ação executável

Fase 2: modelos aninhados M0 (média global) → M1 (UF) → M2 (UF + clima) com o
mesmo conjunto de treino, IC por bloco, e o valor incremental do clima medido
como M2 − M1 por cultura e por UF.

## Bloqueios conhecidos

- CAD em escala de painel: cobertura de 5/1.296 municípios; exige extração WCS.
- Rótulo das classes de ciclo: dicionário de dados do ZARC não coletado.
- ERA5-Land: credencial CDS ausente (D83). CHIRPS/ARCO: sem DNS.
