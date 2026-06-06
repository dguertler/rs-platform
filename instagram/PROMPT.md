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
# Eigene, knackige Headline (Frage/These) fürs Cover + Reel-Hook:
python3 -m instagram.generate --analysis AMD \
  --headline "AMD: Nvidias einziger echter Rivale — Kauf oder Hype?"
```
Output: `out/instagram/<DATUM>_ANALYSE_<TICKER>/{carousel,reel}/*.png` +
`caption.txt`. **Kein Auto-Upload** — prüfen und manuell posten.

### Carousel vs. Reel (zwei getrennte Outputs, ein Lauf)
- **Carousel (4:5):** die VOLLE Analyse (7 Slides) — zum Speichern/Lesen.
- **Reel (9:16):** ein KURZER Teaser (4 Frames): Frage-Hook → Szenarien →
  Das Wichtigste → **Hybrid-CTA** „Die ganze Analyse findest du im
  Karussell-Post auf meinem Profil". Das Reel holt Reichweite und leitet sie
  auf den Karussell-Post um (Hybrid-Funnel).

### Reel-Video & Script (zwei Wege)
Jeder Analyse-Lauf erzeugt zusätzlich:
- **`reel_script.txt`** — fertiges Voiceover-Script + KI-Generator-Prompt (düster,
  cineastisch, B-Roll je Sektor, Timecodes) für **InVideo AI / Google Veo /
  CapCut**. Dort einfügen → professionelles Reel mit KI-Stimme & B-Roll bauen.
- **`reel.mp4`** — einfache, sofort postbare MP4 aus den 9:16-Frames
  (Ken-Burns-Zoom + Crossfade, **ohne** Voiceover/B-Roll). Braucht
  `imageio`+`imageio-ffmpeg` (in requirements; sonst entfällt nur die MP4).

Beide Reels sind **Teaser** und enden mit dem **Hybrid-CTA** „ganze Analyse im
Karussell-Post auf meinem Profil" → leiten Reel-Reichweite aufs Carousel um.

### Hook = Frage/These (die ersten 3 Sekunden)
Die erste Slide (und der Reel-Hook) trägt eine **Frage oder steile These** statt
„Aktienanalyse Firma X" — z. B. „<Aktie>: Kauf oder Falle?". Ohne `--headline`
erzeugt der Generator automatisch eine **verdict-bewusste, pro Ticker variierte**
Frage. Für maximale Wirkung schreibt Claude pro Post eine **individuelle**
Headline und übergibt sie via `--headline` (jede Analyse anders gestalten).

### Slide-Reihenfolge (Analyse, ~8–10 Slides, Tiefe = USP)
1. **Cover** — Frage/These-Hook + Firmenlogo (weiße Karte) + Verdict-Badge + Score
2. **Gesamteinschätzung** — Kernthese (Investment-Case) + 4 **Sterne**-Ratings
3. **Szenarien · 12–18 Monate** — Bull/Base/Bear mit **Eintrittswahrscheinlichkeit**
   (Balken) + Kursziel-Spanne *(aus Punkt 3–5)*
4. **Was macht das Unternehmen?** — Highlights aus Punkt 1+2 (Geschäftsmodell)
5. **Die drei Szenarien erklärt** — je 1 Treibersatz Bull/Base/Bear (konsistent zu 3)
6. **Bewertung: die KGV-Illusion** — Trailing- vs. Forward-KGV-Chips + Text *(Punkt 7)*
7. **Risiko & Realitätscheck** — Positionierung/Erwartungen + Positionsgrößen-Chip
   *(Punkt 8; Kurs & GWS herausgefiltert)*
8. **Langfrist · 3–5 Jahre** — Kursziel-Spannen je Szenario *(Punkt 10)*, ohne %
9. **Profi-Fazit** — Kernaussage + vergleichbare Titel (Peers)
10. **Speichern & mitreden** — Save-CTA + Community-Frage (Engagement)

Tiefen-Slides (6/7/8/10) entfallen automatisch, wenn der Abschnitt fehlt
(Alt-Schema → kürzeres Carousel). **Bewusst NICHT auf den Slides:** aktueller
Kurs; **GWS-Ampel & Breakout-Status** (Punkt 9) — wird aus allen Texten
gefiltert (`analysis.clean_for_slide`).

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
- **Die Caption IST die Analyse** (Text unter den Fotos), kein externer Link:
  Hook, Geschäftsmodell, Szenarien mit %/Kurszielen, Langfrist, Sterne-Rating,
  Fazit, Peers — automatisch auf 2.200 Zeichen zugeschnitten.
- Hashtag-Mix: breit (#aktien #börse) + Ticker (#amd) + Sektor (#technologie) +
  Branded (#aialphaselection). Pflicht-Disclaimer in jeder Caption.
- **Saves/Dwell** treiben: Carousel „swipe für alle Szenarien" + Verweis auf
  Caption. Reels (9:16) zusätzlich für Reichweite.

### Firmenlogos
Siehe `instagram/assets/logos/README.md`. Kurz: `TICKER.png` (transparent)
dort ablegen; fehlt es, nutzt der Cover eine Wortmarke.

**Logo-Suche (Claude):** zuerst auf der **offiziellen Firmenseite** suchen —
Brand-/Media-/Newsroom-/Presse-Portal, sonst Investor Relations (z. B.
`amplify.amd.com` für AMD). Auto-Download ist in der Cloud geblockt
(`Host not in allowlist`) → Claude nennt die gefundene Logo-URL, der Nutzer
lädt die Datei im Chat hoch, Claude legt sie als `<TICKER>.png` ab und committet.

### Caption = die vollständige Analyse (kein externer Link)
Die Caption (`caption.txt`) ist die **für Instagram aufbereitete Analyse als
Text unter den Fotos** — KEIN „Link in Bio" auf eine externe Seite. Sie wird auf
das Instagram-Limit von **2.200 Zeichen** zugeschnitten (Hook, Geschäftsmodell,
Szenarien mit %/Kurszielen, Langfrist, Sterne-Rating, Fazit, Peers, kurzer
Disclaimer, Hashtags). Reicht der Platz nicht, kürzt der Generator automatisch
(weniger Bullets / ohne Langfrist). Die ausführliche Roh-Analyse bleibt in
`analyses/TICKER.md` (Archiv), wird aber NICHT auf Instagram verlinkt.

## Roadmap
- **Jetzt:** wöchentliches Carousel, manueller Upload.
- **Später (genug Follower):** Stories (kurze Updates); Reel-Animation aus den
  9:16-Frames (ffmpeg).
- **Optional:** Auto-Upload via Instagram Graph API (Business-Account).

## Alternativer Modus
Vollständig manueller Wochenreport ohne Stores:
`python3 -m instagram.generate --report instagram/reports/KW<NN>.json`
(Schema: `reports/KW21.example.json`).
