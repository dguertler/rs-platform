"""
check_hidden_alpha.py — Täglicher Screener für Alpha-Kandidaten.

Profil 1: Early Tech Alpha  (Small/Mid-Cap Tech mit Wachstumsbeschleunigung)
Profil 2: Hidden Champions  (Qualitäts-Compounder mit geringer Coverage)
Profil 3: Post-Earnings     (Earnings-Beats aus check_earnings-Logik)

Output: data/alpha_candidates.json (täglich überschrieben)
Kein LLM-Call – reine algorithmische Vorselektion.
"""

import json
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "yfinance", "pandas", "-q"])
    import yfinance as yf
    import pandas as pd

# ── Pfade ─────────────────────────────────────────────────────────────────────

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))

RS_FILES = {
    "QQQ":   DATA_DIR / "rs_full.json",
    "SPX":   DATA_DIR / "rs_sp500.json",
    "DAX":   DATA_DIR / "rs_dax.json",
    "SC600": DATA_DIR / "rs_smallcap.json",
}

FUNDAMENTALS_PATH = DATA_DIR / "fundamentals.json"
ALERTS_STATE_PATH = DATA_DIR / "alerts_state.json"
EARNINGS_PATH     = DATA_DIR / "alpha_candidates.json"

# ── Screening-Schwellen ────────────────────────────────────────────────────────

PROFILE1_SECTORS  = {"Technology", "Communication Services", "Industrials",
                     "Basic Materials", "Consumer Cyclical"}
PROFILE1_MIN_REV_GROWTH   = 0.20   # >20% YoY
PROFILE1_MIN_GROSS_MARGIN = 0.40   # >40%
PROFILE1_MIN_RS           = 60     # RS-Score
PROFILE1_MAX_MARKET_CAP   = 30e9   # <$30B
PROFILE1_MIN_MARKET_CAP   = 0.3e9  # >$300M

PROFILE2_MIN_ROIC         = 0.12   # ROIC >12% (oder ROE-Proxy wenn ROIC fehlt)
PROFILE2_MAX_DE           = 1.0    # D/E <1.0
PROFILE2_MIN_RS           = 45
PROFILE2_MAX_ANALYST_CNT  = 20     # <20 Analysten = geringe Coverage
PROFILE2_MIN_REV_GROWTH   = 0.05   # >5%
PROFILE2_MAX_REV_GROWTH   = 0.30   # <30% (kein Hype-Wachstum)

PROFILE1_MAX_RESULTS = 10
PROFILE2_MAX_RESULTS = 8

# ── GWS-Ampel aus alerts_state.json ──────────────────────────────────────────

def load_gws_state() -> dict:
    """Gibt {ticker: {'daily': bool, 'weekly': bool, 'h4': bool}} zurück."""
    try:
        raw = json.loads(ALERTS_STATE_PATH.read_text(encoding="utf-8"))
        result = {}
        for ticker, state in raw.items():
            result[ticker.upper()] = {
                "daily":  bool(state.get("daily_broken")),
                "weekly": bool(state.get("weekly_broken")),
                "h4":     bool(state.get("h4_broken")),
            }
        return result
    except Exception:
        return {}


def gws_label(state: dict | None) -> str:
    if not state:
        return "❓"
    d, w, h4 = state.get("daily"), state.get("weekly"), state.get("h4")
    if d and w and h4:
        return "🟢"
    if d and w:
        return "🟡"
    return "🔴"


def gws_min_yellow(state: dict | None) -> bool:
    """True wenn mindestens Daily + Weekly gebrochen."""
    if not state:
        return False
    return bool(state.get("daily") and state.get("weekly"))

# ── Fundamentaldaten laden ────────────────────────────────────────────────────

def load_fundamentals() -> dict:
    try:
        raw = json.loads(FUNDAMENTALS_PATH.read_text(encoding="utf-8"))
        return raw.get("tickers", {})
    except Exception:
        return {}


def _float(val, fallback=None):
    try:
        v = float(val)
        return v if v == v else fallback  # NaN-Check
    except (TypeError, ValueError):
        return fallback

# ── RS-Daten laden ────────────────────────────────────────────────────────────

def load_rs_data() -> list[dict]:
    """Alle Ticker aus allen RS-Dateien; doppelte Ticker werden deduped."""
    entries = {}
    for source, path in RS_FILES.items():
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for e in data.get("data", []):
                ticker = e.get("ticker", "").upper()
                if ticker and ticker not in entries:
                    entries[ticker] = {**e, "_source": source}
        except Exception as ex:
            print(f"  RS-Datei {path} Fehler: {ex}")
    return list(entries.values())

# ── Sektor-Median für Forward-PE ─────────────────────────────────────────────

def build_sector_pe_median(fund: dict) -> dict:
    from statistics import median
    sector_pes: dict[str, list] = {}
    for ticker, f in fund.items():
        sector = f.get("sector", "N/A")
        pe = _float(f.get("forwardPE"))
        if sector and sector != "N/A" and pe and 3 < pe < 200:
            sector_pes.setdefault(sector, []).append(pe)
    return {s: median(pes) for s, pes in sector_pes.items() if len(pes) >= 3}

# ── Post-Earnings-Kandidaten aus check_earnings-Logik (leichtgewichtig) ───────

def get_recent_earnings_candidates(rs_entries: list[dict], lookback_days: int = 21) -> list[dict]:
    """
    Prüft Earnings-Daten für die High-Score-Aktien (Top 300 nach RS) der letzten
    lookback_days Tage. Füllt Profil 3 mit den stärksten Setups.
    """
    today = date.today()
    since = today - timedelta(days=lookback_days)

    top_candidates = sorted(rs_entries, key=lambda e: e.get("score") or 0, reverse=True)[:300]
    results = []

    print(f"  Prüfe {len(top_candidates)} Top-Ticker auf Earnings-Beats (letzte {lookback_days} Tage)...")

    for entry in top_candidates:
        ticker = entry.get("ticker", "")
        score  = entry.get("score", 0)
        source = entry.get("_source", "?")

        try:
            tk = yf.Ticker(ticker)
            try:
                ed = tk.get_earnings_dates(limit=20)
            except Exception:
                ed = tk.earnings_dates
            if ed is None or ed.empty:
                continue

            ed = ed.copy()
            ed.index = pd.to_datetime(ed.index).normalize().tz_localize(None)

            window_mask = (ed.index >= pd.Timestamp(since)) & (ed.index <= pd.Timestamp(today))
            hits = ed[window_mask]
            if hits.empty:
                continue

            row = hits.iloc[0]
            eps_surprise = _float(row.get("Surprise(%)"))
            eps_est      = _float(row.get("EPS Estimate"))
            eps_actual   = _float(row.get("Reported EPS"))

            if eps_surprise is None and eps_est and eps_actual and eps_est != 0:
                eps_surprise = (eps_actual - eps_est) / abs(eps_est) * 100

            if not eps_surprise or eps_surprise < 10.0:
                continue

            earnings_date = str(hits.index[0].date())
            days_since    = (today - hits.index[0].date()).days

            # Kursreaktion am Earnings-Tag
            ohlcv = entry.get("ohlcv", [])
            closes = [(c["d"][:10], c["c"]) for c in ohlcv if c.get("c")]
            jump_pct = None
            for i in range(len(closes) - 1, 0, -1):
                if closes[i][0] == earnings_date:
                    jump_pct = closes[i][1] / closes[i-1][1] - 1
                    break

            # Persistenz: hält der Kurs noch über dem Earnings-Close?
            persistence_flag = None
            if jump_pct is not None and closes:
                earnings_close_price = None
                for d, c in closes:
                    if d == earnings_date:
                        earnings_close_price = c
                        break
                if earnings_close_price and closes[-1][1] > earnings_close_price:
                    persistence_flag = True
                elif earnings_close_price:
                    persistence_flag = False

            # Revenue Beat (Quartalsumsatz vs. Vorjahr ≥ 0)
            rev_yoy = None
            try:
                fins = tk.quarterly_financials
                if fins is not None and not fins.empty:
                    for lbl in ("Total Revenue", "Revenue", "Operating Revenue"):
                        if lbl in fins.index:
                            row_r = fins.loc[lbl]
                            if len(row_r) >= 5:
                                r0, r1 = row_r.iloc[0], row_r.iloc[4]
                                if pd.notna(r0) and pd.notna(r1) and r1 != 0:
                                    rev_yoy = float((r0 - r1) / abs(r1))
                            break
            except Exception:
                pass

            results.append({
                "ticker":           ticker,
                "source":           source,
                "rs_score":         score,
                "earnings_date":    earnings_date,
                "days_since":       days_since,
                "eps_surprise_pct": round(eps_surprise, 1),
                "eps_estimate":     eps_est,
                "eps_actual":       eps_actual,
                "jump_pct":         round(jump_pct * 100, 1) if jump_pct is not None else None,
                "revenue_yoy_pct":  round(rev_yoy * 100, 1) if rev_yoy is not None else None,
                "revenue_beat":     rev_yoy is not None and rev_yoy >= 0,
                "persistence_flag": persistence_flag,
                "guidance_raise":   None,  # Nicht automatisch verfügbar; LLM prüft
            })

            if len(results) >= 7:
                break

        except Exception as ex:
            print(f"    Earnings {ticker}: {ex}")
            continue

    results.sort(key=lambda x: x.get("eps_surprise_pct") or 0, reverse=True)
    return results[:7]

# ── Profil 1: Early Tech Alpha ─────────────────────────────────────────────────

def screen_profile1(fund: dict, rs_entries: list[dict], gws: dict) -> list[dict]:
    results = []
    for entry in rs_entries:
        ticker = entry.get("ticker", "").upper()
        score  = entry.get("score", 0) or 0
        source = entry.get("_source", "?")
        f = fund.get(ticker) or fund.get(ticker.split(".")[0])
        if not f:
            continue

        sector     = f.get("sector", "N/A")
        market_cap = _float(f.get("marketCap"))
        rev_growth = _float(f.get("revenueGrowth"))
        gross_m    = _float(f.get("grossMargins"))

        if sector not in PROFILE1_SECTORS:
            continue
        if market_cap is None or not (PROFILE1_MIN_MARKET_CAP <= market_cap <= PROFILE1_MAX_MARKET_CAP):
            continue
        if rev_growth is None or rev_growth < PROFILE1_MIN_REV_GROWTH:
            continue
        if gross_m is None or gross_m < PROFILE1_MIN_GROSS_MARGIN:
            continue
        if score < PROFILE1_MIN_RS:
            continue
        if not gws_min_yellow(gws.get(ticker)):
            continue

        results.append({
            "ticker":       ticker,
            "name":         f.get("shortName", ticker),
            "source":       source,
            "rs_score":     round(score, 1),
            "gws":          gws_label(gws.get(ticker)),
            "sector":       sector,
            "industry":     f.get("industry", "N/A"),
            "market_cap_b": round(market_cap / 1e9, 1) if market_cap else None,
            "rev_growth":   round(rev_growth * 100, 1),
            "gross_margin": round(gross_m * 100, 1),
            "forward_pe":   _float(f.get("forwardPE")),
            "roe":          round(_float(f.get("returnOnEquity"), 0) * 100, 1),
            "roic":         round(_float(f.get("returnOnInvestedCapital"), 0) * 100, 1),
            "de_ratio":     _float(f.get("debtToEquity")),
            "fcf_positive": (_float(f.get("freeCashflow")) or 0) > 0,
        })

    results.sort(key=lambda x: x["rs_score"], reverse=True)
    return results[:PROFILE1_MAX_RESULTS]

# ── Profil 2: Hidden Champions ─────────────────────────────────────────────────

def screen_profile2(fund: dict, rs_entries: list[dict], gws: dict,
                    sector_pe_median: dict) -> list[dict]:
    results = []
    for entry in rs_entries:
        ticker = entry.get("ticker", "").upper()
        score  = entry.get("score", 0) or 0
        source = entry.get("_source", "?")
        f = fund.get(ticker) or fund.get(ticker.split(".")[0])
        if not f:
            continue

        roic       = _float(f.get("returnOnInvestedCapital"))
        roe        = _float(f.get("returnOnEquity"))
        quality    = roic if roic is not None else roe
        de_ratio   = _float(f.get("debtToEquity"))
        fcf        = _float(f.get("freeCashflow"))
        rev_growth = _float(f.get("revenueGrowth"))
        forward_pe = _float(f.get("forwardPE"))
        analyst_n  = _float(f.get("numberOfAnalystOpinions"))
        sector     = f.get("sector", "N/A")

        if quality is None or quality < PROFILE2_MIN_ROIC:
            continue
        if de_ratio is None or de_ratio > PROFILE2_MAX_DE:
            continue
        if fcf is None or fcf <= 0:
            continue
        if rev_growth is None or not (PROFILE2_MIN_REV_GROWTH <= rev_growth <= PROFILE2_MAX_REV_GROWTH):
            continue
        if analyst_n is not None and analyst_n > PROFILE2_MAX_ANALYST_CNT:
            continue
        if score < PROFILE2_MIN_RS:
            continue

        # Forward PE unter Sektor-Median (oder kein PE = akzeptabel)
        pe_below_median = True
        if forward_pe and sector in sector_pe_median:
            pe_below_median = forward_pe < sector_pe_median[sector] * 1.1

        results.append({
            "ticker":          ticker,
            "name":            f.get("shortName", ticker),
            "source":          source,
            "rs_score":        round(score, 1),
            "gws":             gws_label(gws.get(ticker)),
            "sector":          sector,
            "industry":        f.get("industry", "N/A"),
            "market_cap_b":    round(_float(f.get("marketCap"), 0) / 1e9, 1),
            "roic":            round(quality * 100, 1),
            "de_ratio":        round(de_ratio, 2),
            "rev_growth":      round(rev_growth * 100, 1),
            "forward_pe":      forward_pe,
            "sector_pe_med":   round(sector_pe_median.get(sector, 0), 1),
            "pe_below_median": pe_below_median,
            "analyst_count":   int(analyst_n) if analyst_n is not None else None,
        })

    results.sort(key=lambda x: x["roic"], reverse=True)
    return results[:PROFILE2_MAX_RESULTS]

# ── Hauptprogramm ──────────────────────────────────────────────────────────────

def main():
    print(f"check_hidden_alpha.py – {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    print("\n[1/5] Lade RS-Daten...")
    rs_entries = load_rs_data()
    print(f"  {len(rs_entries)} Ticker geladen")

    print("\n[2/5] Lade Fundamentaldaten...")
    fund = load_fundamentals()
    print(f"  {len(fund)} Ticker in fundamentals.json")

    print("\n[3/5] Lade GWS-Ampeln...")
    gws = load_gws_state()
    print(f"  {len(gws)} Ticker-States geladen")

    print("\n[4/5] Baue Sektor-PE-Mediane...")
    sector_pe_median = build_sector_pe_median(fund)
    print(f"  {len(sector_pe_median)} Sektoren mit Median-PE")

    print("\n[5/5] Starte Screening...")

    print("  → Profil 1: Early Tech Alpha")
    p1 = screen_profile1(fund, rs_entries, gws)
    print(f"     {len(p1)} Kandidaten")

    print("  → Profil 2: Hidden Champions")
    p2 = screen_profile2(fund, rs_entries, gws, sector_pe_median)
    print(f"     {len(p2)} Kandidaten")

    print("  → Profil 3: Post-Earnings (Live-Prüfung)")
    p3 = get_recent_earnings_candidates(rs_entries)
    print(f"     {len(p3)} Kandidaten")

    output = {
        "generated_at":            datetime.utcnow().isoformat() + "Z",
        "universe_size":           len(rs_entries),
        "profile1_early_tech":     p1,
        "profile2_hidden_champion": p2,
        "profile3_earnings_breakout": p3,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EARNINGS_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n✅ alpha_candidates.json geschrieben:")
    print(f"   Profil 1: {len(p1)} | Profil 2: {len(p2)} | Profil 3: {len(p3)}")

    # Kompakter Telegram-Ping
    tg_token   = os.environ.get("TELEGRAM_TOKEN", "")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if tg_token and tg_chat_id and (p1 or p2 or p3):
        top3 = ([x["ticker"] for x in p1[:2]] +
                [x["ticker"] for x in p2[:1]] +
                [x["ticker"] for x in p3[:2]])
        msg = (
            f"🔍 <b>Alpha-Screener {datetime.now().strftime('%d.%m.')}</b>\n"
            f"📈 Early Tech: {len(p1)} | 🏆 Hidden: {len(p2)} | "
            f"⚡ Earnings: {len(p3)}\n"
            f"Top: {' · '.join(top3[:5])}"
        )
        try:
            import urllib.request
            url  = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            data = json.dumps({"chat_id": tg_chat_id, "text": msg, "parse_mode": "HTML"}).encode()
            req  = urllib.request.Request(url, data=data,
                                          headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10):
                pass
            print("  Telegram-Ping gesendet")
        except Exception as e:
            print(f"  Telegram-Fehler: {e}")


if __name__ == "__main__":
    main()
