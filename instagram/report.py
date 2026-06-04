"""
Loader für den wöchentlichen Report (Quelle der Wahrheit für den Wochenpost).

Du fütterst pro Woche eine JSON nach instagram/reports/KW<NN>.json
(Format siehe reports/KW21.example.json). In einer neuen Claude-Session genügt
es, den wikifolio-Wochenfeed einzufügen – Claude füllt daraus diese JSON
(siehe instagram/PROMPT.md) und ruft den Generator auf.
"""
import json
from datetime import date


def week_friday(year, kw):
    """ISO-Freitag der Kalenderwoche -> ISO-Datumsstring."""
    return date.fromisocalendar(year, kw, 5).isoformat()


def equity_curve(history, year, start_kw=None):
    """Baut aus den Wochenrenditen eine indexierte Equity-Kurve (Start=100)."""
    hist = sorted(history, key=lambda h: h["kw"])
    if not hist:
        return [], []
    start_kw = start_kw or (hist[0]["kw"] - 1)
    dates = [week_friday(year, start_kw)]
    vals = [100.0]
    for h in hist:
        vals.append(vals[-1] * (1 + h["perf"]))
        dates.append(week_friday(year, h["kw"]))
    return dates, vals


def load_report(path):
    with open(path) as f:
        r = json.load(f)
    r.setdefault("year", 2026)
    r.setdefault("buys", [])
    r.setdefault("sells", [])
    r.setdefault("top_holdings", [])

    hist = r.get("history", [])
    wins = [h["perf"] for h in hist if h["perf"] >= 0]
    losses = [h["perf"] for h in hist if h["perf"] < 0]
    r["avg_win"] = sum(wins) / len(wins) if wins else 0.0
    r["avg_loss"] = sum(losses) / len(losses) if losses else 0.0
    if "weeks_beaten" not in r:
        r["weeks_beaten"] = len(wins)
    r.setdefault("weeks_total", len(hist))
    if "alpha" not in r and "nasdaq_total" in r:
        r["alpha"] = r["total_perf"] - r["nasdaq_total"]

    r["eq_dates"], r["eq_vals"] = equity_curve(hist, r["year"])
    return r
