"""
Historischer NASDAQ-100-Backtest, Schritt 1: Kurse laden und Top 20 ranken.

Läuft in GitHub Actions (backtest_history.yml) — Yahoo Finance ist aus den
Cloud-Sessions heraus gesperrt. Ablauf:

 1. Mitgliedschaft aus data/backtest_history/ndx_membership.json (ab 2007-02)
 2. Tages- und Wochenkerzen ab 2005 via yfinance (auto_adjust wie live)
 3. Historische Symbole auf Yahoo-Symbole abbilden (symbols.py) und prüfen,
    ob die Kursreihe den Mitgliedszeitraum wirklich abdeckt
 4. Tägliches Top-20-Ranking unter den an diesem Tag gelisteten Mitgliedern —
    Formel aus rs_core.py, identisch mit rs_colab.py — in zwei Varianten:
      inkl: alle Mitglieder mit Kursdaten
      exkl: nur Aktien, die heute noch gehandelt werden
 5. Alles für run_backtest.js nach backtest_history/cache/ (nicht versioniert)

Aufruf: python3 backtest_history/prepare_data.py
"""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import yfinance as yf

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _REPO)
sys.path.insert(0, _HERE)

from rs_core import rank_by_day                          # noqa: E402
from repair_backtest_splits import find_jumps            # noqa: E402
from symbols import MAX_START_GAP_DAYS, candidates       # noqa: E402

MEMBERSHIP_FILE = os.path.join(_REPO, "data", "backtest_history", "ndx_membership.json")
CACHE_DIR = os.path.join(_HERE, "cache")
PRICE_START = "2005-01-01"      # 12M-Fenster + GWS-Vorlauf vor dem ersten Mitgliedstag
BENCHMARK = "QQQ"               # wie rs_colab.py
INDEX = "^NDX"                  # Jahresperformance NASDAQ-100 auf der Testseite
ACTIVE_TOLERANCE_DAYS = 10      # letzte Kerze so nah am Datenende → heute gehandelt
BATCH_SIZE = 60


def _download(symbols, interval):
    """Batch-Download; liefert {symbol: DataFrame(Open, High, Low, Close)}."""
    end = (date.today() + timedelta(days=1)).isoformat()
    out = {}
    for k in range(0, len(symbols), BATCH_SIZE):
        chunk = symbols[k:k + BATCH_SIZE]
        raw = yf.download(chunk, start=PRICE_START, end=end, interval=interval,
                          auto_adjust=True, progress=False, group_by="ticker", threads=True)
        for sym in chunk:
            try:
                df = raw[sym] if isinstance(raw.columns, pd.MultiIndex) else raw
            except KeyError:
                continue
            df = df.dropna(subset=["Close"])
            if len(df):
                out[sym] = df
    missing = [s for s in symbols if s not in out]
    for sym in missing:                                   # Nachlader wie rs_colab.py
        try:
            df = yf.download(sym, start=PRICE_START, end=end, interval=interval,
                             auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df):
                out[sym] = df
        except Exception as e:                            # noqa: BLE001 — Yahoo liefert für Delistings Fehler
            print(f"  {sym} ({interval}): {e}")
    return out


def _rows(df):
    """OHLC-Zeilen im Format der Backtest-Engine. 4 Nachkommastellen, weil
    split-bereinigte Altkurse (NVDA 2007 ≈ 0,5 $) sonst ihre Struktur verlieren."""
    return [{"d": ts.strftime("%Y-%m-%d"), "o": round(float(r.Open), 4),
             "h": round(float(r.High), 4), "l": round(float(r.Low), 4),
             "c": round(float(r.Close), 4)}
            for ts, r in df.iterrows()]


def _covers(first_bar, interval_start):
    gap = (datetime.fromisoformat(first_bar) - datetime.fromisoformat(interval_start)).days
    return gap <= MAX_START_GAP_DAYS


def resolve_symbols(intervals, daily):
    """Historisches Symbol → Yahoo-Symbol mit den abgedeckten Intervallen.

    Liefert (resolution, yahoo_intervals):
      resolution[t]      = {"yahoo", "accepted", "rejected", "status"}
      yahoo_intervals[y] = [[von, bis], ...] (bis None = noch Mitglied)
    """
    resolution, yahoo_intervals = {}, {}
    for ticker, ivs in intervals.items():
        best = None
        for sym in candidates(ticker):
            if sym not in daily:
                continue
            first_bar = daily[sym].index[0].strftime("%Y-%m-%d")
            ok = [iv for iv in ivs if _covers(first_bar, iv[0])]
            if ok and (best is None or len(ok) > len(best[1])):
                best = (sym, ok)
            if len(ok) == len(ivs):
                break
        if best is None:
            resolution[ticker] = {"yahoo": None, "accepted": [], "rejected": ivs,
                                  "status": "keine_daten"}
            continue
        sym, ok = best
        resolution[ticker] = {"yahoo": sym, "accepted": ok,
                              "rejected": [iv for iv in ivs if iv not in ok]}
        yahoo_intervals.setdefault(sym, []).extend(ok)
    return resolution, yahoo_intervals


def member_mask(index, symbols, yahoo_intervals):
    days = np.array([d.strftime("%Y-%m-%d") for d in index])
    mask = np.zeros((len(days), len(symbols)), dtype=bool)
    for c, sym in enumerate(symbols):
        for start, end in yahoo_intervals[sym]:
            mask[:, c] |= (days >= start) & ((days < end) if end else True)
    return mask


def top20_history(d_close, symbols, mask):
    return {d: [t for t, _ in ranked[:20]]
            for _, d, ranked in rank_by_day(d_close, BENCHMARK, symbols, mask)}


def coverage_by_year(resolution, first_year, last_year):
    """Je Jahr: Mitglieder insgesamt, davon ohne Kursdaten (mit Namen)."""
    out = {}
    for year in range(first_year, last_year + 1):
        y0, y1 = f"{year}-01-01", f"{year + 1}-01-01"
        members, missing = [], []
        for ticker, res in resolution.items():
            ivs = res["accepted"] + res["rejected"]
            overlap = [iv for iv in ivs if iv[0] < y1 and (iv[1] is None or iv[1] > y0)]
            if not overlap:
                continue
            members.append(ticker)
            if not any(iv in res["accepted"] for iv in overlap):
                missing.append(ticker)
        out[str(year)] = {"members": len(members), "missing": sorted(missing)}
    return out


def ndx_by_year(ndx_close, start):
    """Jahresperformance und max. Drawdown des NASDAQ-100 (Kursindex)."""
    s = ndx_close.dropna()
    start_ts = pd.Timestamp(start)
    out = {}
    for year in range(start_ts.year, s.index[-1].year + 1):
        period_start = max(pd.Timestamp(year=year, month=1, day=1), start_ts)
        cur = s[(s.index >= period_start) & (s.index.year == year)]
        prev = s[s.index < period_start]
        if cur.empty:
            continue
        # Basis = letzter Schluss vor Periodenbeginn (Vorjahresultimo bzw. Tag vor Teststart)
        base = float(prev.iloc[-1]) if len(prev) else float(cur.iloc[0])
        path = pd.concat([pd.Series([base]), cur.reset_index(drop=True)])
        dd = float((path / path.cummax() - 1).min() * 100)
        partial = period_start > pd.Timestamp(year=year, month=1, day=1) or cur.index[-1].month < 12
        out[str(year)] = {"from_date": period_start.strftime("%Y-%m-%d"),
                          "to_date": cur.index[-1].strftime("%Y-%m-%d"),
                          "pct": (float(cur.iloc[-1]) / base - 1) * 100,
                          "max_dd": dd, "partial": partial}
    return out


def _write(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))


def main():
    membership = json.load(open(MEMBERSHIP_FILE, encoding="utf-8"))
    intervals = membership["intervals"]
    symbols = sorted({s for t in intervals for s in candidates(t)} | {BENCHMARK})

    print(f"Tageskerzen für {len(symbols)} Symbole ab {PRICE_START} ...")
    daily = _download(symbols, "1d")
    if BENCHMARK not in daily:
        raise SystemExit(f"Benchmark {BENCHMARK} fehlt — Abbruch.")
    resolution, yahoo_intervals = resolve_symbols(intervals, daily)
    used = sorted(yahoo_intervals)
    print(f"  {len(used)} Yahoo-Symbole decken Mitgliedszeiträume ab")

    print("Wochenkerzen ...")
    weekly = _download(used, "1wk")
    ndx = _download([INDEX], "1d")[INDEX]["Close"]

    data_end = max(df.index[-1] for df in daily.values()).strftime("%Y-%m-%d")
    cutoff = (datetime.fromisoformat(data_end) - timedelta(days=ACTIVE_TOLERANCE_DAYS)).strftime("%Y-%m-%d")
    symbol_info = {}
    for sym in used:
        rows = _rows(daily[sym])
        last = rows[-1]["d"]
        symbol_info[sym] = {"first": rows[0]["d"], "last": last, "active": last >= cutoff,
                            "has_weekly": sym in weekly,
                            "jumps": [j["date"] for j in find_jumps(rows)]}
        _write(os.path.join(CACHE_DIR, "daily", f"{sym}.json"), rows)
        if sym in weekly:
            _write(os.path.join(CACHE_DIR, "weekly", f"{sym}.json"), _rows(weekly[sym]))
    for res in resolution.values():
        if res["yahoo"]:
            res["status"] = "aktiv" if symbol_info[res["yahoo"]]["active"] else "delisted_mit_daten"

    # Ranking-Matrix wie in rs_colab.py: Batch-Schlusskurse, Index = alle Handelstage
    d_close = pd.DataFrame({sym: daily[sym]["Close"] for sym in used + [BENCHMARK]}).sort_index()
    variants = {"inkl": used, "exkl": [s for s in used if symbol_info[s]["active"]]}
    for name, syms in variants.items():
        mask = member_mask(d_close.index, syms, yahoo_intervals)
        hist = top20_history(d_close, syms, mask)
        hist = {d: v for d, v in hist.items() if d >= membership["start"]}
        _write(os.path.join(CACHE_DIR, f"top20_{name}.json"), hist)
        print(f"  Top 20 ({name}): {len(hist)} Handelstage, {len(syms)} Symbole")

    first_year = int(membership["start"][:4])
    meta = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "membership_source": membership["source"],
        "membership_start": membership["start"],
        "price_start": PRICE_START,
        "data_end": data_end,
        "benchmark": BENCHMARK,
        "symbols": symbol_info,
        "resolution": resolution,
        "coverage": coverage_by_year(resolution, first_year, int(data_end[:4])),
        "ndx": ndx_by_year(ndx, membership["start"]),
    }
    _write(os.path.join(CACHE_DIR, "meta.json"), meta)
    no_data = sorted(t for t, r in resolution.items() if r["status"] == "keine_daten")
    print(f"Ohne Kursdaten ({len(no_data)}): {' '.join(no_data)}")


if __name__ == "__main__":
    main()
