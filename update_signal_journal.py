"""
update_signal_journal.py — Signal-Journal für die Forward-Tracking-Feedback-
Schleife (STRATEGIEPLAN.md Abschnitt 7).

Zwei Aufgaben bei jedem Lauf:
1. Heutigen Funnel-Snapshot (KAUFLISTE/KANDIDAT-Ticker aus /api/v2-Logik)
   als neue Journal-Einträge anhängen (ein Eintrag pro Ticker+Markt+Datum,
   keine Duplikate).
2. Bei bestehenden Einträgen, deren Folgerendite-Fenster (1/4/13/26 Wochen)
   inzwischen erreicht ist, die tatsächliche Rendite aus der eigenen
   OHLCV-Historie des Tickers nachtragen.

Läuft NICHT automatisch (kein GitHub-Actions-Workflow angelegt) — analog zu
fetch_earnings_calendar.py bewusst dem Nutzer überlassen, siehe
PROMPT_V2_UMSETZUNG.md Punkt 10.

Nutzung: python3 update_signal_journal.py
"""
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))
from v2_analysis import build_v2_payload  # noqa: E402

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
JOURNAL_PATH = DATA_DIR / "signal_journal.json"
MARKET_FILES = {"nasdaq": "rs_full.json", "sp500": "rs_sp500.json",
                "dax": "rs_dax.json", "smallcap": "rs_smallcap.json"}
LOGGED_STATUSES = {"KAUFLISTE", "KANDIDAT", "EARNINGS-SPERRE"}

# Handelstage-Näherung je Fenster (kein Handelskalender verfügbar)
FWD_WINDOWS = {"1w": 5, "4w": 20, "13w": 65, "26w": 130}


def load_journal() -> dict:
    if JOURNAL_PATH.exists():
        return json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))
    return {"schema_version": 1, "entries": []}


def save_journal(journal: dict):
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL_PATH.write_text(json.dumps(journal, indent=2, ensure_ascii=False), encoding="utf-8")


def append_today_snapshot(journal: dict, today: str):
    fund_path = DATA_DIR / "fundamentals.json"
    fund = json.loads(fund_path.read_text(encoding="utf-8")).get("tickers", {}) if fund_path.exists() else {}
    earnings_path = DATA_DIR / "earnings_calendar.json"
    earnings_map = (json.loads(earnings_path.read_text(encoding="utf-8")).get("next_earnings", {})
                    if earnings_path.exists() else {})

    existing_keys = {(e["date"], e["market"], e["ticker"]) for e in journal["entries"]}
    added = 0

    for market, fn in MARKET_FILES.items():
        path = DATA_DIR / fn
        if not path.exists():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        payload = build_v2_payload(raw, fund, market, earnings_map=earnings_map)
        for row in payload["data"]:
            if row["status"] not in LOGGED_STATUSES:
                continue
            key = (today, market, row["ticker"])
            if key in existing_keys:
                continue
            journal["entries"].append({
                "date": today,
                "market": market,
                "ticker": row["ticker"],
                "close_at_log": row["close"],
                "rs2_pct": row["rs2_pct"],
                "regime": payload["regime"]["label"],
                "setup_pts": row["setup_pts"],
                "gws_pts": row["gws"]["pts"],
                "status": row["status"],
                "verdict_score": None,   # von generate_rating.py/Analyse zu befüllen, falls vorhanden
                "funnel_veto": None,
                "fwd_returns": {k: None for k in FWD_WINDOWS},
            })
            added += 1
    return added


def backfill_forward_returns(journal: dict):
    ohlcv_cache = {}
    filled = 0
    for entry in journal["entries"]:
        if all(v is not None for v in entry["fwd_returns"].values()):
            continue
        cache_key = entry["market"]
        if cache_key not in ohlcv_cache:
            path = DATA_DIR / MARKET_FILES[entry["market"]]
            if not path.exists():
                ohlcv_cache[cache_key] = {}
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            ohlcv_cache[cache_key] = {
                e["ticker"]: e.get("ohlcv", []) for e in raw.get("data", [])
            }
        ohlcv = ohlcv_cache[cache_key].get(entry["ticker"])
        if not ohlcv:
            continue
        dates = [row["d"] for row in ohlcv]
        try:
            log_idx = dates.index(entry["date"])
        except ValueError:
            continue
        base_close = ohlcv[log_idx]["c"]
        for label, offset in FWD_WINDOWS.items():
            if entry["fwd_returns"].get(label) is not None:
                continue
            target_idx = log_idx + offset
            if target_idx < len(ohlcv):
                ret = round((ohlcv[target_idx]["c"] / base_close - 1) * 100, 2)
                entry["fwd_returns"][label] = ret
                filled += 1
    return filled


def main():
    today = date.today().isoformat()
    journal = load_journal()
    added = append_today_snapshot(journal, today)
    filled = backfill_forward_returns(journal)
    journal["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_journal(journal)
    print(f"Signal-Journal: {added} neue Einträge, {filled} Folgerenditen nachgetragen "
          f"({len(journal['entries'])} Einträge gesamt) — {JOURNAL_PATH}")


if __name__ == "__main__":
    main()
