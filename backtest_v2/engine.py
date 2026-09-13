"""
backtest_v2/engine.py — Portfolio-Backtest-Engine für RS-Platform 2.0.

Implementiert die Regeln B1–B10 aus STRATEGIEPLAN.md Abschnitt 5, so weit wie
mit den im Repo vorhandenen Daten möglich (siehe Einschränkungen unten).
Wiederverwendet die LIVE-Signal-Funktionen aus gws_analysis.py und
v2_analysis.py über backtest_v2/signals.py (Regel B10).

BEKANNTE EINSCHRÄNKUNGEN dieses Laufs (in jedem Report erneut ausgewiesen):
  - B3 (survivorship-bias-freie historische Indexmitgliedschaft): NICHT
    umgesetzt. Gehandelt wird das AKTUELLE Marktuniversum rückwirkend über
    dessen eigene Historie — Survivorship-Bias bleibt bestehen.
  - B4/B5 (Out-of-Sample 2016–2021 Training / 2022–2026 Test): NICHT möglich.
    Die im Repo vorhandenen synchronisierten Ticker+Benchmark-Daten decken nur
    die letzten ~2 Jahre ab (kein Netzwerkzugriff in dieser Umgebung, um mehr
    Historie nachzuladen). Jeder Lauf ist ein Smoke-/Validierungstest auf der
    verfügbaren Tiefe, KEINE vollständige B4-Kalibrierung.
  - 4H-Signale sind NICHT im historischen Walk enthalten (Regel B9 — die
    Markt-JSONs halten nur ein rollierendes 60-Tage-Fenster an 4H-Daten,
    keine point-in-time-Historie über den gesamten Backtest-Zeitraum). Das
    Entry-Setup verlangt hier Weekly+Daily GWS (2/2) statt 3/3 wie live.
  - Fundamentaldaten (MarketCap, Sektor) sind ein aktueller Snapshot, nicht
    point-in-time — Investierbarkeits-Filter nähern die gesamte Historie mit
    heutigen Werten an.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from v2_analysis import (                                      # noqa: E402
    MIN_MCAP_DEFAULT, MIN_MCAP_SMALLCAP, MIN_PRICE, MIN_HISTORY_DAYS,
    _num, _sma,
)
from signals import (                                           # noqa: E402
    weekly_signal_cache, entry_signal, compute_stop, _last_confirmed_swing_low,
)

# ── Portfolio-Regeln (STRATEGIEPLAN.md Abschnitt 4) ─────────────────────────
MAX_POSITIONS      = 10
MAX_PER_SECTOR     = 3
MAX_WEIGHT_PCT     = 0.15
RISK_PCT_PER_TRADE = 0.01     # 1 % des Portfolios je Trade (Bandbreite 0,75–1 %)
PARTIAL_AT_R       = 2.0      # Teilverkauf bei +2R
PARTIAL_FRACTION   = 1 / 3
TIME_STOP_DAYS     = 15
RS_DECAY_THRESHOLD = 60


def _date_index(rows):
    return {row["d"]: i for i, row in enumerate(rows)}


def _load_universe(raw, fundamentals, market):
    arr = raw.get("data", [])
    min_mcap = MIN_MCAP_SMALLCAP if market == "smallcap" else MIN_MCAP_DEFAULT
    tickers_data, sectors, mcaps = {}, {}, {}
    for entry in arr:
        ticker = entry.get("ticker")
        daily = entry.get("ohlcv", [])
        weekly = entry.get("ohlcv_w", [])
        if not ticker or len(daily) < MIN_HISTORY_DAYS or len(weekly) < 15:
            continue
        tickers_data[ticker] = {"ohlcv": daily, "ohlcv_w": weekly}
        f = fundamentals.get(ticker, {})
        sectors[ticker] = f.get("sector")
        mcaps[ticker] = _num(f.get("marketCap"))
    return tickers_data, sectors, mcaps, min_mcap


class Position:
    __slots__ = ("ticker", "shares", "entry_price", "entry_date", "stop",
                 "risk_per_share", "partial_taken", "hit_1r", "entry_idx", "sector")

    def __init__(self, ticker, shares, entry_price, entry_date, stop, entry_idx, sector):
        self.ticker = ticker
        self.shares = shares
        self.entry_price = entry_price
        self.entry_date = entry_date
        self.stop = stop
        self.risk_per_share = entry_price - stop
        self.partial_taken = False
        self.hit_1r = False
        self.entry_idx = entry_idx
        self.sector = sector


def run_backtest(raw, fundamentals, market, cost_pct=0.001, initial_capital=100_000.0):
    """Führt den Portfolio-Backtest für ein Markt-JSON (wie rs_full.json) aus.
    Gibt {trades, equity_curve, regime_by_day, benchmark_closes} zurück."""
    tickers_data, sectors, mcaps, min_mcap = _load_universe(raw, fundamentals, market)
    bench_ohlcv = raw.get("benchmark_ohlcv", [])
    bench_ohlcv_w = raw.get("benchmark_ohlcv_w", [])
    if not tickers_data or not bench_ohlcv or not bench_ohlcv_w:
        return None

    weekly_cache = weekly_signal_cache(tickers_data, bench_ohlcv, bench_ohlcv_w)
    week_dates = sorted(weekly_cache.keys())   # effektive Wochenenden (Freitage)

    trading_days = [row["d"] for row in bench_ohlcv]
    bench_close_by_date = {row["d"]: row["c"] for row in bench_ohlcv}

    daily_idx = {t: _date_index(d["ohlcv"]) for t, d in tickers_data.items()}

    cash = initial_capital
    positions: dict[str, Position] = {}
    trades = []
    equity_curve = []
    regime_by_day = []
    pending_entries = {}   # ticker -> {"signal_date":, "stop_hint_date":}
    pending_exits = {}     # ticker -> "market" | "close"

    last_week_seen = None

    for day in trading_days:
        # ── Anstehende Exits von gestern zuerst ausführen (Open von heute) ──
        for ticker in list(pending_exits.keys()):
            reason = pending_exits.pop(ticker)
            pos = positions.get(ticker)
            if not pos:
                continue
            idx = daily_idx[ticker].get(day)
            if idx is None:
                continue
            fill = tickers_data[ticker]["ohlcv"][idx]["o"] * (1 - cost_pct)
            _close_position(pos, fill, day, reason, trades)
            cash += pos.shares * fill
            del positions[ticker]

        # ── Offene Positionen: täglicher Stop-/Exit-Check ───────────────────
        for ticker in list(positions.keys()):
            pos = positions[ticker]
            idx = daily_idx[ticker].get(day)
            if idx is None:
                continue
            bar = tickers_data[ticker]["ohlcv"][idx]

            if bar["l"] <= pos.stop:
                fill = min(pos.stop, bar["o"]) * (1 - cost_pct)
                _close_position(pos, fill, day, "stop", trades)
                cash += pos.shares * fill
                del positions[ticker]
                continue

            if bar["h"] >= pos.entry_price + pos.risk_per_share:
                pos.hit_1r = True

            if not pos.partial_taken and bar["h"] >= pos.entry_price + PARTIAL_AT_R * pos.risk_per_share:
                target = pos.entry_price + PARTIAL_AT_R * pos.risk_per_share
                sell_shares = max(1, int(pos.shares * PARTIAL_FRACTION))
                # Gap über das Ziel → Fill zum besseren Open, sonst zum Zielkurs
                fill = max(target, bar["o"]) * (1 - cost_pct)
                pnl = (fill - pos.entry_price) * sell_shares
                cash += sell_shares * fill
                trades.append({
                    "ticker": ticker, "entry_date": pos.entry_date, "exit_date": day,
                    "entry_price": pos.entry_price, "exit_price": fill, "shares": sell_shares,
                    "pnl": pnl, "pnl_pct": (fill / pos.entry_price - 1) * 100,
                    "reason": "partial_2R", "is_open": False,
                })
                pos.shares -= sell_shares
                pos.stop = pos.entry_price  # Rest auf Einstand
                pos.partial_taken = True
                if pos.shares <= 0:
                    del positions[ticker]
                    continue

            daily_trunc = tickers_data[ticker]["ohlcv"][:idx + 1]
            swing_low = _last_confirmed_swing_low(daily_trunc)
            if swing_low is not None and bar["c"] < swing_low:
                pending_exits[ticker] = "trailing"
                continue

            week_key = last_week_seen
            if week_key and ticker in weekly_cache.get(week_key, {}).get("struct", {}):
                st = weekly_cache[week_key]["struct"][ticker]
                pct = weekly_cache[week_key]["rs2_pct"].get(ticker)
                if pct is not None and pct < RS_DECAY_THRESHOLD and st["sma50"] and bar["c"] < st["sma50"]:
                    pending_exits[ticker] = "rs_decay"
                    continue

            days_held = idx - pos.entry_idx
            if days_held >= TIME_STOP_DAYS and not pos.hit_1r:
                fill = bar["c"] * (1 - cost_pct)
                _close_position(pos, fill, day, "time_stop", trades)
                cash += pos.shares * fill
                del positions[ticker]

        # ── Anstehende Entries von einem früheren Signal ausführen ──────────
        for ticker in list(pending_entries.keys()):
            info = pending_entries[ticker]
            idx = daily_idx[ticker].get(day)
            if idx is None or day <= info["signal_date"]:
                continue
            del pending_entries[ticker]
            if ticker in positions:
                continue
            bar = tickers_data[ticker]["ohlcv"][idx]
            entry_price = bar["o"] * (1 + cost_pct)
            sig_idx = daily_idx[ticker][info["signal_date"]]
            daily_trunc_at_signal = tickers_data[ticker]["ohlcv"][:sig_idx + 1]
            stop = compute_stop(daily_trunc_at_signal, entry_price)
            if stop is None:
                continue
            equity_now = cash + sum(p.shares * bar_close(tickers_data, daily_idx, p.ticker, day, p.entry_price)
                                     for p in positions.values())
            risk_amount = equity_now * RISK_PCT_PER_TRADE
            risk_per_share = entry_price - stop
            if risk_per_share <= 0:
                continue
            shares = int(risk_amount / risk_per_share)
            max_shares_by_weight = int((equity_now * MAX_WEIGHT_PCT) / entry_price)
            shares = min(shares, max_shares_by_weight)
            max_affordable = int(cash / entry_price)
            shares = min(shares, max_affordable)
            if shares <= 0:
                continue
            cash -= shares * entry_price
            positions[ticker] = Position(ticker, shares, entry_price, day, stop, idx, sectors.get(ticker))

        # ── Neue Signale nur an Wochenenddaten prüfen ────────────────────────
        if day in weekly_cache:
            week_idx_list = week_dates
            wi = week_idx_list.index(day)
            if wi > 0:
                prev_week = week_idx_list[wi - 1]
                curr_cache = weekly_cache[day]
                prev_cache = weekly_cache[prev_week]
                regime = curr_cache["regime"]
                threshold = regime.get("rs2_threshold") or 85
                budget = (regime.get("budget") or 100) / 100.0

                sector_counts = {}
                for p in positions.values():
                    sector_counts[p.sector] = sector_counts.get(p.sector, 0) + 1

                equity_now = cash + sum(p.shares * bar_close(tickers_data, daily_idx, p.ticker, day, p.entry_price)
                                         for p in positions.values())
                invested_value = equity_now - cash
                room_for_new = (equity_now * budget) - invested_value

                candidates = []
                for ticker in tickers_data:
                    if ticker in positions or ticker in pending_entries:
                        continue
                    if len(positions) + len(pending_entries) >= MAX_POSITIONS:
                        break
                    mcap = mcaps.get(ticker)
                    if mcap is not None and mcap < min_mcap:
                        continue
                    pct = curr_cache["rs2_pct"].get(ticker)
                    if pct is None or pct < threshold:
                        continue
                    if not entry_signal(ticker, prev_cache, curr_cache):
                        continue
                    sector = sectors.get(ticker)
                    if sector and sector_counts.get(sector, 0) >= MAX_PER_SECTOR:
                        continue
                    candidates.append((pct, ticker, sector))

                candidates.sort(reverse=True)
                for pct, ticker, sector in candidates:
                    if len(positions) + len(pending_entries) >= MAX_POSITIONS:
                        break
                    if room_for_new <= 0:
                        break
                    pending_entries[ticker] = {"signal_date": day}
                    sector_counts[sector] = sector_counts.get(sector, 0) + 1
                    room_for_new -= equity_now * MAX_WEIGHT_PCT

            last_week_seen = day

        # ── Mark-to-Market ───────────────────────────────────────────────────
        equity = cash
        for p in positions.values():
            equity += p.shares * bar_close(tickers_data, daily_idx, p.ticker, day, p.entry_price)
        equity_curve.append((day, equity))
        regime_label = weekly_cache.get(last_week_seen, {}).get("regime", {}).get("label") if last_week_seen else None
        regime_by_day.append((day, regime_label, len(positions)))

    # ── Verbleibende offene Positionen am letzten Tag markieren ─────────────
    if trading_days:
        last_day = trading_days[-1]
        for ticker, pos in positions.items():
            idx = daily_idx[ticker].get(last_day)
            close = tickers_data[ticker]["ohlcv"][idx]["c"] if idx is not None else pos.entry_price
            pnl = (close - pos.entry_price) * pos.shares
            trades.append({
                "ticker": ticker, "entry_date": pos.entry_date, "exit_date": last_day,
                "entry_price": pos.entry_price, "exit_price": close, "shares": pos.shares,
                "pnl": pnl, "pnl_pct": (close / pos.entry_price - 1) * 100,
                "reason": "open_at_end", "is_open": True,
            })

    return {
        "trades": trades,
        "equity_curve": equity_curve,
        "regime_by_day": regime_by_day,
        "benchmark_closes": [bench_close_by_date[d] for d in trading_days],
        "benchmark_dates": trading_days,
        "initial_capital": initial_capital,
        "n_universe": len(tickers_data),
    }


def bar_close(tickers_data, daily_idx, ticker, day, fallback):
    idx = daily_idx[ticker].get(day)
    if idx is None:
        return fallback
    return tickers_data[ticker]["ohlcv"][idx]["c"]


def _close_position(pos, fill_price, day, reason, trades):
    pnl = (fill_price - pos.entry_price) * pos.shares
    trades.append({
        "ticker": pos.ticker, "entry_date": pos.entry_date, "exit_date": day,
        "entry_price": pos.entry_price, "exit_price": fill_price, "shares": pos.shares,
        "pnl": pnl, "pnl_pct": (fill_price / pos.entry_price - 1) * 100,
        "reason": reason, "is_open": False,
    })
