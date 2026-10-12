#!/usr/bin/env node
/**
 * Zeigt für einen Titel, was die Engine (frontend/backtest_logic.js) je 4H-Kerze sieht:
 * Weekly/Daily/4H grün oder rot samt Marke, Top 20 am Tag und die Trades der Engine im
 * Zeitraum (mit Verkaufsgrund). Kurse wie backtest_ndx.js, Wochen- und Tageskerze nur
 * bis zur jeweiligen 4H-Kerze (zeitpunktgenau).
 *
 * Aufruf: node inspect_ticker.js TICKER VON BIS [--alle]
 *   z. B. node inspect_ticker.js AVGO 2024-05-13 2024-06-07
 *   ohne --alle nur die Kerzen 14:00 und 18:00 (Handelszeit), mit --alle jede 4H-Kerze
 */
const { readJson, seriesFor, simulateTradesPIT } = require('./backtest_ndx');

const [ticker, from, to] = process.argv.slice(2);
const all = process.argv.includes('--alle');
if (!ticker || !from || !to) {
  console.error('Aufruf: node inspect_ticker.js TICKER VON BIS [--alle]');
  process.exit(1);
}

const s = seriesFor(ticker.toUpperCase(), readJson('data/rs_full.json'));
if (!s) { console.error(`keine Kursdaten für ${ticker}`); process.exit(1); }
const { ohlcv_w: W, ohlcv_d: D, ohlcv_4h: H } = s.series;
const f = (v) => (v == null ? '–' : v.toFixed(2));

console.log('4H-Kerze         | Schluss | W (Marke)       | D (Marke)       | 4H (Marke)      | Top20');
for (let j = 0; j < H.length; j++) {
  const bar = H[j], day = bar.d.slice(0, 10);
  if (day < from || day > to) continue;
  if (!all && !['14:00', '18:00', '13:00', '17:00'].includes(bar.d.slice(11, 16))) continue;
  const i = D.findIndex((b) => b.d === day);
  if (i < 0) continue;
  const blk = h4Block(bar.d);
  const dh = blk === 0 ? D.slice(0, i)
    : blk === 1 ? D.slice(0, i).concat([{ d: day, o: D[i].o, h: Math.max(D[i].o, bar.h), l: Math.min(D[i].o, bar.l), c: bar.c }])
      : D.slice(0, i + 1);
  const sd = analyzeStructure(dh), sw = analyzeWeeklyStructure(weeklyUpTo(W, dh), dh);
  const s4 = analyze4HStructure(H.slice(Math.max(0, j - 59), j + 1));
  const dot = (on) => (on ? 'grün' : 'rot ');
  console.log(`${bar.d} | ${f(bar.c).padStart(7)} | ${dot(sw?.broken)} ${f(sw?.gwswHigh?.price).padStart(9)} | `
    + `${dot(sd?.broken)} ${f(sd?.gwsdHigh?.price).padStart(9)} | ${dot(s4?.broken4h)} ${f(s4?.gws4hHigh?.price).padStart(9)} | `
    + `${s.inTop(day) ? 'ja' : 'nein'}`);
}

console.log('\nTrades der Engine im Zeitraum (mit Earnings-Regel, mit Zeitstopp):');
for (const t of simulateTradesPIT(W, D, H, s.inTop, undefined, s.earnings)) {
  if (t.exitDate < from || t.signalDate > to) continue;
  console.log(`  Signal ${t.signalBar} → Kauf ${t.entryDate} ${t.entryTime} zu ${f(t.entryPrice)}, Stopp ${f(t.stopPrice)} `
    + `→ ${t.isOpen ? 'offen' : `Verkauf ${t.exitDate} zu ${f(t.exitPrice)} (${t.exitReason})`}, ${t.pnlPct.toFixed(1)} %`);
}
