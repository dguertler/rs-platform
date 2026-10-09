"""
Zugriff auf die Alpaca Market Data API (Historie ab 2016, auch für nicht
mehr gehandelte Aktien). Gemeinsam genutzt von prepare_data.py (Tageskerzen
für Indexmitglieder, die Yahoo nicht mehr führt) und fetch_alpaca_4h.py
(30-Minuten-Kerzen für die 4H-Bildung).

Zugang: Secrets ALPACA_API_KEY / ALPACA_API_SECRET (kostenloser Basic-Plan).
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

API = "https://data.alpaca.markets/v2/stocks/bars"
HISTORY_START = "2016-01-01"     # ab hier liefert Alpaca Kurse
MAX_RETRIES = 6


def credentials():
    """(key, secret) aus der Umgebung, sonst (None, None)."""
    key = os.environ.get("ALPACA_API_KEY", "").strip()
    secret = os.environ.get("ALPACA_API_SECRET", "").strip()
    return (key, secret) if key and secret else (None, None)


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


def fetch_bars(symbols, start, end, feed, key, secret, timeframe="30Min"):
    """Kerzen (split- und dividendenbereinigt) je Symbol: {symbol: [{t,o,h,l,c,v}, ...]}."""
    out = {s: [] for s in symbols}
    params = {"symbols": ",".join(symbols), "timeframe": timeframe, "start": start, "end": end,
              "adjustment": "all", "feed": feed, "limit": 10000, "sort": "asc"}
    while True:
        data = _request(params, key, secret)
        for sym, bars in (data.get("bars") or {}).items():
            out.setdefault(sym, []).extend(bars)
        token = data.get("next_page_token")
        if not token:
            return out
        params["page_token"] = token


def choose_feed(probe_symbol, key, secret):
    """SIP (alle Börsen) bevorzugt; ohne Berechtigung auf IEX ausweichen."""
    for feed in ("sip", "iex"):
        try:
            fetch_bars([probe_symbol], "2016-01-04T00:00:00Z", "2016-01-06T00:00:00Z", feed, key, secret)
            return feed
        except RuntimeError as e:
            print(f"  Feed {feed}: {e}")
    raise SystemExit("Kein Alpaca-Feed verfügbar — Zugangsdaten prüfen.")


def daily_frame(bars):
    """Alpaca-Tageskerzen → DataFrame(Open, High, Low, Close) mit Datumsindex wie Yahoo."""
    if not bars:
        return pd.DataFrame()
    df = pd.DataFrame(bars)
    # Zeitstempel = Mitternacht New York in UTC → Handelstag in New Yorker Zeit
    idx = pd.to_datetime(df["t"], utc=True).dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
    out = pd.DataFrame({"Open": df["o"].values, "High": df["h"].values, "Low": df["l"].values,
                        "Close": df["c"].values}, index=pd.DatetimeIndex(idx.values))
    return out[~out.index.duplicated(keep="last")].sort_index()


def weekly_from_daily(daily):
    """Wochenkerzen aus Tageskerzen, gestempelt auf den Montag der Woche."""
    if daily.empty:
        return daily
    w = daily.resample("W-MON", label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    return w
