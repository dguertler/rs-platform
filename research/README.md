# Studie 10/2026 — Welche Handelsansätze verbessern die Plattform?

Verglichen werden die heutige Breakout-Logik, Varianten davon und alternative
Swing- und Trendansätze. Alle laufen auf denselben Daten und in derselben
Depot-Simulation.

- **Universum:** NASDAQ-100, nur Titel, die am jeweiligen Tag in den Top 20 standen (point-in-time,
  `data/backtest_history/charts`, 182 Titel inkl. ausgeschiedener)
- **Depot:** 100.000 € Start, höchstens 10 Positionen, Zinseszins, **0,1 % Kosten je Seite**
- **Kein Vorgriff:** Signale nur mit Kursen bis zum Signalzeitpunkt. Tagesansätze kaufen zur
  nächsten Eröffnung, die 4H-Signale wie live zur nächsten 4H-Kerze
- **Zeiträume:** 2016–2021 (Training) und 2022–2026 (Test, mit Bärenmarkt 2022). Die Tagesansätze
  laufen zusätzlich 2008–2015 (4H-Kerzen gibt es erst ab 2016)
- **Robustheit:** 30 Läufe, in denen jeweils 20 % der 4H-Signale zufällig wegfallen (in allen
  Varianten dieselben). Jede Variante wird Lauf für Lauf gegen A2 verglichen

```bash
node research/export_signals.js          # alle 4H-Signale der Live-Logik → research/data/signals_4h.json (~1 Min.)
python3 research/trading_approaches.py   # Studie → research/results/trading_approaches.json + Tabellen
```

**Abgleich mit der heutigen Engine:** A1 bildet die heutige Plattform nach. Ohne Kosten
ergibt das 15,1 % p. a., `data/backtest_ndx.json` zeigt 15,3 %. Die Simulation trifft
die Engine also. Der Unterschied zu den 13,0 % unten sind die Kosten.

## Ergebnis 2016–2026 (Auszug)

| Ansatz | CAGR | Max-DD | Sharpe | PF | Trades | Investiert |
|---|---|---|---|---|---|---|
| QQQ Buy & Hold | 20,4 % | −35,1 % | 0,95 | – | – | 100 % |
| QQQ 200-Tage-Timing | 15,9 % | −23,5 % | 0,98 | – | – | – |
| **A1 Plattform heute** (1 % Risiko je Trade) | 13,0 % | −30,6 % | 0,66 | 1,68 | 1064 | 76 % |
| A2 wie A1, volle 10-%-Plätze | 15,1 % | −32,8 % | 0,72 | 1,81 | 1052 | 78 % |
| B1 A2 + Käufe nur bei QQQ über der 200-Tage-Linie | 11,4 % | −27,7 % | 0,60 | 1,63 | 892 | 68 % |
| C5 Ausstieg: Stopp + Schluss unter der 50-Tage-Linie | 16,2 % | −30,8 % | 0,80 | 1,83 | 699 | 82 % |
| C15 Ausstieg: Einstand ab +2R, Zeitstopp, 20 % unter Hoch | 18,6 % | −38,4 % | 0,86 | 2,02 | 667 | 88 % |
| **F1 A2 + RSI(2)-Pullbacks auf freien Plätzen** | **19,7 %** | −36,6 % | **0,84** | 1,97 | 1525 | 83 % |
| D4 Momentum-Rotation 12-1 Monate (wöchentlich) | 20,1 % | −36,1 % | 0,84 | 1,75 | 1111 | 78 % |
| D5 Pullback-Swing RSI(2) < 10 (allein) | 10,6 % | **−11,9 %** | 0,87 | 1,79 | 1274 | 18 % |
| D6 Donchian-50-Breakout + 3×ATR-Trailing | 13,1 % | −28,5 % | 0,69 | 1,62 | 662 | 76 % |
| 50 % QQQ + 50 % D5 (monatlich ausgeglichen) | 16,1 % | −21,7 % | **1,09** | – | – | – |
| 50 % QQQ + 50 % F1 | 20,7 % | −34,5 % | 0,98 | – | – | – |

Alle 36 Varianten, alle Zeiträume und die Jahreswerte stehen in `results/trading_approaches.json`.
Die Tabellen gibt das Skript aus.

## Robustheit — was hält in beiden Zeiträumen?

Median aus 30 Läufen. „besser als A2“ heißt: In so vielen der 30 Läufe hat die
Variante eine höhere CAGR als A2 mit denselben Signalen.

| Variante | 2016–21 CAGR | besser als A2 | 2022–26 CAGR | besser als A2 | Urteil |
|---|---|---|---|---|---|
| A1 heute (1 % Risiko) | 9,8 % | 23 % | 19,9 % | 17 % | volle Plätze sind besser |
| A2 volle Plätze | 10,1 % | – | 22,7 % | – | Referenz |
| B1 200-Tage-Filter | 8,2 % | 7 % | 19,6 % | 10 % | **schadet in beiden Zeiträumen** |
| C5 Schluss < 50-Tage-Linie | 15,5 % | 97 % | 16,1 % | 0 % | kippt im Test |
| C13 Zeitstopp + 20 % unter Hoch | 21,5 % | 100 % | 16,8 % | 3 % | kippt im Test |
| C16 20 % unter Hoch | 19,6 % | 100 % | 6,6 % | 0 % | kippt im Test |
| **F1 + RSI(2)-Pullbacks** | 13,9 % | **100 %** | 25,8 % | **87 %** | **robust besser** |

## Befunde

1. **Ohne 2026 schlägt die heutige Logik den Index nicht.** 2016–2025 erreicht A1
   7,5 % p. a., QQQ 19,7 %. Ein großer Teil der Rendite stammt aus 2026
   (A1 +82 %, QQQ +23 %). In 8 von 10 Jahren bis 2025 lag die Strategie hinter
   QQQ (vorn nur 2016 und 2022). Ein Jahr wie 2026 kann sich wiederholen, darf aber nicht die Grundlage der
   Bewertung sein.
2. **Positionsgröße: volle Plätze statt 1 % Risiko je Trade.** Die Risikobremse
   kauft bei weitem Stopp weniger Stück. Damit liegen im Schnitt nur 76 % des
   Depots im Markt. Volle 10-%-Plätze bringen etwa +2 Prozentpunkte p. a. Das gilt in
   beiden Zeiträumen und in 77–83 % der Läufe. Der maximale Rückgang steigt nur um
   etwa 2 Punkte.
3. **Der 200-Tage-Filter für Käufe schadet.** Er hilft 2022 (−11 % statt −22 %),
   verpasst aber die Erholungen 2016, 2019 und 2025. In beiden Zeiträumen ist er in
   über 90 % der Läufe schlechter. Die geplante Regime-Ampel aus `STRATEGIEPLAN.md`
   (Stufe 0) sollte darum **nicht als Kaufsperre** an den 4H-Breakout gehängt werden.
4. **Weitere Ausstiege sind überangepasst.** Trailing-Stops (20 % unter Hoch,
   Chandelier 5×ATR, 50-Tage-Linie) verdoppeln 2016–2021 die Rendite. 2022–2026 sind
   sie in fast allen Läufen schlechter. Der heutige Ausstieg (Strukturbruch und
   Zeitstopp) bleibt. C1 ohne Strukturbruch hält Gewinner praktisch ewig: 39 % p. a.,
   aber −54 % Rückgang bei nur 100 Trades. Das ist ein konzentriertes Buy & Hold,
   keine Swing-Strategie.
5. **Ein Pullback-Swing (RSI-2) auf den freien Plätzen ist die einzige robuste
   Verbesserung.** Gekauft wird ein Top-20-Titel über seiner 200-Tage-Linie, dessen
   RSI(2) unter 10 fällt. Verkauft wird, sobald der Schluss über der 5-Tage-Linie
   liegt, spätestens nach 10 Tagen. Ein Trade dauert im Schnitt 4 Tage. Breakouts
   haben Vorrang. Ergebnis: +4,6 Punkte p. a. (2016–2025: +2,0 Punkte), besser in
   beiden Zeiträumen. Der Pullback-Swing allein funktioniert auch 2008–2015
   (Sharpe 0,91, Rückgang −15 %). Der Preis: etwa 4 Punkte mehr maximaler Rückgang
   und rund 45 % mehr Trades.
6. **Kosten sind ein großer Hebel.** Jede 0,1 % Kosten je Seite kosten die heutige
   Logik etwa 2 Punkte p. a. Bei 0,25 % (realistisch mit Spread im wikifolio)
   bleiben von 15,1 % nur 9,9 %. Mit F1 bleiben 15,0 %. Limit-Orders zur Eröffnung
   und weniger Fehlausbrüche wirken direkt auf die Rendite.
7. **Momentum-Rotation ist kein Ersatz.** Sie ist 2016–2021 stark (bis 31 % p. a.),
   fällt 2022–2026 aber um bis zu −40 % und bleibt unter dem Breakout. Die
   12-1-Variante ist die stabilste und hat auch 2008–2015 die höchste Rendite der Tagesansätze.
   Sie taugt als Vergleichsmaßstab, nicht als Hauptstrategie.
8. **Core-Satellite mit QQQ verbessert das Risikoprofil am stärksten.** Die
   Strategien sind mit QQQ nur mäßig korreliert (Breakout 0,66, RSI-2 0,38).
   50 % QQQ + 50 % Pullback-Swing erreicht Sharpe 1,09 bei −21,7 % Rückgang. Das ist
   der beste risikobereinigte Wert der Studie, auch besser als QQQ allein.

## Empfehlung (nach Priorität)

| # | Maßnahme | erwarteter Effekt | Aufwand |
|---|---|---|---|
| 1 | Positionsgröße auf volle Plätze (10 % je Titel), Risiko-Staffel nur noch als Dämpfer (REDUCE/VETO) | +2 Pkt. p. a., robust | klein: `portfolio.js`, `live_depot.json`-Logik |
| 2 | RSI(2)-Pullback als zweiter Signaltyp nur für freie Plätze, im Nachtlauf (`check_alerts.py`) mit eigener Mail-Kennzeichnung | +2 bis +4,6 Pkt. p. a., robust | mittel |
| 3 | Kein 200-Tage-Kaufstopp; Regime-Ampel nur als Anzeige bzw. für Position-Sizing testen | vermeidet −3,7 Pkt. p. a. | keine Umsetzung |
| 4 | Ausstieg unverändert lassen; neue Ausstiegsideen nur mit Test 2022–2026 übernehmen | vermeidet Überanpassung | – |
| 5 | Ausführung kostenbewusst (Limit zur Eröffnung, keine Market-Orders im Spread) | je 0,1 % gespart ≈ +2 Pkt. p. a. | klein |
| 6 | Produktseitig ein Core-Satellite-Depot (z. B. 50 % Nasdaq-ETF + Signale) als Variante zeigen | Sharpe 0,98–1,09 statt 0,72 | klein (nur Darstellung) |

## Grenzen

- Das Universum enthält nur Titel, die in der rekonstruierten Rangliste in die Top 20
  kamen. Ausgeschiedene Titel vor 2016 fehlen teilweise. Die Werte für 2008–2015 sind
  darum nur ein grober Plausibilitätscheck.
- 2026 ist ein Ausreißerjahr (Speicher-/KI-Rally). Jede Kennzahl über 2016–2026 wird
  stark davon geprägt. Die Spalte 2016–2025 im Text zeigt die Werte ohne 2026.
- Steuern, Wechselkurs und wikifolio-Gebühren sind nicht enthalten. Kosten gibt es
  nur pauschal je Seite (Sensitivität 0 / 0,1 / 0,25 %).
- Der RSI(2)-Ansatz wurde nicht optimiert, es gelten die Lehrbuchwerte (Connors).
  Vor einer Umsetzung sollte er noch einmal mit festen Parametern auf den neu
  hinzukommenden Daten laufen (Forward-Test über das Signal-Journal).
