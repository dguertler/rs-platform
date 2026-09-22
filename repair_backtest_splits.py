"""
Findet nicht bereinigte Aktiensplits in data/backtest_*.json und lädt die
betroffenen Ticker sauber neu.

Hintergrund: update_backtest_daily.py hängt nur neue Kerzen an. Kommt es zu
einem Split, liefert yfinance die neuen Kerzen bereinigt, die gespeicherte
Historie bleibt aber unbereinigt — mitten in der Zeitreihe entsteht ein Bruch.

Die rs_*.json werden täglich komplett neu geladen und sind daher sauber. Sie
dienen als Referenz: Ein Sprung, den nur die Backtest-Datei zeigt, ist ein
Split-Artefakt; ein Sprung, den auch die Referenz zeigt (z. B. MRNA am
19.08.2026), ist eine echte Kursbewegung.

Repariert wird NICHT durch Umskalieren: Daily, Weekly und 4H brechen an
unterschiedlichen Stellen (bei KLAC etwa bricht 4H an einem anderen Datum als
Daily), ein pauschaler Faktor würde korrekte Reihen beschädigen. Stattdessen
werden betroffene Ticker komplett neu geladen.

Aufruf:
  python3 repair_backtest_splits.py             # nur prüfen und berichten
  python3 repair_backtest_splits.py --refetch   # betroffene Ticker neu laden
"""
import glob
import json
import os
import sys
from datetime import datetime

_REPO = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_REPO, "data")

RS_FILES = ["rs_full.json", "rs_sp500.json", "rs_dax.json", "rs_smallcap.json"]
JUMP_LOW, JUMP_HIGH = 0.55, 1.8   # Verdachtsschwelle für einen Split
GENUINE_TOL = 0.10                # Referenz zeigt denselben Sprung (±10 %) → echt
SERIES_KEYS = ["ohlcv_d", "ohlcv_w", "ohlcv_4h"]


def load_reference():
    """ticker → {datum: {o, c}} aus den täglich neu geladenen RS-Dateien."""
    ref = {}
    for name in RS_FILES:
        path = os.path.join(DATA_DIR, name)
        if not os.path.exists(path):
            continue
        with open(path) as f:
            payload = json.load(f)
        for entry in payload.get("data", []):
            rows = entry.get("ohlcv") or []
            if rows:
                ref.setdefault(entry["ticker"], {}).update(
                    {r["d"]: {"o": r["o"], "c": r["c"]} for r in rows}
                )
    return ref


def find_jumps(rows):
    """Sprünge zwischen Vortagesschluss und Eröffnung außerhalb der Schwellen."""
    jumps = []
    prev = None
    for row in rows:
        if prev and prev["c"] > 0:
            ratio = row["o"] / prev["c"]
            if ratio < JUMP_LOW or ratio > JUMP_HIGH:
                jumps.append({"date": str(row["d"])[:10], "ratio": ratio,
                              "prev_date": str(prev["d"])[:10]})
        prev = row
    return jumps


def is_genuine_move(jump, ref_prices):
    """True, wenn die saubere Referenz denselben Sprung zeigt. None = nicht prüfbar."""
    before = ref_prices.get(jump["prev_date"])
    after = ref_prices.get(jump["date"])
    if not before or not after or before["c"] <= 0:
        return None
    ref_ratio = after["o"] / before["c"]
    return abs(ref_ratio - jump["ratio"]) <= GENUINE_TOL * max(1.0, jump["ratio"])


def inspect_file(path, reference):
    """Klassifiziert auf Ticker-Ebene anhand der TAGESREIHE — nur sie lässt sich
    Kerze für Kerze gegen die Referenz prüfen. Ein Split zeigt sich ohnehin in
    allen drei Reihen; Weekly und 4H werden nur nachrichtlich mitgeführt, weil
    ihre Kerzengrenzen nicht zu den Referenztagen passen."""
    with open(path) as f:
        data = json.load(f)
    ticker = data.get("ticker")
    if not ticker:
        return None

    ref_prices = reference.get(ticker, {})
    broken, genuine, unverifiable = [], [], []
    for jump in find_jumps(data.get("ohlcv_d") or []):
        label = f"{jump['date']} (Faktor {jump['ratio']:.3f})"
        verdict = is_genuine_move(jump, ref_prices)
        if verdict is True:
            genuine.append(label)
        elif verdict is None:
            unverifiable.append(label)
        else:
            broken.append(label)

    if not (broken or unverifiable):
        return None
    other = [key for key in SERIES_KEYS if key != "ohlcv_d" and find_jumps(data.get(key) or [])]
    return {"ticker": ticker, "path": path, "broken": broken,
            "genuine": genuine, "unverifiable": unverifiable, "other_series": other}


def _df_to_ohlcv(df):
    """Wie in load_backtest_all.py — hier lokal, damit der Import dort keinen
    Modul-Code (pip install, Ticker-Sammellauf) auslöst."""
    import pandas as pd
    if df is None or df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    rows = []
    for stamp, row in df.iterrows():
        try:
            close = float(row["Close"])
            if pd.isna(close):
                continue
            rows.append({"d": stamp.strftime("%Y-%m-%d"),
                         "o": round(float(row["Open"]), 2),
                         "h": round(float(row["High"]), 2),
                         "l": round(float(row["Low"]), 2),
                         "c": round(close, 2)})
        except Exception:
            continue
    return rows


def refetch(ticker, path):
    """Lädt einen Ticker komplett neu — der einzige verlässliche Weg zurück
    zu einer durchgehend split-bereinigten Reihe."""
    import yfinance as yf
    df_to_ohlcv = _df_to_ohlcv

    raw_w = yf.download(ticker, period="max", interval="1wk", auto_adjust=True, progress=False)
    raw_d = yf.download(ticker, period="4y", interval="1d", auto_adjust=True, progress=False)
    if raw_w.empty or raw_d.empty:
        return f"FEHLER {ticker}: kein Kursabruf möglich"

    with open(path) as f:
        data = json.load(f)
    data["ohlcv_w"] = df_to_ohlcv(raw_w)
    data["ohlcv_d"] = df_to_ohlcv(raw_d)
    data["ohlcv_4h"] = []   # wird vom nächsten update_backtest_daily.py-Lauf neu aufgebaut
    data["generated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(path, "w") as f:
        json.dump(data, f)
    return f"neu geladen {ticker}: W={len(data['ohlcv_w'])} D={len(data['ohlcv_d'])} 4H=0 (wird nachgezogen)"


def main():
    do_refetch = "--refetch" in sys.argv
    reference = load_reference()
    print(f"Referenzkurse für {len(reference)} Ticker geladen.\n")

    affected = []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "backtest_*.json"))):
        try:
            finding = inspect_file(path, reference)
        except Exception as exc:
            print(f"  FEHLER {os.path.basename(path)}: {exc}")
            continue
        if finding:
            affected.append(finding)

    if not affected:
        print("Keine unbereinigten Splits gefunden.")
        return

    for f in affected:
        print(f"{f['ticker']}:")
        for label in f["broken"]:
            print(f"    SPLIT-ARTEFAKT   {label}")
        for label in f["unverifiable"]:
            print(f"    NICHT PRÜFBAR    {label}  (keine Referenz in den RS-Daten)")
        for label in f["genuine"]:
            print(f"    echte Bewegung   {label}")
        if f["other_series"]:
            print(f"    betroffen außerdem: {', '.join(f['other_series'])}")

    needs_fix = [f for f in affected if f["broken"] or f["unverifiable"]]
    print(f"\n{len(needs_fix)} Ticker brauchen ein vollständiges Neuladen: "
          + ", ".join(f["ticker"] for f in needs_fix))
    if not do_refetch:
        print("Mit --refetch neu laden (benötigt Netzzugang zu Yahoo Finance).")
        return
    for f in needs_fix:
        print("  " + refetch(f["ticker"], f["path"]))


if __name__ == "__main__":
    main()
