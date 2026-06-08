"""
Persistente Wochen-Logik für den Instagram-Generator.

Liest die gespeicherten Daten unter instagram/data/ …
  - config.json            Stammdaten (Symbol, Startdatum, Startwert)
  - wikifolio_history.json Zertifikatswert je KW
  - holdings.json          Top-Positionen + Kaufdatum (+ Rotation)

… und berechnet daraus für eine KW alles Nötige:
  - Wochen-/Gesamtrendite, NASDAQ-Vergleich (aus Repo-Daten), Alpha
  - Wochen-Historie + „X von Y Wochen geschlagen"
  - Performance der Top-Positionen seit Kauf (historisch korrekt via as_of)
  - die rotierende „Aktie der Woche" inkl. Signale

NASDAQ wird aus dem QQQ/NDX-Benchmark in data/rs_full.json gezogen – kein
externer Aufruf nötig.

Historische Reports (rückwirkend): Legt man unter
instagram/data/snapshots/KW<NN>/holdings.json und trades.json ab, nutzt
compute() diese Dateien statt der Live-Daten. Die Performance der
Positionen wird per `as_of` auf das letzte Datum des jeweiligen
Wochenberichts begrenzt (nicht auf den heutigen Kurs).
"""
import json
import os
from datetime import datetime, timedelta

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


def load_trades():
    try:
        return _load("trades.json")
    except FileNotFoundError:
        return {"closed": []}


def _snap(kw, filename):
    """Gibt den Pfad zum historischen Snapshot zurück falls vorhanden, sonst None."""
    p = os.path.join(DATA_DIR, "snapshots", f"KW{kw:02d}", filename)
    return p if os.path.exists(p) else None


def _load_holdings_for(kw):
    snap = _snap(kw, "holdings.json")
    if snap:
        with open(snap) as f:
            return json.load(f)
    return load_holdings()


def _load_trades_for(kw):
    snap = _snap(kw, "trades.json")
    if snap:
        with open(snap) as f:
            return json.load(f)
    return load_trades()


def _sells_for(ticker, trades_data=None):
    """Abgeschlossene Verkäufe eines Tickers (für rote Verkaufsmarker im Chart).
    Quelle: trades_data (oder live trades.json) -> closed mit Ticker + Verkaufsdatum."""
    if trades_data is None:
        trades_data = load_trades()
    return [t for t in trades_data.get("closed", [])
            if t.get("ticker") == ticker and (t.get("date") or t.get("sell_date"))]


def _ret_since(universe, ticker, buy_date, as_of=None):
    """Reale Rendite vom Schlusskurs am/nach Kaufdatum bis as_of (Standard: letzter Kurs).
    as_of begrenzt die OHLCV-Daten — wichtig für historisch korrekte Wochenberichte."""
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


def _trade_dict(universe, t, as_of=None):
    """Chart-Daten für einen abgeschlossenen Trade (Kauf grün + Verkauf rot).
    `ret` ist die realisierte Rendite aus trades.json (nicht der aktuelle Kurs)."""
    tk = t.get("ticker")
    if not tk or tk not in universe or not universe[tk]["ohlcv"]:
        return None
    ohlcv = universe[tk]["ohlcv"]
    if as_of:
        ohlcv = [c for c in ohlcv if c["d"] <= as_of]
    bd = t.get("buy_date")
    entry = next((c for c in ohlcv if c["d"] >= bd), ohlcv[0]) if (bd and ohlcv) else (ohlcv[0] if ohlcv else None)
    if not entry:
        return None
    return {
        "ticker": tk, "name": t.get("name", ""),
        "buy_date": bd or entry["d"], "buy_price_eur": t.get("buy_price_eur"),
        "ret": t.get("ret"), "entry": entry,
        "ohlcv": ohlcv,
        "signals": data.load_signals().get(tk, []),
        "sells": [t], "closed": True,
        "sell_price_eur": t.get("sell_price_eur"),
    }


def _featured_dict(universe, p, as_of=None, trades_data=None):
    """Baut die Daten für eine Chart-Slide (Aktie der Woche / Newcomer).
    as_of begrenzt die OHLCV-Daten auf das Berichtsdatum (historische Korrektheit)."""
    tk = p["ticker"]
    if tk not in universe or not universe[tk]["ohlcv"]:
        # Ticker nicht in Repo-Daten – Slide wird übersprungen (entry=None)
        return {
            "ticker": tk, "name": p.get("name", ""),
            "buy_date": p.get("buy_date"), "buy_price_eur": p.get("buy_price_eur"),
            "ret": None, "entry": None, "ohlcv": [], "signals": [], "sells": [],
        }
    ret, entry = _ret_since(universe, tk, p["buy_date"], as_of=as_of)
    ohlcv = universe[tk]["ohlcv"]
    if as_of:
        ohlcv = [c for c in ohlcv if c["d"] <= as_of]
    return {
        "ticker": tk, "name": p.get("name", ""),
        "buy_date": p["buy_date"], "buy_price_eur": p.get("buy_price_eur"),
        "ret": ret, "entry": entry,
        "ohlcv": ohlcv,
        "signals": data.load_signals().get(tk, []),
        "sells": _sells_for(tk, trades_data=trades_data),
    }


def append_week(kw, value, date=None):
    """Hängt einen Zertifikatswert für KW an (oder aktualisiert ihn).
    `date` (YYYY-MM-DD) wird als echtes Datum des Wochenwerts gespeichert;
    ohne Angabe fällt die Equity-Kurve auf den Freitag der KW zurück."""
    h = load_history()
    weekly = [w for w in h["weekly"] if w["kw"] != kw]
    entry = {"kw": kw, "value": round(float(value), 2)}
    if date:
        entry["date"] = date
    weekly.append(entry)
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

    # as_of: Performance der Positionen historisch korrekt auf letztes Wochendatum begrenzen
    as_of = dates[-1]

    # ── NASDAQ (QQQ) im selben Zeitfenster, auf 100 indexiert ────────────────
    nas_raw = [_qqq_on(benchmark, d) for d in dates]
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

    # ── Top-Positionen: Performance seit Kauf (historisch korrekt via as_of) ─
    hold = _load_holdings_for(kw)
    positions = hold["positions"]
    top = []
    for p in positions:
        ret, _ = _ret_since(universe, p["ticker"], p["buy_date"], as_of=as_of)
        if ret is not None:
            top.append({**p, "ret": ret})
    top.sort(key=lambda t: t["ret"], reverse=True)
    top5_tickers = {t["ticker"] for t in top[:5]}

    # ── Trade-Kennzahlen: abgeschlossene + aktive Trades zusammen ────────────
    _trades_snap = _load_trades_for(kw)
    closed = [t["ret"] for t in _trades_snap.get("closed", [])]
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

    # ── „Aktie der Woche" (Rotation nur durch Positionen mit Repo-Daten) ─────
    base_kw = hold.get("base_kw", weekly[0]["kw"])
    # Nur Ticker mit OHLCV-Daten für Rotation (andere werden übersprungen)
    featured_positions = [p for p in positions if p["ticker"] in universe]
    if not featured_positions:
        featured_positions = positions  # Fallback: alle (entry wird None sein)
    feat_p = featured_positions[(kw - base_kw) % len(featured_positions)]
    featured = _featured_dict(universe, feat_p, as_of=as_of, trades_data=_trades_snap)

    # ── Newcomer: bester Kauf der letzten 3 Wochen, NICHT in den Top-5 ───────
    ref = datetime.strptime(ref_date or as_of, "%Y-%m-%d")
    cutoff = (ref - timedelta(days=21)).strftime("%Y-%m-%d")
    cand = [t for t in top if t["buy_date"] >= cutoff and t["ticker"] not in top5_tickers]
    newcomer = (_featured_dict(universe, max(cand, key=lambda t: t["ret"]),
                               as_of=as_of, trades_data=_trades_snap)
                if cand else None)

    # ── Trade der Woche: größter realisierter Verkauf DIESER KW ───────────────
    #    (Chart mit Kauf grün + Verkauf rot). Quelle: trades.json -> closed
    #    mit `ticker` + Verkaufsdatum `date` innerhalb der KW.
    from datetime import date as _date
    wk_mon = _date.fromisocalendar(year, kw, 1).isoformat()
    wk_sun = _date.fromisocalendar(year, kw, 7).isoformat()
    week_sells = [t for t in _trades_snap.get("closed", [])
                  if t.get("ticker") and wk_mon <= (t.get("date") or "") <= wk_sun]
    trade = None
    if week_sells:
        best = max(week_sells, key=lambda t: t.get("ret", -999))
        # Trade-Chart: as_of = Verkaufsdatum (nicht weiter), damit der Chart korrekt endet
        trade_as_of = best.get("date") or as_of
        trade = _trade_dict(universe, best, as_of=trade_as_of)

    return {
        "kw": kw,
        "period": _period(start_date, as_of),
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
        "trade": trade,
    }


def _period(start_iso, end_iso):
    from datetime import datetime
    s = datetime.strptime(start_iso, "%Y-%m-%d").strftime("%d.%m.")
    e = datetime.strptime(end_iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    return f"{s} – {e}"
