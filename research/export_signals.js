#!/usr/bin/env node
/**
 * Exportiert alle 4H-Breakout-Signale der Live-Logik (simulateTradesPIT in
 * frontend/backtest_logic.js) für die Strategie-Studie research/trading_approaches.py.
 *
 * Unterschied zu simulateTradesPIT: keine Sperre, solange im selben Titel ein
 * Trade offen ist — die Studie testet andere Ausstiegsregeln und braucht dafür
 * auch die Signale, die die heutige Ausstiegsregel verdeckt. Je Signal wird der
 * Trade mit der heutigen Regel (Stopp, Strukturbruch, Zeitstopp) mitgeliefert.
 *
 * Kurse: nur der historische Lauf (data/backtest_history/charts, Top 20 point-in-time).
 * Aufruf: node research/export_signals.js → research/data/signals_4h.json
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const CHARTS = path.join(ROOT, 'data', 'backtest_history', 'charts');
const OUT = path.join(__dirname, 'data', 'signals_4h.json');

vm.runInThisContext(fs.readFileSync(path.join(ROOT, 'frontend', 'backtest_logic.js'), 'utf8')
  + '\n;globalThis.__e = { analyze4HStructure, analyzeStructure, analyzeWeeklyStructure, weeklyUpTo, h4Block, tradeFromEntry, chartToSeries, mergeSeries, top20Lookup, PIT_START };');
const E = globalThis.__e;

function signalsFor(series, inTop) {
  const { ohlcv_w: w, ohlcv_d: d, ohlcv_4h: h } = series;
  const out = [];
  const dIdx = new Map(d.map((b, i) => [b.d, i]));
  const first = Math.max(8, h.findIndex((b) => b.d.slice(0, 10) >= E.PIT_START) - 1);
  if (first < 8 || h.length < 10) return out;
  let prev = null;
  for (let j = first; j < h.length; j++) {
    const p = E.analyze4HStructure(h.slice(Math.max(0, j - 59), j + 1))?.broken4h ? 1 : 0;
    const flip = prev === 0 && p === 1;
    prev = p;
    if (!flip) continue;
    const bar = h[j], day = bar.d.slice(0, 10);
    if (day < E.PIT_START || !inTop(day)) continue;
    const i = dIdx.get(day);
    if (i == null) continue;
    const blk = E.h4Block(bar.d);
    let dHistory;
    if (blk === 0) dHistory = d.slice(0, i);
    else if (blk === 1) {
      const db = d[i];
      dHistory = d.slice(0, i).concat([{ d: day, o: db.o, h: Math.max(db.o, bar.h), l: Math.min(db.o, bar.l), c: bar.c }]);
    } else dHistory = d.slice(0, i + 1);
    if (dHistory.length < 30) continue;
    if (!E.analyzeStructure(dHistory)?.broken) continue;
    if (!E.analyzeWeeklyStructure(E.weeklyUpTo(w, dHistory), dHistory)?.broken) continue;
    let k = j + 1;
    if (!(blk <= 1 && h[k] && h[k].d.slice(0, 10) === day)) {
      while (k < h.length && h[k].d.slice(0, 10) <= day) k++;
    }
    if (k >= h.length) continue;
    const t = E.tradeFromEntry(d, h[k].d.slice(0, 10), h[k].o, { signalBar: bar.d });
    if (!t) continue;
    out.push({
      signalBar: bar.d, entryDate: t.entryDate, entryTime: h[k].d.slice(11, 16),
      entryPrice: +t.entryPrice.toFixed(4), stopPrice: +t.stopPrice.toFixed(4),
      exitDate: t.exitDate, exitPrice: +t.exitPrice.toFixed(4), isOpen: t.isOpen,
    });
  }
  return out;
}

function main() {
  const files = fs.readdirSync(CHARTS).filter((f) => f.endsWith('.json') && f[0] !== '_');
  const signals = {};
  for (const f of files) {
    const chart = JSON.parse(fs.readFileSync(path.join(CHARTS, f), 'utf8'));
    const series = E.mergeSeries(E.chartToSeries(chart), null);
    if (!series.ohlcv_d.length || !series.ohlcv_4h.length) continue;
    const sym = f.slice(0, -5);
    const histEnd = series.ohlcv_d[series.ohlcv_d.length - 1].d;
    const inTop = E.top20Lookup(sym.replace(/_\d{4}$/, ''), chart.top20?.inkl ?? [], histEnd, null);
    signals[sym] = signalsFor(series, inTop);
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString().slice(0, 16), signals }));
  const n = Object.values(signals).reduce((s, a) => s + a.length, 0);
  console.log(`${n} Signale in ${Object.keys(signals).length} Titeln → ${OUT}`);
}

main();
