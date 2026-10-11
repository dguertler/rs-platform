"""Loop 3 Makro: Tagesnäherung des Breakout-Signals (W+D, 2 von 2 Punkten) zeitpunktgenau,
Engine-Ausstieg (Stopp, Strukturbruch, Zeitstopp) — für 2008–2015 ohne 4H-Kerzen.
Erzeugt Signale im Format von load_signals() → research/trading_approaches.simulate."""
import sys, os, json, bisect, pickle, math
import numpy as np, pandas as pd
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import double_bottom as db
from loop_harness import load
import prak
W = os.path.dirname(os.path.abspath(__file__))

def weekly_points(D, H, L, C):
    """pW[t]: GWS-W gebrochen mit Wochenkerzen bis t (laufende Woche aus Tageskerzen bis t), 60 Wochen."""
    dts = pd.to_datetime(D); wk = (dts - pd.to_timedelta(dts.dayofweek, unit='D')).values
    n = len(C); pW = np.zeros(n, bool)
    # abgeschlossene Wochen
    starts = np.r_[0, np.nonzero(wk[1:] != wk[:-1])[0] + 1]
    ends = np.r_[starts[1:], n]
    WH = np.array([H[a:b].max() for a, b in zip(starts, ends)]); WL = np.array([L[a:b].min() for a, b in zip(starts, ends)])
    widx = np.searchsorted(starts, np.arange(n), side='right') - 1
    for t in range(n):
        k = widx[t]; a = starts[k]
        hi = np.r_[WH[max(0, k - 59):k], H[a:t + 1].max()]; lo = np.r_[WL[max(0, k - 59):k], L[a:t + 1].min()]
        first_w = max(0, k - 59)
        m = len(hi)
        if m < 15: continue
        sh = [i for i in range(1, m - 1) if hi[i] >= hi[i - 1] and hi[i] >= hi[i + 1]]
        sl = [i for i in range(1, m - 1) if lo[i] <= lo[i - 1] and lo[i] <= lo[i + 1]]
        g = None
        for j in range(len(sl) - 1, 0, -1):
            if lo[sl[j]] < lo[sl[j - 1]]:
                between = [x for x in sh if sl[j - 1] < x < sl[j]]
                if between:
                    g = max(between, key=lambda x: hi[x]); break
        if g is None: continue
        # gebrochen: Tagesschluss nach Wochenbeginn der GWS-W-Woche (wie JS: d > Wochen-Datum) über dem Hoch
        d0 = starts[first_w + g]
        pW[t] = (C[d0 + 1:t + 1] > hi[g]).any() if t > d0 else False
    return pW

def daily_points(H, L, C):
    sh, sl = db.swings(H, L); lastc = db.gwsd_lastc(H, L, C, sh, sl)
    n = len(C); pD = np.zeros(n, bool)
    for t in range(n):
        mm = bisect.bisect_right(sl, t - 2)
        c = lastc[mm] if mm < len(lastc) else None
        pD[t] = c is not None and c[2] <= t
    return pD, sl, lastc

def swing_low_before(L, e):
    for k in range(e - 2, 0, -1):
        if L[k] <= L[k - 1] and L[k] <= L[k + 1]: return L[k]
    return L[max(0, e - 5):e].min() if e > 0 else None

def ticker_signals(D, O, H, L, C, start='2007-06-01'):
    pD, sl, lastc = daily_points(H, L, C)
    pW = weekly_points(D, H, L, C)
    o = dict(C=C, O=O, L=L, sl=sl, lastc=lastc)
    pts = pD.astype(int) + pW.astype(int)
    out = []; busy = -1; n = len(C)
    for t in range(1, n - 1):
        if D[t] < start or t <= busy: continue
        if not (pts[t - 1] < 2 and pts[t] == 2): continue
        trig = 'D' if (not pD[t - 1] and pD[t]) else ('W' if (not pW[t - 1] and pW[t]) else None)
        if trig is None: continue
        e = t + 1; ep = O[e]; slw = swing_low_before(L, e)
        if slw is None or not ep or ep <= slw * 0.99: continue
        stop = slw * 0.99
        xi, xp, reason, is_open = db.simulate(o, e, ep, stop)
        out.append(dict(signal_i=t, entry_i=e, entryDate=D[e], entryPrice=float(ep), stopPrice=float(stop),
                        exit_i=xi, exitDate=D[xi], exitPrice=float(xp), isOpen=bool(is_open), trigger=trig, reason=reason))
        busy = xi
    return out

def build_all():
    f = os.path.join(W, 'wd_raw.pkl')
    if os.path.exists(f): return pickle.load(open(f, 'rb'))
    m, _ = load(); res = {}
    for s in m.c.columns:
        df = pd.DataFrame({'o': m.o[s], 'h': m.h[s], 'l': m.l[s], 'c': m.c[s]}).dropna()
        if len(df) < 300: continue
        D = df.index.strftime('%Y-%m-%d').values
        res[s] = ticker_signals(D, df.o.values, df.h.values, df.l.values, df.c.values)
    pickle.dump(res, open(f, 'wb')); return res

def to_sigs(m, raw, top_filter=True):
    """Format wie load_signals: by_day[i] → dicts. Top-20 am Signaltag (Vortag der Ausführung)."""
    idx = {d: i for i, d in enumerate(m.dates.strftime('%Y-%m-%d'))}
    col = {x: k for k, x in enumerate(m.c.columns)}; top = m.in_top.values
    by = {}
    for s, lst in raw.items():
        for g in lst:
            i = idx.get(g['entryDate'])
            if i is None: continue
            if top_filter and not top[i - 1, col[s]]: continue
            ex = None if g['isOpen'] else (idx.get(g['exitDate']), g['exitPrice'])
            by.setdefault(i, []).append(dict(sym=s, entryDate=g['entryDate'], entryTime='09:30', entryPrice=g['entryPrice'],
                                             stopPrice=g['stopPrice'], fixed_exit=ex, isOpen=g['isOpen'], trigger=g['trigger']))
    return by

def features(m, sigs, tag):
    f = os.path.join(W, f'feat_{tag}.pkl')
    if os.path.exists(f): return pickle.load(open(f, 'rb'))
    cache = prak.HERE; prak.HERE = W + '/_tmp_' + tag; os.makedirs(prak.HERE, exist_ok=True)
    F = prak.features(m, sigs); prak.HERE = cache
    pickle.dump(F, open(f, 'wb')); return F

if __name__ == '__main__':
    import time; t = time.time()
    raw = build_all(); print('Titel', len(raw), 'Signale', sum(len(v) for v in raw.values()), f'{time.time()-t:.0f}s')
