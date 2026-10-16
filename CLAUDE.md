# RS-Platform — Claude Code Anweisungen

## Git-Regeln

- Alle Änderungen direkt auf `master` pushen (kein Feature-Branch, kein PR, außer explizit gewünscht)
- **Cloud-/Web-Sessions mit vorgegebenem Arbeits-Branch** (z. B. `claude/...`):
  auf den Arbeits-Branch **und zusätzlich direkt auf `master`** pushen (Fast-Forward,
  kein PR nötig) — beide Refs bleiben synchron
- **Bei jedem Commit den Git-Hash im Chat ausgeben**, z.B.: `[a3f92c1] Commit-Nachricht`
- Commit-Messages auf Deutsch oder Englisch, klar und beschreibend

## Doku-Pflege-Regeln (gilt für ALLE MD-Dateien im Repo)

- Neue Vorgaben des Nutzers sofort in der zuständigen MD-Datei festhalten —
  dabei die veraltete Aussage **ersetzen**, nicht als neue „Runde"/Notiz anhängen
- Jede Regel lebt an genau **einer** Stelle (Single Source of Truth):
  - Analyse-Prompt → `analyses/PROMPT.md` (keine Kopie im Code)
  - Instagram-Workflow & -Regeln → `instagram/PROMPT.md`
  - Instagram-Projektstand, Daten-Snapshot, Code-Karte → `instagram/CONTEXT.md`
- **Keine manuell gepflegten Zähler/Stände** in der Doku (z. B. „X von Y
  Analysen") — solche Werte bei Bedarf per Skript/grep frisch ermitteln
- Zahlen in Doku-Snapshots stammen immer aus den JSON-Dateien
  (`instagram/data/*.json`) — die JSONs sind führend, nie umgekehrt

## Analyse-Workflow

Wenn der Nutzer schreibt `Analysiere TICKER`:

1. **Fundamentaldaten laden** aus `data/fundamentals.json`:
   ```python
   import json
   fund = json.load(open('data/fundamentals.json'))['tickers']['TICKER']
   ```

   **Earnings-Check (PFLICHT, autark vor jeder Analyse):** Prüfen, ob TICKER
   in den letzten 7 Tagen einen Earnings-Termin hatte (z. B. via
   `yfinance.Ticker(TICKER).calendar` oder bekanntes Berichtsdatum). Falls ja:
   Wochen-Cache aus `data/fundamentals.json` NICHT unverändert verwenden.
   - **Bevorzugt:** `fetch_fundamentals(TICKER)` aus `generate_rating.py` für
     einen erzwungenen Live-Fetch dieses einen Tickers aufrufen.
   - **Fallback, falls yfinance/Yahoo Finance netzwerkseitig blockiert ist**
     (z. B. 403 auf Proxy-Ebene in Cloud-Sessions): Per WebSearch die
     Earnings-Kennzahlen recherchieren (EPS actual/estimate/surprise,
     Umsatz YoY, Guidance) und diese **Key Facts zuerst im Chat ausgeben**,
     bevor die Aktienanalyse folgt. Die recherchierten Werte fließen
     qualitativ in die Analyse ein (Cache-Fundamentaldaten gelten dafür als
     ggf. veraltet).
   Grund: Der automatische 5 %-Preis-Gap-Trigger in `load_fundamentals()`
   greift nur bei starker Kursreaktion — ein Earnings-Beat/-Miss kann
   Fundamentaldaten (Revenue, Margen, EPS) spürbar verändern, ohne dass der
   Kurs um mehr als 5 % reagiert.

2. **RS-Daten laden** aus dem passenden RS-JSON:
   ```python
   # NASDAQ-100 → data/rs_full.json
   # S&P 500   → data/rs_sp500.json
   # Smallcap  → data/rs_smallcap.json
   rs = next(e for e in json.load(open('data/rs_full.json'))['data'] if e['ticker']=='TICKER')
   rs_score  = rs['score']        # Feldname ist 'score', NICHT 'rs_score'
   rs_rank   = rs['prev_rank']    # Feldname ist 'prev_rank', NICHT 'rank'
   windows   = rs['windows']
   gws       = rs.get('gws')      # None bei Smallcaps — dann gws_smallcap-Dict übergeben:
   # gws = gws or {"weekly": False, "daily": False, "h4": False, "points": 0, "signal_type": "Smallcap"}
   ```

   **Zombie-Stock-Filter (PFLICHT vor jeder Analyse):**
   ```python
   fund = json.load(open('data/fundamentals.json'))['tickers']['TICKER']
   market_cap = fund.get('marketCap') or 0
   if market_cap < 5_000_000:
       print(f"ZOMBIE-STOCK: {TICKER} MCap ${market_cap:,.0f} — keine Analyse, kein write_rating().")
       # Stattdessen nur kurze Chat-Ausgabe: "TICKER — AVOID (Zombie-Stock, MCap < $5M)"
       # STOP — nicht weiter analysieren
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

8. **Chat-Ausgabe:** Nur die Zusammenfassungs-Tabelle ausgeben — KEINE vollständige Analyse im Chat. Format:

   | Ticker | Name | Kurs | RS | Verdict | Ratings | Handlungsempfehlung |
   |--------|------|------|-----|---------|---------|----------------------|
   | TICKER | Name | $X | Score (Rank) | **VERDICT** | Q· G· V· K· · EV ±X% | **Empfehlung** |

   **Handlungsempfehlung (PFLICHT bei jeder Analyse-Ausgabe im Chat)** — klare
   Kauf-/Nicht-Kauf-Aussage, mechanisch aus `verdict` und `funnel_veto.decision`
   (`data/ratings/index.json`) abgeleitet, nicht neu interpretiert:
   - `funnel_veto.decision == "VETO"` → **Nicht kaufen**
   - `verdict == "AVOID"` → **Nicht kaufen**
   - `verdict == "WATCH"` → **Nicht kaufen (nur beobachten)**
   - `verdict == "HOLD"` → **Halten, kein Neukauf**
   - `verdict == "BUY"` und `funnel_veto.decision == "REDUCE"` → **Kaufen (reduzierte Position)**
   - `verdict == "BUY"` und `funnel_veto.decision` in (`"PASS"`, fehlt) → **Kaufen (volle Position)**

   Bei REDUCE/VETO den Grund aus `funnel_veto.reason` in einem Halbsatz
   ergänzen (z. B. „wegen Kundenkonzentration"). Gilt für Einzelanalysen
   genauso wie für Batch-Ausgaben (siehe „Batch-Empfehlung" unten).

### Automatik-Modus: `aktienanalyse` ohne Ticker

Schreibt der Nutzer nur `aktienanalyse` (ohne Ticker-Liste), werden die zu
analysierenden Ticker automatisch aus dem zuletzt per Mail/Telegram
versendeten Breakout-Alert ermittelt statt manuell übergeben:

1. **Letzten Alert-Batch laden** aus `data/last_breakout_alerts.json`
   (`sent_at`, `alerts`-Liste mit `ticker`/`source`; wird von
   `stock_alerts.yml` — Breakout-Alarm 2→3 Punkte, Di–Sa 02:00 UTC via
   `check_alerts.py` — bei jedem Lauf überschrieben und enthält daher immer
   nur die zuletzt an Mail+Telegram verschickte Charge, keinen Verlauf).
2. **Letzten Scan-Zeitpunkt** aus `analyses/.last_stock_alert_scan` lesen
   (ISO-Timestamp). Fehlt die Datei (erster Lauf): den aktuellen Batch trotzdem
   verarbeiten.
3. `sent_at` des Batches <= gespeichertem Scan-Zeitpunkt → kurze Chat-Meldung
   „Keine neuen Breakout-Alerts seit TIMESTAMP." und STOP, kein
   Dateizugriff/Commit.
4. Ticker aus `alerts` extrahieren (Feld `ticker`), nach Ticker
   deduplizieren. Feld `source` gibt direkt die passende RS-Quelle vor
   (`QQQ`→`data/rs_full.json`, `SPX`→`data/rs_sp500.json` — siehe
   Schritt 2 oben).
5. **Für jeden Ticker automatisch, ohne Rückfrage, direkt im selben Lauf**
   den vollständigen Analyse-Workflow oben (Schritte 1–8: Fundamentaldaten,
   Earnings-Check, RS-Daten, Zombie-Stock-Filter, Prompt, Analyse
   generieren, `write_rating()`, committen) durchführen — inkl.
   Git-Hash-Ausgabe je Ticker.
6. `analyses/.last_stock_alert_scan` mit dem `sent_at` des verarbeiteten
   Batches überschreiben, committen und auf `master` pushen.
7. **Am Ende** die Zusammenfassungstabelle (Schritt 8 oben) für alle Ticker
   des Batches zusammen ausgeben, plus die EV/Risiko-Tabelle wie im
   Abschnitt „Batch-Empfehlung" unten beschrieben (gilt automatisch, sobald
   mehr als ein Ticker im Batch war).

## Datenquellen

| Datei | Inhalt | Aktualisierung |
|---|---|---|
| `data/fundamentals.json` | yfinance-Fundamentals (476+ Ticker) | Jeden Montag automatisch |
| `data/rs_full.json` | NASDAQ-100 RS-Scores + OHLCV (4H-Kerzen über Alpaca, `alpaca_live.py`; Yahoo nur als Ersatz) | Täglich automatisch |
| `data/rs_sp500.json` | S&P 500 RS-Scores + OHLCV (4H-Kerzen über Alpaca wie `rs_full.json`) | Täglich automatisch |
| `data/earnings_alerts_log.json` | Event-Log gesendeter Earnings-Alerts (Global-Scan + Live-Premarket), je Eintrag mit `trigger` (`eps-beat` / `kursreaktion`) und `eps_distorted` — Basis für den `earning`/`earningsanalyse`-Automatik-Modus | Laufend automatisch (bei jedem Alert) |
| `data/last_breakout_alerts.json` | Zuletzt per Mail+Telegram versendete Breakout-Alert-Charge (2→3 Punkte) — Basis für den `aktienanalyse`-Automatik-Modus, wird bei jedem Lauf überschrieben (kein Verlauf) | Di–Sa 02:00 UTC automatisch (`stock_alerts.yml`) |
| `data/watchlist.json` | Beobachtete Ticker — Grundlage der Verkaufs- und SL-Verschiebungs-Meldungen (in der täglichen Breakout-Mail). Führende Quelle; die Watchlist-Seite liest sie beim Laden und schreibt Änderungen direkt zurück (GitHub-Contents-API, Token pro Gerät im localStorage). Ohne Token bleibt die Liste lokal und lässt sich über „exportieren" als Datei ablegen | Laufend über `frontend/watchlist.html` |
| `data/open_signals.json` | Offene 4H-Breakout-Signale der Watchlist-Titel inkl. Einstieg, Stopp und zuletzt gemeldetem wirksamen SL (`sl_level`), plus bereits abgeschlossene Signale — Verkäufe (Stopp, Trendumkehr = Schluss unter dem Tief, aus dem das letzte Hoch entstand; Verkauf zur Eröffnung am Folgetag; vor Earnings Verkauf zum Schluss der 14-Uhr-Kerze am letzten Handelstag davor, außer der Trade hatte schon einen Schluss ≥ 2R — identisch in `check_exits.py` und `frontend/backtest_logic.js`) und SL-Verschiebungen stehen in derselben Mail wie die Breakouts. **Jedes Verkaufssignal kommt genau einmal per Mail** — auch bei gerade erst erfassten Positionen; ein Earnings-Termin, der vor dem ersten geprüften Tag lag, löst nicht nachträglich aus | Di–Sa 02:00 UTC automatisch (`stock_alerts.yml` → `check_alerts.py` → `check_exits.process_watchlist`) |
| `data/live_depot.json` | Modell-Depot der verschickten Breakouts (höchstens 10 Positionen) — entscheidet in der Breakout-Mail über „Kauf“ oder „Kein Kauf – 10 von 10 Plätzen belegt“; beim ersten Lauf aus den seit 22.09.2026 verschickten 4H-Alerts rekonstruiert | Di–Sa 02:00 UTC automatisch (`stock_alerts.yml`) |
| `data/intraday_alert_state.json` | Zuletzt geprüfte 4H-Kerzen des 4H-Prüfjobs (`check_alerts_4h.py`): prüft 20 Min. nach dem Schluss der Kerzen 10–14 und 14–18 Uhr Berliner Zeit (Kerzen wie TradingView ab 10/14/18/22 Uhr) die Top-20-Titel zeitpunktgenau und schickt bei neuem 4H-Breakout sofort die Kaufmail (Kauf zur nächsten Kerze, Kauffenster 10:00–22:10); Kerzen mit Schluss 22 bzw. 2 Uhr meldet der Nachtlauf | Mo–Fr 12:20/13:20/16:20/17:20 UTC automatisch (`stock_alerts_4h.yml`) |
| Branch `backtest-data-sp500` | Historischer S&P-500-Backtest (Top 20 point-in-time ab 2016, identische Pipeline und Engine wie NASDAQ-100, Benchmark ^GSPC wie `sp500_colab_1.py`): `sp500_results.json` + Kursdateien je Aktie unter `charts/` — eigener Branch, weil zu groß für `master` | Manuell über `backtest_history_sp500.yml` |
| `data/backtest_history/ndx_membership.json` | Tagesgenaue NASDAQ-100-Zusammensetzung ab 01.02.2007 (Quelle: github.com/jmccarrell/n100tickers, MIT) — Grundlage für Universum und rückwirkendes Top-20-Ranking in `rs_full.json` (Tabelle = heutige Mitglieder, jeder Tag rankt nur die damaligen Mitglieder) und für den historischen Backtest | Täglich mit `update_rs.yml`, zusätzlich bei jedem Lauf von `backtest_history.yml` |
| `data/backtest_history/sp500_membership.json` | Tagesgenaue S&P-500-Zusammensetzung ab 1996 (Quelle: github.com/fja05680/sp500, MIT; die offizielle FMP-/Wikipedia-Liste wird als letzte Änderung eingespielt) — Grundlage für das rückwirkende Top-20-Ranking in `rs_sp500.json`; Universum = heutige Mitglieder plus Watchlist-Titel ohne Index (nur Kursdaten, kein Ranking) | Täglich mit `update_sp500.yml` |
| `data/backtest_history/ndx_results.json` | Historischer Backtest NASDAQ-100 (Top 20 point-in-time) mit der Live-Logik (3 von 3 Punkten, Einstieg über 4H, Zeitstopp 10 Handelstage / +5 %) ab 2016 — 4H-Kerzen über Alpaca (Secrets `ALPACA_API_KEY`/`ALPACA_API_SECRET`); Mitglieder ab 2016, die Yahoo nicht mehr führt, mit Alpaca-Tageskerzen; Depot-Simulation (100.000 €, 10.000 € je Trade, höchstens 10 Plätze, Zinseszins); je Aktie die Kerzen in `data/backtest_history/charts/TICKER.json`. Grundlage für Studien — eine eigene Seite gibt es nicht mehr (B-ÜBERSICHT/B-DETAILS rechnen mit derselben Engine und denselben Alpaca-4H-Kerzen) | Manuell über `backtest_history.yml` (Yahoo ist aus Cloud-Sessions gesperrt) |
| `data/backtest_ndx.json` | NASDAQ-100-Backtest seit 2016 für B-ÜBERSICHT (Jahrestabelle NASDAQ-100 / Rendite / Gewinn / PF, Depot 100.000 €, 10 Plätze) und Grundlage der Trades auf B-DETAILS: **zeitpunktgenau wie live** (`simulateTradesPIT` in `frontend/backtest_logic.js`: Signal an jedem 4H-Kerzenschluss mit Wochen-/Tageskerze nur bis jetzt, Kauf zur nächsten 4H-Kerze bzw. 10 Uhr am nächsten Handelstag). Kurse = historischer Lauf (`backtest_history/charts`) + tägliche `backtest_TICKER.json`, Top 20 danach aus `rs_full.json`. Schalter auf B-ÜBERSICHT: „Top 20 am Tradetag“ (Standard = System, nur Trades von Aktien, die am Signaltag in den Top 20 standen) oder „Alle Signale“ derselben Aktien ohne Top-20-Filter zum Vergleich (Kennzahlen, Jahrestabelle, Aktienliste; Depot eigens gerechnet, `allSignals` in `data/backtest_ndx.json`). Die frühere Wochenzeilen-Rechnung (`simulateTrades`) prüfte die Punkte erst zum Wochenschluss und buchte den Kauf rückwirkend (Vorgriff) — nicht mehr für die Seiten verwenden | Täglich mit `update_backtest_daily.yml` (`node backtest_ndx.js`) |
| `data/live_alerts.json` / `data/live_alerts_performance.json` | Echte Live-Bilanz: alle protokollierten Breakout-Alerts mit Kennzeichen, ob sie verschickt wurden (Top 20 zum Versandzeitpunkt, aus der Git-Historie bzw. seit 09/2026 aus `in_top20` in `signals.json`), und jeder verschickte Alert als Trade (Kauf zur Eröffnung am Alert-Tag, Stopp/Ausstieg wie Backtest-Engine) — Anzeige oben auf `frontend/backtest_overview.html` (B-ÜBERSICHT, `frontend/live_alerts_panel.js`) | Täglich mit `update_backtest_daily.yml` (`live_alerts/reconstruct_alerts.py` + `live_alerts/evaluate_alerts.js`) |
| `data/earnings_history.json` | Earnings-Termine je Ticker mit Uhrzeit (`bmo` vor Börsenbeginn / `amc` nach Börsenschluss / `unk`), vergangen und kommend — Grundlage der Earnings-Regel in Backtest und Live: **kein Kauf weniger als 4 Kalendertage vor den Zahlen**, offene Positionen **zum Schluss der 14-Uhr-Kerze (18:00) am letzten Handelstag vor den Zahlen verkaufen** (nach Börsenschluss: derselbe Tag; vor Börsenbeginn/unbekannt: Vortag), **außer der Trade hatte vorher schon einen Schluss ≥ Einstieg + 2R** (dann durch die Zahlen halten). Live ergänzt um den nächsten Termin aus `earnings_calendar.json` | Sonntags automatisch (`fetch_earnings_history.yml`, Yahoo) |
| `analyses/PROMPT.md` | Vollständiger System-Prompt | Manuell gepflegt |
| `data/reference_trades.json` | Freigegebene Referenz-Trades (Signal-Kerze, Kauf, Ausstiegstag + Begründung) — Regressionsschutz für Logik-Änderungen, siehe „Referenz-Trades“ | Manuell, nur auf Freigabe des Nutzers |

## Logik-Anpassungen & Logik-Verbesserungen (Workflow)

Gilt, sobald es um Signal-, Einstiegs-, Ausstiegs- oder Depotlogik geht (z. B. „ist
dieser Trade richtig?", „Stopp/Ausstieg ändern", „neue Regel", „rechne durch, ob …").
Jeder Chat kann damit ohne Vorwissen weiterarbeiten. **Jede Logik-Änderung gilt immer
für Backtest und Live** (Seiten, Mails, Modell-Depot) — nie nur für eines von beiden.

### Aktueller Logik-Stand (Backtest = Live)

- **Signal:** 4H springt auf grün (Schluss über der 4H-Marke), Weekly und Daily sind zu
  diesem Zeitpunkt grün, Titel am Signaltag in den Top 20 (NASDAQ-100). Nur 4H als
  letzter Punkt löst aus — Weekly/Daily als letzter Punkt bewusst nicht (getestet,
  schwächer). Kauf zur nächsten 4H-Kerze (Kerzen 10–14/14–18 Uhr) bzw. 10 Uhr am
  nächsten Handelstag. Code: `pitSignals`/`simulateTradesPIT` in
  `frontend/backtest_logic.js`, live `check_alerts.py`/`check_alerts_4h.py`
- **Daily-Marke — Ausbruch bestätigt das Swing-Tief (seit 12.10.2026):** Ein Swing-Tief
  braucht sonst zwei Folgekerzen. Ist das Tief der vorletzten Kerze ein tieferes Tief und
  schließt die letzte Kerze über dem höchsten Swing-Hoch seit dem letzten Swing-Tief, ist
  diese Marke sofort gebrochen — Daily wird mit derselben Kerze grün wie 4H (AVGO
  21.08.2023: Tief 18.08. bei 78,18, Marke 82,28 vom 15.08., Schluss 83,30 → Signal 18:00,
  Kauf 22.08.; über alle Top-20-Signale 6 Trades neu, 1 weg, Gewinnsumme 256.906 € →
  253.812 €, PF 1,65 → 1,64). Code: `provisionalMark` in `frontend/backtest_logic.js` und
  `frontend/rs_charts.js`, live `gws_core.provisional_mark_break` (`check_alerts.py`).
  Studie ohne: `BACKTEST_NDX_OUT=/tmp/x.json node backtest_ndx.js --ohne-fruehbruch`
- **Signal halten (Weekly und Daily, seit 12.10.2026):** Bildet ein tieferes Tief eine
  neue Marke (Trendumkehr), bleibt die Ebene grün, solange kein Schluss unter dem
  **Anker** der zuletzt gebrochenen Marke liegt — **Weekly: letztes Swing-Tief vor der
  Ausbruchswoche** (Woche mit dem ersten Tagesschluss über der Marke), **nachgezogen** bei jedem
  erneuten Ausbruch (Wochenschluss über dem letzten bestätigten Swing-Hoch → Swing-Tief davor) und
  gebrochen, sobald ein **Wochentief darunter** liegt — auch schon, solange die gebrochene Marke
  noch gilt und die Trendumkehr noch keine neue Marke gebildet hat (seit 13.10.2026; PANW:
  Ausbruch über 95,44 Woche 28.02.2022, Anker 77,75 vom 21.02., Wochentief 09.05.2022 bei 75,05 →
  Weekly rot bis 22.02.2023, Trades 02.06./05.07./22.08.2022 entfallen; ZS: Woche 08.01.2024
  schließt bei 230,77 über 227,29 vom 25.12.2023 → Anker 206,67 vom 01.01., Woche 19.02. Tief
  202,44 → Weekly rot bis 10.06.2024; über alle Top-20-Signale gegenüber festem Anker mit
  Tagesschluss 102 Trades weg (−350 €), 14 neu (−884 €), PF 1,77 → 1,82, Gesamtrendite verkettet
  +671,0 % → +700,6 %, größter Rückgang −49.093 € → −45.709 €, Depot +440,3 % → +481,6 %; davor
  tiefstes Tief und Wochenschluss: PF 1,75), **Daily: letztes
  Swing-Tief vor der Trendumkehr, das sie noch nicht unterschritten hat**, geprüft ab der
  Trendumkehr und gesucht höchstens bis zum Swing-Tief vor dem Ausbruch (der grünen Linie im
  Chart); liegt die Trendumkehr darunter, gilt dieses Swing-Tief — **keine** Begrenzung auf
  das Tief der Ausbruchskerze (`tuAnchorLow`/`tu_anchor_low`; AVGO Daily: Trendumkehr
  04.08.2023 bei 84,09 → Anker 81,29 vom 06.07., Schluss 10.08. bei 81,16 darunter → Daily rot
  bis zum Ausbruch 21.08.; Trendumkehr 26.10.2023 bei 79,22 → Anker 78,58 vom 06.10., Daily
  bleibt gehalten; März–Mai 2024 gehalten über 116,96 vom 21.02.; über alle Top-20-Signale
  Gewinnsumme 257.389 € → 286.939 €, PF 1,66 → 1,70 gegenüber der Begrenzung auf das Tief der
  Ausbruchskerze). Mit jedem neuen Ausbruch rückt der Anker auf die neue Marke nach
  (Weekly zusätzlich nachgezogen, siehe oben). Die Trendumkehr ist
  nur Ausstieg aus dem Trade, nicht das Ende des Signals. Code: `heldAfterBreakout`/
  `holdSignal`/`holdAnchor` in `frontend/backtest_logic.js` und `frontend/rs_charts.js`
  (Seiten-Ampeln), live `gws_core.held_after_breakout` (`HOLD_WEEKLY`/`HOLD_DAILY`,
  Weekly mit `weekly=True` und `gws_core.weekly_anchor_walk`/`weekly_closed_below` in
  `check_alerts.py`, `anchorWalk` in `backtest_logic.js`/`rs_charts.js`). Studien:
  `BACKTEST_NDX_OUT=/tmp/x.json node backtest_ndx.js --halten=W,D,4H`,
  `--halteanker=W:tiefstes,D:kerze` (kerze | tiefstes | swingtief | tu) bzw.
  `--wochenbruch=tagesschluss|wochenschluss`, `--wochenanker-fest`
- **Daily erlischt unter der Rücksetzer-Untergrenze (seit 16.10.2026):** Untergrenze ist das
  Swing-Tief vor dem Daily-Ausbruch (bzw. vor der Ausbruchskerze der gehaltenen Marke). Sie rückt
  **nur nach einem Rücksetzer von mindestens 10 Handelstagen** (zwei Wochenkerzen) zwischen dem
  bisherigen höchsten Hoch und einem neuen Hoch darüber nach — auf das tiefste Tief dieses
  Rücksetzers; kürzere Rücksetzer setzen kein neues Low. Ein **Schluss** darunter macht Daily rot
  (ein Tief darunter mit Schluss darüber nicht — MRNA 06.05.2021: Tief 143,56 unter 153,27, Schluss
  160,50); ein neues Signal beginnt beim nächsten Schluss über einem Swing-Hoch. NFLX 27.09.2017
  bleibt gültig (Hochs 12.–21.09. ohne 10-Tage-Rücksetzer → Low 17,63 vom 08.09., Schluss 25.09.
  17,86 darüber); AVGO: Daily rot ab 21.09.2023. Über alle Top-20-Signale 36 Trades weg (3.720 €),
  12 neu (4.029 €), PF 1,90 → 1,93, Gewinnsumme 298.350 € → 298.659 €, Gesamtrendite verkettet
  +900,5 % → +909,0 %, größter Rückgang −42.465 € → −41.509 €; verworfen: Untergrenze bei jedem
  Ausbruch über ein Swing-Hoch nachziehen (wie das alte Chart-Band) — per Schluss +591,9 %, per Tief
  +600,9 %. Code: `retracementZone` in `frontend/backtest_logic.js` und `frontend/rs_charts.js`,
  live `gws_core.retracement_zone` (`DAILY_RETR_ZONE` in `check_alerts.py`). Studie ohne:
  `BACKTEST_NDX_OUT=/tmp/x.json node backtest_ndx.js --tageszone-alt`
- **Gültigkeitsbereiche in den Charts** (Weekly, Daily, 4H auf B-DETAILS und den
  Index-/Watchlist-Seiten): grün transparentes Band von der Ausbruchskerze bis zur
  letzten grünen Kerze, vom höchsten Hoch seit der Ausbruchskerze bis zur gestrichelten
  Linie — Weekly: Anker des Signals (letztes Swing-Tief vor dem Ausbruch, bei erneutem Ausbruch
  nachgezogen); Daily: Rücksetzer-Untergrenze (siehe oben, Logik = Band); 4H (nur Darstellung):
  Swing-Tief vor dem Ausbruch (SL-Höhe; nur ein schon vor der Ausbruchskerze bestätigtes —
  AVGO Daily 14.05.2026: 404,92 vom 07.05., nicht 403,43 vom 13.05.); bei jedem weiteren Ausbruch nach oben (Schluss
  über dem letzten Swing-Hoch) springt es auf das Swing-Tief vor diesem Ausbruch; ein
  Schluss darunter beendet das Band, ein neues beginnt beim nächsten Ausbruch
  (`trailingZone`),
  kräftiger, wenn die Ebene nur gehalten ist — je Kerze zeitpunktgenau (`zone` je
  Struktur, `weeklyZones`/`dailyZones`/`h4Zones`)
- **Weekly-Trendumkehr → Retracement abwarten (seit 13.10.2026):** Zeigt Weekly eine
  Trendumkehr (Ebene nur gehalten oder tieferes Tief unter dem letzten bestätigten Swing-Tief
  in Bildung), zählt ein 4H-Signal erst, wenn Daily tatsächlich über seine Marke ausgebrochen
  ist (nicht nur gehalten) und 4H nach dem Tag dieses Daily-Ausbruchs einmal rot war
  (Retracement). AVGO: kein Kauf 31.07.2024 (Woche 29.07. unterbietet das Tief der Woche
  22.07., Daily nur gehalten über 161,98) und 13.08.; Daily bricht 158,06 am 15.08., erstes
  4H-Grün danach am 30.08. vor Earnings gesperrt → Kauf 12.09.2024. Über alle Top-20-Signale
  214 Trades weg (27.546 €), 56 neu (18.581 €), PF 1,70 → 1,75, Gewinnsumme 286.939 € →
  277.974 €, größter Rückgang −58.467 € → −56.787 €. Code: `weeklyReversal`/
  `weeklyReversalRule` in `simulateTradesPIT` (`frontend/backtest_logic.js`), live
  `check_alerts.weekly_reversal_blocks` (`WEEKLY_REVERSAL_RULE`; Nachtlauf und
  `check_alerts_4h.py` — ein gesperrtes Signal wird nicht gemeldet und nicht gekauft).
  Studien: `BACKTEST_NDX_OUT=/tmp/x.json node backtest_ndx.js --wochenumkehr=aus|bestaetigt`
- **Stopp:** letztes Daily-Swing-Tief vor dem Kauf × 0,99 — **war es vor dem Kauf schon per Schluss
  unterschritten, ist es verbraucht; dann gilt das tiefste Tief seit dem Bruch** (seit 16.10.2026; NFLX
  27.09.2017: 18,32 vom 20.09. am 25.09. gebrochen → 17,66 vom 26.09., Stopp 17,48 statt 18,14, Trade
  +5,5 % bis 10.11. statt −0,5 % am 29.09.; über alle Top-20-Signale 9 Trades weg, 10 neu, 36 mit anderem
  Ausstieg, PF 1,91 → 1,90, Gewinnsumme 296.963 € → 298.350 €, Gesamtrendite verkettet +896,9 % → +900,5 %,
  Monate über NASDAQ-100 63 → 66 von 130; `recentSwingLowOf`, live `gws_core.swing_low_stop`, Studie ohne
  `--sl-alt`). **Einstand (seit 13.10.2026):** Schließt
  ein Tag mindestens 2R über dem Einstieg (R = Einstieg − Stopp), gilt ab dem nächsten Tag der
  Einstieg als Stopp; ein Schluss darunter → Verkauf zur Eröffnung, Kürzel BE (über alle
  Top-20-Signale 7 Trades mit anderem Ausstieg, 1 neu, PF 1,82 → 1,83, Gewinnsumme 273.958 € →
  275.610 €, Gesamtrendite verkettet +700,6 % → +711,0 %; früher nachziehen schlechter: ab 1R
  per Tagesschluss +677,3 %, ab 1R per Tageshoch +638,2 %). Code: `breakEven` in
  `tradeFromEntry` (`frontend/backtest_logic.js`), live `check_exits.effective_stop`
  (`BREAK_EVEN_R`, Verkaufsmeldung „Einstand“ und SL-Verschiebung). Studien:
  `--einstand=R:offset[:hoch]`, `--ohne-einstand`
- **Ausstiege** (Grund je Trade als `exitReason`, in Charts/Listen als Kürzel):
  Stopp (SL) · Einstand nach 2R (BE) · Trendumkehr = Schluss unter dem Tief, aus dem das letzte Hoch
  entstand (TU; war dieses Tief schon vor dem Kauf per Schluss unterschritten, ist es verbraucht —
  dann gilt bis zum nächsten Swing-Hoch das tiefste Tief seit dem Bruch bis vor den Kauftag, seit
  13.10.2026; CDNS 29.06.2026: 375,94 vom 12.06. schon am 24./25.06. gebrochen → 358,76 vom 26.06.;
  über alle Top-20-Signale 116 Trades mit anderem Ausstieg (−14.403 € → +19.425 €), 40 Wiedereinstiege
  weg, PF 1,83 → 1,86, Gewinnsumme 275.610 € → 292.403 €, Gesamtrendite verkettet +711,0 % → +828,3 %;
  `entryTrendLow`, live `check_exits.entry_trend_low`, Studie ohne `--tu-alt`) · Verkauf vor Earnings zum Schluss der 14-Uhr-Kerze (ER) — **nur solange der Trade noch keinen
  Schluss ≥ Einstieg + 2R hatte, sonst durch die Zahlen halten** (seit 14.10.2026; Einstand-Stopp schützt;
  über alle Top-20-Signale 156 Trades halten durch (320.533 € → 329.914 €), 73 Wiedereinstiege weg,
  PF 1,85 → 1,93, Gewinnsumme 289.934 € → 299.563 €, Gesamtrendite verkettet +815,8 % → +911,5 %,
  größter Rückgang −44.063 € → −41.781 €; ab 1R +832,9 %, ab 3R +895,2 %, nie verkaufen +819,3 %;
  `earningsHoldR`, live `check_exits.EARNINGS_HOLD_R`, Studie `--earnings-halten=R|aus`). Daily-Signale
  → Verkauf zur Eröffnung am Folgetag. **Kein Zeitstopp** (abgeschaltet seit
  12.10.2026; Kürzel ZS nur noch bei `--mit-zeitstopp`).
  Code: `exitReasonOf`/`tradeFromEntry`, live `check_exits.find_exit`
- **Earnings:** kein Kauf < 4 Kalendertage vor den Zahlen (`data/earnings_history.json`).
  **Kurs fällt nach den Zahlen (seit 12.10.2026):** Schließt der Reaktionstag (nach
  Börsenschluss: nächster Handelstag, sonst der Tag der Zahlen) mindestens 5 % unter dem
  Schluss davor, gibt es keinen Kauf, bis Daily danach einmal rot war (und wieder grün ist)
  oder ein Schluss über dem Kurs vor den Zahlen liegt (AVGO: Zahlen 31.08.2023 nach
  Börsenschluss, 01.09. −5,4 % → kein Kauf am 14.09.; über alle Top-20-Signale 38 Trades weg
  (zusammen −2.600 €), 6 neu, Gewinnsumme 253.812 € → 257.389 €, PF 1,64 → 1,66; ohne
  Mindestrückgang und ohne Freigabe über dem Kurs vor den Zahlen verworfen: 295 Trades weg,
  Gewinnsumme 210.839 €). Code: `earningsDropBlocks` in `frontend/backtest_logic.js`, live
  `check_exits.earnings_drop_block` (Modell-Depot, Kaufentscheid in der Mail, Watchlist).
  Studie ohne: `BACKTEST_NDX_OUT=/tmp/x.json node backtest_ndx.js --ohne-earningsfall`
- **Depot:** höchstens 10 Positionen (nur Depot-Simulation/Modell-Depot)
- **Verworfen (nicht erneut vorschlagen ohne neuen Anlass):** Weekly als letzter
  Punkt, Daily-Fakeout-Sperre, Retracement-Varianten als Ersatz-Einstieg,
  Signal halten auf 4H (Gewinnsumme 204.991 € → 172.381 €, nimmt Wiedereinstiege weg),
  Daily-Trendumkehr → zweites 4H-Signal abwarten (Gesamtrendite +896,9 % → +574,2 %; Kaufsperre
  solange Daily nur gehalten: +447,2 %),
  tiefster Anker auch für Daily (zu viele Fehlkäufe, AVGO-PF 2,48 → 1,77)

### Ablauf

1. **Fall verstehen** — betroffenen Titel/Zeitraum mit
   `node inspect_ticker.js TICKER VON BIS` ansehen (W/D/4H je 4H-Kerze, Marken,
   Top 20, Trades der Engine inkl. Verkaufsgrund). Abweichungen zur Sicht des Nutzers
   mit konkreten Kursen/Marken benennen und klären, bevor gebaut wird.
2. **Bauen — immer Backtest und Live identisch** (`frontend/backtest_logic.js` und
   `check_exits.py`/`check_alerts*.py`), Tests ergänzen.
3. **Wirkung messen** (Regeln unten) und **Referenz-Trades prüfen**.
4. **Dem Nutzer vorlegen** — Tabelle + Jahrestabelle + Referenzprüfung, Einschätzung
   in zwei Sätzen, dann fragen. **Nichts committen**, bis der Nutzer zustimmt; bis
   dahin die Änderung als Patch im Scratchpad sichern (`git diff > …patch`,
   `git checkout -- .`), damit das Repo sauber bleibt.
5. **Nach Zustimmung übernehmen:** Patch einspielen, `node backtest_ndx.js` (normaler
   Lauf, schreibt `data/backtest_ndx.json`), Tests + Referenzprüfung, bei geänderten
   `frontend/*.js` die `?v=` hochsetzen, Doku in dieser Datei anpassen (Logik-Stand
   oben ersetzen), committen, auf Arbeits-Branch und `master` pushen, Hash ausgeben.
   Auswirkungen auf Live (Mails, Modell-Depot) im Chat nennen.

### Wirkung messen

Bewertet wird die **Logik über alle Signale der Top-20-Titel** (Titel am Signaltag in
den Top 20, derselbe Filter wie `backtest_ndx.js`/B-ÜBERSICHT) — **ohne die
Begrenzung auf 10 Depotplätze** (Systemparameter, würde das Urteil über die Logik
verzerren, siehe unten): jeder Trade aus
`simulateTradesPIT` zählt gleich, mit dem Engine-Einsatz (10.000 € je Trade, höchstens
1.000 € Risiko).

```bash
BACKTEST_NDX_OUT=/tmp/vorher.json  node backtest_ndx.js   # Stand vor der Änderung
BACKTEST_NDX_OUT=/tmp/nachher.json node backtest_ndx.js   # mit Änderung
node compare_backtest.js /tmp/vorher.json /tmp/nachher.json                # Tabelle + Jahrestabelle
```

Die Ausgabe enthält immer:

| Kennzahl (alle Top-20-Signale, je Trade 10.000 €) | bisher | neu |
|---|---|---|
| betroffene Trades (weggefallen / neu / mit anderem Ausstieg) | – | Anzahl + Gewinnsumme |
| Anzahl Trades | | |
| Profitfaktor | | |
| absolute Rendite (Gewinnsumme in €) | | |
| **Gesamtrendite in %** — Jahresrenditen über **alle** Jahre inkl. des laufenden **verkettet** (Zinseszins) | | |
| **NASDAQ-100 Gesamtrendite in %** — seine Jahresrenditen verkettet, gleicher Zeitraum | | |
| **Monate über NASDAQ-100** — Anzahl aller Monate (inkl. laufendem), in denen die Monatsrendite der Signale über der des NASDAQ-100 lag („X von Y“, Anteil) | | |
| Ø Rendite je Trade / Trefferquote | | |
| größter Rückgang der Gewinnsumme (€) | | |

Dazu die Jahrestabelle (NASDAQ-100 / bisher / neu je Jahr, dazu Monate über NASDAQ-100
bisher / neu je Jahr, Gesamtzeile) — Jahresrenditen im Chat **immer als Tabelle**, nie als
Fließtext. Gesamtrenditen werden **überall verkettet** dargestellt (Zinseszins:
(1 + r₁) × (1 + r₂) × … − 1), nie als Summe der Jahresrenditen — in `compare_backtest.js`
wie auf B-ÜBERSICHT. Jahresrendite der Signale = Gewinn der im Jahr
verkauften Trades (offene: laufendes Jahr, aktueller Kurs) / 100.000 € (10 × 10.000 €,
Bezugsgröße wie B-ÜBERSICHT); Monatsrendite ebenso je Monat, NASDAQ-100 je Monat aus
denselben QQQ-Kursen (`ndxMonths` in `data/backtest_ndx.json`).
Depotwerte (10 Plätze, CAGR, Endkapital) höchstens ergänzend nennen — nie als
Entscheidungsgrundlage.

**Systemparameter — bei einer Systemoptimierung gesondert berücksichtigen.** Soll das
System als Ganzes optimiert werden, sind sie neu zu prüfen (mit der dann gültigen Logik):
- **Depot höchstens 10 Positionen** (`MAX_POSITIONS` in `backtest_history/portfolio.js`
  und `check_exits.py`) — live und auf B-ÜBERSICHT aktiv, bei der Logik-Bewertung
  ausgeblendet; begrenzt, welche Signale gekauft werden
- **Zeitstopp** (10 Handelstage nach dem Kauf nicht mind. +5 % → Verkauf) —
  **abgeschaltet seit 12.10.2026, Backtest und Live** (`timeStopEnabled` in
  `frontend/backtest_logic.js`, `TIME_STOP_ENABLED` in `check_exits.py`). Mit
  Trendumkehr und Earnings-Regel ohne Zeitstopp: PF 1,61 → 1,70, Gesamtrendite
  +172 % → +205 %, größter Rückgang −32.186 € → −38.350 €. Schnitt Trades ab, die
  sich erst nach zwei Wochen entwickeln (AVGO 05.05.2026: −4,0 % statt +12,7 %).
  Für eine Optimierung wieder testbar mit
  `BACKTEST_NDX_OUT=/tmp/x.json node backtest_ndx.js --mit-zeitstopp`

**Frontend-Cache:** Nach jeder Änderung an `frontend/*.js` die Version `?v=…` in
allen HTML-Seiten hochsetzen, die die Datei einbinden — sonst mischt der Browser
alte und neue Dateien (B-DETAILS blieb so am 12.10.2026 leer).

**Chart-Legende:** Unter den Charts (Weekly, Daily, 4H) steht keine Legende — alle
Erklärungen (GWS-Linien je Ebene, letzter Break, Gültigkeitsbereich, Marker, Verkaufskürzel,
SL, Trend, Kurs, Benchmark, Signal) stehen gesammelt in **einer** Legende über dem ersten
Chart: `ChartLegendMarkers` in `frontend/backtest_charts.js` (B-DETAILS), `ChartLegend` in
`frontend/rs_charts.js` (Index- und Watchlist-Seiten). Neue Chart-Elemente dort erklären;
unter den Charts nur die Kerzenzahl.

**Netz in Cloud-Sessions:** Yahoo, SEC, Nasdaq und Alpaca sind gesperrt — neue Daten
(z. B. Termine, Kurse) über einen GitHub-Workflow laden (Muster:
`fetch_earnings_history.yml`, Start per GitHub-MCP `actions_run_trigger`).

## Referenz-Trades (Regressionsschutz)

`data/reference_trades.json` enthält vom Nutzer freigegebene, „perfekte“ Trades.
Anpassungen an der Logik dürfen an diesen Trades nichts ändern. Geprüft wird **nur mit der
aktuellen Logik inkl. aller Regeln** (auch der Earnings-Regel) — keine Gegenprobe ohne eine
Regel, die zur aktuellen Logik gehört.

- **Prüfen — PFLICHT** vor und nach jeder Änderung an Signal-/Ausstiegslogik
  (`frontend/backtest_logic.js`, `check_exits.py`, `check_alerts*.py`, `gws_core.py`,
  `backtest_ndx.js`) und bei jedem Berechnungslauf für mögliche Anpassungen
  (Studien, Parameter-Varianten):
  ```bash
  python3 -m unittest test_reference_trades   # Backtest-Engine + Live-Verkaufsprüfung
  node check_reference_trades.js              # nur Backtest-Engine, mit Klartext je Trade
  ```
  Eine Variante, die einen Referenz-Trade verändert, gilt als abgelehnt bzw. muss
  dem Nutzer mit genau dieser Abweichung vorgelegt werden — **mit Bild, aber nur bei einer
  Abweichung** (ohne Abweichung kein Bild): Änderung
  im Arbeitsverzeichnis lassen, `node reference_trade_shots.js [ID] [--w YYYY-MM-DD]`
  ausführen und `out/reference_trades/<ID>.png` per SendUserFile zeigen (B-DETAILS mit
  Legende, Weekly, Daily und 4H; Spalten vorher = Logik aus dem letzten Commit / nachher =
  Änderung). Erst danach als Patch sichern. Zusätzlich prüft
  `update_backtest_daily.yml` die Trades täglich mit den aktuellen Kursen
  (Abweichung → Fehler-Mail).
- **Geprüft wird:** Signal in derselben 4H-Kerze, Kauf zur selben Kerze, Ausstieg am
  freigegebenen Tag (Verkauf am Signaltag oder zur Eröffnung des nächsten
  Handelstages) — in der Engine und in `check_exits.find_exit`.
- **Neue Referenz-Trades** nur auf ausdrückliche Freigabe des Nutzers eintragen
  (`id`, `ticker`, `approved`, `setup`, `entry.signal_bar/date/time`,
  `exit.signal_date/reason`); Kurse nicht eintragen (Splits verschieben sie).

## Batch-Empfehlung

Beispiel: `Analysiere MU ARM AMD MRVL ON`

Nach einem Analyse-Batch (mehrere Ticker in einem Rutsch) zusätzlich zur
Zusammenfassungs-Tabelle (Schritt 8 oben, inkl. Handlungsempfehlung-Spalte)
eine **EV/Risiko-Tabelle** ausgeben — exakt dieselben Werte, die danach auch
in den Index-Tabellen der Platform (`frontend/index.html`, `sp500.html`,
`smallcap.html`) erscheinen:

```
| Ticker | EV      | Risiko |
|--------|---------|--------|
| TICKER | ±X%     | Y%     |
```

Werte aus `data/ratings/index.json` nach dem Schreiben aller Analysen des
Batches auslesen (`ev_upside_pct`, `verdict`, `funnel_veto.decision`) —
**nicht** aus dem selbst geschriebenen Analysetext neu berechnen, da
`write_rating()` den EV mechanisch aus den Bull/Base/Bear-Mittelpunkten
ermittelt (einfacher Durchschnitt, nicht wahrscheinlichkeitsgewichtet) und
das die im Frontend tatsächlich angezeigte Zahl ist.

Risiko-Staffel identisch zur Frontend-Logik (`frontend/index.html`,
Abschnitt "Risiko-Staffel"): max. Verlust je Trade in % des Invests.
- `funnel_veto.decision == "VETO"` oder `verdict == "AVOID"` → **0%**
- `funnel_veto.decision == "REDUCE"` → **5%**
- `ev_upside_pct < -20` → **5%**
- `ev_upside_pct > 20` und (`funnel_veto.decision == "PASS"` oder `verdict == "BUY"`) → **15%**
- sonst → **10%**

Am Ende zusätzlich die Ø EV-Upside über alle Batch-Ticker ausgeben (wie die
"Ø EV-Upside"-Kennzahl oben in der Platform-Tabelle).

## Earnings-Kandidaten-Check (Turnaround & Momentum-Beat)

Wenn der Nutzer schreibt `Earningsanalyse TICKER1 TICKER2 ...` (Screening
nach frischen Quartalszahlen, VOR einer vollständigen `Analysiere TICKER`):
Kein `write_rating()`, keine 11-Abschnitte-Analyse — nur die Kennzahlen-
Recherche plus eine Einstufung je Ticker.

**Zwei sich gegenseitig ausschließende Kandidaten-Typen** (Kriterien in
Schritt 3 unten):

- **Turnaround** — Verlust/Krise kippt in Erholung (Referenzmuster CNC)
- **Momentum-Beat** — gesundes, stark wachsendes Geschäft übertrifft die
  Erwartungen deutlich (Referenzmuster PLTR/MSFT/AMZN Q2 2026)

Beide lösen automatisch die Vollanalyse aus. **Ein Momentum-Beat wird
niemals als Turnaround ausgewiesen** — weder in der Tabelle, noch in der
Begründung, noch in der Analyse selbst. Die Kategorien gehören in getrennte
Zeilen der Einstufungsspalte; „Turnaround" bleibt dem Verlust→Gewinn-Muster
vorbehalten.

### Automatik-Modus: `earning` / `earningsanalyse` ohne Ticker

Schreibt der Nutzer nur `earning` oder `earningsanalyse` (ohne Ticker-Liste),
werden die Ticker automatisch ermittelt statt manuell übergeben:

1. **Ticker-Pool ermitteln** aus `data/earnings_alerts_log.json`
   (`alerts`-Liste; wird laufend von `earnings_alert_global.yml` und
   `earnings_alert_premarket.yml` befüllt — der frühere RS-Morgen-Digest
   `earnings_alert.yml` läuft seit 08.08.2026 nicht mehr automatisch und
   schreibt hier nicht rein, siehe „Datenquellen"). Enthält RS-getrackte
   Ticker (Live-Vorbörse **und** Global-Scan — der schließt RS-Titel seit
   08.09.2026 nicht mehr aus, sondern dedupliziert nur noch gegen den Log)
   ebenso wie Ticker aus dem breiten Global-Universum (US/EU).
2. **Letzten Scan-Zeitpunkt** aus `analyses/earnings_screening/.last_scan`
   lesen (ISO-Timestamp UTC). Fehlt die Datei (erster Lauf): stattdessen alle
   Log-Einträge der letzten 7 Tage verwenden.
3. Nur `alerts`-Einträge mit `detected_at` > letztem Scan-Zeitpunkt nehmen,
   nach Ticker deduplizieren (ein Ticker kann mehrfach auftauchen, z. B.
   Live-Alert + späterer Global-Scan-Treffer). Keine neuen Einträge → kurze
   Chat-Meldung „Keine neuen Earnings-Meldungen seit TIMESTAMP." und STOP,
   kein Dateizugriff/Commit.
4. Für jeden gefundenen Ticker die Schritte 1–4 des manuellen Modus unten
   durchführen (Kennzahlen, RS-Score, Turnaround-/Momentum-Beat-Kriterien,
   Einstufung). Das Feld `trigger` des Log-Eintrags mitlesen:
   `"kursreaktion"` heißt, der Alert kam über die Marktreaktion und nicht über
   die EPS-Surprise — die Surprise ist dann als Signal wertlos, die
   Einstufung stützt sich auf Umsatz, Guidance und Kursreaktion.
   `eps_distorted: true` heißt, die gemeldete EPS enthält einen bilanziellen
   Einmaleffekt und darf nicht als operativer Beat zitiert werden.
5. **Ergebnis abspeichern statt nur im Chat zeigen:** Einstufungstabelle +
   Begründungen als Markdown nach `analyses/earnings_screening/<DATUM>.md`
   schreiben (DATUM = heutiges Datum, `YYYY-MM-DD`). Davor: alle Dateien in
   `analyses/earnings_screening/` löschen, deren Datum im Dateinamen älter
   als 7 Tage ist (Aufbewahrungsfrist — ältere Screenings werden automatisch
   entfernt, keine manuelle Pflege nötig).
6. `analyses/earnings_screening/.last_scan` mit dem aktuellen UTC-Zeitstempel
   überschreiben.
7. `analyses/earnings_screening/` committen und auf `master` pushen,
   Git-Hash im Chat ausgeben.
8. **Für jeden bestätigten Kandidaten ("Turnaround" oder "Momentum-Beat")
   automatisch, ohne Rückfrage, direkt im selben Lauf mit `Analysiere TICKER`
   in die volle 11-Abschnitte-Analyse inkl. `write_rating()` übergehen** —
   keine Bestätigung durch den Nutzer abwarten. "Grenzfall"/"Nein" lösen
   keine automatische Vollanalyse aus.

**Referenzmuster Turnaround: CNC Q1 2026** (`analyses/cnc.md`,
`instagram/data/earnings/CNC.json`) — Verlustquartale (Q4 25 EPS −1,16 $)
kippen in einen Blowout-Beat (Q1 26 EPS 3,37 $, +62 % Surprise), die
Kern-Kennzahl der Krise (Health Benefits Ratio) normalisiert sich sichtbar,
und das Management hebt die Jahresprognose an statt sie erneut zu kappen.
Genau diese Kombination — nicht der Beat allein — macht einen echten
Turnaround-Kandidaten aus.

**Referenzmuster Momentum-Beat: PLTR/MSFT/AMZN Q2 2026** — kerngesunde,
stark wachsende Geschäfte (Umsatz +93 % / +18 % / +20 % YoY) übertreffen die
Erwartungen und werden vom Markt mit +29,5 % / +15,5 % / +15,3 % quittiert.
Kein Verlustquartal, keine Krisen-Kennzahl, die sich normalisiert — also
ausdrücklich **kein** Turnaround, aber ein Analyse-Anlass. AMZN zeigt
zusätzlich, warum die EPS-Surprise hier nicht das Maß sein kann: bereinigt
nur +6 % (Mega-Caps steuern ihre Guidance eng), GAAP +200 % durch die
Anthropic-Neubewertung — beide Zahlen taugen nicht als Signal, die
Kursreaktion schon.

1. **Je Ticker Earnings-Kennzahlen ermitteln** — gleiche Quelle/Fallback wie
   im Earnings-Check des Analyse-Workflows (Schritt 1 oben): bevorzugt
   `fetch_fundamentals(TICKER)`, sonst WebSearch. Ermitteln: EPS
   actual/estimate/surprise %, Revenue YoY, Guidance-Richtung (angehoben /
   bestätigt / gesenkt), Kursreaktion, sowie — falls vorhanden — die
   Kern-Kennzahl, die eine vorherige Krise erklärt hätte (Marge, Quote,
   Segment-Kennzahl).
2. **RS-Score/Momentum** aus dem passenden RS-JSON ziehen (siehe Schritt 2
   des Analyse-Workflows). Ist der Ticker in keinem RS-JSON getrackt (z. B.
   Micro-Cap-Bank), das explizit als "RS-Daten nicht verfügbar" ausweisen —
   nicht schätzen oder auslassen.
3. **Einstufung prüfen** — zuerst Turnaround, dann Momentum-Beat. Ein Ticker
   kann nur eines von beidem sein: Kriterium 1 der Turnaround-Prüfung und
   Kriterium 1 der Momentum-Beat-Prüfung schließen sich gegenseitig aus.

   **A) Turnaround** (alle vier nötig):
   - Klares Verlust→Gewinn- oder Krisen→Erholungs-Muster in der jüngsten
     Historie (mind. 1 Verlust-/Krisenquartal in den letzten 12 Monaten) —
     ein Beat bei einem bereits gesunden, stetig wachsenden Geschäft erfüllt
     dies NICHT, unabhängig von der Surprise-Höhe (→ Momentum-Beat prüfen)
   - Eine identifizierbare Kern-Kennzahl normalisiert sich sichtbar
     (analog MCR bei CNC) — sonst als "kein klarer Normalisierungs-Beleg"
     kennzeichnen
   - Guidance wird angehoben statt (wie in Vorperioden) gesenkt
   - EPS-Surprise ≥ 10 % (Schwelle analog `earnings_gate.py`,
     `MIN_EPS_SURPRISE`)

   **B) Momentum-Beat** (alle vier nötig, nur wenn A) an Kriterium 1
   scheitert):
   - **Kein** Verlust-/Krisenquartal in den letzten 12 Monaten — das
     Geschäft war schon vorher gesund
   - Umsatzwachstum ≥ 15 % YoY im gemeldeten Quartal
   - Guidance wird angehoben (bloße Bestätigung reicht nicht)
   - Marktbestätigung: EPS-Surprise ≥ 10 % **oder** Kursreaktion ≥ 8 % am
     ersten Handelstag nach der Meldung (Schwelle `MIN_REACTION_JUMP` in
     `earnings_gate.py`). Bei Mega-Caps ist die Kursreaktion das belastbarere
     Signal — eine bereinigte Surprise von +6 % bei +15 % Kursreaktion (AMZN)
     ist ein Treffer, kein Fehlschlag.

   Zusätzlich für B): Der Ticker muss in einem RS-JSON getrackt sein — ohne
   RS-Score fehlt der Momentum-Beleg, dann höchstens "Grenzfall".

4. **Einstufung ausgeben** — kurze Tabelle, keine Volltext-Analyse:

   ```
   | Ticker | EPS Surprise | Kursreaktion | Guidance | Kern-Kennzahl / Wachstum | Einstufung |
   |--------|--------------|--------------|----------|--------------------------|------------|
   | TICKER | +X %         | +Y %         | ↑/→/↓    | Kurzbefund               | Turnaround / Momentum-Beat / Grenzfall / Nein |
   ```

   Danach je Ticker 1–2 Sätze Begründung, mit explizitem Verweis, welches
   Kriterium fehlt (falls "Nein"/"Grenzfall"). Bei "Momentum-Beat" den
   Begriff "Turnaround" nicht verwenden — auch nicht abschwächend
   ("Turnaround-artig", "kleiner Turnaround"). Ist die EPS-Surprise als
   `eps_distorted` markiert oder kam der Alert über `trigger: "kursreaktion"`,
   das in der Begründung benennen statt die Surprise-Zahl zu zitieren.
5. **Für jeden bestätigten Kandidaten ("Turnaround" oder "Momentum-Beat")
   automatisch, ohne Rückfrage, direkt im selben Lauf** mit
   `Analysiere TICKER` in die volle 11-Abschnitte-Analyse inkl.
   `write_rating()` übergehen — keine Bestätigung durch den Nutzer abwarten.
   "Grenzfall"/"Nein" lösen keine automatische Vollanalyse aus.

## Wikifolio Wochenrückblick (Feed-Post)

Wenn der Nutzer schreibt `Wochenrückblick KW<NN>` oder `Feed-Post KW<NN>`:

### Datenabruf und Berechnung

```python
import json

hist   = json.load(open('instagram/data/wikifolio_history.json'))['weekly']
trades = json.load(open('instagram/data/trades.json'))['closed']
holds  = json.load(open('instagram/data/holdings.json'))['positions']
ndx    = json.load(open('data/rs_full.json'))['ndx_ohlcv']

# Konstanten
START_VALUE = 98.48          # EUR, 30.03.2026
NDX_START   = 22953.38       # NDX-Close 30.03.2026

# Wochenwerte
kw_curr = next(e for e in hist if e['kw'] == NN)
kw_prev = next(e for e in hist if e['kw'] == NN - 1)
port_wk    = (kw_curr['value'] - kw_prev['value']) / kw_prev['value']
port_total = (kw_curr['value'] - START_VALUE) / START_VALUE

# NASDAQ: Freitag KW-Ende vs. Freitag Vorwoche
ndx_curr = next(e for e in ndx if e['d'] == kw_curr['date'])['c']
ndx_prev = next(e for e in ndx if e['d'] == kw_prev['date'])['c']
ndx_wk    = (ndx_curr - ndx_prev) / ndx_prev
ndx_total = (ndx_curr - NDX_START) / NDX_START

alpha_wk    = port_wk - ndx_wk
alpha_total = port_total - ndx_total
```

Wochen über NASDAQ: manuell aus Historie ermitteln (Vergleich port_wk vs. ndx_wk
je KW) oder aus `instagram/CONTEXT.md` entnehmen.

### KW24-Trades (Referenzbeispiel)

Verkäufe KW24: DDOG +7,6% (09.06.), AMAT +5,1% (09.06.), WDC +2,7% (09.06.)
Käufe KW24: GOOGL (09.06.), ASML (12.06.), SQ (12.06.)

### Textformat (Plain Text, kein Markdown)

Ausgabe **ohne Markdown-Formatierung** (keine ##, keine **, keine ---),
damit der Text direkt kopiert und in den wikifolio-Feed eingefügt werden kann.
Struktur analog KW23-Referenz:

```
📊 Wochenreport KW NN (DD.MM. – DD.MM.)

Performance:
	•	Portfoliowert: +X,X% diese Woche
	•	Gesamtrendite Wikifolio seit 30.03.: +XX,X%
	•	Nasdaq-100: +X,X% diese Woche
	•	Gesamtrendite Nasdaq seit 30.03.: +XX,X%
	•	Alpha seit 30.03.: +XX,Xpp
	•	N von M Wochen den Nasdaq geschlagen

🔥 Trades der Woche:
✅ Käufe:
→ FIRMENNAME (DD.MM.)
Kurzbeschreibung: Sektor, RS-Signal, Positionsgröße.

❌ Verkäufe:
← FIRMENNAME (DD.MM., +/-XX,X% seit Kauf)
Kurzbeschreibung: Exit-Grund (RS-Abschwächung / Stopp / Gewinn mitgenommen).

[2–3 Narrativ-Abschnitte mit Emoji-Headline, je 3–5 Sätze]

⚙️ System-Konsistenz:
Die Kombination aus: [4 Bullet-Points] …beweist sich / liefert Woche für Woche.
N von M Wochen den Nasdaq geschlagen. Gesamtrendite XX% vs. XX%.

🎯 Ausblick:
[2–3 Sätze. Immer enden mit: Keine Prognosen, keine Meinungen – nur Daten,
Disziplin und Umsetzung.]
```

### Themen-Auswahl für Narrativ-Abschnitte

Pro Woche 2–3 der folgenden Winkel wählen (je nach Datenlage):
- Outperformance in schwachem Markt (Portfolio + vs. NASDAQ -)
- Outperformance in positivem Markt (beide +, Portfolio stärker)
- Einzeltrade-Highlight (größter Gewinner / Verlierer mit System-Erklärung)
- Schnelle Stopp-Umsetzung (Roundtrip < 5 Tage mit Verlust)
- Portfolio-Rotation (mehrere Exits + Entries in kurzer Folge)
- Re-Entry (Titel der früher mit Verlust verkauft wurde und jetzt zurückkommt)

### Nach dem Erstellen

Keine Datei-Commits nötig (Feed-Text ist reines LLM-Output). Nur committen,
wenn Daten-JSONs geändert wurden (neue Trades, neue Holdings, neuer KW-Wert).

## Instagram-Workflow (AI Alpha Selection)

Markenname: **AI Alpha Selection** (Singular, kein „Selections"). Kein
@-Handle auf Slides oder in Captions — nur der Markenname. Captions sind
**Kurz-Captions** (die volle Analyse steht auf den Slides) mit **max. 5
Hashtags** (Instagram-Limit; optimal 3–5). Nach Änderungen an
`instagram/render.py`/`theme.py`: `python3 -m instagram.qa_golden` laufen
lassen (Golden-Image-Regressionstest).

### Wochenrückblick-Regeln (Samstags)

**Kurse aktualisieren:** Wenn der Wochenrückblick am **Samstag** erstellt wird,
verwenden IMMER die **Freitags-Kurse** (letzter Handelstag):
- `--date YYYY-MM-DD` mit dem **Freitag-Datum** setzen (z. B. `2026-06-12`)
- Dies ensures alle Charts (Performance, Positionen, Trades, Aktie der Woche)
  zeigen die aktuellsten verfügbaren Kurse (EUR/USD, NASDAQ-100, Positionen)
- Nicht das Samstags-Datum verwenden — das würde ältere Kurse heranziehen

**Trade-Filter:** Nur Verkäufe mit **Rendite > 5%** (positiv oder negativ) als
Chart-Slides zeigen. Kleine Trades (<5%) und aktive Positionen (noch nicht
verkauft) nicht als Trade-Slides darstellen.

### Ausgabe-Pflichten nach Instagram-Generierung

Nach jeder Generierung von Instagram-Slides (Analyse-Post, Earnings-Post,
Wochenpost, Reel) IMMER:
1. **Alle Slides einzeln anzeigen** (jeden PNG via SendUserFile ausgeben —
   kein Überspringen, keine Auswahl)
2. **ZIP-Datei ausgeben** (`carousel_TICKER.zip` bzw. entsprechendes Archiv)
3. **Reel MP4 erzeugen** und ausgeben (Wochenpost: nur Hook + Wochenvergleich +
   CTA-Slide; Analyse/Earnings: 4 Teaser-Frames)
4. **Caption ausgeben** — `caption.txt` (Carousel) direkt im Chat anzeigen;
   bei Reel zusätzlich `reel_caption.txt`. Immer zusammen mit Slides + Reel.
5. **Auf `master` pushen** (bzw. den vorgegebenen Session-Branch) — Analyse-
   und Rating-Dateien committen, Slides sind gitignored

### Logo-Suche für Instagram-Slides

Logos liegen unter `instagram/assets/logos/`. Der Generator erwartet den
Dateinamen `TICKER.png` (Großbuchstaben). Existiert diese Datei nicht, nach
dem **vollen Unternehmensnamen** und gängigen Varianten suchen (z.B.
`Marvell.png` → `MRVL.png`, `Sandisk.png` → `SNDK.png`) und eine Kopie unter
dem Ticker-Namen anlegen. Reihenfolge der Suche:
1. `TICKER.png` (exakt)
2. Firmenname (shortName aus `data/fundamentals.json`) als Dateiname
3. Erste Silbe / bekannte Kurzform des Firmennamens
Wird ein Logo gefunden und kopiert → vor der Generierung erledigen, damit
das Cover das Logo zeigt.

Wenn der Nutzer einen wikifolio-Wochenreport einfügt oder schreibt
`Instagram KW<NN>` / `Erstelle Instagram-Post`:

1. **`instagram/CONTEXT.md` lesen** — zentrale Wissensdatei mit komplettem
   Projektstand (Stammdaten, Regeln, Daten-Snapshot, offene Punkte). Danach
   `instagram/PROMPT.md` für den detaillierten Ablauf und die **zwingenden
   wikifolio-Regeln** (Trennung Depot/Zertifikat, keine ISIN, kein wikifolio-Logo,
   Pflicht-Disclaimer).
2. **PFLICHT — gelieferte Werte zuerst abspeichern** (automatisch, ohne
   Rückfrage), bevor generiert wird:
   - Zertifikatswert → `instagram/data/wikifolio_history.json`
     (`python3 -m instagram.add_week --kw <NN> --value <WERT> --date YYYY-MM-DD`)
   - Käufe → Position in `instagram/data/holdings.json` ergänzen
   - Verkäufe → Position aus `holdings.json` entfernen **und** abgeschlossenen
     Trade in `instagram/data/trades.json` (`closed`: `name` + `ret` als Dezimal)
3. Generieren (Hauptweg, dynamische Felder texten):
   `python3 -m instagram.generate --kw <NN> --hook "…" --why "…" --frage "…"`
   (Slide-Datum = Samstag der KW automatisch; ohne Flags greifen Fallbacks.)
4. Slides aus `out/` dem Nutzer zeigen — **kein Auto-Upload**, manueller Post.
5. Datendateien committen (die `out/`-Slides sind gitignored).

Hauptformat **Carousel (4:5)**; Reel-Frames (9:16) entstehen parallel.
Stories erst später (bei genügend Followern) — siehe Roadmap in PROMPT.md.

### Instagram-Analyse-Post (Einzelaktie)

Wenn der Nutzer schreibt `Instagram-Analyse TICKER` / `Analyse-Post TICKER`
(macht aus einer fertigen `analyses/TICKER.md` ein Carousel + Reel-Teaser):

1. `instagram/CONTEXT.md` (Abschnitt 11) + `PROMPT.md` (Abschnitt „Zweiter
   Post-Typ: AKTIEN-ANALYSE") lesen.
2. Generieren — am besten mit individueller Hook-Frage:
   ```bash
   python3 -m instagram.generate --analysis TICKER --headline "<Frage/These>"
   ```
3. Output `out/instagram/<DATUM>_ANALYSE_<TICKER>/`: `carousel/` (10 PNG),
   `reel/` (4 PNG), `reel.mp4`, `caption.txt`, `reel_script.txt` zeigen —
   **kein Auto-Upload**. Firmenlogo unter `instagram/assets/logos/TICKER.png`.
   Kein aktueller Kurs, keine GWS-Ampel/Breakout auf den Slides.

### Instagram-Earnings-Analyse (Quartalszahlen mit Beat)

Wenn der Nutzer schreibt `Earnings-Analyse TICKER für Insta` / `Earnings-Analyse
TICKER` (eigenständiger Post mit Fokus auf einen Earnings-Termin mit übertroffenen
Prognosen — z. B. Kandidaten aus der `check_earnings.py`-Mail: ≥ 5 % Kurssprung +
≥ 10 % EPS-Surprise + Umsatz YoY ≥ 0):

1. `instagram/CONTEXT.md` (Abschnitt 11b) + `PROMPT.md` (Abschnitt „Dritter
   Post-Typ: EARNINGS-ANALYSE") lesen.
2. **Basis-Analyse sicherstellen:** `analyses/TICKER.md` muss existieren (neues
   11-Abschnitte-Schema). Fehlt sie → zuerst „Analysiere TICKER". Älter als der
   Earnings-Termin → vorher neu generieren; danach unverändert nutzen.
3. **Earnings-Zahlen aus dem Web** holen und in `instagram/data/earnings/TICKER.json`
   schreiben (Schema in `PROMPT.md`; Pflicht: ticker, quarter, report_date, source,
   eps_actual/_estimate/_surprise_pct). Der Kurssprung wird automatisch aus
   `data/rs_*.json` berechnet — nicht eintragen. **Für den Tiefgang zusätzlich**
   (optional, empfohlen): `quarterly` (Quartals-EPS → Slide „Gewinn je Quartal")
   und `segments` (Segment-Treiber → Slide „Was den Beat getragen hat").
4. Generieren — am besten mit individueller Beat-Hook (die Hook nennt **weder
   Firmenname noch Ticker**, siehe Design-Regeln in `PROMPT.md`):
   ```bash
   python3 -m instagram.generate --earnings TICKER --headline "<Beat/Turnaround-These>"
   ```
5. Output `out/instagram/<DATUM>_EARNINGS_<TICKER>/`: `carousel/` (bis zu 14 PNG),
   `reel/` (4 PNG), `caption.txt` **und `carousel_<TICKER>.zip`** (alle Slides
   gebündelt, wie bei den Aktienanalysen) zeigen — **kein Auto-Upload**. Danach die
   `instagram/data/earnings/TICKER.json` committen (out/-Slides sind gitignored).

## Monetarisierung / Controlling

Geschäfts-/Umsatz-Ebene (5 Säulen, Content-Pipeline, KPI-Funnel) liegt in
**`controlling/`** — bei Fragen zu Umsatz, Telegram-SaaS (39 €/Monat), Affiliate,
Newsletter, Sponsoring oder Conversion-KPIs dort starten (`controlling/README.md`).
KPI-Rechner: `python3 controlling/kpi_model.py`.
