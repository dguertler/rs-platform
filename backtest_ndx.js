#!/usr/bin/env node
/**
 * NASDAQ-100-Backtest seit 2016 mit der zeitpunktgenauen Live-Logik
 * (simulateTradesPIT in frontend/backtest_logic.js) — Grundlage für B-ÜBERSICHT.
 *
 * Kurse: historischer Lauf (data/backtest_history/charts, Top 20 point-in-time)
 * ergänzt um die täglich aktualisierten Kurse (data/backtest_TICKER.json);
 * Top 20 danach aus data/rs_full.json (top20_history). Universum = alle Titel,
 * die seit 2016 einmal in den Top 20 standen, plus die heutigen Mitglieder.
 *
 * Depot wie live: 100.000 € Start, höchstens 10 Positionen, Zinseszins
 * (backtest_history/portfolio.js). Vergleich: NASDAQ-100 über QQQ (Kurs).
 *
 * Aufruf: node backtest_ndx.js [--hist-only] [--mit-zeitstopp] [--halten=W,D]   → data/backtest_ndx.json
 *   --hist-only: nur die historischen Kurse (Abgleich mit der Studie)
 *   --mit-zeitstopp: Systemoptimierung — Lauf mit dem (seit 12.10.2026 abgeschalteten)
 *     Zeitstopp; schreibt nur mit BACKTEST_NDX_OUT, nie in data/backtest_ndx.json
 *   --halten=W,D,4H: Studie — Ebenen, auf denen das Signal nach einer Trendumkehr bis zum
 *     Schluss unter dem Ausbruchstief grün bleibt (Standard W,D; --halten= ohne Ebene = aus);
 *     nur mit BACKTEST_NDX_OUT
 *   --wochenumkehr=aus|bestaetigt: Studie — Weekly-Trendumkehr-Regel (4H-Retracement nach dem
 *     Daily-Ausbruch) aus bzw. nur bei bestätigter Umkehr; nur mit BACKTEST_NDX_OUT
 *   --halteanker=W:tiefstes,D:kerze: Studie — Anker je Ebene (kerze | tiefstes | swingtief | tu,
 *     Standard W:swingtief, D:tu); nur mit BACKTEST_NDX_OUT
 *   --wochenbruch=tagesschluss|wochenschluss: Studie — Weekly-Anker bricht am Tages- bzw. Wochenschluss
 *     statt am Wochentief (Standard); nur mit BACKTEST_NDX_OUT
 *   --einstand=R:offset[:hoch] | --ohne-einstand: Studie — Einstands-Stopp (Standard 2:0, Tagesschluss)
 *   --tu-alt: Studie — Trendumkehr-Tief auch verwenden, wenn es schon vor dem Kauf gebrochen war
 *   --wochenanker-fest: Studie — Weekly-Anker bei erneutem Ausbruch nicht nachziehen
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = __dirname;
const DATA = path.join(ROOT, 'data');
const CHARTS = path.join(DATA, 'backtest_history', 'charts');
const OUT = process.env.BACKTEST_NDX_OUT || path.join(DATA, 'backtest_ndx.json');
const MAX_POSITIONS = 10;

vm.runInThisContext(fs.readFileSync(path.join(ROOT, 'frontend', 'backtest_logic.js'), 'utf8')
  + '\n;globalThis.__e = { simulateTradesPIT, mergeSeries, chartToSeries, top20Lookup, PIT_START, setTimeStop, setHoldSignal, setHoldAnchor, setEarlyMarkBreak, setEarningsDropRule, setWeeklyReversalRule, setWeeklyBreakCheck, setWeeklyTrail, setBreakEven, setFreshTrendLow };');
const { simulateTradesPIT, mergeSeries, chartToSeries, top20Lookup, PIT_START } = globalThis.__e;
const { kpis } = require('./backtest_kpis');
const { simulatePortfolio, portfolioStats } = require('./backtest_history/portfolio');

const readJson = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const slug = (t) => t.toLowerCase().replace(/[^a-z0-9]/g, '_');
const liveFile = (t) => path.join(DATA, `backtest_${slug(t)}.json`);
const histOnly = process.argv.includes('--hist-only');
if (process.argv.includes('--mit-zeitstopp')) {
  if (!process.env.BACKTEST_NDX_OUT) throw new Error('--mit-zeitstopp nur mit BACKTEST_NDX_OUT (Optimierungslauf)');
  globalThis.__e.setTimeStop(true);
}
const holdArg = process.argv.find((a) => a.startsWith('--halten='));
if (holdArg) {
  if (!process.env.BACKTEST_NDX_OUT) throw new Error('--halten nur mit BACKTEST_NDX_OUT (Studie)');
  const lv = holdArg.slice(9).toUpperCase().split(',');
  globalThis.__e.setHoldSignal({ w: lv.includes('W'), d: lv.includes('D'), h4: lv.includes('4H') });
}
if (process.argv.includes('--ohne-earningsfall')) {   // Studie: Kauf auch nach fallendem Kurs auf Zahlen
  if (!process.env.BACKTEST_NDX_OUT) throw new Error('--ohne-earningsfall nur mit BACKTEST_NDX_OUT (Studie)');
  globalThis.__e.setEarningsDropRule(false);
}
if (process.argv.includes('--ohne-fruehbruch')) {   // Studie: Daily-Swing-Tief erst nach zwei Folgekerzen
  if (!process.env.BACKTEST_NDX_OUT) throw new Error('--ohne-fruehbruch nur mit BACKTEST_NDX_OUT (Studie)');
  globalThis.__e.setEarlyMarkBreak(false);
}
const wrArg = process.argv.find((a) => a.startsWith('--wochenumkehr='));
if (wrArg) {   // Studie: --wochenumkehr=aus | bestaetigt (Retracement nur bei bestätigter Weekly-Umkehr)
  if (!process.env.BACKTEST_NDX_OUT) throw new Error('--wochenumkehr nur mit BACKTEST_NDX_OUT (Studie)');
  const v = wrArg.slice(15);
  globalThis.__e.setWeeklyReversalRule(v === 'bestaetigt' ? 'bestaetigt' : v === 'aus' ? false : true);
}
const wbArg = process.argv.find((a) => a.startsWith('--wochenbruch='));
if (wbArg) {   // Studie: --wochenbruch=tagesschluss|wochenschluss (Standard tief: womit der Weekly-Anker bricht)
  if (!process.env.BACKTEST_NDX_OUT) throw new Error('--wochenbruch nur mit BACKTEST_NDX_OUT (Studie)');
  globalThis.__e.setWeeklyBreakCheck(wbArg.slice(14));
}
if (process.argv.includes('--wochenanker-fest')) {   // Studie: Weekly-Anker bei erneutem Ausbruch nicht nachziehen
  if (!process.env.BACKTEST_NDX_OUT) throw new Error('--wochenanker-fest nur mit BACKTEST_NDX_OUT (Studie)');
  globalThis.__e.setWeeklyTrail(false);
}
const beArg = process.argv.find((a) => a.startsWith('--einstand='));
if (process.argv.includes('--ohne-einstand')) {   // Studie: ohne Einstands-Stopp
  if (!process.env.BACKTEST_NDX_OUT) throw new Error('--ohne-einstand nur mit BACKTEST_NDX_OUT (Studie)');
  globalThis.__e.setBreakEven(null);
}
if (beArg) {   // Studie: --einstand=2:0[:hoch] (ab 2R Gewinn Stopp auf Einstieg + 0 × R; Basis Schluss oder Hoch)
  if (!process.env.BACKTEST_NDX_OUT) throw new Error('--einstand nur mit BACKTEST_NDX_OUT (Studie)');
  const [r, offset, basis] = beArg.slice(11).split(':');
  globalThis.__e.setBreakEven({ r: parseFloat(r), offset: parseFloat(offset || '0'), basis: basis || 'schluss' });
}
if (process.argv.includes('--tu-alt')) {   // Studie: auch ein vor dem Kauf gebrochenes Trendumkehr-Tief verwenden
  if (!process.env.BACKTEST_NDX_OUT) throw new Error('--tu-alt nur mit BACKTEST_NDX_OUT (Studie)');
  globalThis.__e.setFreshTrendLow(false);
}
const anchorArg = process.argv.find((a) => a.startsWith('--halteanker='));
if (anchorArg) {   // Studie, z. B. --halteanker=W:tiefstes,D:kerze
  if (!process.env.BACKTEST_NDX_OUT) throw new Error('--halteanker nur mit BACKTEST_NDX_OUT (Studie)');
  for (const part of anchorArg.slice(13).split(',')) {
    const [lv, mode] = part.split(':');
    globalThis.__e.setHoldAnchor({ [lv.toLowerCase()]: mode });
  }
}
// Earnings-Termine je Ticker (fetch_earnings_history.py); fehlt die Datei, gilt die Regel nicht
const EARNINGS_FILE = path.join(DATA, 'earnings_history.json');
const earningsByTicker = fs.existsSync(EARNINGS_FILE) ? readJson(EARNINGS_FILE).tickers || {} : {};

function loadUniverse() {
  const rs = readJson(path.join(DATA, 'rs_full.json'));
  const charts = fs.existsSync(CHARTS)
    ? fs.readdirSync(CHARTS).filter((f) => f.endsWith('.json') && f[0] !== '_').map((f) => f.slice(0, -5)) : [];
  const members = histOnly ? [] : (rs.data || []).map((e) => e.ticker);
  return { rs, tickers: [...new Set([...charts, ...members])].sort() };
}

function seriesFor(ticker, rs) {
  const chartPath = path.join(CHARTS, `${ticker}.json`);
  const chart = fs.existsSync(chartPath) ? readJson(chartPath) : null;
  const hist = chart ? chartToSeries(chart) : null;
  const live = !histOnly && fs.existsSync(liveFile(ticker)) ? readJson(liveFile(ticker)) : null;
  const series = mergeSeries(hist, live && { ohlcv_w: live.ohlcv_w, ohlcv_d: live.ohlcv_d, ohlcv_4h: live.ohlcv_4h });
  if (!series || !series.ohlcv_d?.length || !series.ohlcv_4h?.length) return null;
  const histEnd = hist ? hist.ohlcv_d[hist.ohlcv_d.length - 1].d : '0000';
  const inTop = top20Lookup(ticker.replace(/_\d{4}$/, ''), chart?.top20?.inkl ?? null, histEnd, histOnly ? null : rs.top20_history);
  return { series, inTop, earnings: earningsByTicker[ticker] || null };
}

const round = (v, n = 2) => (v == null ? null : +v.toFixed(n));

/** Depot-Simulation (10 Plätze, Zinseszins) für eine Signalliste: Kennzahlen, Jahre, gekaufte Trades */
function depotView(list, closesBySymbol, ndx) {
  // closes je Symbol (Ticker mit Jahreszahl = frühere Firma gleichen Kürzels)
  const depotTrades = list.map((t) => ({ ...t, ticker: t.symbol }));
  const sim = simulatePortfolio(depotTrades, closesBySymbol, { start: PIT_START, maxPositions: MAX_POSITIONS });
  const depot = portfolioStats(sim, depotTrades);
  const taken = new Set(depotTrades.filter((t) => sim.results.get(t)?.taken).map((t) => `${t.symbol}|${t.entryDate}`));
  const years = {};
  for (const [y, v] of Object.entries(depot.years)) {
    years[y] = { ndxPct: ndx[y] ?? null, returnPct: v.returnPct, pnl: v.endEquity - v.startEquity,
                 profitFactor: v.profitFactor, trades: v.taken, startEquity: v.startEquity, endEquity: v.endEquity, maxDD: v.maxDD };
  }
  return { depot, years, taken };
}
const depotJson = (depot, ndxTotal) => ({
  startCapital: depot.startCapital, endEquity: round(depot.endEquity, 0), returnPct: round(depot.returnPct),
  cagr: round(depot.cagr), maxDD: round(depot.maxDD), profitFactor: round(depot.profitFactor),
  taken: depot.taken, skipped: depot.skipped, ndxPct: round((ndxTotal - 1) * 100),
});
const signalsJson = (list) => { const k = kpis(list, 10000); return { nTrades: list.length, profitFactor: round(k.profitFactor), winrate: round(k.winrate, 1) }; };
const yearsJson = (years) => Object.fromEntries(Object.entries(years).map(([y, v]) =>
  [y, Object.fromEntries(Object.entries(v).map(([k, x]) => [k, round(x, k === 'trades' ? 0 : 2)]))]));

/** NASDAQ-100-Rendite je Jahr (keyLen 4, 'YYYY') bzw. je Monat (keyLen 7, 'YYYY-MM') aus
 *  QQQ-Schlusskursen (historisch + aktuell): letzter Schluss der Periode / letzter davor. */
function ndxByPeriod(rs, keyLen = 4) {
  const benchPath = path.join(CHARTS, '_benchmark.json');
  const closes = new Map();
  if (fs.existsSync(benchPath)) for (const b of readJson(benchPath).d) closes.set(b[0], b[4]);
  if (!histOnly) for (const b of rs.benchmark_ohlcv || []) closes.set(b.d, b.c);
  const days = [...closes.keys()].sort();
  const lastOf = new Map();
  for (const d of days) lastOf.set(d.slice(0, keyLen), d);
  const out = {};
  let prev = null;
  for (const [p, last] of lastOf) {
    if (prev && p >= PIT_START.slice(0, keyLen)) out[p] = (closes.get(last) / closes.get(prev) - 1) * 100;
    prev = last;
  }
  return out;
}

function main() {
  const { rs, tickers } = loadUniverse();
  const trades = [];
  const unfiltered = [];   // Schalter „Alle Signale“ auf B-ÜBERSICHT: ohne Top-20-Filter
  const closesBySymbol = {};
  let lastDay = '0000';
  const loaded = [];
  for (const t of tickers) {
    const s = seriesFor(t, rs);
    if (!s) continue;
    const d = s.series.ohlcv_d;
    if (d[d.length - 1].d > lastDay) lastDay = d[d.length - 1].d;
    loaded.push({ t, ...s });
  }
  for (const { t, series, inTop, earnings } of loaded) {
    const d = series.ohlcv_d;
    const active = d[d.length - 1].d >= lastDay.slice(0, 8) + '01' || d[d.length - 1].d >= lastDay;
    const ticker = t.replace(/_\d{4}$/, '');
    closesBySymbol[t] = new Map(d.map((b) => [b.d, b.c]));
    const add = (list, tr) => list.push({ ...tr, ticker, symbol: t, rank: 10, isOpen: tr.isOpen && active, dataEnded: tr.isOpen && !active });
    for (const tr of simulateTradesPIT(series.ohlcv_w, d, series.ohlcv_4h, inTop, PIT_START, earnings)) add(trades, tr);
    if (!histOnly) for (const tr of simulateTradesPIT(series.ohlcv_w, d, series.ohlcv_4h, null, PIT_START, earnings)) add(unfiltered, tr);
  }
  const byEntry = (a, b) => (a.entryDate < b.entryDate ? -1 : a.entryDate > b.entryDate ? 1 : a.entryTime < b.entryTime ? -1 : 1);
  trades.sort(byEntry);
  unfiltered.sort(byEntry);

  const ndx = ndxByPeriod(rs, 4);
  const all = depotView(trades, closesBySymbol, ndx);
  const alle = unfiltered.length ? depotView(unfiltered, closesBySymbol, ndx) : null;
  const { depot, years, taken } = all;
  const ndxTotal = Object.values(ndx).reduce((f, p) => f * (1 + p / 100), 1);

  const result = {
    generated: new Date().toISOString().slice(0, 16).replace('T', ' '),
    dataEnd: lastDay,
    start: PIT_START,
    rule: 'Zeitpunktgenau wie live: Signal an jedem 4H-Kerzenschluss (4H neu, Woche und Tag zu diesem Zeitpunkt grün), '
      + 'Kauf zur nächsten 4H-Kerze (Kerzen 10–14/14–18 Uhr) bzw. um 10 Uhr am nächsten Handelstag, Top 20 am Signaltag, '
      + 'Stopp/Trendumkehr/Verkauf vor Earnings wie Engine; Depot 100.000 €, höchstens 10 Positionen, Zinseszins',
    depot: depotJson(depot, ndxTotal),
    signals: signalsJson(trades),
    ndxMonths: Object.fromEntries(Object.entries(ndxByPeriod(rs, 7)).map(([m, v]) => [m, round(v)])),
    years: yearsJson(years),
    // Vergleich ohne Top-20-Filter (alle Signale derselben Aktien), eigenes Depot; Trades kompakt
    ...(alle ? { allSignals: {
      depot: depotJson(alle.depot, ndxTotal), signals: signalsJson(unfiltered), years: yearsJson(alle.years),
      trades: unfiltered.map((t) => ({
        ticker: t.ticker, ...(t.symbol !== t.ticker ? { symbol: t.symbol } : {}), exitDate: t.exitDate, pnl: Math.round(t.pnl),
        pnlPct: round(t.pnlPct, 1), isOpen: t.isOpen, depot: alle.taken.has(`${t.symbol}|${t.entryDate}`),
      })),
    } } : {}),
    trades: trades.map((t) => ({
      ticker: t.ticker, ...(t.symbol !== t.ticker ? { symbol: t.symbol } : {}), signalBar: t.signalBar, weeklyDate: t.weeklyDate, entryDate: t.entryDate, entryTime: t.entryTime,
      entryPrice: round(t.entryPrice, 4), stopPrice: round(t.stopPrice, 4), exitDate: t.exitDate, exitPrice: round(t.exitPrice, 4),
      invested: Math.round(t.invested), pnl: Math.round(t.pnl), pnlPct: round(t.pnlPct, 1), holdingWeeks: t.holdingWeeks,
      isOpen: t.isOpen, ...(t.exitReason ? { exitReason: t.exitReason } : t.dataEnded ? { exitReason: 'datenende' } : {}), ...(t.dataEnded ? { dataEnded: true } : {}), depot: taken.has(`${t.symbol}|${t.entryDate}`),
    })),
  };
  fs.writeFileSync(OUT, JSON.stringify(result));
  const f = (v, d = 1) => (v == null ? '–' : v.toFixed(d).replace('.', ','));
  console.log(`${trades.length} Signale, PF ${f(result.signals.profitFactor, 2)} · Depot ${Math.round(depot.endEquity).toLocaleString('de-DE')} €, `
    + `${f(depot.cagr)} % p. a., PF ${f(depot.profitFactor, 2)}, max. Rückgang ${f(depot.maxDD)} %`);
  console.log('| Jahr | NASDAQ-100 | Rendite | Gewinn | PF |\n|---|---|---|---|---|');
  for (const [y, v] of Object.entries(years)) {
    console.log(`| ${y} | ${f(v.ndxPct)} % | ${f(v.returnPct)} % | ${Math.round(v.pnl).toLocaleString('de-DE')} € | ${f(v.profitFactor, 2)} |`);
  }
  console.log(`→ ${OUT}`);
}

if (require.main === module) main();
module.exports = { readJson, seriesFor, simulateTradesPIT, ndxByPeriod };
