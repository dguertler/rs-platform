// ── Gemeinsame Backtest-Logik für backtest.html und backtest_overview.html ────────

const CAPITAL  = 10000;
const MAX_RISK = 1000;
// Zeitstopp: Liegt der Schlusskurs 10 Handelstage nach dem Einstieg nicht
// mindestens 5 % über dem Einstiegskurs, wird zur nächsten Eröffnung verkauft.
// Seit 12.10.2026 abgeschaltet (Backtest und live, check_exits.TIME_STOP_ENABLED):
// mit Trendumkehr-Ausstieg und Earnings-Regel PF 1,61 → 1,70 ohne Zeitstopp.
// Systemparameter für eine spätere Optimierung — testen mit
// backtest_ndx.js --mit-zeitstopp (siehe CLAUDE.md).
const TIME_STOP_DAYS = 10;
const TIME_STOP_MIN  = 0.05;
let timeStopEnabled = false;
function setTimeStop(on) { timeStopEnabled = !!on; }

// Signal halten (Weekly und Daily, seit 12.10.2026 Backtest und live): Bildet ein
// tieferes Tief eine neue Marke (Trendumkehr), bleibt die Ebene grün, solange kein
// Schluss unter dem Anker der zuletzt gebrochenen Marke liegt (Weekly: tiefstes Tief
// zwischen Marke und Ausbruchswoche, Daily: letztes Swing-Tief, das die Trendumkehr noch
// nicht unterschritten hat, siehe holdAnchor/tuAnchorLow).
// Die Trendumkehr ist dann nur Ausstieg aus dem Trade, nicht das Ende des Signals.
// 4H bewusst nicht (getestet: Gewinnsumme −16 %). Gegenstück live:
// gws_core.held_after_breakout. Systemparameter — Studien mit backtest_ndx.js --halten=…
// und --halteanker=W:…,D:…
let holdSignal = { w: true, d: true, h4: false };
function setHoldSignal(h) { holdSignal = { w: !!h.w, d: !!h.d, h4: !!h.h4 }; }

// Anker je Ebene (Backtest und live): Weekly 'swingtief' = letztes Swing-Tief vor der Ausbruchswoche
// (seit 13.10.2026; vorher 'tiefstes' = tiefstes Tief zwischen Marke und Ausbruchswoche), Daily 'tu' = letztes Swing-Tief vor
// der Trendumkehr, das sie noch nicht unterschritten hat (tuAnchorLow; vorher 'kerze' = Tief
// der Ausbruchskerze; tiefster Anker auch für Daily getestet: zu viele Fehlkäufe, AVGO-PF
// 2,48 → 1,77). Für Studien zusätzlich 'kerze' und 'tiefstes'
let holdAnchor = { w: 'swingtief', d: 'tu' };
// Weekly-Bruch (seit 13.10.2026, Backtest und live): Weekly erlischt, sobald ein Wochentief unter dem
// Anker liegt — auch solange die gebrochene Marke noch gilt, also bevor die Trendumkehr eine neue
// Marke bildet (PANW: Ausbruch über 95,44 Woche 28.02.2022, Anker 77,75 vom 21.02., Woche 09.05.2022
// Tief 75,05 → Weekly rot bis 22.02.2023). Studien: 'tagesschluss' oder 'wochenschluss'
let weeklyBreakCheck = 'tief';
function setWeeklyBreakCheck(v) { weeklyBreakCheck = v; }
// Weekly-Anker nachziehen (seit 13.10.2026, Backtest und live): Schließt eine Woche über dem letzten
// bestätigten Swing-Hoch (erneuter Ausbruch), springt der Anker auf das Swing-Tief davor (ZS: Woche
// 08.01.2024 schließt bei 230,77 über 227,29 vom 25.12.2023 → Anker 206,67 vom 01.01.2024, Woche
// 19.02. Tief 202,44 → Weekly rot). Studie ohne: backtest_ndx.js --wochenanker-fest
let weeklyTrail = true;
function setWeeklyTrail(on) { weeklyTrail = !!on; }
function setHoldAnchor(a) { holdAnchor = { ...holdAnchor, ...a }; }
function holdAnchorLow(lows, markIdx, b, mode) {
  if (mode === 'swingtief') {
    for (let k = b - 1; k > markIdx; k--) if (lows[k] <= lows[k - 1] && lows[k] <= lows[k + 1]) return lows[k];
  }
  if (mode === 'tiefstes' || mode === 'swingtief') return Math.min(...lows.slice(markIdx, b + 1));
  return lows[b];
}

// Gültigkeitsbereich im Chart (Daily, 4H — nur Darstellung, die Logik bleibt unverändert):
// unten das Swing-Tief vor dem Ausbruch b (SL-Höhe). Bei jedem weiteren Ausbruch nach oben
// (Schluss über dem letzten Swing-Hoch) springt die Untergrenze auf das Swing-Tief vor diesem
// Ausbruch (AVGO Daily: 15.08.2024 → 133,08, 12.09. → 132,17 vom 09.09., 20.09. → 157,16 vom
// 16.09.). Zählt nur ein Swing-Tief, das schon vor der Ausbruchskerze bestätigt war — die
// Ausbruchskerze selbst bestätigt keins (AVGO Daily 14.05.2026: 404,92 vom 07.05., bestätigt
// am 08.05., nicht 403,43 vom 13.05.). Schließt eine Kerze darunter, endet der Bereich; ein
// neuer beginnt beim nächsten Ausbruch. { from, top, low } (Indizes) oder null.
function trailingZone(highs, lows, closes, b, n) {
  const isLow  = k => k >= 1 && k + 1 < n && lows[k] <= lows[k - 1] && lows[k] <= lows[k + 1];
  const isHigh = k => k >= 1 && k + 1 < n && highs[k] >= highs[k - 1] && highs[k] >= highs[k + 1];
  const lowBefore = s => {
    for (let k = s - 2; k >= 1; k--) if (isLow(k)) return lows[k];   // bestätigt vor s
    return Math.min(...lows.slice(Math.max(0, s - 5), s + 1));
  };
  // letztes bestätigtes Swing-Hoch nach der Kerze after (bis k-2), sonst null
  const highAfter = (k, after) => {
    for (let j = k - 2; j > after; j--) if (isHigh(j)) return highs[j];
    return null;
  };
  let start = b, low = lowBefore(b), top = highs[b], last = b;
  for (let k = b + 1; k < n; k++) {
    const sh = highAfter(k, last);
    if (start >= 0) {
      if (closes[k] < low) { start = -1; last = k; continue; }
      // Ausbruch nach oben: Untergrenze springt auf das Swing-Tief davor (SL dieses Ausbruchs)
      if (sh != null && closes[k] > sh) { low = lowBefore(k); last = k; }
      top = Math.max(top, highs[k]);
    } else if (sh != null && closes[k] > sh) {
      start = k; low = lowBefore(k); top = highs[k]; last = k;   // neuer Bereich
    }
  }
  return start >= 0 ? { from: start, top, low } : null;
}
function zoneFrom(bars, z) {
  return z ? { from: bars[z.from].d, top: z.top, anchor: z.low } : null;
}

// Anker 'tu' (Daily, seit 12.10.2026): Die Trendumkehr (tieferes Tief tiefNeu, das die nächste Marke bildet)
// deaktiviert nur den Trade; die Ebene bleibt gehalten, bis ein Schluss unter dem letzten
// Swing-Tief vor tiefNeu liegt, das die Trendumkehr noch nicht unterschritten hat (AVGO
// Daily: Trendumkehr 04.08.2023 bei 84,09 → Anker 81,29 vom 06.07., Schluss 10.08. bei 81,16
// darunter → Daily rot). Gesucht wird höchstens bis zum Swing-Tief vor dem Ausbruch (grüne Linie
// im Chart); liegt die Trendumkehr darunter, gilt dieses Swing-Tief (AVGO 30.10.2023: Trendumkehr
// 26.10. bei 79,22 → Anker 78,58 vom 06.10., vor dem Ausbruch 11.10.). Ohne Trendumkehr: Tief der
// Ausbruchskerze.
function tuAnchorLow(next, lows, b) {
  const t = next?.tiefNeu;
  if (!t || t.idx <= b) return lows[b];
  const isLow = k => k >= 2 && k + 2 < lows.length && lows[k] <= lows[k-1] && lows[k] <= lows[k-2]
    && lows[k] <= lows[k+1] && lows[k] <= lows[k+2];
  let p = -1;                                       // Swing-Tief vor dem Ausbruch (grüne Linie)
  for (let k = b - 1; k >= 2; k--) if (isLow(k)) { p = k; break; }
  for (let k = t.idx - 1; k >= Math.max(2, p); k--) if (isLow(k) && lows[k] < t.price) return lows[k];
  return p >= 0 ? lows[p] : lows[b];
}

// Daily: Swing-Tief schon mit einer Folgekerze, wenn diese Kerze die daraus entstehende Marke
// bricht (seit 12.10.2026, Backtest und live — gws_core.provisional_mark_break). Marke = höchstes
// Swing-Hoch zwischen dem letzten bestätigten Swing-Tief und dem neuen tieferen Tief (Kerze
// n-2); Ausbruch = Schluss der letzten Kerze darüber. Studie ohne: backtest_ndx.js --ohne-fruehbruch
let earlyMarkBreak = true;
function setEarlyMarkBreak(on) { earlyMarkBreak = !!on; }
function provisionalMark(highs, lows, closes, swingHighs, swingLows, n) {
  const k = n - 2, last = swingLows[swingLows.length - 1];
  if (k < 2 || !last || last.idx >= k) return null;
  if (!(lows[k] <= lows[k-1] && lows[k] <= lows[k-2] && lows[k] <= lows[k+1] && lows[k] < last.price)) return null;
  const hs = swingHighs.filter(h => h.idx > last.idx && h.idx < k);
  if (!hs.length) return null;
  const mark = hs.reduce((a, h) => h.price > a.price ? h : a);
  return closes[n - 1] > mark.price ? { ...mark, tiefAlt: last, tiefNeu: { idx: k, price: lows[k] } } : null;
}

// breakoutIdx(cand) (optional): Index der Ausbruchskerze, sonst erster Schluss über der Marke
function heldAfterBreakout(cands, closes, lows, n, breakoutIdx, mode = 'kerze') {
  return heldBreakout(cands, closes, lows, n, breakoutIdx, mode) !== null;
}
// Gehaltene Marke: { b: Index der Ausbruchskerze, anchor } oder null
function heldBreakout(cands, closes, lows, n, breakoutIdx, mode = 'kerze', closedBelow = null) {
  for (let c = cands.length - 1; c >= 0; c--) {
    let b = -1;
    if (breakoutIdx) b = breakoutIdx(cands[c]);
    else for (let i = cands[c].idx + 1; i < n; i++) if (closes[i] > cands[c].price) { b = i; break; }
    if (b < 0) continue;
    const anchor = mode === 'tu' ? tuAnchorLow(cands[c + 1], lows, b) : holdAnchorLow(lows, cands[c].idx, b, mode);
    // 'tu': erst ab der Trendumkehr prüfen (davor liegt das Swing-Tief noch im Aufwärtstrend)
    const from = mode === 'tu' && cands[c + 1]?.tiefNeu?.idx > b ? cands[c + 1].tiefNeu.idx : b + 1;
    if (closedBelow && mode !== 'tu') { if (closedBelow(b, anchor)) return null; }
    else for (let i = from; i < n; i++) if (closes[i] < anchor) return null;
    return { b, anchor };
  }
  return null;
}

// Weekly wie broken: Ausbruch = erster Tagesschluss über der Marke, Ausbruchskerze = seine Woche
function weeklyBreakoutIdx(ohlcvW, ohlcvD) {
  return cand => {
    const day = ohlcvD.find(d => d.d > cand.date && d.c > cand.price);
    if (!day) return -1;
    let b = -1;
    for (let i = 0; i < ohlcvW.length && ohlcvW[i].d <= day.d; i++) b = i;
    return b;
  };
}

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

  let gwsdHigh       = gwsdCandidates.length > 0 ? gwsdCandidates[gwsdCandidates.length - 1] : null;
  let prevGwsdHigh   = gwsdCandidates.length > 1 ? gwsdCandidates[gwsdCandidates.length - 2] : null;

  let breakoutIdx = null;
  if (gwsdHigh) {
    for (let i = gwsdHigh.idx + 1; i < n; i++) {
      if (closes[i] > gwsdHigh.price) { breakoutIdx = i; break; }
    }
  }
  // Ausbruch bestätigt das Swing-Tief: Ist das vorletzte Tief ein tieferes Tief (Swing-Tief mit
  // erst einer Folgekerze) und schließt die letzte Kerze über dem höchsten Hoch seit dem
  // vorigen Swing-Tief, ist diese Marke sofort gebrochen (AVGO 21.08.2023: Tief 18.08. bei
  // 78,18, Marke 82,28 vom 15.08., Schluss 83,30 → Daily grün mit dem 4H-Signal um 18:00).
  if (breakoutIdx === null && earlyMarkBreak) {
    const pm = provisionalMark(highs, lows, closes, swingHighs, swingLows, n);
    if (pm) { prevGwsdHigh = gwsdHigh; gwsdHigh = pm; breakoutIdx = n - 1; }
  }
  const breakoutPrice = gwsdHigh ? gwsdHigh.price : null;

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

  // held: grün nur durch das Signal-Halten (Marke selbst ungebrochen)
  const heldD        = gwsdHigh !== null && breakoutIdx === null && holdSignal.d
    ? heldBreakout(gwsdCandidates, closes, lows, n, undefined, holdAnchor.d) : null;
  const held         = heldD !== null;
  const broken       = gwsdHigh !== null && (breakoutIdx !== null || held);
  // Gültigkeitsbereich für die Charts: ab Ausbruchskerze, unten nachgezogenes Swing-Tief
  // (trailingZone, nur Darstellung — das Signal selbst erlischt unter dem Tief der Ausbruchskerze)
  const zone = !broken ? null : breakoutIdx !== null
    ? zoneFrom(ohlcv, trailingZone(highs, lows, closes, breakoutIdx, n))
    : zoneFrom(ohlcv, trailingZone(highs, lows, closes, heldD.b, n));
  const currentClose = closes[n - 1];
  const recentBreakout = broken && (n - 1 - breakoutIdx <= 7);

  return {
    currentClose, gwsdHigh, breakoutIdx, breakoutPrice, broken, held, zone, trend,
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
  const brokenMark = gwswHigh !== null && (hasDailyCandles
    ? ohlcvD.some(d => d.d > gwswHigh.date && d.c > gwswHigh.price)
    : breakoutIdx !== null);
  // held: grün nur durch das Signal-Halten (Marke selbst ungebrochen)
  const wBreak = hasDailyCandles ? weeklyBreakoutIdx(ohlcvW, ohlcvD) : undefined;
  // Anker unterschritten seit der Ausbruchswoche b (weeklyBreakCheck), Woche für Woche; mit
  // weeklyTrail rückt der Anker bei jedem erneuten Ausbruch über das letzte Swing-Hoch nach
  const weekStart = k => weekOfBar(ohlcvW[k].d);
  const belowIn = (k, anchor) => {
    if (weeklyBreakCheck === 'tief') return lows[k] < anchor;
    if (weeklyBreakCheck === 'wochenschluss' || !hasDailyCandles) return closes[k] < anchor;
    const from = weekStart(k), to = k + 1 < n ? weekStart(k + 1) : '9999';
    return ohlcvD.some(d => d.d >= from && d.d < to && d.c < anchor);
  };
  const isSwingLow = k => k >= 1 && k + 1 < n && lows[k] <= lows[k - 1] && lows[k] <= lows[k + 1];
  const isSwingHigh = k => k >= 1 && k + 1 < n && highs[k] >= highs[k - 1] && highs[k] >= highs[k + 1];
  const anchorWalk = (b, anchor) => {
    let last = b;
    for (let k = b + 1; k < n; k++) {
      if (belowIn(k, anchor)) return { lost: true, anchor };
      if (!weeklyTrail) continue;
      let sh = null;
      for (let j = k - 2; j > last; j--) if (isSwingHigh(j)) { sh = highs[j]; break; }
      if (sh != null && closes[k] > sh) {
        for (let j = k - 1; j > last; j--) if (isSwingLow(j)) { anchor = Math.max(anchor, lows[j]); break; }
        last = k;
      }
    }
    return { lost: false, anchor };
  };
  const closedBelow = weeklyBreakCheck === 'wochenschluss' && !weeklyTrail ? null : (b, anchor) => anchorWalk(b, anchor).lost;
  const heldW = gwswHigh !== null && !brokenMark && holdSignal.w
    ? heldBreakout(gwswCandidates, closes, lows, n, wBreak, holdAnchor.w, closedBelow) : null;
  const held = heldW !== null;
  // gebrochene Marke: mit Studie weeklyBreakCheck endet das Signal schon beim Unterschreiten des Ankers
  const wbIdx = brokenMark && closedBelow ? (wBreak ? wBreak(gwswHigh) : breakoutIdx) : null;
  const markLost = wbIdx != null && wbIdx >= 0 && closedBelow(wbIdx, holdAnchorLow(lows, gwswHigh.idx, wbIdx, holdAnchor.w));
  const broken = (brokenMark && !markLost) || held;
  // Gültigkeitsbereich für die Charts: Ausbruchswoche und Anker, unter dem das Signal erlischt
  const wb = brokenMark ? (wBreak ? wBreak(gwswHigh) : breakoutIdx) : null;
  const zone = brokenMark && !markLost && wb != null && wb >= 0
    ? { from: ohlcvW[wb].d, top: Math.max(...highs.slice(wb)), anchor: anchorWalk(wb, holdAnchorLow(lows, gwswHigh.idx, wb, holdAnchor.w)).anchor }
    : held ? { from: ohlcvW[heldW.b].d, top: Math.max(...highs.slice(heldW.b)), anchor: heldW.anchor } : null;
  const recentBreakout = breakoutIdx !== null && (n - 1 - breakoutIdx <= 1);

  return {
    gwswHigh, breakoutIdx, breakoutPrice, broken, held, zone,
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
    gws4hHigh, breakout4hIdx,
    broken4h: gws4hHigh === null || breakout4hIdx !== null
      || (holdSignal.h4 && heldAfterBreakout(gws4hCandidates, closes, lows, n)),
    prevGws4hHigh, prevBreakout4hIdx, recentBreakout,
    // Gültigkeitsbereich für die Charts: ab Ausbruchskerze, unten nachgezogenes Swing-Tief
    zone: breakout4hIdx !== null ? zoneFrom(ohlcv4h, trailingZone(highs, lows, closes, breakout4hIdx, n)) : null,
    tiefNeu: lastGws4hDefLow,
    swingHighs: swingHighs.slice(-8),
    swingLows:  swingLows.slice(-8),
  };
}

// ── Gültigkeitsbereiche je Chart ─────────────────────────────────────────────────
// Für jede angezeigte Kerze die Struktur zu ihrem Schluss (zeitpunktgenau, wie die
// Punkte): ist die Ebene grün, gehört die Kerze zum Bereich ihrer Ausbruchskerze. Ein
// Bereich reicht von der Ausbruchskerze bis zur letzten grünen Kerze, vom höchsten Hoch
// seit der Ausbruchskerze bis zum Anker (darunter erlischt das Signal). Ergebnis:
// [{ start, end, top, anchor, held }]
// mit Indizes in shown.
function validityZones(shown, structAt) {
  const zones = [];
  shown.forEach((bar, k) => {
    const st = structAt(bar);
    const z = st?.zone;
    const last = zones[zones.length - 1];
    if (!z) return;
    if (last && last.from === z.from && last.anchor === z.anchor && last.end === k - 1) {
      last.end = k; last.top = Math.max(last.top, z.top); last.held = last.held || !!st.held; return;
    }
    let start = shown.findIndex(b => b.d >= z.from);
    if (start < 0 || start > k) start = k;
    if (last && start <= last.end) start = last.end + 1;
    zones.push({ from: z.from, top: z.top, anchor: z.anchor, start, end: k, held: !!st.held });
  });
  return zones;
}
function weeklyZones(ohlcv_w, ohlcv_d, shown) {
  return validityZones(shown, b => {
    const a = ohlcv_w.findIndex(w => w.d === b.d);
    const end = getWeekEnd(b.d);
    return a < 0 ? null : analyzeWeeklyStructure(ohlcv_w.slice(Math.max(0, a - 59), a + 1), ohlcv_d.filter(d => d.d <= end));
  });
}
function dailyZones(ohlcv_d, shown) {
  const idx = new Map(ohlcv_d.map((b, i) => [b.d, i]));
  return validityZones(shown, b => {
    const i = idx.get(b.d);
    return i == null ? null : analyzeStructure(ohlcv_d.slice(0, i + 1));
  });
}
function h4Zones(ohlcv_4h, shown) {
  const idx = new Map(ohlcv_4h.map((b, i) => [b.d, i]));
  return validityZones(shown, b => {
    const i = idx.get(b.d);
    return i == null ? null : analyze4HStructure(ohlcv_4h.slice(Math.max(0, i - 59), i + 1));
  });
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

// Trendumkehr-Tief: das letzte Swing-Tief vor dem letzten Swing-Hoch — das Tief,
// aus dem das letzte Hoch entstanden ist (Referenz-Trade AVGO: Tief 25.06.2024,
// Schluss darunter am 17.07.2024). null, wenn es keins gibt.
function trendLowOf(struct) {
  const highs = struct?.swingHighs ?? [];
  const lastHigh = highs[highs.length - 1];
  if (!lastHigh) return null;
  const lows = (struct.swingLows ?? []).filter(l => l.idx < lastHigh.idx);
  return lows.length > 0 ? lows[lows.length - 1].price : null;
}

// Verkaufsgründe — Kürzel und Farbe für Chart-Marker und Trade-Listen
const EXIT_REASONS = {
  stopp:       { short: 'SL', label: 'Stopp: Schluss unter dem Stopp',                                   color: '#f87171' },
  trendumkehr: { short: 'TU', label: 'Trendumkehr: Schluss unter dem Tief, aus dem das letzte Hoch entstand', color: '#fb923c' },
  einstand:    { short: 'BE', label: 'Einstand: nach 2R Gewinn (Tagesschluss) Stopp auf Einstieg, Schluss darunter', color: '#facc15' },
  zeitstopp:   { short: 'ZS', label: 'Zeitstopp: 10 Handelstage nach dem Kauf nicht mind. +5 %',          color: '#c084fc' },
  earnings:    { short: 'ER', label: 'Verkauf vor Earnings (Schluss der 14-Uhr-Kerze)',                   color: '#38bdf8' },
  datenende:   { short: 'DE', label: 'Kursdaten enden (Titel nicht mehr gehandelt)',                      color: '#94a3b8' },
};

// Ausstiegsgrund am Tagesschluss von dHistory[k] ('zeitstopp' | 'trendumkehr' |
// 'stopp') oder null: Zeitstopp, Schluss unter dem Trendumkehr-Tief (aus den
// Kerzen davor) oder unter dem Stopp. Ausführung am nächsten Handelstag zur Eröffnung.
function exitReasonOf(dHistory, k, stopPrice, entry = null) {
  const day = dHistory[k];
  if (entry && isTimeStop(dHistory, k, entry)) return 'zeitstopp';
  const trendLow = trendLowOf(analyzeStructure(dHistory.slice(0, k)));
  if (trendLow != null && day.c < trendLow) return 'trendumkehr';
  return stopPrice != null && day.c < stopPrice ? 'stopp' : null;
}

function isExitDay(dHistory, k, stopPrice, entry = null) {
  return exitReasonOf(dHistory, k, stopPrice, entry) != null;
}

// Zeitstopp am Tagesschluss von dHistory[k] (Handelstage ab dem Einstiegstag gezählt)
const _entryIdxCache = new WeakMap();
function isTimeStop(dHistory, k, entry) {
  // dHistory beginnt immer mit derselben ersten Tageskerze — der Index bleibt gleich
  if (!_entryIdxCache.has(entry)) _entryIdxCache.set(entry, dHistory.findIndex(d => d.d >= entry.entryDate));
  const idx = _entryIdxCache.get(entry);
  return timeStopEnabled && idx >= 0 && k - idx === TIME_STOP_DAYS
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
    const exitReason = exitReasonOf(ohlcv_d, k, stopPrice, entry);
    if (!exitReason) continue;
    const next = ohlcv_d[k + 1];
    const exitPrice = next ? next.o : ohlcv_d[k].c;
    const pnl = (exitPrice - entryPrice) * shares;
    return { ...entry, exitDate: next ? next.d : ohlcv_d[k].d, exitPrice, exitReason, pnl,
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

// ── Zeitpunktgenaue Simulation (Live-Ablauf seit 10/2026) ─────────────────────────
// Geprüft wird an jedem 4H-Kerzenschluss, nur mit Daten, die da schon vorlagen:
// 4H-Punkt springt mit dieser Kerze von 0 auf 1, Wochen- und Tagespunkt sind zu
// diesem Zeitpunkt grün (Tages- und Wochenkerze enthalten nur den Handel bis
// jetzt). Kauf wie live: Kerzen 10–14 und 14–18 Uhr (Berlin) → Eröffnung der
// nächsten 4H-Kerze am selben Tag (4H-Prüfjob), spätere Kerzen → 10-Uhr-Kerze des
// nächsten Handelstages (Nachtlauf). Stopp, Ausstieg und Zeitstopp wie oben.
// simulateTrades (Wochenzeilen) prüfte die Punkte nur zum Wochenschluss und
// buchte den Kauf rückwirkend — gut ein Fünftel der Trades war live unmöglich
// (Studie 10/2026: PF 3,23 → 1,90 zeitpunktgenau).
const PIT_START = '2016-01-01';

function addDaysISO(d, n) {
  const t = new Date(d.slice(0, 10) + 'T12:00:00Z');
  t.setUTCDate(t.getUTCDate() + n);
  return t.toISOString().slice(0, 10);
}
function mondayOf(d) {
  const t = new Date(d.slice(0, 10) + 'T12:00:00Z');
  t.setUTCDate(t.getUTCDate() - (t.getUTCDay() + 6) % 7);
  return t.toISOString().slice(0, 10);
}
// Wochenkerzen tragen je nach Quelle den Montag oder den Samstag davor
const weekOfBar = d => mondayOf(addDaysISO(d, 2));

// 4H-Kerzenbeginn (Berliner Zeit) → Block 0–3 (10, 14, 18, 22 Uhr; bei
// verschobener Zeitumstellung 9, 13, 17, 21 Uhr)
function h4Block(label) {
  const h = +label.slice(11, 13);
  return h <= 10 ? 0 : h <= 14 ? 1 : h <= 18 ? 2 : 3;
}

// Wochenkerzen bis zur Woche von dHistory.at(-1); die laufende Woche nur aus
// den Tageskerzen bis jetzt
function weeklyUpTo(ohlcv_w, dHistory) {
  const last = dHistory[dHistory.length - 1];
  const wk = mondayOf(last.d);
  const out = [];
  for (const b of ohlcv_w) if (weekOfBar(b.d) < wk) out.push(b);
  const days = [];
  for (let i = dHistory.length - 1; i >= 0 && mondayOf(dHistory[i].d) === wk; i--) days.unshift(dHistory[i]);
  out.push({ d: wk, o: days[0].o, h: Math.max(...days.map(x => x.h)), l: Math.min(...days.map(x => x.l)), c: last.c });
  return out.slice(-60);
}

// ── Earnings ──────────────────────────────────────────────────────────────────────
// earnings: [[YYYY-MM-DD, 'bmo'|'amc'|'unk'], …] aufsteigend (data/earnings_history.json).
// Kein Kauf, wenn die nächsten Zahlen weniger als EARNINGS_BLOCK_DAYS Kalendertage
// entfernt sind; offene Positionen werden zum Schluss der 14-Uhr-Kerze am letzten
// Handelstag vor den Zahlen verkauft (nach Börsenschluss: derselbe Tag, vor
// Börsenbeginn oder unbekannt: der Handelstag davor).
const EARNINGS_BLOCK_DAYS = 4;

function nextEarnings(earnings, day) {
  return earnings ? earnings.find(([d]) => d >= day) ?? null : null;
}

function calendarDays(a, b) {
  return Math.round((new Date(b + 'T12:00:00Z') - new Date(a + 'T12:00:00Z')) / 864e5);
}

function earningsBlocksEntry(earnings, entryDay) {
  const e = nextEarnings(earnings, entryDay);
  return !!e && calendarDays(entryDay, e[0]) < EARNINGS_BLOCK_DAYS;
}

// Kurs fällt nach den Zahlen (seit 12.10.2026, Backtest und live — check_exits.earnings_drop_block):
// Schließt der Reaktionstag (nach Börsenschluss: nächster Handelstag, sonst der Tag der Zahlen)
// mindestens EARNINGS_DROP_MIN unter dem Schluss davor, gibt es keinen Kauf, bis Daily nach der
// Reaktion einmal rot war (und wieder grün ist) oder ein Schluss über dem Kurs vor den Zahlen
// liegt (AVGO: Zahlen 31.08.2023 nach Börsenschluss, 01.09. Schluss 84,02 nach 88,79 = −5,4 %
// → kein Kauf am 14.09., Daily blieb grün). dailyGreen(i): Daily grün mit Tageskerze i.
const EARNINGS_DROP_MIN = 0.05;
let earningsDropRule = true;
function setEarningsDropRule(on) { earningsDropRule = !!on; }
function earningsDropBlocks(earnings, ohlcv_d, dIdx, signalDay, dailyGreen) {
  if (!earningsDropRule || !earnings) return false;
  let e = null;
  for (const x of earnings) { if (x[0] >= signalDay) break; e = x; }
  if (!e) return false;
  let r = -1;
  for (let i = 0; i < ohlcv_d.length; i++) {
    if (e[1] === 'amc' ? ohlcv_d[i].d > e[0] : ohlcv_d[i].d >= e[0]) { r = i; break; }
  }
  if (r < 1 || ohlcv_d[r].d >= signalDay || ohlcv_d[r].c > ohlcv_d[r - 1].c * (1 - EARNINGS_DROP_MIN)) return false;
  const sig = dIdx.get(signalDay) ?? ohlcv_d.length;
  for (let i = r + 1; i < sig; i++) if (ohlcv_d[i].c > ohlcv_d[r - 1].c) return false;   // über dem Kurs vor den Zahlen
  for (let i = r; i < sig; i++) if (!dailyGreen(i)) return false;   // Daily war rot → wieder frei
  return true;
}

// Verkaufstag vor den Zahlen e (Handelstag aus ohlcv_d)
function earningsSellDay(ohlcv_d, e) {
  if (e[1] === 'amc') return e[0];
  let prev = null;
  for (const b of ohlcv_d) { if (b.d >= e[0]) break; prev = b.d; }
  return prev;
}

// Schluss der 14-Uhr-Kerze (Block 1) am Tag day; ersatzweise der Tagesschluss
function earningsExitPrice(ohlcv_d, h4, day) {
  const bar = (h4 || []).find(b => b.d.slice(0, 10) === day && h4Block(b.d) === 1);
  return bar ? bar.c : ohlcv_d.find(b => b.d === day)?.c;
}

// Einstands-Stopp (seit 13.10.2026, Backtest und live — check_exits.effective_stop): Schließt ein
// Tag mindestens breakEven.r × R über dem Einstieg (R = Einstieg − Stopp), rückt der Stopp ab dem
// nächsten Tag auf Einstieg + breakEven.offset × R; ein Schluss darunter → Verkauf zur Eröffnung
// (Grund 'einstand'). Über alle Top-20-Signale PF 1,82 → 1,83, Gewinnsumme +1.652 €. Studien:
// backtest_ndx.js --einstand=R:offset[:hoch] bzw. --ohne-einstand
let breakEven = { r: 2, offset: 0, basis: 'schluss' };
function setBreakEven(v) { breakEven = v; }

// Ein Trade ab Einstieg (Tag + Kurs): Stopp, Ausstieg und Zeitstopp wie simulateTrades.
// earn = { earnings, h4 }: Verkauf vor den nächsten Zahlen (siehe oben)
function tradeFromEntry(ohlcv_d, entryDate, entryPrice, extra, earn = null) {
  const idx = ohlcv_d.findIndex(b => b.d >= entryDate);
  if (idx < 0) return null;
  const swingLow = recentSwingLowOf(ohlcv_d.slice(0, idx));
  const stopPrice = swingLow != null ? swingLow * 0.99 : null;
  if (!entryPrice || !stopPrice || entryPrice <= stopPrice) return null;
  let shares = Math.floor(MAX_RISK / (entryPrice - stopPrice));
  if (shares * entryPrice > CAPITAL) shares = Math.floor(CAPITAL / entryPrice);
  if (shares <= 0) return null;
  const entry = { ...extra, trigger: '4H', entryDate: ohlcv_d[idx].d, entryPrice, stopPrice, shares,
                  invested: shares * entryPrice, riskAmount: shares * (entryPrice - stopPrice) };
  const weeks = d => Math.round((new Date(d) - new Date(entry.entryDate)) / (7 * 864e5));
  const nextE = nextEarnings(earn?.earnings, entry.entryDate);
  const sellDay = nextE ? earningsSellDay(ohlcv_d, nextE) : null;
  let curStop = stopPrice;
  for (let k = idx; k < ohlcv_d.length; k++) {
    if (sellDay && sellDay >= entry.entryDate && ohlcv_d[k].d >= sellDay) {
      const exitDate = ohlcv_d[k].d, exitPrice = earningsExitPrice(ohlcv_d, earn.h4, exitDate);
      const pnl = (exitPrice - entryPrice) * shares;
      return { ...entry, exitDate, exitPrice, exitReason: 'earnings', pnl, pnlPct: (exitPrice / entryPrice - 1) * 100,
               isWin: pnl > 0, isOpen: false, holdingWeeks: weeks(exitDate) };
    }
    let exitReason = exitReasonOf(ohlcv_d, k, curStop, entry);
    if (exitReason === 'stopp' && curStop > stopPrice) exitReason = 'einstand';
    if (!exitReason && breakEven && curStop < entryPrice + breakEven.offset * (entryPrice - stopPrice)) {
      const R = entryPrice - stopPrice;
      const px = breakEven.basis === 'hoch' ? ohlcv_d[k].h : ohlcv_d[k].c;
      if (px >= entryPrice + breakEven.r * R) curStop = entryPrice + breakEven.offset * R;
    }
    if (!exitReason) continue;
    const next = ohlcv_d[k + 1];
    const exitPrice = next ? next.o : ohlcv_d[k].c;
    const exitDate = next ? next.d : ohlcv_d[k].d;
    const pnl = (exitPrice - entryPrice) * shares;
    return { ...entry, exitDate, exitPrice, exitReason, pnl, pnlPct: (exitPrice / entryPrice - 1) * 100,
             isWin: pnl > 0, isOpen: false, holdingWeeks: weeks(exitDate) };
  }
  const last = ohlcv_d[ohlcv_d.length - 1];
  const pnl = (last.c - entryPrice) * shares;
  return { ...entry, exitDate: last.d, exitPrice: last.c, pnl, pnlPct: (last.c / entryPrice - 1) * 100,
           isWin: pnl > 0, isOpen: true, holdingWeeks: weeks(last.d) };
}

// Weekly-Trendumkehr → Retracement abwarten (seit 13.10.2026, Backtest und live —
// check_alerts.weekly_reversal_blocks): Zeigt Weekly eine Trendumkehr (Ebene nur gehalten oder
// tieferes Tief in Bildung), zählt ein 4H-Signal erst, wenn Daily tatsächlich über seine Marke
// ausgebrochen ist (nicht nur gehalten) und 4H nach dem Tag dieses Daily-Ausbruchs einmal rot war
// (Retracement). AVGO: kein Kauf 31.07. (Daily nur gehalten über 161,98) und 13.08.2024, Daily
// bricht 158,06 am 15.08., Kauf 12.09.2024. Studien: backtest_ndx.js --wochenumkehr=aus|bestaetigt
let weeklyReversalRule = true;   // true | 'bestaetigt' (nur bestätigte Umkehr = gehalten) | false
function setWeeklyReversalRule(v) { weeklyReversalRule = v; }
function weeklyReversal(wBars, wS) {
  if (wS.held) return true;
  if (weeklyReversalRule === 'bestaetigt') return false;
  const lows = wBars.map(b => b.l), n = lows.length;
  let sl = -1;
  for (let i = n - 2; i >= 1; i--) if (lows[i] <= lows[i - 1] && lows[i] <= lows[i + 1]) { sl = i; break; }
  if (sl < 0 || !wS.gwswHigh) return false;
  // nur Tiefs nach dem Ausbruch über die aktuelle Marke zählen
  return sl > wS.gwswHigh.idx && Math.min(...lows.slice(sl + 1)) < lows[sl];
}

// inTop(day) → true/false (Top 20 am Signaltag); null = ohne Top-20-Filter.
// earnings: Termine des Titels (siehe nextEarnings); null = ohne Earnings-Regel
function simulateTradesPIT(ohlcv_w, ohlcv_d, ohlcv_4h, inTop = null, start = PIT_START, earnings = null) {
  const trades = [];
  const dIdx = new Map(ohlcv_d.map((b, i) => [b.d, i]));
  const h = ohlcv_4h;
  const first = Math.max(8, h.findIndex(b => b.d.slice(0, 10) >= start) - 1);
  if (first < 8 || h.length < 10) return trades;
  const p4 = new Array(h.length).fill(null);
  for (let j = first; j < h.length; j++) {
    p4[j] = analyze4HStructure(h.slice(Math.max(0, j - 59), j + 1))?.broken4h ? 1 : 0;
  }
  let busyUntil = '';
  const dGreen = new Map();   // Daily grün je Tageskerze (für die Earnings-Fall-Sperre)
  const dailyGreen = i => {
    if (!dGreen.has(i)) dGreen.set(i, !!analyzeStructure(ohlcv_d.slice(0, i + 1))?.broken);
    return dGreen.get(i);
  };
  for (let j = first + 1; j < h.length; j++) {
    if (p4[j - 1] !== 0 || p4[j] !== 1) continue;
    const bar = h[j], day = bar.d.slice(0, 10);
    if (day < start || day < busyUntil || (inTop && !inTop(day))) continue;
    const i = dIdx.get(day);
    if (i == null) continue;
    const blk = h4Block(bar.d);
    let dHistory;
    if (blk === 0) dHistory = ohlcv_d.slice(0, i);                     // vor Börsenbeginn
    else if (blk === 1) {                                                // Handel bis 12 Uhr New York
      const db = ohlcv_d[i];
      dHistory = ohlcv_d.slice(0, i).concat([{ d: day, o: db.o, h: Math.max(db.o, bar.h), l: Math.min(db.o, bar.l), c: bar.c }]);
    } else dHistory = ohlcv_d.slice(0, i + 1);                          // Tageskerze komplett
    if (dHistory.length < 30) continue;
    const dS = analyzeStructure(dHistory);
    if (!dS?.broken) continue;
    const wBars = weeklyUpTo(ohlcv_w, dHistory);
    const wS = analyzeWeeklyStructure(wBars, dHistory);
    if (!wS?.broken) continue;
    if (weeklyReversalRule && weeklyReversal(wBars, wS)
        && (dS.breakoutIdx === null || h[j - 1].d.slice(0, 10) <= dHistory[dS.breakoutIdx].d)) continue;

    let k = j + 1;
    if (!(blk <= 1 && h[k] && h[k].d.slice(0, 10) === day)) {
      while (k < h.length && h[k].d.slice(0, 10) <= day) k++;
    }
    if (k >= h.length) continue;
    if (earningsBlocksEntry(earnings, h[k].d.slice(0, 10))) continue;
    if (earningsDropBlocks(earnings, ohlcv_d, dIdx, day, dailyGreen)) continue;
    const wk = ohlcv_w.find(w => weekOfBar(w.d) === mondayOf(day));
    const t = tradeFromEntry(ohlcv_d, h[k].d.slice(0, 10), h[k].o,
      { signalBar: bar.d, entryTime: h[k].d.slice(11, 16), signalDate: day, weeklyDate: wk ? wk.d : mondayOf(day) },
      earnings ? { earnings, h4: h } : null);
    if (!t) continue;
    trades.push(t);
    busyUntil = t.exitDate;
  }
  return trades;
}

// Historische Kurse (data/backtest_history/charts, ab 2005/2016) mit den täglich
// aktualisierten Kursen (backtest_TICKER.json) zusammenführen. Weicht der
// Schlusskurs am Übergang um mehr als 2 % ab (Split seit dem historischen Lauf),
// wird die Historie auf den aktuellen Stand skaliert.
// Wochenkerzen auf den Montag normieren; doppelte Einträge derselben Woche (Yahoo
// liefert gelegentlich eine zweite Zeile, z. B. 21.09. und 22.09.) zusammenfassen
function normalizeWeekly(arr) {
  const out = [];
  for (const b of arr) {
    const d = weekOfBar(b.d), last = out[out.length - 1];
    if (last && last.d === d) Object.assign(last, { h: Math.max(last.h, b.h), l: Math.min(last.l, b.l), c: b.c });
    else out.push({ ...b, d });
  }
  return out;
}

function mergeSeries(hist, live) {
  if (!hist && !live) return null;
  if (!hist || !live || !live.ohlcv_d?.length) {
    const only = hist || live;
    return { ...only, ohlcv_w: normalizeWeekly(only.ohlcv_w || []) };
  }
  const liveD = new Map(live.ohlcv_d.map(b => [b.d, b.c]));
  const anchor = [...hist.ohlcv_d].reverse().find(b => liveD.has(b.d));
  const ratio = anchor ? liveD.get(anchor.d) / anchor.c : 1;
  const scale = Math.abs(ratio - 1) > 0.02
    ? arr => arr.map(b => ({ ...b, o: b.o * ratio, h: b.h * ratio, l: b.l * ratio, c: b.c * ratio }))
    : arr => arr;
  const join = (a, b, key) => {
    if (!a.length) return b;
    const lastKey = key(a[a.length - 1]);
    const tail = b.filter(x => key(x) >= lastKey);
    const head = tail.length && key(tail[0]) === lastKey ? a.slice(0, -1) : a;
    return head.concat(tail);
  };
  return {
    ohlcv_w:  join(normalizeWeekly(scale(hist.ohlcv_w)), normalizeWeekly(live.ohlcv_w || []), b => b.d),
    ohlcv_d:  join(scale(hist.ohlcv_d), live.ohlcv_d, b => b.d),
    ohlcv_4h: join(scale(hist.ohlcv_4h), live.ohlcv_4h || [], b => b.d),
  };
}

// Kursdatei aus data/backtest_history/charts → Engine-Format
function chartToSeries(c) {
  const bar = a => ({ d: a[0], o: a[1], h: a[2], l: a[3], c: a[4] });
  return { ohlcv_w: c.w.map(bar), ohlcv_d: c.d.map(bar), ohlcv_4h: c.h.map(bar) };
}

// Top 20 am Tag: bis zum Ende des historischen Laufs dessen Ranking, danach die
// tägliche Top-20-Historie der RS-Datei
function top20Lookup(ticker, histIntervals, histEnd, liveHistory) {
  return day => {
    if (histIntervals && day <= histEnd) return histIntervals.some(([a, z]) => day >= a && day <= z);
    const list = liveHistory?.[day];
    return !!list && list.includes(ticker);
  };
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
