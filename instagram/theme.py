"""
Marken- und Design-System für die AI-Alpha-Selections Instagram-Grafiken.
Zentrale Stelle für Farben, Fonts, Canvas-Größen und Layout-Konstanten,
damit Carousel (4:5) und Reel (9:16) konsistent aussehen.
"""
from matplotlib import font_manager

# ── Farben ───────────────────────────────────────────────────────────────────
BG        = "#0B0E14"   # fast-schwarzer Hintergrund
PANEL     = "#131A26"   # Kachel-/Panel-Hintergrund
PANEL_HI  = "#1B2433"   # hellere Kachel
GREEN     = "#22D3A0"   # Akzent / positiv
RED       = "#FF5C6C"   # negativ
BLUE      = "#4C8DFF"   # Benchmark / sekundär
TEXT      = "#FFFFFF"   # Haupttext
MUTED     = "#8A93A6"   # Sekundärtext
GRID      = "#222C3C"   # Gitterlinien

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


# Pflicht-Disclaimer (kurz fürs Bild, lang für die Caption)
DISCLAIMER_SHORT = (
    "Keine Anlageberatung. Investieren in Wertpapiere birgt Verlustrisiken "
    "bis zum Totalverlust. Vergangene Wertentwicklung ist kein verlässlicher "
    "Indikator für die Zukunft."
)

DISCLAIMER_LONG = (
    "⚠️ Risikohinweis & Disclaimer\n"
    "Dieser Beitrag ist Eigenwerbung für das wikifolio „AI Alpha Selections\" "
    "und stellt KEINE Anlageberatung, Kauf-/Verkaufsempfehlung oder "
    "Finanzanalyse dar. Ein wikifolio-Zertifikat ist eine "
    "Inhaberschuldverschreibung mit Emittentenrisiko (Totalverlustrisiko). "
    "Die gezeigte Wertentwicklung bezieht sich auf einen kurzen, vergangenen "
    "Zeitraum und ist KEIN verlässlicher Indikator für künftige Ergebnisse. "
    "Triff keine Anlageentscheidung allein aufgrund dieses Beitrags."
)
