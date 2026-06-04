# Instagram-Workflow — AI Alpha Selections

**Diese Datei ist die Anleitung für Claude.** In einer neuen Session genügt es,
hierauf zu verweisen („Folge instagram/PROMPT.md") und den wikifolio-Wochenfeed
einzufügen. Claude erstellt daraus die fertigen Slides + Caption in `out/`.

Account: **@aialphaselections** · Hauptformat: **Carousel (4:5)** · zusätzlich
**Reel-Frames (9:16)**. Faceless. **Es wird nichts automatisch hochgeladen** –
der Nutzer prüft `out/` und postet manuell.

---

## ⚖️ wikifolio-Regeln (ZWINGEND einhalten)

Quelle: wikifolio Hilfecenter „Trader Do's and Don'ts" / „Externe Kommunikation".
Es gilt die **strikte Trennung zwischen Musterdepot (wikifolio) und Zertifikat**:

**Erlaubt** (über das *Musterdepot* sprechen):
- Strategie, Trades, Käufe/Verkäufe, Performance des wikifolios darstellen.
- Auf die wikifolio-Seite (Musterdepot) verweisen.

**Verboten:**
- Kommentare/Analysen/Meinungen zum **Zertifikat** (Finanzprodukt).
- Empfehlung, ein **Zertifikat zu kaufen** (= erlaubnispflichtige Beratung).
- Veröffentlichen/Bewerben der **ISIN** – on- und offline.
- Den Eindruck erwecken, man sei wikifolio-Mitarbeiter.
- **wikifolio-Logo** ohne vorherige schriftliche Freigabe von wikifolio.

**Pflicht:** Risikohinweis (vergangene Wertentwicklung ≠ Zukunft, Verlustrisiko)
— ist im Generator als letzte Slide + in der Caption integriert.

→ In Texten daher nie „kauf das Zertifikat", keine ISIN, kein „investiere jetzt".
Immer „das Musterdepot / das wikifolio". Eigenes Marken-Logo statt wikifolio-Logo.

---

## Wöchentlicher Ablauf

1. **Feed einfügen.** Der Nutzer postet seinen wikifolio-Wochenreport (Text).
2. **Report-JSON füllen:** Daraus `instagram/reports/KW<NN>.json` schreiben
   (Schema unten / `reports/KW21.example.json`). Claude ist das LLM, das den
   Freitext in die Felder überträgt — kein externer Call.
3. **Wikifolio-Kurve** sicherstellen (`data/wikifolio_performance.json`),
   falls die Equity-vs-NASDAQ-Kurve real sein soll. Sonst wird sie aus den
   Wochenrenditen der `history` rekonstruiert (das reicht meist).
4. **Generieren:**
   ```bash
   python3 -m instagram.generate --report instagram/reports/KW<NN>.json
   ```
5. **Review:** Bilder aus `out/instagram/<DATUM>_KW<NN>/` dem Nutzer zeigen.
6. **Manuell posten.** Carousel = `carousel/`-PNGs in Reihenfolge; Caption aus
   `caption.txt`. Reel-Frames liegen in `reel/`.

---

## Slide-Reihenfolge (Wochenpost)

1. Hook — KW, Wochenperformance, Gesamtrendite
2. Performance Musterdepot vs. NASDAQ-100 (Equity-Kurve)
3. Kennzahlen — Gesamtrendite, Alpha, Wochen geschlagen, Ø Gewinn/Verlustwoche
4. Wochen-Historie (Balken grün/rot je KW)
5. **Käufe der Woche** (neueste, mit Positionsgröße)
6. **Stärkste Positionen** (Top-3 Wertzuwachs seit Kauf) — `top_holdings`
7. **Verkäufe der Woche** (mit Performance, grün/rot)
8. CTA + Risikohinweis

**Bewusst NICHT enthalten:** Erklärung, *wie* das System funktioniert
(RS-Methodik, Zeitfenster etc.) — das bleibt dem wikifolio vorbehalten und
wird auf Instagram nicht preisgegeben.

---

## Report-Schema (`reports/KW<NN>.json`)

```json
{
  "kw": 21, "year": 2026, "period": "18.05. – 22.05.2026",
  "week_perf": 0.031, "total_perf": 0.418,
  "nasdaq_week": 0.011, "nasdaq_total": 0.277, "alpha": 0.141,
  "weeks_beaten": 6, "weeks_total": 8,
  "history": [{ "kw": 14, "perf": 0.074 }, ...],
  "buys":  [{ "ticker": "STX", "name": "Seagate Technology", "date": "21.05.", "size": 0.074 }],
  "sells": [{ "ticker": "ASML", "name": "ASML Holding", "date": "18.05.", "ret": -0.053 }],
  "top_holdings": [{ "ticker": "STX", "name": "Seagate Technology", "ret": 0.182 }]
}
```

- Prozente als **Dezimal** (3,1 % → `0.031`).
- `alpha` und `weeks_beaten` werden automatisch berechnet, wenn weggelassen.
- `top_holdings` = aktuelle Depotpositionen mit größtem Zuwachs seit Kauf
  (kommt aus dem wikifolio, nicht aus dem Wochenfeed — vom Nutzer erfragen,
  sonst Slide weglassen).

### Ticker-Mapping (häufige Namen → Symbol)
Seagate→STX · Western Digital→WDC · ASML→ASML · Akamai→AKAM ·
Analog Devices→ADI · NXP→NXPI · Micron→MU · Marvell→MRVL · Broadcom→AVGO.
Bei Unsicherheit nachfragen statt raten.

---

## Roadmap

- **Jetzt:** Carousel (Feed) wöchentlich, manueller Upload.
- **Später (bei genügend Followern):** Stories als kurze Updates/„Signal heute";
  Reel-Animation aus den 9:16-Frames (ffmpeg).
- **Stufe 2 (optional):** Auto-Upload via Instagram Graph API (Business-Account)
  — erst nach finalem Design + rechtlicher Freigabe.

## Design ändern
Farben/Fonts/Disclaimer in `instagram/theme.py`. Logo: `instagram/assets/logo.png`.
