# Consolidação técnica — registro de execução

**Data:** 2026-11-14 · Branch: `maintenance/technical-consolidation`

---

## 1. Auditoria do repositório

- `HEAD` = `32dfb88` (V3.5), árvore limpa, branch sincronizada com o remoto.
- Referências conferidas: `main` e tag `v1-final` = `3f7ad33`; V3.0 `40fd6aa`;
  V3.1 `345b22e`; V3.2 `3bf9360`; V3.3 `6eff88c`; V3.4 `b9e7098`; V3.5 `32dfb88`.
- Bundle V3.5 conferido: 27.487.686 bytes, SHA-256 `981EFA33…F5755E`.
- Suíte herdada: **458/458**.
- **Numeração de decisões:** o pedido supunha D1–D115 e início em D116, mas a
  V3.5 já havia usado D116–D119. Esta etapa começa em **D120**.

## 2. Auditoria da PAM

Construído `tools/audit_pam_quality.py`. Achados:

- 43.650 células, **0 duplicidades** de chave, **0** municípios com série
  parcial (não há criação/extinção dentro de 2017–2025).
- Rendimento consistente com produção/área em **99,8%** das células com área.
- 66 divergências > 1% (mediana 1,75%, máximo 16,7%) — arredondamento da fonte,
  não erro de unidade.
- 99 extremos por MAD; nenhum excluído.
- **Crosswalk:** 0 códigos só na PAM; **2 códigos só no cadastro** —
  `4300001` e `4300002`, que são **Áreas Operacionais** do IBGE (Lagoa Mirim e
  Lagoa dos Patos), não municípios. Zero linhas no painel. Regra de exclusão
  explicitada no pipeline (D121).
- Impacto: **27 de 30.207** linhas analíticas (0,09%) vêm de célula com flag,
  todas em BA (0,35% do painel).

**Erro cometido e corrigido:** três expectativas de caso manual da replicação
foram escritas erradas na primeira versão (déficit de 30 em vez de 20; CAD zero
com déficit no último mês; excedente 70 em vez de 30). O código estava certo; as
expectativas foram recalculadas à mão.

## 3. Auditoria do painel — dois achados materiais

### 3.1. Duas fontes de clima sob a mesma chave

`climate_daily.csv` tem 6.552.547 linhas para 1.622 municípios em 3.653 dias —
**duas linhas por município-dia**. Os 627.381 pares existentes são sempre
**NASA-POWER × INMET**, com valores **diferentes** (ex.: 27,86 °C vs 26,30 °C no
mesmo dia).

O filtro já existia (`source == "NASA-POWER"`), mas era **implícito**. Detectado
porque o loader canônico, escrito para "primeira ocorrência", funcionou **por
acidente de ordenação**. Corrigido: a fonte passou a ser declarada em
`config/panel_v35.json` e o descarte é contado no manifesto (D123).

### 3.2. Linhas INMET com aparência de utilizáveis

No painel base, **2.020 linhas têm `climate_source = INMET` e
`status = paired_usable`**. Nunca foram usadas — mas quem filtrar só por
`status` obtém duas fontes misturadas. Armadilha documentada (D123).

### 3.3. Latitude exportada só para SP

`v35_panel_windows.csv` tem latitude em **10.805 de 30.207** linhas (só SP).
Não afeta cálculo (o gradiente vem do centros do cadastro), mas impede
reconstruir radiação/ET0 a partir do painel sozinho. A replicação passou a ler o
centróide do cadastro.

## 4. Pipeline canônico

`tools/pipeline/build_panel.py` + `config/panel_v35.json`. Não reimplementa
cálculo: chama `v31_rebuild_panel._aggregate`, `v33_water_variables._descriptors`
e `agroclimate.*`. Os scripts históricos **não** foram convertidos em wrappers.

Equivalência verificada em 14 municípios de 7 UFs: **diferença máxima 0,000** em
10 variáveis × 204 linhas (2.040 comparações numéricas).

**Erro cometido e corrigido:** o loader somava variância por cluster uma única
vez nas simulações de poder, criando viés fixo que não se anulava — ver §6.

## 5. Replicação independente

`tools/independent_replication/water_balance_reference.py`, reimplementado a
partir das equações, sem importar `agroclimate.water_balance`.

- 8/8 casos manuais.
- 90 janelas reais: déficit com diferença máxima **4,3 × 10⁻⁶ mm**.
- **D124:** excedente superestimado quando a reposição satura a CAD a partir de
  armazenamento parcial — caso de prova: 15 mm em vez de 5 mm. Déficit,
  armazenamento e ETR não são afetados.
- ET0: divergência de convenção de −1,1% mediana (es(Tmean) vs es(Tmax,Tmin);
  vento com fator 0,4 indevido).

## 6. Poder estatístico

`tools/analysis/statistical_power.py`. Três correções durante a construção:

1. `y - coluna*escalar` gerava matriz n×n por broadcasting (mesmo defeito que
   apaguei do meu próprio `fit_within`).
2. O Monte Carlo **sorteava o componente de cluster uma única vez** e reusava em
   todas as réplicas: a correlação amostral dele com `x_within` virava viés
   constante. Resultado era `type_i_error = 0,0` e `power = 0,0/1,0` — impossível
   em 400 réplicas. Corrigido sorteando por réplica.
3. `design_scenarios` tinha assinatura incompatível com os testes; nomes
   alinhados.

Depois das correções: erro tipo I **7,8% / 6,0% / 10,3%**; poder no MDE
**88% / 92% / 94%**.

## 7. Clone limpo

Clone `--no-hardlinks --single-branch` em diretório temporário isolado: 537
arquivos, 91,9 MB, sem painéis derivados. `venv` novo, `pip install -r
requirements.txt`.

**Defeito encontrado:** `requirements.txt` **não declarava `pytest`** — ambiente
novo não conseguia rodar a suíte. Corrigido (`pytest==9.2.0`).

Resultados: 479 passaram, 3 pularam (dados derivados ausentes, esperado), painel
reconstruído e verificado com **0,000** de diferença, replicação independente
reproduzida (36 janelas), auditoria PAM reproduzida com **números idênticos**.

**Caveat registrado:** o hash do manifesto da auditoria **difere** entre clone e
original porque o arquivo embute `generated_at` e tamanhos de arquivo. Os
**números** são idênticos. Manifesto não é bit-reprodutível por desenho.

## 8. Publicação

Commits na branch `maintenance/technical-consolidation`. Sem force push, sem
reescrita, sem merge em `main`, sem exclusão de branch ou tag.
