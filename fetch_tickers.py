"""
Ticker-Listen-Kaskade für RS-Platform
======================================
Reihenfolge pro Index:
  1. Financial Modeling Prep API  (wenn FMP_API_KEY gesetzt)
  2. Wikipedia  (pd.read_html)
  3. Hardcoded Fallback

Alle fetch_*-Funktionen geben ein Tupel zurück:
  (all_tickers, official_tickers)

  all_tickers     = offizielle Ticker + Fallback-Ergänzungen
  official_tickers = nur FMP/Wikipedia-Ergebnis (ohne Fallback)
                     Leere Liste wenn nur Fallback genutzt wurde.

Der Unterschied ist entscheidend für detect_index_changes():
Nur Ticker die neu in der offiziellen Quelle auftauchen, werden als
"neu im Index" gewertet – nicht Ticker die vorher schon im Fallback
waren (wie LITE vor der offiziellen Aufnahme).

API-Key setzen:  .env  →  FMP_API_KEY=dein_key_hier
Registrierung:   https://financialmodelingprep.com/developer/docs  (kostenlos)
"""

import os
import json
import urllib.request
from pathlib import Path


def detect_index_changes(ic_official: list, edc_json_path: str) -> dict:
    """
    Vergleicht die OFFIZIELLE Index-Zusammensetzung (IC, ohne Fallback) mit
    dem zuletzt gespeicherten JSON-Cache (EDC, Feld 'fmp_tickers').

    Wichtig: ic_official muss das reine FMP/Wikipedia-Ergebnis sein,
    OHNE Fallback-Ergänzungen. Nur so werden Ticker korrekt als neu
    erkannt, die vorher nur im Fallback standen (z.B. LITE).

    Gibt {'new': [...], 'removed': [...]} zurück.
    """
    if not ic_official:
        print("  IC leer (nur Fallback aktiv) – kein Vergleich möglich")
        return {"new": [], "removed": []}

    edc_path = Path(edc_json_path)
    if not edc_path.exists():
        print(f"  EDC: {edc_json_path} nicht gefunden – erster Lauf, kein Vergleich")
        return {"new": list(ic_official), "removed": []}

    try:
        with open(edc_path, encoding="utf-8") as f:
            edc = json.load(f)
        # Bevorzuge gespeicherte fmp_tickers (genau dieser Vergleich)
        # Fallback auf data-Ticker für Rückwärtskompatibilität
        if "fmp_tickers" in edc:
            edc_official = set(edc["fmp_tickers"])
        else:
            edc_official = {d["ticker"] for d in edc.get("data", [])}
    except Exception as e:
        print(f"  EDC: Fehler beim Lesen – {e}")
        return {"new": [], "removed": []}

    ic_set = set(ic_official)
    new_tickers     = sorted(ic_set - edc_official)
    removed_tickers = sorted(edc_official - ic_set)

    if new_tickers:
        print(f"  ✅ Neue Aktien im Index ({len(new_tickers)}): {', '.join(new_tickers)}")
        print(f"     → Historische Kursdaten (bis 2 Jahre) werden geladen")
    if removed_tickers:
        print(f"  ⚠️  Aus dem Index entfernt ({len(removed_tickers)}): {', '.join(removed_tickers)}")
    if not new_tickers and not removed_tickers:
        print(f"  Keine Indexänderungen erkannt ({len(ic_official)} Ticker unverändert)")

    return {"new": new_tickers, "removed": removed_tickers}


def _get_fmp_key() -> str:
    # 1) Umgebungsvariable (Railway / Shell)
    key = os.environ.get("FMP_API_KEY", "")
    if key:
        return key
    # 2) .env Datei im Root-Verzeichnis
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("FMP_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _fmp_fetch(endpoint: str) -> list | None:
    key = _get_fmp_key()
    if not key:
        print("  FMP: Kein API-Key – überspringe FMP-Quelle")
        return None
    url = f"https://financialmodelingprep.com/api/v3/{endpoint}?apikey={key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rs-platform/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        if not isinstance(data, list) or not data:
            print(f"  FMP: Leere Antwort für {endpoint}")
            return None
        if "symbol" not in data[0]:
            print(f"  FMP: Unerwartetes Format für {endpoint}: {list(data[0].keys())}")
            return None
        tickers = [d["symbol"] for d in data if d.get("symbol")]
        print(f"  FMP: {len(tickers)} Ticker geladen ({endpoint})")
        return tickers
    except Exception as e:
        print(f"  FMP: Fehler bei {endpoint}: {e}")
        return None


def _wikipedia_table(url: str, col_names: tuple, min_count: int,
                     transform=None) -> list | None:
    try:
        import pandas as pd
        tables = pd.read_html(url)
        for t in tables:
            for col in t.columns:
                if str(col).lower() in col_names:
                    ts = t[col].dropna().astype(str).str.strip().tolist()
                    if transform:
                        ts = transform(ts)
                    if len(ts) >= min_count:
                        print(f"  Wikipedia: {len(ts)} Ticker geladen")
                        return ts
    except Exception as e:
        print(f"  Wikipedia: Fehler – {e}")
    return None


# ── Öffentliche Funktionen ────────────────────────────────────────────────────

def fetch_nasdaq100(fallback: list) -> tuple[list, list]:
    """Nasdaq-100: FMP → Wikipedia → Fallback.
    Gibt (all_tickers, official_tickers) zurück.
    official_tickers = FMP/Wikipedia-Ergebnis ohne Fallback ([] wenn nur Fallback).
    """
    print("Lade Nasdaq-100 Ticker-Liste …")

    primary = None

    # 1) FMP
    raw = _fmp_fetch("nasdaq_constituent")
    if raw and len(raw) >= 95:
        primary = list(set(raw))

    # 2) Wikipedia
    if primary is None:
        def _clean_ndx(ts):
            return [x for x in ts if x and x.replace('-', '').isalpha() and 1 < len(x) <= 5]
        ts = _wikipedia_table(
            "https://en.wikipedia.org/wiki/Nasdaq-100",
            ("ticker", "symbol"), 95, _clean_ndx
        )
        if ts:
            primary = list(set(ts))

    # 3) Nur Fallback
    if primary is None:
        print(f"  Fallback: {len(fallback)} Ticker")
        return list(fallback), []

    official = list(primary)  # Snapshot vor Fallback-Ergänzungen

    # Fallback-Ticker ergänzen die FMP/Wikipedia noch nicht kennt
    primary_set = set(primary)
    extra = [t for t in fallback if t not in primary_set]
    if extra:
        print(f"  +{len(extra)} Fallback-Ticker ergänzt: {', '.join(extra)}")
        primary.extend(extra)

    return primary, official


def fetch_sp500(fallback: list) -> tuple[list | None, list]:
    """S&P 500: FMP → Wikipedia → Fallback.
    Gibt (all_tickers, official_tickers) zurück.
    all_tickers = None wenn nur Fallback verfügbar.
    """
    print("Lade S&P 500 Ticker-Liste …")

    primary = None

    # 1) FMP
    raw = _fmp_fetch("sp500_constituent")
    if raw and len(raw) >= 490:
        primary = sorted(set(t.replace(".", "-") for t in raw))

    # 2) Wikipedia
    if primary is None:
        try:
            import pandas as pd
            df = pd.read_html(
                "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            )[0]
            ts = (df["Symbol"].dropna().astype(str).str.strip()
                  .str.replace(".", "-", regex=False).tolist())
            ts = sorted([x for x in ts if x and len(x) <= 6])
            if len(ts) >= 490:
                print(f"  Wikipedia: {len(ts)} Ticker geladen")
                primary = ts
            else:
                print(f"  Wikipedia: nur {len(ts)} Ticker – zu wenig")
        except Exception as e:
            print(f"  Wikipedia: Fehler – {e}")

    # 3) Beide Quellen fehlgeschlagen
    if primary is None:
        print(f"  Fallback: {len(fallback)} Ticker")
        return None, []

    official = list(primary)  # Snapshot vor Fallback-Ergänzungen

    # Fallback-Ticker ergänzen
    primary_set = set(primary)
    extra = [t for t in fallback if t not in primary_set]
    if extra:
        print(f"  +{len(extra)} Fallback-Ticker ergänzt: {', '.join(extra)}")
        primary = sorted(set(primary) | set(extra))

    return primary, official


def fetch_dax40(fallback: list) -> tuple[list, list]:
    """DAX 40: Wikipedia → Fallback  (FMP hat kein DAX-Endpoint).
    Gibt (all_tickers, official_tickers) zurück.
    """
    print("Lade DAX 40 Ticker-Liste …")

    def _clean_dax(ts):
        result = []
        for x in ts:
            if not x or len(x) > 10:
                continue
            if not x.endswith(".DE"):
                x = x + ".DE"
            result.append(x)
        return [x for x in result if x.endswith(".DE")]

    primary = _wikipedia_table(
        "https://en.wikipedia.org/wiki/DAX",
        ("ticker", "symbol"), 35, _clean_dax
    )

    if primary is None:
        print(f"  Fallback: {len(fallback)} Ticker")
        return list(fallback), []

    official = list(primary)  # Snapshot vor Fallback-Ergänzungen

    # Fallback-Ticker ergänzen
    primary_set = set(primary)
    extra = [t for t in fallback if t not in primary_set]
    if extra:
        print(f"  +{len(extra)} Fallback-Ticker ergänzt: {', '.join(extra)}")
        primary = list(set(primary) | set(extra))

    return primary, official
