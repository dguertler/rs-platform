# Umsetzungs-Prompt — RS-Platform 2.0 (weiterführen mit Claude/Sonnet)

Dieser Prompt ist dafür gedacht, 1:1 als Aufgabenstellung an eine neue
Claude-Code-Session gegeben zu werden. Er enthält den vollen Kontext — keine
Rückfragen zum "warum" nötig, nur zum "wie im Detail".

---

## Kontext (bereits erledigt — nicht neu bauen)

Auf dem Branch `claude/rs-platform-stock-selection-utpupd` (bzw. bereits nach
`master` gemergt — mit `git log`/`git branch` prüfen) existiert:

1. **`STRATEGIEPLAN.md`** — vollständiges Zielkonzept: Regime-Ampel, RS 2.0,
   Setup-Qualität, Exit-Regelwerk, Backtesting-Regeln B1–B10, Roadmap.
   **Lies diese Datei zuerst vollständig.**
2. **`backend/v2_analysis.py`** — Regime-Ampel, RS 2.0 (Perzentil-Rang),
   Investierbarkeits-Filter (MCap/Kurs/Historie/Ø-Dollar-Volumen 20T),
   Earnings-Sperre (fail-safe, optional), GWS-Setup-Punkte inkl.
   Volumen-Bestätigung (fail-safe, optional), Stop-Berechnung. Funnel-Status
   je Ticker: `KAUFLISTE` / `KANDIDAT` / `GEFILTERT` / `EARNINGS-SPERRE`.
3. **`backend/main.py`** — `GET /api/v2/{market}` und `GET
   /api/v2/backtest/{market}` (additiv, kein v1-Endpoint verändert).
4. **`frontend/v2.html`** — eigenständige Seite mit Regime-Box (immer
   sichtbar, erklärt 🟢/🟡/🔴/❓), Funnel-Tabelle mit Legende, v1-vs-2.0-
   Ranking-Vergleich, Regelwerke als `<details>`, sowie einem **Backtest-Tab**
   (lädt echte Reports aus `backtest_v2/results/` über den neuen Endpoint,
   mit Markt-Auswahl und ehrlicher Einordnung der Ergebnisse).
5. Alle bestehenden Frontend-Seiten haben einen zusätzlichen Nav-Button
   `RS-Platform 2.0` — sonst unverändert.
6. **Volumen-Export**: `rs_colab.py`, `dax_colab.py`, `sp500_colab_1/2.py`,
   `smallcap_colab_1/2.py` schreiben jetzt zusätzlich `"v"` (Volumen) in die
   OHLCV-Arrays — additiv, mit synthetischen Pandas-DataFrames getestet.
   **Wichtig:** Die aktuell im Repo liegenden `data/rs_*.json` wurden noch
   NICHT mit dieser neuen Version neu generiert (das passiert erst beim
   nächsten Lauf der GitHub-Actions-Workflows `update_rs.yml` etc.) — bis
   dahin liefern `dollar_vol_20d`/`volume_confirmed` in `/api/v2` weiterhin
   `null` (fail-safe, kein Fehler).
7. **`fetch_earnings_calendar.py`** — Cache-Skript für `data/earnings_calendar.json`
   (Ticker → nächster Earnings-Termin). **Läuft NICHT automatisch** (keine
   GitHub-Actions-Workflow-Datei angelegt — bewusste Entscheidung, siehe unten).
8. **`backtest_v2/`** — Portfolio-Backtest-Engine (`engine.py`, `signals.py`,
   `metrics.py`, `run.py`), reused `backend/gws_analysis.py` und
   `backend/v2_analysis.py` direkt (Regel B10). **Erste echte Läufe für alle
   vier Märkte durchgeführt und in `backtest_v2/results/` abgelegt — lies
   `backtest_v2/results/README.md` für die Ergebnisse und deren ehrliche
   Einordnung, bevor du hier weiterarbeitest.** Wichtigstes Ergebnis: Die
   Strategie unterliegt in diesem Zeitraum (~2 Jahre, überwiegend Bullenmarkt,
   kein echter Bärenmarkt enthalten) in allen vier Märkten dem
   Buy-and-Hold-Vergleich. Das ist ein echter Befund, keine Kalibrierungs-
   Vorlage — siehe Einschränkungen unten.
9. **`analyses/PROMPT.md`** — neue Pflichtzeile `**Funnel-Entscheidung:**
   PASS|REDUCE|VETO — Kategorie: … — Begründung` in Abschnitt 11.
   `generate_rating.py` parst sie additiv (`_extract_funnel_veto()`,
   `funnel_veto`-Feld in `data/ratings/index.json`) — bestehende Q/G/V/K-
   Score-Logik unverändert, Rückwärtskompatibilität mit älteren Analysen
   ohne diese Zeile geprüft (liefert `None`).
10. **`update_signal_journal.py`** + **`data/signal_journal.json`** — loggt
    täglich alle KAUFLISTE/KANDIDAT/EARNINGS-SPERRE-Signale aus allen vier
    Märkten und trägt automatisch Folgerenditen (1/4/13/26 Wochen) aus der
    eigenen OHLCV-Historie nach, sobald die Fenster erreicht sind. Erster
    Lauf: 121 echte Einträge vom 2026-07-03. **Läuft NICHT automatisch.**

**Wichtigstes Prinzip, das für den gesamten weiteren Ausbau gilt:**
Die bestehende Plattform (v1) bleibt **byte-für-byte unverändert nutzbar**.
Alles Neue entsteht in eigenen Dateien (`v2_*.py`, `v2.html`, `backtest_v2/`)
und zusätzlichen `/api/v2/...`-Routen. Wo eine Änderung an geteiltem Code
(z. B. `backend/gws_analysis.py`) fachlich nötig wäre, gilt: nur
**erweitern**, nie bestehende Funktionssignaturen ändern, die v1 verwendet.
Wenn unklar, ob eine Änderung dieses Prinzip verletzt: NICHT umsetzen,
sondern im Chat kurz zur Bestätigung vorlegen.

**Zweitwichtigstes Prinzip:** Produktions-Infrastruktur (neue
GitHub-Actions-Workflows, die automatisch laufen und Yahoo-Finance-Requests
für hunderte Ticker auslösen) wird NICHT eigenmächtig angelegt. Die Skripte
`fetch_earnings_calendar.py` und `update_signal_journal.py` existieren
lauffähig, aber unscheduled — der Nutzer entscheidet, ob/wann sie automatisiert
werden.

---

## Bekannte Umgebungs-Einschränkung: kein Netzwerkzugriff auf Yahoo Finance

In der Sandbox, in der dieser Stand entstanden ist, blockiert der
Netzwerk-Proxy Zugriffe auf `query1.finance.yahoo.com` (403 beim
`yf.download()`-Aufruf). Das bedeutet:
- Keine neuen/längeren Kursdaten ladbar — alle Backtest-Läufe verwenden
  ausschließlich die bereits im Repo committeten JSONs.
- Die synchronisierten Ticker+Benchmark-Daten (`data/rs_*.json`) decken nur
  **~2 Jahre** ab (2024-06/07 bis heute) — nicht die für Regel B4 geforderte
  Trainingsperiode 2016–2021.
- `fetch_earnings_calendar.py` und weitere Datenupgrades konnten nicht mit
  echten Daten befüllt/verifiziert werden (nur mit synthetischen Testfällen).

**Falls diese Session Netzwerkzugriff hat**, zuerst prüfen (`yf.download('QQQ',
period='5d')`) — falls ja, sind die folgenden Punkte 6/7 aus der Roadmap
(historische Indexmitgliedschaft, Out-of-Sample-Kalibrierung 2016–2021/
2022–2026) direkt angehbar und sollten priorisiert werden, da sie die
größte verbleibende Lücke zu einer belastbaren Strategie-Validierung sind.

---

## Auftrag — was als Nächstes zu tun ist

### Phase B — Rest (höchste Priorität, sobald Netzwerkzugriff verfügbar ist)

1. **Historische Indexmitgliedschaft** (Regel B3): `data/index_history.json`
   aus der Wikipedia-Änderungshistorie rekonstruieren (NASDAQ-100, S&P 500,
   DAX). Neues Skript `fetch_index_history.py`.

2. **Längere, netzwerk-nachgeladene Historie + Out-of-Sample-Kalibrierung**
   (B4/B5): Trainingsfenster bis 2021, Validierung 2022–2026 (Pflicht: enthält
   den Bärenmarkt 2022). Sensitivitätsanalyse ±30 % auf: `RS2_WINDOWS`,
   `REGIME_THRESHOLDS`, `MAX_STOP_ATR`, `TIME_STOP_DAYS`. Erst NACH Punkt 1+2
   sinnvoll — vorher würde jede Kalibrierung auf dem verzerrten, zu kurzen
   ~2-Jahres-Fenster overfitten (Regel B5 warnt explizit davor).

3. **`backtest_v2/engine.py` erweitern**, sobald mehr Historie da ist: aktuell
   ist die Engine bewusst auf Weekly+Daily-GWS (2/2, kein 4H) begrenzt, weil
   die Markt-JSONs nur ein 60-Tage-Rolling-Fenster an 4H-Daten halten (Regel
   B9). Mit `load_backtest.py`-artigen Einzelticker-Dateien (die period="max"
   für Weekly nutzen) ließe sich das ggf. umgehen — prüfen, ob ein
   synchronisierter Benchmark (QQQ) mit vergleichbarer Tiefe beschaffbar ist.

### Phase C — Rest

4. **`signal_journal_report.py`**: Quartalsauswertung, die die drei Fragen aus
   `STRATEGIEPLAN.md` Abschnitt 7 beantwortet (schlagen PASS-Titel VETO-Titel?
   Korreliert Verdict-Score mit Folgerendite? Funktioniert die Regime-Ampel
   live?). Noch nicht gebaut — `data/signal_journal.json` hat aktuell erst
   einen einzigen Tages-Snapshot (2026-07-03), zu wenig für eine sinnvolle
   Auswertung. Sollte erst gebaut werden, wenn über mehrere Wochen/Monate
   Journal-Daten vorliegen (`update_signal_journal.py` regelmäßig laufen
   lassen, manuell oder — nach Rücksprache mit dem Nutzer — per Workflow).

5. **Exit-Regelwerk 2.0 im wikifolio verankern**: Das Regelwerk aus
   `STRATEGIEPLAN.md` Abschnitt 3 ist in `v2.html` dokumentiert, aber noch
   nicht dort verankert, wo tatsächliche wikifolio-Trades entschieden werden
   (`instagram/CONTEXT.md` / `CLAUDE.md`). Nur nach Rücksprache mit dem
   Nutzer (Single-Source-of-Truth-Regel, und weil das reale Handelsentscheidungen
   betrifft, keine reine Code-Änderung).

6. **Earnings-Sperre + Signal-Journal mit echten Daten validieren**, sobald
   Netzwerkzugriff besteht: `fetch_earnings_calendar.py` einmal laufen lassen,
   `/api/v2/{market}` erneut prüfen, ob `EARNINGS-SPERRE`-Status tatsächlich
   auftritt.

---

## Arbeitsweise / Leitplanken

- **Immer zuerst lesen:** `STRATEGIEPLAN.md`, `backtest_v2/results/README.md`
  und die konkret betroffene(n) Datei(en), bevor editiert wird.
- **v1 niemals anfassen**, außer additive Nav-Bar-Ergänzungen.
- **Kein Look-Ahead-Bias**: Bei jeder neuen Signal-/Backtest-Funktion prüfen,
  ob nur Daten verwendet werden, die zum Signalzeitpunkt bereits bekannt
  waren (Regel B1). In `backtest_v2/engine.py` wurde dazu bereits ein
  echter Bug gefunden und behoben (Positionsgrößen-Berechnung verwendete
  fälschlich den Benchmark- statt den Ticker-Schlusskurs — siehe
  `backtest_v2/results/README.md`) — bei jeder Änderung an der Engine mit
  einem kleinen Sanity-Check (max. Positionsgewicht plausibel? Keine
  Einzelposition > 15–20 % des Portfolios?) erneut gegenprüfen.
- **Smoke-Test nach jeder Backend-Änderung:** `python3 -c "import ast;
  ast.parse(open('main.py').read())"`, danach `fastapi.testclient.TestClient`
  (Context-Manager wegen Startup-Event!) gegen neuen UND unveränderten
  v1-Endpoint (`/api/rs/nasdaq`). `DATA_DIR` env var auf `data/` setzen.
- **Backtest-Läufe:** `python3 backtest_v2/run.py <market>` dauert
  ~10–60 Sekunden pro Markt (Smallcap/S&P 500 am längsten). Ergebnis immer
  gegen Plausibilität prüfen (siehe Bug-Beispiel oben), bevor es als Report
  interpretiert wird.
- **Git:** Nach jedem sinnvollen Zwischenschritt committen, Hash im Chat
  ausgeben (`[a3f92c1] Commit-Nachricht`).
- **Keine neuen Abhängigkeiten ohne Not** — `requirements.txt` prüfen.
- **Keine neuen automatisch laufenden GitHub-Actions-Workflows** ohne
  Rücksprache mit dem Nutzer (siehe oben).

---

## Definition of Done

Nach Abschluss der bearbeiteten Phase(n):
- Neuer Code lauffähig, gegen echte Daten smoke-getestet
- `v1`-Endpoints/-Seiten nachweislich unverändert (`git diff` gegen einen
  älteren Commit sollte für v1-Dateien leer sein, bis auf den Nav-Button)
- `STRATEGIEPLAN.md` und `backtest_v2/results/README.md` aktualisiert, wenn
  sich Parameter durch Kalibrierung geändert haben — alte Werte ersetzen,
  nicht ergänzen (Single-Source-of-Truth-Regel aus `CLAUDE.md`)
- Commit(s) gepusht, Hash im Chat ausgegeben
