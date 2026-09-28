import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import yfinance as yf
import pandas as pd
from rs_core import hourly_to_4h_rows
import json
import math
from datetime import datetime, timedelta
from fetch_tickers import fetch_sp500, detect_index_changes
from index_membership import NDX_FILE, SP500_FILE, apply_official, current_members, load_intervals, watchlist_extras

_SP500_FALLBACK_1 = [
    # Financials
    "JPM", "BAC", "WFC", "GS",  "MS",   "BLK", "C",   "AXP", "SCHW", "USB",
    "PNC", "TFC", "COF", "SPGI","ICE",  "MCO", "CME", "CB",  "MMC",  "PGR",
    "TRV", "AFL", "MET", "PRU", "ALL",  "AIG", "HIG", "BK",  "STT",  "NTRS",
    "GPN", "FIS", "FI",  "V",   "MA",   "AMP", "SYF", "DFS", "ALLY", "CBOE",
    "NDAQ","RJF", "WRB", "L",   "CINF", "TROW","AON",
    # Healthcare
    "UNH", "LLY", "JNJ", "ABBV","MRK",  "TMO", "ABT", "DHR", "PFE",  "SYK",
    "BSX", "HCA", "ELV", "CI",  "CVS",  "MCK", "CAH", "CNC", "MOH",  "HUM",
    "A",   "BDX", "BAX", "EW",  "RMD",  "IQV", "ZBH", "BMY", "HOLX", "VTRS",
    "HSIC","ALGN","TFX", "COO", "DGX",  "LH",  "BIO",
    # Consumer Discretionary
    "HD",  "MCD", "NKE", "TGT", "LOW",  "CMG", "TJX", "AZO", "GM",   "F",
    "BBY", "DRI", "YUM", "EXPE","POOL", "NVR", "PHM", "DHI", "LEN",  "TOL",
    "TPR", "RL",  "APTV","MGM", "WYNN", "LVS", "MAR", "HLT", "H",    "RCL",
    "CCL", "NCLH","CZR",
    # Consumer Staples
    "WMT", "PG",  "KO",  "PM",  "MO",   "CL",  "KR",  "GIS", "K",    "SJM",
    "CPB", "CAG", "TSN", "HRL", "MKC",  "CHD", "CLX", "EL",  "SYY",  "WBA",
    # Energy
    "XOM", "CVX", "COP", "SLB", "OXY",  "EOG", "PSX", "MPC", "VLO",  "HAL",
    "DVN", "BKR", "APA", "HES", "MRO",  "CTRA","EQT", "RRC", "SM",   "OVV",
    # Industrials
    "CAT", "GE",  "UNP", "BA",  "RTX",  "LMT", "NOC", "GD",  "MMM",  "DE",
    "EMR", "ETN", "ITW", "PH",  "CSX",  "NSC", "UPS", "FDX", "ROK",  "CMI",
    "WM",  "RSG", "FTV", "CARR","OTIS", "JCI", "TT",  "IR",  "ROP",  "SWK",
    "HII", "HWM", "XYL", "MAS", "AME",
]

_all_sp500, _official_sp500 = fetch_sp500(fallback=_SP500_FALLBACK_1)

# ── Universum aus der historischen Zusammensetzung (point-in-time) ──────────
# Heutige S&P-500-Mitglieder (Datei + offizielle Liste als letzte Änderung)
# plus Watchlist-Titel ohne Indexzugehörigkeit (Kursdaten für Verkaufssignale,
# kein Ranking). Die Fallback-Ergänzungen der Ticker-Liste enthielten
# Nicht-Mitglieder und verfälschten Tabelle und Top-20-Ranking.
_sp_intervals = load_intervals(SP500_FILE)
if _sp_intervals:
    _sp_intervals = apply_official(_sp_intervals, _official_sp500)
    _sp_members = current_members(_sp_intervals)
    _ndx_iv = load_intervals(NDX_FILE) or {}
    _extras = watchlist_extras(set(_sp_members) | set(current_members(_ndx_iv)))
    _all_sp500 = sorted(set(_sp_members) | set(_extras))
    _official_sp500 = _sp_members
    print(f"S&P-500-Universum: {len(_sp_members)} Mitglieder"
          + (f" + Watchlist ohne Index: {', '.join(_extras)}" if _extras else ""))
if _all_sp500:
    tickers = _all_sp500[:len(_all_sp500)//2]
    print(f"Teil 1: {len(tickers)} Ticker (erste Hälfte A–M)")
    print("\nPrüfe Indexänderungen (IC vs. EDC) Teil 1...")
    _changes = detect_index_changes(_official_sp500, "data/rs_sp500.json")
    _new_stocks = set(_changes["new"])
    if _new_stocks:
        print(f"Neue Aktien im S&P 500 (gesamt): {', '.join(sorted(_new_stocks))}")
else:
    tickers = list(set(_SP500_FALLBACK_1))
    _official_sp500 = []
    _new_stocks = set()

# new_since-Datum: aus EDC übernehmen oder heute für neue Aktien setzen
_today = datetime.now().strftime("%Y-%m-%d")
_new_since_map = {}
try:
    with open("data/rs_sp500.json", encoding="utf-8") as _f:
        for _d in json.load(_f).get("data", []):
            if _d.get("new_since"):
                _new_since_map[_d["ticker"]] = _d["new_since"]
except Exception:
    pass
for _t in _new_stocks:
    _new_since_map.setdefault(_t, _today)

benchmark   = "^GSPC"
rs_windows  = {"5T": 5, "10T": 10, "20T": 20, "50T": 50, "6M": 126, "12M": 252}
OUTPUT_FILE = "rs_sp500_1.json"

def sanitize_nan(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nan(v) for v in obj]
    return obj

print(f"Teil 1: RS-Berechnung für {len(tickers)} S&P 500-Aktien (ohne QQQ-Werte)...")
all_tickers = tickers + [benchmark]
raw   = yf.download(all_tickers, period="2y", auto_adjust=True, progress=False)  # 2 Jahre, sonst fehlt das 12M-Fenster (252 Handelstage)
close = raw["Close"]
spx   = close[benchmark].dropna()
if len(spx) < 60:
    raise RuntimeError(
        f"Benchmark {benchmark}: nur {len(spx)} gueltige Kurse im Batch-Download – "
        f"Abbruch, damit keine leeren RS-Scores committet werden."
    )

all_results = []
for ticker in tickers:
    if ticker not in close.columns:
        continue
    s = close[ticker].dropna()
    if len(s) < 50:
        continue
    windows_result = {}
    for label, days in rs_windows.items():
        try:
            windows_result[label] = round(
                float((s.iloc[-1]/s.iloc[-days]-1)*100 - (spx.iloc[-1]/spx.iloc[-days]-1)*100), 2)
        except:
            windows_result[label] = None
    score = round(sum(v for v in windows_result.values() if v is not None), 2)
    all_results.append({"ticker": ticker, "score": score, "windows": windows_result})

# Schutz: bei fehlerhafter Datenquelle (z.B. NaN-Benchmark) nicht stillschweigend
# leere Scores committen, sondern abbrechen -> Workflow schlaegt fehl + Fehler-Mail.
_valid = sum(1 for r in all_results if r["score"] is not None and r["score"] == r["score"])
if _valid < len(tickers) * 0.5:
    raise RuntimeError(
        f"Nur {_valid}/{len(tickers)} gueltige RS-Scores berechnet – Abbruch "
        f"(Datenquelle fehlerhaft, keine NaN-Daten committen)."
    )

all_results.sort(key=lambda x: (x["score"] is not None and x["score"] == x["score"], x["score"]), reverse=True)
print(f"Top 5: {', '.join(r['ticker'] for r in all_results[:5])}")

end_date     = datetime.now()
end_str      = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
start_weekly = end_date - timedelta(days=730)
start_daily  = end_date - timedelta(days=730)
start_4h     = end_date - timedelta(days=60)

all_tickers_list = [r["ticker"] for r in all_results]

print(f"\nWeekly OHLCV ({len(all_tickers_list)} Ticker)...")
raw_weekly = yf.download(
    all_tickers_list + [benchmark],
    start=start_weekly.strftime("%Y-%m-%d"), end=end_str,
    interval="1wk", auto_adjust=True, progress=False)

print(f"Daily OHLCV ({len(all_tickers_list)} Ticker)...")
raw_daily = yf.download(
    all_tickers_list + [benchmark],
    start=start_daily.strftime("%Y-%m-%d"), end=end_str,
    interval="1d", auto_adjust=True, progress=False)

def extract_ohlcv(ticker, raw_data, n_candles, date_fmt="%Y-%m-%d"):
    try:
        if isinstance(raw_data.columns, pd.MultiIndex):
            c = raw_data["Close"][ticker].dropna()
            o = raw_data["Open"][ticker].reindex(c.index)
            h = raw_data["High"][ticker].reindex(c.index)
            l = raw_data["Low"][ticker].reindex(c.index)
            v = raw_data["Volume"][ticker].reindex(c.index) if "Volume" in raw_data.columns.get_level_values(0) else None
        else:
            c = raw_data["Close"].dropna()
            o = raw_data["Open"].reindex(c.index)
            h = raw_data["High"].reindex(c.index)
            l = raw_data["Low"].reindex(c.index)
            v = raw_data["Volume"].reindex(c.index) if "Volume" in raw_data.columns else None
        if v is None:
            v = pd.Series([None] * len(c), index=c.index)
        result = []
        for date, ov, hv, lv, cv, vv in zip(c.index, o, h, l, c, v):
            if pd.isna(cv): continue
            row = {"d": date.strftime(date_fmt),
                   "o": round(float(ov), 2), "h": round(float(hv), 2),
                   "l": round(float(lv), 2), "c": round(float(cv), 2)}
            if vv is not None and not pd.isna(vv):
                row["v"] = round(float(vv), 0)
            result.append(row)
        return result[-n_candles:]
    except:
        return []

def extract_ohlcv_4h(ticker, n_candles=3000):
    try:
        df = yf.download(ticker, start=start_4h.strftime("%Y-%m-%d"), end=end_str,
                         interval="1h", prepost=True, auto_adjust=True, progress=False)
        if df.empty: return []
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return hourly_to_4h_rows(df)[-n_candles:]   # gemeinsame 4H-Bildung (rs_core)
    except Exception as e:
        print(f"  4H Fehler {ticker}: {e}")
        return []

print(f"\n4H OHLCV ({len(all_tickers_list)} Ticker)...")
ohlcv_4h_map = {}
for i, ticker in enumerate(all_tickers_list):
    print(f"  4H [{i+1}/{len(all_tickers_list)}] {ticker}...", end=" ", flush=True)
    ohlcv_4h_map[ticker] = extract_ohlcv_4h(ticker)
    print(f"{len(ohlcv_4h_map[ticker])} Kerzen")

print("\nHistorisches tägliches Ranking (Teil 1)...")
try:
    d_close = raw_daily["Close"] if isinstance(raw_daily.columns, pd.MultiIndex) else raw_daily
    if benchmark not in d_close.columns:
        raise KeyError(f"Benchmark {benchmark} nicht in Tagesdaten")
    bench_s = d_close[benchmark]
    avail   = [t for t in all_tickers_list if t in d_close.columns]
    daily_scores_by_date = {}
    prev_week_scores = {}
    n = len(d_close)
    prev_week_i = max(0, n - 6)
    for i in range(n):
        date_str = d_close.index[i].strftime("%Y-%m-%d")
        b_now = bench_s.iloc[i]
        if pd.isna(b_now) or b_now == 0:
            continue
        scores = []
        for t in avail:
            s_now = d_close[t].iloc[i]
            if pd.isna(s_now) or s_now == 0:
                continue
            total, cnt = 0, 0
            for days in rs_windows.values():
                if i >= days:
                    s_prev = d_close[t].iloc[i - days]
                    b_prev = bench_s.iloc[i - days]
                    if not pd.isna(s_prev) and not pd.isna(b_prev) and s_prev != 0 and b_prev != 0:
                        total += (s_now / s_prev - 1) * 100 - (b_now / b_prev - 1) * 100
                        cnt   += 1
            if cnt > 0:
                scores.append((t, total))
        if len(scores) >= 5:
            scores.sort(key=lambda x: x[1], reverse=True)
            daily_scores_by_date[date_str] = [[t, round(s, 2)] for t, s in scores[:50]]
            if i == prev_week_i:
                prev_week_scores = {t: round(s, 2) for t, s in scores}
                print(f"  Vorwoche-Scores (Teil 1): {len(prev_week_scores)} Ticker (Stand: {date_str})")
    print(f"  {len(daily_scores_by_date)} Tage berechnet")
except Exception as e:
    daily_scores_by_date = {}
    prev_week_scores = {}
    print(f"  ⚠️ Fehler: {e}")

print("\nJSON zusammenbauen...")
data = []
for r in all_results:
    t = r["ticker"]
    data.append({"ticker": t, "score": r["score"], "windows": r["windows"],
                 "new_since": _new_since_map.get(t),
                 "ohlcv_w":  extract_ohlcv(t, raw_weekly, 104),
                 "ohlcv":    extract_ohlcv(t, raw_daily, 520),
                 "ohlcv_4h": ohlcv_4h_map.get(t, [])})

output = {
    "timestamp":            datetime.now().strftime("%Y-%m-%d %H:%M"),
    "benchmark":            "SPX",
    "fmp_tickers":          _official_sp500,
    "data":                 data,
    "daily_scores_by_date": daily_scores_by_date,
    "prev_week_scores":     prev_week_scores,
    "benchmark_ohlcv_w":    extract_ohlcv(benchmark, raw_weekly, 104),
    "benchmark_ohlcv":      extract_ohlcv(benchmark, raw_daily, 520),
}
with open(OUTPUT_FILE, "w") as f:
    json.dump(sanitize_nan(output), f)
print(f"✅ Teil 1 fertig – {len(data)} Ticker → {OUTPUT_FILE}")

# ── Validierung ───────────────────────────────────────────────────────────────
_loaded   = len(data)
_expected = len(tickers)
_missing  = set(tickers) - {r['ticker'] for r in data}
print(f"\nValidierung: {_loaded}/{_expected} Ticker geladen ({_loaded/_expected*100:.0f}%)")
if _missing:
    print(f"  Fehlende Ticker ({len(_missing)}): {', '.join(sorted(_missing))}")

import os as _os
_sf = _os.environ.get('GITHUB_STEP_SUMMARY')
if _sf:
    _pct  = _loaded / _expected * 100 if _expected else 0
    _icon = '✅' if _pct >= 95 else '⚠️'
    with open(_sf, 'a') as _f:
        _f.write(f"### S&P 500 – Teil 1\n{_icon} **{_loaded}/{_expected} Ticker geladen ({_pct:.0f}%)**\n")
        if _missing:
            _f.write(f"Fehlende Ticker: `{'`, `'.join(sorted(_missing))}`\n")
        _f.write("\n")
