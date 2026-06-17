"""
Psychologische Hook-Generator für AI Alpha Selection.

Drei Frameworks (Verlustangst, Wissenslücke, Widerspruch) werden zufällig
gezogen und in Caption, Carousel Slide 1 und Reel Szene 1 eingesetzt.
Derselbe Hook-Typ bleibt innerhalb eines Generierungsdurchlaufs konsistent.
"""
import random

HOOKS = {
    "verlustangst": (
        "Hör auf, blind {hype_aktie} zu kaufen. "
        "Während alle auf die Charts starren, übernimmt das Monopol von {ticker} heimlich den Markt."
    ),
    "wissensluecke": (
        "Es gibt einen Grund, warum die großen Tech-Insider gerade extrem leise "
        "bei {ticker} einsteigen… und nein, es hat nichts mit den Earnings zu tun."
    ),
    "widerspruch": (
        "Jeder denkt, dass {hype_aktie} diesen Sektor dominiert. "
        "Aber die echten Alpha-Signale zeigen: Der wahre Gewinner steht im Schatten von {ticker}."
    ),
}

# Pexels-Suchbegriffe je Framework — aggressiv, kein Standard-B-Roll
HOOK_VISUALS = {
    "verlustangst": "glowing quantum chip fast zoom 4k dark",
    "wissensluecke": "dark server room dramatic light flicker 4k",
    "widerspruch":   "neon stock market data surge abstract 4k",
}

# Kürzere Versionen für Slide-Headlines (nur erster Satz, max. ~12 Wörter)
_HOOK_SHORT = {
    "verlustangst": "Hör auf, blind {hype_aktie} zu kaufen. {ticker} übernimmt heimlich den Markt.",
    "wissensluecke": "Warum steigen Tech-Insider gerade leise bei {ticker} ein?",
    "widerspruch":   "{hype_aktie} dominiert den Sektor? Die echten Alpha-Signale zeigen: {ticker}.",
}


def get_hook(ticker: str, hype_aktie: str = "Nvidia") -> dict:
    """
    Zieht zufällig einen Hook und gibt ihn als Dict zurück.

    Returns: {"typ": str, "text": str, "short": str, "visual": str}
    """
    typ = random.choice(list(HOOKS.keys()))
    return {
        "typ": typ,
        "text": HOOKS[typ].format(ticker=ticker, hype_aktie=hype_aktie),
        "short": _HOOK_SHORT[typ].format(ticker=ticker, hype_aktie=hype_aktie),
        "visual": HOOK_VISUALS[typ],
    }


def get_hook_typed(typ: str, ticker: str, hype_aktie: str = "Nvidia") -> dict:
    """Gibt einen spezifischen Hook-Typ zurück (für reproduzierbare Läufe)."""
    if typ not in HOOKS:
        typ = "wissensluecke"
    return {
        "typ": typ,
        "text": HOOKS[typ].format(ticker=ticker, hype_aktie=hype_aktie),
        "short": _HOOK_SHORT[typ].format(ticker=ticker, hype_aktie=hype_aktie),
        "visual": HOOK_VISUALS[typ],
    }
