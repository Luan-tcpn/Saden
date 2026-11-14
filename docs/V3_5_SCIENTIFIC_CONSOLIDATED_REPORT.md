# SADEN V3.5 — Relatório científico consolidado

**Expansão de São Paulo, identificação dentro da UF e rebaseline**

Branch: `v3/sp-within-state-validation` · Base: `b9e7098` (V3.4) · 2026-11-14

---

## 1. Conclusão em cinco frases

São Paulo entrou com **645 municípios**, dos quais **582** têm painel utilizável,
somando **10.774 linhas** (+55,8% no painel). Pela primeira vez existe **uma UF
com municípios em MRS 1 e MRS 3** (44 e 168), o que quebra o confundimento que
tornava o contraste regional não identificável na V3.4. E o contraste **não
aparece**: na cultura primária (soja), D = **+7,3 kg/ha** (IC de ano [−18,8;
26,9]) e a interação tem p = 0,77 — contra −78,3 kg/ha medidos entre estados na
V3.4. O padrão "Sul a favor, Cerrado contra" era **descritivo entre grupos de
estados** e não se reproduz dentro de um estado. M2 continua o melhor modelo no
painel expandido, e o bloco hídrico continua sem melhorar a previsão (D108).

## 2. O que foi feito

| etapa | estado |
|---|---|
| auditoria de integridade (V1.1 → V3.4, bundles) | ✔ |
| reprodução da V3.4 com o código novo (Experimento A) | ✔ exata |
| aquisição de SP: geometria, clima, PAM, ZARC, CAD | ✔ 645/645 no clima, 0 falhas |
| painel de SP: 19.608 linhas, 10.805 utilizáveis | ✔ |
| mapeamento regional estendido a SP, com verificação de não regressão | ✔ |
| janela corrigida (D100) e descritores (V3.3) aplicados a SP | ✔ |
| rebaseline M0/M1/M2/M2+água (Experimento B) | ✔ |
| comparação de composição (Experimento C) | ✔ |
| contraste MRS 1 × MRS 3 dentro de SP | ✔ |
| robustez: leave-one-year-out, grupos alternativos | ✔ |
| transferência para UF nunca vista | ✔ |
| reconciliação 1.422 × 1.425 | ✔ resolvida |
| cobertura e priorização dos próximos estados | ✔ |

## 3. O achado principal

**Dentro de SP, MRS 1 e MRS 3 não diferem.**

| grupo | n (soja) | ΔMAE (bloco hídrico) |
|---|---:|---:|
| MRS 1 (RE 103, Itapeva/Itararé) | 178 | +2,5 |
| MRS 2 (transição, fora do contraste) | 2.272 | +16,4 |
| MRS 3 (RE 302, oeste paulista) | 1.173 | −4,8 |

**D = +7,3 kg/ha**; IC por ano [−18,8; +26,9]; por município [−9,8; +23,6];
interação associativa +54,0 kg/ha por 100 mm com **p = 0,77** (G = 7 anos).

O intervalo é estreito o suficiente para **descartar** um efeito da ordem do
contraste entre estados (−78,3). Não é falta de poder para o que importa.

Robustez: o sinal de D na soja **inverte** entre anos (−17,8 a +13,2); os grupos
alternativos (MRS 1 × 2 = +1,1; MRS 2 × 3 = +9,0) não mostram gradiente.

## 4. Culturas secundárias (exploratório)

| cultura | Δ MRS 1 | Δ MRS 3 | D | IC ano | p |
|---|---:|---:|---:|---|---:|
| milho | +1,5 | +20,1 | −18,6 | [−51,2; 7,4] | 0,191 |
| milho 2ª | −34,5 | −5,7 | −28,8 | [−71,5; 8,3] | 0,184 |

Nenhum significativo. A MRS é classificação **sojícola**; para milho isso é
estratificação geográfica exploratória (D112), não evidência de zonas de milho.

## 5. Rebaseline

| cultura | M0 (6→7 UFs) | M1 | M2 | ganho M2−M1 (6→7) |
|---|---:|---:|---:|---|
| milho | 1.632,8 → 1.487,6 | 1.836,6 → 1.538,8 | **1.661,2 → 1.452,8** | 175,4 → 86,0 |
| soja | 641,3 → 604,7 | 611,4 → 573,9 | **592,7 → 554,7** | 18,7 → 19,2 |
| milho 2ª | 1.467,1 → 1.326,6 | 1.502,7 → 1.384,6 | **1.272,3 → 1.234,4** | 230,4 → 150,2 |

**As MAEs não são comparáveis entre colunas** (o conjunto de teste muda). O que se
afirma: no painel expandido, M2 supera M1 em 86,0 / 19,2 / 150,2 kg/ha nas mesmas
linhas. A queda do ganho no milho e na milho 2ª é **efeito de composição** (SP tem
níveis mais próximos da média nacional, o que melhora M1), não degradação do
modelo.

**Transferência para UF nunca vista** (treino nas 6 UFs, teste em SP): milho
**−27,3%** e soja **−5,9%** contra a média global; milho 2ª +4,1%. O modelo
**não** transfere para um estado ausente do treino — a dummy de UF não existe e a
previsão cai no intercepto nacional.

## 6. Cobertura

| indicador | V3.4 | V3.5 |
|---|---:|---:|
| UFs | 6 | **7** |
| municípios | 1.274 | **1.856** |
| linhas | 19.307 | **30.081** |
| % do território com indicação de soja | 33,25% | **48,3%** |

Reconciliação da pendência da V3.4: os 3 municípios "faltantes" são **Poxoréo**
(grafia de Poxoréu), **Santo Antônio do Leverger** (`de`/`do`) e **Vila Alta**
(extinto, hoje Alto Paraíso/PR). Não é território ausente.

**Participação na produção nacional não é estimada**: o PAM do repositório não
cobre as 14 UFs restantes. A lacuna é medida em municípios, não em toneladas.

## 7. O que mudou no entendimento do projeto

| afirmação | estado após V3.5 |
|---|---|
| "o bloco hídrico é relativamente melhor no Sul" (V3.3/V3.4, descritivo) | **mantido como descrição entre estados**; **não** se reproduz dentro de SP |
| "a fronteira MRS organiza o efeito" (hipótese da V3.4) | **não sustentada** no primeiro teste dentro de UF |
| "região era não identificável por falta de uma UF mista" | **resolvido** — e o teste foi feito |
| "M2 é o melhor modelo" | **mantido** no painel expandido |
| "SP melhoraria a generalização" | **não**: transferência para SP a partir das 6 UFs é fraca |
| "cobertura nacional" | **não**: 48,3% do território indicado |

## 8. Decisões

* **D116** — SP integrada pela cadeia existente; painel histórico preservado como
  snapshot (`panel_v34_legacy`); rebaseline obrigatório.
* **D117** — o contraste MRS 1 × MRS 3 **não se sustenta** dentro de SP; a
  hipótese regional fica encerrada como explicação (Nível D).
* **D118** — a classificação MRS permanece válida como estratificação
  **sojícola**; para milho e milho 2ª é apenas geográfica e exploratória.
* **D119** — a próxima expansão é **MG** (852 municípios, MRS 2 e 3), por
  critério de identificação e território, não por proximidade.

## 9. Limitações

1. **MRS 1 em SP tem 178 linhas de soja** (~20 municípios) — braço pequeno.
2. **7 anos** no teste associativo; `G` = 7 é pouco.
3. **Desenho escolhido após a V3.4** — teste prospectivo em dados novos, não
   pré-registro (registrado como desvio de processo).
4. **Milho 2ª** carrega a incompatibilidade semântica do PAM (total anual).
5. **Transferência** foi medida só espacialmente, com um estado.
6. **Produção nacional não medida**.

## 10. Recomendação para V3.6

**Integrar MG**, que traz 852 municípios e — mais importante — municípios em
**MRS 2 e MRS 3**, permitindo repetir o teste de identificação dentro de UF num
segundo estado e num par de grupos diferente. Se também falhar, a leitura
regional está duplamente refutada; se funcionar, há um caso onde a MRS organiza
algo.

Não recomendado: novas variáveis climáticas, novos limiares, novas interações.
A especificação não é o gargalo (D108), e agora a fronteira regional também não.

## 11. Reprodutibilidade

```
python tools/v35_acquire_sp.py --stage municipalities
python tools/v35_acquire_sp.py --stage climate
python tools/v35_acquire_sp.py --stage productivity
python tools/v35_acquire_sp.py --stage zarc
python tools/v30_cad_acquire.py --states SP --municipalities ... --geojson ... --panel ... --out ...
python tools/v35_acquire_sp.py --stage panel
python tools/v35_region_mapping.py
python tools/v35_build_windows.py
python tools/v35_models.py
python tools/v35_coverage_and_robustness.py
python tools/v35_verify_report.py
pytest geospatial/tests -q
```
