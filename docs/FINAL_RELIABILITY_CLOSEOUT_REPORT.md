# SADEN — Relatório de fechamento de confiabilidade

**Branch:** `maintenance/final-reliability-closeout`
**Base:** `0973b77` · **Data:** 2026-11-14
**Natureza:** fechamento de confiabilidade. Nenhuma hipótese nova, nenhuma UF
nova, nenhuma alteração de produto ou de TCC.

---

## 1. Resumo executivo

As seis pendências herdadas foram fechadas. Três resultados merecem destaque
porque **contrariam o que se esperava**:

1. **As duas não conformidades da ET0 se cancelam.** O fator 0,4 indevido no
   vento elevaria a ET0 em 11,3%; o `es(Tmean)` errado reduz. Juntas: **+0,54%**.
   A ET0 publicada está praticamente onde a FAO-56 manda — por acidente duplo.
2. **A liberalidade do CR1 não produziu nenhum falso positivo** nos 18
   estimandos do painel: nenhuma conclusão inverteu de lado ao trocar CR1 por
   wild cluster bootstrap calibrado.
3. **O build completo cobre 1.880 municípios, não 2.425.** Os 545 restantes do
   cadastro não têm linha analítica utilizável. Nenhum dado foi inventado.

E um resultado que é só má notícia: **a validação do clima continua incompleta.**
O diário foi comparado (627.381 pares); a agregação de janela, que é o que entra
no modelo, não.

## 2. Estado anterior

`0973b77`, 482 testes, decisões até D127. V1.1 e V3.0–V3.5 intactas.

## 3. Conflito NASA POWER × INMET

| item | valor |
|---|---|
| linhas NASA-POWER / INMET | 5.925.166 / 627.381 |
| pares conflitantes (mesma chave) | **627.381** |
| municípios com INMET | 215 de 1.622 (13,3%) |
| estações | 215, todas dentro do município |
| distância estação–centróide | mediana 13,5 km · máx. 95,7 km |

Não é duplicação: são produtos distintos (reanálise em grade vs observação de
estação). Viés pequeno, erro aleatório material.

## 4. Fonte canônica por variável

NASA-POWER para **todas** as variáveis do painel (precipitação, temperatura,
umidade, vento, radiação, solo), por cobertura integral. INMET fica como
referência auxiliar de validação, nunca em modelo. Justificativa por variável em
`CLIMATE_SOURCE_ADJUDICATION.md` §5.

## 5. Análise das 627.381 observações

| variável | viés | MAE | r | % acima do limite |
|---|---:|---:|---:|---:|
| precipitação | −0,29 mm | 3,10 mm | 0,644 | 16,9% |
| temperatura média | +0,40 °C | 1,42 | 0,931 | 10,1% |
| temperatura máxima | +0,25 °C | 1,95 | 0,899 | 21,1% |
| temperatura mínima | +0,08 °C | 1,57 | 0,907 | 13,2% |
| umidade relativa | −0,02 pp | 7,67 | 0,796 | 5,4% |
| **vento** | **+2,53 km/h** | 4,50 | **0,409** | 7,8% |
| radiação | +1,17 MJ/m² | 2,45 | 0,817 | 4,8% |

Limites definidos por critério agronômico, não estatístico.

## 6. Rastreabilidade das 2.020 linhas INMET

9,43% das 21.422 linhas utilizáveis do painel base. Varredura AST de 72 arquivos:
**28 funções com guarda de fonte, 0 sem guarda** (1 waiver documentado para um
contador de cobertura). Ambos os runners de V2.6/V2.7 filtram NASA-POWER por
padrão. **Nenhuma análise as consumiu.**

O risco era real: `prepare_rows` filtrava só por status. Passou a levantar
`ValueError` com amostra mista (D128).

## 7. Adjudicação de ET0

Duas não conformidades com a FAO-56, medidas por identidade exata
(`vento × 2,5 ⇒ u2 = vento/3,6`, erro 9 × 10⁻¹⁶):

| variante | ET0 | mediana relativa | déficit |
|---|---:|---:|---:|
| referência | 531,8 mm | — | 125,6 mm |
| só vento corrigido | 600,5 mm | +11,30% | 185,6 mm |
| **FAO-56** | **533,2 mm** | **+0,54%** | **124,9 mm** |

Física corrigida é canônica (D130). Implementação histórica intacta. Nenhum
artefato reescrito — o efeito não justifica nova versão científica.

**Correção de registro:** a etapa anterior reportou −1,1% (harness com dia
juliano aproximado) e o primeiro instrumento desta etapa reportou +10,3%
(reimplementação que não reproduzia a biblioteca). O valor correto, medido por
dois caminhos independentes, é **≈ +0,5%**. Ambos os erros eram de ferramenta.

## 8. Decisão D124

O excedente correto é o transbordo (`ARM_anterior + saldo − CAD`). A referência
lança o saldo bruto quando o mês satura a CAD, porque o teste é feito depois de
`storage` já estar limitado à CAD. Caso de prova: 15 mm vs 5 mm. Déficit, ETR e
armazenamento não são afetados; o gatilho não ocorreu em 30 janelas reais
verificadas nesta etapa. Nenhuma conclusão publicada depende de excedente (D131).

## 9. Validação do wild bootstrap

5.000 réplicas, G e tamanhos reais, ICC do erro e da exposição estimados do
painel, ruído casado por momento.

**CR2 ≡ CR1** com um regressor (`K2 = 1`). WCR (Rademacher, H0 imposta) é o
único calibrado.

## 10. Erro tipo I (α = 5%)

| cultura | CR1 | WCR | WCU | WCR-Webb |
|---|---:|---:|---:|---:|
| soja | 7,54% | **5,40%** | 5,88% | 5,38% |
| milho | 7,86% | **5,26%** | 5,88% | 5,56% |
| milho 2ª | 9,98% | **5,96%** | 6,90% | 6,20% |

MC SE 0,32–0,42 pp; intervalos de Wilson no manifesto. CR1 reprovado nos três
(intervalo inteiro acima de 5%); WCR aprovado em soja e milho, levemente acima
em milho 2ª.

## 11. Cobertura dos intervalos de 95%

| cultura | CR1 | WCR |
|---|---:|---:|
| soja | 92,5% | **94,3%** |
| milho | 92,1% | **94,5%** |
| milho 2ª | 90,0% | **93,8%** |

## 12. Resultados reavaliados

`applied_inference.json`, 18 estimandos, B = 9.999: **7 sustentados**, 2
inconclusivos, 9 nulos confirmados. **Nenhum inverteu.** O poder do teste
calibrado é 3–8 pontos menor que o do CR1 — a comparação anterior era otimista.

## 13. Manifestos determinísticos

Conteúdo canônico em `<nome>.json`, metadados em `<nome>.json.run.json`. Duas
execuções → `content_sha256` `96599508…` e arquivo `8624B904…`, ambos idênticos.
Merge de blocos também determinístico (`a8329388…` / `6a95581c…`).

## 14. Build completo

Seis blocos, merge validado: **30.207 janelas**, **120.828** linhas de água,
**1.880 municípios**, 0 chaves duplicadas, 0 problemas. Tempo ~11 min.

Comparação com V3.5: **mesmas 30.207 chaves**, **37 colunas idênticas**, 11
alteradas pela física (ET0 +3,06 mm mediano, déficit +1,07, excedente −13,16).

## 15. Reprodução

| item | estado |
|---|---|
| suíte | **505 testes**, 0 falhas |
| compilação | limpa |
| pipeline | determinístico; recusa sobrescrita sem `--force` |
| replicação independente | 8/8 casos manuais; déficit máx 6,1 × 10⁻⁶ mm em 54 janelas |
| artefatos históricos | inalterados (hashes conferidos) |

## 16. Limitações

1. **Clima não validado na agregação de janela** — maior lacuna aberta.
2. Vento INMET com r = 0,409 sem explicação.
3. Magnitude do D124 no painel completo não medida.
4. Build completo com física histórica não executado (equivalência provada em amostra).
5. Wild bootstrap bidimensional e Conley HAC não implementados.
6. Seis manifestos ainda não migrados para o formato determinístico.
7. Efeito isolado de C1 na ET0 não identificável.
8. Cobertura de 77,5% do cadastro.

## 17. Testes

505 (482 herdados + 23 novos), 0 falhas, `compileall` limpo. Novos cobrem
contrato de fonte, `prepare_rows` com amostra mista, identidade do vento,
conservação de água, D124, `cr1_fit` contra a biblioteca, WCR × WCU,
canonicalização e determinismo de manifesto.

## 18. Decisões

**D128** contrato de fonte executável · **D129** defeitos de ferramenta
(dia juliano, `null_imposed`, `auto`) · **D130** ET0: correções se cancelam,
nada reescrito · **D131** excedente corrigido convive com o histórico ·
**D132** WCR é o método de inferência · **D133** manifestos separam conteúdo de
execução · **D134** build em blocos com merge validado.

## 19. Situação final

A infraestrutura científica do SADEN está consolidada: fonte declarada e
verificada, física adjudicada com números, inferência calibrada com incerteza
explícita, manifestos verificáveis e build integral executável. O que resta não é
mais consolidação — é uma decisão de produto ou uma pesquisa nova, e nenhuma das
duas tem lugar nesta etapa.
