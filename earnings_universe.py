"""
earnings_universe.py — Breites US-/Europa-Ticker-Universum für check_earnings_global.py
==========================================================================================
Liefert Ticker-Listen OHNE historische Kursdaten abzurufen — reine Symbol-Listen
aus öffentlichen, kostenlosen Quellen:

  US:     NASDAQ Trader Symbol-Directory (nasdaqlisted.txt + otherlisted.txt)
          → mehrere Tausend Ticker (NASDAQ, NYSE, NYSE American, Cboe BZX etc.)
  Europa: Wikipedia-Indexlisten (DAX 40, CAC 40, FTSE 100, IBEX 35, FTSE MIB,
          SMI, AEX) mit Yahoo-Finance-Suffix je Börse, Fallback auf hartcodierte
          Listen falls Wikipedia nicht erreichbar/parsbar ist.

Test-Issues und ETFs werden beim US-Universum ausgefiltert (Earnings-Überraschung
ist für Fonds nicht sinnvoll).
"""

import urllib.request
from fetch_tickers import _wikipedia_table

_HEADERS = {"User-Agent": "rs-platform/1.0 (+https://github.com/dguertler/rs-platform)"}

NASDAQ_TRADER_URLS = [
    "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
]


def _fetch_text(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  US-Universum: Fehler bei {url} — {e}")
        return None


def fetch_us_universe() -> list[str]:
    """NASDAQ Trader Symbol-Directory: alle NASDAQ/NYSE/NYSE American/Cboe-Ticker,
    ohne ETFs und Test-Issues. Pipe-getrennte Textdateien mit Header- und
    Footer-Zeile ('File Creation Time: ...')."""
    tickers = set()

    txt = _fetch_text(NASDAQ_TRADER_URLS[0])
    if txt:
        lines = txt.strip().splitlines()
        for line in lines[1:]:
            if line.startswith("File Creation Time"):
                continue
            parts = line.split("|")
            if len(parts) < 7:
                continue
            symbol, _name, _market, test_issue, _fin_status, _lot, etf = parts[:7]
            if test_issue == "Y" or etf == "Y":
                continue
            if symbol and symbol.replace("-", "").replace(".", "").isalnum():
                tickers.add(symbol.strip())
        print(f"  US: nasdaqlisted.txt — {len(tickers)} Ticker nach Filter")
    else:
        print("  US: nasdaqlisted.txt nicht verfügbar")

    txt = _fetch_text(NASDAQ_TRADER_URLS[1])
    if txt:
        before = len(tickers)
        lines = txt.strip().splitlines()
        for line in lines[1:]:
            if line.startswith("File Creation Time"):
                continue
            parts = line.split("|")
            if len(parts) < 7:
                continue
            act_symbol, _name, _exchange, _cqs, etf, _lot, test_issue = parts[:7]
            if test_issue == "Y" or etf == "Y":
                continue
            if act_symbol and act_symbol.replace("-", "").replace(".", "").isalnum():
                tickers.add(act_symbol.strip())
        print(f"  US: otherlisted.txt — +{len(tickers) - before} zusätzliche Ticker")
    else:
        print("  US: otherlisted.txt nicht verfügbar")

    return sorted(tickers)


# ── Europa: Wikipedia-Indexlisten + Fallback ─────────────────────────────────

_CAC40_FALLBACK = [
    "AI", "AIR", "ALO", "MT", "ATO", "CS", "BNP", "EN", "CAP", "CA",
    "ACA", "BN", "DSY", "EDEN", "ENGI", "EL", "ERF", "RMS", "KER", "OR",
    "LR", "MC", "ML", "ORA", "RI", "PUB", "RNO", "SAF", "SGO", "SAN",
    "SU", "GLE", "STLAP", "STM", "TEP", "HO", "TTE", "URW", "VIE", "DG",
    "VIV",
]
_FTSE100_FALLBACK = [
    "AAL", "ANTO", "AHT", "ABF", "AZN", "AUTO", "AV", "BME", "BA", "BARC",
    "BDEV", "BEZ", "BKG", "BP", "BATS", "BLND", "BT-A", "BNZL", "BRBY", "CNA",
    "CCH", "CPG", "CTEC", "CRDA", "DCC", "DGE", "DPLM", "EZJ", "ENT", "EXPN",
    "FCIT", "FRAS", "FRES", "GAW", "GLEN", "GSK", "HLN", "HLMA", "HIK", "HSBA",
    "HWDN", "IHG", "IMI", "IMB", "INF", "ICG", "IAG", "ITRK", "JD", "KGF",
    "LAND", "LGEN", "LLOY", "LMP", "LSEG", "MNG", "MKS", "MRO", "MNDI", "NG",
    "NWG", "NXT", "PSON", "PSH", "PSN", "PHNX", "PRU", "RKT", "REL", "RTO",
    "RMV", "RIO", "RR", "SGE", "SBRY", "SDR", "SMT", "SGRO", "SVT", "SHEL",
    "SN", "SMDS", "SMIN", "SKG", "SPX", "SSE", "STAN", "STJ", "TW", "TSCO",
    "ULVR", "UTG", "UU", "VOD", "WEIR", "WTB", "WPP",
]
_IBEX35_FALLBACK = [
    "ACS", "ACX", "AENA", "AMS", "ANA", "ANE", "BBVA", "BKT", "CABK", "CLNX",
    "COL", "ELE", "ENG", "FDR", "FER", "GRF", "IAG", "IBE", "IDR", "ITX",
    "LOG", "MAP", "MRL", "MTS", "NTGY", "PUIG", "RED", "REP", "ROVI", "SAB",
    "SAN", "SCYR", "SLR", "TEF", "UNI",
]
_FTSEMIB_FALLBACK = [
    "A2A", "AMP", "AZM", "BAMI", "BGN", "BMED", "BPE", "BPSO", "BZU", "CPR",
    "DIA", "ENEL", "ENI", "ERG", "FBK", "G", "HER", "IF", "INW", "ISP",
    "IVG", "LDO", "MB", "MONC", "NEXI", "PIRC", "PRY", "PST", "RACE", "REC",
    "SPM", "SRG", "STLAM", "STMMI", "TEN", "TIT", "TRN", "UCG", "UNI",
]
_SMI_FALLBACK = [
    "ABBN", "ALC", "CFR", "GEBN", "GIVN", "HOLN", "KNIN", "LOGN", "LONN", "NESN",
    "NOVN", "PGHN", "ROG", "SGSN", "SIKA", "SLHN", "SCMN", "SOON", "SREN", "UBSG",
    "ZURN",
]
_AEX_FALLBACK = [
    "ADYEN", "AD", "AGN", "AKZA", "MT", "ASM", "ASML", "ASRNL", "BESI", "DSFIR",
    "GLPG", "HEIA", "IMCD", "INGA", "KPN", "NN", "PHIA", "PRX", "RAND", "REN",
    "SHELL", "UMG", "UNA", "WKL",
]

EU_INDICES = [
    ("CAC 40",   "https://en.wikipedia.org/wiki/CAC_40",              ".PA", _CAC40_FALLBACK),
    ("FTSE 100", "https://en.wikipedia.org/wiki/FTSE_100_Index",      ".L",  _FTSE100_FALLBACK),
    ("IBEX 35",  "https://en.wikipedia.org/wiki/IBEX_35",             ".MC", _IBEX35_FALLBACK),
    ("FTSE MIB", "https://en.wikipedia.org/wiki/FTSE_MIB",            ".MI", _FTSEMIB_FALLBACK),
    ("SMI",      "https://en.wikipedia.org/wiki/Swiss_Market_Index",  ".SW", _SMI_FALLBACK),
    ("AEX",      "https://en.wikipedia.org/wiki/AEX_index",           ".AS", _AEX_FALLBACK),
]


def _clean_eu(ts: list[str], suffix: str) -> list[str]:
    result = []
    for x in ts:
        x = x.strip().upper()
        if not x or len(x) > 12 or " " in x:
            continue
        if not x.endswith(suffix):
            x = x + suffix
        result.append(x)
    return result


def fetch_europe_universe() -> list[str]:
    """DAX 40 (über fetch_tickers.fetch_dax40) + sechs weitere große europäische
    Indizes über Wikipedia mit Fallback-Listen. Kein Anspruch auf lückenlose
    Abdeckung aller europäischen Börsen — deckt die liquidesten Blue-Chips ab."""
    from fetch_tickers import fetch_dax40

    tickers = set()

    dax, _ = fetch_dax40(fallback=[])
    tickers.update(dax)
    print(f"  EU: DAX 40 — {len(dax)} Ticker")

    for name, url, suffix, fallback in EU_INDICES:
        official = _wikipedia_table(url, ("ticker", "symbol"), len(fallback) // 2)
        if official:
            cleaned = _clean_eu(official, suffix)
            tickers.update(cleaned)
            print(f"  EU: {name} — {len(cleaned)} Ticker (Wikipedia)")
        else:
            fb_cleaned = _clean_eu(fallback, suffix)
            tickers.update(fb_cleaned)
            print(f"  EU: {name} — {len(fb_cleaned)} Ticker (Fallback)")

    return sorted(tickers)
