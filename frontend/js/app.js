'use strict';
// SADEN frontend: dashboard, mapa, relatórios e fontes. Toda tela consome o backend.
(function () {
  const state = {
    inited: false,
    commodities: [],
    commodity: 'soja',
    horizon: 14,
    range: '1y',
    uf: null,
    lat: -21.1775, // Ribeirão Preto (referência inicial)
    lon: -47.8103,
    place: 'Ribeirão Preto, SP',
    charts: {},
    map: null,
    mapLayers: {},
    mapMarker: null,
  };

  const $ = (id) => document.getElementById(id);
  const Api = () => window.SadenApi;
  const fmtBRL = (n) => n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  // Escape HTML para qualquer string vinda de input do usuário, API ou fonte
  // externa antes de interpolar em innerHTML (anti-XSS; sem dependências).
  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function setStatus(id, kind, msg) {
    const el = $(id);
    el.className = `status ${kind || ''}`;
    el.textContent = msg || '';
  }

  // Contexto por tela (decisão D33): o formulário completo (.topbar) é exibido
  // via CSS só em dashboard, mapa e relatórios; Aparência/Fontes/Alertas/Locais
  // não o exibem. O estado interno continua compartilhado.

  function destroyChart(id) {
    if (state.charts[id]) {
      state.charts[id].destroy();
      delete state.charts[id];
    }
  }

  // ---------------- navegação ----------------
  function bindNav() {
    document.querySelectorAll('[data-nav]').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('[data-nav]').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const page = btn.getAttribute('data-nav');
        ['dashboard', 'mapa', 'relatorio', 'fontes', 'alertas', 'aparencia'].forEach((p) => {
          $(`page-${p}`).classList.toggle('hidden', p !== page);
        });
        // Contexto completo só onde tem valor operacional (D33): o formulário
        // é movido para antes da página ativa (preserva listeners e estado).
        // Aparência/Fontes/Alertas/Locais não o exibem.
        const topbar = document.querySelector('.topbar');
        if (['dashboard', 'mapa', 'relatorio'].includes(page)) {
          topbar.style.display = '';
          const sec = $(`page-${page}`);
          sec.parentNode.insertBefore(topbar, sec);
        } else {
          topbar.style.display = 'none';
        }
        if (page === 'mapa') {
          initMap();
          initPlaces();
        }
        if (page === 'fontes') loadSources();
        if (page === 'alertas') initAlerts();
        closeDrawer();
      });
    });
    $('btn-drawer').addEventListener('click', () => {
      $('view-app').classList.add('drawer-open');
      $('drawer-overlay').classList.remove('hidden');
      $('btn-drawer-close').focus();
      if (state.map) setTimeout(() => state.map.invalidateSize(), 250);
    });
    const close = () => closeDrawer();
    $('btn-drawer-close').addEventListener('click', close);
    $('drawer-overlay').addEventListener('click', close);
  }

  function closeDrawer() {
    const wasOpen = $('view-app').classList.contains('drawer-open');
    $('view-app').classList.remove('drawer-open');
    $('drawer-overlay').classList.add('hidden');
    if (wasOpen) $('btn-drawer').focus();
  }

  // ---------------- tema ----------------
  function currentThemeIsDark() {
    return document.documentElement.dataset.theme === 'dark';
  }

  function applyChartTheme() {
    if (typeof Chart === 'undefined') return;
    const dark = currentThemeIsDark();
    Chart.defaults.color = dark ? '#c4d2c6' : '#5d6b5a';
    Chart.defaults.borderColor = dark ? '#3a463f' : '#e4eae2';
  }

  function applyTheme(pref, { silent } = {}) {
    localStorage.setItem('saden_theme', pref);
    let dark = pref === 'dark';
    if (pref === 'system') {
      dark = matchMedia('(prefers-color-scheme: dark)').matches;
    }
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    document.querySelectorAll('input[name="theme"]').forEach((r) => {
      r.checked = r.value === pref;
    });
    applyChartTheme();
    if (!silent && state.inited) {
      refresh();
      const ok = $('theme-ok');
      if (ok) ok.classList.remove('hidden');
    }
  }

  function bindTheme() {
    const saved = localStorage.getItem('saden_theme') || 'system';
    applyTheme(saved, { silent: true });
    document.querySelectorAll('input[name="theme"]').forEach((r) => {
      r.addEventListener('change', (e) => applyTheme(e.target.value));
    });
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if ((localStorage.getItem('saden_theme') || 'system') === 'system') {
        applyTheme('system', { silent: true });
        if (state.inited) refresh();
      }
    });
  }

  // ---------------- filtros ----------------
  async function loadFilters() {
    const { commodities } = await Api().commodities();
    state.commodities = commodities;
    $('sel-commodity').innerHTML = commodities
      .map((c) => `<option value="${esc(c.key)}">${esc(c.name)}</option>`)
      .join('');
    $('sel-commodity').value = state.commodity;

    const { estados } = await Api().estados();
    $('sel-uf').innerHTML =
      '<option value="">—</option>' + estados.map((e) => `<option value="${esc(e.sigla)}">${esc(e.nome)} (${esc(e.sigla)})</option>`).join('');

    $('sel-commodity').addEventListener('change', (e) => {
      state.commodity = e.target.value;
    });
    $('sel-horizon').addEventListener('change', (e) => {
      state.horizon = Number(e.target.value);
    });
    $('sel-range').addEventListener('change', (e) => {
      state.range = e.target.value;
    });
    $('sel-uf').addEventListener('change', async (e) => {
      const uf = e.target.value;
      state.uf = uf || null;
      $('sel-municipio').innerHTML = '<option value="">—</option>';
      if (!uf) return;
      try {
        const { municipios } = await Api().municipios(uf);
        $('sel-municipio').innerHTML =
          '<option value="">—</option>' +
          municipios.map((m) => `<option value="${m.id}">${esc(m.nome)}</option>`).join('');
        $('sel-municipio').dataset.uf = uf;
      } catch (err) {
        setStatus('dash-status', 'error', `Falha ao listar municípios: ${err.message}`);
      }
    });
    $('sel-municipio').addEventListener('change', async (e) => {
      const opt = e.target.selectedOptions[0];
      if (!opt || !opt.value) return;
      const wanted = e.target.value; // ignora resposta defasada se o usuário trocar de município
      const nome = `${opt.text}, ${e.target.dataset.uf}`;
      setStatus('loc-status', 'loading', `Localizando ${nome}…`);
      try {
        const res = await Api().geoSearch(nome);
        if (e.target.value !== wanted) return;
        if (!res.results.length) throw new Error('município não geocodificado');
        const first = res.results[0];
        state.lat = first.latitude;
        state.lon = first.longitude;
        state.place = first.label || nome;
        state.locApplied = $('inp-location').value;
        $('inp-location').value = first.label && first.label.length < 80 ? first.label : first.name;
        state.locApplied = $('inp-location').value;
        $('coord-label').textContent = `${state.lat.toFixed(4)}, ${state.lon.toFixed(4)}`;
        $('place-label').textContent = `— ${state.place}`;
        setStatus('loc-status', 'ok', `Localidade: ${state.place}`);
        syncMapMarker();
      } catch (err) {
        setStatus('loc-status', 'error', `Não foi possível localizar ${nome}: ${err.message}. As análises seguem com a localidade anterior.`);
      }
    });

    let searchTimer;
    let lastSuggestions = [];
    let activeSug = -1;
    const locBox = $('location-results');
    const hideSuggest = () => {
      locBox.classList.add('hidden');
      activeSug = -1;
      $('inp-location').removeAttribute('aria-activedescendant');
    };
    const paintActive = () => {
      locBox.querySelectorAll('button[data-i]').forEach((b, i) => {
        const on = i === activeSug;
        b.classList.toggle('active', on);
        if (on) {
          b.id = `sug-${i}`;
          $('inp-location').setAttribute('aria-activedescendant', `sug-${i}`);
          b.scrollIntoView({ block: 'nearest' });
        }
      });
    };
    $('inp-location').addEventListener('keydown', (e) => {
      const items = locBox.querySelectorAll('button[data-i]');
      if (e.key === 'Enter' && (locBox.classList.contains('hidden') || !items.length || activeSug < 0)) {
        e.preventDefault();
        refresh();
        return;
      }
      if (locBox.classList.contains('hidden') || !items.length) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        activeSug = e.key === 'ArrowDown'
          ? (activeSug + 1) % items.length
          : (activeSug - 1 + items.length) % items.length;
        paintActive();
      } else if (e.key === 'Enter' && activeSug >= 0 && lastSuggestions[activeSug]) {
        e.preventDefault();
        applyPlace(lastSuggestions[activeSug], $('inp-location').value.trim());
        hideSuggest();
      } else if (e.key === 'Escape') {
        hideSuggest();
      }
    });
    $('inp-location').addEventListener('input', (e) => {
      clearTimeout(searchTimer);
      state.locApplied = null;
      const q = e.target.value.trim();
      if (q.length < 3) {
        hideSuggest();
        return;
      }
      searchTimer = setTimeout(async () => {
        try {
          const res = await Api().geoSearch(q);
          lastSuggestions = res.results || [];
          if (!lastSuggestions.length) {
            locBox.innerHTML = `<button type="button" disabled>Nenhum local encontrado para “${esc(q)}”.</button>`;
          } else {
            locBox.innerHTML = lastSuggestions
              .map(
                (r, i) =>
                  `<button type="button" data-i="${i}" role="option"><strong>${esc(r.name)}</strong><span class="src">${esc(r.label || '')} · ${esc(r.provider)}</span></button>`
              )
              .join('');
          }
          locBox.classList.remove('hidden');
        } catch (err) {
          locBox.innerHTML = `<button type="button" disabled>Busca indisponível: ${esc(err.message)}</button>`;
          locBox.classList.remove('hidden');
        }
      }, 400);
    });
    locBox.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-i]');
      if (!btn) return;
      const r = lastSuggestions[Number(btn.getAttribute('data-i'))];
      if (r) applyPlace(r, $('inp-location').value.trim());
      hideSuggest();
    });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.loc-field')) hideSuggest();
    });

    $('btn-myloc').addEventListener('click', useMyLocation);
    $('btn-apply').addEventListener('click', refresh);
    $('btn-clear').addEventListener('click', () => {
      state.commodity = 'soja';
      state.horizon = 14;
      state.range = '1y';
      state.lat = -21.1775;
      state.lon = -47.8103;
      state.place = 'Ribeirão Preto, SP';
      state.locApplied = null;
      $('sel-commodity').value = 'soja';
      $('sel-horizon').value = '14';
      $('sel-range').value = '1y';
      $('inp-location').value = '';
      $('sel-uf').value = '';
      $('sel-municipio').innerHTML = '<option value="">—</option>';
      setStatus('loc-status', '', '');
      refresh();
    });
  }

  function applyPlace(r, typedText) {
    state.lat = r.latitude;
    state.lon = r.longitude;
    state.place = r.label || r.name;
    state.locApplied = typedText != null ? typedText : null;
    $('inp-location').value = r.label && r.label.length < 80 ? r.label : r.name;
    state.locApplied = $('inp-location').value;
    $('coord-label').textContent = `${state.lat.toFixed(4)}, ${state.lon.toFixed(4)}`;
    $('place-label').textContent = `— ${state.place}`;
    setStatus('loc-status', 'ok', `Localidade: ${state.place}`);
    syncMapMarker();
  }

  function syncMapMarker() {
    if (!state.map) return;
    if (state.mapMarker) state.mapMarker.remove();
    state.mapMarker = L.marker([state.lat, state.lon]).addTo(state.map);
    state.map.setView([state.lat, state.lon], Math.max(state.map.getZoom(), 6));
  }

  function useMyLocation() {
    setStatus('loc-status', 'loading', 'Solicitando sua localização ao navegador…');
    if (!('geolocation' in navigator)) {
      setStatus('loc-status', 'error', 'Este navegador não suporta geolocalização. Pesquise por cidade, endereço ou coordenadas.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(4));
        const lon = Number(pos.coords.longitude.toFixed(4));
        try {
          const r = await Api().geoReverse(lat, lon);
          applyPlace(r, `minha-localizacao:${lat},${lon}`);
          if (!r.in_brazil) {
            setStatus('loc-status', 'ok', `Você está em ${r.label}. Nota: análises do SADEN focam o Brasil.`);
          }
        } catch (err) {
          state.lat = lat;
          state.lon = lon;
          state.place = 'minha localização';
          state.locApplied = $('inp-location').value;
          $('coord-label').textContent = `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
          $('place-label').textContent = '— minha localização';
          setStatus('loc-status', 'error', `Coordenadas obtidas, mas sem nome do local: ${err.message}`);
          syncMapMarker();
        }
      },
      (err) => {
        const msg =
          err.code === 1
            ? 'Permissão de localização negada. Você pode pesquisar manualmente por cidade, endereço ou coordenadas.'
            : err.code === 3
              ? 'Tempo esgotado ao obter localização. Tente novamente ou pesquise manualmente.'
              : 'Localização indisponível no momento. Pesquise manualmente por cidade, endereço ou coordenadas.';
        setStatus('loc-status', 'error', msg);
      },
      { timeout: 12000, maximumAge: 60000 }
    );
  }

  // Interpreta "lat, lon" digitados (espelho simples da regra do backend).
  // Quando o usuário digita coordenadas, a ANÁLISE usa os valores exatos
  // digitados; o rótulo vem do reverse geocoding (display apenas).
  function parseTypedCoords(typed) {
    const m = String(typed || '')
      .replace(/[()]/g, ' ')
      .trim()
      .match(/^(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)$/);
    if (!m) return null;
    const lat = Number(m[1]);
    const lon = Number(m[2]);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
    return { lat, lon };
  }

  function resolveLocation() {
    // 1) sugestão aplicada ou texto inalterado: usa o que já foi resolvido.
    // 2) município IBGE selecionado: geocodifica o nome para obter lat/lon.
    // 3) texto digitado (cidade, endereço, rua ou "lat, lon"): busca unificada.
    const typed = $('inp-location').value.trim();
    if (typed && state.locApplied === typed) return Promise.resolve();
    if (typed && typed.length >= 3) {
      return Api()
        .geoSearch(typed)
        .then((res) => {
          if (!res.results.length) throw new Error(`Nenhum local encontrado para “${typed}”. Tente cidade, endereço ou coordenadas.`);
          const first = res.results[0];
          const exact = res.mode === 'coordinates' ? parseTypedCoords(typed) : null;
          state.lat = exact ? exact.lat : first.latitude;
          state.lon = exact ? exact.lon : first.longitude;
          state.place = first.label || first.name;
          state.locApplied = typed;
        });
    }
    return Promise.resolve();
  }

  // ---------------- dashboard ----------------
  async function refresh() {
    setStatus('dash-status', 'loading', 'Consultando backend…');
    try {
      await resolveLocation();
      $('coord-label').textContent = `${state.lat.toFixed(4)}, ${state.lon.toFixed(4)}`;
      $('place-label').textContent = state.place ? `— ${state.place}` : '';
      const [latest, series, fc, wx] = await Promise.all([
        Api().reference(state.commodity, { uf: state.uf }),
        Api().series(state.commodity, state.range),
        Api().forecast(state.commodity, state.horizon),
        Api().weather(state.lat, state.lon),
      ]);
      renderPriceCards(latest, series);
      renderHistory(series);
      renderForecast(fc);
      renderMetrics(fc);
      renderWeather(wx);
      await renderCompare();
      setStatus('dash-status', 'ok', `Atualizado em ${new Date().toLocaleString('pt-BR')} · ${latest.cached ? 'cache local' : 'fontes consultadas agora'}.`);
    } catch (err) {
      setStatus('dash-status', 'error', `Não foi possível carregar: ${err.message}`);
    }
  }

  function renderPriceCards(latest, series) {
    const dir = latest.variation_pct >= 0 ? 'up' : 'down';
    const ageDays = Math.max(0, Math.round((Date.now() - new Date(`${latest.data_date}T12:00:00Z`).getTime()) / 86400000));
    const ageNote = ageDays <= 1 ? '' : `<br/>Último dado disponível há ${ageDays} dias.`;
    $('price-cards').innerHTML = `
      <div class="card ${dir}"><h3>${esc(latest.commodity.name)} — referência</h3>
        <div class="big">R$ ${fmtBRL(latest.price_brl)}</div>
        <div class="sub">${esc(latest.unit)} · ${latest.variation_pct >= 0 ? '+' : ''}${latest.variation_pct.toFixed(2)}% vs pregão anterior</div></div>
      <div class="card"><h3>Data do dado</h3><div class="big" style="font-size:18px">${esc(latest.data_date)}</div>
        <div class="sub">fonte: ${esc(latest.provider)} · atualizado: ${esc(new Date(latest.retrieved_at).toLocaleString('pt-BR'))}${ageNote}</div></div>
      <div class="card"><h3>Câmbio PTAX (venda)</h3><div class="big">R$ ${fmtBRL(latest.fx_venda)}</div>
        <div class="sub">fonte: ${esc(latest.fx_provider)} · ${series.count} pregões na série</div></div>
      <div class="card"><h3>Contrato</h3><div class="big" style="font-size:18px">${esc(latest.commodity.yahoo_symbol)}</div>
        <div class="sub">nível geográfico: ${esc(latest.geographic_level || 'nacional')} · ${esc(latest.geographic_name || 'Brasil')}</div></div>
      ${latest.fallback_chain && latest.fallback_chain.length ? `<div class="card"><h3>Cobertura territorial</h3><div class="sub">${esc(latest.note || '')}</div></div>` : ''}`;
  }

  function renderHistory(series) {
    $('hist-sub').textContent = `· ${series.data_start} → ${series.data_end} · ${series.points.length} pontos`;
    const tail = series.points.slice(-180);
    destroyChart('chart-history');
    state.charts['chart-history'] = new Chart($('chart-history'), {
      type: 'line',
      data: {
        labels: tail.map((p) => p.date),
        datasets: [{ label: `Preço (${series.unit})`, data: tail.map((p) => p.price_brl), borderWidth: 2, pointRadius: 0, tension: 0.15 }],
      },
      options: { responsive: true, plugins: { legend: { display: true } }, scales: { x: { ticks: { maxTicksLimit: 8 } } } },
    });
  }

  function renderForecast(fc) {
    $('fc-sub').textContent = `· ${fc.model} (λ=${fc.lambda}) · tendência: ${fc.trend}`;
    const hist = fc.history_tail.slice(-30);
    destroyChart('chart-forecast');
    state.charts['chart-forecast'] = new Chart($('chart-forecast'), {
      type: 'line',
      data: {
        labels: [...hist.map((p) => p.date), ...fc.forecast.map((p) => p.date)],
        datasets: [
          { label: 'Histórico', data: [...hist.map((p) => p.price_brl), ...fc.forecast.map(() => null)], borderWidth: 2, pointRadius: 0 },
          { label: 'Previsão', data: [...hist.map(() => null), ...fc.forecast.map((p) => p.price_brl)], borderWidth: 2, pointRadius: 0, borderDash: [6, 4] },
          { label: 'Intervalo sup.', data: [...hist.map(() => null), ...fc.forecast.map((p) => p.upper_brl)], borderWidth: 1, pointRadius: 0, borderDash: [2, 3] },
          { label: 'Intervalo inf.', data: [...hist.map(() => null), ...fc.forecast.map((p) => p.lower_brl)], borderWidth: 1, pointRadius: 0, borderDash: [2, 3] },
        ],
      },
      options: { responsive: true, scales: { x: { ticks: { maxTicksLimit: 8 } } } },
    });
    const last = fc.forecast[fc.forecast.length - 1];
    $('forecast-meta').innerHTML =
      `Atual: R$ ${fmtBRL(fc.current_price_brl)} → ${fc.horizon_days}d: <strong>R$ ${fmtBRL(last.price_brl)}</strong> ` +
      `(faixa R$ ${fmtBRL(last.lower_brl)} – R$ ${fmtBRL(last.upper_brl)}) · modelo vencedor: <strong>${esc(fc.model_selected)}</strong>` +
      `<br/><span>A faixa indica a incerteza do modelo (95%), não uma garantia: o preço real pode ficar fora dela, sobretudo em choques de mercado.</span>`;
  }

  function renderMetrics(fc) {
    const row = (name, m) => `<tr><td>${name}</td><td>${m.mae}</td><td>${m.rmse}</td><td>${m.mape_pct}%</td><td>${m.n}</td></tr>`;
    $('metrics-table').innerHTML = `
      <table class="data"><thead><tr><th>Modelo / segmento</th><th>MAE</th><th>RMSE</th><th>MAPE</th><th>n</th></tr></thead>
      <tbody>
        ${row('Ridge — treino', fc.metrics.train)}
        ${row('Ridge — validação', fc.metrics.val)}
        ${row('Ridge — teste', fc.metrics.test)}
        ${row('Baseline naive (val)', fc.baselines.naive)}
        ${row('Baseline sazonal-5 (val)', fc.baselines.seasonal_naive_5)}
        ${row('Baseline MM7 (val)', fc.baselines.ma7)}
      </tbody></table>
      <p class="meta">Seleção pelo menor RMSE de validação. Teste nunca usado no treino.</p>`;
  }

  function renderWeather(wx) {
    $('wx-sub').textContent = `· ${state.place || ''} · Open-Meteo`;
    const days = wx.daily.slice(0, 7);
    $('wx-cards').innerHTML = days
      .map(
        (d) => `<div class="card"><h3>${d.date.slice(5)}</h3>
          <div class="big" style="font-size:18px">${d.t_max != null ? d.t_max.toFixed(1) + '° / ' + d.t_min.toFixed(1) + '°' : '—'}</div>
          <div class="sub">chuva: ${d.precipitation != null ? d.precipitation.toFixed(1) + ' mm' : '—'}</div></div>`
      )
      .join('');
    destroyChart('chart-climate');
    state.charts['chart-climate'] = new Chart($('chart-climate'), {
      type: 'bar',
      data: {
        labels: days.map((d) => d.date.slice(5)),
        datasets: [
          { label: 'Temp. máx (°C)', data: days.map((d) => d.t_max), type: 'line', borderWidth: 2, pointRadius: 2 },
          { label: 'Chuva (mm)', data: days.map((d) => d.precipitation) },
        ],
      },
      options: { responsive: true },
    });
  }

  async function renderCompare() {
    const rows = [];
    for (const c of state.commodities) {
      try {
        const l = await Api().latest(c.key);
        rows.push(l);
      } catch {
        rows.push({ commodity: c, price_brl: null });
      }
    }
    $('compare-table').innerHTML = `
      <table class="data"><thead><tr><th>Commodity</th><th>Preço ref.</th><th>Unidade</th><th>Variação</th><th>Data</th></tr></thead>
      <tbody>${rows
        .map((r) => `<tr><td>${esc(r.commodity.name)}</td><td>${r.price_brl != null ? 'R$ ' + fmtBRL(r.price_brl) : 'indisponível'}</td><td>${esc(r.unit || '—')}</td><td>${r.variation_pct != null ? r.variation_pct.toFixed(2) + '%' : '—'}</td><td>${esc(r.data_date || '—')}</td></tr>`)
        .join('')}</tbody></table>`;
    // Variação % é adimensional: comparável entre contratos com unidades distintas.
    const withVar = rows.filter((r) => r.variation_pct != null);
    destroyChart('chart-compare');
    state.charts['chart-compare'] = new Chart($('chart-compare'), {
      type: 'bar',
      data: {
        labels: withVar.map((r) => r.commodity.name),
        datasets: [{
          label: 'Variação no pregão (%)',
          data: withVar.map((r) => r.variation_pct),
          backgroundColor: withVar.map((r) => (r.variation_pct >= 0 ? '#2c5f3a' : '#a63a2e')),
        }],
      },
      options: { responsive: true, plugins: { legend: { display: false } } },
    });
  }

  // ---------------- mapa ----------------
  function initMap() {
    if (state.map) {
      state.map.invalidateSize();
      return;
    }
    const map = L.map('map').setView([-14.2, -51.9], 4);
    const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    });
    const sat = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 19, attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics' }
    );
    const lulc = L.tileLayer('/api/landcover/tile/{z}/{x}/{y}.png', {
      maxZoom: 14,
      attribution: 'Cobertura: Esri, Impact Observatory (Sentinel-2 10m)',
    });
    osm.addTo(map);
    state.mapLayers = { osm, sat, lulc };
    state.map = map;

    const setBase = (name) => {
      ['osm', 'sat', 'lulc'].forEach((k) => {
        if (k === name) state.mapLayers[k].addTo(map);
        else if (map.hasLayer(state.mapLayers[k])) map.removeLayer(state.mapLayers[k]);
      });
      $('btn-layer-osm').classList.toggle('active', name === 'osm');
      $('btn-layer-sat').classList.toggle('active', name === 'sat');
      $('btn-layer-lulc').classList.toggle('active', name === 'lulc');
      $('lulc-legend').classList.toggle('hidden', name !== 'lulc');
    };
    $('btn-layer-osm').addEventListener('click', () => setBase('osm'));
    $('btn-layer-sat').addEventListener('click', () => setBase('sat'));
    $('btn-layer-lulc').addEventListener('click', async () => {
      setBase('lulc');
      if (!$('lulc-legend').dataset.loaded) {
        try {
          const info = await Api().landcoverInfo();
          const short = ['Crops', 'Rangeland', 'Trees', 'Water'];
          const SW_CLASS = { 1: 'sw-water', 2: 'sw-trees', 4: 'sw-flooded', 5: 'sw-crops', 7: 'sw-built', 8: 'sw-bare', 9: 'sw-snow', 10: 'sw-clouds' };
          const swatch = (c) => c.color && SW_CLASS[c.value]
            ? `<i class="sw ${SW_CLASS[c.value]}" aria-hidden="true"></i>`
            : `<i class="sw none" title="Cor não amostrada nos mosaicos verificados" aria-hidden="true"></i>`;
          const chips = (list) => list.map((n) => {
            const c = info.classes.find((k) => k.name === n);
            return c ? `<span>${swatch(c)}${esc(c.name)} — ${esc(c.description.split('.')[0])}.</span>` : '';
          }).join('');
          const rest = info.classes.filter((c) => !short.includes(c.name))
            .map((c) => `<span>${swatch(c)}${esc(c.name)} — ${esc(c.description.split('.')[0])}.</span>`).join('');
          $('lulc-legend').innerHTML =
            `<span><strong>Cobertura do solo (mosaico anual ${info.years[info.years.length - 1]})</strong> ` +
            `<button class="linklike" id="lulc-more" type="button" aria-expanded="false">ver legenda completa</button></span>` +
            `<span class="lulc-short">${chips(short)}</span>` +
            `<span class="lulc-rest hidden">${rest}</span>` +
            `<span class="meta">Atribuição: ${esc(info.attribution)}. Sem consulta por ponto/estatística (ver Fontes).</span>`;
          $('lulc-legend').dataset.loaded = '1';
          $('lulc-more').addEventListener('click', () => {
            const r = $('lulc-legend').querySelector('.lulc-rest');
            const open = r.classList.toggle('hidden');
            $('lulc-more').textContent = open ? 'ver legenda completa' : 'ocultar';
            $('lulc-more').setAttribute('aria-expanded', open ? 'false' : 'true');
          });
        } catch (err) {
          $('lulc-legend').innerHTML = `<span>Falha ao carregar legenda: ${esc(err.message)}</span>`;
        }
      }
    });
    map.on('click', (e) => onMapClick(e.latlng.lat, e.latlng.lng));
  }

  async function onMapClick(lat, lon) {
    state.lat = Number(lat.toFixed(4));
    state.lon = Number(lon.toFixed(4));
    state.place = 'ponto do mapa';
    state.locApplied = $('inp-location').value;
    $('coord-label').textContent = `${state.lat.toFixed(4)}, ${state.lon.toFixed(4)}`;
    $('place-label').textContent = '— ponto do mapa';
    setStatus('map-status', 'loading', 'Consultando preço + clima do ponto…');
    $('map-result').classList.add('hidden');
    try {
      const [latest, wx] = await Promise.all([Api().latest(state.commodity), Api().weather(state.lat, state.lon)]);
      if (state.mapMarker) state.mapMarker.remove();
      state.mapMarker = L.marker([state.lat, state.lon])
        .addTo(state.map)
        .bindPopup(
          `<strong>${esc(latest.commodity.name)}</strong>: R$ ${fmtBRL(latest.price_brl)} ${esc(latest.unit)}<br/>` +
            `Clima agora: ${wx.current.temperature_2m}°C, umidade ${wx.current.relative_humidity_2m}%`
        )
        .openPopup();
      const today = wx.daily[0];
      $('map-result').innerHTML = `
        <h2>Ponto ${state.lat.toFixed(4)}, ${state.lon.toFixed(4)}</h2>
        <p><strong>${esc(latest.commodity.name)}</strong> (ref. internacional): R$ ${fmtBRL(latest.price_brl)} ${esc(latest.unit)} em ${esc(latest.data_date)} · PTAX R$ ${fmtBRL(latest.fx_venda)}.</p>
        <p>Clima hoje: máx ${today.t_max}°C / mín ${today.t_min}°C · chuva ${today.precipitation} mm · vento máx ${today.wind_max} km/h.</p>
        <p class="meta">Fontes: ${esc(latest.provider)} + ${esc(latest.fx_provider)} · clima Open-Meteo · ${esc(new Date(latest.retrieved_at).toLocaleString('pt-BR'))}</p>`;
      $('map-result').classList.remove('hidden');
      setStatus('map-status', 'ok', 'Dados do ponto carregados (mesma fonte do dashboard).');
    } catch (err) {
      setStatus('map-status', 'error', `Falha no ponto: ${err.message}`);
    }
  }

  // ---------------- locais salvos ----------------
  let placesBound = false;

  function initPlaces() {
    if (!placesBound) {
      placesBound = true;
      $('btn-place-save').addEventListener('click', async () => {
        setStatus('places-status', 'loading', 'Salvando local…');
        try {
          const label = $('inp-place-label').value.trim() || `${state.place || 'Ponto'} (${state.lat.toFixed(2)}, ${state.lon.toFixed(2)})`;
          await Api().placeCreate({ label, latitude: state.lat, longitude: state.lon });
          $('inp-place-label').value = '';
          setStatus('places-status', 'ok', 'Local salvo.');
          await loadPlaces();
        } catch (err) {
          setStatus('places-status', 'error', err.message);
        }
      });
    }
    loadPlaces();
  }

  async function loadPlaces() {
    try {
      const { places } = await Api().places();
      $('places-list').innerHTML = places.length
        ? `<table class="data"><thead><tr><th>Rótulo</th><th>Coordenadas</th><th>Ações</th></tr></thead><tbody>${places
            .map(
              (p) =>
                `<tr><td>${esc(p.label)}</td><td>${p.latitude.toFixed(4)}, ${p.longitude.toFixed(4)}</td>` +
                `<td><button class="btn" data-place-go="${p.id}" type="button">Usar</button> ` +
                `<button class="btn" data-place-del="${p.id}" type="button">Excluir</button></td></tr>`
            )
            .join('')}</tbody></table>`
        : '<p class="meta">Nenhum local salvo. Clique no mapa e salve o ponto atual.</p>';
      // Guarda coordenadas para o "Usar" sem nova busca.
      loadPlaces._cache = Object.fromEntries(places.map((p) => [p.id, p]));
    } catch (err) {
      $('places-list').innerHTML = `<p class="status error">Falha: ${esc(err.message)}</p>`;
    }
  }

  document.addEventListener('click', (e) => {
    const g = e.target.closest('[data-place-go]');
    if (g) {
      const p = (loadPlaces._cache || {})[g.getAttribute('data-place-go')];
      if (!p) return;
      state.lat = p.latitude;
      state.lon = p.longitude;
      state.place = p.label;
      state.locApplied = $('inp-location').value;
      $('inp-location').value = p.label;
      state.locApplied = p.label;
      $('coord-label').textContent = `${state.lat.toFixed(4)}, ${state.lon.toFixed(4)}`;
      $('place-label').textContent = `— ${state.place}`;
      syncMapMarker();
      setStatus('map-status', 'ok', `Local "${p.label}" aplicado. Use Consultar no topo para atualizar o dashboard.`);
      return;
    }
    const d = e.target.closest('[data-place-del]');
    if (d) {
      Api()
        .placeDelete(d.getAttribute('data-place-del'))
        .then(() => {
          loadPlaces();
          setStatus('places-status', 'ok', 'Local excluído.');
        })
        .catch((err) => setStatus('places-status', 'error', err.message));
    }
  });

  // ---------------- relatório ----------------
  function bindReport() {
    $('btn-report').addEventListener('click', async () => {
      setStatus('report-status', 'loading', 'Gerando relatório…');
      try {
        const rep = await Api().report(state.commodity, { lat: state.lat, lon: state.lon, horizon: state.horizon });
        rep.placeLabel = state.place || null;
        renderReport(rep);
        setStatus('report-status', 'ok', 'Relatório gerado e arquivado.');
      } catch (err) {
        setStatus('report-status', 'error', `Falha: ${err.message}`);
      }
    });
    $('btn-csv').addEventListener('click', () => {
      const token = Api().getToken();
      const a = document.createElement('a');
      a.href = `/api/reports/${state.commodity}/csv?horizon=${state.horizon}&lat=${state.lat}&lon=${state.lon}`;
      a.download = `saden-${state.commodity}-relatorio.csv`;
      // CSV exige auth: abre com fetch + blob para enviar o Bearer.
      fetch(a.href, { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.blob();
        })
        .then((b) => {
          const url = URL.createObjectURL(b);
          a.href = url;
          a.click();
          setTimeout(() => URL.revokeObjectURL(url), 5000);
        })
        .catch((err) => setStatus('report-status', 'error', `Falha no CSV: ${err.message}`));
    });
    $('btn-print').addEventListener('click', () => window.print());
  }

  function renderReport(rep) {
    const fcPts = rep.forecast.points.map((p) => `<tr><td>${p.date}</td><td>R$ ${fmtBRL(p.price_brl)}</td><td>R$ ${fmtBRL(p.lower_brl)} – R$ ${fmtBRL(p.upper_brl)}</td></tr>`).join('');
    const hist = rep.history_tail.slice(-15).map((p) => `<tr><td>${p.date}</td><td>R$ ${fmtBRL(p.price_brl)}</td><td>PTAX R$ ${fmtBRL(p.fx_venda)}</td></tr>`).join('');
    $('report-body').innerHTML = `
      <h1>SADEN — Relatório de ${esc(rep.commodity.name)}${rep.placeLabel ? ` — ${esc(rep.placeLabel)}` : ''}</h1>
      <p class="meta">Gerado em ${esc(new Date(rep.generated_at).toLocaleString('pt-BR'))} · unidade ${esc(rep.unit)}</p>
      <h2>Preço de referência atual</h2>
      <p><strong>R$ ${fmtBRL(rep.price.current_brl)} ${esc(rep.unit)}</strong> (dado de ${esc(rep.price.data_end)}; série desde ${esc(rep.price.data_start)}). Fontes: ${esc(rep.price.provider)} + ${esc(rep.price.fx_provider)} (PTAX venda R$ ${fmtBRL(rep.price.fx_last)}).</p>
      <h2>Histórico recente (15 últimos pregões)</h2>
      <table class="data"><thead><tr><th>Data</th><th>Preço</th><th>Câmbio</th></tr></thead><tbody>${hist}</tbody></table>
      <h2>Previsão — ${esc(rep.forecast.model)} (tendência: ${esc(rep.forecast.trend)})</h2>
      <p class="meta">Teste: MAE ${rep.forecast.metrics.test.mae} · RMSE ${rep.forecast.metrics.test.rmse} · MAPE ${rep.forecast.metrics.test.mape_pct}% · vencedor: ${esc(rep.forecast.model_selected)}</p>
      <table class="data"><thead><tr><th>Data</th><th>Previsão</th><th>Intervalo 95%</th></tr></thead><tbody>${fcPts}</tbody></table>
      ${rep.weather ? `<h2>Clima — ${rep.weather.latitude.toFixed(2)}, ${rep.weather.longitude.toFixed(2)}</h2><p>Agora: ${rep.weather.current.temperature_2m}°C, umidade ${rep.weather.current.relative_humidity_2m}%, chuva ${rep.weather.current.precipitation} mm. Amanhã: máx ${rep.weather.daily[1].t_max}°C, chuva ${rep.weather.daily[1].precipitation} mm.</p>` : '<h2>Clima</h2><p>Sem coordenadas selecionadas.</p>'}
      <h2>Limitações</h2><ul>${rep.forecast.limitations.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>
      <h2>Fontes</h2><ul>${rep.sources.map((s) => `<li><strong>${esc(s.name)}</strong> (${esc(s.status)}) — <span>${esc(s.base_url)}</span></li>`).join('')}</ul>`;
  }

  // ---------------- alertas ----------------
  let alertsBound = false;

  function initAlerts() {
    if (!alertsBound) {
      alertsBound = true;
      $('al-commodity').innerHTML = state.commodities
        .map((c) => `<option value="${esc(c.key)}">${esc(c.name)}</option>`)
        .join('');
      $('btn-al-create').addEventListener('click', async () => {
        setStatus('al-form-status', 'loading', 'Criando alerta…');
        try {
          const kind = $('al-kind').value;
          const body = {
            commodity_key: $('al-commodity').value,
            kind,
            threshold: Number($('al-threshold').value),
            label: $('al-label').value.trim() || null,
          };
          if (kind === 'rain_above') {
            body.latitude = state.lat;
            body.longitude = state.lon;
          }
          await Api().alertCreate(body);
          setStatus('al-form-status', 'ok', 'Alerta criado.');
          $('al-threshold').value = '';
          $('al-label').value = '';
          await loadAlerts();
        } catch (err) {
          setStatus('al-form-status', 'error', err.message);
        }
      });
      $('btn-al-check').addEventListener('click', async () => {
        setStatus('al-status', 'loading', 'Avaliando alertas ativos…');
        try {
          const res = await Api().alertCheck();
          const rows = res.results
            .map(
              (r) =>
                `<tr><td>${esc(r.alert.label || r.alert.kind_label)}</td><td>${esc(r.alert.commodity_key)}</td>` +
                `<td>${r.triggered ? '<strong>DISPARADO</strong>' : 'não'}</td><td>${r.value != null ? r.value : '—'}</td><td>${esc(r.detail || '')}</td></tr>`
            )
            .join('');
          $('al-events').innerHTML = res.results.length
            ? `<table class="data"><thead><tr><th>Alerta</th><th>Commodity</th><th>Estado</th><th>Valor</th><th>Detalhe</th></tr></thead><tbody>${rows}</tbody></table>`
            : '<p class="meta">Nenhum alerta ativo para avaliar.</p>';
          setStatus('al-status', 'ok', `${res.evaluated} alerta(s) avaliado(s) em ${new Date(res.evaluated_at).toLocaleString('pt-BR')}.`);
          await loadAlerts();
        } catch (err) {
          setStatus('al-status', 'error', err.message);
        }
      });
    }
    $('al-coords-note').textContent =
      `Alertas de chuva usam a localidade atual: ${state.place || ''} (${state.lat.toFixed(4)}, ${state.lon.toFixed(4)}). ` +
      `Ajuste a localidade no Dashboard antes de criar.`;
    loadAlerts();
  }

  async function loadAlerts() {
    try {
      const { alerts } = await Api().alerts();
      $('al-list').innerHTML = alerts.length
        ? `<table class="data"><thead><tr><th>Rótulo</th><th>Commodity</th><th>Condição</th><th>Limite</th><th>Ativo</th><th>Ações</th></tr></thead><tbody>${alerts
            .map(
              (a) =>
                `<tr><td>${esc(a.label || '—')}</td><td>${esc(a.commodity_key)}</td><td>${esc(a.kind_label)}</td>` +
                `<td>${a.threshold}</td><td>${a.active ? 'sim' : 'não'}</td>` +
                `<td><button class="btn" data-al-toggle="${a.id}" data-active="${a.active ? 0 : 1}" type="button">${a.active ? 'Desativar' : 'Ativar'}</button> ` +
                `<button class="btn" data-al-del="${a.id}" type="button">Excluir</button></td></tr>`
            )
            .join('')}</tbody></table>`
        : '<p class="meta">Nenhum alerta criado.</p>';
    } catch (err) {
      $('al-list').innerHTML = `<p class="status error">Falha: ${esc(err.message)}</p>`;
    }
  }

  document.addEventListener('click', (e) => {
    const t = e.target.closest('[data-al-toggle]');
    if (t) {
      Api()
        .alertToggle(t.getAttribute('data-al-toggle'), t.getAttribute('data-active') === '1')
        .then(() => {
          loadAlerts();
          setStatus('al-status', 'ok', 'Alerta atualizado.');
        })
        .catch((err) => setStatus('al-status', 'error', err.message));
      return;
    }
    const d = e.target.closest('[data-al-del]');
    if (d) {
      Api()
        .alertDelete(d.getAttribute('data-al-del'))
        .then(() => {
          loadAlerts();
          setStatus('al-status', 'ok', 'Alerta excluído.');
        })
        .catch((err) => setStatus('al-status', 'error', err.message));
    }
  });

  // ---------------- fontes ----------------
  async function loadSources() {    try {
      const { sources } = await Api().sources();
      $('sources-table').innerHTML = `
        <table class="data"><thead><tr><th>Fonte</th><th>Tipo</th><th>Status</th><th>URL</th></tr></thead>
        <tbody>${sources.map((s) => `<tr><td>${esc(s.name)}</td><td>${esc(s.kind)}</td><td>${esc(s.status)}</td><td><span>${esc(s.base_url)}</span></td></tr>`).join('')}</tbody></table>`;
    } catch (err) {
      $('sources-table').textContent = `Falha: ${err.message}`;
    }
  }

  async function init() {
    if (state.inited) {
      await refresh();
      return;
    }
    state.inited = true;
    bindNav();
    bindReport();
    bindTheme();
    applyChartTheme();
    try {
      await loadFilters();
      await refresh();
    } catch (err) {
      setStatus('dash-status', 'error', `Falha na inicialização: ${err.message}`);
    }
  }

  window.SadenApp = { init, refresh, state };
})();
