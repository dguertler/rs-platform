"""
Daten-Lader für die Instagram-Grafiken.

Quellen (alle bereits im Repo, außer Wikifolio-Kurve):
  - data/signals.json        – historische Trade-Signale je Ticker
  - data/rs_full.json        – NASDAQ-100 RS + OHLCV  (+ QQQ-Benchmark)
  - data/rs_dax.json         – DAX-40   RS + OHLCV
  - data/rs_sp500.json       – S&P 500  RS + OHLCV
  - data/wikifolio_performance.json – Equity-Kurve des wikifolios
        Format: {"name": "...", "currency": "EUR",
                 "series": [{"d": "2026-04-01", "v": 100.0}, ...]}
        Fehlt die Datei, wird eine klar gekennzeichnete BEISPIEL-Kurve erzeugt.
"""
import json
import os
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

_RS_FILES = ["rs_full.json", "rs_dax.json", "rs_sp500.json"]


def _load(path):
    with open(path) as f:
        return json.load(f)


def load_universe():
    """Mischt alle RS-Universen zu ticker -> {ohlcv, ohlcv_w, score, windows}
    und liefert zusätzlich die Benchmark-Serie (QQQ / NASDAQ-100)."""
    universe = {}
    benchmark = None
    for fname in _RS_FILES:
        path = os.path.join(DATA, fname)
        if not os.path.exists(path):
            continue
        d = _load(path)
        for e in d.get("data", []):
            universe[e["ticker"]] = {
                "ohlcv": e.get("ohlcv", []),
                "ohlcv_w": e.get("ohlcv_w", []),
                "score": e.get("score"),
                "windows": e.get("windows", {}),
            }
        # NASDAQ-Benchmark einmalig aus rs_full übernehmen.
        # NDX-Index (exakt) bevorzugen, sonst QQQ-ETF als Fallback.
        if benchmark is None:
            src = d.get("ndx_ohlcv") or d.get("benchmark_ohlcv")
            if src:
                benchmark = [(c["d"], c["c"]) for c in src]
    return universe, benchmark


def load_signals():
    return _load(os.path.join(DATA, "signals.json"))


def recent_signals(signals, universe, limit=2, min_days=10):
    """Wählt die jüngsten Signale, die einen OHLCV-Verlauf haben und deren
    Signal weit genug zurückliegt, um eine Entwicklung zu zeigen."""
    flat = []
    for ticker, sigs in signals.items():
        if ticker not in universe or not universe[ticker]["ohlcv"]:
            continue
        for s in sigs:
            flat.append((ticker, s))
    # nach Signaldatum absteigend
    flat.sort(key=lambda x: x[1]["signal_date"], reverse=True)
    today = datetime.utcnow().date()
    out = []
    for ticker, s in flat:
        try:
            d = datetime.strptime(s["signal_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if (today - d).days < min_days:
            continue
        out.append((ticker, s))
        if len(out) >= limit:
            break
    return out


def signal_return(universe, ticker, signal_date):
    """Reale Rendite vom Schlusskurs am/ nach Signaltag bis zum letzten Kurs."""
    ohlcv = universe[ticker]["ohlcv"]
    entry = next((c for c in ohlcv if c["d"] >= signal_date), None)
    if not entry or not ohlcv:
        return None, None, None
    last = ohlcv[-1]
    ret = last["c"] / entry["c"] - 1.0
    return ret, entry, last


def load_performance():
    """Lädt die Wikifolio-Equity-Kurve oder erzeugt eine BEISPIEL-Kurve.
    Rückgabe: (dates[list[str]], values[list[float]], is_sample[bool], meta)"""
    path = os.path.join(DATA, "wikifolio_performance.json")
    if os.path.exists(path):
        d = _load(path)
        series = d.get("series", [])
        dates = [p["d"] for p in series]
        vals = [float(p["v"]) for p in series]
        return dates, vals, False, d
    # ── Fallback: klar gekennzeichnete Beispiel-Kurve ─────────────────────────
    start = datetime(2026, 4, 1)
    dates, vals, v = [], [], 100.0
    steps = [0.9, 1.1, -0.4, 1.6, 0.8, -0.6, 2.1, 1.2, 0.5, -0.3, 1.8,
             0.7, 1.4, -0.5, 2.3, 1.0, 0.6, 1.9, -0.4, 1.5, 0.9, 1.3]
    for i, s in enumerate(steps):
        d = start + timedelta(days=i * 3)
        v *= (1 + s / 100.0 * 3)  # grob skaliert auf ~+60 %
        dates.append(d.strftime("%Y-%m-%d"))
        vals.append(round(v, 2))
    meta = {"name": "AI Alpha Selections", "currency": "EUR", "sample": True}
    return dates, vals, True, meta


def benchmark_window(benchmark, start_date, end_date):
    """Normiert die Benchmark-Serie auf 100 im Zeitfenster [start, end]."""
    pts = [(d, c) for d, c in benchmark if start_date <= d <= end_date]
    if not pts:
        return [], []
    base = pts[0][1]
    return [d for d, _ in pts], [c / base * 100.0 for _, c in pts]
