# Consolidação técnica — estado mestre

**Branch:** `maintenance/technical-consolidation`
**Base:** `32dfb88` (V3.5)
**Data:** 2026-11-14
**Escopo:** consolidar, não expandir. Nenhuma hipótese agroclimática nova.

---

## 1. O que esta etapa fez

| # | entrega | estado |
|---|---|---|
| 1 | auditoria de qualidade do IBGE/PAM em todas as UFs do painel | **concluída** |
| 2 | auditoria de linhagem e qualidade do painel | **concluída** |
| 3 | pipeline canônico único, com configuração declarativa | **concluído** |
| 4 | teste real de clone limpo | **concluído** (níveis 1–4) |
| 5 | replicação independente do balanço hídrico | **concluída** |
| 6 | análise formal de poder e MDE | **concluída** |
| 7 | documento de conclusões defensáveis | **concluído** |
| 8 | diagnóstico de prontidão para produto | **concluído** |
| 9 | organização de ferramentas e documentação | **concluída** |
| 10 | bundle de recuperação | **concluído** |

## 2. Números de controle

| item | valor |
|---|---|
| testes | **482** (458 herdados + 24 novos), 0 falhas |
| compilação | limpa (`compileall`) |
| células PAM auditadas | 43.650 (2.425 municípios × 9 anos × 2 culturas) |
| duplicidades de chave na PAM | **0** |
| alterações de código municipal 2017–2025 | **0** |
| linhas analíticas com fonte marcada | **27 de 30.207** (0,09%) |
| reprodução do painel V3.5 | **bit-idêntica** (0,000) |
| réplicas independentes do déficit | 90 janelas, diferença máx. 4,3 × 10⁻⁶ mm |
| MDE déficit × soja | 1,14 kg/ha por mm |
| erro tipo I observado | 6,0% – 10,3% (nominal 5%) |

## 3. Decisões novas

D120 a D127. D116–D119 já estavam ocupadas pela V3.5.

## 4. O que **não** foi feito, por decisão

- nenhuma UF nova (MG segue planejada, D119);
- nenhum modelo novo de produtividade;
- nenhuma correção retroativa de resultado publicado;
- nenhuma alteração no produto (frontend, backend, banco);
- **nenhum acesso a `SADEN-TCC`** (fora de escopo, ver seção 5).

## 5. Pasta acadêmica

`SADEN-TCC/` permaneceu **fora do escopo**: não foi listada, lida, buscada,
copiada, indexada nem incluída em bundle ou manifesto. Nenhuma verificação de
coerência entre o texto acadêmico e V2.6–V3.5 foi executada. Uma eventual
revisão acadêmica depende de etapa futura separada, com autorização expressa.

## 6. Resultado em uma frase

O projeto agora tem um caminho único e reproduzível para construir o painel, uma
auditoria de dados que não encontra problema material na fonte de produtividade,
uma replicação matemática independente que confirma o déficit e expõe um defeito
no excedente, e uma análise de poder que mostra que **a expansão de cobertura
feita até aqui quase não comprou precisão**.
