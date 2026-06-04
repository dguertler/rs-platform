"""
Holt die Equity-Kurve deines wikifolios und schreibt sie nach
data/wikifolio_performance.json (Format siehe instagram/data.py).

WICHTIG: In der Claude-Cloud-Umgebung ist wikifolio.com per Bot-Schutz/
Netz-Policy gesperrt (HTTP 403). Dieses Script ist dafür gedacht, BEI DIR
LOKAL zu laufen, wo der Netzzugang offen ist. Falls auch lokal 403 kommt,
nutze den manuellen Weg: data/wikifolio_performance.example.json kopieren
und Werte eintragen.

Aufruf:
    python3 -m instagram.fetch_wikifolio --symbol WFAIALPHA
    python3 -m instagram.fetch_wikifolio --url https://www.wikifolio.com/de/de/p/wfaialpha

Die genauen API-Endpunkte von wikifolio ändern sich gelegentlich. Die GUID-
und Endpoint-Erkennung unten ist „best effort\" und ggf. anzupassen.
"""
import argparse
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "wikifolio_performance.json")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/json",
    "Accept-Language": "de-DE,de;q=0.9",
}


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def resolve_guid(symbol=None, url=None):
    """Liest die interne wikifolio-GUID aus der öffentlichen Seite."""
    page = url or f"https://www.wikifolio.com/de/de/w/{symbol}"
    html = _get(page)
    m = re.search(r'"wikifolioId"\s*:\s*"([0-9a-fA-F\-]{36})"', html)
    if not m:
        m = re.search(r'data-wikifolio-id="([0-9a-fA-F\-]{36})"', html)
    if not m:
        raise RuntimeError("wikifolio-GUID nicht gefunden – Seitenstruktur "
                           "geändert? Bitte manuellen Weg nutzen.")
    return m.group(1)


def fetch_chart(guid):
    """Holt die Chartdaten. Endpoint ggf. anpassen, falls wikifolio ihn ändert."""
    # Beobachteter Endpoint-Stil; liefert i.d.R. eine Liste {date,value}.
    url = (f"https://www.wikifolio.com/api/chart/{guid}/data"
           f"?country=de&language=de&range=max")
    raw = json.loads(_get(url))
    # Heuristik: finde eine Liste mit Datum+Wert-Paaren
    series = raw.get("series") or raw.get("data") or raw
    out = []
    for p in series:
        d = p.get("date") or p.get("d") or p.get("x")
        v = p.get("value") or p.get("v") or p.get("y")
        if d and v is not None:
            out.append({"d": str(d)[:10], "v": float(v)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", help="z.B. WFAIALPHA")
    ap.add_argument("--url", help="vollständige wikifolio-URL")
    ap.add_argument("--name", default="AI Alpha Selections")
    args = ap.parse_args()
    if not (args.symbol or args.url):
        ap.error("--symbol oder --url angeben")

    guid = resolve_guid(args.symbol, args.url)
    series = fetch_chart(guid)
    if not series:
        raise RuntimeError("Keine Datenpunkte erhalten.")
    data = {"name": args.name, "currency": "EUR", "guid": guid, "series": series}
    with open(OUT, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✓ {len(series)} Punkte → {OUT}")


if __name__ == "__main__":
    main()
