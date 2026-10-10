# Studie 10/2026 — Was haben Gewinner- und Verlierer-Trades gemeinsam?

Untersucht wurden alle Trades der 4H-Breakout-Logik: 1.318 Backtest-Trades 2016 bis 10/2026
(`data/backtest_ndx.json`) und 199 verschickte Live-Alerts seit 04/2026
(`data/live_alerts_performance.json`). Für jeden Trade wurde die Lage zum Einstieg
berechnet, und zwar nur aus Kursen vor dem Einstiegstag:

- Abstand zum Allzeithoch, laufende Korrektur, Basen
- Trend, Überdehnung, Volatilität
- Marktlage (QQQ)
- Verlauf nach dem Einstieg

Die Befunde wurden von vier unabhängigen Analysten-Rollen geprüft und in zwei Runden
diskutiert: Breakout-Praktiker, Quant-Skeptiker, Risk-Manager und Makro-Stratege.

```bash
python3 research/trade_patterns.py          # Merkmalstabellen → research/data/trade_features*.csv
python3 research/trade_patterns_depot.py    # Depot-Test der Verbesserungen (~10 Min., --runs 0 = schnell)
```

**Prüfregel:** Ein Muster gilt nur, wenn es in **beiden** Zeiträumen (2016–21 und 2022–26)
in dieselbe Richtung zeigt und live nicht widerspricht. Viele Muster sehen nur wegen
einzelner Ausreißer stark aus. Deshalb zählen zusätzlich der Median, der PF ohne die Top 1 %
und die Zahl der Jahre, in denen der Effekt in dieselbe Richtung geht.

## Kurzfassung

1. **Kein Merkmal teilen alle Gewinner oder alle Verlierer.** In jedem Merkmalsbereich liegt
   die Trefferquote bei 43–54 %. Die Strategie lebt von wenigen Ausreißern:
   - Die besten 1 % der Trades liefern 73 % des Gewinns.
   - Ohne die besten 5 % läge der PF bei 0,65.
2. **These „Die besten Trades brechen auf ein Allzeithoch aus“: widerlegt.** Große Gewinner
   (über +20 %) lagen beim Einstieg im Median 9,5 % unter dem Allzeithoch und 98 Tage nach
   dessen Datum. Nur 13 % starteten auf einem Allzeithoch. Gemeinsam ist ihnen, dass sie das
   Allzeithoch *während* des Trades holen (90 %). Am Einstieg lässt sich das nicht erkennen.
3. **These „Verlierer sind nur Teil einer laufenden Korrektur“: in dieser Form widerlegt.**
   - Weder eine laufende Korrektur der Aktie noch eine des Marktes macht Trades schlechter.
     Einstiege in einen korrigierenden Markt gehören 2022–26 sogar zu den besten.
   - Verlierer haben das *Gegenteil* gemeinsam: Sie werden **am Ende einer gestreckten
     Bewegung** gekauft, also bei Klimax-Wochenhoch, späterer Basis oder überhitztem Markt.
   - Und sie **scheitern sofort**: 69 % der großen Verlierer schließen am zweiten Tag unter
     dem Einstieg, bei den großen Gewinnern sind es 10 %.
4. **Volatilität spreizt beide Enden.** Hohe ATR, weiter Stopp und tiefe Basis bringen mehr
   große Gewinner *und* mehr große Verlierer. In R gerechnet ist der Effekt neutral, also
   kein Filter, aber auch kein Grund für kleinere Positionen.
5. **Robusteste Verbesserungen im Depot:**
   - **Frühausstieg bei Schluss an Tag 2 unter Einstieg**
   - **Klimax-Sperre**
   - **halbe Position bei überhitztem Markt**

   Zusammen steigt der Sharpe von 0,56 auf 1,00 (2016–21) und von 0,82 auf 1,08 (2022–26).
   Der maximale Rückgang sinkt von −24 auf −18 %. Die CAGR 2022–26 bleibt etwa gleich.

## 1. Gewinner und Verlierer im Überblick (Backtest, abgeschlossen)

| Klasse | n | Ø | Ausstieg | Median MFE / MAE | Haltedauer (Median) | neues Allzeithoch im Trade |
|---|---|---|---|---|---|---|
| großer Verlust < −5 % | 272 | −8,6 % | 83 % Stopp | +1,9 / −9,6 % | 8 Tage | 39 % |
| kleiner Verlust | 420 | −2,3 % | 66 % Zeitstopp | +2,4 / −4,7 % | 11 Tage | 50 % |
| kleiner Gewinn < 5 % | 445 | +2,2 % | 91 % Zeitstopp | +4,6 / −2,3 % | 11 Tage | 63 % |
| Gewinn 5–20 % | 107 | +10,4 % | 99 % Strukturbruch | +19 / −2,0 % | 38 Tage | 74 % |
| großer Gewinn > +20 % | 68 | +63 % | 100 % Strukturbruch | +59 / −2,7 % | 90 Tage | 90 % |

MFE und MAE sind die größte günstige und die größte ungünstige Kursbewegung während des Trades.

Merkmale vor dem Einstieg, jeweils Median:

| Merkmal | großer Verlust | großer Gewinn |
|---|---|---|
| Abstand zum Allzeithoch | −4,0 % | −9,5 % |
| Tage seit Allzeithoch | 22 | 98 |
| Tiefe der Korrektur (126 Tage) | −7,5 % | −11,3 % |
| ATR 14 Tage | 2,9 % | 3,2 % |
| Stoppweite | 6,7 % | 8,8 % |
| Abstand zum 50-Tage-Schnitt | +9,7 % | +10,3 % |

Die Unterschiede sind klein und überlappen stark. Die Gewinner kommen aus tieferen und
älteren Basen und sind volatiler. Viele Verlierer sind das ebenfalls.

## 2. These „Ausbruch auf ein Allzeithoch“

Fünftel nach Abstand zum Allzeithoch beim Einstieg (PF je Zeitraum):

| Abstand zum Allzeithoch | n | Trefferquote | Ø | PF 2016–21 | PF 2022–26 |
|---|---|---|---|---|---|
| < −16,6 % | 263 | 47 % | +7,2 % | 2,08 | 4,39 |
| −16,6 bis −4,7 % | 262 | 45 % | +1,5 % | 1,67 | 1,46 |
| −4,7 bis −1,4 % | 263 | 46 % | +1,6 % | 1,41 | 1,97 |
| −1,4 bis 0 % | 264 | 50 % | +0,1 % | 1,35 | 0,66 |
| **auf dem Allzeithoch** | 260 | 49 % | +1,4 % | 2,17 | **0,76** |

- Einstiege direkt am Allzeithoch waren nur 2016–21 gut. Nach 2022 lag ihr PF unter 1.
  Insgesamt waren sie nur in 4 von 11 Jahren besser als der Rest. Live gibt es keinen Unterschied.
- Das gute oberste Fünftel („weit unter dem Allzeithoch“) ist **größtenteils ein
  Volatilitätseffekt**:
  - Abstand zum Allzeithoch und ATR hängen zusammen (ρ −0,39).
  - Der Median dieser Gruppe ist schlechter als der des Rests.
  - Live liegt der PF der Gruppe bei 0,34.
- Aus Sicht des Breakout-Praktikers ist die Frage falsch gestellt. Entscheidend ist, **ob vor
  dem Ausbruch eine echte Basis lag**, nicht wie nah der Kurs am Allzeithoch steht:
  - Einstiege am Allzeithoch ohne Basis (höchstens 5 Tage seit dem Hoch, Korrektur unter 6 %)
    brachten 2022–26 keinen einzigen Trade über +20 %.
  - Der Vorteil tiefer Basen (Korrektur ≤ −20 %) bleibt nur bei volatilen Titeln bestehen
    (oberes ATR-Drittel) und dort auch nur 2022–26 und live.

## 3. These „Verlierer sind nur Teil einer Korrektur“

**Korrektur der Aktie.** Geprüft wurden die Tiefe der letzten Korrektur, wie viel davon schon
zurückgeholt war und die Wochenstruktur mit tieferen Hochs.

- Alle Rangkorrelationen mit dem Ergebnis in R liegen unter |0,04|, die Vorzeichen wechseln zwischen den Zeiträumen.
- Eine bearishe Wochenstruktur ist bei großen Gewinnern sogar häufiger (34 %) als bei großen Verlierern (23 %).

**Korrektur des Marktes (QQQ)**, PF je Gruppe:

| Einstieg, während … | 2016–21 | 2022–26 | live |
|---|---|---|---|
| der Markt korrigiert, ohne bestätigten Boden | 1,49 | **4,55** | 0,47 (n = 10) |
| ≤ 25 Tage nach dem ersten Boden-Signal (Follow-through-Day) | 1,20 | 0,68 | 2,09 (n = 11) |
| der Markt schon stark gelaufen ist (QQQ 63 Tage > +11 %) | 1,21 | **0,85** | **0,33** (n = 98) |
| der Markt 63 Tage im Minus liegt | 3,51 | 2,52 | 3,22 (n = 8) |

Die These stimmt also, aber mit umgekehrtem Vorzeichen. Schlechte Trades stammen nicht aus
der Korrektur. Sie entstehen **spät in der Erholung bzw. Rally**, wenn der Markt schon weit
gelaufen ist.

## 4. Was Verlierer tatsächlich gemeinsam haben

**a) Sie scheitern sofort.** Median-Schluss gegenüber dem Einstieg (2016–21 / 2022–26 / live):

| | Tag 1 | Tag 2 | Schluss Tag 2 unter Einstieg |
|---|---|---|---|
| großer Verlust | −0,5 / −0,8 / −1,9 % | −1,2 / −1,8 / −2,4 % | 69 % |
| großer Gewinn | +1,6 / +2,0 / +1,8 % | +2,1 / +3,3 / +4,9 % | 10 % |

- 52 % der großen Verlierer steigen nie mehr als 2 % über den Einstieg.
- Trotzdem halten sie im Median 8 Tage, bis der Stopp greift. Der Verlust entsteht durch
  langsames Ausbluten, nicht durch Kurslücken.
- Fehlausbrüche kommen in allen Marktphasen ähnlich oft vor (38–59 %). Das Merkmal ist also
  **kein versteckter Marktfilter**.

**b) Sie werden am Ende einer gestreckten Bewegung gekauft.**
- Gemeint ist ein letztes Wochen-Swing-Hoch mehr als 12,7 % über dem vorherigen (Klimax-Woche).
- Diese Trades waren in 10 von 11 Jahren schlechter als der Rest.
- Das gilt für jede Schwelle zwischen 6 und 20 %.
- PF 0,97 (2016–21), 1,15 (2022–26), 0,44 live, gegenüber 2,23 beim Rest.
- Verwandt damit sind eine 6-Monats-Rendite im oberen Fünftel, mehr als 32 % Abstand zum
  200-Tage-Schnitt und ein Ausbruch aus der dritten oder späteren Basis. Diese Merkmale messen
  denselben Faktor „schon gelaufen“ und bringen über die Klimax-Woche hinaus nichts Belastbares.

**c) Sie werden in einem heißen Markt gekauft.** Klimax und heißer Markt überschneiden sich kaum
(φ = 0,11–0,29) und **ergänzen sich**. PF (n):

| Klimax-Woche | Markt heiß (QQQ 63 Tage > 11 %) | 2016–21 | 2022–26 | live |
|---|---|---|---|---|
| nein | nein | **2,13** (505) | **3,06** (371) | **1,74** (57) |
| nein | ja | 1,35 (98) | 0,72 (82) | 0,36 (52) |
| ja | nein | 1,02 (104) | 1,29 (81) | 0,99 (13) |
| ja | ja | 0,85 (39) | 1,18 (38) | 0,30 (46) |

Das schwache Live-Ergebnis (PF 0,78 bei den geschlossenen Trades) geht etwa zu zwei Dritteln
auf die überhitzte Marktphase Mai bis Juli 2026 zurück und zu einem Drittel auf Klimax-Titel.
Hinzu kommt das breitere Live-Universum: SPX-Titel im heißen Markt erreichten PF 0,18.

## 5. Was Gewinner gemeinsam haben

- **Sofortiges Mitziehen:** Tag 1 und Tag 2 schließen fast immer über dem Einstieg.
- **Sie wackeln später trotzdem:** 46 % der großen Gewinner fallen zwischenzeitlich mehr als
  3 % unter den Einstieg (Median-MAE −2,8 %). Deshalb schneiden Einstandsstopps oder enge
  Trailing-Stopps sie ab, wie schon in der Vorstudie (`README.md`).
- **Weiter Stopp und hohe Volatilität:** Die Stoppweite liegt im Median bei 8,8 %, bei großen
  Verlierern bei 6,7 %. Eine Positionsgröße nach Stoppweite oder ATR schadet daher im Depot:
  CAGR 13,3 bzw. 18,6 % statt 23,7 % (2022–26).
- **Erholungsausbruch statt Ausbruch auf ein Allzeithoch:** Ausbrüche aus tiefen und alten
  Basen, die erst im Trade das Allzeithoch holen.
- **Kein Klimax und kein überhitzter Markt:** In dieser Gruppe ist die Strategie in allen drei
  Stichproben klar profitabel.

## 6. Diskussion der vier Analysten

| Thema | Praktiker | Quant | Risk-Manager | Makro | Ergebnis |
|---|---|---|---|---|---|
| ATH-Ausbruch | falsche Frage, Basis zählt | Rauschen | am Einstieg nicht erkennbar | Allzeithoch des Markts ist gefährlicher als das der Aktie | verworfen |
| Tiefe Basen bevorzugen | ja, nur bei hoher ATR | Volatilitätseffekt | Depot: +2 Pkt. 2016–21, aber höherer Rückgang, 2022–26 neutral | – | nur beobachten |
| Klimax-Sperre | ja, Lehrbuch (O'Neil: späte Basen scheitern) | robustester Einzelfilter | Rendite 2022–26 nur in 4 von 30 Läufen besser, Drawdown in 30 von 30 | ein Drittel der Live-Schwäche | **umsetzen** |
| Markt heiß (QQQ 63 T. > 11 %) | ergänzt Klimax | als Größenregel, nicht als Sperre (Kante bei 8 %) | Sperre glänzt nur 2022–26 | halbe Position | **halbe Position** |
| Frühausstieg Tag 2 | richtige Übersetzung der O'Neil-Regel; Variante mit Pivot schneidet Ausreißer | wirkt vor allem über frei werdende Plätze, scharfer Parameter | bester Einzelbaustein | kein Marktfilter; schadet, wenn QQQ 63 Tage im Minus | **umsetzen**, Nachbarvarianten prüfen |
| Pause nach Stopp-Häufung, QQQ unter 50-Tage-Schnitt, Kaufstopp in Marktkorrektur | – | – | – | schadet in beiden Zeiträumen | verworfen |

Die offenen Streitpunkte:

- **Frühausstieg.** Der Quant-Skeptiker hält „Tag 2 / 0 %“ für eine Spitze im Parameterraum:
  Tag 1 und Tag 3 bringen je Trade kaum etwas, Tag 5 schadet. Der Risk-Manager hält dagegen,
  dass im Depot auch „Tag 2 < −1 %“ und „Tag 1 < 0 %“ ähnlich gut sind. Die Nachbarvarianten
  in Abschnitt 7 klären das: Die Schwelle ist unkritisch, der Tag nicht. Tag 3 verliert den
  größten Teil des Vorteils.
- **Klimax-Sperre und Ausreißer.** Die Sperre schneidet 2022–26 neun große Gewinner ab, unter
  anderem ARM +92 %, META +63 % und INTC +50 %. Bei einer Strategie, die von ihren Ausreißern
  lebt, ist das ein ernstes Gegenargument. Mit dem Frühausstieg werden die Klimax-Trades
  deutlich besser (PF 0,97 → 1,04 / 1,26 → 1,64 / live 1,15 → 1,58). Kommt der Frühausstieg,
  bremst die Sperre deshalb vor allem den Drawdown.

## 7. Verbesserungen im Depot-Test

Grundlage: 10 Plätze, Platzgröße wie in der Engine, ohne Kosten. Simuliert wurde mit dem
Nachbau der Engine in `trade_patterns_depot.py`; er trifft 1.317 Trades exakt.
„> Basis“ zählt, in wie vielen der 30 Läufe (je 20 % der Signale fallen zufällig weg) die
Variante die Basis bei CAGR / Sharpe / MaxDD schlägt.

| Variante | 2016–21 CAGR | Sharpe | MaxDD | PF | 2022–26 CAGR | Sharpe | MaxDD | PF |
|---|---|---|---|---|---|---|---|---|
| B Basis (heute) | 11,2 % | 0,56 | −24,5 % | 1,48 | 23,7 % | 0,82 | −24,2 % | 2,32 |
| E Frühausstieg Tag 2 (Schluss < Einstieg) | 15,9 % | 0,80 | −21,8 % | 1,74 | 26,4 % | 0,93 | −22,8 % | 2,77 |
| E2−1 Tag 2 Schluss < Einstieg −1 % | 15,2 % | 0,74 | −21,8 % | 1,66 | 27,1 % | 0,96 | −22,0 % | 2,80 |
| E3 Frühausstieg Tag 3 | 13,0 % | 0,65 | −21,9 % | 1,57 | 24,0 % | 0,84 | −24,3 % | 2,53 |
| K Klimax-Sperre | 13,0 % | 0,68 | −21,3 % | 1,63 | 24,0 % | 0,91 | −20,6 % | 2,47 |
| K½ Klimax halbe Position | 11,1 % | 0,60 | −23,4 % | 1,50 | 23,0 % | 0,85 | −22,7 % | 2,37 |
| Q½ Markt heiß halbe Position | 10,9 % | 0,60 | −20,5 % | 1,50 | 24,9 % | 0,88 | −24,1 % | 2,49 |
| E+K | 17,4 % | 0,92 | −20,9 % | 1,96 | 26,1 % | 1,03 | −19,0 % | 3,06 |
| E + K½ + Q½ | 16,4 % | 0,93 | −18,5 % | 1,92 | 25,9 % | 1,00 | −20,4 % | 3,04 |
| **E + K + Q½ (Empfehlung)** | **17,4 %** | **1,00** | **−17,8 %** | 2,08 | **26,2 %** | **1,08** | **−18,4 %** | **3,27** |

Robustheit: In wie vielen der 30 Läufe schlägt die Variante die Basis bei CAGR / Sharpe / MaxDD?

| Variante | 2016–21 | 2022–26 |
|---|---|---|
| E Frühausstieg Tag 2 | 30 / 30 / 27 | 20 / 24 / 29 |
| E2−1 Tag 2 < −1 % | 30 / 30 / 29 | 19 / 24 / 29 |
| E3 Frühausstieg Tag 3 | 15 / 18 / 27 | 5 / 9 / 23 |
| K Klimax-Sperre | 18 / 28 / 27 | 6 / 28 / 30 |
| K½ Klimax halbe Position | 10 / 30 / 27 | 5 / 29 / 30 |
| Q½ Markt heiß halbe Position | 11 / 30 / 30 | 25 / 30 / 18 |
| E+K | 30 / 30 / 30 | 10 / 30 / 30 |
| E + K½ + Q½ | 30 / 30 / 30 | 18 / 29 / 30 |
| **E + K + Q½** | **30 / 30 / 30** | 13 / **30 / 30** |

Lesart:
- **Frühausstieg (E):** Tag 2 ist robust, auch mit Schwelle −1 %. Tag 3 ist deutlich schwächer.
  Die Regel muss früh greifen. Die Warnung des Quant-Skeptikers vor einer Parameterspitze gilt
  also für den Tag, nicht für die Schwelle.
- **Klimax-Sperre (K) und halbe Position bei heißem Markt (Q½):** Beide verbessern Sharpe und
  Drawdown fast immer, die CAGR aber nicht verlässlich.
- **Gesamtpaket E + K + Q½:** Es verbessert Sharpe und Drawdown in 60 von 60 Läufen. Die CAGR
  2022–26 liegt im Median etwa auf dem Niveau der Basis (13 von 30 Läufen besser).

## 8. Empfehlung

| # | Maßnahme | Wirkung | Risiko der Überanpassung | Ort |
|---|---|---|---|---|
| 1 | **Frühausstieg:** Schluss am 2. Handelstag nach dem Einstieg unter dem Einstiegskurs → Verkauf zur nächsten Eröffnung | Sharpe und Drawdown in beiden Zeiträumen besser; Kapital wird ~18 % früher frei | gering bis mittel (Schwelle 0 / −1 % gleich gut, Tag 3 deutlich schwächer) | `isExitDay` in `frontend/backtest_logic.js`, Verkaufsmeldung in `check_exits.py` |
| 2 | **Markt-Thermometer:** QQQ 63 Tage > +11 % → neue Positionen nur zur Hälfte | weniger Drawdown in beiden Zeiträumen, Rendite 2016–21 neutral | mittel (wenige unabhängige Phasen) | Breakout-Mail und `live_depot.json` (Hinweis „halbe Position“) |
| 3 | **Klimax-Sperre:** letztes Wochen-Swing-Hoch > 12,7 % über dem vorherigen → kein Kauf (alternativ halbe Position) | stärkste Drawdown-Bremse; mit #1 kaum Renditeverlust | mittel (kostet einzelne Ausreißer) | Signalprüfung in `check_alerts.py` / `check_alerts_4h.py` und `simulateTradesPIT` |
| 4 | Im Signal-Journal mitschreiben: Klimax, Markt heiß, Schluss Tag 2 | Vorwärtstest mit echten Daten, bevor #2/#3 hart werden | – | `update_signal_journal.py` |

Nur beobachten: Tiefe Basen bei vollem Depot vorziehen (nur bei hoher ATR, Effekt 2016–21 reine
Volatilität).

**Nicht umsetzen:**
- Filter auf Einstiege am Allzeithoch
- Kaufstopp in einer Marktkorrektur oder unter dem 50- bzw. 200-Tage-Schnitt
- Pause nach mehreren Stopps
- Positionsgröße nach ATR oder Stoppweite
- Einstands- und Trailing-Stopps
- multivariate Scoring-Modelle (Test-Korrelation 0,04, reine Überanpassung)

## Grenzen

- Die Live-Trades stammen fast alle aus einer einzigen Marktphase (04–10/2026). Etwa die Hälfte
  sind SPX-Titel, für die nur Kurse ab 10/2022 vorliegen. 31 Live-Trades sind noch offen.
- Die Depot-Rechnung enthält keine Kosten. Der Frühausstieg erzeugt rund 10 % mehr Trades. Bei
  0,1 % je Seite kostet das grob 0,2–0,3 Punkte p. a. und ändert die Rangfolge nicht.
- Die Ausstiegsgründe in `trade_features.csv` sind eine Näherung. Die Depot-Rechnung nutzt den
  exakten Nachbau.
- Alle Effekte vor dem Einstieg sind klein (|ρ| ≤ 0,1). Die Rendite hängt an rund 1 % der
  Trades. Jede neue Regel sollte daher nur die linke Seite der Verteilung beschneiden und nach
  der Umsetzung im Signal-Journal weiter beobachtet werden.
