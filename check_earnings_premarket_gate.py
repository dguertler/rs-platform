"""
check_earnings_premarket_gate.py — billiges Vorab-Gate für den Live-Vorbörsen-Check
======================================================================================
Läuft ohne externe Abhängigkeiten (kein yfinance, kein pip install) alle 15 Minuten
tagsüber. Prüft nur, ob laut data/earnings_calendar.json überhaupt ein getrackter
Ticker HEUTE oder am letzten Handelstag davor (AMC-Meldung von gestern Abend) einen
Earnings-Termin hat. Nur wenn ja, lohnt sich der teure Live-Kurs-Check
(check_earnings_premarket.py) mit yfinance-Installation.

Gibt has_candidates=true/false und tickers=TICKER1,TICKER2,... im
GITHUB_OUTPUT-Format auf stdout aus und beendet sich immer mit Exit-Code 0.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

CALENDAR_PATH = Path("data/earnings_calendar.json")


def prev_trading_day(d: date) -> date:
    d -= timedelta(days=1)
    if d.weekday() == 6:      # Sonntag
        d -= timedelta(days=2)
    elif d.weekday() == 5:    # Samstag
        d -= timedelta(days=1)
    return d


def main():
    today = date.today()

    if today.weekday() >= 5:
        print("Wochenende — kein Handel.", file=sys.stderr)
        print("has_candidates=false")
        print("tickers=")
        return

    candidate_dates = {today.isoformat(), prev_trading_day(today).isoformat()}
    print(f"Ziel-Termine: {sorted(candidate_dates)}", file=sys.stderr)

    try:
        cal = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Kalender nicht lesbar ({e}) — gilt als keine Kandidaten.", file=sys.stderr)
        print("has_candidates=false")
        print("tickers=")
        return

    next_earnings = cal.get("next_earnings", {})
    tickers = sorted(t for t, d in next_earnings.items() if d in candidate_dates)

    print(f"Kandidaten: {tickers or '(keine)'}", file=sys.stderr)
    print(f"has_candidates={'true' if tickers else 'false'}")
    print(f"tickers={','.join(tickers)}")


if __name__ == "__main__":
    main()
