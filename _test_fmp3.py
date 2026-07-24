"""Einmaliges Test-Skript — prüft europäische Abdeckung von stable/earnings-calendar
und Rate-Limits bei größerem Datumsbereich. Wird nach dem Test wieder entfernt."""
import json
import os
import urllib.request
from datetime import date, timedelta

key = os.environ.get("FMP_API_KEY", "")
print("Key vorhanden:", bool(key))

# Größerer Zeitraum (letzte 5 Tage), um mehr Treffer zu bekommen und Nicht-US-Exchanges zu finden
start = (date.today() - timedelta(days=5)).isoformat()
end = date.today().isoformat()

url = f"https://financialmodelingprep.com/stable/earnings-calendar?from={start}&to={end}&apikey={key}"
req = urllib.request.Request(url, headers={"User-Agent": "rs-platform/1.0"})
with urllib.request.urlopen(req, timeout=20) as r:
    data = json.loads(r.read().decode("utf-8"))

print(f"Zeitraum {start} bis {end}: {len(data)} Einträge gesamt")

# Exchange-Verteilung ermitteln (falls Feld vorhanden) und Symbol-Suffixe prüfen (.DE/.PA/.L etc = non-US)
non_us_suffixes = set()
us_like = 0
for d in data:
    sym = d.get("symbol", "")
    if "." in sym:
        non_us_suffixes.add(sym.split(".")[-1])
    else:
        us_like += 1

print(f"Symbole ohne Suffix (vermutlich US): {us_like}")
print(f"Gefundene Nicht-US-Suffixe: {sorted(non_us_suffixes)}")

# Ein paar Beispiele mit Suffix zeigen, falls vorhanden
examples = [d for d in data if "." in d.get("symbol", "")][:5]
for e in examples:
    print(json.dumps(e, indent=2)[:300])

if not examples:
    print("Keine Nicht-US-Ticker (mit Suffix) im Zeitraum gefunden — erste 5 Symbole zur Kontrolle:")
    for d in data[:5]:
        print(" ", d.get("symbol"), d.get("date"))
