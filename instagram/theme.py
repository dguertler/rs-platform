"""
Marken- und Design-System für die AI-Alpha-Selections Instagram-Grafiken.
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

# ── Farben (an das Logo „AI Alpha Selection" angelehnt: Navy + Royalblau) ──────
BG        = "#0E1320"   # dunkles Navy (Logo-Hintergrund)
PANEL     = "#172131"   # Kachel-/Panel-Hintergrund
PANEL_HI  = "#1F2A3D"   # hellere Kachel
GREEN     = "#22D3A0"   # positiv / eigenes Depot
RED       = "#FF5C6C"   # negativ
BLUE      = "#2F6BFF"   # Markenakzent (Logo-Blau) / Benchmark / Alpha
TEXT      = "#FFFFFF"   # Haupttext
MUTED     = "#8A93A6"   # Sekundärtext
GRID      = "#232E42"   # Gitterlinien

# ── Canvas-Formate (Breite, Höhe in px) ───────────────────────────────────────
FORMATS = {
    "carousel": (1080, 1350),   # 4:5  – Feed
    "reel":     (1080, 1920),   # 9:16 – Reel / Story
}

DPI = 150  # figsize wird daraus berechnet: px / DPI

# ── Schrift ────────────────────────────────────────────────────────────────────
# Liberation Sans ist Helvetica-artig und sauber; DejaVu Mono für Zahlen.
_SANS = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
_SANS_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def register_fonts():
    """Registriert die Fonts in matplotlib und liefert Namen zurück."""
    for path in (_SANS, _SANS_BOLD, _MONO):
        try:
            font_manager.fontManager.addfont(path)
        except Exception:
            pass
    return {
        "sans": "Liberation Sans",
        "mono": "DejaVu Sans Mono",
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
