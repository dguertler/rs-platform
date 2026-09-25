#!/usr/bin/env node
/**
 * Historischer NASDAQ-100-Backtest, Schritt 2: Trades simulieren und je Jahr
 * auswerten. Voraussetzung: backtest_history/prepare_data.py hat den Cache
 * unter backtest_history/cache/ gefüllt.
 *
 * Engine: frontend/backtest_logic.js unverändert, nur ohne 4H-Kerzen im
 * Modus 'WD' (Einstieg bei 2 von 2 Punkten W + D). Stopp, täglicher Ausstieg,
 * Top-20-Filter am Einstiegstag, 10.000 € je Signal und 1.000 € Risiko wie live.
 *
 * Zusätzlich der Abgleich W+D gegen 4H auf den vorhandenen Live-Daten
 * (data/rs_full.json + data/backtest_*.json): gleiche Kerzen, gleicher
 * Zeitraum, gleiche Top-20-Historie — einmal mit, einmal ohne 4H-Auslöser.
 *
 * Aufruf:  node backtest_history/run_backtest.js [--calibration-only]
 * Schreibt data/backtest_history/ndx_results.json
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
// Überschreibbar für den Offline-Test (test_backtest_history.py)
const CACHE = process.env.BACKTEST_HISTORY_CACHE || path.join(__dirname, 'cache');
const OUT_FILE = process.env.BACKTEST_HISTORY_OUT || path.join(ROOT, 'data', 'backtest_history', 'ndx_results.json');

const engineCode = fs.readFileSync(path.join(ROOT, 'frontend', 'backtest_logic.js'), 'utf8');
vm.runInThisContext(engineCode + '\n;globalThis.__engine = { buildWeekRows, simulateTrades, CAPITAL, MAX_RISK };');
const { buildWeekRows, simulateTrades, CAPITAL, MAX_RISK } = globalThis.__engine;
const { kpis: kpisFor } = require(path.join(ROOT, 'backtest_kpis'));
const { simulatePortfolio, portfolioStats } = require('./portfolio');
const kpis = (trades) => kpisFor(trades, CAPITAL);

const readJson = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const year = (d) => d.slice(0, 4);

const slim = (t) => ({
  ticker: t.ticker,
  trigger: t.trigger,
  entryDate: t.entryDate,
  exitDate: t.exitDate,
  entryPrice: +t.entryPrice.toFixed(4),
  exitPrice: +t.exitPrice.toFixed(4),
  invested: Math.round(t.invested),
  pnl: Math.round(t.pnl),
  pnlPct: +t.pnlPct.toFixed(1),
  holdingWeeks: t.holdingWeeks,
  isOpen: t.isOpen,
  ...(t.dataEnded ? { dataEnded: true } : {}),
});

/**
 * Kapitalbedarf = höchste Summe des gleichzeitig gebundenen Einsatzes, wenn man
 * alle übergebenen Trades wie simuliert parallel hält (10.000 € je Signal).
 * Am selben Tag wird erst Kapital frei (Ausstieg), dann neu gebunden (Einstieg).
 */
function capitalPeak(trades) {
  const events = [];
  for (const t of trades) {
    events.push([t.entryDate, 1, t.invested]);
    events.push([t.exitDate, 0, -t.invested]);
  }
  events.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1] - b[1]));
  let open = 0, peak = 0;
  for (const [, , amount] of events) {
    open += amount;
    peak = Math.max(peak, open);
  }
  return peak;
}

/** Kennzahlen ohne die Top/Flop-Listen (die stehen in der Trade-Liste). */
function summary(trades) {
  const k = kpis(trades);
  if (!k) return null;
  const { best, worst, ...rest } = k;
  const peak = capitalPeak(trades);
  rest.capitalPeak = peak;
  // Rendite auf das Kapital, das man für alle Trades gleichzeitig gebraucht hätte
  rest.returnOnCapital = peak > 0 ? (k.totalPnl / peak) * 100 : null;
  const byTrigger = {};
  for (const trig of ['D', 'W', '4H']) {
    const sub = trades.filter((t) => t.trigger === trig);
    if (sub.length) {
      const s = kpis(sub);
      byTrigger[trig] = { nTrades: s.nTrades, winrate: s.winrate, profitFactor: s.profitFactor, totalPnl: s.totalPnl };
    }
  }
  return { ...rest, byTrigger };
}

function byYear(trades) {
  const out = {};
  for (const t of trades) (out[year(t.entryDate)] ||= []).push(t);
  return Object.fromEntries(Object.entries(out).sort().map(([y, ts]) => [y, summary(ts)]));
}

/**
 * RS-Rang (1–20) am Einstiegstag. Die Engine prüft zuerst den Einstiegstag,
 * sonst den Wochenstempel — hier ersatzweise die sieben Tage davor.
 */
function rankAt(hist, day, sym) {
  const d = new Date(day + 'T12:00:00Z');
  for (let k = 0; k <= 7; k++) {
    const key = new Date(d - k * 864e5).toISOString().slice(0, 10);
    const pos = hist[key] ? hist[key].indexOf(sym) : -1;
    if (pos >= 0) return pos + 1;
  }
  return 21;
}

// ── Historischer Lauf ─────────────────────────────────────────────────────────
function runHistory() {
  const meta = readJson(path.join(CACHE, 'meta.json'));
  const top20 = {
    inkl: readJson(path.join(CACHE, 'top20_inkl.json')),
    exkl: readJson(path.join(CACHE, 'top20_exkl.json')),
  };
  const everTop = {};
  for (const [variant, hist] of Object.entries(top20)) {
    everTop[variant] = new Set(Object.values(hist).flat());
  }

  const trades = { inkl: [], exkl: [] };
  const closesBySymbol = {};
  const symbols = Object.keys(meta.symbols).sort();
  let done = 0;
  for (const sym of symbols) {
    const info = meta.symbols[sym];
    const needed = Object.keys(trades).filter((v) => everTop[v].has(sym));
    done++;
    if (!needed.length || !info.has_weekly) continue;       // nie in den Top 20 → kein Trade möglich
    const daily = readJson(path.join(CACHE, 'daily', `${sym}.json`));
    const weekly = readJson(path.join(CACHE, 'weekly', `${sym}.json`));
    const rows = buildWeekRows(weekly, daily, []);
    closesBySymbol[sym] = new Map(daily.map((r) => [r.d, r.c]));
    for (const variant of needed) {
      for (const t of simulateTrades(rows, daily, sym, top20[variant], true, 'WD')) {
        // Kursreihe endet vor dem Datenende (Übernahme, Delisting): der Trade ist
        // nicht mehr offen, sondern zum letzten verfügbaren Kurs beendet.
        const dataEnded = t.isOpen && !info.active;
        const rank = rankAt(top20[variant], t.entryDate, sym);
        trades[variant].push({ ...t, ticker: sym, rank, isOpen: t.isOpen && !dataEnded, dataEnded });
      }
    }
    if (done % 25 === 0) console.error(`  ${done}/${symbols.length} Symbole`);
  }

  const variants = {};
  for (const [variant, list] of Object.entries(trades)) {
    list.sort((a, b) => (a.entryDate < b.entryDate ? -1 : 1));
    const negYears = new Set(Object.entries(meta.ndx).filter(([, v]) => v.pct < 0).map(([y]) => y));
    const sim = simulatePortfolio(list, closesBySymbol, { start: meta.membership_start });
    variants[variant] = {
      total: summary(list),
      years: byYear(list),
      ndxDown: summary(list.filter((t) => negYears.has(year(t.entryDate)))),
      ndxUp: summary(list.filter((t) => !negYears.has(year(t.entryDate)))),
      portfolio: portfolioStats(sim, list),
      trades: list.map((t) => {
        const r = sim.results.get(t) || { taken: false };
        return { ...slim(t), rank: t.rank, taken: r.taken,
          ...(r.taken ? { depotInvested: Math.round(r.depotInvested), depotPnl: Math.round(r.depotPnl) } : {}) };
      }),
    };
  }

  const resolution = meta.resolution;
  const count = (status) => Object.values(resolution).filter((r) => r.status === status).length;
  return {
    period: { start: meta.membership_start, end: meta.data_end },
    dataGenerated: meta.generated,
    membershipSource: meta.membership_source,
    ndx: meta.ndx,
    coverage: meta.coverage,
    symbols: {
      total: Object.keys(resolution).length,
      aktiv: count('aktiv'),
      delistedMitDaten: count('delisted_mit_daten'),
      keineDaten: count('keine_daten'),
      withJumps: Object.entries(meta.symbols).filter(([, v]) => v.jumps.length).map(([k, v]) => ({ ticker: k, dates: v.jumps })),
      delistedMitDatenList: Object.entries(resolution).filter(([, r]) => r.status === 'delisted_mit_daten').map(([t, r]) => ({ ticker: t, yahoo: r.yahoo })),
      aliases: Object.entries(resolution).filter(([t, r]) => r.yahoo && r.yahoo !== t).map(([t, r]) => ({ ticker: t, yahoo: r.yahoo })),
    },
    variants,
  };
}

// ── Abgleich W+D gegen 4H auf den Live-Daten ─────────────────────────────────
/** OHLCV-Aufbereitung exakt wie frontend/backtest_overview.html (letzte 104 Wochen). */
function liveSeries(entry) {
  let bt = null;
  try {
    bt = readJson(path.join(ROOT, 'data', `backtest_${entry.ticker.toLowerCase().replace(/[^a-z0-9]/g, '_')}.json`));
  } catch (e) {
    bt = null;
  }
  const full = bt && bt.ohlcv_w && bt.ohlcv_d ? bt : null;
  const rawW = full ? full.ohlcv_w : entry.ohlcv_w || [];
  const rawD = full ? full.ohlcv_d : entry.ohlcv || [];
  const raw4h = full ? full.ohlcv_4h || [] : entry.ohlcv_4h || [];
  if (!rawW.length || !rawD.length) return null;
  const ohlcvW = rawW.slice(-104);
  const cutDate = ohlcvW[0].d;
  return {
    ohlcvW,
    ohlcvD: rawD.filter((d) => d.d >= cutDate),
    ohlcv4h: raw4h.filter((d) => d.d.slice(0, 10) >= cutDate),
  };
}

function runCalibration() {
  const rs = readJson(path.join(ROOT, 'data', 'rs_full.json'));
  const hist = rs.top20_history || {};
  const out = { '4H': [], WD: [] };
  let first4h = null;
  for (const entry of rs.data || []) {
    const s = liveSeries(entry);
    if (!s) continue;
    if (s.ohlcv4h.length && (!first4h || s.ohlcv4h[0].d < first4h)) first4h = s.ohlcv4h[0].d.slice(0, 10);
    const rows4h = buildWeekRows(s.ohlcvW, s.ohlcvD, s.ohlcv4h);
    const rowsWD = buildWeekRows(s.ohlcvW, s.ohlcvD, []);
    for (const t of simulateTrades(rows4h, s.ohlcvD, entry.ticker, hist, true)) out['4H'].push({ ...t, ticker: entry.ticker });
    for (const t of simulateTrades(rowsWD, s.ohlcvD, entry.ticker, hist, true, 'WD')) out.WD.push({ ...t, ticker: entry.ticker });
  }
  // Gleiches Fenster für beide: ab dem ersten Tag, an dem 4H-Kerzen vorliegen
  const start = first4h || Object.keys(hist).sort()[0];
  const result = { start, end: (rs.benchmark_ohlcv || []).slice(-1)[0]?.d ?? null, modes: {} };
  for (const [mode, list] of Object.entries(out)) {
    const inWindow = list.filter((t) => t.entryDate >= start);
    result.modes[mode] = { total: summary(inWindow), years: byYear(inWindow) };
  }
  return result;
}

function main() {
  const calibrationOnly = process.argv.includes('--calibration-only');
  let previous = {};
  try {
    previous = readJson(OUT_FILE);
  } catch (e) {
    previous = {};
  }
  const result = {
    ...previous,
    generated: new Date().toISOString().slice(0, 16).replace('T', ' '),
    engine: 'frontend/backtest_logic.js, Modus WD (W + D, ohne 4H), TOP 20 = AN',
    capital: CAPITAL,
    maxRisk: MAX_RISK,
    calibration: runCalibration(),
  };
  if (!calibrationOnly) Object.assign(result, runHistory());
  fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
  fs.writeFileSync(OUT_FILE, JSON.stringify(result));

  const fmt = (n, d = 2) => (n == null ? '–' : n.toLocaleString('de-DE', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const c = result.calibration.modes;
  console.log(`Abgleich ab ${result.calibration.start}: PF 4H ${fmt(c['4H'].total?.profitFactor)} ` +
    `(${c['4H'].total?.nTrades ?? 0} Trades) · PF W+D ${fmt(c.WD.total?.profitFactor)} (${c.WD.total?.nTrades ?? 0} Trades)`);
  if (result.variants) {
    console.log('\n| Jahr | NDX | Trades | PF inkl. | PF exkl. |');
    console.log('|---|---|---|---|---|');
    for (const [y, n] of Object.entries(result.ndx)) {
      const a = result.variants.inkl.years[y];
      const b = result.variants.exkl.years[y];
      console.log(`| ${y} | ${fmt(n.pct, 1)} % | ${a?.nTrades ?? 0} | ${fmt(a?.profitFactor)} | ${fmt(b?.profitFactor)} |`);
    }
  }
  console.log(`\n→ ${OUT_FILE}`);
}

main();
