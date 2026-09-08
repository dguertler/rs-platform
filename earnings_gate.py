"""earnings_gate.py — Entscheidungslogik: Wird ein Earnings-Event gemeldet?

Single Source of Truth für die Alert-Schwellen aller drei Earnings-Scanner
(check_earnings.py, check_earnings_global.py, check_earnings_premarket.py).
Bewusst ohne yfinance/pandas-Import, damit die Logik ohne Netzwerkzugriff
getestet werden kann (siehe test_earnings_gate.py).

Zwei Auslöser führen zu einem Alert:

  1. TRIGGER_EPS_BEAT       — EPS-Surprise >= MIN_EPS_SURPRISE (10 %).
                              Der klassische Auslöser; trifft vor allem Small-
                              und Midcaps, bei denen die Konsensschätzung weit
                              streut.
  2. TRIGGER_PRICE_REACTION — Kurssprung >= MIN_REACTION_JUMP (8 %) bei einem
                              RS-getrackten Titel, unabhängig von der Surprise.
                              Grund: Mega-Caps mit enger eigener Guidance und
                              40 Analysten erreichen 10 % EPS-Surprise praktisch
                              nie (AMZN Q2 2026: +6 % bereinigt bei +15 %
                              Kursreaktion). Bei diesen Titeln IST die
                              Marktreaktion das Signal.

Zusätzlich filtert detect_eps_oneoff() Surprises heraus, die nur auf einem
bilanziellen Einmaleffekt beruhen (AMZN Q2 2026: GAAP-EPS 5,75 $ durch die
53,4 Mrd. $ schwere Anthropic-Neubewertung gegenüber ~1,9 $ in den Vorquartalen
— eine Surprise von rund +200 %, die operativ nichts bedeutet).
"""

from collections import namedtuple
from statistics import median

# ── Schwellen ────────────────────────────────────────────────────────────────

MIN_PRICE_JUMP    = 0.05   # ≥5 % Close-zu-Close als Vorfilter für den Scan
MIN_EPS_SURPRISE  = 10.0   # ≥10 % EPS-Surprise (klassischer Auslöser)
MIN_REACTION_JUMP = 0.08   # ≥8 % Kurssprung → Alert auch ohne EPS-Surprise
                            # (nur für RS-getrackte Titel)
MAX_REVENUE_DECLINE = -0.05  # Umsatz YoY darunter → kein Alert

# Einmaleffekt-Erkennung
EPS_ONEOFF_FACTOR         = 3.0  # EPS ≥ 3× Median der Vorquartale …
MIN_ONEOFF_REVENUE_GROWTH = 1.0  # … und Umsatz YoY < +100 % → verzerrt
EPS_HISTORY_QUARTERS      = 4    # Vergleichsfenster für den Median

TRIGGER_EPS_BEAT       = "eps-beat"
TRIGGER_PRICE_REACTION = "kursreaktion"

GateResult = namedtuple("GateResult", "passed trigger reason")


def detect_eps_oneoff(eps_actual, prior_eps, revenue_growth_yoy=None) -> bool:
    """True, wenn der gemeldete EPS-Wert so weit über der eigenen Quartals-
    historie liegt, dass ein bilanzieller Einmaleffekt wahrscheinlicher ist
    als eine operative Ergebnisverbesserung.

    prior_eps: gemeldete EPS der Vorquartale (jüngstes zuerst), None-Werte
    erlaubt. Zwei Schutzregeln gegen Fehlklassifikation:

    - Enthält die Historie ein Verlustquartal, gilt der Ausschlag als echtes
      Turnaround-Muster (Referenzfall CNC: Q4 25 EPS −1,16 $ → Q1 26 3,37 $)
      und wird NICHT als Einmaleffekt gewertet.
    - Wird der Ausschlag vom Umsatzwachstum getragen (YoY ≥ 100 %), ist er
      operativ erklärbar und zählt ebenfalls nicht als Einmaleffekt.
    """
    if eps_actual is None:
        return False

    history = [e for e in (prior_eps or [])[:EPS_HISTORY_QUARTERS] if e is not None]
    if not history:
        return False

    if any(e < 0 for e in history):
        return False  # Verlustquartal in der Historie → Turnaround, kein Einmaleffekt

    baseline = median(abs(e) for e in history)
    if baseline <= 0:
        return False

    if abs(eps_actual) < EPS_ONEOFF_FACTOR * baseline:
        return False

    if revenue_growth_yoy is not None and revenue_growth_yoy >= MIN_ONEOFF_REVENUE_GROWTH:
        return False

    return True


def evaluate_gate(jump, surprise_pct, revenue_growth_yoy=None,
                  eps_distorted=False, rs_tracked=False) -> GateResult:
    """Entscheidet über den Alert-Versand.

    jump:          Kursreaktion als Dezimalwert (0.153 = +15,3 %), darf None sein
    surprise_pct:  EPS-Surprise in Prozent (11.8 = +11,8 %), darf None sein
    rs_tracked:    Ticker steht in einem der RS-Indizes → Kursreaktions-Trigger
                   ist zulässig

    Rückgabe: GateResult(passed, trigger, reason) — reason ist auch im
    Negativfall gesetzt und wird von den Scannern geloggt.
    """
    if revenue_growth_yoy is not None and revenue_growth_yoy < MAX_REVENUE_DECLINE:
        return GateResult(False, None,
                          f"Umsatz YoY stark negativ ({revenue_growth_yoy * 100:.1f} %)")

    beat = surprise_pct is not None and surprise_pct >= MIN_EPS_SURPRISE

    if beat and not eps_distorted:
        return GateResult(True, TRIGGER_EPS_BEAT,
                          f"EPS-Surprise {surprise_pct:+.1f} % ≥ {MIN_EPS_SURPRISE:.0f} %")

    if rs_tracked and jump is not None and jump >= MIN_REACTION_JUMP:
        if eps_distorted:
            surprise_note = " (EPS-Surprise durch Einmaleffekt verzerrt, nicht verwendet)"
        elif surprise_pct is not None:
            surprise_note = f", EPS-Surprise {surprise_pct:+.1f} %"
        else:
            surprise_note = ""
        return GateResult(True, TRIGGER_PRICE_REACTION,
                          f"Kursreaktion {jump * 100:+.1f} % ≥ "
                          f"{MIN_REACTION_JUMP * 100:.0f} % bei RS-getracktem Titel"
                          f"{surprise_note}")

    if beat and eps_distorted:
        return GateResult(False, None,
                          "EPS-Surprise durch bilanziellen Einmaleffekt verzerrt — "
                          "operativ nicht belastbar")

    if surprise_pct is None:
        return GateResult(False, None, "keine EPS-Surprise ermittelbar")

    return GateResult(False, None,
                      f"unter EPS-Schwelle ({surprise_pct:+.1f} % < {MIN_EPS_SURPRISE:.0f} %)"
                      + ("" if rs_tracked else " und nicht RS-getrackt"))
