#!/usr/bin/env node
/**
 * Vorher/Nachher-Vergleich zweier Backtest-Läufe (Ausgabe von backtest_ndx.js) für
 * Logik-Änderungen — Tabelle wie in CLAUDE.md „Logik-Anpassungen & Logik-Verbesserungen“ vorgegeben.
 *
 * Bewertet werden alle Trades der Läufe (= alle Top-20-Signale, ohne Depot-Begrenzung),
 * je Trade 10.000 € Einsatz wie in der Engine. Jahresrendite = Gewinn der im Jahr
 * verkauften Trades (offene: laufendes Jahr, aktueller Kurs) / 100.000 € (10 × 10.000 €,
 * Bezugsgröße wie B-ÜBERSICHT); Gesamtrendite = Summe der Jahresrenditen inkl. des
 * laufenden Jahres. NASDAQ-100 ebenso als Summe seiner Jahresrenditen (years[].ndxPct).
 *
 * Aufruf: node compare_backtest.js vorher.json nachher.json
 *   Läufe z. B.: BACKTEST_NDX_OUT=/tmp/vorher.json node backtest_ndx.js
 */
const fs = require('fs');
const { kpis } = require('./backtest_kpis');

const BASE_CAPITAL = 100000;
const fmtEur = (v) => `${Math.round(v).toLocaleString('de-DE')} €`;
const fmtPct = (v, d = 1) => `${v >= 0 ? '+' : ''}${v.toFixed(d).replace('.', ',')} %`;
const fmtNum = (v, d = 2) => v.toFixed(d).replace('.', ',');

const key = (t) => `${t.symbol || t.ticker}|${t.signalBar}`;
const sum = (a) => a.reduce((s, t) => s + t.pnl, 0);

function yearly(run) {
  const out = {};
  for (const y of Object.keys(run.years)) out[y] = 0;
  for (const t of run.trades) {
    const y = (t.exitDate || t.entryDate).slice(0, 4);
    out[y] = (out[y] || 0) + t.pnl;
  }
  return Object.fromEntries(Object.entries(out).map(([y, p]) => [y, (p / BASE_CAPITAL) * 100]));
}

function maxDrawdown(trades) {
  let c = 0, peak = 0, dd = 0;
  for (const t of [...trades].filter((x) => !x.isOpen).sort((a, b) => (a.exitDate < b.exitDate ? -1 : 1))) {
    c += t.pnl; peak = Math.max(peak, c); dd = Math.min(dd, c - peak);
  }
  return dd;
}

function main() {
  const [a, b] = process.argv.slice(2).map((p) => JSON.parse(fs.readFileSync(p, 'utf8')));
  if (!a || !b) { console.error('Aufruf: node compare_backtest.js vorher.json nachher.json'); process.exit(1); }
  const ka = kpis(a.trades, 10000), kb = kpis(b.trades, 10000);
  const ya = yearly(a), yb = yearly(b);
  const years = [...new Set([...Object.keys(ya), ...Object.keys(yb)])].sort();
  const ndx = Object.fromEntries(years.map((y) => [y, (b.years[y] || a.years[y] || {}).ndxPct ?? 0]));
  const total = (o) => years.reduce((s, y) => s + (o[y] || 0), 0);

  const A = new Map(a.trades.map((t) => [key(t), t])), B = new Map(b.trades.map((t) => [key(t), t]));
  const gone = a.trades.filter((t) => !B.has(key(t)));
  const added = b.trades.filter((t) => !A.has(key(t)));
  const changed = b.trades.filter((t) => A.has(key(t)) && (A.get(key(t)).exitDate !== t.exitDate || Math.abs(A.get(key(t)).pnl - t.pnl) > 1));
  const better = changed.filter((t) => t.pnl > A.get(key(t)).pnl).length;

  const span = `${years[0]}–${years[years.length - 1]}`;
  console.log(`| Kennzahl (alle Top-20-Signale, je Trade 10.000 €) | bisher | neu |`);
  console.log(`|---|---|---|`);
  console.log(`| betroffene Trades | – | ${gone.length} weggefallen (${fmtEur(sum(gone))}), ${added.length} neu (${fmtEur(sum(added))}), ${changed.length} mit anderem Ausstieg (${fmtEur(sum(changed.map((t) => A.get(key(t)))))} → ${fmtEur(sum(changed))}, ${better} besser / ${changed.length - better} schlechter) |`);
  console.log(`| Anzahl Trades | ${a.trades.length} | ${b.trades.length} |`);
  console.log(`| Profitfaktor | ${fmtNum(ka.profitFactor)} | ${fmtNum(kb.profitFactor)} |`);
  console.log(`| absolute Rendite (Gewinnsumme) | ${fmtEur(ka.totalPnl)} | ${fmtEur(kb.totalPnl)} |`);
  console.log(`| **Gesamtrendite ${span}** (Summe der Jahresrenditen) | ${fmtPct(total(ya))} | ${fmtPct(total(yb))} |`);
  console.log(`| NASDAQ-100 Gesamtrendite ${span} (Summe der Jahresrenditen) | ${fmtPct(total(ndx))} | ${fmtPct(total(ndx))} |`);
  console.log(`| Ø Rendite je Trade / Trefferquote | ${fmtPct(ka.avgReturnPerTrade, 2)} / ${fmtNum(ka.winrate, 1)} % | ${fmtPct(kb.avgReturnPerTrade, 2)} / ${fmtNum(kb.winrate, 1)} % |`);
  console.log(`| größter Rückgang der Gewinnsumme | ${fmtEur(maxDrawdown(a.trades))} | ${fmtEur(maxDrawdown(b.trades))} |`);
  console.log('');
  console.log(`| Jahr | NASDAQ-100 | bisher | neu |`);
  console.log(`|---|---|---|---|`);
  for (const y of years) console.log(`| ${y} | ${fmtPct(ndx[y])} | ${fmtPct(ya[y] || 0)} | ${fmtPct(yb[y] || 0)} |`);
  console.log(`| **Summe** | **${fmtPct(total(ndx))}** | **${fmtPct(total(ya))}** | **${fmtPct(total(yb))}** |`);
}

main();
