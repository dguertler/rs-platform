# Studie 10/2026 — Stopp auf Tages- oder 4H-Ebene?

**Ausgangslage:** Der Einstieg kommt über die 4H-Kerze, der Stopp aber schon heute
von der **Tageskerze**: letztes Swing-Tief der Tageskerzen vor dem Einstieg × 0,99,
geprüft zum Tagesschluss, Verkauf zur nächsten Eröffnung (`recentSwingLowOf` /
`isExitDay` in `frontend/backtest_logic.js`, live `swing_low_stop` in `check_exits.py`).

**Verglichen:** Stoppkurs (Tages- oder 4H-Swing-Tief) × Prüfung (Tagesschluss oder
jeder 4H-Schluss, Verkauf zur nächsten 4H-Kerze). Alles andere bleibt gleich:
zeitpunktgenauer Einstieg (`simulateTradesPIT`), Ausstieg über die Tagesstruktur,
Zeitstopp, Positionsgröße, Depot (100.000 €, 10 Plätze, Zinseszins, ohne Kosten).

```bash
SL_LEVEL=h4 SL_CHECK=h4 node research/stop_level_study.js   # d|h4 je Schalter, ~30 s
```

Die Variante `d`/`d` ergibt exakt `data/backtest_ndx.json` (464.413 €).

## Ergebnis NASDAQ-100, Top 20, 2016 – 10/2026

| Stoppkurs | Prüfung | Depot | CAGR | PF Depot | Max-DD | Trefferquote | Ø Verlust | Stoppabstand (Median) | 2016–20 | 2021–25 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Tag (heute)** | Tag | 464.413 € | 15,3 % | 1,91 | −30,4 % | 47,9 % | −4,8 % | 5,6 % | ×1,77 | ×1,31 |
| Tag | 4H | 462.731 € | 15,3 % | 1,89 | −30,9 % | 46,5 % | −4,7 % | 5,6 % | ×1,84 | ×1,28 |
| 4H | Tag | 462.796 € | 15,3 % | 1,92 | −31,2 % | 46,0 % | −4,6 % | 4,3 % | ×1,69 | ×1,34 |
| 4H | 4H | 511.027 € | 16,4 % | 2,04 | −31,2 % | 44,3 % | −4,3 % | 4,3 % | ×1,59 | ×1,56 |

## Bewertung

- Halbe Umstellungen (nur Kurs oder nur Prüfung auf 4H) bringen nichts.
- Der volle 4H-Stopp liegt über den ganzen Zeitraum vorn (+1,1 Pp. p. a.), aber
  **nicht stabil**: 2016–2020 klar schlechter (×1,59 statt ×1,77), 2021–2025 klar
  besser (×1,56 statt ×1,31). Das Plus stammt fast ganz aus 2024–2026.
- Engerer Stopp → mehr Ausstiege nach höchstens 3 Tagen (143 statt 44) und eine
  niedrigere Trefferquote. Der Drawdown wird nicht kleiner.
- Live bräuchte der 4H-Stopp eine Prüfung an jedem 4H-Schluss für alle offenen
  Positionen. Heute prüft der Nachtlauf (`check_exits.py`) nur Tageskerzen.

**Empfehlung:** Tagesstopp beibehalten. Das Plus des 4H-Stopps hängt am Zeitraum,
und er bringt mehr Fehlausstiege bei gleichem Drawdown.
