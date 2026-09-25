"""
Zuordnung historischer NASDAQ-100-Symbole zu Yahoo-Finance-Symbolen.

Die Mitgliedschaftsliste ist point-in-time (FB bis 2022, danach META). Yahoo
führt die Kurshistorie umbenannter Firmen dagegen nur unter dem heutigen
Symbol. ALIASES nennt je altem Symbol die Yahoo-Kandidaten in Prüfreihenfolge;
das Originalsymbol wird immer zusätzlich (zuletzt) probiert.

Nur Umbenennungen derselben Gesellschaft gehören hierher — keine Übernahmen,
bei denen die Käuferin eine andere Kurshistorie hat.
"""

ALIASES = {
    "FB":    ["META"],
    "ERTS":  ["EA"],
    "HANS":  ["MNST"],
    "PCLN":  ["BKNG"],
    "KFT":   ["MDLZ"],
    "UAUA":  ["UAL"],
    "RIMM":  ["BB"],
    "SYMC":  ["GEN"],
    "NLOK":  ["GEN"],
    "CTRP":  ["TCOM"],
    "WLTW":  ["WTW"],
    "DISCA": ["WBD"],
    "FISV":  ["FISV", "FI"],
    "LINTA": ["QRTEA", "QVCGA"],
    "QVCA":  ["QRTEA", "QVCGA"],
    "QRTEA": ["QRTEA", "QVCGA"],
}

# Symbole, die Yahoo heute einer ANDEREN Firma zuordnet, deren Historie den
# Mitgliedszeitraum trotzdem abdeckt — die Abdeckungsprüfung kann das nicht
# erkennen. GOLD war bis 2013 Randgold Resources, bei Yahoo steht darunter
# die Historie von Barrick Gold.
BLOCKLIST = {"GOLD"}

# Die Kursreihe muss spätestens so viele Kalendertage nach Beginn eines
# Mitgliedsintervalls einsetzen. Beginnt sie später, gehört das Symbol bei
# Yahoo zu einer anderen, jüngeren Firma (DELL 2016, ALTR, LIFE, NWSA …).
MAX_START_GAP_DAYS = 7


def candidates(ticker):
    """Yahoo-Symbole, die für ein historisches Symbol probiert werden."""
    if ticker in BLOCKLIST:
        return []
    out = list(ALIASES.get(ticker, []))
    if ticker not in out:
        out.append(ticker)
    return out
