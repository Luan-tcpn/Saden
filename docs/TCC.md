# SADEN — Material técnico para o TCC

> Todos os números abaixo foram **gerados pelo próprio sistema em 2026-09-08**
> (série 2025-09-08 → 2026-09-08, n=252 pregões, horizonte 14 dias).
> Nada aqui foi inventado: os payloads completos podem ser reproduzidos via
> `GET /api/forecast/:key?horizon=14`. Evidências de tela em `tmp/shots/`.

## 1. Problema e objetivo

Produtores e analistas precisam acompanhar preços de commodities, clima e
tendências em um só lugar, com fonte declarada. O SADEN integra essas três
dimensões e adiciona previsão quantitativa com incerteza explícita.

## 2. Arquitetura e tecnologias

Ver `docs/ARCHITECTURE.md`. Backend Node.js + Express + SQLite (arquivo único,
zero-config); frontend estático (HTML/CSS/JS + Leaflet + Chart.js) servido na
mesma porta; autenticação JWT + bcrypt; cache em banco com TTL.

## 3. Fontes de dados (ver `docs/API_SOURCES.md`)

| Dado | Fonte | Acesso | Observação |
|---|---|---|---|
| Futuros (soja ZS=F, milho ZC=F, café KC=F, trigo ZW=F, algodão CT=F) | Yahoo Finance chart | sem chave, via backend (sem CORS p/ browser) | referência internacional |
| Câmbio | BCB PTAX (OData) | sem chave | venda; 1 chamada por período |
| Clima (atual, 7d, histórico ERA5) | Open-Meteo | sem chave | fuso America/Sao_Paulo |
| Estados/municípios | IBGE Localidades | sem chave | + geocoding Open-Meteo |
| CEPEA/ESALQ, CONAB | — | **sem API pública** | não integradas; consulta manual linkada |

Preços exibidos = futuro internacional × PTAX (saca 60kg = 2,20462 bu para grãos;
café 60kg = 132,277 lb; algodão em R$/libra-peso). Declarado em tela e relatórios.

## 4. Coleta e tratamento

Série diária 1 ano → ordenação, remoção de não-finitos, sem interpolação silenciosa;
cruzamento com PTAX por data (fallback: última cotação; contador `fx_fallback_days`).
Mínimo de 60 pontos, senão HTTP 422.

## 5. Features e validação

Lags 1/2/5, MM7/MM30, volatilidade 14d, índice de tendência — sempre só com o
passado (alvo = preço seguinte). Split temporal ordenado 70/15/15 (sem leakage).

## 6. Modelos e baselines

Naive, seasonal-naive-5, MM7 e ridge (implementação própria, grade λ ∈ {0.1,1,10,100},
seleção pelo RMSE de validação). Intervalo ±1,96σ√h, piso em zero.

## 7. Resultados reais (horizonte 14 dias)

| Commodity | Atual | Tendência | Vencedor (val) | Teste MAE / RMSE / MAPE |
|---|---|---|---|---|
| Soja | R$ 147,74/sc | baixa | ridge (2,07 < 2,26) | 2,68 / 3,14 / 1,94% |
| Milho | R$ 60,88/sc | baixa | ridge (1,05 < 1,07) | 1,46 / 1,82 / 2,63% |
| Café | R$ 1.988,46/sc | baixa | **naive** (107,99 < 157,96) | 170,71 / 190,50 / 7,36% |
| Trigo | R$ 84,91/sc | baixa | ridge (1,90 < 1,97) | 2,88 / 3,84 / 3,57% |
| Algodão | R$ 4,46/lp | baixa | ridge (0,090 < 0,094) | 0,13 / 0,15 / 2,95% |

Leitura honesta: o ridge supera os baselines em 4 de 5 casos com margem pequena;
no café (série com choque: R$ 1,7 mil → R$ 2,5 mil → R$ 1,9 mil em 2026) o naive
vence — o sistema **declara o baseline como vencedor** em vez de forçar o modelo
complexo. MAPEs de 2–7% refletem mercado real, não precisão artificial.

## 8. Limitações

1. Referência internacional convertida, não preço físico regional (CEPEA/CONAB sem API).
2. Modelo univariado (clima/câmbio como contexto, não features).
3. Datas futuras em dias corridos; intervalo gaussiano subestima choques.
4. Yahoo sem documentação oficial pública — adapter isolado, com retry/cache/fallback de erro.

## 9. Trabalhos futuros

Região/preço físico via convênio de dados; features climáticas e cambiais;
modelos temporais (ARIMA/ETS) como candidatos; cache de forecast; testes mobile
automatizados; endpoint único de comparação se o uso justificar.

## 10. Perguntas esperadas da banca (com respostas curtas e honestas)

- **Por que o preço pode ser nacional?** Porque nenhuma fonte regional possui API
  pública automatizável (CONAB tem reCAPTCHA, CEPEA usa Cloudflare); o Price
  Reference Engine declara o nível e o fallback em cada resposta.
- **Por que não há NDVI?** Exige credencial CDSE e pilha raster; documentado em
  `docs/NDVI_STUDY.md` como fase futura, sem botão falso na interface.
- **Por que não há frete automático?** Coeficientes ANTT vivem em DOU/calculadora
  interativa; subtrair frete estimado do preço seria enganoso — exibimos só
  referência manual.
- **Por que ridge e não XGBoost?** Série curta (~250 pontos) univariada: o ridge
  vence os baselines com margem pequena e é auditável; modelos complexos seriam
  aparência sem evidência de ganho.
- **Como validaram e evitaram leakage?** Split temporal 70/15/15, features só com
  o passado, teste holdout nunca usado no treino; métricas MAE/RMSE/MAPE reais.
- **E se a fonte cair?** Timeout + retry + cache + erro 502 honesto; a UI mostra
  staleness ("último dado há N dias") em vez de fingir atualidade.
