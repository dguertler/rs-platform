"""
check_4h_reentry.py – 4H-Wiederkehr-Check
==========================================
Läuft alle 4h während der Handelszeit (Mo-Fr).

Prüft AUSSCHLIESSLICH ob Ticker, die:
  • Weekly = grün (✓)
  • Daily  = grün (✓)
  • 4H     = rot  (✗)   ← zuvor verloren gegangen

...das 4H-Signal zurückgewonnen haben.

Alle anderen Breakout-Fälle (erstmaliger 2→3, 0→3, 1→3)
bleiben dem nächtlichen check_alerts.py überlassen.

Doppel-Mail-Schutz:
  - Gleicher Tag:    alerts_state.json['alerted'][ticker] == today
  - Folgetag:        h4_bar_date in signals.json unverändert → check_alerts.py
                     erkennt keinen frischen Breakout und sendet nicht nochmal
"""

import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "matplotlib", "deep-translator", "-q"])

import sys
import os
import json
import smtplib
from datetime import datetime

# Gemeinsame Funktionen aus check_alerts importieren
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_alerts import (
    analyze_4h_structure,
    analyze_weekly_structure,
    analyze_daily_structure,
    fetch_news,
    send_alert_email,
    render_chart,
    load_state,
    save_state,
    load_signals,
    save_signals,
    _breakout_date,
)

import yfinance as yf

# ── Konfiguration ─────────────────────────────────────────────────────────────

SOURCES = {
    'QQQ': 'rs_full.json',
    'DAX': 'rs_dax.json',
    'SPX': 'rs_sp500.json',
}

# Anzahl Tage, die für frische 4H-Daten geladen werden
FRESH_4H_DAYS = 15


# ── Frische 4H-OHLCV-Daten per yfinance ──────────────────────────────────────

def fetch_fresh_4h(ticker):
    """
    Holt aktuelle 4H-OHLCV-Daten via yfinance.
    Gibt Liste von {o, h, l, c, d}-Dicts zurück (aufsteigend nach Datum).
    """
    try:
        hist = yf.Ticker(ticker).history(
            period=f'{FRESH_4H_DAYS}d', interval='4h', auto_adjust=True
        )
        if hist.empty:
            return []
        result = []
        for ts, row in hist.iterrows():
            result.append({
                'o': float(row['Open']),
                'h': float(row['High']),
                'l': float(row['Low']),
                'c': float(row['Close']),
                'd': ts.strftime('%Y-%m-%d %H:%M'),
            })
        return result
    except Exception as e:
        print(f'  4H-Fetch fehlgeschlagen für {ticker}: {e}')
        return []


# ── Datei-Hilfsfunktionen ─────────────────────────────────────────────────────

def load_source_data(source):
    """Lädt rs_*.json und gibt (entries_dict, top20_set) zurück."""
    path = SOURCES.get(source, 'rs_full.json')
    if not os.path.exists(path):
        print(f'  Datei nicht gefunden: {path}')
        return {}, set()
    with open(path) as f:
        data = json.load(f)
    top20_set = set(data.get('top20', []))
    entries = {e['ticker']: e for e in data.get('data', [])}
    return entries, top20_set


# ── Wiederkehr-Erkennung ──────────────────────────────────────────────────────

def find_reentry_candidates(state):
    """
    Gibt alle Ticker zurück, bei denen:
      - Weekly = True, Daily = True (beide Punkte aktiv)
      - 4H     = False              (4H-Punkt zuletzt verloren)

    Das sind die einzigen Kandidaten für einen 4H-Wiederkehralert.
    """
    candidates = []
    for ticker, s in state.get('states', {}).items():
        if s.get('weekly') and s.get('daily') and not s.get('h4'):
            candidates.append({'ticker': ticker, 'source': s.get('source', 'QQQ')})
    return candidates


# ── Haupt-Logik ───────────────────────────────────────────────────────────────

def main():
    smtp_host = os.environ.get('SMTP_HOST', '')
    smtp_port = os.environ.get('SMTP_PORT', '587')
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    to_addr   = os.environ.get('ALERT_EMAIL_TO', '')

    if not all([smtp_host, smtp_user, smtp_pass, to_addr]):
        print('FEHLER: Bitte SMTP_HOST, SMTP_USER, SMTP_PASS und ALERT_EMAIL_TO setzen.')
        sys.exit(1)

    today_str = datetime.now().strftime('%Y-%m-%d')
    now_str   = datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f'check_4h_reentry.py – {now_str}')

    state   = load_state()
    signals = load_signals()
    alerted = state.get('alerted', {})

    candidates = find_reentry_candidates(state)
    print(f'Wiederkehr-Kandidaten (W+D aktiv, 4H fehlt): {len(candidates)}'
          + (f' – {[c["ticker"] for c in candidates]}' if candidates else ''))

    if not candidates:
        print('Keine Kandidaten. Beende.')
        return

    # Quell-Daten je Source einmal laden (nicht für jeden Ticker neu)
    source_cache = {}
    for src in SOURCES:
        source_cache[src] = load_source_data(src)

    alerts = []

    for cand in candidates:
        ticker = cand['ticker']
        source = cand['source']

        # Bereits heute gemeldet → überspringen
        if alerted.get(ticker) == today_str:
            print(f'  {ticker}: heute bereits gemeldet – übersprungen')
            continue

        entries, top20_set = source_cache.get(source, ({}, set()))

        if ticker not in top20_set:
            print(f'  {ticker}: nicht in Top 20 von {source} – übersprungen')
            continue

        print(f'  {ticker} ({source}): hole frische 4H-Daten …')
        fresh_4h = fetch_fresh_4h(ticker)

        if not fresh_4h:
            print(f'  {ticker}: keine 4H-Daten erhalten – übersprungen')
            continue

        struct_4h = analyze_4h_structure(fresh_4h)
        if not struct_4h or not struct_4h.get('broken4h'):
            print(f'  {ticker}: 4H-Struktur noch nicht gebrochen')
            continue

        # 4H ist jetzt aktiv → Wiederkehr!
        cur_h4_date = _breakout_date(fresh_4h, struct_4h)

        # Prüfen ob dieser Breakout neu ist (nicht schon bekannt in signals.json)
        last_sig    = (signals.get(ticker) or [{}])[-1]
        if cur_h4_date and cur_h4_date == last_sig.get('h4_bar_date'):
            print(f'  {ticker}: 4H-Breakout ({cur_h4_date}) bereits bekannt – übersprungen')
            continue

        print(f'  ✓ WIEDERKEHR: {ticker} ({source})  4H wieder aktiv (Breakout: {cur_h4_date})')

        # Bestehende W+D Struktur aus den RS-Daten (Charts und GWS-Preise)
        entry     = entries.get(ticker, {})
        ohlcv_w   = entry.get('ohlcv_w', [])
        ohlcv_d   = entry.get('ohlcv', [])
        score     = entry.get('score', 0)

        struct_w  = analyze_weekly_structure(ohlcv_w)
        struct_d  = analyze_daily_structure(ohlcv_d)

        # Charts mit frischen 4H-Daten
        w_b64  = render_chart(
            ohlcv_w, ticker, 'Weekly (letzten 60 Kerzen)',
            gws_price=struct_w['gws_price'] if struct_w else None, n_candles=60
        )
        d_b64  = render_chart(
            ohlcv_d, ticker, 'Daily (letzten 60 Kerzen)',
            gws_price=struct_d['gws_price'] if struct_d else None, n_candles=60
        )
        h4_b64 = render_chart(
            fresh_4h, ticker, '4H (letzten 60 Kerzen)',
            gws_price=struct_4h.get('gws_price'), n_candles=60
        )

        charts = []
        if w_b64:  charts.append((w_b64,  'Weekly'))
        if d_b64:  charts.append((d_b64,  'Daily'))
        if h4_b64: charts.append((h4_b64, '4H'))

        cur_w_date = _breakout_date(ohlcv_w, struct_w)
        cur_d_date = _breakout_date(ohlcv_d, struct_d)

        alerts.append({
            'ticker':          ticker,
            'score':           score,
            'info':            {
                'weekly': True, 'daily': True, 'h4': True,
                'struct_w': struct_w, 'struct_d': struct_d, 'struct_4h': struct_4h,
                'points': 3,
            },
            'source':          source,
            'charts':          charts,
            'new_weekly':      False,
            'new_daily':       False,
            'new_h4':          True,   # 4H ist das wiedergekehrte Signal → gelb
            'weekly_bar_date': cur_w_date,
            'daily_bar_date':  cur_d_date,
            'h4_bar_date':     cur_h4_date,
            'news':            fetch_news(ticker),
            'in_top20':        True,
            '_fresh_4h':       fresh_4h,   # intern für State-Update
            '_struct_4h':      struct_4h,
        })

    if not alerts:
        print('Keine neuen 4H-Wiederkehren.')
        # State unverändert lassen
        return

    # Mail senden
    subject = (
        f'4H-Wiederkehr {datetime.now().strftime("%d.%m.%Y")}: '
        f'{len(alerts)} Aktie(n) – 4H-Signal zurückgekehrt'
    )
    send_alert_email(alerts, smtp_host, smtp_port, smtp_user, smtp_pass, to_addr,
                     subject_override=subject)

    # State und signals.json aktualisieren
    states = state.get('states', {})
    for a in alerts:
        ticker = a['ticker']
        alerted[ticker] = today_str

        # 4H wieder auf True setzen
        if ticker in states:
            states[ticker]['h4']    = True
            states[ticker]['points'] = 3

        # Signal eintragen
        signals.setdefault(ticker, []).append({
            'signal_date':     today_str,
            'trigger_tf':      '4h',
            'weekly_bar_date': a.get('weekly_bar_date'),
            'daily_bar_date':  a.get('daily_bar_date'),
            'h4_bar_date':     a.get('h4_bar_date'),
            'source':          a['source'],
            'reentry':         True,   # Markierung: Wiederkehr (nicht Erstbreakout)
        })

    state['states']  = states
    state['alerted'] = alerted
    save_state(state)
    save_signals(signals)
    print(f'State und signals.json aktualisiert ({len(alerts)} Wiederkehr-Alert(s)).')


if __name__ == '__main__':
    main()
