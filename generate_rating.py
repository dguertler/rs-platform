"""
generate_rating.py — KI-Aktienbewertung für Breakout-Kandidaten
===============================================================
Wird von check_alerts.py und check_4h_reentry.py aufgerufen,
wenn ein Ticker ein 3-Punkte-GWS-Signal erreicht.

Ablauf:
1. Fundamentaldaten on-demand via yfinance
2. Gemini Flash API (gemini-2.0-flash) für die KI-Analyse
3. HTML-Seite generieren → data/ratings/{ticker}.html
4. data/ratings/index.json aktualisieren
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import yfinance as yf

RATINGS_DIR = Path("data/ratings")

# ── System-Prompt (wird gecacht — spart ~90% Input-Token-Kosten) ─────────────

SYSTEM_PROMPT = """Du bist ein institutioneller Investor, Hedgefonds-Analyst und ehemaliger Portfolio-Manager mit Fokus auf:
- Technologie
- AI-Infrastruktur
- Halbleiter
- Makro
- Energie
- Compounder-Aktien
- Marktpsychologie

Du analysierst eine Aktie anhand bereitgestellter Fundamentaldaten und RS-Platform-Signaldaten.
Die Analyse soll NICHT wie eine klassische Analysten-Zusammenfassung klingen, sondern wie eine ehrliche professionelle Einschätzung eines erfahrenen Börsenprofis.
WICHTIG: Schreibe die gesamte Analyse OHNE horizontale Trennlinien.

STIL & TON
- Schreibe klar, direkt und intelligent — auf Deutsch
- Keine generischen Floskeln oder Marketing-Sprache
- Erkläre die eigentlichen Treiber hinter der Aktie
- Denke wie institutionelle Investoren
- Fokus auf Ursache-Wirkung, nicht nur Kennzahlen
- Ehrlich über Risiken und Schwächen
- Professionell, aber nicht steril

PFLICHT-STRUKTUR

## 1. INVESTMENT-CASE
Max. 6-8 Sätze. Was ist die eigentliche Story? Warum interessiert die Aktie institutionelle Investoren? Was versteht der Markt möglicherweise falsch oder richtig?

## 2. GESCHÄFTSMODELL
Max. 8-10 Bullet Points mit -. Wie verdient die Firma wirklich Geld? Wichtige Segmente? Strukturelle Trends?

## 3. BULL CASE
Max. 6-8 Bullet Points mit -. Warum könnte die Aktie massiv steigen? Megatrends? Repricing-Szenarien?

## 4. BEAR CASE
Max. 6-8 Bullet Points mit -. Größte Risiken, Zyklik, Konkurrenz, Bewertungsrisiko.

## 5. FUNDAMENTALE QUALITÄT
Max. 10-12 Bullet Points mit - (kurz & knackig). Umsatzwachstum, Margen, FCF, Bilanz, Wettbewerbsvorteile, ROIC/ROE.

## 6. BEWERTUNG
Max. 6-8 Sätze. Teuer oder günstig mit konkreten Multiples? Was preist der Markt ein? Vergleich mit Wettbewerbern.

## 7. MARKTPSYCHOLOGIE & POSITIONIERUNG
Max. 5-6 Bullet Points mit - (je 1 Zeile). Crowded/under-owned, Hype/fundamental, institutionelles Ownership, Momentum, Smart Money.

## 8. TECHNISCHE EINSCHÄTZUNG / MOMENTUM
Max. 4-5 Bullet Points mit - (je 1 Zeile). Kurzfristig überhitzt oder gesund? Chartbild? Zyklus-Phase? GWS-Ampel-Einordnung (nutze die RS-Platform-Daten).

## 9. LANGFRISTIGES POTENZIAL (3-5 Jahre)
Konservatives Szenario: Annahmen / Kursziel / Wahrscheinlichkeit
Bull Case: Annahmen / Kursziel / Wahrscheinlichkeit
Extrem-Bull-Case: Annahmen / Kursziel / Wahrscheinlichkeit

## 10. VERGLEICH MIT ÄHNLICHEN AKTIEN
Max. 4-5 Bullet Points mit - (je 1 Zeile). 3-4 Comparable Tickers mit kurzem Vergleich.

## 11. PROFI-FAZIT
Max. 8-10 Sätze. Hedgefonds-Perspektive, Trading-Play oder Compounder, Qualität vs. Bewertung, Risiko/Rendite, Wann kaufen/verkaufen bezogen auf GWS-Ampel-Status.

Rating (Zahl, nicht Sterne):
- Qualität: X/5
- Wachstum: X/5
- Bewertung: X/5
- Langfristiges Potenzial: X/5

FORMATIERUNGS-REGELN
- ## für Hauptüberschriften (exakt wie in der Struktur angegeben)
- - als Bullet-Marker (kein •)
- Zahlen konkret, nie vage
- Keine Füllwörter
- KEINE horizontalen Trennlinien
- MAX. 1000 Wörter gesamt
- Sprache: DEUTSCH"""


# ── Fundamentaldaten ──────────────────────────────────────────────────────────

def fetch_fundamentals(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info or {}
        return {
            "shortName":        info.get("shortName", ticker),
            "sector":           info.get("sector", "N/A"),
            "industry":         info.get("industry", "N/A"),
            "marketCap":        info.get("marketCap"),
            "currentPrice":     info.get("currentPrice") or info.get("regularMarketPrice"),
            "trailingPE":       info.get("trailingPE"),
            "forwardPE":        info.get("forwardPE"),
            "grossMargins":     info.get("grossMargins"),
            "operatingMargins": info.get("operatingMargins"),
            "profitMargins":    info.get("profitMargins"),
            "freeCashflow":     info.get("freeCashflow"),
            "totalRevenue":     info.get("totalRevenue"),
            "revenueGrowth":    info.get("revenueGrowth"),
            "dividendYield":    info.get("dividendYield"),
            "debtToEquity":     info.get("debtToEquity"),
            "returnOnEquity":   info.get("returnOnEquity"),
            "priceToBook":      info.get("priceToBook"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow":  info.get("fiftyTwoWeekLow"),
            "beta":             info.get("beta"),
            "recommendationKey":info.get("recommendationKey"),
            "targetMeanPrice":  info.get("targetMeanPrice"),
        }
    except Exception as e:
        print(f"  Fundamentaldaten für {ticker} fehlgeschlagen: {e}")
        return {}


def _pct(v):
    return f"{v * 100:.1f}%" if v is not None else "N/A"

def _bn(v):
    return f"${v / 1e9:.2f} Mrd." if v is not None else "N/A"

def _fmt(v):
    return str(round(v, 2)) if v is not None else "N/A"


def build_context(ticker: str, fund: dict, rs_score: float, windows: dict, gws: dict) -> str:
    return f"""FUNDAMENTALDATEN FÜR DIE ANALYSE:
Ticker: {ticker}
Unternehmen: {fund.get('shortName', ticker)}
Sektor: {fund.get('sector', 'N/A')} | Industrie: {fund.get('industry', 'N/A')}
Kurs: ${_fmt(fund.get('currentPrice'))} | Market Cap: {_bn(fund.get('marketCap'))}
52W-Hoch: ${_fmt(fund.get('fiftyTwoWeekHigh'))} | 52W-Tief: ${_fmt(fund.get('fiftyTwoWeekLow'))}
Beta: {_fmt(fund.get('beta'))}

Bewertung:
- Trailing PE: {_fmt(fund.get('trailingPE'))} | Forward PE: {_fmt(fund.get('forwardPE'))}
- Price/Book: {_fmt(fund.get('priceToBook'))}
- Analysten-Konsens: {fund.get('recommendationKey', 'N/A')} | Kursziel: ${_fmt(fund.get('targetMeanPrice'))}

Finanzkennzahlen:
- Revenue (TTM): {_bn(fund.get('totalRevenue'))} | Wachstum YoY: {_pct(fund.get('revenueGrowth'))}
- Gross Margin: {_pct(fund.get('grossMargins'))} | Operating Margin: {_pct(fund.get('operatingMargins'))}
- Net Margin: {_pct(fund.get('profitMargins'))} | Free Cashflow: {_bn(fund.get('freeCashflow'))}
- Dividende: {_pct(fund.get('dividendYield'))} | Debt/Equity: {_fmt(fund.get('debtToEquity'))}
- Return on Equity: {_pct(fund.get('returnOnEquity'))}

RS-PLATFORM SIGNALDATEN:
RS-Score vs. QQQ: {rs_score:.2f}
RS-Fenster (relative Performance): {json.dumps(windows)}

GWS-AMPEL (Gleichgewichts-Widerstandsstruktur):
- Weekly: {'AKTIV — Wochenchart-Struktur gebrochen' if gws.get('weekly') else 'NICHT AKTIV'}
- Daily:  {'AKTIV — Tageschart-Struktur gebrochen'  if gws.get('daily')  else 'NICHT AKTIV'}
- 4H:     {'AKTIV — 4H-Struktur gebrochen'          if gws.get('h4')     else 'NICHT AKTIV'}
- Gesamtpunkte: {gws.get('points', 0)}/3
- Signal-Typ: {gws.get('signal_type', 'Erstmaliger Breakout')}

Analysiere jetzt: {ticker}"""


# ── HTML-Generierung ──────────────────────────────────────────────────────────

def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def _md_to_html(text: str) -> str:
    lines = text.split('\n')
    result = []
    in_ul = False
    for line in lines:
        s = line.strip()
        if not s:
            if in_ul:
                result.append('</ul>')
                in_ul = False
            continue
        if s.startswith('## '):
            if in_ul:
                result.append('</ul>')
                in_ul = False
            result.append(f'<h3>{s[3:]}</h3>')
        elif s.startswith('- '):
            if not in_ul:
                result.append('<ul class="al">')
                in_ul = True
            result.append(f'<li>{s[2:]}</li>')
        else:
            if in_ul:
                result.append('</ul>')
                in_ul = False
            result.append(f'<p>{s}</p>')
    if in_ul:
        result.append('</ul>')
    return '\n'.join(result)


def _extract_ratings(text: str) -> dict:
    out = {}
    for cat in ["Qualität", "Wachstum", "Bewertung", "Langfristiges Potenzial"]:
        m = re.search(rf'{re.escape(cat)}:\s*(\d)/5', text)
        out[cat] = int(m.group(1)) if m else 3
    return out


def _safe_name(ticker: str) -> str:
    return re.sub(r'[^a-z0-9]', '_', ticker.lower())


def build_html(ticker: str, fund: dict, analysis_text: str, rs_score: float, gws: dict) -> str:
    today = datetime.now().strftime("%d.%m.%Y")
    short_name = fund.get("shortName", ticker)
    sector     = fund.get("sector",    "N/A")
    industry   = fund.get("industry",  "N/A")
    sig_type   = gws.get("signal_type", "Breakout")

    rt = _extract_ratings(analysis_text)
    q, g, v, p = rt["Qualität"], rt["Wachstum"], rt["Bewertung"], rt["Langfristiges Potenzial"]
    score = round((q + g + v + p) / 20 * 100)

    if score >= 70:
        verd, vc, vbg, vbr = "BUY",   "#86c429", "#3B6D11", "#639922"
    elif score >= 50:
        verd, vc, vbg, vbr = "HOLD",  "#f59e0b", "#1a1200", "#b45309"
    else:
        verd, vc, vbg, vbr = "WATCH", "#f87171", "#1a0505", "#ef4444"

    price  = fund.get("currentPrice")
    mcap   = fund.get("marketCap")
    fpe    = fund.get("forwardPE")
    rev    = fund.get("totalRevenue")
    gm     = fund.get("grossMargins")
    div    = fund.get("dividendYield")
    roe    = fund.get("returnOnEquity")

    price_s = f"${price:.2f}"    if isinstance(price, (int, float)) else "N/A"
    mcap_s  = f"${mcap/1e9:.0f}B" if isinstance(mcap,  (int, float)) else "N/A"
    fpe_s   = f"{fpe:.1f}×"      if isinstance(fpe,   (int, float)) else "N/A"
    rev_s   = f"${rev/1e9:.1f}B" if isinstance(rev,   (int, float)) else "N/A"
    gm_s    = f"{gm*100:.1f}%"   if isinstance(gm,    (int, float)) else "N/A"
    div_s   = f"{div*100:.2f}%"  if isinstance(div,   (int, float)) else "—"
    roe_s   = f"{roe*100:.1f}%"  if isinstance(roe,   (int, float)) else "N/A"
    rs_c    = "#86c429" if rs_score > 0 else "#f87171"

    def gws_item(label: str, active: bool) -> str:
        dot_c  = "#86c429" if active else "#334155"
        text_c = "#86c429" if active else "#64748b"
        txt    = "✓ Aktiv" if active else "✗ Inaktiv"
        return (
            f'<div style="background:#111d33;border-radius:6px;padding:10px 14px;text-align:center;border:1px solid #1e2d45">'
            f'<div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">{label}</div>'
            f'<div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{dot_c};margin-right:5px;vertical-align:middle"></span>'
            f'<span style="font-size:12px;font-weight:700;color:{text_c}">{txt}</span></div></div>'
        )

    analysis_html = _md_to_html(analysis_text)

    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{ticker} — Aktienbewertung</title>
<style>
:root{{--bg:#060b14;--bg2:#0d1526;--bg3:#111d33;--bdr:#1e2d45;
  --tx:#e2e8f0;--mu:#64748b;--gl:#86c429;--al:#f59e0b}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font-family:'Inter',system-ui,sans-serif;
  font-size:14px;line-height:1.6;padding:20px}}
.w{{max-width:960px;margin:0 auto}}
.hdr{{background:var(--bg2);border:1px solid var(--bdr);border-radius:10px;
  padding:20px 24px;margin-bottom:16px;display:flex;align-items:flex-start;
  justify-content:space-between;flex-wrap:wrap;gap:12px}}
.hdr h1{{font-size:28px;font-weight:800;letter-spacing:-.5px}}
.hdr h2{{font-size:14px;color:var(--mu);font-weight:400;margin-top:2px}}
.meta{{display:flex;gap:12px;margin-top:8px;flex-wrap:wrap}}
.mi{{font-size:12px;color:var(--mu)}}.mi span{{color:var(--tx);font-weight:600}}
.vb{{padding:8px 20px;border-radius:6px;font-size:16px;font-weight:800;letter-spacing:1px;
  background:{vbg};color:{vc};border:1px solid {vbr}}}
.g3{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px}}
@media(max-width:600px){{.g3{{grid-template-columns:repeat(2,1fr)}}}}
.card{{background:var(--bg2);border:1px solid var(--bdr);border-radius:8px;padding:14px 16px}}
.cl{{font-size:11px;color:var(--mu);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}}
.cv{{font-size:18px;font-weight:700;color:var(--gl)}}
.sec{{background:var(--bg2);border:1px solid var(--bdr);border-radius:8px;
  padding:18px 20px;margin-bottom:16px}}
.st{{font-size:13px;font-weight:700;color:var(--mu);text-transform:uppercase;
  letter-spacing:.5px;margin-bottom:14px}}
.ac h3{{font-size:12px;font-weight:700;color:var(--mu);text-transform:uppercase;
  letter-spacing:.5px;margin:16px 0 8px;padding-top:10px;border-top:1px solid var(--bdr)}}
.ac h3:first-child{{margin-top:0;padding-top:0;border-top:none}}
.ac p{{font-size:13px;margin-bottom:8px;line-height:1.6}}
.al{{padding-left:16px;margin-bottom:8px}}
.al li{{font-size:13px;margin-bottom:4px;line-height:1.5}}
.sg{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}
.sr{{background:var(--bg3);border-radius:6px;padding:10px 12px;
  display:flex;align-items:center;justify-content:space-between}}
.stars{{color:var(--al);font-size:14px;letter-spacing:1px}}
.dis{{background:var(--bg3);border:1px solid var(--bdr);border-radius:6px;
  padding:10px 14px;font-size:11px;color:var(--mu);line-height:1.5;margin-top:16px}}
</style>
</head>
<body>
<div style="background:#0a1628;border-bottom:1px solid #1e2d45;padding:7px 20px;
  font-size:11px;color:#64748b;display:flex;justify-content:space-between;align-items:center">
  <span>KI-Aktienbewertung &middot; RS-Platform</span>
  <span>&#128337; Letzte Aktualisierung: <strong style="color:#94a3b8">{today}</strong></span>
</div>
<div class="w">
  <div class="hdr">
    <div>
      <h1>{ticker}</h1>
      <h2>{short_name}</h2>
      <div class="meta">
        <div class="mi">Sektor: <span>{sector}</span></div>
        <div class="mi">Industrie: <span>{industry}</span></div>
        <div class="mi">MCap: <span>{mcap_s}</span></div>
        <div class="mi">Signal: <span>{sig_type}</span></div>
      </div>
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px">
      <div class="vb">{verd}</div>
      <div style="font-size:12px;color:var(--mu);text-align:right">
        Score: <strong style="color:{vc};font-size:20px">{score}</strong><span style="color:var(--mu)">/100</span>
      </div>
      <div style="font-size:11px;color:var(--mu)">Erstellt: {today}</div>
      <div style="font-size:11px;color:var(--mu)">RS-Score: <span style="color:{rs_c};font-weight:700">{rs_score:.1f}</span></div>
    </div>
  </div>

  <div class="g3">
    <div class="card"><div class="cl">Kurs</div><div class="cv" style="color:var(--tx)">{price_s}</div></div>
    <div class="card"><div class="cl">Forward PE</div><div class="cv">{fpe_s}</div></div>
    <div class="card"><div class="cl">Revenue (TTM)</div><div class="cv">{rev_s}</div></div>
    <div class="card"><div class="cl">Gross Margin</div><div class="cv">{gm_s}</div></div>
    <div class="card"><div class="cl">Dividende</div><div class="cv" style="color:var(--al)">{div_s}</div></div>
    <div class="card"><div class="cl">ROE</div><div class="cv">{roe_s}</div></div>
  </div>

  <div class="sec">
    <div class="st">GWS-Ampel — Breakout-Status</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
      {gws_item("Weekly", bool(gws.get("weekly")))}
      {gws_item("Daily",  bool(gws.get("daily")))}
      {gws_item("4H",     bool(gws.get("h4")))}
    </div>
  </div>

  <div class="sec">
    <div class="st">Professionelle Analyse</div>
    <div class="ac">{analysis_html}</div>
  </div>

  <div class="sec">
    <div class="st">Gesamteinschätzung</div>
    <div class="sg">
      <div class="sr"><span style="font-size:12px;color:var(--mu)">Qualität</span><span class="stars">{_stars(q)}</span></div>
      <div class="sr"><span style="font-size:12px;color:var(--mu)">Wachstum</span><span class="stars">{_stars(g)}</span></div>
      <div class="sr"><span style="font-size:12px;color:var(--mu)">Bewertung</span><span class="stars">{_stars(v)}</span></div>
      <div class="sr"><span style="font-size:12px;color:var(--mu)">Langfrist. Potenzial</span><span class="stars">{_stars(p)}</span></div>
    </div>
  </div>

  <div class="dis">Keine Anlageberatung. KI-generierte Analyse auf Basis öffentlicher Daten zum Zeitpunkt des GWS-Breakout-Signals. Kurse können verzögert oder veraltet sein. Eigene Recherche empfohlen.</div>
</div>
</body>
</html>'''


# ── Index-Verwaltung ──────────────────────────────────────────────────────────

def load_index() -> dict:
    RATINGS_DIR.mkdir(parents=True, exist_ok=True)
    p = RATINGS_DIR / "index.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"ratings": []}


def save_index(data: dict):
    with open(RATINGS_DIR / "index.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Haupt-Funktion ────────────────────────────────────────────────────────────

def generate_for_ticker(ticker: str, rs_score: float, windows: dict, gws: dict) -> bool:
    """
    Generiert eine KI-Analyse für einen Breakout-Ticker.
    Wird von check_alerts.py und check_4h_reentry.py aufgerufen.
    Gibt True zurück bei Erfolg.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"  generate_rating: GEMINI_API_KEY nicht gesetzt — übersprungen")
        return False

    print(f"  Generiere Rating für {ticker}...")

    fund    = fetch_fundamentals(ticker)
    context = build_context(ticker, fund, rs_score, windows, gws)

    import requests as _req
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": context}]}],
    }
    try:
        resp = _req.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data     = resp.json()
        analysis = data["candidates"][0]["content"]["parts"][0]["text"]
        usage    = data.get("usageMetadata", {})
        print(f"  Tokens: input={usage.get('promptTokenCount')}  output={usage.get('candidatesTokenCount')}")
    except Exception as e:
        print(f"  Gemini API Fehler für {ticker}: {e}")
        return False

    rt    = _extract_ratings(analysis)
    q, g, v, p = rt["Qualität"], rt["Wachstum"], rt["Bewertung"], rt["Langfristiges Potenzial"]
    score = round((q + g + v + p) / 20 * 100)
    verd  = "BUY" if score >= 70 else ("HOLD" if score >= 50 else "WATCH")

    html = build_html(ticker, fund, analysis, rs_score, gws)

    RATINGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RATINGS_DIR / f"{_safe_name(ticker)}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Gespeichert: {out_path}")

    idx = load_index()
    idx["ratings"] = [r for r in idx["ratings"] if r.get("ticker", "").upper() != ticker.upper()]
    idx["ratings"].append({
        "ticker":     ticker.upper(),
        "verdict":    verd,
        "score":      score,
        "created_at": datetime.now().isoformat(),
    })
    save_index(idx)
    print(f"  Index aktualisiert: {len(idx['ratings'])} Rating(s)")

    return True


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Verwendung: python generate_rating.py TICKER [TICKER2 ...]")
        sys.exit(1)

    # Spezial-Keywords in echte Ticker-Listen expandieren
    KEYWORDS = {
        "DAX_TOP20":     ("data/rs_dax.json",   "rs_dax.json",   20),
        "SP500_TOP20":   ("data/rs_sp500.json",  "rs_sp500.json", 20),
        "NASDAQ_TOP20":  ("data/rs_full.json",   "rs_full.json",  20),
    }

    raw_args = [t.upper() for t in sys.argv[1:]]
    tickers = []
    for arg in raw_args:
        if arg in KEYWORDS:
            paths = KEYWORDS[arg]
            for fname in (paths[0], paths[1]):
                if Path(fname).exists():
                    with open(fname) as f:
                        entries = json.load(f).get("data", [])
                    expanded = [e["ticker"].upper() for e in entries[:paths[2]]]
                    print(f"  {arg} → {expanded}")
                    tickers.extend(expanded)
                    break
            else:
                print(f"  Warnung: Datei für {arg} nicht gefunden")
        else:
            tickers.append(arg)

    if not tickers:
        print("Keine Ticker gefunden.")
        sys.exit(1)

    # RS-Daten aller verfügbaren Dateien laden (Score + Windows)
    rs_data = {}
    for fname in ("rs_full.json", "data/rs_full.json",
                  "rs_dax.json",  "data/rs_dax.json",
                  "rs_sp500.json","data/rs_sp500.json"):
        if Path(fname).exists():
            with open(fname) as f:
                for entry in json.load(f).get("data", []):
                    rs_data[entry["ticker"].upper()] = entry

    print(f"RS-Daten geladen: {len(rs_data)} Einträge")

    for ticker in tickers:
        entry    = rs_data.get(ticker, {})
        rs_score = entry.get("score", 0.0)
        windows  = entry.get("windows", {})
        gws = {
            "weekly":      True,
            "daily":       True,
            "h4":          True,
            "points":      3,
            "signal_type": "Manuell generiert",
        }
        ok = generate_for_ticker(ticker, rs_score, windows, gws)
        print(f"  {ticker}: {'OK' if ok else 'FEHLER'}")
