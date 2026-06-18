"""
Marken- und Design-System für die AI-Alpha-Selection-Instagram-Grafiken.
Zentrale Stelle für Farben, Fonts, Canvas-Größen und Layout-Konstanten,
damit Carousel (4:5) und Reel (9:16) konsistent aussehen.
"""
import os

from matplotlib import font_manager

# ── Eigenes Logo (optional) ────────────────────────────────────────────────────
# Lege dein Logo unter instagram/assets/logo.png ab (PNG, transparent).
# WICHTIG: Das wikifolio-Logo NICHT verwenden – nur mit vorheriger schriftlicher
# Freigabe durch wikifolio erlaubt. Dein eigenes Marken-Logo ist frei nutzbar.
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_PATH = os.path.join(ASSETS, "logo.png")   # Ziel für make_logo.py


def logo_file():
    """Findet dein Logo (logo.png/.jpg/.webp, Groß-/Kleinschreibung egal).
    PNG/WEBP bevorzugt. None, wenn keins da ist."""
    if not os.path.isdir(ASSETS):
        return None
    found = {}
    for f in os.listdir(ASSETS):
        low = f.lower()
        if low in ("logo.png", "logo.webp", "logo.jpg", "logo.jpeg"):
            found[low] = os.path.join(ASSETS, f)
    for pref in ("logo.png", "logo.webp", "logo.jpg", "logo.jpeg"):
        if pref in found:
            return found[pref]
    return None


# ── Firmenlogos (für Analyse-Cover) ────────────────────────────────────────────
# Lege Logos der Aktiengesellschaften unter instagram/assets/logos/<TICKER>.png
# ab (transparent bevorzugt). Ticker wie im Dateinamen der Analyse, Punkt durch
# Unterstrich ersetzt: AMD -> AMD.png, SIE.DE -> SIE_DE.png oder SIE.DE.png.
# Fehlt das Logo, fällt der Cover sauber auf eine Wortmarke zurück.
LOGOS_DIR = os.path.join(ASSETS, "logos")


def company_logo_file(ticker):
    """Sucht das Firmenlogo für einen Ticker (case-insensitiv, . oder _).
    Reihenfolge: .png > .webp > .jpg/.jpeg. None, wenn keins da ist."""
    if not os.path.isdir(LOGOS_DIR):
        return None
    keys = {ticker.lower(), ticker.lower().replace(".", "_"),
            ticker.lower().replace(".", "")}
    found = {}
    for f in os.listdir(LOGOS_DIR):
        stem, ext = os.path.splitext(f)
        if stem.lower() in keys and ext.lower() in (".png", ".webp", ".jpg", ".jpeg"):
            found[ext.lower()] = os.path.join(LOGOS_DIR, f)
    for pref in (".png", ".webp", ".jpg", ".jpeg"):
        if pref in found:
            return found[pref]
    return None

# ── Farben (an das Logo „AI Alpha Selection" angelehnt: Navy + Royalblau) ──────
BG        = "#0E1320"   # dunkles Navy (Logo-Hintergrund)
PANEL     = "#172131"   # Kachel-/Panel-Hintergrund
PANEL_HI  = "#1F2A3D"   # hellere Kachel
GREEN     = "#22D3A0"   # positiv / eigenes Depot / BUY
RED       = "#FF5C6C"   # negativ / Bear / SELL
BLUE      = "#2F6BFF"   # Markenakzent (Logo-Blau) / Benchmark / Alpha / Base
AMBER     = "#F5B43C"   # neutral / HOLD / WATCH
TEXT      = "#FFFFFF"   # Haupttext
SUBTLE    = "#C2C9D6"   # gut lesbarer Sekundärtext (heller als MUTED)
MUTED     = "#8A93A6"   # Sekundärtext
GRID      = "#232E42"   # Gitterlinien

# ── Canvas-Formate (Breite, Höhe in px) ───────────────────────────────────────
FORMATS = {
    "carousel": (1080, 1350),   # 4:5  – Feed
    "reel":     (1080, 1920),   # 9:16 – Reel / Story
}

DPI = 150  # figsize wird daraus berechnet: px / DPI

# ── Schrift ────────────────────────────────────────────────────────────────────
# Plattformübergreifende Font-Kandidaten (Linux → Windows → macOS → Fallback)
_FONT_CANDIDATES = {
    "sans": [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",   # Linux
        "C:/Windows/Fonts/arial.ttf",                                         # Windows
        "/Library/Fonts/Arial.ttf",                                           # macOS
        "/System/Library/Fonts/Helvetica.ttc",                                # macOS alt
    ],
    "sans_bold": [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
    "mono": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "/Library/Fonts/Courier New Bold.ttf",
    ],
}


def _find_font(candidates: list) -> str | None:
    import os
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def register_fonts():
    """Registriert die Fonts in matplotlib und liefert Namen zurück."""
    sans_path = _find_font(_FONT_CANDIDATES["sans"])
    bold_path = _find_font(_FONT_CANDIDATES["sans_bold"])
    mono_path = _find_font(_FONT_CANDIDATES["mono"])
    for path in (sans_path, bold_path, mono_path):
        if path:
            try:
                font_manager.fontManager.addfont(path)
            except Exception:
                pass
    # Namen aus dem registrierten Font ableiten
    from matplotlib import font_manager as fm
    def _name(path, fallback):
        if not path:
            return fallback
        try:
            prop = fm.FontProperties(fname=path)
            return prop.get_name()
        except Exception:
            return fallback
    return {
        "sans": _name(sans_path, "DejaVu Sans"),
        "mono": _name(mono_path, "DejaVu Sans Mono"),
    }


# ── Pflicht-Disclaimer ──────────────────────────────────────────────────────
# An die wikifolio-Trennungsregel angepasst: Es wird über das wikifolio /
# Depot gesprochen, NICHT über das Zertifikat; keine ISIN, keine Kaufempfehlung.
DISCLAIMER_SHORT = (
    "Keine Anlageberatung oder Kaufempfehlung. Dargestellt wird die vergangene "
    "Wertentwicklung des Depots – kein verlässlicher Indikator für die "
    "Zukunft. Kapitalanlagen bergen Verlustrisiken bis zum Totalverlust."
)

DISCLAIMER_LONG = (
    "Risikohinweis & Disclaimer\n"
    "Dieser Beitrag bezieht sich auf das wikifolio „AI Alpha Selection\" und "
    "dient der Information/Eigenwerbung. Er stellt KEINE Anlageberatung, "
    "Finanzanalyse oder Kauf-/Verkaufsempfehlung dar – insbesondere keine "
    "Empfehlung zum Erwerb eines Zertifikats. Gezeigt wird die vergangene "
    "Wertentwicklung des Depots; diese ist KEIN verlässlicher Indikator für "
    "künftige Ergebnisse. Kapitalmarktanlagen bergen Verlustrisiken bis zum "
    "Totalverlust. Triff keine Anlageentscheidung allein aufgrund dieses Beitrags."
)

# ── Disclaimer für Einzelaktien-ANALYSEN (kein wikifolio-Bezug) ───────────────
# Analyse-Posts sind redaktionelle Einschätzungen zu einer Aktie — KEINE
# Anlageberatung. Score/Verdict/Kursziele sind KI-generiert.
DISCLAIMER_ANALYSE_SHORT = (
    "Keine Anlageberatung. Analysen auf Basis öffentlicher Daten. "
    "Kursziele sind Szenarien, keine Prognosen. Kapitalanlagen bergen "
    "Verlustrisiken bis zum Totalverlust."
)

DISCLAIMER_ANALYSE_LONG = (
    "Risikohinweis & Disclaimer\n"
    "Diese Aktienanalyse ist eine KI-generierte, redaktionelle Einschätzung auf "
    "Basis öffentlich verfügbarer Daten und stellt KEINE Anlageberatung, "
    "Finanzanalyse oder Kauf-/Verkaufsempfehlung dar. Verdict, Score und "
    "Kursziel-Szenarien sind keine Prognosen und kein verlässlicher Indikator "
    "für künftige Kursentwicklungen. Kapitalmarktanlagen bergen Verlustrisiken "
    "bis zum Totalverlust. Triff keine Anlageentscheidung allein aufgrund dieses "
    "Beitrags und konsultiere bei Bedarf einen unabhängigen Berater."
)
