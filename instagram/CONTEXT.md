# CONTEXT — AI Alpha Selection · Instagram (zentrale Wissensdatei)

> **Für eine neue Claude-Session:** Diese Datei enthält den kompletten Stand des
> Instagram-Projekts. Lies sie zuerst, dann `instagram/PROMPT.md` (detaillierter
> Ablauf). Damit kannst du nahtlos weiterarbeiten. Live-Daten stehen in
> `instagram/data/*.json` — diese Datei beschreibt sie + den aktuellen Snapshot.

---

## 1. Projekt in einem Satz
Faceless-Instagram-Account, der wöchentlich die Performance des wikifolios
**„AI Alpha Selection"** als Carousel (4:5) + Reel-Frames (9:16) bewirbt –
vollautomatisch aus Repo-Daten generiert, **manueller Upload** durch den Nutzer.

## 2. Stammdaten
| Feld | Wert |
|---|---|
| Marke / Account-Name | **AI Alpha Selection** |
| wikifolio-Symbol | `wfdg1983go` |
| wikifolio-URL | https://www.wikifolio.com/de/de/w/wfdg1983go |
| Start | **30.03.2026**, Zertifikatswert **98,48 €** |
| Hauptformat | Carousel 1080×1350; zusätzlich Reel-Frames 1080×1920 |
| Logo | `instagram/assets/Logo.png` (transparent; Blau #2F6BFF + Navy) |
| Instagram-Handle | **noch offen** (Platzhalter entfernt, Markenname statt @handle) |

## 3. wikifolio-Regeln (ZWINGEND — siehe PROMPT.md)
Strikte Trennung **wikifolio/Depot ↔ Zertifikat**. Erlaubt: Strategie, Trades,
Performance des Depots. Verboten: Meinung/Empfehlung zum **Zertifikat**, **ISIN**
nennen, **wikifolio-Logo** ohne Freigabe, sich als wikifolio-Mitarbeiter ausgeben.
Pflicht-Risikohinweis ist in jeder Slide (Footer) + CTA + Caption integriert.
Wort „Musterdepot" wird bewusst NICHT verwendet (es sind reale Käufe).

## 4. Slide-Reihenfolge (Wochenpost, 9 Slides — CTR-/Engagement-Upgrade)
1. **🆕 Dynamic Hook** (Slide 1, visueller Stopper, KEIN Dashboard) — dynamische
   Schlagzeile (`--hook`) + Beweis-Chips Gesamtrendite + Alpha
2. **Performance vs. NASDAQ-100** (Eye-Catcher) + Kennzahlen-Streifen
   (Gesamtrendite, NASDAQ, Alpha, Trades, Trefferquote, Profitfaktor,
   Ø Gewinn/Trade, Ø Verlust/Trade; `*` = inkl. offener Positionen)
3. **Mehrrendite ggü. NASDAQ-100** (wöchentliche Abweichung, Balken)
4. **Stärkste Positionen** (Top-5 nach Wertzuwachs, mit Kaufdatum + Einstiegskurs)
5. **🆕 Strategisches „Warum"** (minimalistische Text-Slide, KI-Kontext) —
   Übergang zu den Einzelaktien; Text aus `--why`
6. **Aktie der Woche** (rotiert durch ALLE Positionen; Kauf = blaues Signal,
   weitere Signale als blaue Punkte)
6a. **Trade der Woche** (NUR wenn diese KW ein Verkauf in `trades.json` liegt):
   größter realisierter Verkauf der Woche, Chart mit **Kauf grün + Verkauf rot**,
   Kacheln „Realisierter Gewinn" + „Verkaufskurs"
7. **Weitere Positionen** (alle außerhalb der Top-5)
8. **Newcomer** (bester Kauf der letzten 3 Wochen, NUR wenn nicht in Top-5)
9. **🆕 CTA + Engagement-Boost + Risikohinweis** — Bio-Link-Pfad (URLs im
   IG-Text nicht klickbar) + dynamische Interaktions-Frage (`--frage`), Box unten

**Dynamische Felder (Claude textet pro Woche, siehe PROMPT.md):** `--hook`
(Schlagzeile), `--why` (KI-Kontext), `--frage` (Kommentar-Frage). Ohne Flags
greifen datenbasierte Fallbacks (`auto_hook/auto_why/auto_question`).

**Slide-Datum (oben rechts):** standardmäßig **Samstag der KW** (`report.slide_date`);
liegt dieser noch in der Zukunft → heute; `--date` überschreibt. So bekommt jede
rückwirkend erzeugte Analyse das passende Wochen-Samstagsdatum.

Rotation Aktie der Woche: `index = (kw - base_kw) % anzahl_positionen`.
Kennzahlen = `trades.json` (abgeschlossen) **+** aktive Positionen (Rendite aus
OHLCV der RS-JSONs). NASDAQ aus QQQ-Benchmark (`data/rs_full.json`).

## 5. Daten-Dateien (Live-Quelle: `instagram/data/`)
| Datei | Inhalt | Pflege |
|---|---|---|
| `config.json` | Symbol, Startdatum/-wert, Name | einmalig |
| `wikifolio_history.json` | Zertifikatswert je KW (+opt. `nasdaq_pct`) | **wöchentlich** |
| `holdings.json` | alle Positionen + Kaufdatum + Einstiegskurs + `base_kw` | bei Kauf/Verkauf |
| `trades.json` | abgeschlossene Trades (realisierte Rendite) | bei Verkauf |

## 6. Aktueller Daten-Snapshot (Stand KW23 / 06.06.2026)

**Wikifolio-Werte (EUR):** Start 30.03. = 98,48 →
KW14 105,80 · 15 111,91 · 16 118,55 · 17 126,15 · 18 125,50 · 19 135,98 ·
20 135,44 · 21 139,66 · 22 148,25 · **23 149,86** → Gesamt **+52,2 %**,
NASDAQ +26,2 %, Alpha +26,0 %, 8/10 Wochen über NASDAQ (QQQ-basiert, siehe §8).

**Positionen (7):**
| Ticker | Name | Kauf | Einstieg € |
|---|---|---|---|
| MRVL | Marvell Technology | 24.03.2026 | 80,07 |
| MU | Micron Technology | 21.05.2026 | 658,47 |
| CNC | Centene | 29.04.2026 | 42,55 |
| WDC | Western Digital | 22.05.2026 | 421,19 |
| STX | Seagate Technology | 21.05.2026 | 676,07 |
| DDOG | Datadog | 15.05.2026 | 178,62 |
| AMAT | Applied Materials | 27.05.2026 | 398,09 |

**KW23-Trades:** Kauf IBM (02.06., 285,95 €). Verkäufe (05.06.):
AMD +69,7 % · Lam Research +29,9 % · NXP −6,0 % · IBM −12,6 % (kurzfristiger
Roundtrip Kauf 02.06./Verkauf 05.06.).

**Abgeschlossene Trades (19):** NVIDIA +0,39 · Analog Devices +10,99 ·
Akamai −7,58 · ASML −5,28 · Amazon +0,82 · Broadcom +0,11 · Siemens Energy +0,37 ·
Applied Materials +1,08 · Definium Therapeutics +22,32 · ASML +0,63 ·
Credo Technology +0,56 · Alphabet +2,93 · IBM −7,41 · Microsoft −0,68 · NXP +0,30 ·
NXP −6,0 · AMD +69,7 · IBM −12,6 · Lam Research +29,9
(alle in %). Kennzahlen KW23: 26 Trades, Trefferquote 77 %, Profitfaktor 9,6,
Ø Gewinn +18,9 %, Ø Verlust −6,6 % (inkl. offener Positionen).

## 7. Wöchentlicher Ablauf (Kurzform)
> ⚠️ **PFLICHT:** Gelieferte Werte (Zertifikatswert + Käufe/Verkäufe) **immer
> zuerst** in `instagram/data/` abspeichern (Schritt 1), dann generieren.
> Details: `PROMPT.md`, „Wöchentlicher Ablauf".
```bash
# 1) Werte persistieren — IMMER zuerst
python3 -m instagram.add_week --kw 23 --value 149.86 --date 2026-06-05
#    Käufe  → holdings.json (Position ergänzen)
#    Verkäufe → holdings.json (Position entfernen) + trades.json (closed: name+ret)
# 2) Generieren
python3 -m instagram.generate --kw 23 \
  --hook  "<dynamische Schlagzeile aus den Wochendaten>" \
  --why   "<KI-Kontext: Sektor/Thema · Marktereignis · Aktie X>" \
  --frage "<Interaktions-Frage zu den Trades der Woche>"
# ohne --hook/--why/--frage greifen datenbasierte Fallbacks
```
Output: `out/instagram/<SAMSTAG-KW>_KW<NN>/`
- `carousel/*.png` — einzelne Slides (werden dem Nutzer einzeln gezeigt)
- `reel/*.png` — Reel-Frames
- `caption.txt` — Caption-Text
- **`carousel_KW<NN>.zip`** — ZIP aller Carousel-PNGs (wird automatisch erstellt,
  für einfachen Download und Upload)

Datum = Samstag der KW, sonst heute; `--date` überschreibt.
Neue Käufe/Verkäufe → `holdings.json` / `trades.json` pflegen.
In einer neuen Session reicht: „Folge instagram/CONTEXT.md, KW23-Wert ist X" —
Claude textet Hook/Warum/Frage selbst aus den Daten.

### Slide-Regeln für rückwirkende / erste Reports
- **Slide 3 (Mehrrendite-Historie) erst ab KW15** (erst ab 2+ Wochen Datenbasis
  sinnvoll). Für KW14 wird Slide 3 automatisch übersprungen.
- **Positionen ohne Kursdaten** (z. B. DFNM/Definium Therapeutics — nicht in
  NASDAQ-100/S&P-500-Daten) erscheinen auf dem Positionen-Slide mit „—" als
  Rendite und werden ans Ende der Liste gesetzt. Kein Ausschluss mehr.
- **Historisch korrekte Performance:** `store.py` begrenzt Kursrenditen via `as_of`
  auf das Berichtsdatum (nicht auf den heutigen Kurs). Korrekt für alle `--kw`-Aufrufe.

### Design-Regeln Wochenbericht-Slides
- **Schriftgrößen**: Alle Wochenbericht-Slides nutzen vergrößerte Fonts. Subtitles
  18 px → 22 px, Listen-Haupttext 30 → 34 px, Untertitelzeilen 22 → 26 px,
  Rendite-Werte 40 → 44 px, Eyebrow-Label 24 → 28 px.
- **CTA-Slide (letzter Slide)**:
  - Kein @-Handle auf dem Bild (Handle gehört in die IG-Bio, nicht in den Post)
  - Frage-Box im Analysis-Stil: PANEL-Hintergrund + blauer Akzentbalken links (8 px),
    „DEINE MEINUNG?"-Label 20 px blau, Fragetext 28 px bold
  - Risikohinweis als Plain-Text (kein roter Kasten), Trennlinie + 12-14 px MUTED,
    analog zur Analyse-Footer-Formatierung

### Historische Snapshots (`instagram/data/snapshots/KW<NN>/`)
Für rückwirkende Wochenberichte legt man Snapshot-Dateien ab:
- `holdings.json` — Depot-Zustand am Ende der Woche
- `trades.json` — abgeschlossene Trades bis zu dieser Woche
`store.py` lädt automatisch den Snapshot wenn er existiert, sonst die Live-Daten.

**Bestehende Snapshots (KW14–KW23, vollständig aus Excel-Transaktionsexport):**
| KW | Positionen am Ende | Neue Closes diese KW |
|---|---|---|
| KW14 | MRVL, DFNM | — |
| KW15 | +LRCX, AMAT, ADI, SNDK, ASML | — |
| KW16 | +MSFT (15.04.), SIEGY (17.04.) | — |
| KW17 | −ASML, −DFNM / +CRDO, AMD, AVGO | ASML +0,65 %, DFNM +22,3 % |
| KW18 | −CRDO, −AMAT / +AMZN, NVDA, CNC, GOOGL | CRDO +0,07 %, AMAT +1,1 % |
| KW19 | −MSFT / +ASML (07.05.) | MSFT −1,3 % |
| KW20 | −SIEGY, AVGO, AMZN / +AKAM, DDOG | SIEGY +0,4 %, AVGO +0,1 %, AMZN +0,8 % |
| KW21 | −ASML, AKAM, ADI / +STX, MU, WDC | ASML −5,2 %, AKAM −7,6 %, ADI +11,0 % |
| KW22 | −NVDA, GOOGL / +NXPI (25.05.), AMAT (27.05.) | NVDA +0,4 %, GOOGL −7,4 % |
| KW23 | −NXPI, AMD, LRCX / +NXPI (307,33 €) | NXPI −6,2 %, AMD +69,6 %, LRCX +29,9 % |

## 8. Offene Punkte / Entscheidungen
- **NASDAQ-Quelle (NDX vs. QQQ):** Es wird jetzt der echte **NASDAQ-100-Index
  `^NDX`** verwendet (exakt wie im wikifolio-Report → 7/9 statt 6/9). `^NDX` wird
  automatisch von `rs_colab.py` (Workflow `update_rs.yml`, täglich) mit nach
  `data/rs_full.json` → `ndx_ohlcv` geladen. `store.py`/`data.py` bevorzugen
  `ndx_ohlcv`, fallback QQQ (`benchmark_ohlcv`). Optionaler Override pro Woche
  via `"nasdaq_pct"` in `wikifolio_history.json` bleibt möglich.
- **Instagram-Handle:** aktuell kein @handle auf den Bildern (nur Markenname).
  Echten Handle in `config.json` → `account` eintragen, falls er erscheinen soll.

## 9. Roadmap
Jetzt: Carousel wöchentlich (manueller Upload). Später: Stories + Reel-Animation
(ffmpeg aus 9:16-Frames). Optional: Auto-Upload via Instagram Graph API.

## 10. Render-Technik
matplotlib + Pillow (kein Browser nötig). Design/Farben/Disclaimer in `theme.py`.
Logo-Reproduktion via `make_logo.py` (durch echtes `assets/Logo.png` ersetzt).

**Verbindliche Slide-Konventionen** (Details + Begründung: `PROMPT.md`,
„Standard-Konventionen für Charts & Slides"):
- Chart-Marker: **Kauf = grün, Verkauf = rot** (rote Marker aus `trades.json`,
  wenn `ticker` + Verkaufsdatum gesetzt sind).
- Listen-Slides (Stärkste/Weitere Positionen): Detailzeile unter dem Ticker
  **groß & gut lesbar** (Größe 22, `T.SUBTLE`).
- **Single Source of Truth:** alle neuen Vorgaben/Details werden sofort in den
  Repo-MD-Dateien (`PROMPT.md`/`CONTEXT.md`) festgehalten — nicht nur im Chat.

## 11. Zweiter Post-Typ: Aktien-Analyse-Posts  (★ HIER WEITERARBEITEN)
Neben dem Wochenupdate werden **fertige KI-Analysen** (`analyses/TICKER.md`) als
**Carousel (volle Analyse) + Reel-Teaser (Reichweite)** gepostet — Ziel **1–2/
Woche**. Vollständiger Standard/Ablauf/SEO: `PROMPT.md`, Abschnitt „Zweiter
Post-Typ: AKTIEN-ANALYSE". Dieser Abschnitt = Kurz-Stand zum Weitermachen.

**Befehl (erzeugt alles auf einmal):**
```bash
python3 -m instagram.generate --analysis AMD \
  --headline "AMD: Nvidias einziger echter Rivale — Kauf oder Hype?"
```
Output `out/instagram/<DATUM>_ANALYSE_<TICKER>/`:
`carousel/` (10 PNG) · `reel/` (4 PNG) · **`reel.mp4`** · `caption.txt` ·
**`reel_script.txt`**. Nichts wird hochgeladen — manuell posten.

**Karussell (10 Slides, volle Tiefe = USP):** Cover (Frage-Hook + Logo) ·
Gesamteinschätzung+**Sterne** · Szenarien 12–18M (%+Kursziele) · Geschäftsmodell ·
Szenarien erklärt · **Bewertung „KGV-Illusion"** · **Risiko & Realitätscheck** ·
Langfrist 3–5J · Profi-Fazit · **Speichern & mitreden** (Community-CTA).
**NICHT** auf den Slides: aktueller Kurs, GWS-Ampel/Breakout (Punkt 9) — wird per
`analysis.clean_for_slide()` aus allen Texten gefiltert.

**Reel = Teaser (4 Frames + Hybrid-CTA):** Hook → Szenarien → Das Wichtigste →
„ganze Analyse im Karussell auf meinem Profil". Zwei Video-Wege:
`reel.mp4` (einfach, Ken-Burns, sofort postbar) **und** `reel_script.txt`
(Voiceover + KI-Prompt für InVideo/Veo/CapCut → cineastisches Reel).

**Grid-Logik:** Wochenpost = AI-Alpha-Marke; Analyse = **Firmenlogo** der AG auf
weißer Karte + Verdict-Badge (BUY grün / HOLD gelb / WATCH-SELL rot).

**Marken-Tagline (Fazit + „Speichern & mitreden"-Slide):** exakt
**„datengetrieben · unabhängig · systematisiert"** (kein „faceless") — einheitlich
für Analyse- und Earnings-Posts.

**Hook:** Cover + Reel tragen eine **Frage/These** (erste 3 Sek). Ohne
`--headline` autogeneriert (verdict-bewusst, pro Ticker variiert); für beste
Wirkung pro Post eine **individuelle** `--headline` setzen.

**Code-Karte:**
- `instagram/analysis.py` — Parser für `analyses/TICKER.md` (Verdict/Score/
  Sterne/Wahrscheinlichkeiten/Kursziele/Geschäftsmodell/Peers/KGV-Multiples),
  `clean_for_slide()` (Kurs/GWS raus), `sentences()` (abkürzungssicher),
  `short_name()`, `analysis_headline`-Daten.
- `instagram/render.py` — `slide_analysis_*` (Cover, Verdict, Szenarien,
  Business, Cases, Valuation, Risk, Longterm, Fazit, CTA) + `slide_reel_*`
  (Hook, Szenarien, Takeaway, Hybrid-CTA) + `analysis_headline()` + `_logo_card`.
- `instagram/generate.py` — CLI `--analysis` / `--headline`; `build_analysis`,
  `build_analysis_reel`, `caption_analysis`, `reel_script`.
- `instagram/video.py` — `build_reel_video()` (MP4 via imageio-ffmpeg).
- `instagram/assets/logos/<TICKER>.png` — Firmenlogos (siehe dortige README).

**Schema-Hinweis:** Nur **17 von 55** Analysen folgen dem neuen 11-Abschnitte-
Schema mit %/Kurszielen (AMD, SNDK, MU, AMAT, MRVL, STX, NXPI, KLAC, NTAP, LITE,
AKAM, HPE, IBM, MGM, SM, CNC, F). Alt-Schema → Tiefen-/Szenario-Slides entfallen
automatisch (kürzeres Carousel, dafür „Chancen & Risiken"). Für volle Posts die
Analyse zuvor nach `analyses/PROMPT.md` neu erzeugen.

**Offene Punkte / nächste Schritte:**
- **Logo-Workflow:** Firmenlogos als `<TICKER>.png` unter
  `instagram/assets/logos/` ablegen (GitHub-Upload oder lokaler Push). **PNG
  mit weißem oder transparentem Hintergrund** — beides funktioniert, da
  `_trim_logo` automatisch weiße UND transparente Ränder abschneidet. Logo
  erscheint auf der weißen Cover-Karte und oben rechts auf allen Innen-Slides.
  Fehlt ein Logo → Wortmarke (Fallback). Auto-Download in der Cloud geblockt.
- Optional: individuelle Headlines für die 17 Ticker vorbereiten;
  Reel-MP4-Feintuning (Tempo/Textgröße); Stories; Auto-Upload via Graph API.
- Abhängigkeiten: `pip install -r instagram/requirements.txt` (matplotlib,
  numpy, Pillow, imageio, imageio-ffmpeg, **pyphen**).

## 11b. Dritter Post-Typ: Earnings-Analyse-Posts

Aus einem **Quartalsbericht mit Beat** wird ein eigenständiger Carousel-Post
(bis zu 14 Slides — Tiefe = USP) + Reel-Teaser, mit **Fokus auf dem
Earnings-Ereignis**. Vollständiger Ablauf + JSON-Schema + Design-Regeln:
`PROMPT.md`, Abschnitt „Dritter Post-Typ: EARNINGS-ANALYSE".

**Befehl** (die Hook nennt **weder Firmenname noch Ticker** — siehe Design-Regeln):
```bash
python3 -m instagram.generate --earnings CNC \
  --headline "Turnaround bestätigt — der Q1-Gewinn sprengt die Erwartung"
```
Output `out/instagram/<DATUM>_EARNINGS_<TICKER>/`: `carousel/` (bis zu 14 PNG) ·
`reel/` (4 PNG) · `caption.txt` · **`carousel_<TICKER>.zip`** (alle Slides
gebündelt, wie bei den Aktienanalysen). Nichts wird hochgeladen — manuell posten.

**Drei Datenquellen:**
1. `instagram/data/earnings/<TICKER>.json` — Beat-Zahlen **aus dem Web** (EPS
   Ist/Erwartung/Surprise, Umsatz, Guidance, Turnaround-Kennzahl, Treiber,
   Kontext). Claude befüllt + committet die Datei (yfinance ist in der Cloud
   geblockt → Zahlen aus IR/SEC-8-K/Finanzportalen).
2. **Kurssprung + Reaktions-Chart** — live aus `data/rs_*.json` berechnet.
   `price_jump()` und `reaction_window()` verwenden **`reaction_date`** (falls
   vorhanden) sonst `report_date`. `reaction_date` muss gesetzt werden, wenn
   die Zahlen **nach Marktschluss** kamen (After-Hours) — dann ist der Kurssprung
   am Folgetag. NICHT in der JSON dupliziert.
3. **Basis-Analyse** `analyses/TICKER.md` (Pflicht) — Verdict/Szenarien/Kursziele/
   Fazit. Fehlt sie → zuerst Analyse erzeugen; ist sie älter als der Earnings-
   Termin → vorher neu generieren.

**Beat-Kandidaten** liefert der bestehende `check_earnings.py` (tägliche
Earnings-Mail/Telegram): ≥ 5 % Kurssprung **+** ≥ 10 % EPS-Surprise **+** Umsatz
YoY ≥ 0. Dieselben Schwellen sind in `instagram/earnings.py` gespiegelt.

**Slide-Reihenfolge:** Cover (EARNINGS/BEAT-Pille + Beat-Hook + Logo + Hero-Zahlen)
· Der Beat in Zahlen (EPS+Umsatz Ist/Erwartung) · Die Kursreaktion (Candle-Chart,
Sprungtag markiert) · Ausblick & Treiber (Guidance + Turnaround-Kennzahl) ·
Einordnung (+ Verdict-Badge) · Szenarien 12–18M · Langfrist 3–5J · Profi-Fazit ·
Speichern & mitreden. Datengetriebene Slides entfallen automatisch, wenn Felder
fehlen.

**Grid-Logik:** Wochenpost = Equity-Kurve · Analyse = Logo + Verdict-Badge ·
**Earnings = Logo + grüne EARNINGS/BEAT-Pille** (akzentfarbe Grün=Beat / Rot=Miss).

**Design-Regeln (Round 12/13 — verbindlich):**
- Slide-Datum oben rechts = **Tag nach dem Earningscall** (`report_date`+1, auto).
- **After-Hours-Sonderfall:** Bei Zahlen nach Marktschluss (z. B. GOOGL 29. Apr.)
  `report_date` = Earnings-Tag, `reaction_date` = Folgetag (Kurssprung-Tag).
  Beide Felder zusammen ergeben korrektes Datum + korrekten Kurssprung.
- Firmenlogo **ab Slide 2 oben rechts auf weißer Karte** (AMD-Größe) —
  `_company_logo_chip()`; auf dem Cover getrimmt & mittig auf großer weißer Karte
  (`_trim_logo` schneidet transparente UND weiße Ränder weg).
- Slide 2 ohne RS-Score/GAAP-Chips, dafür `beat_summary`-Text.
- Slide 3 Chart = **Tageskerzen, letzte 50 Handelstage (10×5) bis zum Meldetag**
  (`reaction_window(before=49, after=0)`) mit **Datums-Achse unten** + Preis-Labels
  links. OHLCV hat nur Handelstage → 50 Kerzen ≈ 10 Kalenderwochen.
- **„Ausblick" und „Die Treiber" sind IMMER zwei separate Slides:**
  Slide „Ausblick" = Guidance-Kachel + Turnaround-Kennzahl.
  Slide „Die Treiber" = alle Driver-Bullets. Kein Mischen mehr.
  Funktionen: `render.slide_earnings_ausblick` / `render.slide_earnings_treiber`.
- **Overflow-Regel (gilt für alle Slides):** Sobald eine Box oder ein Text
  den unteren Bildbereich berühren würde (footer_y = Canvas-H − 200),
  kommt der Inhalt auf eine Folgefolie. Gilt für Treiber-Bullets UND Segment-Boxen.
- **Slide „Was den Beat getragen hat" (Segmente):** Automatischer Seitenumbruch
  via `_seg_pages()` in `generate.py` — emit mehrere `segmente`/`segmente_2`-Slides
  wenn nötig. Metriken vertikal gestapelt: absoluter Wert (32 px, T.TEXT, mono) +
  Prozentwert (26 px, Akzentfarbe, mono). Notizen: TY_BODY=28, T.TEXT.
- Slide „Einordnung": `verdict_note` erklärt das Verdict (z. B. HALTEN trotz Beat,
  weil Base Case zwar über Kurs, aber binäres Risiko).
- Fazit + CTA-Tagline: **„datengetrieben · unabhängig · systematisiert"**.
- **Reel = Slides 1–3 der Analyse** (Cover/Zahlen/Reaktion) + CTA (Slide 4) ohne
  Verdict, ohne „Profil öffnen" (nur Handle + ▲). Reel = **9:16 (1080×1920)**,
  Carousel = **4:5 (1080×1350)** → wiederverwendete Slides werden auf dem hohen
  Canvas automatisch vertikal zentriert (`dy=(c.H−1350)//2`).

**Code-Karte:**
- `instagram/earnings.py` — `load_earnings()` (JSON + Kurssprung aus RS-JSON +
  geparste Basis-Analyse unter `e["analysis"]`), `price_jump()`,
  `reaction_window()`, `fmt_num`/`fmt_pct`/`fmt_pct_pts`. Schnelltest:
  `python3 -m instagram.earnings CNC`.
- `instagram/render.py` — `slide_earnings_*` (cover, numbers, **quarterly**,
  reaction, guidance, **segments**, context, **ratings**, cta) + `slide_earnings_reel_*`
  + `earnings_headline()` + `_stat_tile`/`_eyebrow_pill`. Reused aus der Analyse:
  `slide_analysis_business/-valuation/-scenarios/-longterm/-fazit` (aus `e["analysis"]`).
- **Tiefgang-Slides:** A = aus der Basis-Analyse (Geschäftsmodell, Bewertung,
  Sterne, Szenarien, Langfrist, Fazit). B = aus Earnings-JSON-Feldern `quarterly`
  (Mini-Balkenchart bereinigtes EPS, V-Turnaround) + `segments` (Segment-Treiber).
  Jede Slide entfällt ohne ihre Daten. Bis zu 14 Slides; Minimal-Set ohne
  Tiefgang-Daten: Cover/Zahlen/Reaktion/Ausblick/Einordnung/CTA.
- `instagram/generate.py` — CLI `--earnings` / `--headline`; `build_earnings`,
  `build_earnings_reel`, `caption_earnings`.
- `instagram/data/earnings/<TICKER>.json` — persistierte Beat-Zahlen (Beispiel:
  `CNC.json` — Q1 2026, +62 % EPS-Surprise, +14 % Kurssprung).

**Wichtig (Render-Engine):** Dollarzeichen in Texten werden NICHT als
LaTeX-Mathmodus interpretiert (`matplotlib.rcParams["text.parse_math"] = False`
in render.py) — sonst würden „$3,37 …" kursiv und ohne Leerzeichen gesetzt.

**Status / Beispiel:** CNC Q1 2026 (Earnings 28.04.) ist vollständig umgesetzt &
getestet (`instagram/data/earnings/CNC.json`). Nächste Schritte: weitere
Beat-Ticker aus der Earnings-Mail als Posts; Firmenlogos hochladen.

## 12. Design-System & Typografie-Regeln (render.py — verbindlich für alle Slide-Typen)

Alle drei Post-Typen (Wochenpost + Analyse + Earnings) verwenden **dieselbe** Render-Engine
(`instagram/render.py`). Folgende Regeln gelten für alle Slides — Änderungen
hier immer in render.py umsetzen und als Konstante/Parameter fixieren.

### 12.1 Farbschema (`instagram/theme.py`)
| Konstante | Hex | Einsatz |
|---|---|---|
| `BG` | `#0E1320` | Slide-Hintergrund (Navy) |
| `PANEL` | `#172131` | Kachel-/Tile-Hintergrund |
| `PANEL_HI` | `#1F2A3D` | hellere Kachel (Tags etc.) |
| `GREEN` | `#22D3A0` | BUY · positiv · Depot |
| `RED` | `#FF5C6C` | SELL · negativ · Bear |
| `BLUE` | `#2F6BFF` | Markenakzent · Base · Alpha |
| `AMBER` | `#F5B43C` | HOLD · WATCH · neutral |
| `TEXT` | `#FFFFFF` | Haupttext |
| `MUTED` | `#8A93A6` | Sekundärtext / Labels |
| `GRID` | `#232E42` | Trennlinien |

### 12.2 Schrift (`register_fonts()`)
- **Liberation Sans** (Regular + Bold) — Körpertext, Headlines, Labels
- **DejaVu Sans Mono** (Bold) — Zahlen, Kursziele, Prozente, Scores
- DPI = 150; Größen in *Pixel* (intern zu Punkt: `px * 72 / 150`)

### 12.3 Typografie-Konstanten (nach `MX = 90` in render.py)
```python
TY_H1      = 42   # Slide-Hauptüberschrift
TY_SUB     = 22   # Subtitle / Kontext-Zeile (MUTED)
TY_BODY    = 28   # Fließtext (Investment-Case, Szenarien, Fazit usw.)
TY_BODY_LH = 44   # Zeilenabstand zu TY_BODY
MX         = 90   # Seitenrand links/rechts in px
```
**Regel:** Alle neuen Fließtext-Slides verwenden `TY_BODY`/`TY_BODY_LH`.
Alle H1-Überschriften `TY_H1`. Alle Subtitles `TY_SUB` in `T.MUTED`.
Rating-Labels, Firmenname, Kachel-Beschriftungen: `TY_BODY`, `color=T.TEXT`.
Footer-Disclaimer: 16 px, `color=T.MUTED`.

### 12.4 Textausrichtung & Zeilenumbruch (gültig für Deutsch + Englisch)

**Standard: linksbündig** (`justify=False` in `_draw_paragraph`).
Blocksatz (`justify=True`) nur für abgegrenzte Boxen wie den CTA-Disclaimer.

**Bindestrich-Darstellung (Deutsch + Englisch) — REGEL (Round 8):**
Zusammengesetzte Wörter bleiben **genau so wie sie sind** (`CUDA-Moat` bleibt `CUDA-Moat`,
`GPU-Mix` bleibt `GPU-Mix`). Das frühere `re.sub` das `Text - Text` aus `Text-Text` machte
wurde **entfernt** — sah falsch aus und brach Fachbegriffe auseinander.

**Pyphen-Silbentrennung am Zeilenumbruch bleibt aktiv:** Lange Wörter ohne Bindestrich
(≥ 10 Zeichen) werden am letzten passenden Silbenpunkt getrennt. Der Trennstrich
erscheint nur am echten Zeilenende — nicht im Wortinneren.

**Zeilenumbruch:** `_wrap_px(text, px_width, size, factor=0.50, lang="de")`
- `factor=0.50` entspricht der durchschnittlichen Zeichenbreite von Liberation
  Sans (0.50 × Schriftgröße px), gibt ~64 Zeichen/Zeile bei 28 px / 900 px Breite.
- `lang="de"`: aktiviert **pyphen-Silbentrennung** (`de_DE`-Wörterbuch).
  Lange deutsche Komposita (≥ 10 Zeichen, kein echter Bindestrich) werden am
  **rechtesten passenden Silbenpunkt** getrennt; Trennstrich erscheint **nur am
  echten Zeilenende** — nie mitten im Wort.
- `lang=None`: Silbentrennung deaktiviert (für englische Texte).

**Äquivalenz CSS ↔ Python (zur Orientierung):**
| CSS | Python-Äquivalent |
|---|---|
| `text-align: left` | `justify=False` (Standard) |
| `hyphens: auto; lang="de"` | `_wrap_px(..., lang="de")` via pyphen |
| `word-break: break-word` | `break_long_words=True` in textwrap |
| `text-align: justify` + Hyphens | `justify=True` nur mit `lang="de"` |

### 12.5 Slide-Layout-Muster (für neue Slides)

**Header (`analysis_header`):** Brand-Logo links (52 px), Firmen-Logo rechts (52 px,
`T.company_logo_file(ticker)`), Trennlinie bei y=140. Kein ANALYSE-Tag mehr.

**Cover (`slide_analysis_cover`):** Kein AKTIENANALYSE-Tag oben links. Headline
direkt ab y=140. Firmename/Sektor: `TY_BODY`, `color=T.TEXT`. Rating-Labels
(Wachstum, Qualität, ...): `TY_BODY`, `color=T.TEXT`.

**Verdict-Badge:** Score als "80 von 100 Punkten" (nicht "/100"). Label-Zeile
"EINSCHÄTZUNG" in `TY_BODY`, `color=T.TEXT`.

```python
def slide_analysis_NEU(c, a, date_iso):
    analysis_header(c, a, date_iso)               # Header + Trennlinie bei y=140
    c.text(MX, 184, "Titel", TY_H1, weight="bold")
    c.text(MX, 240, "Untertitel", TY_SUB, color=T.MUTED)
    txt = A.clean_for_slide(a["sections"].get(N, ""))
    _draw_paragraph(c, MX, 304, txt, TY_BODY, c.W - 2 * MX,
                    color=T.TEXT, line_h=TY_BODY_LH, max_lines=20)
    analysis_footer(c)                             # Linie + Disclaimer 16 px bei y=H-150
```

**Verfügbare Textfläche** (Carousel 1080×1350):
- Content-Bereich: y=160 … y=1200 (nach Header/vor Footer) = ~1040 px
- Body-Text ab y=304: ~896 px / TY_BODY_LH=44 ≈ **20 Zeilen** ohne max_lines-Limit

### 12.6 Wochenpost-Slides (dieselben Regeln)
Alle `slide_performance`, `slide_history`, `slide_list`, `slide_featured` etc.
verwenden denselben `MX=90`, dieselben Farben und dieselbe Footer-Funktion.
Textgröße für Kachel-Zahlen: 34–64 px (je Wichtigkeit), Labels immer `MUTED`.
Das `_draw_paragraph`-Muster wird auch im Wochenpost genutzt (z. B. Hook-Text).

### 12.7 Konsistenz-Checkliste für neue Slides
- [ ] `analysis_header` / `analysis_footer` aufrufen (Analyse-Posts)
- [ ] Überschrift: `TY_H1=42`, bold; Subtitle: `TY_SUB=22`, `color=T.MUTED`
- [ ] Fließtext: `TY_BODY=28`, `TY_BODY_LH=44`, `justify=False` (Standard)
- [ ] Labels/Firmennamen/Rating-Beschriftungen: `TY_BODY`, `color=T.TEXT`
- [ ] Silbentrennung: `_wrap_px` automatisch via `lang="de"` (kein manuelles Eingreifen)
- [ ] Bindestrich in Komposita: unveränderlich lassen (`CUDA-Moat` bleibt `CUDA-Moat`); kein `re.sub`
- [ ] Kein aktueller Kurs, keine GWS-/Breakout-Nennungen → `A.clean_for_slide()`
- [ ] Disclaimer: `DISCLAIMER_ANALYSE_SHORT` im Footer 16 px (kein wikifolio-Bezug)
- [ ] Verdict-Badge: Score als "X von 100 Punkten", kein "/100"
- [ ] Cover: kein AKTIENANALYSE-Tag; Header: kein ANALYSE-Tag
- [ ] Header rechts: Firmen-Logo (52 px), kein Ticker-Tag

### 12.8 Caption-Aufbau (generate.py `caption_analysis`) — Round 10

Die Caption ist eine **inhaltliche Ergänzung zu den Slides**, keine Zusammenfassung.
Die "💡 Nicht auf den Slides"-Sektion enthält exklusiven Content der Caption.

Reihenfolge:
1. Titel + Verdict + Score
2. Hook-Satz (Section 1)
3. Business-Bullets (Section 2, max 4 → wird beim Kürzen reduziert)
4. Szenarien 12-18M mit Wahrscheinlichkeit + Kursziel (+ Zusammenfassung wenn Platz)
5. Langfrist-Spannen (3-5J)
6. Rating-Sterne
7. Fazit-Kernaussage
8. Vergleichbare Titel (Peers)
9. **💡 Nicht auf den Slides** (caption-exklusiv, IMMER vollständig, nie beim Kürzen weglassen):
   - **EPYC vs. Intel**: AMD gewinnt Rechenzentrums-CPU-Marktanteile (aus Sections 2+3)
   - **TSMC-Abhängigkeit**: Fabless-Modell, 3nm/5nm-Kapazität + CoWoS-Packaging (IMMER wenn in Sec2)
   - **HBM-Risiko**: HBM3e von SK Hynix/Samsung, Lieferketten-Engpass (IMMER wenn in Sec2)
   - **D/E-Ratio + Bilanz**: Verschuldungsgrad + FCF (aus Section 6, regex: `D/E`)
   - **Analyst-Konsensus**: Kursziel vs. aktueller Kurs (aus Section 7, regex: Konsensus|Konsensziel)
10. Folge-CTA
11. Disclaimer
12. Hashtags (25–30 Tags, maximale Algorithmus-Reichweite)

**Kürzungsreihenfolge** bei Überschreitung des 2.200-Zeichen-Limits (Python `len()`):
Bullets 4→3→2→0, Cases-Zusammenfassung, Langfrist — "Weitere Details" bleibt IMMER drin.

**Hashtag-Strategie** (22–25 zielgerichtete Tags, Round 11):
- Basis (12): `#aktien #aktienanalyse #aktienmarkt #börse #boersewissen #geldanlage #finanzbildung #vermögensaufbau #wachstumsaktien #börsentipps #investing #stockanalysis`
- Ticker + Stock-Tag (2): `#{tic} #{tic}stock` (z.B. #amd + #amdstock)
- Sektor Technology (5): `#halbleiter #semiconductor #chips #technologieaktien #techaktien`
- Themen-Tags (aus Bullets erkannt): GPU/KI → `#ki #aistock #aiinvesting #datacenter #gpu #aiinfrastructure`; EPYC/CPU → `#cpu #serverchips`
- Peer-Tags (max 2, aus a["peers"]): automatisch aus der Analyse (z.B. #nvda #avgo)
- Brand (1): `#aialphaselection`
- Entfernt (zu unspezifisch/falsch): `#kisemiconductor #fabless #stockpicking #momentum #aiaccelerator`

**ZIP-Download**: `build_analysis` erstellt nach dem Rendern automatisch `carousel_{TICKER}.zip`
mit allen Carousel-PNGs im Output-Ordner. Wird in der `saved`-Liste zurückgegeben und im Output angezeigt.

**Slide 12 (Fazit) CTA-Box:** "Weitere Details zur Analyse in der Caption" (nicht auf vollständigen Text verweisen).

### 12.9 Slide-spezifische Layout-Regeln

**Cover (Slide 1) — Round 9:**
- Hook: 60 px, Zeilenabstand 74, Start y=170
- BUY-Verdict: Hook **immer** `"Kaufen — oder schon zu spät?"` — **KEIN Aktienname im Hook** (pool[0] = `"Kaufen — oder schon zu spät?"`, kein `{name}:` Präfix). In `analysis_headline()`: `if v == "BUY": return buy[0]`
- Logo-Karte: zentriert zwischen Hook-Ende und gesamtem unteren Block (via chain_h)
- Aktienname + Sektor: **direkt unter der Logo-Karte** (y = card_top + card_h + 16)
- **Visueller Abstand Name → Verdict-Badge: `logo_name_gap = 70` px** — Logo und Aktienname stehen allein oben, erst dann folgen die grauen Boxen
- Verdict-Badge + Rating-Blöcke: nach dem Abstand, bis Footer
- chain_h berücksichtigt `logo_name_gap`: `card_h + 16 + sub_h + logo_name_gap + verdict_h + 14 + ratings_h + 10`
- Rating-Labels: 24 px (eine Größe kleiner als TY_BODY), Sterne unter den Labels

**Business-Slide (Slide 3) — Round 8:**
- Box-Höhe **dynamisch** pro Bullet: `pad_top + n_head*TY_BODY_LH + n_body*TY_BODY_LH + pad_bot`
- Blaue Überschriften und Body-Text: beide TY_BODY=28, line_h=TY_BODY_LH
- Jede Box hat immer eine blaue Überschrift (bei fehlendem " — "-Trenner: erste 5 Wörter als Titel)
- Titeltext wird geWrapped (kein Überlaufen der Box)
- **Jargon-Vereinfachung:** `_simplify_bullet()` in render.py ersetzt Fachbegriffe vor dem Rendern:
  - `"TSMC-Leading-Edge-Allokation und CoWoS-Packaging-Kapazität"` → `"TSMC-Fertigungskapazität für die neusten Chips"`
  - `"Datacenter-GPU-Mix-Verschiebung hebt Gruppen-Marge strukturell"` → `"Mehr GPU-Umsatz verbessert die Gesamtmarge dauerhaft"`
  - `"Operativer Hebel:"`, `"Fabless-Modell:"` → entfernt (Resttext bleibt)
  - `"niedrigmargigere"` → `"margenschwächere"`, `"Cash-Sockel"` → `"stabile Cashflow-Basis"`
- Boxes die footer_y=c.H-160 überschreiten: werden abgebrochen

**Szenarien-Slide (Slide 4) — Round 8:**
- Box-Höhe rh=180 (content-fit: Wahrscheinlichkeit + Kursziel passen rein)
- **Wahrscheinlichkeit-Label y+36** (war y+22), **Wert y+58** (war y+44)
- **Kursziel-Label y+114** (war y+100), **Wert y+136** (war y+122)
- Mehr Abstand von der Case-Überschrift, optisch klar getrennt

**Cases-Blöcke (Slides 5+6+) — Round 8:**
- Wahrscheinlichkeit + Kursziel in EINER Zeile rechts: `"45%  ·  560–700 $"` — Position y+36 (mehr Abstand zur Case-Überschrift)
- Overflow-Split in generate.py: findet automatisch wieviele Items auf eine Slide passen
  (avail=890px: c.H-160 - top0=300). Kann 3 Slides erzeugen (szenarien_erklaert_1/2/3)
- _draw_cases_blocks bricht NICHT ab — die Split-Logik in generate.py ist dafür zuständig

**Fundamentals-Slide (Slide 7) — Round 11:**
- Oben 2 Kennzahl-Tiles nebeneinander (gap=26, ch=140):
  - Links: D/E-Verhältnis (grün) — regex `r'D/E[^0-9]*([0-9]+(?:[,.][0-9]+)?)'` aus Section 6
  - Rechts: Free Cashflow (blau) — regex `r'FCF\s*\$\s*([0-9]+[,.][0-9]+)\s*(Mrd|Mio)'` aus Section 6
  - Darunter: Fließtext Section 6, max_lines=14

**Bewertungs-Slide (Slide 8) — Round 11:**
- Oben 2 KGV-Tiles (Trailing rot / Forward grün, ch=150)
- Darunter: **Analysten-Konsensus-Tile** (amber, h=120) — regex
  `r'Analyst-?Konsens(?:us|ziel)\s*\$\s*([0-9]+(?:[,.][0-9]+)?)'` aus Section 7
  Text: "Ø Kursziel: 472 $" + rechts "Coverage hinkt der Rally hinterher"
- Darunter: Fließtext Section 7, max_lines=11
- "Trailing-KGV": Label "optisch teuer · Basiseffekt" (nicht "Artefakt")

**Risk-Slide (Slide 9) — Round 11:**
- Positions-Warn-Box: Text-Größe TY_BODY=28 (gleich wie der weiße Text darunter)
- **HBM-Lieferkettenrisiko-Box** (amber, h=24+TY_BODY+24) wenn "HBM" in Section 2:
  `c.text(MX+34, y+24, "HBM-LIEFERKETTENRISIKO", TY_BODY, color=T.AMBER, weight="bold")`
  Rechts: "SK Hynix / Samsung" — max_lines=14 für den Fließtext darunter

**Profi-Fazit (Slide 12) — Round 11:**
- CTA-Box ohne Caption-Verweis: "Folge für wöchentliche Profi-Analysen" + "datengetrieben · unabhängig · faceless"
- Kein "Weitere Details in der Caption" — alle Infos sind auf den Slides
- `max_lines` **dynamisch** berechnet: `max(4, int(((c.H-160) - 256 - 120 - 40 - peers_reserve) / TY_BODY_LH))`
  (peers_reserve=100 wenn Peers vorhanden, sonst 0) → ca. 15 Zeilen, nie mehr abschneiden
- Markdown-Tabellen + Disclaimer aus Section 11 vor dem Rendern entfernen:
  `re.sub(r'\s*-{3,}\s*\|.*', '', raw11, flags=DOTALL)` + `re.sub(r'\|[^\n]*', '', raw11)`
  + `re.sub(r'\*?Keine Anlageberatung[^*\n]*\*?', '', raw11)`
  + `re.sub(r'Verdict:\s*\w+\s*\(\d+/\d+\)[^\n]*', '', raw11)`

**Allgemeine Regeln — Round 11 (aktualisiert):**
- **Ausnahmslos echte Umlaute** (ä, ö, ü, Ä, Ö, Ü, ß) in allen deutschen Strings — niemals ae/oe/ue/ss
- Keine hardcodierten `--headline` Argumente mit ASCII-Ersatz übergeben (auto-Headline verwendet korrekte Umlaute)
- **Hook-Texte enthalten KEINEN Aktiennamen** — nur die generische Frage/These
- **Bindestrich in Komposita: unveränderlich** (`GPU-Mix` bleibt `GPU-Mix`). Kein `re.sub` in `_wrap_px`
- Pyphen-Silbentrennung bei langen Wörtern (≥10 Zeichen) am Zeilenende: aktiv und erwünscht
- Graue Boxen: Höhe immer dynamisch berechnet (an Text angepasst)
- Wenn Box/Text Footer-Linie überschreitet: weiterer Slide (Overflow-Split in generate.py)

### 12.10 AMD-Analyse: Abdeckung auf den Slides (Vergleich)

**Abgedeckt auf den Slides:**
- Investment-Case (Slide 2): AMD als glaubwürdige Nr. 2 im KI-Beschleuniger-Markt, MI300 als CUDA-Alternative
- Szenarien 12-18M (Slide 4): Bull 750-900$ 30%, Base 560-700$ 45%, Bear 280-380$ 25%
- Bull/Base/Bear erklärt (Slides 5+6): ROCm-Gap, Margin-Expansion, CUDA-Moat, Custom Silicon
- Fundamentale Qualität (Slide 7): Gross Margin 53%, Operating Margin 14,4%, FCF 7,2B, ROE 8,1%
- Bewertung KGV (Slide 8): Trailing-PE 173x vs. Forward-PE 39,7x (Pre-Inflection-Artefakt)
- Risiko & Psychologie (Slide 9): RS-Score 311, Beta 2,4, FOMO-Magnet, Positionsgröße max 3-4%
- Technisches Bild (Slide 10): SMA50 ~347, SMA200 ~243, Warnsignal SMA20 ~466
- Langfrist 3-5J (Slide 11): Bull 1000-1400$, Base 600-850$, Bear 250-400$
- Profi-Fazit (Slide 12): BUY 80/100, Beta + Forward-PE = 30-40% Drawdowns möglich
- Peers (Slide 12): NVDA, AVGO

**In der Caption (automatisch extrahiert via "Weitere Details"-Block):**
- D/E-Verhältnis 6 (Bilanz solide)
- Analysten-Konsensus $472 < aktueller Kurs $516 (Abdeckung läuft Rally nach)
- HBM-Speicher von SK Hynix/Samsung (Verfügbarkeitsrisiko)
- TSMC-Fabless (wenn nicht schon in Business-Bullets)

**Bewusst weggelassen (zu technisch für IG-Publikum):**
- Jahrestarget EPS $18-22 (Bull), Forward-EPS-Revisionen aufwärts (Base)
- ROCm-Architektur-Details (CUDA-Gap)
- Beta 2,4 → bereits auf Risiko-Slide erwähnt

