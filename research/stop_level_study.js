// Studie 10/2026: Stopp-Ebene Daily vs. 4H (Ergebnis: research/STOP_LEVEL.md).
// Aufruf: SL_LEVEL=d|h4 SL_CHECK=d|h4 node research/stop_level_study.js
//   SL_LEVEL: Stoppkurs aus dem letzten Swing-Tief der Tages- (d) oder 4H-Kerzen (h4) × 0,99
//   SL_CHECK: Stopp geprüft zum Tagesschluss (d) oder an jedem 4H-Schluss (h4, Verkauf zur nächsten 4H-Kerze)
// Unverändert: Einstieg, Tagesstruktur-Ausstieg, Zeitstopp, Positionsgröße, Depot.
const fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
const LEVEL = process.env.SL_LEVEL || 'd', CHECK = process.env.SL_CHECK || 'd';
const src = fs.readFileSync(path.join(ROOT, 'backtest_ndx.js'), 'utf8')
  .replace("const ROOT = __dirname;", `const ROOT = ${JSON.stringify(ROOT)};`)
  .replace("require('./backtest_kpis')", `require(${JSON.stringify(ROOT + '/backtest_kpis')})`)
  .replace("require('./backtest_history/portfolio')", `require(${JSON.stringify(ROOT + '/backtest_history/portfolio')})`)
  .replace("globalThis.__e = {", "globalThis.__e = { tradeFromEntryOrig: tradeFromEntry, recentSwingLowOf, isExitDay,")
  .replace("const { simulateTradesPIT,", "globalThis.__patch(); const { simulateTradesPIT,")
  .replace("for (const tr of simulateTradesPIT(", "globalThis.__H4 = series.ohlcv_4h; for (const tr of simulateTradesPIT(")
  .replace("if (require.main === module) main();", "main();");

globalThis.__patch = () => {
  if (LEVEL === 'd' && CHECK === 'd' && !process.env.FORCE) return;              // Basis = Engine unverändert
  const { recentSwingLowOf, isExitDay } = globalThis.__e;
  globalThis.tradeFromEntry = function (ohlcv_d, entryDate, entryPrice, extra) {
    const h = globalThis.__H4;
    const idx = ohlcv_d.findIndex(b => b.d >= entryDate);
    if (idx < 0) return null;
    // Einstiegskerze (4H) über Datum + Uhrzeit
    const hEntry = h.findIndex(b => b.d.slice(0, 10) === entryDate && b.d.slice(11, 16) === extra.entryTime);
    if (hEntry < 0) return null;
    const swingLow = LEVEL === 'h4' ? recentSwingLowOf(h.slice(0, hEntry)) : recentSwingLowOf(ohlcv_d.slice(0, idx));
    const stopPrice = swingLow != null ? swingLow * 0.99 : null;
    if (!entryPrice || !stopPrice || entryPrice <= stopPrice) return null;
    let shares = Math.floor(MAX_RISK / (entryPrice - stopPrice));
    if (shares * entryPrice > CAPITAL) shares = Math.floor(CAPITAL / entryPrice);
    if (shares <= 0) return null;
    const entry = { ...extra, trigger: '4H', entryDate: ohlcv_d[idx].d, entryPrice, stopPrice, shares,
                    invested: shares * entryPrice, riskAmount: shares * (entryPrice - stopPrice) };
    const weeks = d => Math.round((new Date(d) - new Date(entry.entryDate)) / (7 * 864e5));
    const done = (exitDate, exitPrice, reason, isOpen = false) => {
      const pnl = (exitPrice - entryPrice) * shares;
      return { ...entry, exitDate, exitPrice, pnl, pnlPct: (exitPrice / entryPrice - 1) * 100,
               isWin: pnl > 0, isOpen, holdingWeeks: weeks(exitDate), exitReason: reason };
    };
    let hj = hEntry;
    for (let k = idx; k < ohlcv_d.length; k++) {
      const day = ohlcv_d[k].d;
      // 4H-Prüfung: Schluss jeder 4H-Kerze dieses Tages unter dem Stopp → nächste 4H-Eröffnung
      if (CHECK === 'h4') {
        for (; hj < h.length && h[hj].d.slice(0, 10) <= day; hj++) {
          if (h[hj].d.slice(0, 10) < day) continue;
          if (h[hj].c < stopPrice) {
            const nx = h[hj + 1];
            if (!nx) return done(day, h[hj].c, 'stop4h');
            return done(nx.d.slice(0, 10), nx.o, 'stop4h');
          }
        }
      }
      // Tagesschluss: Struktur + Zeitstopp (immer), Stopp nur bei Tagesprüfung
      if (!isExitDay(ohlcv_d, k, CHECK === 'd' ? stopPrice : null, entry)) continue;
      const next = ohlcv_d[k + 1];
      return done(next ? next.d : day, next ? next.o : ohlcv_d[k].c, 'daily');
    }
    const last = ohlcv_d[ohlcv_d.length - 1];
    return done(last.d, last.c, 'open', true);
  };
};
process.env.BACKTEST_NDX_OUT = process.env.BACKTEST_NDX_OUT || path.join(require('os').tmpdir(), `stop_level_${LEVEL}_${CHECK}.json`);
eval(src.replace(/^#!.*\n/, ''));
