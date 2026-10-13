"""
4H-Kerzen ab 2016 für den Benchmark QQQ (NASDAQ-100) über Alpaca — Grundlage für
„NASDAQ-100 mit Logik“ (dieselbe Signal-/Ausstiegslogik wie bei den Aktien, angewandt
auf QQQ selbst; backtest_ndx.js → ndxLogic, B-ÜBERSICHT/B-DETAILS).

Schreibt data/backtest_history/charts/QQQ.json im Format der übrigen Kursdateien:
w/d aus charts/_benchmark.json (Yahoo, ab 2005), h = 4H-Kerzen wie live
(30-Minuten-Kerzen → Yahoo-Stundenraster → rs_core.hourly_to_4h_rows).

Zugang: Secrets ALPACA_API_KEY / ALPACA_API_SECRET (in Cloud-Sessions gesperrt —
Aufruf über .github/workflows/fetch_benchmark_4h.yml).

Aufruf: python3 backtest_history/fetch_benchmark_4h.py
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)

from rs_core import hourly_to_4h_rows                       # noqa: E402
from alpaca import choose_feed, credentials, fetch_bars      # noqa: E402
from fetch_alpaca_4h import FETCH_START, yahoo_like_hourly   # noqa: E402

CHARTS = os.path.join(os.path.dirname(_HERE), "data", "backtest_history", "charts")
SYMBOL = "QQQ"


def main():
    key, secret = credentials()
    if not key:
        raise SystemExit("ALPACA_API_KEY / ALPACA_API_SECRET fehlen")
    bench = json.load(open(os.path.join(CHARTS, "_benchmark.json")))
    end = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
    feed = choose_feed(SYMBOL, key, secret)
    bars = fetch_bars([SYMBOL], f"{FETCH_START}T00:00:00Z", end, feed, key, secret).get(SYMBOL) or []
    rows = hourly_to_4h_rows(yahoo_like_hourly(bars), decimals=4) if bars else []
    if not rows:
        raise SystemExit("Keine 4H-Kerzen für QQQ erhalten")
    out = {"ticker": SYMBOL, "w": bench["w"], "d": bench["d"],
           "h": [[r["d"], r["o"], r["h"], r["l"], r["c"]] for r in rows]}
    with open(os.path.join(CHARTS, f"{SYMBOL}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"QQQ: {len(rows)} 4H-Kerzen {rows[0]['d']} … {rows[-1]['d']} (Feed {feed})")


if __name__ == "__main__":
    main()
