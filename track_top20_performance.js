#!/usr/bin/env node
/**
 * Top-20-Performance-Tracking seit Start der Live-Signale.
 *
 * Nutzt die identische Backtest-Engine wie frontend/backtest.html und
 * frontend/backtest_overview.html (frontend/backtest_logic.js, TOP 20 = AN):
 * 10.000 EUR Kapital je Signal, max. 1.000 EUR Risiko (10 %), Stopp = letztes
 * Swing-Tief * 0,99, Ausstieg bei Bruch der GWS-D-Struktur.
 *
 * Gewertet werden nur Trades, deren Einstieg ab dem ersten live versendeten
 * Signal des jeweiligen Index liegt (data/signals.json) und bei denen der
 * Ticker am Einstiegstag in den Top 20 des Index stand (top20_history).
 *
 * Aufruf:  node track_top20_performance.js
 * Schreibt data/top20_performance.json und gibt eine Zusammenfassung aus.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = __dirname;
const OUT_FILE = path.join(ROOT, 'data', 'top20_performance.json');

const INDICES = [
  { key: 'QQQ', name: 'NASDAQ-100', rsFile: 'data/rs_full.json' },
  { key: 'SPX', name: 'S&P 500', rsFile: 'data/rs_sp500.json' },
  { key: 'DAX', name: 'DAX-40', rsFile: 'data/rs_dax.json' },
];

// ── Backtest-Engine laden (Single Source of Truth: frontend/backtest_logic.js) ──
const engineCode = fs.readFileSync(path.join(ROOT, 'frontend', 'backtest_logic.js'), 'utf8');
vm.runInThisContext(
  engineCode + '\n;globalThis.__engine = { buildWeekRows, simulateTrades, CAPITAL, MAX_RISK };'
);
const { buildWeekRows, simulateTrades, CAPITAL, MAX_RISK } = globalThis.__engine;

const readJson = (rel) => JSON.parse(fs.readFileSync(path.join(ROOT, rel), 'utf8'));
const slugify = (ticker) => ticker.toLowerCase().replace(/[^a-z0-9]/g, '_');

/** Erstes live versendetes Signal je Index-Quelle aus data/signals.json. */
function firstSignalDates() {
  const signals = readJson('data/signals.json');
  const first = {};
  for (const list of Object.values(signals)) {
    for (const s of list) {
      const src = s.source || 'QQQ';
      if (!first[src] || s.signal_date < first[src]) first[src] = s.signal_date;
    }
  }
  return first;
}

/** OHLCV-Aufbereitung exakt wie in frontend/backtest_overview.html. */
function prepareSeries(entry) {
  let bt = null;
  try {
    bt = readJson(`data/backtest_${slugify(entry.ticker)}.json`);
  } catch (e) {
    bt = null;
  }
  const full = bt && bt.ohlcv_w && bt.ohlcv_d ? bt : null;
  const rawW = full ? full.ohlcv_w : entry.ohlcv_w || [];
  const rawD = full ? full.ohlcv_d : entry.ohlcv || [];
  const raw4h = full ? full.ohlcv_4h || [] : entry.ohlcv_4h || [];
  if (!rawW.length || !rawD.length) return null;
  const ohlcvW = rawW.slice(-104);
  const cutDate = ohlcvW[0] ? ohlcvW[0].d : '2000-01-01';
  return {
    hasFullHistory: !!full,
    ohlcvW,
    ohlcvD: rawD.filter((d) => d.d >= cutDate),
    ohlcv4h: raw4h.filter((d) => d.d.slice(0, 10) >= cutDate),
  };
}

function collectTrades(index, startDate) {
  const rs = readJson(index.rsFile);
  const top20Hist = rs.top20_history || null;
  const trades = [];
  let withoutFullHistory = 0;

  for (const entry of rs.data || []) {
    const series = prepareSeries(entry);
    if (!series) continue;
    if (!series.hasFullHistory) withoutFullHistory++;
    const weekRows = buildWeekRows(series.ohlcvW, series.ohlcvD, series.ohlcv4h);
    const simulated = simulateTrades(weekRows, series.ohlcvD, entry.ticker, top20Hist, true);
    for (const t of simulated) {
      if (t.entryDate >= startDate) trades.push({ ...t, ticker: entry.ticker, index: index.key });
    }
  }

  const bench = rs.benchmark_ohlcv || [];
  const benchSlice = bench.filter((b) => b.d >= startDate);
  const benchmarkPct =
    benchSlice.length > 1
      ? (benchSlice[benchSlice.length - 1].c / benchSlice[0].c - 1) * 100
      : null;

  return {
    trades,
    universe: (rs.data || []).length,
    withoutFullHistory,
    benchmark: rs.benchmark || index.key,
    benchmarkPct,
    lastBar: benchSlice.length ? benchSlice[benchSlice.length - 1].d : null,
  };
}

function kpis(trades) {
  if (!trades.length) return null;
  const closed = trades.filter((t) => !t.isOpen);
  const open = trades.filter((t) => t.isOpen);
  const wins = closed.filter((t) => t.pnl > 0);
  const losses = closed.filter((t) => t.pnl <= 0);
  const sum = (arr, f) => arr.reduce((s, t) => s + f(t), 0);
  const grossProfit = sum(wins, (t) => t.pnl);
  const grossLoss = sum(losses, (t) => t.pnl);
  const totalPnl = sum(trades, (t) => t.pnl);
  const invested = sum(trades, (t) => t.invested);

  let equity = CAPITAL;
  let peak = CAPITAL;
  let maxDD = 0;
  for (const t of [...closed].sort((a, b) => (a.exitDate < b.exitDate ? -1 : 1))) {
    equity += t.pnl;
    peak = Math.max(peak, equity);
    maxDD = Math.max(maxDD, ((peak - equity) / peak) * 100);
  }

  const byPnl = [...trades].sort((a, b) => b.pnl - a.pnl);
  const slim = (t) => ({
    ticker: t.ticker,
    entryDate: t.entryDate,
    exitDate: t.exitDate,
    isOpen: t.isOpen,
    pnl: Math.round(t.pnl),
    pnlPct: +t.pnlPct.toFixed(1),
  });

  return {
    nTrades: trades.length,
    nClosed: closed.length,
    nOpen: open.length,
    nTickers: new Set(trades.map((t) => t.ticker)).size,
    winrate: closed.length ? (wins.length / closed.length) * 100 : null,
    totalPnl,
    realizedPnl: sum(closed, (t) => t.pnl),
    openPnl: sum(open, (t) => t.pnl),
    invested,
    returnOnInvested: invested ? (totalPnl / invested) * 100 : null,
    avgPnlPerTrade: totalPnl / trades.length,
    avgReturnPerTrade: sum(trades, (t) => t.pnlPct) / trades.length,
    avgInvested: invested / trades.length,
    avgRisk: sum(trades, (t) => t.riskAmount) / trades.length,
    avgWin: wins.length ? grossProfit / wins.length : 0,
    avgWinPct: wins.length ? sum(wins, (t) => t.pnlPct) / wins.length : 0,
    avgLoss: losses.length ? grossLoss / losses.length : 0,
    avgLossPct: losses.length ? sum(losses, (t) => t.pnlPct) / losses.length : 0,
    profitFactor: grossLoss < 0 ? Math.abs(grossProfit / grossLoss) : null,
    avgHoldingWeeks: sum(trades, (t) => t.holdingWeeks) / trades.length,
    maxDD,
    best: byPnl.slice(0, 5).map(slim),
    worst: byPnl.slice(-5).reverse().map(slim),
  };
}

function main() {
  const starts = firstSignalDates();
  const result = {
    generated: new Date().toISOString().slice(0, 16).replace('T', ' '),
    capital: CAPITAL,
    maxRisk: MAX_RISK,
    note: 'Backtest-Engine frontend/backtest_logic.js, TOP 20 = AN, Trades ab erstem Live-Signal des Index.',
    indices: {},
  };
  const allTrades = [];

  for (const index of INDICES) {
    const startDate = starts[index.key];
    if (!startDate) {
      console.error(`${index.key}: kein Live-Signal in data/signals.json – übersprungen.`);
      continue;
    }
    const { trades, universe, withoutFullHistory, benchmark, benchmarkPct, lastBar } =
      collectTrades(index, startDate);
    allTrades.push(...trades);
    result.indices[index.key] = {
      name: index.name,
      start: startDate,
      lastBar,
      universe,
      withoutFullHistory,
      benchmark,
      benchmarkPct,
      kpis: kpis(trades),
    };
    console.error(`${index.key}: ${trades.length} Trades seit ${startDate}`);
  }

  result.total = kpis(allTrades);
  fs.writeFileSync(OUT_FILE, JSON.stringify(result, null, 1));

  const fmt = (n, d = 0) =>
    n == null ? '–' : n.toLocaleString('de-DE', { minimumFractionDigits: d, maximumFractionDigits: d });
  console.log('\n| Index | Start | Trades | Winrate | Ø Rendite/Trade | Σ P&L | Rendite a. Einsatz | PF | Benchmark |');
  console.log('|---|---|---|---|---|---|---|---|---|');
  for (const index of INDICES) {
    const e = result.indices[index.key];
    if (!e || !e.kpis) continue;
    const k = e.kpis;
    console.log(
      `| ${e.name} | ${e.start} | ${k.nTrades} (${k.nOpen} offen) | ${fmt(k.winrate, 1)} % | ` +
        `${fmt(k.avgReturnPerTrade, 1)} % | ${fmt(k.totalPnl)} € | ${fmt(k.returnOnInvested, 1)} % | ` +
        `${fmt(k.profitFactor, 2)} | ${fmt(e.benchmarkPct, 1)} % |`
    );
  }
  const t = result.total;
  console.log(
    `| **Gesamt** | – | ${t.nTrades} (${t.nOpen} offen) | ${fmt(t.winrate, 1)} % | ` +
      `${fmt(t.avgReturnPerTrade, 1)} % | ${fmt(t.totalPnl)} € | ${fmt(t.returnOnInvested, 1)} % | ` +
      `${fmt(t.profitFactor, 2)} | – |`
  );
  console.log(`\n→ ${OUT_FILE}`);
}

main();
