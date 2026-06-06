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

1. **Performance vs. NASDAQ-100** (Eye-Catcher, erste Slide) — Equity-Kurve +
   Kennzahlen unter dem Graph: Gesamtrendite, NASDAQ, Alpha, Trades seit Start,
   Trefferquote, Profitfaktor, Ø Gewinn/Trade, Ø Verlust/Trade
2. **Wochen-Historie** — wöchentliche Mehrrendite ggü. NASDAQ-100 (grün = besser)
3. **Stärkste Positionen** (Top-5, mit Kaufdatum + Einstiegskurs)
4. **Aktie der Woche** — rotierend eine Position; Kursverlauf mit Kauf-Signal
   (blau) + eingearbeiteten weiteren Signalen
5. **Newcomer** — bestperformende Aktie der letzten 3 Wochen, NUR wenn sie nicht
   in den Top-5 ist (sonst entfällt die Slide)
6. CTA + Risikohinweis

Rotation der Aktie der Woche: `index = (kw - base_kw) % anzahl_positionen`
(in `holdings.json`). Jede Woche eine andere – auch wenn die Top-5 gleich bleiben.
Kennzahlen werden aus `trades.json` (abgeschlossene Trades) + den aktiven
Positionen berechnet.

**Bewusst NICHT enthalten:** Erklärung, *wie* das System funktioniert
(RS-Methodik) — bleibt dem wikifolio vorbehalten.

---

## Gespeicherte Daten (`instagram/data/`)

| Datei | Inhalt | Wer pflegt |
|---|---|---|
| `config.json` | Symbol, Startdatum, Startwert, Account | einmalig |
| `wikifolio_history.json` | Zertifikatswert je KW | **wöchentlich** (Nutzer/Claude) |
| `holdings.json` | ALLE Positionen + Kaufdatum + Einstiegskurs (EUR) + `base_kw` | bei Kauf/Verkauf |
| `trades.json` | abgeschlossene Trades (realisierte Rendite) für Kennzahlen | bei Verkauf |

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

---

## Zweiter Post-Typ: AKTIEN-ANALYSE (aus `analyses/TICKER.md`)

Neben dem Wochenupdate gibt es **Analyse-Posts**: Sie machen aus einer fertigen
KI-Analyse (`analyses/TICKER.md`) ein Carousel. Ziel: **1–2 Analysen pro Woche**.

**Grid-Logik (auf einen Blick erkennbar):**
- **Wochenupdate** → Cover mit AI-Alpha-Marke + Equity-Kurve.
- **Analyse** → Cover mit **Firmenlogo** der AG + Verdict-Badge (BUY=grün,
  HOLD=gelb, WATCH/SELL=rot). So sieht man im Profil-Raster sofort, was was ist.

### Ablauf
```bash
# Logo der AG (einmalig) ablegen: instagram/assets/logos/<TICKER>.png
python3 -m instagram.generate --analysis AMD          # Carousel 4:5 + Reel 9:16
python3 -m instagram.generate --analysis sie_de       # Ticker oder Pfad/Dateiname
```
Output: `out/instagram/<DATUM>_ANALYSE_<TICKER>/{carousel,reel}/*.png` +
`caption.txt`. **Kein Auto-Upload** — prüfen und manuell posten.

### Slide-Reihenfolge (Analyse, 5–7 Slides)
1. **Cover** — Firmenlogo + Name/Sektor + Verdict-Badge + Score/100 + 1-Satz-Hook
2. **Gesamteinschätzung** — Kernthese (Investment-Case) + 4 Rating-Pips
   (Qualität/Wachstum/Bewertung/Katalysator)
3. **Szenarien · 12–18 Monate** — Bull/Base/Bear mit **Eintrittswahrscheinlichkeit**
   (Balken) + Kursziel-Spanne *(aus Analyse-Punkten 3–5)*
4. **Langfrist · 3–5 Jahre** — Kursziel-Spannen je Szenario *(aus Punkt 10)*,
   bewusst **ohne** Wahrscheinlichkeiten — Zeithorizont klar getrennt von Slide 3
5. **Was macht das Unternehmen?** — Highlights aus Punkt 1+2 (Geschäftsmodell)
6. **Die drei Szenarien erklärt** — je 1 Treibersatz Bull/Base/Bear (konsistent zu 3)
7. **Profi-Fazit** — Kernaussage + vergleichbare Titel (Peers) + Verweis auf die
   vollständige Analyse in der **Caption** (Pfeile ⌄ + „Link in Bio")

**Bewusst NICHT auf den Slides:** aktueller Kurs; Punkt 9 (Technik/Momentum);
**GWS-Ampel & Breakout-Status**; Punkte 6/7/8 (Detail zu Qualität/Bewertung/
Psychologie) — die volle Tiefe steht in der Caption / auf der Rating-Seite.

### Wichtig: Kursziele konsistent halten
- **Slide 3 = 12–18 Monate** (mit Wahrscheinlichkeit, aus Punkt 3/4/5).
- **Slide 4 = 3–5 Jahre** (ohne Wahrscheinlichkeit, aus Punkt 10).
- Jede Slide trägt ihren **Zeithorizont** in der Überschrift → keine
  widersprüchlichen Zahlen, weil Leser den Bezug sehen.

### Analyse-Schema beachten (sonst reduziertes Carousel!)
Nur Analysen im **neuen 11-Abschnitte-Schema** (`analyses/PROMPT.md`) liefern
Wahrscheinlichkeiten + Kursziele. Ältere/abweichende Analysen (z. B. mit
„## 4. BEAR CASE" statt BASE, ohne `Eintrittswahrscheinlichkeit: X%`) lassen
die Szenario-Slides automatisch weg (Cover/Einschätzung/Unternehmen/Fazit
bleiben). Der Generator meldet beim Lauf `Szenarien ja/NEIN`. Für volle Posts:
Analyse vorher nach `analyses/PROMPT.md` neu generieren.

### SEO / Algorithmus (in `caption.txt` umgesetzt)
- **Erste Zeile = Keyword zuerst:** „<Firmenname> (TICKER) — Aktienanalyse:
  <Verdict>" → das indexiert Instagram für die Suche.
- Strukturierte Kurzfassung (Szenarien, Geschäftsmodell, Fazit, Peers) als
  „👇 vollständige Analyse" — die echte Langfassung (bis 1000 Wörter) passt
  nicht in die 2.200-Zeichen-Caption → **Link in Bio** auf die Rating-Seite
  (`data/ratings/TICKER.html`).
- Hashtag-Mix: breit (#aktien #börse) + Ticker (#amd) + Sektor (#technologie) +
  Branded (#aialphaselection). Pflicht-Disclaimer in jeder Caption.
- **Saves/Dwell** treiben: Carousel „swipe für alle Szenarien" + Verweis auf
  Caption. Reels (9:16) zusätzlich für Reichweite.

### Firmenlogos
Siehe `instagram/assets/logos/README.md`. Kurz: `TICKER.png` (transparent)
dort ablegen; fehlt es, nutzt der Cover eine Wortmarke. Auto-Download ist in
der Cloud geblockt — Logos manuell ablegen (oder im Chat hochladen).

## Roadmap
- **Jetzt:** wöchentliches Carousel, manueller Upload.
- **Später (genug Follower):** Stories (kurze Updates); Reel-Animation aus den
  9:16-Frames (ffmpeg).
- **Optional:** Auto-Upload via Instagram Graph API (Business-Account).

## Alternativer Modus
Vollständig manueller Wochenreport ohne Stores:
`python3 -m instagram.generate --report instagram/reports/KW<NN>.json`
(Schema: `reports/KW21.example.json`).
