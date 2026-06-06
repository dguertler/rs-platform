"""
Parser für die KI-Aktienanalysen (`analyses/TICKER.md`).

Zerlegt eine Analyse in strukturierte Felder, aus denen der Instagram-Generator
die Slides + Caption baut. Bewusst tolerant: fehlt ein Wert (z. B. eine
Kursziel-Spanne), wird das Feld leer gelassen statt zu raten — die Render-Slides
degradieren dann sauber.

WICHTIG: Der aktuelle Kurs wird absichtlich NICHT extrahiert/angezeigt
(Vorgabe für die Instagram-Analyse-Posts).
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYSES_DIR = os.path.join(ROOT, "analyses")

# Abschnitte, die für Instagram bewusst NICHT verwendet werden:
#   6 Fundamentale Qualität, 7 Bewertung, 8 Marktpsychologie,
#   9 Technik/Momentum (inkl. GWS-Ampel / Breakout — explizit raus).


def _de_num(s):
    """'3.500' -> 3500.0 ; '403,9' -> 403.9 ; '1.694,98' -> 1694.98."""
    if s is None:
        return None
    s = s.strip().replace(" ", "").replace(" ", "")
    if not s:
        return None
    if "," in s:                       # Komma = Dezimaltrenner, Punkt = Tausender
        s = s.replace(".", "").replace(",", ".")
    else:                              # nur Punkte -> Tausendertrenner
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _cur_symbol(raw):
    if not raw:
        return ""
    if "€" in raw or "EUR" in raw:
        return "€"
    if "$" in raw or "USD" in raw:
        return "$"
    return ""


# Kursziel-Spanne: 'Kursziel 280–380 USD', 'Kursziel: 470-500 USD',
# 'Kursziel 700+ USD', 'Kursziel $1.000–2.000', 'Kursziel 403,9 USD'
_RANGE_RE = re.compile(
    r"Kursziel[:\s]*\$?\s*([\d.,]+)\s*(?:[–\-]\s*\$?\s*([\d.,]+))?\s*(\+)?\s*(USD|EUR|\$|€)?",
    re.IGNORECASE)

_PROB_RE = re.compile(
    r"(?:Eintritts)?[Ww]ahrscheinlichkeit[:\s]*?(\d{1,3})\s*%")


def _parse_range(text):
    """Findet die letzte Kursziel-Spanne in einem Abschnitt."""
    m = None
    for m in _RANGE_RE.finditer(text):
        pass
    if not m:
        return None
    low = _de_num(m.group(1))
    high = _de_num(m.group(2)) if m.group(2) else None
    plus = bool(m.group(3))
    cur = _cur_symbol(m.group(4) or text[max(0, m.start()): m.end() + 6])
    if high is None and not plus:
        high = low                     # Einzelwert -> Punktziel
    return {"low": low, "high": high, "plus": plus, "cur": cur}


def _parse_prob(text):
    probs = _PROB_RE.findall(text)
    return int(probs[-1]) if probs else None


# Spanne im Klammer-Ausdruck von Abschnitt 10: '($3.000–5.000)' / '(1.000–2.000 USD)'
_PAREN_RANGE_RE = re.compile(
    r"\(\s*\$?\s*([\d.,]+)\s*[–\-]\s*\$?\s*([\d.,]+)\s*(USD|EUR|\$|€)?")


def _parse_longterm(sec10):
    out = {}
    for key, label in (("bull", "Bull"), ("base", "Base"), ("bear", "Bear")):
        m = re.search(r"\*\*\s*" + label + r"[^*]*?\(([^)]*)\)", sec10)
        rng = None
        if m:
            inner = "(" + m.group(1) + ")"
            pm = _PAREN_RANGE_RE.search(inner)
            if pm:
                rng = {"low": _de_num(pm.group(1)), "high": _de_num(pm.group(2)),
                       "cur": _cur_symbol(pm.group(3) or inner)}
        out[key] = rng
    return out


# Abkürzungen, nach denen ein Punkt KEIN Satzende ist
_ABBREV = {"nr", "z", "b", "ca", "mrd", "mio", "bzw", "u", "a", "ggf", "inkl",
           "max", "min", "vs", "co", "inc", "corp", "etc", "sog", "ggü", "d",
           "h", "i", "e", "mind", "evtl", "st", "dr", "usw", "bspw", "ehem",
           "tsd", "abb"}


def _first_sentence(text, max_len=240):
    """Erster Satz — Abkürzungen (Nr., z.B., Mrd. …) brechen NICHT um,
    Zahlen mit Punkt (4.800) ebenfalls nicht (Regex verlangt Space/Ende)."""
    text = " ".join(text.split())
    s = text
    for m in re.finditer(r"[.!?](\s|$)", text):
        i = m.start()
        prev = re.search(r"(\S+)$", text[:i])
        word = prev.group(1).lower().strip(".,;:()-—«»\"'") if prev else ""
        if word in _ABBREV:
            continue
        s = text[:i + 1].strip()
        break
    if len(s) > max_len:
        s = s[:max_len].rsplit(" ", 1)[0] + "…"
    return s.strip()


def _bullets(text, limit=6):
    out = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("- "):
            out.append(ln[2:].strip())
    return out[:limit]


def _peers(fazit):
    """Fett markierte Peers aus dem Profi-Fazit, z. B. **Nvidia (NVDA)**."""
    peers = []
    for m in re.finditer(r"\*\*([^*]+?)\*\*", fazit):
        name = m.group(1).strip()
        # Rating-/Struktur-Zeilen ausschließen
        if name.endswith(":"):
            continue
        if any(k in name for k in ("Qualität", "Wachstum", "Bewertung",
                                   "Katalysator", "Summe", "Verdict", "Rating")):
            continue
        peers.append(name)
    return peers[:3]


def parse_analysis(path_or_ticker):
    """Liest eine Analyse und gibt ein strukturiertes Dict zurück."""
    path = path_or_ticker
    if not os.path.isfile(path):
        cand = os.path.join(ANALYSES_DIR, path_or_ticker.lower() + ".md")
        if os.path.isfile(cand):
            path = cand
        else:
            raise FileNotFoundError(f"Analyse nicht gefunden: {path_or_ticker}")
    with open(path, encoding="utf-8") as f:
        md = f.read()

    a = {"path": path}

    # Titelzeile: '# AMD — KI-Aktienbewertung'
    m = re.search(r"^#\s+(\S+)\s+—", md, re.MULTILINE)
    a["ticker"] = (m.group(1) if m else
                   os.path.splitext(os.path.basename(path))[0].upper())

    # Meta: '**Name** · Sector · Datum · Signal: X'
    m = re.search(r"^\*\*(.+?)\*\*\s*·\s*(.+?)\s*·\s*([\d.]+)", md, re.MULTILINE)
    if m:
        a["name"] = m.group(1).strip()
        a["sector"] = m.group(2).strip()
        a["date"] = m.group(3).strip()
    else:
        a["name"] = a["ticker"]
        a["sector"] = ""
        a["date"] = ""

    # Verdict + Score
    m = re.search(r"\*\*Verdict:\s*([A-ZÄÖÜ]+)\s*\((\d+)\s*/\s*100\)", md)
    a["verdict"] = m.group(1) if m else "—"
    a["score"] = int(m.group(2)) if m else None

    # Rating-Tabelle
    ratings = {}
    for key in ("Qualität", "Wachstum", "Bewertung", "Katalysator"):
        rm = re.search(r"\|\s*" + key + r"\s*\|\s*(\d)\s*/\s*5", md)
        if not rm:
            rm = re.search(key + r"[:\s]+(\d)\s*/\s*5", md)
        ratings[key] = int(rm.group(1)) if rm else None
    a["ratings"] = ratings

    # Abschnitte 1..11 splitten
    sections = {}
    parts = re.split(r"^##\s+(\d+)\.\s*[^\n]*$", md, flags=re.MULTILINE)
    # parts: [vortext, num, body, num, body, ...]
    for i in range(1, len(parts) - 1, 2):
        try:
            num = int(parts[i])
        except ValueError:
            continue
        sections[num] = parts[i + 1].strip()
    a["sections"] = sections

    # Hook = erster Satz aus Investment-Case
    a["hook"] = _first_sentence(sections.get(1, ""), max_len=200)

    # Was macht die AG: Highlights aus 1 (Kernsatz) + 2 (Bullets)
    a["business_bullets"] = _bullets(sections.get(2, ""), limit=6)

    # Chancen/Risiken als Bullets (v. a. Alt-Schema: 3=BULL, 4=BEAR als Listen).
    # Im neuen Schema sind 3/4 Fließtext -> _bullets liefert [] (Slide entfällt).
    a["pro_bullets"] = _bullets(sections.get(3, ""), limit=5)
    a["con_bullets"] = _bullets(sections.get(4, ""), limit=5)

    # Szenarien 12–18 Mon. aus 3/4/5
    scen = {}
    for key, sec in (("bull", 3), ("base", 4), ("bear", 5)):
        body = sections.get(sec, "")
        scen[key] = {
            "prob": _parse_prob(body),
            "range": _parse_range(body),
            "summary": _first_sentence(body, max_len=200),
        }
    a["scenarios"] = scen

    # Langfrist-Szenarien 3–5 J. aus 10
    a["longterm"] = _parse_longterm(sections.get(10, ""))

    # Profi-Fazit
    fazit = sections.get(11, "")
    a["fazit"] = fazit
    a["fazit_core"] = _first_sentence(fazit, max_len=260)
    a["peers"] = _peers(fazit)

    return a


def fmt_range(rng, decimals=0):
    """'600–750 $' ; '700+ $' ; '' wenn keine Daten."""
    if not rng or rng.get("low") is None:
        return ""
    cur = (" " + rng["cur"]) if rng.get("cur") else ""

    def n(x):
        if x is None:
            return ""
        if decimals == 0 and abs(x - round(x)) < 1e-9:
            return f"{int(round(x)):,}".replace(",", ".")
        return f"{x:,.{decimals}f}".replace(",", "·").replace(".", ",").replace("·", ".")

    if rng.get("plus") and not rng.get("high"):
        return f"{n(rng['low'])}+{cur}"
    if rng.get("high") and rng["high"] != rng["low"]:
        return f"{n(rng['low'])}–{n(rng['high'])}{cur}"
    return f"{n(rng['low'])}{cur}"


if __name__ == "__main__":          # Schnelltest: python3 -m instagram.analysis AMD
    import sys
    import json
    t = sys.argv[1] if len(sys.argv) > 1 else "AMD"
    a = parse_analysis(t)
    slim = {k: v for k, v in a.items() if k != "sections"}
    print(json.dumps(slim, ensure_ascii=False, indent=2))
