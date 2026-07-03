"""
backtest_v2/metrics.py — Kennzahlen-Berechnung für Backtest-Ergebnisse.

Implementiert die Kennzahlen-Pflicht aus STRATEGIEPLAN.md Regel B7:
CAGR, Sharpe, Calmar, Max-DD, längste DD-Dauer, Exposure-Zeit, Profit-Factor,
Trade-Anzahl, Alpha vs. Benchmark.
"""

import math
from statistics import pstdev


def equity_curve_stats(equity_curve, trading_days_per_year=252):
    """equity_curve: Liste von (datum_str, wert), täglich, lückenlos.
    Liefert CAGR, Sharpe, Max-DD, längste DD-Dauer (Handelstage)."""
    if len(equity_curve) < 2:
        return {"cagr": None, "sharpe": None, "max_dd": None, "max_dd_days": None}

    values = [v for _, v in equity_curve]
    n_days = len(values)
    years = n_days / trading_days_per_year
    total_return = values[-1] / values[0] - 1 if values[0] else None
    cagr = ((values[-1] / values[0]) ** (1 / years) - 1) if values[0] and years > 0 else None

    daily_rets = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        if prev:
            daily_rets.append(values[i] / prev - 1)
    sharpe = None
    if len(daily_rets) >= 10:
        mean_r = sum(daily_rets) / len(daily_rets)
        sd = pstdev(daily_rets)
        if sd > 0:
            sharpe = (mean_r / sd) * math.sqrt(trading_days_per_year)

    peak = values[0]
    max_dd = 0.0
    dd_start_idx = 0
    max_dd_days = 0
    cur_dd_start = 0
    for i, v in enumerate(values):
        if v >= peak:
            peak = v
            cur_dd_start = i
        else:
            dd = (peak - v) / peak if peak else 0
            if dd > max_dd:
                max_dd = dd
                max_dd_days = i - cur_dd_start
    calmar = (cagr / max_dd) if cagr is not None and max_dd else None

    return {
        "total_return_pct": round(total_return * 100, 2) if total_return is not None else None,
        "cagr_pct": round(cagr * 100, 2) if cagr is not None else None,
        "sharpe": round(sharpe, 2) if sharpe is not None else None,
        "calmar": round(calmar, 2) if calmar is not None else None,
        "max_dd_pct": round(max_dd * 100, 2),
        "max_dd_days": max_dd_days,
    }


def trade_stats(trades):
    """trades: Liste von Dicts mit mind. 'pnl' (absolut) und 'pnl_pct'."""
    closed = [t for t in trades if not t.get("is_open")]
    if not closed:
        return {
            "n_trades": 0, "win_rate_pct": None, "profit_factor": None,
            "avg_win_pct": None, "avg_loss_pct": None,
        }
    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] <= 0]
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = sum(t["pnl"] for t in losses)
    return {
        "n_trades": len(closed),
        "n_wins": len(wins),
        "n_losses": len(losses),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1),
        "profit_factor": round(gross_profit / abs(gross_loss), 2) if gross_loss < 0 else None,
        "avg_win_pct": round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else None,
        "avg_loss_pct": round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else None,
    }


def exposure_pct(equity_curve_with_positions):
    """Anteil der Handelstage mit mind. einer offenen Position.
    Eingabe: Liste von (datum, n_positions)."""
    if not equity_curve_with_positions:
        return None
    days_with_pos = sum(1 for _, n in equity_curve_with_positions if n > 0)
    return round(days_with_pos / len(equity_curve_with_positions) * 100, 1)


def benchmark_alpha(strategy_equity, benchmark_closes):
    """Gesamtrendite Strategie vs. Buy-and-Hold Benchmark über denselben Zeitraum."""
    if len(strategy_equity) < 2 or len(benchmark_closes) < 2:
        return None
    strat_ret = strategy_equity[-1][1] / strategy_equity[0][1] - 1
    bench_ret = benchmark_closes[-1] / benchmark_closes[0] - 1
    return {
        "strategy_return_pct": round(strat_ret * 100, 2),
        "benchmark_buyhold_return_pct": round(bench_ret * 100, 2),
        "alpha_pct": round((strat_ret - bench_ret) * 100, 2),
    }


def sma_rule_return(benchmark_closes, benchmark_dates, sma_period=200):
    """Einfache 200d-Regel auf den Benchmark (B8-Vergleich): investiert wenn
    Close > SMA(200), sonst Cash (0% Rendite in dieser Phase). Erste
    sma_period Tage ohne SMA-Wert gelten als investiert (Buy&Hold-Startphase)."""
    if len(benchmark_closes) < sma_period + 2:
        return None
    equity = 1.0
    for i in range(1, len(benchmark_closes)):
        if i >= sma_period:
            sma = sum(benchmark_closes[i - sma_period:i]) / sma_period
            invested = benchmark_closes[i - 1] > sma
        else:
            invested = True
        if invested and benchmark_closes[i - 1]:
            equity *= benchmark_closes[i] / benchmark_closes[i - 1]
    return round((equity - 1) * 100, 2)
