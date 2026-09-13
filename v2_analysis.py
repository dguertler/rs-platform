"""
v2_analysis.py — RS-Platform 2.0 Berechnungsmodul (rein additiv).

Berechnet aus den bestehenden Markt-JSONs (rs_full.json etc.) und
fundamentals.json — ohne die v1-Daten oder v1-Endpoints zu verändern:

  - Regime-Ampel je Universum (Trend / Marktbreite / Volatilität)
  - RS 2.0: volatilitätsadjustierter, gewichteter RS-Score als Perzentil-Rang
    (statt der v1-Rohsumme der Überrenditen)
  - Auswahl-Funnel: Investierbarkeit → RS-Schwelle → GWS-Setup → Kaufliste

Wird ausschließlich vom neuen Endpoint /api/v2/{market} verwendet.
Regelwerk und Parameter-Startwerte: siehe STRATEGIEPLAN.md.
"""

import math
from statistics import median, pstdev

from gws_analysis import struct_for_entry

# ── Parameter (Startwerte laut STRATEGIEPLAN.md, per Backtest zu kalibrieren) ──

RS2_WINDOWS = {20: 0.2, 50: 0.3, 126: 0.3, 252: 0.2}   # Fenster → Gewicht
RS2_TREND_LOOKBACK = 10          # Handelstage für RS-Trend (Perzentil-Δ)

MIN_MCAP_DEFAULT  = 300e6        # Investierbarkeit
MIN_MCAP_SMALLCAP = 100e6
MIN_PRICE         = 5.0
MIN_HISTORY_DAYS  = 130

MIN_DOLLAR_VOL_DEFAULT   = 5e6   # Ø-Dollar-Volumen 20T (STRATEGIEPLAN.md Stufe 1)
MIN_DOLLAR_VOL_SMALLCAP  = 1e6
VOLUME_CONFIRM_MULT      = 1.5   # Breakout-Volumen ≥ 1,5× 20T-Ø

ATR_PERIOD        = 14
MAX_STOP_ATR      = 1.5          # Entry−Stop ≤ 1,5×ATR = enges Setup

EARNINGS_BLACKOUT_CALENDAR_DAYS = 7   # Näherung für "< 5 Handelstage" — kein Handelskalender verfügbar

REGIME_THRESHOLDS = {"green": 85, "yellow": 90, "red": 90}   # RS2-Perzentil-Schwelle
REGIME_BUDGET     = {"green": 100, "yellow": 60, "red": 30}  # Exposure-Budget %


# ── Basis-Helfer ──────────────────────────────────────────────────────────────

def _closes(ohlcv):
    return [row["c"] for row in ohlcv if row.get("c") is not None]


def _num(value):
    """Fundamentals-Wert als Zahl — Strings wie 'UNGÜLTIG (…)' oder 'N/A' → None."""
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _sma(values, n, end=None):
    end = len(values) if end is None else end
    if end < n or n <= 0:
        return None
    window = values[end - n:end]
    return sum(window) / n


def _daily_returns(closes, start, end):
    result = []
    for i in range(max(start, 1), end):
        prev = closes[i - 1]
        if prev:
            result.append(closes[i] / prev - 1)
    return result


def _atr(ohlcv, period=ATR_PERIOD):
    if len(ohlcv) < period + 1:
        return None
    trs = []
    for i in range(len(ohlcv) - period, len(ohlcv)):
        h, l, pc = ohlcv[i]["h"], ohlcv[i]["l"], ohlcv[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / period


def _in_earnings_blackout(ticker, earnings_map, today=None):
    """True, wenn earnings_map einen zukünftigen Termin für ticker innerhalb
    EARNINGS_BLACKOUT_CALENDAR_DAYS enthält. earnings_map=None oder Ticker
    fehlt → False (fail-safe: Sperre nie aktiv, wenn keine Daten vorliegen)."""
    if not earnings_map:
        return False
    date_str = earnings_map.get(ticker)
    if not date_str:
        return False
    try:
        from datetime import date as _date
        target = _date.fromisoformat(date_str)
        today = today or _date.today()
        delta = (target - today).days
        return 0 <= delta <= EARNINGS_BLACKOUT_CALENDAR_DAYS
    except Exception:
        return False


def _dollar_volume_20d(ohlcv):
    """Ø-Dollar-Volumen der letzten 20 Handelstage, oder None wenn kein
    Volumen-Feld vorhanden ist (ältere JSON-Exporte vor dem Volumen-Rollout)."""
    tail = ohlcv[-20:]
    pairs = [(row["c"], row["v"]) for row in tail if row.get("v") is not None]
    if len(pairs) < 10:
        return None
    return sum(c * v for c, v in pairs) / len(pairs)


def _volume_confirmed_breakout(ohlcv):
    """True, wenn das Volumen am letzten Handelstag ≥ VOLUME_CONFIRM_MULT ×
    Ø-Volumen der vorherigen 20 Tage liegt. None (nicht False!) wenn Volumen
    fehlt — Aufrufer muss None von False unterscheiden, um das Kriterium bei
    fehlenden Daten neutral zu behandeln statt Setups fälschlich abzuwerten."""
    if len(ohlcv) < 21:
        return None
    last_v = ohlcv[-1].get("v")
    prior = [row["v"] for row in ohlcv[-21:-1] if row.get("v") is not None]
    if last_v is None or len(prior) < 10:
        return None
    avg_prior = sum(prior) / len(prior)
    if avg_prior <= 0:
        return None
    return last_v >= VOLUME_CONFIRM_MULT * avg_prior


def _last_confirmed_swing_low(ohlcv):
    """Letztes Daily-Swing-Low (±2 Bars), das bereits bestätigt ist
    (mind. 2 Bars nach dem Tief liegen vor) — kein Look-Ahead."""
    lows = [row["l"] for row in ohlcv]
    n = len(lows)
    for i in range(n - 3, 1, -1):
        if (lows[i] <= lows[i - 1] and lows[i] <= lows[i - 2]
                and lows[i] <= lows[i + 1] and (i + 2 >= n or lows[i] <= lows[i + 2])):
            if i <= n - 3:
                return lows[i]
    return None


# ── RS 2.0 ────────────────────────────────────────────────────────────────────

def _rs2_raw(closes, bench_closes, offset=0):
    """Volatilitätsadjustierter, gewichteter RS-Score am Index len-1-offset.

    Je Fenster w: (Rendite Aktie − Rendite Benchmark) / (Tagesvola × √w).
    Fehlende Fenster werden übersprungen, Gewichte renormalisiert.
    Aktien- und Benchmark-Serie werden vom Ende her ausgerichtet (beide
    enden am selben Handelstag — identisch zur v1-Berechnung in rs_colab.py).
    """
    end_s = len(closes) - offset
    end_b = len(bench_closes) - offset
    if end_s < 21 or end_b < 21:
        return None
    total, weight_sum = 0.0, 0.0
    for w, weight in RS2_WINDOWS.items():
        if end_s <= w or end_b <= w:
            continue
        s_now, s_prev = closes[end_s - 1], closes[end_s - 1 - w]
        b_now, b_prev = bench_closes[end_b - 1], bench_closes[end_b - 1 - w]
        if not s_prev or not b_prev:
            continue
        excess = (s_now / s_prev - 1) - (b_now / b_prev - 1)
        rets = _daily_returns(closes, end_s - 1 - w, end_s)
        vol = pstdev(rets) if len(rets) >= 10 else None
        if not vol:
            continue
        total += weight * (excess / (vol * math.sqrt(w)))
        weight_sum += weight
    if weight_sum == 0:
        return None
    return total / weight_sum


def _percentiles(values_by_ticker):
    """{ticker: raw} → {ticker: Perzentil 0–100} (None bleibt None)."""
    valid = sorted(v for v in values_by_ticker.values() if v is not None)
    n = len(valid)
    result = {}
    for ticker, v in values_by_ticker.items():
        if v is None or n < 2:
            result[ticker] = None
        else:
            rank = sum(1 for x in valid if x <= v)
            result[ticker] = round((rank - 1) / (n - 1) * 100, 1)
    return result


# ── Regime-Ampel ──────────────────────────────────────────────────────────────

def compute_regime(bench_ohlcv, ticker_close_lists):
    closes = _closes(bench_ohlcv or [])
    if len(closes) < 60:
        return {"label": "unknown", "budget": None, "detail": "Zu wenig Benchmark-Historie"}

    sma200 = _sma(closes, 200)
    sma50_now = _sma(closes, 50)
    sma50_prev = _sma(closes, 50, end=len(closes) - RS2_TREND_LOOKBACK)
    trend_ok = sma200 is not None and closes[-1] > sma200
    sma50_rising = (sma50_now is not None and sma50_prev is not None
                    and sma50_now > sma50_prev)

    above50 = total50 = above200 = total200 = 0
    for tcloses in ticker_close_lists:
        s50 = _sma(tcloses, 50)
        if s50 is not None:
            total50 += 1
            if tcloses[-1] > s50:
                above50 += 1
        s200 = _sma(tcloses, 200)
        if s200 is not None:
            total200 += 1
            if tcloses[-1] > s200:
                above200 += 1
    breadth50 = round(above50 / total50 * 100, 1) if total50 else None
    breadth200 = round(above200 / total200 * 100, 1) if total200 else None

    vol20 = vol_median = None
    rets = _daily_returns(closes, 0, len(closes))
    if len(rets) >= 40:
        vol20 = pstdev(rets[-20:]) * math.sqrt(252) * 100
        rolling = [pstdev(rets[i - 20:i]) * math.sqrt(252) * 100
                   for i in range(20, len(rets))]
        vol_median = median(rolling[-252:]) if rolling else None

    if sma200 is None:
        label = "unknown"
    elif not trend_ok:
        label = "red"
    elif (breadth50 is not None and breadth50 < 50) or not sma50_rising:
        label = "yellow"
    else:
        label = "green"

    return {
        "label": label,
        "budget": REGIME_BUDGET.get(label),
        "rs2_threshold": REGIME_THRESHOLDS.get(label),
        "close": closes[-1],
        "sma200": round(sma200, 2) if sma200 else None,
        "trend_ok": trend_ok,
        "sma50_rising": sma50_rising,
        "breadth50": breadth50,
        "breadth200": breadth200,
        "vol20_annualized": round(vol20, 1) if vol20 else None,
        "vol_median_1y": round(vol_median, 1) if vol_median else None,
    }


# ── Funnel / Payload ──────────────────────────────────────────────────────────

def build_v2_payload(raw, fundamentals, market, earnings_map=None):
    arr = raw.get("data", []) if isinstance(raw, dict) else raw
    bench_ohlcv = raw.get("benchmark_ohlcv", []) if isinstance(raw, dict) else []
    bench_closes = _closes(bench_ohlcv)
    min_mcap = MIN_MCAP_SMALLCAP if market == "smallcap" else MIN_MCAP_DEFAULT

    ticker_close_lists = []
    raw_now, raw_prev = {}, {}
    entries = {}
    for entry in arr:
        ticker = entry.get("ticker")
        closes = _closes(entry.get("ohlcv", []))
        if not ticker or not closes:
            continue
        entries[ticker] = (entry, closes)
        ticker_close_lists.append(closes)
        if bench_closes:
            raw_now[ticker] = _rs2_raw(closes, bench_closes)
            raw_prev[ticker] = _rs2_raw(closes, bench_closes, offset=RS2_TREND_LOOKBACK)

    pct_now = _percentiles(raw_now)
    pct_prev = _percentiles(raw_prev)
    regime = compute_regime(bench_ohlcv, ticker_close_lists)
    threshold = regime.get("rs2_threshold") or REGIME_THRESHOLDS["green"]

    # Sektor-RS: Ø RS2-Perzentil je Sektor (mind. 3 Titel)
    sector_values = {}
    for ticker, (entry, _) in entries.items():
        f = fundamentals.get(ticker, {})
        sector, pct = f.get("sector"), pct_now.get(ticker)
        if sector and pct is not None:
            sector_values.setdefault(sector, []).append(pct)
    sector_rs = {s: round(sum(v) / len(v), 1)
                 for s, v in sector_values.items() if len(v) >= 3}
    top_sectors = [s for s, _ in sorted(sector_rs.items(), key=lambda kv: -kv[1])[:3]]

    rows = []
    for ticker, (entry, closes) in entries.items():
        f = fundamentals.get(ticker, {})
        close = closes[-1]
        mcap = _num(f.get("marketCap"))

        min_dollar_vol = MIN_DOLLAR_VOL_SMALLCAP if market == "smallcap" else MIN_DOLLAR_VOL_DEFAULT
        dollar_vol = _dollar_volume_20d(entry.get("ohlcv", []))

        reasons = []
        if mcap is not None and mcap < min_mcap:
            reasons.append(f"MCap < ${min_mcap / 1e6:.0f}M")
        if close < MIN_PRICE:
            reasons.append(f"Kurs < ${MIN_PRICE:.0f}")
        if len(closes) < MIN_HISTORY_DAYS:
            reasons.append(f"Historie < {MIN_HISTORY_DAYS}T")
        if dollar_vol is not None and dollar_vol < min_dollar_vol:
            reasons.append(f"Ø-$-Vol 20T < ${min_dollar_vol / 1e6:.0f}M")
        investable = not reasons

        struct = struct_for_entry(entry)
        gws_w = bool(struct.get("weekly", {}).get("broken"))
        gws_d = bool(struct.get("daily", {}).get("broken"))
        gws_h4 = bool(struct.get("h4", {}).get("broken4h"))
        gws_pts = int(gws_w) + int(gws_d) + int(gws_h4)

        atr = _atr(entry.get("ohlcv", []))
        swing_low = _last_confirmed_swing_low(entry.get("ohlcv", []))
        stop = round(swing_low * 0.99, 2) if swing_low else None
        tight_stop = (atr is not None and stop is not None
                      and 0 < close - stop <= MAX_STOP_ATR * atr)

        pct = pct_now.get(ticker)
        prev = pct_prev.get(ticker)
        trend = round(pct - prev, 1) if pct is not None and prev is not None else None
        sector = f.get("sector")

        volume_confirmed = _volume_confirmed_breakout(entry.get("ohlcv", []))
        has_volume_data = volume_confirmed is not None

        setup_pts = sum([
            gws_pts == 3,
            bool(tight_stop),
            trend is not None and trend > 0,
            sector in top_sectors,
            bool(volume_confirmed),
        ])
        setup_max = 5 if has_volume_data else 4

        earnings_blackout = _in_earnings_blackout(ticker, earnings_map)

        if not investable:
            status = "GEFILTERT"
        elif pct is not None and pct >= threshold and gws_pts == 3:
            status = "EARNINGS-SPERRE" if earnings_blackout else "KAUFLISTE"
        elif pct is not None and pct >= threshold:
            status = "KANDIDAT"
        else:
            status = ""

        rows.append({
            "ticker": ticker,
            "name": f.get("shortName"),
            "sector": sector,
            "close": close,
            "market_cap": mcap,
            "score_v1": entry.get("score"),
            "rank_v1": entry.get("prev_rank"),
            "rs2_pct": pct,
            "rs2_trend": trend,
            "investable": investable,
            "filter_reasons": reasons,
            "gws": {"w": gws_w, "d": gws_d, "h4": gws_h4, "pts": gws_pts},
            "atr": round(atr, 2) if atr else None,
            "stop": stop,
            "tight_stop": tight_stop,
            "dollar_vol_20d": round(dollar_vol, 0) if dollar_vol is not None else None,
            "volume_confirmed": volume_confirmed,
            "setup_pts": setup_pts,
            "setup_max": setup_max,
            "next_earnings": (earnings_map or {}).get(ticker),
            "earnings_blackout": earnings_blackout,
            "status": status,
        })

    rows.sort(key=lambda r: (r["rs2_pct"] is not None, r["rs2_pct"]), reverse=True)
    return {
        "market": market,
        "timestamp": raw.get("timestamp") if isinstance(raw, dict) else None,
        "benchmark": raw.get("benchmark") if isinstance(raw, dict) else None,
        "regime": regime,
        "rs2_threshold": threshold,
        "top_sectors": top_sectors,
        "sector_rs": sector_rs,
        "data": rows,
    }
