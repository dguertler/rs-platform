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


def build_hc_reason(f: dict, roic_or_roe: float, de_ratio: float,
                    fcf: float, rev_growth: float, analyst_n, score: float) -> str:
    """Einzeiliger Text: warum dieser Ticker als Hidden Champion gilt."""
    parts = []
    roic = f.get("returnOnInvestedCapital")
    roe  = f.get("returnOnEquity")
    if roic is not None:
        parts.append(f"ROIC {roic * 100:.0f}%")
    elif roe is not None:
        parts.append(f"ROE {roe * 100:.0f}%")
    if de_ratio is not None:
        parts.append(f"D/E {de_ratio:.1f}")
    if analyst_n is not None:
        parts.append(f"nur {int(analyst_n)} Analysten")
    else:
        parts.append("keine Coverage")
    if fcf is not None:
        if abs(fcf) >= 1e9:
            parts.append(f"FCF +${fcf / 1e9:.1f}B")
        else:
            parts.append(f"FCF +${fcf / 1e6:.0f}M")
    if rev_growth is not None:
        parts.append(f"RevWachstum +{rev_growth * 100:.0f}%")
    parts.append(f"RS {round(score)}")
    return " · ".join(parts)


def gws_state_for_item(ticker: str, gws: dict) -> dict | None:
    state = gws.get(ticker)
    if not state:
        return None
    return {
        "weekly": {"broken": bool(state.get("weekly"))},
        "daily":  {"broken": bool(state.get("daily"))},
        "h4":     {"broken4h": bool(state.get("h4"))},
    }

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

def get_recent_earnings_candidates(rs_entries: list[dict], fund: dict = None, gws: dict = None, lookback_days: int = 21) -> list[dict]:
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

            _f = (fund or {}).get(ticker) or (fund or {}).get(ticker.split(".")[0]) or {}
            results.append({
                "ticker":           ticker,
                "score":            score,
                "gws":              gws_state_for_item(ticker, gws or {}),
                "source":           source,
                "fundamentals": {
                    "shortName":     _f.get("shortName", ticker),
                    "sector":        _f.get("sector"),
                    "industry":      _f.get("industry"),
                    "profitMargins": _f.get("profitMargins"),
                },
                "earnings_date":    earnings_date,
                "days_since":       days_since,
                "eps_surprise_pct": round(eps_surprise, 1),
                "eps_estimate":     eps_est,
                "eps_actual":       eps_actual,
                "jump_pct":         round(jump_pct * 100, 1) if jump_pct is not None else None,
                "revenue_yoy_pct":  rev_yoy,
                "revenue_beat":     rev_yoy is not None and rev_yoy >= 0,
                "persistence_flag": persistence_flag,
                "guidance_raise":   None,
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
            "score":        round(score, 1),
            "gws":          gws_state_for_item(ticker, gws),
            "source":       source,
            "fundamentals": {
                "shortName":               f.get("shortName", ticker),
                "sector":                  sector,
                "industry":                f.get("industry", "N/A"),
                "marketCap":               market_cap,
                "revenueGrowth":           rev_growth,
                "grossMargins":            gross_m,
                "forwardPE":               _float(f.get("forwardPE")),
                "returnOnEquity":          _float(f.get("returnOnEquity")),
                "returnOnInvestedCapital": _float(f.get("returnOnInvestedCapital")),
                "debtToEquity":            _float(f.get("debtToEquity")),
                "freeCashflow":            _float(f.get("freeCashflow")),
            },
        })

    results.sort(key=lambda x: x["score"], reverse=True)
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

        reason = build_hc_reason(f, quality, de_ratio, fcf, rev_growth, analyst_n, score)
        results.append({
            "ticker":                   ticker,
            "score":                    round(score, 1),
            "gws":                      gws_state_for_item(ticker, gws),
            "source":                   source,
            "pe_below_median":          pe_below_median,
            "sector_pe_med":            round(sector_pe_median.get(sector, 0), 1),
            "hidden_champion_reason":   reason,
            "fundamentals": {
                "shortName":               f.get("shortName", ticker),
                "sector":                  sector,
                "industry":               f.get("industry", "N/A"),
                "marketCap":              _float(f.get("marketCap")),
                "returnOnInvestedCapital": roic if roic is not None else roe,
                "returnOnEquity":          roe,
                "debtToEquity":            de_ratio,
                "freeCashflow":            fcf,
                "revenueGrowth":           rev_growth,
                "forwardPE":               forward_pe,
                "numberOfAnalystOpinions": int(analyst_n) if analyst_n is not None else None,
                "profitMargins":           _float(f.get("profitMargins")),
            },
        })

    results.sort(key=lambda x: (x["fundamentals"].get("returnOnInvestedCapital") or 0), reverse=True)
    return results[:PROFILE2_MAX_RESULTS]

# ── E-Mail-Benachrichtigung ───────────────────────────────────────────────────

def send_alpha_email(p1, p2, p3, smtp_host, smtp_port, smtp_user, smtp_pass, to_addr):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    if not all([smtp_host, smtp_port, smtp_user, smtp_pass, to_addr]):
        print("  SMTP nicht konfiguriert – E-Mail übersprungen")
        return

    subject = (f"Alpha-Screener {datetime.now().strftime('%d.%m.%Y')} – "
               f"{len(p1)} Early Tech · {len(p2)} Hidden · {len(p3)} Earnings")

    lines = [
        f"Alpha-Screening – {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC\n",
        f"🚀 Profil 1 – Early Tech Alpha: {len(p1)} Kandidaten",
    ]
    for item in p1:
        f = item.get("fundamentals", {})
        lines.append(f"  • {item['ticker']} ({f.get('shortName', '')})"
                     f"  RS={round(item.get('score', 0))}"
                     f"  RevGrowth={round((f.get('revenueGrowth') or 0) * 100, 1)}%"
                     f"  Marge={round((f.get('grossMargins') or 0) * 100, 1)}%")
    lines.append(f"\n💎 Profil 2 – Hidden Champions: {len(p2)} Kandidaten")
    for item in p2:
        f = item.get("fundamentals", {})
        lines.append(f"  • {item['ticker']} ({f.get('shortName', '')})"
                     f"  RS={round(item.get('score', 0))}"
                     f"  ROIC={round((f.get('returnOnInvestedCapital') or 0) * 100, 1)}%"
                     f"  D/E={f.get('debtToEquity', '–')}")
    lines.append(f"\n⚡ Profil 3 – Post-Earnings Breakout: {len(p3)} Kandidaten")
    for item in p3:
        f = item.get("fundamentals", {})
        lines.append(f"  • {item['ticker']} ({f.get('shortName', '')})"
                     f"  EPS-Beat={item.get('eps_surprise_pct', 0)}%"
                     f"  Kurssprung={item.get('jump_pct') or '–'}%"
                     f"  ({item.get('earnings_date', '')})")

    body = "\n".join(lines)
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = to_addr
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_addr], msg.as_string())
        print(f"  E-Mail gesendet an {to_addr}")
    except Exception as e:
        print(f"  E-Mail-Fehler: {e}")


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
    p3 = get_recent_earnings_candidates(rs_entries, fund, gws)
    print(f"     {len(p3)} Kandidaten")

    output = {
        "updated_at":    datetime.utcnow().isoformat() + "Z",
        "universe_size": len(rs_entries),
        "profiles": {
            "early_tech":       p1,
            "hidden_champions": p2,
            "post_earnings":    p3,
        },
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EARNINGS_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n✅ alpha_candidates.json geschrieben:")
    print(f"   Profil 1: {len(p1)} | Profil 2: {len(p2)} | Profil 3: {len(p3)}")

    if p1 or p2 or p3:
        smtp_host = os.environ.get("SMTP_HOST", "")
        smtp_port = os.environ.get("SMTP_PORT", "587")
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASS", "")
        to_addr   = os.environ.get("ALERT_EMAIL_TO", "")
        send_alpha_email(p1, p2, p3, smtp_host, smtp_port, smtp_user, smtp_pass, to_addr)


if __name__ == "__main__":
    main()
