# SADEN V2.7 — Decisões D76 em diante

> Registro de decisões da etapa V2.7 (robustez estatística, validação
> espacial e agronomia). As decisões D1–D75 permanecem em
> `docs/DECISIONS.md`. Cada decisão traz a **evidência** que a sustenta.

## D76 — A dependência espacial excede a resolução nominal da grade (2026-11-14)

**Decisão.** A célula nominal de 55 km (MERRA-2) **não** é a unidade de
agrupamento adequada. A escala de dependência é calibrada empiricamente pelo
correlograma de anomalias e fixada em **blocos espaciais de 250 km**.

**Evidência.**
* NASA POWER **interpola** a coordenada solicitada: 0% dos dias têm séries
  idênticas entre municípios da mesma célula; diferença média absoluta de
  temperatura entre 0,32 °C e 1,90 °C. Portanto, tratar a célula nominal
  como "observações iguais" é incorreto.
* Correlograma das **anomalias anuais** (1.296 municípios, 3.653 dias):
  temperatura 0,9965 / 0,9876 / 0,9737 / 0,9417 / 0,9032 / 0,8568 e
  precipitação 0,9773 / 0,9195 / 0,8307 / 0,6479 / 0,4911 / 0,3591 nas
  bandas 0–25 / 50–75 / 100–125 / 200–225 / 300–325 / 400–425 km.
* Na banda 400–425 km a correlação ainda é 0,834 (temperatura) e 0,630
  (precipitação) — a dependência não termina na resolução da grade.

**Consequência.** A inferência passa a ser reportada em quatro esquemas
(município, célula MERRA-2, bloco de 250 km, UF) e o bloco de 250 km é
adotado como esquema **conservador** de referência.

## D77 — Esquemas de inferência pré-declarados e Holm sobre a família completa (2026-11-14)

**Decisão.** Nenhum esquema é escolhido *a posteriori*. A família de
hipóteses é fixada em **21 hipóteses** (3 culturas × 7 variáveis), com
correção de **Holm** (FWER) aplicada separadamente a cada esquema. Conley
(150/250/400/600 km) e o bootstrap wild são **procedimentos alternativos**,
não combináveis entre si.

**Evidência.** O manifesto `v27_robust_inference.json` registra, para cada
esquema, o p bruto e o p ajustado de Holm. O esquema conservador (bloco
250 km) mantém **4 de 21** hipóteses; a célula MERRA-2 (383 grupos) mantém
12; o Conley mantém 8–10 conforme o corte.

**Proibição explícita.** Não se ajusta critério, banda ou esquema para
obter significância.

## D78 — Janela fenológica é experimento, com requisitos térmicos publicados (2026-11-14)

**Decisão.** O ZARC é janela de **plantio por risco**, não calendário
fenológico. A janela de **enchimento de grãos** é construída a partir de
requisitos térmicos **publicados** (Embrapa) e usada como **linha
experimental**; a janela do ZARC é preservada como protocolo principal.

**Parâmetros e fontes.**
* Soja (Fehr & Caviness, 1977; requisitos de Schneider et al., 1987 e
  Martorano et al., 2012, via Embrapa Soja): **R1 = 92,5 °C·dia**,
  **R5 = 554 °C·dia** (Tb = 10 °C). Janela = R5 → R5 + 45 dias (cenário
  explícito; a sensibilidade 30/45/60 dias está declarada).
* Milho (Embrapa Milho e Sorgo): Tmax ≤ 30 °C, Tmin ≥ 10 °C, Tb = 10 °C;
  780–830 °C·dia (superprecoces), 831–890 (precoces), 890–1.200 (normais)
  da emergência ao início da polinização. Janela = VT + 22,5 dias (R3,
  ≈20–25 d) até VT + 55 dias (R6, ≈50–60 d).
* Milho 2ª safra: **sem** definição publicada com precisão suficiente →
  permanece na janela do ZARC (ausência preservada).

**Método.** As datas são **aproximadas**, obtidas acumulando a soma térmica
**real observada** a partir da data de plantio do ZARC — logo dependem do
clima do ano. Nenhuma data municipal é inventada.

## D79 — Calibração do bootstrap wild por Monte Carlo (2026-11-14)

**Decisão.** O bootstrap wild **só pode ser usado** se o seu tamanho
nominal for demonstrado. A V2.7 executa calibração Monte Carlo com dois
DGP: (A) erro agrupado por grupo; (B) painel município × ano com efeitos
fixos nas duas direções e erro **AR(1) intracluster** (espelha o painel
real). Diagnóstico por **taxa de rejeição em vários níveis nominais**
(1%, 5%, 10%) com incerteza de Monte Carlo, mais a largura da distribuição
bootstrap. O KS contra U(0,1) é apenas indicativo: o p-valor do bootstrap é
**discreto**.

**Regra.** Nenhuma técnica é declarada "calibrada" sem evidência de
simulação.

## D80 — Correção dos pesos do bootstrap wild: um peso por grupo (2026-11-14)

**Decisão.** O bootstrap wild usa **um peso de Rademacher por grupo e por
replicação** (Cameron, Gelbach & Miller, 2008), que é o que preserva a
dependência intracluster.

**Defeito corrigido.** A implementação herdada da sessão anterior sorteava
`size=len(grupo)` pesos — isto é, **um peso por observação** — apesar de o
próprio texto do código afirmar "pesos por grupo". Com pesos por
observação o bootstrap **não preserva** a estrutura de dependência e
degenera no bootstrap wild ordinário.

**Efeito observado (calibração).** Com 5 grupos, o esquema por grupo tem
poder de **46%** sob efeito verdadeiro, enquanto o esquema por observação
tem **88%** — ou seja, a variante herdada não corrigia o problema de
poucos grupos.

**Nota metodológica.** As duas variantes foram mantidas no código
(`weight_scheme="cluster" | "observation"`) para comparação explícita; o
padrão é `"cluster"`.

## D81 — Política de nulidade do bootstrap declarada, não implícita (2026-11-14)

**Decisão.** O bootstrap wild é reportado com **os dois** p-valores:
nulidade **imposta** (β = 0) e nulidade **irrestrita** (β = β̂), mais a
política efetivamente usada (`--null-policy`, padrão `auto`).

**Motivo.** A convenção de Cameron, Gelbach & Miller para alternar entre as
duas nulidades **não pôde ser verificada no artigo primário** neste
ambiente (artigo, CRAN e repositórios inacessíveis). Aplicar uma regra
silenciosa seria presenter uma convenção não verificada como se fosse
fato. Reportar as duas e declarar a política é a alternativa honesta.

## D82 — CAD territorial geoespacial da Embrapa Solos (2026-11-14)

**Decisão.** A capacidade de água disponível (CAD) pode ser derivada de
fonte **oficial e geoespacial**: Embrapa Solos / GeoInfo, *Mapas de água
disponível do solo do Brasil* (Vasques, G.M., Dart, R.O., Cintra, L.C. &
Baca, J.F.M., 2021; 90 m; versões 2021; licença **CC BY-NC 3.0 BR**).

**Unidade e conversão.** As camadas são declaradas em **mm/cm**
(milímetros de água por centímetro de solo), nas profundidades 0–5, 5–15,
15–30, 30–60, 60–100 e 100–200 cm. A CAD do perfil, em **mm de água**, é a
integração `Σ AW(mm/cm) × espessura(cm)` — **nunca** uma multiplicação
direta. Valor não válido (no-data −9999) permanece ausência.

**Resultado da amostra controlada (10 municípios).** CAD de 0–100 cm entre
**126,0 e 239,9 mm** (mediana **158,9 mm**); os **10/10** municípios
superam os três cenários da V2.6 (35/50/70 mm). Os cenários da V2.6 são,
portanto, **conservadores** frente ao dado oficial.

**Status.** A CAD geoespacial entra como **linha experimental**; o balanço
hídrico da V2.6 é mantido como comparação.

## D83 — ERA5-Land permanece bloqueado; NASA POWER é a base (2026-11-14)

**Decisão.** O acesso nativo ao CDS exige credencial
(`CDS_API_KEY` / `~/.cdsapirc` / pacote `cdsapi`) **não configurada** neste
ambiente. Não se cria conta em nome do usuário, não se pede credencial por
chat e não se guarda segredo no Git. O bloqueio fica **documentado** e a
V2.7 prossegue com **NASA POWER** como base reanalisada e **INMET** como
observação independente. O acesso parcial via Open-Meteo (429) não é
repetido.

## D84 — Painel e artefatos grandes fora do Git; manifests versionados (2026-11-14)

**Decisão.** Estendida de D74. O painel de 1.076 MB (835 MB de base diária)
permanece fora do Git; os **manifests** (`v27_*.json`, `v27_*.csv`) são
versionados porque são pequenos e verificáveis. Os scripts de
experimento ficam em `tools/` e são versionados; os scripts de sondagem
temporários da sessão anterior (`tmp/v27_*.py`) permanecem fora do Git e
têm seus resultados consolidados nos manifests.

## D85 — Réplica com erro-padrão nulo é descartada, não contada (2026-11-14)

**Decisão.** Uma réplica do bootstrap cuja variância agrupada se anula por
arredondamento (`se` positivo da ordem de 1e-19) é **descartada**, e não
contada como excedência. O critério é relativo à magnitude do coeficiente:
`se <= sqrt(eps) · max(|β̂|, 1)`, a mesma tolerância de posto do
`numpy.linalg.lstsq`. A regra vale para o bootstrap OLS
(`robust.py`) e para o bootstrap *within* (`spatial_inference.py`), e
também para decidir se um coeficiente observado tem `t` definido.

**Evidência.** A grade de calibração da sessão anterior registrou
`mean_t_boot_sd_cluster ≈ 8,5e14` em 9 casos (G = 5 e G = 10, DGP
`agrupado`). O valor não era ruído de diagnóstico: vinha de `|t| ≈ 1e18`
produzido por `se > 0` aceitar um erro-padrão numericamente nulo. Cada
réplica assim entrava na cauda como excedência espúria e inflava
`t_boot_sd` e os quantis.

**Alcance verificado.** Nos resultados publicados da V2.7 **não havia**
réplica degenerada: os 105 bootstraps de `v27_robust_inference.json`
usaram `n_bootstrap_used = 999` de 999. A correção não altera nenhum
p-valor já reportado; ela elimina um modo de falha latente e restaura a
utilidade dos diagnósticos de dispersão.

## D86 — Holdout espacial **e** temporal simultâneos (P5) (2026-11-14)

**Decisão.** Os protocolos territoriais da V2.6/V2.7 (P1–P4) separam
apenas o **espaço**. Como as variáveis climáticas têm componente regional
comum dentro do ano, o treino contém o **mesmo ano** da observação de
teste em outros municípios, e o coeficiente ajustado pode absorver o
choque daquele ano. Acrescenta-se o protocolo **P5**, que remove do
treino, ao mesmo tempo, os blocos espaciais e os anos da dobra: nenhuma
observação de treino compartilha bloco **nem** ano com a de teste.

**Consequência metodológica.** O ganho que sobrevive a P5 não pode ser
atribuído a vizinhança geográfica nem a informação do próprio ano. Se o
ganho desaparecer em P5 e existir em P1–P3, a conclusão correta é que o
ganho territorial aparente era, em parte, **efeito do ano compartilhado** —
e isso deve ser reportado como limitação, não corrigido.

**Evidência.** `v27_spatial_validation.json`, chave `P5_bloco_x_ano`;
implementação em `analysis.two_way_blocked_holdout`; teste de ausência de
vazamento em `TwoWayHoldoutTest`.
