"""
Führt rs_smallcap_1.json und rs_smallcap_2.json zusammen,
sortiert nach RS-Score und schreibt rs_smallcap.json.
"""
import json
import math
import os

def sanitize_nan(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nan(v) for v in obj]
    return obj

parts = ["rs_smallcap_1.json", "rs_smallcap_2.json"]
all_data          = []
benchmark_ohlcv_w = []
benchmark_ohlcv   = []
timestamps        = []
combined_scores   = {}
combined_prev_week = {}

for path in parts:
    if not os.path.exists(path):
        print(f"WARNUNG: {path} nicht gefunden – übersprungen")
        continue
    with open(path) as f:
        part = json.load(f)
    all_data.extend(part.get("data", []))
    timestamps.append(part.get("timestamp", ""))
    if not benchmark_ohlcv_w:
        benchmark_ohlcv_w = part.get("benchmark_ohlcv_w", [])
    if not benchmark_ohlcv:
        benchmark_ohlcv   = part.get("benchmark_ohlcv", [])
    for date, scores in part.get("daily_scores_by_date", {}).items():
        if date not in combined_scores:
            combined_scores[date] = {}
        for ticker, score in (scores if isinstance(scores, list) else scores.items()):
            if isinstance(scores, list):
                combined_scores[date][ticker] = score
            else:
                combined_scores[date][ticker] = score
    combined_prev_week.update(part.get("prev_week_scores", {}))

# Deduplizieren (falls Ticker in beiden Hälften)
seen = set()
deduped = []
for d in all_data:
    t = d.get("ticker", "")
    if t not in seen:
        seen.add(t)
        deduped.append(d)
all_data = deduped

# Zombie-Filter: MCap < $5M oder Kurs < $0.10
ZOMBIE_MCAP_THRESHOLD = 5_000_000
fund_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "fundamentals.json")
fund_map = {}
if os.path.exists(fund_path):
    with open(fund_path) as f:
        fund_map = json.load(f).get("tickers", {})

def is_zombie(entry):
    ticker = entry.get("ticker", "")
    fund = fund_map.get(ticker, {})
    mcap = fund.get("marketCap")
    if mcap is not None and mcap < ZOMBIE_MCAP_THRESHOLD:
        return True
    ohlcv = entry.get("ohlcv_w") or entry.get("ohlcv", [])
    if ohlcv:
        last_price = ohlcv[-1].get("c", 999)
        if last_price < 0.10:
            return True
    return False

pre_filter = len(all_data)
all_data = [d for d in all_data if not is_zombie(d)]
filtered = pre_filter - len(all_data)
if filtered:
    print(f"   Zombie-Filter: {filtered} Ticker entfernt (MCap < $5M oder Kurs < $0.10)")

all_data.sort(key=lambda x: x.get("score") if x.get("score") is not None else float("-inf"), reverse=True)
top20 = [d["ticker"] for d in all_data[:20]]

top20_history = {}
for date in sorted(combined_scores):
    ranked = sorted(combined_scores[date].items(), key=lambda x: x[1], reverse=True)
    top20_history[date] = [t for t, _ in ranked[:20]]
print(f"   top20_history: {len(top20_history)} Tage")

ranked_prev = sorted(combined_prev_week.items(), key=lambda x: x[1], reverse=True)
prev_rank_map = {t: i + 1 for i, (t, _) in enumerate(ranked_prev)}
for stock in all_data:
    stock["prev_rank"] = prev_rank_map.get(stock["ticker"])
print(f"   prev_rank: {len(prev_rank_map)} Ticker")

output = {
    "timestamp":         max(timestamps) if timestamps else "–",
    "benchmark":         "SC600",
    "top20":             top20,
    "top20_history":     top20_history,
    "data":              all_data,
    "benchmark_ohlcv_w": benchmark_ohlcv_w,
    "benchmark_ohlcv":   benchmark_ohlcv,
}

with open("rs_smallcap.json", "w") as f:
    json.dump(sanitize_nan(output), f)

print(f"✅ Merge abgeschlossen: {len(all_data)} Ticker total")
print(f"   Top 5: {', '.join(top20[:5])}")
print(f"   Timestamp: {output['timestamp']}")
