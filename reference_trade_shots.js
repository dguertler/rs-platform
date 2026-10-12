#!/usr/bin/env node
/**
 * Bilder der Referenz-Trades (data/reference_trades.json) vorher / nachher — B-DETAILS mit
 * Legende, Weekly, Daily und 4H in der Woche des Signals. Pflicht, sobald eine Logik-Änderung
 * einen Referenz-Trade verändert (siehe CLAUDE.md „Referenz-Trades“).
 *
 *   vorher  = Logik frontend/*.js aus dem letzten Commit (git HEAD)
 *   nachher = frontend/*.js aus dem Arbeitsverzeichnis (die ungesicherte Änderung)
 *
 * Je Referenz-Trade entsteht ein Bild mit zwei Zeilen (mit Earnings-Regel = System, ohne =
 * Gegenprobe) und zwei Spalten (vorher | nachher):
 *   out/reference_trades/<ID>.png
 *
 * Aufruf: node reference_trade_shots.js [ID …] [--out DIR] [--w YYYY-MM-DD]
 *   --w: andere Woche zeigen (z. B. die, in der die Abweichung beginnt); Standard: Signaltag
 *
 * Braucht Chromium (Cloud-Sessions: /opt/pw-browsers); Playwright, React und Babel werden bei
 * Bedarf aus npm nach $TMPDIR/refshot-deps geladen.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const { execFileSync } = require('child_process');

const ROOT = __dirname;
const args = process.argv.slice(2);
const opt = (name) => { const i = args.indexOf(name); return i >= 0 ? args.splice(i, 2)[1] : null; };
const OUT = path.resolve(opt('--out') || path.join(ROOT, 'out', 'reference_trades'));
const WEEK = opt('--w');
const ids = args.filter(a => !a.startsWith('--'));

const DEPS = path.join(os.tmpdir(), 'refshot-deps');
const CDN_FILES = {
  'react.production.min.js': 'react/umd/react.production.min.js',
  'react-dom.production.min.js': 'react-dom/umd/react-dom.production.min.js',
  'babel.min.js': '@babel/standalone/babel.min.js',
};

function requirePlaywright() {
  for (const p of [ROOT, DEPS]) {
    try { return require(require.resolve('playwright', { paths: [p] })); } catch { /* weiter */ }
  }
  ensureDeps();
  return require(require.resolve('playwright', { paths: [DEPS] }));
}

function ensureDeps() {
  if (fs.existsSync(path.join(DEPS, 'node_modules', '@babel', 'standalone'))
      && fs.existsSync(path.join(DEPS, 'node_modules', 'playwright'))) return;
  fs.mkdirSync(DEPS, { recursive: true });
  execFileSync('npm', ['i', '--silent', '--prefix', DEPS, 'playwright@1.47.2', 'react@18.2.0',
    'react-dom@18.2.0', '@babel/standalone@7.23.2'], { stdio: 'inherit',
    env: { ...process.env, PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD: '1' } });
}

function chromiumPath() {
  const base = '/opt/pw-browsers';
  if (!fs.existsSync(base)) return undefined;
  for (const d of fs.readdirSync(base).filter(d => d.startsWith('chromium_headless_shell'))) {
    for (const sub of fs.readdirSync(path.join(base, d))) {
      const p = path.join(base, d, sub, 'headless_shell');
      if (fs.existsSync(p)) return p;
    }
  }
  return undefined;
}

// Datei für eine Fassung: vorher = git HEAD (nur die Logik frontend/*.js), nachher =
// Arbeitsverzeichnis; die Seite selbst (HTML) immer aus dem Arbeitsverzeichnis
function readVersion(rel, version) {
  if (version === 'vorher' && rel.startsWith('frontend/') && rel.endsWith('.js')) {
    try { return execFileSync('git', ['show', `HEAD:${rel}`], { cwd: ROOT, maxBuffer: 1 << 28 }); }
    catch { /* neue Datei → Arbeitsverzeichnis */ }
  }
  return fs.readFileSync(path.join(ROOT, rel));
}

const TYPES = { '.html': 'text/html', '.js': 'application/javascript', '.json': 'application/json',
  '.png': 'image/png', '.css': 'text/css' };

function serve() {
  // /<version>/frontend/... ; data/ liegt neben frontend/ (wie auf der Seite: frontend/data → data)
  const server = http.createServer((req, res) => {
    const [, version, ...rest] = decodeURIComponent(req.url.split('?')[0]).split('/');
    let rel = rest.join('/').replace(/^frontend\/data\//, 'data/');
    if (rel.includes('..')) { res.writeHead(400); return res.end(); }
    if (rel === 'compose.html') { res.writeHead(200, { 'Content-Type': 'text/html' }); return res.end(composeHtml); }
    if (rel.startsWith('shots/')) rel = path.relative(ROOT, path.join(OUT, rel.slice(6)));
    try {
      const body = readVersion(rel, version);
      res.writeHead(200, { 'Content-Type': TYPES[path.extname(rel)] || 'application/octet-stream' });
      res.end(body);
    } catch { res.writeHead(404); res.end(); }
  });
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(server)));
}

let composeHtml = '';

async function shoot(browser, port, version, ref, withEarnings, file) {
  const page = await browser.newPage({ viewport: { width: 1500, height: 2200 } });
  // React/Babel immer aus npm (gleiche Versionen wie auf der Seite) — das CDN ist in
  // Cloud-Sessions gesperrt und macht die Bilder sonst vom Netz abhängig
  await page.route(/cdnjs\.cloudflare\.com/, route => route.fulfill({
    path: path.join(DEPS, 'node_modules', CDN_FILES[route.request().url().split('/').pop()]),
    contentType: 'application/javascript' }));
  const week = WEEK || ref.entry.date;
  const url = `http://127.0.0.1:${port}/${version}/frontend/backtest.html?t=${ref.ticker}&w=${week}${withEarnings ? '' : '&er=0'}`;
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('requestfailed', r => errors.push(`${r.url()}: ${r.failure()?.errorText}`));
  await page.goto(url);
  try {
    await page.waitForSelector('.desktop-right svg', { timeout: 180000 });
  } catch (e) {
    await page.screenshot({ path: file.replace(/\.png$/, '_fehler.png') });
    throw new Error(`${url}: Charts nicht geladen (${errors.slice(0, 3).join(' | ') || e.message})`);
  }
  await page.waitForTimeout(1500);
  await page.locator('.desktop-right').screenshot({ path: file });
  await page.close();
}

async function main() {
  const refs = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'reference_trades.json'))).trades
    .filter(r => !ids.length || ids.includes(r.id));
  if (!refs.length) throw new Error('kein Referenz-Trade gefunden');
  fs.mkdirSync(OUT, { recursive: true });
  ensureDeps();
  const { chromium } = requirePlaywright();
  const browser = await chromium.launch({ executablePath: chromiumPath() });
  const server = await serve();
  const port = server.address().port;
  for (const ref of refs) {
    const cells = [];
    for (const withEarnings of [true, false]) {
      for (const version of ['vorher', 'nachher']) {
        const name = `${ref.id}_${version}_${withEarnings ? 'mit' : 'ohne'}_earnings.png`;
        await shoot(browser, port, version, ref, withEarnings, path.join(OUT, name));
        cells.push({ name, version, withEarnings });
      }
    }
    const head = (c) => `${c.version === 'vorher' ? 'VORHER (letzter Commit)' : 'NACHHER (Änderung)'} · `
      + `${c.withEarnings ? 'mit Earnings-Regel (System)' : 'ohne Earnings-Regel (Gegenprobe)'}`;
    composeHtml = `<!doctype html><meta charset="utf-8"><body style="margin:0;background:#020617;color:#e2e8f0;font:14px monospace">
      <div style="padding:10px 14px;font-size:18px;font-weight:700">Referenz-Trade ${ref.id} — Signal ${ref.entry.signal_bar},
        Kauf ${ref.entry.date} ${ref.entry.time}, Verkauf ${ref.exit.signal_date}${ref.exit_without_earnings ? ` (ohne Earnings-Regel ${ref.exit_without_earnings.signal_date})` : ''}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 10px 10px">
      ${cells.map(c => `<div><div style="padding:4px 2px;color:${c.version === 'vorher' ? '#94a3b8' : '#fbbf24'}">${head(c)}</div>
        <img src="/x/shots/${c.name}" style="width:100%;display:block;border:1px solid #1e293b"></div>`).join('')}
      </div></body>`;
    const page = await browser.newPage({ viewport: { width: 2400, height: 1000 } });
    await page.goto(`http://127.0.0.1:${port}/x/compose.html`);
    await page.waitForLoadState('networkidle');
    const file = path.join(OUT, `${ref.id}.png`);
    await page.screenshot({ path: file, fullPage: true });
    await page.close();
    for (const c of cells) fs.unlinkSync(path.join(OUT, c.name));
    console.log(`→ ${path.relative(ROOT, file)}`);
  }
  server.close();
  await browser.close();
}

main().catch(e => { console.error(e.message); process.exit(1); });
