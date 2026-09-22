// ── Gemeinsame Backtest-Logik für backtest.html und backtest_overview.html ────────

const CAPITAL  = 10000;
const MAX_RISK = 1000;

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
    if (tiefNeu.price < tiefAlt.price &&
        (lastGwswDefLow === null || tiefNeu.price < lastGwswDefLow.price)) {
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
    if (tiefNeu.price < tiefAlt.price &&
        (lastGws4hDefLow === null || tiefNeu.price < lastGws4hDefLow.price)) {
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
function buildWeekRows(ohlcv_w, ohlcv_d, ohlcv_4h) {
  return ohlcv_w.map((week, i) => {
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

// ── Trade-Simulation ──────────────────────────────────────────────────────────────
function simulateTrades(weekRows, ohlcv_d, ticker, top20Hist, useTop20) {
  const result = [];
  let inTrade = false, entry = null, lastCheckedDay = null;

  for (let i = 1; i < weekRows.length; i++) {
    const prev = weekRows[i - 1], curr = weekRows[i];

    if (!inTrade) {
      if (prev.pts < 3 && curr.pts === 3) {
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
        let recentSwingLow = null;
        for (let k = barsBeforeEntry.length - 2; k >= 1; k--) {
          if (barsBeforeEntry[k].l <= barsBeforeEntry[k-1].l && barsBeforeEntry[k].l <= barsBeforeEntry[k+1].l) {
            recentSwingLow = barsBeforeEntry[k].l; break;
          }
        }
        if (recentSwingLow == null && barsBeforeEntry.length > 0)
          recentSwingLow = Math.min(...barsBeforeEntry.slice(-5).map(d => d.l));
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

        const structBefore = analyzeStructure(curr.dHistory.slice(0, k));
        let exitSignal = false;
        if (structBefore && !structBefore.broken) {
          const swingLows = structBefore.swingLows ?? [];
          const lastSL    = swingLows.length > 0 ? swingLows[swingLows.length - 1] : null;
          if (lastSL != null && day.c < lastSL.price) exitSignal = true;
        }
        if (!exitSignal && entry.stopPrice != null && day.c < entry.stopPrice) exitSignal = true;
        if (!exitSignal) continue;

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
    const last = weekRows[weekRows.length - 1];
    const exitPrice = last.week.c;
    const pnl = (exitPrice - entry.entryPrice) * entry.shares;
    result.push({ ...entry, exitDate: last.week.d, exitPrice, pnl, pnlPct: (exitPrice / entry.entryPrice - 1) * 100, isWin: pnl > 0, holdingWeeks: weekRows.length - 1 - entry.entryWeekIdx, isOpen: true });
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
    profitFactor: grossLoss < 0 ? Math.abs(grossProfit / grossLoss) : null,
    avgWin:       wins.length   > 0 ? grossProfit / wins.length                             : 0,
    avgWinPct:    wins.length   > 0 ? wins.reduce((s,t) => s + t.pnlPct, 0) / wins.length  : 0,
    avgLoss:      losses.length > 0 ? Math.abs(grossLoss) / losses.length                  : 0,
    gesamtGewinn: (equity - CAPITAL) + openPnl,
    hasOpen:      !!openTrade,
    equityCurve,
  };
}
