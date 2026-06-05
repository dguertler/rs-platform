# wikifolio News-Feed — Wochenreport-Format (VERBINDLICH)

> **Zweck:** Dies ist der Text-Wochenreport, der direkt im **wikifolio-News-Feed**
> der „AI Alpha Selection" (`wfdg1983go`) gepostet wird. Er ist **getrennt** vom
> Instagram-Carousel (`instagram/generate.py`), nutzt aber **dieselben Zahlen**
> (Quelle: `instagram/data/*.json`, identisch zu den Instagram-Slides).
>
> **Alle zukünftigen Wochenfeeds für wikifolio werden EXAKT nach diesem Schema
> erstellt.** Referenz-Beispiele: `KW21.md`, `KW22.md`. Neuer Feed: `KW<NN>.md`.

---

## Ablauf (pro Woche)

1. Zahlen aus `instagram/data/` ziehen bzw. via `store.compute(kw, …)` berechnen
   (Wochen-/Gesamtrendite, NASDAQ-100 Woche/Gesamt, Alpha, „N von M Wochen").
   → **Müssen mit den Instagram-Slides übereinstimmen.**
2. Käufe/Verkäufe der Woche aus `holdings.json` / `trades.json` entnehmen.
3. `KW<NN>.md` nach der untenstehenden Struktur schreiben.
4. Dem Nutzer zeigen — **kein Auto-Post**, manuelles Einstellen im wikifolio-Feed.

## Pflicht-Struktur (Reihenfolge & Bausteine)

```
📊 Wochenreport KW <NN> (<DD.MM.> – <DD.MM.>)

Performance:
    •    Portfoliowert: <±X,X%> diese Woche
    •    Gesamtrendite Wikifolio seit 30.03.: <±X,X%>
    •    Nasdaq-100: <±X,X%> diese Woche
    •    Gesamtrendite Nasdaq seit 30.03.: <±X,X%>
    •    Alpha seit 30.03.: <±X,X%>
    •    <N> von <M> Wochen den Nasdaq geschlagen

🔥 Trades der Woche:

✅ Käufe:
→ <Name> (<DD.MM.>)
<1–2 Sätze: RS-Score / technisches Setup / Sektor-Logik.> Positionsgröße <X,X%>.

❌ Verkäufe:
← <Name> (<DD.MM.>, <±X,X%> seit Kauf)
<1–2 Sätze: Grund — Gewinnmitnahme bei abgeschwächtem RS, oder Stopp/Risiko­management.>

📈 <Wochen-Headline>:
<Kurze Einordnung der Wochenperformance vs. NASDAQ-100.>

🔍 <Strategie-/Sektorrotation>:
<Was hat der RS-Screen erkannt, wie wurde rotiert.>

⚙️ System-Konsistenz:
<RS-Screening (6 Zeitfenster) · technische Validierung · 1% Risiko/Trade ·
dynamische Rotation → konsistente Outperformance.>

🎯 Ausblick:
<Der RS-Screen läuft täglich; Stärke wird konsequent umgesetzt.>

<Schluss-Claim, z. B.:>
„Keine Prognosen, keine Meinungen – nur Daten, Disziplin und Umsetzung."
```

Optionale Zusatzblöcke (wie in KW21): `💡 Verluste gehören zur Systematik`,
`📊 Bilanz nach N Wochen` (Wochenhistorie als ✅/❌-Liste + Ø Gewinn-/Verlustwoche).

## Ton & Inhalt

- **Systematisch, nüchtern, diszipliniert.** Keine Euphorie, keine Panik, keine Prognosen.
- **RS-Methodik DARF hier erklärt werden** (KI-gestütztes RS-Screening über 6 Zeitfenster,
  technische Chartvalidierung, 1 % Risiko pro Trade, dynamische Rotation) — anders als beim
  Instagram-Post, der die Methodik bewusst auslässt.
- Verluste offen benennen und als Teil des Risikomanagements einordnen
  (konsequente Stopps, Kapitalumschichtung in stärkere RS-Leader).

## wikifolio-Regeln (ZWINGEND, siehe instagram/PROMPT.md)

- **Keine ISIN**, keine Empfehlung, das **Zertifikat** zu kaufen, kein „investiere jetzt".
- Strikte Trennung Musterdepot/Strategie ↔ Zertifikat. Nur über Depot/Strategie/Trades sprechen.
- Nicht als wikifolio-Mitarbeiter auftreten. Vergangene Wertentwicklung ≠ Zukunft.

## Zahlen-Konsistenz

- Quelle der Wahrheit = `instagram/data/` (gleich wie Instagram-Slides).
- NASDAQ-100 = **^NDX**; bei fehlendem Tageswert in der RS-JSON via
  `"nasdaq_value"` in `wikifolio_history.json` setzen (greift für Woche **und** Gesamt/Alpha).
- „N von M Wochen geschlagen": Woche zählt als geschlagen, wenn die **gerundete**
  Wochen-Mehrrendite ggü. NASDAQ ≥ 0 ist (Gleichstand = geschlagen).
