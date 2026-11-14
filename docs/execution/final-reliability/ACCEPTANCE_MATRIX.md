# Fechamento — matriz de aceitação

**Data:** 2026-11-14

Critério: só é **aceito** o que foi executado e verificado nesta etapa.
Classificações: investigado · implementado · corrigido · validado · reproduzido ·
inconclusivo · bloqueado.

| # | item | estado | evidência |
|---|---|---|---|
| 1 | branch correta, base `0973b77` | **aceito** | `git rev-parse` |
| 2 | V1.1 e V3.0–V3.5 intactas | **aceito** | hashes conferidos |
| 3 | conflito NASA/INMET investigado | **aceito** | 627.381 pares, 7 variáveis |
| 4 | fonte canônica por variável documentada | **aceito** | `CLIMATE_SOURCE_ADJUDICATION.md` |
| 5 | 2.020 linhas INMET rastreadas | **aceito** | AST 72 arquivos, 0 sem guarda |
| 6 | contrato de fonte executável | **implementado + validado** | `contracts.py`, testes |
| 7 | ET0 adjudicada | **aceito** | 1.200 janelas, identidade 9e-16 |
| 8 | D124 adjudicada | **aceito** | caso manual + identidade de conservação |
| 9 | impacto das correções medido | **aceito** | 37 colunas idênticas, 11 alteradas |
| 10 | wild bootstrap avaliado na estrutura real | **aceito** | 5.000 réplicas, 4 métodos |
| 11 | erro tipo I documentado com incerteza | **aceito** | MC SE + Wilson |
| 12 | cobertura de intervalos documentada | **aceito** | 92,5% → 94,3% |
| 13 | inferência calibrada aplicada aos estimandos | **aceito** | 18 estimandos, B = 9.999 |
| 14 | manifestos determinísticos | **implementado + validado** | hash idêntico em 2 execuções |
| 15 | build completo executado | **aceito** | 30.207 linhas, 1.880 municípios |
| 16 | cobertura real registrada com causa | **aceito** | 77,5%, 545 ausentes |
| 17 | proteção contra sobrescrita | **implementado + testado** | `FileExistsError` |
| 18 | artefatos históricos preservados | **aceito** | hashes V3.0/V3.5 inalterados |
| 19 | resultados afetados reavaliados | **aceito** | 0 de 18 inverteram |
| 20 | testes passando | **aceito** | ver `EXECUTION_LOG.md` |
| 21 | bundle validado | **aceito** | `BUNDLE_INFO.txt` |
| 22 | branch publicada | **aceito** | `origin/maintenance/final-reliability-closeout` |

## Não aceito / bloqueado

| # | item | estado | motivo |
|---|---|---|---|
| 23 | validação da ET0/agregação contra estação | **não investigado** | INMET não publica ET0; exigiria derivar de saldo de radiação |
| 24 | magnitude do D124 no painel completo | **não medido** | exigiria rodar o balanço de referência em 30.207 janelas; sem impacto em conclusão |
| 25 | build completo com física histórica | **não executado** | equivalência histórica provada em amostra (14 municípios) na etapa anterior |
| 26 | wild bootstrap bidimensional | **não implementado** | município é absorvido por efeitos fixos; a afirmação vale para este estimador |
| 27 | Conley HAC | **não implementado** | registrado como sensibilidade pendente |
| 28 | migração dos 6 manifestos restantes | **pendente** | reescrever laudos da mesma etapa criaria versões duplicadas |
| 29 | verificação do texto acadêmico | **bloqueado por escopo** | `SADEN-TCC` fora do escopo por decisão |
