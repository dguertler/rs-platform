"""Strategie-Studie: Welche Handelsansätze verbessern die RS-Plattform?

Vergleicht auf denselben Daten (NASDAQ-100, Top 20 point-in-time, Kurse aus
data/backtest_history/charts) und in derselben Depot-Simulation:

  * heutige Plattform-Logik (4H-Breakout W+D+4H, Stopp/Strukturbruch/Zeitstopp)
  * Varianten davon: Positionsgröße, Marktphasen-Filter, Ausstiegsregeln
  * alternative Ansätze: Momentum-Rotation, Pullback-Swing (RSI-2),
    Donchian-Breakout (Trendfolge), QQQ-Timing über die 200-Tage-Linie

Depot wie live: 100.000 € Start, höchstens 10 Positionen, Zinseszins,
0,1 % Kosten je Seite. Signale am Tagesschluss, Ausführung zur nächsten
Eröffnung; die 4H-Signale kaufen wie live zur nächsten 4H-Kerze
(research/export_signals.js). Kein Vorgriff: jede Regel sieht nur Kurse bis
zum Signalzeitpunkt.

Aufruf: python3 research/trading_approaches.py → research/results/trading_approaches.json
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CHARTS = ROOT / "data" / "backtest_history" / "charts"
SIGNALS = Path(__file__).resolve().parent / "data" / "signals_4h.json"
OUT = Path(__file__).resolve().parent / "results" / "trading_approaches.json"

START_CAPITAL = 100_000.0
MAX_POSITIONS = 10
COST = 0.001                     # 0,1 % je Seite (Gebühr + Slippage)
RISK_PER_TRADE = 0.01            # heutige Plattform: höchstens 1 % des Depots je Trade

PERIODS = {
    "2016–2026": ("2016-01-01", "2026-12-31"),
    "2016–2021 (Training)": ("2016-01-01", "2021-12-31"),
    "2022–2026 (Test)": ("2022-01-01", "2026-12-31"),
}


# ── Daten ───────────────────────────────────────────────────────────────────────
@dataclass
class Market:
    dates: pd.DatetimeIndex
    o: pd.DataFrame
    h: pd.DataFrame
    l: pd.DataFrame
    c: pd.DataFrame
    in_top: pd.DataFrame
    qqq: pd.DataFrame
    ind: dict = field(default_factory=dict)


def _intervals_to_mask(dates: pd.DatetimeIndex, intervals: list) -> np.ndarray:
    mask = np.zeros(len(dates), dtype=bool)
    for a, z in intervals:
        mask |= (dates >= pd.Timestamp(a)) & (dates <= pd.Timestamp(z))
    return mask


def load_market() -> Market:
    bench = json.loads((CHARTS / "_benchmark.json").read_text())
    qqq = pd.DataFrame(bench["d"], columns=["d", "o", "h", "l", "c"]).set_index("d")
    qqq.index = pd.to_datetime(qqq.index)
    dates = qqq.index
    cols = {k: {} for k in "ohlc"}
    top = {}
    for f in sorted(CHARTS.glob("*.json")):
        if f.name.startswith("_"):
            continue
        chart = json.loads(f.read_text())
        df = pd.DataFrame(chart["d"], columns=["d", "o", "h", "l", "c"]).drop_duplicates("d").set_index("d")
        df.index = pd.to_datetime(df.index)
        df = df.reindex(dates)
        sym = f.stem
        for k in "ohlc":
            cols[k][sym] = df[k]
        top[sym] = _intervals_to_mask(dates, (chart.get("top20") or {}).get("inkl", []))
    frames = {k: pd.DataFrame(v, index=dates) for k, v in cols.items()}
    in_top = pd.DataFrame(top, index=dates) & frames["c"].notna()
    m = Market(dates, frames["o"], frames["h"], frames["l"], frames["c"], in_top, qqq)
    m.ind = indicators(m)
    return m


def _rsi(c: pd.DataFrame, n: int) -> pd.DataFrame:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def indicators(m: Market) -> dict:
    c, h, l = m.c, m.h, m.l
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()]).groupby(level=0).max()
    q = m.qqq["c"]
    return {
        "sma5": c.rolling(5).mean(),
        "sma20": c.rolling(20).mean(),
        "sma50": c.rolling(50).mean(),
        "sma100": c.rolling(100).mean(),
        "sma200": c.rolling(200).mean(),
        "atr14": tr.rolling(14).mean(),
        "rsi2": _rsi(c, 2),
        "ret63": c / c.shift(63) - 1,
        "ret126": c / c.shift(126) - 1,
        "ret252_21": c.shift(21) / c.shift(252) - 1,
        "vol63": c.pct_change().rolling(63).std(),
        "hi50": c.rolling(50).max().shift(1),
        "lo10": l.rolling(10).min().shift(1),
        "lo20": l.rolling(20).min().shift(1),
        "qqq_up": (q > q.rolling(200).mean()).reindex(m.dates),
        "qqq_sma200": q.rolling(200).mean(),
    }


# ── Depot-Simulation ────────────────────────────────────────────────────────────
@dataclass
class Position:
    sym: str
    entry_i: int
    entry_price: float
    shares: float
    cost: float
    stop: float | None
    max_close: float
    fixed_exit: tuple | None = None      # (Datum-Index, Kurs) — heutige Engine-Ausstiege
    exit_flag: bool = False
    tag: str = ""


@dataclass
class Entry:
    sym: str
    priority: float
    price: float | None = None           # None = Eröffnung des Tages
    stop: float | None = None
    fixed_exit: tuple | None = None
    tag: str = ""


@dataclass
class Strategy:
    name: str
    # candidates(i) → Einstiege, die am Tag i ausgeführt werden (auf Basis von Daten bis i-1 bzw. 4H-Signal)
    candidates: Callable[[int, set], list]
    # exit_rule(pos, i) → True: Schluss am Tag i löst Verkauf zur Eröffnung i+1 aus
    exit_rule: Callable[[Position, int], bool] | None = None
    sizing: str = "equal"                # equal | risk
    max_positions: int = MAX_POSITIONS
    regime_exit: bool = False            # alles verkaufen, wenn QQQ unter die 200-Tage-Linie fällt
    cash_in_qqq: bool = False            # freies Cash liegt im QQQ (Kosten bei jeder Umschichtung)


def simulate(m: Market, s: Strategy, start: str, end: str, fee: float = COST) -> dict:
    o, c = m.o.values, m.c.values
    syms = list(m.c.columns)
    col = {x: k for k, x in enumerate(syms)}
    i0 = int(m.dates.searchsorted(pd.Timestamp(start)))
    i1 = int(m.dates.searchsorted(pd.Timestamp(end), side="right"))
    qqq_up = m.ind["qqq_up"].values
    qqq_ret = m.qqq["c"].pct_change().fillna(0).values
    cash = START_CAPITAL
    open_pos: list[Position] = []
    equity = np.full(i1 - i0, np.nan)
    invested = np.zeros(i1 - i0)
    trades = []
    last_close = {}

    def close_pos(p: Position, i: int, price: float):
        nonlocal cash
        proceeds = p.shares * price * (1 - fee)
        cash += proceeds * (1 - fee if s.cash_in_qqq else 1)
        trades.append({"sym": p.sym, "entry": str(m.dates[p.entry_i].date()), "exit": str(m.dates[i].date()),
                       "pnl": proceeds - p.cost, "ret": proceeds / p.cost - 1, "days": i - p.entry_i})

    for i in range(i0, i1):
        if s.cash_in_qqq and i > i0:
            cash *= 1 + qqq_ret[i]
        # 1. Verkäufe zur Eröffnung (Signal vom Vortag) bzw. feste Engine-Ausstiege
        for p in list(open_pos):
            k = col[p.sym]
            if p.fixed_exit is not None:
                if i >= p.fixed_exit[0]:
                    close_pos(p, i, p.fixed_exit[1])
                    open_pos.remove(p)
                continue
            if p.exit_flag:
                price = o[i, k] if not math.isnan(o[i, k]) else last_close.get(p.sym, p.entry_price)
                close_pos(p, i, price)
                open_pos.remove(p)
            elif math.isnan(c[i, k]) and i > p.entry_i + 5 and np.isnan(c[i:min(i + 10, len(m.dates)), k]).all():
                close_pos(p, i, last_close.get(p.sym, p.entry_price))   # Kursreihe endet (Delisting)
                open_pos.remove(p)

        # 2. Käufe
        held = {p.sym for p in open_pos}
        eq_prev = cash + sum(p.shares * last_close.get(p.sym, p.entry_price) for p in open_pos)
        for e in sorted(s.candidates(i, held), key=lambda x: -x.priority):
            if len(open_pos) >= s.max_positions or e.sym in held:
                continue
            k = col[e.sym]
            price = e.price if e.price is not None else o[i, k]
            if price is None or math.isnan(price) or price <= 0:
                continue
            slot = eq_prev / s.max_positions
            if s.sizing == "risk" and e.stop is not None and price > e.stop:
                slot = min(slot, eq_prev * RISK_PER_TRADE / (price - e.stop) * price)
            amount = min(slot, cash)
            if amount < 0.2 * eq_prev / s.max_positions:
                continue
            cash -= amount
            net = amount * (1 - fee) * (1 - fee if s.cash_in_qqq else 1)
            open_pos.append(Position(e.sym, i, price, net / price, amount, e.stop, price, e.fixed_exit, tag=e.tag))
            held.add(e.sym)

        # 3. Bewertung zum Schluss + Verkaufssignale
        for p in open_pos:
            k = col[p.sym]
            if not math.isnan(c[i, k]):
                last_close[p.sym] = c[i, k]
                p.max_close = max(p.max_close, c[i, k])
                if p.fixed_exit is None and s.exit_rule is not None:
                    p.exit_flag = bool(s.exit_rule(p, i))
            if s.regime_exit and not qqq_up[i]:
                p.exit_flag = True
        pos_val = sum(p.shares * last_close.get(p.sym, p.entry_price) for p in open_pos)
        equity[i - i0] = cash + pos_val
        invested[i - i0] = pos_val / (cash + pos_val)

    for p in open_pos:               # offen zum Datenende: Buchwert
        trades.append({"sym": p.sym, "entry": str(m.dates[p.entry_i].date()), "exit": None,
                       "pnl": p.shares * last_close.get(p.sym, p.entry_price) - p.cost,
                       "ret": p.shares * last_close.get(p.sym, p.entry_price) / p.cost - 1, "days": i1 - 1 - p.entry_i})
    eq = pd.Series(equity, index=m.dates[i0:i1])
    return {"equity": eq, "exposure": float(invested.mean()), "trades": trades}


# ── Kennzahlen ──────────────────────────────────────────────────────────────────
def metrics(eq: pd.Series, trades: list | None = None, exposure: float | None = None) -> dict:
    eq = eq.dropna()
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1
    dd = (eq / eq.cummax() - 1).min()
    r = eq.pct_change().dropna()
    sharpe = r.mean() / r.std() * math.sqrt(252) if r.std() > 0 else float("nan")
    out = {"cagr": cagr * 100, "maxDD": dd * 100, "sharpe": sharpe,
           "calmar": cagr / abs(dd) if dd < 0 else float("nan")}
    if exposure is not None:
        out["exposure"] = exposure * 100
    if trades is not None:
        pnl = np.array([t["pnl"] for t in trades]) if trades else np.array([0.0])
        win, loss = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
        out.update({"trades": len(trades), "winrate": (pnl > 0).mean() * 100 if trades else 0,
                    "pf": win / loss if loss > 0 else float("nan"),
                    "avgDays": float(np.mean([t["days"] for t in trades])) if trades else 0})
    return out


def yearly(eq: pd.Series) -> dict:
    eq = eq.dropna()
    ends = eq.groupby(eq.index.year).last()
    prev = eq.iloc[0]
    out = {}
    for y, v in ends.items():
        out[int(y)] = (v / prev - 1) * 100
        prev = v
    return out


# ── Strategien ──────────────────────────────────────────────────────────────────
def load_signals(m: Market) -> dict[int, list]:
    """4H-Signale je Ausführungstag (Index in m.dates)."""
    raw = json.loads(SIGNALS.read_text())["signals"]
    by_day: dict[int, list] = {}
    idx = {d: i for i, d in enumerate(m.dates.strftime("%Y-%m-%d"))}
    for sym, lst in raw.items():
        if sym not in m.c.columns:
            continue
        for sg in lst:
            i = idx.get(sg["entryDate"])
            if i is None:
                continue
            ex = None if sg["isOpen"] else (idx.get(sg["exitDate"]), sg["exitPrice"])
            if ex is not None and ex[0] is None:
                ex = None
            by_day.setdefault(i, []).append({**sg, "sym": sym, "fixed_exit": ex})
    return by_day


def keep_signal(seed: int | None, sym: str, day: str, share: float = 0.8) -> bool:
    """Robustheitstest: je Seed fällt derselbe zufällige Anteil der Signale weg (für alle Varianten gleich)."""
    if seed is None:
        return True
    h = int.from_bytes(hashlib.blake2b(f"{seed}|{sym}|{day}".encode(), digest_size=8).digest(), "big")
    return h / 2**64 < share


def gws_candidates(m: Market, sigs: dict, *, engine_exit: bool, regime: bool = False,
                   rank_by: str | None = None, min_trend: bool = False, seed: int | None = None):
    up = m.ind["qqq_up"].values
    rank = m.ind[rank_by].values if rank_by else None
    sma50, c = m.ind["sma50"].values, m.c.values
    col = {x: k for k, x in enumerate(m.c.columns)}

    def cand(i: int, held: set) -> list:
        out = []
        for sg in sigs.get(i, []):
            if not keep_signal(seed, sg["sym"], sg["entryDate"]):
                continue
            k = col[sg["sym"]]
            if regime and not up[i - 1]:
                continue
            if min_trend and not (c[i - 1, k] > sma50[i - 1, k]):
                continue
            pr = rank[i - 1, k] if rank is not None and not math.isnan(rank[i - 1, k]) else 0.0
            # gleicher Tag: frühere 4H-Kerze zuerst (wie live), dann Rang
            pr = pr - (10 if sg["entryTime"] > "14:00" else 0)
            out.append(Entry(sg["sym"], pr, sg["entryPrice"], sg["stopPrice"],
                             sg["fixed_exit"] if engine_exit else None, tag="gws"))
        return out
    return cand


def exit_rules(m: Market, *, stop=True, time_stop=(10, 0.05), chandelier=None, sma=None,
               low_n=None, leave_top=None, trail_pct=None, breakeven_r=None):
    c = m.c.values
    atr = m.ind["atr14"].values
    smav = m.ind[f"sma{sma}"].values if sma else None
    lows = m.ind[f"lo{low_n}"].values if low_n else None
    top = m.in_top.values
    col = {x: k for k, x in enumerate(m.c.columns)}

    def rule(p: Position, i: int) -> bool:
        k = col[p.sym]
        x = c[i, k]
        if breakeven_r and p.stop is not None and p.max_close >= p.entry_price + breakeven_r * (p.entry_price - p.stop):
            p.stop = max(p.stop, p.entry_price)
        if stop and p.stop is not None and x < p.stop:
            return True
        if trail_pct and x < p.max_close * (1 - trail_pct):
            return True
        if time_stop and i - p.entry_i == time_stop[0] and x < p.entry_price * (1 + time_stop[1]):
            return True
        if chandelier and not math.isnan(atr[i, k]) and x < p.max_close - chandelier * atr[i, k]:
            return True
        if smav is not None and not math.isnan(smav[i, k]) and x < smav[i, k] and i > p.entry_i:
            return True
        if lows is not None and not math.isnan(lows[i, k]) and x < lows[i, k]:
            return True
        if leave_top and i - leave_top >= p.entry_i and not top[i - leave_top + 1:i + 1, k].any():
            return True
        return False
    return rule


def rotation(m: Market, *, score="ret126", k_hold=10, buffer=15, every=5, regime=True, trend=True):
    """Momentum-Rotation: alle `every` Handelstage die stärksten Titel der Top 20 halten."""
    sc = m.ind[score].values
    sma50, c, top = m.ind["sma50"].values, m.c.values, m.in_top.values
    up = m.ind["qqq_up"].values
    syms = list(m.c.columns)
    state = {"keep": set(), "last": -99}

    def ranking(i: int) -> list:
        ok = [(sc[i, k], s) for k, s in enumerate(syms)
              if top[i, k] and not math.isnan(sc[i, k]) and (not trend or c[i, k] > sma50[i, k])]
        return [s for _, s in sorted(ok, reverse=True)]

    def cand(i: int, held: set) -> list:
        j = i - 1
        if j - state["last"] < every:
            return []
        state["last"] = j
        if regime and not up[j]:
            state["keep"] = set()
            return []
        rk = ranking(j)
        state["keep"] = set(rk[:buffer])
        return [Entry(s, -n) for n, s in enumerate(rk[:k_hold])]

    def rule(p: Position, i: int) -> bool:
        k = syms.index(p.sym)
        if regime and not up[i]:
            return True
        if (i + 1) - state["last"] >= every:       # morgen wird neu sortiert
            rk = ranking(i)
            return p.sym not in set(rk[:buffer])
        return False
    return cand, rule


def rsi2_pullback(m: Market, *, entry_rsi=10, regime=True, max_days=10):
    """Pullback-Swing (Connors): starke Titel im Aufwärtstrend nach kurzem Rücksetzer kaufen."""
    rsi, sma200, sma5 = m.ind["rsi2"].values, m.ind["sma200"].values, m.ind["sma5"].values
    c, top, up = m.c.values, m.in_top.values, m.ind["qqq_up"].values
    syms = list(m.c.columns)

    def cand(i: int, held: set) -> list:
        j = i - 1
        if regime and not up[j]:
            return []
        return [Entry(s, -rsi[j, k]) for k, s in enumerate(syms)
                if top[j, k] and c[j, k] > sma200[j, k] and rsi[j, k] < entry_rsi]

    def rule(p: Position, i: int) -> bool:
        k = syms.index(p.sym)
        return c[i, k] > sma5[i, k] or i - p.entry_i >= max_days
    return cand, rule


def donchian(m: Market, *, regime=True, trail=3.0):
    """Trendfolge: Schluss über dem 50-Tage-Hoch, Ausstieg per ATR-Trailing-Stopp."""
    hi, c, top, up = m.ind["hi50"].values, m.c.values, m.in_top.values, m.ind["qqq_up"].values
    atr, ret = m.ind["atr14"].values, m.ind["ret126"].values
    syms = list(m.c.columns)

    def cand(i: int, held: set) -> list:
        j = i - 1
        if regime and not up[j]:
            return []
        out = []
        for k, s in enumerate(syms):
            if top[j, k] and c[j, k] > hi[j, k] and not (c[j - 1, k] > hi[j - 1, k]):
                out.append(Entry(s, ret[j, k] if not math.isnan(ret[j, k]) else 0, None, c[j, k] - 2 * atr[j, k]))
        return out
    return cand, exit_rules(m, stop=True, time_stop=None, chandelier=trail)


def qqq_strategies(m: Market, start: str, end: str) -> dict:
    q = m.qqq.loc[start:end]
    bh = q["c"] / q["c"].iloc[0] * START_CAPITAL
    up = m.ind["qqq_up"].loc[start:end].shift(1).fillna(False).astype(bool)
    r = q["c"].pct_change().fillna(0)
    switch = up.astype(int).diff().abs().fillna(0)
    timed = START_CAPITAL * (1 + r * up - switch * COST).cumprod()
    return {"QQQ Buy & Hold": bh, "QQQ 200-Tage-Timing": timed}


def combined(gws_cand, gws_rule, rsi_cand, rsi_rule):
    """Breakout-Depot, dessen freie Plätze ein Pullback-Swing (RSI-2) nutzt — Breakouts haben Vorrang."""
    def cand(i: int, held: set) -> list:
        out = gws_cand(i, held)
        for e in out:
            e.priority += 1000
        return out + [Entry(e.sym, e.priority, e.price, e.stop, e.fixed_exit, tag="rsi2") for e in rsi_cand(i, held)]

    def rule(p: Position, i: int) -> bool:
        return rsi_rule(p, i) if p.tag == "rsi2" else gws_rule(p, i)
    return cand, rule


# ── Lauf ────────────────────────────────────────────────────────────────────────
# Kernvarianten für den Robustheitstest (Kurzname → Name in der Haupttabelle)
KEY = ["A1", "A2", "B1", "C2", "C5", "C10", "C13", "C16", "C18", "F1", "F2"]


def build_strategies(m: Market, sigs: dict, seed: int | None = None) -> list[tuple[str, str, Strategy]]:
    S = []
    add = lambda grp, st: S.append((grp, st.name, st))
    gws = lambda **kw: gws_candidates(m, sigs, seed=seed, **kw)
    # A — heutige Plattform
    add("A Heute", Strategy("A1 Plattform heute (1 % Risiko je Trade)", gws(engine_exit=True), sizing="risk"))
    add("A Heute", Strategy("A2 wie A1, volle 10 %-Slots", gws(engine_exit=True)))
    # B — Marktphase / Auswahl (Ausstieg wie heute)
    add("B Filter", Strategy("B1 A2 + nur Käufe bei QQQ > 200T", gws(engine_exit=True, regime=True)))
    add("B Filter", Strategy("B2 A2 + Vorrang stärkstes 6M-Momentum", gws(engine_exit=True, rank_by="ret126")))
    add("B Filter", Strategy("B3 A2 + Kauf nur über 50-Tage-Linie", gws(engine_exit=True, min_trend=True)))
    # C — Ausstiege (Einstieg = heutige 4H-Signale, Anfangsstopp wie heute: Swing-Tief − 1 %)
    c_in = gws(engine_exit=False)
    X = lambda **kw: exit_rules(m, **kw)
    add("C Ausstieg", Strategy("C1 Stopp + Zeitstopp 10T/+5 % (ohne Strukturbruch)", c_in, X()))
    add("C Ausstieg", Strategy("C2 Stopp + Chandelier 3×ATR", c_in, X(time_stop=None, chandelier=3)))
    add("C Ausstieg", Strategy("C3 Stopp + Zeitstopp + Chandelier 3×ATR", c_in, X(chandelier=3)))
    add("C Ausstieg", Strategy("C4 Stopp + Schluss < 20-Tage-Linie", c_in, X(time_stop=None, sma=20)))
    add("C Ausstieg", Strategy("C5 Stopp + Schluss < 50-Tage-Linie", c_in, X(time_stop=None, sma=50)))
    add("C Ausstieg", Strategy("C6 Stopp + 20-Tage-Tief (Turtle)", c_in, X(time_stop=None, low_n=20)))
    add("C Ausstieg", Strategy("C7 Stopp + Chandelier 3×ATR + Top-20-Austritt 10T", c_in, X(time_stop=None, chandelier=3, leave_top=10)))
    add("C Ausstieg", Strategy("C8 Stopp + Zeitstopp + Chandelier 4×ATR", c_in, X(chandelier=4)))
    add("C Ausstieg", Strategy("C9 Stopp + Chandelier 4×ATR", c_in, X(time_stop=None, chandelier=4)))
    add("C Ausstieg", Strategy("C10 Stopp + Chandelier 5×ATR", c_in, X(time_stop=None, chandelier=5)))
    add("C Ausstieg", Strategy("C11 Stopp + Zeitstopp + Chandelier 6×ATR", c_in, X(chandelier=6)))
    add("C Ausstieg", Strategy("C12 Stopp + Zeitstopp + Schluss < 100T", c_in, X(sma=100)))
    add("C Ausstieg", Strategy("C13 Stopp + Zeitstopp + 20 % unter Hoch", c_in, X(trail_pct=0.20)))
    add("C Ausstieg", Strategy("C14 Stopp + Zeitstopp + 25 % unter Hoch", c_in, X(trail_pct=0.25)))
    add("C Ausstieg", Strategy("C15 Stopp (Einstand ab +2R) + Zeitstopp + 20 % unter Hoch", c_in, X(trail_pct=0.20, breakeven_r=2)))
    add("C Ausstieg", Strategy("C16 Stopp + 20 % unter Hoch", c_in, X(time_stop=None, trail_pct=0.20)))
    add("C Ausstieg", Strategy("C17 Stopp + 15 % unter Hoch", c_in, X(time_stop=None, trail_pct=0.15)))
    add("C Ausstieg", Strategy("C18 Stopp + Zeitstopp 10T/0 % + 20 % unter Hoch", c_in, X(time_stop=(10, 0.0), trail_pct=0.20)))
    add("C Ausstieg", Strategy("C19 C16 + nur Käufe bei QQQ > 200T", gws(engine_exit=False, regime=True), X(time_stop=None, trail_pct=0.20)))
    # E — freies Cash nutzen
    add("E Cash", Strategy("E1 A2 + freies Cash im QQQ", gws(engine_exit=True), cash_in_qqq=True))
    add("E Cash", Strategy("E2 C16 + freies Cash im QQQ", c_in, X(time_stop=None, trail_pct=0.20), cash_in_qqq=True))
    # F — Kombination Breakout + Pullback-Swing in einem Depot
    rc, rr = rsi2_pullback(m)
    cand, rule = combined(gws(engine_exit=True), lambda p, i: False, rc, rr)
    add("F Kombi", Strategy("F1 A2 + RSI(2)-Pullbacks auf freien Plätzen", cand, rule))
    rc, rr = rsi2_pullback(m)
    cand, rule = combined(c_in, X(time_stop=None, trail_pct=0.20), rc, rr)
    add("F Kombi", Strategy("F2 C16 + RSI(2)-Pullbacks auf freien Plätzen", cand, rule))
    # D — alternative Ansätze (ohne 4H-Signale)
    cand, rule = rotation(m)
    add("D Alternativ", Strategy("D1 Momentum-Rotation wöchentlich (Top 10 nach 6M, 200T)", cand, rule))
    cand, rule = rotation(m, every=21)
    add("D Alternativ", Strategy("D2 Momentum-Rotation monatlich", cand, rule))
    cand, rule = rotation(m, k_hold=5, buffer=8)
    add("D Alternativ", Strategy("D3 Momentum-Rotation konzentriert (5 Titel)", cand, rule, max_positions=5))
    cand, rule = rotation(m, score="ret252_21")
    add("D Alternativ", Strategy("D4 Momentum-Rotation 12-1-Monate", cand, rule))
    cand, rule = rsi2_pullback(m)
    add("D Alternativ", Strategy("D5 Pullback-Swing RSI(2) < 10", cand, rule))
    cand, rule = donchian(m)
    add("D Alternativ", Strategy("D6 Donchian-50-Breakout + 3×ATR-Trailing", cand, rule))
    return S


def short(name: str) -> str:
    return name.split(" ", 1)[0]


def robustness(m: Market, sigs: dict, seeds: int = 30) -> dict:
    """Je Seed fallen 20 % der 4H-Signale weg (für alle Varianten dieselben) — Ergebnis
    gepaart gegen A2: Wie oft ist die Variante besser (Sharpe/CAGR), Median und Spanne?"""
    out = {}
    for pname in ("2016–2021 (Training)", "2022–2026 (Test)"):
        a, z = PERIODS[pname]
        per = {}
        for sd in range(seeds):
            for grp, name, st in build_strategies(m, sigs, seed=sd):
                if short(name) not in KEY:
                    continue
                r = metrics(simulate(m, st, a, z)["equity"])
                per.setdefault(short(name), []).append(r)
        base = per["A2"]
        rows = {}
        for k, lst in per.items():
            cg = np.array([x["cagr"] for x in lst]); sh = np.array([x["sharpe"] for x in lst])
            dd = np.array([x["maxDD"] for x in lst])
            rows[k] = {"cagr_med": float(np.median(cg)), "cagr_p10": float(np.percentile(cg, 10)),
                       "cagr_p90": float(np.percentile(cg, 90)), "sharpe_med": float(np.median(sh)),
                       "maxdd_med": float(np.median(dd)),
                       "beats_a2_sharpe": float(np.mean(sh > np.array([x["sharpe"] for x in base])) * 100),
                       "beats_a2_cagr": float(np.mean(cg > np.array([x["cagr"] for x in base])) * 100)}
        out[pname] = rows
    return out


def cost_sensitivity(m: Market, sigs: dict) -> dict:
    a, z = PERIODS["2016–2026"]
    out = {}
    for grp, name, st in build_strategies(m, sigs):
        if short(name) in ("A1", "A2", "C16", "F2", "D5"):
            out[name] = {f"{fee * 100:.2f}": metrics(simulate(m, st, a, z, fee=fee)["equity"])["cagr"]
                         for fee in (0.0, 0.001, 0.0025)}
    return out


def run() -> dict:
    m = load_market()
    sigs = load_signals(m)
    result = {"periods": {}, "yearly": {}, "meta": {"cost_per_side": COST, "max_positions": MAX_POSITIONS,
                                                   "data_end": str(m.dates[-1].date())}}
    for pname, (a, z) in PERIODS.items():
        rows = []
        for name, eq in qqq_strategies(m, a, z).items():
            rows.append({"group": "Benchmark", "name": name, **metrics(eq)})
            if pname == "2016–2026":
                result["yearly"][name] = yearly(eq)
        for grp, name, st in build_strategies(m, sigs):
            res = simulate(m, st, a, z)
            rows.append({"group": grp, "name": name, **metrics(res["equity"], res["trades"], res["exposure"])})
            if pname == "2016–2026":
                result["yearly"][name] = yearly(res["equity"])
        result["periods"][pname] = rows
    # Tages-Ansätze auch 2008–2015 (Finanzkrise; 4H-Kerzen erst ab 2016)
    rows = [{"group": "Benchmark", "name": n, **metrics(eq)} for n, eq in qqq_strategies(m, "2008-01-01", "2015-12-31").items()]
    for grp, name, st in build_strategies(m, sigs):
        if grp == "D Alternativ":
            res = simulate(m, st, "2008-01-01", "2015-12-31")
            rows.append({"group": grp, "name": name, **metrics(res["equity"], res["trades"], res["exposure"])})
    result["periods"]["2008–2015 (nur Tagesdaten)"] = rows
    result["robustness"] = robustness(m, sigs)
    result["costs"] = cost_sensitivity(m, sigs)
    return result


def fmt(v, d=1):
    return "–" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{d}f}".replace(".", ",")


def print_tables(res: dict) -> None:
    for pname, rows in res["periods"].items():
        print(f"\n### {pname}\n")
        print("| Ansatz | CAGR | Max-DD | Sharpe | Calmar | PF | Trades | Trefferquote | Ø Tage | Investiert |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            print(f"| {r['name']} | {fmt(r['cagr'])} % | {fmt(r['maxDD'])} % | {fmt(r['sharpe'], 2)} | {fmt(r['calmar'], 2)} | "
                  f"{fmt(r.get('pf'), 2)} | {r.get('trades', '–')} | {fmt(r.get('winrate'))} % | {fmt(r.get('avgDays'), 0)} | {fmt(r.get('exposure'), 0)} % |")
    for pname, rows in res["robustness"].items():
        print(f"\n### Robustheit {pname} (30 Läufe, je 20 % Signale zufällig ausgelassen)\n")
        print("| Variante | CAGR Median | CAGR 10–90 % | Sharpe Median | Max-DD Median | besser als A2 (Sharpe) | besser als A2 (CAGR) |")
        print("|---|---|---|---|---|---|---|")
        for k, r in rows.items():
            print(f"| {k} | {fmt(r['cagr_med'])} % | {fmt(r['cagr_p10'])} … {fmt(r['cagr_p90'])} % | {fmt(r['sharpe_med'], 2)} | "
                  f"{fmt(r['maxdd_med'])} % | {fmt(r['beats_a2_sharpe'], 0)} % | {fmt(r['beats_a2_cagr'], 0)} % |")
    print("\n### Kosten je Seite → CAGR 2016–2026\n")
    print("| Variante | 0 % | 0,1 % | 0,25 % |\n|---|---|---|---|")
    for name, v in res["costs"].items():
        print(f"| {name} | " + " | ".join(f"{fmt(x)} %" for x in v.values()) + " |")


if __name__ == "__main__":
    res = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=float))
    print_tables(res)
    print(f"\n→ {OUT}")
