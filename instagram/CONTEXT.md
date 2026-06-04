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
python3 -m instagram.generate --kw 23          # Carousel + Reel + caption.txt
```
Output: `out/instagram/<DATUM>_KW<NN>/{carousel,reel}/*.png` + `caption.txt`.
Neue Käufe/Verkäufe → `holdings.json` / `trades.json` pflegen.
In einer neuen Session reicht: „Folge instagram/CONTEXT.md, KW23-Wert ist X".

## 8. Offene Punkte / Entscheidungen
- **NDX-Wochenwerte (7 vs. 6):** Die „X von 9 Wochen über NASDAQ" rechnet aus
  dem **QQQ-ETF** (im Repo) = 6/9. Dein wikifolio-Report nutzt den **NASDAQ-100-
  Index (NDX)** = 7/9 (eine Woche, KW16 oder KW20, lag nur −0,1…−0,2 % drunter).
  Fix: in `wikifolio_history.json` je Woche `"nasdaq_pct": <NDX-Wochenrendite>`
  ergänzen → dann 7/9 wie im Report. (Werte vom Nutzer nötig.)
- **Instagram-Handle:** aktuell kein @handle auf den Bildern (nur Markenname).
  Echten Handle in `config.json` → `account` eintragen, falls er erscheinen soll.

## 9. Roadmap
Jetzt: Carousel wöchentlich (manueller Upload). Später: Stories + Reel-Animation
(ffmpeg aus 9:16-Frames). Optional: Auto-Upload via Instagram Graph API.

## 10. Render-Technik
matplotlib + Pillow (kein Browser nötig). Design/Farben/Disclaimer in `theme.py`.
Logo-Reproduktion via `make_logo.py` (durch echtes `assets/Logo.png` ersetzt).
