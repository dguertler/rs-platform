"""
Earnings-Post-Datenschicht (Dritter Post-Typ: EARNINGS-ANALYSE).

Baut den Kontext für einen Earnings-Slide-Post aus drei Quellen zusammen:

  1. **Earnings-Datei** `instagram/data/earnings/<TICKER>.json` — von Claude aus
     dem Web befüllt (EPS Ist/Erwartung/Surprise, Umsatz, Guidance, Turnaround-
     Kennzahl, Treiber, Kontext-Text). yfinance ist in der Cloud meist geblockt,
     deshalb kommen die harten Earnings-Zahlen aus dem Web und werden hier
     persistiert (Repo-Philosophie: Werte zuerst speichern).
  2. **Kurssprung** — live aus der passenden RS-JSON (`data/rs_*.json`) berechnet:
     Close-zu-Close am Meldetag + das OHLCV-Fenster für den Reaktions-Chart.
     Bewusst NICHT in der JSON dupliziert, damit die Daten frisch bleiben.
  3. **Basis-Analyse** `analyses/<TICKER>.md` — die volle KI-Aktienbewertung
     (Verdict, Szenarien, Kursziele, Fazit), geparst über `analysis.py`. Pflicht-
     Voraussetzung; fehlt sie, wird zuerst eine Analyse erzeugt (siehe PROMPT.md).

Die Earnings-Regeln (≥ 5 % Kurssprung, ≥ 10 % EPS-Surprise, Umsatz-YoY ≥ 0)
stammen aus `check_earnings.py` und werden hier nur zur Plausibilitäts-Prüfung
gespiegelt — der Generator baut die Slides auch, wenn eine Schwelle knapp
verfehlt wird, weist aber darauf hin.
"""
import json
import os
import sys

from . import analysis as ana

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EARNINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "earnings")

# Earnings-Schwellen — Single Source of Truth ist earnings_gate.py im Repo-Root
sys.path.insert(0, ROOT)
from earnings_gate import MIN_PRICE_JUMP, MIN_EPS_SURPRISE  # noqa: E402

# RS-JSON je Quelle (source-Label in der Earnings-JSON)
_SOURCE_JSON = {
    "QQQ":  "rs_full.json",
    "NDX":  "rs_full.json",
    "SPX":  "rs_sp500.json",
    "SP500": "rs_sp500.json",
}


def earnings_path(ticker_or_path):
    """Pfad zur Earnings-JSON; akzeptiert Ticker (CNC), Slug (SIE_DE) oder Pfad."""
    if os.path.isfile(ticker_or_path):
        return ticker_or_path
    t = os.path.splitext(os.path.basename(ticker_or_path))[0]
    for cand in (t.upper(), t, t.replace(".", "_").upper()):
        p = os.path.join(EARNINGS_DIR, cand + ".json")
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(
        f"Earnings-Datei nicht gefunden: {ticker_or_path} "
        f"(erwartet z. B. {os.path.join(EARNINGS_DIR, t.upper() + '.json')})")


def _rs_ticker(ticker):
    """Ticker unverändert — RS-JSON und Earnings-JSON nutzen dasselbe Kürzel."""
    return ticker


def _load_rs_entry(ticker, source):
    """Lädt den OHLCV-Eintrag aus der passenden RS-JSON. Probiert Ticker direkt
    und mit/ohne .DE-Suffix. Gibt (entry, json_name) oder (None, json_name)."""
    json_name = _SOURCE_JSON.get((source or "").upper())
    candidates = [json_name] if json_name else []
    # Fallback: beide durchsuchen, falls source fehlt/falsch
    for jn in ("rs_full.json", "rs_sp500.json"):
        if jn not in candidates:
            candidates.append(jn)

    want = {ticker.upper(), ticker.upper() + ".DE", ticker.upper().replace(".DE", "")}
    for jn in candidates:
        # RS-JSONs liegen in data/ (Fallback: Repo-Root, wie check_earnings.py)
        path = next((p for p in (os.path.join(ROOT, "data", jn), os.path.join(ROOT, jn))
                     if os.path.isfile(p)), None)
        if not path:
            continue
        with open(path) as f:
            data = json.load(f)
        for e in data.get("data", []):
            if e.get("ticker", "").upper() in want:
                return e, jn
    return None, json_name


def price_jump(ohlcv, target_date_str):
    """Close-zu-Close-Sprung am Meldetag. (jump, close, prev_close) oder
    (None, None, None). Identische Logik wie check_earnings.get_price_jump,
    hier lokal kopiert, um den pip-install-Import von check_earnings zu meiden."""
    closes = [(c["d"][:10], c["c"]) for c in ohlcv if c.get("c")]
    if len(closes) < 2:
        return None, None, None
    for i in range(len(closes) - 1, 0, -1):
        day, close = closes[i]
        if day == target_date_str:
            return close / closes[i - 1][1] - 1, close, closes[i - 1][1]
    return None, None, None


def reaction_window(ohlcv, target_date_str, before=49, after=0):
    """OHLCV-Fenster für den Reaktions-Chart. Standard: die letzten 50 Handelstage
    (10 × 5) bis EINSCHLIESSLICH Meldetag — der Sprungtag ist die letzte Kerze
    (after=0). Hinweis: OHLCV enthält nur Handelstage (keine Wochenenden/Feiertage),
    50 Kerzen decken daher ~10 Kalenderwochen ab. Liefert (candles, idx) — idx =
    Position des Meldetags im Fenster (oder None)."""
    days = [c["d"][:10] for c in ohlcv]
    if target_date_str in days:
        i = days.index(target_date_str)
    else:
        # nächster Handelstag ≥ target
        i = next((k for k, d in enumerate(days) if d >= target_date_str), len(days) - 1)
    lo = max(0, i - before)
    hi = min(len(ohlcv), i + after + 1)
    window = ohlcv[lo:hi]
    rel = i - lo if lo <= i < hi else None
    return window, rel


def load_earnings(ticker_or_path):
    """Liest die Earnings-JSON und reichert sie mit Kurssprung + Reaktions-Fenster
    aus der RS-JSON und der geparsten Basis-Analyse an. Gibt ein Dict `e`."""
    path = earnings_path(ticker_or_path)
    with open(path, encoding="utf-8") as f:
        e = json.load(f)
    e["path"] = path
    ticker = e["ticker"]

    # ── Kurssprung + Reaktions-Chart-Fenster aus der RS-JSON ──────────────────
    entry, json_name = _load_rs_entry(ticker, e.get("source"))
    e["rs_json"] = json_name
    if entry:
        e["rs_score"] = entry.get("score")
        ohlcv = entry.get("ohlcv", [])
        jump, close, prev = price_jump(ohlcv, e["report_date"])
        e["jump_pct"] = jump
        e["jump_close"] = close
        e["jump_prev_close"] = prev
        window, rel = reaction_window(ohlcv, e["report_date"])
        e["reaction_ohlcv"] = window
        e["reaction_idx"] = rel
    else:
        e.setdefault("jump_pct", None)
        e["reaction_ohlcv"] = []
        e["reaction_idx"] = None

    # ── Basis-Analyse (Pflicht) ───────────────────────────────────────────────
    try:
        e["analysis"] = ana.parse_analysis(ticker)
    except FileNotFoundError:
        e["analysis"] = None

    # ── Plausibilität (Regel-Spiegel, nur Hinweis) ────────────────────────────
    e["meets_jump"]     = (e.get("jump_pct") or 0) >= MIN_PRICE_JUMP
    e["meets_surprise"] = (e.get("eps_surprise_pct") or 0) >= MIN_EPS_SURPRISE
    e["beat"] = (e.get("eps_surprise_pct") or 0) > 0
    return e


def fmt_num(x, decimals=2):
    """3.37 -> '3,37' ; 49.94 -> '49,94' ; None -> '–'."""
    if x is None:
        return "–"
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "·").replace(".", ",").replace("·", ".")


def fmt_pct(x, decimals=1, signed=True):
    """0.14 (Anteil) -> '+14,0 %'. Für bereits-Prozent-Werte fmt_pct_pts nutzen."""
    if x is None:
        return "–"
    sign = ("+" if x >= 0 else "−") if signed else ""
    return f"{sign}{abs(x) * 100:.{decimals}f}".replace(".", ",") + " %"


def fmt_pct_pts(x, decimals=0, signed=True):
    """62.0 (schon Prozent) -> '+62 %'."""
    if x is None:
        return "–"
    sign = ("+" if x >= 0 else "−") if signed else ""
    return f"{sign}{abs(x):.{decimals}f}".replace(".", ",") + " %"


if __name__ == "__main__":          # Schnelltest: python3 -m instagram.earnings CNC
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "CNC"
    e = load_earnings(t)
    slim = {k: v for k, v in e.items()
            if k not in ("reaction_ohlcv", "analysis")}
    slim["reaction_candles"] = len(e.get("reaction_ohlcv") or [])
    slim["analysis"] = ("geladen: " + e["analysis"]["verdict"]) if e.get("analysis") else None
    print(json.dumps(slim, ensure_ascii=False, indent=2))
