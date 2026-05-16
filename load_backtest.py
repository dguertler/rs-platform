import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import os
import yfinance as yf
import pandas as pd
import json
from datetime import datetime

TICKER   = os.environ.get("BACKTEST_TICKER", "SNDK")
OUT_FILE = f"backtest_{TICKER.lower().replace('.', '_')}.json"

print(f"Lade {TICKER} Daten von yfinance ...")

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
                "c": round(c, 2)
            })
        except Exception:
            continue
    return result

# ── Weekly (max verfügbar) ───────────────────────────────────────────────────
print("  Weekly (period=max) ...")
raw_w   = yf.download(TICKER, period="max", interval="1wk", auto_adjust=True, progress=False)
ohlcv_w = df_to_ohlcv(raw_w)
print(f"    {len(ohlcv_w)} Kerzen  "
      f"({ohlcv_w[0]['d'] if ohlcv_w else 'N/A'} – {ohlcv_w[-1]['d'] if ohlcv_w else 'N/A'})")

# ── Daily – genug um ALLE Weekly-Kerzen abzudecken ──────────────────────────
# Startpunkt = erster Wochentag - 90 Puffer-Tage (für Swing-Analyse)
if ohlcv_w:
    from datetime import timedelta
    first_week = datetime.strptime(ohlcv_w[0]['d'], "%Y-%m-%d")
    daily_start = (first_week - timedelta(days=90)).strftime("%Y-%m-%d")
else:
    daily_start = "2020-01-01"

print(f"  Daily (ab {daily_start}) ...")
raw_d   = yf.download(TICKER, start=daily_start, interval="1d", auto_adjust=True, progress=False)
ohlcv_d = df_to_ohlcv(raw_d)
print(f"    {len(ohlcv_d)} Kerzen  "
      f"({ohlcv_d[0]['d'] if ohlcv_d else 'N/A'} – {ohlcv_d[-1]['d'] if ohlcv_d else 'N/A'})")

# ── 4H via 1H (letzte 730 Tage – yfinance-Maximum) ──────────────────────────
print("  4H via 1H (period=730d) ...")
ohlcv_4h = []
try:
    raw_1h = yf.download(
        TICKER, period="730d", interval="1h",
        prepost=True, auto_adjust=True, progress=False
    )
    if not raw_1h.empty:
        if isinstance(raw_1h.columns, pd.MultiIndex):
            raw_1h.columns = raw_1h.columns.get_level_values(0)
        raw_1h = raw_1h[["Open", "High", "Low", "Close"]].dropna()
        raw_1h.index = pd.to_datetime(raw_1h.index)
        raw_4h = raw_1h.resample("4h", offset="1h30min").agg({
            "Open":  "first",
            "High":  "max",
            "Low":   "min",
            "Close": "last"
        }).dropna()
        ohlcv_4h = df_to_ohlcv(raw_4h, fmt="%Y-%m-%d %H:%M")
        print(f"    {len(ohlcv_4h)} Kerzen  "
              f"({ohlcv_4h[0]['d'] if ohlcv_4h else 'N/A'} – "
              f"{ohlcv_4h[-1]['d'] if ohlcv_4h else 'N/A'})")
    else:
        print("    Keine 1H-Daten verfügbar")
except Exception as e:
    print(f"    Fehler: {e}")

# ── Speichern ────────────────────────────────────────────────────────────────
output = {
    "ticker":    TICKER,
    "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "ohlcv_w":   ohlcv_w,
    "ohlcv_d":   ohlcv_d,
    "ohlcv_4h":  ohlcv_4h,
}

with open(OUT_FILE, "w") as f:
    json.dump(output, f)

print(f"\nGespeichert: {OUT_FILE}")
print(f"  Weekly: {len(ohlcv_w)} Kerzen")
print(f"  Daily:  {len(ohlcv_d)} Kerzen")
print(f"  4H:     {len(ohlcv_4h)} Kerzen")
