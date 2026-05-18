import os
from datetime import datetime


def fetch_news(ticker: str, max_specific: int = 5, max_general: int = 5) -> dict:
    """Fetch news via yfinance, translate to German.
    Returns {'specific': [...], 'general': [...]}
    """
    try:
        import yfinance as yf
        from deep_translator import GoogleTranslator
    except ImportError:
        return {"specific": [], "general": []}

    try:
        raw = yf.Ticker(ticker).news or []
        ticker_upper = ticker.upper().replace(".DE", "")
        all_parsed = []

        for item in raw:
            if len(all_parsed) >= max_specific + max_general:
                break
            content = item.get("content", {}) or {}
            title = content.get("title") or item.get("title", "")
            url = (
                (content.get("canonicalUrl") or {}).get("url")
                or (content.get("clickThroughUrl") or {}).get("url")
                or item.get("link", "")
            )
            if not title or not url:
                continue
            publisher = (content.get("provider") or {}).get("displayName") or item.get("publisher", "")
            pub_time = content.get("pubDate") or ""
            if pub_time:
                date_str = pub_time[:10]
            else:
                ts = item.get("providerPublishTime", 0)
                date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""

            tagged = [
                t.get("symbol", "").upper()
                for t in (content.get("finance") or {}).get("stockTickers", [])
            ]
            if not tagged:
                tagged = [t.upper() for t in item.get("relatedTickers", [])]

            is_specific = ticker_upper in tagged and len(tagged) <= 3

            try:
                title = GoogleTranslator(source="auto", target="de").translate(title)
            except Exception:
                pass

            all_parsed.append({
                "entry": {"title": title, "url": url, "publisher": publisher, "date_str": date_str},
                "is_specific": is_specific,
            })

        specific, general = [], []
        for p in all_parsed:
            if p["is_specific"] and len(specific) < max_specific:
                specific.append(p["entry"])
            elif not p["is_specific"] and len(general) < max_general:
                general.append(p["entry"])

        if not specific:
            flat = [p["entry"] for p in all_parsed]
            specific = flat[:max_specific]
            general = flat[max_specific : max_specific + max_general]

        return {"specific": specific, "general": general}
    except Exception as e:
        print(f"  News-Abruf für {ticker} fehlgeschlagen: {e}")
        return {"specific": [], "general": []}
