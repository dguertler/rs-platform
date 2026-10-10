"""Studie: Rücksetzer im QQQ kaufen — welche Dip-Strategien tragen?

Bekannte Regeln (Connors RSI-2, Double 7s, IBS, Serien roter Tage, Drawdown-Kauf)
auf den QQQ-Tageskerzen (data/backtest_history/charts/_benchmark.json, ab 2005).
Je Strategie zwei Ausführungen: Kauf zum Schlusskurs des Signaltags (Market-on-Close)
und — wie die Plattform-Jobs — zur Eröffnung des nächsten Tages. Verkauf in derselben
Ausführung. 0,1 % Kosten je Seite, Cash ohne Zins.

Aufruf: python3 research/qqq_dips.py → research/results/qqq_dips.json + Tabellen
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "data" / "backtest_history" / "charts" / "_benchmark.json"
OUT = Path(__file__).resolve().parent / "results" / "qqq_dips.json"
COST = 0.001
PERIODS = {"2006–2026": ("2006-01-01", "2026-12-31"),
           "2006–2015": ("2006-01-01", "2015-12-31"),
           "2016–2026": ("2016-01-01", "2026-12-31")}


def load() -> pd.DataFrame:
    d = pd.DataFrame(json.loads(BENCH.read_text())["d"], columns=["d", "o", "h", "l", "c"]).set_index("d")
    d.index = pd.to_datetime(d.index)
    c = d["c"]
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    d["rsi2"] = 100 - 100 / (1 + up / dn)
    d["sma5"] = c.rolling(5).mean()
    d["sma200"] = c.rolling(200).mean()
    d["lo7"] = c.rolling(7).min()
    d["hi7"] = c.rolling(7).max()
    d["ibs"] = (c - d["l"]) / (d["h"] - d["l"]).replace(0, np.nan)
    d["down"] = (delta < 0).astype(int)
    d["down3"] = d["down"].rolling(3).sum() == 3
    d["hi252"] = c.rolling(252).max()
    d["dd"] = c / d["hi252"] - 1
    return d


# Regeln: entry(row) / exit(row, tage_gehalten) am Tagesschluss
STRATS = {
    "RSI(2) < 10 über 200T (Connors)": (
        lambda r: r.c > r.sma200 and r.rsi2 < 10, lambda r, n: r.c > r.sma5 or n >= 10),
    "RSI(2) < 10 ohne Trendfilter": (
        lambda r: r.rsi2 < 10, lambda r, n: r.c > r.sma5 or n >= 10),
    "Double 7s (7-Tage-Tief → 7-Tage-Hoch)": (
        lambda r: r.c > r.sma200 and r.c <= r.lo7, lambda r, n: r.c >= r.hi7 or n >= 15),
    "IBS < 0,2 über 200T (Schluss am Tagestief)": (
        lambda r: r.c > r.sma200 and r.ibs < 0.2, lambda r, n: r.ibs > 0.8 or n >= 5),
    "3 rote Tage in Folge über 200T": (
        lambda r: r.c > r.sma200 and r.down3, lambda r, n: r.c > r.sma5 or n >= 10),
    "Drawdown ≥ 10 % → halten bis neues 52W-Hoch": (
        lambda r: r.dd <= -0.10, lambda r, n: r.dd >= -0.001),
    "Drawdown ≥ 20 % → halten bis neues 52W-Hoch": (
        lambda r: r.dd <= -0.20, lambda r, n: r.dd >= -0.001),
}


def simulate(d: pd.DataFrame, entry, exit_, mode: str) -> tuple[pd.Series, list]:
    """Tägliche Rendite; mode 'close' = Handel zum Signal-Schluss, 'open' = Eröffnung am Folgetag.
    Trades als (Verkaufsdatum, Rendite)."""
    rows = list(d.itertuples())
    ret = np.zeros(len(rows))
    trades = []
    inpos = buy_pending = sell_pending = False
    held, buy_px = 0, 0.0
    for i in range(1, len(rows)):
        r, prev = rows[i], rows[i - 1]
        # Ausführung zur Eröffnung (nur mode 'open')
        if buy_pending:
            ret[i] = r.c / r.o * (1 - COST) - 1
            inpos, held, buy_px, buy_pending = True, 0, r.o, False
        elif sell_pending:
            ret[i] = r.o / prev.c * (1 - COST) - 1
            trades.append((r.Index, r.o / buy_px * (1 - COST) ** 2 - 1))
            inpos = sell_pending = False
            continue                                   # kein Neueinstieg am Verkaufstag
        elif inpos:
            ret[i] = r.c / prev.c - 1
        # Entscheidung zum Schluss
        if inpos:
            held += 1
            if exit_(r, held):
                if mode == "close":
                    ret[i] = (1 + ret[i]) * (1 - COST) - 1
                    trades.append((r.Index, r.c / buy_px * (1 - COST) ** 2 - 1))
                    inpos = False
                else:
                    sell_pending = True
        elif not math.isnan(r.sma200) and not math.isnan(r.rsi2) and entry(r):
            if mode == "close":
                ret[i] -= COST
                inpos, held, buy_px = True, 0, r.c
            else:
                buy_pending = True
    return pd.Series(ret, index=d.index), trades


def metrics(r: pd.Series, trades: list | None = None, expo: float | None = None) -> dict:
    eq = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = (eq / eq.cummax() - 1).min()
    out = {"cagr": cagr * 100, "maxDD": dd * 100,
           "sharpe": r.mean() / r.std() * math.sqrt(252) if r.std() > 0 else float("nan")}
    if expo is not None:
        out["exposure"] = expo * 100
        out["cagr_per_exposure"] = cagr * 100 / expo if expo > 0 else float("nan")
    if trades is not None:
        t = np.array(trades) if trades else np.array([0.0])
        out.update({"trades": len(trades), "winrate": (t > 0).mean() * 100, "avgTrade": t.mean() * 100,
                    "pf": t[t > 0].sum() / -t[t <= 0].sum() if (t <= 0).any() else float("nan")})
    return out


def run() -> dict:
    d = load()
    bh = d["c"].pct_change().fillna(0)
    up = (d["c"] > d["sma200"]).shift(1, fill_value=False)
    timing = bh * up - up.astype(int).diff().abs().fillna(0) * COST
    res = {}
    for pname, (a, z) in PERIODS.items():
        rows = [{"name": "QQQ Buy & Hold", **metrics(bh[a:z], expo=1.0)},
                {"name": "QQQ 200-Tage-Timing", **metrics(timing[a:z], expo=float(up[a:z].mean()))}]
        for name, (en, ex) in STRATS.items():
            for mode, label in (("close", "Schluss"), ("open", "nächste Eröffnung")):
                r, trades = simulate(d, en, ex, mode)
                rr = r[a:z]
                tr = [x for dt, x in trades if pd.Timestamp(a) <= dt <= pd.Timestamp(z)]
                rows.append({"name": f"{name} — {label}", **metrics(rr, tr, float((rr != 0).mean()))})
        res[pname] = rows
    return res


def fmt(v, n=1):
    return "–" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{n}f}".replace(".", ",")


if __name__ == "__main__":
    res = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=float))
    for p, rows in res.items():
        print(f"\n### {p}\n\n| Strategie | CAGR | Max-DD | Sharpe | investiert | Trades | Treffer | Ø Trade |\n|---|---|---|---|---|---|---|---|")
        for r in rows:
            print(f"| {r['name']} | {fmt(r['cagr'])} % | {fmt(r['maxDD'])} % | {fmt(r['sharpe'], 2)} | "
                  f"{fmt(r.get('exposure'), 0)} % | {r.get('trades', '–')} | {fmt(r.get('winrate'), 0)} % | {fmt(r.get('avgTrade'), 2)} % |")
    print(f"\n→ {OUT}")
