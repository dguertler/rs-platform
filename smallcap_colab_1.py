import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import yfinance as yf
import pandas as pd
import json
import math
from datetime import datetime, timedelta
from fetch_tickers import fetch_sp600, detect_index_changes

_SP600_FALLBACK_1 = [
    # Technology
    "AAON","ACIW","ACLS","ADTN","AGYS","ALRM","AMBA","ANET","ANGI","APPF",
    "APPN","ARLO","ASGN","ATEN","ATNI","AVAV","AVNT","AWH","BAND","BDC",
    "BELFB","BJRI","BL","BLKB","BMI","BRKS","CABO","CALX","CASA","CDNA",
    "CEVA","CHKP","COHU","COWI","CRSR","CSGS","CSTL","CVLT","DDOG","DIOD",
    "DLB","DMRC","DSGN","DXPE","DZSI","EGHT","ENFN","ENPH","ESNT","ETSY",
    "EVBG","EXTR","FARO","FCFS","FFIV","FORM","FOUR","FRSH","GKOS","GLOW",
    "GRMN","HLIT","HMHC","HURN","ICFI","IDCC","IDEX","IIPR","INFU","INFN",
    "INGN","IPGP","ISRG","ITRI","JCOM","JRVR","JTAI","KFRC","KLAC","KLIC",
    "LASR","LBRT","LNTH","LOPE","LQDT","LUNA","LYFT","MARA","MASI","MATR",
    "MATX","MBUU","MCHP","MCRI","MGLN","MMSI","MNKD","MNTV","MOGA","MPWR",
    "MRCY","MRTN","MTSI","NATI","NCNO","NDSN","NKTR","NMBL","NOVT","NSIT",
    "NUAN","NVEI","NVST","OMCL","ONTO","OPEN","OPTN","OSPN","PAYX","PCTY",
    "PDCO","PLAB","PLAY","PLMR","PLXS","PODD","POWL","PRFT","PRLB","PRSC",
    "PSMT","PTEN","PWSC","QCRH","QLYS","QLYX","RMBS","RNET","ROCK","RODI",
    "ROKU","RPAY","RSKD","RXT","SAFE","SAIA","SAVA","SBCF","SCHL","SFBS",
    "SFLY","SGH","SHOO","SITM","SMBC","SMCI","SMED","SNBR","SOFI","SOHU",
    "SPNS","SPSC","SPWR","SQ","SRCE","SSNC","STER","STRL","SUMO","SUPN",
    "SWBI","SWCH","SYBT","SYNA","TAST","TCBK","TCMD","TDOC","TGTX","TILE",
    "TMDX","TMHC","TPVG","TREE","TRIN","TRMK","TRNO","TRSOX","TRUP","TTEC",
    "TTGT","TTMI","TWNK","UCBI","UFCS","UFPT","ULBI","UMBF","UMPQ","UNFI",
    "UNIT","UPLD","USAP","USDP","USFD","UTHR","VCRA","VERX","VICR","VIRT",
    "VIVO","VLGEA","VNET","VNTV","VRRM","VSCO","VSEA","VSLR","VTOL","VYGR",
    "WAFD","WARR","WASH","WBTN","WEST","WGO","WILC","WINA","WINT","WLDN",
    "WOLF","WOOF","WOR","WRLD","WSBC","WSBF","WSFS","WTBA","WTFC","WTTR",
    "XBIT","XELA","XERS","XNCR","XPEL","XTLB","YEXT","YMAB","YNAB","ZETA",
    # Healthcare Small-Cap
    "ACAD","ACHC","ADMA","AGIO","AIXI","AKBA","ALEC","ALGN","ALKS","ALLO",
    "ALNY","ALTR","AMAG","AMEH","AMKR","AMRS","AMTI","ANIK","AORT","APLS",
    "APLT","APOG","APRE","APVO","ARAV","ARDX","ARGT","AROW","ARQT","ARWR",
    "ASRT","ASTC","ATIS","ATLO","ATMU","ATNI","ATRC","ATRI","ATRS","ATSG",
    "ATUS","AUID","AUMN","AURX","AUTL","AVAH","AVCO","AVDL","AVEO","AVES",
    "AVIR","AVNS","AVTE","AVXL","AXDX","AXNX","AXON","AXSM","AXTI","AYTU",
    # Industrials Small-Cap
    "AAOI","ABCB","ABCL","ABEO","ABED","ABGI","ABIO","ABKX","ABMD","ABTX",
    "ABTS","ABVC","ABVX","ABXX","ACBI","ACBT","ACCD","ACEL","ACGL","ACHC",
]

_all_sp600, _official_sp600 = fetch_sp600(fallback=_SP600_FALLBACK_1)
if _all_sp600:
    tickers = _all_sp600[:len(_all_sp600)//2]
    print(f"Teil 1: {len(tickers)} Ticker (erste Hälfte)")
    print("\nPrüfe Indexänderungen (IC vs. EDC) Teil 1...")
    _changes = detect_index_changes(_official_sp600, "data/rs_smallcap.json")
    _new_stocks = set(_changes["new"])
    if _new_stocks:
        print(f"Neue Aktien im S&P 600 (gesamt): {', '.join(sorted(_new_stocks))}")
else:
    tickers = list(set(_SP600_FALLBACK_1))
    _official_sp600 = []
    _new_stocks = set()

_today = datetime.now().strftime("%Y-%m-%d")
_new_since_map = {}
try:
    with open("data/rs_smallcap.json", encoding="utf-8") as _f:
        for _d in json.load(_f).get("data", []):
            if _d.get("new_since"):
                _new_since_map[_d["ticker"]] = _d["new_since"]
except Exception:
    pass
for _t in _new_stocks:
    _new_since_map.setdefault(_t, _today)

benchmark   = "^SP600"
rs_windows  = {"5T": 5, "10T": 10, "20T": 20, "50T": 50, "6M": 126, "12M": 252}
OUTPUT_FILE = "rs_smallcap_1.json"

def sanitize_nan(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nan(v) for v in obj]
    return obj

print(f"Teil 1: RS-Berechnung für {len(tickers)} S&P 600-Aktien...")
all_tickers = tickers + [benchmark]
raw   = yf.download(all_tickers, period="1y", auto_adjust=True, progress=False)
close = raw["Close"]
spsc  = close[benchmark].dropna()
if len(spsc) < 60:
    raise RuntimeError(
        f"Benchmark {benchmark}: nur {len(spsc)} gueltige Kurse im Batch-Download – "
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
                float((s.iloc[-1]/s.iloc[-days]-1)*100 - (spsc.iloc[-1]/spsc.iloc[-days]-1)*100), 2)
        except:
            windows_result[label] = None
    score = round(sum(v for v in windows_result.values() if v is not None), 2)
    all_results.append({"ticker": ticker, "score": score, "windows": windows_result})

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

def extract_ohlcv(ticker, raw_data, n_candles):
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
            row = {"d": date.strftime("%Y-%m-%d"),
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
        df = df[["Open","High","Low","Close"]].copy()
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

# 4H nur für Top-100 (Laufzeit-Optimierung bei 300 Tickern pro Script)
top100_set = set(r["ticker"] for r in all_results[:100])
print(f"\n4H OHLCV ({len(all_tickers_list)} Ticker, vollständig für Top 100)...")
ohlcv_4h_map = {}
for i, ticker in enumerate(all_tickers_list):
    if ticker in top100_set:
        print(f"  4H [{i+1}/{len(all_tickers_list)}] {ticker}...", end=" ", flush=True)
        ohlcv_4h_map[ticker] = extract_ohlcv_4h(ticker)
        print(f"{len(ohlcv_4h_map[ticker])} Kerzen")
    else:
        ohlcv_4h_map[ticker] = []

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
        if scores:
            daily_scores_by_date[date_str] = scores
        if i == prev_week_i:
            prev_week_scores = dict(scores)
    print(f"  {len(daily_scores_by_date)} Tage berechnet")
except Exception as e:
    daily_scores_by_date = {}
    prev_week_scores = {}
    print(f"  ⚠️ Fehler: {e}")

print("\nJSON zusammenbauen (Teil 1)...")
data = []
for r in all_results:
    ticker = r["ticker"]
    data.append({
        "ticker":    ticker,
        "score":     r["score"],
        "windows":   r["windows"],
        "prev_rank": None,
        "new_since": _new_since_map.get(ticker),
        "ohlcv_w":   extract_ohlcv(ticker, raw_weekly, 104),
        "ohlcv":     extract_ohlcv(ticker, raw_daily, 520),
        "ohlcv_4h":  ohlcv_4h_map.get(ticker, []),
    })

benchmark_ohlcv_w = extract_ohlcv(benchmark, raw_weekly, 104)
benchmark_ohlcv_d = extract_ohlcv(benchmark, raw_daily, 520)

output = {
    "timestamp":              datetime.now().strftime("%Y-%m-%d %H:%M"),
    "benchmark":              "SC600",
    "fmp_tickers":            _official_sp600,
    "data":                   data,
    "benchmark_ohlcv_w":      benchmark_ohlcv_w,
    "benchmark_ohlcv":        benchmark_ohlcv_d,
    "daily_scores_by_date":   {d: s for d, s in daily_scores_by_date.items()},
    "prev_week_scores":       prev_week_scores,
}

with open(OUTPUT_FILE, "w") as f:
    json.dump(sanitize_nan(output), f)

size_kb = len(json.dumps(sanitize_nan(output))) / 1024
print(f"\n✅ Teil 1 fertig! {len(data)} Ticker, {size_kb:.0f} KB → {OUTPUT_FILE}")

_sf = __import__("os").environ.get("GITHUB_STEP_SUMMARY")
if _sf:
    _pct = len(data) / len(tickers) * 100 if tickers else 0
    with open(_sf, "a") as _f:
        _f.write(f"### S&P 600 SmallCap – Teil 1\n✅ **{len(data)}/{len(tickers)} Ticker ({_pct:.0f}%)**\n\n")
