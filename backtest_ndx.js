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
 * Aufruf: node backtest_ndx.js [--hist-only]   → data/backtest_ndx.json
 *   --hist-only: nur die historischen Kurse (Abgleich mit der Studie)
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
  + '\n;globalThis.__e = { simulateTradesPIT, mergeSeries, chartToSeries, top20Lookup, PIT_START };');
const { simulateTradesPIT, mergeSeries, chartToSeries, top20Lookup, PIT_START } = globalThis.__e;
const { kpis } = require('./backtest_kpis');
const { simulatePortfolio, portfolioStats } = require('./backtest_history/portfolio');

const readJson = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const slug = (t) => t.toLowerCase().replace(/[^a-z0-9]/g, '_');
const liveFile = (t) => path.join(DATA, `backtest_${slug(t)}.json`);
const histOnly = process.argv.includes('--hist-only');

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
  return { series, inTop };
}

/** NASDAQ-100-Jahresrendite aus QQQ-Schlusskursen (historisch + aktuell). */
function ndxByYear(rs) {
  const benchPath = path.join(CHARTS, '_benchmark.json');
  const closes = new Map();
  if (fs.existsSync(benchPath)) for (const b of readJson(benchPath).d) closes.set(b[0], b[4]);
  if (!histOnly) for (const b of rs.benchmark_ohlcv || []) closes.set(b.d, b.c);
  const days = [...closes.keys()].sort();
  const out = {};
  for (let y = +PIT_START.slice(0, 4); y <= +days[days.length - 1].slice(0, 4); y++) {
    const before = days.filter((d) => d < `${y}-01-01`).pop();
    const last = days.filter((d) => d.startsWith(`${y}`)).pop();
    if (before && last) out[y] = (closes.get(last) / closes.get(before) - 1) * 100;
  }
  return out;
}

function main() {
  const { rs, tickers } = loadUniverse();
  const trades = [];
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
  for (const { t, series, inTop } of loaded) {
    const d = series.ohlcv_d;
    const active = d[d.length - 1].d >= lastDay.slice(0, 8) + '01' || d[d.length - 1].d >= lastDay;
    const ticker = t.replace(/_\d{4}$/, '');
    closesBySymbol[t] = new Map(d.map((b) => [b.d, b.c]));
    for (const tr of simulateTradesPIT(series.ohlcv_w, d, series.ohlcv_4h, inTop)) {
      trades.push({ ...tr, ticker, symbol: t, rank: 10, isOpen: tr.isOpen && active, dataEnded: tr.isOpen && !active });
    }
  }
  trades.sort((a, b) => (a.entryDate < b.entryDate ? -1 : a.entryDate > b.entryDate ? 1 : a.entryTime < b.entryTime ? -1 : 1));

  // Depot: closes je Symbol (Ticker mit Jahreszahl = frühere Firma gleichen Kürzels)
  const depotTrades = trades.map((t) => ({ ...t, ticker: t.symbol }));
  const sim = simulatePortfolio(depotTrades, closesBySymbol, { start: PIT_START, maxPositions: MAX_POSITIONS });
  const depot = portfolioStats(sim, depotTrades);
  const taken = new Set(depotTrades.filter((t) => sim.results.get(t)?.taken).map((t) => `${t.symbol}|${t.entryDate}`));
  const ndx = ndxByYear(rs);

  const years = {};
  for (const [y, v] of Object.entries(depot.years)) {
    years[y] = { ndxPct: ndx[y] ?? null, returnPct: v.returnPct, pnl: v.endEquity - v.startEquity,
                 profitFactor: v.profitFactor, trades: v.taken, startEquity: v.startEquity, endEquity: v.endEquity, maxDD: v.maxDD };
  }
  const ndxTotal = Object.values(ndx).reduce((f, p) => f * (1 + p / 100), 1);

  const round = (v, n = 2) => (v == null ? null : +v.toFixed(n));
  const result = {
    generated: new Date().toISOString().slice(0, 16).replace('T', ' '),
    dataEnd: lastDay,
    start: PIT_START,
    rule: 'Zeitpunktgenau wie live: Signal an jedem 4H-Kerzenschluss (4H neu, Woche und Tag zu diesem Zeitpunkt grün), '
      + 'Kauf zur nächsten 4H-Kerze (Kerzen 10–14/14–18 Uhr) bzw. um 10 Uhr am nächsten Handelstag, Top 20 am Signaltag, '
      + 'Stopp/Ausstieg/Zeitstopp wie Engine; Depot 100.000 €, höchstens 10 Positionen, Zinseszins',
    depot: {
      startCapital: depot.startCapital, endEquity: round(depot.endEquity, 0), returnPct: round(depot.returnPct),
      cagr: round(depot.cagr), maxDD: round(depot.maxDD), profitFactor: round(depot.profitFactor),
      taken: depot.taken, skipped: depot.skipped, ndxPct: round((ndxTotal - 1) * 100),
    },
    signals: (() => { const k = kpis(trades, 10000); return { nTrades: trades.length, profitFactor: round(k.profitFactor), winrate: round(k.winrate, 1) }; })(),
    years: Object.fromEntries(Object.entries(years).map(([y, v]) => [y, Object.fromEntries(Object.entries(v).map(([k, x]) => [k, round(x, k === 'trades' ? 0 : 2)]))])),
    trades: trades.map((t) => ({
      ticker: t.ticker, ...(t.symbol !== t.ticker ? { symbol: t.symbol } : {}), signalBar: t.signalBar, weeklyDate: t.weeklyDate, entryDate: t.entryDate, entryTime: t.entryTime,
      entryPrice: round(t.entryPrice, 4), stopPrice: round(t.stopPrice, 4), exitDate: t.exitDate, exitPrice: round(t.exitPrice, 4),
      invested: Math.round(t.invested), pnl: Math.round(t.pnl), pnlPct: round(t.pnlPct, 1), holdingWeeks: t.holdingWeeks,
      isOpen: t.isOpen, ...(t.dataEnded ? { dataEnded: true } : {}), depot: taken.has(`${t.symbol}|${t.entryDate}`),
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
