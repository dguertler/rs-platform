"""
Persistente Wochen-Logik für den Instagram-Generator.

Liest die gespeicherten Daten unter instagram/data/ …
  - config.json            Stammdaten (Symbol, Startdatum, Startwert)
  - wikifolio_history.json Zertifikatswert je KW
  - holdings.json          Top-Positionen + Kaufdatum (+ Rotation)

… und berechnet daraus für eine KW alles Nötige:
  - Wochen-/Gesamtrendite, NASDAQ-Vergleich (aus Repo-Daten), Alpha
  - Wochen-Historie + „X von Y Wochen geschlagen"
  - Performance der Top-Positionen seit Kauf
  - die rotierende „Aktie der Woche" inkl. Signale

NASDAQ wird aus dem QQQ-Benchmark in data/rs_full.json gezogen – kein
externer Aufruf nötig.
"""
import json
import os

from . import data, report

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load(name):
    with open(os.path.join(DATA_DIR, name)) as f:
        return json.load(f)


def load_config():
    return _load("config.json")


def load_history():
    return _load("wikifolio_history.json")


def load_holdings():
    return _load("holdings.json")


def append_week(kw, value):
    """Hängt einen Zertifikatswert für KW an (oder aktualisiert ihn)."""
    h = load_history()
    weekly = [w for w in h["weekly"] if w["kw"] != kw]
    weekly.append({"kw": kw, "value": round(float(value), 2)})
    weekly.sort(key=lambda w: w["kw"])
    h["weekly"] = weekly
    with open(os.path.join(DATA_DIR, "wikifolio_history.json"), "w") as f:
        json.dump(h, f, indent=2, ensure_ascii=False)
    return h


def _qqq_on(benchmark, date_iso):
    """Letzter QQQ-Schlusskurs am/ vor date_iso."""
    val = None
    for d, c in benchmark:
        if d <= date_iso:
            val = c
        else:
            break
    return val


def _ret_since(universe, ticker, buy_date):
    """Reale Rendite vom Schlusskurs am/ nach Kaufdatum bis zum letzten Kurs."""
    if ticker not in universe or not universe[ticker]["ohlcv"]:
        return None, None
    ohlcv = universe[ticker]["ohlcv"]
    entry = next((c for c in ohlcv if c["d"] >= buy_date), None)
    if not entry:
        return None, None
    return ohlcv[-1]["c"] / entry["c"] - 1.0, entry


def compute(kw, universe, benchmark):
    cfg = load_config()
    year = cfg["year"]
    start_date, start_value = cfg["start_date"], cfg["start_value"]

    weekly = sorted((w for w in load_history()["weekly"] if w["kw"] <= kw),
                    key=lambda w: w["kw"])
    if not weekly:
        raise ValueError(f"Keine wikifolio-Werte bis KW{kw} in wikifolio_history.json")

    # ── Equity-Kurve (auf 100 indexiert) ─────────────────────────────────────
    dates = [start_date] + [report.week_friday(year, w["kw"]) for w in weekly]
    vals = [start_value] + [w["value"] for w in weekly]
    eq_vals = [v / start_value * 100 for v in vals]
    total_perf = vals[-1] / vals[0] - 1
    week_perf = vals[-1] / vals[-2] - 1 if len(vals) > 1 else 0.0

    # ── NASDAQ (QQQ) im selben Zeitfenster, auf 100 indexiert ────────────────
    nas_raw = [_qqq_on(benchmark, d) for d in dates]
    nas_raw = [v for v in nas_raw if v]  # robust
    nas_vals = [v / nas_raw[0] * 100 for v in nas_raw] if nas_raw else []
    nasdaq_total = nas_raw[-1] / nas_raw[0] - 1 if len(nas_raw) > 1 else 0.0
    nasdaq_week = nas_raw[-1] / nas_raw[-2] - 1 if len(nas_raw) > 1 else 0.0
    alpha = total_perf - nasdaq_total

    # ── Wochen-Historie + „geschlagen" ───────────────────────────────────────
    history, beaten = [], 0
    prev_v, prev_n = start_value, nas_raw[0] if nas_raw else None
    for i, w in enumerate(weekly):
        wk = w["value"] / prev_v - 1
        history.append({"kw": w["kw"], "perf": wk})
        if prev_n and i + 1 < len(nas_raw):
            if wk > (nas_raw[i + 1] / prev_n - 1):
                beaten += 1
            prev_n = nas_raw[i + 1]
        prev_v = w["value"]
    wins = [h["perf"] for h in history if h["perf"] >= 0]
    losses = [h["perf"] for h in history if h["perf"] < 0]

    # ── Top-Positionen: Performance seit Kauf ────────────────────────────────
    hold = load_holdings()
    positions = hold["positions"]
    top = []
    for p in positions:
        ret, _ = _ret_since(universe, p["ticker"], p["buy_date"])
        if ret is not None:
            top.append({**p, "ret": ret})
    top.sort(key=lambda t: t["ret"], reverse=True)

    # ── „Aktie der Woche" (Rotation) ─────────────────────────────────────────
    base_kw = hold.get("base_kw", weekly[0]["kw"])
    feat = positions[(kw - base_kw) % len(positions)]
    feat_ret, feat_entry = _ret_since(universe, feat["ticker"], feat["buy_date"])
    feat_signals = data.load_signals().get(feat["ticker"], [])

    return {
        "kw": kw,
        "period": _period(start_date, dates[-1]),
        "name": cfg["name"], "account": cfg["account"], "url": cfg["wikifolio_url"],
        "eq_dates": dates, "eq_vals": eq_vals,
        "nas_dates": dates[:len(nas_vals)], "nas_vals": nas_vals,
        "week_perf": week_perf, "total_perf": total_perf,
        "nasdaq_week": nasdaq_week, "nasdaq_total": nasdaq_total, "alpha": alpha,
        "history": history,
        "weeks_beaten": beaten, "weeks_total": len(history),
        "avg_win": sum(wins) / len(wins) if wins else 0.0,
        "avg_loss": sum(losses) / len(losses) if losses else 0.0,
        "top_holdings": top,
        "featured": {
            "ticker": feat["ticker"], "name": feat.get("name", ""),
            "buy_date": feat["buy_date"], "buy_price_eur": feat.get("buy_price_eur"),
            "ret": feat_ret, "entry": feat_entry,
            "ohlcv": universe[feat["ticker"]]["ohlcv"], "signals": feat_signals,
        },
    }


def _period(start_iso, end_iso):
    from datetime import datetime
    s = datetime.strptime(start_iso, "%Y-%m-%d").strftime("%d.%m.")
    e = datetime.strptime(end_iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    return f"{s} – {e}"
