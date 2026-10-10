// ── Gemeinsame Backtest-Logik für backtest.html und backtest_overview.html ────────

const CAPITAL  = 10000;
const MAX_RISK = 1000;
// Zeitstopp: Liegt der Schlusskurs 10 Handelstage nach dem Einstieg nicht
// mindestens 5 % über dem Einstiegskurs, wird zur nächsten Eröffnung verkauft
// (Studie 10/2026 über alle Alpaca-Signale seit 2016: PF 2,60 → 3,23).
const TIME_STOP_DAYS = 10;
const TIME_STOP_MIN  = 0.05;

// ── GWS-D Analyse ────────────────────────────────────────────────────────────────
function analyzeStructure(ohlcv) {
  if (!ohlcv || ohlcv.length < 30) return null;
  const n      = ohlcv.length;
  const highs  = ohlcv.map(d => d.h);
  const lows   = ohlcv.map(d => d.l);
  const closes = ohlcv.map(d => d.c);

  const swingHighs = [];
  for (let i = 2; i < n - 2; i++) {
    if (highs[i] >= highs[i-1] && highs[i] >= highs[i-2] &&
        highs[i] >= highs[i+1] && highs[i] >= highs[i+2])
      swingHighs.push({ idx: i, date: ohlcv[i].d, price: highs[i] });
  }

  const swingLows = [];
  for (let i = 2; i < n - 2; i++) {
    if (lows[i] <= lows[i-1] && lows[i] <= lows[i-2] &&
        lows[i] <= lows[i+1] && lows[i] <= lows[i+2])
      swingLows.push({ idx: i, date: ohlcv[i].d, price: lows[i] });
  }

  const gwsdCandidates = [];
  for (let j = 1; j < swingLows.length; j++) {
    const tiefNeu = swingLows[j];
    const tiefAlt = swingLows[j - 1];
    if (tiefNeu.price < tiefAlt.price) {
      const hochsDazwischen = swingHighs.filter(
        sh => sh.idx > tiefAlt.idx && sh.idx < tiefNeu.idx
      );
      if (hochsDazwischen.length > 0) {
        const gwsdHoch = hochsDazwischen.reduce((best, h) => h.price > best.price ? h : best);
        gwsdCandidates.push({
          idx: gwsdHoch.idx, date: gwsdHoch.date, price: gwsdHoch.price,
          tiefAlt, tiefNeu,
        });
      }
    }
  }

  const gwsdHigh     = gwsdCandidates.length > 0 ? gwsdCandidates[gwsdCandidates.length - 1] : null;
  const prevGwsdHigh = gwsdCandidates.length > 1 ? gwsdCandidates[gwsdCandidates.length - 2] : null;
  const breakoutPrice = gwsdHigh ? gwsdHigh.price : null;

  let breakoutIdx = null;
  if (gwsdHigh) {
    for (let i = gwsdHigh.idx + 1; i < n; i++) {
      if (closes[i] > gwsdHigh.price) { breakoutIdx = i; break; }
    }
  }

  let prevBreakoutIdx = null;
  if (prevGwsdHigh) {
    for (let i = prevGwsdHigh.idx + 1; i < n; i++) {
      if (closes[i] > prevGwsdHigh.price) { prevBreakoutIdx = i; break; }
    }
  }

  let trend = "neutral";
  if (swingHighs.length >= 2) {
    const last = swingHighs[swingHighs.length - 1];
    const prev = swingHighs[swingHighs.length - 2];
    if (last.price > prev.price) trend = "bullish";
    else if (last.price < prev.price) trend = "bearish";
  }

  const broken       = gwsdHigh !== null && breakoutIdx !== null;
  const currentClose = closes[n - 1];
  const recentBreakout = broken && (n - 1 - breakoutIdx <= 7);

  return {
    currentClose, gwsdHigh, breakoutIdx, breakoutPrice, broken, trend,
    prevGwsdHigh, prevBreakoutIdx, recentBreakout,
    swingHighs: swingHighs.slice(-6),
    swingLows:  swingLows.slice(-6),
    setup: broken && trend !== "bearish",
  };
}

// ── GWS-W Analyse (Weekly) ────────────────────────────────────────────────────────
function analyzeWeeklyStructure(ohlcvW, ohlcvD = null) {
  if (!ohlcvW || ohlcvW.length < 15) return null;
  const n      = ohlcvW.length;
  const highs  = ohlcvW.map(d => d.h);
  const lows   = ohlcvW.map(d => d.l);
  const closes = ohlcvW.map(d => d.c);

  // ±1 Bar für Weekly (±2 ist zu streng, übersieht valide Swing-Hochs wie SNDK Feb 2)
  const swingHighs = [];
  for (let i = 1; i < n - 1; i++) {
    if (highs[i] >= highs[i-1] && highs[i] >= highs[i+1])
      swingHighs.push({ idx: i, date: ohlcvW[i].d, price: highs[i] });
  }

  const swingLows = [];
  for (let i = 1; i < n - 1; i++) {
    if (lows[i] <= lows[i-1] && lows[i] <= lows[i+1])
      swingLows.push({ idx: i, date: ohlcvW[i].d, price: lows[i] });
  }

  const gwswCandidates = [];
  let lastGwswDefLow = null;
  for (let j = 1; j < swingLows.length; j++) {
    const tiefNeu = swingLows[j];
    const tiefAlt = swingLows[j - 1];
    // Wie live (gws_core.py, rs_charts.js): jedes tiefere Tief bildet eine neue Marke
    if (tiefNeu.price < tiefAlt.price) {
      const hochsDazwischen = swingHighs.filter(
        sh => sh.idx > tiefAlt.idx && sh.idx < tiefNeu.idx
      );
      if (hochsDazwischen.length > 0) {
        const gwswHoch = hochsDazwischen.reduce((best, h) => h.price > best.price ? h : best);
        gwswCandidates.push({ idx: gwswHoch.idx, date: gwswHoch.date, price: gwswHoch.price });
        lastGwswDefLow = tiefNeu;
      }
    }
  }

  const gwswHigh     = gwswCandidates.length > 0 ? gwswCandidates[gwswCandidates.length - 1] : null;
  const prevGwswHigh = gwswCandidates.length > 1 ? gwswCandidates[gwswCandidates.length - 2] : null;

  let breakoutPrice = gwswHigh ? gwswHigh.price : null;
  let breakoutIdx = null;
  if (gwswHigh) {
    for (let i = gwswHigh.idx + 1; i < n; i++) {
      if (closes[i] > gwswHigh.price) { breakoutIdx = i; break; }
    }
  }

  let prevBreakoutIdx = null;
  if (prevGwswHigh) {
    for (let i = prevGwswHigh.idx + 1; i < n; i++) {
      if (closes[i] > prevGwswHigh.price) { prevBreakoutIdx = i; break; }
    }
  }

  let trend = "neutral";
  if (swingHighs.length >= 2) {
    const last = swingHighs[swingHighs.length - 1];
    const prev = swingHighs[swingHighs.length - 2];
    if (last.price > prev.price) trend = "bullish";
    else if (last.price < prev.price) trend = "bearish";
  }

  const hasDailyCandles = Array.isArray(ohlcvD) && ohlcvD.length > 0;
  const broken = gwswHigh !== null && (hasDailyCandles
    ? ohlcvD.some(d => d.d > gwswHigh.date && d.c > gwswHigh.price)
    : breakoutIdx !== null);
  const recentBreakout = breakoutIdx !== null && (n - 1 - breakoutIdx <= 1);

  return {
    gwswHigh, breakoutIdx, breakoutPrice, broken,
    prevGwswHigh, prevBreakoutIdx, recentBreakout,
    swingHighs: swingHighs.slice(-6),
    swingLows:  swingLows.slice(-6),
  };
}

// ── GWS-4H Analyse ────────────────────────────────────────────────────────────────
function analyze4HStructure(ohlcv4h) {
  if (!ohlcv4h || ohlcv4h.length < 8) return null;
  const n     = ohlcv4h.length;
  const highs = ohlcv4h.map(d => d.h);
  const lows  = ohlcv4h.map(d => d.l);
  const closes= ohlcv4h.map(d => d.c);

  const swingHighs = [];
  for (let i = 2; i < n - 2; i++) {
    if (highs[i] >= highs[i-1] && highs[i] >= highs[i-2] &&
        highs[i] >= highs[i+1] && highs[i] >= highs[i+2])
      swingHighs.push({ idx: i, date: ohlcv4h[i].d, price: highs[i] });
  }

  const swingLows = [];
  for (let i = 2; i < n - 2; i++) {
    if (lows[i] <= lows[i-1] && lows[i] <= lows[i-2] &&
        lows[i] <= lows[i+1] && lows[i] <= lows[i+2])
      swingLows.push({ idx: i, date: ohlcv4h[i].d, price: lows[i] });
  }

  const gws4hCandidates = [];
  let lastGws4hDefLow = null;
  for (let j = 1; j < swingLows.length; j++) {
    const tiefNeu = swingLows[j];
    const tiefAlt = swingLows[j - 1];
    // Wie live (gws_core.py, rs_charts.js): jedes tiefere Tief bildet eine neue Marke
    if (tiefNeu.price < tiefAlt.price) {
      const hochsDazwischen = swingHighs.filter(
        sh => sh.idx > tiefAlt.idx && sh.idx < tiefNeu.idx
      );
      if (hochsDazwischen.length > 0) {
        const gws4hHoch = hochsDazwischen.reduce((best, h) => h.price > best.price ? h : best);
        gws4hCandidates.push({ idx: gws4hHoch.idx, date: gws4hHoch.date, price: gws4hHoch.price });
        lastGws4hDefLow = tiefNeu;
      }
    }
  }

  const gws4hHigh     = gws4hCandidates.length > 0 ? gws4hCandidates[gws4hCandidates.length - 1] : null;
  const prevGws4hHigh = gws4hCandidates.length > 1 ? gws4hCandidates[gws4hCandidates.length - 2] : null;

  let breakout4hIdx = null;
  if (gws4hHigh) {
    for (let i = gws4hHigh.idx + 1; i < n; i++) {
      if (closes[i] > gws4hHigh.price) { breakout4hIdx = i; break; }
    }
  }

  let prevBreakout4hIdx = null;
  if (prevGws4hHigh) {
    for (let i = prevGws4hHigh.idx + 1; i < n; i++) {
      if (closes[i] > prevGws4hHigh.price) { prevBreakout4hIdx = i; break; }
    }
  }

  let trend4h = "neutral";
  if (swingHighs.length >= 2) {
    const last4h = swingHighs[swingHighs.length - 1];
    const prev4h = swingHighs[swingHighs.length - 2];
    if (last4h.price > prev4h.price) trend4h = "bullish";
    else if (last4h.price < prev4h.price) trend4h = "bearish";
  }

  const recentBreakout = breakout4hIdx !== null && (() => {
    const breakoutDate = new Date(ohlcv4h[breakout4hIdx].d.replace(' ', 'T'));
    const lastDate     = new Date(ohlcv4h[n - 1].d.replace(' ', 'T'));
    return (lastDate - breakoutDate) / (1000 * 60 * 60 * 24) <= 7;
  })();

  return {
    gws4hHigh, breakout4hIdx, broken4h: gws4hHigh === null || breakout4hIdx !== null,
    prevGws4hHigh, prevBreakout4hIdx, recentBreakout,
    tiefNeu: lastGws4hDefLow,
    swingHighs: swingHighs.slice(-8),
    swingLows:  swingLows.slice(-8),
  };
}

// ── Hilfsfunktionen ───────────────────────────────────────────────────────────────
function isoWeek(dateStr) {
  const d = new Date(dateStr + 'T12:00:00Z');
  const jan4 = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
  const startW1 = new Date(jan4);
  startW1.setUTCDate(jan4.getUTCDate() - ((jan4.getUTCDay() + 6) % 7));
  const wn = Math.round((d - startW1) / 604800000) + 1;
  return { kw: wn, year: d.getUTCFullYear() };
}

function getWeekEnd(weekStartStr) {
  const d = new Date(weekStartStr + 'T12:00:00Z');
  d.setUTCDate(d.getUTCDate() + 6);
  return d.toISOString().slice(0, 10);
}

// ── Wochen-Rows vorberechnen ──────────────────────────────────────────────────────
// from/to (optional): nur die Wochen mit diesem Index berechnen — die Schnitte
// davor bleiben vollständig (so lassen sich nur die Wochen um einen Trade rechnen).
function buildWeekRows(ohlcv_w, ohlcv_d, ohlcv_4h, from = 0, to = ohlcv_w.length - 1) {
  return ohlcv_w.slice(from, to + 1).map((week, k) => {
    const i = from + k;
    const weekEnd  = getWeekEnd(week.d);
    const wSlice   = ohlcv_w.slice(Math.max(0, i - 59), i + 1);
    const dHistory = ohlcv_d.filter(d => d.d <= weekEnd);
    const dSlice   = dHistory.slice(-60);
    const h4Slice  = ohlcv_4h.filter(d => d.d.slice(0,10) <= weekEnd).slice(-60);
    const structW     = analyzeWeeklyStructure(wSlice, dHistory);
    const structD     = analyzeStructure(dSlice);
    const structDFull = analyzeStructure(dHistory);
    const has4h    = h4Slice.length >= 8;
    const struct4H = has4h ? analyze4HStructure(h4Slice) : null;
    const pW  = structW?.broken              ? 1 : 0;
    const pD  = structDFull?.broken          ? 1 : 0;
    const p4H = (has4h && struct4H?.broken4h) ? 1 : 0;
    const pts = pW + pD + (has4h ? p4H : 0);
    const { kw, year } = isoWeek(week.d);
    return { week, i, weekEnd, kw, year, wSlice, dSlice, dHistory, h4Slice, structW, structD, structDFull, struct4H, pW, pD, p4H, has4h, pts };
  });
}

// ── Stopp und Ausstieg (gemeinsam für simulateTrades und simulateFromEntry) ────
// Letztes Swing-Tief (von beiden Nachbartagen nicht unterboten) der Tageskerzen
// vor dem Einstieg; sonst das Minimum der letzten fünf Kerzen.
function recentSwingLowOf(barsBeforeEntry) {
  for (let k = barsBeforeEntry.length - 2; k >= 1; k--) {
    if (barsBeforeEntry[k].l <= barsBeforeEntry[k-1].l && barsBeforeEntry[k].l <= barsBeforeEntry[k+1].l)
      return barsBeforeEntry[k].l;
  }
  return barsBeforeEntry.length > 0 ? Math.min(...barsBeforeEntry.slice(-5).map(d => d.l)) : null;
}

// Ausstiegssignal am Tagesschluss von dHistory[k]: GWS-D-Struktur (aus den
// Kerzen davor) intakt und Schluss unter dem letzten Swing-Tief, oder Schluss
// unter dem Stopp. Ausführung am nächsten Handelstag zur Eröffnung.
function isExitDay(dHistory, k, stopPrice, entry = null) {
  const day = dHistory[k];
  if (entry && isTimeStop(dHistory, k, entry)) return true;
  const structBefore = analyzeStructure(dHistory.slice(0, k));
  if (structBefore && !structBefore.broken) {
    const swingLows = structBefore.swingLows ?? [];
    const lastSL    = swingLows.length > 0 ? swingLows[swingLows.length - 1] : null;
    if (lastSL != null && day.c < lastSL.price) return true;
  }
  return stopPrice != null && day.c < stopPrice;
}

// Zeitstopp am Tagesschluss von dHistory[k] (Handelstage ab dem Einstiegstag gezählt)
const _entryIdxCache = new WeakMap();
function isTimeStop(dHistory, k, entry) {
  // dHistory beginnt immer mit derselben ersten Tageskerze — der Index bleibt gleich
  if (!_entryIdxCache.has(entry)) _entryIdxCache.set(entry, dHistory.findIndex(d => d.d >= entry.entryDate));
  const idx = _entryIdxCache.get(entry);
  return idx >= 0 && k - idx === TIME_STOP_DAYS
    && dHistory[k].c < entry.entryPrice * (1 + TIME_STOP_MIN);
}

// Ein Trade ab festem Einstiegstag (z. B. ein verschickter Live-Alert): Kauf zur
// Eröffnung, Stopp und Ausstieg exakt wie in simulateTrades, gleiche
// Positionsgröße (CAPITAL, max. MAX_RISK Risiko). null, wenn kein gültiger Einstieg.
// entryPriceOverride: Kauf im Tagesverlauf (4H-Prüfjob) statt zur Eröffnung.
function simulateFromEntry(ohlcv_d, entryDate, entryPriceOverride = null) {
  const entryIdx = ohlcv_d.findIndex(d => d.d >= entryDate);
  if (entryIdx < 0) return null;
  const entryBar = ohlcv_d[entryIdx];
  const swingLow = recentSwingLowOf(ohlcv_d.slice(0, entryIdx));
  const stopPrice = swingLow != null ? swingLow * 0.99 : null;
  const entryPrice = entryPriceOverride || entryBar.o;
  if (!entryPrice || !stopPrice || entryPrice <= stopPrice) return null;
  let shares = Math.floor(MAX_RISK / (entryPrice - stopPrice));
  if (shares * entryPrice > CAPITAL) shares = Math.floor(CAPITAL / entryPrice);
  if (shares <= 0) return null;
  const entry = { entryDate: entryBar.d, entryPrice, stopPrice, shares,
                  invested: shares * entryPrice, riskAmount: shares * (entryPrice - stopPrice) };
  for (let k = entryIdx; k < ohlcv_d.length; k++) {
    if (!isExitDay(ohlcv_d, k, stopPrice, entry)) continue;
    const next = ohlcv_d[k + 1];
    const exitPrice = next ? next.o : ohlcv_d[k].c;
    const pnl = (exitPrice - entryPrice) * shares;
    return { ...entry, exitDate: next ? next.d : ohlcv_d[k].d, exitPrice, pnl,
             pnlPct: (exitPrice / entryPrice - 1) * 100, isWin: pnl > 0, isOpen: false };
  }
  const last = ohlcv_d[ohlcv_d.length - 1];
  const pnl = (last.c - entryPrice) * shares;
  return { ...entry, exitDate: last.d, exitPrice: last.c, pnl,
           pnlPct: (last.c / entryPrice - 1) * 100, isWin: pnl > 0, isOpen: true };
}

// ── Trade-Simulation ──────────────────────────────────────────────────────────────
// Gewertet werden nur Einstiege, bei denen die 4H-Ebene den dritten Punkt liefert.
// Über beide Testfenster schlägt dieser Auslöser die Tages- und Wochen-Variante
// klar (höherer Profitfaktor, etwa halber Drawdown-Beitrag); die Breakout-Mails
// melden ebenfalls nur diesen Fall. Andere Auslöser werden nicht mehr simuliert.
//
// mode 'WD' nur für den historischen Backtest (backtest_history/), wo es keine
// 4H-Kerzen gibt: Einstieg beim Sprung auf 2 von 2 Punkten (W + D), Auslöser
// ist der zuletzt hinzugekommene D- oder W-Punkt. weekRows dafür ohne 4H-Daten
// bauen. Stopp, Ausstieg und Top-20-Filter bleiben identisch.
function simulateTrades(weekRows, ohlcv_d, ticker, top20Hist, useTop20, mode = '4H') {
  const result = [];
  let inTrade = false, entry = null, lastCheckedDay = null;
  const fullPts = mode === 'WD' ? 2 : 3;

  for (let i = 1; i < weekRows.length; i++) {
    const prev = weekRows[i - 1], curr = weekRows[i];

    if (!inTrade) {
      if (prev.pts < fullPts && curr.pts === fullPts) {
        const new4H = curr.has4h && prev.has4h && prev.p4H === 0 && curr.p4H === 1;
        const newD  = prev.pD === 0 && curr.pD === 1;
        const newW  = prev.pW === 0 && curr.pW === 1;
        let entryPrice, trigger, entryDate;

        if (new4H) {
          trigger = '4H';
          const g = curr.struct4H?.gws4hHigh;
          const sigBar = g ? curr.h4Slice.find(d => d.d > g.date && d.c > g.price) : null;
          const sigDate = sigBar?.d.slice(0,10) ?? curr.week.d;
          const nextBar = ohlcv_d.find(d => d.d > sigDate);
          entryDate = nextBar?.d ?? sigDate;
          entryPrice = nextBar?.o ?? sigBar?.c ?? g?.price;
        } else if (newD) {
          trigger = 'D';
          const g = curr.structDFull?.gwsdHigh;
          const sigBar = g ? curr.dHistory.find(d => d.d > g.date && d.c > g.price) : null;
          const sigDate = sigBar?.d ?? curr.week.d;
          const nextBar = ohlcv_d.find(d => d.d > sigDate);
          entryDate = nextBar?.d ?? sigDate;
          entryPrice = nextBar?.o ?? sigBar?.c ?? curr.structDFull?.breakoutPrice;
        } else if (newW) {
          trigger = 'W';
          const g = curr.structW?.gwswHigh;
          const sigBar = g ? curr.dHistory.find(d => d.d > g.date && d.c > g.price) : null;
          const sigDate = sigBar?.d ?? curr.week.d;
          const nextBar = ohlcv_d.find(d => d.d > sigDate);
          entryDate = nextBar?.d ?? sigDate;
          entryPrice = nextBar?.o ?? sigBar?.c ?? curr.structW?.breakoutPrice;
        } else {
          trigger = '?';
          const sigDate = curr.week.d;
          const nextBar = ohlcv_d.find(d => d.d > sigDate);
          entryDate = nextBar?.d ?? sigDate;
          entryPrice = nextBar?.o ?? curr.struct4H?.gws4hHigh?.price ?? curr.structDFull?.breakoutPrice ?? curr.structW?.breakoutPrice;
        }

        const barsBeforeEntry = curr.dHistory.filter(d => d.d < entryDate);
        let recentSwingLow = recentSwingLowOf(barsBeforeEntry);
        if (recentSwingLow == null && curr.h4Slice.length > 0) {
          const h4Before = curr.h4Slice.filter(d => d.d.slice(0,10) < entryDate);
          for (let k = h4Before.length - 2; k >= 1; k--) {
            if (h4Before[k].l <= h4Before[k-1].l && h4Before[k].l <= h4Before[k+1].l) {
              recentSwingLow = h4Before[k].l; break;
            }
          }
          if (recentSwingLow == null && h4Before.length > 0)
            recentSwingLow = Math.min(...h4Before.slice(-5).map(d => d.l));
        }
        const stopPrice = recentSwingLow != null ? recentSwingLow * 0.99 : null;

        if (mode === 'WD' ? (trigger !== 'D' && trigger !== 'W') : trigger !== '4H') continue;
        if (!entryPrice || !stopPrice || entryPrice <= stopPrice) continue;
        if (useTop20 && top20Hist) {
          const dayList = top20Hist[entryDate] ?? top20Hist[curr.week.d.slice(0,10)];
          if (!dayList || !dayList.includes(ticker)) continue;
        }
        const riskPerShare = entryPrice - stopPrice;
        let shares = Math.floor(MAX_RISK / riskPerShare);
        if (shares * entryPrice > CAPITAL) shares = Math.floor(CAPITAL / entryPrice);
        if (shares <= 0) continue;
        inTrade = true;
        entry = { signalDate: curr.week.d, weeklyDate: curr.week.d, entryDate, trigger, entryPrice, stopPrice, shares, invested: shares * entryPrice, riskAmount: shares * riskPerShare, entryWeekIdx: i };
      }
    } else {
      // Ausstieg wird TÄGLICH geprüft, jeder Tag nur einmal und nur mit Daten,
      // die an diesem Tag schon vorlagen. Signal = Tagesschluss, Ausführung =
      // Eröffnung des Folgetages. (Die frühere Wochenprüfung hat rückwirkend
      // einen Tag der Vorwoche als Ausstieg gebucht — im Median 6 Tage vor dem
      // Zeitpunkt, an dem das Signal überhaupt erkennbar war.)
      for (let k = 0; k < curr.dHistory.length; k++) {
        const day = curr.dHistory[k];
        if (day.d < entry.entryDate) continue;
        if (lastCheckedDay != null && day.d <= lastCheckedDay) continue;

        if (!isExitDay(curr.dHistory, k, entry.stopPrice, entry)) continue;

        const nextDay   = ohlcv_d.find(d => d.d > day.d);
        const exitPrice = nextDay ? nextDay.o : day.c;
        const exitDate  = nextDay ? nextDay.d : day.d;
        const pnl = (exitPrice - entry.entryPrice) * entry.shares;
        result.push({ ...entry, exitDate, exitPrice, pnl, pnlPct: (exitPrice / entry.entryPrice - 1) * 100, isWin: pnl > 0, holdingWeeks: i - entry.entryWeekIdx, isOpen: false });
        inTrade = false; entry = null; lastCheckedDay = null;
        break;
      }
      if (inTrade) lastCheckedDay = curr.weekEnd;
    }
  }

  if (inTrade && entry) {
    // Offene Position: Bewertung zum letzten Tagesschluss. Der Wochenstempel
    // (Montag) läge bei einem Einstieg mitten in der laufenden Woche vor dem Einstieg.
    const last = weekRows[weekRows.length - 1];
    const lastDay = ohlcv_d[ohlcv_d.length - 1];
    const exitPrice = lastDay ? lastDay.c : last.week.c;
    const pnl = (exitPrice - entry.entryPrice) * entry.shares;
    result.push({ ...entry, exitDate: lastDay ? lastDay.d : last.week.d, exitPrice, pnl, pnlPct: (exitPrice / entry.entryPrice - 1) * 100, isWin: pnl > 0, holdingWeeks: weekRows.length - 1 - entry.entryWeekIdx, isOpen: true });
  }

  return result;
}

// ── KPI-Berechnung ────────────────────────────────────────────────────────────────
function calcKpis(trades) {
  const closed    = trades.filter(t => !t.isOpen);
  const openTrade = trades.find(t => t.isOpen) ?? null;
  if (closed.length === 0) return null;
  const wins   = closed.filter(t =>  t.isWin);
  const losses = closed.filter(t => !t.isWin);
  let equity = CAPITAL, peak = CAPITAL, maxDD = 0;
  const equityCurve = [{ equity: CAPITAL }];
  for (const t of closed) {
    equity += t.pnl;
    peak    = Math.max(peak, equity);
    maxDD   = Math.max(maxDD, (peak - equity) / peak * 100);
    equityCurve.push({ date: t.exitDate, equity });
  }
  const grossProfit = wins.reduce((s, t)   => s + t.pnl, 0);
  const grossLoss   = losses.reduce((s, t) => s + t.pnl, 0);
  const openPnl     = openTrade?.pnl ?? 0;

  // Profitfaktor inklusive offener Positionen zum aktuellen Stand. Nur über
  // geschlossene Trades gerechnet verzerrt er systematisch: Die Exit-Regel hält
  // Gewinner deutlich länger als Verlierer, in einem jungen Zeitraum sind die
  // Verluste daher schon abgerechnet, während die Gewinner noch laufen.
  const pfWins   = trades.filter(t => t.pnl >  0).reduce((s, t) => s + t.pnl, 0);
  const pfLosses = trades.filter(t => t.pnl <= 0).reduce((s, t) => s + t.pnl, 0);
  return {
    nTrades:      closed.length,
    nLosses:      losses.length,
    nWins:        wins.length,
    winrate:      wins.length / closed.length * 100,
    totalPnl:     equity - CAPITAL,
    totalReturn:  (equity / CAPITAL - 1) * 100,
    maxDD,
    grossProfit,
    grossLoss,
    grossProfitAll: pfWins,
    grossLossAll:   pfLosses,
    profitFactor: pfLosses < 0 ? Math.abs(pfWins / pfLosses) : null,
    avgWin:       wins.length   > 0 ? grossProfit / wins.length                             : 0,
    avgWinPct:    wins.length   > 0 ? wins.reduce((s,t) => s + t.pnlPct, 0) / wins.length  : 0,
    avgLoss:      losses.length > 0 ? Math.abs(grossLoss) / losses.length                  : 0,
    gesamtGewinn: (equity - CAPITAL) + openPnl,
    hasOpen:      !!openTrade,
    equityCurve,
  };
}
