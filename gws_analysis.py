from datetime import datetime


def _find_gws(swing_highs, swing_lows):
    candidates = []
    for j in range(1, len(swing_lows)):
        tief_neu_idx, tief_neu_price = swing_lows[j]
        tief_alt_idx, tief_alt_price = swing_lows[j - 1]
        if tief_neu_price < tief_alt_price:
            between = [(idx, p) for idx, p in swing_highs if tief_alt_idx < idx < tief_neu_idx]
            if between:
                candidates.append(max(between, key=lambda x: x[1]))
    return candidates[-1] if candidates else None


def struct_weekly(ohlcv_w):
    if not ohlcv_w or len(ohlcv_w) < 8:
        return None
    n = len(ohlcv_w)
    highs  = [d["h"] for d in ohlcv_w]
    lows   = [d["l"] for d in ohlcv_w]
    closes = [d["c"] for d in ohlcv_w]
    sh = [(i, highs[i]) for i in range(1, n - 1) if highs[i] >= highs[i-1] and highs[i] >= highs[i+1]]
    sl = [(i, lows[i])  for i in range(1, n - 1) if lows[i]  <= lows[i-1]  and lows[i]  <= lows[i+1]]
    gws = _find_gws(sh, sl)
    trend = "neutral"
    if len(sh) >= 2:
        if sh[-1][1] > sh[-2][1]: trend = "bullish"
        elif sh[-1][1] < sh[-2][1]: trend = "bearish"
    breakout_idx = None
    if gws:
        gws_idx, gws_price = gws
        for i in range(gws_idx + 1, n):
            if closes[i] > gws_price:
                breakout_idx = i
                break
    broken = breakout_idx is not None or (gws is None and trend == "bullish")
    recent = breakout_idx is not None and (n - 1 - breakout_idx) <= 1
    return {"broken": broken, "recentBreakout": recent}


def struct_daily(ohlcv):
    if not ohlcv or len(ohlcv) < 10:
        return None
    n = len(ohlcv)
    highs  = [d["h"] for d in ohlcv]
    lows   = [d["l"] for d in ohlcv]
    closes = [d["c"] for d in ohlcv]
    sh = [(i, highs[i]) for i in range(2, n - 2)
          if highs[i] >= highs[i-1] and highs[i] >= highs[i-2] and highs[i] >= highs[i+1] and highs[i] >= highs[i+2]]
    sl = [(i, lows[i])  for i in range(2, n - 2)
          if lows[i]  <= lows[i-1]  and lows[i]  <= lows[i-2]  and lows[i]  <= lows[i+1]  and lows[i]  <= lows[i+2]]
    gws = _find_gws(sh, sl)
    trend = "neutral"
    if len(sh) >= 2:
        if sh[-1][1] > sh[-2][1]: trend = "bullish"
        elif sh[-1][1] < sh[-2][1]: trend = "bearish"
    breakout_idx = None
    if gws:
        gws_idx, gws_price = gws
        for i in range(gws_idx + 1, n):
            if closes[i] > gws_price:
                breakout_idx = i
                break
    broken = breakout_idx is not None or (gws is None and trend == "bullish")
    recent = broken and breakout_idx is not None and (n - 1 - breakout_idx) <= 7
    return {"broken": broken, "recentBreakout": recent}


def struct_4h(ohlcv_4h):
    if not ohlcv_4h or len(ohlcv_4h) < 8:
        return None
    n = len(ohlcv_4h)
    highs  = [d["h"] for d in ohlcv_4h]
    lows   = [d["l"] for d in ohlcv_4h]
    closes = [d["c"] for d in ohlcv_4h]
    sh = [(i, highs[i]) for i in range(2, n - 2)
          if highs[i] >= highs[i-1] and highs[i] >= highs[i-2] and highs[i] >= highs[i+1] and highs[i] >= highs[i+2]]
    sl = [(i, lows[i])  for i in range(2, n - 2)
          if lows[i]  <= lows[i-1]  and lows[i]  <= lows[i-2]  and lows[i]  <= lows[i+1]  and lows[i]  <= lows[i+2]]
    gws = _find_gws(sh, sl)
    trend = "neutral"
    if len(sh) >= 2:
        if sh[-1][1] > sh[-2][1]: trend = "bullish"
        elif sh[-1][1] < sh[-2][1]: trend = "bearish"
    breakout_idx = None
    if gws:
        gws_idx, gws_price = gws
        for i in range(gws_idx + 1, n):
            if closes[i] > gws_price:
                breakout_idx = i
                break
    broken4h = breakout_idx is not None or (gws is None and trend == "bullish")
    recent = False
    if breakout_idx is not None:
        try:
            d_str   = ohlcv_4h[breakout_idx]["d"].replace(" ", "T")
            last_str = ohlcv_4h[n - 1]["d"].replace(" ", "T")
            recent = (datetime.fromisoformat(last_str) - datetime.fromisoformat(d_str)).days <= 7
        except Exception:
            recent = (n - 1 - breakout_idx) <= 28
    return {"broken4h": broken4h, "recentBreakout": recent}


def struct_for_entry(entry):
    result = {}
    s = struct_weekly(entry.get("ohlcv_w"))
    if s: result["weekly"] = s
    s = struct_daily(entry.get("ohlcv"))
    if s: result["daily"] = s
    s = struct_4h(entry.get("ohlcv_4h"))
    if s: result["h4"] = s
    return result
