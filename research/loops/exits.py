"""Loop 1 (Risk): Ausstiege, Positionsgröße, Pyramide auf den 4H-Signalen.
Nachbau des Engine-Ausstiegs (Stopp, Strukturbruch GWS-D, Zeitstopp 10T/+5 %) als exit_rule,
damit Hybrid-Ausstiege möglich sind. Kein Vorgriff: Regel sieht nur Schlusskurse bis Tag i,
Verkauf zur Eröffnung i+1 (simulate)."""
from __future__ import annotations
import bisect, math, sys
import numpy as np
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
from trading_approaches import Strategy, gws_candidates, Position  # noqa: E402


class Struct:
    """Je Symbol: kompakte Tagesreihe (nur Handelstage mit Kurs) + GWS-D-Vorberechnung."""
    def __init__(self, m):
        self.m = m
        self.cache = {}
        self.cols = {x: k for k, x in enumerate(m.c.columns)}

    def get(self, sym):
        if sym in self.cache:
            return self.cache[sym]
        k = self.cols[sym]
        C = self.m.c.values[:, k]; H = self.m.h.values[:, k]; L = self.m.l.values[:, k]
        valid = np.nonzero(~np.isnan(C))[0]
        C, H, L = C[valid], H[valid], L[valid]
        n = len(C)
        pos = np.full(len(self.m.dates), -1); pos[valid] = np.arange(n)
        sh = [i for i in range(2, n - 2) if H[i] >= H[i-1] and H[i] >= H[i-2] and H[i] >= H[i+1] and H[i] >= H[i+2]]
        sl = [i for i in range(2, n - 2) if L[i] <= L[i-1] and L[i] <= L[i-2] and L[i] <= L[i+1] and L[i] <= L[i+2]]
        cand = [None] * len(sl)
        for j in range(1, len(sl)):
            a, b = sl[j-1], sl[j]
            if L[b] < L[a]:
                lo, hi = bisect.bisect_right(sh, a), bisect.bisect_left(sh, b)
                if hi > lo:
                    best = max(sh[lo:hi], key=lambda x: H[x])
                    above = np.nonzero(C[best+1:] > H[best])[0]
                    cand[j] = (best, H[best], best + 1 + above[0] if len(above) else 10**9)
        lastc, cur = [None] * (len(sl) + 1), None
        for mm in range(1, len(sl) + 1):
            if cand[mm-1] is not None:
                cur = cand[mm-1]
            lastc[mm] = cur
        o = dict(C=C, L=L, sl=sl, lastc=lastc, pos=pos)
        self.cache[sym] = o
        return o

    def struct_exit(self, sym, i):
        o = self.get(sym); k = o['pos'][i]
        if k < 0:
            return False
        mm = bisect.bisect_right(o['sl'], k - 3)
        if mm == 0:
            return False
        c = o['lastc'][mm]
        if c is not None and c[2] <= k - 1:
            return False
        return o['C'][k] < o['L'][o['sl'][mm-1]]

    def day(self, sym, p, i):
        o = self.get(sym)
        return o['pos'][i] - o['pos'][p.entry_i]


def make_rule(m, S: Struct, *, early=None, ts=(10, 0.05), confirm_r=None, trail_pct=None,
              chandelier=None, struct_after_confirm=False, be_after_confirm=False):
    """Engine-Ausstieg + Optionen.
    early: (Tag, Schwelle) — Schluss an Tag N unter Einstieg*(1+Schwelle) → raus (Frühausstieg).
    ts: (Tag, Mindestgewinn) Zeitstopp wie Engine; None = aus.
    confirm_r: ab max. Schluss ≥ Einstieg + X·R gilt der Trade als bestätigt: dann kein Strukturausstieg
               mehr (außer struct_after_confirm), sondern Trailing (trail_pct unter Hoch / Chandelier ATR).
    """
    c = m.c.values; atr = m.ind['atr14'].values
    col = S.cols

    def rule(p: Position, i: int) -> bool:
        k = col[p.sym]; x = c[i, k]
        d = S.day(p.sym, p, i)
        risk = p.entry_price - p.stop if p.stop is not None and p.entry_price > p.stop else None
        confirmed = confirm_r is not None and risk is not None and p.max_close >= p.entry_price + confirm_r * risk
        if confirmed and not getattr(p, '_conf', False):
            p._conf = True
            if be_after_confirm:
                p.stop = max(p.stop, p.entry_price)
        confirmed = confirmed or getattr(p, '_conf', False)
        if p.stop is not None and x < p.stop:
            return True
        if early and d == early[0] and x < p.entry_price * (1 + early[1]):
            return True
        if ts and d == ts[0] and x < p.entry_price * (1 + ts[1]):
            return True
        if confirmed:
            if trail_pct and x < p.max_close * (1 - trail_pct):
                return True
            if chandelier and not math.isnan(atr[i, k]) and x < p.max_close - chandelier * atr[i, k]:
                return True
            if struct_after_confirm and S.struct_exit(p.sym, i):
                return True
            return False
        return S.struct_exit(p.sym, i)
    return rule
