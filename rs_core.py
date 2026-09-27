"""
rs_core.py — RS-Tagesranking, gemeinsam für rs_colab.py (live) und den
historischen Backtest (backtest_history/). Eine Formel, eine Stelle: der
historische Test ist nur aussagekräftig, wenn er exakt so rankt wie live.

Score je Ticker und Tag = Summe über alle Fenster von
  (Kursrendite Ticker − Kursrendite Benchmark) in Prozentpunkten.
Ein Fenster zählt nur, wenn beide Vergangenheitskurse vorliegen und ≠ 0 sind;
ein Ticker ohne ein einziges gültiges Fenster fällt aus dem Tagesranking.
"""
import numpy as np

RS_WINDOWS = {"5T": 5, "10T": 10, "20T": 20, "50T": 50, "6M": 126, "12M": 252}
MIN_RANKED = 20


def rank_by_day(d_close, benchmark, tickers, member_mask=None, windows=RS_WINDOWS):
    """Tagesranking über alle Zeilen von d_close.

    d_close:     DataFrame Schlusskurse (Zeilen = Handelstage, Spalten = Symbole)
    benchmark:   Spaltenname der Benchmark (z. B. "QQQ")
    tickers:     zu rankende Spalten; die Reihenfolge entscheidet bei Gleichstand
    member_mask: optional bool-Array (Zeilen × tickers) — False = an diesem Tag
                 nicht im Index, wird nicht gerankt (Kurse zählen trotzdem für
                 die Fenster)

    Liefert je Tag mit mindestens MIN_RANKED gerankten Tickern
    (zeilenindex, "YYYY-MM-DD", [(ticker, score), ...] absteigend sortiert).
    """
    tickers = [t for t in tickers if t in d_close.columns]
    if benchmark not in d_close.columns or not tickers:
        return
    prices = d_close[tickers].to_numpy(dtype=float)
    bench = d_close[benchmark].to_numpy(dtype=float)
    n = len(d_close)

    total = np.zeros_like(prices)
    count = np.zeros(prices.shape, dtype=int)
    with np.errstate(divide="ignore", invalid="ignore"):
        for days in windows.values():
            if days >= n:
                continue
            s_prev = np.full_like(prices, np.nan)
            s_prev[days:] = prices[:-days]
            b_prev = np.full_like(bench, np.nan)
            b_prev[days:] = bench[:-days]
            valid = (~np.isnan(s_prev) & (s_prev != 0)
                     & ~np.isnan(b_prev)[:, None] & (b_prev != 0)[:, None])
            contrib = (prices / s_prev - 1) * 100 - ((bench / b_prev - 1) * 100)[:, None]
            total += np.where(valid, contrib, 0.0)
            count += valid

    rankable = ~np.isnan(prices) & (prices != 0) & (count > 0)
    if member_mask is not None:
        rankable &= member_mask
    bench_ok = ~np.isnan(bench) & (bench != 0)
    index = d_close.index

    for i in range(n):
        if not bench_ok[i]:
            continue
        cols = np.flatnonzero(rankable[i])
        if len(cols) < MIN_RANKED:
            continue
        scores = [(tickers[c], float(total[i, c])) for c in cols]
        scores.sort(key=lambda x: x[1], reverse=True)
        yield i, index[i].strftime("%Y-%m-%d"), scores


def membership_mask(index, tickers, intervals):
    """Mitgliedschafts-Maske (Zeilen = Handelstage aus index, Spalten = tickers).

    intervals: {ticker: [[von, bis], ...]} mit bis = None für „noch Mitglied";
    Mitglied ist, wer von <= Tag < bis erfüllt (am Abgangstag nicht mehr).
    """
    days = np.array([d.strftime("%Y-%m-%d") for d in index])
    mask = np.zeros((len(days), len(tickers)), dtype=bool)
    for c, t in enumerate(tickers):
        for start, end in intervals.get(t, []):
            mask[:, c] |= (days >= start) & ((days < end) if end else True)
    return mask


def hourly_to_4h_rows(df, decimals=2):
    """Stundenkerzen (inkl. Vor-/Nachbörse, Index mit Zeitzone) → 4H-Kerzen.

    Live-Logik aus rs_colab.py: Ausreißer-Tiefs außerhalb der Handelszeit
    glätten, dann 4-Stunden-Blöcke ab Mitternacht Börsenzeit, Zeitstempel in
    Berliner Zeit. Der historische Backtest baut seine 4H-Kerzen hierüber.
    """
    import pandas as pd

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
            "o": round(float(row["Open"]),  decimals),
            "h": round(float(row["High"]),  decimals),
            "l": round(float(row["Low"]),   decimals),
            "c": round(float(row["Close"]), decimals)
        })
    return result
