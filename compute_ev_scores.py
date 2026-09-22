"""
compute_ev_scores.py — Automatisierter EV-Screening-Score (kein LLM)
=====================================================================
Grobe, rein mechanische Orientierung analog zur Claude-Analyse-Methodik
(Peer-Multiple-Verankerung + Reverse-Engineering), aber ohne Geschäftsmodell-
oder Risikoprüfung. Kein Ersatz für die 11-Abschnitte-Analyse — nur ein
Screening-Signal für Ticker ohne manuelle Analyse.

Peer-Gruppe: alle Ticker aus data/fundamentals.json mit gleichem
sector+industry (Fallback: nur sector, wenn <3 Peers). Bear/Bull-Multiple
aus dem 25./75. Perzentil des Peer-Forward-KGV, Base aus dem eigenen
aktuellen Forward-KGV. Gewichtung 25/50/25 wie in den manuellen Analysen.

Schreibt data/ev_scores.json für alle drei Indizes (NASDAQ-100, S&P 500,
Smallcap) — nach erfolgreichem NASDAQ-100-Pilot und Sanity-Check
(MPWR/ODFL/CI) freigegeben.
"""

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

FUNDAMENTALS_PATH = Path("data/fundamentals.json")
OUTPUT_PATH = Path("data/ev_scores.json")

MIN_PEERS = 3
WEIGHTS = (0.25, 0.50, 0.25)  # Bear, Base, Bull


def _num(v):
    """Gibt v als float zurück, oder None wenn nicht numerisch (N/A, UNGÜLTIG(...), fehlend)."""
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _load_universe() -> dict:
    with open(FUNDAMENTALS_PATH, encoding="utf-8") as f:
        return json.load(f)["tickers"]


RS_FILES = ["data/rs_full.json", "data/rs_sp500.json", "data/rs_smallcap.json"]


def _load_target_tickers() -> list:
    tickers = []
    seen = set()
    for path in RS_FILES:
        p = Path(path)
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as f:
            for e in json.load(f)["data"]:
                t = e["ticker"]
                if t not in seen:
                    seen.add(t)
                    tickers.append(t)
    return tickers


def _build_groups(universe: dict) -> tuple:
    industry_groups, sector_groups = {}, {}
    for ticker, fund in universe.items():
        fpe = _num(fund.get("forwardPE"))
        if fpe is None or fpe <= 0:
            continue
        sector, industry = fund.get("sector"), fund.get("industry")
        industry_groups.setdefault((sector, industry), []).append((ticker, fpe))
        sector_groups.setdefault(sector, []).append((ticker, fpe))
    return industry_groups, sector_groups


def _peer_percentiles(peers: list, exclude_ticker: str) -> tuple:
    """Gibt (p25, p75, n) der Forward-KGVs der Peers zurück, exclude_ticker ausgeschlossen."""
    values = sorted(fpe for t, fpe in peers if t != exclude_ticker)
    n = len(values)
    if n < MIN_PEERS:
        return None, None, n
    qs = statistics.quantiles(values, n=4, method="inclusive")
    return qs[0], qs[2], n  # p25, p75


def compute_score(ticker: str, universe: dict, industry_groups: dict, sector_groups: dict) -> dict | None:
    fund = universe.get(ticker)
    if not fund:
        return None

    price = _num(fund.get("currentPrice"))
    trailing_eps = _num(fund.get("trailingEps"))
    forward_eps = _num(fund.get("forwardEps"))
    own_fpe = _num(fund.get("forwardPE"))

    if not price or price <= 0 or not trailing_eps or trailing_eps <= 0 or not forward_eps or forward_eps <= 0:
        return {"available": False, "reason": "EPS negativ/fehlend — P/E-Methodik nicht anwendbar"}

    sector, industry = fund.get("sector"), fund.get("industry")
    peer_source = "industry"
    p25, p75, n = _peer_percentiles(industry_groups.get((sector, industry), []), ticker)
    if p25 is None:
        peer_source = "sector"
        p25, p75, n = _peer_percentiles(sector_groups.get(sector, []), ticker)
    if p25 is None:
        return {"available": False, "reason": f"Zu wenige Peers ({n}) auch auf Sektor-Ebene"}

    base_pe = own_fpe if (own_fpe and own_fpe > 0) else (p25 + p75) / 2
    # Bear/Bull dürfen die Base-Bandbreite nie unterschreiten/überschreiten (z.B. wenn das eigene
    # Multiple bereits über dem 75. Perzentil der Peers liegt) — sonst Bull < Base rechnerisch möglich.
    bear_pe = min(p25, base_pe)
    bull_pe = max(p75, base_pe)

    bear = trailing_eps * bear_pe
    base = forward_eps * base_pe
    bull = forward_eps * bull_pe

    ev = WEIGHTS[0] * bear + WEIGHTS[1] * base + WEIGHTS[2] * bull
    upside_pct = (ev / price - 1) * 100

    return {
        "available": True,
        "price": round(price, 2),
        "bear": round(bear, 2),
        "base": round(base, 2),
        "bull": round(bull, 2),
        "ev": round(ev, 2),
        "upside_pct": round(upside_pct, 1),
        "peer_source": peer_source,
        "peer_count": n,
        "peer_bear_pe": round(bear_pe, 1),
        "peer_bull_pe": round(bull_pe, 1),
        "own_forward_pe": round(own_fpe, 1) if own_fpe else None,
    }


def main():
    universe = _load_universe()
    targets = _load_target_tickers()
    industry_groups, sector_groups = _build_groups(universe)

    scores = {}
    for ticker in targets:
        result = compute_score(ticker, universe, industry_groups, sector_groups)
        if result:
            scores[ticker] = result

    output = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "method": "peer-multiple (25./75. Perzentil sector+industry) + reverse-engineering, 25/50/25-Gewichtung",
        "universe": "nasdaq100+sp500+smallcap",
        "count": len(scores),
        "scores": scores,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Gespeichert: {OUTPUT_PATH} ({len(scores)} Ticker)")


if __name__ == "__main__":
    main()
