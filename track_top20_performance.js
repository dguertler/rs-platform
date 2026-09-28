#!/usr/bin/env node
/**
 * Top-20-Performance-Tracking seit Start der Live-Signale.
 *
 * Die Einstiege sind die tatsächlich per Mail/Telegram verschickten
 * Breakout-Alerts (data/live_alerts.json, live_alerts/alert_trades.js): Kauf
 * zur Eröffnung des Alert-Tags. Stopp und Ausstieg wie in der Backtest-Engine
 * (frontend/backtest_logic.js): 10.000 EUR je Signal, max. 1.000 EUR Risiko,
 * Stopp = letztes Swing-Tief * 0,99, Ausstieg bei Bruch der GWS-D-Struktur.
 *
 * Früher simulierte das Skript die Einstiege selbst (Wochenlauf, nur
 * 4H-Auslöser, Kauf am Folgetag, Top 20 aus top20_history) — das traf andere
 * Tage und andere Titel als die echten Alerts (z. B. AMD 15.04. statt 17.04.)
 * und unterschätzte die Live-Bilanz deutlich.
 *
 * Aufruf:  node track_top20_performance.js
 * Schreibt data/top20_performance.json und gibt eine Zusammenfassung aus.
 */
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const OUT_FILE = path.join(ROOT, 'data', 'top20_performance.json');

const INDICES = [
  { key: 'QQQ', name: 'NASDAQ-100', rsFile: 'data/rs_full.json' },
  { key: 'SPX', name: 'S&P 500', rsFile: 'data/rs_sp500.json' },
];

const { alertTrades, readJson, CAPITAL, MAX_RISK } = require('./live_alerts/alert_trades');
const { kpis: kpisFor } = require('./backtest_kpis');
const kpis = (trades) => kpisFor(trades, CAPITAL);

function indexStats(index, trades) {
  const rs = readJson(index.rsFile);
  const startDate = trades.reduce((m, t) => (!m || t.alertDate < m ? t.alertDate : m), null);
  const benchSlice = (rs.benchmark_ohlcv || []).filter((b) => startDate && b.d >= startDate);
  return {
    name: index.name,
    start: startDate,
    lastBar: benchSlice.length ? benchSlice[benchSlice.length - 1].d : null,
    benchmark: rs.benchmark || index.key,
    benchmarkPct: benchSlice.length > 1
      ? (benchSlice[benchSlice.length - 1].c / benchSlice[0].c - 1) * 100
      : null,
    kpis: kpis(trades),
  };
}

function main() {
  const { trades: allTrades, sent } = alertTrades();
  const result = {
    generated: new Date().toISOString().slice(0, 16).replace('T', ' '),
    capital: CAPITAL,
    maxRisk: MAX_RISK,
    note: 'Einstiege = tatsächlich verschickte Alerts (Kauf zur Eröffnung am Alert-Tag), '
      + 'Stopp/Ausstieg wie frontend/backtest_logic.js, eine Position je Titel.',
    alertsSent: sent.length,
    indices: {},
  };
  for (const index of INDICES) {
    const trades = allTrades.filter((t) => t.source === index.key);
    if (!trades.length) {
      console.error(`${index.key}: keine verschickten Alerts – übersprungen.`);
      continue;
    }
    result.indices[index.key] = indexStats(index, trades);
    console.error(`${index.key}: ${trades.length} Trades seit ${result.indices[index.key].start}`);
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
