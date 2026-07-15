# Strategieplan — Auswahlmechanismus 2.0

**Stand:** Juli 2026
**Ziel:** Je Marktphase in die relativ stärksten Aktien investieren — Mischung aus
risikoadjustierter Rendite und stabilem Track-Record (Max-Drawdown-Ziel ~15–20 %,
8–12 Positionen). Ansatz: **Hybrid** — regelbasierter Quant-Funnel liefert die
Kaufliste, die LLM-Analyse wirkt nur noch als Qualitäts-/Veto-Layer.
Datenbasis: zunächst kostenlos (yfinance + rekonstruierte Indexhistorie),
Upgrade auf bezahlte survivorship-bias-freie Daten erst nach bestandener Validierung.

---

## 1. Ist-Zustand — Bewertung der heutigen Vorgehensweise

### Was bereits gut ist
- Mehrere Universen (NDX, S&P 500, DAX, Smallcap) mit täglicher RS-Berechnung
- Multi-Timeframe-Struktursignal (GWS Weekly/Daily/4H) als Ampel — konsistent in
  Frontend, Alerts und Backtest portiert
- Analyse-Prompt mit Szenario-EV, Pflicht-Herleitung der Kursziele und
  Anti-Halluzinations-Regeln — überdurchschnittlich diszipliniert
- Zombie-Stock-Filter, Fehler-Abbruch statt stiller NaN-Commits, Indexänderungs-Erkennung

### Konkrete Schwächen

| # | Baustein | Schwäche | Wirkung |
|---|---|---|---|
| S1 | RS-Score | Simple Summe der Überrenditen (5T…12M) — nicht volatilitätsadjustiert, Fenster überlappen, 12M dominiert | High-Beta-Titel werden systematisch bevorzugt; Score misst Beta × Momentum, nicht Qualität des Momentums |
| S2 | RS-Score | Absolutwert statt Perzentil-Rang je Universum | Scores zwischen Indizes/Regimen nicht vergleichbar; Schwellen (z.B. „RS > 60") bedeuten je Marktphase etwas anderes |
| S3 | Marktphase | Keinerlei Regime-Logik — Entries werden in jeder Marktphase gleich behandelt | Breakout-Strategien haben in Risk-Off-Phasen historisch negative Erwartungswerte; genau dort entstehen die großen Drawdowns |
| S4 | Entry | Swing-Erkennung braucht ±2 Zukunfts-Bars zur Bestätigung; Backtest erlaubt Breakouts ab `gws_idx+1` | Look-Ahead-Bias: Der Backtest handelt Breakouts, die live erst 2 Bars später erkennbar gewesen wären |
| S5 | Exit | Kein definiertes Gewinnziel, kein Trailing-Mechanismus außer Strukturbruch; Hard-Stop nur auf Wochenschluss geprüft | Intra-Woche-Verluste deutlich größer als geplantes Risiko; Gewinner werden teils zu spät abgegeben |
| S6 | Exit | Backtest-Exit (Daily-Strukturbruch) ≠ Live-Praxis (diskretionär: „RS-Abschwächung / Gewinn mitgenommen") | Backtest validiert eine andere Strategie als die, die tatsächlich gehandelt wird |
| S7 | Backtest | Einzel-Ticker-Simulation (10k fix je Ticker), keine Portfolio-Ebene | Keine Aussage über Kapitalallokation, Klumpenrisiko, Portfolio-Drawdown, Cash-Quote |
| S8 | Backtest | Keine Transaktionskosten/Slippage, Survivorship-Bias (nur heutige Indexmitglieder), `top20_history` mit heutiger Mitgliederliste rückgerechnet | Ergebnisse strukturell zu optimistisch |
| S9 | Backtest | 4H-Daten nur 730 Tage; keine Out-of-Sample-Trennung, keine Parameter-Sensitivität | Regeln sind implizit auf die jüngste (Bullen-)Phase gefittet |
| S10 | Analyse | Verdicts/Scores werden nie gegen die tatsächliche Folgerendite gemessen | Kein Lerneffekt; unbekannt, ob der LLM-Layer Alpha hinzufügt oder kostet |
| S11 | Auswahl | Zombie-/Liquiditätsfilter erst bei der Analyse, nicht im Screening | RS-Listen enthalten nicht investierbare Titel |

---

## 2. Zielarchitektur — der Auswahl-Funnel

```
Stufe 0  REGIME       Marktphasen-Ampel bestimmt Exposure-Budget (0–100 %)
Stufe 1  UNIVERSUM    Investierbarkeit: Liquidität, MCap, Datenqualität
Stufe 2  RS 2.0       Volatilitätsadjustierter RS-Perzentil-Rang je Universum
Stufe 3  SETUP        GWS-Breakout (3/3) + Qualitätsmerkmale des Breakouts
Stufe 4  LLM-VETO     11-Abschnitte-Analyse als Qualitätsfilter (nur Veto/Sizing)
Stufe 5  PORTFOLIO    Positionsgröße, Sektor-Caps, Max-Positionen, Cash-Quote
```

Regel: **Stufen 0–3 und 5 sind vollständig regelbasiert und backtestbar.**
Nur Stufe 4 ist LLM-basiert — sie darf Kandidaten streichen oder die
Positionsgröße reduzieren, aber niemals Kandidaten hinzufügen oder Regeln der
anderen Stufen überstimmen. So bleibt der backtestbare Kern messbar und der
LLM-Beitrag separat auswertbar (siehe Abschnitt 7).

### Stufe 0 — Marktphasen-Modul (neu, höchste Priorität)

Tägliche Regime-Ampel je Universum (Benchmark: QQQ/SPY/DAX):

- **Trend:** Benchmark-Close vs. 200-Tage-Linie und Steigung der 50-Tage-Linie
- **Breite:** Anteil der Universums-Titel über ihrer 50d- und 200d-Linie
  (aus vorhandenen OHLCV-Daten berechenbar, keine neuen Quellen nötig)
- **Vola:** Realisierte 20d-Volatilität des Benchmark vs. 1-Jahres-Median

| Regime | Bedingung (Startwerte, per Backtest zu kalibrieren) | Exposure-Budget | Verhalten |
|---|---|---|---|
| 🟢 Risk-On | Benchmark > 200d, Breite > 50 % | 90–100 % | Volle Entry-Aktivität |
| 🟡 Neutral | Benchmark > 200d, Breite < 50 % **oder** 50d fallend | 50–60 % | Nur A-Setups (RS-Perzentil ≥ 90), halbe Positionsgröße neu |
| 🔴 Risk-Off | Benchmark < 200d | 0–30 % | Keine neuen Entries, Trailing-Stops enger (Faktor 0,75), Cash aufbauen |

Regimewechsel erzwingen **keinen** sofortigen Komplettverkauf — bestehende
Positionen laufen über ihre Exit-Regeln aus. Das vermeidet Whipsaw an der 200d-Linie.

### Stufe 1 — Investierbarkeits-Filter (ins Screening vorziehen)

- MCap ≥ $300 M (Smallcap-Universum: ≥ $100 M), Zombie-Filter aus PROMPT.md hier anwenden
- Ø-Dollar-Volumen 20d ≥ $5 M (Smallcap: ≥ $1 M)
- Kurs ≥ $5 · mind. 126 Handelstage Historie
- Earnings-Termin in < 5 Handelstagen → Entry-Sperre (Termin liegt in fundamentals.json bzw. yfinance)

### Stufe 2 — RS 2.0

Ersetzt die Roh-Summe:

1. Je Fenster (20/50/126/252 Tage; 5T/10T raus — zu viel Rauschen fürs Ranking,
   bleiben nur als Anzeige) Überrendite vs. Benchmark **geteilt durch die
   realisierte Volatilität des Titels im selben Fenster** (Sharpe-artige Ratio)
2. Gewichtung: 20T×0,2 · 50T×0,3 · 126T×0,3 · 252T×0,2 — Startwerte, per Backtest kalibrieren
3. Ergebnis je Universum in **Perzentil-Rang 0–100** umrechnen (das wird der neue RS-Score)
4. Zusätzlich ausweisen: RS-Trend (Perzentil heute vs. vor 10 Handelstagen) —
   steigende RS-Linie ist Entry-Bonus, fallende ist Exit-Frühwarnung
5. Sektor-RS: gleiche Rechnung auf Sektor-Ebene; Entry-Bonus, wenn der Titel
   in einem Top-3-Sektor liegt

Kandidatenliste: RS-Perzentil ≥ 85 (🟡-Regime: ≥ 90).

### Stufe 3 — Setup-Qualität (GWS beibehalten, präzisieren)

- GWS-Logik bleibt, aber: **Breakout zählt erst, wenn das Swing-Hoch bestätigt ist**
  (d.h. frühestens 2 Bars nach dem Swing-Hoch) — behebt S4 in Live UND Backtest
- Breakout-Qualität als Zusatzpunkte:
  - Volumen am Breakout-Tag ≥ 1,5× 20d-Durchschnitt (Volumen liegt in den Rohdaten vor, wird bislang verworfen — in `rs_colab.py` mit exportieren)
  - Abstand Entry → Stop ≤ 1,5× ATR(14): enge Basis = besseres CRV
  - Basis-Dauer ≥ 4 Wochen (längere Konsolidierung = tragfähigerer Ausbruch)

---

## 3. Exit-Regelwerk (neu — eine Regel-Familie für Live UND Backtest)

Das heutige größte Einzelproblem ist S6: Es wird eine andere Strategie gelebt als
getestet. Ab sofort gilt ein einziges, schriftliches Regelwerk:

1. **Initial-Stop:** unter letztem bestätigten Daily-Swing-Low − 1 %,
   maximal aber 2× ATR(14) unter Entry. Risiko pro Trade = 0,75–1 % des Portfolios.
2. **Teilverkauf:** 1/3 der Position bei +2R (2× Initialrisiko), Stop des Rests auf Einstand.
   → stabilisiert Wochen-Track-Record (Ziel „stabiler Track-Record") und senkt Vola.
3. **Trailing:** Rest läuft mit Struktur-Trailing (Close unter letztem bestätigten
   Daily-Swing-Low = Exit am Folgetag Open). Im 🔴-Regime: Trailing auf letztes
   4H-Swing-Low verengt.
4. **RS-Decay-Exit:** Fällt der Titel unter RS-Perzentil 60 **und** unter die 50d-Linie → Exit.
5. **Zeit-Stopp:** Nach 15 Handelstagen weder +1R erreicht noch Stop ausgelöst → Exit
   (totes Kapital rotieren; Parameter per Backtest kalibrieren).
6. **Stop-Prüfung täglich** (nicht wöchentlich) — auch im Backtest (behebt S5).
7. **Kein diskretionäres „Gewinn mitnehmen"** außerhalb dieser Regeln. Ausnahmen
   müssen als Regel formuliert, gebacktestet und hier eingetragen werden.

---

## 4. Portfolio-Regeln (Stufe 5)

- Max. 10 Positionen · max. 3 je Sektor · max. 15 % Portfoliogewicht je Titel
- Positionsgröße = (Portfoliowert × Risiko% ) / (Entry − Stop), gedeckelt durch Exposure-Budget der Regime-Ampel
- Neue Entries nur, wenn Cash-Quote nach Kauf ≥ (100 % − Exposure-Budget)
- Bei mehr Signalen als Slots: Rangfolge nach RS-Perzentil, dann Setup-Qualitätspunkten

---

## 5. Backtesting 2.0

### Architektur
Neuer Python-Portfolio-Backtester (`backtest_v2/engine.py`) statt (bzw. zusätzlich zu)
der Einzel-Ticker-JS-Logik. Das Frontend-Backtesting bleibt als Anschauung; die
Strategie-Validierung läuft in Python (gleiche Signal-Module wie Live:
`backend/gws_analysis.py` importieren, nicht duplizieren).

### Verbindliche Backtesting-Regeln

| # | Regel | Status (Juli 2026) |
|---|---|---|
| B1 | **Kein Look-Ahead:** Jedes Signal darf nur Daten verwenden, die am Signaltag verfügbar waren. Swing-Punkte gelten erst 2 Bars nach Auftreten als bestätigt. Entry immer zum Open des Folgetags. | ✅ umgesetzt |
| B2 | **Kosten:** 0,1 % Slippage + Gebühren je Seite (wikifolio-Realität eher 0,2 % — beide Varianten rechnen). | ✅ umgesetzt |
| B3 | **Survivorship:** Historische Indexmitgliedschaft verwenden. Phase 1: Wikipedia-Änderungshistorie der Indizes rekonstruieren (kostenlos); delistete Titel fehlen weiterhin in yfinance → Ergebnis konservativ interpretieren und dokumentieren. Phase 2 (nach Validierung): EODHD/Norgate. | ❌ offen |
| B4 | **Out-of-Sample:** Kalibrierung nur auf Trainingsfenster (z.B. 2016–2021), Validierung auf 2022–2026 (enthält echten Bärenmarkt 2022 — Pflicht-Testfall für das Regime-Modul). Danach Walk-Forward: je 3 Jahre Training, 1 Jahr Test, rollierend. | ❌ nicht möglich — siehe Datenbefund unten |
| B5 | **Parameter-Disziplin:** Jeder Parameter (Fenster-Gewichte, Perzentil-Schwellen, ATR-Faktoren, Zeit-Stopp) bekommt eine Sensitivitätsanalyse (±30 %). Regeln, deren Ergebnis bei kleinen Parameteränderungen kippt, gelten als überfittet und fliegen raus. | ❌ offen (erst nach B3/B4 sinnvoll) |
| B6 | **Portfolio-Ebene:** Simuliert wird das Gesamtportfolio inkl. Positionslimits, Cash-Quote, Regime-Budget — nicht Einzeltrades mit fixem Kapital. | ✅ umgesetzt |
| B7 | **Kennzahlen-Pflicht:** CAGR, Sharpe, Calmar, Max-DD, längste DD-Dauer, Exposure-Zeit, Profit-Factor, Trade-Anzahl, Alpha vs. Benchmark bei gleichem Beta — je Regime getrennt ausgewiesen. | ✅ umgesetzt |
| B8 | **Benchmark-Fairness:** Vergleich gegen Buy-and-Hold QQQ **und** gegen simple 200d-Regel auf QQQ. Die Strategie muss beide risikoadjustiert schlagen, sonst rechtfertigt sie ihre Komplexität nicht. | ✅ umgesetzt — bisher NICHT geschlagen (s. u.) |
| B9 | **Keine 4H-Abhängigkeit im Langfrist-Backtest:** Da Intraday-Historie fehlt, wird der Kern (Regime + RS 2.0 + Daily-GWS + Exits) auf Daily/Weekly validiert. 4H bleibt Timing-Verfeinerung, deren Zusatznutzen nur auf den letzten 730 Tagen gemessen wird. | ✅ umgesetzt (Entry verlangt Weekly+Daily 2/2 statt 3/3) |
| B10 | **Eine Quelle der Wahrheit:** Live-Signal-Code und Backtest-Code teilen sich dieselben Funktionen. Jede Regeländerung → Backtest neu → Ergebnis im Repo versionieren (`backtest_v2/results/`). | ✅ umgesetzt |

### Datenbefund (Juli 2026) — B3/B4 aktuell nicht durchführbar

In der Entwicklungsumgebung besteht kein Netzwerkzugriff auf Yahoo Finance
(Proxy blockiert `query1.finance.yahoo.com`). Die im Repo committeten
Markt-JSONs (`data/rs_full.json` etc.) decken nur **~2 Jahre synchronisierte
Ticker+Benchmark-Historie** ab (2024-06/07 bis heute) — nicht die für B4
geforderte Trainingsperiode 2016–2021, und keinen echten Bärenmarkt (2022
fehlt komplett). B3/B4/B5 bleiben deshalb offen, bis entweder Netzwerkzugriff
zum Nachladen längerer Historie besteht oder eine bezahlte Datenquelle
angebunden wird (siehe Abschnitt 8, Phase B).

**Validierungslauf auf dem verfügbaren ~2-Jahres-Fenster** (Engine-Stand v3
nach zwei behobenen Bugs — Positionsgrößen-Berechnung und Weekly-Look-Ahead;
volle Auswertung und Bug-Beschreibung in `backtest_v2/results/README.md`):
Smallcap schlägt Buy-and-Hold deutlich (+16pp Alpha, PF 1,51 — aber Max-DD
41,6 % wegen fehlender Regime-Bremse im "unknown"-Anlauffenster), Nasdaq
erreicht PF 1,66 bei Sharpe 1,07, S&P 500 PF 1,16, DAX funktioniert nicht
(PF 0,89 — Universum mit 38 Titeln zu klein für einen Perzentil-Funnel).
Nasdaq/S&P 500 bleiben hinter Buy-and-Hold — plausibel für ein Fenster ohne
echte Korrektur, aber unbewiesen bleibt genau der Kapitalschutz-Nutzen, den
das System verspricht. Das Ziel Profit-Faktor 2 wird NICHT durch Tuning auf
diesem kurzen Fenster angestrebt (Overfitting-Falle, Regel B5), sondern erst
nach Datenerweiterung (B3/B4) kalibriert.

### Was der Backtest bewusst NICHT abdeckt
Der LLM-Veto-Layer (Stufe 4) ist nicht rückwirkend simulierbar. Er wird
**forward** validiert (Abschnitt 7). Der Backtest misst den regelbasierten Kern;
der Live-Track-Record misst Kern + Veto. Die Differenz ist der messbare
LLM-Beitrag.

---

## 6. Analysen (LLM-Layer) — vom Autor zum Prüfer

- Rolle neu: Die Analyse bewertet **nur noch Kandidaten aus dem Funnel** und gibt
  eine von drei Entscheidungen ab: `PASS` (volle Größe) · `REDUCE` (halbe Größe) ·
  `VETO` (kein Trade) — mit maschinenlesbarer Begründung (ein Satz + Kategorie:
  Bewertung / Verwässerung / Kundenkonzentration / Bilanz / Katalysator fehlt).
- Q/G/V/K-Ratings und Szenario-EV bleiben, aber die Score→Verdict-Schwellen werden
  ab sofort **kalibriert statt gesetzt**: siehe Tracking (Abschnitt 7).
- Frische-Regel: Analyse älter als 60 Tage oder älter als der letzte
  Earnings-Termin → vor Entry-Entscheidung neu generieren (Check existiert
  bereits in `check_analysis_age.py` — an den Funnel anschließen).
- Neue Pflichtsektion im Analyse-Kopf: Regime-Ampel + RS-Perzentil + Setup-Punkte
  aus dem Funnel, damit jede Analyse ihren quantitativen Kontext dokumentiert.

### Rollen im Trade-Prozess (Breakout · EV · Analyse · Exit)

Klare Arbeitsteilung — die Signale ersetzen sich nicht gegenseitig:

1. **Einstieg:** ausschließlich der Funnel (Regime + RS 2.0 + GWS-Breakout W/D/4H).
   Weder EV noch Verdict sind Entry-Filter. EV misst Fair-Value-Konvergenz auf
   12–18 Monate — der Breakout-Trade lebt von Momentum-Fortsetzung über Tage bis
   Wochen; das sind verschiedene Renditequellen. Ein Positiv-EV-Filter würde die
   stärksten Momentum-Namen systematisch wegfiltern (Beispiel SNDK: RS-Rang 1
   bei klar negativem EV, trotzdem Ausnahme-Run).
2. **Auto-EV (ohne manuelle Analyse):** grobe Orientierung + Gap-Risiko-Indikator.
   Wirkt in der Risiko-Staffel nur als Dämpfer, nie als Verstärker.
3. **Manuelle Analyse:** liefert das belastbare, peer-verankerte EV, die
   Funnel-Entscheidung (PASS/REDUCE/VETO) und den Katalysator-Check. Ihr Gewicht
   wächst mit der Haltedauer: Wer Wochen bis Monate hält, läuft durch
   Earnings-Termine — dort entscheiden Katalysator und Fundamentaldaten, nicht
   das Chartbild.
4. **Exit:** Daily-Signal — immer. EV oder Verdict rechtfertigen nie das
   Überreiten eines Exit-Signals; sonst wird der Momentum-Trade zum
   unfreiwilligen Value-Investment.

**Verdict richtig lesen:** BUY vs. WATCH ist keine Kurzfrist-Steigungswahrschein-
lichkeit, sondern Halte-Qualität auf 12–18 Monate. BUY = längeres Halten ist
fundamental gedeckt (volle Größe, dem Daily-Signal mehr Raum geben). WATCH mit
starkem Breakout = reiner Momentum-Trade an kurzer Leine. Ob PASS-Titel die
VETO-Titel tatsächlich schlagen, misst das Signal-Journal (Abschnitt 7) — die
Schwellen sind kalibrierbar, nicht Dogma.

### Risiko-Staffel (max. Verlust je Trade, % des eingesetzten Kapitals)

Normalfall **10 %** Risiko auf das Invest je Trade; Skalierung nach Analyse-/EV-Lage.
Wird auf der Plattform als Spalte „Risiko" zwischen EV und Analyse angezeigt:

| Risiko | Bedingung |
|---|---|
| **0 %** (kein Trade) | Funnel-Entscheidung VETO oder Verdict AVOID |
| **5 %** (halb) | REDUCE · oder EV < −20 % (manuell wie Auto-Score) |
| **10 %** (normal) | Standard — auch ohne Analyse-/EV-Daten |
| **15 %** (erhöht) | PASS bzw. BUY **und** EV > +20 % (asymmetrischer Edge) — nur mit manueller Analyse, nie aus dem Auto-Score |

Verhältnis zu Abschnitt 3/4: Die Staffel ersetzt nicht den strukturbasierten
Stop (Abschnitt 3) — sie deckelt ihn. Liegt der Struktur-Stop weiter entfernt
als das Risiko-Budget, wird die Positionsgröße entsprechend reduziert
(Formel Abschnitt 4) oder der Trade ausgelassen.

---

## 7. Forward-Tracking (Signal-Journal) — die fehlende Feedback-Schleife

Neues `data/signal_journal.json`, automatisch gepflegt:

- **Jedes** Funnel-Signal wird geloggt (auch nicht gehandelte): Datum, Ticker,
  RS-Perzentil, Regime, Setup-Punkte, LLM-Entscheidung (PASS/REDUCE/VETO), Verdict-Score
- Automatische Nachmessung der Folgerendite nach 1/4/13/26 Wochen vs. Benchmark
- Quartalsauswertung beantwortet messbar:
  1. Schlagen PASS-Titel die VETO-Titel? (→ LLM-Beitrag positiv/negativ)
  2. Korreliert der Verdict-Score mit der Folgerendite? (→ Schwellen kalibrieren)
  3. Funktioniert die Regime-Ampel live? (Exposure vs. Marktphase)
- Nebenwirkung: genau der „nachgewiesene Signal-Track-Record", der laut
  PROJEKTPLAN.md der wichtigste Bewertungs-Multiplikator der Plattform ist.

---

## 8. Umsetzungs-Roadmap

### Phase A — Fundament — ✅ abgeschlossen (Juli 2026)
1. ✅ Regime-Ampel (Trend/Breite/Vola) — `backend/v2_analysis.py`, Anzeige in `frontend/v2.html`
2. ✅ RS 2.0 — vola-adjustierte gewichtete Fenster + Perzentil-Rang, alter Score läuft parallel als `score_v1`
3. ✅ Investierbarkeits-Filter im Funnel (`build_v2_payload()`), inkl. Ø-Dollar-Volumen 20T und Earnings-Sperre (fail-safe)
4. ✅ Volumen in OHLCV-Exporte aufgenommen (alle `*_colab*.py`) — greift ab dem nächsten Workflow-Lauf
5. ⚠️ Exit-Regelwerk (Abschnitt 3) ist schriftlich fixiert (in `v2.html` + hier) — **Anwendung im echten wikifolio noch nicht verankert** (offener Punkt 5 in `PROMPT_V2_UMSETZUNG.md` Phase C, braucht Rücksprache)

### Phase B — Backtesting 2.0 — teilweise abgeschlossen
6. ✅ Python-Portfolio-Engine (`backtest_v2/`) mit Regeln B1/B2/B6/B7/B8/B9/B10; Signal-Funktionen aus `backend/` wiederverwendet
7. ❌ Historische Indexmitgliedschaft (`data/index_history.json`) — offen, braucht Netzwerkzugriff
8. ❌ Kalibrierungslauf (Training bis 2021, Validierung 2022–2026) — **nicht möglich**, nur ~2 Jahre Historie im Repo verfügbar (siehe Datenbefund oben). Stattdessen: erster Validierungslauf auf dem verfügbaren Fenster durchgeführt, Ergebnis in `backtest_v2/results/README.md`
9. ✅ Ergebnisbericht nach B7 in `backtest_v2/results/` versioniert (vier Märkte, zwei Kostenvarianten je Markt)

### Phase C — Hybrid-Betrieb & Feedback — teilweise abgeschlossen
10. ✅ LLM-Veto-Format (PASS/REDUCE/VETO) in `analyses/PROMPT.md` + `generate_rating.py` integriert
11. ✅ `data/signal_journal.json` + `update_signal_journal.py` (automatische Folgerendite-Messung aus eigener OHLCV-Historie) — **läuft noch nicht automatisiert** (kein Workflow angelegt, siehe `PROMPT_V2_UMSETZUNG.md`)
12. ❌ Quartalsweise Kalibrierung — zu früh, Journal hat erst einen Tages-Snapshot
13. ❌ Datenupgrade (EODHD/Norgate) — nicht begonnen

### Definition of Done je Phase
- A: ✅ erreicht (Anwendung im wikifolio als einziger offener Teilpunkt)
- B: ⚠️ Engine + Kennzahlen stehen, aber OOS-Zeitraum inkl. 2022 und Sensitivitätsanalyse sind mangels Datentiefe noch offen
- C: LLM-Veto-Format + Signal-Journal-Infrastruktur stehen; erstes Quartals-Review erst möglich, sobald über Wochen/Monate Journal-Daten vorliegen

---

## 9. Offene Punkte / bewusste Nicht-Ziele

- **Kein Short/Inverse, keine Defensiv-Rotation** — Risk-Off = Cash (Nutzerentscheidung Juli 2026)
- Smallcap-Universum bleibt vorerst Screening-Quelle, wird aber erst nach
  Phase B in den Funnel aufgenommen (Liquiditäts-/Datenqualitätsrisiko)
- Intraday-Backtesting (4H) erst nach Datenupgrade sinnvoll erweiterbar
