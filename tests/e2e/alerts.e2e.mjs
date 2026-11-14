// E2E do fluxo de alertas (Release 2) — sem dependências externas.
//
// Dirige o Chrome real via CDP usando o WebSocket nativo do Node 22. Cobre o
// caminho visível ao usuário: cadastro → alertas → criação → evento → leitura,
// e verifica console limpo e ausência de overflow horizontal em 390 px.
//
// A observação de preço é semeada direto no SQLite (fixture determinística):
// o teste de CI não pode depender de Yahoo/BCB estarem no ar.
//
// Uso:
//   node tests/e2e/alerts.e2e.mjs
// Variáveis:
//   BASE_URL       (default http://127.0.0.1:3100)
//   DATABASE_PATH  (default tmp/e2e-saden.db)
//   CHROME_PATH    (default: Chrome do sistema)
//   HEADLESS=0     para ver a janela

import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:3100';
const DATABASE_PATH = process.env.DATABASE_PATH || path.join(ROOT, 'tmp', 'e2e-saden.db');
const PORT = Number(process.env.CDP_PORT || 9333);
const HEADLESS = process.env.HEADLESS !== '0';

const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  process.env.CHROME_BIN,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
  '/usr/bin/chromium-browser',
  '/usr/bin/chromium',
].filter(Boolean);

function findChrome() {
  for (const candidate of CHROME_CANDIDATES) {
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error('Chrome não encontrado. Defina CHROME_PATH.');
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchJson(url, attempts = 40) {
  let lastError;
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetch(url);
      if (res.ok) return res.json();
    } catch (error) {
      lastError = error;
    }
    await sleep(250);
  }
  throw new Error(`CDP indisponível em ${url}: ${lastError ? lastError.message : 'timeout'}`);
}

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.next = 1;
    this.pending = new Map();
    this.events = [];
    ws.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const { resolve, reject } = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) reject(new Error(message.error.message));
        else resolve(message.result);
      } else if (message.method) {
        this.events.push(message);
      }
    });
  }

  static async connect(url) {
    const ws = new WebSocket(url);
    await new Promise((resolve, reject) => {
      ws.addEventListener('open', resolve, { once: true });
      ws.addEventListener('error', () => reject(new Error('falha ao abrir WebSocket do CDP')), { once: true });
    });
    return new Cdp(ws);
  }

  send(method, params = {}) {
    const id = this.next++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`timeout no comando CDP ${method}`));
        }
      }, 30000);
    });
  }

  async evaluate(expression) {
    const result = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (result.exceptionDetails) {
      throw new Error(`erro na página: ${result.exceptionDetails.text} ${result.exceptionDetails.exception?.description || ''}`);
    }
    return result.result.value;
  }

  async waitFor(expression, { timeoutMs = 15000, label = expression } = {}) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const value = await this.evaluate(expression).catch(() => false);
      if (value) return value;
      await sleep(200);
    }
    throw new Error(`tempo esgotado esperando: ${label}`);
  }

  close() {
    try {
      this.ws.close();
    } catch {
      /* já fechado */
    }
  }
}

function seedObservation(price) {
  const Database = require(path.join(ROOT, 'backend', 'node_modules', 'better-sqlite3'));
  const db = new Database(DATABASE_PATH);
  const date = new Date().toISOString().slice(0, 10);
  db.prepare(
    `INSERT OR REPLACE INTO price_observations(commodity_key, data_date, price_usd, fx_rate, price_brl, unit_br, provider)
     VALUES('cafe', ?, ?, 5.5, ?, 'R$/sc 60kg', 'yahoo')`
  ).run(date, price / 5.5, price);
  db.close();
  return date;
}

async function main() {
  const chrome = findChrome();
  const userDataDir = path.join(ROOT, 'tmp', 'e2e-chrome-' + Date.now());
  fs.mkdirSync(userDataDir, { recursive: true });
  const chromeLog = path.join(ROOT, 'tmp', 'e2e-chrome.log');

  const baseArgs = [
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${userDataDir}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--disable-setuid-sandbox',
    '--no-sandbox',
  ];

  const checks = [];
  const record = (name, ok, detail = '') => {
    checks.push({ name, ok, detail });
    if (!ok) throw new Error(`FALHOU: ${name} ${detail}`);
  };

  let browser = null;
  let cdp = null;
  try {
    // Sobe o navegador com retry: o primeiro headless pode não expor CDP em
    // tempo (runner frio); a segunda tentativa usa o modo headless legado.
    for (const headlessFlag of HEADLESS ? ['--headless=new', '--headless'] : [null]) {
      const args = [...baseArgs];
      if (headlessFlag) args.push(headlessFlag);
      args.push('about:blank');
      const out = fs.openSync(chromeLog, 'a');
      browser = spawn(chrome, args, { stdio: ['ignore', out, out] });
      try {
        await fetchJson(`http://127.0.0.1:${PORT}/json/version`, 120);
        break;
      } catch (error) {
        browser.kill();
        browser = null;
        const tail = fs.existsSync(chromeLog) ? fs.readFileSync(chromeLog, 'utf8').slice(-400) : '';
        if (headlessFlag === (HEADLESS ? '--headless' : null)) {
          throw new Error(`${error.message} | chrome: ${tail.replace(/\n/g, ' ')}`);
        }
      }
    }
    if (!browser) throw new Error('não foi possível iniciar o Chrome com CDP');

    const target = await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: 'PUT' }).then((r) => r.json());
    cdp = await Cdp.connect(target.webSocketDebuggerUrl);
    await cdp.send('Runtime.enable');
    await cdp.send('Page.enable');
    await cdp.send('Log.enable');

    const email = `e2e-${Date.now()}@saden.local`;
    await cdp.send('Page.navigate', { url: `${BASE_URL}/register` });
    await cdp.waitFor("!!document.getElementById('reg-email')", { label: 'formulário de cadastro' });

    await cdp.evaluate(`
      (() => {
        const set = (id, value) => {
          const el = document.getElementById(id);
          el.value = value;
          el.dispatchEvent(new Event('input', { bubbles: true }));
        };
        set('reg-name', 'Teste E2E');
        set('reg-email', ${JSON.stringify(email)});
        set('reg-password', 'senha123456');
        document.getElementById('form-register').requestSubmit();
        return true;
      })()
    `);
    await cdp.waitFor(
      "(() => { const app = document.getElementById('view-app'); return app && !app.classList.contains('hidden') && document.getElementById('sel-commodity') && document.getElementById('sel-commodity').options.length > 0; })()",
      { timeoutMs: 30000, label: 'app autenticado com filtros carregados' }
    );
    record('cadastro e login', true);

    // Semeia a observação e avalia pelo mesmo motor que o worker usa.
    const observationDate = seedObservation(200);
    await cdp.evaluate("document.querySelector('[data-nav=\"alertas\"]').click()");
    await cdp.waitFor(
      "(() => { const page = document.getElementById('page-alertas'); return page && !page.classList.contains('hidden') && document.getElementById('al-series') && document.getElementById('al-series').options.length >= 5; })()",
      { timeoutMs: 20000, label: 'catálogo de séries carregado' }
    );
    record('catálogo de séries', true, '5 séries');

    await cdp.evaluate(`
      (() => {
        window.confirm = () => true;
        const select = document.getElementById('al-series');
        select.value = 'yahoo:KC=F:brl:sc60';
        select.dispatchEvent(new Event('change', { bubbles: true }));
        document.getElementById('al-threshold').value = '150';
        document.getElementById('al-label').value = 'E2E café';
        document.getElementById('btn-al-create').click();
        return true;
      })()
    `);
    await cdp.waitFor("document.querySelectorAll('#al-list tbody tr').length >= 1", { label: 'alerta criado' });
    record('criação de alerta', true);

    const evaluated = await cdp.evaluate(`
      (async () => {
        const token = localStorage.getItem('saden_token');
        const res = await fetch('/api/alerts/evaluate', { method: 'POST', headers: { Authorization: 'Bearer ' + token } });
        return res.status;
      })()
    `);
    record('avaliação pelo motor', evaluated === 200, `status ${evaluated}`);

    await cdp.send('Page.reload');
    await cdp.waitFor(
      "(() => { const app = document.getElementById('view-app'); return app && !app.classList.contains('hidden') && document.getElementById('sel-commodity') && document.getElementById('sel-commodity').options.length > 0; })()",
      { timeoutMs: 30000, label: 'recarga autenticada' }
    );
    await cdp.evaluate("document.querySelector('[data-nav=\"alertas\"]').click()");
    await cdp.waitFor("document.querySelectorAll('#al-events tbody tr').length >= 1", { label: 'evento persistido' });
    const eventText = await cdp.evaluate("document.getElementById('al-events').innerText");
    record('evento persistido aparece após reabrir', /novo/i.test(eventText), eventText.split('\n')[1] || '');

    await cdp.evaluate("document.getElementById('btn-al-read').click()");
    await cdp.waitFor("document.getElementById('al-events').innerText.includes('lido')", { label: 'marcar como lido' });
    record('marcar como lido', true);

    const monitorText = await cdp.evaluate("document.getElementById('al-monitor-text').innerText");
    record('banner de monitoramento presente', /monitoramento/i.test(monitorText), monitorText.slice(0, 60));

    // Responsividade e console.
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 390,
      height: 844,
      deviceScaleFactor: 1,
      mobile: true,
    });
    await sleep(400);
    const overflow = await cdp.evaluate('document.documentElement.scrollWidth > window.innerWidth + 1');
    record('sem overflow horizontal em 390px', overflow === false);

    const consoleErrors = cdp.events
      .filter((event) => event.method === 'Log.entryAdded' && event.params.entry.level === 'error')
      .map((event) => event.params.entry.text)
      .filter((text) => !/favicon|ERR_|tile\.openstreetmap|arcgisonline/i.test(text))
      // CSP de style inline disparado por Chart.js/Leaflet (existe desde a V1.1;
      // registrado em KNOWN_ISSUES, sem impacto funcional observado).
      .filter((text) => !/Content Security Policy/i.test(text))
      // 503 do health do worker é resposta correta quando o worker não está
      // rodando neste ambiente de teste — o banner usa esse dado.
      .filter((text) => !/503 \(Service Unavailable\)/i.test(text));
    record('sem erro de console', consoleErrors.length === 0, consoleErrors.join(' | ').slice(0, 200));

    console.log(JSON.stringify({ ok: true, base: BASE_URL, email, observationDate, checks }, null, 2));
  } finally {
    if (cdp) cdp.close();
    if (browser) browser.kill();
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: error.message }));
  process.exit(1);
});
