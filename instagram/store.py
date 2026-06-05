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
from datetime import datetime, timedelta

from . import data, report

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Ab dieser absoluten Rendite gilt ein realisierter Trade als „grosser Verkauf"
# und bekommt einen eigenen Kauf-/Verkauf-Chart (statt „Aktie der Woche").
BIG_SELL_THRESHOLD = 0.25


def _load(name):
    with open(os.path.join(DATA_DIR, name)) as f:
        return json.load(f)


def load_config():
    return _load("config.json")


def load_history():
    return _load("wikifolio_history.json")


def load_holdings():
    return _load("holdings.json")


def load_trades():
    try:
        return _load("trades.json")
    except FileNotFoundError:
        return {"closed": []}


def _featured_dict(universe, p, as_of=None):
    """Baut die Daten für eine Chart-Slide (Aktie der Woche / Newcomer)."""
    ret, entry = _ret_since(universe, p["ticker"], p["buy_date"], as_of)
    ohlcv = universe[p["ticker"]]["ohlcv"]
    if as_of:
        ohlcv = [c for c in ohlcv if c["d"] <= as_of]
    return {
        "ticker": p["ticker"], "name": p.get("name", ""),
        "buy_date": p["buy_date"], "buy_price_eur": p.get("buy_price_eur"),
        "ret": ret, "entry": entry,
        "ohlcv": ohlcv,
        "signals": data.load_signals().get(p["ticker"], []),
    }


def _snapshot(kw):
    """Optionaler historischer Depot-Snapshot in
    instagram/data/snapshots/KW<kw>.json (Felder: base_kw, positions, closed).
    Ermöglicht historisch korrekte Slides vergangener Wochen, ohne die Live-Daten
    (holdings.json/trades.json) zu verändern."""
    path = os.path.join(DATA_DIR, "snapshots", f"KW{kw}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _big_sell(universe, closed_raw, kw, as_of=None):
    """Groesster realisierter Trade der laufenden KW (|ret| >= Schwelle) mit
    genug Chart-Metadaten, um Kauf UND Verkauf einzuzeichnen. Sonst None."""
    cand = [
        t for t in closed_raw
        if t.get("kw") == kw and t.get("ticker") in universe
        and t.get("buy_date") and universe[t["ticker"]]["ohlcv"]
        and abs(t.get("ret", 0)) >= BIG_SELL_THRESHOLD
    ]
    if not cand:
        return None
    t = max(cand, key=lambda x: abs(x["ret"]))
    ohlcv = universe[t["ticker"]]["ohlcv"]
    if as_of:
        ohlcv = [c for c in ohlcv if c["d"] <= as_of]
        if not ohlcv:
            return None
    entry = next((c for c in ohlcv if c["d"] >= t["buy_date"]), None)
    sell_date = t.get("sell_date") or ohlcv[-1]["d"]
    exit_pt = next((c for c in reversed(ohlcv) if c["d"] <= sell_date), ohlcv[-1])
    if not entry:
        return None
    return {
        "ticker": t["ticker"], "name": t.get("name", ""),
        "buy_date": t["buy_date"], "sell_date": sell_date,
        "buy_price_eur": t.get("buy_price_eur"),
        "sell_price_eur": t.get("sell_price_eur"),
        "ret": t["ret"], "ohlcv": ohlcv, "entry": entry, "exit": exit_pt,
    }


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


def _ret_since(universe, ticker, buy_date, as_of=None):
    """Reale Rendite vom Schlusskurs am/ nach Kaufdatum bis zum Stichtag (as_of)
    bzw. bis zum letzten verfügbaren Kurs."""
    if ticker not in universe or not universe[ticker]["ohlcv"]:
        return None, None
    ohlcv = universe[ticker]["ohlcv"]
    if as_of:
        ohlcv = [c for c in ohlcv if c["d"] <= as_of]
        if not ohlcv:
            return None, None
    entry = next((c for c in ohlcv if c["d"] >= buy_date), None)
    if not entry:
        return None, None
    return ohlcv[-1]["c"] / entry["c"] - 1.0, entry


def compute(kw, universe, benchmark, ref_date=None):
    cfg = load_config()
    year = cfg["year"]
    start_date, start_value = cfg["start_date"], cfg["start_value"]

    weekly = sorted((w for w in load_history()["weekly"] if w["kw"] <= kw),
                    key=lambda w: w["kw"])
    if not weekly:
        raise ValueError(f"Keine wikifolio-Werte bis KW{kw} in wikifolio_history.json")

    # ── Equity-Kurve (auf 100 indexiert) ─────────────────────────────────────
    dates = [start_date] + [w.get("date") or report.week_friday(year, w["kw"]) for w in weekly]
    vals = [start_value] + [w["value"] for w in weekly]
    eq_vals = [v / start_value * 100 for v in vals]
    total_perf = vals[-1] / vals[0] - 1
    week_perf = vals[-1] / vals[-2] - 1 if len(vals) > 1 else 0.0

    # ── NASDAQ (NDX/QQQ) im selben Zeitfenster, auf 100 indexiert ────────────
    # Optionaler Override pro Woche via "nasdaq_value" (absoluter NDX-Indexstand)
    # in wikifolio_history.json – z. B. wenn die RS-JSON den Tageswert noch nicht
    # enthält. Greift fuer Wochen- UND Gesamtrendite/Alpha gleichermassen.
    nas_raw = [_qqq_on(benchmark, dates[0])]
    for i, w in enumerate(weekly):
        ov = w.get("nasdaq_value")
        nas_raw.append(ov if ov is not None else _qqq_on(benchmark, dates[i + 1]))
    nas_raw = [v for v in nas_raw if v]  # robust
    nas_vals = [v / nas_raw[0] * 100 for v in nas_raw] if nas_raw else []
    nasdaq_total = nas_raw[-1] / nas_raw[0] - 1 if len(nas_raw) > 1 else 0.0
    nasdaq_week = nas_raw[-1] / nas_raw[-2] - 1 if len(nas_raw) > 1 else 0.0
    alpha = total_perf - nasdaq_total

    # ── Wochen-Historie: wöchentliche Mehrrendite ggü. NASDAQ ────────────────
    history, beaten = [], 0
    prev_v, prev_n = start_value, nas_raw[0] if nas_raw else None
    def _r1(x):                                    # auf 1 Nachkommastelle (% wie im Report)
        return round(x * 100, 1) / 100
    for i, w in enumerate(weekly):
        wk = w["value"] / prev_v - 1
        if "nasdaq_pct" in w:                      # vom Nutzer hinterlegter NDX-Wert
            nwk = w["nasdaq_pct"]
        else:
            nwk = (nas_raw[i + 1] / prev_n - 1) if (prev_n and i + 1 < len(nas_raw)) else 0.0
        dev = _r1(wk) - _r1(nwk)                    # Differenz der gerundeten Wochenwerte
        history.append({"kw": w["kw"], "perf": wk, "nasdaq": nwk, "dev": dev})
        if dev >= 0:                               # Gleichstand zählt als „geschlagen" (wie Report)
            beaten += 1
        prev_v = w["value"]
        if i + 1 < len(nas_raw):
            prev_n = nas_raw[i + 1]

    # ── Depotstand: Live-Daten oder historischer Snapshot (vergangene KW) ────
    # Stichtag = Datum der Woche; Kurse werden darauf begrenzt (historisch korrekt).
    as_of = dates[-1]
    snap = _snapshot(kw)
    hold = snap or load_holdings()

    # ── Top-Positionen: Performance seit Kauf (bis Stichtag) ─────────────────
    positions = hold["positions"]
    top = []
    for p in positions:
        ret, _ = _ret_since(universe, p["ticker"], p["buy_date"], as_of)
        if ret is not None:
            top.append({**p, "ret": ret})
    top.sort(key=lambda t: t["ret"], reverse=True)
    top5_tickers = {t["ticker"] for t in top[:5]}

    # ── Trade-Kennzahlen: abgeschlossene + aktive Trades zusammen ────────────
    closed_raw = snap["closed"] if (snap and "closed" in snap) else load_trades().get("closed", [])
    closed = [t["ret"] for t in closed_raw]
    active = [t["ret"] for t in top]
    rets = closed + active
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r < 0]
    stats = {
        "alpha": alpha,
        "trades": len(rets),
        "win_rate": len(wins) / len(rets) if rets else 0.0,
        "avg_win": sum(wins) / len(wins) if wins else 0.0,
        "avg_loss": sum(losses) / len(losses) if losses else 0.0,
        "profit_factor": (sum(wins) / abs(sum(losses))) if losses else None,
    }

    # ── „Aktie der Woche" (Rotation durch ALLE Positionen) ───────────────────
    base_kw = hold.get("base_kw", weekly[0]["kw"])
    featured = _featured_dict(universe, positions[(kw - base_kw) % len(positions)], as_of)

    # ── „Großer Verkauf der Woche" ───────────────────────────────────────────
    # Wurde diese KW eine grosse Position realisiert (|Rendite| >= Schwelle),
    # ersetzt deren Kauf-/Verkauf-Chart die „Weitere Positionen"-Slide und der
    # Newcomer entfaellt (siehe generate.build_from_store).
    big_sell = _big_sell(universe, closed_raw, kw, as_of)

    # ── Newcomer: bester Kauf der letzten 3 Wochen, NICHT in den Top-5 ───────
    ref = datetime.strptime(ref_date or dates[-1], "%Y-%m-%d")
    cutoff = (ref - timedelta(days=21)).strftime("%Y-%m-%d")
    cand = [t for t in top if t["buy_date"] >= cutoff and t["ticker"] not in top5_tickers]
    newcomer = _featured_dict(universe, max(cand, key=lambda t: t["ret"]), as_of) if cand else None

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
        "stats": stats,
        "top_holdings": top,
        "rest_holdings": top[5:],
        "featured": featured,
        "newcomer": newcomer,
        "big_sell": big_sell,
    }


def _period(start_iso, end_iso):
    from datetime import datetime
    s = datetime.strptime(start_iso, "%Y-%m-%d").strftime("%d.%m.")
    e = datetime.strptime(end_iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    return f"{s} – {e}"
