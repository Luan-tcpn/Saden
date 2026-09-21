'use strict';

// Interpreta entradas de coordenadas em formatos comuns.
// Aceita: "-21.1775,-47.8103" · "-21.1775, -47.8103" · "(-21.17, -47.81)"
//        "lat: -21.17 lng: -47.81" · "lat=-21.17, lon=-47.81"
// Retorna { lat, lon } ou null (não parece coordenada).
// Valida faixas: lat -90..90, lon -180..180 (fora disso = null + motivo).
function parseCoordinates(input) {
  if (typeof input !== 'string') return null;
  let s = input.trim().replace(/[()]/g, ' ').trim();
  // Formato rotulado: lat:/latitude/lng/lon/longitude
  const labeled = s.match(
    /lat(?:itude)?\s*[:=]\s*(-?\d+(?:\.\d+)?)\s*[,;\s]+lo?n?g?(?:itude)?\s*[:=]\s*(-?\d+(?:\.\d+)?)/i
  );
  let lat;
  let lon;
  if (labeled) {
    lat = Number(labeled[1]);
    lon = Number(labeled[2]);
  } else {
    const parts = s.split(/[,;]/).map((p) => p.trim()).filter(Boolean);
    if (parts.length !== 2) return null;
    if (!/^-?\d+(?:\.\d+)?$/.test(parts[0]) || !/^-?\d+(?:\.\d+)?$/.test(parts[1])) return null;
    lat = Number(parts[0]);
    lon = Number(parts[1]);
  }
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
    return { invalid: true, lat, lon };
  }
  return { lat, lon };
}

module.exports = { parseCoordinates };
