"""
Einmaliger Backfill: Erstellt signals.json für alle Tickers,
die laut alerts_state.json bereits eine Alert-Mail erhalten haben.
Läuft ohne yfinance/matplotlib.
"""
import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ── GWS-Analyse (inline, ohne externe Abhängigkeiten) ────────────────────────

def _find_swing_points(highs, lows, n):
    swing_highs, swing_lows = [], []
    for i in range(2, n - 2):
        if (highs[i] >= highs[i-1] and highs[i] >= highs[i-2] and
                highs[i] >= highs[i+1] and highs[i] >= highs[i+2]):
            swing_highs.append({'idx': i, 'price': highs[i]})
        if (lows[i] <= lows[i-1] and lows[i] <= lows[i-2] and
                lows[i] <= lows[i+1] and lows[i] <= lows[i+2]):
            swing_lows.append({'idx': i, 'price': lows[i]})
    return swing_highs, swing_lows


def _gws_core(swing_highs, swing_lows, closes, n):
    candidates = []
    for j in range(1, len(swing_lows)):
        tief_neu = swing_lows[j]
        tief_alt = swing_lows[j - 1]
        if tief_neu['price'] < tief_alt['price']:
            hochs = [h for h in swing_highs
                     if tief_alt['idx'] < h['idx'] < tief_neu['idx']]
            if hochs:
                candidates.append(max(hochs, key=lambda h: h['price']))
    gws_high = candidates[-1] if candidates else None
    breakout_idx = None
    if gws_high:
        for i in range(gws_high['idx'] + 1, n):
            if closes[i] > gws_high['price']:
                breakout_idx = i
                break
    return gws_high, breakout_idx


def analyze_weekly(ohlcv_w):
    if not ohlcv_w or len(ohlcv_w) < 8:
        return None
    n = len(ohlcv_w)
    highs  = [c['h'] for c in ohlcv_w]
    lows   = [c['l'] for c in ohlcv_w]
    closes = [c['c'] for c in ohlcv_w]
    sh, sl = _find_swing_points(highs, lows, n)
    gws, bi = _gws_core(sh, sl, closes, n)
    trend = None
    if len(sh) >= 2:
        trend = 'bullish' if sh[-1]['price'] > sh[-2]['price'] else 'bearish'
    broken = bi is not None or (gws is None and trend == 'bullish')
    return {'broken': broken, 'breakout_idx': bi}


def analyze_daily(ohlcv):
    if not ohlcv or len(ohlcv) < 10:
        return None
    n = len(ohlcv)
    highs  = [c['h'] for c in ohlcv]
    lows   = [c['l'] for c in ohlcv]
    closes = [c['c'] for c in ohlcv]
    sh, sl = _find_swing_points(highs, lows, n)
    _, bi  = _gws_core(sh, sl, closes, n)
    return {'broken': bi is not None, 'breakout_idx': bi}


def analyze_4h(ohlcv_4h):
    if not ohlcv_4h or len(ohlcv_4h) < 8:
        return None
    n = len(ohlcv_4h)
    highs  = [c['h'] for c in ohlcv_4h]
    lows   = [c['l'] for c in ohlcv_4h]
    closes = [c['c'] for c in ohlcv_4h]
    sh, sl = _find_swing_points(highs, lows, n)
    _, bi  = _gws_core(sh, sl, closes, n)
    return {'broken4h': bi is not None, 'breakout_idx': bi}


def breakout_date(ohlcv, struct):
    if not struct or not ohlcv:
        return None
    idx = struct.get('breakout_idx')
    if idx is not None and 0 <= idx < len(ohlcv):
        return ohlcv[idx]['d']
    return None


# ── Backfill ──────────────────────────────────────────────────────────────────

def backfill():
    with open('alerts_state.json') as f:
        state = json.load(f)

    alerted = state.get('alerted', {})
    states  = state.get('states',  {})

    # Daten laden
    data_by_ticker = {}
    for json_path, source_label in [('rs_full.json', 'QQQ'), ('rs_dax.json', 'DAX')]:
        if not os.path.exists(json_path):
            continue
        with open(json_path) as f:
            js = json.load(f)
        for entry in js.get('data', []):
            data_by_ticker[entry['ticker']] = (entry, source_label)

    signals = {}
    if os.path.exists('signals.json'):
        with open('signals.json') as f:
            signals = json.load(f)

    added = 0

    for ticker, signal_date in sorted(alerted.items()):
        ts = states.get(ticker, {})
        if ts.get('points', 0) < 3:
            print(f'  SKIP {ticker}: nur {ts.get("points",0)} Punkte aktuell')
            continue

        if ticker not in data_by_ticker:
            print(f'  SKIP {ticker}: nicht in JSON')
            continue

        entry, source_label = data_by_ticker[ticker]

        sw  = analyze_weekly(entry.get('ohlcv_w',  []))
        sd  = analyze_daily( entry.get('ohlcv',    []))
        s4h = analyze_4h(    entry.get('ohlcv_4h', []))

        wd  = breakout_date(entry.get('ohlcv_w',  []), sw)
        dd  = breakout_date(entry.get('ohlcv',    []), sd)
        hd  = breakout_date(entry.get('ohlcv_4h', []), s4h)

        # trigger_tf: Breakout-Datum ≤ signal_date, das neueste
        candidates = []
        if sw  and sw.get('broken')   and wd: candidates.append(('weekly', wd))
        if sd  and sd.get('broken')   and dd: candidates.append(('daily',  dd))
        if s4h and s4h.get('broken4h') and hd: candidates.append(('4h',    hd))

        if not candidates:
            print(f'  SKIP {ticker}: keine Breakout-Daten')
            continue

        valid = [(tf, d) for tf, d in candidates if d[:10] <= signal_date]
        if valid:
            trigger_tf = max(valid, key=lambda x: x[1])[0]
        else:
            trigger_tf = max(candidates, key=lambda x: x[1])[0]

        # Nicht doppelt eintragen
        existing = signals.get(ticker, [])
        if any(s['signal_date'] == signal_date for s in existing):
            print(f'  SKIP {ticker}: {signal_date} bereits vorhanden')
            continue

        sig = {
            'signal_date':     signal_date,
            'trigger_tf':      trigger_tf,
            'weekly_bar_date': wd,
            'daily_bar_date':  dd,
            'h4_bar_date':     hd,
            'source':          source_label,
        }
        signals.setdefault(ticker, []).append(sig)
        added += 1
        print(f'  + {ticker:<12} signal={signal_date}  trigger={trigger_tf:<6}  '
              f'W={wd}  D={dd}  4H={hd}')

    with open('signals.json', 'w') as f:
        json.dump(signals, f, indent=2)

    print(f'\nFertig: {added} Signale hinzugefügt → signals.json')


if __name__ == '__main__':
    backfill()
