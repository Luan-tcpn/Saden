# SADEN — Estudo de viabilidade NDVI (FASE H, somente estudo — NADA implementado)

## Objetivo futuro avaliado

Imagem multiespectral → bandas Red/NIR → NDVI = (NIR − Red)/(NIR + Red) →
evolução temporal por localidade → correlação com clima/preços do SADEN.

## Opções verificadas (set/2026)

### 1. Sentinel-2 via Copernicus Data Space (recomendado se avançar)
- Bandas B04 (Red) e B08 (NIR) a 10 m; revisita de 5 dias no equador.
- Dados gratuitos e abertos (atribuição "contains modified Copernicus Sentinel data").
- Acesso: Sentinel Hub Process API (evalscript NDVI) + Statistics API (série temporal
  por polígono/ponto); catálogo STAC + COGs para processamento próprio.
- Exige: **conta CDSE + credenciais OAuth** (credencial externa — ver abaixo).
- Riscos: nuvens frequentes no Brasil tropical geram lacunas; cotas gratuitas
  limitam uso intensivo; processamento raster é outra ordem de complexidade
  versus o stack tabular atual.

### 2. CBERS-04A (INPE) — alternativa brasileira
- Sensor WPM multiespectral (~8 m) com bandas Red/NIR; dados gratuitos.
- Catálogo/API de acesso menos direto que o CDSE — **não confirmado** se há
  endpoint operacional simples em 2026; exige verificação antes de prometer.

### 3. Produtos NDVI prontos (300 m / 1 km, 10-daily)
- Resolução insuficiente para talhão; úteis no máximo para contexto regional.
- Não recomendado como base do recurso.

## Requisitos para implementação futura

1. Credencial CDSE (OAuth) — **BLOQUEIO atual: sem credencial, sem implementação**.
2. Seleção de área: desenho de polígono no mapa (nova dependência ou código próprio).
3. Máscara de nuvens + agregação temporal + armazenamento de séries.
4. Módulo de correlação NDVI × clima/preço (metodologia a definir no TCC).
5. Cota/licença documentada em API_SOURCES antes de qualquer código.

## Arquitetura recomendada (quando desbloqueado)

```
polígono do usuário (Leaflet)
→ Sentinel Hub Statistics API (NDVI médio por data, com máscara de nuvens)
→ série em nova tabela ndvi_observations (provider, retrieved_at, origem)
→ dashboard: curva NDVI + clima lado a lado; correlação como análise futura
→ tiles NDVI (Process API) como camada opcional do mapa
```

## Veredito

**VIÁVEL tecnicamente, BLOQUEADO por credencial e escopo.** Fases: (1) série
pontual para locais salvos via Statistics API; (2) overlay de tiles + polígono;
(3) correlação. Não iniciar sem credencial CDSE e sem demanda validada do
orientador. Camada "satélite" atual (Esri) é apenas mapa-base — NÃO confundir
com dado espectral.

Fontes: Copernicus Data Space (dataspace.copernicus.eu), Sentinel Hub Process API
(docs.sentinel-hub.com), STAC browser CDSE, sentinels.copernicus.eu.
