"""
index_membership.py — historische Indexzusammensetzung für das rückwirkende
Top-20-Ranking (rs_colab.py für den NASDAQ-100, sp500_*.py für den S&P 500).

Die Dateien unter data/backtest_history/*_membership.json halten je Ticker die
Mitgliedsintervalle ([von, bis], bis = None → noch Mitglied). Ranking-Regel:
an jedem Tag werden nur die Aktien gerankt, die an diesem Tag im Index waren.
"""
import json
from datetime import date

from backtest_history.symbols import candidates

NDX_FILE = "data/backtest_history/ndx_membership.json"
SP500_FILE = "data/backtest_history/sp500_membership.json"
WATCHLIST_FILE = "data/watchlist.json"
MIN_OFFICIAL = 490          # offizielle S&P-Liste nur nutzen, wenn vollständig


def load_intervals(path):
    """{Yahoo-Symbol: [[von, bis], ...]} oder None, wenn die Datei fehlt.

    Historische Symbole werden auf das heutige Yahoo-Symbol abgebildet
    (FB → META), damit Kursreihe und Mitgliedschaft zusammenpassen.
    """
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError) as e:
        print(f"Indexzusammensetzung {path} nicht lesbar ({e}) – Ranking ohne Mitgliedsprüfung")
        return None
    out = {}
    for ticker, ivs in payload.get("intervals", {}).items():
        cands = candidates(ticker)
        if cands:
            out.setdefault(cands[0], []).extend(ivs)
    return out


def current_members(intervals):
    return sorted(t for t, ivs in intervals.items() if any(end is None for _, end in ivs))


def apply_official(intervals, official, as_of=None):
    """Heutige offizielle Liste (FMP/Wikipedia) als letzte Änderung einspielen.

    Die historische Datei wird nur in Abständen gepflegt; neue Mitglieder seit
    ihrer letzten Änderung beginnen ab as_of, ausgeschiedene enden an as_of.
    Ohne vollständige offizielle Liste bleibt die Datei unverändert.
    """
    if not official or len(official) < MIN_OFFICIAL:
        return intervals
    as_of = as_of or date.today().isoformat()
    official = set(official)
    out = {t: [list(iv) for iv in ivs] for t, ivs in intervals.items()}
    for t, ivs in out.items():
        if t not in official and ivs and ivs[-1][1] is None:
            ivs[-1][1] = as_of
    for t in official:
        ivs = out.setdefault(t, [])
        if not ivs or ivs[-1][1] is not None:
            ivs.append([as_of, None])
    return out


def active_in_window(intervals, window_start):
    """Alle Ticker, die ab window_start irgendwann Mitglied waren."""
    return sorted(t for t, ivs in intervals.items()
                  if any(end is None or end > window_start for _, end in ivs))


def watchlist_extras(exclude):
    """Watchlist-Titel ohne Indexzugehörigkeit (z. B. NTRA): sie brauchen Kursdaten
    für die Verkaufssignale (check_exits.py), werden aber nicht gerankt."""
    try:
        with open(WATCHLIST_FILE, encoding="utf-8") as f:
            tickers = json.load(f).get("tickers", [])
    except (OSError, ValueError):
        return []
    return sorted(t for t in tickers if t not in exclude)


def point_in_time_top20(close, benchmark, intervals):
    """Top-20-Historie und Vorwochen-Rang (Rang ~5 Handelstage vor Ende).

    close: Schlusskurse (Zeilen = Handelstage, Spalten = Symbole inkl. Benchmark);
    gerankt wird je Tag nur, wer laut intervals an diesem Tag Mitglied war.
    """
    from rs_core import membership_mask, rank_by_day

    tickers = [t for t in close.columns if t != benchmark and t in intervals]
    mask = membership_mask(close.index, tickers, intervals)
    history, prev_rank = {}, {}
    prev_i = max(0, len(close) - 6)
    for i, day, scores in rank_by_day(close, benchmark, tickers, mask):
        history[day] = [t for t, _ in scores[:20]]
        if i == prev_i:
            prev_rank = {t: r + 1 for r, (t, _) in enumerate(scores)}
    return history, prev_rank
