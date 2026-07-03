"""
fetch_earnings_calendar.py — Earnings-Termin-Cache für die Entry-Sperre (v2).

Schreibt data/earnings_calendar.json: {ticker: naechster_earnings_termin (YYYY-MM-DD)}
nur zukünftige Termine, ältere/vergangene werden nicht aufgenommen.

backend/v2_analysis.py liest diese Datei optional — fehlt sie oder ist ein
Ticker nicht enthalten, wird die Earnings-Sperre für diesen Ticker einfach
übersprungen (fail-safe, nie fail-blocking).

Läuft NICHT automatisch (kein GitHub-Actions-Workflow angelegt) — bewusste
Entscheidung, siehe PROMPT_V2_UMSETZUNG.md Punkt 3: Aktivierung eines
Scheduled-Workflows ist eine Produktions-Infrastruktur-Änderung und obliegt
dem Nutzer.

Nutzung: python3 fetch_earnings_calendar.py
"""
import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import yfinance as yf

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
OUT_PATH = DATA_DIR / "earnings_calendar.json"
MARKET_FILES = ["rs_full.json", "rs_dax.json", "rs_sp500.json", "rs_smallcap.json"]


def collect_universe() -> list[str]:
    """Alle Ticker aus den vier Markt-JSONs, dedupliziert."""
    tickers = set()
    for fn in MARKET_FILES:
        path = DATA_DIR / fn
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for entry in raw.get("data", []):
                t = entry.get("ticker")
                if t:
                    tickers.add(t)
        except Exception as e:
            print(f"  Warnung: {fn} konnte nicht gelesen werden — {e}")
    return sorted(tickers)


def next_earnings_date(ticker: str) -> str | None:
    """Nächster zukünftiger Earnings-Termin (YYYY-MM-DD) oder None."""
    try:
        tk = yf.Ticker(ticker)
        try:
            df = tk.get_earnings_dates(limit=12)
        except Exception:
            df = tk.earnings_dates
        if df is None or df.empty:
            return None
        today = date.today()
        future = [idx.date() for idx in df.index if idx.date() >= today]
        if not future:
            return None
        return min(future).isoformat()
    except Exception as e:
        print(f"  {ticker}: Fehler — {e}")
        return None


def main():
    tickers = collect_universe()
    print(f"Earnings-Kalender für {len(tickers)} Ticker …")
    result = {}
    for i, ticker in enumerate(tickers):
        d = next_earnings_date(ticker)
        if d:
            result[ticker] = d
        if (i + 1) % 50 == 0:
            print(f"  [{i + 1}/{len(tickers)}] …")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps({
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "next_earnings": result,
        }, indent=None),
        encoding="utf-8",
    )
    print(f"\n{len(result)}/{len(tickers)} Ticker mit bekanntem Termin — gespeichert: {OUT_PATH}")


if __name__ == "__main__":
    main()
