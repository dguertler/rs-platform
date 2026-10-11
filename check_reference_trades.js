#!/usr/bin/env node
/**
 * Prüft die freigegebenen Referenz-Trades (data/reference_trades.json) gegen die
 * Backtest-Engine (simulateTradesPIT in frontend/backtest_logic.js) mit denselben
 * Kursen und demselben Top-20-Filter wie backtest_ndx.js.
 *
 * Je Trade muss die Engine das Signal in derselben 4H-Kerze liefern, zur selben
 * Kerze kaufen und am erwarteten Tag aussteigen (Verkauf am Ausstiegstag oder zur
 * Eröffnung des nächsten Handelstages).
 *
 * Aufruf: node check_reference_trades.js   → Exit-Code 1, wenn ein Trade abweicht
 */
const path = require('path');
const { readJson, seriesFor, simulateTradesPIT } = require('./backtest_ndx');

const DATA = path.join(__dirname, 'data');

function checkTrade(ref, rs) {
  const s = seriesFor(ref.ticker, rs);
  if (!s) return [`keine Kursdaten für ${ref.ticker}`];
  const days = s.series.ohlcv_d.map((b) => b.d);
  const trades = simulateTradesPIT(s.series.ohlcv_w, s.series.ohlcv_d, s.series.ohlcv_4h, s.inTop);
  const t = trades.find((x) => x.signalBar === ref.entry.signal_bar);
  if (!t) {
    const near = trades.filter((x) => x.signalDate >= ref.entry.date.slice(0, 7)).slice(0, 1)
      .map((x) => ` (nächstes Signal: ${x.signalBar})`).join('');
    return [`kein Signal in der Kerze ${ref.entry.signal_bar}${near}`];
  }
  const errors = [];
  if (t.entryDate !== ref.entry.date || t.entryTime !== ref.entry.time) {
    errors.push(`Kauf ${t.entryDate} ${t.entryTime}, erwartet ${ref.entry.date} ${ref.entry.time}`);
  }
  const nextDay = days.find((d) => d > ref.exit.signal_date);
  if (t.isOpen) errors.push(`Trade noch offen, erwartet Ausstieg am ${ref.exit.signal_date}`);
  else if (t.exitDate !== ref.exit.signal_date && t.exitDate !== nextDay) {
    errors.push(`Verkauf ${t.exitDate}, erwartet ${ref.exit.signal_date} (${ref.exit.reason})`);
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
