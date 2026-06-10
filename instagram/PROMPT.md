# Instagram-Workflow — AI Alpha Selection

**Diese Datei ist die Anleitung für Claude.** In einer neuen Session genügt es,
hierauf zu verweisen („Folge instagram/PROMPT.md") und den aktuellen
wikifolio-Wert (+ ggf. Trades) zu schicken. Claude erzeugt daraus die fertigen
Slides + Caption in `out/`.

Marke: **AI Alpha Selection** (Singular; Instagram-Handle noch offen — kein
@-Handle auf Slides oder in Captions, nur der Markenname) ·
wikifolio: `wfdg1983go` (https://www.wikifolio.com/de/de/w/wfdg1983go)
Hauptformat **Carousel (4:5)** + **Reel-Frames (9:16)**. Faceless betrieben
(das Wort „faceless" erscheint nirgends auf Slides/Captions).
**Es wird nichts automatisch hochgeladen** – der Nutzer prüft `out/` und postet
manuell.

> 📌 **Single Source of Truth & Pflege-Regel:**
> - **Diese Datei (`PROMPT.md`)** = alle Abläufe, Regeln und Konventionen.
> - **`CONTEXT.md`** = aktueller Projektstand (Daten-Snapshot, Design-System,
>   Code-Karte, offene Punkte). Regeln stehen NICHT doppelt dort.
> - Macht der Nutzer eine neue Vorgabe (Design, Ablauf, Texte, …), wird sie
>   **sofort** in der zuständigen Datei festgehalten — dabei die veraltete
>   Aussage **ersetzen statt ergänzen** (keine „Round"-Historie; die Historie
>   liegt im Git-Log). Nichts „nur im Chat" merken.
> - Keine manuell gepflegten Zähler („X von Y Analysen") — per grep ermitteln.

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
„das wikifolio AI Alpha Selection". Das Wort „Musterdepot" wird in Posts
bewusst NICHT verwendet (es sind reale Käufe); ebenso nicht „Live-Depot".

---

## Wöchentlicher Ablauf (Hauptweg)

**Der Nutzer schickt:** den aktuellen **Zertifikatswert** der KW (eine Zahl) und
bei Änderungen die **Käufe/Verkäufe** der Woche (Ticker/Name, Datum, Kurs, ggf.
realisierte Rendite in %).

> ⚠️ **PFLICHT — Werte IMMER zuerst persistent abspeichern.** Sobald der Nutzer
> einen Wochenstand und/oder Trades schickt, schreibt Claude diese **automatisch
> und ohne Rückfrage** in die Datendateien (Schritt 1), **bevor** generiert wird.
> Das ist fixer Bestandteil jeder Wochen-Session — auch rückwirkend.

1. **Alle gelieferten Werte abspeichern** (`instagram/data/`):
   1. **Zertifikatswert** → `wikifolio_history.json` (echtes Datum mitgeben):
      ```bash
      python3 -m instagram.add_week --kw 23 --value 149.86 --date 2026-06-05
      ```
      (Claude darf die JSON auch direkt editieren; ein Eintrag pro KW.)
   2. **Käufe** → neue Position in `holdings.json` ergänzen
      (`ticker`, `name`, `buy_date`, `buy_price_eur`).
   3. **Verkäufe** → Position aus `holdings.json` **entfernen** **und** den
      abgeschlossenen Trade in `trades.json` (`closed`) ergänzen
      (`name` + `ret` als **Dezimal**, z. B. +69,7 % → `0.697`, −6 % → `-0.06`).
      Ein im selben Zeitraum ge- und wieder verkaufter Titel (z. B. IBM Kauf Mo /
      Verkauf Do) erscheint **nicht** in `holdings.json`, sondern **nur** als
      abgeschlossener Trade.
   4. Ticker-Mapping bei Namen beachten (Tabelle unten). Bei Unsicherheit fragen.
2. **Dynamische Felder texten (PFLICHT, siehe unten):** Claude formuliert pro
   Woche aus den Daten eine **Hook-Schlagzeile**, ein strategisches **„Warum"**
   und eine **Interaktions-Frage** und übergibt sie:
   ```bash
   python3 -m instagram.generate --kw 22 \
     --hook  "+18,4% Alpha: Während der Nasdaq schlief, hat die KI agiert." \
     --why   "Sektor-Rotation in Halbleiter: Volatilitäts-Check bestanden, der \
              bestätigte Trend hat die Signale für MRVL getriggert." \
     --frage "Hättest du MU bei diesem Kurs auch gekauft – oder auf einen \
              Rücksetzer gewartet? Schreib's unten rein!"
   ```
   Ohne Flags greifen datenbasierte **Fallbacks** (`auto_hook` / `auto_why` /
   `auto_question` in `generate.py`) — die Slides funktionieren also immer, aber
   die individuell getextete Variante ist Standard für maximale CTR/Engagement.
3. **Review:** Slides aus `out/instagram/<DATUM>_KW<NN>/` zeigen.
4. **Manuell posten.** Carousel = `carousel/`-PNGs in Reihenfolge; Caption aus
   `caption.txt`. Reel-Frames in `reel/`.
5. **Datendateien committen** (`wikifolio_history.json`, `holdings.json`,
   `trades.json`) — die `out/`-Slides sind bewusst gitignored, die Werte bleiben
   aber dauerhaft im Repo.

NASDAQ-Vergleich, Wochen-/Gesamtrendite, Alpha, Wochen-Historie und
„X von Y Wochen geschlagen" werden **automatisch** aus den gespeicherten Werten
+ dem **^NDX**-Benchmark (`ndx_ohlcv` in `data/rs_full.json`; QQQ nur
Fallback) berechnet. USD-Kursrenditen werden über die EUR/USD-Serie
(`eurusd_ohlcv`) in echte EUR-Renditen umgerechnet.

### Slide-Datum (oben rechts) — Samstag der KW
Das Datum oben rechts ist **standardmäßig der Samstag der jeweiligen KW**
(Wochenabschluss). Logik (`report.slide_date`):

- Liegt der Samstag der KW in der **Vergangenheit** (Bericht wird später oder
  rückwirkend erstellt) → es wird **dieser Samstag** eingetragen. Bsp.: heute ist
  KW24, du erstellst den Report für KW23 → Datum = Samstag KW23.
- Liegt der Samstag noch in der **Zukunft** (Bericht entsteht in der laufenden
  Woche vor Samstag) → es wird **heute** eingetragen. Bsp.: heute ist noch KW23
  (z. B. Donnerstag) → Datum = heute.
- Ein expliziter `--date YYYY-MM-DD` hat immer Vorrang (manuelles Override).

So trägt jede rückwirkend erzeugte Analyse automatisch das korrekte
Wochen-Samstagsdatum. Der Output-Ordner heißt entsprechend `<DATUM>_KW<NN>`.

---

## Slide-Reihenfolge (Wochenpost — VERBINDLICH, entspricht `generate.build_from_store`)

1. **Dynamic Hook** (visueller Stopper – KEIN Dashboard) — dynamische
   **Schlagzeile** (`--hook`) + Beweis-Chips (Gesamtrendite + NASDAQ-100 seit
   Start). Macht in den ersten 3 Sek. neugierig.
2. **Performance vs. NASDAQ-100** (Eye-Catcher) — Equity-Kurve + Kennzahlen
   unter dem Graph: Gesamtrendite, NASDAQ, Alpha, Trades seit Start,
   Trefferquote, Profitfaktor, Ø Gewinn/Trade, Ø Verlust/Trade
   (`*` = inkl. offener Positionen)
3. **Wochen-Historie** — wöchentliche Mehrrendite ggü. NASDAQ-100 (grün =
   besser); erscheint erst ab 2+ Wochen Datenbasis (ab KW15)
4. **Stärkste Positionen** (Top-5 nach Wertzuwachs, mit Kaufdatum + Einstiegskurs)
5. **Aktie der Woche** — rotiert durch ALLE Positionen; Kursverlauf mit
   Kauf-Signal + eingearbeiteten weiteren Signalen
6. **Weitere Positionen** (alle außerhalb der Top-5)
7. **Newcomer** — bester Kauf der letzten 3 Wochen, NUR wenn nicht in den
   Top-5 (sonst entfällt die Slide)
8. **Strategisches „Warum"** (minimalistische Text-Slide, KI-Kontext) — NACH
   den Positionsslides: erklärt kurz, warum das Modell so entschieden hat
   (Sektor-Rotation / Volatilitäts-Check / Trendbestätigung). Text aus `--why`.
9. **Trade der Woche** — ALLE realisierten Verkäufe der KW als je eine eigene
   Slide, sortiert nach Rendite absteigend (`trades.json` → `closed` mit
   Verkaufsdatum in der KW). Chart mit **Kauf grün + Verkauf rot**; das
   Chart-Fenster endet kurz nach dem Verkauf.
10. **CTA + Engagement-Boost + Risikohinweis** — Bio-Link-Pfad (URLs sind in
   IG-Beiträgen nicht klickbar) + dynamische Interaktions-Frage (`--frage`) +
   Pflicht-Risikohinweis.

**Reihenfolge-Begründung:** Erst das Portfolio zeigen (Positionen + Charts),
dann erklären WARUM (Rotation/Trades); die Trade-Slides folgen nach dem „Warum".

Rotation der Aktie der Woche: `index = (kw - base_kw) % anzahl_positionen`
(in `holdings.json`). Jede Woche eine andere – auch wenn die Top-5 gleich bleiben.
Kennzahlen werden aus `trades.json` (abgeschlossene Trades) + den aktiven
Positionen berechnet.

**Bewusst NICHT enthalten:** Erklärung, *wie* das System funktioniert
(RS-Methodik) — bleibt dem wikifolio vorbehalten.

---

## Dynamische Felder (Standard-Workflow für jede KW)

Diese drei Texte schreibt **Claude pro Woche aus den Daten** — sie sind der Kern
des CTR-/Engagement-Upgrades. Render-Funktionen: `slide_hook_dynamic`,
`slide_why`, `slide_cta` in `render.py`.

### 1) `--hook` — Dynamic-Hook-Schlagzeile (Slide 1)
- **Logik:** Aus den Wochendaten die *eine* Story ableiten, die neugierig macht —
  hoher Alpha-Wert, Outperformance ggü. NASDAQ, Krisenfestigkeit oder
  Sektor-Gewinne.
- **Dynamik-Regel:** an wöchentliche Ereignisse koppeln, z. B.
  - „Warum die KI Halbleiter-Dips ignoriert hat"
  - „+X% Alpha: Während der Nasdaq schlief, hat die KI agiert"
  - „Sektor-Rotation: Wie das Modell rechtzeitig in Memory-Chips drehte"
- **Beweis:** Die Slide zeigt zusätzlich automatisch Gesamtrendite + Alpha als
  Kennzahlen-Chips (Daten, kein Texten nötig).

### 2) `--why` — Strategisches „Warum" (KI-Kontext-Slide)
- **Zweck:** Kontext zur KI-Logik, Übergang zu den Einzelaktien-Deep-Dives.
- **Template:** „Hinter den Kulissen: Unser KI-Modell hat diese Woche den Fokus
  auf **[Sektor/Thema]** gelegt, da **[Marktereignis]** die Signale für
  **[Aktie X]** getriggert hat."

### 3) `--frage` — Interaktions-Frage (CTA-Slide, Engagement-Boost)
- **Zweck:** Kommentare pushen (Algorithmus-Signal).
- **Logik:** spezifisch aus den Trades der Woche generieren, z. B.
  „Hättest du **[Aktie]** bei diesem Preis auch gekauft oder hättest du auf einen
  Rücksetzer gewartet? Schreib's unten rein! 👇"
- Die **CTA-Slide** verweist strikt auf die **Bio**, da URLs im IG-Text nicht
  klickbar sind: „Den Link zum wikifolio AI Alpha Selection findest du aktuell
  in unserer Bio." (kein @-Handle, kein „Live-Depot").

> ⚖️ wikifolio-Regeln bleiben bindend: kein „kauf das Zertifikat", keine ISIN.
> Der Bio-Link führt auf die **wikifolio-Seite des Depots** (erlaubt).

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

### Standard-Konventionen für Charts & Slides (verbindlich)
Diese Regeln gelten für **alle künftigen** Wochenposts (in `render.py` umgesetzt):

- **Chart-Marker = Ampel-Logik:** **Kauf = grün** (`T.GREEN`), **Verkauf = rot**
  (`T.RED`). Das große Kauf-Signal ist grün, weitere Kauf-Signale grün (kleiner,
  transparent), Verkäufe als rote Marker mit „Verkauf <Datum>". Legende unter dem
  Chart: „● Kauf · ● Verkauf · ● weitere Kauf-Signale".
- **Verkaufsmarker-Datenquelle:** rote Marker erscheinen automatisch, wenn ein
  abgeschlossener Trade in `trades.json` ein `ticker` + Verkaufsdatum (`date`)
  trägt (siehe Schema dort). Aktuell gehaltene Titel (Aktie der Woche / Newcomer)
  zeigen nur den grünen Kauf — ein roter Marker kommt erst, wenn die Position
  (teil-)verkauft wurde.
- **Listen-Slides** „Stärkste Positionen" und „Weitere Positionen": die
  **Detailzeile unter dem Ticker** (Name · Kaufdatum · Einstiegskurs) wird **groß
  und gut lesbar** gesetzt (Schriftgröße 22, Farbe `T.SUBTLE`) — bewusst größer
  als der Standard-Sekundärtext.

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
- **Carousel (4:5):** die VOLLE Analyse (10 Slides, siehe Slide-Reihenfolge
  unten) — alle Analyseteile stehen auf den Slides, zum Speichern/Lesen.
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

**Marken-Tagline (Profi-Fazit + „Speichern & mitreden"-Slide):** unter „Folge für
wöchentliche Profi-Analysen" steht exakt **„datengetrieben · unabhängig ·
systematisiert"** (kein „faceless"). Gilt einheitlich für Analyse- UND
Earnings-Posts (`slide_analysis_fazit`, `slide_analysis_cta`, `slide_earnings_cta`).

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
- **Kurz-Caption:** Die volle Analyse steht AUF DEN SLIDES — die Caption
  enthält keinen Analyse-Content, sondern nur SEO-Zeile, Hook-Satz,
  Save-/Folge-CTA, Pflicht-Disclaimer und Hashtags (`caption_analysis`
  in `generate.py`).
- **Hashtags: max. 5 pro Post** (Instagram-Limit seit 2025; lt. Instagram
  optimal 3–5 hochrelevante Tags als Kontextsignal — Masse bringt nichts):
  Ticker (#amd) + Kern-Keyword (#aktienanalyse) + Sektor
  (#technologieaktien) + breit (#investieren) + Brand (#aialphaselection).
  Hashtags in die Caption, nicht in die Kommentare (sofortige Indexierung).
- **Saves/Dwell** treiben: Carousel „swipe für alle Szenarien" + Save-CTA.
  Reels (9:16) zusätzlich für Reichweite.

### Firmenlogos
Siehe `instagram/assets/logos/README.md`. Kurz: `TICKER.png` (transparent)
dort ablegen; fehlt es, nutzt der Cover eine Wortmarke.

**Logo-Suche (Claude):** zuerst auf der **offiziellen Firmenseite** suchen —
Brand-/Media-/Newsroom-/Presse-Portal, sonst Investor Relations (z. B.
`amplify.amd.com` für AMD). Auto-Download ist in der Cloud geblockt
(`Host not in allowlist`) → Claude nennt die gefundene Logo-URL, der Nutzer
lädt die Datei im Chat hoch, Claude legt sie als `<TICKER>.png` ab und committet.

### Caption = Kurz-Caption (volle Analyse auf den Slides)
Die Caption (`caption.txt`) ist bewusst kurz — **alle Analyseteile stehen auf
den Slides**, nichts wird in die Caption ausgelagert und kein externer Link
gesetzt. Inhalt: SEO-Zeile (Keyword zuerst) · Hook-Satz · Save-/Folge-CTA ·
Pflicht-Disclaimer · max. 5 Hashtags. Die ausführliche Roh-Analyse bleibt in
`analyses/TICKER.md` (Archiv), wird aber NICHT auf Instagram verlinkt.

## Dritter Post-Typ: EARNINGS-ANALYSE (aus Quartalszahlen)

**Trigger:** `Earnings-Analyse TICKER für Insta` (z. B. nach einem Earnings-Termin
mit übertroffenen Prognosen) bzw. `Earnings-Analyse TICKER`.

Macht aus einem **Quartalsbericht mit Beat** einen eigenständigen Carousel-Post
(bis zu 14 Slides — Tiefe ist der USP) + Reel-Teaser. Anders als der Analyse-Post liegt der Fokus auf dem
**Earnings-Ereignis** (Beat-Zahlen, Kurssprung, Guidance) — die Slide 1 macht
sofort klar: *das ist ein Earnings-Post, keine normale Analyse* (grüne
„EARNINGS · Q<N> <Jahr> · BEAT"-Pille + Hero-Zahlen EPS-Surprise & Kurssprung).

### Welche Aktien? — die Beat-Regeln (aus `check_earnings.py`)
Der bestehende Workflow `check_earnings.py` findet täglich genau diese Kandidaten
und mailt/telegrammt sie. Schwellen (identisch in `instagram/earnings.py` gespiegelt):
- **≥ 5 % Kurssprung** (Close-zu-Close am Meldetag), **und**
- **≥ 10 % EPS-Surprise** (Ist vs. Analysten-Erwartung), **und**
- **Umsatz YoY ≥ 0** (kein schrumpfender Umsatz).

→ Ein Titel aus der Earnings-Mail / dem Telegram-Alert ist immer ein guter
Kandidat für einen Earnings-Post.

### Ablauf (was Claude pro Earnings-Post tut)

1. **Basis-Analyse sicherstellen (Voraussetzung).** Es muss eine `analyses/TICKER.md`
   im **neuen 11-Abschnitte-Schema** geben (liefert Verdict, Szenarien, Kursziele,
   Fazit für die Slides).
   - Fehlt sie → **zuerst** die Aktienanalyse nach `analyses/PROMPT.md` erzeugen
     (siehe Haupt-`CLAUDE.md`, „Analysiere TICKER").
   - **Ist sie älter als der Earnings-Termin** → vorher **neu generieren**, damit
     Zahlen/Verdict den Quartalsstand widerspiegeln. (Ist sie nach dem Earnings-
     Datum erstellt, unverändert nutzen.)

2. **Earnings-Daten aus dem Web holen & persistieren (PFLICHT, zuerst).**
   yfinance ist in der Cloud meist geblockt → die harten Zahlen kommen aus dem
   **Web** (Pressemitteilung/IR, SEC-8-K, Finanzportale). Claude schreibt sie in
   `instagram/data/earnings/<TICKER>.json` (Schema unten). Der **Kurssprung** wird
   NICHT eingetragen — er wird automatisch live aus der passenden RS-JSON
   (`data/rs_*.json`) berechnet (inkl. Reaktions-Chart).
   - **Optional, für den Tiefgang (sehr empfohlen):** zusätzlich die Felder
     `quarterly` (bereinigtes EPS der letzten ~6 Quartale → Slide „Gewinn je
     Quartal") und `segments` (Segment-Treiber des Beats → Slide „Was den Beat
     getragen hat") aus dem Web recherchieren. Fehlen sie, entfallen die beiden
     Slides automatisch. Abgeleitete Werte (z. B. ein fehlendes Quartal aus
     Jahres- minus Neunmonatszahl) in `quarterly_derived_note` dokumentieren.

3. **Generieren:**
   ```bash
   python3 -m instagram.generate --earnings CNC \
     --headline "Turnaround bestätigt — der Q1-Gewinn sprengt die Erwartung"
   ```
   Ohne `--headline` baut der Generator eine Beat-bewusste Hook automatisch.
   **Wichtig:** Die Hook nennt **weder Firmenname noch Ticker** (siehe Design-Regeln).
   Output: `out/instagram/<DATUM>_EARNINGS_<TICKER>/{carousel,reel}/*.png`,
   `caption.txt` **und `carousel_<TICKER>.zip`** (alle Carousel-Slides gebündelt,
   wie bei den Aktienanalysen). **Kein Auto-Upload** — prüfen und manuell posten.

4. **Earnings-JSON committen** (die `out/`-Slides sind gitignored).

### `instagram/data/earnings/<TICKER>.json` — Schema
Claude befüllt die dynamischen Felder aus dem Web. Pflicht: `ticker`, `quarter`,
`report_date`, `source`, `eps_actual`, `eps_estimate`, `eps_surprise_pct`.
```jsonc
{
  "ticker": "CNC",
  "quarter": "Q1 2026",
  "report_date": "2026-04-28",        // Handelstag des Kurssprungs (für RS-JSON-Lookup)
  "source": "SPX",                     // QQQ→rs_full · DAX→rs_dax · SPX→rs_sp500
  "currency": "$",
  "eps_actual": 3.37, "eps_estimate": 2.08, "eps_surprise_pct": 62.0,
  "eps_gaap": 3.11,                    // optional
  "revenue_actual": 49.94, "revenue_estimate": 47.53,
  "revenue_unit": "Mrd. $", "revenue_surprise_pct": 5.1,
  "revenue_yoy_pct": null,             // optional (Beat-Regel: ≥ 0)
  "guidance": "FY2026 adj. EPS-Untergrenze auf > $3,40 angehoben; …",
  "key_metric_label": "Health Benefits Ratio (MCR)",   // die Turnaround-Kennzahl
  "key_metric_value": "87,3 %",
  "key_metric_note": "verbessert — genau die Normalisierung, auf die …",
  "drivers": ["…", "…"],               // 3–4 Treiber-Bullets
  "context": "Was die Zahlen für die These bedeuten (2–3 Sätze).",
  "beat_summary": "Kurz-Zusammenfassung für Slide 2 (optional; sonst auto).",
  "verdict_note": "Warum dieses Verdict trotz Beat (optional; sonst auto aus Analyse).",

  // ── Earnings-Tiefgang (optional; nur wenn Daten aus dem Web vorhanden) ──
  "quarterly_label": "Bereinigtes EPS je Quartal ($)",
  "quarterly_note": "1 Satz zum Trend (z. B. V-Erholung).",
  "quarterly": [                       // Mini-Balkenchart „Gewinn je Quartal"
    {"q": "Q4 24", "eps": 0.80}, {"q": "Q1 25", "eps": 2.90},
    {"q": "Q2 25", "eps": -0.16}, {"q": "Q1 26", "eps": 3.37}
  ],
  "quarterly_derived_note": "Falls ein Quartal abgeleitet ist: Quelle/Rechnung notieren.",
  "segments_note": "1 Satz, was den Umsatz/Beat segmentübergreifend trug.",
  "segments": [                        // Slide „Was den Beat getragen hat"
    {"name": "Medicaid", "metric": "HBR 93,1 %", "note": "…"},
    {"name": "Medicare", "metric": "HBR 84,9 %", "note": "…"}
  ],
  "sources": ["https://…"]             // Quellen-Links (Nachvollziehbarkeit)
}
```
Schnelltest der Datenschicht: `python3 -m instagram.earnings CNC`.

### Slide-Reihenfolge (Earnings, eigenständig — bis zu 14 Slides, Tiefe = USP)
**Earnings-Block (die News):**
1. **Cover** — EARNINGS-Pille + Beat-Hook + Firmenlogo + Hero-Zahlen
   (EPS-Surprise + Kurssprung)
2. **Der Beat in Zahlen** — EPS & Umsatz Ist vs. Erwartung + Kurz-Zusammenfassung
3. **Gewinn je Quartal** — Mini-Balkenchart bereinigtes EPS *(B; nur mit `quarterly`)*
4. **Die Kursreaktion** — 50-Handelstage-Candle-Chart (live aus `data/rs_*.json`)
5. **Ausblick & Treiber** — angehobene Guidance + Turnaround-Kennzahl + Treiber
6. **Was den Beat getragen hat** — Segmente im Detail *(B; nur mit `segments`)*

**Unternehmen & These (aus der Basis-Analyse):**
7. **Was macht das Unternehmen?** — Geschäftsmodell *(A; aus Analyse-Punkt 2)*
8. **Einordnung** — was die Zahlen für die These bedeuten + Verdict + „Warum?"
9. **Bewertung** — Forward-KGV: noch günstig nach dem Pop? *(A; aus Analyse-Punkt 7)*
10. **Qualität auf einen Blick** — 4 Sterne-Ratings *(A; aus Analyse)*
11. **Szenarien · 12–18 Monate** *(aus der Basis-Analyse)*
12. **Langfrist · 3–5 Jahre** *(aus der Basis-Analyse, falls vorhanden)*
13. **Profi-Fazit** *(aus der Basis-Analyse)*
14. **Speichern & mitreden** — Save-CTA + Community-Frage (Turnaround vs. Strohfeuer)

Jede Slide entfällt automatisch, wenn die Daten fehlen: B-Slides (3, 6) nur mit
`quarterly`/`segments` in der JSON; A-/These-Slides (7–13) nur mit passender
Basis-Analyse (neues 11-Abschnitte-Schema); Reaktion (4) nur mit OHLCV. So bleibt
der Post auch ohne Tiefgang-Daten lauffähig (Minimal-Set: 1, 2, 4, 5, 8, 14).
Reel-Teaser (9:16): Slides 1–3 der Analyse (Cover/Zahlen/Reaktion) + Hybrid-CTA.

**Grid-Logik:** Wochenupdate = Equity-Kurve · Analyse = Firmenlogo + Verdict ·
**Earnings = Firmenlogo + grüne EARNINGS/BEAT-Pille** (sofort als Earnings erkennbar).

**Design-Regeln (verbindlich — alle Vorgaben aus dem Review):**
- **Hook (Slide 1) nennt KEINE Aktie** — **kein Firmenname, kein Tickerkürzel**
  (z. B. weder „Centene" noch „(CNC)"). Der Hook ist eine zugespitzte Beat-These
  („Turnaround bestätigt — der Quartalsgewinn schlägt die Erwartung um 62 %"); um
  welchen Wert es geht, zeigen die **Logo-Karte** und die **Zeile darunter**
  (Firma · Sektor). `earnings_headline` erzeugt das automatisch; ein eigenes
  `--headline` wird unverändert übernommen (dann selbst auf diese Regel achten).
- **Bewertungs-Slide: Chips immer linksbündig auffüllen.** Fehlt eine Kennzahl
  (z. B. kein Trailing-KGV), rückt die nächste (Forward-KGV) in die **linke** Spalte
  — nie in die Mitte. Verfügbare Chips in der Reihenfolge Trailing-KGV · Forward-KGV
  · Kurs-Buchwert, max. 2 nebeneinander (`slide_analysis_valuation`).
- **Fehlende Daten NIE als „nicht verfügbar" zeigen.** Sätze/Klauseln wie
  „… nicht verfügbar", „keine Angabe", „n/a" werden in `clean_for_slide` automatisch
  entfernt; der Text muss ohne sie schlüssig weiterlaufen. Generell: nur zeigen, was
  belastbar ist — keine Platzhalter, keine Negativ-Hinweise auf fehlende Daten.
- **Output wie bei den Aktienanalysen:** pro Post die **Einzel-Slides als PNG**
  (`carousel/01_…png …`) **und** ein gebündeltes **`carousel_<TICKER>.zip`** zum
  einfachen Hochladen (erzeugt `build_earnings`, identisch zu `build_analysis`).
- **Slide-Datum (oben rechts) = Tag NACH dem Earningscall** (`report_date` + 1).
  Wird automatisch gesetzt (auch rückwirkend), `--date` überschreibt. So ist der
  Post immer auf den Folgetag der Zahlen datiert. Datum steht nur auf dem Cover.
- **Firmenlogo ab Slide 2 oben rechts auf weißer Karte** (AMD-Logo-Größe), damit
  dunkle/transparente Logos sichtbar sind (`_company_logo_chip` in render.py; gilt
  via `analysis_header` für Analyse- UND Earnings-Innen-Slides). Auf dem Cover sitzt
  das getrimmte, **mittig** (horizontal + vertikal) zentrierte Logo auf der großen
  weißen Karte (`_trim_logo` schneidet transparente UND weiße Ränder weg).
- **Slide 2 „Der Beat in Zahlen":** EPS- + Umsatz-Vergleich Ist/Erwartung; darunter
  eine **Kurz-Zusammenfassung als Text** (Feld `beat_summary`, sonst auto aus den
  Zahlen). **Keine** technischen Chips (kein RS-Score, kein GAAP-EPS).
- **Slide „Die Kursreaktion":** **Tageskerzen der letzten 50 Handelstage (10 × 5)
  bis EINSCHLIESSLICH Meldetag** (kein Tag danach; `reaction_window(before=49,
  after=0)`). Mit **Datums-Achse unten** (Meldetag grün), Preis-Labels links,
  Sprung-Highlight + „+X %"-Callout. Untertitel: „Tageskerzen — die letzten 50
  Handelstage bis zum Meldetag". Hinweis: OHLCV enthält nur **Handelstage** (keine
  Wochenenden/Feiertage) — 50 Kerzen ≈ 10 Kalenderwochen.
- **Slide „Einordnung":** Kontext + Verdict-Badge + **„Warum dieses Verdict?"**
  (Feld `verdict_note`, sonst verdict-bewusster Fallback). Erklärt z. B. HALTEN trotz
  Beat, obwohl der Base Case über dem Kurs liegt (Risiko/Positionsgröße).
- **Vorletzte + letzte Slide (Fazit + CTA):** Tagline lautet exakt
  **„datengetrieben · unabhängig · systematisiert"** (kein „faceless").
- **Reel = Slides 1–3 der Earnings-Analyse** (Cover → Beat in Zahlen → Kursreaktion)
  in **9:16 (1080×1920)** + Hybrid-CTA (Slide 4) **ohne Verdict**, ohne „Profil
  öffnen" (nur Markenname „AI Alpha Selection" + ▲ — kein @-Handle).
  **Format-Hinweis:** Reel ist absichtlich höher als das
  **Carousel (4:5, 1080×1350)** — das ist das Instagram-Reel/Story-Format; der Inhalt
  der wiederverwendeten Slides wird auf dem hohen Canvas automatisch **vertikal
  zentriert** (`dy = (c.H − 1350)//2`), das untere Drittel ist Safe-Zone für die
  Instagram-UI.

**Caption (`caption.txt`):** Kurz-Caption wie beim Analyse-Post — erste Zeile
„<Firma> (TICKER) — Earnings-Analyse Q<N>: Beat" (SEO) + Beat-Einzeiler
(EPS-Überraschung · Kurssprung) + Save-/Folge-CTA + Disclaimer + max. 5
Hashtags (#ticker #earnings #quartalszahlen #aktienanalyse #aialphaselection).
Alle Zahlen und die Einordnung stehen auf den Slides.

---

## Roadmap
- **Jetzt:** wöchentliches Carousel, manueller Upload.
- **Später (genug Follower):** Stories (kurze Updates); Reel-Animation aus den
  9:16-Frames (ffmpeg).
- **Optional:** Auto-Upload via Instagram Graph API (Business-Account).

## Alternativer Modus
Vollständig manueller Wochenreport ohne Stores:
`python3 -m instagram.generate --report instagram/reports/KW<NN>.json`
(Schema: `reports/KW21.example.json`).
