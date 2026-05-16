"""
Aktualisiert backtest_*.json inkrementell mit neuen Kerzen seit dem letzten bekannten Datum.
Nur Ticker mit vorhandener JSON-Datei werden verarbeitet.
"""
import os, json, time
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
PAUSE          = 2   # Sekunden zwischen Tickern
PAUSE_ON_ERROR = 10  # Sekunden nach einem Fehler


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
                "o": round(float(row["Open"]), 2),
                "h": round(float(row["High"]), 2),
                "l": round(float(row["Low"]),  2),
                "c": round(c, 2),
            })
        except Exception:
            continue
    return result


def update_ticker(ticker):
    fname = f"backtest_{ticker.lower().replace('.', '_')}.json"
    fpath = os.path.join(OUT_DIR, fname)
    if not os.path.exists(fpath):
        return "skip"

    with open(fpath) as f:
        data = json.load(f)

    changed = False

    # Daily: nur neue Kerzen seit letztem bekannten Tag laden
    if data.get("ohlcv_d"):
        last_d = data["ohlcv_d"][-1]["d"]
        start  = (datetime.strptime(last_d, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        raw = yf.download(ticker, start=start, interval="1d", auto_adjust=True, progress=False)
        new_rows = df_to_ohlcv(raw)
        if new_rows:
            known = {r["d"] for r in data["ohlcv_d"]}
            added = [r for r in new_rows if r["d"] not in known]
            if added:
                data["ohlcv_d"].extend(added)
                changed = True

    # Weekly: nur neue Wochen-Kerzen laden
    if data.get("ohlcv_w"):
        last_w = data["ohlcv_w"][-1]["d"]
        start  = (datetime.strptime(last_w, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        raw = yf.download(ticker, start=start, interval="1wk", auto_adjust=True, progress=False)
        new_rows = df_to_ohlcv(raw)
        if new_rows:
            known = {r["d"] for r in data["ohlcv_w"]}
            added = [r for r in new_rows if r["d"] not in known]
            if added:
                data["ohlcv_w"].extend(added)
                changed = True

    # 4H: yfinance liefert max. 730 Tage → re-fetch und neue Einträge mergen
    try:
        raw_1h = yf.download(ticker, period="730d", interval="1h",
                              prepost=True, auto_adjust=True, progress=False)
        if not raw_1h.empty:
            if isinstance(raw_1h.columns, pd.MultiIndex):
                raw_1h.columns = raw_1h.columns.get_level_values(0)
            raw_1h = raw_1h[["Open", "High", "Low", "Close"]].dropna()
            raw_1h.index = pd.to_datetime(raw_1h.index)
            raw_4h = raw_1h.resample("4h", offset="1h30min").agg(
                {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
            ).dropna()
            new_rows = df_to_ohlcv(raw_4h, fmt="%Y-%m-%d %H:%M")
            if new_rows:
                known = {r["d"] for r in data.get("ohlcv_4h", [])}
                added = [r for r in new_rows if r["d"] not in known]
                if added:
                    data["ohlcv_4h"] = sorted(
                        data.get("ohlcv_4h", []) + added,
                        key=lambda x: x["d"]
                    )
                    changed = True
    except Exception:
        pass  # 4H-Fehler nicht kritisch

    if changed:
        data["generated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(fpath, "w") as f:
            json.dump(data, f)
        return "aktualisiert"
    return "keine neuen Daten"


# Ticker aus allen RS-Quellen sammeln
sources = ["rs_full.json", "rs_sp500.json", "rs_dax.json"]
tickers = []
seen = set()
for src in sources:
    path = os.path.join(OUT_DIR, src)
    if not os.path.exists(path):
        print(f"  {src} nicht gefunden, übersprungen")
        continue
    raw = json.load(open(path))
    for entry in raw.get("data", []):
        t = entry["ticker"]
        if t not in seen:
            tickers.append(t)
            seen.add(t)

# Nur Ticker mit vorhandener JSON verarbeiten
to_update = [t for t in tickers
             if os.path.exists(os.path.join(OUT_DIR,
                f"backtest_{t.lower().replace('.', '_')}.json"))]

print(f"\nBacktest-Update: {len(to_update)} / {len(tickers)} Ticker haben JSON-Dateien\n")

errors = []
for i, ticker in enumerate(to_update, 1):
    result = update_ticker(ticker)
    print(f"[{i:3}/{len(to_update)}] {ticker:<12} {result}")
    if "error" in result.lower():
        errors.append(ticker)
        time.sleep(PAUSE_ON_ERROR)
    else:
        time.sleep(PAUSE)

print(f"\nFertig. Fehler bei {len(errors)} Ticker: {errors if errors else '–'}")
if errors:
    raise SystemExit(1)
