import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import yfinance as yf
import pandas as pd
import json
import math
from datetime import datetime, timedelta

_SP500_FALLBACK_2 = [
    # Technology (nicht im QQQ)
    "ORCL","CRM", "IBM", "ACN", "FICO","GLW", "HPQ", "HPE", "STX", "WDC",
    "NTAP","KEYS","TER", "SWKS","QRVO","AKAM","CDW", "GDDY","VRT", "LDOS",
    "TDY", "TRMB","PAYC","IT",  "JNPR","JKHY","ANET","PTC", "EPAM","DXC",
    "ZBRA",
    # Communication Services (nicht im QQQ)
    "DIS", "CMCSA","T",  "VZ",  "WBD", "FOXA","FOX", "IPG", "OMC", "LYV",
    "PARA","NWSA",
    # Utilities
    "NEE", "DUK", "SO",  "D",   "EXC", "SRE", "PCG", "ED",  "ETR", "FE",
    "PPL", "CMS", "NI",  "WEC", "DTE", "EIX", "ES",  "AWK", "AES", "CNP",
    "PNW", "EVRG",
    # Real Estate
    "PLD", "AMT", "EQIX","SPG", "O",   "VICI","AVB", "EQR", "MAA", "UDR",
    "CPT", "ESS", "BXP", "VTR", "IRM", "PSA", "EXR", "DLR", "CCI", "SBAC",
    "GLPI","KIM", "REG", "FRT", "ARE",
    # Materials
    "LIN", "APD", "SHW", "FCX", "NEM", "NUE", "PPG", "DOW", "DD",  "LYB",
    "CF",  "MOS", "IFF", "EMN", "CE",  "ALB", "FMC", "IP",  "WRK", "PKG",
    "SON", "SEE", "GWW", "RPM", "STLD","RS",
    # Weitere Financials
    "BEN", "AMG", "IVZ", "PFG", "WTW", "PRI", "ERIE","RNR", "ACGL","EG",
    "BRO", "FAF", "MTB", "CFG", "FITB","HBAN","KEY", "RF",  "ZION",
    # Weitere Healthcare
    "ALNY","INCY","EXAS","NTRA","BMRN","SRPT","PODD","CRL", "NVCR",
    # Weitere Industrials (Transport, Defense, Spezial)
    "LHX", "SAIC","WAT", "CHRW","EXPD","XPO", "GXO", "JBHT","LSTR","HUBB",
    "NDSN","GGG", "PWR", "FLR", "J",   "MTZ", "ACM",
]

def _fetch_sp500_tickers():
    try:
        df = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
        ts = df['Symbol'].dropna().astype(str).str.strip().str.replace('.', '-', regex=False).tolist()
        ts = sorted([x for x in ts if x and len(x) <= 6])
        if len(ts) >= 490:
            print(f"S&P 500: {len(ts)} Ticker von Wikipedia geladen")
            return ts
        raise ValueError(f"Nur {len(ts)} Ticker gefunden")
    except Exception as e:
        print(f"⚠️  Wikipedia-Fetch fehlgeschlagen ({e}), nutze Fallback")
        return None

_all_sp500 = _fetch_sp500_tickers()
if _all_sp500:
    tickers = _all_sp500[len(_all_sp500)//2:]
    print(f"Teil 2: {len(tickers)} Ticker (zweite Hälfte N–Z)")
else:
    tickers = list(set(_SP500_FALLBACK_2))

benchmark   = "^GSPC"
rs_windows  = {"5T": 5, "10T": 10, "20T": 20, "50T": 50, "6M": 126, "12M": 252}
OUTPUT_FILE = "rs_sp500_2.json"

def sanitize_nan(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nan(v) for v in obj]
    return obj

print(f"Teil 2: RS-Berechnung für {len(tickers)} S&P 500-Aktien (ohne QQQ-Werte)...")
all_tickers = tickers + [benchmark]
raw   = yf.download(all_tickers, period="1y", auto_adjust=True, progress=False)
close = raw["Close"]
spx   = close[benchmark]

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

all_results.sort(key=lambda x: x["score"], reverse=True)
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

def extract_ohlcv(ticker, raw_data, n_candles):
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
            result.append({"d": date.strftime("%Y-%m-%d"),
                           "o": round(float(ov), 2), "h": round(float(hv), 2),
                           "l": round(float(lv), 2), "c": round(float(cv), 2)})
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
        df = df[["Open","High","Low","Close"]].dropna()
        df.index = pd.to_datetime(df.index)
        df_4h = df.resample("4h", offset="1h30min").agg(
            {"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
        result = []
        for dt, row in df_4h.iterrows():
            if pd.isna(row["Close"]): continue
            result.append({"d": dt.strftime("%Y-%m-%d %H:%M"),
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

print("\nHistorisches tägliches Ranking (Teil 2)...")
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
                print(f"  Vorwoche-Scores (Teil 2): {len(prev_week_scores)} Ticker (Stand: {date_str})")
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
                 "ohlcv_w":  extract_ohlcv(t, raw_weekly, 104),
                 "ohlcv":    extract_ohlcv(t, raw_daily, 520),
                 "ohlcv_4h": ohlcv_4h_map.get(t, [])})

output = {
    "timestamp":            datetime.now().strftime("%Y-%m-%d %H:%M"),
    "benchmark":            "SPX",
    "data":                 data,
    "daily_scores_by_date": daily_scores_by_date,
    "prev_week_scores":     prev_week_scores,
    "benchmark_ohlcv_w":    extract_ohlcv(benchmark, raw_weekly, 104),
    "benchmark_ohlcv":      extract_ohlcv(benchmark, raw_daily, 520),
}
with open(OUTPUT_FILE, "w") as f:
    json.dump(sanitize_nan(output), f)
print(f"✅ Teil 2 fertig – {len(data)} Ticker → {OUTPUT_FILE}")

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
        _f.write(f"### S&P 500 – Teil 2\n{_icon} **{_loaded}/{_expected} Ticker geladen ({_pct:.0f}%)**\n")
        if _missing:
            _f.write(f"Fehlende Ticker: `{'`, `'.join(sorted(_missing))}`\n")
        _f.write("\n")
