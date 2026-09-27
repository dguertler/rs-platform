"""
Führt rs_sp500_1.json und rs_sp500_2.json zusammen,
sortiert nach RS-Score und schreibt rs_sp500.json.
"""
import json
import math
import os
from datetime import datetime, timedelta

def sanitize_nan(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nan(v) for v in obj]
    return obj

BENCHMARK = "^GSPC"


def point_in_time_ranking(official):
    """Top-20-Historie und Vorwochen-Rang nur unter den damaligen Mitgliedern.

    Lädt dafür die Schlusskurse aller Titel, die im Zeitfenster irgendwann im
    S&P 500 waren (auch ausgeschiedene), und rankt mit derselben Funktion wie
    der NASDAQ-100 (rs_core.rank_by_day). Liefert None, wenn die
    Zusammensetzung fehlt — dann gilt das bisherige Ranking der Teile.
    """
    import yfinance as yf
    from index_membership import (SP500_FILE, active_in_window, apply_official, load_intervals,
                                  point_in_time_top20)

    intervals = load_intervals(SP500_FILE)
    if not intervals:
        return None
    intervals = apply_official(intervals, official)
    start = datetime.now() - timedelta(days=760)
    end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    symbols = active_in_window(intervals, start.strftime("%Y-%m-%d"))
    close = yf.download(symbols + [BENCHMARK], start=start.strftime("%Y-%m-%d"), end=end,
                        auto_adjust=True, progress=False)["Close"].dropna(axis=1, how="all")
    if BENCHMARK not in close.columns:
        raise RuntimeError(f"Benchmark {BENCHMARK} fehlt im Download")
    history, prev_rank = point_in_time_top20(close, BENCHMARK, intervals)
    tickers = [t for t in close.columns if t != BENCHMARK]
    print(f"   Ranking unter damaligen Mitgliedern: {len(tickers)} Titel, {len(history)} Tage")
    return history, prev_rank


parts = ["rs_sp500_1.json", "rs_sp500_2.json"]
all_data          = []
benchmark_ohlcv_w = []
benchmark_ohlcv   = []
timestamps        = []
official          = set()
combined_scores   = {}  # {date: {ticker: score}}
combined_prev_week = {}  # {ticker: score} für ~5 Handelstage zurück

for path in parts:
    if not os.path.exists(path):
        print(f"WARNUNG: {path} nicht gefunden – übersprungen")
        continue
    with open(path) as f:
        part = json.load(f)
    all_data.extend(part.get("data", []))
    timestamps.append(part.get("timestamp", ""))
    official.update(part.get("fmp_tickers") or [])
    if not benchmark_ohlcv_w:
        benchmark_ohlcv_w = part.get("benchmark_ohlcv_w", [])
    if not benchmark_ohlcv:
        benchmark_ohlcv   = part.get("benchmark_ohlcv", [])
    for date, scores in part.get("daily_scores_by_date", {}).items():
        if date not in combined_scores:
            combined_scores[date] = {}
        for ticker, score in scores:
            combined_scores[date][ticker] = score
    combined_prev_week.update(part.get("prev_week_scores", {}))

all_data.sort(key=lambda x: x.get("score") if x.get("score") is not None else float("-inf"), reverse=True)
top20 = [d["ticker"] for d in all_data[:20]]

top20_history = {}
for date in sorted(combined_scores):
    ranked = sorted(combined_scores[date].items(), key=lambda x: x[1], reverse=True)
    top20_history[date] = [t for t, _ in ranked[:20]]
print(f"   top20_history: {len(top20_history)} Tage")

# prev_rank aus kombinierten Vorwoche-Scores
ranked_prev = sorted(combined_prev_week.items(), key=lambda x: x[1], reverse=True)
prev_rank_map = {t: i + 1 for i, (t, _) in enumerate(ranked_prev)}

# Rückwirkend korrektes Ranking: je Tag nur die damaligen Mitglieder
try:
    _pit = point_in_time_ranking(sorted(official))
except Exception as e:                                   # noqa: BLE001 — Rückfall statt Abbruch
    print(f"   ⚠️ Ranking unter damaligen Mitgliedern fehlgeschlagen ({e}) – bisheriges Ranking bleibt")
    _pit = None
if _pit and _pit[0]:
    top20_history, prev_rank_map = _pit
    top20 = top20_history[max(top20_history)]
    print(f"   Top 20 (nur Indexmitglieder): {', '.join(top20)}")

for stock in all_data:
    stock["prev_rank"] = prev_rank_map.get(stock["ticker"])
print(f"   prev_rank: {len(prev_rank_map)} Ticker")

output = {
    "timestamp":         max(timestamps) if timestamps else "–",
    "benchmark":         "SPX",
    "top20":             top20,
    "top20_history":     top20_history,
    "data":              all_data,
    "benchmark_ohlcv_w": benchmark_ohlcv_w,
    "benchmark_ohlcv":   benchmark_ohlcv,
}

with open("rs_sp500.json", "w") as f:
    json.dump(sanitize_nan(output), f)

print(f"✅ Merge abgeschlossen: {len(all_data)} Ticker total")
print(f"   Top 5: {', '.join(top20[:5])}")
print(f"   Timestamp: {output['timestamp']}")
