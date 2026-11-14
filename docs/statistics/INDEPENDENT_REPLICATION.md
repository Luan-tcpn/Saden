# SADEN — Replicação independente do balanço hídrico e da ET0

**Data:** 2026-11-14
**Código:** `tools/independent_replication/water_balance_reference.py`
**Manifesto:** `geospatial/data/manifests/independent_replication.json`

---

## 1. O que foi replicado

| cálculo | método documentado | independência |
|---|---|---|
| balanço hídrico sequencial | Thornthwaite & Mather (1955) | função própria, **não importa** `agroclimate.water_balance` |
| ET0 diária | Allen et al. (1998), FAO-56 eq. 6 | função própria, **não chama** `fao56_penman_monteith` |

Os verificadores anteriores (`v33_verify_report.py`) comparam números do relatório com
manifests — consistência de **transcrição**. Este é o primeiro verificador de
**correção matemática**: recalcula a transformação a partir das equações.

## 2. Casos manuais

Oito casos com resultado calculado à mão, antes de qualquer execução:

| caso | CAD | ARM inicial | resultado esperado | passou |
|---|---:|---:|---|---|
| chuva sobre solo saturado | 50 | 50 | ARM 50, ETR 10, DEF 0, EXC 90 | sim |
| reposição parcial | 50 | 30 | ARM 40, ETR 5, DEF 0, EXC 0 | sim |
| enche e transborda | 50 | 45 | ARM 50, ETR 5, DEF 0, **EXC 10** | sim |
| consumo sem chuva | 50 | 50 | ARM 20, ETR 30, DEF 0, EXC 0 | sim |
| armazenamento esgotado | 50 | 20 | ARM 0, ETR 25, DEF 15, EXC 0 | sim |
| déficit em dois meses secos | 50 | 50 | DEF total 20, ETR total 60 | sim |
| CAD zero | 0 | 0 | DEF total 10, EXC total 20 | sim |
| transição seco → úmido | 50 | 50 | DEF total 20, EXC total 30 | sim |

**8/8 passaram.** As expectativas foram escritas antes da execução; três delas
estavam erradas na primeira versão e foram corrigidas (o cálculo manual, não o
código) — registro em `EXECUTION_LOG.md`.

## 3. Comparação em casos reais

**Regra de amostragem declarada antes da comparação:** estratificada por UF ×
cultura, semente fixa `20261114`, cenário `cad50`, 90 casos.

| métrica | valor |
|---|---:|
| janelas completas comparadas | **90** |
| diferença absoluta máxima no déficit | **4,3 × 10⁻⁶ mm** |
| diferença absoluta mediana | **9,8 × 10⁻⁷ mm** |
| casos com diferença ≤ 10⁻⁶ mm | 45 de 90 |
| diferença relativa máxima | ~10⁻⁸ |

A diferença residual é **ordem de soma em ponto flutuante** (o clima é
`float32`), não divergência de método. Em unidades interpretáveis: 4 × 10⁻⁶ mm
sobre déficits de 100–300 mm.

**Conclusão:** o déficit sazonal publicado é aritmeticamente correto.

## 4. Defeito encontrado — D124 (excedente)

O excedente é **superestimado** quando um mês de saldo positivo satura a CAD a
partir de um armazenamento parcial. Caso de prova (CAD 50):

| mês | P | ETP | ARM anterior | ARM correta | EXC correto | EXC da referência |
|---|---:|---:|---:|---:|---:|---:|
| 2020-01 | 0 | 10 | 50 | 40 | 0 | 0 |
| 2020-02 | 20 | 5 | 40 | 50 | **5** | **15** |

O armazenamento final é igual nos dois (50 mm) e o déficit é zero nos dois. A
referência soma o saldo inteiro (15 mm) como excedente, ignorando os 10 mm que o
solo absorveu.

**Causa:** na implementação de referência, o teste ``storage >= cad`` é feito
**depois** de `storage` já ter sido limitado à CAD, de modo que a condição ficou
verdadeira em todo mês que satura o solo, e aí `exc` recebe o saldo bruto em vez
de `ARM_anterior + saldo − CAD`.

**Alcance:**

| item | resultado |
|---|---|
| déficit afetado | **não** |
| armazenamento afetado | **não** |
| ET0/ETR afetadas | **não** (ETR = ETP nesses meses) |
| coluna afetada | `excess_total_mm`, `excess_cad_*` |
| meses com gatilho em 45 janelas reais | **0** |
| variáveis `excess` no teste de inferência V3.3 | `soja`, `milho`, `milho_2` |
| classificação dessas variáveis na V3.3 | `mantida_apenas_bruta`, `mantida_apenas_bruta`, `sem_evidencia_em_nenhum` |

**Nenhuma conclusão publicada depende do excedente**: as três variáveis já
haviam sido classificadas como não sustentadas após correção de multiplicidade.
O defeito **não foi corrigido** na biblioteca, porque corrigir mudaria artefatos
publicados e quebraria a reprodução bit-a-bit da V3.5 (D124). A formulação
correta está implementada e testada neste módulo; qualquer uso futuro de
excedente deve usá-la.

## 5. Divergência de convenção na ET0

Formulação independente contra a de referência, 2.828 dias aleatórios
(semente fixa):

| estatística | valor |
|---|---:|
| diferença relativa mediana | **−1,1%** |
| percentil 5 | −7,7% |
| percentil 95 | +6,7% |
| diferença absoluta mediana | −0,04 mm/dia |

Duas causas identificadas, ambas **de convenção**, não de aritmética:

1. **Pressão de vapor saturado.** A referência usa `es(Tmean)`. FAO-56
   (equação 12) especifica `es = [e°(Tmax) + e°(Tmin)] / 2`. A diferença cresce
   com a amplitude térmica: em dias de grande amplitude a referência subestima o
   VPD e, portanto, a ET0.
2. **Conversão do vento.** A coluna `vento_kmh` já está a 2 m (NASA POWER
   `WS2M`); a conversão correta é somente `/3,6`. A referência aplica um fator
   **0,4 adicional**, deixando `u2` 60% menor do que o valor a 2 m. O termo
   aerodinâmico fica subestimado.

**Classificação:** a ET0 publicada é **válida como variável de exposição
consistente** — o erro é sistemático e afeta todas as linhas do mesmo modo, de
modo que associações e comparações entre municípios não são invertidas. Mas o
valor absoluto **não deve ser lido como ET0 de referência FAO-56**, e a
decomposição radiação/aerodinâmica não é interpretável.

**Consequência prática:** o déficit (que é `ET0 acumulada − ETR`) herda esse viés.
Como todos os resultados de V3.3–V3.5 usam déficit, eles continuam internamente
consistentes; comparações com valores publicados de ET0 de outras fontes, não.

## 6. Classificação final

| item | classificação |
|---|---|
| balanço sequencial (déficit, armazenamento, ETR) | **replicado independentemente** |
| excedente | **replicado, com defeito identificado na referência** |
| ET0 absoluta | **divergência de convenção documentada** |
| ET0 como exposição relativa | **válida, com ressalva** |
| casos manuais | **8/8** |

## 7. Limitações desta replicação

1. **A ET0 de entrada é a da referência** na comparação de algoritmo. Isso é
   deliberado: fixa o insumo para isolar o balanço. Não valida a ET0.
2. **90 janelas** de 30.207. A amostra é estratificada e reprodutível, não
   exaustiva.
3. **Replicação não valida a fonte.** Verifica a transformação com entradas
   conhecidas; não diz que a precipitação da NASA POWER está correta.
4. **A divergência de ET0 não foi resolvida** — corrigi-la exigiria reconstruir
   o painel e reexecutar V3.3–V3.5, o que está fora do escopo desta etapa e
   exigiria uma versão científica explicitamente identificada.
5. **O gatilho do D124 não ocorreu** nas 45 janelas verificadas; a frequência
   real no painel completo não foi medida.
