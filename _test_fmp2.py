"""Einmaliges Test-Skript — prüft FMP /stable/-Endpoints für Index-Konstituenten
und Quotes. Wird nach dem Test wieder entfernt."""
import json
import os
import urllib.request

key = os.environ.get("FMP_API_KEY", "")
print("Key vorhanden:", bool(key), "Länge:", len(key))

endpoints = [
    f"https://financialmodelingprep.com/stable/nasdaq-constituent?apikey={key}",
    f"https://financialmodelingprep.com/stable/sp500-constituent?apikey={key}",
    f"https://financialmodelingprep.com/stable/sp600-constituent?apikey={key}",
    f"https://financialmodelingprep.com/stable/dowjones-constituent?apikey={key}",
    f"https://financialmodelingprep.com/stable/quote?symbol=AAPL&apikey={key}",
    f"https://financialmodelingprep.com/stable/quote-short?symbol=AAPL&apikey={key}",
]

for url in endpoints:
    safe_url = url.replace(key, "***")
    print(f"\n--- {safe_url} ---")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rs-platform/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            status = r.status
            raw = r.read().decode("utf-8")
            data = json.loads(raw)
        print(f"Status: {status}")
        if isinstance(data, list):
            print(f"Anzahl Einträge: {len(data)}")
            if data:
                print(f"Erstes Element: {json.dumps(data[0], indent=2)[:500]}")
                if len(data) > 1:
                    print(f"Letztes Element: {json.dumps(data[-1], indent=2)[:300]}")
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
