# V3.2 — KNOWN RISKS

Riscos identificados, com estado e mitigação. Nenhum foi descoberto depois de
ver resultados sem registro.

## R1 — Inferência com poucos clusters (aberto, estrutural)

**Risco:** há 4–6 UFs. Tratar estados como unidades independentes é inválido, e
qualquer aproximação assintótica no nível estadual é frágil.
**Mitigação:** o teste global é sobre interações, com clusters UF×ano (32–48);
contrastes estaduais são descritivos; `F(q, G−1)` em vez de qui-quadrado.
**Residual:** não é possível estimar a variância entre UFs nem IC que a
incorporem. Registrado como limitação em todo resultado.

## R2 — Partial pooling não é hierárquico completo (aberto, escolhido)

**Risco:** `M2-HET-PP` é ridge sobre desvios, com λ escolhido por validação
interna. Não há REML nem propagação da incerteza de λ.
**Mitigação:** caminho completo de λ reportado; limitação declarada (D106).
**Residual:** os IC de predição não incluem incerteza de seleção de λ.

## R3 — λ instável (observado)

**Risco:** a seleção por célula escolhe λ=0 em 18 de 25 células do milho e λ=100
em 4; o caminho de λ fixo não é monótono em relação ao PP.
**Mitigação:** todos os λ fixos são reportados (§16.3 do relatório); a
instabilidade é parte da classificação Nível C.

## R4 — Colinearidade precipitação/temperatura (observado, mitigado)

**Risco:** correlação *within* de −0,60 a −0,67. Um modelo de variável única
atribui à temperatura o efeito da água.
**Mitigação:** especificação primária conjunta; modelos de variável única
rotulados como sensibilidade; a família exploratória é explicitamente rotulada
como não-identificadora.

## R5 — Composição territorial (observado)

**Risco:** PR domina (389–391 municípios) e BA tem 106 linhas; a variação
*within* de temperatura em PR/RS é só 17–29%.
**Mitigação:** diagnóstico por UF antes da estimativa; leave-one-UF-out;
classificação de elegibilidade por UF.

## R6 — `_legacy` acidental (mitigado por teste)

**Risco:** misturar janela histórica e corrigida.
**Mitigação:** teste de regressão que falha se as ferramentas V3.2 mencionarem
`_legacy`; todas as cargas vêm de `v31_panel_windows.csv` com colunas
`_corrected`.

## R7 — Sobreajuste do modelo heterogêneo (monitorado)

**Risco:** ganho só no treino. **Mitigação:** toda comparação é em TE, com
seleção de λ dentro do treino; MAE de treino não é reportado como evidência.

## R8 — Fontes externas bloqueadas (aberto)

ERA5-Land (sem credencial CDS) e CHIRPS/ARCO (DNS). Nenhuma tentativa nova;
nenhuma credencial inventada.
