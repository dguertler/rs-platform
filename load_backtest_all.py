"""
Lädt backtest_*.json für alle Ticker aus rs_full.json, rs_sp500.json, rs_dax.json.
Bereits vorhandene Dateien werden übersprungen (Resume-fähig).
Aufruf: python3 load_backtest_all.py
"""
import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import os, json, time
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

PAUSE_BETWEEN   = 3   # Sekunden zwischen Tickern
PAUSE_ON_ERROR  = 10  # Sekunden nach einem Fehler


def df_to_ohlcv(df, fmt="%Y-%m-%d"):
    if df is None or df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    result = []
    for dt, row in df.iterrows():
        try:
            c = float(row["Close"])
            if pd.isna(c):
                continue
            result.append({
                "d": dt.strftime(fmt),
                "o": round(float(row["Open"]),  2),
                "h": round(float(row["High"]),  2),
                "l": round(float(row["Low"]),   2),
                "c": round(c, 2),
            })
        except Exception:
            continue
    return result


def load_ticker(ticker):
    out_file = os.path.join(OUT_DIR, f"backtest_{ticker.lower().replace('.', '_')}.json")
    if os.path.exists(out_file):
        return "skip"

    try:
        # Weekly (max)
        raw_w   = yf.download(ticker, period="max", interval="1wk",
                               auto_adjust=True, progress=False)
        ohlcv_w = df_to_ohlcv(raw_w)
        if not ohlcv_w:
            return "no_data"

        # Daily – ab erstem Weekly-Datum minus 90 Tage Puffer
        first_week  = datetime.strptime(ohlcv_w[0]["d"], "%Y-%m-%d")
        daily_start = (first_week - timedelta(days=90)).strftime("%Y-%m-%d")
        raw_d   = yf.download(ticker, start=daily_start, interval="1d",
                               auto_adjust=True, progress=False)
        ohlcv_d = df_to_ohlcv(raw_d)

        # 4H via 1H (yfinance-Maximum: 730 Tage)
        ohlcv_4h = []
        try:
            raw_1h = yf.download(ticker, period="730d", interval="1h",
                                  prepost=True, auto_adjust=True, progress=False)
            if not raw_1h.empty:
                if isinstance(raw_1h.columns, pd.MultiIndex):
                    raw_1h.columns = raw_1h.columns.get_level_values(0)
                raw_1h = raw_1h[["Open", "High", "Low", "Close"]].dropna()
                raw_1h.index = pd.to_datetime(raw_1h.index)
                raw_4h = raw_1h.resample("4h", offset="1h30min").agg({
                    "Open":  "first",
                    "High":  "max",
                    "Low":   "min",
                    "Close": "last",
                }).dropna()
                ohlcv_4h = df_to_ohlcv(raw_4h, fmt="%Y-%m-%d %H:%M")
        except Exception:
            pass  # 4H-Fehler ist nicht kritisch

        output = {
            "ticker":    ticker,
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "ohlcv_w":   ohlcv_w,
            "ohlcv_d":   ohlcv_d,
            "ohlcv_4h":  ohlcv_4h,
        }
        with open(out_file, "w") as f:
            json.dump(output, f)
        return f"ok  W={len(ohlcv_w)} D={len(ohlcv_d)} 4H={len(ohlcv_4h)}"

    except Exception as e:
        return f"error: {e}"


# ── Ticker aus allen drei Indizes sammeln ─────────────────────────────────────
sources = ["rs_full.json", "rs_sp500.json", "rs_dax.json"]
tickers = []
seen = set()
for src in sources:
    path = os.path.join(OUT_DIR, src)
    if not os.path.exists(path):
        print(f"⚠  {src} nicht gefunden, übersprungen")
        continue
    data = json.load(open(path))
    for entry in data.get("data", []):
        t = entry["ticker"]
        if t not in seen:
            tickers.append(t)
            seen.add(t)

total   = len(tickers)
skipped = sum(1 for t in tickers
              if os.path.exists(os.path.join(OUT_DIR,
                 f"backtest_{t.lower().replace('.','_')}.json")))

print(f"\n{'='*60}")
print(f"Backtest-Bulk-Download · {total} Ticker")
print(f"Bereits vorhanden: {skipped}  →  Noch zu laden: {total - skipped}")
print(f"{'='*60}\n")

failed = []
for i, ticker in enumerate(tickers, 1):
    result = load_ticker(ticker)
    status = "·" if result == "skip" else ("✓" if result.startswith("ok") else "✗")
    print(f"[{i:3}/{total}] {status} {ticker:<12} {result}")

    if result.startswith("error"):
        failed.append(ticker)
        time.sleep(PAUSE_ON_ERROR)
    elif result != "skip":
        time.sleep(PAUSE_BETWEEN)

print(f"\n{'='*60}")
print(f"Fertig. Fehler bei {len(failed)} Ticker: {failed if failed else '–'}")
print(f"{'='*60}")
