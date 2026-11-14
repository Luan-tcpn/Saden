# SADEN V3.4 — Relatório científico consolidado

**Hipótese regional do bloco hídrico, identificação geográfica e generalização territorial**

Branch: `v3/regional-water-block-hypothesis` · Base: `6eff88c` (V3.3) · 2026-11-14

---

## 1. Conclusão em quatro frases

O efeito do bloco hídrico **difere muito** entre as regiões agronômicas Sul e
Cerrado: no milho, ΔMAE é −45,5 kg/ha no Sul e +32,7 no Cerrado (D = −78,3;
IC UF×ano [−131,7; −26,7]), estável em todas as exclusões de UF e de ano.
Mas **região está perfeitamente aninhada em UF** (Cramér's V = 1,000; nenhuma UF
tem municípios nos dois grupos), então isso não é um efeito regional — é um
contraste entre grupos de estados.
Além disso, a fronteira agronômica testada **não organiza o fenômeno**: dentro do
PR, MRS 1 e MRS 2 diferem em +1.012 kg/ha/100 mm (p = 0,0022), e MS-MRS3
(Cerrado) se comporta como o Sul.
Classificação final: **Nível E — não identificável**; M2 permanece; a prioridade
passa a ser cobertura territorial, e **SP é a única UF que resolve a identificação**.

## 2. O que foi executado

| etapa | estado |
|---|---|
| auditoria de integridade (V1.1 → V3.3, bundles) | ✔ |
| classificação regional em fonte oficial, congelada antes das estimativas | ✔ |
| mapeamento municipal parseado da planilha oficial (4.286 pares) | ✔ |
| cobertura, suporte e avaliação de identificação | ✔ |
| pré-registro com regra de decisão A–F | ✔ |
| reprodução de M2 e M2+bloco hídrico (V3.3) | ✔ |
| contraste preditivo por região, com dois bootstraps | ✔ |
| interação associativa com agrupamento duplo | ✔ |
| estabilidade: leave-one-UF, leave-one-ano, dentro de estado | ✔ |
| sensibilidades: 5 classificações, 3 ponderações, decis de déficit | ✔ |
| diagnóstico de cobertura territorial | ✔ |
| 6 figuras, 17 testes novos, verificação numérica | ✔ |

## 3. O achado, em números

**Predição (MAE, kg/ha; negativo = bloco hídrico melhor):**

| cultura | Sul | Cerrado | D | IC UF×ano |
|---|---:|---:|---:|---|
| **milho** | **−45,5** | **+32,7** | **−78,3** | [−131,7; −26,7] |
| soja | −6,8 | +28,2 | −35,0 | [−80,7; +0,7] |
| milho 2ª | −8,8 | +13,7 | −22,5 | [−42,2; +1,4] |

No milho o bloco **melhora** no Sul e **piora** no Cerrado — não é "menos
prejudicial" no Sul; é benéfico lá.

**Associação (within de município e ano, agrupamento duplo):** interação Sul ×
déficit = **−1.287 kg/ha por 100 mm** (EP 236; p = 1,8×10⁻⁶; 47 clusters UF×ano;
n = 5.229).

**Estabilidade:** milho estável nas duas dimensões; **soja e milho 2ª não** (a
soja inverte em um ano; a milho 2ª inverte o sinal no leave-one-UF-out).

## 4. Por que o resultado é Nível E, e não B

O pré-registro fixou, antes dos resultados:

> "E tem precedência sobre B: se não houver nenhuma UF com municípios nos dois
> grupos, a alegação de efeito regional independente de estado é não
> identificável, mesmo que D seja grande."

O diagnóstico mediu exatamente isso: **Cramér's V = 1,000** nas três culturas;
**nenhuma** UF contribui para os dois grupos. O contraste é
{RS, PR-sul/oeste} × {GO, MS-norte, MT, BA-oeste}.

Com 2 vs 4 UFs, **nenhum bootstrap de linhas ou de UF×ano representa a incerteza
do tratamento**. Por isso o IC reportado é descritivo e o leave-one-UF-out é a
medida honesta — e ela é favorável no milho, o que está registrado como tal.

Não se está dizendo que o efeito não existe. Está-se dizendo que **não é
atribuível à região em vez do estado**, com estes dados.

## 5. Por que nem a descrição "Sul vs Cerrado" se sustenta

Três evidências independentes, todas obtidas sem olhar o resultado antes:

1. **Dentro do PR**, MRS 1 × MRS 2 difere em +1.012 kg/ha/100 mm (p = 0,0022) —
   magnitude comparável ao contraste Sul×Cerrado. Uma fronteira *dentro de um
   estado* produz diferença do mesmo tamanho.
2. **MS-MRS3 (Cerrado) tem Δ = −50,3**, comportando-se como o Sul, enquanto
   MS-MRS2 tem +31,6. O grupo "Cerrado" contém as duas direções.
3. Em **milho 2ª**, as três comparações dentro de estado são significativas
   (GO, MS, PR) — a heterogeneidade é mais fina que a macrorregião.

Ou seja: há heterogeneidade real de inclinação, mas ela **não segue a fronteira
agronômica testada**. Codificar essa fronteira num modelo regional seria
formalizar uma divisão que os dados não sustentam.

## 6. O que resistiu aos testes

| teste | resultado |
|---|---|
| 5 classificações alternativas (primária, MRS3, sem MT, Sul∪transição, edafoclimática) | D negativo em **todas** (−48,4 a −91,4) |
| 3 ponderações (observação, município, UF) | D negativo em **todas** (−61,9 a −139,9) |
| decis de déficit (suporte comum) | D negativo em **9 de 10** decis |
| leave-one-UF-out (milho) | negativo em **6 de 6** |
| leave-one-ano-out (milho) | negativo em **8 de 8** |

Ou seja: **a descrição é robusta**; o que ela não é, é identificável como efeito
regional. Essas duas conclusões convivem e foram mantidas separadas.

## 7. O que não resistiu

* **Soja**: D = −35,0 mas o IC de UF×ano inclui zero ([−80,7; +0,7]); inverte o
  sinal em um dos anos (até +3,8) e nos decis intermediários de déficit (+4,7 e
  +23,2). O agregado é sustentado por 37 linhas no decil mais alto. **Replicação
  não sustentada.**
* **Milho 2ª**: D = −22,5 mas o leave-one-UF-out vai de −9,7 a +47,0 (sinal
  inverte) e o de ano até +30,9. Além disso o grupo "Sul" é apenas PR-MRS1 (388
  linhas), e remover PR elimina o grupo. **Não sustentado.**
* **Leitura mecânica do padrão da V3.3** ("o bloco é melhor no Sul"): refutada
  como explicação regional por §5.

## 8. Decisão sobre a linha de modelagem

* **M2 permanece** o modelo de referência (D108 reforçada).
* **Nenhum modelo regional é adotado**: não há efeito regional identificado e a
  fronteira não organiza o fenômeno.
* Não se cria interação regularizada, modelo por UF, nem limiar.
* **A linha de especificação hídrica está encerrada com esta base**: a V3.3
  mostrou que a forma funcional não melhora a previsão; a V3.4 mostra que o que
  resta de heterogeneidade não é regional.

## 9. Consequência para o programa

A V3.4 fecha o ciclo de investigação da especificação agroclimática aberto na
V3.1 (janela corrigida) e ampliado na V3.2–V3.3 (heterogeneidade, forma
funcional). O que resta **não é um problema de modelo, é um problema de dados**:
6 UFs de 27, e nenhuma delas contém os dois grupos regionais.

O diagnóstico mediu o tamanho do problema: **33,25%** do território com indicação
oficial de soja; 2.861 municípios fora do escopo. E identificou o caminho:
**SP é a única UF ausente com municípios em MRS 1 e MRS 3** (645 indicados). É a
aquisição de maior valor científico por unidade de esforço.

## 10. Limitações gerais

1. **Sem validação independente**: a hipótese nasceu nos mesmos dados; nada aqui
   é confirmação independente.
2. **Classificação de soja aplicada ao milho**: aproximação declarada; não há
   lista municipal oficial equivalente para milho.
3. **MRS 4 ≠ bioma Cerrado**: inclui MT com transição amazônica.
4. **Produção nacional não medida**: o PAM do repositório cobre só 6 UFs; a
   lacuna é quantificada em municípios, não em toneladas.
5. **Associação ≠ causalidade; associação ≠ ganho preditivo** (§3 mostra as duas
   coisas lado a lado, medindo coisas diferentes).
6. **Grupos internamente heterogêneos**, como a V3.4 demonstrou.

## 11. Decisões registradas

* **D112** — classificação regional congelada em fonte oficial (MAPA/ZARC), com
  MRS 2 fora do contraste.
* **D113** — contraste regional não identificável como efeito independente de
  estado; Nível E.
* **D114** — a fronteira Sul/Cerrado não organiza o fenômeno; linha de
  especificação hídrica encerrada.
* **D115** — prioridade passa a ser cobertura territorial; SP é a única UF que
  resolve a identificação.

## 12. Recomendação para V3.5

**Expansão de cobertura para SP**, com os critérios de aceitação do diagnóstico
(§7): série PAM compatível, malha, clima na janela corrigida, CAD ou cenário
declarado, e reestimação dos baselines — porque adicionar UFs muda a composição
de M0/M1 e torna os resultados anteriores não comparáveis sem reestimação.

Não recomendado: novas variáveis climáticas, novos limiares, novas interações
regionais. A especificação não é o gargalo; o território é.

## 13. Reprodutibilidade

```
python tools/v34_region_mapping.py
python tools/v34_coverage.py
python tools/v34_regional_contrast.py --stage main
python tools/v34_regional_contrast.py --stage robustness
python tools/v34_regional_sensitivity.py
python tools/v34_coverage_gap.py
python tools/v34_figures.py
python tools/v34_verify_report.py
pytest geospatial/tests -q
```

Todas as decisões de desenho estão nos dois documentos congelados antes das
estimativas: `docs/V3_4_REGIONAL_CLASSIFICATION_PROTOCOL.md` e
`docs/V3_4_REGIONAL_WATER_PREREGISTRATION.md`.
