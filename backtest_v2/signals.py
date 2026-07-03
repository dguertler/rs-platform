"""
backtest_v2/signals.py — Point-in-Time-Signalberechnung für den Backtest.

Reused ausschließlich die LIVE-Signal-Funktionen aus backend/gws_analysis.py
und backend/v2_analysis.py (Regel B10 — eine Quelle der Wahrheit). Dieses
Modul truncated die Eingabedaten je Woche auf "nur bis dahin bekannt" und
ruft die bestehenden Funktionen darauf auf — es implementiert KEINE eigene
Signal-Logik.
"""

import sys
from pathlib import Path

_BACKEND = Path(__file__).parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from gws_analysis import struct_daily, struct_weekly          # noqa: E402
from v2_analysis import (                                      # noqa: E402
    _rs2_raw, _percentiles, compute_regime, _atr,
    _last_confirmed_swing_low, _sma,
)


def weekly_signal_cache(tickers_data, bench_ohlcv, week_dates):
    """Berechnet für jede Woche (week_dates, aufsteigend) und jeden Ticker:
    RS2-Perzentil, Regime, GWS-Weekly/Daily-Status — jeweils NUR mit Daten
    bis einschließlich diesem Wochendatum (kein Look-Ahead).

    tickers_data: {ticker: {"ohlcv": [...], "ohlcv_w": [...]}}
    Rückgabe: {week_date: {"regime": {...}, "rs2_pct": {ticker: float|None},
                            "struct": {ticker: {"w": bool, "d": bool}}}}
    """
    bench_dates = [row["d"] for row in bench_ohlcv]
    bench_closes = [row["c"] for row in bench_ohlcv]

    cache = {}
    for week_end in week_dates:
        # Wie viele Benchmark-Handelstage liegen <= week_end?
        b_cut = sum(1 for d in bench_dates if d <= week_end)
        bench_trunc = bench_ohlcv[:b_cut]

        raw_now = {}
        ticker_close_lists = []
        struct_map = {}
        for ticker, d in tickers_data.items():
            daily = d["ohlcv"]
            weekly = d["ohlcv_w"]
            d_cut = sum(1 for row in daily if row["d"] <= week_end)
            w_cut = sum(1 for row in weekly if row["d"] <= week_end)
            daily_trunc = daily[:d_cut]
            weekly_trunc = weekly[:w_cut]
            if not daily_trunc:
                continue
            closes = [r["c"] for r in daily_trunc]
            ticker_close_lists.append(closes)
            raw_now[ticker] = _rs2_raw(closes, [r["c"] for r in bench_trunc])

            sd = struct_daily(daily_trunc)
            sw = struct_weekly(weekly_trunc)
            struct_map[ticker] = {
                "w": bool(sw and sw.get("broken")),
                "d": bool(sd and sd.get("broken")),
                "close": closes[-1],
                "sma50": _sma(closes, 50),
            }

        pct_now = _percentiles(raw_now)
        regime = compute_regime(bench_trunc, ticker_close_lists)
        cache[week_end] = {"regime": regime, "rs2_pct": pct_now, "struct": struct_map}
    return cache


def entry_signal(ticker, prev_week_cache, curr_week_cache):
    """True, wenn Weekly+Daily GWS in curr_week neu beide gebrochen sind
    (Übergang von 'nicht beides' zu 'beides'), analog zur v1-Logik in
    backtest_logic.js (simulateTrades: prev.pts < 3 && curr.pts === 3),
    hier ohne 4H (Regel B9 — keine point-in-time 4H-Historie verfügbar)."""
    prev = prev_week_cache["struct"].get(ticker)
    curr = curr_week_cache["struct"].get(ticker)
    if not curr:
        return False
    curr_both = curr["w"] and curr["d"]
    prev_both = bool(prev and prev["w"] and prev["d"])
    return curr_both and not prev_both


def compute_stop(daily_ohlcv_trunc, entry_price):
    """Initial-Stop = letztes bestätigtes Swing-Low − 1 %, gedeckelt auf
    max. 2×ATR(14) unter dem Entry (STRATEGIEPLAN.md Abschnitt 3, Regel 1)."""
    swing_low = _last_confirmed_swing_low(daily_ohlcv_trunc)
    atr = _atr(daily_ohlcv_trunc)
    if swing_low is None:
        return None
    stop = swing_low * 0.99
    if atr:
        stop = max(stop, entry_price - 2 * atr)
    return round(stop, 2) if stop < entry_price else None
