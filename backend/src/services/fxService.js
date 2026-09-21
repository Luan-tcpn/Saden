'use strict';

// Conversão futuro internacional (USD) -> referência em BRL.
// Metodologia (documentada também em docs/API_SOURCES.md):
//  - Soja/Milho/Trigo (CBOT, centavos/bushel): USD/bu = cents/100.
//    1 saca 60kg = 60 / 27,2155 = 2,20462 bu  =>  R$/sc = USD/bu × PTAX × 2,20462.
//  - Café arábica (ICE, centavos/libra-peso): 60kg = 132,277 lb
//    => R$/sc = USD/lb × PTAX × 132,277.
//  - Algodão (ICE, centavos/libra-peso): R$/lp = USD/lb × PTAX.
// Resultado = REFERÊNCIA internacional convertida, não é o indicador CEPEA
// (preço físico regional). A UI e os relatórios deixam isso explícito.
const BU60 = 60 / 27.2155; // 2.20462
const LB60 = 60 / 0.45359237; // 132.277

function converter(commodityKey) {
  switch (commodityKey) {
    case 'soja':
    case 'milho':
    case 'trigo':
      return { factor: BU60, fromUnit: 'cents/bu', toUnit: 'R$/sc 60kg' };
    case 'cafe':
      return { factor: LB60, fromUnit: 'cents/lb', toUnit: 'R$/sc 60kg' };
    case 'algodao':
      return { factor: 1, fromUnit: 'cents/lb', toUnit: 'R$/lp' };
    default:
      throw new Error(`Commodity desconhecida: ${commodityKey}`);
  }
}

// cents -> USD nativo (por bu ou por lb) -> BRL via fator e PTAX.
function toBRL(commodityKey, cents, fxVenda) {
  const { factor } = converter(commodityKey);
  return (cents / 100) * fxVenda * factor;
}

module.exports = { converter, toBRL, BU60, LB60 };
