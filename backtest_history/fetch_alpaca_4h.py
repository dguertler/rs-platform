"""
Historischer Backtest, Schritt 1b: 4H-Kerzen ab 2016 über die Alpaca Market
Data API (Yahoo liefert Stundenkerzen nur für ~2 Jahre).

Die 4H-Kerzen entstehen exakt wie live (rs_core.hourly_to_4h_rows). Dafür
werden aus Alpacas 30-Minuten-Kerzen zuerst dieselben Stundenkerzen gebaut,
die Yahoo liefert: in der Handelszeit ab 9:30 ET je volle Stunde (9:30,
10:30 … 15:30), außerhalb zur vollen Stunde (4:00 … 9:00, 16:00 … 19:00).

Geladen werden nur Symbole, die ab 2016 mindestens einmal in den Top 20
standen (backtest_history/cache/top20_inkl.json aus prepare_data.py). Für
Aktien, deren Tageskerzen schon von Alpaca stammen (Yahoo führt sie nicht
mehr), gilt das dort hinterlegte Alpaca-Symbol und dessen Zeitraum.

Zugang: Secrets ALPACA_API_KEY / ALPACA_API_SECRET (kostenloser Basic-Plan).
Fehlen sie, überspringt das Skript den Schritt ohne Fehler.

Aufruf: python3 backtest_history/fetch_alpaca_4h.py
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)

from rs_core import hourly_to_4h_rows          # noqa: E402
from alpaca import HISTORY_START, choose_feed, credentials, fetch_bars   # noqa: E402

CACHE_DIR = os.path.join(_HERE, "cache")
H4_START = HISTORY_START         # Alpaca-Historie beginnt 2016
FETCH_START = "2015-12-01"       # etwas Vorlauf für die 60 Kerzen der 4H-Struktur
SYMBOLS_PER_REQUEST = 10
PARALLEL_REQUESTS = 4          # Basic-Plan: 200 Anfragen/Minute, 429 wird abgewartet
ET = "America/New_York"


def yahoo_like_hourly(bars):
    """30-Minuten-Kerzen → Stundenkerzen mit Yahoos Raster (Index in ET)."""
    if not bars:
        return pd.DataFrame()
    df = pd.DataFrame(bars)
    idx = pd.to_datetime(df["t"], utc=True).dt.tz_convert(ET)
    minutes = idx.dt.hour * 60 + idx.dt.minute
    regular = (minutes >= 9 * 60 + 30) & (minutes < 16 * 60)
    # Handelszeit: Stundenblöcke ab 9:30 (Abstand zur letzten :30-Marke abziehen,
    # ohne Tagesarithmetik — die ginge an Zeitumstellungstagen um eine Stunde fehl);
    # sonst volle Stunde
    anchor_reg = idx - pd.to_timedelta((minutes - (9 * 60 + 30)) % 60, unit="min")
    anchor_ext = idx.dt.floor("h")
    df["anchor"] = anchor_reg.where(regular, anchor_ext)
    hourly = df.groupby("anchor").agg(
        Open=("o", "first"), High=("h", "max"), Low=("l", "min"), Close=("c", "last"), Volume=("v", "sum"))
    hourly.index.name = None
    return hourly


def symbols_needed():
    hist = json.load(open(os.path.join(CACHE_DIR, "top20_inkl.json")))
    return sorted({t for d, top in hist.items() if d >= H4_START for t in top})


def alpaca_sources():
    """Cache-Symbol → {query, from, to} für Aktien mit Alpaca-Tageskerzen."""
    meta = json.load(open(os.path.join(CACHE_DIR, "meta.json")))
    return {sym: info["alpaca"] for sym, info in meta.get("symbols", {}).items() if info.get("alpaca")}


def main():
    key, secret = credentials()
    if not key:
        print("ALPACA_API_KEY / ALPACA_API_SECRET fehlen — 4H-Historie wird übersprungen.")
        return
    symbols = symbols_needed()
    sources = alpaca_sources()
    query = {s: sources.get(s, {}).get("query", s) for s in symbols}
    end = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
    feed = choose_feed(symbols[0] if symbols else "AAPL", key, secret)
    print(f"4H-Kerzen für {len(symbols)} Symbole ab {FETCH_START} (Feed {feed}) ...")

    os.makedirs(os.path.join(CACHE_DIR, "h4"), exist_ok=True)
    info, missing = {}, []
    chunks = [symbols[k:k + SYMBOLS_PER_REQUEST] for k in range(0, len(symbols), SYMBOLS_PER_REQUEST)]

    def load(chunk):
        try:
            names = sorted({query[s] for s in chunk})
            return chunk, fetch_bars(names, f"{FETCH_START}T00:00:00Z", end, feed, key, secret), None
        except RuntimeError as e:
            return chunk, None, e

    done = 0
    with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as pool:
        for chunk, bars, err in pool.map(load, chunks):
            done += len(chunk)
            if err:
                print(f"  {','.join(chunk)}: {err}")
                missing.extend(chunk)
                continue
            for sym in chunk:
                hourly = yahoo_like_hourly(bars.get(query[sym]) or [])
                rows = hourly_to_4h_rows(hourly, decimals=4) if len(hourly) else []
                src = sources.get(sym)
                if src:                    # nur der Zeitraum, für den das Symbol gilt
                    rows = [r for r in rows if src["from"] <= r["d"][:10] <= src["to"]]
                if not rows:
                    missing.append(sym)
                    continue
                with open(os.path.join(CACHE_DIR, "h4", f"{sym}.json"), "w", encoding="utf-8") as f:
                    json.dump(rows, f, separators=(",", ":"))
                info[sym] = {"first": rows[0]["d"][:10], "last": rows[-1]["d"][:10], "bars": len(rows)}
            print(f"  {done}/{len(symbols)}", flush=True)

    meta = {"source": "Alpaca Market Data API (30Min → Yahoo-Stundenraster → 4H wie live)",
            "feed": feed, "start": H4_START, "symbols": info, "missing": sorted(missing)}
    with open(os.path.join(CACHE_DIR, "h4_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    print(f"Fertig: {len(info)} Symbole mit 4H-Kerzen, {len(missing)} ohne: {' '.join(sorted(missing))}")


if __name__ == "__main__":
    main()
