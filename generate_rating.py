"""
generate_rating.py — KI-Aktienbewertung für Breakout-Kandidaten
===============================================================
Die Analysen werden manuell von Claude Code generiert (kein API-Call):
Claude liest analyses/PROMPT.md (einzige Prompt-Quelle), schreibt die
Analyse und ruft write_rating() auf. Dieses Modul liefert dafür:

1. Fundamentaldaten-Kontext (build_context, CLI-Aufruf)
2. HTML-Seite → data/ratings/{ticker}.html
3. Markdown-Analyse → analyses/{ticker}.md (inkl. automatisch
   berechnetem Verdict/Score aus den vier X/5-Ratings)
4. data/ratings/index.json aktualisieren

check_alerts.py / check_4h_reentry.py rufen nur den Stub
generate_for_ticker() auf (Ratings entstehen nicht automatisch).
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import yfinance as yf

RATINGS_DIR  = Path("data/ratings")
ANALYSES_DIR = Path("analyses")

# ── System-Prompt ────────────────────────────────────────────────────────────
# Der vollständige Analyse-Prompt (Struktur, Stil, Regeln, Verdict/Score) lebt
# AUSSCHLIESSLICH in analyses/PROMPT.md — dort pflegen, hier nicht duplizieren.

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
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        raw = {
            "shortName":             info.get("shortName", ticker),
            "sector":                info.get("sector", "N/A"),
            "industry":              info.get("industry", "N/A"),
            "marketCap":             info.get("marketCap"),
            "currentPrice":          info.get("currentPrice") or info.get("regularMarketPrice"),
            "trailingPE":            info.get("trailingPE"),
            "forwardPE":             info.get("forwardPE"),
            "grossMargins":          info.get("grossMargins"),
            "operatingMargins":      info.get("operatingMargins"),
            "profitMargins":         info.get("profitMargins"),
            "freeCashflow":          info.get("freeCashflow"),
            "totalRevenue":          info.get("totalRevenue"),
            "revenueGrowth":         info.get("revenueGrowth"),
            "dividendYield":         info.get("dividendYield"),
            "debtToEquity":          info.get("debtToEquity"),
            "returnOnEquity":        info.get("returnOnEquity"),
            "priceToBook":           info.get("priceToBook"),
            "fiftyTwoWeekHigh":      info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow":       info.get("fiftyTwoWeekLow"),
            "beta":                  info.get("beta"),
            "recommendationKey":     info.get("recommendationKey"),
            "targetMeanPrice":       info.get("targetMeanPrice"),
            "numberOfAnalystOpinions": info.get("numberOfAnalystOpinions"),
            "sharesOutstanding":     info.get("sharesOutstanding"),
            "floatShares":           info.get("floatShares"),
            "shortRatio":            info.get("shortRatio"),
            "shortPercentOfFloat":   info.get("shortPercentOfFloat"),
            "_snapshot_date":        datetime.now().strftime("%Y-%m-%d"),
        }
        validated = validate_fundamentals(raw)
        # Fetch SBC from cashflow statement (B4)
        try:
            cf = stock.cashflow
            if cf is not None and not cf.empty:
                sbc_row = None
                for label in ("Stock Based Compensation", "Share Based Compensation"):
                    if label in cf.index:
                        sbc_row = cf.loc[label]
                        break
                if sbc_row is not None:
                    latest_sbc = sbc_row.iloc[0]
                    validated["stockBasedCompensation"] = latest_sbc if latest_sbc else None
        except Exception:
            pass
        # Fetch earnings dates (B2)
        try:
            cal = stock.calendar
            if cal is not None and not cal.empty:
                if "Earnings Date" in cal.index:
                    ed = cal.loc["Earnings Date"]
                    validated["_next_earnings"] = str(ed.iloc[0])[:10] if hasattr(ed, "iloc") else str(ed)[:10]
        except Exception:
            pass
        return validated
    except Exception as e:
        print(f"  Fundamentaldaten für {ticker} fehlgeschlagen: {e}")
        return {}


def _live_price(ticker: str):
    """Fetch current price via yfinance fast_info."""
    try:
        fi = yf.Ticker(ticker).fast_info
        return fi.get("last_price") or fi.get("regularMarketPrice")
    except Exception:
        return None


def load_fundamentals(ticker: str) -> dict:
    """Lädt Fundamentaldaten aus data/fundamentals.json; Fallback auf live yfinance.
    B1: Snapshot-Datum mitliefern.
    B3: Live-Kurs gegen Snapshot-Kurs prüfen; bei >5% Abweichung Snapshot refreshen
        und price_gap_detected setzen.
    """
    p = Path("data/fundamentals.json")
    fund = None
    snapshot_date = None
    if p.exists():
        with open(p, encoding="utf-8") as f:
            cached = json.load(f)
        fund = cached.get("tickers", {}).get(ticker.upper())
        if fund:
            snapshot_date = cached.get("updated_at", "unbekannt")[:10]
            print(f"  Fundamentaldaten aus Cache ({snapshot_date})")
            fund = dict(fund)
            fund.setdefault("_snapshot_date", snapshot_date)

    if fund is None:
        print(f"  {ticker} nicht in fundamentals.json — live fetch via yfinance...")
        return fetch_fundamentals(ticker)

    # B3: live price check
    snapshot_price = fund.get("currentPrice")
    if isinstance(snapshot_price, (int, float)) and snapshot_price > 0:
        live_price = _live_price(ticker)
        if live_price and isinstance(live_price, (int, float)):
            gap_pct = abs(live_price - snapshot_price) / snapshot_price
            if gap_pct > 0.05:
                print(f"  Preis-Gap {gap_pct*100:.1f}% erkannt (Snapshot ${snapshot_price:.2f} → Live ${live_price:.2f}) — refreshe Fundamentaldaten...")
                fresh = fetch_fundamentals(ticker)
                fresh["_price_gap_detected"] = True
                fresh["_price_gap_pct"] = round(gap_pct * 100, 1)
                fresh["_snapshot_price"] = snapshot_price
                fresh["_snapshot_date"] = snapshot_date or fresh.get("_snapshot_date", "unbekannt")
                return fresh
            else:
                fund["_live_price"] = round(live_price, 2)

    return fund


def _pct(v):
    return f"{v * 100:.1f}%" if isinstance(v, (int, float)) else "N/A" if v is None else str(v)

def _bn(v):
    return f"${v / 1e9:.2f} Mrd." if isinstance(v, (int, float)) else "N/A" if v is None else str(v)

def _fmt(v):
    return str(round(v, 2)) if isinstance(v, (int, float)) else "N/A" if v is None else str(v)


def build_context(ticker: str, fund: dict, rs_score: float, windows: dict, gws: dict) -> str:
    snapshot_date = fund.get("_snapshot_date", "unbekannt")
    live_price    = fund.get("_live_price")
    gap_detected  = fund.get("_price_gap_detected", False)
    gap_pct       = fund.get("_price_gap_pct")
    snap_price    = fund.get("_snapshot_price")
    next_earnings = fund.get("_next_earnings", "N/A")
    shares_out    = fund.get("sharesOutstanding")
    sbc           = fund.get("stockBasedCompensation")
    short_pct     = fund.get("shortPercentOfFloat")
    short_ratio   = fund.get("shortRatio")
    num_analysts  = fund.get("numberOfAnalystOpinions")

    gap_warning = ""
    if gap_detected:
        gap_warning = (
            f"\n⚠ PREIS-GAP ERKANNT: Snapshot-Kurs ${snap_price} vs. aktuellem Kurs "
            f"${_fmt(fund.get('currentPrice'))} — Abweichung {gap_pct}%. "
            f"price_gap_detected=True — Datenlage-Hinweis im Investment-Case PFLICHT."
        )

    live_price_line = ""
    if live_price and not gap_detected:
        live_price_line = f"\nAktueller Live-Kurs (Prüfung): ${live_price}"

    sbc_line     = f"- Stock-based Compensation (letztes FJ): {_bn(sbc)}" if sbc else "- SBC: N/A"
    shares_line  = f"- Shares Outstanding: {shares_out/1e9:.2f} Mrd." if isinstance(shares_out, (int, float)) else "- Shares Outstanding: N/A"
    short_line   = (f"- Short % of Float: {short_pct*100:.1f}% | Short Ratio: {_fmt(short_ratio)}"
                    if isinstance(short_pct, (int, float)) else "- Short Float: N/A")
    analysts_line = f"- Anzahl Analysten (Konsens): {num_analysts}" if num_analysts else "- Anzahl Analysten: N/A"

    return f"""FUNDAMENTALDATEN FÜR DIE ANALYSE:
Ticker: {ticker}
Unternehmen: {fund.get('shortName', ticker)}
Sektor: {fund.get('sector', 'N/A')} | Industrie: {fund.get('industry', 'N/A')}
Fundamental-Snapshot-Datum: {snapshot_date}{gap_warning}{live_price_line}
Kurs (Snapshot): ${_fmt(fund.get('currentPrice'))} | Market Cap: {_bn(fund.get('marketCap'))}
52W-Hoch: ${_fmt(fund.get('fiftyTwoWeekHigh'))} | 52W-Tief: ${_fmt(fund.get('fiftyTwoWeekLow'))}
Beta: {_fmt(fund.get('beta'))}

Bewertung:
- Trailing PE: {_fmt(fund.get('trailingPE'))} | Forward PE: {_fmt(fund.get('forwardPE'))}
- Price/Book: {_fmt(fund.get('priceToBook'))}
- Analysten-Konsens: {fund.get('recommendationKey', 'N/A')} | Kursziel: ${_fmt(fund.get('targetMeanPrice'))}
{analysts_line}

Finanzkennzahlen:
- Revenue (TTM): {_bn(fund.get('totalRevenue'))} | Wachstum YoY: {_pct(fund.get('revenueGrowth'))}
- Gross Margin: {_pct(fund.get('grossMargins'))} | Operating Margin: {_pct(fund.get('operatingMargins'))}
- Net Margin: {_pct(fund.get('profitMargins'))} | Free Cashflow: {_bn(fund.get('freeCashflow'))}
- Dividende: {_pct(fund.get('dividendYield'))} | Debt/Equity: {_fmt(fund.get('debtToEquity'))}
- Return on Equity: {_pct(fund.get('returnOnEquity'))}
{sbc_line}
{shares_line}

Positionierung & Leerverkäufer:
{short_line}

Earnings-Kalender:
- Nächster Earnings-Termin: {next_earnings}

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
    for cat in ["Qualität", "Wachstum", "Bewertung", "Katalysator"]:
        m = re.search(rf'{re.escape(cat)}:\s*(\d)/5', text)
        out[cat] = int(m.group(1)) if m else 3
    return out


_VETO_DECISIONS = {"PASS", "REDUCE", "VETO"}
_VETO_CATEGORIES = {"Bewertung", "Verwässerung", "Kundenkonzentration", "Bilanz",
                     "Katalysator fehlt", "Sonstiges"}


def _extract_funnel_veto(text: str) -> dict | None:
    """Parst die Pflichtzeile '**Funnel-Entscheidung:** PASS|REDUCE|VETO —
    Kategorie: <Kategorie> — <Begründung>' aus analyses/PROMPT.md.
    Reiner Qualitäts-Layer (STRATEGIEPLAN.md Abschnitt 6) — None wenn die
    Analyse (noch) keine solche Zeile enthält, z.B. bei älteren Analysen
    aus der Zeit vor diesem Format."""
    m = re.search(
        r'\*\*Funnel-Entscheidung:\*\*\s*(PASS|REDUCE|VETO)\s*—\s*Kategorie:\s*([^—\n]+?)\s*—\s*(.+)',
        text)
    if not m:
        return None
    decision = m.group(1)
    category = m.group(2).strip()
    reason = m.group(3).strip()
    if decision not in _VETO_DECISIONS:
        return None
    return {
        "decision": decision,
        "category": category if category in _VETO_CATEGORIES else "Sonstiges",
        "reason": reason,
    }


def _parse_price_range_midpoint(price_str: str) -> float | None:
    """Parst einen Kursstring ('1.400–2.100 USD', '$500–$900') und gibt den Mittelpunkt zurück."""
    s = price_str.replace(",", "").replace("USD", "").replace("EUR", "").replace("€", "").replace("$", "").strip()
    m = re.search(r'([\d.]+)\s*[–—-]+\s*([\d.]+)', s)
    if m:
        try:
            lo, hi = float(m.group(1)), float(m.group(2))
            return (lo + hi) / 2
        except ValueError:
            return None
    m = re.search(r'([\d.]+)', s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _compute_ev_score(analysis_text: str, current_price) -> tuple:
    """
    Berechnet EV-Score (0–20 Punkte) aus Bull/Base/Bear-Kurszielen.
    EV = Mittelwert der Szenario-Mittelpunkte (mind. 2 Szenarien nötig).
    Gibt (ev_punkte, upside_pct_oder_None) zurück.
    """
    if not isinstance(current_price, (int, float)) or current_price <= 0:
        return 10, None

    sc = _extract_scenarios(analysis_text)
    mids = []
    for key in ("bull", "base", "bear"):
        price_str = sc[key].get("price", "N/A")
        if price_str and price_str != "N/A":
            mid = _parse_price_range_midpoint(price_str)
            if mid:
                mids.append(mid)

    if len(mids) < 2:
        return 10, None

    ev = sum(mids) / len(mids)
    upside = (ev / current_price - 1) * 100

    if upside > 20:
        pts = 20
    elif upside > 10:
        pts = 15
    elif upside > 0:
        pts = 10
    elif upside > -10:
        pts = 5
    else:
        pts = 0

    return pts, round(upside, 1)


def _calc_score_and_verdict(rt: dict, ev_pts: int) -> tuple:
    """Score = 80% Basis-Ratings + 20% EV-Punkte. Thresholds: BUY≥70, HOLD≥55, WATCH≥40, AVOID<40."""
    q, g, v, p = rt["Qualität"], rt["Wachstum"], rt["Bewertung"], rt["Katalysator"]
    score = min(100, round((q + g + v + p) / 20 * 80) + ev_pts)
    if score >= 70:
        verd = "BUY"
    elif score >= 55:
        verd = "HOLD"
    elif score >= 40:
        verd = "WATCH"
    else:
        verd = "AVOID"
    return score, verd


def _extract_scenarios(text: str) -> dict:
    result = {"bull": {"price": "N/A", "prob": "N/A"},
              "base": {"price": "N/A", "prob": "N/A"},
              "bear": {"price": "N/A", "prob": "N/A"}}

    def _price(s: str) -> str:
        def _from(txt: str) -> str:
            # "€X–€Y" or "$X–$Y" — currency symbol precedes each number (European format)
            m = re.search(r'[€$]\s*(\d[\d.,]*)\s*[–—-]+\s*[€$]\s*(\d[\d.,]*)', txt)
            if m:
                return f"{m.group(1)}–{m.group(2)}"
            # Range + explicit currency after: "2.450–2.800 USD"
            m = re.search(r'(\d[\d.]*\s*[–—-]+\s*[\d.,]+)\s*(USD|EUR|€)', txt)
            if m:
                return f"{m.group(1).strip()} {m.group(2)}"
            # "$X–$Y" or "$X-Y" dollar range
            m = re.search(r'\$\s*(\d[\d.,]*)\s*[–—-]+\s*\$?\s*(\d[\d.,]*)', txt)
            if m:
                return f"${m.group(1)}–${m.group(2)}"
            # "$X+" or "$X" single dollar value
            m = re.search(r'\$\s*(\d[\d.,]*\+?)', txt)
            if m:
                return f"${m.group(1)}"
            # "€X+" or "€X" single euro value
            m = re.search(r'€\s*(\d[\d.,]*\+?)', txt)
            if m:
                return f"€{m.group(1)}"
            # "45 USD" or "90+ USD" — single value with explicit currency
            m = re.search(r'(\d[\d.,]*\+?)\s*(USD|EUR|€)', txt)
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
        # Markdown-Betonung (** __) entfernen — sonst bricht z.B. "Eintrittswahrscheinlichkeit: **20%**"
        s = s.replace('*', '').replace('_', '')
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
    sc = _extract_scenarios(analysis_text)
    price  = fund.get("currentPrice")
    ev_pts, upside_pct = _compute_ev_score(analysis_text, price)
    score, verd = _calc_score_and_verdict(rt, ev_pts)
    q, g, v, p = rt["Qualität"], rt["Wachstum"], rt["Bewertung"], rt["Katalysator"]
    asymm_edge = upside_pct is not None and upside_pct > 20

    if verd == "BUY":
        vc, vbg, vbr = "#86c429", "#3B6D11", "#639922"
    elif verd == "HOLD":
        vc, vbg, vbr = "#f59e0b", "#1a1200", "#b45309"
    elif verd == "WATCH":
        vc, vbg, vbr = "#f87171", "#1a0505", "#ef4444"
    else:  # AVOID
        vc, vbg, vbr = "#ef4444", "#1a0000", "#7f1d1d"

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
    upside_s = (f"{upside_pct:+.1f}%" if upside_pct is not None else "N/A")
    upside_c = ("#86c429" if (upside_pct or 0) > 0 else "#f87171") if upside_pct is not None else "#64748b"

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
      <div style="display:flex;align-items:center;gap:6px">
        <div class="vb">{verd}</div>
        {f'<span style="color:#ef4444;font-size:18px;font-weight:900;line-height:1" title="Asymmetrischer Edge: EV-Upside >{upside_pct:.0f}%">!</span>' if asymm_edge else ''}
      </div>
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
    <div class="card"><div class="cl">ROE</div><div class="cv">{roe_s}</div></div>
    <div class="card"><div class="cl">EV-Upside</div><div class="cv" style="color:{upside_c}">{upside_s}</div></div>
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
    ev_pts, upside_pct = _compute_ev_score(analysis_text, fund.get("currentPrice"))
    score, verd = _calc_score_and_verdict(rt, ev_pts)
    q, g, v, p = rt["Qualität"], rt["Wachstum"], rt["Bewertung"], rt["Katalysator"]
    asymm_edge = upside_pct is not None and upside_pct > 20
    edge_line  = f"\n**⚡ ASYMMETRISCHER EDGE** — EV-Upside {upside_pct:+.1f}% (>20%)\n" if asymm_edge else ""

    gws_weekly = "✓ Aktiv" if gws.get("weekly") else "✗ Inaktiv"
    gws_daily  = "✓ Aktiv" if gws.get("daily")  else "✗ Inaktiv"
    gws_h4     = "✓ Aktiv" if gws.get("h4")     else "✗ Inaktiv"

    return f"""# {ticker} — KI-Aktienbewertung

**{short_name}** · {sector} · {today} · Signal: {sig_type}

| Kennzahl | Wert |
|---|---|
| Kurs | {_fmt(fund.get('currentPrice'))} |
| Market Cap | {_bn(fund.get('marketCap'))} |
| Forward PE | {_fmt(fund.get('forwardPE'))} |
| Revenue (TTM) | {_bn(fund.get('totalRevenue'))} |
| Gross Margin | {_pct(fund.get('grossMargins'))} |
| ROE | {_pct(fund.get('returnOnEquity'))} |
| RS-Score | {rs_score:.1f} |

**GWS-Ampel:** Weekly {gws_weekly} · Daily {gws_daily} · 4H {gws_h4}
{edge_line}
---

{analysis_text}

---

| Rating | Score |
|---|---|
| Qualität | {q}/5 |
| Wachstum | {g}/5 |
| Bewertung | {v}/5 |
| Katalysator | {p}/5 |
| EV-Upside | {f"{upside_pct:+.1f}%" if upside_pct is not None else "N/A"} |

**Verdict: {verd} ({score}/100)**

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
    ev_pts, upside_pct = _compute_ev_score(analysis_text, fund.get("currentPrice"))
    score, verd = _calc_score_and_verdict(rt, ev_pts)
    asymm_edge = upside_pct is not None and upside_pct > 20
    funnel_veto = _extract_funnel_veto(analysis_text)

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
        "ticker":          ticker.upper(),
        "verdict":         verd,
        "score":           score,
        "asymmetric_edge": asymm_edge,
        "funnel_veto":     funnel_veto,
        "created_at":      datetime.now().isoformat(),
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
        context = build_context(ticker, fund, rs_score, windows, gws)
        print("=" * 60)
        print(context)
        print("=" * 60)
        print()
