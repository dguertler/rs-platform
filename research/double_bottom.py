"""Studie 10/2026 — Kauf am Doppelboden (statt am Breakout).

Sucht in allen Tageskursen seit 2016 Doppelböden und simuliert jeden Einstieg
mit den Ausstiegen der Engine (Stopp, Strukturbruch, Zeitstopp 10 Tage/+5 %).
Kein Vorgriff: Ein Tief zählt erst als Swing-Tief, wenn zwei Folgetage es nicht
unterschritten haben; gekauft wird zur nächsten Eröffnung.

Doppelboden (Tageskerzen, Swing-Punkte ±2 Tage wie GWS-D):
  - Vorlauf: Hoch der 60 Tage vor Tief 1 mindestens MIN_DECLINE über Tief 1
  - Tief 1 und Tief 2: Swing-Tiefs, MIN_SEP–MAX_SEP Handelstage auseinander,
    Tief 2 höchstens TOL über/unter Tief 1, dazwischen kein tieferes Tief
  - Nackenlinie: höchstes Hoch zwischen den Tiefs, mindestens MIN_BOUNCE über Tief 1
Auslöser (je Muster zwei Zeilen):
  - "frueh":   Tief 2 bestätigt (2 Tage ohne neues Tief) → Kauf nächste Eröffnung
  - "nacken":  erster Schluss über der Nackenlinie (≤ 40 Tage nach Tief 2,
               ohne neues Tief davor) → Kauf nächste Eröffnung
Stopp: tieferes der beiden Tiefs × 0,99.

Universen:
  - NDX: data/backtest_history/charts (182 Titel inkl. ausgeschiedener), 2016–2026,
         Spalte in_top20 = Titel am Signaltag in den RS-Top-20
  - SPX: übrige data/backtest_*.json (Kurse ab 10/2022) — eigene Stichprobe ab 2023

Aufruf: python3 research/double_bottom.py  → research/data/double_bottom.csv
"""
from __future__ import annotations

import bisect
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CHARTS = ROOT / "data" / "backtest_history" / "charts"
OUT = ROOT / "research" / "data" / "double_bottom.csv"
START = "2016-01-01"

MIN_DECLINE = 0.08
MIN_SEP, MAX_SEP = 8, 80
TOL = 0.05
MIN_BOUNCE = 0.04
NECK_WINDOW = 40
TIME_STOP_DAYS, TIME_STOP_MIN = 10, 0.05


def series_from(ticker: str) -> tuple[str, dict] | None:
    rows, universe = [], "SPX"
    f = CHARTS / f"{ticker}.json"
    top = []
    if f.exists():
        ch = json.loads(f.read_text())
        rows = [tuple(r[:5]) for r in ch["d"]]
        top = (ch.get("top20") or {}).get("inkl", [])
        universe = "NDX"
    g = ROOT / "data" / f"backtest_{ticker.lower()}.json"
    if g.exists():
        extra = [(b["d"], b["o"], b["h"], b["l"], b["c"]) for b in json.loads(g.read_text()).get("ohlcv_d", [])]
        last = rows[-1][0] if rows else ""
        rows += [r for r in extra if r[0] > last]
    if len(rows) < 260:
        return None
    D = np.array([r[0] for r in rows])
    O, H, L, C = (np.array([r[i] for r in rows], float) for i in (1, 2, 3, 4))
    return universe, dict(D=D, O=O, H=H, L=L, C=C, top=top)


def swings(H, L):
    n = len(H)
    sh = [i for i in range(2, n - 2) if H[i] >= max(H[i-2], H[i-1], H[i+1], H[i+2])]
    sl = [i for i in range(2, n - 2) if L[i] <= min(L[i-2], L[i-1], L[i+1], L[i+2])]
    return sh, sl


def gwsd_lastc(H, L, C, sh, sl):
    """Für den Strukturausstieg der Engine: letzte GWS-D-Marke je Swing-Tief-Zahl."""
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
    for m in range(1, len(sl) + 1):
        if cand[m-1] is not None:
            cur = cand[m-1]
        lastc[m] = cur
    return lastc


def simulate(o, idx, ep, stop):
    """Ausstieg wie Engine: Zeitstopp, Strukturbruch (GWS-D intakt + Schluss < letztes
    Swing-Tief), Schluss < Stopp — Signal zum Schluss, Ausführung nächste Eröffnung."""
    C, O, L, sl, lastc = o["C"], o["O"], o["L"], o["sl"], o["lastc"]
    n = len(C)
    for k in range(idx, n):
        j = k - idx
        reason = None
        if j == TIME_STOP_DAYS and C[k] < ep * (1 + TIME_STOP_MIN):
            reason = "zeitstopp"
        else:
            m = bisect.bisect_right(sl, k - 3)
            lvl = None
            if m:
                c = lastc[m]
                if not (c is not None and c[2] <= k - 1):
                    lvl = L[sl[m-1]]
            if lvl is not None and C[k] < lvl:
                reason = "struktur"
            elif C[k] < stop:
                reason = "stopp"
        if reason:
            if k + 1 < n:
                return k + 1, O[k+1], reason, False
            return k, C[k], reason, False
    return n - 1, C[-1], "offen", True


def rsi(C, n=14):
    d = np.diff(C, prepend=C[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1/n, adjust=False).mean()
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1/n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).fillna(50).values


def in_intervals(day, iv):
    return any(a <= day <= z for a, z in iv)


def bench():
    d = json.loads((CHARTS / "_benchmark.json").read_text())["d"]
    q = pd.DataFrame(d, columns=["d", "o", "h", "l", "c"]).set_index("d")
    c = q["c"]
    return dict(
        c=c, sma200=c.rolling(200).mean(), sma50=c.rolling(50).mean(),
        ret63=c / c.shift(63) - 1, ath=q["h"].cummax(),
    )


def scan(ticker, universe, s, Q):
    D, O, H, L, C = s["D"], s["O"], s["H"], s["L"], s["C"]
    n = len(C)
    sh, sl = swings(H, L)
    o = dict(C=C, O=O, L=L, sl=sl, lastc=gwsd_lastc(H, L, C, sh, sl))
    tr = np.maximum(H[1:] - L[1:], np.maximum(abs(H[1:] - C[:-1]), abs(L[1:] - C[:-1])))
    atr = pd.Series(np.concatenate([[H[0] - L[0]], tr])).rolling(14).mean().values
    sma50 = pd.Series(C).rolling(50).mean().values
    sma200 = pd.Series(C).rolling(200).mean().values
    rs = rsi(C)
    cummax_h = np.maximum.accumulate(H)
    rows, busy_until = [], {"frueh": "", "nacken": ""}
    sl_set = sl
    for jb, b in enumerate(sl_set):
        if D[b] < START or b + 3 >= n:
            continue
        # Tief 1 suchen: jüngstes passendes Swing-Tief davor
        best = None
        for ja in range(jb - 1, -1, -1):
            a = sl_set[ja]
            sep = b - a
            if sep < MIN_SEP:
                continue
            if sep > MAX_SEP:
                break
            if abs(L[b] / L[a] - 1) > TOL:
                continue
            lo_between = L[a+1:b].min()
            if lo_between < min(L[a], L[b]):
                continue
            neck_i = a + 1 + int(np.argmax(H[a+1:b]))
            neck = H[neck_i]
            if neck < L[a] * (1 + MIN_BOUNCE):
                continue
            pre_hi = H[max(0, a - 60):a].max() if a > 0 else 0
            if pre_hi < L[a] * (1 + MIN_DECLINE):
                continue
            best = (a, neck_i, neck, pre_hi)
            break
        if best is None:
            continue
        a, neck_i, neck, pre_hi = best
        low = min(L[a], L[b])
        stop = low * 0.99
        cb = b + 2  # Bestätigung des 2. Tiefs (Schluss dieses Tages)
        triggers = [("frueh", cb)]
        for k in range(cb, min(n - 1, b + NECK_WINDOW)):
            if L[k] < low:
                break
            if C[k] > neck:
                triggers.append(("nacken", k))
                break
        for trig, sig in triggers:
            e = sig + 1
            if e >= n or D[sig] <= busy_until[trig]:
                continue
            ep = O[e]
            if ep <= stop:
                continue
            xi, xp, reason, is_open = simulate(o, e, ep, stop)
            busy_until[trig] = D[xi]
            day = D[sig]
            seg = slice(e, xi + 1)
            qd = Q["c"].index.searchsorted(day, side="right") - 1
            qday = Q["c"].index[qd] if qd >= 0 else None
            rows.append(dict(
                universe=universe, ticker=ticker, trigger=trig,
                low1_date=D[a], low2_date=D[b], signal_date=day, entry_date=D[e],
                exit_date=D[xi], entry=round(ep, 4), stop=round(stop, 4), exit=round(xp, 4),
                exit_reason=reason, is_open=int(is_open), hold_days=int(xi - e),
                pnl_pct=round((xp / ep - 1) * 100, 2), win=int(xp > ep),
                r_multiple=round((xp - ep) / (ep - stop), 2),
                mfe_pct=round((H[seg].max() / ep - 1) * 100, 2), mae_pct=round((L[seg].min() / ep - 1) * 100, 2),
                # Muster
                decline_pct=round((L[a] / pre_hi - 1) * 100, 2),
                bounce_pct=round((neck / L[a] - 1) * 100, 2),
                low2_vs_low1_pct=round((L[b] / L[a] - 1) * 100, 2),
                sep_days=int(b - a), days_low2_to_signal=int(sig - b),
                neck_dist_pct=round((neck / ep - 1) * 100, 2),
                stop_dist_pct=round((ep / stop - 1) * 100, 2),
                low2_close_pos=round((C[b] - L[b]) / (H[b] - L[b]), 2) if H[b] > L[b] else 0.5,
                low2_green=int(C[b] > O[b]),
                rsi_low1=round(rs[a], 1), rsi_low2=round(rs[b], 1),
                rsi_divergence=int(rs[b] > rs[a]),
                # Trend/Lage beim Signal
                atr_pct=round(atr[sig] / C[sig] * 100, 2),
                above_sma200=int(C[sig] > sma200[sig]) if sma200[sig] == sma200[sig] else -1,
                above_sma50=int(C[sig] > sma50[sig]) if sma50[sig] == sma50[sig] else -1,
                sma200_rising=int(sma200[sig] > sma200[sig - 20]) if sig >= 220 else -1,
                low_vs_sma200_pct=round((low / sma200[b] - 1) * 100, 2) if sma200[b] == sma200[b] else np.nan,
                dist_ath_pct=round((ep / cummax_h[sig] - 1) * 100, 2),
                ret126_pct=round((C[sig] / C[sig - 126] - 1) * 100, 2) if sig >= 126 else np.nan,
                in_top20=int(in_intervals(day, s["top"])) if universe == "NDX" else -1,
                # Markt
                qqq_above_sma200=int(Q["c"].iloc[qd] > Q["sma200"].iloc[qd]) if qday else -1,
                qqq_above_sma50=int(Q["c"].iloc[qd] > Q["sma50"].iloc[qd]) if qday else -1,
                qqq_ret63_pct=round(Q["ret63"].iloc[qd] * 100, 2) if qday else np.nan,
                qqq_dist_ath_pct=round((Q["c"].iloc[qd] / Q["ath"].iloc[qd] - 1) * 100, 2) if qday else np.nan,
            ))
    return rows


def main():
    Q = bench()
    tickers = {p.stem for p in CHARTS.glob("*.json") if not p.stem.startswith("_")}
    tickers |= {p.stem[len("backtest_"):].upper() for p in (ROOT / "data").glob("backtest_*.json")
                if p.stem not in ("backtest_ndx",)}
    rows = []
    for tk in sorted(tickers):
        got = series_from(tk)
        if got is None:
            continue
        rows += scan(tk, got[0], got[1], Q)
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"{len(df)} Doppelboden-Trades aus {df.ticker.nunique()} Titeln → {OUT.relative_to(ROOT)}")
    closed = df[df.is_open == 0]
    for (u, t), g in closed.groupby(["universe", "trigger"]):
        pf = g.pnl_pct[g.pnl_pct > 0].sum() / -g.pnl_pct[g.pnl_pct < 0].sum()
        print(f"{u} {t:7s} n={len(g):5d}  Trefferquote {g.win.mean()*100:5.1f} %  Ø {g.pnl_pct.mean():+.2f} %  PF {pf:.2f}")


if __name__ == "__main__":
    main()
