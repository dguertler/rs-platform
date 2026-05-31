"""
fetch_fundamentals.py — Wöchentlicher Fundamentaldaten-Fetch für alle RS-Ticker
=================================================================================
Wird von GitHub Actions jeden Montag ausgeführt (nach den RS-Updates).
Liest alle Ticker aus den drei RS-JSONs, fetcht yfinance-Daten und
schreibt data/fundamentals.json in die Repo.
Kein API-Key erforderlich.
"""

import json
from datetime import datetime
from pathlib import Path

import yfinance as yf

FUNDAMENTALS_PATH = Path("data/fundamentals.json")

PLAUSIBILITY = {
    "grossMargins":     (0.0, 1.0),
    "operatingMargins": (-1.0, 1.0),
    "profitMargins":    (-1.0, 1.0),
    "returnOnEquity":   (-5.0, 10.0),
    "debtToEquity":     (0.0, 2000.0),
    "trailingPE":       (0.0, 2000.0),
    "forwardPE":        (0.0, 500.0),
    "revenueGrowth":    (-1.0, 50.0),
    "beta":             (-3.0, 10.0),
}


def _validate(data: dict) -> dict:
    cleaned = {}
    for key, value in data.items():
        if value is None:
            cleaned[key] = "N/A"
            continue
        if key in PLAUSIBILITY:
            try:
                lo, hi = PLAUSIBILITY[key]
                if not (lo <= float(value) <= hi):
                    cleaned[key] = f"UNGÜLTIG ({value})"
                    continue
            except (TypeError, ValueError):
                cleaned[key] = "N/A"
                continue
        cleaned[key] = value
    return cleaned


def _fetch_one(ticker: str) -> dict:
    info = yf.Ticker(ticker).info or {}
    raw = {
        "shortName":         info.get("shortName", ticker),
        "sector":            info.get("sector", "N/A"),
        "industry":          info.get("industry", "N/A"),
        "marketCap":         info.get("marketCap"),
        "currentPrice":      info.get("currentPrice") or info.get("regularMarketPrice"),
        "trailingPE":        info.get("trailingPE"),
        "forwardPE":         info.get("forwardPE"),
        "grossMargins":      info.get("grossMargins"),
        "operatingMargins":  info.get("operatingMargins"),
        "profitMargins":     info.get("profitMargins"),
        "freeCashflow":      info.get("freeCashflow"),
        "totalRevenue":      info.get("totalRevenue"),
        "revenueGrowth":     info.get("revenueGrowth"),
        "dividendYield":     info.get("dividendYield"),
        "debtToEquity":      info.get("debtToEquity"),
        "returnOnEquity":    info.get("returnOnEquity"),
        "priceToBook":       info.get("priceToBook"),
        "fiftyTwoWeekHigh":  info.get("fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow":   info.get("fiftyTwoWeekLow"),
        "beta":              info.get("beta"),
        "recommendationKey": info.get("recommendationKey"),
        "targetMeanPrice":   info.get("targetMeanPrice"),
    }
    return _validate(raw)


def _load_tickers() -> list:
    tickers = set()
    for path in ("data/rs_full.json", "data/rs_dax.json", "data/rs_sp500.json"):
        p = Path(path)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                for entry in json.load(f).get("data", []):
                    t = entry.get("ticker", "").upper().strip()
                    if t:
                        tickers.add(t)
    return sorted(tickers)


def main():
    tickers = _load_tickers()
    print(f"Ticker geladen: {len(tickers)}")

    result = {}
    errors = []
    for i, ticker in enumerate(tickers, 1):
        print(f"  [{i}/{len(tickers)}] {ticker} ...", end=" ", flush=True)
        try:
            data = _fetch_one(ticker)
            if data:
                result[ticker] = data
                print("OK")
            else:
                print("leer")
                errors.append(ticker)
        except Exception as e:
            print(f"FEHLER: {e}")
            errors.append(ticker)

    FUNDAMENTALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "updated_at": datetime.utcnow().isoformat(),
        "count":      len(result),
        "tickers":    result,
    }
    with open(FUNDAMENTALS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nGespeichert: {FUNDAMENTALS_PATH} ({len(result)} Ticker)")
    if errors:
        print(f"Fehler bei {len(errors)} Ticker(n): {', '.join(errors)}")


if __name__ == "__main__":
    main()
