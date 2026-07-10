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
subprocess.run(["pip", "install", "yfinance", "pandas", "matplotlib", "deep-translator", "requests", "-q"])

import sys
import os
import json
import smtplib
from datetime import datetime, timedelta

# Gemeinsame Funktionen aus check_alerts importieren
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_alerts import (
    analyze_4h_structure,
    analyze_weekly_structure,
    analyze_daily_structure,
    send_alert_email,
    render_chart,
    load_state,
    save_state,
    load_signals,
    save_signals,
    _breakout_date,
    _is_recent,
)

import yfinance as yf
import pandas as pd
from zoneinfo import ZoneInfo

# ── Konfiguration ─────────────────────────────────────────────────────────────

SOURCES = {
    'QQQ': 'rs_full.json',
    'DAX': 'rs_dax.json',
    'SPX': 'rs_sp500.json',
}

_ET     = ZoneInfo('America/New_York')
_BERLIN = ZoneInfo('Europe/Berlin')


# ── Frische 4H-OHLCV-Daten per yfinance ──────────────────────────────────────

def fetch_fresh_4h(ticker, days=60):
    """
    Holt 4H-OHLCV-Daten identisch zu rs_colab.py:
      - interval='1h', dann resample('4h')
      - 60 Tage History (gleicher Kontext wie Nacht-Update)
      - Pre/Post-Market Spike-Filter
      - Timestamps in Europe/Berlin
    """
    try:
        end_dt   = datetime.now()
        start_dt = end_dt - timedelta(days=days)

        df = yf.download(
            ticker,
            start=start_dt.strftime('%Y-%m-%d'),
            end=end_dt.strftime('%Y-%m-%d'),
            interval='1h',
            prepost=True,
            auto_adjust=True,
            progress=False,
        )
        if df.empty:
            return []

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[['Open', 'High', 'Low', 'Close']].copy()
        df.index = pd.to_datetime(df.index)
        df.dropna(subset=['Close'], inplace=True)

        # Pre/Post-Market Spike-Filter (identisch zu rs_colab.py)
        extended = pd.Series(
            [ts.astimezone(_ET).hour < 9 or
             (ts.astimezone(_ET).hour == 9 and ts.astimezone(_ET).minute < 30) or
             ts.astimezone(_ET).hour >= 16
             for ts in df.index],
            index=df.index, dtype=bool,
        )
        prev_low = df['Low'].shift(1)
        next_low = df['Low'].shift(-1)
        bad_low  = extended & (df['Low'] < prev_low * 0.70) & (df['Low'] < next_low * 0.70)
        df.loc[bad_low, 'Low'] = df.loc[bad_low, ['Open', 'Close']].min(axis=1)

        df_4h = df[['Open', 'High', 'Low', 'Close']].resample('4h').agg({
            'Open':  'first',
            'High':  'max',
            'Low':   'min',
            'Close': 'last',
        }).dropna()

        result = []
        for dt, row in df_4h.iterrows():
            if pd.isna(row['Close']):
                continue
            dt_local = (dt.astimezone(_BERLIN) if dt.tzinfo
                        else dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(_BERLIN))
            result.append({
                'd': dt_local.strftime('%Y-%m-%d %H:%M'),
                'o': round(float(row['Open']),  2),
                'h': round(float(row['High']),  2),
                'l': round(float(row['Low']),   2),
                'c': round(float(row['Close']), 2),
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


# ── Ticker in allen Sources suchen ───────────────────────────────────────────

def find_ticker_source(ticker, source_cache):
    """Sucht Ticker in allen geladenen Sources. Gibt (entry, top20_set, source) zurück."""
    for src, (entries, top20_set) in source_cache.items():
        if ticker in entries:
            return entries[ticker], top20_set, src
    return None, set(), None


# ── Einen Ticker analysieren und ggf. Alert bauen ────────────────────────────

def check_one_ticker(ticker, source, entries, top20_set, signals, alerted,
                     today_str, test_mode=False):
    """
    Prüft einen Ticker auf 4H-Wiederkehr.
    Gibt ein Alert-Dict zurück oder None.
    Im test_mode werden alle Sperren (alerted, bar-Datum) umgangen.
    """
    if not test_mode and alerted.get(ticker) == today_str:
        print(f'  {ticker}: heute bereits gemeldet – übersprungen')
        return None

    print(f'  {ticker} ({source}): hole frische 4H-Daten …')
    fresh_4h = fetch_fresh_4h(ticker)

    if not fresh_4h:
        print(f'  {ticker}: keine 4H-Daten erhalten – übersprungen')
        return None

    struct_4h = analyze_4h_structure(fresh_4h)
    if not struct_4h or not struct_4h.get('broken4h'):
        print(f'  {ticker}: 4H-Struktur {"(Test) " if test_mode else ""}nicht gebrochen')
        return None

    cur_h4_date = _breakout_date(fresh_4h, struct_4h)

    # 4H-Breakout muss aktuell sein (≤ 3 Kalendertage), sonst kein Alert.
    if not test_mode and not _is_recent(cur_h4_date):
        print(f'  {ticker}: 4H-Breakout veraltet ({cur_h4_date}) – übersprungen')
        return None

    if not test_mode:
        last_sig = (signals.get(ticker) or [{}])[-1]
        if cur_h4_date and cur_h4_date == last_sig.get('h4_bar_date'):
            print(f'  {ticker}: 4H-Breakout ({cur_h4_date}) bereits bekannt – übersprungen')
            return None

    label = '[TEST] ' if test_mode else ''
    print(f'  ✓ {label}WIEDERKEHR: {ticker} ({source})  4H aktiv (Breakout: {cur_h4_date})')

    entry    = entries.get(ticker, {})
    ohlcv_w  = entry.get('ohlcv_w', [])
    ohlcv_d  = entry.get('ohlcv', [])
    score    = entry.get('score', 0)

    struct_w = analyze_weekly_structure(ohlcv_w)
    struct_d = analyze_daily_structure(ohlcv_d)

    w_b64  = render_chart(ohlcv_w,   ticker, 'Weekly (letzten 60 Kerzen)',
                          gws_price=struct_w['gws_price'] if struct_w else None, n_candles=60)
    d_b64  = render_chart(ohlcv_d,   ticker, 'Daily (letzten 60 Kerzen)',
                          gws_price=struct_d['gws_price'] if struct_d else None, n_candles=60)
    h4_b64 = render_chart(fresh_4h,  ticker, '4H (letzten 60 Kerzen)',
                          gws_price=struct_4h.get('gws_price'), n_candles=60)

    charts = []
    if w_b64:  charts.append((w_b64,  'Weekly'))
    if d_b64:  charts.append((d_b64,  'Daily'))
    if h4_b64: charts.append((h4_b64, '4H'))

    display_ticker = f'[TEST] {ticker}' if test_mode else ticker

    return {
        'ticker':          display_ticker,
        '_real_ticker':    ticker,
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
        'new_h4':          True,
        'reentry':         True,
        'weekly_bar_date': _breakout_date(ohlcv_w, struct_w),
        'daily_bar_date':  _breakout_date(ohlcv_d, struct_d),
        'h4_bar_date':     cur_h4_date,
        'in_top20':        ticker in top20_set,
        '_test_mode':      test_mode,
    }


# ── Haupt-Logik ───────────────────────────────────────────────────────────────

def main():
    # --test TICKER  → Testmodus für einen bestimmten Ticker
    test_ticker = None
    if '--test' in sys.argv:
        idx = sys.argv.index('--test')
        if idx + 1 < len(sys.argv):
            test_ticker = sys.argv[idx + 1].upper()
        else:
            print('FEHLER: --test erwartet einen Ticker, z.B.: --test ARM')
            sys.exit(1)

    # Auch über Umgebungsvariable steuerbar (für workflow_dispatch)
    if not test_ticker:
        test_ticker = os.environ.get('TEST_TICKER', '').strip().upper() or None

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
    mode_label = f'  [TEST: {test_ticker}]' if test_ticker else ''
    print(f'check_4h_reentry.py – {now_str}{mode_label}')

    state   = load_state()
    signals = load_signals()
    alerted = state.get('alerted', {})

    # Quell-Daten je Source einmal laden
    source_cache = {}
    for src in SOURCES:
        source_cache[src] = load_source_data(src)

    alerts = []

    if test_ticker:
        # ── Testmodus: gezielt einen Ticker erzwingen ─────────────────────────
        entry, top20_set, source = find_ticker_source(test_ticker, source_cache)
        if entry is None:
            # Ticker nicht in den RS-Daten: trotzdem 4H-Daten holen, Source=QQQ annehmen
            print(f'  [TEST] {test_ticker} nicht in RS-Daten gefunden – versuche QQQ')
            _, top20_set, source = source_cache.get('QQQ', ({}, set(), 'QQQ'))
            source = 'QQQ'
            entries_fallback = {}
        else:
            entries_fallback = source_cache[source][0]

        alert = check_one_ticker(
            test_ticker, source,
            entries_fallback if entry is None else source_cache[source][0],
            top20_set, signals, alerted, today_str,
            test_mode=True
        )
        if alert:
            alerts.append(alert)

    else:
        # ── Normalmodus: alle Wiederkehr-Kandidaten aus State ─────────────────
        candidates = find_reentry_candidates(state)
        print(f'Wiederkehr-Kandidaten (W+D aktiv, 4H fehlt): {len(candidates)}'
              + (f' – {[c["ticker"] for c in candidates]}' if candidates else ''))

        if not candidates:
            print('Keine Kandidaten. Beende.')
            return

        for cand in candidates:
            entries, top20_set = source_cache.get(cand['source'], ({}, set()))
            alert = check_one_ticker(
                cand['ticker'], cand['source'],
                entries, top20_set, signals, alerted, today_str,
                test_mode=False
            )
            if alert:
                alerts.append(alert)

    if not alerts:
        print('Keine neuen 4H-Wiederkehren.')
        return

    # Top-20-Aktien zuerst, danach alle weiteren Breakouts (stabile Sortierung)
    alerts.sort(key=lambda a: 0 if a.get('in_top20') else 1)

    # Mail senden
    is_test     = any(a.get('_test_mode') for a in alerts)
    date_label  = datetime.now().strftime('%d.%m.%Y')
    subject = (
        f'[TEST] 4H-Wiederkehr {date_label} – {alerts[0]["_real_ticker"] if is_test else ""}'
        if is_test else
        f'4H-Wiederkehr {date_label}: {len(alerts)} Aktie(n) – 4H-Signal zurückgekehrt'
    )
    send_alert_email(alerts, smtp_host, smtp_port, smtp_user, smtp_pass, to_addr,
                     subject_override=subject)

    tg_token   = os.environ.get('TELEGRAM_TOKEN', '')
    tg_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if tg_token:
        from telegram_handler import send_breakout_telegram, resolve_recipients, send_section_divider
        tg_recipients = resolve_recipients(tg_chat_id)
        if tg_recipients:
            has_top20 = any(a.get('in_top20') for a in alerts)
            has_other = any(not a.get('in_top20') for a in alerts)
            divider_sent = False
            for a in alerts:
                if has_top20 and has_other and not a.get('in_top20') and not divider_sent:
                    send_section_divider(tg_token, tg_recipients,
                                         'Weitere Breakouts – außerhalb Top 20')
                    divider_sent = True
                send_breakout_telegram(tg_token, tg_recipients, a)

    # Im Testmodus: State NICHT verändern
    if is_test:
        print('Test-Mail gesendet. State bleibt unverändert.')
        return

    # State und signals.json aktualisieren
    states = state.get('states', {})
    for a in alerts:
        ticker = a['_real_ticker']
        alerted[ticker] = today_str
        if ticker in states:
            states[ticker]['h4']    = True
            states[ticker]['points'] = 3
        signals.setdefault(ticker, []).append({
            'signal_date':     today_str,
            'trigger_tf':      '4h',
            'weekly_bar_date': a.get('weekly_bar_date'),
            'daily_bar_date':  a.get('daily_bar_date'),
            'h4_bar_date':     a.get('h4_bar_date'),
            'source':          a['source'],
            'reentry':         True,
        })

    state['states']  = states
    state['alerted'] = alerted
    save_state(state)
    save_signals(signals)
    print(f'State und signals.json aktualisiert ({len(alerts)} Wiederkehr-Alert(s)).')

    # KI-Analysen für Wiederkehr-Kandidaten generieren
    try:
        import generate_rating
        for a in alerts:
            ticker  = a['_real_ticker']
            entry   = source_cache.get(a['source'], ({}, set()))[0].get(ticker, {})
            gws = {
                'weekly':      True,
                'daily':       True,
                'h4':          True,
                'points':      3,
                'signal_type': '4H-Wiederkehr',
            }
            generate_rating.generate_for_ticker(
                ticker, a['score'], entry.get('windows', {}), gws
            )
    except Exception as _e:
        print(f'Rating-Generierung fehlgeschlagen (nicht kritisch): {_e}')


if __name__ == '__main__':
    main()
