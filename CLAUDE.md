# RS-Platform — Claude Code Anweisungen

## Git-Regeln

- Alle Änderungen direkt auf `master` pushen (kein Feature-Branch, kein PR, außer explizit gewünscht)
- **Bei jedem Commit den Git-Hash im Chat ausgeben**, z.B.: `[a3f92c1] Commit-Nachricht`
- Commit-Messages auf Deutsch oder Englisch, klar und beschreibend

## Analyse-Workflow

Wenn der Nutzer schreibt `Analysiere TICKER`:

1. **Fundamentaldaten laden** aus `data/fundamentals.json`:
   ```python
   import json
   fund = json.load(open('data/fundamentals.json'))['tickers']['TICKER']
   ```

2. **RS-Daten laden** aus dem passenden RS-JSON:
   ```python
   # NASDAQ-100 → data/rs_full.json
   # DAX-40    → data/rs_dax.json
   # S&P 500   → data/rs_sp500.json
   rs = next(e for e in json.load(open('data/rs_full.json'))['data'] if e['ticker']=='TICKER')
   ```

3. **`analyses/PROMPT.md` lesen** — dort stehen Analyse-Struktur, Prompt und alle Formatregeln

4. **`analyses/sndk.md` als Format-Referenz** für den Aufbau der Ausgabe nutzen

5. **Analyse generieren** — Claude Code ist das LLM, kein externer API-Call

6. **Dateien schreiben** via `write_rating()` aus `generate_rating.py`:
   ```python
   import sys; sys.path.insert(0, '.')
   from generate_rating import write_rating
   write_rating(ticker, analysis_text, rs_score, windows, gws)
   ```
   Schreibt automatisch:
   - `analyses/TICKER.md` — Markdown-Analyse
   - `data/ratings/TICKER.html` — HTML für das Frontend
   - `data/ratings/index.json` — Index-Eintrag

7. **Committen und pushen**:
   ```bash
   git add analyses/TICKER.md data/ratings/TICKER.html data/ratings/index.json
   git commit -m "Analyse: TICKER — Verdict (Score X/100)"
   git push origin master
   ```
   → Git-Hash danach im Chat ausgeben

## Datenquellen

| Datei | Inhalt | Aktualisierung |
|---|---|---|
| `data/fundamentals.json` | yfinance-Fundamentals (476+ Ticker) | Jeden Montag automatisch |
| `data/rs_full.json` | NASDAQ-100 RS-Scores + OHLCV | Täglich automatisch |
| `data/rs_dax.json` | DAX-40 RS-Scores + OHLCV | Täglich automatisch |
| `data/rs_sp500.json` | S&P 500 RS-Scores + OHLCV | Täglich automatisch |
| `analyses/PROMPT.md` | Vollständiger System-Prompt | Manuell gepflegt |

## Batch-Empfehlung

Max. **5 Ticker pro Session** für optimale Kontext-Qualität.
Beispiel: `Analysiere MU ARM AMD MRVL ON`

## Instagram & wikifolio (Doku ausschließlich im Repo)

Sämtliche Details zu Instagram-Post **und** wikifolio-News-Feed werden
ausschließlich unter `instagram/` gepflegt — **nicht** in dieser Datei.
Bei Triggern wie `Instagram KW<NN>`, `Wochenfeed KW<NN>`,
„Erstelle Instagram-Post" / „wikifolio-Wochenbericht":

1. **`instagram/CONTEXT.md`** lesen (zentrale Wissensdatei, aktueller Stand).
2. Dann je nach Aufgabe **`instagram/PROMPT.md`** (Instagram-Slides) bzw.
   **`instagram/wikifolio_feed/FORMAT.md`** (wikifolio-News-Feed).
