"""
Historischer Backtest, Schritt 1b: 4H-Kerzen ab 2016 über die Alpaca Market
Data API (Yahoo liefert Stundenkerzen nur für ~2 Jahre).

Die 4H-Kerzen entstehen exakt wie live (rs_core.hourly_to_4h_rows). Dafür
werden aus Alpacas 30-Minuten-Kerzen zuerst dieselben Stundenkerzen gebaut,
die Yahoo liefert: in der Handelszeit ab 9:30 ET je volle Stunde (9:30,
10:30 … 15:30), außerhalb zur vollen Stunde (4:00 … 9:00, 16:00 … 19:00).

Geladen werden nur Symbole, die ab 2016 mindestens einmal in den Top 20
standen (backtest_history/cache/top20_inkl.json aus prepare_data.py).

Zugang: Secrets ALPACA_API_KEY / ALPACA_API_SECRET (kostenloser Basic-Plan).
Fehlen sie, überspringt das Skript den Schritt ohne Fehler.

Aufruf: python3 backtest_history/fetch_alpaca_4h.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from rs_core import hourly_to_4h_rows          # noqa: E402

API = "https://data.alpaca.markets/v2/stocks/bars"
CACHE_DIR = os.path.join(_HERE, "cache")
H4_START = "2016-01-01"          # Alpaca-Historie beginnt 2016
FETCH_START = "2015-12-01"       # etwas Vorlauf für die 60 Kerzen der 4H-Struktur
SYMBOLS_PER_REQUEST = 10
MAX_RETRIES = 6
ET = "America/New_York"


def _request(params, key, secret):
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret, "Accept": "application/json"})
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            if e.code == 429 or e.code >= 500:           # Limit / Serverfehler → warten
                time.sleep(2 ** attempt * 3)
                continue
            raise RuntimeError(f"HTTP {e.code}: {body}") from None
        except urllib.error.URLError:
            time.sleep(2 ** attempt * 3)
    raise RuntimeError("Alpaca nicht erreichbar (zu viele Wiederholungen)")


def fetch_bars(symbols, start, end, feed, key, secret):
    """30-Minuten-Kerzen (split- und dividendenbereinigt) je Symbol."""
    out = {s: [] for s in symbols}
    params = {"symbols": ",".join(symbols), "timeframe": "30Min", "start": start, "end": end,
              "adjustment": "all", "feed": feed, "limit": 10000, "sort": "asc"}
    while True:
        data = _request(params, key, secret)
        for sym, bars in (data.get("bars") or {}).items():
            out.setdefault(sym, []).extend(bars)
        token = data.get("next_page_token")
        if not token:
            return out
        params["page_token"] = token


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


def _choose_feed(probe_symbol, end, key, secret):
    """SIP (alle Börsen) bevorzugt; ohne Berechtigung auf IEX ausweichen."""
    for feed in ("sip", "iex"):
        try:
            fetch_bars([probe_symbol], "2016-01-04T00:00:00Z", "2016-01-06T00:00:00Z", feed, key, secret)
            return feed
        except RuntimeError as e:
            print(f"  Feed {feed}: {e}")
    raise SystemExit("Kein Alpaca-Feed verfügbar — Zugangsdaten prüfen.")


def main():
    key = os.environ.get("ALPACA_API_KEY", "").strip()
    secret = os.environ.get("ALPACA_API_SECRET", "").strip()
    if not key or not secret:
        print("ALPACA_API_KEY / ALPACA_API_SECRET fehlen — 4H-Historie wird übersprungen.")
        return
    symbols = symbols_needed()
    end = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
    feed = _choose_feed(symbols[0] if symbols else "AAPL", end, key, secret)
    print(f"4H-Kerzen für {len(symbols)} Symbole ab {FETCH_START} (Feed {feed}) ...")

    os.makedirs(os.path.join(CACHE_DIR, "h4"), exist_ok=True)
    info, missing = {}, []
    for k in range(0, len(symbols), SYMBOLS_PER_REQUEST):
        chunk = symbols[k:k + SYMBOLS_PER_REQUEST]
        try:
            bars = fetch_bars(chunk, f"{FETCH_START}T00:00:00Z", end, feed, key, secret)
        except RuntimeError as e:
            print(f"  {','.join(chunk)}: {e}")
            missing.extend(chunk)
            continue
        for sym in chunk:
            hourly = yahoo_like_hourly(bars.get(sym) or [])
            rows = hourly_to_4h_rows(hourly, decimals=4) if len(hourly) else []
            if not rows:
                missing.append(sym)
                continue
            with open(os.path.join(CACHE_DIR, "h4", f"{sym}.json"), "w", encoding="utf-8") as f:
                json.dump(rows, f, separators=(",", ":"))
            info[sym] = {"first": rows[0]["d"][:10], "last": rows[-1]["d"][:10], "bars": len(rows)}
        print(f"  {min(k + SYMBOLS_PER_REQUEST, len(symbols))}/{len(symbols)}")

    meta = {"source": "Alpaca Market Data API (30Min → Yahoo-Stundenraster → 4H wie live)",
            "feed": feed, "start": H4_START, "symbols": info, "missing": sorted(missing)}
    with open(os.path.join(CACHE_DIR, "h4_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    print(f"Fertig: {len(info)} Symbole mit 4H-Kerzen, {len(missing)} ohne: {' '.join(sorted(missing))}")


if __name__ == "__main__":
    main()
