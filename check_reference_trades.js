#!/usr/bin/env node
/**
 * Prüft die freigegebenen Referenz-Trades (data/reference_trades.json) gegen die
 * Backtest-Engine (simulateTradesPIT in frontend/backtest_logic.js) mit denselben
 * Kursen und demselben Top-20-Filter wie backtest_ndx.js.
 *
 * Je Trade muss die Engine das Signal in derselben 4H-Kerze liefern, zur selben
 * Kerze kaufen und am erwarteten Tag aussteigen (Verkauf am Ausstiegstag oder zur
 * Eröffnung des nächsten Handelstages) — immer mit der aktuellen Logik inkl. aller Regeln
 * (auch Earnings-Regel).
 *
 * Aufruf: node check_reference_trades.js   → Exit-Code 1, wenn ein Trade abweicht
 */
const path = require('path');
const { readJson, seriesFor, simulateTradesPIT } = require('./backtest_ndx');

const DATA = path.join(__dirname, 'data');

function checkTrade(ref, rs) {
  const s = seriesFor(ref.ticker, rs);
  if (!s) return [`keine Kursdaten für ${ref.ticker}`];
  if (!s.earnings) return [`keine Earnings-Termine für ${ref.ticker} (data/earnings_history.json)`];
  return checkRun(ref.entry, s, s.earnings, ref.exit, '');
}

function checkRun(entry, s, earnings, exit, label) {
  const days = s.series.ohlcv_d.map((b) => b.d);
  const trades = simulateTradesPIT(s.series.ohlcv_w, s.series.ohlcv_d, s.series.ohlcv_4h, s.inTop, undefined, earnings);
  const t = trades.find((x) => x.signalBar === entry.signal_bar);
  if (!t) {
    const near = trades.filter((x) => x.signalDate >= entry.date.slice(0, 7)).slice(0, 1)
      .map((x) => ` (nächstes Signal: ${x.signalBar})`).join('');
    return [`${label}kein Signal in der Kerze ${entry.signal_bar}${near}`];
  }
  const errors = [];
  if (t.entryDate !== entry.date || t.entryTime !== entry.time) {
    errors.push(`${label}Kauf ${t.entryDate} ${t.entryTime}, erwartet ${entry.date} ${entry.time}`);
  }
  const nextDay = days.find((d) => d > exit.signal_date);
  if (t.isOpen) errors.push(`${label}Trade noch offen, erwartet Ausstieg am ${exit.signal_date}`);
  else if (t.exitDate !== exit.signal_date && t.exitDate !== nextDay) {
    errors.push(`${label}Verkauf ${t.exitDate}, erwartet ${exit.signal_date} (${exit.reason})`);
  }
  return errors;
}

function main() {
  const refs = readJson(path.join(DATA, 'reference_trades.json')).trades;
  const rs = readJson(path.join(DATA, 'rs_full.json'));
  let failed = 0;
  for (const ref of refs) {
    const errors = checkTrade(ref, rs);
    if (errors.length) failed++;
    console.log(`${errors.length ? '✗' : '✓'} ${ref.id}${errors.length ? ': ' + errors.join('; ') : ''}`);
  }
  console.log(`${refs.length - failed} von ${refs.length} Referenz-Trades unverändert`);
  process.exitCode = failed ? 1 : 0;
}

if (require.main === module) main();
module.exports = { checkTrade };
