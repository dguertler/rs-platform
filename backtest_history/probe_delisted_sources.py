"""
Prüft, welche Datenquelle Kurse für die NASDAQ-100-Mitglieder liefert, die
bei Yahoo fehlen (übernommen, insolvent, umbenannt). Läuft in GitHub Actions
(probe_delisted_sources.yml) — die Anbieter sind aus den Cloud-Sessions
heraus gesperrt.

Geprüft werden:
  - Tiingo: öffentliche Tickerliste supported_tickers.zip (ohne Schlüssel),
    mit Start-/Enddatum je Ticker → deckt sie den Mitgliedszeitraum ab?
  - FMP: Tageskurse über den vorhandenen FMP_API_KEY (stable- und v3-Endpunkt)
  - Stooq: CSV-Download ohne Schlüssel

Ausgabe: data/backtest_history/delisted_sources_probe.json
"""
import csv
import io
import json
import os
import urllib.request
import zipfile
from datetime import datetime, timezone

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_REPO, "data", "backtest_history")
TIINGO_LIST = "https://apimedia.tiingo.com/docs/tiingo/daily/supported_tickers.zip"
HEADERS = {"User-Agent": "rs-platform/1.0 (backtest data probe)"}
FMP_PROBE_LIMIT = 100          # Free-Tier: 250 Aufrufe/Tag


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def missing_tickers():
    """Historische Symbole ohne Yahoo-Kurse samt Mitgliedsintervallen."""
    results = json.load(open(os.path.join(DATA_DIR, "ndx_results.json")))
    membership = json.load(open(os.path.join(DATA_DIR, "ndx_membership.json")))["intervals"]
    names = sorted({t for c in results["coverage"].values() for t in c["missing"]})
    return {t: membership[t] for t in names}


def _overlap(start, end, ivs):
    """Deckt [start, end] die Mitgliedsintervalle ab? Liefert Anteil 0..1."""
    if not start:                      # Tiingo: leeres Startdatum = keine Kurse
        return 0.0
    total = covered = 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for a, b in ivs:
        b = b or today
        days = (datetime.fromisoformat(b) - datetime.fromisoformat(a)).days or 1
        lo, hi = max(a, start or a), min(b, end or b)
        total += days
        if lo < hi:
            covered += (datetime.fromisoformat(hi) - datetime.fromisoformat(lo)).days
    return round(covered / total, 3) if total else 0.0


def probe_tiingo(tickers):
    try:
        raw = _get(TIINGO_LIST, timeout=120)
    except Exception as e:                                    # noqa: BLE001
        return {"error": str(e)}
    zf = zipfile.ZipFile(io.BytesIO(raw))
    rows = csv.DictReader(io.TextIOWrapper(zf.open(zf.namelist()[0]), encoding="utf-8"))
    by_ticker = {}
    for r in rows:
        t = (r.get("ticker") or "").upper()
        if t in tickers and r.get("assetType") == "Stock":
            by_ticker.setdefault(t, []).append(
                {"exchange": r.get("exchange"), "start": r.get("startDate") or None,
                 "end": r.get("endDate") or None})
    out = {}
    for t, ivs in tickers.items():
        best = max(by_ticker.get(t, []), default=None,
                   key=lambda e: _overlap(e["start"], e["end"], ivs))
        out[t] = {"listed": best, "coverage": _overlap(best["start"], best["end"], ivs) if best else 0.0}
    return out


def _fmp_range(ticker, key):
    urls = [
        f"https://financialmodelingprep.com/stable/historical-price-eod/light?symbol={ticker}&from=2005-01-01&apikey={key}",
        f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}?from=2005-01-01&serietype=line&apikey={key}",
    ]
    errors = []
    for url in urls:
        try:
            data = json.loads(_get(url))
        except Exception as e:                                # noqa: BLE001
            errors.append(f"{url.split('?')[0].split('.com')[1]}: {e}")
            continue
        rows = data.get("historical") if isinstance(data, dict) else data
        if isinstance(rows, list) and rows:
            dates = sorted(r["date"] for r in rows if r.get("date"))
            return {"endpoint": url.split("?")[0].split(".com")[1], "start": dates[0], "end": dates[-1],
                    "rows": len(dates)}
        errors.append(f"{url.split('?')[0].split('.com')[1]}: {str(data)[:120]}")
    return {"error": errors}


def probe_fmp(tickers):
    key = os.environ.get("FMP_API_KEY", "").strip()
    if not key:
        return {"error": "FMP_API_KEY fehlt"}
    out = {}
    for t in list(tickers)[:FMP_PROBE_LIMIT]:
        r = _fmp_range(t, key)
        if "start" in r:
            r["coverage"] = _overlap(r["start"], r["end"], tickers[t])
        out[t] = r
    return out


def probe_stooq(tickers, sample=10):
    out = {}
    for t in list(tickers)[:sample]:
        try:
            text = _get(f"https://stooq.com/q/d/l/?s={t.lower()}.us&i=d").decode("utf-8", "replace")
            lines = [ln for ln in text.splitlines()[1:] if ln and ln[0].isdigit()]
            out[t] = ({"start": lines[0][:10], "end": lines[-1][:10], "rows": len(lines)}
                      if lines else {"error": text[:80]})
        except Exception as e:                                # noqa: BLE001
            out[t] = {"error": str(e)}
    return out


def _summary(name, res):
    if "error" in res and not isinstance(res.get("error"), dict):
        return f"{name}: Fehler – {res['error']}"
    hits = [t for t, r in res.items() if isinstance(r, dict) and (r.get("coverage") or 0) >= 0.9]
    part = [t for t, r in res.items() if isinstance(r, dict) and 0 < (r.get("coverage") or 0) < 0.9]
    return f"{name}: {len(hits)}/{len(res)} voll abgedeckt, {len(part)} teilweise — {' '.join(hits)}"


def main():
    tickers = missing_tickers()
    print(f"{len(tickers)} Symbole ohne Yahoo-Kurse")
    result = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "tickers": tickers,
        "tiingo": probe_tiingo(tickers),
        "fmp": probe_fmp(tickers),
        "stooq": probe_stooq(tickers),
    }
    for name in ("tiingo", "fmp", "stooq"):
        print(_summary(name, result[name]))
    with open(os.path.join(DATA_DIR, "delisted_sources_probe.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)


if __name__ == "__main__":
    main()
