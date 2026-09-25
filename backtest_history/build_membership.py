"""
Historische NASDAQ-100-Zusammensetzung (point-in-time) als JSON.

Quelle: github.com/jmccarrell/n100tickers (MIT-Lizenz, (c) Jeff McCarrell).
Das Projekt hält je Jahr eine YAML-Datei mit dem Stand am 1. Januar und allen
Zu- und Abgängen mit Stichtag. Abdeckung ab 01.02.2007 — für 2000–2006 gibt es
keine freie, tagesgenaue Quelle, deshalb beginnt der historische Backtest 2007.

Ausgabe: data/backtest_history/ndx_membership.json
  {"source", "license", "start", "end",
   "intervals": {TICKER: [[von, bis], ...]}}   bis = null → heute noch im Index
Ein Ticker ist am Tag d Mitglied, wenn von <= d < bis (am Abgangstag nicht mehr).
Ticker-Symbole sind point-in-time (FB bis 2022-06-08, danach META).

Aufruf:
  git clone --depth 1 https://github.com/jmccarrell/n100tickers.git /tmp/n100tickers
  python3 backtest_history/build_membership.py /tmp/n100tickers
"""
import glob
import json
import os
import sys
from datetime import date

import yaml

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_FILE = os.path.join(_REPO, "data", "backtest_history", "ndx_membership.json")
YAML_SUBDIR = os.path.join("src", "nasdaq_100_ticker_history")


def load_years(src_dir):
    """Jahr → (Stand 1. Januar, sortierte Liste (datum, zugänge, abgänge)).

    BaseLoader ist Pflicht: der Standard-Loader macht aus dem Ticker ON
    (ON Semiconductor) den Wahrheitswert True.
    """
    years = {}
    for path in sorted(glob.glob(os.path.join(src_dir, YAML_SUBDIR, "n100-ticker-changes-*.yaml"))):
        with open(path, encoding="utf-8") as f:
            doc = yaml.load(f, Loader=yaml.BaseLoader)
        changes = []
        for day, ch in sorted((doc.get("changes") or {}).items()):
            changes.append((day, ch.get("union") or [], ch.get("difference") or []))
        years[int(doc["year"])] = (doc["tickers_on_Jan_1"], changes)
    if not years:
        raise SystemExit(f"Keine YAML-Dateien unter {src_dir}/{YAML_SUBDIR} gefunden.")
    return years


def build_intervals(years):
    """Zu-/Abgänge der Reihe nach abspielen und Mitgliedschaftsintervalle bilden."""
    first_year = min(years)
    start = f"{first_year}-02-01" if first_year == 2007 else f"{first_year}-01-01"
    current = set(years[first_year][0])
    opened = {t: start for t in current}
    intervals = {}

    def close(ticker, day):
        intervals.setdefault(ticker, []).append([opened.pop(ticker), day])

    for year in sorted(years):
        jan1, changes = years[year]
        if year != first_year and set(jan1) != current:
            # Die Jahresdateien sollen lückenlos aneinander anschließen; ein
            # Bruch hieße, dass Zu-/Abgänge fehlen — lieber abbrechen als raten.
            diff = sorted(set(jan1) ^ current)
            raise SystemExit(f"Stand 1.1.{year} passt nicht zum Vorjahr: {diff}")
        for day, added, removed in changes:
            if day < start:
                continue
            for t in removed:
                if t in current:
                    current.discard(t)
                    close(t, day)
            for t in added:
                if t not in current:
                    current.add(t)
                    opened[t] = day

    for t, since in opened.items():
        intervals.setdefault(t, []).append([since, None])
    return start, intervals


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/n100tickers"
    years = load_years(src)
    start, intervals = build_intervals(years)
    payload = {
        "source": "https://github.com/jmccarrell/n100tickers",
        "license": "MIT, Copyright (c) 2021 - 2025 Jeff McCarrell",
        "generated": date.today().isoformat(),
        "start": start,
        "intervals": dict(sorted(intervals.items())),
    }
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)
    active = sum(1 for iv in intervals.values() if iv[-1][1] is None)
    print(f"{len(intervals)} Ticker seit {start}, davon {active} aktuell im Index → {OUT_FILE}")


if __name__ == "__main__":
    main()
