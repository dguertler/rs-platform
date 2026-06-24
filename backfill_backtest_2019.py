"""
Erweitert alle bestehenden backtest_*.json-Dateien rückwärts bis 2018-12-01.
Lädt nur die fehlenden Kerzen (vor dem aktuellen Startdatum) und prepended sie.
Bestehende Daten werden nicht verändert.

Aufruf: python3 backfill_backtest_2019.py
"""
import os, json, time
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_REPO   = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(_REPO, "data")
TARGET_START = "2018-12-01"
PAUSE        = 3
PAUSE_ERROR  = 10
_berlin = ZoneInfo("Europe/Berlin")


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
            if "%H" in fmt and dt.tzinfo:
                dt = dt.astimezone(_berlin)
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


def backfill_ticker(ticker, fpath):
    with open(fpath) as f:
        data = json.load(f)

    changed = False

    # Weekly
    current_w_start = data["ohlcv_w"][0]["d"] if data.get("ohlcv_w") else None
    if current_w_start and current_w_start > TARGET_START:
        end_date = (datetime.strptime(current_w_start, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        raw = yf.download(ticker, start=TARGET_START, end=end_date,
                          interval="1wk", auto_adjust=True, progress=False)
        new_rows = df_to_ohlcv(raw)
        if new_rows:
            known = {r["d"] for r in data["ohlcv_w"]}
            prepend = [r for r in new_rows if r["d"] not in known and r["d"] >= TARGET_START]
            if prepend:
                data["ohlcv_w"] = prepend + data["ohlcv_w"]
                changed = True

    # Daily
    current_d_start = data["ohlcv_d"][0]["d"] if data.get("ohlcv_d") else None
    if current_d_start and current_d_start > TARGET_START:
        end_date = (datetime.strptime(current_d_start, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        raw = yf.download(ticker, start=TARGET_START, end=end_date,
                          interval="1d", auto_adjust=True, progress=False)
        new_rows = df_to_ohlcv(raw)
        if new_rows:
            known = {r["d"] for r in data["ohlcv_d"]}
            prepend = [r for r in new_rows if r["d"] not in known and r["d"] >= TARGET_START]
            if prepend:
                data["ohlcv_d"] = prepend + data["ohlcv_d"]
                changed = True

    if changed:
        data["generated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(fpath, "w") as f:
            json.dump(data, f)
        w_start = data["ohlcv_w"][0]["d"] if data.get("ohlcv_w") else "?"
        d_start = data["ohlcv_d"][0]["d"] if data.get("ohlcv_d") else "?"
        return f"ok  W_start={w_start}  D_start={d_start}"
    return "bereits aktuell"


# Ticker-Liste: nur Ticker mit vorhandener JSON
files = sorted(f for f in os.listdir(OUT_DIR) if f.startswith("backtest_") and f.endswith(".json"))
print(f"\nBackfill → 2019 · {len(files)} Dateien\n{'='*60}")

errors = []
for i, fname in enumerate(files, 1):
    fpath = os.path.join(OUT_DIR, fname)
    ticker = fname[len("backtest_"):-len(".json")].upper().replace("_", ".")
    try:
        result = backfill_ticker(ticker, fpath)
        print(f"[{i:3}/{len(files)}] {ticker:<14} {result}")
        if result.startswith("ok"):
            time.sleep(PAUSE)
    except Exception as e:
        print(f"[{i:3}/{len(files)}] {ticker:<14} FEHLER: {e}")
        errors.append(ticker)
        time.sleep(PAUSE_ERROR)

print(f"\n{'='*60}")
print(f"Fertig. Fehler bei {len(errors)} Ticker: {errors if errors else '–'}")
if errors:
    raise SystemExit(1)
