'use strict';

// Cobertura do solo Sentinel-2 10m (Impact Observatory + Esri, Living Atlas).
// Serviço ImageServer público VERIFICADO em 2026-09-15:
//   https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer
// Operações verificadas: exportImage (tiles PNG), legend (9 classes), query de
// catálogo (anos 2017–2025). `identify` pixel a pixel retorna NoData anônimo
// (provável exigência de token) — portanto SEM consulta de classe por ponto e
// SEM estatísticas de área (sem cálculo real, sem porcentagem inventada).
// Licença: obra LULC CC BY 4.0; serviço sob Esri Master License Agreement.
// Atribuição obrigatória: "Esri, Impact Observatory".
const { withRetry } = require('../utils/http');
const config = require('../config');

const BASE = 'https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer';
const UA = 'SADEN-TCC/0.1 (uso-academico)';

// Classes verificadas via /legend do próprio serviço (nomes exatos).
// Cores MEDIDAS de tiles reais do serviço (amostradas em 2026-09-15 de áreas
// de classe inequívoca: oceano/Amazônia/urbanização/dunas/nevealpina — ver
// docs/DECISIONS.md D29). Rangeland: cor não amostrada nos mosaicos verificados
// (pastagens renderizam como Bare/Crops) — sem caixa de cor, sem invenção.
const CLASSES = [
  { value: 1, name: 'Water', color: '#1a5bab', description: 'Água predominante no ano (rios, lagos, oceanos).' },
  { value: 2, name: 'Trees', color: '#358221', description: 'Vegetação densa alta (matas, plantações arbóreas, manguezais).' },
  { value: 4, name: 'Flooded Vegetation', color: '#87d19e', description: 'Vegetação alagada na maior parte do ano (várzeas, arroz irrigado).' },
  { value: 5, name: 'Crops', color: '#ffdb5c', description: 'Culturas plantadas (milho, trigo, soja, talhões em pousio).' },
  { value: 7, name: 'Built Area', color: '#ed022a', description: 'Área construída (casas, cidades, estradas pavimentadas).' },
  { value: 8, name: 'Bare Ground', color: '#efcfa8', description: 'Solo exposto ou rocha (mineração, deserto, salinas).' },
  { value: 9, name: 'Snow/Ice', color: '#f2faff', description: 'Neve/gelo permanente (irrelevante no Brasil).' },
  { value: 10, name: 'Clouds', color: '#ede9e4', description: 'Sem informação por cobertura persistente de nuvens.' },
  { value: 11, name: 'Rangeland', color: null, description: 'Pastagens e campos naturais (pastagens, savanas, cerrado aberto).' },
];

function xyzToBbox(z, x, y) {
  const n = 2 ** z;
  const lonW = (x / n) * 360 - 180;
  const lonE = ((x + 1) / n) * 360 - 180;
  const toLat = (t) => {
    const rad = Math.atan(Math.sinh(Math.PI * (1 - (2 * t) / n)));
    return (rad * 180) / Math.PI;
  };
  const latN = toLat(y);
  const latS = toLat(y + 1);
  const R = 6378137;
  const x3857 = (lon) => (lon * Math.PI * R) / 180;
  const y3857 = (lat) => Math.log(Math.tan(Math.PI / 4 + ((lat * Math.PI) / 180) / 2)) * R;
  return { xmin: x3857(lonW), ymin: y3857(latS), xmax: x3857(lonE), ymax: y3857(latN) };
}

async function tile(z, x, y) {
  const b = xyzToBbox(z, x, y);
  const params = new URLSearchParams({
    bbox: `${b.xmin},${b.ymin},${b.xmax},${b.ymax}`,
    bboxSR: '3857',
    imageSR: '3857',
    size: '256,256',
    format: 'png',
    pixelType: 'U8',
    mosaicRule: JSON.stringify({ mosaicMethod: 'esriMosaicNorthWest' }),
    f: 'image',
  });
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), Math.max(config.httpTimeoutMs, 25000));
  try {
    const res = await withRetry(() =>
      fetch(`${BASE}/exportImage?${params.toString()}`, {
        signal: ctrl.signal,
        headers: { 'User-Agent': UA },
      }).then((r) => {
        if (!r.ok) {
          const e = new Error(`LandCover respondeu ${r.status}`);
          e.status = 502;
          throw e;
        }
        return r;
      })
    );
    const buf = Buffer.from(await res.arrayBuffer());
    const ct = res.headers.get('content-type') || '';
    if (!ct.includes('image') || buf.length < 100) {
      throw Object.assign(new Error('LandCover sem tile válido para a área'), { status: 502 });
    }
    return buf;
  } catch (e) {
    if (e.name === 'AbortError') throw Object.assign(new Error('Timeout na camada LandCover'), { status: 502 });
    if (!e.status) e.status = 502;
    throw e;
  } finally {
    clearTimeout(t);
  }
}

module.exports = { tile, xyzToBbox, CLASSES, SERVICE_URL: BASE };
