import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import yfinance as yf
import pandas as pd
import json
import math
from datetime import datetime, timedelta
from fetch_tickers import fetch_nasdaq100, detect_index_changes
from rs_core import RS_WINDOWS, rank_by_day

_NASDAQ100_FALLBACK = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "COST",
    "NFLX", "AMD", "ADBE", "QCOM", "PEP", "INTU", "CSCO", "AMAT", "TXN", "HON",
    "AMGN", "SBUX", "BKNG", "ISRG", "GILD", "ADI", "LRCX", "REGN", "MU", "VRTX",
    "PANW", "KLAC", "SNPS", "CDNS", "MRVL", "ORLY", "CTAS", "ASML", "FTNT", "MDLZ",
    "ABNB", "MNST", "PYPL", "MELI", "NXPI", "WDAY", "CPRT", "ROST", "KDP", "AEP",
    "PCAR", "DDOG", "IDXX", "ODFL", "FAST", "BIIB", "TEAM", "EA", "ZS", "SIRI",
    "VRSK", "GEHC", "ON", "INTC", "CTSH", "DLTR", "XEL", "FANG", "CRWD", "TTWO",
    "ILMN", "MRNA", "SMCI", "ARM", "MCHP", "ADSK", "CHTR", "PAYX", "DXCM", "CEG",
    "CCEP", "COIN", "APP", "AXON", "WELL", "HUBS", "TTD", "OKTA", "SNDK", "MSTR",
    "PLTR", "RXRX", "GFS", "LULU", "EBAY", "LITE", "FSLR", "DASH",
    "ROP", "CDW", "NTRA",
]
# ANSS entfernt: Synopsys hat Ansys 2025 übernommen, Ticker delisted (yfinance liefert keine Daten mehr)

tickers, _official = fetch_nasdaq100(fallback=_NASDAQ100_FALLBACK)

# IC vs. EDC: neue Aktien im Index erkennen (nur offizielle FMP/Wikipedia-Liste)
print("\nPrüfe Indexänderungen (IC vs. EDC)...")
_changes = detect_index_changes(_official, "data/rs_full.json")
_new_stocks = set(_changes["new"])
if _new_stocks:
    print(f"Neue Aktien erhalten vollständige 2-Jahres-Historie: {', '.join(sorted(_new_stocks))}")

# new_since-Datum: aus EDC übernehmen oder heute für neue Aktien setzen
_today = datetime.now().strftime("%Y-%m-%d")
_new_since_map = {}
try:
    with open("data/rs_full.json", encoding="utf-8") as _f:
        for _d in json.load(_f).get("data", []):
            if _d.get("new_since"):
                _new_since_map[_d["ticker"]] = _d["new_since"]
except Exception:
    pass
for _t in _new_stocks:
    _new_since_map.setdefault(_t, _today)

benchmark = "QQQ"
rs_windows = RS_WINDOWS

def sanitize_nan(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nan(v) for v in obj]
    return obj

# ── Schritt 1: RS-Score Batch-Download ──────────────────────────────────────
print(f"Schritt 1: RS-Berechnung für alle {len(tickers)} Aktien...")
all_tickers = tickers + [benchmark]
raw = yf.download(all_tickers, period="1y", auto_adjust=True, progress=False)
close = raw["Close"]
qqq = close[benchmark].dropna()
if len(qqq) < 60:
    raise RuntimeError(
        f"Benchmark {benchmark}: nur {len(qqq)} gueltige Kurse im Batch-Download – "
        f"Abbruch, damit keine leeren RS-Scores committet werden."
    )

def _calc_rs(s, qqq_s):
    windows_result = {}
    for label, days in rs_windows.items():
        try:
            windows_result[label] = round(
                float((s.iloc[-1]/s.iloc[-days]-1)*100 - (qqq_s.iloc[-1]/qqq_s.iloc[-days]-1)*100), 2)
        except:
            windows_result[label] = None
    score = round(sum(v for v in windows_result.values() if v is not None), 2)
    return score, windows_result

all_results = []
for ticker in tickers:
    if ticker not in close.columns:
        continue
    s = close[ticker].dropna()
    if len(s) < 50:
        continue
    score, windows_result = _calc_rs(s, qqq)
    all_results.append({"ticker": ticker, "score": score, "windows": windows_result})

# Nachlader: Ticker die im Batch fehlen oder < 50 Tage haben
batch_found = {r["ticker"] for r in all_results}
missing_rs  = [t for t in tickers if t not in batch_found]
if missing_rs:
    print(f"\n  Nachlader RS: {len(missing_rs)} fehlende Ticker: {', '.join(missing_rs)}")
    qqq_ind = yf.download(benchmark, period="2y", auto_adjust=True, progress=False)
    if isinstance(qqq_ind.columns, pd.MultiIndex):
        qqq_ind.columns = qqq_ind.columns.get_level_values(0)
    qqq_ind_s = qqq_ind["Close"].dropna()
    for t in missing_rs:
        try:
            r = yf.download(t, period="2y", auto_adjust=True, progress=False)
            if isinstance(r.columns, pd.MultiIndex):
                r.columns = r.columns.get_level_values(0)
            s = r["Close"].dropna()
            if len(s) < 10:
                print(f"    {t}: zu wenig Daten ({len(s)} Tage) – übersprungen")
                continue
            score, windows_result = _calc_rs(s, qqq_ind_s)
            all_results.append({"ticker": t, "score": score, "windows": windows_result})
            print(f"    {t}: ✓ Score={score}, {len(s)} Tage")
        except Exception as e:
            print(f"    {t}: Fehler – {e}")

# Schutz: bei fehlerhafter Datenquelle (z.B. NaN-Benchmark) nicht stillschweigend
# leere Scores committen, sondern abbrechen -> Workflow schlaegt fehl + Fehler-Mail,
# bestehende gute Daten bleiben erhalten.
_valid = sum(1 for r in all_results if r["score"] is not None and r["score"] == r["score"])
if _valid < len(tickers) * 0.5:
    raise RuntimeError(
        f"Nur {_valid}/{len(tickers)} gueltige RS-Scores berechnet – Abbruch "
        f"(Datenquelle fehlerhaft, keine NaN-Daten committen)."
    )

all_results.sort(key=lambda x: (x["score"] is not None and x["score"] == x["score"], x["score"]), reverse=True)
top20 = [r["ticker"] for r in all_results[:20]]
print(f"Top 20: {', '.join(top20)}")

# ── Schritt 2: Weekly OHLCV (letzte 104 Wochen = 2 Jahre) ───────────────────
print(f"\nSchritt 2: Weekly OHLCV für {len(all_results)} Ticker (104 Wochen)...")
end_date     = datetime.now()
end_str      = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
start_weekly = end_date - timedelta(days=760)
start_daily  = end_date - timedelta(days=760)

all_tickers_list = [r["ticker"] for r in all_results]
raw_weekly = yf.download(
    all_tickers_list + [benchmark],
    start=start_weekly.strftime("%Y-%m-%d"),
    end=end_str,
    interval="1wk",
    auto_adjust=True,
    progress=False
)

def _ohlcv_from_raw(ticker, raw_data, n_candles, date_fmt="%Y-%m-%d"):
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
            row = {
                "d": date.strftime(date_fmt),
                "o": round(float(ov), 2),
                "h": round(float(hv), 2),
                "l": round(float(lv), 2),
                "c": round(float(cv), 2)
            }
            if vv is not None and not pd.isna(vv):
                row["v"] = round(float(vv), 0)
            result.append(row)
        return result[-n_candles:]
    except:
        return []

def _ohlcv_individual(ticker, start_str, end_str, interval, n_candles, date_fmt="%Y-%m-%d"):
    """Einzeldownload für einen Ticker – Fallback wenn Batch-Daten fehlen/dünn."""
    try:
        df = yf.download(ticker, start=start_str, end=end_str,
                         interval=interval, auto_adjust=True, progress=False)
        if df.empty:
            return []
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        result = []
        for date, row in df.iterrows():
            if pd.isna(row["Close"]): continue
            entry = {
                "d": date.strftime(date_fmt),
                "o": round(float(row["Open"]), 2),
                "h": round(float(row["High"]), 2),
                "l": round(float(row["Low"]),  2),
                "c": round(float(row["Close"]), 2)
            }
            if pd.notna(row.get("Volume")):
                entry["v"] = round(float(row["Volume"]), 0)
            result.append(entry)
        return result[-n_candles:]
    except Exception as e:
        print(f"    Einzeldownload {ticker} ({interval}): Fehler – {e}")
        return []

def extract_ohlcv_weekly(ticker, raw_data, n_candles=104):
    data = _ohlcv_from_raw(ticker, raw_data, n_candles)
    if len(data) < 10:
        print(f"  {ticker}: nur {len(data)} Wochenkerzen im Batch – lade individuell nach...")
        data = _ohlcv_individual(ticker, start_weekly.strftime("%Y-%m-%d"), end_str, "1wk", n_candles)
        print(f"    → {len(data)} Kerzen")
    return data

# ── Schritt 3: Daily OHLCV (letzte 520 Kerzen ≈ 2 Jahre) ────────────────────
print(f"\nSchritt 3: Daily OHLCV für {len(all_results)} Ticker (520 Kerzen)...")
raw_daily = yf.download(
    all_tickers_list + [benchmark],
    start=start_daily.strftime("%Y-%m-%d"),
    end=end_str,
    interval="1d",
    auto_adjust=True,
    progress=False
)

def extract_ohlcv_daily(ticker, raw_data, n_candles=520):
    data = _ohlcv_from_raw(ticker, raw_data, n_candles)
    if len(data) < 30:
        print(f"  {ticker}: nur {len(data)} Tageskerzen im Batch – lade individuell nach...")
        data = _ohlcv_individual(ticker, start_daily.strftime("%Y-%m-%d"), end_str, "1d", n_candles)
        print(f"    → {len(data)} Kerzen")
    return data

# ── Schritt 4: 4H OHLCV ─────────────────────────────────────────────────────
print(f"\nSchritt 4: 4H OHLCV für {len(all_results)} Ticker (60 Tage)...")
start_4h = end_date - timedelta(days=60)

def extract_ohlcv_4h(ticker, n_candles=3000):
    try:
        df = yf.download(
            ticker,
            start=start_4h.strftime("%Y-%m-%d"),
            end=end_str,
            interval="1h",
            prepost=True,
            auto_adjust=True,
            progress=False
        )
        if df.empty:
            return []
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
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
        df.loc[bad_low, "Low"] = df.loc[bad_low, ["Open", "Close"]].min(axis=1)

        df_4h = df[["Open", "High", "Low", "Close"]].resample("4h").agg({
            "Open":  "first",
            "High":  "max",
            "Low":   "min",
            "Close": "last"
        }).dropna()

        result = []
        for dt, row in df_4h.iterrows():
            if pd.isna(row["Close"]): continue
            dt_local = dt.astimezone(_berlin) if dt.tzinfo else dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(_berlin)
            result.append({
                "d": dt_local.strftime("%Y-%m-%d %H:%M"),
                "o": round(float(row["Open"]),  2),
                "h": round(float(row["High"]),  2),
                "l": round(float(row["Low"]),   2),
                "c": round(float(row["Close"]), 2)
            })
        return result[-n_candles:]
    except Exception as e:
        print(f"  Fehler 4H {ticker}: {e}")
        return []

ohlcv_4h_map = {}
for i, ticker in enumerate(all_tickers_list):
    print(f"  4H [{i+1}/{len(all_tickers_list)}] {ticker}...", end=" ")
    data_4h = extract_ohlcv_4h(ticker)
    ohlcv_4h_map[ticker] = data_4h
    print(f"{len(data_4h)} Kerzen")

# ── Schritt 5: Historisches tägliches Top-20-Ranking ────────────────────────
print("\nSchritt 5: Historisches tägliches Top-20-Ranking...")
try:
    d_close = raw_daily["Close"] if isinstance(raw_daily.columns, pd.MultiIndex) else raw_daily
    if benchmark not in d_close.columns:
        raise KeyError(f"Benchmark {benchmark} nicht in Tagesdaten")
    top20_history = {}
    prev_rank_map = {}
    prev_week_i = max(0, len(d_close) - 6)
    # Formel liegt in rs_core.py — dieselbe nutzt der historische Backtest
    for i, date_str, scores in rank_by_day(d_close, benchmark, all_tickers_list, windows=rs_windows):
        top20_history[date_str] = [t for t, _ in scores[:20]]
        if i == prev_week_i:
            prev_rank_map = {t: r + 1 for r, (t, _) in enumerate(scores)}
            print(f"  Vorwoche-Ranking: {len(prev_rank_map)} Ticker (Stand: {date_str})")
    print(f"  {len(top20_history)} Tage berechnet")
except Exception as e:
    top20_history = {}
    prev_rank_map = {}
    print(f"  ⚠️ Fehler: {e}")

# ── Schritt 6: JSON zusammenbauen ───────────────────────────────────────────
print("\nSchritt 6: JSON zusammenbauen...")
data = []
for r in all_results:
    ticker  = r["ticker"]
    ohlcv_w = extract_ohlcv_weekly(ticker, raw_weekly)
    ohlcv_d = extract_ohlcv_daily(ticker, raw_daily)
    ohlcv4h = ohlcv_4h_map.get(ticker, [])
    data.append({
        "ticker":    ticker,
        "score":     r["score"],
        "windows":   r["windows"],
        "prev_rank": prev_rank_map.get(ticker),
        "new_since": _new_since_map.get(ticker),
        "ohlcv_w":   ohlcv_w,
        "ohlcv":     ohlcv_d,
        "ohlcv_4h":  ohlcv4h
    })

benchmark_ohlcv_w = extract_ohlcv_weekly(benchmark, raw_weekly)
benchmark_ohlcv_d = extract_ohlcv_daily(benchmark, raw_daily)
print(f"Benchmark {benchmark}: Weekly={len(benchmark_ohlcv_w)} Kerzen, Daily={len(benchmark_ohlcv_d)} Kerzen")

# ── NASDAQ-100-Index (NDX) für exakten Vergleich (z.B. Instagram) ────────────
# QQQ ist der ETF; ^NDX ist der echte Index. Wird hier zusätzlich mitgeladen,
# damit die Mehrrendite-Berechnung exakt zum wikifolio-Report passt.
# Explizite Daten statt period= vermeidet das 500-Kerzen-Limit bei ^NDX.
try:
    import datetime as _dt
    _ndx_end = (_dt.date.today() + _dt.timedelta(days=1)).isoformat()
    _ndx_start = (_dt.date.today() - _dt.timedelta(days=760)).isoformat()
    ndx_raw = yf.download("^NDX", start=_ndx_start, end=_ndx_end,
                           auto_adjust=True, progress=False)
    if isinstance(ndx_raw.columns, pd.MultiIndex):
        ndx_raw.columns = ndx_raw.columns.get_level_values(0)
    ndx_close = ndx_raw["Close"].dropna()
    ndx_ohlcv = [{"d": d.strftime("%Y-%m-%d"), "c": round(float(v), 2)}
                 for d, v in ndx_close.items()]
    print(f"NDX (^NDX): {len(ndx_ohlcv)} Tageskerzen (letzter: {ndx_ohlcv[-1]['d'] if ndx_ohlcv else 'n/a'})")
except Exception as _e:
    print(f"NDX-Download fehlgeschlagen: {_e}")
    ndx_ohlcv = []

# ── EUR/USD-Zeitreihe für exakte EUR-Renditen (Instagram-Slides) ─────────────
# EURUSD=X = USD je EUR. instagram/store.py rechnet damit USD-Kursrenditen in
# echte EUR-Renditen um: ret_eur = (P1/P0) * (fx0/fx1) - 1.
try:
    fx_raw = yf.download("EURUSD=X", period="2y", auto_adjust=True, progress=False)
    if isinstance(fx_raw.columns, pd.MultiIndex):
        fx_raw.columns = fx_raw.columns.get_level_values(0)
    fx_close = fx_raw["Close"].dropna()
    eurusd_ohlcv = [{"d": d.strftime("%Y-%m-%d"), "c": round(float(v), 4)}
                    for d, v in fx_close.items()]
    print(f"EUR/USD (EURUSD=X): {len(eurusd_ohlcv)} Tageswerte")
except Exception as _e:
    print(f"EUR/USD-Download fehlgeschlagen: {_e}")
    eurusd_ohlcv = []

output = {
    "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M"),
    "benchmark":         "QQQ",
    "fmp_tickers":       _official,
    "top20":             top20,
    "top20_history":     top20_history,
    "data":              data,
    "benchmark_ohlcv_w": benchmark_ohlcv_w,
    "benchmark_ohlcv":   benchmark_ohlcv_d,
    "ndx_ohlcv":         ndx_ohlcv,
    "eurusd_ohlcv":      eurusd_ohlcv,
}

with open("rs_full.json", "w") as f:
    json.dump(sanitize_nan(output), f)

size_kb = len(json.dumps(sanitize_nan(output))) / 1024
print(f"\n✅ Fertig! Dateigröße: {size_kb:.0f} KB")
print(f"Timestamp: {output['timestamp']}")
print(f"Ticker gesamt: {len(data)}")
print("Top 5:")
for i, r in enumerate(data[:5]):
    print(f"  {i+1}. {r['ticker']}: Score={r['score']}, Weekly={len(r['ohlcv_w'])} Kerzen, Daily={len(r['ohlcv'])} Kerzen, 4H={len(r['ohlcv_4h'])} Kerzen")
print("\nDatei gespeichert: rs_full.json")

# ── Validierung ──────────────────────────────────────────────────────────────
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
        _f.write(f"### NASDAQ 100\n{_icon} **{_loaded}/{_expected} Ticker geladen ({_pct:.0f}%)**\n")
        if _missing:
            _f.write(f"Fehlende Ticker: `{'`, `'.join(sorted(_missing))}`\n")
        _f.write("\n")
