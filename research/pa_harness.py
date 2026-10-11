"""Prüfstand für die Price-Action-Loops 10/2026: Ziel „Nasdaq schlagen“ mit PF ≥ 3.

Tagesansätze (Signal zum Tagesschluss, Kauf zur nächsten Eröffnung) lassen sich ohne Näherung
ab 2008 rechnen. Ein Lauf deckt 2008–2026 ab; die Zeiträume sind Abschnitte derselben Kurve.

Abschlusstor (gilt ab Loop 1, Kosten 0,25 % je Seite auf Aktien und QQQ-Umschichtungen):
  G1  2016–26: PF (€, Trades mit Einstieg 2016–26) ≥ 3, CAGR > QQQ in 2016–21 und 2022–26,
      ≥ 70 % von 30 Robustheitsläufen (20 % der Signale fallen weg) in beiden Zeiträumen vorn
  G2  2008–15: CAGR > QQQ und PF ≥ 3
  G3  Nullmodell: gleiche Zahl Einstiege je Tag in zufällige Top-20-Titel, gleicher Ausstieg,
      gleiche Stoppweite → Kandidat ≥ 90. Perzentil der CAGR in 2016–21 UND 2022–26

Eine Variante ist build(m, seed) -> Strategy (trading_approaches.Strategy). Die Kandidaten-
funktion muss keep_signal(seed, sym, tag) nutzen, damit der Robustheitstest greift, und darf
für Tag i nur Daten bis i-1 verwenden.

    from pa_harness import load, gates, fmt
    m = load()
    print(fmt(gates("Name", build, m)))

Aufruf direkt: python3 research/pa_harness.py → QQQ-Referenz und zwei Referenzansätze.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trading_approaches import (Entry, Strategy, donchian, keep_signal, load_market,  # noqa: E402
                                metrics, qqq_strategies, rsi2_pullback, simulate)

FEE = 0.0025
START, END = "2008-01-01", "2026-12-31"
PERIODS = {"08-15": ("2008-01-01", "2015-12-31"), "16-21": ("2016-01-01", "2021-12-31"),
           "22-26": ("2022-01-01", "2026-12-31"), "16-26": ("2016-01-01", "2026-12-31")}
_cache: dict = {}


def load():
    if "m" not in _cache:
        _cache["m"] = load_market()
    return _cache["m"]


def qqq_ref(m) -> dict:
    return {k: metrics(qqq_strategies(m, a, z)["QQQ Buy & Hold"])["cagr"] for k, (a, z) in PERIODS.items()}


def _slice(res: dict, a: str, z: str) -> dict:
    eq = res["equity"].loc[a:z].dropna()
    tr = [t for t in res["trades"] if a <= t["entry"] <= z]
    return metrics(eq, tr)


def run(m, strat: Strategy, fee: float = FEE) -> dict:
    """Ein Lauf 2008–2026. Merkt sich je Einstieg die Stoppweite (für das Nullmodell)."""
    stops: dict = {}
    tags: dict = {}
    inner = strat.candidates
    o = m.o.values
    col = {x: k for k, x in enumerate(m.c.columns)}

    def cand(i, held):
        es = inner(i, held)
        for e in es:
            px = e.price if e.price is not None else o[i, col[e.sym]]
            if e.stop is not None and px and px > e.stop:
                stops[(e.sym, i)] = 1 - e.stop / px
            tags[(e.sym, i)] = e.tag
        return es
    strat.candidates = cand
    res = simulate(m, strat, START, END, fee=fee)
    strat.candidates = inner
    idx = {d: i for i, d in enumerate(m.dates.strftime("%Y-%m-%d"))}
    for t in res["trades"]:
        t["stop_frac"] = stops.get((t["sym"], idx.get(t["entry"])))
        t["tag"] = tags.get((t["sym"], idx.get(t["entry"])), "")
    return {k: _slice(res, a, z) for k, (a, z) in PERIODS.items()} | {"_raw": res}


def null_model(m, build, real: dict, n: int, fee: float = FEE, seed0: int = 4242) -> list[dict]:
    """Je echtem Einstieg (Tag, Stoppweite) ein zufälliger Top-20-Titel am selben Tag, gleicher Ausstieg."""
    trades = real["_raw"]["trades"]
    idx = {d: i for i, d in enumerate(m.dates.strftime("%Y-%m-%d"))}
    per_day: dict[int, list] = {}
    o = m.o.values
    col = {x: k for k, x in enumerate(m.c.columns)}
    for t in trades:
        i = idx.get(t["entry"])
        if i is None:
            continue
        per_day.setdefault(i, []).append((t.get("stop_frac"), t.get("tag", "")))
    syms = list(m.c.columns)
    top = m.in_top.values
    base = build(m, None)
    out = []
    for r in range(n):
        rng = np.random.default_rng(seed0 + r)

        def cand(i, held, rng=rng):
            lst = per_day.get(i)
            if not lst:
                return []
            pool = [s for k, s in enumerate(syms) if top[i - 1, k] and s not in held and not math.isnan(o[i, k])]
            if not pool:
                return []
            pick = rng.choice(len(pool), size=min(len(lst), len(pool)), replace=False)
            es = []
            for j, (sf, tag) in zip(pick, lst):
                s = pool[j]
                px = o[i, col[s]]
                es.append(Entry(s, 0.0, None, px * (1 - sf) if sf is not None else None, tag=tag))
            return es
        st = Strategy(f"null{r}", cand, base.exit_rule, sizing=base.sizing, max_positions=base.max_positions,
                      regime_exit=base.regime_exit, cash_in_qqq=base.cash_in_qqq)
        res = simulate(m, st, START, END, fee=fee)
        out.append({k: _slice(res, a, z)["cagr"] for k, (a, z) in PERIODS.items()})
    return out


def gates(name: str, build, m, runs: int = 30, nperm: int = 200, fee: float = FEE) -> dict:
    q = qqq_ref(m)
    real = run(m, build(m, None), fee)
    rob = {"16-21": [], "22-26": []}
    for sd in range(runs):
        r = run(m, build(m, sd), fee)
        for k in rob:
            rob[k].append(r[k]["cagr"] > q[k])
    rob = {k: float(np.mean(v)) if v else float("nan") for k, v in rob.items()}
    perm = null_model(m, build, real, nperm, fee) if nperm else []
    pct = {k: float(np.mean([p[k] < real[k]["cagr"] for p in perm]) * 100) if perm else float("nan")
           for k in ("16-21", "22-26")}
    g1 = (real["16-26"]["pf"] >= 3 and real["16-21"]["cagr"] > q["16-21"] and real["22-26"]["cagr"] > q["22-26"]
          and min(rob.values()) >= 0.70)
    g2 = real["08-15"]["cagr"] > q["08-15"] and real["08-15"]["pf"] >= 3
    g3 = bool(perm) and min(pct.values()) >= 90
    return {"name": name, "qqq": q, **{k: real[k] for k in PERIODS}, "robust": rob, "perm_pct": pct,
            "G1": g1, "G2": g2, "G3": g3, "goal": g1 and g2 and g3}


def fmt(r: dict) -> str:
    f = lambda x, d=1: "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"
    parts = [f"{k} {f(r[k]['cagr'])} % PF {f(r[k]['pf'], 2)}" for k in PERIODS]
    return (f"{r['name']}: " + " | ".join(parts) + f" | MaxDD 16–26 {f(r['16-26']['maxDD'])} % | "
            f"robust {r['robust']} | Nullmodell-Perzentil {r['perm_pct']} | "
            f"G1 {r['G1']} G2 {r['G2']} G3 {r['G3']} → {'ZIEL' if r['goal'] else 'nein'}")


def ref_rsi2(m, seed):
    cand, rule = rsi2_pullback(m)

    def c(i, held):
        return [e for e in cand(i, held) if keep_signal(seed, e.sym, str(m.dates[i].date()))]
    return Strategy("Referenz RSI(2)-Pullback + Cash in QQQ", c, rule, cash_in_qqq=True)


def ref_donchian(m, seed):
    cand, rule = donchian(m)

    def c(i, held):
        return [e for e in cand(i, held) if keep_signal(seed, e.sym, str(m.dates[i].date()))]
    return Strategy("Referenz Donchian-50 + Cash in QQQ", c, rule, cash_in_qqq=True)


if __name__ == "__main__":
    m = load()
    print("QQQ", {k: round(v, 1) for k, v in qqq_ref(m).items()})
    for nm, b in (("RSI2", ref_rsi2), ("Donchian", ref_donchian)):
        print(fmt(gates(nm, b, m, runs=3, nperm=3)))
