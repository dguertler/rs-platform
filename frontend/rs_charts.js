// ── Gemeinsame Chart- und Struktur-Bausteine für alle Index-Seiten ──────────────
// Vorher lag dieser Block als Kopie in index.html, sp500.html und
// smallcap.html — die Kopien waren bereits auseinandergedriftet (die Signal-Pfeile
// im Weekly-Chart gab es nur in einer Kopie in der robusten Fassung). Hier steht er
// einmal; die Seiten binden ihn per <script type="text/babel" src="rs_charts.js"> ein.

// Signal halten nach Trendumkehr (Weekly und Daily, wie heldAfterBreakout in
// backtest_logic.js und gws_core.held_after_breakout live): Hat ein tieferes Tief eine
// neue, noch ungebrochene Marke gebildet, bleibt die Ebene grün, solange seit der
// Ausbruchskerze der zuletzt gebrochenen Marke kein Schluss unter dem Anker liegt
// (Weekly: letztes Swing-Tief vor der Ausbruchswoche, bei erneutem Ausbruch nachgezogen, gebrochen
// beim ersten Wochentief darunter — weeklyAnchorLow/anchorWalk; Daily: letztes Swing-Tief vor der Trendumkehr, das sie noch nicht
// unterschritten hat — tuAnchorLow, geprüft ab der Trendumkehr).
// breakoutIdx(marke) (optional): Index der Ausbruchskerze, sonst erster Schluss darüber.
// weekly: Weekly-Anker, sonst Daily-Anker 'tu'; closedBelow(b, anchor) (optional): eigene Bruchprüfung
function heldAfterBreakout(cands, closes, lows, n, breakoutIdx, weekly = false, closedBelow = null) {
  return heldBreakout(cands, closes, lows, n, breakoutIdx, weekly, closedBelow) !== null;
}
// Weekly-Anker wie holdAnchorLow(…, 'swingtief') in backtest_logic.js: letztes Swing-Tief vor der
// Ausbruchswoche b (nach der Marke), sonst tiefstes Tief dazwischen (PANW: 77,75 vom 21.02.2022)
function weeklyAnchorLow(lows, markIdx, b) {
  for (let k = b - 1; k > markIdx; k--) if (lows[k] <= lows[k - 1] && lows[k] <= lows[k + 1]) return lows[k];
  return Math.min(...lows.slice(markIdx, b + 1));
}
// Daily-Anker nach Trendumkehr wie tuAnchorLow in backtest_logic.js: letztes Swing-Tief vor
// tiefNeu (dem tieferen Tief der nächsten Marke), das tiefer liegt als tiefNeu — gesucht höchstens
// bis zum Swing-Tief vor dem Ausbruch b (AVGO Daily 04.08.2023 → 81,29 vom 06.07.; 30.10.2023 →
// 78,58 vom 06.10.)
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
// bricht (wie provisionalMark in backtest_logic.js, live gws_core.provisional_mark_break;
// AVGO 21.08.2023: Tief 18.08. bei 78,18, Marke 82,28 vom 15.08., Schluss 83,30 → grün)
function provisionalMark(highs, lows, closes, swingHighs, swingLows, n) {
  const k = n - 2, last = swingLows[swingLows.length - 1];
  if (k < 2 || !last || last.idx >= k) return null;
  if (!(lows[k] <= lows[k-1] && lows[k] <= lows[k-2] && lows[k] <= lows[k+1] && lows[k] < last.price)) return null;
  const hs = swingHighs.filter(h => h.idx > last.idx && h.idx < k);
  if (!hs.length) return null;
  const mark = hs.reduce((a, h) => h.price > a.price ? h : a);
  return closes[n - 1] > mark.price ? { ...mark, tiefAlt: last, tiefNeu: { idx: k, price: lows[k] } } : null;
}
// Gehaltene Marke: { b: Index der Ausbruchskerze, anchor } oder null
function heldBreakout(cands, closes, lows, n, breakoutIdx, weekly = false, closedBelow = null) {
  for (let c = cands.length - 1; c >= 0; c--) {
    let b = -1;
    if (breakoutIdx) b = breakoutIdx(cands[c]);
    else for (let i = cands[c].idx + 1; i < n; i++) if (closes[i] > cands[c].price) { b = i; break; }
    if (b < 0) continue;
    const anchor = weekly ? weeklyAnchorLow(lows, cands[c].idx, b) : tuAnchorLow(cands[c + 1], lows, b);
    const from = !weekly && cands[c + 1]?.tiefNeu?.idx > b ? cands[c + 1].tiefNeu.idx : b + 1;
    if (closedBelow) { if (closedBelow(b, anchor)) return null; }
    else for (let i = from; i < n; i++) if (closes[i] < anchor) return null;
    return { b, anchor };
  }
  return null;
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
// Daily-Gültigkeit (seit 16.10.2026, Backtest = Live gws_core.retracement_zone): Untergrenze ist
// das Swing-Tief vor dem Ausbruch b. Sie rückt nur nach einem Rücksetzer von mindestens
// RETR_MIN_DAYS Handelstagen (zwei Wochenkerzen) zwischen dem bisherigen höchsten Hoch und einem
// neuen Hoch darüber nach — auf das tiefste Tief dieses Rücksetzers. Ein Schluss darunter beendet
// das Daily-Signal; ein neues beginnt beim nächsten Schluss über einem Swing-Hoch (MRNA 06.05.2021:
// Tief 143,56 unter 153,27, Schluss 160,50 darüber → bleibt). { from, top, low } oder null.
const RETR_MIN_DAYS = 10;
function retracementZone(highs, lows, closes, b, n) {
  const isLow  = k => k >= 1 && k + 1 < n && lows[k] <= lows[k - 1] && lows[k] <= lows[k + 1];
  const isHigh = k => k >= 1 && k + 1 < n && highs[k] >= highs[k - 1] && highs[k] >= highs[k + 1];
  const lowBefore = s => {
    for (let k = s - 2; k >= 1; k--) if (isLow(k)) return lows[k];   // bestätigt vor s
    return Math.min(...lows.slice(Math.max(0, s - 5), s + 1));
  };
  const highAfter = (k, after) => {
    for (let j = k - 2; j > after; j--) if (isHigh(j)) return highs[j];
    return null;
  };
  let start = b, low = lowBefore(b), peak = highs[b], peakIdx = b, last = b;
  for (let k = b + 1; k < n; k++) {
    if (start >= 0) {
      if (closes[k] < low) { start = -1; last = k; continue; }
      if (highs[k] > peak) {
        if (k - peakIdx >= RETR_MIN_DAYS) low = Math.min(...lows.slice(peakIdx, k + 1));
        peak = highs[k]; peakIdx = k;
      }
    } else {
      const sh = highAfter(k, last);
      if (sh != null && closes[k] > sh) { start = k; low = lowBefore(k); peak = highs[k]; peakIdx = k; last = k; }
    }
  }
  return start >= 0 ? { from: start, top: peak, low } : null;
}
function zoneFrom(bars, z) {
  return z ? { from: bars[z.from].d, top: z.top, anchor: z.low } : null;
}

// Weekly: Ausbruchswoche = Woche mit dem ersten Tagesschluss über der Marke
function weeklyBreakoutIdx(ohlcvW, ohlcvD) {
  return cand => {
    const day = ohlcvD.find(d => d.d > cand.date && d.c > cand.price);
    if (!day) return -1;
    let b = -1;
    for (let i = 0; i < ohlcvW.length && ohlcvW[i].d <= day.d; i++) b = i;
    return b;
  };
}

// Gültigkeitsbereiche je Chart (wie validityZones in backtest_logic.js): je angezeigter
// Kerze die Struktur zu ihrem Schluss; grüne Kerzen gehören zum Bereich ihrer
// Ausbruchskerze — von dort bis zur letzten grünen Kerze, vom höchsten Hoch seit der
// Ausbruchskerze bis zum Anker. Ergebnis: [{ start, end, top, anchor, held }] mit Indizes in shown.
function validityZones(shown, structAt) {
  const zones = [];
  if (!shown) return zones;
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
function weeklyZones(ohlcvW, ohlcvD, shown) {
  if (!ohlcvW) return [];
  return validityZones(shown, b => {
    const a = ohlcvW.findIndex(w => w.d === b.d);
    if (a < 0) return null;
    const next = ohlcvW[a + 1]?.d;
    const days = ohlcvD ? ohlcvD.filter(d => !next || d.d < next) : null;
    return analyzeWeeklyStructure(ohlcvW.slice(0, a + 1), days);
  });
}
function dailyZones(ohlcvD, shown) {
  if (!ohlcvD) return [];
  const idx = new Map(ohlcvD.map((b, i) => [b.d, i]));
  return validityZones(shown, b => {
    const i = idx.get(b.d);
    return i == null ? null : analyzeStructure(ohlcvD.slice(0, i + 1));
  });
}
function h4Zones(ohlcv4h, shown) {
  if (!ohlcv4h) return [];
  const idx = new Map(ohlcv4h.map((b, i) => [b.d, i]));
  return validityZones(shown, b => {
    const i = idx.get(b.d);
    return i == null ? null : analyze4HStructure(ohlcv4h.slice(Math.max(0, i - 59), i + 1));
  });
}

function analyzeStructure(ohlcv) {
  if (!ohlcv || ohlcv.length < 10) return null;
  const n      = ohlcv.length;
  const highs  = ohlcv.map(d => d.h);
  const lows   = ohlcv.map(d => d.l);
  const closes = ohlcv.map(d => d.c);

  // Swing-Hochs (±2 Bars)
  const swingHighs = [];
  for (let i = 2; i < n - 2; i++) {
    if (highs[i] >= highs[i-1] && highs[i] >= highs[i-2] &&
        highs[i] >= highs[i+1] && highs[i] >= highs[i+2])
      swingHighs.push({ idx: i, date: ohlcv[i].d, price: highs[i] });
  }

  // Swing-Tiefs (±2 Bars)
  const swingLows = [];
  for (let i = 2; i < n - 2; i++) {
    if (lows[i] <= lows[i-1] && lows[i] <= lows[i-2] &&
        lows[i] <= lows[i+1] && lows[i] <= lows[i+2])
      swingLows.push({ idx: i, date: ohlcv[i].d, price: lows[i] });
  }

  // ── Kernlogik: Tiefere Tiefs erkennen und GWS-D bestimmen ──────────────────
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
          idx:      gwsdHoch.idx,
          date:     gwsdHoch.date,
          price:    gwsdHoch.price,
          tiefAlt:  tiefAlt,
          tiefNeu:  tiefNeu,
        });
      }
    }
  }

  let gwsdHigh     = gwsdCandidates.length > 0 ? gwsdCandidates[gwsdCandidates.length - 1] : null;
  let prevGwsdHigh = gwsdCandidates.length > 1 ? gwsdCandidates[gwsdCandidates.length - 2] : null;

  let breakoutIdx = null;
  if (gwsdHigh) {
    for (let i = gwsdHigh.idx + 1; i < n; i++) {
      if (closes[i] > gwsdHigh.price) { breakoutIdx = i; break; }
    }
  }
  // Ausbruch bestätigt das Swing-Tief (wie provisionalMark in backtest_logic.js)
  if (breakoutIdx === null) {
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

  // held: grün nur durch das Signal-Halten (Marke selbst ungebrochen) — Chart-Hinterlegung
  const heldD        = gwsdHigh !== null && breakoutIdx === null ? heldBreakout(gwsdCandidates, closes, lows, n) : null;
  const held         = heldD !== null;
  let broken         = breakoutIdx !== null || (gwsdHigh === null && trend === "bullish") || held;
  // Gültigkeitsbereich wie backtest_logic.js: Untergrenze nach retracementZone, ein Schluss
  // darunter beendet das Daily-Signal
  const zb = breakoutIdx !== null ? breakoutIdx : held ? heldD.b : null;
  const rz = zb === null ? null : retracementZone(highs, lows, closes, zb, n);
  if (zb !== null && !rz) broken = false;
  const zone = rz ? zoneFrom(ohlcv, rz) : null;
  const currentClose = closes[n - 1];

  const recentBreakout = broken && (n - 1 - breakoutIdx <= 7);

  return {
    currentClose, gwsdHigh, breakoutIdx, breakoutPrice, broken, held, zone, trend,
    prevGwsdHigh, prevBreakoutIdx,
    recentBreakout,
    swingHighs: swingHighs.slice(-6),
    swingLows:  swingLows.slice(-6),
    setup: broken && trend !== "bearish",
  };
}

// ── GWS-W Analyse (Weekly, gleiche korrekte Logik) ───────────────────────────
// ohlcvD (optional): Tageskerzen für die Ausbruchswoche beim Signal-Halten
function analyzeWeeklyStructure(ohlcvW, ohlcvD = null) {
  if (!ohlcvW || ohlcvW.length < 8) return null;
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

  // Gleiche Kernlogik: tiefere Tiefs → GWS-W = höchstes Hoch dazwischen
  const gwswCandidates = [];
  for (let j = 1; j < swingLows.length; j++) {
    const tiefNeu = swingLows[j];
    const tiefAlt = swingLows[j - 1];
    if (tiefNeu.price < tiefAlt.price) {
      const hochsDazwischen = swingHighs.filter(
        sh => sh.idx > tiefAlt.idx && sh.idx < tiefNeu.idx
      );
      if (hochsDazwischen.length > 0) {
        const gwswHoch = hochsDazwischen.reduce((best, h) => h.price > best.price ? h : best);
        gwswCandidates.push({ idx: gwswHoch.idx, date: gwswHoch.date, price: gwswHoch.price });
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

  // Trend: höhere Swing-Hochs = bullish (deckt reine Uptrends wie ROST ab)
  let trend = "neutral";
  if (swingHighs.length >= 2) {
    const last = swingHighs[swingHighs.length - 1];
    const prev = swingHighs[swingHighs.length - 2];
    if (last.price > prev.price) trend = "bullish";
    else if (last.price < prev.price) trend = "bearish";
  }

  // Broken: GWS durchbrochen ODER kein GWS-Muster aber klarer Aufwärtstrend
  // Weekly-Bruch wie anchorWalk in backtest_logic.js: Wochentief unter dem Anker ab der Woche nach
  // der Ausbruchswoche b; bei jedem erneuten Ausbruch (Wochenschluss über dem letzten Swing-Hoch)
  // rückt der Anker auf das Swing-Tief davor (ZS: 08.01.2024 → 206,67, Woche 19.02. Tief 202,44 → rot)
  const isSwingLow = k => k >= 1 && k + 1 < n && lows[k] <= lows[k - 1] && lows[k] <= lows[k + 1];
  const isSwingHigh = k => k >= 1 && k + 1 < n && highs[k] >= highs[k - 1] && highs[k] >= highs[k + 1];
  const anchorWalk = (b, anchor) => {
    let last = b;
    for (let k = b + 1; k < n; k++) {
      if (lows[k] < anchor) return { lost: true, anchor };
      let sh = null;
      for (let j = k - 2; j > last; j--) if (isSwingHigh(j)) { sh = highs[j]; break; }
      if (sh != null && closes[k] > sh) {
        for (let j = k - 1; j > last; j--) if (isSwingLow(j)) { anchor = Math.max(anchor, lows[j]); break; }
        last = k;
      }
    }
    return { lost: false, anchor };
  };
  const closedBelow = (b, anchor) => anchorWalk(b, anchor).lost;
  const heldW = gwswHigh !== null && breakoutIdx === null ? heldBreakout(gwswCandidates, closes, lows, n,
    ohlcvD?.length ? weeklyBreakoutIdx(ohlcvW, ohlcvD) : undefined, true, closedBelow) : null;
  const held = heldW !== null;
  // gebrochene Marke: erlischt schon beim Unterschreiten des Ankers, bevor die Trendumkehr eine neue
  // Marke bildet (PANW KW 09.05.2022)
  const markLost = breakoutIdx !== null && closedBelow(breakoutIdx, weeklyAnchorLow(lows, gwswHigh.idx, breakoutIdx));
  const broken = (breakoutIdx !== null && !markLost) || (gwswHigh === null && trend === "bullish") || held;
  // Gültigkeitsbereich: Ausbruchswoche und Anker (letztes Swing-Tief vor dem Ausbruch)
  const zone = breakoutIdx !== null && !markLost
    ? { from: ohlcvW[breakoutIdx].d, top: Math.max(...highs.slice(breakoutIdx)), anchor: anchorWalk(breakoutIdx, weeklyAnchorLow(lows, gwswHigh.idx, breakoutIdx)).anchor }
    : held ? { from: ohlcvW[heldW.b].d, top: Math.max(...highs.slice(heldW.b)), anchor: heldW.anchor } : null;

  const recentBreakout = breakoutIdx !== null && (n - 1 - breakoutIdx <= 1);

  return {
    gwswHigh, breakoutIdx, breakoutPrice, broken, held, zone,
    prevGwswHigh, prevBreakoutIdx,
    recentBreakout,
    swingHighs: swingHighs.slice(-6),
    swingLows:  swingLows.slice(-6),
  };
}

// ── GWS-4H Analyse (gleiche korrekte Logik) ──────────────────────────────────
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

  // Gleiche Kernlogik: tiefere Tiefs → GWS-4H = höchstes Hoch dazwischen
  const gws4hCandidates = [];
  for (let j = 1; j < swingLows.length; j++) {
    const tiefNeu = swingLows[j];
    const tiefAlt = swingLows[j - 1];
    if (tiefNeu.price < tiefAlt.price) {
      const hochsDazwischen = swingHighs.filter(
        sh => sh.idx > tiefAlt.idx && sh.idx < tiefNeu.idx
      );
      if (hochsDazwischen.length > 0) {
        const gws4hHoch = hochsDazwischen.reduce((best, h) => h.price > best.price ? h : best);
        gws4hCandidates.push({ idx: gws4hHoch.idx, date: gws4hHoch.date, price: gws4hHoch.price });
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
    gws4hHigh, breakout4hIdx, broken4h: breakout4hIdx !== null || (gws4hHigh === null && trend4h === "bullish"),
    // Gültigkeitsbereich: ab Ausbruchskerze, unten nachgezogenes Swing-Tief (nur Darstellung)
    zone: breakout4hIdx !== null ? zoneFrom(ohlcv4h, trailingZone(highs, lows, closes, breakout4hIdx, n)) : null,
    prevGws4hHigh, prevBreakout4hIdx,
    recentBreakout,
    swingHighs: swingHighs.slice(-8),
    swingLows:  swingLows.slice(-8),
  };
}

// ── Gemeinsame Legende, einmal über dem ersten Chart ─────────────────────────
// Die einzige Legende der Charts (unter den Charts steht keine): GWS-Linien je Ebene,
// letzter Break, Gültigkeitsbereich, Trendlinie, Kurslinie, Benchmark und Signal
function ChartLegend({ benchLabel = null, showSignal = false }) {
  const item = { display: "flex", alignItems: "center", gap: 4 };
  const txt  = { fontSize: 9, color: "#64748b" };
  const dash = (color, w = 1.8, op = 1) =>
    <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke={color} strokeWidth={w} strokeDasharray="4,3" opacity={op}/></svg>;
  return (
    <div style={{padding:"6px 12px",marginBottom:12,display:"flex",gap:"4px 14px",alignItems:"center",background:"#0a0f1e",border:"1px solid #1e293b",borderRadius:10,flexWrap:"wrap",fontFamily:"monospace"}}>
      <div style={item}>
        {dash("#f59e0b")}<span style={txt}>GWS-W</span>
        {dash("#ef4444")}<span style={txt}>GWS-D</span>
        {dash("#a78bfa")}<span style={txt}>GWS-4H</span>
      </div>
      <div style={item}>{dash("#94a3b8", 1.2, 0.35)}<span style={txt}>letzter Break (gedimmt, Farbe der Ebene)</span></div>
      <div style={item}>
        <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#4ade80" strokeWidth="1.2" strokeDasharray="3,6" opacity="0.7"/></svg>
        <span style={txt}>Trend ↑ (höhere Hochs, keine GWS)</span>
      </div>
      <div style={item}>
        <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#7dd3fc" strokeWidth="0.9" strokeDasharray="2,3" opacity="0.7"/></svg>
        <span style={txt}>letzter Kurs</span>
      </div>
      {benchLabel && (
        <div style={item}>
          <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#64748b" strokeWidth="1.2" opacity="0.55"/></svg>
          <span style={txt}>{benchLabel} (Weekly/Daily)</span>
        </div>
      )}
      {showSignal && (
        <div style={item}>
          <svg width="10" height="16"><polygon points="5,0 9,8 1,8" fill="#eab308"/><line x1="5" x2="5" y1="8" y2="16" stroke="#eab308" strokeWidth="1.5"/></svg>
          <span style={{...txt, color:"#eab308"}}>Signal</span>
        </div>
      )}
      <div style={item}>
        <svg width="14" height="10"><rect width="14" height="10" fill="#22c55e" opacity="0.3"/><line x1="0" x2="14" y1="9.5" y2="9.5" stroke="#22c55e" strokeDasharray="2,2"/></svg>
        <span style={txt}>Gültigkeitsbereich (kräftig = nur gehalten): ab Ausbruchskerze, vom höchsten Hoch seit dem Ausbruch bis zur gestrichelten Linie — Weekly: Anker des Signals (letztes Swing-Tief vor dem Ausbruch, bei erneutem Ausbruch nachgezogen; Wochentief darunter beendet das Signal); Daily/4H: Swing-Tief vor dem Ausbruch (SL-Höhe), springt bei jedem weiteren Ausbruch nach oben auf das Swing-Tief davor</span>
      </div>
    </div>
  );
}

// ── Weekly Candlestick Chart ───────────────────────────────────────────────
function ChartWeekly({ ohlcvW, structureW, chartId, benchOhlcv, benchLabel, signals = [], zones = null }) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);
  const W = 600, H = 260;
  const PL = 56, PR = 52, PT = 18, PB = 32;
  const cW = W - PL - PR, cH = H - PT - PB;
  const n = ohlcvW.length;
  const allH = ohlcvW.map(d => d.h), allL = ohlcvW.map(d => d.l);
  const rawMax = Math.max(...allH), rawMin = Math.min(...allL);
  const pad = (rawMax - rawMin) * 0.07;
  const maxP = rawMax + pad, minP = rawMin - pad, range = maxP - minP;
  const toY = p => PT + (1 - (p - minP) / range) * cH;
  const toX = i => PL + (i + 0.5) * (cW / n);
  const bW  = Math.max(2, cW / n * 0.65);

  const yTicks = [];
  for (let k = 0; k <= 5; k++) yTicks.push(minP + k * range / 5);

  // Monats-Labels für Weekly
  const monthLabels = [];
  let lastMonth = null;
  ohlcvW.forEach((d, i) => {
    const m = d.d.slice(0, 7);
    if (m !== lastMonth) { monthLabels.push({ i, label: d.d.slice(5,7)+"/"+d.d.slice(2,4) }); lastMonth = m; }
  });

  const { gwswHigh, breakoutIdx, breakoutPrice, broken, prevGwswHigh, prevBreakoutIdx } = structureW || {};

  // Index-Linie (grau) – normalisiert auf Aktien-Preisskala
  const benchLine = useMemo(() => {
    if (!benchOhlcv || !ohlcvW.length) return [];
    const benchMap = {};
    benchOhlcv.forEach(d => { benchMap[d.d] = d.c; });
    let stockRef = null, benchRef = null;
    for (const d of ohlcvW) {
      if (benchMap[d.d] != null) { stockRef = d.c; benchRef = benchMap[d.d]; break; }
    }
    if (!stockRef || !benchRef) return [];
    return ohlcvW.map((d, i) => {
      const bc = benchMap[d.d];
      return bc != null ? { i, price: stockRef * (bc / benchRef) } : null;
    }).filter(Boolean);
  }, [benchOhlcv, ohlcvW]);
  const gwswColor  = "#f59e0b"; // Amber für Weekly
  const gwswLineEnd = breakoutIdx !== null ? breakoutIdx : n - 1;

  const handleMouseMove = useCallback((e) => {
    const svg = svgRef.current; if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (W / rect.width);
    const idx = Math.round((mx - PL) / (cW / n) - 0.5);
    setHover(idx >= 0 && idx < n ? idx : null);
  }, [n, cW]);

  const hd = hover !== null ? ohlcvW[hover] : null;

  return (
    <div className="chart-wrap" style={{background:"#07090f",borderRadius:8,border:"1px solid #1e293b",overflow:"hidden"}}>
      <div style={{height:28,padding:"0 12px",display:"flex",alignItems:"center",gap:14,background:"#0a0f1e",borderBottom:"1px solid #1e293b",fontSize:10,fontFamily:"monospace"}}>
        {hd ? <>
          <span style={{color:"#475569"}}>{hd.d}</span>
          <span>O <span style={{color:"#e2e8f0"}}>{hd.o.toFixed(2)}</span></span>
          <span>H <span style={{color:"#4ade80"}}>{hd.h.toFixed(2)}</span></span>
          <span>L <span style={{color:"#f87171"}}>{hd.l.toFixed(2)}</span></span>
          <span>C <span style={{color:hd.c>=hd.o?"#4ade80":"#f87171",fontWeight:700}}>{hd.c.toFixed(2)}</span></span>
          <span style={{color:"#475569",marginLeft:"auto"}}>{hd.c>=hd.o?"▲":"▼"} {((hd.c-hd.o)/hd.o*100).toFixed(2)}%</span>
        </> : <span style={{color:"#334155"}}>Hover für Weekly-Details</span>}
      </div>

      <svg ref={svgRef} width="100%" viewBox={`0 0 ${W} ${H}`}
        onMouseMove={handleMouseMove} onMouseLeave={()=>setHover(null)} style={{cursor:"crosshair"}}>
        <defs>
          <linearGradient id={`bgW_${chartId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#22c55e" stopOpacity="0.10"/>
            <stop offset="100%" stopColor="#22c55e" stopOpacity="0.01"/>
          </linearGradient>
          <clipPath id={`clipW_${chartId}`}>
            <rect x={PL} y={PT} width={cW} height={cH}/>
          </clipPath>
        </defs>
        <rect x={PL} y={PT} width={cW} height={cH} fill="#07090f"/>

        {/* Gitter */}
        {yTicks.map((val, k) => {
          const y = toY(val);
          return <g key={k}>
            <line x1={PL} x2={PL+cW} y1={y} y2={y} stroke="#1a2235" strokeWidth="0.8"/>
            <text x={PL-5} y={y+3.5} textAnchor="end" fill="#334155" fontSize="9" fontFamily="monospace">{val.toFixed(0)}</text>
          </g>;
        })}

        {/* Monatstrennlinien */}
        {monthLabels.map(({i, label}) => (
          <g key={i}>
            <line x1={toX(i)} x2={toX(i)} y1={PT} y2={PT+cH} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,4" opacity="0.25"/>
            <text x={toX(i)} y={PT+cH+14} textAnchor="middle" fill="#334155" fontSize="8.5" fontFamily="monospace">{label}</text>
          </g>
        ))}

        {/* Breakout-Zone (nur ohne Gültigkeitsbereiche) */}
        {!zones && breakoutIdx !== null && (
          <rect x={toX(breakoutIdx)} y={PT} width={PL+cW-toX(breakoutIdx)} height={cH} fill={`url(#bgW_${chartId})`}/>
        )}

        {/* Index-Linie (grau) */}
        {benchLine.length > 1 && (
          <polyline
            points={benchLine.map(({i, price}) => `${toX(i)},${toY(price)}`).join(' ')}
            fill="none" stroke="#64748b" strokeWidth="1.2" opacity="0.55"
            clipPath={`url(#clipW_${chartId})`}/>
        )}

        {/* Vorheriger GWS-W Break (gedimmt) */}
        {prevGwswHigh && (() => {
          const prevLineEnd = prevBreakoutIdx !== null ? prevBreakoutIdx : (gwswHigh ? gwswHigh.idx : n - 1);
          const y  = toY(prevGwswHigh.price);
          const x1 = toX(prevGwswHigh.idx);
          const x2 = toX(prevLineEnd);
          return <>
            <line x1={x1} x2={x2} y1={y} y2={y} stroke={gwswColor} strokeWidth="1.2" strokeDasharray="4,4" opacity="0.30"/>
          </>;
        })()}

        {/* Aktueller GWS-W */}
        {gwswHigh && (() => {
          const y  = toY(breakoutPrice ?? gwswHigh.price);
          const x1 = toX(gwswHigh.idx);
          const x2 = toX(gwswLineEnd);
          return <line x1={x1} x2={x2} y1={y} y2={y} stroke={gwswColor} strokeWidth="1.8" strokeDasharray="5,4"/>;
        })()}
                {/* Trend-Fallback: kein GWS aber höhere Hochs (Weekly) */}
        {broken && !gwswHigh && structureW?.swingHighs?.length >= 2 && (() => {
          const lastSH = structureW.swingHighs[structureW.swingHighs.length - 1];
          const y = toY(lastSH.price);
          return <>
            <line x1={PL} x2={PL+cW} y1={y} y2={y} stroke="#4ade80" strokeWidth="1.2" strokeDasharray="3,6" opacity="0.7"/>
            <text x={PL+6} y={y-4} fill="#4ade80" fontSize="8" fontFamily="monospace" opacity="0.8">Trend ↑</text>
          </>;
        })()}

        {/* Gültigkeitsbereiche: Ausbruchskerze bis letzte grüne Kerze, vom höchsten Hoch
            seit der Ausbruchskerze bis zum Anker (Schluss darunter → Signal erlischt); gehalten kräftiger */}
        {zones && zones.map((z, zi) => {
          const x1 = PL + z.start * (cW / n), x2 = PL + (z.end + 1) * (cW / n);
          const clampY = y => Math.min(PT + cH, Math.max(PT, y));
          const yA = clampY(toY(z.anchor)), yT = clampY(toY(z.top));
          return <g key={`zone${zi}`}>
            <rect x={x1} y={yT} width={x2 - x1} height={Math.max(0, yA - yT)} fill="#22c55e" opacity={z.held ? 0.22 : 0.13}/>
            <line x1={x1} x2={x2} y1={yA} y2={yA} stroke="#22c55e" strokeWidth="1" strokeDasharray="3,3" opacity="0.8"/>
          </g>;
        })}

        {/* Kerzen */}
        {ohlcvW.map((d, i) => {
          const bull = d.c >= d.o;
          const isBoc = i === breakoutIdx;
          const col  = bull ? "#22c55e" : "#ef4444";
          const bTop = toY(Math.max(d.o, d.c));
          const bH   = Math.max(1.5, toY(Math.min(d.o, d.c)) - bTop);
          const isHov = hover === i;
          return <g key={i}>
            <line x1={toX(i)} x2={toX(i)} y1={toY(d.h)} y2={toY(d.l)} stroke={col} strokeWidth={isHov?1.5:1} opacity={0.9}/>
            <rect x={toX(i)-bW/2} y={bTop} width={bW} height={bH}
              fill={col} opacity={isBoc?1:isHov?0.95:0.8}
              stroke={isBoc?gwswColor:"none"} strokeWidth={isBoc?1.2:0}/>
          </g>;
        })}

        {/* Signal-Pfeile (Weekly-Chart: alle Timeframes) */}
        {signals.map((sig, si) => {
          const td = sig.weekly_bar_date?.slice(0,10);
          if (!td) return null;
          const idx = ohlcvW.findIndex(d => d.d.slice(0,10) === td);
          if (idx < 0) return null;
          const x = toX(idx);
          const yTip = Math.min(toY(ohlcvW[idx].l) + 4, PT + cH - 28);
          const lbl = [sig.weekly_bar_date&&'W', sig.daily_bar_date&&'D', sig.h4_bar_date&&'4H'].filter(Boolean).join('/');
          return <g key={si}>
            <rect x={x-6} y={yTip-2} width={12} height={22} rx={2} fill="#eab308" opacity={0.2}/>
            <polygon points={`${x-4},${yTip+8} ${x+4},${yTip+8} ${x},${yTip}`} fill="#eab308" opacity="0.95"/>
            <line x1={x} x2={x} y1={yTip+8} y2={yTip+18} stroke="#eab308" strokeWidth="1.5" opacity="0.95"/>
            <text x={x} y={yTip+28} textAnchor="middle" fill="#eab308" fontSize="7" fontFamily="monospace" opacity="0.9">{lbl}</text>
          </g>;
        })}

        {/* Aktueller Preis */}
        <line x1={PL} x2={PL+cW} y1={toY(ohlcvW[n-1].c)} y2={toY(ohlcvW[n-1].c)} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.45"/>
        <rect x={PL+cW+2} y={toY(ohlcvW[n-1].c)-8} width={46} height={15} rx="3" fill="#1e293b"/>
        <text x={PL+cW+25} y={toY(ohlcvW[n-1].c)+3} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">{ohlcvW[n-1].c.toFixed(2)}</text>

        {/* Crosshair */}
        {hover !== null && <>
          <line x1={toX(hover)} x2={toX(hover)} y1={PT} y2={PT+cH} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.5"/>
          <line x1={PL} x2={PL+cW} y1={toY(ohlcvW[hover].c)} y2={toY(ohlcvW[hover].c)} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.5"/>
          <rect x={PL-52} y={toY(ohlcvW[hover].c)-8} width={48} height={15} rx="3" fill="#1e293b"/>
          <text x={PL-28} y={toY(ohlcvW[hover].c)+3} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">{ohlcvW[hover].c.toFixed(2)}</text>
        </>}
        <rect x={PL} y={PT} width={cW} height={cH} fill="none" stroke="#1e293b" strokeWidth="0.8"/>
      </svg>

      <div style={{padding:"5px 12px",display:"flex",gap:14,alignItems:"center",background:"#0a0f1e",borderTop:"1px solid #0f172a",flexWrap:"wrap"}}>
        <div style={{marginLeft:"auto",fontSize:9,color:"#334155",fontFamily:"monospace"}}>{ohlcvW.length} Wochen · Weekly</div>
      </div>
    </div>
  );
}

// ── Daily Candlestick Chart ────────────────────────────────────────────────
function CandleChart({ ohlcv, structure, chartId, benchOhlcv, benchLabel, signals = [], zones = null }) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);
  const W = 600, H = 270;
  const PL = 56, PR = 52, PT = 18, PB = 32;
  const cW = W - PL - PR, cH = H - PT - PB;
  const n = ohlcv.length;
  const allH = ohlcv.map(d => d.h), allL = ohlcv.map(d => d.l);
  const rawMax = Math.max(...allH), rawMin = Math.min(...allL);
  const pad = (rawMax - rawMin) * 0.07;
  const maxP = rawMax + pad, minP = rawMin - pad, range = maxP - minP;
  const toY = p => PT + (1 - (p - minP) / range) * cH;
  const toX = i => PL + (i + 0.5) * (cW / n);
  const bW  = Math.max(2, cW / n * 0.65);

  const yTicks = [];
  for (let k = 0; k <= 5; k++) yTicks.push(minP + k * range / 5);

  const monthLabels = [];
  let lastMonth = null;
  ohlcv.forEach((d, i) => {
    const m = d.d.slice(0, 7);
    if (m !== lastMonth) { monthLabels.push({ i, label: d.d.slice(5,7)+"/"+d.d.slice(2,4) }); lastMonth = m; }
  });

  const { gwsdHigh, breakoutIdx, breakoutPrice, broken, prevGwsdHigh, prevBreakoutIdx } = structure || {};

  // Index-Linie (grau) – normalisiert auf Aktien-Preisskala
  const benchLine = useMemo(() => {
    if (!benchOhlcv || !ohlcv.length) return [];
    const benchMap = {};
    benchOhlcv.forEach(d => { benchMap[d.d] = d.c; });
    let stockRef = null, benchRef = null;
    for (const d of ohlcv) {
      if (benchMap[d.d] != null) { stockRef = d.c; benchRef = benchMap[d.d]; break; }
    }
    if (!stockRef || !benchRef) return [];
    return ohlcv.map((d, i) => {
      const bc = benchMap[d.d];
      return bc != null ? { i, price: stockRef * (bc / benchRef) } : null;
    }).filter(Boolean);
  }, [benchOhlcv, ohlcv]);
  const gwsdColor   = "#ef4444";
  const gwsdLineEnd = breakoutIdx !== null ? breakoutIdx : n - 1;

  const handleMouseMove = useCallback((e) => {
    const svg = svgRef.current; if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (W / rect.width);
    const idx = Math.round((mx - PL) / (cW / n) - 0.5);
    setHover(idx >= 0 && idx < n ? idx : null);
  }, [n, cW]);

  const hd = hover !== null ? ohlcv[hover] : null;

  return (
    <div className="chart-wrap" style={{background:"#07090f",borderRadius:8,border:"1px solid #1e293b",overflow:"hidden"}}>
      <div style={{height:28,padding:"0 12px",display:"flex",alignItems:"center",gap:14,background:"#0a0f1e",borderBottom:"1px solid #1e293b",fontSize:10,fontFamily:"monospace"}}>
        {hd ? <>
          <span style={{color:"#475569"}}>{hd.d}</span>
          <span>O <span style={{color:"#e2e8f0"}}>{hd.o.toFixed(2)}</span></span>
          <span>H <span style={{color:"#4ade80"}}>{hd.h.toFixed(2)}</span></span>
          <span>L <span style={{color:"#f87171"}}>{hd.l.toFixed(2)}</span></span>
          <span>C <span style={{color:hd.c>=hd.o?"#4ade80":"#f87171",fontWeight:700}}>{hd.c.toFixed(2)}</span></span>
          <span style={{color:"#475569",marginLeft:"auto"}}>{hd.c>=hd.o?"▲":"▼"} {((hd.c-hd.o)/hd.o*100).toFixed(2)}%</span>
        </> : <span style={{color:"#334155"}}>Hover für Daily-Details</span>}
      </div>

      <svg ref={svgRef} width="100%" viewBox={`0 0 ${W} ${H}`}
        onMouseMove={handleMouseMove} onMouseLeave={()=>setHover(null)} style={{cursor:"crosshair"}}>
        <defs>
          <linearGradient id={`bg_${chartId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#22c55e" stopOpacity="0.12"/>
            <stop offset="100%" stopColor="#22c55e" stopOpacity="0.01"/>
          </linearGradient>
          <clipPath id={`clipD_${chartId}`}>
            <rect x={PL} y={PT} width={cW} height={cH}/>
          </clipPath>
        </defs>
        <rect x={PL} y={PT} width={cW} height={cH} fill="#07090f"/>

        {/* Gitter */}
        {yTicks.map((val, k) => {
          const y = toY(val);
          return <g key={k}>
            <line x1={PL} x2={PL+cW} y1={y} y2={y} stroke="#1a2235" strokeWidth="0.8"/>
            <text x={PL-5} y={y+3.5} textAnchor="end" fill="#334155" fontSize="9" fontFamily="monospace">{val.toFixed(0)}</text>
          </g>;
        })}

        {/* Monatstrennlinien */}
        {monthLabels.map(({i, label}) => (
          <g key={i}>
            <line x1={toX(i)} x2={toX(i)} y1={PT} y2={PT+cH} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,4" opacity="0.25"/>
            <text x={toX(i)} y={PT+cH+14} textAnchor="middle" fill="#334155" fontSize="8.5" fontFamily="monospace">{label}</text>
          </g>
        ))}

        {/* Breakout-Zone (nur ohne Gültigkeitsbereiche) */}
        {!zones && breakoutIdx !== null && (
          <rect x={toX(breakoutIdx)} y={PT}
            width={PL+cW-toX(breakoutIdx)} height={cH}
            fill={`url(#bg_${chartId})`}/>
        )}

        {/* Index-Linie (grau) */}
        {benchLine.length > 1 && (
          <polyline
            points={benchLine.map(({i, price}) => `${toX(i)},${toY(price)}`).join(' ')}
            fill="none" stroke="#64748b" strokeWidth="1.2" opacity="0.55"
            clipPath={`url(#clipD_${chartId})`}/>
        )}

        {/* Vorheriger GWS-D Break (gedimmt) */}
        {prevGwsdHigh && (() => {
          const prevLineEnd = prevBreakoutIdx !== null ? prevBreakoutIdx : (gwsdHigh ? gwsdHigh.idx : n - 1);
          const y  = toY(prevGwsdHigh.price);
          const x1 = toX(prevGwsdHigh.idx);
          const x2 = toX(prevLineEnd);
          return <>
            <line x1={x1} x2={x2} y1={y} y2={y} stroke="#ef4444" strokeWidth="1.2" strokeDasharray="4,4" opacity="0.35"/>
          </>;
        })()}

        {/* Aktueller GWS-D */}
        {gwsdHigh && (() => {
          const levelPrice = breakoutPrice ?? gwsdHigh.price;
          const y  = toY(levelPrice);
          const x1 = toX(gwsdHigh.idx);
          const x2 = toX(gwsdLineEnd);
          return <line x1={x1} x2={x2} y1={y} y2={y} stroke={gwsdColor} strokeWidth="1.8" strokeDasharray="5,4"/>;
        })()}

                {/* Trend-Fallback: kein GWS aber höhere Hochs (Daily) */}
        {broken && !gwsdHigh && structure?.swingHighs?.length >= 2 && (() => {
          const lastSH = structure.swingHighs[structure.swingHighs.length - 1];
          const y = toY(lastSH.price);
          return <>
            <line x1={PL} x2={PL+cW} y1={y} y2={y} stroke="#4ade80" strokeWidth="1.2" strokeDasharray="3,6" opacity="0.7"/>
            <text x={PL+6} y={y-4} fill="#4ade80" fontSize="8" fontFamily="monospace" opacity="0.8">Trend ↑</text>
          </>;
        })()}

        {/* Gültigkeitsbereiche: Ausbruchskerze bis letzte grüne Kerze, vom höchsten Hoch
            seit der Ausbruchskerze bis zum Anker (Schluss darunter → Signal erlischt); gehalten kräftiger */}
        {zones && zones.map((z, zi) => {
          const x1 = PL + z.start * (cW / n), x2 = PL + (z.end + 1) * (cW / n);
          const clampY = y => Math.min(PT + cH, Math.max(PT, y));
          const yA = clampY(toY(z.anchor)), yT = clampY(toY(z.top));
          return <g key={`zone${zi}`}>
            <rect x={x1} y={yT} width={x2 - x1} height={Math.max(0, yA - yT)} fill="#22c55e" opacity={z.held ? 0.22 : 0.13}/>
            <line x1={x1} x2={x2} y1={yA} y2={yA} stroke="#22c55e" strokeWidth="1" strokeDasharray="3,3" opacity="0.8"/>
          </g>;
        })}

        {/* Kerzen */}
        {ohlcv.map((d, i) => {
          const bull = d.c >= d.o;
          const isBoc = i === breakoutIdx;
          const col  = bull ? "#22c55e" : "#ef4444";
          const bTop = toY(Math.max(d.o, d.c));
          const bH   = Math.max(1.5, toY(Math.min(d.o, d.c)) - bTop);
          const isHov = hover === i;
          return <g key={i}>
            <line x1={toX(i)} x2={toX(i)} y1={toY(d.h)} y2={toY(d.l)} stroke={col} strokeWidth={isHov?1.5:1} opacity={0.9}/>
            <rect x={toX(i)-bW/2} y={bTop} width={bW} height={bH}
              fill={col} opacity={isBoc?1:isHov?0.95:0.8}
              stroke={isBoc?"#ef4444":"none"} strokeWidth={isBoc?1.2:0}/>
          </g>;
        })}

        {/* Signal-Pfeile (Daily-Chart: Daily + 4H) */}
        {signals.filter(s => s.daily_bar_date).map((sig, si) => {
          const td = sig.daily_bar_date?.slice(0,10);
          if (!td) return null;
          const idx = ohlcv.findIndex(d => d.d.slice(0,10) === td);
          if (idx < 0) return null;
          const x = toX(idx);
          const yTip = Math.min(toY(ohlcv[idx].l) + 4, PT + cH - 28);
          const lbl = [sig.weekly_bar_date&&'W', sig.daily_bar_date&&'D', sig.h4_bar_date&&'4H'].filter(Boolean).join('/');
          return <g key={si}>
            <rect x={x-6} y={yTip-2} width={12} height={22} rx={2} fill="#eab308" opacity={0.2}/>
            <polygon points={`${x-4},${yTip+8} ${x+4},${yTip+8} ${x},${yTip}`} fill="#eab308" opacity="0.95"/>
            <line x1={x} x2={x} y1={yTip+8} y2={yTip+18} stroke="#eab308" strokeWidth="1.5" opacity="0.95"/>
            <text x={x} y={yTip+28} textAnchor="middle" fill="#eab308" fontSize="7" fontFamily="monospace" opacity="0.9">{lbl}</text>
          </g>;
        })}

        {/* Aktueller Preis */}
        <line x1={PL} x2={PL+cW} y1={toY(ohlcv[n-1].c)} y2={toY(ohlcv[n-1].c)} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.45"/>
        <rect x={PL+cW+2} y={toY(ohlcv[n-1].c)-8} width={46} height={15} rx="3" fill="#1e293b"/>
        <text x={PL+cW+25} y={toY(ohlcv[n-1].c)+3} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">{ohlcv[n-1].c.toFixed(2)}</text>

        {/* Crosshair */}
        {hover !== null && <>
          <line x1={toX(hover)} x2={toX(hover)} y1={PT} y2={PT+cH} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.5"/>
          <line x1={PL} x2={PL+cW} y1={toY(ohlcv[hover].c)} y2={toY(ohlcv[hover].c)} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.5"/>
          <rect x={PL-52} y={toY(ohlcv[hover].c)-8} width={48} height={15} rx="3" fill="#1e293b"/>
          <text x={PL-28} y={toY(ohlcv[hover].c)+3} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">{ohlcv[hover].c.toFixed(2)}</text>
        </>}
        <rect x={PL} y={PT} width={cW} height={cH} fill="none" stroke="#1e293b" strokeWidth="0.8"/>
      </svg>

      <div style={{padding:"5px 12px",display:"flex",gap:14,alignItems:"center",background:"#0a0f1e",borderTop:"1px solid #0f172a",flexWrap:"wrap"}}>
        <div style={{marginLeft:"auto",fontSize:9,color:"#334155",fontFamily:"monospace"}}>{ohlcv.length} Tage · Daily</div>
      </div>
    </div>
  );
}

// ── 4H Candlestick Chart (60 Kerzen) ─────────────────────────────────────────
function Chart4H({ ohlcv4h, structure4h, chartId, signals = [], zones = null }) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);
  const W = 600, H = 260;
  const PL = 56, PR = 52, PT = 18, PB = 32;
  const cW = W - PL - PR, cH = H - PT - PB;

  const display4h = useMemo(() => ohlcv4h, [ohlcv4h]);
  const n = display4h.length;

  const allH = display4h.map(d => d.h), allL = display4h.map(d => d.l);
  const rawMax = Math.max(...allH), rawMin = Math.min(...allL);
  const pad = (rawMax - rawMin) * 0.07;
  const maxP = rawMax + pad, minP = rawMin - pad, range = maxP - minP;
  const toY = p => PT + (1 - (p - minP) / range) * cH;
  const toX = i => PL + (i + 0.5) * (cW / n);
  const bW  = Math.max(1.5, cW / n * 0.65);

  const yTicks = [];
  for (let k = 0; k <= 5; k++) yTicks.push(minP + k * range / 5);

  const dayLabels = [];
  let lastDay = null;
  display4h.forEach((d, i) => {
    const day = d.d.slice(0, 10);
    if (day !== lastDay && i % 2 === 0) { dayLabels.push({ i, label: d.d.slice(5, 10) }); lastDay = day; }
  });

  const offset = 0;
  const { gws4hHigh, breakout4hIdx, broken4h, prevGws4hHigh, prevBreakout4hIdx } = structure4h || {};
  const col4h = broken4h ? "#ef4444" : "#a78bfa";

  const localGws4hIdx      = gws4hHigh      ? gws4hHigh.idx - offset      : null;
  const localBreakout4hIdx = breakout4hIdx  !== null ? breakout4hIdx - offset  : null;
  const localPrevGws4hIdx  = prevGws4hHigh  ? prevGws4hHigh.idx - offset  : null;
  const localPrevBreakIdx  = prevBreakout4hIdx !== null ? prevBreakout4hIdx - offset : null;

  const lineEnd4h = localBreakout4hIdx !== null && localBreakout4hIdx >= 0
    ? Math.min(localBreakout4hIdx, n - 1)
    : n - 1;

  const handleMouseMove = useCallback((e) => {
    const svg = svgRef.current; if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (W / rect.width);
    const idx = Math.round((mx - PL) / (cW / n) - 0.5);
    setHover(idx >= 0 && idx < n ? idx : null);
  }, [n, cW]);

  const hd = hover !== null ? display4h[hover] : null;

  return (
    <div className="chart-wrap" style={{background:"#07090f",borderRadius:8,border:"1px solid #1e293b",overflow:"hidden"}}>
      <div style={{height:28,padding:"0 12px",display:"flex",alignItems:"center",gap:14,background:"#0a0f1e",borderBottom:"1px solid #1e293b",fontSize:10,fontFamily:"monospace"}}>
        {hd ? <>
          <span style={{color:"#475569"}}>{hd.d}</span>
          <span>O <span style={{color:"#e2e8f0"}}>{hd.o.toFixed(2)}</span></span>
          <span>H <span style={{color:"#4ade80"}}>{hd.h.toFixed(2)}</span></span>
          <span>L <span style={{color:"#f87171"}}>{hd.l.toFixed(2)}</span></span>
          <span>C <span style={{color:hd.c>=hd.o?"#4ade80":"#f87171",fontWeight:700}}>{hd.c.toFixed(2)}</span></span>
        </> : <span style={{color:"#334155"}}>Hover für 4H-Details</span>}
      </div>

      <svg ref={svgRef} width="100%" viewBox={`0 0 ${W} ${H}`}
        onMouseMove={handleMouseMove} onMouseLeave={()=>setHover(null)} style={{cursor:"crosshair"}}>
        <defs>
          <linearGradient id={`g4h_${chartId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#22c55e" stopOpacity="0.13"/>
            <stop offset="100%" stopColor="#22c55e" stopOpacity="0.01"/>
          </linearGradient>
        </defs>
        <rect x={PL} y={PT} width={cW} height={cH} fill="#07090f"/>

        {yTicks.map((val, k) => {
          const y = toY(val);
          return <g key={k}>
            <line x1={PL} x2={PL+cW} y1={y} y2={y} stroke="#1a2235" strokeWidth="0.8"/>
            <text x={PL-5} y={y+3.5} textAnchor="end" fill="#334155" fontSize="9" fontFamily="monospace">{val.toFixed(0)}</text>
          </g>;
        })}

        {/* Tagestrennlinien */}
        {dayLabels.map(({i, label}) => (
          <g key={i}>
            <line x1={toX(i)} x2={toX(i)} y1={PT} y2={PT+cH} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,4" opacity="0.25"/>
            <text x={toX(i)} y={PT+cH+14} textAnchor="middle" fill="#334155" fontSize="8" fontFamily="monospace">{label}</text>
          </g>
        ))}

        {/* Breakout-Zone 4H (nur ohne Gültigkeitsbereiche) */}
        {!zones && localBreakout4hIdx !== null && localBreakout4hIdx >= 0 && (
          <rect x={toX(localBreakout4hIdx)} y={PT} width={PL+cW-toX(localBreakout4hIdx)} height={cH} fill={`url(#g4h_${chartId})`}/>
        )}

        {/* Vorheriger GWS-4H Break (gedimmt) */}
        {prevGws4hHigh && localPrevGws4hIdx !== null && localPrevGws4hIdx >= 0 && (() => {
          const prevEnd = localPrevBreakIdx !== null && localPrevBreakIdx >= 0
            ? Math.min(localPrevBreakIdx, localGws4hIdx !== null && localGws4hIdx >= 0 ? localGws4hIdx : n - 1)
            : (localGws4hIdx !== null && localGws4hIdx >= 0 ? localGws4hIdx : n - 1);
          const y  = toY(prevGws4hHigh.price);
          const x1 = toX(Math.max(0, localPrevGws4hIdx));
          const x2 = toX(prevEnd);
          return <>
            <line x1={x1} x2={x2} y1={y} y2={y} stroke={col4h} strokeWidth="1.1" strokeDasharray="4,4" opacity="0.3"/>
          </>;
        })()}

        {/* Aktueller GWS-4H */}
        {gws4hHigh && localGws4hIdx !== null && localGws4hIdx >= 0 && (() => {
          const y  = toY(gws4hHigh.price);
          const x1 = toX(localGws4hIdx);
          const x2 = toX(lineEnd4h);
          return <>
            <line x1={x1} x2={x2} y1={y} y2={y} stroke={col4h} strokeWidth="1.8" strokeDasharray="4,3"/>
          </>;
        })()}

                {/* Trend-Fallback: kein GWS aber höhere Hochs (4H) */}
        {broken4h && !gws4hHigh && structure4h?.swingHighs?.length >= 2 && (() => {
          const lastSH4h = structure4h.swingHighs[structure4h.swingHighs.length - 1];
          const localIdx = lastSH4h.idx - offset;
          if (localIdx < 0) return null;
          const y = toY(lastSH4h.price);
          return <>
            <line x1={PL} x2={PL+cW} y1={y} y2={y} stroke="#4ade80" strokeWidth="1.2" strokeDasharray="3,6" opacity="0.7"/>
            <text x={PL+6} y={y-4} fill="#4ade80" fontSize="8" fontFamily="monospace" opacity="0.8">Trend ↑</text>
          </>;
        })()}

        {/* Gültigkeitsbereiche: Ausbruchskerze bis letzte grüne Kerze, vom höchsten Hoch
            seit der Ausbruchskerze bis zum Anker (Schluss darunter → Signal erlischt); gehalten kräftiger */}
        {zones && zones.map((z, zi) => {
          const x1 = PL + z.start * (cW / n), x2 = PL + (z.end + 1) * (cW / n);
          const clampY = y => Math.min(PT + cH, Math.max(PT, y));
          const yA = clampY(toY(z.anchor)), yT = clampY(toY(z.top));
          return <g key={`zone${zi}`}>
            <rect x={x1} y={yT} width={x2 - x1} height={Math.max(0, yA - yT)} fill="#22c55e" opacity={z.held ? 0.22 : 0.13}/>
            <line x1={x1} x2={x2} y1={yA} y2={yA} stroke="#22c55e" strokeWidth="1" strokeDasharray="3,3" opacity="0.8"/>
          </g>;
        })}

        {/* Kerzen 4H */}
        {display4h.map((d, i) => {
          const bull = d.c >= d.o;
          const isBoc = i === localBreakout4hIdx;
          const col  = bull ? "#22c55e" : "#ef4444";
          const bTop = toY(Math.max(d.o, d.c));
          const bH   = Math.max(1, toY(Math.min(d.o, d.c)) - bTop);
          const isHov = hover === i;
          return <g key={i}>
            <line x1={toX(i)} x2={toX(i)} y1={toY(d.h)} y2={toY(d.l)} stroke={col} strokeWidth={isHov?1.5:0.8} opacity={0.85}/>
            <rect x={toX(i)-bW/2} y={bTop} width={bW} height={bH}
              fill={col} opacity={isBoc?1:isHov?0.95:0.75}
              stroke={isBoc?col4h:"none"} strokeWidth={isBoc?1:0}/>
          </g>;
        })}

        {/* Signal-Pfeile (4H-Chart: nur 4H) */}
        {signals.filter(s => s.h4_bar_date).map((sig, si) => {
          if (!sig.h4_bar_date) return null;
          const idx = display4h.findIndex(d => d.d.slice(0,16) === sig.h4_bar_date.slice(0,16));
          if (idx < 0) return null;
          const x = toX(idx);
          const yTip = Math.min(toY(display4h[idx].l) + 4, PT + cH - 20);
          return <g key={si}>
            <rect x={x-6} y={yTip-2} width={12} height={20} rx={2} fill="#eab308" opacity={0.2}/>
            <polygon points={`${x-4},${yTip+8} ${x+4},${yTip+8} ${x},${yTip}`} fill="#eab308" opacity="0.95"/>
            <line x1={x} x2={x} y1={yTip+8} y2={yTip+18} stroke="#eab308" strokeWidth="1.5" opacity="0.95"/>
          </g>;
        })}

        {/* Aktueller Preis */}
        <line x1={PL} x2={PL+cW} y1={toY(display4h[n-1].c)} y2={toY(display4h[n-1].c)} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.45"/>
        <rect x={PL+cW+2} y={toY(display4h[n-1].c)-8} width={46} height={15} rx="3" fill="#1e293b"/>
        <text x={PL+cW+25} y={toY(display4h[n-1].c)+3} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">{display4h[n-1].c.toFixed(2)}</text>

        {/* Crosshair */}
        {hover !== null && <>
          <line x1={toX(hover)} x2={toX(hover)} y1={PT} y2={PT+cH} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.5"/>
          <line x1={PL} x2={PL+cW} y1={toY(display4h[hover].c)} y2={toY(display4h[hover].c)} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.5"/>
        </>}
        <rect x={PL} y={PT} width={cW} height={cH} fill="none" stroke="#1e293b" strokeWidth="0.8"/>
      </svg>

      <div style={{padding:"5px 12px",display:"flex",gap:14,alignItems:"center",background:"#0a0f1e",borderTop:"1px solid #0f172a",flexWrap:"wrap"}}>
        <div style={{marginLeft:"auto",fontSize:9,color:"#334155",fontFamily:"monospace"}}>{n} Kerzen (von {ohlcv4h.length}) · 4H</div>
      </div>
    </div>
  );
}

// ── Hilfskomponenten ───────────────────────────────────────────────────────
// ── Live-Fetch Benchmark-OHLCV (Yahoo Finance → Stooq Fallback) ──────────
async function fetchYFChart(ticker, interval, range) {
  // Versuch 1: Yahoo Finance v8
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=${interval}&range=${range}&events=history`;
    const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (r.ok) {
      const j = await r.json();
      const res = j?.chart?.result?.[0];
      if (res) {
        const ts = res.timestamp || [];
        const q  = res.indicators?.quote?.[0] || {};
        const { open:o=[], high:h=[], low:l=[], close:c=[] } = q;
        const result = [];
        for (let i = 0; i < ts.length; i++) {
          if (c[i] == null) continue;
          const d = new Date(ts[i]*1000).toISOString().slice(0,10);
          result.push({ d, o:+o[i].toFixed(2), h:+h[i].toFixed(2), l:+l[i].toFixed(2), c:+c[i].toFixed(2) });
        }
        if (result.length > 0) return result;
      }
    }
  } catch {}

  // Versuch 2: Stooq.com CSV (CORS-freundlich)
  try {
    // US-ETFs brauchen bei Stooq das Länderkürzel; Indizes (^GDAXI, ^SP600)
    // funktionieren URL-kodiert, ebenso Einzelticker.
    const STOOQ_ALIASES = { QQQ: "QQQ.US", SPY: "SPY.US" };
    const stooqSym = STOOQ_ALIASES[ticker] || encodeURIComponent(ticker);
    const si = interval === "1wk" ? "w" : "d";
    const url2 = `https://stooq.com/q/d/l/?s=${stooqSym}&i=${si}`;
    const r2 = await fetch(url2);
    if (r2.ok) {
      const text = await r2.text();
      const lines = text.trim().split('\n');
      const result = [];
      for (let i = 1; i < lines.length; i++) {
        const [d, o, h, l, c] = lines[i].split(',');
        if (!c || c === 'null' || isNaN(+c)) continue;
        result.push({ d, o:+o, h:+h, l:+l, c:+c });
      }
      result.reverse();
      if (result.length > 0) return result;
    }
  } catch {}

  return [];
}

const WINDOWS = ["5T","10T","20T","50T","6M"];

function Cell({ v }) {
  if (v == null) return <span style={{color:"#334155"}}>—</span>;
  return <span style={{color:v>0?"#4ade80":"#f87171",fontFamily:"monospace",fontSize:11}}>{v>0?"+":""}{Math.round(v)}</span>;
}

// ── W/D/4H Breach-Punkte Spalten ───────────────────────────────────────────
function BreachDots({ structW, structD, struct4H, changedW, changedD, changed4H }) {
  const dot = (active, changed) => (
    <span style={{
      display:"inline-block", width:7, height:7, borderRadius:"50%",
      background: active ? "#4ade80" : "#1e293b",
      border: changed ? "1.5px solid #eab308" : active ? "1px solid #22c55e" : "1px solid #334155",
      flexShrink: 0, boxSizing:"border-box",
    }}/>
  );
  const col = { display:"flex", alignItems:"center", justifyContent:"center", width:18 };
  return (
    <div style={{display:"flex", gap:1, alignItems:"center"}}>
      <div style={col}>{dot(structW?.broken,  changedW)}</div>
      <div style={col}>{dot(structD?.broken,  changedD)}</div>
      <div style={col}>{dot(struct4H?.broken4h, changed4H)}</div>
    </div>
  );
}

// ── Watchlist-Knopf ───────────────────────────────────────────────────────────
// Plus, solange der Titel nicht auf der Watchlist steht, danach ein Haken.
// Zustand kommt aus watchlist.js (localStorage); die Seite hört auf das Event,
// damit alle Knöpfe gleichzeitig umspringen.
function WatchButton({ ticker }) {
  const [on, setOn] = React.useState(() => window.RSWatchlist.has(ticker));
  // Solange der Schreibvorgang nicht bestätigt ist, darf der Haken nicht grün
  // aussehen: sonst signalisiert er einen Stand, den der nächtliche
  // Verkaufssignal-Job gar nicht kennt.
  const [pending, setPending] = React.useState(() => window.RSWatchlist.pending());

  React.useEffect(() => {
    const sync = () => { setOn(window.RSWatchlist.has(ticker)); setPending(window.RSWatchlist.pending()); };
    const syncState = e => setPending(e.detail.pending);
    window.addEventListener(window.RSWatchlist.EVENT, sync);
    window.addEventListener(window.RSWatchlist.SYNC_EVENT, syncState);
    return () => {
      window.removeEventListener(window.RSWatchlist.EVENT, sync);
      window.removeEventListener(window.RSWatchlist.SYNC_EVENT, syncState);
    };
  }, [ticker]);

  const open = on && pending;
  const label = on
    ? `${ticker} von der Watchlist entfernen`
    : `${ticker} zur Watchlist hinzufügen`;

  return (
    <div style={{display:"flex", justifyContent:"center"}}>
      <button
        onClick={e => { e.stopPropagation(); window.RSWatchlist.toggle(ticker); }}
        title={open ? `${ticker} aufgenommen — noch nicht im Repository gespeichert` : label}
        aria-label={label}
        aria-pressed={on}
        style={{
          width:18, height:18, lineHeight:"16px", padding:0, cursor:"pointer",
          borderRadius:4, fontSize:12, fontWeight:700, fontFamily:"monospace",
          background: on ? (open ? "#2a1a05" : "#14532d") : "transparent",
          border: `1px solid ${on ? (open ? "#a16207" : "#4ade80") : "#334155"}`,
          color: on ? (open ? "#fbbf24" : "#4ade80") : "#475569",
        }}
      >{on ? (open ? "!" : "✓") : "+"}</button>
    </div>
  );
}
