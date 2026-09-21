# SADEN — Arquitetura

```
┌─────────────┐   HTTPS/JSON    ┌──────────────────────────────┐
│  Frontend   │◄──────────────►│  Backend Express (porta 3001) │
│ vanilla JS  │  /api/* (JWT)  │  routes → services →          │
│ Leaflet +   │  + estáticos   │  integrations → fontes reais  │
│ Chart.js    │                │  SQLite (db + kv_cache)       │
└─────────────┘                └──────┬─────────┬────────┬─────┘
                                      │         │        │
                               Yahoo+PTAX  Open-Meteo  IBGE/geocode
                               (preços)    (clima)   (localidades)
```

## Backend (`backend/src/`)

| Camada | Arquivos | Papel |
|---|---|---|
| entry | `index.js` | Express, `/api/*`, estáticos, erro padronizado |
| config | `config.js` | env (`.env`), TTLs, timeouts |
| db | `db.js` | schema + seed + `kv_cache` |
| middleware | `auth.js`, `rateLimit.js` | JWT `requireAuth`; rate-limit 10/10min em login/registro |
| routes | `auth, commodities, weather, geo, forecast, reports` | HTTP ↔ services |
| services | `priceService, weatherService, geoService, forecastService, fxService` | regras, cache, persistência |
| integrations | `yahooProvider, bcbProvider, openmeteoProvider, ibgeProvider` | 1 arquivo por fonte, retry+timeout |
| utils | `http (fetchJson/withRetry), errors, validate` | transversal |

## Banco (SQLite)

`users, commodities, regions, price_observations, weather_observations, model_runs,
forecasts, reports, data_sources, kv_cache` — ver `db.js` (fonte de verdade do schema).

## Endpoints

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/health` | não | status |
| POST | `/api/auth/register`, `/api/auth/login` | não | credenciais → JWT |
| GET | `/api/auth/me` | sim | sessão |
| GET | `/api/commodities` | sim | 5 commodities |
| GET | `/api/commodities/:key/series?range=` | sim | série BRL + rastreio |
| GET | `/api/commodities/:key/latest` | sim | preço atual + variação |
| GET | `/api/weather/forecast?lat&lon` | sim | clima 7d |
| GET | `/api/weather/history?lat&lon&start&end` | sim | histórico ERA5 |
| GET | `/api/geo/search?q=` | sim | geocode + âncora IBGE |
| GET | `/api/geo/estados`, `/api/geo/estados/:uf/municipios` | sim | IBGE |
| GET | `/api/forecast/:key?horizon=7\|14\|30` | sim | previsão + métricas |
| GET | `/api/reports/:key?...` | sim | relatório consolidado (persiste) |
| GET | `/api/reports/:key/csv?...` | sim | CSV download |
| GET/POST/PATCH/DELETE | `/api/alerts`, `/api/alerts/check`, `/api/alerts/:id/events` | sim | alertas MVP + histórico |
| GET/POST/DELETE | `/api/places` | sim | locais salvos do usuário |
| GET | `/api/prices/reference?commodity=&uf=&ibge_code=` | sim | Price Reference Engine (nível + fallback) |
| GET | `/api/landcover/tile/:z/:x/:y.png`, `/api/landcover/info` | não (tiles públicos) | camada Sentinel-2 Land Cover + metadados |
| GET | `/api/sources` | não | catálogo de fontes |

## Frontend (`frontend/`)

`index.html` (auth + shell com 4 páginas), `css/styles.css` (identidade agro: verde/terra),
`js/api.js` (fetch+JWT), `js/auth.js` (sessão), `js/app.js` (filtros, dashboard+Chart.js,
mapa Leaflet OSM/Esri, relatórios, fontes).
