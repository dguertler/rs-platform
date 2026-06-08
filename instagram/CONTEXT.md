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

## 6. Aktueller Daten-Snapshot (Stand KW22 / 04.06.2026)

**Wikifolio-Werte (EUR):** Start 30.03. = 98,48 →
KW14 105,80 · 15 111,91 · 16 118,55 · 17 126,15 · 18 125,50 · 19 135,98 ·
20 135,44 · 21 139,66 · **22 148,25** → Gesamt **+50,5 %**, NASDAQ +32,2 %,
Alpha +18,3 %, 6/9 Wochen über NASDAQ (QQQ-basiert, siehe §8).

**Positionen (10):**
| Ticker | Name | Kauf | Einstieg € |
|---|---|---|---|
| MRVL | Marvell Technology | 24.03.2026 | 80,07 |
| AMD | AMD | 22.04.2026 | 247,73 |
| LRCX | Lam Research | 08.04.2026 | 205,07 |
| MU | Micron Technology | 21.05.2026 | 658,47 |
| CNC | Centene | 29.04.2026 | 42,55 |
| WDC | Western Digital | 22.05.2026 | 421,19 |
| STX | Seagate Technology | 21.05.2026 | 676,07 |
| DDOG | Datadog | 15.05.2026 | 178,62 |
| AMAT | Applied Materials | 27.05.2026 | 398,09 |
| NXPI | NXP Semiconductors | 25.05.2026 | 282,16 |

**Abgeschlossene Trades (15):** NVIDIA +0,39 · Analog Devices +10,99 ·
Akamai −7,58 · ASML −5,28 · Amazon +0,82 · Broadcom +0,11 · Siemens Energy +0,37 ·
Applied Materials +1,08 · Definium Therapeutics +22,32 · ASML +0,63 ·
Credo Technology +0,56 · Alphabet +2,93 · IBM −7,41 · Microsoft −0,68 · NXP +0,30
(alle in %). Kennzahlen KW22: 25 Trades, Trefferquote 80 %, Profitfaktor 21,0,
Ø Gewinn +25,4 %, Ø Verlust −4,8 % (inkl. offener Positionen).

## 7. Wöchentlicher Ablauf (Kurzform)
```bash
python3 -m instagram.add_week --kw 23 --value <Zertifikatswert> --date 2026-06-05
python3 -m instagram.generate --kw 23 \
  --hook  "<dynamische Schlagzeile aus den Wochendaten>" \
  --why   "<KI-Kontext: Sektor/Thema · Marktereignis · Aktie X>" \
  --frage "<Interaktions-Frage zu den Trades der Woche>"
# ohne --hook/--why/--frage greifen datenbasierte Fallbacks
```
Output: `out/instagram/<SAMSTAG-KW>_KW<NN>/{carousel,reel}/*.png` + `caption.txt`
(Datum = Samstag der KW, sonst heute; `--date` überschreibt).
Neue Käufe/Verkäufe → `holdings.json` / `trades.json` pflegen.
In einer neuen Session reicht: „Folge instagram/CONTEXT.md, KW23-Wert ist X" —
Claude textet Hook/Warum/Frage selbst aus den Daten.

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
- **Logos hochladen:** Firmenlogos fehlen noch (Auto-Download in der Cloud
  geblockt). Datei als `instagram/assets/logos/<TICKER>.png` ins Repo legen
  (z. B. GitHub-Upload) → echtes Logo erscheint auf der weißen Cover-Karte.
- Optional: individuelle Headlines für die 17 Ticker vorbereiten;
  Reel-MP4-Feintuning (Tempo/Textgröße); Stories; Auto-Upload via Graph API.
- Abhängigkeiten: `pip install -r instagram/requirements.txt` (matplotlib,
  numpy, Pillow, imageio, imageio-ffmpeg).
