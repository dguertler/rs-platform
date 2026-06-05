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

## 4. Slide-Reihenfolge (Wochenpost, 7 Slides)
1. **Performance vs. NASDAQ-100** (Eye-Catcher) + Kennzahlen-Streifen
   (Gesamtrendite, NASDAQ, Alpha, Trades, Trefferquote, Profitfaktor,
   Ø Gewinn/Trade, Ø Verlust/Trade; `*` = inkl. offener Positionen)
2. **Mehrrendite ggü. NASDAQ-100** (wöchentliche Abweichung, Balken)
3. **Stärkste Positionen** (Top-5 nach Wertzuwachs, mit Kaufdatum + Einstiegskurs)
4. **Aktie der Woche** (rotiert durch ALLE Positionen; Kauf = blaues Signal,
   weitere Signale als blaue Punkte)
5. **Weitere Positionen** (alle außerhalb der Top-5)
6. **Newcomer** (bester Kauf der letzten 3 Wochen, NUR wenn nicht in Top-5)
7. **CTA + Risikohinweis** (Blocksatz, Box unten)

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
| `snapshots/KW<NN>.json` | historischer Depotstand (`base_kw`/`positions`/`closed`) einer vergangenen KW | optional, für Backfill |

**Vergangene Wochen (Backfill):** `python3 -m instagram.generate --kw <NN> --date <Wochendatum>`
nutzt automatisch `snapshots/KW<NN>.json` (falls vorhanden) statt der Live-Daten und
**kappt die Kurse aufs Wochendatum** (`as_of`) → historisch korrekte Slides, ohne die
Live-Daten zu verändern.

## 6. Aktueller Daten-Snapshot (Stand KW23 / 05.06.2026)

**Wikifolio-Werte (EUR):** Start 30.03. = 98,48 →
KW14 105,80 · 15 111,91 · 16 118,55 · 17 126,15 · 18 125,50 · 19 135,98 ·
20 135,44 · 21 139,66 · 22 148,25 · **23 150,08** → Gesamt **+52,4 %**,
NASDAQ **+26,5 %**, Alpha **+25,9 %**, **8/10** Wochen über NASDAQ.
KW23: NDX fiel auf **29.035** (−4,3 % Woche) → Override `nasdaq_value` im
KW23-Eintrag von `wikifolio_history.json` (RS-JSON hatte den Tag noch nicht).

**Positionen (7):** (AMD, LRCX, NXPI in KW23 verkauft)
| Ticker | Name | Kauf | Einstieg € |
|---|---|---|---|
| MRVL | Marvell Technology | 24.03.2026 | 80,07 |
| MU | Micron Technology | 21.05.2026 | 658,47 |
| CNC | Centene | 29.04.2026 | 42,55 |
| WDC | Western Digital | 22.05.2026 | 421,19 |
| STX | Seagate Technology | 21.05.2026 | 676,07 |
| DDOG | Datadog | 15.05.2026 | 178,62 |
| AMAT | Applied Materials | 27.05.2026 | 398,09 |

**Abgeschlossene Trades (19):** NVIDIA +0,39 · Analog Devices +10,99 ·
Akamai −7,58 · ASML −5,28 · Amazon +0,82 · Broadcom +0,11 · Siemens Energy +0,37 ·
Applied Materials +1,08 · Definium Therapeutics +22,32 · ASML +0,63 ·
Credo Technology +0,56 · Alphabet +2,93 · IBM −7,41 · Microsoft −0,68 · NXP +0,30 ·
**AMD +69,7 · Lam Research +29,9 · NXP −6,0 · IBM −12,6** (alle in %, KW23-Verkäufe
mit Chart-Metadaten in `trades.json`). Kennzahlen KW23: 26 Trades, Trefferquote 77 %,
Profitfaktor 12,4, Ø Gewinn +24,5 %, Ø Verlust −6,6 % (inkl. offener Positionen).
**Großer Verkauf KW23 = AMD +69,7 %** → eigener Kauf-/Verkauf-Chart (ersetzt
„Weitere Positionen", Newcomer entfällt; „Aktie der Woche" = MU bleibt).

## 7. Wöchentlicher Ablauf (Kurzform)
```bash
python3 -m instagram.add_week --kw 23 --value <Zertifikatswert> --date 2026-06-05
python3 -m instagram.generate --kw 23          # Carousel + Reel + caption.txt
```
Output: `out/instagram/<DATUM>_KW<NN>/{carousel,reel}/*.png` + `caption.txt`.
Neue Käufe/Verkäufe → `holdings.json` / `trades.json` pflegen.
In einer neuen Session reicht: „Folge instagram/CONTEXT.md, KW23-Wert ist X".

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

**Chart-Konventionen (verbindlich, in `render.py` umgesetzt):**
- Marker-Texte stehen **immer links** der gepunkteten Linie (`ha="right"`, negativer Offset).
- **Kauf = grün**, **Verkauf = rot** (Marker). Der Renditewert (Kachel/Titel) bleibt
  vorzeichenabhängig grün/rot.
- „Großer Verkauf" (|Rendite| ≥ 25 %): eigener Kauf-/Verkauf-Chart (`slide_trade`)
  mit beiden Kursen; ersetzt die **„Weitere Positionen"**-Slide und unterdrückt den
  **Newcomer**. Die rotierende **„Aktie der Woche" bleibt** erhalten.
- Risikohinweis-Box (`slide_cta`): Zeilen werden **pixelbasiert** gefüllt
  (`_wrap_px`), damit der Blocksatz keine großen Lücken erzeugt.
