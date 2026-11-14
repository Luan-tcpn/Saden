# SADEN — Auditoria de qualidade do IBGE/PAM

**Data:** 2026-11-14 · Manifesto: `geospatial/data/manifests/pam_quality_audit.json`
**Células com flag:** `docs/data_quality/pam/pam_flagged_cells.csv`

---

## 1. Escopo e fonte

Fonte efetivamente usada pelo painel: **IBGE — Produção Agrícola Municipal**,
SIDRA tabela 5457, variáveis 214 (quantidade), 216 (área colhida), 112 (área
plantada) e 8331 (rendimento médio).

Arquivos auditados (os que sustentam todas as versões):

| arquivo | UFs | linhas | bytes |
|---|---|---:|---:|
| `pam_panel.csv` | MT, GO, MS, PR, RS, BA | 128.160 | 448,8 MB |
| `pam_panel_sp.csv` | SP | 46.440 | — |

Período: **2017–2025** (9 anos). Culturas: soja (40124) e milho (40122).

## 2. Chave canônica

`geography_code + reference_year + crop_code`.

| verificação | resultado |
|---|---|
| células município–ano–cultura | **43.650** |
| municípios distintos | **2.425** |
| **chaves duplicadas** | **0** |
| linhas com UF desconhecida | 0 |

O campo `safra` vem **vazio** em toda a base: a PAM é anual e **não separa 1ª e
2ª safra de milho**. Isso confirma a limitação já registrada — as linhas de
"milho 2ª" usam o rendimento anual total com janela de 2ª safra
(`retrospective_mask`, `semantic_compatibility = incompativel`).

## 3. Série temporal e alterações territoriais

| verificação | resultado |
|---|---|
| municípios com série completa (9 anos) | **2.425 de 2.425** |
| municípios com série parcial | **0** |

**Não há criação, extinção ou mudança de código de município dentro da série
2017–2025.** Não foi preciso harmonizar territórios nem agregar produção/área de
municípios extintos: a PAM devolve a mesma lista de códigos nos 9 anos. A
auditoria territorial, portanto, se encerra aqui sem crosswalk retrospectivo — o
que existia era o problema de **nome** (já resolvido na V3.4/V3.5) e não de
**código**.

### 3.1. Divergência entre a PAM e o cadastro municipal

| item | valor |
|---|---|
| códigos só na PAM | **0** |
| códigos só no cadastro IBGE usado pelo painel | **2** |

Os dois são `4300001` e `4300002` (RS):

| código | nome oficial | natureza |
|---|---|---|
| 4300001 | Área Operacional "Lagoa Mirim" | **não é município** |
| 4300002 | Área Operacional "Lagoa dos Patos" | **não é município** |

São unidades territoriais que o IBGE publica na malha municipal para corpos
d'água. **Não têm nenhuma linha no painel analítico** (0 em 19.402), logo o
impacto científico é nulo. **Impacto de engenharia:** o cadastro mistura 1.780
municípios com 2 unidades operacionais; o pipeline canônico passa a filtrá-las
por regra explícita (D121).

## 4. Zeros, ausentes e semântica

Decomposição das 43.650 células:

| classe | células | leitura |
|---|---:|---|
| `sem_area` (área plantada e colhida = 0) | **7.507** | município não cultiva a cultura naquele ano — **não é erro** |
| `area_ausente` (área nula) | **778** | célula sem valor publicado |
| `plantado_sem_colheita` (plantou > 0, colheu = 0) | **85** | **perda de safra** — informação válida, não erro |
| `rendimento_zero_com_area` (colheu > 0, rendimento = 0) | 0 | — |
| `rendimento_divergente` (>1% do recalculado) | **66** | ver §5 |
| `extremo_mad` (>8 MAD dentro de cultura×UF) | **99** | ver §6 |

**Nenhum zero foi convertido em nulo, nem nulo em zero.** A classificação é
semântica, não estatística: `sem_area` significa "não produziu", e
`plantado_sem_colheita` significa "produziu e perdeu" — as duas são informação.

## 5. Consistência matemática do rendimento

Rendimento publicado (8331) contra `produção × 1000 / área colhida`:

| estatística | valor |
|---|---:|
| células com área > 0 e rendimento > 0 | 34.957 |
| divergência ≤ 1% | 34.891 (99,8%) |
| divergência > 1% | **66** |
| mediana da divergência entre os 66 | **1,75%** |
| máximo | **16,7%** |

Os casos de 1,01% são **arredondamento** (o SIDRA publica o rendimento em kg/ha
inteiro). As 66 divergências não indicam unidade errada: se houvesse troca de
unidade, o erro seria de 10² ou 10³. A maior (16,7%) fica registrada para
rastreabilidade, sem exclusão automática.

## 6. Valores extremos

Critério: |valor − mediana| > 8 × MAD, dentro de **cultura × UF** (robusto a
cauda e à diferença de nível entre estados). Resultado: **99 células**.

Nenhuma foi removida. Distribuição por cultura/UF no manifesto. Os extremos são
compatíveis com agricultura irrigada e com anos atípicos; a decisão é **não
excluir** e manter o flag (D122).

## 7. Revisões históricas

Não existe vintage anterior da extração no repositório. O que se sabe:

| item | valor |
|---|---|
| data de extração | 2026-11-12 (`acquired_at` por linha) |
| versão da fonte | SIDRA 5457, estado em 2026-11-12 |
| snapshots anteriores | **nenhum** |
| revisões mensuráveis | **impossíveis** com o que existe |

Registrado como limitação: não é possível medir revisão de valores publicados
porque não há duas extrações da mesma tabela em datas diferentes. O campo
`revision` vem vazio em todas as 128.160 + 46.440 linhas.

## 8. Impacto no painel publicado

| item | valor |
|---|---:|
| linhas analíticas verificadas (`v35_panel_windows.csv`) | **30.207** |
| linhas cuja fonte tem algum flag (exceto `sem_area`) | **27** |
| proporção | **0,09%** |
| por flag | `extremo_mad`: 25 · `rendimento_divergente`: 2 |
| concentração | **todas em BA** (106 linhas no painel) |

**Conclusão:** a qualidade da fonte de produtividade **não ameaça** os resultados
publicados. 99,91% das linhas analíticas vêm de células sem nenhum flag, e as 27
restantes são valores plausíveis (extremos ou arredondamento), não erros
demonstrados. A BA é apenas 0,35% do painel (106 de 30.207 linhas), portanto a
concentração dos flags não altera nenhuma inferência.

## 9. O que foi corrigido e o que não foi

| item | decisão |
|---|---|
| códigos `4300001/4300002` no cadastro | **filtrar** no pipeline canônico (D121); não reescrever o histórico |
| `sem_area` | não é erro; mantido |
| `plantado_sem_colheita` | informação válida; mantido |
| 66 rendimentos divergentes | mantidos, com flag |
| 99 extremos | mantidos, com flag |
| nomes divergentes (Poxoréo, Leverger, Vila Alta) | já tratados na V3.4/V3.5 |
| revisões históricas | **não mensuráveis** — limitação registrada |

## 10. Limitações

1. **Sem vintage anterior**: revisão de valores não é auditável.
2. **Milho 2ª safra**: a PAM não separa as safras; a limitação é da fonte.
3. **MAD por cultura×UF** é descritivo; não substitui validação de campo.
4. **Não houve verificação contra fonte independente** (Conab, sensoriamento):
   a auditoria é interna à PAM.
5. A PAM pode revisar séries para trás; sem snapshots não há como detectar.

## 11. Classificação

| achado | classificação |
|---|---|
| chaves únicas, 0 duplicidade | **auditado** |
| série completa nos 9 anos, 0 alteração de código | **auditado** |
| 2 unidades operacionais no cadastro | **corrigido** no pipeline (filtro) |
| rendimento aritmeticamente consistente (99,8%) | **auditado** |
| 27 de 19.402 linhas com flag de fonte | **auditado**, sem ação |
| revisões históricas | **não auditável** (sem snapshot) |
| validação contra fonte externa | **não investigado** nesta etapa |
