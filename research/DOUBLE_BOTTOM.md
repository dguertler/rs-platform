# Studie 10/2026 — Kauf am Doppelboden: Wann stimmt der Einstieg?

## Frage

Gekauft werden soll unabhängig von den GWS-Ausbrüchen, sobald ein Doppelboden steht, also
wenn die Verkäufer den Kurs nicht weiter drücken können. Welche Bedingungen müssen dafür
erfüllt sein, damit die Trefferquote Richtung 60 % steigt? Die Ausstiege der Engine bleiben
vorerst unverändert: Stopp, Strukturbruch und Zeitstopp (Tag 10 unter +5 %).

## Daten

`research/double_bottom.py` durchsucht alle Tageskurse seit 2016 nach Doppelböden, ohne
Vorgriff. Die Ergebnisse stehen in `research/data/double_bottom.csv` (37.289 Trades).

- **NDX:** 182 Nasdaq-100-Titel einschließlich ausgeschiedener, 2016–2026
- **SPX:** die übrigen S&P-Titel, Kurse erst ab 10/2022. Diese Gruppe dient als echte
  Out-of-Sample-Stichprobe für 2023–26.

## Definition

| Baustein | Regel |
|---|---|
| Tief 1 / Tief 2 | Tages-Swing-Tiefs (±2 Tage), 8–80 Handelstage auseinander, höchstens ±5 % Abweichung, dazwischen kein tieferes Tief |
| Vorlauf | Hoch der 60 Tage vor Tief 1 mindestens 8 % darüber |
| Nackenlinie | höchstes Hoch zwischen den Tiefs, mindestens 4 % über Tief 1 |
| Auslöser „früh“ | Tief 2 bestätigt (2 Tage ohne neues Tief), Kauf zur nächsten Eröffnung |
| Auslöser „Nacken“ | erster Schluss über der Nackenlinie (höchstens 40 Tage nach Tief 2), Kauf zur nächsten Eröffnung |
| Stopp | tieferes Tief × 0,99 |

Wie bei den Breakouts haben vier Analysten-Rollen die Daten unabhängig ausgewertet und in zwei
Runden diskutiert: Breakout-Praktiker, Quant-Skeptiker, Risk-Manager, Makro-Stratege.
Zeiträume: **N1** = NDX 2016–21 (Training), **N2** = NDX 2022–26, **SPX** = 2023–26 (Test).

## Kurzfassung

1. **Mit den Engine-Ausstiegen liegen realistisch 45–55 % drin, nicht 60 %.**
   - Basis: 36–48 % Trefferquote.
   - Der Grund ist der Strukturausstieg. Ein Doppelboden entsteht in einer Abwärtsstruktur, das
     GWS-D-Hoch ist noch nicht überwunden. Der Strukturausstieg greift deshalb schon beim ersten
     Schluss unter dem jüngsten Swing-Tief.
   - Hält man dieselben Einstiege starr 20 Tage, steigt die Trefferquote auf 52–62 %. Die
     Einstiege sind also besser, als die Engine-Quote zeigt.
2. **Die rund 60 % kommen vom Ausstieg, nicht vom Einstieg.**
   - Mit Ziel bei 1R über dem Einstieg und Stopp unter dem Doppeltief erreicht die Regel
     „Kauf über der Nackenlinie + QQQ über der 200-Tage-Linie“ **61 / 57 / 62 %**, ohne
     optimierte Schwellen.
   - Der Preis: Die Ausreißer werden gekappt. Der PF liegt bei 1,35–1,62.
3. **Freie Suche nach Filtern ist eine Falle.** Unter rund 10.000 Filterkombinationen gibt es
   viele mit 60 % im Training. Im Test kommen sie nur auf 30–48 %. Belastbar sind wenige,
   grobe Bedingungen.
4. **Im Breakout-Depot schadet der Doppelboden eher.** Auf freien Plätzen verdrängt er
   2022–26 die großen Breakout-Ausreißer. Mit Makro-Filter verdrängt er nichts mehr, bringt
   aber auch keinen belastbaren Mehrwert (10–18 von 30 Läufen besser). Allein läuft er nur
   bei 2–10 % CAGR.

## 1. Welche Annahmen stimmen?

| Annahme | Befund (N1 / N2 / SPX) | Urteil |
|---|---|---|
| Doppelboden als **Rücksetzer im Aufwärtstrend** (Aktie über SMA200, nahe Allzeithoch) | Nacken über SMA200: PF 1,55 / 1,35 / 1,63, darunter 1,22 / 0,81 / 1,13. Aktie mindestens 40 % unter dem Allzeithoch: Treffer 7–13 Punkte niedriger | **stimmt** |
| **Reifes W**: Abstand der Tiefs mindestens 15–20 Tage | Treffer +2 bis +9 Punkte, PF 2,12 / 1,87 / 1,62 gegenüber 1,50 / 1,08 / 1,22 | **stimmt** |
| **Shakeout**: Tief 2 kurz unter Tief 1 (Spring nach Wyckoff) | hebt im Trend den PF (ohne Top 1 %: 1,47 / 1,20 / 1,67 gegenüber 1,08 / 0,90 / 1,07) und den Anteil über +5 %; die Trefferquote kaum | **Qualitätsmerkmal**, kein Hebel für die Trefferquote |
| **Exakt gleiche Tiefs** (±1 %) als „perfektes W“ | schlechteste Gruppe: PF 1,78 / 1,05 / 0,84 | **falsch**: Stopps sammeln sich an einer Stelle |
| **Umkehrkerze** an Tief 2 (Schluss oben, grüne Kerze) | neutral bis schädlich | **falsch** |
| **RSI-Divergenz** zwischen den Tiefs | schadet beim Nacken-Auslöser in allen drei Stichproben | **falsch** |
| **Tiefer Absturz** davor („Verkäufer erschöpft“) | Vorlauf über 35 %: in N2 PF 0,5–0,8 | **falsch**: flache Konsolidierungen sind besser |
| **Markt korrigiert** (QQQ 8–20 % unter dem Hoch) | 2016–21 der beste Filter (Nacken 59 %), 2022 aber Totalausfall (PF 0,29); nicht ohne Vorgriff von einem Bärenmarkt-Beginn zu trennen | **regimeabhängig**, nicht als Kernregel |
| **QQQ über SMA200** | mit 1R-Ziel die einzige stabile Marktbedingung (siehe 3.) | **stimmt** |
| **Markt-Boden bestätigt** (FTD, QQQ über SMA50) | schadet oder neutral; die ersten 25 Tage nach dem FTD sind schwach | **falsch** |
| **QQQ-Doppelboden** als eigenes Signal | 3–6 Signale pro Jahr, 2022 ein Friedhof | **kein Handelssignal** |

## 2. Auslöser und Stopp

Trefferquote (N1 / N2 / SPX):

| Auslöser | Engine-Ausstieg | 20 Tage halten, ohne Stopp | Ziel 1R |
|---|---|---|---|
| früh (Tief 2 bestätigt) | 46 / 36 / 41 % | 61 / 53 / 55 % | 60 / 50 / 54 % |
| 10 Tage über Tief 2 halten | 48 / 41 / 45 % | 59 / 52 / 55 % | 61 / 52 / 56 % |
| Schluss über dem Hoch der Tief-2-Kerze | 48 / 39 / 43 % | 60 / 52 / 55 % | 60 / 50 / 53 % |
| **Schluss über der Nackenlinie** | 48 / 41 / 47 % | 55 / 50 / 52 % | 59 / 52 / 54 % |
| Retest der Nackenlinie | 49 / 41 / 47 % | 56 / 51 / 53 % | 59 / 53 / 55 % |

- **Ohne Filter liegen die Auslöser nah beieinander.** Mit Trend- und Marktfilter gewinnt die
  **Nackenlinie** deutlich. Mit Regel A des Praktikers erreicht sie 52 / 52 / 55 % gegenüber
  48 / 44 / 46 % bei „10 Tage halten“. Mit 1R-Ziel ist sie die einzige Variante mit PF über 1,25
  in allen drei Stichproben. Der Grund: Ihr weiterer Stopp ergibt ein weiteres Ziel, im Median
  +9,5 % Gewinn statt +5 %.
- **Nachteil der Nackenlinie:** Der Stopp liegt im Median 12–17 % entfernt. Die Positionsgröße
  sollte sich daher nach der Stoppweite richten.
- **Stopp unter Tief 2 statt unter dem Doppeltief:** Mit Engine-Ausstieg ist das egal, nur 5 %
  der Trades enden am Stopp. Mit 1R-Ziel ist das Doppeltief leicht besser. Ein Stopp nach ATR
  schadet (PF 0,92–1,07).

## 3. Die besten Regelsätze

| Regel | Ausstieg | Treffer N1 / N2 / SPX | PF | Median | Trades pro Jahr (NDX) | Risiko Überanpassung |
|---|---|---|---|---|---|---|
| **R1** Nacken + QQQ über SMA200 | **1R-Ziel**, Stopp unter Doppeltief | **60,6 / 57,1 / 61,5 %** | 1,56 / 1,35 / 1,62 | +9,6 / +9,5 / +9,6 % | 60–120 | gering (Schwellen vorab fest) |
| R2 = R1 + Aktie höchstens 15 % unter Allzeithoch, Tiefs mindestens 15 Tage auseinander | 1R | 62,8 / 51,0 / 58,6 % | 1,69 / 1,03 / 1,56 | | 90–180 | gering |
| **R3** Nacken + Tiefs mindestens 15 Tage auseinander + Shakeout (über 1 %) + Aktie über SMA200 | Engine | 52,4 / 51,5 / 55,1 % | **1,92 / 1,97 / 1,90** | +0,4 / +0,2 / +0,5 % | ~60 | gering (Plateau) |
| R3 + QQQ 8–20 % unter dem Hoch | Engine | 66,0 / 56,4 / 59,2 % | 4,19 / 2,41 / 4,83 | | 9–19 | mittel (wenige Trades, 2022) |
| früh + Makro-Filter, Strukturausstieg erst ab Tag 10 | Engine (angepasst) | 58,1 / 51,7 / 53,1 % | 2,41 / 1,70 / 2,08 | | 30–60 | mittel |

Trefferquote je Jahr für R1:

| 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|
| 72 % | 72 % | 54 % | 58 % | 63 % | 47 % | 29 % (n = 7) | 62 % | 63 % | 59 % | 56 % |

Bärenmärkte wie 2022 lassen sich mit keinem Marktfilter vorab erkennen. Im Januar 2022 lag
QQQ noch über der SMA200. Die Bedingung „QQQ nicht tiefer als −20 %“ greift erst, wenn es
zu spät ist.

## 4. Was ein Trader am Chart prüfen muss

1. **Rücksetzer im Aufwärtstrend, keine Wende.** Die Aktie liegt über der steigenden
   200-Tage-Linie und nahe ihrem Hoch (höchstens 15 % darunter). Der Gesamtmarkt (QQQ) liegt
   über seiner 200-Tage-Linie.
2. **Ein reifes W.** Zwischen den Tiefs liegen mindestens 3 Wochen. Die Nackenlinie liegt
   deutlich (rund 10 %) über Tief 1. Kein Absturz um mehr als 35 % davor.
3. **Tief 2 darf Tief 1 kurz unterschreiten** (Shakeout um 1–5 %) und wird zurückerobert.
   Keine exakt gleichen Tiefs. Nicht auf Umkehrkerze oder RSI-Divergenz warten.
4. **Kauf beim Schluss über der Nackenlinie.** Stopp unter dem Doppeltief, Positionsgröße nach
   der Stoppweite.

## 5. Empfehlung

| # | Option | Wirkung | Bewertung |
|---|---|---|---|
| 1 | **Ziel 60 % Trefferquote:** R1 als **eigenes, getrenntes Signal** mit eigenem Ausstieg (1R-Ziel, Stopp unter Doppeltief), nicht im Breakout-Depot | ~60 % Treffer, PF ~1,5, Median-Gewinner ~+9,5 % | geringes Risiko der Überanpassung, aber hohes Regimerisiko (2022) |
| 2 | **Engine-Ausstiege behalten:** R3 als Signal, Strukturausstieg für Doppelboden-Trades erst ab Tag 10 | 52–58 % Treffer, PF ~1,9 | +4 Punkte ohne PF-Verlust, nur ein Eingriff |
| 3 | Doppelböden auf freien Plätzen im Breakout-Depot | 2022–26 verdrängt er die Ausreißer (CAGR 23,7 → 4,5 %); mit Makro-Filter nur Münzwurf | **nicht umsetzen** |
| 4 | QQQ-Doppelboden, FTD- oder SMA50-Filter, Umkehrkerze, RSI-Divergenz | – | **nicht umsetzen** |

Nächster Schritt: R1 und R3 als Signaltyp „Doppelboden“ ins Signal-Journal schreiben
(`update_signal_journal.py`) und einige Monate vorwärts beobachten, bevor Mails oder das Depot
darauf reagieren.

## Grenzen

- Keine Volumendaten. Klassische Doppelboden-Kriterien wie sinkendes Volumen an Tief 2 und
  steigendes am Ausbruch fehlen.
- SPX-Titel haben erst ab 10/2022 Kurse. „Allzeithoch“ heißt dort Hoch seit 10/2022, und die
  Prüfung über der 200-Tage-Linie greift erst ab Mitte 2023.
- Keine Kosten eingerechnet. Das 1R-Ziel erzeugt mehr Trades, bei 0,1 % je Seite kostet das
  grob 0,2 Punkte je Trade.
- Bei Ziel und Stopp am selben Tag wird der Stopp zuerst gezählt (vorsichtig).
- Die Varianten der Agenten (zusätzliche Auslöser, 1R-Ausstieg, Depot-Lauf) wurden mit Kopien
  von `double_bottom.py` gerechnet. Im Repo liegt nur der Basis-Scan. Vor einer Umsetzung ist
  R1/R3 als festes Skript nachzuziehen.
