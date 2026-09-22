"""
Aktualisiert backtest_*.json inkrementell mit neuen Kerzen seit dem letzten bekannten Datum.
Nur Ticker mit vorhandener JSON-Datei werden verarbeitet.

Rolling Window: Der Datenbestand bleibt konstant — kommt ein Tag hinzu,
fällt der älteste weg. Daily/Weekly werden auf 4 Jahre begrenzt (genug für
das 60-Wochen-Lookback in backtest_logic.js, identisch zu trim_backtest.py),
4H auf 730 Tage (yfinance-Maximum für 1h-Daten).
"""
import os, json, time
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

_REPO   = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(_REPO, "data")
PAUSE          = 2   # Sekunden zwischen Tickern
PAUSE_ON_ERROR = 10  # Sekunden nach einem Fehler

CUTOFF_DW = (datetime.now() - timedelta(days=4 * 365)).strftime("%Y-%m-%d")
CUTOFF_4H = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")


def _trim(rows, cutoff):
    """Behält nur Kerzen ab cutoff (Datum-Präfix-Vergleich, auch '... HH:MM')."""
    if not rows:
        return rows, False
    kept = [r for r in rows if str(r.get("d", ""))[:10] >= cutoff]
    return kept, len(kept) != len(rows)


from zoneinfo import ZoneInfo
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
                "o": round(float(row["Open"]), 2),
                "h": round(float(row["High"]), 2),
                "l": round(float(row["Low"]),  2),
                "c": round(c, 2),
            })
        except Exception:
            continue
    return result


OVERLAP_DAYS = 15    # Tage Überlappung beim Daily-Abruf, um Splits zu erkennen
SCALE_TOL    = 0.01  # >1 % Abweichung auf den Überlappungstagen = Split


def scale_drift(stored_rows, fresh_rows):
    """Verhältnis frisch/gespeichert auf gemeinsamen Tagen (Median).

    Nach einem Split liefert yfinance die neuen Kerzen bereinigt, die
    gespeicherte Historie ist es nicht — dann weicht das Verhältnis von 1 ab.
    Gibt None zurück, wenn zu wenig Überlappung für eine Aussage vorliegt.
    """
    stored = {r["d"]: r["c"] for r in stored_rows}
    ratios = [r["c"] / stored[r["d"]]
              for r in fresh_rows
              if r["d"] in stored and stored[r["d"]] > 0]
    if len(ratios) < 3:
        return None
    ratios.sort()
    return ratios[len(ratios) // 2]


def refetch_full(ticker, data):
    """Lädt Weekly und Daily komplett neu und verwirft die 4H-Reihe, die im
    selben Lauf ohnehin neu aufgebaut wird. Einziger verlässlicher Weg zurück
    zu einer durchgehend split-bereinigten Historie."""
    raw_w = yf.download(ticker, period="max", interval="1wk", auto_adjust=True, progress=False)
    raw_d = yf.download(ticker, start=CUTOFF_DW, interval="1d", auto_adjust=True, progress=False)
    rows_w, rows_d = df_to_ohlcv(raw_w), df_to_ohlcv(raw_d)
    if not rows_w or not rows_d:
        return False
    data["ohlcv_w"], data["ohlcv_d"], data["ohlcv_4h"] = rows_w, rows_d, []
    return True


def update_ticker(ticker):
    fname = f"backtest_{ticker.lower().replace('.', '_')}.json"
    fpath = os.path.join(OUT_DIR, fname)
    if not os.path.exists(fpath):
        return "skip"

    with open(fpath) as f:
        data = json.load(f)

    changed = False
    note = None

    # Daily: mit Überlappung laden, damit ein Split auffällt, bevor angehängt wird
    if data.get("ohlcv_d"):
        last_d = data["ohlcv_d"][-1]["d"]
        start  = (datetime.strptime(last_d, "%Y-%m-%d") - timedelta(days=OVERLAP_DAYS)).strftime("%Y-%m-%d")
        raw = yf.download(ticker, start=start, interval="1d", auto_adjust=True, progress=False)
        new_rows = df_to_ohlcv(raw)

        drift = scale_drift(data["ohlcv_d"], new_rows)
        if drift is not None and abs(drift - 1.0) > SCALE_TOL:
            # Split: Anhängen würde einen Bruch in die Reihe schreiben.
            if refetch_full(ticker, data):
                note = f"Split erkannt (Faktor {drift:.4f}) – komplett neu geladen"
                changed = True
                new_rows = []          # Daily steht bereits vollständig, 4H wird unten neu aufgebaut
            else:
                return f"Split erkannt (Faktor {drift:.4f}) – Neuladen fehlgeschlagen"

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
            raw_1h = raw_1h[["Open", "High", "Low", "Close", "Volume"]].copy()
            raw_1h.index = pd.to_datetime(raw_1h.index)
            raw_1h.dropna(subset=["Close"], inplace=True)
            _et = ZoneInfo("America/New_York")
            _ext = pd.Series(
                [ts.astimezone(_et).hour < 9 or
                 (ts.astimezone(_et).hour == 9 and ts.astimezone(_et).minute < 30) or
                 ts.astimezone(_et).hour >= 16
                 for ts in raw_1h.index],
                index=raw_1h.index, dtype=bool
            )
            _prev_low = raw_1h["Low"].shift(1)
            _next_low = raw_1h["Low"].shift(-1)
            _bad_low  = _ext & (raw_1h["Low"] < _prev_low * 0.70) & (raw_1h["Low"] < _next_low * 0.70)
            raw_1h.loc[_bad_low, "Low"] = raw_1h.loc[_bad_low, ["Open","Close"]].min(axis=1)
            raw_4h = raw_1h[["Open","High","Low","Close"]].resample("4h").agg(
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

    # Rolling Window: älteste Kerzen jenseits des Fensters entfernen,
    # damit der Datenbestand trotz täglicher neuer Kerzen konstant bleibt.
    for key, cutoff in (("ohlcv_d", CUTOFF_DW), ("ohlcv_w", CUTOFF_DW),
                        ("ohlcv_4h", CUTOFF_4H)):
        if data.get(key):
            data[key], trimmed = _trim(data[key], cutoff)
            changed = changed or trimmed
    if isinstance(data.get("top20Hist"), list):
        data["top20Hist"], trimmed = _trim(data["top20Hist"], CUTOFF_DW)
        changed = changed or trimmed

    if changed:
        data["generated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(fpath, "w") as f:
            json.dump(data, f)
        return note or "aktualisiert"
    return note or "keine neuen Daten"


def main():
    # Ticker aus allen RS-Quellen sammeln
    sources = ["rs_full.json", "rs_sp500.json"]
    tickers = []
    seen = set()
    for src in sources:
        path = os.path.join(_REPO, "data", src)
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


if __name__ == "__main__":
    main()
