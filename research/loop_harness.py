"""Prüfstand für die Strategie-Loops 10/2026: Ziel „Nasdaq schlagen“.

Ziel (alle Bedingungen, nach 0,1 % Kosten je Seite):
  1. Profitfaktor (in €, alle Trades 2016–2026) ≥ 3
  2. CAGR über QQQ Buy & Hold in 2016–2021 UND in 2022–2026
  3. Robust: in ≥ 70 % von 30 Läufen (je 20 % der 4H-Signale fallen weg) über QQQ — beide Zeiträume

Eine Variante ist eine Funktion build(m, sigs, seed) -> Strategy (siehe trading_approaches.py:
Strategy, Entry, Position, gws_candidates, exit_rules, rsi2_pullback, rotation, combined ...).

    from loop_harness import evaluate, load
    m, sigs = load()
    print(evaluate("Name", build, m, sigs, runs=30))

Aufruf direkt: python3 research/loop_harness.py  → QQQ-Referenz und heutige Plattform (A2).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trading_approaches import (PERIODS, Strategy, gws_candidates, load_market, load_signals,  # noqa: E402
                                metrics, qqq_strategies, simulate)

GOAL_PF = 3.0
GOAL_ROBUST = 0.70
SPLITS = {"16-21": PERIODS["2016–2021 (Training)"], "22-26": PERIODS["2022–2026 (Test)"]}
FULL = PERIODS["2016–2026"]
_cache: dict = {}


def load():
    if "m" not in _cache:
        m = load_market()
        _cache["m"], _cache["sigs"] = m, load_signals(m)
    return _cache["m"], _cache["sigs"]


def qqq_ref(m) -> dict:
    out = {}
    for k, (a, z) in {**SPLITS, "16-26": FULL}.items():
        out[k] = metrics(qqq_strategies(m, a, z)["QQQ Buy & Hold"])
    return out


def evaluate(name: str, build, m, sigs, runs: int = 30) -> dict:
    """build(m, sigs, seed) -> Strategy. Liefert Kennzahlen, QQQ-Vergleich und Zielprüfung."""
    q = qqq_ref(m)
    res = {"name": name}
    full = simulate(m, build(m, sigs, None), *FULL)
    res["16-26"] = metrics(full["equity"], full["trades"], full["exposure"])
    for k, (a, z) in SPLITS.items():
        r = simulate(m, build(m, sigs, None), a, z)
        res[k] = metrics(r["equity"], r["trades"], r["exposure"])
    beats = {k: [] for k in SPLITS}
    for sd in range(runs):
        for k, (a, z) in SPLITS.items():
            cagr = metrics(simulate(m, build(m, sigs, sd), a, z)["equity"])["cagr"]
            beats[k].append(cagr > q[k]["cagr"])
    res["robust"] = {k: float(np.mean(v)) if v else float("nan") for k, v in beats.items()}
    res["goal"] = {
        "pf": res["16-26"]["pf"] >= GOAL_PF,
        "beats_qqq_16_21": res["16-21"]["cagr"] > q["16-21"]["cagr"],
        "beats_qqq_22_26": res["22-26"]["cagr"] > q["22-26"]["cagr"],
        "robust": runs == 0 or all(v >= GOAL_ROBUST for v in res["robust"].values()),
    }
    res["goal_met"] = all(res["goal"].values())
    return res


def fmt(res: dict, q: dict | None = None) -> str:
    f = lambda x, d=1: f"{x:.{d}f}"
    s = (f"{res['name']}: 16–26 CAGR {f(res['16-26']['cagr'])} % PF {f(res['16-26']['pf'], 2)} "
         f"MaxDD {f(res['16-26']['maxDD'])} % Sharpe {f(res['16-26']['sharpe'], 2)} Trades {res['16-26']['trades']} | "
         f"16–21 {f(res['16-21']['cagr'])} % (PF {f(res['16-21']['pf'], 2)}) | 22–26 {f(res['22-26']['cagr'])} % "
         f"(PF {f(res['22-26']['pf'], 2)}) | robust >QQQ {res['robust']} | Ziel {'ERREICHT' if res['goal_met'] else res['goal']}")
    return s


def platform_today(m, sigs, seed):
    return Strategy("A2 Plattform (volle Plätze)", gws_candidates(m, sigs, engine_exit=True, seed=seed))


if __name__ == "__main__":
    m, sigs = load()
    for k, v in qqq_ref(m).items():
        print(f"QQQ Buy & Hold {k}: CAGR {v['cagr']:.1f} %  MaxDD {v['maxDD']:.1f} %  Sharpe {v['sharpe']:.2f}")
    print(fmt(evaluate("A2 Plattform heute", platform_today, m, sigs, runs=5)))
