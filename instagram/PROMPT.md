# Instagram-Workflow — AI Alpha Selections

**Diese Datei ist die Anleitung für Claude.** In einer neuen Session genügt es,
hierauf zu verweisen („Folge instagram/PROMPT.md") und den aktuellen
wikifolio-Wert (+ ggf. Trades) zu schicken. Claude erzeugt daraus die fertigen
Slides + Caption in `out/`.

Account: **@aialphaselections** · wikifolio: `wfdg1983go`
(https://www.wikifolio.com/de/de/w/wfdg1983go)
Hauptformat **Carousel (4:5)** + **Reel-Frames (9:16)**. Faceless.
**Es wird nichts automatisch hochgeladen** – der Nutzer prüft `out/` und postet
manuell.

---

## ⚖️ wikifolio-Regeln (ZWINGEND einhalten)

Quelle: wikifolio Hilfecenter „Trader Do's and Don'ts" / „Externe Kommunikation".
**Strikte Trennung zwischen Musterdepot (wikifolio) und Zertifikat:**

**Erlaubt:** Strategie, Trades, Käufe/Verkäufe und Performance des *Musterdepots*
darstellen; auf die wikifolio-Seite verweisen.
**Verboten:** Kommentare/Meinungen zum **Zertifikat**; Empfehlung, ein Zertifikat
zu **kaufen**; **ISIN** veröffentlichen/bewerben (on- & offline); Eindruck
erwecken, man sei wikifolio-Mitarbeiter; **wikifolio-Logo** ohne schriftliche
Freigabe (eigenes Logo nutzen).
**Pflicht:** Risikohinweis (vergangene Wertentwicklung ≠ Zukunft, Verlustrisiko)
— im Generator als CTA-Slide + Caption integriert.

→ Nie „kauf das Zertifikat", keine ISIN, kein „investiere jetzt". Immer
„das Musterdepot / das wikifolio".

---

## Wöchentlicher Ablauf (Hauptweg)

**Der Nutzer schickt:** den aktuellen **Zertifikatswert** der KW
(eine Zahl). Bei Änderungen zusätzlich aktualisierte **Top-Positionen**.

1. **Wert speichern** (hängt an `data/wikifolio_history.json` an):
   ```bash
   python3 -m instagram.add_week --kw 22 --value 145.30
   ```
   (Claude darf die JSON auch direkt editieren.)
2. **Holdings ggf. aktualisieren:** `data/holdings.json` (Top-Positionen +
   `buy_date`). Reihenfolge = Rotationsreihenfolge der „Aktie der Woche".
3. **Generieren:**
   ```bash
   python3 -m instagram.generate --kw 22
   ```
4. **Review:** Slides aus `out/instagram/<DATUM>_KW22/` zeigen.
5. **Manuell posten.** Carousel = `carousel/`-PNGs in Reihenfolge; Caption aus
   `caption.txt`. Reel-Frames in `reel/`.

NASDAQ-Vergleich, Wochen-/Gesamtrendite, Alpha, Wochen-Historie und
„X von Y Wochen geschlagen" werden **automatisch** aus den gespeicherten Werten
+ dem QQQ-Benchmark (`data/rs_full.json`) berechnet.

---

## Slide-Reihenfolge (Wochenpost)

1. Hook — KW, Wochenperformance, Gesamtrendite
2. Performance Musterdepot vs. NASDAQ-100 (Equity-Kurve)
3. Kennzahlen — Gesamtrendite, Alpha, Wochen geschlagen, Ø Gewinn/Verlustwoche
4. Wochen-Historie (Balken grün/rot je KW)
5. **Stärkste Positionen** (Top-5, Wertzuwachs seit Kauf)
6. **Aktie der Woche** — rotierend eine Position; Kursverlauf mit Kaufmarker +
   eingearbeiteten weiteren Signalen
7. CTA + Risikohinweis

Rotation der Aktie der Woche: `index = (kw - base_kw) % anzahl_positionen`
(in `holdings.json`). Jede Woche eine andere – auch wenn die Top-5 gleich bleiben.

**Bewusst NICHT enthalten:** Erklärung, *wie* das System funktioniert
(RS-Methodik) — bleibt dem wikifolio vorbehalten.

---

## Gespeicherte Daten (`instagram/data/`)

| Datei | Inhalt | Wer pflegt |
|---|---|---|
| `config.json` | Symbol, Startdatum, Startwert, Account | einmalig |
| `wikifolio_history.json` | Zertifikatswert je KW | **wöchentlich** (Nutzer/Claude) |
| `holdings.json` | ALLE Positionen + Kaufdatum + Einstiegskurs (EUR) + `base_kw` | bei Kauf/Verkauf |

- **`value`** in `wikifolio_history.json`: Zertifikatswert auf gleicher Skala wie
  `start_value` in `config.json` (z. B. Index 100 oder echter EUR-Wert; dann
  `start_value` = Wert am Startdatum).
- In `holdings.json` werden **alle** Depotpositionen gespeichert. Die Slide
  „Stärkste Positionen" zeigt automatisch die **Top-5 nach Wertzuwachs**; die
  „Aktie der Woche" rotiert wöchentlich durch **alle** Positionen.
- **Performance** wird aus den OHLCV-Daten der RS-JSONs berechnet (Kurs seit
  `buy_date`, native %). `buy_price_eur` ist nur Anzeige (echter EUR-Einstieg).
- Neue Käufe/Verkäufe: Position in `holdings.json` ergänzen/entfernen; Top-5 und
  Rotation passen sich automatisch an.

### Ticker-Mapping (häufige Namen → Symbol)
Seagate→STX · Western Digital→WDC · NXP→NXPI · Micron→MU · Marvell→MRVL ·
Lam Research→LRCX · Applied Materials→AMAT · Datadog→DDOG · Centene→CNC ·
AMD→AMD · ASML→ASML · Akamai→AKAM · Analog Devices→ADI · Broadcom→AVGO.
Bei Unsicherheit nachfragen statt raten.

---

## Logo & Design
- Logo: `instagram/assets/logo.png` (transparent) bzw. `.jpg` — wird automatisch
  im Header genutzt; sonst Wortmarke als Fallback.
- Farben/Fonts/Disclaimer: `instagram/theme.py` (Navy + Royalblau, am Logo orientiert).

## Roadmap
- **Jetzt:** wöchentliches Carousel, manueller Upload.
- **Später (genug Follower):** Stories (kurze Updates); Reel-Animation aus den
  9:16-Frames (ffmpeg).
- **Optional:** Auto-Upload via Instagram Graph API (Business-Account).

## Alternativer Modus
Vollständig manueller Wochenreport ohne Stores:
`python3 -m instagram.generate --report instagram/reports/KW<NN>.json`
(Schema: `reports/KW21.example.json`).
