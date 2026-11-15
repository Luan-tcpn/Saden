'use strict';

process.env.DATABASE_PATH = require('path').join(__dirname, '..', '..', 'tmp', 'test-freshness.db');

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const series = require('../../backend/src/services/seriesService');

// Instantes em UTC correspondentes a America/Sao_Paulo (UTC-3).
const FRI_NOON = new Date('2026-11-13T15:00:00Z'); // sexta 12h SP
const FRI_NIGHT = new Date('2026-11-13T23:00:00Z'); // sexta 20h SP
const SAT_NOON = new Date('2026-11-14T15:00:00Z'); // sábado 12h SP
const SUN_NOON = new Date('2026-11-15T15:00:00Z'); // domingo 12h SP
const MON_MORNING = new Date('2026-11-16T13:00:00Z'); // segunda 10h SP
const MON_NIGHT = new Date('2026-11-16T23:00:00Z'); // segunda 20h SP

describe('calendário de sessão esperada', () => {
  it('sexta antes do fechamento espera a sessão de quinta', () => {
    assert.equal(series.expectedSessionDate(FRI_NOON), '2026-11-12');
  });

  it('sexta depois do fechamento espera a própria sexta', () => {
    assert.equal(series.expectedSessionDate(FRI_NIGHT), '2026-11-13');
  });

  it('sábado e domingo apontam para a sexta', () => {
    assert.equal(series.expectedSessionDate(SAT_NOON), '2026-11-13');
    assert.equal(series.expectedSessionDate(SUN_NOON), '2026-11-13');
  });

  it('segunda de manhã ainda aponta para sexta; à noite, para segunda', () => {
    assert.equal(series.expectedSessionDate(MON_MORNING), '2026-11-13');
    assert.equal(series.expectedSessionDate(MON_NIGHT), '2026-11-16');
  });

  it('reconhece dia de pregão', () => {
    assert.equal(series.isMarketDay(FRI_NOON), true);
    assert.equal(series.isMarketDay(SAT_NOON), false);
    assert.equal(series.isMarketDay(SUN_NOON), false);
    assert.equal(series.isMarketDay(MON_NIGHT), true);
  });
});

describe('estado de frescor', () => {
  it('observação de hoje é atualizada', () => {
    const result = series.freshnessFor('2026-11-16', { now: MON_NIGHT });
    assert.equal(result.status, 'fresh');
    assert.equal(result.detail, 'atualizado');
  });

  it('fim de semana não vira atraso artificial', () => {
    const result = series.freshnessFor('2026-11-13', { now: SAT_NOON });
    assert.equal(result.status, 'fresh');
    assert.equal(result.detail, 'sem_pregao_esperado');
    assert.equal(result.market_day, false);
  });

  it('segunda de manhã aguarda o fechamento do pregão', () => {
    const result = series.freshnessFor('2026-11-13', { now: MON_MORNING });
    assert.equal(result.status, 'fresh');
    assert.equal(result.detail, 'aguardando_pregao');
  });

  it('atraso real vence o fim de semana', () => {
    // 10 dias de atraso num sábado: stale, não "sem pregão".
    const result = series.freshnessFor('2026-11-04', { now: SAT_NOON });
    assert.equal(result.status, 'stale');
    assert.equal(result.detail, 'atrasado');
  });

  it('sem observação é desconhecido, não atrasado', () => {
    const result = series.freshnessFor(null, { now: SAT_NOON });
    assert.equal(result.status, 'unknown');
    assert.equal(result.detail, 'sem_observacao');
  });

  it('o limite de tolerância é exposto para auditoria', () => {
    const result = series.freshnessFor('2026-11-16', { now: MON_NIGHT });
    assert.equal(result.stale_after_days, series.staleAfterDays());
    assert.equal(result.expected_session_date, '2026-11-16');
  });
});

describe('estado operacional da série', () => {
  it('erro de fonte prevalece sobre fim de semana', () => {
    const state = { last_error: 'timeout', consecutive_failures: 2 };
    const status = series.operationalStatus({ observation_date: '2026-11-13' }, state);
    assert.equal(status.status, 'source_error');
  });

  it('sem pregão esperado tem rótulo próprio', () => {
    const status = series.operationalStatus({ observation_date: '2026-11-13' }, null);
    assert.ok(['updated', 'no_session'].includes(status.status));
  });

  it('fonte sem erro e dado velho é atrasado', () => {
    const status = series.operationalStatus({ observation_date: '2026-10-01' }, null);
    assert.equal(status.status, 'late');
  });
});
