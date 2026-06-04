# Instagram-Generator — AI Alpha Selections

Erzeugt automatisiert Slides (PNG) + Caption für Instagram aus den
vorhandenen Repo-Daten. **Lädt nichts hoch** — du prüfst alles und postest
manuell. Faceless, markenkonsistent, mit Pflicht-Disclaimer.

## Installation

```bash
pip install -r instagram/requirements.txt
```

## Nutzung

**Wochenmodus (Hauptfall)** — aus deinem wikifolio-Wochenreport:

```bash
python3 -m instagram.generate --report instagram/reports/KW21.example.json
```

Erzeugt das komplette Wochen-Carousel (Hook, Performance, Kennzahlen,
Wochen-Historie, Käufe, Top-Positionen, Verkäufe, CTA) +`caption.txt`.
→ Ablauf & Regeln: **`instagram/PROMPT.md`**.

**Auto-Modus** — Signale direkt aus den Repo-Daten (ohne Wochenreport):

```bash
python3 -m instagram.generate                      # beide Formate
python3 -m instagram.generate --format carousel --signals 3
```

Output: `out/instagram/<DATUM>[_KW<NN>]/{carousel,reel}/NN_*.png` + `caption.txt`.

> ⚖️ **wikifolio-Regeln** (Trennung Musterdepot/Zertifikat, keine ISIN, kein
> wikifolio-Logo, Pflicht-Disclaimer) sind in `PROMPT.md` dokumentiert und im
> Generator umgesetzt.

## Wikifolio-Performance

Die echte Equity-Kurve liegt **nicht** im Repo. Zwei Wege:

1. **Automatisch** (lokal, offenes Netz):
   ```bash
   python3 -m instagram.fetch_wikifolio --symbol DEIN_SYMBOL
   ```
   → schreibt `data/wikifolio_performance.json`.
   *In der Claude-Cloud blockt wikifolio.com (403), daher dort nicht testbar.*

2. **Manuell**: `data/wikifolio_performance.example.json` nach
   `data/wikifolio_performance.json` kopieren und Werte eintragen.

Fehlt die Datei, rendert der Generator mit klar markierten **BEISPIELDATEN**.
Die NASDAQ-100-Vergleichslinie kommt real aus `data/rs_full.json` (QQQ).

## Aufbau

| Datei | Zweck |
|---|---|
| `theme.py` | Farben, Fonts, Canvas-Größen, Disclaimer-Texte |
| `data.py` | Lädt Signale, RS/OHLCV, Benchmark, Performance |
| `render.py` | Zeichnet die einzelnen Slides (matplotlib) |
| `generate.py` | CLI: baut Slide-Set + Caption |
| `fetch_wikifolio.py` | Holt die Equity-Kurve (best effort) |

## Slide-Reihenfolge

1. Hook (große Performance-Zahl)
2. Performance vs. NASDAQ-100
3. Kennzahlen (Rendite, Outperformance, Signale, Titel)
4…n. Einzelne Trade-Signale (Chart + Marker)
letzte. CTA + Risikohinweis

## Anpassen

- **Design**: Farben/Fonts in `theme.py`.
- **Mehr/weniger Signale**: `--signals N`.
- **Reel-Video**: die 9:16-Frames lassen sich später mit ffmpeg zu einem
  animierten Reel zusammensetzen (separater Schritt).
