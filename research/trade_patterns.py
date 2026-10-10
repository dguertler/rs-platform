"""Studie 10/2026 — Was unterscheidet Gewinner- von Verlust-Trades?

Berechnet für jeden Trade aus `data/backtest_ndx.json` (zeitpunktgenauer
4H-Breakout-Backtest 2016–2026) und `data/live_alerts_performance.json`
(verschickte Live-Alerts seit 04/2026) die Chartlage zum Einstieg — nur mit
Kursen VOR dem Einstiegstag (kein Vorgriff) — und schreibt eine Merkmalstabelle:

    research/data/trade_features.csv        (Backtest)
    research/data/trade_features_live.csv   (Live-Alerts)

Aufruf: python3 research/trade_patterns.py
Auswertung/Bericht: research/TRADE_PATTERNS.md
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CHARTS = ROOT / "data" / "backtest_history" / "charts"
OUT = ROOT / "research" / "data"


def load_daily(ticker: str) -> pd.DataFrame | None:
    """Tageskerzen: historischer Lauf (charts/) + tägliche backtest_TICKER.json."""
    frames = []
    f = CHARTS / f"{ticker}.json"
    if f.exists():
        d = json.loads(f.read_text())["d"]
        frames.append(pd.DataFrame(d, columns=["d", "o", "h", "l", "c"]))
    g = ROOT / "data" / f"backtest_{ticker.lower()}.json"
    if g.exists():
        d = json.loads(g.read_text()).get("ohlcv_d") or []
        if d:
            frames.append(pd.DataFrame(d)[["d", "o", "h", "l", "c"]])
    if not frames:
        return None
    df = pd.concat(frames).drop_duplicates("d", keep="last").sort_values("d")
    df["d"] = pd.to_datetime(df["d"])
    return df.set_index("d").astype(float)


def load_bench() -> pd.DataFrame:
    d = json.loads((CHARTS / "_benchmark.json").read_text())["d"]
    df = pd.DataFrame(d, columns=["d", "o", "h", "l", "c"])
    df["d"] = pd.to_datetime(df["d"])
    return df.set_index("d").astype(float)


def sma(s: pd.Series, n: int) -> float:
    return float(s.iloc[-n:].mean()) if len(s) >= n else np.nan


def atr_pct(h: pd.DataFrame, n: int = 14) -> float:
    if len(h) < n + 1:
        return np.nan
    pc = h["c"].shift(1)
    tr = pd.concat([h["h"] - h["l"], (h["h"] - pc).abs(), (h["l"] - pc).abs()], axis=1).max(axis=1)
    return float(tr.iloc[-n:].mean() / h["c"].iloc[-1] * 100)


def weekly_swing_trend(h: pd.DataFrame) -> tuple[str, float]:
    """Trend der Wochenkerzen aus den letzten zwei Swing-Hochs (±1 Woche, wie GWS-W).
    Zweiter Wert: Abstand des letzten Swing-Hochs zum vorletzten in %."""
    w = h.resample("W-FRI").agg({"h": "max", "l": "min", "c": "last"}).dropna().iloc[-60:]
    hi = w["h"].values
    sh = [hi[i] for i in range(1, len(hi) - 1) if hi[i] >= hi[i - 1] and hi[i] >= hi[i + 1]]
    if len(sh) < 2:
        return "neutral", np.nan
    diff = (sh[-1] / sh[-2] - 1) * 100
    return ("bullish" if sh[-1] > sh[-2] else "bearish" if sh[-1] < sh[-2] else "neutral"), diff


def correction_stats(h: pd.DataFrame, entry: float, lookback: int) -> dict:
    """Letzte Korrektur im Fenster: Hoch → tiefster Punkt danach → Einstieg."""
    win = h.iloc[-lookback:]
    if len(win) < 10:
        return {}
    peak_idx = win["h"].idxmax()
    peak = float(win.loc[peak_idx, "h"])
    after = win.loc[peak_idx:]
    trough = float(after["l"].min())
    depth = (trough / peak - 1) * 100
    rng = peak - trough
    recovery = (entry - trough) / rng if rng > 0 else np.nan
    return {
        f"corr{lookback}_depth": round(depth, 2),
        f"corr{lookback}_recovery": round(recovery, 3) if recovery == recovery else np.nan,
        f"corr{lookback}_days_since_peak": int(len(after) - 1),
    }


def features(h: pd.DataFrame, entry_date: pd.Timestamp, entry: float, stop: float,
             bench: pd.DataFrame) -> dict | None:
    hist = h[h.index < entry_date]
    if len(hist) < 60:
        return None
    c = hist["c"]
    prev_close = float(c.iloc[-1])
    ath = float(hist["h"].max())
    ath_day = hist["h"].idxmax()
    hi252 = float(hist["h"].iloc[-252:].max())
    lo252 = float(hist["l"].iloc[-252:].min())
    s20, s50, s200 = sma(c, 20), sma(c, 50), sma(c, 200)
    s50_prev = float(c.iloc[-70:-20].mean()) if len(c) >= 70 else np.nan
    s200_prev = float(c.iloc[-220:-20].mean()) if len(c) >= 220 else np.nan
    wtrend, wdiff = weekly_swing_trend(hist)
    years = (hist.index[-1] - hist.index[0]).days / 365.25

    f = {
        "hist_years": round(years, 1),
        "dist_ath_pct": round((entry / ath - 1) * 100, 2),
        "at_ath": int(entry >= ath),
        "near_ath5": int(entry >= ath * 0.95),
        "days_since_ath": int((hist.index >= ath_day).sum() - 1),
        "dist_52w_pct": round((entry / hi252 - 1) * 100, 2),
        "pos_52w_range": round((entry - lo252) / (hi252 - lo252), 3) if hi252 > lo252 else np.nan,
        "ext_sma20_pct": round((entry / s20 - 1) * 100, 2),
        "ext_sma50_pct": round((entry / s50 - 1) * 100, 2),
        "ext_sma200_pct": round((entry / s200 - 1) * 100, 2) if s200 == s200 else np.nan,
        "sma50_gt_sma200": int(s50 > s200) if s200 == s200 else np.nan,
        "sma50_slope20_pct": round((s50 / s50_prev - 1) * 100, 2) if s50_prev == s50_prev else np.nan,
        "sma200_slope20_pct": round((s200 / s200_prev - 1) * 100, 2) if s200_prev == s200_prev else np.nan,
        "ret5_pct": round((prev_close / float(c.iloc[-6]) - 1) * 100, 2),
        "ret20_pct": round((prev_close / float(c.iloc[-21]) - 1) * 100, 2),
        "ret63_pct": round((prev_close / float(c.iloc[-64]) - 1) * 100, 2) if len(c) > 64 else np.nan,
        "ret126_pct": round((prev_close / float(c.iloc[-127]) - 1) * 100, 2) if len(c) > 127 else np.nan,
        "gap_entry_pct": round((entry / prev_close - 1) * 100, 2),
        "atr14_pct": round(atr_pct(hist), 2),
        "stop_dist_pct": round((entry / stop - 1) * 100, 2),
        "weekly_trend": wtrend,
        "weekly_last_sh_vs_prev_pct": round(wdiff, 2) if wdiff == wdiff else np.nan,
    }
    f["stop_dist_atr"] = round(f["stop_dist_pct"] / f["atr14_pct"], 2) if f["atr14_pct"] else np.nan
    for lb in (63, 126):
        f.update(correction_stats(hist, entry, lb))

    b = bench[bench.index < entry_date]
    bc = b["c"]
    bs200, bs50 = sma(bc, 200), sma(bc, 50)
    f.update({
        "qqq_above_sma200": int(float(bc.iloc[-1]) > bs200),
        "qqq_above_sma50": int(float(bc.iloc[-1]) > bs50),
        "qqq_dist_ath_pct": round((float(bc.iloc[-1]) / float(b["h"].max()) - 1) * 100, 2),
        "qqq_ret20_pct": round((float(bc.iloc[-1]) / float(bc.iloc[-21]) - 1) * 100, 2),
        "qqq_ret63_pct": round((float(bc.iloc[-1]) / float(bc.iloc[-64]) - 1) * 100, 2),
        "rs63_vs_qqq_pct": round(((prev_close / float(c.iloc[-64])) / (float(bc.iloc[-1]) / float(bc.iloc[-64])) - 1) * 100, 2)
        if len(c) > 64 else np.nan,
    })
    return f


def trade_outcome(h: pd.DataFrame, t: dict) -> dict:
    """R-Vielfaches, Haltedauer, MFE/MAE und Ausstiegsgrund-Näherung."""
    e, s, x = t["entryPrice"], t["stopPrice"], t["exitPrice"]
    risk = e - s
    seg = h[(h.index >= pd.Timestamp(t["entryDate"])) & (h.index <= pd.Timestamp(t["exitDate"]))]
    days = max(len(seg) - 1, 0)
    mfe = (float(seg["h"].max()) / e - 1) * 100 if len(seg) else np.nan
    mae = (float(seg["l"].min()) / e - 1) * 100 if len(seg) else np.nan
    if t.get("isOpen"):
        reason = "offen"
    elif 10 <= days <= 12 and x < e * 1.05 and x > s:
        reason = "zeitstopp"
    elif x <= s * 1.005 or (len(seg) > 1 and float(seg["c"].iloc[:-1].min()) < s):
        reason = "stopp"
    else:
        reason = "struktur"
    # Kam nach dem Einstieg ein neues Allzeithoch?
    prior_ath = float(h[h.index < pd.Timestamp(t["entryDate"])]["h"].max())
    new_ath_in_trade = int(len(seg) > 0 and float(seg["h"].max()) > prior_ath)
    return {
        "r_multiple": round((x - e) / risk, 2) if risk > 0 else np.nan,
        "hold_days": days,
        "mfe_pct": round(mfe, 2),
        "mae_pct": round(mae, 2),
        "exit_reason": reason,
        "new_ath_in_trade": new_ath_in_trade,
    }


def build(trades: list[dict], bench: pd.DataFrame, kind: str) -> list[dict]:
    cache: dict[str, pd.DataFrame | None] = {}
    by_ticker_prev: dict[str, dict] = {}
    rows = []
    for t in sorted(trades, key=lambda z: (z["entryDate"], z["ticker"])):
        tk = t["ticker"]
        if tk not in cache:
            cache[tk] = load_daily(tk)
        h = cache[tk]
        if h is None:
            continue
        ed = pd.Timestamp(t["entryDate"])
        f = features(h, ed, t["entryPrice"], t["stopPrice"], bench)
        if f is None:
            continue
        prev = by_ticker_prev.get(tk)
        row = {
            "kind": kind, "ticker": tk, "entryDate": t["entryDate"], "exitDate": t["exitDate"],
            "year": int(t["entryDate"][:4]), "entryTime": t.get("entryTime", ""),
            "depot": int(bool(t.get("depot", True))), "isOpen": int(bool(t.get("isOpen"))),
            "source": t.get("source", "QQQ"), "trigger": t.get("trigger", "4h"),
            "pnlPct": t["pnlPct"],
            "prev_trade_pnl": prev["pnlPct"] if prev else np.nan,
            "days_since_prev_exit": int((ed - pd.Timestamp(prev["exitDate"])).days) if prev else np.nan,
        }
        row.update(f)
        row.update(trade_outcome(h, t))
        rows.append(row)
        by_ticker_prev[tk] = t
    # Signal-Häufung: wie viele andere Einstiege im selben 10-Tage-Fenster (Breite/Euphorie)
    dates = pd.to_datetime(pd.Series([r["entryDate"] for r in rows]))
    for i, r in enumerate(rows):
        d = dates.iloc[i]
        r["signals_10d"] = int(((dates > d - pd.Timedelta(days=10)) & (dates <= d)).sum() - 1)
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    keys = list(rows[0].keys())
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bench = load_bench()
    bt = json.loads((ROOT / "data" / "backtest_ndx.json").read_text())["trades"]
    rows = build(bt, bench, "backtest")
    write_csv(rows, OUT / "trade_features.csv")
    print(f"Backtest: {len(rows)} von {len(bt)} Trades mit Merkmalen")
    live = json.loads((ROOT / "data" / "live_alerts_performance.json").read_text())["trades"]
    lrows = build(live, bench, "live")
    write_csv(lrows, OUT / "trade_features_live.csv")
    print(f"Live: {len(lrows)} von {len(live)} Trades mit Merkmalen")


if __name__ == "__main__":
    main()
