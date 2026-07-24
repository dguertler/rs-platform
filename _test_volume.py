"""Einmaliges Test-Skript — prüft Handelsvolumen am Earnings-Tag vs. Ø-Volumen
der 20 Handelstage davor, für die 5 heute gefundenen Alert-Ticker.
Wird nach dem Test wieder entfernt."""
import yfinance as yf
import pandas as pd

TICKERS = ["THRM", "ACU", "LMT", "ARGX", "DGX"]
TARGET_DATE = "2026-07-23"

for ticker in TICKERS:
    print(f"\n--- {ticker} ---")
    try:
        df = yf.download(ticker, period="2mo", interval="1d",
                          auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Close", "Volume"]].dropna()
        df.index = pd.to_datetime(df.index)
        dates = [d.strftime("%Y-%m-%d") for d in df.index]

        if TARGET_DATE not in dates:
            print(f"  {TARGET_DATE} nicht im Datensatz (letzte Daten: {dates[-1]})")
            continue

        idx = dates.index(TARGET_DATE)
        target_vol = df["Volume"].iloc[idx]

        # Ø-Volumen der 20 Handelstage VOR dem Earnings-Tag (ohne den Tag selbst)
        window = df["Volume"].iloc[max(0, idx - 20):idx]
        avg_vol = window.mean()

        ratio = target_vol / avg_vol if avg_vol > 0 else None
        print(f"  Volumen am {TARGET_DATE}: {target_vol:,.0f}")
        print(f"  Ø-Volumen (20 Tage davor): {avg_vol:,.0f}")
        print(f"  Verhältnis: {ratio:.2f}x" if ratio else "  Verhältnis: n/a")
        print(f"  >= 150% Schwelle: {'JA' if ratio and ratio >= 1.5 else 'NEIN'}")
        print(f"  >= 200% Schwelle: {'JA' if ratio and ratio >= 2.0 else 'NEIN'}")
    except Exception as e:
        print(f"  Fehler: {type(e).__name__}: {e}")
