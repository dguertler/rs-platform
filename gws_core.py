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


def _gws_core(swing_highs, swing_lows, closes, n, min_margin=0.001):
    """Kernlogik: tiefere Tiefs erkennen → GWS = höchstes Hoch dazwischen.
    min_margin: Close muss mindestens diesen Bruchteil über GWS liegen (Standard 0.1%)."""
    candidates = []
    for j in range(1, len(swing_lows)):
        tief_neu = swing_lows[j]
        tief_alt = swing_lows[j - 1]
        if tief_neu['price'] < tief_alt['price']:
            hochs = [h for h in swing_highs
                     if tief_alt['idx'] < h['idx'] < tief_neu['idx']]
            if hochs:
                gws_hoch = max(hochs, key=lambda h: h['price'])
                candidates.append(gws_hoch)

    gws_high = candidates[-1] if candidates else None

    breakout_idx = None
    if gws_high:
        threshold = gws_high['price'] * (1 + min_margin)
        for i in range(gws_high['idx'] + 1, n):
            if closes[i] > threshold:
                breakout_idx = i
                break

    return gws_high, breakout_idx


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
