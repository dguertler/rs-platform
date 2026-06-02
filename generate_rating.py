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

RATINGS_DIR  = Path("data/ratings")
ANALYSES_DIR = Path("analyses")

# ── System-Prompt (wird gecacht — spart ~90% Input-Token-Kosten) ─────────────

SYSTEM_PROMPT = """Du bist ein institutioneller Investor, Hedgefonds-Analyst und ehemaliger Portfolio-Manager mit Fokus auf:
- Technologie
- AI-Infrastruktur
- Halbleiter
- Makro
- Energie
- Compounder-Aktien
- Marktpsychologie

Du analysierst eine Aktie anhand bereitgestellter Fundamentaldaten und RS-Platform-Signaldaten. Die Analyse soll NICHT wie eine klassische Analysten-Zusammenfassung klingen, sondern wie eine ehrliche professionelle Einschätzung eines erfahrenen Börsenprofis.
WICHTIG: Schreibe die gesamte Analyse OHNE horizontale Trennlinien.

STIL & TON
- Schreibe klar, direkt und intelligent — auf Deutsch
- Keine generischen Floskeln oder Marketing-Sprache
- Erkläre die eigentlichen Treiber hinter der Aktie — Ursache-Wirkung, nicht nur Kennzahlen
- Denke wie institutionelle Investoren: Was preist der Markt ein, was übersieht er?
- Ehrlich über Risiken und Schwächen — kein Schönreden
- Professionell, aber nicht steril

PFLICHT-STRUKTUR

## 1. INVESTMENT-CASE
Max. 6–8 Sätze. Was ist die eigentliche Story hinter der Aktie — nicht das offensichtliche Narrativ, sondern der strukturelle Kern? Warum ist das jetzt relevant? Was übersieht der Markt gerade noch?

## 2. GESCHÄFTSMODELL
Max. 8–10 Bullet Points mit -. Keine Selbstverständlichkeiten. Fokus auf: Wie verdient das Unternehmen wirklich Geld? Wo liegt der operative Hebel? Wo liegt die strukturelle Abhängigkeit?

## 3. BULL CASE
Konkret und quantifiziert wo möglich. Welche spezifischen Faktoren müssen eintreten? Nenne reale Datenpunkte, Analystenziele oder strukturelle Argumente. Kursziel-Bandbreite und Eintrittswahrscheinlichkeit in Prozent nennen.

## 4. BASE CASE
Wahrscheinlichstes Szenario auf Sicht 12–18 Monate unter aktuellen Marktbedingungen — nicht das rechnerische Mittel zwischen Bull und Bear. Kursziel-Bandbreite angeben. Eintrittswahrscheinlichkeit in Prozent nennen.

## 5. BEAR CASE
Gleiche Tiefe wie Bull Case. Welches Szenario zerstört die These? Nenne den konkreten Auslöser — nicht nur "Zyklus dreht". Was passiert mit der Bewertung in diesem Fall? Kursziel-Bandbreite und Eintrittswahrscheinlichkeit in Prozent nennen.

Bull + Base + Bear müssen exakt 100% ergeben — Summe am Ende von Abschnitt 5 ausweisen.

## 6. FUNDAMENTALE QUALITÄT
Konkrete Kennzahlen: ROE, ROIC, Margen, Bilanzqualität, Free Cashflow. Wichtig: Bewerte die Kennzahlen im Zykluskontext — Top-of-Cycle-Zahlen anders gewichten als normalisierte Werte. Wo liegt der echte wirtschaftliche Burggraben, wo ist er nur scheinbar?
Pflicht: ROIC im Verhältnis zu den Kapitalkosten (WACC) bewerten — schafft das Unternehmen Wert ÜBER den Kapitalkosten? Nutze Beta zur Plausibilisierung der Eigenkapitalkosten (Beta > 1,5 ⇒ erhöhte Kapitalkosten und Drawdown-Sensitivität explizit benennen). FCF-Conversion (Free Cashflow / Nettogewinn) ausweisen und einordnen.
Bei NEGATIVEM Eigenkapital: P/B und Debt/Equity sind Artefakte — kommentarlos überspringen (nicht erklären, nicht erwähnen); stattdessen Net Debt/EBITDA heranziehen. Sind diese Größen nicht aus den gelieferten Daten berechenbar, explizit als Datenlücke kennzeichnen — niemals "Schulden manageable" o.ä. ohne Kennzahl behaupten.

## 7. BEWERTUNG
Niemals eine zyklische Aktie nur anhand des aktuellen KGVs bewerten. Pflicht: Bewertung über normalisierten FCF über den vollen Zyklus oder KBV. Zusätzlich Forward-Multiples und was der Markt damit implizit aussagt. Ist die aktuelle Bewertung eine Value-Falle, eine strukturierte Wette oder echtes Upside?
Eine hohe Trailing-Bewertung NICHT nur als "verzerrt" abtun, sondern die vom Markt IMPLIZIT eingepreiste Erwartung explizit ausrechnen (z.B. "Forward-PE 33x impliziert ~2,5-fachen Gewinn") und einen Mid-Cycle-Ertragsanker nennen (oder als Datenlücke kennzeichnen).
Das gelieferte Analysten-Konsensziel (targetMeanPrice) und die Empfehlung (recommendationKey) sind IMMER zu verwenden, sofern nicht N/A — niemals als "nicht verfügbar" bezeichnen, wenn ein Wert vorliegt. Konsensziel ins Verhältnis zum aktuellen Kurs setzen (Kurs ÜBER Konsensziel = Markt handelt bereits über der Sell-Side).

## 8. MARKTPSYCHOLOGIE & POSITIONIERUNG
Wie ist die institutionelle Positionierung aktuell? Short Float, Fast Money vs. Long Only, FOMO-Dynamik. Was muss künftig passieren, damit neue Käufer anziehen? Wo liegt das Enttäuschungsrisiko?

## 9. TECHNISCHE EINSCHÄTZUNG / MOMENTUM
Trendstruktur, SMA-Stellung, RSI. Es werden berechnete Indikatoren geliefert (SMA50, SMA200, RSI14, Abstand zum 52W-Hoch) — diese verwenden. Volumen ist NICHT verfügbar und darf nicht erfunden werden. "GWS NICHT AKTIV" bedeutet "kein Breakout-Signal", NICHT "Daten nicht verfügbar".
Parabolik-Check: Steht der Kurs >90% am 52W-Hoch UND mehr als 3x über dem 52W-Tief, das Mean-Reversion-/Drawdown-Risiko explizit benennen.
Ist das Momentum fundamental gestützt oder rein reaktiv? Was wäre ein technisches Warnsignal?

## 10. LANGFRISTIGES POTENZIAL (3–5 Jahre)
Drei explizite Szenarien mit Kurszielbandbreiten: Bull / Base / Bear. Was ist die entscheidende Variable, die zwischen den Szenarien unterscheidet?

## 11. PROFI-FAZIT
Klare Positionierung: Ist das ein Buy-and-Hold-Compounder, ein zyklischer Trading-Trade oder ein High-Conviction-Momentum-Play? Für welchen Investorentyp geeignet? Explizite Risikowarnung zur Positionsgröße wenn relevant. Kein Herumdrucksen — klare Aussage. Max. 2–3 direkte Peers nennen: Wer ist das reinere Instrument für die These, wo ist die relative Bewertung attraktiver?

Rating (Zahl, nicht Sterne):
- Qualität: X/5
- Wachstum: X/5
- Bewertung: X/5
- Katalysator: X/5

Katalysator bewertet die Stärke und Nachhaltigkeit des fundamentalen Auslösers
hinter dem Momentum-Signal: Earnings-Beat, Guidance-Anhebung, Produktzyklus,
Sektorrotation oder Makro-Tailwind.
5 = starker, nachhaltiger fundamentaler Treiber.
1 = kein erkennbarer fundamentaler Katalysator — rein technisches Momentum.

## 12. FAZIT & KLASSIFIKATION
2–3 Sätze Schluss-Fazit, dann eine explizite Klassifikation aus dieser festen Taxonomie. Die Klassifikation ist REIN FUNDAMENTAL — der RS-Score und das Momentum fließen NICHT in die Einstufung ein, sie dienen nur als Kontext:
- CHAMPION — herausragende Qualität, Wachstum UND Katalysator; Top-Konviktion
- AUFSTREBENDER CHAMPION — starke Fundamentaldaten im Aufbau; Ziel ist, solche Kandidaten FRÜH zu erkennen, bevor der breite Markt sie einpreist (Hidden-Champion-Logik)
- SOLIDE — überdurchschnittlich, aber kein Marktführer-Profil
- NEUTRAL — marktkonform, kein Edge
- SCHWACH — fundamentale Schwächen überwiegen
Kennzeichne explizit, ob es sich um einen "Hidden Champion" handelt (fundamental stark, aber vom Markt — gemessen am RS-Score — noch nicht erkannt) oder um einen bereits "bestätigten Leader" (fundamental stark UND hohes RS-Momentum, also schon eingepreist). Der höchste Wert liegt in fundamental starken Titeln mit noch niedrigem RS.
Die maßgebliche, screenbare Klassifikation berechnet die Pipeline deterministisch aus den vier Sub-Ratings — formuliere konsistent dazu.

FORMATIERUNGS-REGELN
- ## für Hauptüberschriften (exakt wie in der Struktur angegeben)
- - als Bullet-Marker (kein •)
- MAX. 1300 Wörter gesamt
- Sprache: DEUTSCH
- Keine horizontalen Trennlinien
- Konkrete Zahlen > vage Formulierungen — wo immer möglich

DATENVERFÜGBARKEIT
Fehlende oder als "N/A" markierte Kennzahlen nicht interpolieren oder
schätzen. Explizit als "nicht verfügbar" kennzeichnen und die Analyse
entsprechend einschränken.
Als "UNGÜLTIG (Wert)" markierte Kennzahlen sind yfinance-Artefakte —
nicht verwenden, nicht erwähnen, nicht in die Analyse einbeziehen.
Keine Kennzahlen erfinden oder aus dem Kontext ableiten.
Neu gelistete Ticker oder Spin-offs können unvollständige TTM-Daten
haben — dies explizit im Investment-Case erwähnen wenn mehr als 3
Felder N/A oder UNGÜLTIG sind.

DATENVERBINDLICHKEIT
Jede in der Analyse genannte Zahl muss auf ein geliefertes Datenfeld
zurückführbar sein — nicht zurückführbare Zahlen weglassen oder klar
als Annahme kennzeichnen. targetMeanPrice (Analysten-Konsensziel) und
recommendationKey werden im Kontext geliefert: bei vorhandenem Wert
immer nutzen, nie als "nicht verfügbar" bezeichnen.

MOMENTUM IST KEIN BEWEIS
RS-Score und vergangene Performance belegen NICHT die fundamentale
These — sie messen nur vergangene relative Kursbewegung und
Konsens-Popularität. Fundamentale Argumentation (§1, §6, §7) und
Momentum-Lesart (§9) strikt trennen. Steigende Kurse oder ein hoher
RS-Score niemals als Bestätigung der These anführen.

STRUKTURELLE GESCHÄFTSMODELL-ANALYSE
Im Investment-Case explizit prüfen ob strukturelle
Geschäftsmodell-Veränderungen die Zyklus-These abschwächen
oder widerlegen — z.B. langfristige Lieferverträge,
Multi-Year-Abnahmevereinbarungen oder strategische
Partnerschaften mit Hyperscalern. Falls solche Strukturen
aus den Fundamentaldaten oder dem Marktkontext erkennbar
sind, müssen sie bewertet werden: Verändern sie das
Risikoprofil fundamental oder sind sie zyklisch überlagert?

BASE CASE VALIDIERUNG
Das Kursziel im Base Case muss konsistent mit der
zugehörigen Wahrscheinlichkeit sein: Ein Base Case mit
negativem Kurspotenzial von über 30% vom aktuellen Kurs
ist definitorisch kein Base Case sondern ein Bear Case.
Entsprechend neu einordnen.

STRUKTURELLE MARGENNACHHALTIGKEIT
Im Bull Case explizit begründen warum das Unternehmen
dauerhaft höhere Margen als historische Zyklus-Mittelwerte
erzielen könnte. Konkret adressieren:
- Technologieführerschaft oder proprietäres IP
- Produktmix-Verschiebung zu höhermargigen Segmenten
- Wettbewerbsposition vs. direkten Peers
- Kundenbindung durch Switching Costs oder Vertragsstrukturen
- Skalierungseffekte oder operative Hebelwirkung
Falls diese Begründung nicht aus den verfügbaren Daten
ableitbar ist: explizit als "strukturelle Differenzierung
nicht beurteilbar auf Basis verfügbarer Daten" kennzeichnen.
Niemals Margennachhaltigkeit implizieren ohne Begründung.

UMSATZBASIS BEI NEUEN ODER RESTRUKTURIERTEN UNTERNEHMEN
Falls das Unternehmen jünger als 12 Monate gelistet ist,
einen Spin-off durchgeführt hat oder eine wesentliche
Restrukturierung hinter sich hat: TTM-Kennzahlen explizit
als möglicherweise verzerrt kennzeichnen. Stattdessen
annualisierten Run-Rate auf Basis des letzten Quartals
als primäre Bewertungsbasis verwenden und dies transparent
ausweisen. Beispiel: "TTM Revenue $X Mrd. (Spin-off-verzerrt),
annualisierter Run-Rate Q3: $Y Mrd."

ANALYSTENKURSZIELE KORREKT EINORDNEN
Analystenkursziele nie als Ceiling oder als Konsens-Wahrheit
behandeln. Standardmäßig einordnen als:
- Oft 6–12 Monate hinter starken Kursbewegungen
- Bei Spin-offs und neuen Listings häufig noch unreife Modelle
- Relevant als Sentiment-Indikator, nicht als fairer Wert
Formulierung: "Analyst-Konsensziel X USD — als
Orientierungspunkt, nicht als Kursziel-Ceiling zu verstehen." """


# ── Fundamentaldaten ──────────────────────────────────────────────────────────

PLAUSIBILITY = {
    "grossMargins":     (0.0, 1.0),
    "operatingMargins": (-1.0, 1.0),
    "profitMargins":    (-1.0, 1.0),
    "returnOnEquity":   (-5.0, 10.0),
    "debtToEquity":     (0.0, 2000.0),
    "trailingPE":       (0.0, 2000.0),
    "forwardPE":        (0.0, 500.0),
    "revenueGrowth":    (-1.0, 50.0),
    "beta":             (-3.0, 10.0),
}

def validate_fundamentals(data: dict) -> dict:
    cleaned = {}
    for key, value in data.items():
        if value is None:
            cleaned[key] = "N/A"
            continue
        if key in PLAUSIBILITY:
            try:
                lo, hi = PLAUSIBILITY[key]
                if not (lo <= float(value) <= hi):
                    cleaned[key] = f"UNGÜLTIG ({value})"
                    continue
            except (TypeError, ValueError):
                cleaned[key] = "N/A"
                continue
        cleaned[key] = value
    return cleaned


def fetch_fundamentals(ticker: str) -> dict:
    try:
        import yfinance as yf  # lazy: nur für den Live-Fallback nötig
        info = yf.Ticker(ticker).info or {}
        raw = {
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
        return validate_fundamentals(raw)
    except Exception as e:
        print(f"  Fundamentaldaten für {ticker} fehlgeschlagen: {e}")
        return {}


def load_fundamentals(ticker: str) -> dict:
    """Lädt Fundamentaldaten aus data/fundamentals.json; Fallback auf live yfinance."""
    p = Path("data/fundamentals.json")
    if p.exists():
        with open(p, encoding="utf-8") as f:
            cached = json.load(f)
        fund = cached.get("tickers", {}).get(ticker.upper())
        if fund:
            updated = cached.get("updated_at", "unbekannt")[:10]
            print(f"  Fundamentaldaten aus Cache ({updated})")
            return fund
    print(f"  {ticker} nicht in fundamentals.json — live fetch via yfinance...")
    return fetch_fundamentals(ticker)


def _pct(v):
    return f"{v * 100:.1f}%" if isinstance(v, (int, float)) else "N/A" if v is None else str(v)

def _bn(v):
    return f"${v / 1e9:.2f} Mrd." if isinstance(v, (int, float)) else "N/A" if v is None else str(v)

def _fmt(v):
    return str(round(v, 2)) if isinstance(v, (int, float)) else "N/A" if v is None else str(v)


def _num(v):
    """True, wenn v eine echte Zahl ist (kein N/A / UNGÜLTIG-String)."""
    return isinstance(v, (int, float))


# ── Verdict-Logik (risikoadjustiert) ──────────────────────────────────────────

def compute_verdict(rt: dict) -> tuple:
    """
    Risikoadjustiertes Verdict aus den vier Sub-Ratings.
    - Bewertung wird stärker gewichtet als der reine Mittelwert.
    - Hard Cap: schwache Bewertung (<=2/5) deckelt das Verdict auf HOLD.
    Gibt (score:int, verdict:str) zurück.
    """
    q, g, v, p = rt["Qualität"], rt["Wachstum"], rt["Bewertung"], rt["Katalysator"]
    score = round((0.20 * q + 0.25 * g + 0.30 * v + 0.25 * p) / 5 * 100)
    if v <= 2:                       # keine Sicherheitsmarge → kein BUY
        score = min(score, 69)
    verd = "BUY" if score >= 70 else ("HOLD" if score >= 50 else "WATCH")
    return score, verd


# ── Leadership / Hidden-Champion-Klassifikation ───────────────────────────────
# WICHTIG: Der RS-Score fließt NICHT in den Klassifikations-Score ein. Die
# Klassifikation ist rein fundamental (Qualität/Wachstum/Katalysator/Bewertung).
# Der RS-Score dient ausschließlich als nicht-bewertendes Overlay, um einen noch
# nicht erkannten "Hidden Champion" von einem bereits bestätigten Leader zu
# unterscheiden — genau die Marvell-vor-Durchbruch-Situation.

_RS_SCORES_CACHE = None

def _all_rs_scores() -> list:
    global _RS_SCORES_CACHE
    if _RS_SCORES_CACHE is not None:
        return _RS_SCORES_CACHE
    scores, seen = [], set()
    for fname in ("data/rs_full.json", "rs_full.json",
                  "data/rs_dax.json",  "rs_dax.json",
                  "data/rs_sp500.json","rs_sp500.json"):
        p = Path(fname)
        if not p.exists():
            continue
        try:
            for e in json.load(open(p, encoding="utf-8")).get("data", []):
                t, s = e.get("ticker"), e.get("score")
                if t and _num(s) and t.upper() not in seen:
                    seen.add(t.upper())
                    scores.append(s)
        except Exception:
            continue
    _RS_SCORES_CACHE = scores
    return scores


def rs_percentile(rs_score) -> int:
    """Perzentil (0–100) des RS-Scores im Gesamt-Universum. None wenn unbekannt."""
    scores = _all_rs_scores()
    if not scores or not _num(rs_score):
        return None
    return round(100 * sum(1 for s in scores if s <= rs_score) / len(scores))


def champion_score(rt: dict) -> int:
    """
    Fundamentale Überzeugung (0–100) — OHNE RS/Momentum.
    Qualität, Wachstum und Katalysator tragen die Substanz; eine attraktive
    Bewertung gibt einen Bonus (Hidden Champion = stark UND noch nicht teuer).
    """
    q, g, v, p = rt["Qualität"], rt["Wachstum"], rt["Bewertung"], rt["Katalysator"]
    return round((0.30 * q + 0.30 * g + 0.25 * p + 0.15 * v) / 5 * 100)


def classify_leadership(rt: dict, rs_score) -> dict:
    cs = champion_score(rt)
    if   cs >= 80: emoji, tier = "🏆", "CHAMPION"
    elif cs >= 65: emoji, tier = "🚀", "AUFSTREBENDER CHAMPION"
    elif cs >= 50: emoji, tier = "✅", "SOLIDE"
    elif cs >= 35: emoji, tier = "⚖️", "NEUTRAL"
    else:          emoji, tier = "⚠️", "SCHWACH"

    pct = rs_percentile(rs_score)
    if   pct is None: recognition = ""
    elif pct < 40:    recognition = f"💎 Hidden — vom Markt noch nicht erkannt (RS-Perzentil {pct})"
    elif pct >= 80:   recognition = f"Bestätigter Leader — bereits eingepreist (RS-Perzentil {pct})"
    else:             recognition = f"im Aufbau (RS-Perzentil {pct})"

    risk = "⚡ Hohes Bewertungsrisiko" if rt["Bewertung"] <= 2 else ""
    return {
        "tier":            tier,
        "emoji":           emoji,
        "champion_score":  cs,
        "rs_percentile":   pct,
        "recognition":     recognition,
        "risk_flag":       risk,
    }


# ── Technische Indikatoren (aus Tagesdaten der RS-JSONs) ──────────────────────

def _rsi(closes: list, period: int = 14):
    if len(closes) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(-period, 0):
        ch = closes[i] - closes[i - 1]
        if ch >= 0: gains += ch
        else:       losses -= ch
    avg_g, avg_l = gains / period, losses / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return round(100 - 100 / (1 + rs), 1)


def compute_technicals(entry: dict, fund: dict) -> dict:
    """SMA50/200, RSI14, Trendstruktur und 52W-Position aus der Tagesserie."""
    o = (entry or {}).get("ohlcv") or []
    closes = [c["c"] for c in o if isinstance(c, dict) and _num(c.get("c"))]
    if len(closes) < 50:
        return None
    last = closes[-1]
    sma50  = sum(closes[-50:]) / 50
    sma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
    hi52   = fund.get("fiftyTwoWeekHigh")
    lo52   = fund.get("fiftyTwoWeekLow")
    tech = {
        "last":     round(last, 2),
        "sma50":    round(sma50, 2),
        "sma200":   round(sma200, 2) if sma200 else None,
        "rsi14":    _rsi(closes, 14),
        "vs_sma50": round((last / sma50 - 1) * 100, 1),
        "vs_sma200":round((last / sma200 - 1) * 100, 1) if sma200 else None,
        "below_52w_high": round((last / hi52 - 1) * 100, 1) if _num(hi52) and hi52 else None,
        "above_52w_low":  round((last / lo52 - 1) * 100, 1) if _num(lo52) and lo52 else None,
    }
    if sma200:
        tech["stage"] = "Stage 2 (Aufwärtstrend: Kurs > SMA50 > SMA200)" \
            if last > sma50 > sma200 else "kein sauberer Aufwärtstrend"
    return tech


def build_context(ticker: str, fund: dict, rs_score: float, windows: dict, gws: dict, tech: dict = None) -> str:
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
HINWEIS: "NICHT AKTIV" bedeutet "kein Breakout-Signal", NICHT "Daten nicht verfügbar".

{_tech_block(tech)}
HINWEIS ZUR DATENVERBINDLICHKEIT: Analysten-Konsensziel (targetMeanPrice) und
recommendationKey sind oben enthalten — bei vorhandenem Wert immer nutzen, nie
als "nicht verfügbar" bezeichnen. Jede in der Analyse genannte Zahl muss auf ein
hier geliefertes Feld zurückführbar sein.

Analysiere jetzt: {ticker}"""


def _tech_block(tech: dict) -> str:
    if not tech:
        return ("TECHNISCHE INDIKATOREN: nicht verfügbar (zu wenige Kursdaten). "
                "Volumen ist generell NICHT verfügbar.")
    parts = [
        "TECHNISCHE INDIKATOREN (aus Tagesdaten berechnet; Volumen NICHT verfügbar):",
        f"- Kurs: {tech.get('last')} | SMA50: {tech.get('sma50')} | SMA200: {tech.get('sma200')}",
        f"- Abstand zu SMA50: {tech.get('vs_sma50')}% | zu SMA200: {tech.get('vs_sma200')}%",
        f"- RSI(14): {tech.get('rsi14')}",
        f"- Abstand zum 52W-Hoch: {tech.get('below_52w_high')}% | über 52W-Tief: {tech.get('above_52w_low')}%",
    ]
    if tech.get("stage"):
        parts.append(f"- Trendstruktur: {tech['stage']}")
    return "\n".join(parts)


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
    for cat in ["Qualität", "Wachstum", "Bewertung", "Katalysator"]:
        m = re.search(rf'{re.escape(cat)}:\s*(\d)/5', text)
        out[cat] = int(m.group(1)) if m else 3
    return out


def _extract_scenarios(text: str) -> dict:
    result = {"bull": {"price": "N/A", "prob": "N/A"},
              "base": {"price": "N/A", "prob": "N/A"},
              "bear": {"price": "N/A", "prob": "N/A"}}

    def _price(s: str) -> str:
        def _from(txt: str) -> str:
            # Range + explicit currency: "2.450–2.800 USD"
            m = re.search(r'(\d[\d.]*\s*[–—-]+\s*[\d.,]+)\s*(USD|EUR|€)', txt)
            if m:
                return f"{m.group(1).strip()} {m.group(2)}"
            # "$X–$Y" or "$X-Y" dollar range
            m = re.search(r'\$\s*(\d[\d.,]+)\s*[–—-]+\s*\$?\s*(\d[\d.,]+)', txt)
            if m:
                return f"${m.group(1)}–${m.group(2)}"
            # "$X+" or "$X" single dollar value
            m = re.search(r'\$\s*(\d[\d.,]+\+?)', txt)
            if m:
                return f"${m.group(1)}"
            # "45 USD" or "90+ USD" — single value with explicit currency
            m = re.search(r'(\d[\d.,]+\+?)\s*(USD|EUR|€)', txt)
            if m:
                return f"{m.group(1)} {m.group(2)}"
            # Bare range — NOT followed by % (avoids matching e.g. "9-10%")
            m = re.search(r'(\d[\d.,]*\s*[–—-]+\s*[\d.,]+)(?!\s*%)', txt)
            if m:
                return m.group(1).strip()
            return "N/A"
        # Prioritize value after "Kursziel" keyword
        kz = re.search(r'Kursziel[:\s]+(.{1,60})', s, re.IGNORECASE)
        if kz:
            p = _from(kz.group(1))
            if p != "N/A":
                return p.rstrip('.,').strip()
        p = _from(s)
        return p.rstrip('.,').strip() if p != "N/A" else "N/A"

    def _prob(s: str) -> str:
        m = re.search(r'(?:Eintrittswahrscheinlichkeit|Wahrscheinlichkeit)[:\s]*(\d+)\s*%', s, re.IGNORECASE)
        return f"{m.group(1)}%" if m else "N/A"

    # ── Neue Struktur: BULL/BASE/BEAR CASE Abschnitte ────────────────────────
    for case, key in [("BULL", "bull"), ("BASE", "base"), ("BEAR", "bear")]:
        m = re.search(
            rf'##\s*\d*\.?\s*{case}\s+CASE\b(.*?)(?=\n\s*##|\Z)',
            text, re.DOTALL | re.IGNORECASE
        )
        if not m:
            continue
        section = m.group(1)
        prob = _prob(section)
        if prob != "N/A":
            result[key] = {"price": _price(section), "prob": prob}

    # ── Alte Struktur: LANGFRISTIGES POTENZIAL Abschnitt ─────────────────────
    if all(result[k]["prob"] == "N/A" for k in ["bull", "base", "bear"]):
        lt_m = re.search(
            r'##\s*\d*\.?\s*LANGFRISTIG[^\n]*\n(.*?)(?=\n\s*##|\Z)',
            text, re.DOTALL | re.IGNORECASE
        )
        if lt_m:
            entries = []  # (label_lower, price, prob)
            for line in lt_m.group(1).split('\n'):
                line = line.strip()
                p = _prob(line)
                if p == "N/A":
                    continue
                # Extract label: strip leading *, get text before first ':'
                stripped = line.lstrip('*').lstrip()
                colon = stripped.find(':')
                label = stripped[:colon].rstrip('*').strip().lower() if colon > 0 else ""
                entries.append((label, _price(line), p))

            bear_kw  = ('konservativ', 'bear', 'bär', 'negativ')
            bull_kw  = ('bull',)
            extrm_kw = ('extrem',)

            bears  = [(l, p, pr) for l, p, pr in entries if any(k in l for k in bear_kw)]
            extrm  = [(l, p, pr) for l, p, pr in entries if any(k in l for k in extrm_kw)]
            bulls  = [(l, p, pr) for l, p, pr in entries if any(k in l for k in bull_kw)
                      and not any(k in l for k in extrm_kw)]

            # Konservativ → bear card, Bull Case → base card, Extrem-Bull → bull card
            if bears:
                result["bear"] = {"price": bears[0][1], "prob": bears[0][2]}
            if bulls:
                result["base"] = {"price": bulls[0][1], "prob": bulls[0][2]}
            if extrm:
                result["bull"] = {"price": extrm[0][1], "prob": extrm[0][2]}
            elif bulls and len(bulls) > 1:
                result["bull"] = {"price": bulls[-1][1], "prob": bulls[-1][2]}

    return result


def _safe_name(ticker: str) -> str:
    return re.sub(r'[^a-z0-9]', '_', ticker.lower())


def build_html(ticker: str, fund: dict, analysis_text: str, rs_score: float, gws: dict) -> str:
    today = datetime.now().strftime("%d.%m.%Y")
    short_name = fund.get("shortName", ticker)
    sector     = fund.get("sector",    "N/A")
    industry   = fund.get("industry",  "N/A")
    sig_type   = gws.get("signal_type", "Breakout")

    rt = _extract_ratings(analysis_text)
    q, g, v, p = rt["Qualität"], rt["Wachstum"], rt["Bewertung"], rt["Katalysator"]
    score, verd = compute_verdict(rt)
    cls = classify_leadership(rt, rs_score)
    sc = _extract_scenarios(analysis_text)

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
    rs_c    = "#86c429" if rs_score > 0 else "#f87171"

    # ROE-Card nur rendern, wenn echter Zahlenwert (kein N/A / UNGÜLTIG-Artefakt)
    roe_card = (f'<div class="card"><div class="cl">ROE</div>'
                f'<div class="cv">{roe*100:.1f}%</div></div>'
                ) if isinstance(roe, (int, float)) else ""

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

    def sc_card(label: str, icon: str, pv: str, prob: str, bg: str, bdr: str, clr: str) -> str:
        return (
            f'<div style="background:{bg};border:1px solid {bdr};border-radius:8px;padding:14px 16px;text-align:center">'
            f'<div style="font-size:10px;color:{clr};text-transform:uppercase;font-weight:700;letter-spacing:1px;margin-bottom:10px">{icon} {label}</div>'
            f'<div style="font-size:11px;color:#64748b;margin-bottom:3px">Kursziel</div>'
            f'<div style="font-size:13px;font-weight:700;color:#e2e8f0;margin-bottom:8px">{pv}</div>'
            f'<div style="font-size:11px;color:#64748b;margin-bottom:3px">Wahrscheinlichkeit</div>'
            f'<div style="font-size:20px;font-weight:800;color:{clr}">{prob}</div>'
            f'</div>'
        )

    bull_card = sc_card("Bull Case", "▲", sc["bull"]["price"], sc["bull"]["prob"], "#0a1a00", "#2d5a00", "#86c429")
    base_card = sc_card("Base Case", "◆", sc["base"]["price"], sc["base"]["prob"], "#111d33", "#1e2d45", "#f59e0b")
    bear_card = sc_card("Bear Case", "▼", sc["bear"]["price"], sc["bear"]["prob"], "#1a0505", "#3b0a0a", "#f87171")

    analysis_html = _md_to_html(analysis_text)

    # Klassifikations-Badge (fundamental; RS nur als Overlay)
    cls_color = {"CHAMPION": "#86c429", "AUFSTREBENDER CHAMPION": "#86c429",
                 "SOLIDE": "#f59e0b", "NEUTRAL": "#94a3b8",
                 "SCHWACH": "#f87171"}.get(cls["tier"], "#94a3b8")
    cls_extra = " &middot; ".join(x for x in (cls["recognition"], cls["risk_flag"]) if x)
    cls_html = (
        f'<div class="sec" style="border-color:{cls_color}">'
        f'<div class="st">Klassifikation</div>'
        f'<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">'
        f'<span style="font-size:20px;font-weight:800;color:{cls_color}">{cls["emoji"]} {cls["tier"]}</span>'
        f'<span style="font-size:13px;color:var(--mu)">Champion-Score '
        f'<strong style="color:{cls_color}">{cls["champion_score"]}</strong>/100</span>'
        f'</div>'
        + (f'<div style="font-size:12px;color:var(--mu);margin-top:8px">{cls_extra}</div>' if cls_extra else '')
        + '</div>'
    )

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
@media(max-width:480px){{.sg{{grid-template-columns:1fr}}}}
.sz{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
@media(max-width:600px){{.sz{{grid-template-columns:1fr}}}}
.sr{{background:var(--bg3);border-radius:6px;padding:10px 12px;
  display:flex;align-items:center;justify-content:space-between;
  position:relative;cursor:pointer;user-select:none}}
.stars{{color:var(--al);font-size:14px;letter-spacing:1px;flex-shrink:0}}
.tip{{display:none;position:absolute;bottom:calc(100% + 6px);left:50%;
  transform:translateX(-50%);background:#0a1628;border:1px solid var(--bdr);
  border-radius:6px;padding:9px 12px;font-size:11px;color:#94a3b8;
  width:210px;z-index:20;line-height:1.6;pointer-events:none;
  box-shadow:0 4px 16px rgba(0,0,0,.4)}}
.sr:hover .tip,.sr.open .tip{{display:block}}
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

  <div class="sec">
    <div class="st">Gesamteinschätzung</div>
    <div class="sg">
      <div class="sr">
        <span style="font-size:12px;color:var(--mu)">Qualität</span><span class="stars">{_stars(q)}</span>
        <div class="tip">Burggraben, FCF-Stärke, Bilanzqualität, Margenstabilität über den Zyklus.<br><br>5 = Compounder-Qualität<br>1 = strukturell gefährdet</div>
      </div>
      <div class="sr">
        <span style="font-size:12px;color:var(--mu)">Wachstum</span><span class="stars">{_stars(g)}</span>
        <div class="tip">Umsatzwachstum und Nachhaltigkeit. Strukturell vs. zyklisch bewertet.<br><br>5 = &gt;30% nachhaltiges Wachstum<br>1 = schrumpfend oder rein zyklisch</div>
      </div>
      <div class="sr">
        <span style="font-size:12px;color:var(--mu)">Bewertung</span><span class="stars">{_stars(v)}</span>
        <div class="tip">Kurs vs. fairer Wert — normalisiertes FCF-KGV über den vollen Zyklus.<br><br>5 = deutlich unterbewertet<br>1 = massiv überstreckt</div>
      </div>
      <div class="sr">
        <span style="font-size:12px;color:var(--mu)">Katalysator</span><span class="stars">{_stars(p)}</span>
        <div class="tip">Stärke und Nachhaltigkeit des Auslösers: Earnings-Beat, Guidance, Produktzyklus, Makro-Tailwind.<br><br>5 = starker fundamentaler Treiber<br>1 = rein technisches Momentum</div>
      </div>
    </div>
  </div>

  <div class="g3">
    <div class="card"><div class="cl">Kurs</div><div class="cv" style="color:var(--tx)">{price_s}</div></div>
    <div class="card"><div class="cl">Forward PE</div><div class="cv">{fpe_s}</div></div>
    <div class="card"><div class="cl">Revenue (TTM)</div><div class="cv">{rev_s}</div></div>
    <div class="card"><div class="cl">Gross Margin</div><div class="cv">{gm_s}</div></div>
    <div class="card"><div class="cl">Dividende</div><div class="cv" style="color:var(--al)">{div_s}</div></div>
    {roe_card}
  </div>

  <div class="sec">
    <div class="st">Szenarien — 12–18 Monate</div>
    <div class="sz">
      {bull_card}
      {base_card}
      {bear_card}
    </div>
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

  {cls_html}

  <div class="dis">Keine Anlageberatung. KI-generierte Analyse auf Basis öffentlicher Daten zum Zeitpunkt des GWS-Breakout-Signals. Kurse können verzögert oder veraltet sein. Eigene Recherche empfohlen.</div>
</div>
<script>
var srs=document.querySelectorAll('.sr');
srs.forEach(function(el){{
  el.addEventListener('click',function(e){{
    var isOpen=el.classList.contains('open');
    srs.forEach(function(x){{x.classList.remove('open');}});
    if(!isOpen)el.classList.add('open');
    e.stopPropagation();
  }});
}});
document.addEventListener('click',function(){{
  srs.forEach(function(el){{el.classList.remove('open');}});
}});
</script>
</body>
</html>'''


# ── Markdown-Generierung ─────────────────────────────────────────────────────

def build_markdown(ticker: str, fund: dict, analysis_text: str, rs_score: float, gws: dict) -> str:
    today      = datetime.now().strftime("%d.%m.%Y")
    short_name = fund.get("shortName", ticker)
    sector     = fund.get("sector",    "N/A")
    sig_type   = gws.get("signal_type", "Breakout")

    rt = _extract_ratings(analysis_text)
    q, g, v, p = rt["Qualität"], rt["Wachstum"], rt["Bewertung"], rt["Katalysator"]
    score, verd = compute_verdict(rt)
    cls = classify_leadership(rt, rs_score)

    gws_weekly = "✓ Aktiv" if gws.get("weekly") else "✗ Inaktiv"
    gws_daily  = "✓ Aktiv" if gws.get("daily")  else "✗ Inaktiv"
    gws_h4     = "✓ Aktiv" if gws.get("h4")     else "✗ Inaktiv"

    # ROE-Zeile nur bei echtem Zahlenwert (kein N/A / UNGÜLTIG-Artefakt)
    roe = fund.get("returnOnEquity")
    roe_row = f"| ROE | {_pct(roe)} |\n" if isinstance(roe, (int, float)) else ""

    cls_extra = " · ".join(x for x in (cls["recognition"], cls["risk_flag"]) if x)
    cls_line = f"**Klassifikation: {cls['emoji']} {cls['tier']}** · Champion-Score {cls['champion_score']}/100"
    if cls_extra:
        cls_line += f" · {cls_extra}"

    return f"""# {ticker} — KI-Aktienbewertung

**{short_name}** · {sector} · {today} · Signal: {sig_type}

| Kennzahl | Wert |
|---|---|
| Kurs | {_fmt(fund.get('currentPrice'))} |
| Market Cap | {_bn(fund.get('marketCap'))} |
| Forward PE | {_fmt(fund.get('forwardPE'))} |
| Revenue (TTM) | {_bn(fund.get('totalRevenue'))} |
| Gross Margin | {_pct(fund.get('grossMargins'))} |
{roe_row}| RS-Score | {rs_score:.1f} |

**GWS-Ampel:** Weekly {gws_weekly} · Daily {gws_daily} · 4H {gws_h4}

---

{analysis_text}

---

| Rating | Score |
|---|---|
| Qualität | {q}/5 |
| Wachstum | {g}/5 |
| Bewertung | {v}/5 |
| Katalysator | {p}/5 |

**Verdict: {verd} ({score}/100)**

{cls_line}

*Keine Anlageberatung. KI-generierte Analyse auf Basis öffentlicher Daten.*
"""


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


# ── Datei-Schreiber (wird von Claude Code nach Analyse-Generierung aufgerufen) ─

def write_rating(ticker: str, analysis_text: str, rs_score: float, windows: dict, gws: dict):
    """
    Schreibt HTML + Markdown und aktualisiert den Index.
    Wird von Claude Code aufgerufen, nachdem die Analyse generiert wurde.
    Kein LLM-Call — analysis_text kommt direkt von Claude Code.
    """
    fund = load_fundamentals(ticker)

    rt    = _extract_ratings(analysis_text)
    score, verd = compute_verdict(rt)
    cls = classify_leadership(rt, rs_score)

    html = build_html(ticker, fund, analysis_text, rs_score, gws)

    RATINGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RATINGS_DIR / f"{_safe_name(ticker)}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Gespeichert: {out_path}")

    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
    md_path = ANALYSES_DIR / f"{_safe_name(ticker)}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_markdown(ticker, fund, analysis_text, rs_score, gws))
    print(f"  Gespeichert: {md_path}")

    idx = load_index()
    idx["ratings"] = [r for r in idx["ratings"] if r.get("ticker", "").upper() != ticker.upper()]
    idx["ratings"].append({
        "ticker":         ticker.upper(),
        "verdict":        verd,
        "score":          score,
        "classification": cls["tier"],
        "champion_score": cls["champion_score"],
        "rs_percentile":  cls["rs_percentile"],
        "hidden":         (cls["rs_percentile"] is not None and cls["rs_percentile"] < 40),
        "risk_flag":      bool(cls["risk_flag"]),
        "created_at":     datetime.now().isoformat(),
    })
    save_index(idx)
    print(f"  Index aktualisiert: {len(idx['ratings'])} Rating(s)")


def generate_for_ticker(ticker: str, rs_score: float, windows: dict, gws: dict) -> bool:
    """Stub für check_alerts.py / check_4h_reentry.py — Ratings werden manuell via Claude Code generiert."""
    print(f"  generate_rating: Ratings werden manuell via Claude Code generiert — übersprungen")
    return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Verwendung: python generate_rating.py TICKER [TICKER2 ...]")
        print()
        print("Gibt den formatierten Analyse-Kontext für Claude Code aus.")
        print("Claude Code generiert daraus die Analyse und ruft write_rating() auf.")
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

    tickers = [t.upper() for t in sys.argv[1:]]

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
        fund    = load_fundamentals(ticker)
        tech    = compute_technicals(entry, fund)
        context = build_context(ticker, fund, rs_score, windows, gws, tech)
        print("=" * 60)
        print(context)
        print("=" * 60)
        print()
