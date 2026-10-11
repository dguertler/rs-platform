"""Loop 1 Praktiker: Einstieg/Auswahl-Varianten auf dem Prüfstand research/loop_harness.py."""
import sys, math, pickle, os
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
import numpy as np, pandas as pd
from loop_harness import evaluate, load, fmt, qqq_ref
from trading_approaches import Strategy, Entry, keep_signal

HERE = os.path.dirname(os.path.abspath(__file__))

def weekly_diff(h):
    w = h.resample("W-FRI").agg({"h": "max", "l": "min", "c": "last"}).dropna().iloc[-60:]
    hi = w["h"].values
    sh = [hi[i] for i in range(1, len(hi) - 1) if hi[i] >= hi[i - 1] and hi[i] >= hi[i + 1]]
    return (sh[-1] / sh[-2] - 1) * 100 if len(sh) >= 2 else np.nan

def base_cnt(c, l):
    if len(c) < 210: return np.nan
    s200 = pd.Series(c).rolling(200).mean().values
    below = np.where(c < s200)[0]
    start = min(below[-1] + 1 if len(below) else 200, len(c) - 1)
    nb = 0; hi = c[start]; hid = start; inbase = False; lows = hi
    for i in range(start, len(c)):
        if c[i] > hi:
            if inbase: nb += 1
            hi = c[i]; hid = i; inbase = False; lows = c[i]
        else:
            lows = min(lows, l[i])
            if i - hid >= 15 and (hi - lows) / hi >= 0.08: inbase = True
    return nb

def features(m, sigs):
    f = os.path.join(HERE, 'feat.pkl')
    if os.path.exists(f): return pickle.load(open(f, 'rb'))
    col = {x: k for k, x in enumerate(m.c.columns)}
    ret126 = m.ind['ret126'].values; top = m.in_top.values
    out = {}
    for i, lst in sigs.items():
        j = i - 1
        # RS-Rang (ret126) innerhalb der Top 20 am Vortag
        r = ret126[j]; mask = top[j] & ~np.isnan(r)
        order = np.argsort(-np.where(mask, r, -np.inf))
        rank = {k: n + 1 for n, k in enumerate(order[:mask.sum()])}
        for sg in lst:
            k = col[sg['sym']]
            hist = pd.DataFrame({'h': m.h.iloc[:i, k], 'l': m.l.iloc[:i, k], 'c': m.c.iloc[:i, k]}).dropna()
            c = hist.c.values; l = hist.l.values; h = hist.h.values
            win = hist.iloc[-126:]
            pk = win.h.values.argmax(); depth = (win.l.values[pk:].min() / win.h.values[pk] - 1) * 100
            out[(sg['sym'], sg['entryDate'])] = dict(
                wk=weekly_diff(hist), base=base_cnt(c, l), rank=rank.get(k, 99),
                ret126=r[k] if not math.isnan(r[k]) else 0.0, corr126=depth,
                dist_ath=(c[-1] / h.max() - 1) * 100)
    pickle.dump(out, open(f, 'wb'))
    return out

def day2_exit(m, i, sg, pct=0.0):
    """Frühausstieg: Schluss Tag 2 (i+2) < Einstieg → Verkauf Eröffnung i+3, falls Engine-Ausstieg später."""
    k = m.c.columns.get_loc(sg['sym']); fe = sg['fixed_exit']
    if i + 3 >= len(m.dates): return fe
    cl = m.c.values[i + 2, k]
    if not math.isnan(cl) and cl < sg['entryPrice'] * (1 + pct / 100) and (fe is None or fe[0] > i + 3):
        return (i + 3, m.o.values[i + 3, k])
    return fe

def make(F, *, climax=None, late=None, maxrank=None, prio='time', early=False, deep_only=None,
         max_pos=10, name='x', cash_q=False):
    def build(m, sigs, seed):
        def cand(i, held):
            out = []
            for sg in sigs.get(i, []):
                if not keep_signal(seed, sg['sym'], sg['entryDate']): continue
                x = F[(sg['sym'], sg['entryDate'])]
                if climax is not None and x['wk'] == x['wk'] and x['wk'] > climax: continue
                if late is not None and x['base'] == x['base'] and x['base'] >= late: continue
                if maxrank is not None and x['rank'] > maxrank: continue
                if deep_only is not None and x['corr126'] > deep_only: continue
                pr = {'time': 0.0, 'ret126': x['ret126'], 'deep': -x['corr126'] / 100}[prio]
                pr -= (10 if sg['entryTime'] > '14:00' else 0)
                fe = day2_exit(m, i, sg) if early else sg['fixed_exit']
                out.append(Entry(sg['sym'], pr, sg['entryPrice'], sg['stopPrice'], fe, tag='gws'))
            return out
        return Strategy(name, cand, max_positions=max_pos, cash_in_qqq=cash_q)
    return build

if __name__ == '__main__':
    m, sigs = load()
    F = features(m, sigs)
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    V = {
     'V0 A2 Basis': dict(),
     'V1 Klimax-Sperre': dict(climax=12.7),
     'V2 Klimax+Spätbasis(>=3)': dict(climax=12.7, late=3),
     'V3 V2+Tag2': dict(climax=12.7, late=3, early=True),
     'V4 V3+Vorrang ret126': dict(climax=12.7, late=3, early=True, prio='ret126'),
     'V5 V3+nur RS-Top10': dict(climax=12.7, late=3, early=True, maxrank=10),
     'V6 V3+7 Plätze': dict(climax=12.7, late=3, early=True, max_pos=7),
     'V7 V3+Top10+5 Plätze': dict(climax=12.7, late=3, early=True, maxrank=10, max_pos=5),
     'V8 V3+Vorrang tiefe Basis': dict(climax=12.7, late=3, early=True, prio='deep'),
     'V9 Tag2 allein': dict(early=True),
     'V10 Tag2+Vorrang tief': dict(early=True, prio='deep'),
     'V11 Tag2+Vorrang ret126': dict(early=True, prio='ret126'),
     'V12 Tag2+Spätbasis+Vorrang tief': dict(early=True, late=3, prio='deep'),
     'V13 Tag2+nur Basis<=-12%': dict(early=True, deep_only=-12),
     'V14 V10+Cash in QQQ': dict(early=True, prio='deep', cash_q=True),
     'V15 V8+Cash in QQQ': dict(climax=12.7, late=3, early=True, prio='deep', cash_q=True),
     'V16 V13+Cash in QQQ': dict(early=True, deep_only=-12, cash_q=True),
     'V17 V16+Klimax+Spätbasis': dict(early=True, deep_only=-12, climax=12.7, late=3, cash_q=True),
     'V18 Tag2+Basis<=-8%+Cash': dict(early=True, deep_only=-8, cash_q=True),
     'V19 Tag2+Basis<=-15%+Cash': dict(early=True, deep_only=-15, cash_q=True),
     'V20 Tag2+Basis<=-20%+Cash': dict(early=True, deep_only=-20, cash_q=True),
     'V21 V16 ohne Tag2': dict(deep_only=-12, cash_q=True),
    }
    sel = sys.argv[2].split(',') if len(sys.argv) > 2 else list(V)
    for k in V:
        if not any(k.startswith(s) for s in sel): continue
        r = evaluate(k, make(F, name=k, **V[k]), m, sigs, runs=runs)
        print(fmt(r), f"| MaxDD16-21 {r['16-21']['maxDD']:.1f} 22-26 {r['22-26']['maxDD']:.1f} trades {r['16-26']['trades']}", flush=True)
