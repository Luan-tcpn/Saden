'use strict';

// Price Reference Engine: resolve o melhor preço disponível na hierarquia
// geográfica com metadados honestos.
//
// Hierarquia: MUNICIPAL → REGIONAL → ESTADUAL → REGIÃO → NACIONAL.
// Estado real (verificado): nenhuma fonte regional automatizável foi encontrada
// (CONAB com reCAPTCHA, CEPEA sem API, ANTT sem tabelas abertas). Portanto os
// níveis municipal→região retornam `unavailable` explícito e o motor entrega o
// nível NACIONAL (Yahoo×PTAX) com a cadeia de fallback declarada.
// NUNCA rotula um preço nacional como municipal/regional.
const priceService = require('./priceService');

const LEVELS = ['municipal', 'regional', 'estadual', 'regiao', 'nacional'];

async function reference(commodityKey, { ibgeCode, uf } = {}) {
  const requested = [];
  if (ibgeCode) requested.push({ level: 'municipal', name: String(ibgeCode) });
  if (uf) requested.push({ level: 'estadual', name: String(uf).toUpperCase() });
  requested.push({ level: 'nacional', name: 'Brasil' });

  const fallbackChain = requested
    .filter((r) => r.level !== 'nacional')
    .map((r) => ({
      level: r.level,
      name: r.name,
      status: 'unavailable',
      reason: 'sem fonte regional automatizável verificada (CONAB/CEPEA sem API pública)',
    }));

  const latest = await priceService.getLatest(commodityKey);
  return {
    commodity: latest.commodity,
    price_brl: latest.price_brl,
    price_usd_cents: latest.price_usd_cents,
    fx_venda: latest.fx_venda,
    unit: latest.unit,
    currency: 'BRL',
    geographic_level: 'nacional',
    geographic_name: 'Brasil',
    source: `${latest.provider} + ${latest.fx_provider}`,
    provider: latest.provider,
    fx_provider: latest.fx_provider,
    trading_level: 'futuro internacional (referência convertida)',
    data_date: latest.data_date,
    previous_date: latest.previous_date,
    variation_pct: latest.variation_pct,
    retrieved_at: latest.retrieved_at,
    cached: latest.cached,
    fallback_chain: fallbackChain,
    note:
      fallbackChain.length > 0
        ? 'Sem cobertura regional automatizada para a localidade: exibida a referência nacional.'
        : 'Preço de referência nacional.',
  };
}

module.exports = { reference, LEVELS };
