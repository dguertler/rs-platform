"""Studie 10/2026 — Depot-Test der Verbesserungen aus der Trade-Muster-Studie.

Bildet Stopp, Strukturbruch und Zeitstopp der Engine (frontend/backtest_logic.js)
auf Tageskerzen nach (trifft ~98 % der Trades aus data/backtest_ndx.json) und
rechnet die Varianten im 10-Platz-Depot, getrennt für 2016–21 und 2022–26,
plus Robustheitsläufe (je 20 % der Signale fallen zufällig weg).
Ohne Handelskosten — wie data/backtest_ndx.json.

    python3 research/trade_patterns.py          # vorher: Merkmalstabelle
    python3 research/trade_patterns_depot.py    # ~10 Min. (30 Läufe), --runs 0 für nur den vollen Lauf

Bericht: research/TRADE_PATTERNS.md
"""
import argparse
import bisect
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = str(Path(__file__).resolve().parent.parent)
_cache = {}
def load_daily(tk):
    if tk in _cache:
        return _cache[tk]
    p = f'{ROOT}/data/backtest_history/charts/{tk}.json'
    rows = []
    if os.path.exists(p):
        rows = [tuple(r[:5]) for r in json.load(open(p))['d']]
    p2 = f'{ROOT}/data/backtest_{tk.lower()}.json'
    if os.path.exists(p2):
        extra = [(b['d'], b['o'], b['h'], b['l'], b['c']) for b in json.load(open(p2))['ohlcv_d']]
        if rows:
            last = rows[-1][0]
            rows += [r for r in extra if r[0] > last]
        else:
            rows = extra
    if not rows:
        _cache[tk] = None
        return None
    D = np.array([r[0] for r in rows])
    O, H, L, C = (np.array([r[i] for r in rows], float) for i in (1, 2, 3, 4))
    n = len(C)
    sh = [i for i in range(2, n - 2) if H[i] >= H[i-1] and H[i] >= H[i-2] and H[i] >= H[i+1] and H[i] >= H[i+2]]
    sl = [i for i in range(2, n - 2) if L[i] <= L[i-1] and L[i] <= L[i-2] and L[i] <= L[i+1] and L[i] <= L[i+2]]
    sh_arr = np.array(sh)
    # candidates per swing-low index j
    cand = [None] * len(sl)
    for j in range(1, len(sl)):
        a, b = sl[j-1], sl[j]
        if L[b] < L[a]:
            lo = bisect.bisect_right(sh, a); hi = bisect.bisect_left(sh, b)
            if hi > lo:
                hs = sh[lo:hi]
                best = hs[0]
                for x in hs:
                    if H[x] > H[best]:
                        best = x
                # first break
                above = np.nonzero(C[best+1:] > H[best])[0]
                fb = best + 1 + above[0] if len(above) else 10**9
                cand[j] = (best, H[best], fb)
    lastc = [None] * (len(sl) + 1)  # lastc[m] = last candidate among sl[0:m]
    cur = None
    for m in range(1, len(sl) + 1):
        if cand[m-1] is not None:
            cur = cand[m-1]
        lastc[m] = cur
    # ATR14
    tr = np.maximum(H[1:] - L[1:], np.maximum(abs(H[1:] - C[:-1]), abs(L[1:] - C[:-1])))
    tr = np.concatenate([[H[0]-L[0]], tr])
    atr = np.convolve(tr, np.ones(14)/14, 'full')[:n]
    obj = dict(D=D, O=O, H=H, L=L, C=C, sl=sl, lastc=lastc, atr=atr)
    _cache[tk] = obj
    return obj


def struct_exit_level(o, k):
    """Swing-low exit level at close of day k if structure (from bars <k) not broken, else None."""
    m = bisect.bisect_right(o['sl'], k - 3)
    if m == 0:
        return None
    c = o['lastc'][m]
    broken = c is not None and c[2] <= k - 1
    if broken:
        return None
    return o['L'][o['sl'][m-1]]


def stop_of(o, idx):
    # recentSwingLowOf(bars[0:idx])
    L = o['L']
    for k in range(idx - 2, 0, -1):
        if L[k] <= L[k-1] and L[k] <= L[k+1]:
            return L[k] * 0.99
    return L[max(0, idx-5):idx].min() * 0.99


def simulate(o, idx, ep, stop, ts_days=10, ts_min=0.05, extra=None, max_days=None):
    """extra(o, idx, ep, stop, k, j) -> True = exit signal at close of day k (j = k-idx)."""
    C, O = o['C'], o['O']
    n = len(C)
    for k in range(idx, n):
        j = k - idx
        reason = None
        if ts_days is not None and j == ts_days and C[k] < ep * (1 + ts_min):
            reason = 'zeitstopp'
        elif extra is not None and extra(o, idx, ep, stop, k, j):
            reason = 'extra'
        else:
            lvl = struct_exit_level(o, k)
            if lvl is not None and C[k] < lvl:
                reason = 'struktur'
            elif C[k] < stop:
                reason = 'stopp'
        if reason:
            if k + 1 < n:
                return k + 1, O[k+1], reason, False
            return k, C[k], reason, False
    return n - 1, C[-1], 'offen', True


def load_trades() -> pd.DataFrame:
    rows = []
    for t in json.load(open(ROOT + '/data/backtest_ndx.json'))['trades']:
        o = load_daily(t['ticker'])
        if o is None:
            continue
        idx = int(np.searchsorted(o['D'], t['entryDate']))
        if idx >= len(o['D']):
            continue
        ei, xp, _, op = simulate(o, idx, t['entryPrice'], t['stopPrice'])
        if op != t['isOpen'] or o['D'][ei] != t['exitDate']:
            continue  # nur Trades, deren Ausstieg der Nachbau exakt trifft
        rows.append(dict(ticker=t['ticker'], entryDate=t['entryDate'], idx=idx, ep=t['entryPrice'],
                         stop=t['stopPrice'], etime=t['entryTime'], inv=t['invested']))
    return pd.DataFrame(rows).sort_values(['entryDate', 'etime', 'ticker']).reset_index(drop=True)
def exits_for(sub: pd.DataFrame, extra=None, ts_days=10, ts_min=0.05):
    ed, xp = [], []
    for r in sub.itertuples():
        o = load_daily(r.ticker)
        ei, x, _, op = simulate(o, r.idx, r.ep, r.stop, ts_days, ts_min, extra)
        ed.append(o['D'][ei] if not op else '9999')
        xp.append(x)
    return np.array(ed), np.array(xp)


def depot(sub, ed, xp, frac, start, end, cal, closes):
    """10 Plätze, Platzgröße wie Engine (frac = invested/10000), Zinseszins ab 100.000 €."""
    idxs = np.nonzero(((sub.entryDate >= start) & (sub.entryDate <= end)).values)[0]
    cash, openp, eq, nxt, taken = 100000.0, [], [], 0, []
    for day in (d for d in cal if d >= start):
        for p in list(openp):
            if ed[p[0]] <= day:
                cash += p[1] * xp[p[0]]
                taken.append(p[1] * xp[p[0]] - p[2])
                openp.remove(p)
        while nxt < len(idxs) and sub.entryDate.iloc[idxs[nxt]] <= day:
            i = idxs[nxt]
            nxt += 1
            equity = cash + sum(p[1] * p[3] for p in openp)
            lim, slot = (10, equity / 10) if equity >= 100000 else (int(equity // 10000), 10000)
            if len(openp) >= lim or any(sub.ticker.iloc[p[0]] == sub.ticker.iloc[i] for p in openp):
                continue
            cost = min(slot * min(frac[i], 1.0), cash)
            if cost <= 0:
                continue
            cash -= cost
            openp.append([i, cost / sub.ep.iloc[i], cost, sub.ep.iloc[i]])
        for p in openp:
            c = closes[sub.ticker.iloc[p[0]]].get(day)
            if c is not None:
                p[3] = c
        eq.append((day, cash + sum(p[1] * p[3] for p in openp)))
        if day >= end and nxt >= len(idxs):
            break
    k = max(i for i, x in enumerate(eq) if x[0] <= end)
    e = np.array([x[1] for x in eq[:k + 1]])
    cagr = (e[-1] / 1e5) ** (252 / len(e)) - 1
    dd = (e / np.maximum.accumulate(e) - 1).min()
    r = np.diff(np.log(e))
    pn = np.array(taken)
    return dict(cagr=round(cagr * 100, 1), maxDD=round(dd * 100, 1),
                sharpe=round(r.mean() / r.std() * np.sqrt(252), 2), taken=len(pn),
                PF=round(pn[pn > 0].sum() / -pn[pn < 0].sum(), 2))


PERIODS = [('2016-21', '2016-01-01', '2021-12-31'), ('2022-26', '2022-01-01', '2026-10-09')]


def day_close_below_entry(day, pct=0.0):
    """Frühausstieg: Schluss am Tag `day` nach dem Einstieg unter Einstieg × (1 + pct)."""
    return lambda o, idx, ep, stop, k, j: j == day and o['C'][k] < ep * (1 + pct / 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=30)
    args = ap.parse_args()
    bt = load_trades()
    feats = pd.read_csv(ROOT + '/research/data/trade_features.csv')
    feats = feats[['ticker', 'entryDate', 'weekly_last_sh_vs_prev_pct', 'qqq_ret63_pct']]
    B = bt.merge(feats.drop_duplicates(['ticker', 'entryDate']), on=['ticker', 'entryDate'], how='left')
    closes = {tk: dict(zip(load_daily(tk)['D'], load_daily(tk)['C'])) for tk in B.ticker.unique()}
    cal = sorted({d for tk in closes for d in closes[tk] if d >= '2016-01-01'})
    print(f'{len(B)} Trades (Ausstieg exakt wie Engine)')

    exits = {'base': exits_for(B), 'E': exits_for(B, day_close_below_entry(2)),
             'E3': exits_for(B, day_close_below_entry(3)), 'E2-1': exits_for(B, day_close_below_entry(2, -1))}
    fr = (B.inv / 10000).values
    klimax = B.weekly_last_sh_vs_prev_pct.fillna(0).values > 12.7
    hot = B.qqq_ret63_pct.fillna(0).values > 11
    alle = np.ones(len(B), bool)
    half = lambda m: np.where(m, fr * 0.5, fr)
    variants = {  # Name: (Ausstieg, behalten, Positionsanteil)
        'B Basis': ('base', alle, fr),
        'E Frühausstieg Tag 2': ('E', alle, fr),
        'E3 Frühausstieg Tag 3': ('E3', alle, fr),
        'E2-1 Tag 2 < -1 %': ('E2-1', alle, fr),
        'K Klimax-Sperre': ('base', ~klimax, fr),
        'K½ Klimax halbe Pos.': ('base', alle, half(klimax)),
        'Q½ Markt heiß halbe Pos.': ('base', alle, half(hot)),
        'E+K': ('E', ~klimax, fr),
        'E+K½+Q½': ('E', alle, half(klimax | hot)),
        'E+K+Q½': ('E', ~klimax, half(hot)),
    }

    def run(name, keep):
        ex, km, f = variants[name]
        ed, xp = exits[ex]
        m = km & keep
        sub = B[m].reset_index(drop=True)
        return {p: depot(sub, ed[m], xp[m], f[m], s, e, cal, closes) for p, s, e in PERIODS}

    full = {v: run(v, alle) for v in variants}
    rng = np.random.default_rng(7)
    mc = {v: {p: [] for p, _, _ in PERIODS} for v in variants}
    for _ in range(args.runs):
        keep = rng.random(len(B)) > 0.2
        for v in variants:
            for p, r in run(v, keep).items():
                mc[v][p].append((r['cagr'], r['sharpe'], r['maxDD']))
    rows = []
    for v in variants:
        row = {'Variante': v}
        for p, _, _ in PERIODS:
            f = full[v][p]
            row.update({f'{p} CAGR': f['cagr'], f'{p} Sharpe': f['sharpe'], f'{p} MaxDD': f['maxDD'], f'{p} PF': f['PF']})
            if args.runs:
                a, b = np.array(mc[v][p]), np.array(mc['B Basis'][p])
                row[f'{p} >B CAGR/Sh/DD'] = f"{(a[:, 0] > b[:, 0]).sum()}/{(a[:, 1] > b[:, 1]).sum()}/{(a[:, 2] > b[:, 2]).sum()}"
        rows.append(row)
    pd.set_option('display.width', 300)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == '__main__':
    main()
