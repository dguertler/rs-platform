# Backtest 2.0 — Ergebnisse (erster Validierungslauf)

**Stand:** 03.07.2026 · Engine-Version: erster funktionsfähiger Stand nach Bugfix
(siehe unten). Rohdaten je Markt: `{market}_{datum}.json` in diesem Verzeichnis.

## Wichtigste Erkenntnis: In diesem Zeitraum unterliegt die Strategie Buy-and-Hold

| Markt | Zeitraum | Strategie (0,1% Kosten) | Buy&Hold Benchmark | Alpha | 200d-Regel | Max-DD Strategie | Sharpe |
|---|---|---|---|---|---|---|---|
| Nasdaq-100 | 2024-06 – 2026-07 | +22,8% | +55,6% | **−32,8pp** | +41,5% | 14,7% | 0,82 |
| S&P 500 | 2024-07 – 2026-07 | +2,9% | +35,2% | **−32,3pp** | +16,2% | 15,9% | 0,17 |
| DAX-40 | 2024-07 – 2026-07 | +9,6% | +39,2% | **−29,6pp** | +25,6% | 4,0% | 0,83 |
| Smallcap SC600 | 2024-07 – 2026-07 | −4,4% | +37,9% | **−42,3pp** | +8,2% | 18,9% | −0,04 |

In allen vier Märkten liegt die Strategie deutlich hinter Buy-and-Hold — und in
drei von vier Fällen auch hinter der trivialen "Nur bei Close > 200d-Linie
investiert"-Regel. Das ist **kein gutes Ergebnis für die Strategie**, aber ein
ehrliches: dieser Befund wird hier unverändert berichtet, nicht wegkalibriert.

## Warum das plausibel ist — und warum es (noch) keine Verwerfung der Strategie ist

1. **Der Testzeitraum enthält keinen echten Bärenmarkt.** Das Regime war laut
   Aufschlüsselung überwiegend "unknown" (SMA200 noch nicht verfügbar, s.u.)
   oder "green"/"yellow"; "red" kam nur kurz vor. Das System ist explizit dafür
   gebaut, in **Korrekturen** Kapital zu schützen (Exposure-Drosselung, Stops,
   Trailing) — dieser Vorteil kann sich in einem fast durchgehenden
   Aufwärtsmarkt gar nicht zeigen. Stattdessen kostet er in einer solchen Phase
   Rendite (Cash-Drag, Teilverkäufe bei +2R kappen Gewinner, die einfach
   weitergelaufen wären).
2. **SMA200-Anlaufzeit frisst ~35–40 % des verfügbaren Fensters.** Mit nur
   ~2 Jahren Historie steht die Regime-Ampel für die ersten ~40 Wochen auf
   "unknown" (SMA200 braucht 200 Handelstage Vorlauf) — das ist fast die
   Hälfte des Testzeitraums ohne funktionierende Regime-Steuerung.
3. **Kleine Stichprobe.** 54–223 Trades je Markt über nur ~2 Jahre — zu wenig,
   um von einer statistisch belastbaren Aussage zu sprechen (Regel B5 fordert
   deshalb explizit eine Sensitivitätsanalyse, die hier noch aussteht).
4. **Exposure 76–93 %**, nie 100 % — ein Teil der Differenz ist reiner
   Cash-Drag in einem Markt, der fast nur steigt.

**Das ändert nichts an der Kernaussage:** Diese Zahlen sind reale
Backtest-Ergebnisse, keine Kalibrierungs-Vorlage. Ob das System langfristig
sein Ziel erfüllt (risikoadjustierte Outperformance + stabiler Track-Record),
lässt sich erst mit einem Testfenster beurteilen, das einen echten Bärenmarkt
enthält (z. B. 2022) — genau das, was Regel B4 verlangt und in dieser Umgebung
mangels Netzwerkzugriff nicht nachladbar war.

## Ein echter Engine-Bug wurde im Zuge dieses Laufs gefunden und behoben

Der erste Testlauf zeigte für S&P 500 ein Alpha von −64 %. Untersuchung ergab:
Die Positionsgrößen-Berechnung beim Entry verwendete versehentlich den
**Benchmark**-Schlusskurs (QQQ) statt des Schlusskurses der jeweiligen Aktie
zur Berechnung des Portfolio-Werts (`equity_now`) — dadurch griff die
15 %-Gewichtungsgrenze nicht korrekt, einzelne Positionen erreichten bis zu
54 % des Portfolios (z. B. TER). Nach dem Fix (`backtest_v2/engine.py`,
Funktion `bar_close()` konsequent statt der fehlerhaften `date_idx`-Variable
verwendet) sank der Max-Drawdown im S&P-500-Lauf von 33,9 % auf 15,9 % und
die Ergebnisse wurden über alle vier Märkte hinweg konsistent plausibel.
Alle oben gezeigten Zahlen sind bereits die **korrigierten** Werte.

## Bekannte Einschränkungen dieses Laufs (siehe auch `engine.py`-Docstring)

| Regel | Status | Grund |
|---|---|---|
| B1 Kein Look-Ahead | ✅ umgesetzt | Swing-Punkte erst nach Bestätigung nutzbar, Entry zum Open des Folgetags |
| B2 Kosten | ✅ umgesetzt | 0,1 % und 0,2 % je Seite parallel gerechnet |
| B3 Survivorship-frei | ❌ offen | Aktuelles Universum rückwirkend gehandelt — Survivorship-Bias bleibt bestehen |
| B4 Out-of-Sample 2016–2021/2022–2026 | ❌ nicht möglich | Nur ~2 Jahre synchronisierte Historie im Repo, kein Netzwerkzugriff zum Nachladen in dieser Umgebung |
| B5 Sensitivitätsanalyse ±30 % | ❌ offen | Folgt, sobald längere Historie verfügbar ist (sonst nicht aussagekräftig) |
| B6 Portfolio-Ebene | ✅ umgesetzt | Positionslimits, Sektor-Caps, Cash-Quote, Regime-Budget |
| B7 Kennzahlen-Pflicht | ✅ umgesetzt | CAGR, Sharpe, Calmar, Max-DD, DD-Dauer, Exposure, Profit-Factor — je Regime |
| B8 Benchmark-Fairness | ✅ umgesetzt | Vergleich vs. Buy&Hold und vs. simple 200d-Regel |
| B9 Kein 4H im Walk | ✅ dokumentierte Einschränkung | Markt-JSONs halten nur 60-Tage-Rolling-Window an 4H-Daten — Entry verlangt hier Weekly+Daily (2/2) statt 3/3 |
| B10 Eine Quelle der Wahrheit | ✅ umgesetzt | `backtest_v2/signals.py` importiert `gws_analysis.struct_daily/struct_weekly` und `v2_analysis`-Funktionen direkt, keine Duplikate |

## Nächste Schritte (siehe PROMPT_V2_UMSETZUNG.md)

1. Sobald Netzwerkzugriff oder eine bezahlte Datenquelle verfügbar ist: längere
   Historie laden (mind. 2016–2026), damit B4/B5 tatsächlich durchführbar sind
   und ein echter Bärenmarkt (2022) im Test enthalten ist.
2. Historische Indexmitgliedschaft (B3) rekonstruieren, um Survivorship-Bias
   zu beseitigen.
3. Erst nach 1+2: Parameter-Kalibrierung (RS2-Fenstergewichte, Regime-Schwellen,
   ATR-Faktor, Zeit-Stopp) mit Sensitivitätsanalyse — nicht vorher, sonst
   Overfitting auf ein zu kurzes, nicht-repräsentatives Fenster.
