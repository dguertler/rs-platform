"""Loop 4 (Risk): S3 mit weniger Umschlag. Pre-registriert in loop/l4_candidates.md.
R4A = S3 + Stoppweite >= 4 % + QQQ-Umschichtung monatlich;  R4B = R4A + Zeitstopp 15 Tage.
Simulator sim_sweep: Kopie der Logik von trading_approaches.simulate, aber getrennte Konten
Cash / QQQ-Bestand. sweep='trade' bildet das bisherige cash_in_qqq exakt nach (Referenz S3)."""
import sys, math, pickle
from multiprocessing import Pool
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
for p in [os.path.dirname(_HERE), _HERE]:
    sys.path.insert(0, p)
import numpy as np, pandas as pd
from loop_harness import load
from trading_approaches import Entry, Position, metrics, keep_signal, qqq_strategies, START_CAPITAL
from exits import Struct, make_rule
import prak
from guard import guard, pf_ci

m, sigs4 = load()
S = Struct(m)
F4 = prak.features(m, sigs4)
COL = {x: k for k, x in enumerate(m.c.columns)}
QRET = m.qqq['c'].pct_change().fillna(0).values
MONTH = m.dates.to_period('M')

CAND = {  # Name: (Stopp-Mindestweite %, QQQ-Umschichtung, Zeitstopp-Tage)
    'S3 (Referenz)': (None, 'trade', 10),
    'R4A': (4.0, 'month', 10),
    'R4B': (4.0, 'month', 15),
}


def select(sg, F, min_stop):
    x = F[(sg['sym'], sg['entryDate'])]
    if x['wk'] == x['wk'] and x['wk'] > 12.7: return False
    if x['base'] == x['base'] and x['base'] >= 3: return False
    if not x['corr126'] <= -12: return False
    if min_stop is not None and (sg['entryPrice'] / sg['stopPrice'] - 1) * 100 < min_stop: return False
    return True


def sim_sweep(sigs, F, cfg, start, end, fee=0.0025, seed=None, allowed=None, max_pos=10):
    min_stop, sweep, ts_days = cfg
    rule = make_rule(m, S, early=(2, 0.0), ts=(ts_days, 0.05))
    o, c = m.o.values, m.c.values
    i0 = int(m.dates.searchsorted(pd.Timestamp(start))); i1 = int(m.dates.searchsorted(pd.Timestamp(end), side='right'))
    cash, qv, fees = START_CAPITAL, 0.0, 0.0
    open_pos, trades, last = [], [], {}
    eq = np.full(i1 - i0, np.nan)

    def to_qqq(x):
        nonlocal cash, qv, fees
        cash -= x; qv += x * (1 - fee); fees += x * fee

    def from_qqq(need):           # beschafft `need` Cash durch QQQ-Verkauf
        nonlocal cash, qv, fees
        gross = min(qv, need / (1 - fee)); qv -= gross; cash += gross * (1 - fee); fees += gross * fee

    if sweep in ('trade', 'month'):
        to_qqq(cash)
    for i in range(i0, i1):
        if i > i0: qv *= 1 + QRET[i]
        for p in list(open_pos):
            k = COL[p.sym]
            if p.exit_flag:
                price = o[i, k] if not math.isnan(o[i, k]) else last.get(p.sym, p.entry_price)
            elif math.isnan(c[i, k]) and i > p.entry_i + 5 and np.isnan(c[i:min(i + 10, len(m.dates)), k]).all():
                price = last.get(p.sym, p.entry_price)
            else:
                continue
            proc = p.shares * price * (1 - fee); fees += p.shares * price * fee
            cash += proc
            trades.append({'sym': p.sym, 'entry': str(m.dates[p.entry_i].date()), 'exit': str(m.dates[i].date()),
                           'pnl': proc - p.cost, 'ret': proc / p.cost - 1, 'days': i - p.entry_i})
            open_pos.remove(p)
        if sweep == 'trade' and cash > 0:
            to_qqq(cash)
        if sweep == 'month' and i > i0 and MONTH[i] != MONTH[i - 1] and cash > 0:
            to_qqq(cash)
        held = {p.sym for p in open_pos}
        eqp = cash + qv + sum(p.shares * last.get(p.sym, p.entry_price) for p in open_pos)
        cands = []
        for sg in sigs.get(i, []):
            if allowed is not None:
                if (sg['sym'], sg['entryDate']) not in allowed: continue
            elif not (keep_signal(seed, sg['sym'], sg['entryDate']) and select(sg, F, min_stop)):
                continue
            cands.append(Entry(sg['sym'], -(10 if sg['entryTime'] > '14:00' else 0), sg['entryPrice'], sg['stopPrice']))
        for e in sorted(cands, key=lambda x: -x.priority):
            if len(open_pos) >= max_pos or e.sym in held: continue
            slot = eqp / max_pos
            if cash < slot and sweep != 'none':
                from_qqq(slot - cash)
            amt = min(slot, cash)
            if amt < 0.2 * slot: continue
            cash -= amt; fees += amt * fee
            open_pos.append(Position(e.sym, i, e.price, amt * (1 - fee) / e.price, amt, e.stop, e.price, None))
            held.add(e.sym)
        for p in open_pos:
            k = COL[p.sym]
            if not math.isnan(c[i, k]):
                last[p.sym] = c[i, k]; p.max_close = max(p.max_close, c[i, k])
                p.exit_flag = bool(rule(p, i))
        eq[i - i0] = cash + qv + sum(p.shares * last.get(p.sym, p.entry_price) for p in open_pos)
    for p in open_pos:
        v = p.shares * last.get(p.sym, p.entry_price)
        trades.append({'sym': p.sym, 'entry': str(m.dates[p.entry_i].date()), 'exit': None, 'pnl': v - p.cost,
                       'ret': v / p.cost - 1, 'days': i1 - 1 - p.entry_i})
    e = pd.Series(eq, index=m.dates[i0:i1])
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    return {'equity': e, 'trades': trades, 'fees': fees, 'fee_pa': fees / e.mean() / yrs * 100,
            'trades_pa': len(trades) / yrs}


P = {'16-21': ('2016-01-01', '2021-12-31'), '22-26': ('2022-01-01', '2026-12-31'),
     '16-26': ('2016-01-01', '2026-12-31'), '08-15': ('2008-01-01', '2015-12-31')}
QC = {k: metrics(qqq_strategies(m, a, z)['QQQ Buy & Hold'])['cagr'] for k, (a, z) in P.items()}
CTX = {}


def _rob(args):
    name, sd, per = args
    a, z = P[per]
    return metrics(sim_sweep(CTX['sigs'], CTX['F'], CAND[name], a, z, seed=sd)['equity'])['cagr'] > QC[per]


def _perm(args):
    name, allowed = args
    out = {}
    for per in ('16-21', '22-26'):
        a, z = P[per]
        out[per] = metrics(sim_sweep(CTX['sigs'], CTX['F'], CAND[name], a, z, allowed=allowed)['equity'])['cagr']
    return out
