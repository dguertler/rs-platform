"""Studie: klassische Swing-Trading-Setups auf den Top-20-Titeln.

Gleiche Daten, gleiche Depot-Simulation und gleiche Kosten wie
research/trading_approaches.py (NASDAQ-100 Top 20 point-in-time, 10 Plätze,
0,1 % je Seite, Signal am Tagesschluss → Kauf zur nächsten Eröffnung).

Je Setup zwei Läufe:
  * allein (eigenes Depot, 10 Plätze)
  * auf den freien Plätzen des heutigen Breakout-Depots (A2), Breakouts haben Vorrang

Aufruf: python3 research/swing_setups.py → research/results/swing_setups.json + Tabellen
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

import trading_approaches as T

OUT = Path(__file__).resolve().parent / "results" / "swing_setups.json"
PERIODS = dict(T.PERIODS, **{"2008–2015 (nur Tagesdaten)": ("2008-01-01", "2015-12-31")})


def extra_indicators(m: T.Market) -> dict:
    c, h, l, o = m.c, m.h, m.l, m.o
    rng = h - l
    std20 = c.rolling(20).std()
    return {
        "ema9": c.ewm(span=9, adjust=False).mean(),
        "ema21": c.ewm(span=21, adjust=False).mean(),
        "bb_lo": c.rolling(20).mean() - 2 * std20,
        "nr7": rng <= rng.rolling(7).min(),
        "inside": (h <= h.shift(1)) & (l >= l.shift(1)),
        "ret1": c / c.shift(1) - 1,
        "clv": (c - l) / rng.where(rng > 0),          # Schluss im Tagesbereich (0 = Tief, 1 = Hoch)
        "hi10": h.rolling(10).max(),
        "lo3": l.rolling(3).min(),
    }


def swing_exit(m: T.Market, *, target_r=None, max_days=None, trail_low=None, below=None):
    """Swing-Ausstieg am Tagesschluss: Anfangsstopp, optional Kursziel in R, Zeitlimit,
    Schluss unter dem n-Tage-Tief oder unter einer Linie (z. B. ema21)."""
    c = m.c.values
    col = {x: k for k, x in enumerate(m.c.columns)}
    lows = m.ind[f"lo{trail_low}"].values if trail_low else None
    line = m.ind[below].values if below else None

    def rule(p: T.Position, i: int) -> bool:
        k, x = col[p.sym], c[i, col[p.sym]]
        if p.stop is not None and x < p.stop:
            return True
        if target_r and p.stop is not None and x >= p.entry_price + target_r * (p.entry_price - p.stop):
            return True
        if max_days and i - p.entry_i >= max_days:
            return True
        if lows is not None and i > p.entry_i and not math.isnan(lows[i, k]) and x < lows[i, k]:
            return True
        if line is not None and i > p.entry_i and not math.isnan(line[i, k]) and x < line[i, k]:
            return True
        return False
    return rule


def setup(m: T.Market, cond, stop_of):
    """Kandidaten am Tag i aus dem Signal am Schluss von i-1; Vorrang = 6M-Momentum."""
    top, ret = m.in_top.values, m.ind["ret126"].values
    syms = list(m.c.columns)

    def cand(i: int, held: set) -> list:
        j = i - 1
        out = []
        for k, s in enumerate(syms):
            if not top[j, k] or s in held:
                continue
            try:
                ok = cond(j, k)
            except (IndexError, ValueError):
                ok = False
            if ok:
                st = stop_of(j, k)
                out.append(T.Entry(s, 0 if math.isnan(ret[j, k]) else ret[j, k], None,
                                   None if st is None or math.isnan(st) else st, tag="swing"))
        return out
    return cand


def build(m: T.Market) -> dict:
    I = m.ind
    c, h, l = m.c.values, m.h.values, m.l.values
    v = {k: I[k].values for k in ("sma20", "sma50", "sma200", "ema9", "ema21", "bb_lo", "nr7", "inside",
                                   "ret1", "clv", "hi10", "lo3", "atr14", "ret63", "rsi2", "sma5")}
    up = lambda j, k: c[j, k] > v["sma50"][j, k] > v["sma200"][j, k]
    S = {}

    # 1 Pullback an die 21-EMA im Aufwärtstrend mit Umkehrkerze (Holy-Grail-Variante)
    S["S1 Pullback an 21-EMA + Umkehr"] = (setup(m,
        lambda j, k: up(j, k) and v["ret63"][j, k] > 0.10 and l[j, k] <= v["ema21"][j, k] < c[j, k]
        and v["hi10"][j, k] > v["ema21"][j, k] * 1.05,
        lambda j, k: v["lo3"][j, k] * 0.99),
        swing_exit(m, target_r=2, max_days=15))
    # 2 Bollinger-Rücksetzer im Aufwärtstrend (Mean Reversion)
    S["S2 Schluss unter unterem Bollinger-Band (über 200T)"] = (setup(m,
        lambda j, k: c[j, k] > v["sma200"][j, k] and c[j, k] < v["bb_lo"][j, k],
        lambda j, k: c[j, k] - 2.5 * v["atr14"][j, k]),
        _mean_exit(m))
    # 3 NR7/Inside-Day-Ausbruch im Trend
    S["S3 NR7-/Inside-Day-Ausbruch im Trend"] = (setup(m,
        lambda j, k: up(j, k) and (v["nr7"][j - 1, k] or v["inside"][j - 1, k]) and c[j, k] > h[j - 1, k],
        lambda j, k: l[j - 1, k] * 0.99),
        swing_exit(m, target_r=3, max_days=10, trail_low=None))
    # 4 Momentum-Burst (≥ 4 % Tagesplus, Schluss nahe Hoch, nach ruhigem Vortag)
    S["S4 Momentum-Burst ≥ 4 %"] = (setup(m,
        lambda j, k: c[j, k] > v["sma50"][j, k] and v["ret1"][j, k] >= 0.04 and v["clv"][j, k] >= 0.7
        and abs(v["ret1"][j - 1, k]) < 0.015,
        lambda j, k: l[j, k] * 0.99),
        swing_exit(m, max_days=5))
    # 5 EMA-9/21-Kreuzung im Trend, Ausstieg bei Schluss unter der 21-EMA
    S["S5 EMA-9/21-Kreuzung"] = (setup(m,
        lambda j, k: c[j, k] > v["sma200"][j, k] and v["ema9"][j, k] > v["ema21"][j, k]
        and v["ema9"][j - 1, k] <= v["ema21"][j - 1, k],
        lambda j, k: c[j, k] - 2 * v["atr14"][j, k]),
        swing_exit(m, below="ema21"))
    # 6 Pullback-Kontinuität: 3 rote Tage im starken Trend, Kauf über Vortageshoch
    S["S6 3-Tage-Rücksetzer + Ausbruch über Vortageshoch"] = (setup(m,
        lambda j, k: up(j, k) and v["ret1"][j - 1, k] < 0 and v["ret1"][j - 2, k] < 0 and v["ret1"][j - 3, k] < 0
        and c[j, k] > h[j - 1, k],
        lambda j, k: v["lo3"][j, k] * 0.99),
        swing_exit(m, target_r=2, max_days=10))
    # Referenz aus der ersten Studie
    rc, rr = T.rsi2_pullback(m)
    S["D5 RSI(2) < 10 (Referenz)"] = (rc, rr)
    return S


def _mean_exit(m: T.Market):
    c, sma20 = m.c.values, m.ind["sma20"].values
    col = {x: k for k, x in enumerate(m.c.columns)}

    def rule(p: T.Position, i: int) -> bool:
        k = col[p.sym]
        return (p.stop is not None and c[i, k] < p.stop) or c[i, k] > sma20[i, k] or i - p.entry_i >= 10
    return rule


def run() -> dict:
    m = T.load_market()
    m.ind.update(extra_indicators(m))
    sigs = T.load_signals(m)
    res = {}
    for pname, (a, z) in PERIODS.items():
        rows = []
        if not pname.startswith("2008"):
            a2 = T.Strategy("A2 Breakout heute (volle Plätze)", T.gws_candidates(m, sigs, engine_exit=True))
            r = T.simulate(m, a2, a, z)
            rows.append({"name": a2.name, "mode": "Breakout", **T.metrics(r["equity"], r["trades"], r["exposure"])})
        for name, (cand, rule) in build(m).items():
            r = T.simulate(m, T.Strategy(name, cand, rule), a, z)
            rows.append({"name": name, "mode": "allein", **T.metrics(r["equity"], r["trades"], r["exposure"])})
            if pname.startswith("2008"):
                continue
            cc, cr = T.combined(T.gws_candidates(m, sigs, engine_exit=True), lambda p, i: False, cand, rule)
            r = T.simulate(m, T.Strategy(name, cc, cr), a, z)
            rows.append({"name": name, "mode": "+ Breakout", **T.metrics(r["equity"], r["trades"], r["exposure"])})
        res[pname] = rows
    return res


if __name__ == "__main__":
    res = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=float))
    f = T.fmt
    for p, rows in res.items():
        print(f"\n### {p}\n\n| Setup | Modus | CAGR | Max-DD | Sharpe | PF | Trades | Treffer | Ø Tage | investiert |\n|---|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            print(f"| {r['name']} | {r['mode']} | {f(r['cagr'])} % | {f(r['maxDD'])} % | {f(r['sharpe'], 2)} | {f(r.get('pf'), 2)} | "
                  f"{r.get('trades')} | {f(r.get('winrate'), 0)} % | {f(r.get('avgDays'), 0)} | {f(r.get('exposure'), 0)} % |")
    print(f"\n→ {OUT}")
