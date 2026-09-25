"""
Prüft, dass rs_core.rank_by_day exakt dasselbe Tagesranking liefert wie die
ursprüngliche Schleife aus rs_colab.py (Schritt 5) — Grundlage dafür, dass
der historische Backtest (backtest_history/) wie live rankt.

Aufruf: python3 -m pytest test_rs_core.py -q
"""
import json
import os

import numpy as np
import pandas as pd

from rs_core import RS_WINDOWS, rank_by_day

_REPO = os.path.dirname(os.path.abspath(__file__))


def reference_top20(d_close, benchmark, tickers):
    """Wörtliche Kopie der bisherigen Schleife aus rs_colab.py, Schritt 5."""
    bench_s = d_close[benchmark]
    avail = [t for t in tickers if t in d_close.columns]
    top20_history = {}
    for i in range(len(d_close)):
        date_str = d_close.index[i].strftime("%Y-%m-%d")
        b_now = bench_s.iloc[i]
        if pd.isna(b_now) or b_now == 0:
            continue
        scores = []
        for t in avail:
            s_now = d_close[t].iloc[i]
            if pd.isna(s_now) or s_now == 0:
                continue
            total, cnt = 0, 0
            for days in RS_WINDOWS.values():
                if i >= days:
                    s_prev = d_close[t].iloc[i - days]
                    b_prev = bench_s.iloc[i - days]
                    if not pd.isna(s_prev) and not pd.isna(b_prev) and s_prev != 0 and b_prev != 0:
                        total += (s_now / s_prev - 1) * 100 - (b_now / b_prev - 1) * 100
                        cnt += 1
            if cnt > 0:
                scores.append((t, total))
        if len(scores) >= 20:
            scores.sort(key=lambda x: x[1], reverse=True)
            top20_history[date_str] = [t for t, _ in scores[:20]]
    return top20_history


def new_top20(d_close, benchmark, tickers, mask=None):
    return {d: [t for t, _ in ranked[:20]]
            for _, d, ranked in rank_by_day(d_close, benchmark, tickers, mask)}


def synthetic_frame(seed=7, n_days=320, n_tickers=30):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n_days)
    data = {}
    for k in range(n_tickers):
        px = 50 * np.exp(np.cumsum(rng.normal(0, 0.02, n_days)))
        start = rng.integers(0, 200) if k % 5 == 0 else 0     # späte Börsengänge
        px[:start] = np.nan
        holes = rng.choice(n_days, 4, replace=False)          # einzelne Lücken
        px[holes] = np.nan
        data[f"T{k:02d}"] = px
    qqq = 300 * np.exp(np.cumsum(rng.normal(0, 0.01, n_days)))
    qqq[[3, 150]] = np.nan
    data["QQQ"] = qqq
    return pd.DataFrame(data, index=idx)


def test_matches_reference_on_synthetic_data():
    df = synthetic_frame()
    tickers = [c for c in df.columns if c != "QQQ"]
    ref = reference_top20(df, "QQQ", tickers)
    assert ref, "Referenz liefert kein Ranking"
    assert new_top20(df, "QQQ", tickers) == ref


def test_matches_reference_on_repo_data():
    rs = json.load(open(os.path.join(_REPO, "data", "rs_full.json")))
    series = {}
    for entry in rs["data"]:
        path = os.path.join(_REPO, "data", f"backtest_{entry['ticker'].lower()}.json")
        rows = json.load(open(path))["ohlcv_d"] if os.path.exists(path) else entry["ohlcv"]
        series[entry["ticker"]] = pd.Series({r["d"]: r["c"] for r in rows})
    series["QQQ"] = pd.Series({r["d"]: r["c"] for r in rs["benchmark_ohlcv"]})
    df = pd.DataFrame(series)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    tickers = [e["ticker"] for e in rs["data"]]
    assert new_top20(df, "QQQ", tickers) == reference_top20(df, "QQQ", tickers)


def test_member_mask_excludes_non_members_but_keeps_their_prices():
    df = synthetic_frame(seed=3, n_tickers=25)
    tickers = [c for c in df.columns if c != "QQQ"]
    mask = np.ones((len(df), len(tickers)), dtype=bool)
    mask[:, 0] = False                                       # T00 nie Mitglied
    ranked = list(rank_by_day(df, "QQQ", tickers, mask))
    assert ranked
    assert all("T00" not in [t for t, _ in r] for _, _, r in ranked)
    # Die Scores der übrigen Ticker bleiben unverändert
    full = {d: dict(r) for _, d, r in rank_by_day(df, "QQQ", tickers)}
    for _, d, r in ranked:
        for t, s in r:
            assert full[d][t] == s
