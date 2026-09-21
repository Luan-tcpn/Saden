'use strict';
// Cliente HTTP mínimo: injeta o JWT e trata erros de forma amigável.
(function () {
  const TOKEN_KEY = 'saden_token';

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }
  function setToken(t) {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
  }

  async function request(path, { method = 'GET', body } = {}) {
    const headers = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (!res.ok) {
      const err = new Error((data && data.error) || `Falha na requisição (${res.status})`);
      err.status = res.status;
      err.details = data && data.details;
      throw err;
    }
    return data;
  }

  window.SadenApi = {
    getToken,
    setToken,
    health: () => request('/api/health'),
    register: (name, email, password) => request('/api/auth/register', { method: 'POST', body: { name, email, password } }),
    login: (email, password) => request('/api/auth/login', { method: 'POST', body: { email, password } }),
    me: () => request('/api/auth/me'),
    forgot: (email) => request('/api/auth/forgot', { method: 'POST', body: { email } }),
    reset: (token, password) => request('/api/auth/reset', { method: 'POST', body: { token, password } }),
    commodities: () => request('/api/commodities'),
    series: (key, range) => request(`/api/commodities/${key}/series?range=${range || '1y'}`),
    latest: (key) => request(`/api/commodities/${key}/latest`),
    reference: (key, { uf, ibge } = {}) => {
      const qs = new URLSearchParams();
      if (uf) qs.set('uf', uf);
      if (ibge) qs.set('ibge_code', ibge);
      const s = qs.toString();
      return request(`/api/prices/reference?commodity=${key}${s ? `&${s}` : ''}`);
    },
    forecast: (key, horizon) => request(`/api/forecast/${key}?horizon=${horizon || 14}`),
    weather: (lat, lon) => request(`/api/weather/forecast?lat=${lat}&lon=${lon}`),
    weatherHistory: (lat, lon, start, end) => request(`/api/weather/history?lat=${lat}&lon=${lon}&start=${start}&end=${end}`),
    geoSearch: (q) => request(`/api/geo/search?q=${encodeURIComponent(q)}`),
    geoReverse: (lat, lon) => request(`/api/geo/reverse?lat=${lat}&lon=${lon}`),
    landcoverInfo: () => request('/api/landcover/info'),
    estados: () => request('/api/geo/estados'),
    municipios: (uf) => request(`/api/geo/estados/${uf}/municipios`),
    report: (key, { lat, lon, horizon } = {}) => {
      const qs = new URLSearchParams({ horizon: horizon || 14 });
      if (lat != null) qs.set('lat', lat);
      if (lon != null) qs.set('lon', lon);
      return request(`/api/reports/${key}?${qs.toString()}`);
    },
    alerts: () => request('/api/alerts'),
    alertCreate: (body) => request('/api/alerts', { method: 'POST', body }),
    alertToggle: (id, active) => request(`/api/alerts/${id}`, { method: 'PATCH', body: { active } }),
    alertDelete: (id) => request(`/api/alerts/${id}`, { method: 'DELETE' }),
    alertCheck: () => request('/api/alerts/check', { method: 'POST' }),
    alertEvents: (id) => request(`/api/alerts/${id}/events`),
    places: () => request('/api/places'),
    placeCreate: (body) => request('/api/places', { method: 'POST', body }),
    placeDelete: (id) => request(`/api/places/${id}`, { method: 'DELETE' }),
    sources: () => request('/api/sources'),
  };
})();
