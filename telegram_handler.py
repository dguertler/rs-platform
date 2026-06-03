"""
telegram_handler.py – Telegram-Benachrichtigungen für RS-Platform
=================================================================
Wird von check_alerts.py, check_4h_reentry.py und check_earnings.py
importiert. Sendet:
  - Foto-Album mit Charts (Weekly, Daily, 4H) — zuerst
  - Textnachricht (HTML-formatiert) mit Ticker-Info, Dots, Links, News, Analyse-Link
"""

import base64
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime


# ── Empfänger-Auflösung ───────────────────────────────────────────────────────

def _parse_chat_ids(raw):
    """Zerlegt einen kommagetrennten (oder Leerzeichen/Newline) Chat-ID-String
    in eine Liste eindeutiger IDs. Akzeptiert auch bereits fertige Listen."""
    if not raw:
        return []
    if isinstance(raw, (list, tuple, set)):
        parts = [str(x) for x in raw]
    else:
        parts = re.split(r'[,\s]+', str(raw).strip())
    seen, out = set(), []
    for p in (x.strip() for x in parts):
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def fetch_registered_chat_ids():
    """Holt zusätzlich die von registrierten Usern hinterlegten Chat-IDs vom
    Backend. Nur aktiv, wenn RS_API_URL und ALERT_API_KEY gesetzt sind —
    sonst leere Liste (voll abwärtskompatibel)."""
    base = os.environ.get('RS_API_URL', '').rstrip('/')
    key  = os.environ.get('ALERT_API_KEY', '')
    if not base or not key:
        return []
    try:
        req = urllib.request.Request(
            f'{base}/api/telegram/recipients',
            headers={'X-Alert-Key': key},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        return [str(c) for c in data.get('chat_ids', []) if c]
    except Exception as e:
        print(f'  [Telegram] Empfaenger-Abruf vom Backend fehlgeschlagen: {e}')
        return []


def resolve_recipients(chat_id_env):
    """Kombiniert die env-Chat-IDs (kommagetrennt) mit den im Backend
    registrierten Empfängern. Doppelte werden entfernt."""
    ids = _parse_chat_ids(chat_id_env)
    for cid in fetch_registered_chat_ids():
        if cid not in ids:
            ids.append(cid)
    return ids


# ── Interne Hilfsfunktionen ───────────────────────────────────────────────────

def _post_json(token, method, payload):
    """JSON-POST gegen Telegram Bot API (kein requests nötig)."""
    url  = f'https://api.telegram.org/bot{token}/{method}'
    data = json.dumps(payload).encode('utf-8')
    req  = urllib.request.Request(
        url, data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if not result.get('ok'):
                print(f'  [Telegram] {method} Fehler: {result.get("description", "")}')
            return result
    except Exception as e:
        print(f'  [Telegram] {method} fehlgeschlagen: {e}')
        return {}


def _post_multipart(token, method, fields, files):
    """Multipart-POST für sendMediaGroup (Fotos)."""
    import requests as req
    url = f'https://api.telegram.org/bot{token}/{method}'
    try:
        resp = req.post(url, data=fields, files=files, timeout=60)
        result = resp.json()
        if not result.get('ok'):
            print(f'  [Telegram] {method} Fehler: {result.get("description", "")}')
        return result
    except Exception as e:
        print(f'  [Telegram] {method} fehlgeschlagen: {e}')
        return {}


def _esc(text):
    """HTML-Sonderzeichen escapen."""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _dot(active, is_new=False):
    if is_new:  return '🟡'
    if active:  return '🟢'
    return '⚫'


def _dashboard(source):
    if source == 'DAX':
        return 'https://dguertler.github.io/Rel.-Strength/dax.html', 'DAX-Dashboard'
    if source == 'SPX':
        return 'https://dguertler.github.io/Rel.-Strength/sp500.html', 'S&amp;P 500-Dashboard'
    return 'https://dguertler.github.io/Rel.-Strength/', 'Nasdaq-Dashboard'


def _news_lines(news, max_specific=3, max_general=2):
    """Formatiert News-Links als HTML-Zeilen."""
    if not isinstance(news, dict):
        return ''
    specific = (news.get('specific') or [])[:max_specific]
    general  = (news.get('general')  or [])[:max_general]
    lines = []
    for n in specific:
        title = _esc(n.get('title', '')[:80])
        lines.append(f'📰 <a href="{n["url"]}">{title}</a>')
    for n in general:
        title = _esc(n.get('title', '')[:80])
        lines.append(f'📄 <a href="{n["url"]}">{title}</a>')
    return ('\n' + '\n'.join(lines)) if lines else ''


def _analyse_link(display_ticker):
    """Gibt einen HTML-Link zur KI-Analyse zurück, oder ''."""
    frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
    if not frontend_url:
        return ''
    ticker_param = urllib.parse.quote(display_ticker.replace('[TEST] ', '').strip())
    url = f'{frontend_url}?openRating={ticker_param}'
    return f'\n📊 <a href="{url}">Zur {_esc(display_ticker)}-Analyse</a>'


def _send_charts(token, chat_id, charts):
    """Schickt bis zu 3 Charts als Foto-Album (sendMediaGroup)."""
    if not charts:
        return
    media = []
    files = {}
    for i, item in enumerate(charts[:3]):
        b64, label = item
        if not b64:
            continue
        key = f'photo{i}'
        files[key] = (f'{label}.png', base64.b64decode(b64), 'image/png')
        media.append({'type': 'photo', 'media': f'attach://{key}', 'caption': label})
    if media:
        _post_multipart(token, 'sendMediaGroup',
                        {'chat_id': str(chat_id), 'media': json.dumps(media)},
                        files)


# ── Öffentliche API ───────────────────────────────────────────────────────────

def send_breakout_telegram(token, chat_id, alert):
    """
    Breakout- oder 4H-Wiederkehr-Alert:
    Charts zuerst als Foto-Album, dann Textnachricht.
    `chat_id` darf eine einzelne ID, eine kommagetrennte Liste oder eine
    Python-Liste sein — es wird an alle Empfänger gesendet.
    """
    recipients = _parse_chat_ids(chat_id)
    if not token or not recipients:
        return

    raw_ticker = alert['ticker'].replace('[TEST] ', '')
    display    = raw_ticker.replace('.DE', '') if raw_ticker.endswith('.DE') else raw_ticker
    source     = alert.get('source', 'QQQ')
    score      = alert.get('score', 0)
    info       = alert.get('info', {})
    is_reentry = alert.get('reentry', False)

    w_dot  = _dot(info.get('weekly'), alert.get('new_weekly'))
    d_dot  = _dot(info.get('daily'),  alert.get('new_daily'))
    h4_dot = _dot(info.get('h4'),     alert.get('new_h4'))

    dash_url, dash_label = _dashboard(source)
    top20   = '  ✅ <b>TOP 20</b>' if alert.get('in_top20') else ''
    reentry = '  <i>↩ 4H Wiederkehr</i>' if is_reentry else ''
    today   = datetime.now().strftime('%d.%m.%Y')

    text = (
        f'🔥 <b>{_esc(display)}</b> · {_esc(source)}{top20}\n'
        f'<b>{today}</b>{reentry}\n'
        f'RS-Score: <b>{score:.1f}</b>\n'
        f'W {w_dot}  D {d_dot}  4H {h4_dot}\n'
        f'<a href="{dash_url}">Zum {_esc(dash_label)}</a>'
        + _news_lines(alert.get('news'))
        + _analyse_link(display)
    )

    charts = alert.get('charts', [])
    for cid in recipients:
        _send_charts(token, cid, charts)
        _post_json(token, 'sendMessage', {
            'chat_id':    cid,
            'text':       text,
            'parse_mode': 'HTML',
            'link_preview_options': {'is_disabled': True},
        })


def send_earnings_telegram(token, chat_id, alert):
    """
    Earnings-Überraschungs-Alert:
    Charts zuerst als Foto-Album, dann Textnachricht.
    `chat_id` darf eine einzelne ID, eine kommagetrennte Liste oder eine
    Python-Liste sein — es wird an alle Empfänger gesendet.
    """
    recipients = _parse_chat_ids(chat_id)
    if not token or not recipients:
        return

    ticker  = alert['ticker']
    display = ticker.replace('.DE', '') if ticker.endswith('.DE') else ticker
    source  = alert.get('source', 'QQQ')
    score   = alert.get('score', 0)
    jump    = alert.get('jump_pct', 0) * 100
    surprise = alert.get('surprise_pct', 0)
    eps_est  = alert.get('eps_estimate')
    eps_act  = alert.get('eps_actual')
    rev_yoy  = alert.get('revenue_growth_yoy')
    today    = datetime.now().strftime('%d.%m.%Y')

    dash_url, dash_label = _dashboard(source)

    rev_line = ''
    if rev_yoy is not None:
        sign = '+' if rev_yoy >= 0 else ''
        rev_line = f'\nUmsatz YoY: <b>{sign}{rev_yoy*100:.1f}%</b>'

    eps_line = ''
    if eps_est is not None and eps_act is not None:
        eps_line = f'\nEPS: Schätzung <b>{eps_est:.2f}</b> → Ist <b>{eps_act:.2f}</b>'

    text = (
        f'📈 <b>{_esc(display)}</b> · {_esc(source)}\n'
        f'<b>{today}</b>\n'
        f'Kurssprung: <b>+{jump:.1f}%</b>  EPS-Surprise: <b>+{surprise:.1f}%</b>'
        f'{rev_line}{eps_line}\n'
        f'RS-Score: <b>{score:.1f}</b>\n'
        f'<a href="{dash_url}">Zum {_esc(dash_label)}</a>'
        + _news_lines(alert.get('news'))
        + _analyse_link(display)
    )

    charts = alert.get('charts', [])
    for cid in recipients:
        _send_charts(token, cid, charts)
        _post_json(token, 'sendMessage', {
            'chat_id':    cid,
            'text':       text,
            'parse_mode': 'HTML',
            'link_preview_options': {'is_disabled': True},
        })
