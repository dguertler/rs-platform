"""
fetch_earnings_history.py — Earnings-Termine mit Uhrzeit (vergangen + kommend).

Schreibt data/earnings_history.json:
  {"updated_at": "...", "tickers": {"AVGO": [["2024-06-12", "amc"], ...]}}
Uhrzeit: "bmo" = vor Börsenbeginn, "amc" = nach Börsenschluss, "unk" = unbekannt.

Grundlage der Earnings-Regel in Backtest (frontend/backtest_logic.js) und Live
(check_exits.py): kein Kauf weniger als 4 Kalendertage vor den Zahlen, offene
Positionen zum Schluss der 14-Uhr-Kerze am letzten Handelstag davor verkaufen.

Universum: Backtest-Titel (data/backtest_history/charts) plus alle Titel der
RS-Dateien und der Watchlist. Ticker mit Jahreszahl (frühere Firma gleichen
Kürzels, z. B. ABC_2019) werden übersprungen — Yahoo liefert dafür die heutige
Firma. Bereits gespeicherte Termine bleiben erhalten (Yahoo kürzt die Historie
gelegentlich), neue Angaben zur Uhrzeit überschreiben alte.

Läuft wöchentlich via .github/workflows/fetch_earnings_history.yml (Yahoo ist aus
Cloud-Sessions gesperrt). Manuell: python3 fetch_earnings_history.py [TICKER ...]
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import yfinance as yf

REQUEST_PAUSE = 0.4
LIMIT = 100          # ~25 Jahre Quartalstermine
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
OUT_PATH = DATA_DIR / "earnings_history.json"
CHARTS = DATA_DIR / "backtest_history" / "charts"
RS_FILES = ["rs_full.json", "rs_sp500.json", "rs_smallcap.json"]


def collect_universe() -> list[str]:
    tickers = set()
    if CHARTS.exists():
        tickers.update(p.stem for p in CHARTS.glob("*.json") if not p.stem.startswith("_"))
    for fn in RS_FILES:
        path = DATA_DIR / fn
        if path.exists():
            tickers.update(e["ticker"] for e in json.loads(path.read_text()).get("data", []) if e.get("ticker"))
    wl = DATA_DIR / "watchlist.json"
    if wl.exists():
        raw = json.loads(wl.read_text())
        items = raw.get("tickers", raw) if isinstance(raw, dict) else raw
        tickers.update(t if isinstance(t, str) else t.get("ticker", "") for t in items)
    return sorted(t for t in tickers if t and not re.search(r"_\d{4}$", t))


def classify(ts) -> str:
    """Uhrzeit des Termins (America/New_York) → bmo / amc / unk."""
    try:
        ts = ts.tz_convert("America/New_York")
    except (TypeError, AttributeError):
        pass
    if ts.hour == 0 and ts.minute == 0:
        return "unk"
    if ts.hour < 12:
        return "bmo"
    if ts.hour >= 15:
        return "amc"
    return "unk"


def fetch(ticker: str) -> list[list[str]] | None:
    for attempt in (1, 2):
        try:
            df = yf.Ticker(ticker).get_earnings_dates(limit=LIMIT)
            if df is None or df.empty:
                return []
            return sorted({ts.strftime("%Y-%m-%d"): [ts.strftime("%Y-%m-%d"), classify(ts)] for ts in df.index}.values())
        except Exception as e:
            if attempt == 1:
                time.sleep(3)
                continue
            print(f"  {ticker}: Fehler — {e}")
            return None


def merge(old: list, new: list) -> list:
    by_day = {d: [d, t] for d, t in old}
    for d, t in new:
        if t != "unk" or d not in by_day:
            by_day[d] = [d, t]
    return [by_day[d] for d in sorted(by_day)]


def main():
    existing = json.loads(OUT_PATH.read_text()).get("tickers", {}) if OUT_PATH.exists() else {}
    tickers = sys.argv[1:] or collect_universe()
    print(f"Earnings-Historie für {len(tickers)} Ticker …")
    result = dict(existing)
    for i, ticker in enumerate(tickers):
        rows = fetch(ticker)
        if rows:
            result[ticker] = merge(existing.get(ticker, []), rows)
        if (i + 1) % 50 == 0:
            print(f"  [{i + 1}/{len(tickers)}] … ({len(result)} mit Terminen)")
        time.sleep(REQUEST_PAUSE)
    OUT_PATH.write_text(json.dumps({
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tickers": dict(sorted(result.items())),
    }, separators=(",", ":")))
    print(f"{len(result)} Ticker mit Terminen — gespeichert: {OUT_PATH}")


if __name__ == "__main__":
    main()
