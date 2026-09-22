# Earnings-Daten (Dritter Post-Typ: Earnings-Analyse)

Eine JSON pro Earnings-Post: `<TICKER>.json` (z. B. `CNC.json`).
Claude befüllt die Beat-Zahlen **aus dem Web** (IR/Pressemitteilung, SEC-8-K,
Finanzportale), da yfinance in der Cloud meist geblockt ist. Der **Kurssprung**
und der Reaktions-Chart werden NICHT hier eingetragen — sie werden zur Laufzeit
live aus `data/rs_*.json` über `report_date` berechnet.

Vollständiges Schema + Workflow: `instagram/PROMPT.md`, Abschnitt
„Dritter Post-Typ: EARNINGS-ANALYSE".

Pflichtfelder: `ticker`, `quarter`, `report_date`, `source`
(`QQQ`/`SPX`), `eps_actual`, `eps_estimate`, `eps_surprise_pct`.

Schnelltest der Datenschicht (zeigt Kurssprung + geladene Basis-Analyse):
```bash
python3 -m instagram.earnings CNC
```

Generieren:
```bash
python3 -m instagram.generate --earnings CNC --headline "<Beat/Turnaround-These>"
```
