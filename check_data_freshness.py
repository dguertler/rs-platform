"""
check_data_freshness.py — Retry-Gate für die täglichen Daten-Workflows
========================================================================
Yahoo Finance liefert den Schlusskurs vom Vortag nicht garantiert sofort
nach Handelsschluss (siehe PLTR-Vorfall 04.08.2026: Batch-Download lieferte
selbst 8h nach Handelsschluss noch keine Montags-Kerze). Die Update- und
Earnings-Alert-Workflows laufen deshalb im Stundentakt und nutzen dieses
Skript als Gate: nur wenn die Daten fürs Zieldatum wirklich da sind, macht
der restliche (teure) Workflow-Schritt Sinn.

Zwei Modi:
  --files a.json b.json ...   Prüft bereits committete RS-JSON-Dateien
                               (Feld 'benchmark_ohlcv', Fallback 'ndx_ohlcv'
                               bzw. erster Ticker-Eintrag).
  --live TICKER1,TICKER2,...  Live-Sample per yfinance (für Workflows ohne
                               eigene Kurs-JSON, z. B. den globalen Scan).

Gibt IMMER "fresh=true"/"fresh=false" im GITHUB_OUTPUT-Format auf stdout aus
und beendet sich mit Exit-Code 0 — ein Fehler beim Prüfen selbst darf den
Retry-Workflow nicht als 'failed' markieren, sondern soll wie "noch nicht
fertig" behandelt werden (nächster stündlicher Versuch holt es nach).
"""
import argparse
import json
import sys
from datetime import date, timedelta


def target_trading_day() -> str:
    d = date.today() - timedelta(days=1)
    if d.weekday() == 6:      # Sonntag
        d -= timedelta(days=2)
    elif d.weekday() == 5:    # Samstag
        d -= timedelta(days=1)
    return d.isoformat()


def last_date_in_file(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  {path}: nicht lesbar ({e})", file=sys.stderr)
        return None

    for key in ("benchmark_ohlcv", "ndx_ohlcv"):
        series = data.get(key)
        if series:
            return series[-1].get("d")

    for entry in data.get("data", []):
        ohlcv = entry.get("ohlcv")
        if ohlcv:
            return ohlcv[-1].get("d")

    return None


def last_date_live(tickers: list[str]) -> str | None:
    try:
        import yfinance as yf
    except Exception as e:
        print(f"  yfinance nicht verfügbar: {e}", file=sys.stderr)
        return None

    try:
        raw = yf.download(tickers, period="5d", interval="1d",
                           auto_adjust=True, progress=False)
        if raw.empty:
            return None
        close = raw["Close"]
        if hasattr(close, "columns"):
            last_dates = [close[t].dropna().index[-1] for t in close.columns
                          if close[t].dropna().size]
        else:
            last_dates = [close.dropna().index[-1]] if close.dropna().size else []
        if not last_dates:
            return None
        return max(last_dates).strftime("%Y-%m-%d")
    except Exception as e:
        print(f"  Live-Check fehlgeschlagen: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="", help="Zieldatum YYYY-MM-DD (Default: Vortag, wochenend-bereinigt)")
    parser.add_argument("--files", nargs="*", default=[], help="RS-JSON-Dateien, die alle das Zieldatum enthalten müssen")
    parser.add_argument("--live", default="", help="Kommagetrennte Ticker für einen Live-yfinance-Sample-Check")
    args = parser.parse_args()

    target = args.target.strip() or target_trading_day()
    print(f"Zieldatum: {target}", file=sys.stderr)

    fresh = True

    for path in args.files:
        last = last_date_in_file(path)
        ok = last is not None and last >= target
        print(f"  {path}: letzte Kerze {last or 'n/a'} — {'OK' if ok else 'veraltet'}", file=sys.stderr)
        fresh = fresh and ok

    if args.live.strip():
        tickers = [t.strip() for t in args.live.split(",") if t.strip()]
        last = last_date_live(tickers)
        ok = last is not None and last >= target
        print(f"  live[{','.join(tickers)}]: letzte Kerze {last or 'n/a'} — {'OK' if ok else 'veraltet'}", file=sys.stderr)
        fresh = fresh and ok

    if not args.files and not args.live.strip():
        print("Weder --files noch --live angegeben — gilt als nicht frisch.", file=sys.stderr)
        fresh = False

    print(f"target={target}")
    print(f"fresh={'true' if fresh else 'false'}")


if __name__ == "__main__":
    main()
