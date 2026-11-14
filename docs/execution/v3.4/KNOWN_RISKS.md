# V3.4 — KNOWN RISKS

## R1 — Confundimento região × UF (aberto, decisivo)

Cramér's V = 1,000 em todas as culturas: região é função da UF. Nenhuma UF tem
municípios nos dois grupos. Mitigação: relatar o contraste como descritivo,
leave-one-UF-out como medida honesta e classificar como Nível E (D113). Residual:
não há como atribuir o efeito à região com estes dados.

## R2 — Ausência de validação independente (aberto, estrutural)

A hipótese nasceu nos mesmos dados. Nenhuma amostra não examinada existe para o
período/território. Mitigação: declarado no pré-registro **antes** dos resultados;
nada é chamado de confirmação independente.

## R3 — Classificação de soja aplicada ao milho (aberto, declarado)

A fonte oficial é a de indicação de cultivares de soja. Para milho é aproximação.
Mitigação: declarada em protocolo, relatório e decisão; sensibilidade por região
edafoclimática reportada (D = −91,4, mesmo sinal).

## R4 — Grupos internamente heterogêneos (observado)

MS-MRS3 (Cerrado) comporta-se como o Sul; dentro do PR, MRS 1 × MRS 2 difere
significativamente. Mitigação: reportado como refutação da fronteira (D114), não
como detalhe.

## R5 — Dois bootstraps, nenhum no nível do tratamento (aberto)

Bootstrap por UF×ano e por bloco tratam unidades de linha, não as 2 vs 4 UFs do
tratamento. Mitigação: IC reportado como descritivo; LOO-UF obrigatório. Residual:
nenhum IC válido para o efeito regional existe com 6 UFs.

## R6 — Bug corrigido em análise por decis (fechado)

A primeira versão mapeava déficit por `ibge_code`, colapsando anos. Corrigido para
(município, ano). Registrado no log; a conclusão anterior era artefato.

## R7 — Protocolo diferente na análise dentro de estado (fechado)

A primeira versão usou 3 dobras espaciais (vs 5 do principal) e inflou o spread do
PR para 144. Recomputado no protocolo principal: 20,2. Números corrigidos.

## R8 — Download oficial bloqueado por rede (contornado)

O PDF e a planilha retornam 404 para clientes programáticos nesta rede, mas são
obtidos por outro caminho (planilha com UA de navegador; PDF via ferramenta de
fetch). Mitigação: hash registrado e mapeamento derivado versionado.

## R9 — Produção nacional não medida (aberto)

O PAM do repositório cobre 6 UFs. A lacuna é quantificada em municípios, não em
toneladas. Mitigação: declarado; não se estima participação nacional.
