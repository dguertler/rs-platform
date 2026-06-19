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
    "grossMargins":            (0.0, 1.0),
    "operatingMargins":        (-1.0, 1.0),
    "profitMargins":           (-1.0, 1.0),
    "returnOnEquity":          (-5.0, 10.0),
    "returnOnInvestedCapital": (-2.0, 5.0),
    "debtToEquity":            (0.0, 2000.0),
    "trailingPE":              (0.0, 2000.0),
    "forwardPE":               (0.0, 500.0),
    "revenueGrowth":           (-1.0, 50.0),
    "beta":                    (-3.0, 10.0),
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


def _calc_roic(ticker_obj) -> float | None:
    """ROIC = NOPAT / Invested Capital. NOPAT = EBIT × (1 - tax_rate).
    Invested Capital = Total Equity + Total Debt - Cash."""
    try:
        inc = ticker_obj.income_stmt
        bal = ticker_obj.balance_sheet
        if inc is None or inc.empty or bal is None or bal.empty:
            return None

        def _get(df, labels):
            for lbl in labels:
                if lbl in df.index:
                    v = df.loc[lbl].iloc[0]
                    if v is not None and str(v) not in ("nan", "None"):
                        return float(v)
            return None

        ebit = _get(inc, ["EBIT", "Operating Income", "Operating Profit"])
        tax  = _get(inc, ["Tax Provision", "Income Tax Expense"])
        pbt  = _get(inc, ["Pretax Income", "Income Before Tax"])
        eq   = _get(bal, ["Stockholders Equity", "Total Stockholders Equity", "Common Stock Equity"])
        debt = _get(bal, ["Total Debt", "Long Term Debt And Capital Lease Obligation",
                           "Current Debt And Capital Lease Obligation"])
        cash = _get(bal, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])

        if ebit is None or eq is None:
            return None

        tax_rate = (tax / pbt) if (tax and pbt and pbt != 0 and tax > 0) else 0.21
        nopat = ebit * (1 - min(tax_rate, 0.40))
        invested_capital = (eq or 0) + (debt or 0) - (cash or 0)
        if invested_capital <= 0:
            return None
        return round(nopat / invested_capital, 4)
    except Exception:
        return None


def _fetch_one(ticker: str) -> dict:
    tk_obj = yf.Ticker(ticker)
    info = tk_obj.info or {}
    roic = _calc_roic(tk_obj)
    raw = {
        "shortName":               info.get("shortName", ticker),
        "sector":                  info.get("sector", "N/A"),
        "industry":                info.get("industry", "N/A"),
        "marketCap":               info.get("marketCap"),
        "currentPrice":            info.get("currentPrice") or info.get("regularMarketPrice"),
        "trailingPE":              info.get("trailingPE"),
        "forwardPE":               info.get("forwardPE"),
        "grossMargins":            info.get("grossMargins"),
        "operatingMargins":        info.get("operatingMargins"),
        "profitMargins":           info.get("profitMargins"),
        "freeCashflow":            info.get("freeCashflow"),
        "totalRevenue":            info.get("totalRevenue"),
        "revenueGrowth":           info.get("revenueGrowth"),
        "dividendYield":           info.get("dividendYield"),
        "debtToEquity":            info.get("debtToEquity"),
        "returnOnEquity":          info.get("returnOnEquity"),
        "returnOnInvestedCapital": roic,
        "priceToBook":             info.get("priceToBook"),
        "fiftyTwoWeekHigh":        info.get("fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow":         info.get("fiftyTwoWeekLow"),
        "beta":                    info.get("beta"),
        "recommendationKey":       info.get("recommendationKey"),
        "targetMeanPrice":         info.get("targetMeanPrice"),
        "numberOfAnalystOpinions": info.get("numberOfAnalystOpinions"),
        "revenueEstimate":         (info.get("revenueEstimate") or
                                    info.get("nextYearRevenue") or
                                    info.get("earningsEstimate")),
    }
    return _validate(raw)


def _load_tickers() -> list:
    tickers = set()
    for path in ("data/rs_full.json", "data/rs_dax.json", "data/rs_sp500.json",
                 "data/rs_smallcap.json"):
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
