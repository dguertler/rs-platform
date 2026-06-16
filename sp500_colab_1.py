import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import yfinance as yf
import pandas as pd
import json
import math
from datetime import datetime, timedelta
from fetch_tickers import fetch_sp500, detect_index_changes

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
raw   = yf.download(all_tickers, period="1y", auto_adjust=True, progress=False)
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
        else:
            c = raw_data["Close"].dropna()
            o = raw_data["Open"].reindex(c.index)
            h = raw_data["High"].reindex(c.index)
            l = raw_data["Low"].reindex(c.index)
        result = []
        for date, ov, hv, lv, cv in zip(c.index, o, h, l, c):
            if pd.isna(cv): continue
            result.append({"d": date.strftime(date_fmt),
                           "o": round(float(ov), 2), "h": round(float(hv), 2),
                           "l": round(float(lv), 2), "c": round(float(cv), 2)})
        return result[-n_candles:]
    except:
        return []

def _ohlcv_individual(ticker, start_str, end_str_local, interval, n_candles):
    """Einzeldownload für einen Ticker – Fallback wenn Batch-Daten fehlen/veraltet."""
    try:
        df = yf.download(ticker, start=start_str, end=end_str_local,
                         interval=interval, auto_adjust=True, progress=False)
        if df.empty:
            return []
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close"]].dropna(subset=["Close"])
        result = []
        for date, row in df.iterrows():
            if pd.isna(row["Close"]): continue
            result.append({
                "d": date.strftime("%Y-%m-%d"),
                "o": round(float(row["Open"]), 2),
                "h": round(float(row["High"]), 2),
                "l": round(float(row["Low"]),  2),
                "c": round(float(row["Close"]), 2)
            })
        return result[-n_candles:]
    except Exception as e:
        print(f"    Einzeldownload {ticker} ({interval}): Fehler – {e}")
        return []

def _last_expected_trading_day():
    """Letzter erwarteter Handelstag (Mo–Fr) vor heute."""
    d = datetime.now().date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

def extract_ohlcv_daily(ticker, raw_data, n_candles=520):
    data = extract_ohlcv(ticker, raw_data, n_candles)
    if len(data) < 30:
        print(f"  {ticker}: nur {len(data)} Tageskerzen im Batch – lade individuell nach...")
        data = _ohlcv_individual(ticker, start_daily.strftime("%Y-%m-%d"), end_str, "1d", n_candles)
        print(f"    → {len(data)} Kerzen")
        return data
    # Recency-Check: fehlende Kerzen der letzten Handelstage nachziehen
    last_date = datetime.strptime(data[-1]['d'], '%Y-%m-%d').date()
    expected  = _last_expected_trading_day()
    if last_date < expected:
        patch_start = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
        patch = _ohlcv_individual(ticker, patch_start, end_str, '1d', n_candles)
        if patch:
            existing = {c['d'] for c in data}
            new_c = [c for c in patch if c['d'] not in existing]
            if new_c:
                data = (data + new_c)[-n_candles:]
                print(f"  {ticker}: +{len(new_c)} fehlende Tageskerzen nachgeladen ({new_c[0]['d']}–{new_c[-1]['d']})")
    return data

def extract_ohlcv_4h(ticker, n_candles=3000):
    try:
        df = yf.download(ticker, start=start_4h.strftime("%Y-%m-%d"), end=end_str,
                         interval="1h", prepost=True, auto_adjust=True, progress=False)
        if df.empty: return []
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open","High","Low","Close","Volume"]].copy()
        df.index = pd.to_datetime(df.index)
        df.dropna(subset=["Close"], inplace=True)
        from zoneinfo import ZoneInfo
        _et     = ZoneInfo("America/New_York")
        _berlin = ZoneInfo("Europe/Berlin")
        extended = pd.Series(
            [ts.astimezone(_et).hour < 9 or
             (ts.astimezone(_et).hour == 9 and ts.astimezone(_et).minute < 30) or
             ts.astimezone(_et).hour >= 16
             for ts in df.index],
            index=df.index, dtype=bool
        )
        prev_low = df["Low"].shift(1)
        next_low = df["Low"].shift(-1)
        bad_low  = extended & (df["Low"] < prev_low * 0.70) & (df["Low"] < next_low * 0.70)
        df.loc[bad_low, "Low"] = df.loc[bad_low, ["Open","Close"]].min(axis=1)
        df_4h = df[["Open","High","Low","Close"]].resample("4h").agg(
            {"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
        from zoneinfo import ZoneInfo
        _berlin = ZoneInfo("Europe/Berlin")
        result = []
        for dt, row in df_4h.iterrows():
            if pd.isna(row["Close"]): continue
            dt_local = dt.astimezone(_berlin) if dt.tzinfo else dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(_berlin)
            result.append({"d": dt_local.strftime("%Y-%m-%d %H:%M"),
                           "o": round(float(row["Open"]),  2),
                           "h": round(float(row["High"]),  2),
                           "l": round(float(row["Low"]),   2),
                           "c": round(float(row["Close"]), 2)})
        return result[-n_candles:]
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
                 "ohlcv":    extract_ohlcv_daily(t, raw_daily),
                 "ohlcv_4h": ohlcv_4h_map.get(t, [])})

output = {
    "timestamp":            datetime.now().strftime("%Y-%m-%d %H:%M"),
    "benchmark":            "SPX",
    "fmp_tickers":          _official_sp500,
    "data":                 data,
    "daily_scores_by_date": daily_scores_by_date,
    "prev_week_scores":     prev_week_scores,
    "benchmark_ohlcv_w":    extract_ohlcv(benchmark, raw_weekly, 104),
    "benchmark_ohlcv":      extract_ohlcv_daily(benchmark, raw_daily),
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
