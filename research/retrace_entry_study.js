// Studie 10/2026: Einstieg nach 4H-Rücksetzer statt sofort (Ergebnis: research/RETRACE_ENTRY.md).
// Signal wie live (simulateTradesPIT): 4H springt auf grün, Woche und Tag zu diesem
// Zeitpunkt grün, Top 20 am Signaltag. Danach wird auf einen Rücksetzer gewartet:
//   MODE=now    sofort kaufen (Vergleich, entspricht dem 4H-Stopp aus STOP_LEVEL.md)
//   MODE=touch  eine 4H-Kerze läuft bis auf 1 % an die gebrochene 4H-Marke zurück,
//               Kauf zur nächsten 4H-Kerze
//   MODE=limit  Limit-Kauf auf der gebrochenen 4H-Marke (ab der Kerze, zu der live gekauft würde)
//   MODE=tw     4H-Trendwechsel: nach dem Signal tieferes 4H-Tief (neue 4H-Marke, 4H rot),
//               kein 4H-Tief unter dem Daily-Low des Bruchs (DL=signal: Tageskerze des
//               Signaltags, DL=breakout: Tageskerze des Daily-Ausbruchs); Kauf, wenn ein
//               4H-Schluss über dem letzten Hoch des Retracements (neue 4H-Marke) liegt
//   MODE=re     Signal wie live, aufgeteilt nach Muster (AVGO 05.06.2024): vorher 3/3 grün,
//               dann 4H rot (Retracement, höchstens MAXRED 4H-Kerzen), Tief des Retracements
//               über dem Daily-Swing-Tief vor dem Daily-Ausbruch, dann 4H wieder grün.
//               FILTER=re (nur Muster) | other (nur der Rest) | all; STOP=d (Engine) | h4
//               (Retracement-Tief × 0,99, 4H-Prüfung)
//   MODE=wm     Signal wie live, Weekly zählt aber auch als grün, wenn die aktuelle
//               Weekly-Marke noch offen ist, der vorherige Weekly-Bruch stattfand (höchstens
//               WMWEEKS Wochen her) und die Daily-Marke über diesem Weekly-Bruch liegt
//               (Beispiel AVGO 12.09.2024). STOP=d (Engine) | h4 (letztes 4H-Swing-Tief)
//   MODE=pb     Schluss mind. PB % unter dem höchsten Schluss seit dem Signal, danach
//               4H-Schluss über dem Hoch der Vorkerze → Kauf zur nächsten 4H-Kerze
// Stopp: tiefstes 4H-Tief seit dem Signal × 0,99 (now: letztes 4H-Swing-Tief × 0,99),
// geprüft an jedem 4H-Schluss. Tagesstruktur-Ausstieg und Zeitstopp wie die Engine.
// Abbruch: Schluss unter dem 4H-Stopp zum Signalzeitpunkt oder nach WAIT 4H-Kerzen.
// Aufruf: MODE=pb PB=3 WAIT=20 node research/retrace_entry_study.js
const fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
const MODE = process.env.MODE || 'now';
const PB = +(process.env.PB || 3) / 100;
const WAIT = +(process.env.WAIT || 20);
const DL = process.env.DL || 'signal';
const FILTER = process.env.FILTER || 'all', STOP = process.env.STOP || 'd';
const MAXRED = +(process.env.MAXRED || 60);
const WMWEEKS = +(process.env.WMWEEKS || 52);
const wmTrades = [];
const stats = { signals: 0, entered: 0, cancelled: 0, expired: 0, noLevel: 0, noRetrace: 0, re: 0, other: 0 };

const src = fs.readFileSync(path.join(ROOT, 'backtest_ndx.js'), 'utf8')
  .replace("const ROOT = __dirname;", `const ROOT = ${JSON.stringify(ROOT)};`)
  .replace("require('./backtest_kpis')", `require(${JSON.stringify(ROOT + '/backtest_kpis')})`)
  .replace("require('./backtest_history/portfolio')", `require(${JSON.stringify(ROOT + '/backtest_history/portfolio')})`)
  .replace("for (const tr of simulateTradesPIT(", "for (const tr of globalThis.__sim(")
  .replace("if (require.main === module) main();", "main(); globalThis.__report();");

// Kaufkerze wie live: Signal in den Kerzen 10–14/14–18 Uhr → nächste 4H-Kerze am selben
// Tag, sonst die erste Kerze des nächsten Handelstages
function buyBar(h, j) {
  const day = h[j].d.slice(0, 10);
  let k = j + 1;
  if (!(h4Block(h[j].d) <= 1 && h[k] && h[k].d.slice(0, 10) === day)) {
    while (k < h.length && h[k].d.slice(0, 10) <= day) k++;
  }
  return k < h.length ? k : -1;
}

// Tageskerzen, wie sie zum Schluss der 4H-Kerze j vorlagen (wie simulateTradesPIT)
function dHistoryAt(h, j, ohlcv_d, dIdx) {
  const bar = h[j], day = bar.d.slice(0, 10), i = dIdx.get(day);
  if (i == null) return null;
  const blk = h4Block(bar.d);
  if (blk === 0) return ohlcv_d.slice(0, i);
  if (blk === 1) {
    const db = ohlcv_d[i];
    return ohlcv_d.slice(0, i).concat([{ d: day, o: db.o, h: Math.max(db.o, bar.h), l: Math.min(db.o, bar.l), c: bar.c }]);
  }
  return ohlcv_d.slice(0, i + 1);
}

// Muster: 3/3 grün → 4H rot (Retracement) über dem Daily-Swing-Tief → 4H grün in Kerze j.
// Liefert die erste rote Kerze r oder -1
function retraceStart(h, j, { p4, ohlcv_w, ohlcv_d, dIdx }) {
  let r = j - 1;
  while (r > 0 && p4[r - 1] === 0) r--;
  if (p4[r - 1] !== 1 || j - r > MAXRED) return -1;
  const dh = dHistoryAt(h, r - 1, ohlcv_d, dIdx);
  if (!dh || dh.length < 30) return -1;
  const sd = analyzeStructure(dh);
  if (!sd?.broken || !analyzeWeeklyStructure(weeklyUpTo(ohlcv_w, dh), dh)?.broken) return -1;
  const dailyLow = recentSwingLowOf(dh.slice(0, sd.breakoutIdx));
  return dailyLow != null && lowest(h, r, j) >= dailyLow ? r : -1;
}

// Vorheriger Weekly-Bruch gilt weiter: Bruch höchstens WMWEEKS Wochen her, Daily-Marke darüber
function weeklyMemory(sw, sd, nW) {
  if (!sw?.prevGwswHigh || sw.prevBreakoutIdx == null || !sd?.gwsdHigh) return false;
  return nW - 1 - sw.prevBreakoutIdx <= WMWEEKS && sd.gwsdHigh.price > sw.prevGwswHigh.price;
}

function lowest(h, a, b) {
  let m = Infinity;
  for (let i = a; i <= b; i++) m = Math.min(m, h[i].l);
  return m;
}

// Trade ab 4H-Kerze hStart (Kauf zu entryPrice), Stopp an jedem 4H-Schluss ab hStart
function tradeH4(ohlcv_d, h, hStart, entryPrice, stopPrice, extra) {
  const entryDay = h[hStart].d.slice(0, 10);
  const idx = ohlcv_d.findIndex(b => b.d >= entryDay);
  if (idx < 0 || !(entryPrice > stopPrice)) return null;
  let shares = Math.floor(MAX_RISK / (entryPrice - stopPrice));
  if (shares * entryPrice > CAPITAL) shares = Math.floor(CAPITAL / entryPrice);
  if (shares <= 0) return null;
  const entry = { ...extra, trigger: '4H', entryDate: ohlcv_d[idx].d, entryTime: h[hStart].d.slice(11, 16),
                  entryPrice, stopPrice, shares, invested: shares * entryPrice, riskAmount: shares * (entryPrice - stopPrice) };
  const weeks = d => Math.round((new Date(d) - new Date(entry.entryDate)) / (7 * 864e5));
  const done = (exitDate, exitPrice, isOpen = false) => {
    const pnl = (exitPrice - entryPrice) * shares;
    return { ...entry, exitDate, exitPrice, pnl, pnlPct: (exitPrice / entryPrice - 1) * 100,
             isWin: pnl > 0, isOpen, holdingWeeks: weeks(exitDate) };
  };
  let hj = hStart;
  for (let k = idx; k < ohlcv_d.length; k++) {
    const day = ohlcv_d[k].d;
    for (; hj < h.length && h[hj].d.slice(0, 10) <= day; hj++) {
      if (h[hj].d.slice(0, 10) < day || h[hj].c >= stopPrice) continue;
      const nx = h[hj + 1];
      return nx ? done(nx.d.slice(0, 10), nx.o) : done(day, h[hj].c);
    }
    if (!isExitDay(ohlcv_d, k, null, entry)) continue;
    const next = ohlcv_d[k + 1];
    return done(next ? next.d : day, next ? next.o : ohlcv_d[k].c);
  }
  const last = ohlcv_d[ohlcv_d.length - 1];
  return done(last.d, last.c, true);
}

// Rücksetzer nach dem Signal in Kerze j suchen → { hStart, entryPrice, stopPrice } oder null
function findEntry(h, j, ctx) {
  const k0 = buyBar(h, j);
  if (k0 < 0) return null;
  if (MODE === 'tw') return findTrendChangeEntry(h, j, ctx);
  if (MODE === 'wm') {
    if (STOP === 'd') return { hStart: k0, entryPrice: h[k0].o, daily: true };
    const sl = recentSwingLowOf(h.slice(0, k0));
    return sl == null ? null : { hStart: k0, entryPrice: h[k0].o, stopPrice: sl * 0.99 };
  }
  if (MODE === 're') {
    const r = retraceStart(h, j, ctx);
    stats[r >= 0 ? 're' : 'other']++;
    if ((FILTER === 're' && r < 0) || (FILTER === 'other' && r >= 0)) return null;
    if (STOP === 'd') return { hStart: k0, entryPrice: h[k0].o, daily: true };
    const sl = r >= 0 ? lowest(h, r, j) : recentSwingLowOf(h.slice(0, k0));
    return sl == null ? null : { hStart: k0, entryPrice: h[k0].o, stopPrice: sl * 0.99 };
  }
  if (MODE === 'now') {
    const sl = recentSwingLowOf(h.slice(0, k0));
    return sl == null ? null : { hStart: k0, entryPrice: h[k0].o, stopPrice: sl * 0.99 };
  }
  const sl0 = recentSwingLowOf(h.slice(0, j + 1));
  if (sl0 == null) return null;
  const stop0 = sl0 * 0.99;
  let level = null;
  if (MODE === 'touch' || MODE === 'limit') {
    level = analyze4HStructure(h.slice(Math.max(0, j - 59), j + 1))?.gws4hHigh?.price ?? null;
    if (level == null) { stats.noLevel++; return null; }
  }
  let hiC = h[j].c, pulled = false;
  const end = Math.min(h.length - 1, j + WAIT);
  for (let m = j + 1; m <= end; m++) {
    const bar = h[m];
    if (MODE === 'limit' && m >= k0 && bar.l <= level) {
      const fill = Math.min(bar.o, level);
      return { hStart: m, entryPrice: fill, stopPrice: Math.min(lowest(h, j, m - 1), fill) * 0.99 };
    }
    if (bar.c < stop0) { stats.cancelled++; return null; }
    let trig = false;
    if (MODE === 'touch') trig = bar.l <= level * 1.01;
    if (MODE === 'pb') {
      if (bar.c <= hiC * (1 - PB)) pulled = true;
      trig = pulled && bar.c > h[m - 1].h;
      hiC = Math.max(hiC, bar.c);
    }
    if (!trig) continue;
    const k = buyBar(h, m);
    if (k < 0) return null;
    return { hStart: k, entryPrice: h[k].o, stopPrice: lowest(h, j, m) * 0.99 };
  }
  stats.expired++;
  return null;
}

// Trendwechsel-Retracement: 4H rot (tieferes Tief) und wieder grün, über dem Daily-Low
function findTrendChangeEntry(h, j, { p4, ohlcv_d, dIdx, dHistory }) {
  const day = h[j].d.slice(0, 10);
  let dailyLow = ohlcv_d[dIdx.get(day)].l;
  if (DL === 'breakout') {
    const bi = analyzeStructure(dHistory)?.breakoutIdx;
    const bDay = bi != null ? dHistory[bi].d : null;
    if (bDay == null || !dIdx.has(bDay)) return null;
    dailyLow = ohlcv_d[dIdx.get(bDay)].l;
  }
  const end = Math.min(h.length - 1, j + WAIT);
  let down = false;
  for (let m = j + 1; m <= end; m++) {
    if (h[m].l < dailyLow) { stats.cancelled++; return { resolved: m }; }
    if (p4[m] === 0) { down = true; continue; }
    if (!down || p4[m - 1] !== 0) continue;
    const k = buyBar(h, m);
    if (k < 0) return { resolved: m };
    return { resolved: m, hStart: k, entryPrice: h[k].o, stopPrice: lowest(h, j, m) * 0.99 };
  }
  stats[down ? 'expired' : 'noRetrace']++;
  return { resolved: end };
}

globalThis.__sim = (ohlcv_w, ohlcv_d, h, inTop, start = PIT_START) => {
  const trades = [];
  const dIdx = new Map(ohlcv_d.map((b, i) => [b.d, i]));
  const first = Math.max(8, h.findIndex(b => b.d.slice(0, 10) >= start) - 1);
  if (first < 8 || h.length < 10) return trades;
  const p4 = new Array(h.length).fill(null);
  for (let j = first; j < h.length; j++) {
    p4[j] = analyze4HStructure(h.slice(Math.max(0, j - 59), j + 1))?.broken4h ? 1 : 0;
  }
  let busyUntil = '', pendingUntil = -1;
  for (let j = first + 1; j < h.length; j++) {
    if (p4[j - 1] !== 0 || p4[j] !== 1 || j <= pendingUntil) continue;
    const bar = h[j], day = bar.d.slice(0, 10);
    if (day < start || day < busyUntil || (inTop && !inTop(day))) continue;
    const i = dIdx.get(day);
    if (i == null) continue;
    const blk = h4Block(bar.d);
    let dHistory;
    if (blk === 0) dHistory = ohlcv_d.slice(0, i);
    else if (blk === 1) {
      const db = ohlcv_d[i];
      dHistory = ohlcv_d.slice(0, i).concat([{ d: day, o: db.o, h: Math.max(db.o, bar.h), l: Math.min(db.o, bar.l), c: bar.c }]);
    } else dHistory = ohlcv_d.slice(0, i + 1);
    if (dHistory.length < 30) continue;
    const sd = analyzeStructure(dHistory);
    if (!sd?.broken) continue;
    const wBars = weeklyUpTo(ohlcv_w, dHistory);
    const sw = analyzeWeeklyStructure(wBars, dHistory);
    const wmExtra = MODE === 'wm' && !sw?.broken && weeklyMemory(sw, sd, wBars.length);
    if (!sw?.broken && !wmExtra) continue;
    stats.signals++;
    const e = findEntry(h, j, { p4, ohlcv_w, ohlcv_d, dIdx, dHistory });
    if (e?.resolved != null) pendingUntil = e.resolved;
    if (!e || e.hStart == null) continue;
    const wk = ohlcv_w.find(w => weekOfBar(w.d) === mondayOf(day));
    const extra = { signalBar: bar.d, signalDate: day, weeklyDate: wk ? wk.d : mondayOf(day) };
    const t = e.daily
      ? tradeFromEntry(ohlcv_d, h[e.hStart].d.slice(0, 10), e.entryPrice, { ...extra, entryTime: h[e.hStart].d.slice(11, 16) })
      : tradeH4(ohlcv_d, h, e.hStart, e.entryPrice, e.stopPrice, extra);
    if (!t) continue;
    if (wmExtra) wmTrades.push(t);
    stats.entered++;
    trades.push(t);
    busyUntil = t.exitDate;
  }
  return trades;
};

globalThis.__report = () => {
  const r = JSON.parse(fs.readFileSync(process.env.BACKTEST_NDX_OUT, 'utf8'));
  const T = r.trades, cl = T.filter(t => !t.isOpen), w = cl.filter(t => t.pnl > 0), l = cl.filter(t => t.pnl <= 0);
  const avg = (a, f) => a.reduce((s, t) => s + f(t), 0) / (a.length || 1);
  const dist = T.map(t => (t.entryPrice - t.stopPrice) / t.entryPrice * 100).sort((a, b) => a - b);
  const grow = (a, b) => { let f = 1; for (let y = a; y <= b; y++) f *= 1 + (r.years[y]?.returnPct ?? 0) / 100; return f.toFixed(2); };
  const wmPf = (() => {
    const sum = a => a.reduce((x, t) => x + t.pnl, 0);
    const lo = sum(wmTrades.filter(t => t.pnl <= 0));
    return { n: wmTrades.length, pf: lo < 0 ? +Math.abs(sum(wmTrades.filter(t => t.pnl > 0)) / lo).toFixed(2) : null,
             avgPct: +(wmTrades.reduce((x, t) => x + t.pnlPct, 0) / (wmTrades.length || 1)).toFixed(2) };
  })();
  console.log(JSON.stringify({ wmExtra: MODE === 'wm' ? wmPf : undefined, wmWeeks: MODE === 'wm' ? WMWEEKS : undefined, mode: MODE, pb: MODE === 'pb' ? PB * 100 : undefined, wait: MODE === 'now' ? undefined : WAIT, dl: MODE === 'tw' ? DL : undefined, filter: MODE === 're' ? FILTER : undefined, stop: ['re', 'wm'].includes(MODE) ? STOP : undefined, maxRed: MODE === 're' ? MAXRED : undefined,
    ...stats, depot: r.depot.endEquity, cagr: r.depot.cagr, pf: r.depot.profitFactor, maxDD: r.depot.maxDD,
    depotTrades: T.filter(t => t.depot).length, winrate: +(w.length / cl.length * 100).toFixed(1),
    avgWin: +avg(w, t => t.pnlPct).toFixed(1), avgLoss: +avg(l, t => t.pnlPct).toFixed(1),
    stopDistMedian: +dist[dist.length >> 1].toFixed(1), g1620: grow(2016, 2020), g2125: grow(2021, 2025),
    years: Object.fromEntries(Object.entries(r.years).map(([y, v]) => [y, v.returnPct])) }));
};

process.env.BACKTEST_NDX_OUT = process.env.BACKTEST_NDX_OUT
  || path.join(require('os').tmpdir(), `retrace_${MODE}_${PB * 100}_${WAIT}_${DL}_${FILTER}_${STOP}_${MAXRED}_${WMWEEKS}.json`);
eval(src.replace(/^#!.*\n/, ''));
