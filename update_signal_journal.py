"""
update_signal_journal.py — Signal-Journal für die Forward-Tracking-Feedback-
Schleife (STRATEGIEPLAN.md Abschnitt 7).

Vier Aufgaben bei jedem Lauf:
1. Heutigen Funnel-Snapshot (KAUFLISTE/KANDIDAT-Ticker aus /api/v2-Logik)
   als neue Journal-Einträge anhängen (ein Eintrag pro Ticker+Markt+Datum,
   keine Duplikate). verdict_score/funnel_veto werden dabei aus
   data/ratings/index.json übernommen, aber NUR wenn die Analyse am
   Log-Tag bereits existierte (kein Look-Ahead, analog Backtest-Regel B1).
2. Bestehende Einträge ohne verdict_score/funnel_veto nachträglich
   befüllen, falls inzwischen eine zum Log-Datum passende (nicht spätere)
   Analyse verfügbar ist.
3. Bei Einträgen, deren Folgerendite-Fenster (1/4/13/26 Wochen) inzwischen
   erreicht ist, die tatsächliche Rendite aus der eigenen OHLCV-Historie
   des Tickers UND die Benchmark-Rendite im selben Fenster nachtragen —
   daraus die Alpha-Rendite (Ticker minus Benchmark) berechnen. Ohne
   Benchmark-Bezug sagt eine positive Rendite in einer Rally nichts über
   den Signalwert aus.
4. Läuft automatisch via .github/workflows/update_signal_journal.yml
   (Di-Sa 02:00 UTC, nach allen Markt-Updates).

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
RATINGS_PATH = DATA_DIR / "ratings" / "index.json"
MARKET_FILES = {"nasdaq": "rs_full.json", "sp500": "rs_sp500.json",
                "dax": "rs_dax.json", "smallcap": "rs_smallcap.json"}
LOGGED_STATUSES = {"KAUFLISTE", "KANDIDAT", "EARNINGS-SPERRE"}

# Handelstage-Näherung je Fenster (kein Handelskalender verfügbar)
FWD_WINDOWS = {"1w": 5, "4w": 20, "13w": 65, "26w": 130}


def load_ratings_by_ticker() -> dict:
    if not RATINGS_PATH.exists():
        return {}
    ratings = json.loads(RATINGS_PATH.read_text(encoding="utf-8")).get("ratings", [])
    return {r["ticker"].upper(): r for r in ratings}


def _rating_for_entry(ratings_by_ticker: dict, ticker: str, entry_date: str):
    """Gibt (verdict_score, funnel_veto) zurück — nur wenn die Analyse am oder vor
    entry_date erstellt wurde (kein Look-Ahead). Sonst (None, None)."""
    r = ratings_by_ticker.get(ticker.upper())
    if not r or not r.get("created_at"):
        return None, None
    if r["created_at"][:10] > entry_date:
        return None, None
    return r.get("score"), r.get("funnel_veto")


def load_journal() -> dict:
    if JOURNAL_PATH.exists():
        return json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))
    return {"schema_version": 1, "entries": []}


def save_journal(journal: dict):
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL_PATH.write_text(json.dumps(journal, indent=2, ensure_ascii=False), encoding="utf-8")


def append_today_snapshot(journal: dict, today: str, ratings_by_ticker: dict):
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
            verdict_score, funnel_veto = _rating_for_entry(ratings_by_ticker, row["ticker"], today)
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
                "verdict_score": verdict_score,
                "funnel_veto": funnel_veto,
                "fwd_returns": {k: None for k in FWD_WINDOWS},
                "fwd_alpha": {k: None for k in FWD_WINDOWS},
            })
            added += 1
    return added


def backfill_verdict_data(journal: dict, ratings_by_ticker: dict) -> int:
    """Befüllt verdict_score/funnel_veto bei bestehenden Einträgen nach, deren
    Analyse zum Log-Zeitpunkt noch fehlte, aber inzwischen (zum oder vor dem
    Log-Datum) existiert — kein Look-Ahead, siehe _rating_for_entry."""
    filled = 0
    for entry in journal["entries"]:
        if entry.get("verdict_score") is not None:
            continue
        verdict_score, funnel_veto = _rating_for_entry(ratings_by_ticker, entry["ticker"], entry["date"])
        if verdict_score is not None:
            entry["verdict_score"] = verdict_score
            entry["funnel_veto"] = funnel_veto
            filled += 1
    return filled


def backfill_forward_returns(journal: dict):
    ohlcv_cache = {}
    bench_cache = {}
    filled = 0
    alpha_filled = 0
    for entry in journal["entries"]:
        if all(v is not None for v in entry["fwd_returns"].values()):
            continue
        cache_key = entry["market"]
        if cache_key not in ohlcv_cache:
            path = DATA_DIR / MARKET_FILES[entry["market"]]
            if not path.exists():
                ohlcv_cache[cache_key] = {}
                bench_cache[cache_key] = []
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            ohlcv_cache[cache_key] = {
                e["ticker"]: e.get("ohlcv", []) for e in raw.get("data", [])
            }
            bench_cache[cache_key] = raw.get("benchmark_ohlcv", [])
        ohlcv = ohlcv_cache[cache_key].get(entry["ticker"])
        if not ohlcv:
            continue
        bench = bench_cache.get(cache_key, [])
        bench_dates = [row["d"] for row in bench]

        dates = [row["d"] for row in ohlcv]
        try:
            log_idx = dates.index(entry["date"])
        except ValueError:
            continue
        base_close = ohlcv[log_idx]["c"]

        bench_base_idx = bench_dates.index(entry["date"]) if entry["date"] in bench_dates else None
        bench_base_close = bench[bench_base_idx]["c"] if bench_base_idx is not None else None

        entry.setdefault("fwd_alpha", {k: None for k in FWD_WINDOWS})
        for label, offset in FWD_WINDOWS.items():
            target_idx = log_idx + offset
            already_has_return = entry["fwd_returns"].get(label) is not None
            needs_alpha = entry["fwd_alpha"].get(label) is None
            if already_has_return and not needs_alpha:
                continue
            if target_idx >= len(ohlcv):
                continue

            if already_has_return:
                ret = entry["fwd_returns"][label]
            else:
                ret = round((ohlcv[target_idx]["c"] / base_close - 1) * 100, 2)
                entry["fwd_returns"][label] = ret
                filled += 1

            if needs_alpha and bench_base_close is not None and bench_base_idx + offset < len(bench):
                bench_ret = (bench[bench_base_idx + offset]["c"] / bench_base_close - 1) * 100
                entry["fwd_alpha"][label] = round(ret - bench_ret, 2)
                alpha_filled += 1
    return filled, alpha_filled


def main():
    today = date.today().isoformat()
    journal = load_journal()
    ratings_by_ticker = load_ratings_by_ticker()
    added = append_today_snapshot(journal, today, ratings_by_ticker)
    backfilled_verdicts = backfill_verdict_data(journal, ratings_by_ticker)
    filled, alpha_filled = backfill_forward_returns(journal)
    journal["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_journal(journal)
    print(f"Signal-Journal: {added} neue Einträge, {backfilled_verdicts} Verdict/Funnel nachgetragen, "
          f"{filled} Folgerenditen + {alpha_filled} Alpha-Werte nachgetragen "
          f"({len(journal['entries'])} Einträge gesamt) — {JOURNAL_PATH}")


if __name__ == "__main__":
    main()
