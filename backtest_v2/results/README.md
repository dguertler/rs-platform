# Backtest 2.0 — Ergebnisse (Validierungslauf, Engine-Stand v3)

**Stand:** 03.07.2026 · Rohdaten je Markt: `{market}_{datum}.json` in diesem
Verzeichnis (enthalten seit v3 auch Equity-Kurve, Benchmark-Verlauf und die
vollständige Trade-Liste für die Chart-Ansicht im Backtest-Tab von `v2.html`).

## Ergebnisse (je 0,1 % Kosten pro Seite)

| Markt | Zeitraum | Strategie | Buy&Hold | Alpha | 200d-Regel | Max-DD | Sharpe | Profit-Factor | Trades |
|---|---|---|---|---|---|---|---|---|---|
| Nasdaq-100 | 2024-06 – 2026-07 | +31,4% | +55,6% | −24,2pp | +41,5% | 14,6% | 1,07 | **1,66** | 123 |
| S&P 500 | 2024-07 – 2026-07 | +14,2% | +35,2% | −21,0pp | +16,2% | 17,7% | 0,49 | 1,16 | 218 |
| Smallcap SC600 | 2024-07 – 2026-07 | **+53,9%** | +37,9% | **+16,0pp** | +8,2% | **41,6%** ⚠️ | 0,74 | 1,51 | 229 |

## Zwei Engine-Bugs wurden im Zuge der Validierung gefunden und behoben

Die Bugs wurden durch kritisches Nachfragen des Nutzers ("sicher, dass da
alles richtig eingestellt ist?") bzw. durch Plausibilitätsprüfung der ersten
Läufe entdeckt — beide sind ein Beleg dafür, warum Regel B5
(Plausibilitäts-/Sensitivitätsprüfung) existiert:

1. **Positionsgrößen-Bug (v1→v2):** Die Entry-Größenberechnung verwendete den
   **Benchmark**-Schlusskurs statt des Ticker-Schlusskurses für den
   Portfolio-Wert — einzelne Positionen erreichten bis zu 54 % statt max.
   15 % des Portfolios. Nach Fix sank der Max-DD im S&P-500-Lauf von 33,9 %
   auf ~16 %.
2. **Weekly-Look-Ahead-Bug (v2→v3):** yfinance stempelt Weekly-Kerzen mit dem
   **Montag**, die Kerze enthält aber die ganze Woche bis Freitag. Die Engine
   wertete Signale am Montag aus und sah dabei bereits Freitags-Schlusskurse
   (Verstoß gegen Regel B1); zusätzlich fielen 8 Feiertags-Montage komplett
   aus der Signal-Auswertung. Fix: Auswertung am letzten Handelstag der Woche
   (Freitag), Entry am nächsten Handelstag zum Open — exakt wie es die
   v1-Logik in `backtest_logic.js` (getWeekEnd) schon immer machte.
   Effekt des Fixes: Nasdaq +22,8 % → +31,4 %, Smallcap −4,4 % → +53,9 %
   (der Look-Ahead hatte paradoxerweise geschadet: Entries feuerten dienstags
   auf Basis unvollständiger Wochensignale und produzierten Fehltrades).

## Einordnung der Ergebnisse

**Positiv:**
- Smallcap schlägt Buy&Hold deutlich (+16pp Alpha) — konsistent mit der
  Theorie, dass RS-Momentum-Strategien in breiten, ineffizienteren Universen
  am besten funktionieren.
- Nasdaq-PF von 1,66 bei Sharpe 1,07 ist eine solide Basis.
- Die Regime-Aufschlüsselung zeigt das erwartete Muster: bester Ertrag in
  green/yellow-Phasen; das lange "unknown"-Fenster (SMA200-Anlauf, ~40 % des
  Zeitraums) verwässert alles.

**Negativ / offene Probleme:**
- **DAX funktionierte nicht** (PF 0,89): 38 investierbare Titel sind zu wenig
  für einen RS-Perzentil-Funnel — die Schwelle ≥85 ließ nur ~5 Kandidaten zu,
  Zufallsrauschen dominierte. Konsequenz: DAX im September 2026 komplett aus
  der Plattform entfernt (Tabelle, Workflow, Daten, Backtest-Ergebnisse).
- **Smallcap-Max-DD von 41,6 % ist inakzeptabel** für das erklärte Ziel
  (Max-DD 15–20 %). Haupttreiber: die 197 "unknown"-Tage liefen ohne
  Regime-Bremse voll investiert, und Smallcap-Gaps reißen Stops (realisiertes
  Risiko > geplantes 1 %). Vor Live-Einsatz zwingend zu lösen (z. B.
  konservatives Verhalten bei "unknown": Budget 50 % statt 100 %).
- Nasdaq/S&P 500 bleiben hinter Buy&Hold — in einem fast durchgehenden
  Bullenmarkt erwartbar (das System zahlt eine Versicherungsprämie in Form
  von Cash-Drag und Stops, deren Nutzen sich erst in einem Bärenmarkt zeigen
  kann), aber unbewiesen bleibt eben genau dieser Nutzen: **das verfügbare
  Datenfenster (~2 Jahre) enthält keinen echten Bärenmarkt.**

## Zum Ziel "Profit-Faktor 2"

Aktueller Stand: 1,16 (S&P 500) bis 1,66 (Nasdaq). Der Weg zu PF 2 führt über
Selektivität (weniger, bessere Trades), z. B.: Entry nur bei Setup-Qualität
≥ 3 Punkte, Volumen-Bestätigung (Daten ab dem nächsten Collector-Lauf
verfügbar), höhere RS-Schwelle, konservativeres "unknown"-Verhalten.
**Bewusste Entscheidung, das JETZT NICHT zu tun:** Jede dieser Stellschrauben
auf dem vorhandenen 2-Jahres-Fenster zu drehen, bis PF 2 erscheint, wäre
Overfitting im Lehrbuchsinn (Regel B5) — das Ergebnis wäre eine Strategie,
die genau ein historisches Fenster auswendig gelernt hat. Kalibrierung
erst nach Datenerweiterung (B3/B4: längere Historie inkl. 2022, historische
Indexmitgliedschaft), dann Training/Validierung getrennt.

## Regel-Status (B1–B10)

| Regel | Status |
|---|---|
| B1 Kein Look-Ahead | ✅ umgesetzt (nach Bugfix v3 — Weekly-Auswertung am Wochenschluss) |
| B2 Kosten 0,1 %/0,2 % | ✅ umgesetzt |
| B3 Survivorship-frei | ❌ offen (aktuelles Universum rückwirkend gehandelt) |
| B4 Out-of-Sample inkl. 2022 | ❌ nicht möglich (~2 Jahre Daten, kein Netzwerkzugriff zum Nachladen) |
| B5 Sensitivitätsanalyse | ❌ offen (erst nach B3/B4 sinnvoll) |
| B6 Portfolio-Ebene | ✅ umgesetzt |
| B7 Kennzahlen-Pflicht | ✅ umgesetzt (je Regime getrennt) |
| B8 Benchmark-Fairness | ✅ umgesetzt — nur Smallcap schlägt bisher beide Vergleiche |
| B9 Kein 4H im Langfrist-Walk | ✅ dokumentiert (Entry = Weekly+Daily 2/2) |
| B10 Eine Quelle der Wahrheit | ✅ umgesetzt (`signals.py` importiert Live-Funktionen) |

## Nächste Schritte

1. Längere Historie beschaffen (Netzwerkzugriff oder EODHD/Norgate) → B4-
   Kalibrierung mit Bärenmarkt 2022, erst dann Parameter-Tuning Richtung PF 2.
2. Historische Indexmitgliedschaft (B3) rekonstruieren.
3. "unknown"-Regime-Verhalten entscheiden (konservativ vs. voll investiert) —
   Backtest beider Varianten nach Datenerweiterung.
