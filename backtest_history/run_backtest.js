#!/usr/bin/env node
/**
 * Historischer NASDAQ-100-Backtest, Schritt 3: Trades simulieren und je Jahr
 * auswerten. Voraussetzung: prepare_data.py (Kurse, Top-20-Ranking) und
 * fetch_alpaca_4h.py (4H-Kerzen ab 2016) haben den Cache unter
 * backtest_history/cache/ gefüllt.
 *
 * Engine: frontend/backtest_logic.js unverändert (Live-Logik, 3 von 3 Punkten,
 * Einstieg über 4H), Top-20-Filter am Einstiegstag, 10.000 € je Signal und
 * 1.000 € Risiko wie live. Gerechnet wird ab Beginn der 4H-Kerzen (2016) —
 * ohne 4H gibt es keinen Backtest.
 *
 * Aufruf:  node backtest_history/run_backtest.js
 * Schreibt data/backtest_history/ndx_results.json und die Kursdateien für
 * B-DETAILS 2 (data/backtest_history/charts/).
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
// Überschreibbar für den Offline-Test (test_backtest_history.py)
const CACHE = process.env.BACKTEST_HISTORY_CACHE || path.join(__dirname, 'cache');
const OUT_FILE = process.env.BACKTEST_HISTORY_OUT || path.join(ROOT, 'data', 'backtest_history', 'ndx_results.json');
// Kursausschnitte je Aktie für die Seite B-DETAILS 2 (frontend/backtest_history_details.html)
const CHART_DIR = path.join(path.dirname(OUT_FILE), 'charts');

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
  weeklyDate: t.weeklyDate,
  entryDate: t.entryDate,
  exitDate: t.exitDate,
  entryPrice: +t.entryPrice.toFixed(4),
  stopPrice: t.stopPrice != null ? +t.stopPrice.toFixed(4) : null,
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

const bar = (r) => [r.d, r.o, r.h, r.l, r.c];

/** Tage, an denen sym in den Top 20 stand, als Zeiträume [von, bis] aufeinanderfolgender Handelstage. */
function top20Ranges(hist, days, sym) {
  const out = [];
  let open = null, prev = null;
  for (const d of days) {
    const inTop = hist[d].includes(sym);
    if (inTop && !open) open = d;
    if (!inTop && open) { out.push([open, prev]); open = null; }
    prev = d;
  }
  if (open) out.push([open, prev]);
  return out;
}

/**
 * Kurse einer Aktie für B-DETAILS 2 (frontend/backtest_history_details.html):
 * vollständige Wochen-, Tages- und (ab 2016) 4H-Kerzen in derselben Genauigkeit
 * wie der Cache, damit die Seite die GWS-Punkte jeder Woche exakt wie die
 * Engine nachrechnet, dazu die Top-20-Zeiträume je Variante.
 */
function writeChart(sym, weekly, daily, h4, top20) {
  fs.mkdirSync(CHART_DIR, { recursive: true });
  fs.writeFileSync(path.join(CHART_DIR, `${sym}.json`), JSON.stringify({
    ticker: sym,
    w: weekly.map(bar),
    d: daily.map(bar),
    h: (h4 || []).map(bar),
    top20: Object.fromEntries(Object.entries(top20).map(([v, { hist, days }]) => [v, top20Ranges(hist, days, sym)])),
  }));
}

// ── Historischer Lauf ─────────────────────────────────────────────────────────
function runHistory() {
  const meta = readJson(path.join(CACHE, 'meta.json'));
  const h4MetaPath = path.join(CACHE, 'h4_meta.json');
  if (!fs.existsSync(h4MetaPath)) throw new Error('4H-Kerzen fehlen (fetch_alpaca_4h.py) — ohne 4H kein Backtest');
  const h4Meta = readJson(h4MetaPath);
  const top20 = readJson(path.join(CACHE, 'top20_inkl.json'));
  const top20Days = { inkl: { hist: top20, days: Object.keys(top20).sort() } };
  // Nur Titel, die ab Beginn der 4H-Kerzen mindestens einmal in den Top 20 standen
  const everTop = new Set(Object.entries(top20).filter(([d]) => d >= h4Meta.start).flatMap(([, v]) => v));

  const trades = { live4h: [] };
  const closesBySymbol = {};
  const symbols = Object.keys(meta.symbols).sort();
  let done = 0;
  for (const sym of symbols) {
    const info = meta.symbols[sym];
    const h4File = path.join(CACHE, 'h4', `${sym}.json`);
    done++;
    if (!everTop.has(sym) || !info.has_weekly || !fs.existsSync(h4File)) continue;
    const daily = readJson(path.join(CACHE, 'daily', `${sym}.json`));
    const weekly = readJson(path.join(CACHE, 'weekly', `${sym}.json`));
    const h4 = readJson(h4File);
    closesBySymbol[sym] = new Map(daily.map((r) => [r.d, r.c]));
    // Live-Logik mit 4H (3 von 3 Punkten, Einstieg über 4H) — unveränderte Engine
    for (const t of simulateTrades(buildWeekRows(weekly, daily, h4), daily, sym, top20, true)) {
      // Kursreihe endet vor dem Datenende (Übernahme, Delisting): der Trade ist
      // nicht mehr offen, sondern zum letzten verfügbaren Kurs beendet.
      const dataEnded = t.isOpen && !info.active;
      const rank = rankAt(top20, t.entryDate, sym);
      trades.live4h.push({ ...t, ticker: sym, rank, isOpen: t.isOpen && !dataEnded, dataEnded });
    }
    writeChart(sym, weekly, daily, h4, top20Days);
    if (done % 25 === 0) console.error(`  ${done}/${symbols.length} Symbole`);
  }

  const benchDaily = path.join(CACHE, 'daily', `${meta.benchmark}.json`);
  if (meta.benchmark && fs.existsSync(benchDaily)) {
    const benchWeekly = path.join(CACHE, 'weekly', `${meta.benchmark}.json`);
    fs.mkdirSync(CHART_DIR, { recursive: true });
    fs.writeFileSync(path.join(CHART_DIR, '_benchmark.json'), JSON.stringify({
      ticker: meta.benchmark,
      w: fs.existsSync(benchWeekly) ? readJson(benchWeekly).map(bar) : [],
      d: readJson(benchDaily).map(bar),
    }));
  }
  const startOf = { live4h: h4Meta.start };

  const variants = {};
  for (const [variant, list] of Object.entries(trades)) {
    list.sort((a, b) => (a.entryDate < b.entryDate ? -1 : 1));
    const negYears = new Set(Object.entries(meta.ndx).filter(([, v]) => v.pct < 0).map(([y]) => y));
    const start = startOf[variant];
    const sim = simulatePortfolio(list, closesBySymbol, { start });
    variants[variant] = {
      start,
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
      alpaca: Object.entries(resolution).filter(([, r]) => r.source === 'alpaca').map(([t, r]) => ({ ticker: t, symbol: r.yahoo })),
      keineDaten: count('keine_daten'),
      withJumps: Object.entries(meta.symbols).filter(([, v]) => v.jumps.length).map(([k, v]) => ({ ticker: k, dates: v.jumps })),
      delistedMitDatenList: Object.entries(resolution).filter(([, r]) => r.status === 'delisted_mit_daten').map(([t, r]) => ({ ticker: t, yahoo: r.yahoo })),
      aliases: Object.entries(resolution).filter(([t, r]) => r.yahoo && r.yahoo !== t).map(([t, r]) => ({ ticker: t, yahoo: r.yahoo })),
    },
    variants,
    h4: {
      source: h4Meta.source,
      feed: h4Meta.feed,
      start: h4Meta.start,
      symbols: Object.keys(h4Meta.symbols).length,
      missing: h4Meta.missing,
      errors: h4Meta.errors || {},
    },
  };
}

// ── Fenster der Live-Daten (B-Übersicht) ────────────────────────────────────
/** Erster Tag mit Yahoo-4H-Kerzen in den Live-Backtest-Dateien (letzte 104 Wochen). */
function liveWindowStart() {
  const rs = readJson(path.join(ROOT, 'data', 'rs_full.json'));
  let first = null;
  for (const e of rs.data || []) {
    const f = path.join(ROOT, 'data', `backtest_${e.ticker.toLowerCase().replace(/[^a-z0-9]/g, '_')}.json`);
    if (!fs.existsSync(f)) continue;
    const bt = readJson(f);
    const cut = (bt.ohlcv_w || []).slice(-104)[0]?.d;
    const h = (bt.ohlcv_4h || []).find((d) => !cut || d.d.slice(0, 10) >= cut);
    if (h && (!first || h.d.slice(0, 10) < first)) first = h.d.slice(0, 10);
  }
  return first || Object.keys(rs.top20_history || {}).sort()[0];
}

// ── Vorher/Nachher für den Zeitraum des bisherigen Backtests ────────────────
/**
 * Zerlegt den Unterschied zwischen bisherigem Backtest (B-Übersicht, Live-Daten)
 * und neuer historischer Rechnung für dasselbe Zeitfenster in Einzelschritte.
 * Jeder Schritt ändert genau eine Sache gegenüber dem vorigen.
 */
function runBeforeAfter(calStart) {
  const h4MetaPath = path.join(CACHE, 'h4_meta.json');
  if (!fs.existsSync(h4MetaPath)) return null;
  const meta = readJson(path.join(CACHE, 'meta.json'));
  const histTop = readJson(path.join(CACHE, 'top20_inkl.json'));
  const rs = readJson(path.join(ROOT, 'data', 'rs_full.json'));
  const liveTop = rs.top20_history || {};
  const end = (rs.benchmark_ohlcv || []).slice(-1)[0]?.d ?? meta.data_end;
  const inWindow = (t) => t.entryDate >= calStart && t.entryDate <= end;
  const repo = (sym) => {
    try {
      return readJson(path.join(ROOT, 'data', `backtest_${sym.toLowerCase().replace(/[^a-z0-9]/g, '_')}.json`));
    } catch (e) {
      return null;
    }
  };
  const clean4h = (rows) => rows.filter((d) => !d.d.endsWith(':30'));   // doppeltes Raster entfernen

  const liveSyms = (rs.data || []).map((e) => e.ticker);
  const histSyms = Object.keys(meta.symbols).filter((s) => fs.existsSync(path.join(CACHE, 'daily', `${s}.json`)));
  const run = (syms, series, top) => {
    const out = [];
    for (const sym of syms) {
      const s = series(sym);
      if (!s || !s.w.length || !s.d.length) continue;
      for (const t of simulateTrades(buildWeekRows(s.w, s.d, s.h), s.d, sym, top, true)) {
        if (inWindow(t)) out.push({ ...t, ticker: sym });
      }
    }
    return out;
  };
  const repoSeries = (full, cleaned) => (sym) => {
    const bt = repo(sym);
    if (!bt || !bt.ohlcv_w || !bt.ohlcv_d) return null;
    const w = full ? bt.ohlcv_w : bt.ohlcv_w.slice(-104);
    const cut = w[0]?.d ?? '0000';
    const h = (bt.ohlcv_4h || []).filter((d) => d.d.slice(0, 10) >= cut);
    return { w, d: bt.ohlcv_d.filter((d) => d.d >= cut), h: cleaned ? clean4h(h) : h };
  };
  const cacheSeries = (alpaca) => (sym) => {
    const wf = path.join(CACHE, 'weekly', `${sym}.json`);
    if (!fs.existsSync(wf)) return null;
    let h = [];
    if (alpaca) {
      const hf = path.join(CACHE, 'h4', `${sym}.json`);
      h = fs.existsSync(hf) ? readJson(hf) : [];
    } else {
      const bt = repo(sym);
      h = bt ? clean4h(bt.ohlcv_4h || []) : [];
    }
    return { w: readJson(wf), d: readJson(path.join(CACHE, 'daily', `${sym}.json`)), h };
  };

  const steps = [
    ['bisher', 'Bisheriger Backtest (B-Übersicht): 104 Wochen, Yahoo-4H, heutiges Top-20-Ranking',
      () => run(liveSyms, repoSeries(false, false), liveTop)],
    ['clean4h', '+ doppelte 4H-Kerzen entfernt',
      () => run(liveSyms, repoSeries(false, true), liveTop)],
    ['fullHistory', '+ volle Kurshistorie (ab 2022 statt 104 Wochen)',
      () => run(liveSyms, repoSeries(true, true), liveTop)],
    ['histRanking', '+ Top 20 nur unter den damaligen Indexmitgliedern',
      () => run(liveSyms, repoSeries(true, true), histTop)],
    ['histPrices', '+ Kurse und Universum aus dem historischen Lauf (ab 2005)',
      () => run(histSyms, cacheSeries(false), histTop)],
    ['alpaca4h', '+ 4H-Kerzen von Alpaca statt Yahoo (= neue Rechnung)',
      () => run(histSyms, cacheSeries(true), histTop)],
  ];
  const key = (t) => `${t.ticker}|${t.entryDate}`;
  const results = steps.map(([id, label, fn]) => ({ id, label, trades: fn() }));
  const first = new Set(results[0].trades.map(key));
  const last = new Set(results[results.length - 1].trades.map(key));

  // Wie stark weichen die beiden Top-20-Listen voneinander ab?
  const days = Object.keys(liveTop).filter((d) => d >= calStart && histTop[d]);
  const overlap = days.length
    ? days.reduce((s, d) => s + liveTop[d].filter((t) => histTop[d].includes(t)).length, 0) / days.length : null;

  return {
    start: calStart,
    end,
    top20Overlap: overlap,        // Ø gemeinsame Titel je Tag (von 20)
    top20Days: days.length,
    steps: results.map((r) => ({
      id: r.id,
      label: r.label,
      total: summary(r.trades),
      years: byYear(r.trades),
      sameAsBefore: r.trades.filter((t) => first.has(key(t))).length,
      sameAsNew: r.trades.filter((t) => last.has(key(t))).length,
    })),
    before: results[0].trades.map(slim),
    after: results[results.length - 1].trades.map(slim),
  };
}

function main() {
  const result = {
    generated: new Date().toISOString().slice(0, 16).replace('T', ' '),
    engine: 'frontend/backtest_logic.js, Live-Logik mit 4H (3 von 3 Punkten), TOP 20 = AN',
    capital: CAPITAL,
    maxRisk: MAX_RISK,
    ...runHistory(),
  };
  result.beforeAfter = runBeforeAfter(liveWindowStart());
  fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
  fs.writeFileSync(OUT_FILE, JSON.stringify(result));

  const fmt = (n, d = 2) => (n == null ? '–' : n.toLocaleString('de-DE', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const v = result.variants.live4h;
  console.log(`Live-Logik mit 4H ab ${v.start}: ${v.total?.nTrades ?? 0} Trades, PF ${fmt(v.total?.profitFactor)}, `
    + `Depot ${fmt(v.portfolio.endEquity, 0)} €`);
  console.log('\n| Jahr | NDX | Trades | PF |');
  console.log('|---|---|---|---|');
  for (const [y, k] of Object.entries(v.years)) {
    console.log(`| ${y} | ${fmt(result.ndx[y]?.pct, 1)} % | ${k.nTrades} | ${fmt(k.profitFactor)} |`);
  }
  console.log(`\n→ ${OUT_FILE}`);
}

main();
