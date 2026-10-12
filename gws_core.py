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


def held_after_breakout(candidates, closes, lows, n, min_margin=0.001, breakout_idx=None, lowest=False):
    """Signal halten wie heldAfterBreakout in frontend/backtest_logic.js: Hat ein
    tieferes Tief eine neue, noch ungebrochene Marke gebildet (Trendumkehr), bleibt die
    Ebene grün, solange seit der Ausbruchskerze der zuletzt gebrochenen Marke kein
    Schluss unter deren Tief liegt (AVGO KW 15.07.2024: Ausbruchswoche 13.05., Tief
    129,48). breakout_idx(marke) → Index der Ausbruchskerze (optional, sonst erster
    Schluss über der Marke). lowest: Anker = tiefstes Tief zwischen Marke und Ausbruch
    (Weekly, wie holdAnchor.w), sonst Daily-Anker 'tu' (tu_anchor_low), geprüft ab der
    Trendumkehr."""
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
        if lowest:
            anchor, start = min(lows[cand['idx']:b + 1]), b + 1
        else:
            anchor = tu_anchor_low(nxt, lows, b)
            t = (nxt or {}).get('tief_neu')
            start = t['idx'] if t and t['idx'] > b else b + 1
        return all(closes[i] >= anchor for i in range(start, n))
    return False


def tu_anchor_low(nxt, lows, b):
    """Daily-Anker nach Trendumkehr wie tuAnchorLow in frontend/backtest_logic.js: Die
    Trendumkehr (tieferes Tief tief_neu der nächsten Marke) deaktiviert nur den Trade; die
    Ebene bleibt gehalten bis zu einem Schluss unter dem letzten Swing-Tief vor tief_neu, das
    tiefer liegt als tief_neu — höchstens bis zum Tief der Ausbruchskerze b (AVGO Daily:
    Trendumkehr 04.08.2023 bei 84,09 → Anker 81,29 vom 06.07., Schluss 10.08. darunter)."""
    t = (nxt or {}).get('tief_neu')
    if not t or t['idx'] <= b:
        return lows[b]
    for k in range(t['idx'] - 1, 1, -1):
        if (k + 2 < len(lows) and lows[k] < t['price']
                and all(lows[k] <= lows[k - j] and lows[k] <= lows[k + j] for j in (1, 2))):
            return max(lows[k], lows[b])
    return lows[b]


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
    """
    if not bars or len(bars) < 3:
        return None
    for k in range(len(bars) - 2, 0, -1):
        if bars[k]['l'] <= bars[k - 1]['l'] and bars[k]['l'] <= bars[k + 1]['l']:
            return bars[k]['l'] * buffer
    return min(b['l'] for b in bars[-5:]) * buffer
