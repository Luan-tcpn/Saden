# V3.4 — PROTOCOLO DE CLASSIFICAÇÃO REGIONAL (congelado)

**Data de congelamento:** 2026-11-14, **antes** de qualquer estimativa regional
da V3.4.
**Estado:** congelado. Alterações posteriores só podem entrar como análise de
sensibilidade identificada como tal.

---

## 1. Por que este documento existe

A V3.3 encontrou, de forma **exploratória**, que o bloco hídrico ajudava em PR e
RS e atrapalhava em MS, GO, MT e BA. Classificar os estados olhando esse
resultado seria raciocínio circular. Este protocolo fixa a classificação a partir
de uma **fonte oficial agronômica**, independente dos resultados do SADEN.

## 2. Fonte escolhida

**Instrução Normativa SPA/MAPA nº 1, de 9 de novembro de 2021**, anexo
atualizado pelas **Portarias SPA/MAPA nº 387/2023** e **nº 281/2025**.

> "Estabelece as macrorregiões sojícolas e respectivas regiões edafoclimáticas
> para fins de indicação de cultivares de soja no Zoneamento Agrícola de Risco
> Climático – ZARC."

* **Instituição:** Ministério da Agricultura e Pecuária (MAPA) — Secretaria de
  Política Agrícola.
* **Formato usado:** a planilha oficial publicada na mesma página de normativos
  do ZARC ("Planilha dos municípios e suas respectivas regiões
  edafoclimáticas"), que é a versão legível por máquina do anexo da IN.
  `MacrorregioSojicolasAtualizado_2025.xlsx`, 140.020 bytes,
  SHA-256 `91126b6b512724cd90ab2bfc951ac418c0114bf78a697562a9c8c377f7458c84`
  (registrado no manifesto `v34_region_mapping.json`).
* **URLs:**
  * planilha: `https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/programa-nacional-de-zoneamento-agricola-de-risco-climatico/MacrorregioSojicolasAtualizado_2025.xlsx`
  * anexo em PDF: `…/INSTRUONORMATIVAN1DE9DENOVEMBRODE2021MACRORREGIOSOJCOLASATUALIZADO2025.pdf`
  * página: `…/normativos-do-zarc`
* **Acesso:** 2026-11-14.

### 2.1. Autoridade e nível geográfico

O normativo é federal, tem **lista municipal explícita** (4.286 pares
UF–município) e é a base oficial da indicação de cultivares no ZARC. É,
portanto, a delimitação agronômica municipal de maior autoridade disponível
para o território coberto e para o período dos dados (2017–2025).

### 2.2. Limitação da finalidade original — declarada

A finalidade é **indicação de cultivares de soja**. O uso aqui é como
**classificação agroclimática do território**, não como recomendação de
cultivar:

* para **soja**, é o uso para o qual a fonte foi feita;
* para **milho e milho 2ª**, é **aproximação declarada**: assume-se que as
  macrorregiões sojícolas delimitam ambientes edafoclimáticos que também
  organizam a produção de milho. Essa premissa é uma hipótese do desenho, não
  um fato da fonte, e é tratada como limitação em todo resultado de milho.

Não foi encontrada, nas fontes consultadas, classificação municipal oficial
equivalente específica para milho com o mesmo nível de detalhe e
rastreabilidade (o ZARC de milho é organizado por safra, solo e ciclo, não por
macrorregião publicada em lista municipal). Essa ausência está registrada.

## 3. Estrutura da classificação

O normativo define **5 macrorregiões sojícolas** e, dentro delas, **regiões
edafoclimáticas** (101–104, 201–204, 301–304, 401–405, 501–503).

| macro | nome usual | composição no painel |
|---|---|---|
| **MRS 1** | Sul | RS (todas as RE) + PR nas RE 102 e 103 |
| **MRS 2** | transição | PR nas RE 201 e 202 + MS nas RE 202 e 204 |
| **MRS 3** | Cerrado (sul/nordeste) | GO (RE 301–304) + MS (RE 301) |
| **MRS 4** | Cerrado (centro/oeste) | MT (RE 401–403) + GO (RE 401, 404) + BA (RE 405) |
| **MRS 5** | Norte/Nordeste | BA (RE 501) |

### 3.1. Regra de agrupamento (congelada)

* **Sul** = MRS 1.
* **Cerrado** = MRS 3 ∪ MRS 4.
* **Transição** = MRS 2 — **excluída do contraste primário** e reportada
  separadamente.
* **Excluídos**: MRS 5 (nordeste, 5 municípios no milho) e municípios do painel
  sem indicação de soja (22 municípios; 20 na BA).

**Por que MRS 2 fica fora:** a própria fonte a define como faixa distinta, e
ela cruza dois estados (norte do PR e centro-sul do MS). Incluí-la em "Sul" ou
em "Cerrado" seria decisão do analista, não da fonte. Mantê-la separada é o que
preserva a independência da classificação.

**Por que não se usa "Centro-Oeste = Cerrado":** MRS 4 inclui MT, cuja porção
norte está em transição amazônica, e MRS 2 inclui MS, que é Centro-Oeste e não
é Cerrado no sentido desta classificação. Região geográfica, bioma e
macrorregião sojícola **não** são sinônimos aqui.

### 3.2. O que a classificação NÃO é

* não é bioma (Cerrado/Amazônia/Mata Atlântica);
* não é mesorregião do IBGE;
* não é divisão político-administrativa;
* não é a classificação de aptidão de milho.

## 4. Mapeamento municipal

Arquivo: `geospatial/data/processed/municipality_region_mapping.csv`
(colunas `ibge_code`, `municipality`, `uf`, `edapho_region`, `macroregion`),
gerado por `tools/v34_region_mapping.py` — **parseado da planilha oficial**, sem
transcrição manual.

| item | valor |
|---|---:|
| pares UF–município na planilha (todos os estados) | 4.286 |
| pares nos 6 estados do painel | 1.425 |
| municípios do painel (1.782 candidatos) com região | 1.422 |
| municípios do painel **analítico** (1.296) sem região | 22 |
| códigos IBGE duplicados | 0 |

Os 360 não pareados são municípios **sem indicação de soja** (quase todos na
BA), não erro de correspondência: a lista de origem não os contém.

## 5. Cobertura por cultura (linhas do painel)

| cultura | Sul (MRS1) | Cerrado (MRS3+4) | Transição (MRS2) | fora |
|---|---:|---:|---:|---:|
| soja | 3.943 | 2.647 | 2.278 | 16 |
| milho | 2.482 | 2.747 | 2.298 | 89 |
| milho 2ª | 388 | 743 | 1.766 | 5 |

Municípios distintos:

| cultura | Sul | Cerrado | Transição |
|---|---:|---:|---:|
| soja | 556 | 371 | 314 |
| milho | 364 | 381 | 311 |
| milho 2ª | 72 | 149 | 283 |

## 6. Composição UF × macrorregião (a informação decisiva)

| UF | MRS1 | MRS2 | MRS3 | MRS4 | MRS5 |
|---|---:|---:|---:|---:|---:|
| PR | **134** | **266** | — | — | — |
| RS | **497** | — | — | — | — |
| MS | — | **53** | **26** | — | — |
| GO | — | — | **119** | **127** | — |
| MT | — | — | — | **141** | — |
| BA | — | — | — | **27** | **35** |

### 6.1. Consequência para identificação — registrada antes dos resultados

**Nenhuma UF tem municípios nas duas categorias do contraste primário**
(Sul = MRS1; Cerrado = MRS3∪MRS4):

* PR aparece em MRS1 e MRS2 — mas MRS2 é transição, excluída;
* MS aparece em MRS2 e MRS3 — mas MRS2 é transição, excluída;
* GO aparece em MRS3 e MRS4 — ambas no grupo Cerrado.

Portanto **região está aninhada em UF**. O contraste Sul × Cerrado é, na
prática, um contraste entre {RS, PR-sul/oeste} e {GO, MS-norte, MT, BA-oeste}.
Um efeito "regional" não é separável de um efeito de estado.

**O que continua identificado:** diferenças de **inclinação** (interação
bloco hídrico × grupo) são estimáveis mesmo com efeitos fixos de município,
porque vêm da co-movimentação temporal dentro do município. O que **não** é
identificável é atribuir a diferença ao território em si em vez de aos estados.

**Testes de falsificação que continuam válidos** (dentro do mesmo estado, com
macrorregião variando):

* GO: MRS 3 (108 municípios) × MRS 4 (100);
* MS: MRS 2 (52) × MRS 3 (24);
* PR: MRS 1 (132) × MRS 2 (266) — Sul × transição dentro de PR.

Se o efeito variar entre macroregiões **dentro do mesmo estado** na mesma
magnitude do contraste Sul × Cerrado, a leitura "fronteira regional" não é a
descrição correta do fenômeno.

## 7. Regra de atribuição e casos de fronteira

* Atribuição **por lista oficial**, município a município (não por centroide,
  não por polígono).
* Não há imputação: município fora da lista fica com região vazia e é
  **excluído** das análises que dependem de região.
* Não há "município parcialmente na região": a fonte é discreta por município.
* Regiões edafoclimáticas são mantidas na tabela para permitir uma
  sensibilidade mais fina (dentro de macrorregião).

## 8. Sensibilidades previstas (fixadas agora)

1. **Cerrado restrito** = MRS 3 apenas (exclui MT e BA, que são MRS 4).
2. **Grupos por região edafoclimática** (ex.: 101+102 vs 401+402) como
   granularidade alternativa.
3. **Incluir MRS 2 no Sul** (pior caso de má atribuição) — só como sensibilidade.
4. **Excluir MT** (por ser MRS 4 com transição amazônica) do Cerrado.

Nenhuma delas substitui a classificação primária.

## 9. Hash e reprodutibilidade

* O mapeamento é regenerável por `python tools/v34_region_mapping.py`.
* O SHA-256 da planilha de origem e o do arquivo derivado ficam em
  `geospatial/data/manifests/v34_region_mapping.json`.
* A planilha **não** é versionada (arquivo de terceiro, grande); é baixada do
  sítio oficial. O que o repositório guarda é o mapeamento derivado, o hash e a
  citação.

## 10. O que este protocolo impede

Impede que a fronteira seja desenhada depois de ver o resultado; impede chamar
"MRS 4" de "Cerrado"; impede tratar a classificação de soja como classificação
de milho sem declarar; e impede que um município mude de grupo porque o
resultado ficou melhor.
