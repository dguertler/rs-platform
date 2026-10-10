"""
alpaca_live.py — Live-4H-Kerzen über die Alpaca Market Data API

Die Live-Daten (rs_full.json, rs_sp500.json und die Backtest-Dateien für
B-ÜBERSICHT / B-DETAILS) bauen ihre 4H-Kerzen aus denselben Quellkerzen wie der
historische Backtest: Alpaca-30-Minuten-Kerzen → Yahoos Stundenraster →
rs_core.hourly_to_4h_rows. Yahoos nachbörsliche Stundenkerzen enthalten viele
Ausreißer-Dochte, die falsche Ausbruchsmarken setzen (Studie 10/2026).

Fehlen die Zugangsdaten (ALPACA_API_KEY / ALPACA_API_SECRET) oder liefert Alpaca
für einen Ticker nichts, bleibt der Aufrufer beim bisherigen Yahoo-Abruf.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "backtest_history"))

from alpaca import choose_feed, credentials, fetch_bars          # noqa: E402
from fetch_alpaca_4h import yahoo_like_hourly                    # noqa: E402
from rs_core import hourly_to_4h_rows                            # noqa: E402

SYMBOLS_PER_REQUEST = 20
RECENT_DELAY = timedelta(minutes=16)   # Basic-Plan: SIP-Daten erst nach 15 Minuten


_FEED = {}


def _feed(key, secret):
    """SIP bevorzugt, sonst IEX — einmal je Lauf ermittelt."""
    if "feed" not in _FEED:
        try:
            _FEED["feed"] = choose_feed("AAPL", key, secret)
        except SystemExit as e:
            print(f"  Alpaca nicht verfügbar ({e}) – 4H weiter über Yahoo")
            _FEED["feed"] = None
    return _FEED["feed"]


def alpaca_symbol(ticker):
    """Yahoo-Schreibweise → Alpaca (BRK-B → BRK.B)."""
    return ticker.replace("-", ".")


def _fetch_30min(tickers, days):
    """{ticker: 30-Minuten-Kerzen} (SIP 16 Minuten verzögert) — leer ohne Zugang."""
    key, secret = credentials()
    if not key or not tickers:
        if not key:
            print("  Alpaca: keine Zugangsdaten – 4H weiter über Yahoo")
        return {}
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
    end = (now - RECENT_DELAY).strftime("%Y-%m-%dT%H:%M:%SZ")
    feed = _feed(key, secret)
    if not feed:
        return {}

    names = {t: alpaca_symbol(t) for t in tickers}
    bars = {}
    unique = sorted(set(names.values()))
    for k in range(0, len(unique), SYMBOLS_PER_REQUEST):
        chunk = unique[k:k + SYMBOLS_PER_REQUEST]
        try:
            bars.update(fetch_bars(chunk, start, end, feed, key, secret))
        except RuntimeError:
            for name in chunk:            # ein abgelehntes Symbol kostet nicht die ganze Anfrage
                try:
                    bars.update(fetch_bars([name], start, end, feed, key, secret))
                except RuntimeError as e:
                    print(f"  Alpaca {name}: {str(e)[:120]}")
    return {t: bars.get(name) or [] for t, name in names.items()}


def fetch_4h_map(tickers, days=60, decimals=2):
    """{ticker: 4H-Kerzen} für alle Ticker, die Alpaca liefert. Leeres Dict ohne Zugang."""
    raw = _fetch_30min(tickers, days)
    out = {}
    for t, bars in raw.items():
        hourly = yahoo_like_hourly(bars)
        rows = hourly_to_4h_rows(hourly, decimals=decimals) if len(hourly) else []
        if rows:
            out[t] = rows
    if len(tickers) > 1 and raw:
        print(f"  Alpaca ({_FEED.get('feed')}): 4H für {len(out)} von {len(tickers)} Tickern")
    return out


def regular_session_today(bars, day):
    """Tageskerze von `day` (YYYY-MM-DD, New Yorker Datum) aus den 30-Minuten-Kerzen
    der regulären Handelszeit bis jetzt — None vor Börsenbeginn."""
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    rows = []
    for b in bars:
        ts = datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(et)
        minutes = ts.hour * 60 + ts.minute
        if ts.strftime("%Y-%m-%d") == day and 9 * 60 + 30 <= minutes < 16 * 60:
            rows.append(b)
    if not rows:
        return None
    return {"d": day, "o": round(rows[0]["o"], 2), "h": round(max(b["h"] for b in rows), 2),
            "l": round(min(b["l"] for b in rows), 2), "c": round(rows[-1]["c"], 2)}


def fetch_intraday(tickers, day, days=60, decimals=2):
    """{ticker: {"h4": 4H-Kerzen (auch die laufende), "today": Tageskerze bis jetzt}}."""
    out = {}
    for t, bars in _fetch_30min(tickers, days).items():
        hourly = yahoo_like_hourly(bars)
        rows = hourly_to_4h_rows(hourly, decimals=decimals) if len(hourly) else []
        if rows:
            out[t] = {"h4": rows, "today": regular_session_today(bars, day)}
    return out
