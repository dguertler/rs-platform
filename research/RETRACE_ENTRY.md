# Studie 10/2026 — Einstieg erst nach 4H-Rücksetzer, mit 4H-Stopp

**Frage:** Weekly, Daily und 4H grün abwarten (Signal wie live), dann aber nicht sofort
kaufen, sondern erst nach einem Rücksetzer auf der 4H-Ebene, mit Stopp auf 4H-Ebene.

**Aufbau** (`research/retrace_entry_study.js`, gleiche Engine und gleiches Depot wie
B-ÜBERSICHT, NASDAQ-100 Top 20, 2016 – 10/2026, ohne Kosten):

- Signal unverändert (`simulateTradesPIT`): 4H springt auf grün, Woche und Tag zu diesem
  Zeitpunkt grün, Top 20 am Signaltag
- Rücksetzer-Regeln:
  - **pb X %**: ein 4H-Schluss liegt mind. X % unter dem höchsten Schluss seit dem Signal,
    danach schließt eine 4H-Kerze über dem Hoch der Vorkerze → Kauf zur nächsten 4H-Kerze
  - **Retest**: eine 4H-Kerze läuft bis auf 1 % an die gebrochene 4H-Marke zurück → Kauf zur nächsten 4H-Kerze
  - **Limit**: Limit-Kauf direkt auf der gebrochenen 4H-Marke
- Kaufzeitpunkt wie live: Kerzen 10–14/14–18 Uhr → nächste 4H-Kerze, spätere → 10 Uhr am nächsten Handelstag
- Stopp: tiefstes 4H-Tief seit dem Signal × 0,99, geprüft an jedem 4H-Schluss.
  Tagesstruktur-Ausstieg und Zeitstopp wie die Engine
- Abbruch: Schluss unter dem 4H-Swing-Tief zum Signalzeitpunkt, oder kein Rücksetzer
  innerhalb der Wartezeit (20/40/60 4H-Kerzen ≈ 5/10/15 Handelstage)

```bash
MODE=pb PB=2 WAIT=40 node research/retrace_entry_study.js    # MODE=now|touch|limit|pb, ~30 s
```

`MODE=now` (Sofortkauf, 4H-Stopp) trifft exakt den 4H-Stopp aus `STOP_LEVEL.md` (511.027 €).

## Ergebnis

| Einstieg | Warten | Trades Depot | Depot | CAGR | PF | Max-DD | Trefferq. | 2016–20 | 2021–25 | 2016–25 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Heute** (sofort, Tagesstopp) | – | 1013 | 464.413 € | 15,3 % | 1,91 | −30,4 % | 47,9 % | ×1,77 | ×1,31 | ×2,32 |
| Sofort, 4H-Stopp | – | 1071 | 511.027 € | 16,4 % | 2,04 | −31,2 % | 44,3 % | ×1,59 | ×1,56 | ×2,48 |
| pb 1 % | 40 | 963 | 566.791 € | 17,5 % | 2,09 | −25,1 % | 42,7 % | ×2,05 | ×1,40 | ×2,87 |
| pb 1,5 % | 40 | 917 | 528.537 € | 16,7 % | 2,11 | −27,5 % | 42,5 % | ×1,99 | ×1,34 | ×2,66 |
| pb 2 % | 20 | 718 | 551.155 € | 17,2 % | 2,35 | −27,7 % | 41,6 % | ×2,11 | ×1,33 | ×2,81 |
| pb 2 % | 30 | 818 | 512.434 € | 16,4 % | 2,11 | −29,8 % | 40,7 % | ×2,25 | ×1,11 | – |
| **pb 2 %** | **40** | 846 | **598.622 €** | **18,1 %** | 2,27 | −27,6 % | 41,6 % | ×2,29 | ×1,29 | ×2,96 |
| pb 2 % | 60 | 856 | 654.329 € | 19,1 % | 2,34 | −26,2 % | 42,0 % | ×2,48 | ×1,32 | – |
| pb 2,5 % | 40 | 778 | 513.898 € | 16,4 % | 2,19 | −23,6 % | 42,2 % | ×2,05 | ×1,26 | ×2,57 |
| pb 3 % | 40 | 702 | 410.757 € | 14,0 % | 1,99 | −26,9 % | 42,0 % | ×2,02 | ×1,29 | ×2,61 |
| pb 5 % | 40 | 396 | 238.498 € | 8,4 % | 1,89 | −24,6 % | 39,9 % | ×1,48 | ×1,06 | – |
| Retest 4H-Marke | 20 | 1157 | 490.476 € | 15,9 % | 1,90 | −26,9 % | 36,7 % | ×1,92 | ×1,30 | ×2,51 |
| Limit auf 4H-Marke | 40 | 1193 | 488.999 € | 15,9 % | 2,00 | −25,6 % | 32,6 % | ×1,74 | ×1,45 | ×2,52 |

## Bewertung

- **Leichter Rücksetzer (1–2,5 %) plus Wiederanstieg schlägt den Sofortkauf durchgängig.**
  CAGR 16,4–19,1 % statt 15,3 %, PF 2,1–2,4 statt 1,9, Drawdown 3–7 Pp. kleiner.
  2016–2025 (ohne das Ausnahmejahr 2026) ×2,57 bis ×2,96 statt ×2,32.
- **pb 3 % fällt nur durch 2026 ab:** Ohne 2026 liegt die Variante mit ×2,61 ebenfalls vor heute.
  Tiefere Rücksetzer (5 %) kommen zu selten vor, viele starke Titel laufen ohne Rücksetzer weg.
- **Das Plus kommt vor allem aus 2016–2020** (×2,0–2,5 statt ×1,77). In 2021–2025 liegen die
  Varianten etwa gleichauf mit heute (×1,1–1,4 statt ×1,31). Ein Vorteil, aber kein Selbstläufer.
- Retest und Limit auf der 4H-Marke: kleinerer Drawdown, aber kaum mehr Rendite. Der Stopp liegt
  sehr eng (Median 1,8–2,6 %), die Trefferquote fällt auf 33–37 %.
- Weniger Trades (rund 850 statt 1013) → mit Kosten verschiebt sich das Bild eher zugunsten des Rücksetzers.

## Variante Trendwechsel-Retracement (`MODE=tw`)

Nach dem Signal bildet sich auf 4H ein tieferes Tief (neue 4H-Marke, 4H-Punkt rot =
Trendwechsel). Kein 4H-Tief seit dem Signal darf unter dem Daily-Low des Bruchs liegen
(`DL=signal`: Tageskerze des Signaltags, `DL=breakout`: Tageskerze des Daily-Ausbruchs).
Kauf, wenn ein 4H-Schluss das letzte Hoch des Retracements (die neue 4H-Marke)
überwindet. Stopp: tiefstes 4H-Tief seit dem Signal × 0,99.

| Daily-Low | Warten | Signale | gekauft | abgebrochen (Daily-Low) | Depot | CAGR | PF | Max-DD | Trefferq. | Stopp (Median) | 2016–25 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Signaltag | 40 | 1874 | 245 | 1261 | 122.604 € | 1,9 % | 1,33 | −18,3 % | 50,0 % | 6,6 % | ×1,19 |
| Signaltag | 80 | 1645 | 408 | 1165 | 179.171 € | 5,6 % | 1,74 | −17,9 % | 51,2 % | 8,0 % | ×1,35 |
| Signaltag | 120 | 1609 | 442 | 1146 | 193.008 € | 6,3 % | 1,80 | −14,4 % | 50,5 % | 8,3 % | ×1,46 |
| Daily-Ausbruch | 40 | 1567 | 498 | 431 | 215.952 € | 7,4 % | 1,79 | −21,5 % | 51,6 % | 6,0 % | ×1,49 |
| Daily-Ausbruch | 80 | 1308 | 767 | 423 | 200.718 € | 6,7 % | 1,51 | −31,0 % | 49,8 % | 6,9 % | ×1,59 |
| Daily-Ausbruch | 120 | 1274 | 820 | 428 | 211.507 € | 7,2 % | 1,49 | −31,2 % | 49,5 % | 7,0 % | ×1,69 |

**Klar schlechter als heute (×2,32) und als pb 2 % (×2,96).** Mit dem Daily-Low des
Signaltags fallen rund drei Viertel der Signale weg, weil das tiefere 4H-Tief meist
darunter liegt. Die übrigen Käufe kommen spät (Median gut zwei Wochen nach dem Signal),
mit weitem Stopp (6–8 %) und schwächerem PF. Die Trefferquote steigt zwar auf rund 50 %,
die Gewinner fallen aber kleiner aus (Ø +8,6 bis +9,6 %).

**Kandidat:** pb 2 %, 40 Kerzen Wartezeit. Vor einer Umstellung offen:
- Robustheitslauf mit zufällig weggelassenen Signalen (wie in `README.md`)
- Prüfen, ob Weekly und Daily beim Kauf noch grün sein müssen
- Live-Umsetzung: offene Signale über Tage nachhalten und an jedem 4H-Schluss prüfen,
  auch den Stopp der offenen Positionen
