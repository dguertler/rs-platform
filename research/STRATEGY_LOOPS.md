# Strategie-Loops 10/2026 — Ziel: den Nasdaq schlagen

**Auftrag des Nutzers:** in Loops mit den vier Analysten-Rollen so lange Rahmenbedingungen und
Annahmen ändern, bis eine Variante **PF ≥ 3** erreicht **und den Nasdaq-100 schlägt**. Wird
das Ziel nicht erreicht, gilt die bisher beste Variante.

**Analysten-Rollen:** Breakout-Praktiker, Risk-Manager, Makro-Stratege, Quant-Skeptiker
(Schiedsrichter).

## Ergebnis in einem Satz

Das Ziel wurde in 4 Loops und rund 220 getesteten Varianten **nur auf den Daten 2016–2026
erreicht, auf denen gesucht wurde**. Außerhalb davon (2008–2015) scheiterten alle Kandidatinnen.
Die ehrlich beste Variante ist **R4B**. Sie liegt im Backtest bei etwa QQQ + 6–9 Punkten p. a.
Realistisch zu erwarten ist aber eher **QQQ ± 3 Punkte**.

## Prüfstand

`research/loop_harness.py` baut auf der Depot-Simulation aus `trading_approaches.py` auf:
- NDX-Universum, RS-Top-20 point-in-time, 4H-Signale der Live-Logik
- 10 Plätze, Kosten je Seite
- Robustheit: 30 Läufe mit je 20 % zufällig weggelassenen Signalen

QQQ Buy & Hold als Maßstab (CAGR / MaxDD):

| Zeitraum | CAGR | MaxDD |
|---|---|---|
| 2008–15 | 11,6 % | – |
| 2016–21 | 25,0 % | −29 % |
| 2022–26 | 14,7 % | −35 % |
| 2016–26 | 20,4 % | −35 % |

Die heutige Plattform (Breakout-Depot mit vollen Plätzen) erreicht 15,1 % p. a. bei PF 1,81.

## Loops

| Loop | Geänderte Rahmenbedingung | Bestes Ergebnis | Erkenntnis |
|---|---|---|---|
| 1 | Je Agent ein Hebel: Einstieg/Auswahl, Ausstieg/Pyramide, Kapitalrahmen/Regime, alternative Ansätze (Rotation) | **V17 (Praktiker):** Frühausstieg Tag 2, nur Basen ≥ 12 % tief, Klimax- und Spätbasis-Sperre, freies Cash in QQQ. 26,2 / 33,1 % p. a., PF 4,75, robust 80 / 100 % → Ziel formal erreicht | Tag 2 ist der Basisbaustein, Basentiefe der stärkste PF-Hebel. Der Engpass liegt immer in 2016–21. Hebel > 1 erreicht das Ziel nur über das QQQ-Beta (DD −47 … −58 %). |
| 2 | Pflichtkennzahlen: PF gleichgewichtet, Deflated Sharpe, PF-Intervall, Satellit allein, 60 Läufe, Nachbarschwellen. Bausteine kombinieren. | S3 (= V17) bestätigt (Plateau, 83 % robust). W8 (zusätzlich größere Plätze, Thermometer, Pyramide) erreicht 28,9 / 45,3 %, PF 5,27 | Thermometer, Top-20 und Pyramide machen das Plateau zur Spitze. Deflated Sharpe 0,4–0,6 (Rauschen). In 2016–21 trägt der QQQ-Anteil von rund 76 % das Ergebnis. |
| 3 | Kandidatinnen eingefroren, unabhängige Tests: Nullmodell, fester Kern, Kosten 0,25 %, spätere Ausführung, 2008–15, zweiter Signaltyp | Nur 2016–26 mit RSI(2) auf freien Plätzen (98–100 % robust) | Zufallsauswahl im selben Rahmen erreicht das Ziel in 25–36 % der Fälle. Bei 0,25 % Kosten fallen S3 und W8 durch. In 2008–15 liegen beide klar unter QQQ (PF 1,3–1,5). |
| 4 | Finale mit festem Abschlusstor: **G1** Ziel bei 0,25 % Kosten, **G2** 2008–15 > QQQ und PF ≥ 3, **G3** ≥ 90. Perzentil im Nullmodell | **R4B** besteht G1 und G3, scheitert an G2 | Keine Kandidatin besteht G2. Die Breakout-Logik erreicht vor 2016 nur PF 1,1–1,8. |

### Abschlusstor (Loop 4, unabhängig vom Quant nachgerechnet, 0,25 % Kosten)

| Kandidatin | Idee | G1 (2016–26) | G2 (2008–15) | G3 (Nullmodell) |
|---|---|---|---|---|
| **R4B** | S3 + Stoppweite ≥ 4 % + QQQ-Umschichtung monatlich + Zeitstopp nach 15 Tagen | **ja:** 26,8 / 32,8 %, PF 5,02 [1,67–10,3], robust 90 / 100 % | nein: 9,3 %, PF 1,54 | **ja:** Perzentil 98 / 99,6 |
| R4A | wie R4B, Zeitstopp nach 10 Tagen | ja: 26,0 / 33,1 %, PF 5,21, robust 73 / 100 % | nein: 8,1 %, PF 1,21 | ja: 93 / 99 |
| P4 | höchstens 3 Satelliten-Plätze, nur 1./2. Basis nach ≥ 15 % Korrektur | knapp: 25,2 / 26,5 %, robust 73 / 97 % | nein: 9,7 %, PF 1,38 | nein: 73 / 98 |
| M4 | Satellit nur bei kaltem Markt, sonst 100 % QQQ | nein: 20,2 / 16,4 %, PF 2,20 | nein: 4,7 %, PF 1,09 | nein: 30 / 95 |

## Die beste Variante: R4B

**Code:** `research/loops/r4b.py`. Die Prüfung aller drei Tore liegt in
`python3 research/loops/r4b_gates.py` (dauert mehrere Minuten). `r4b_gates.py check` gleicht die
Referenz ab.

Die Regeln:

1. **Signal:** 4H-Breakout der Live-Logik (3 von 3 Punkten), Titel in den RS-Top-20.
2. **Nur Ausbrüche aus einer echten Basis:** tiefste Korrektur in den 126 Tagen davor
   mindestens 12 %.
3. **Keine Klimax-Woche:** Das letzte Wochen-Swing-Hoch liegt höchstens 12,7 % über dem vorherigen.
4. **Keine späte Basis:** Die 3. oder spätere Basis seit Trendbeginn wird gesperrt.
5. **Stoppweite mindestens 4 %.**
6. **Ausstieg wie die Engine** (Stopp, Strukturbruch), dazu:
   - **Frühausstieg**, wenn der Schluss an Tag 2 unter dem Einstieg liegt,
   - **Zeitstopp** nach 15 Handelstagen, wenn der Kurs dann unter +5 % liegt.
7. **Freies Kapital liegt im QQQ.** Es wird monatlich umgeschichtet. Käufe werden zuerst aus Cash
   bezahlt.

**Was man von R4B ehrlich erwarten kann:**
- **Rendite im Backtest:** 2016–26 29,5 % p. a. gegenüber 20,4 % für QQQ. Ohne 2026 sind es
  22,5 % gegenüber 19,7 %. Der Vorsprung stammt vor allem aus 2020, 2025 und 2026. QQQ wird in
  6 von 11 Jahren geschlagen.
- **Out-of-Sample:** In 2008–15 (Tagesnäherung) lag R4B 2–3 Punkte unter QQQ. Ein Minderertrag
  ist damit ebenso plausibel wie ein Mehrertrag.
- **Risiko:** MaxDD −37 %, also wie QQQ.
- **Satellit allein:** 15–17 % p. a., unter QQQ. Der größte Teil der Rendite kommt aus dem
  QQQ-Anteil.
- **PF:** Im Backtest liegt er bei rund 5, das Intervall reicht bis 1,7 hinunter. Realistisch sind
  eher 1,5–3.
- **Statistik:** Deflated Sharpe 0,30 bei N ≈ 220. Ein echter Vorsprung ist statistisch nicht
  belegt.

## Was robust gelernt wurde

- **Frühausstieg an Tag 2:** in allen Loops der wirksamste Einzelbaustein (+5 Punkte CAGR in
  beiden Zeiträumen).
- **Freies Cash im QQQ:** macht aus dem Breakout-Depot erst eine Chance auf den Index. Ohne QQQ-Anteil
  schlägt in 2016–21 keine Breakout-Variante den Nasdaq.
- **Basentiefe, Klimax- und Spätbasis-Sperre:** heben den Trade-PF auf über 4. Der Effekt
  besteht im Nullmodell 2022–26, aber nicht in 2016–21 und nicht vor 2016.
- **Was nicht trägt:**
  - Hebel bringt nur QQQ-Beta mit einem Drawdown von −47 bis −58 %.
  - Ein fester QQQ-Kern kostet 2016–21.
  - Kalter-Markt-Regel, Momentum-Rotation und Pyramide: Die Rotation verfehlt PF ≥ 3, kalter
    Markt und Pyramide sind nicht robust.
  - Ein zweiter Signaltyp hilft nur in Seitwärtsjahren, nicht in Bärenmärkten.
- **Kosten:** Jede 0,1 % Kosten je Seite kosten rund 1–2 Punkte p. a. Monatliche
  QQQ-Umschichtung senkt die Kostenlast von 2,8 auf 2,0 % p. a.

## Empfehlung

1. **Das Ziel als nicht robust erreicht werten.** R4B nicht als „schlägt den Nasdaq“ vermarkten,
   sondern als Nasdaq-Anlage mit einem disziplinierten Breakout-Satelliten.
2. **R4B ab jetzt mit eingefrorenen Parametern vorwärts mitschreiben,** zum Beispiel im
   Signal-Journal. Das ist der einzige verbleibende unabhängige Test. Ohne neue Daten würde jede
   weitere Variante die Zahl der Tests erhöhen und die Aussagekraft weiter senken.
3. **Für die Live-Logik unabhängig davon übernehmen:** Frühausstieg Tag 2 und Klimax-Sperre (siehe
   `TRADE_PATTERNS.md`). Sie verbessern Sharpe und Drawdown in allen Prüfungen.

## Korrektur 10/2026 (nach den Loops)

Der Prüfstand buchte die QQQ-Rendite des freien Cash für den ganzen Tag (Schluss → Schluss), bevor
zur Eröffnung gehandelt wurde. Ein kleiner Vorgriff, gefunden vom Quant-Skeptiker in den
Price-Action-Loops. Korrigiert in `trading_approaches.simulate` und `loops/r4b.py`: Übernacht-Anteil
vor dem Handel, Tagesanteil danach. Die Strategien mit tradeweiser Umschichtung verlieren dadurch
bis zu 3 Punkte p. a. R4B ist wegen der monatlichen Umschichtung kaum betroffen: 26,4 / 33,2 / 29,5 %
statt 26,8 / 32,8 / 29,5 % (2016–21 / 2022–26 / 2016–26, 0,25 % Kosten). Damit liegt R4B 2016–21
weiter über QQQ (25,0 %). Die Werte aus Loop 1–3 mit „Cash in QQQ“ sind entsprechend etwas zu hoch.

## Grenzen

- **Keine 4H-Kerzen vor 2016.** Der Out-of-Sample-Test nutzt eine Tagesnäherung des Signals, die
  in 2016–26 rund 30 % gleiche Trades hat.
- **Datenlücken vor 2016.** 83 Index-Titel haben keine Kursdatei, 19 weitere erst ab 2016. Diese
  Überlebensverzerrung begünstigt die Strategie, trotzdem scheiterte sie dort.
- **Steuern, Wechselkurs und wikifolio-Gebühren sind nicht enthalten.**
- **Die Agenten-Skripte der Zwischenschritte lagen im Arbeitsverzeichnis.** Ins Repo übernommen
  sind der Prüfstand, die finale Kandidatin R4B und die Bausteine dafür (`research/loops/`).
