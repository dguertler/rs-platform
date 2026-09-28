#!/usr/bin/env node
/**
 * Echte Live-Bilanz: jeder tatsächlich verschickte Breakout-Alert
 * (data/live_alerts.json aus reconstruct_alerts.py) als Trade.
 *
 * Kauf zur Eröffnung des Alert-Tags (Mail/Telegram gehen vor US-Börsenstart
 * raus), Stopp und Ausstieg exakt wie im Backtest (live_alerts/alert_trades.js),
 * 10.000 € je Signal, max. 1.000 € Risiko, eine Position je Titel.
 *
 * Aufruf:  node live_alerts/evaluate_alerts.js
 * Schreibt data/live_alerts_performance.json
 */
const fs = require('fs');
const path = require('path');
const { alertTrades, CAPITAL, MAX_RISK } = require('./alert_trades');
const { kpis: kpisFor } = require(path.join(__dirname, '..', 'backtest_kpis'));

const OUT_FILE = path.join(__dirname, '..', 'data', 'live_alerts_performance.json');

function summary(trades) {
  const k = kpisFor(trades, CAPITAL);
  if (!k) return null;
  const { best, worst, ...rest } = k;
  return { ...rest, best, worst };
}

function main() {
  const { generated, sent, trades, skipped } = alertTrades();
  const groups = {
    alle: trades,
    QQQ: trades.filter((t) => t.source === 'QQQ'),
    SPX: trades.filter((t) => t.source === 'SPX'),
    nur4H: trades.filter((t) => t.trigger === '4h'),
    ohneNaeherung: trades.filter((t) => t.basis !== 'naeherung'),
  };
  const result = {
    generated: new Date().toISOString().slice(0, 16).replace('T', ' '),
    alertsGenerated: generated,
    rule: 'Kauf zur Eröffnung am Alert-Tag, Stopp/Ausstieg wie Backtest-Engine, '
      + `${CAPITAL} € je Signal, max. ${MAX_RISK} € Risiko, eine Position je Titel`,
    alertsSent: sent.length,
    firstAlert: sent[0]?.signal_date ?? null,
    skipped,
    groups: Object.fromEntries(Object.entries(groups).map(([k, v]) => [k, summary(v)])),
    trades,
  };
  fs.writeFileSync(OUT_FILE, JSON.stringify(result, null, 1));

  const fmt = (n, d = 2) => (n == null ? '–' : n.toLocaleString('de-DE', { minimumFractionDigits: d, maximumFractionDigits: d }));
  console.log(`${sent.length} verschickte Alerts → ${trades.length} Trades (übersprungen: ${JSON.stringify(skipped)})`);
  console.log('| Gruppe | Trades (offen) | Trefferquote | PF | PF abgeschl. | Ø Rendite | Rendite a. Einsatz | Σ P&L |');
  console.log('|---|---|---|---|---|---|---|---|');
  for (const [k, s] of Object.entries(result.groups)) {
    if (!s) continue;
    console.log(`| ${k} | ${s.nTrades} (${s.nOpen}) | ${fmt(s.winrate, 1)} % | ${fmt(s.profitFactor)} | `
      + `${fmt(s.profitFactorClosed)} | ${fmt(s.avgReturnPerTrade, 1)} % | ${fmt(s.returnOnInvested, 1)} % | ${fmt(s.totalPnl, 0)} € |`);
  }
}

main();
