"""
gws_core.py — Swing-Punkte und GWS-Kernlogik

Gemeinsame Basis für check_alerts.py (Breakout-Meldungen) und check_exits.py
(Verkaufssignale). Bewusst ohne schwere Abhängigkeiten, damit beide Jobs das
Modul importieren können, ohne matplotlib oder yfinance zu laden.
"""


def _find_swing_points(highs, lows, n, window=2):
    """Swing-Hochs und Swing-Tiefs mit konfigurierbarem Fenster (±window Bars)."""
    swing_highs = []
    swing_lows  = []
    for i in range(window, n - window):
        if all(highs[i] >= highs[i-k] and highs[i] >= highs[i+k] for k in range(1, window+1)):
            swing_highs.append({'idx': i, 'price': highs[i]})
        if all(lows[i] <= lows[i-k] and lows[i] <= lows[i+k] for k in range(1, window+1)):
            swing_lows.append({'idx': i, 'price': lows[i]})
    return swing_highs, swing_lows


def gws_candidates(swing_highs, swing_lows):
    """Alle GWS-Marken: jedes tiefere Tief bildet eine, Marke = höchstes Hoch dazwischen."""
    candidates = []
    for j in range(1, len(swing_lows)):
        tief_neu = swing_lows[j]
        tief_alt = swing_lows[j - 1]
        if tief_neu['price'] < tief_alt['price']:
            hochs = [h for h in swing_highs
                     if tief_alt['idx'] < h['idx'] < tief_neu['idx']]
            if hochs:
                candidates.append({**max(hochs, key=lambda h: h['price']), 'tief_neu': tief_neu})
    return candidates


def _gws_core(swing_highs, swing_lows, closes, n, min_margin=0.001):
    """Kernlogik: tiefere Tiefs erkennen → GWS = höchstes Hoch dazwischen.
    min_margin: Close muss mindestens diesen Bruchteil über GWS liegen (Standard 0.1%)."""
    candidates = gws_candidates(swing_highs, swing_lows)
    gws_high = candidates[-1] if candidates else None

    breakout_idx = None
    if gws_high:
        threshold = gws_high['price'] * (1 + min_margin)
        for i in range(gws_high['idx'] + 1, n):
            if closes[i] > threshold:
                breakout_idx = i
                break

    return gws_high, breakout_idx


def held_after_breakout(candidates, closes, lows, n, min_margin=0.001, breakout_idx=None, weekly=False,
                        closed_below=None):
    """Signal halten wie heldAfterBreakout in frontend/backtest_logic.js: Hat ein
    tieferes Tief eine neue, noch ungebrochene Marke gebildet (Trendumkehr), bleibt die
    Ebene grün, solange seit der Ausbruchskerze der zuletzt gebrochenen Marke kein
    Schluss unter deren Tief liegt (AVGO KW 15.07.2024: Ausbruchswoche 13.05., Tief
    129,48). breakout_idx(marke) → Index der Ausbruchskerze (optional, sonst erster
    Schluss über der Marke). weekly: Anker = letztes Swing-Tief vor der Ausbruchswoche
    (weekly_anchor_low, wie holdAnchor.w 'swingtief'), sonst Daily-Anker 'tu' (tu_anchor_low),
    geprüft ab der Trendumkehr. closed_below(b, anker) (optional): eigene Bruchprüfung, z. B.
    Weekly per Tagesschluss (weekly_closed_below)."""
    for c in range(len(candidates) - 1, -1, -1):
        cand = candidates[c]
        if breakout_idx:
            b = breakout_idx(cand)
        else:
            threshold = cand['price'] * (1 + min_margin)
            b = next((i for i in range(cand['idx'] + 1, n) if closes[i] > threshold), -1)
        if b is None or b < 0:
            continue
        nxt = candidates[c + 1] if c + 1 < len(candidates) else None
        if weekly:
            anchor, start = weekly_anchor_low(lows, cand['idx'], b), b + 1
        else:
            anchor = tu_anchor_low(nxt, lows, b)
            t = (nxt or {}).get('tief_neu')
            start = t['idx'] if t and t['idx'] > b else b + 1
        if closed_below and weekly:
            return not closed_below(b, anchor)
        return all(closes[i] >= anchor for i in range(start, n))
    return False


def weekly_anchor_low(lows, mark_idx, b):
    """Weekly-Anker wie holdAnchorLow(…, 'swingtief') in frontend/backtest_logic.js (seit
    13.10.2026): letztes Swing-Tief (±1) vor der Ausbruchswoche b nach der Marke, sonst das
    tiefste Tief dazwischen (PANW: Ausbruch Woche 28.02.2022 → 77,75 vom 21.02.)."""
    for k in range(b - 1, mark_idx, -1):
        if lows[k] <= lows[k - 1] and lows[k] <= lows[k + 1]:
            return lows[k]
    return min(lows[mark_idx:b + 1])


def weekly_anchor_walk(ohlcv_w, b, anchor):
    """Weekly-Anker ab der Ausbruchswoche b wie anchorWalk in frontend/backtest_logic.js (seit
    13.10.2026): Woche für Woche gebrochen, sobald ein Wochentief unter dem Anker liegt; schließt
    eine Woche über dem letzten bestätigten Swing-Hoch (erneuter Ausbruch), rückt der Anker auf das
    Swing-Tief davor (ZS: Woche 08.01.2024 → 206,67 vom 01.01., Woche 19.02. Tief 202,44 → gebrochen;
    PANW: Woche 09.05.2022 Tief 75,05 unter 77,75). Rückgabe: (gebrochen, aktueller Anker)."""
    n = len(ohlcv_w)
    lows = [w['l'] for w in ohlcv_w]
    highs = [w['h'] for w in ohlcv_w]
    closes = [w['c'] for w in ohlcv_w]

    def swing_low(k):
        return 1 <= k < n - 1 and lows[k] <= lows[k - 1] and lows[k] <= lows[k + 1]

    def swing_high(k):
        return 1 <= k < n - 1 and highs[k] >= highs[k - 1] and highs[k] >= highs[k + 1]

    last = b
    for k in range(b + 1, n):
        if lows[k] < anchor:
            return True, anchor
        sh = next((highs[j] for j in range(k - 2, last, -1) if swing_high(j)), None)
        if sh is not None and closes[k] > sh:
            sl = next((lows[j] for j in range(k - 1, last, -1) if swing_low(j)), None)
            if sl is not None:
                anchor = max(anchor, sl)
            last = k
    return False, anchor


def weekly_closed_below(ohlcv_w, ohlcv_d=None):
    """Weekly-Bruch für held_after_breakout/check_alerts: weekly_anchor_walk als Prüffunktion
    (b, anker) → gebrochen. ohlcv_d bleibt für die Ausbruchswoche (weekly_breakout_idx) nötig."""
    def check(b, anchor):
        return weekly_anchor_walk(ohlcv_w, b, anchor)[0]
    return check


def provisional_mark_break(swing_highs, swing_lows, highs, lows, closes, n, min_margin=0.001):
    """Daily wie provisionalMark in frontend/backtest_logic.js: Ist das Tief der vorletzten
    Kerze ein tieferes Tief (Swing-Tief mit erst einer Folgekerze) und schließt die letzte
    Kerze über dem höchsten Swing-Hoch seit dem letzten bestätigten Swing-Tief, ist diese
    Marke sofort gebrochen (AVGO 21.08.2023: Tief 18.08. bei 78,18, Marke 82,28 vom 15.08.,
    Schluss 83,30). Rückgabe: Marke (dict) oder None."""
    k = n - 2
    if k < 2 or not swing_lows or swing_lows[-1]['idx'] >= k:
        return None
    last = swing_lows[-1]
    if not (lows[k] <= lows[k - 1] and lows[k] <= lows[k - 2] and lows[k] <= lows[k + 1]
            and lows[k] < last['price']):
        return None
    hs = [h for h in swing_highs if last['idx'] < h['idx'] < k]
    if not hs:
        return None
    mark = max(hs, key=lambda h: h['price'])
    return mark if closes[n - 1] > mark['price'] * (1 + min_margin) else None


def tu_anchor_low(nxt, lows, b):
    """Daily-Anker nach Trendumkehr wie tuAnchorLow in frontend/backtest_logic.js: Die
    Trendumkehr (tieferes Tief tief_neu der nächsten Marke) deaktiviert nur den Trade; die
    Ebene bleibt gehalten bis zu einem Schluss unter dem letzten Swing-Tief vor tief_neu, das
    tiefer liegt als tief_neu, gesucht höchstens bis zum Swing-Tief vor dem Ausbruch b (grüne
    Linie im Chart); liegt die Trendumkehr darunter, gilt dieses Swing-Tief (AVGO Daily:
    Trendumkehr 04.08.2023 bei 84,09 → Anker 81,29 vom 06.07., Schluss 10.08. darunter;
    Trendumkehr 26.10.2023 bei 79,22 → Anker 78,58 vom 06.10., vor dem Ausbruch 11.10.)."""
    t = (nxt or {}).get('tief_neu')
    if not t or t['idx'] <= b:
        return lows[b]

    def is_low(k):
        return 2 <= k and k + 2 < len(lows) and all(lows[k] <= lows[k - j] and lows[k] <= lows[k + j]
                                                     for j in (1, 2))
    p = next((k for k in range(b - 1, 1, -1) if is_low(k)), -1)   # Swing-Tief vor dem Ausbruch
    for k in range(t['idx'] - 1, max(2, p) - 1, -1):
        if is_low(k) and lows[k] < t['price']:
            return lows[k]
    return lows[p] if p >= 0 else lows[b]


def weekly_breakout_idx(ohlcv_w, ohlcv_d):
    """Ausbruchswoche wie weeklyBreakoutIdx in backtest_logic.js: die Woche mit dem
    ersten Tagesschluss über der Marke (Wochenkerzen mit Montagsdatum)."""
    def find(cand):
        mark_day = ohlcv_w[cand['idx']]['d']
        day = next((d['d'] for d in ohlcv_d if d['d'] > mark_day and d['c'] > cand['price']), None)
        if day is None:
            return -1
        b = -1
        for i, w in enumerate(ohlcv_w):
            if w['d'] > day:
                break
            b = i
        return b
    return find


def swing_low_stop(bars, buffer=0.99):
    """Stopp aus dem letzten Swing-Tief der übergebenen Kerzen.

    Gleiche Herleitung wie in frontend/backtest_logic.js: das jüngste Tief, das
    von beiden Nachbartagen nicht unterboten wird, mit einem Puffer darunter.
    Fällt auf das Minimum der letzten fünf Kerzen zurück, wenn es kein solches
    Tief gibt. Gibt None zurück, wenn zu wenige Kerzen vorliegen.

    Ein Swing-Tief, das vor dem Kauf schon per Schluss unterschritten war, ist
    verbraucht — dann gilt das tiefste Tief seit dem Bruch (seit 16.10.2026,
    NFLX 27.09.2017: 18,32 vom 20.09. am 25.09. gebrochen → 17,66 vom 26.09.).
    """
    if not bars or len(bars) < 3:
        return None
    for k in range(len(bars) - 2, 0, -1):
        if bars[k]['l'] <= bars[k - 1]['l'] and bars[k]['l'] <= bars[k + 1]['l']:
            low = bars[k]['l']
            first = next((i for i in range(k + 1, len(bars)) if bars[i]['c'] < low), None)
            if first is not None:
                low = min(b['l'] for b in bars[first:])
            return low * buffer
    return min(b['l'] for b in bars[-5:]) * buffer
