"""
Historische S&P-500-Zusammensetzung (point-in-time) als JSON.

Quelle: github.com/fja05680/sp500 (MIT-Lizenz, (c) Farrell J. Aultman).
Die Datei „S&P 500 Historical Components & Changes (Updated).csv" enthält je
Änderungsdatum die vollständige Liste der Mitglieder. Daraus werden
Mitgliedsintervalle je Ticker gebildet (Klassenaktien mit Yahoo-Schreibweise,
BRK.B → BRK-B).

Ausgabe: data/backtest_history/sp500_membership.json — gleiches Format wie
ndx_membership.json: {"source", "license", "generated", "start", "last_change",
"intervals": {TICKER: [[von, bis], ...]}}  (bis = null → laut letzter Liste Mitglied)

Aufruf:
  git clone --depth 1 https://github.com/fja05680/sp500.git /tmp/sp500
  python3 backtest_history/build_sp500_membership.py /tmp/sp500
"""
import csv
import json
import os
import sys
from datetime import date

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_FILE = os.path.join(_REPO, "data", "backtest_history", "sp500_membership.json")
CSV_NAME = "S&P 500 Historical Components & Changes (Updated).csv"


def yahoo_symbol(ticker):
    return ticker.strip().upper().replace(".", "-")


def load_snapshots(src_dir):
    """[(datum, {ticker, ...}), ...] aufsteigend nach Datum."""
    path = os.path.join(src_dir, CSV_NAME)
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    snaps = [(r["date"], {yahoo_symbol(t) for t in r["tickers"].split(",") if t.strip()}) for r in rows]
    snaps.sort(key=lambda x: x[0])
    if not snaps:
        raise SystemExit(f"Keine Einträge in {path}")
    return snaps


def build_intervals(snaps):
    """Ein Ticker ist ab dem Datum der ersten Liste mit ihm Mitglied, bis zu dem
    Datum der ersten Liste ohne ihn (am Abgangstag nicht mehr)."""
    intervals, opened = {}, {}
    for day, members in snaps:
        for t in list(opened):
            if t not in members:
                intervals.setdefault(t, []).append([opened.pop(t), day])
        for t in members:
            if t not in opened:
                opened[t] = day
    for t, since in opened.items():
        intervals.setdefault(t, []).append([since, None])
    return intervals


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/sp500"
    snaps = load_snapshots(src)
    intervals = build_intervals(snaps)
    payload = {
        "source": "https://github.com/fja05680/sp500",
        "license": "MIT, Copyright (c) 2019-2020 Farrell J. Aultman",
        "generated": date.today().isoformat(),
        "start": snaps[0][0],
        "last_change": snaps[-1][0],
        "intervals": dict(sorted(intervals.items())),
    }
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)
    active = sum(1 for iv in intervals.values() if iv[-1][1] is None)
    print(f"{len(intervals)} Ticker seit {snaps[0][0]}, letzte Änderung {snaps[-1][0]}, "
          f"{active} aktuell im Index → {OUT_FILE}")


if __name__ == "__main__":
    main()
