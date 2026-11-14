# V3.3 — KNOWN RISKS

## R1 — 5–6 UFs (aberto, estrutural)

Nenhuma conclusão vale fora das UFs cobertas. Toda inferência com 31–48 clusters
UF×ano é razoável, não exata. Mitigação: IC e `t(G−1)`; nenhuma alegação
nacional.

## R2 — Resolução mensal do balanço (aberto)

Duração em dias não existe. H3 é não identificável (D109). Um balanço diário
introduziria uma segunda metodologia no projeto — não feito.

## R3 — Colinearidade estrutural água/temperatura/calor (observado, mitigado)

`heat` 0,84 com déficit, 0,76 com temperatura; `etr/etp` é `1 − def/etp`.
Mitigação: blocos escolhidos antes do pré-registro; `heat` só como sensibilidade;
nenhuma conclusão depende de separar calor de seca.

## R4 — Não linearidade testada só na forma quadrática (aberto)

Splines/limiares não testados por falta de limiar defensável. O resultado negativo
vale para a forma testada, não para "toda não linearidade".

## R5 — Agrupamento duplo não é uniformemente conservador (observado)

Sete hipóteses têm SE menor sob UF×ano (até 0,56×). O critério de escolha é a
estrutura de dependência, não o efeito no p-valor (D111). Risco de leitura
oportunista — mitigado por declarar o esquema primário antes de estimar.

## R6 — CR1 apenas (aberto)

Sem wild bootstrap multidimensional. Com 31–48 clusters, a aproximação é
aceitável; milho 2ª (31) está no limite. Recomendado na V3.4 como sensibilidade.

## R7 — Reprodução de V2.7 depende de colunas `_legacy` (mitigado)

O painel `v31_panel_windows.csv` mantém as duas janelas. Há teste que impede as
ferramentas de modelagem de usarem `_legacy`; a ferramenta de auditoria usa
`_legacy` de propósito e isso é verificado explicitamente.

## R8 — Padrão regional pode ser ruído (observado)

O gradiente Sul/Cerrado aparece nas duas culturas de verão, o que sugere estrutura
real, mas não foi pré-registrado nem testado como hipótese. Classificado como
exploratório; risco de ser promovido indevidamente — mitigado pela D111 e por
`NEXT_ACTIONS` exigir pré-registro.
