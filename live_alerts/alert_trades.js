/**
 * Verschickte Breakout-Alerts → Trades. Gemeinsam genutzt von
 * live_alerts/evaluate_alerts.js (Live-Bilanz) und track_top20_performance.js
 * (Top-20-Performance seit Live-Start).
 *
 * Grundlage ist data/live_alerts.json (reconstruct_alerts.py): nur Alerts mit
 * sent = true, also genau die Titel, die per Mail/Telegram rausgingen — mit
 * dem Tag, an dem sie rausgingen. Kauf zur Eröffnung des Alert-Tags, Stopp und
 * Ausstieg wie im Backtest (simulateFromEntry aus frontend/backtest_logic.js).
 * Solange ein Titel gehalten wird, zählen weitere Alerts desselben Titels
 * nicht als neuer Trade (eine Position je Titel).
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const RS_FILES = { QQQ: 'data/rs_full.json', SPX: 'data/rs_sp500.json' };

vm.runInThisContext(fs.readFileSync(path.join(ROOT, 'frontend', 'backtest_logic.js'), 'utf8')
  + '\n;globalThis.__alertEngine = { simulateFromEntry, CAPITAL, MAX_RISK };');
const { simulateFromEntry, CAPITAL, MAX_RISK } = globalThis.__alertEngine;

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

/** { generated, sent, trades, skipped } aus data/live_alerts.json. */
function alertTrades() {
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
    const t = simulateFromEntry(daily, a.signal_date, a.entry_price);
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
  return { generated, sent, trades, skipped };
}

module.exports = { alertTrades, readJson, RS_FILES, CAPITAL, MAX_RISK };
