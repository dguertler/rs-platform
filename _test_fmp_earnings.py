"""Einmaliges Test-Skript — prüft, ob der FMP-Key Zugriff auf den
Earnings-Calendar-Endpoint hat. Wird nach dem Test wieder entfernt."""
import json
import os
import urllib.request
from datetime import date, timedelta

key = os.environ.get("FMP_API_KEY", "")
print("Key vorhanden:", bool(key), "Länge:", len(key))

yesterday = (date.today() - timedelta(days=1)).isoformat()
today = date.today().isoformat()

endpoints = [
    f"https://financialmodelingprep.com/api/v3/earning_calendar?from={yesterday}&to={today}&apikey={key}",
    f"https://financialmodelingprep.com/stable/earnings-calendar?from={yesterday}&to={today}&apikey={key}",
    f"https://financialmodelingprep.com/api/v3/quote/AAPL?apikey={key}",
]

for url in endpoints:
    safe_url = url.replace(key, "***")
    print(f"\n--- {safe_url} ---")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rs-platform/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            status = r.status
            data = json.loads(r.read().decode("utf-8"))
        print(f"Status: {status}")
        if isinstance(data, list):
            print(f"Anzahl Einträge: {len(data)}")
            if data:
                print(f"Erstes Element: {json.dumps(data[0], indent=2)[:500]}")
        else:
            print(f"Antwort: {json.dumps(data, indent=2)[:500]}")
    except urllib.error.HTTPError as e:
        print(f"HTTP-Fehler: {e.code} {e.reason}")
        try:
            print(f"Body: {e.read().decode('utf-8')[:500]}")
        except Exception:
            pass
    except Exception as e:
        print(f"Fehler: {type(e).__name__}: {e}")
