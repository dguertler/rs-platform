#!/usr/bin/env node
/**
 * Echte Live-Bilanz: jeder tatsächlich verschickte Breakout-Alert
 * (data/live_alerts.json aus reconstruct_alerts.py) als Trade.
 *
 * Kauf zur Eröffnung des Alert-Tags (Mail/Telegram gehen vor US-Börsenstart
 * raus), Stopp und Ausstieg exakt wie im Backtest (simulateFromEntry aus
 * frontend/backtest_logic.js), 10.000 € je Signal, max. 1.000 € Risiko. Solange
 * ein Titel gehalten wird, zählen weitere Alerts desselben Titels nicht als
 * neuer Trade (wie die Engine: eine Position je Titel).
 *
 * Aufruf:  node live_alerts/evaluate_alerts.js
 * Schreibt data/live_alerts_performance.json
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const OUT_FILE = path.join(ROOT, 'data', 'live_alerts_performance.json');
const RS_FILES = { QQQ: 'data/rs_full.json', SPX: 'data/rs_sp500.json' };

vm.runInThisContext(fs.readFileSync(path.join(ROOT, 'frontend', 'backtest_logic.js'), 'utf8')
  + '\n;globalThis.__engine = { simulateFromEntry, CAPITAL, MAX_RISK };');
const { simulateFromEntry, CAPITAL, MAX_RISK } = globalThis.__engine;
const { kpis: kpisFor } = require(path.join(ROOT, 'backtest_kpis'));

const readJson = (rel) => JSON.parse(fs.readFileSync(path.join(ROOT, rel), 'utf8'));

/** Tageskerzen je Ticker: Backtest-Datei (volle Historie), sonst RS-Datei. */
function dailySeries() {
  const fromRs = {};
  for (const file of Object.values(RS_FILES)) {
    for (const e of readJson(file).data || []) if (!fromRs[e.ticker]) fromRs[e.ticker] = e.ohlcv || [];
  }
  const cache = {};
  return (ticker) => {
    if (!(ticker in cache)) {
      const f = `data/backtest_${ticker.toLowerCase().replace(/[^a-z0-9]/g, '_')}.json`;
      cache[ticker] = fs.existsSync(path.join(ROOT, f)) ? readJson(f).ohlcv_d : (fromRs[ticker] || []);
    }
    return cache[ticker];
  };
}

function summary(trades) {
  const k = kpisFor(trades, CAPITAL);
  if (!k) return null;
  const { best, worst, ...rest } = k;
  return { ...rest, best, worst };
}

function main() {
  const { alerts, generated } = readJson('data/live_alerts.json');
  const sent = alerts.filter((a) => a.sent).sort((a, b) => (a.signal_date < b.signal_date ? -1 : 1));
  const series = dailySeries();
  const trades = [];
  const skipped = { position_offen: 0, keine_kurse: 0, kein_gueltiger_einstieg: 0 };
  const openUntil = {};                        // Ticker → Ausstiegsdatum der laufenden Position

  for (const a of sent) {
    if (openUntil[a.ticker] && a.signal_date <= openUntil[a.ticker]) { skipped.position_offen++; continue; }
    const daily = series(a.ticker);
    if (!daily.length) { skipped.keine_kurse++; continue; }
    const t = simulateFromEntry(daily, a.signal_date);
    if (!t) { skipped.kein_gueltiger_einstieg++; continue; }
    openUntil[a.ticker] = t.isOpen ? '9999-12-31' : t.exitDate;
    trades.push({
      ticker: a.ticker, source: a.source, trigger: a.trigger_tf, alertDate: a.signal_date, basis: a.basis,
      entryDate: t.entryDate, entryPrice: +t.entryPrice.toFixed(2), stopPrice: +t.stopPrice.toFixed(2),
      exitDate: t.exitDate, exitPrice: +t.exitPrice.toFixed(2), invested: Math.round(t.invested),
      riskAmount: Math.round(t.riskAmount), pnl: Math.round(t.pnl), pnlPct: +t.pnlPct.toFixed(1),
      isWin: t.isWin, isOpen: t.isOpen,
    });
  }

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
