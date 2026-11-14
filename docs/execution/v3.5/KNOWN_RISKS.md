# V3.5 — KNOWN RISKS

## R1 — Braço pequeno em MRS 1 de SP (aberto, estrutural)

178 linhas de soja, ~20 municípios, 7–8 anos. Efeitos menores que ~20 kg/ha não
seriam detectados. Mitigação: IC reportado; conclusão limitada a "sem diferença
material", não a "efeito exatamente zero".

## R2 — Poucos clusters temporais (aberto)

7 anos no teste associativo dentro de SP. Com `G` = 7, o `t(G−1)` é frágil.
Mitigação: dois bootstraps (ano e município) reportados; resultado classificado
como n.s.

## R3 — Desenho escolhido após a V3.4 (aberto, declarado)

O pré-registro foi consolidado **depois** da primeira execução. Registrado como
desvio de processo no `V3_5_PREREGISTRATION.md` §0. Mitigação: os dados são novos
(SP nunca analisada antes), o que dá alguma independência territorial; a
limitação está explícita em todos os relatórios.

## R4 — MRS é classificação de soja (aberto, declarado)

Aplicada a milho e milho 2ª como estratificação geográfica (D118). Resultados
dessas culturas são exploratórios.

## R5 — Blocos espaciais dependem do cadastro (mitigado)

Verificado que a entrada de SP **não reatribui** nenhum município histórico
(0 alterações; SP cria 11 blocos). Sem essa verificação, A e B não seriam
comparáveis.

## R6 — MAEs não comparáveis entre painéis (mitigado)

O conjunto de teste muda com SP. Mitigação: decomposição explícita (Experimento
C) e nota em cada tabela; nunca se compara MAE absoluta entre versões.

## R7 — Milho 2ª: PAM publica total anual (aberto, herdado)

O painel marca essas linhas como `retrospective_mask` e
`semantic_compatibility = incompativel`. Não é resolvível sem fonte por safra.

## R8 — Classificação de SP incompleta em 2 municípios (fechado)

643 de 645 têm MRS; os 2 restantes não estão na lista oficial de indicação de
soja e não entram em análises por região.

## R9 — Transferência medida só espacialmente (aberto)

Treinou-se em todos os anos das 6 UFs e testou-se em SP; não é validação
temporal. Ver nota no relatório de rebaseline.

## R10 — Produção nacional não medida (aberto)

PAM cobre 7 UFs. A lacuna é territorial, não produtiva. Não se estima
participação.
