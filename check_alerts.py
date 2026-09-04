import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "matplotlib", "deep-translator", "requests", "-q"])

import json
import os
import smtplib
import base64
import io
import sys
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── GWS-Analyse (Python-Port der JavaScript-Logik) ──────────────────────────
# Exakte Portierung der analyzeStructure / analyzeWeeklyStructure / analyze4HStructure
# Funktionen aus index.html

def _find_swing_points(highs, lows, n, window=2):
    """Swing-Hochs und Swing-Tiefs mit konfigurierbarem Fenster (±window Bars)."""
    swing_highs = []
    swing_lows  = []
    for i in range(window, n - window):
        if all(highs[i] >= highs[i-k] and highs[i] >= highs[i+k] for k in range(1, window+1)):
            swing_highs.append({'idx': i, 'price': highs[i]})
        if all(lows[i] <= lows[i-k] and lows[i] <= lows[i+k] for k in range(1, window+1)):
            swing_lows.append({'idx': i, 'price': lows[i]})
    return swing_highs, swing_lows


def _gws_core(swing_highs, swing_lows, closes, n, min_margin=0.001):
    """Kernlogik: tiefere Tiefs erkennen → GWS = höchstes Hoch dazwischen.
    min_margin: Close muss mindestens diesen Bruchteil über GWS liegen (Standard 0.1%)."""
    candidates = []
    for j in range(1, len(swing_lows)):
        tief_neu = swing_lows[j]
        tief_alt = swing_lows[j - 1]
        if tief_neu['price'] < tief_alt['price']:
            hochs = [h for h in swing_highs
                     if tief_alt['idx'] < h['idx'] < tief_neu['idx']]
            if hochs:
                gws_hoch = max(hochs, key=lambda h: h['price'])
                candidates.append(gws_hoch)

    gws_high = candidates[-1] if candidates else None

    breakout_idx = None
    if gws_high:
        threshold = gws_high['price'] * (1 + min_margin)
        for i in range(gws_high['idx'] + 1, n):
            if closes[i] > threshold:
                breakout_idx = i
                break

    return gws_high, breakout_idx


def analyze_daily_structure(ohlcv):
    """Port von analyzeStructure() aus index.html."""
    if not ohlcv or len(ohlcv) < 10:
        return None
    n      = len(ohlcv)
    highs  = [c['h'] for c in ohlcv]
    lows   = [c['l'] for c in ohlcv]
    closes = [c['c'] for c in ohlcv]

    swing_highs, swing_lows = _find_swing_points(highs, lows, n)
    gws_high, breakout_idx  = _gws_core(swing_highs, swing_lows, closes, n)

    trend = None
    if len(swing_highs) >= 2:
        last = swing_highs[-1]
        prev = swing_highs[-2]
        if last['price'] > prev['price']:
            trend = 'bullish'
        elif last['price'] < prev['price']:
            trend = 'bearish'

    broken = breakout_idx is not None or (gws_high is None and trend == 'bullish')
    return {
        'broken':      broken,
        'gws_price':   gws_high['price'] if gws_high else None,
        'breakout_idx': breakout_idx,
        'swing_highs': swing_highs[-6:],
        'swing_lows':  swing_lows[-6:],
    }


def analyze_weekly_structure(ohlcv_w):
    """Port von analyzeWeeklyStructure() aus index.html (±1 Bar wie im JS)."""
    if not ohlcv_w or len(ohlcv_w) < 8:
        return None
    n      = len(ohlcv_w)
    highs  = [c['h'] for c in ohlcv_w]
    lows   = [c['l'] for c in ohlcv_w]
    closes = [c['c'] for c in ohlcv_w]

    swing_highs, swing_lows = _find_swing_points(highs, lows, n, window=1)
    gws_high, breakout_idx  = _gws_core(swing_highs, swing_lows, closes, n)

    # Trend (für den Fall ohne GWS-Muster – wie im JS)
    trend = None
    if len(swing_highs) >= 2:
        last = swing_highs[-1]
        prev = swing_highs[-2]
        if last['price'] > prev['price']:
            trend = 'bullish'
        elif last['price'] < prev['price']:
            trend = 'bearish'

    # broken: GWS durchbrochen ODER kein GWS vorhanden aber klarer Aufwärtstrend
    broken = breakout_idx is not None or (gws_high is None and trend == 'bullish')

    return {
        'broken':       broken,
        'gws_price':    gws_high['price'] if gws_high else None,
        'breakout_idx': breakout_idx,
    }


def analyze_4h_structure(ohlcv_4h):
    """Port von analyze4HStructure() aus index.html."""
    if not ohlcv_4h or len(ohlcv_4h) < 8:
        return None
    n      = len(ohlcv_4h)
    highs  = [c['h'] for c in ohlcv_4h]
    lows   = [c['l'] for c in ohlcv_4h]
    closes = [c['c'] for c in ohlcv_4h]

    swing_highs, swing_lows   = _find_swing_points(highs, lows, n)
    gws_high, breakout_4h_idx = _gws_core(swing_highs, swing_lows, closes, n)

    trend = None
    if len(swing_highs) >= 2:
        last = swing_highs[-1]
        prev = swing_highs[-2]
        if last['price'] > prev['price']:
            trend = 'bullish'
        elif last['price'] < prev['price']:
            trend = 'bearish'

    return {
        'broken4h':     breakout_4h_idx is not None or (gws_high is None and trend == 'bullish'),
        'gws_price':    gws_high['price'] if gws_high else None,
        'breakout_idx': breakout_4h_idx,
    }


def _breakout_date(ohlcv, struct):
    """Gibt das Datum der Breakout-Kerze zurück (oder None)."""
    if not struct or not ohlcv:
        return None
    idx = struct.get('breakout_idx')
    if idx is not None and 0 <= idx < len(ohlcv):
        return ohlcv[idx]['d']
    return None


def _is_recent(date_str, max_days=3):
    """True wenn date_str (YYYY-MM-DD) nicht älter als max_days Kalendertage ist."""
    if not date_str:
        return False
    try:
        d = datetime.strptime(date_str[:10], '%Y-%m-%d').date()
        return (datetime.now().date() - d) <= timedelta(days=max_days)
    except ValueError:
        return False


def count_points(entry):
    """Berechnet die aktiven Punkte (0–3: W / D / 4H) für einen Ticker."""
    struct_w  = analyze_weekly_structure(entry.get('ohlcv_w',  []))
    struct_d  = analyze_daily_structure(entry.get('ohlcv',    []))
    struct_4h = analyze_4h_structure(entry.get('ohlcv_4h', []))

    p_w  = bool(struct_w.get('broken'))    if struct_w  else False
    p_d  = bool(struct_d.get('broken'))    if struct_d  else False
    p_4h = bool(struct_4h.get('broken4h')) if struct_4h else False

    return {
        'points':    int(p_w) + int(p_d) + int(p_4h),
        'weekly':    p_w,
        'daily':     p_d,
        'h4':        p_4h,
        'struct_w':  struct_w,
        'struct_d':  struct_d,
        'struct_4h': struct_4h,
    }


# ── Chart-Rendering (matplotlib) ────────────────────────────────────────

BG_DARK   = '#07090f'
BG_PANEL  = '#0a0f1e'
BULL_CLR  = '#4ade80'
BEAR_CLR  = '#f87171'
GWS_CLR   = '#f59e0b'
TICK_CLR  = '#475569'
GRID_CLR  = '#1e293b'
TEXT_CLR  = '#e2e8f0'


def render_chart(ohlcv, ticker, timeframe, gws_price=None, n_candles=40):
    """Zeichnet einen Kerzenchart und gibt ihn als base64-PNG zurück."""
    if not ohlcv:
        return None

    candles = ohlcv[-n_candles:]
    n = len(candles)

    fig, ax = plt.subplots(figsize=(9, 3.5))
    fig.patch.set_facecolor(BG_DARK)
    ax.set_facecolor(BG_DARK)

    for i, c in enumerate(candles):
        o, h, l, cl = c['o'], c['h'], c['l'], c['c']
        color = BULL_CLR if cl >= o else BEAR_CLR
        # Docht
        ax.plot([i, i], [l, h], color=color, linewidth=0.8, zorder=1)
        # Körper
        body_h = max(abs(cl - o), (h - l) * 0.01)
        body_y = min(cl, o)
        rect = mpatches.Rectangle(
            (i - 0.35, body_y), 0.7, body_h,
            facecolor=color, edgecolor=color, zorder=2
        )
        ax.add_patch(rect)

    # GWS-Linie
    if gws_price:
        ax.axhline(gws_price, color=GWS_CLR, linewidth=1.2, linestyle='--',
                   label=f'GWS  {gws_price:.2f}', zorder=3)

    # Achsen & Styling
    all_h = [c['h'] for c in candles]
    all_l = [c['l'] for c in candles]
    price_range = max(all_h) - min(all_l)
    pad = price_range * 0.06
    ax.set_xlim(-1, n)
    ax.set_ylim(min(all_l) - pad, max(all_h) + pad)

    step = max(1, n // 7)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels(
        [candles[i]['d'][:10] for i in range(0, n, step)],
        rotation=25, fontsize=7, color=TICK_CLR, ha='right'
    )
    ax.yaxis.tick_right()
    ax.tick_params(axis='y', colors=TICK_CLR, labelsize=7)
    ax.tick_params(axis='x', length=0)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_CLR)
    ax.grid(axis='y', color=GRID_CLR, linewidth=0.5)

    ax.set_title(f'{ticker}  –  {timeframe}',
                 color=TEXT_CLR, fontsize=10, pad=6, loc='left',
                 fontfamily='monospace')

    if gws_price:
        legend = ax.legend(loc='upper left', facecolor=BG_PANEL,
                           edgecolor=GRID_CLR, labelcolor=GWS_CLR, fontsize=8)

    buf = io.BytesIO()
    fig.tight_layout(pad=0.5)
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight',
                facecolor=BG_DARK)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


# ── E-Mail versenden ──────────────────────────────────────────────

def send_alert_email(alerts, smtp_host, smtp_port, smtp_user, smtp_pass, to_addr,
                     subject_override=None):
    """Versendet eine HTML-E-Mail mit Alarmen und eingebetteten Charts."""
    today_str = datetime.now().strftime('%d.%m.%Y')
    subject   = subject_override or f'Breakout-Alarm {today_str}: {len(alerts)} Aktie(n) auf 3 Punkte'

    msg = MIMEMultipart('related')
    msg['Subject'] = subject
    msg['From']    = smtp_user
    msg['To']      = to_addr

    html_parts = [f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="background:#060b14;color:#e2e8f0;font-family:monospace;
             padding:24px;max-width:780px;margin:0 auto">
  <h2 style="color:#fca5a5;margin:0 0 4px">
    Breakout-Alarm &mdash; {today_str}
  </h2>
  <p style="color:#64748b;margin:0 0 24px;font-size:12px">
    Folgende Aktien haben heute den 3.&nbsp;GWS-Punkt erreicht (2&nbsp;&rarr;&nbsp;3):
  </p>
"""]

    cid_counter  = 0
    inline_imgs  = []

    has_top20 = any(a.get('in_top20') for a in alerts)
    has_other = any(not a.get('in_top20') for a in alerts)
    divider_inserted = False

    def dot_html(active, is_new=False):
        # Gleiche Farblogik wie auf der HTML-Seite:
        # gelb (#eab308) = neu aktiv, grün (#4ade80) = aktiv, grau = inaktiv
        if is_new:
            color = '#eab308'
        elif active:
            color = '#4ade80'
        else:
            color = '#334155'
        return (f'<span style="display:inline-block;width:9px;height:9px;'
                f'border-radius:50%;background:{color};'
                f'vertical-align:middle;margin:0 1px"></span>')

    for alert in alerts:
        if has_top20 and has_other and not alert.get('in_top20') and not divider_inserted:
            html_parts.append("""
  <div style="margin:32px 0 20px;text-align:center;color:#64748b;
              font-size:11px;letter-spacing:2px;font-family:monospace">
    <span style="display:inline-block;width:40px;height:1px;
                 background:#334155;vertical-align:middle;margin-right:10px"></span>
    WEITERE BREAKOUTS &middot; AUSSERHALB TOP 20
    <span style="display:inline-block;width:40px;height:1px;
                 background:#334155;vertical-align:middle;margin-left:10px"></span>
  </div>
""")
            divider_inserted = True

        ticker         = alert['ticker']
        display_ticker = ticker.replace('.DE', '') if ticker.endswith('.DE') else ticker
        score    = alert['score']
        score_str = f"{score:.1f}" if isinstance(score, (int, float)) else "–"
        info     = alert['info']
        source   = alert.get('source', 'QQQ')

        w_dot  = dot_html(info['weekly'], alert.get('new_weekly', False))
        d_dot  = dot_html(info['daily'],  alert.get('new_daily',  False))
        h4_dot = dot_html(info['h4'],     alert.get('new_h4',     False))
        top20_badge = ('<span style="background:#1e3a5f;color:#60a5fa;padding:2px 7px;'
                       'border-radius:10px;font-size:10px;font-weight:bold">TOP&nbsp;20</span>&nbsp;'
                       if alert.get('in_top20') else '')

        _base_url = os.environ.get('FRONTEND_URL', os.environ.get('APP_URL', 'https://rs-platform-production.up.railway.app')).rstrip('/')
        if source == 'DAX':
            dashboard_url   = _base_url
            dashboard_label = 'DAX-Dashboard'
        elif source == 'SPX':
            dashboard_url   = _base_url
            dashboard_label = 'S&P 500-Dashboard'
        else:
            dashboard_url   = _base_url
            dashboard_label = 'RS-Dashboard'

        html_parts.append(f"""
  <div style="margin:0 0 28px;padding:16px;
              background:#160303;border:1px solid #ef4444;
              border-left:4px solid #ef4444;border-radius:8px">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
      <span style="font-size:18px">&#128293;</span>
      <span style="font-size:16px;font-weight:bold;color:#fca5a5">{display_ticker}</span>
      <span style="font-size:11px;color:#64748b">({source})</span>
      <span style="margin-left:auto;font-size:11px;color:#94a3b8;display:flex;align-items:center;gap:6px">
        {top20_badge}RS-Score:&nbsp;<strong style="color:#f1f5f9">{score_str}</strong>
      </span>
    </div>
    <div style="font-size:12px;margin-bottom:10px;letter-spacing:1px">
      <span style="color:#64748b">W</span>&nbsp;{w_dot}
      &nbsp;&nbsp;
      <span style="color:#64748b">D</span>&nbsp;{d_dot}
      &nbsp;&nbsp;
      <span style="color:#64748b">4H</span>&nbsp;{h4_dot}
      &nbsp;&nbsp;&nbsp;
      <a href="{dashboard_url}" style="color:#3b82f6;font-size:11px;
         text-decoration:none">&rarr; {dashboard_label}</a>
    </div>
""")

        for chart_b64, timeframe_label in alert.get('charts', []):
            if chart_b64:
                cid = f'chart_{cid_counter}'
                cid_counter += 1
                inline_imgs.append((cid, chart_b64))
                html_parts.append(
                    f'    <img src="cid:{cid}" '
                    f'style="width:100%;max-width:720px;display:block;'
                    f'margin:6px 0;border-radius:6px">\n'
                )

        # "Analyse ansehen"-Button — öffnet die Bewertungsseite im Dashboard
        frontend_url = _base_url
        url_ticker   = display_ticker.replace('[TEST] ', '').strip()
        if frontend_url:
            html_parts.append(
                f'    <div style="margin-top:14px">'
                f'<a href="{frontend_url}?openRating={url_ticker}" '
                f'style="display:inline-block;padding:7px 16px;background:#1e3a5f;'
                f'color:#60a5fa;border:1px solid #2563eb;border-radius:5px;'
                f'font-size:12px;font-weight:600;text-decoration:none;font-family:monospace">'
                f'&#128196; KI-Analyse ansehen &rarr;</a></div>\n'
            )

        html_parts.append('  </div>\n')

    html_parts.append("""
  <p style="font-size:10px;color:#334155;margin-top:24px">
    Generiert von RS-Dashboard &middot; check_alerts.py
  </p>
</body></html>""")

    html_body = ''.join(html_parts)

    msg_alt = MIMEMultipart('alternative')
    msg_alt.attach(MIMEText(html_body, 'html', 'utf-8'))
    msg.attach(msg_alt)

    for cid, b64_data in inline_imgs:
        img_data = base64.b64decode(b64_data)
        img      = MIMEImage(img_data, 'png')
        img.add_header('Content-ID',          f'<{cid}>')
        img.add_header('Content-Disposition', 'inline', filename=f'{cid}.png')
        msg.attach(img)

    with smtplib.SMTP(smtp_host, int(smtp_port), timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_addr, msg.as_string())

    print(f'E-Mail gesendet an {to_addr}')


# ── Zustandsdatei ───────────────────────────────────────────────

STATE_FILE = 'alerts_state.json'


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {'states': {}, 'alerted': {}}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


SIGNALS_FILE = 'signals.json'


def load_signals():
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE) as f:
            return json.load(f)
    return {}


def save_signals(signals):
    with open(SIGNALS_FILE, 'w') as f:
        json.dump(signals, f, indent=2)


# Letzte tatsächlich verschickte Breakout-Charge – wird vom Backend genutzt,
# um neu verbundenen Telegram-Usern die letzten Alerts nachzureichen.
LAST_BATCH_FILE = 'last_breakout_alerts.json'


def save_last_breakout_batch(alerts):
    """Speichert die zuletzt verschickte Breakout-Charge (inkl. Charts) mit
    Zeitstempel, damit das Backend sie nachreichen kann."""
    now = datetime.now()
    payload = {
        'sent_at':      now.isoformat(timespec='seconds'),
        'sent_at_label': now.strftime('%d.%m.%Y %H:%M'),
        'date_label':   now.strftime('%d.%m.%Y'),
        'alerts':       alerts,
    }
    with open(LAST_BATCH_FILE, 'w') as f:
        json.dump(payload, f)


# Quelle → RS-JSON-Datei (im Actions-Lauf liegen die Dateien im Root)
_SOURCE_FILE = {'QQQ': 'rs_full.json', 'DAX': 'rs_dax.json', 'SPX': 'rs_sp500.json'}


def _build_alert(entry, source_label, top20_set, trigger_tf=None):
    """Baut ein vollständiges Alert-Dict (inkl. Charts) für einen Ticker –
    unabhängig von Trigger-/Dedup-Logik. Für Backfill der letzten Charge."""
    ticker = entry['ticker']
    score  = entry.get('score', 0)
    info   = count_points(entry)

    cur_w_date  = _breakout_date(entry.get('ohlcv_w',  []), info['struct_w'])
    cur_d_date  = _breakout_date(entry.get('ohlcv',    []), info['struct_d'])
    cur_h4_date = _breakout_date(entry.get('ohlcv_4h', []), info['struct_4h'])

    w_b64  = render_chart(entry.get('ohlcv_w', []), ticker, 'Weekly (letzten 60 Kerzen)',
                          gws_price=info['struct_w']['gws_price'] if info['struct_w'] else None,
                          n_candles=60)
    d_b64  = render_chart(entry.get('ohlcv', []), ticker, 'Daily (letzten 60 Kerzen)',
                          gws_price=info['struct_d']['gws_price'] if info['struct_d'] else None,
                          n_candles=60)
    h4_b64 = render_chart(entry.get('ohlcv_4h', []), ticker, '4H (letzten 60 Kerzen)',
                          gws_price=info['struct_4h']['gws_price'] if info['struct_4h'] else None,
                          n_candles=60)
    charts = []
    if w_b64:  charts.append((w_b64,  'Weekly'))
    if d_b64:  charts.append((d_b64,  'Daily'))
    if h4_b64: charts.append((h4_b64, '4H'))

    return {
        'ticker':          ticker,
        'score':           score,
        'windows':         entry.get('windows', {}),
        'info':            info,
        'source':          source_label,
        'charts':          charts,
        'new_weekly':      trigger_tf == 'weekly',
        'new_daily':       trigger_tf == 'daily',
        'new_h4':          trigger_tf == '4h',
        'weekly_bar_date': cur_w_date,
        'daily_bar_date':  cur_d_date,
        'h4_bar_date':     cur_h4_date,
        'in_top20':        ticker in top20_set,
    }


def backfill_last_batch(date_str):
    """Rekonstruiert die Breakouts eines Datums aus signals.json (inkl. Charts)
    und speichert sie als 'letzte Charge' – ohne erneuten Versand."""
    signals = load_signals()
    # Quelle → {ticker: trigger_tf}
    wanted = {}
    for ticker, lst in signals.items():
        for s in lst:
            if s.get('signal_date') == date_str:
                wanted.setdefault(s.get('source', 'QQQ'), {})[ticker] = s.get('trigger_tf')

    total = sum(len(v) for v in wanted.values())
    print(f'Backfill {date_str}: {total} Ticker aus signals.json')

    alerts = []
    for source, tickmap in wanted.items():
        path = _SOURCE_FILE.get(source)
        if not path or not os.path.exists(path):
            print(f'  RS-Datei für Quelle {source} fehlt ({path}) – übersprungen.')
            continue
        with open(path) as f:
            data = json.load(f)
        top20_set = set(data.get('top20', []))
        by_ticker = {e['ticker']: e for e in data.get('data', [])}
        for ticker, tf in tickmap.items():
            entry = by_ticker.get(ticker)
            if not entry:
                print(f'  {ticker} nicht in {path} gefunden – übersprungen.')
                continue
            print(f'  Baue Alert: {ticker} ({source}, tf={tf})')
            alerts.append(_build_alert(entry, source, top20_set, tf))

    save_last_breakout_batch(alerts)
    print(f'Backfill: {len(alerts)} Alerts in {LAST_BATCH_FILE} gespeichert.')


# ── Hauptprogramm ───────────────────────────────────────────────

def process_json(json_path, source_label, prev_states, today_str, signals=None):
    """
    Lädt eine RS-JSON-Datei, berechnet Punkte, gibt neue Zustände
    und eine Liste von Alert-Dicts zurück.
    """
    if signals is None:
        signals = {}

    if not os.path.exists(json_path):
        print(f'Datei nicht gefunden: {json_path}')
        return {}, []

    with open(json_path) as f:
        data = json.load(f)

    top20_set  = set(data.get('top20', []))
    new_states = {}
    alerts     = []

    for entry in data.get('data', []):
        ticker = entry['ticker']
        score  = entry.get('score', 0)
        info   = count_points(entry)

        new_states[ticker] = {
            'points':  info['points'],
            'weekly':  info['weekly'],
            'daily':   info['daily'],
            'h4':      info['h4'],
            'source':  source_label,
        }

        prev = prev_states.get(ticker, {})
        prev_points = prev.get('points', 0)

        if info['points'] == 3:
            # Breakout-Daten der aktuellen Timeframes
            cur_w_date  = _breakout_date(entry.get('ohlcv_w',  []), info['struct_w'])
            cur_d_date  = _breakout_date(entry.get('ohlcv',    []), info['struct_d'])
            cur_h4_date = _breakout_date(entry.get('ohlcv_4h', []), info['struct_4h'])

            # Letztes gespeichertes Signal für Vergleich der Breakout-Daten.
            # Ohne vorherige Signal-Historie für diesen Ticker gibt es keine
            # Vergleichsbasis — dann NICHT als "frisch" werten (sonst würde
            # jeder Ticker, der zum ersten Mal betrachtet wird, fälschlich
            # als frischer Re-Entry gelten, nur weil last_sig leer ist).
            ticker_signals = signals.get(ticker) or []
            last_sig = ticker_signals[-1] if ticker_signals else {}
            has_history = bool(ticker_signals)

            # Ein Teilsignal ist "frisch", wenn sein Breakout-Datum sich geändert hat
            # (Signal war weg und ist neu zurückgekommen – auch ohne messbaren 2→3-Übergang)
            # Das neu erkannte Breakout-Datum muss zusätzlich aktuell sein — sonst wird
            # jede Verschiebung des GWS-Musters durch neue Kerzen (Swing-Neuberechnung,
            # ohne echten frischen Bruch) fälschlich als "frisch" gewertet. Weekly-Kerzen
            # decken eine ganze Woche ab, daher dort ein größeres Zeitfenster als bei
            # Daily/4H.
            w_is_fresh  = bool(has_history and info['weekly'] and cur_w_date
                               and cur_w_date  != last_sig.get('weekly_bar_date')
                               and _is_recent(cur_w_date, max_days=7))
            d_is_fresh  = bool(has_history and info['daily']  and cur_d_date
                               and cur_d_date  != last_sig.get('daily_bar_date')
                               and _is_recent(cur_d_date))
            h4_is_fresh = bool(has_history and info['h4']     and cur_h4_date
                               and cur_h4_date != last_sig.get('h4_bar_date')
                               and _is_recent(cur_h4_date))

            # Welcher Punkt ist neu hinzugekommen?
            new_w  = (info['weekly'] and not prev.get('weekly', False)) or w_is_fresh
            new_d  = (info['daily']  and not prev.get('daily',  False)) or d_is_fresh
            new_h4 = (info['h4']     and not prev.get('h4',     False)) or h4_is_fresh

            # Beim klassischen 2→3-Übergang (prev_points < 3): 4H-Breakout muss aktuell sein,
            # wenn 4H der neu hinzugekommene Punkt ist. Sonst kein Alert für veraltete 4H-Brüche.
            h4_newly_added = info['h4'] and not prev.get('h4', False)
            if h4_newly_added and not _is_recent(cur_h4_date):
                print(f'  SKIP {ticker}: 4H-Breakout veraltet ({cur_h4_date}), kein Alert.')
                continue

            # Auslöser:
            # 1. Klassisch: von < 3 auf 3 (inkl. 0/1→3, nicht nur 2→3)
            # 2. Wiederkehrender Punkt: auf 3 geblieben, aber mind. ein Breakout ist neu
            #    (Punkt war weg und zurückgekommen innerhalb desselben Tages)
            trigger = (prev_points < 3) or (prev_points == 3 and (w_is_fresh or d_is_fresh or h4_is_fresh))

            if not trigger:
                continue

            print(f'  ALERT: {ticker} ({source_label})  {prev_points} → {info["points"]} Punkte'
                  + (' [Wiederkehr]' if prev_points == 3 else ''))

            # Charts: Weekly → Daily → 4H
            w_b64  = render_chart(
                entry.get('ohlcv_w', []), ticker, 'Weekly (letzten 60 Kerzen)',
                gws_price=info['struct_w']['gws_price'] if info['struct_w'] else None,
                n_candles=60
            )
            d_b64  = render_chart(
                entry.get('ohlcv', []), ticker, 'Daily (letzten 60 Kerzen)',
                gws_price=info['struct_d']['gws_price'] if info['struct_d'] else None,
                n_candles=60
            )
            h4_b64 = render_chart(
                entry.get('ohlcv_4h', []), ticker, '4H (letzten 60 Kerzen)',
                gws_price=info['struct_4h']['gws_price'] if info['struct_4h'] else None,
                n_candles=60
            )
            charts = []
            if w_b64:  charts.append((w_b64,  'Weekly'))
            if d_b64:  charts.append((d_b64,  'Daily'))
            if h4_b64: charts.append((h4_b64, '4H'))

            alerts.append({
                'ticker':          ticker,
                'score':           score,
                'windows':         entry.get('windows', {}),
                'info':            info,
                'source':          source_label,
                'charts':          charts,
                'new_weekly':      new_w,
                'new_daily':       new_d,
                'new_h4':          new_h4,
                'weekly_bar_date': cur_w_date,
                'daily_bar_date':  cur_d_date,
                'h4_bar_date':     cur_h4_date,
                'in_top20':        ticker in top20_set,
            })

    return new_states, alerts


def run_test_mode(smtp_host, smtp_port, smtp_user, smtp_pass, to_addr):
    """
    Testmodus: Nimmt die Aktie mit den meisten Punkten aus rs_full.json
    (egal ob 2→3-Übergang) und schickt sofort eine Test-Mail.
    """
    print('── TEST-MODUS ──')
    json_path = 'rs_full.json'
    if not os.path.exists(json_path):
        print(f'Datei nicht gefunden: {json_path}')
        sys.exit(1)

    with open(json_path) as f:
        data = json.load(f)

    # Suche Aktie mit höchster Punktzahl (bevorzugt 3, sonst 2, sonst 1)
    best_entry = None
    best_points = -1
    for entry in data.get('data', []):
        info = count_points(entry)
        if info['points'] > best_points:
            best_points = info['points']
            best_entry  = (entry, info)
        if best_points == 3:
            break

    if not best_entry:
        print('Keine Einträge gefunden.')
        sys.exit(1)

    entry, info = best_entry
    ticker = entry['ticker']
    score  = entry.get('score') or 0
    print(f'Test-Aktie: {ticker}  ({best_points} Punkte, Score {score:.1f})')

    # Charts: Weekly → Daily → 4H
    w_b64  = render_chart(
        entry.get('ohlcv_w', []), ticker, 'Weekly (letzten 60 Kerzen)',
        gws_price=info['struct_w']['gws_price'] if info['struct_w'] else None,
        n_candles=60,
    )
    d_b64  = render_chart(
        entry.get('ohlcv', []), ticker, 'Daily (letzten 60 Kerzen)',
        gws_price=info['struct_d']['gws_price'] if info['struct_d'] else None,
        n_candles=60,
    )
    h4_b64 = render_chart(
        entry.get('ohlcv_4h', []), ticker, '4H (letzten 60 Kerzen)',
        gws_price=info['struct_4h']['gws_price'] if info['struct_4h'] else None,
        n_candles=60,
    )
    charts = []
    if w_b64:  charts.append((w_b64,  'Weekly'))
    if d_b64:  charts.append((d_b64,  'Daily'))
    if h4_b64: charts.append((h4_b64, '4H'))

    test_alert = [{
        'ticker':     f'[TEST] {ticker}',
        'score':      score,
        'info':       info,
        'source':     'QQQ – Testmail',
        'charts':     charts,
        'new_weekly': False,
        'new_daily':  False,
        'new_h4':     True,   # Im Test: 4H als neu/gelb markieren
        'in_top20':   True,
    }]

    # Subject als Test kennzeichnen
    today_str = datetime.now().strftime('%d.%m.%Y')
    msg = MIMEMultipart('related')
    msg['Subject'] = f'[TEST] Breakout-Alarm {today_str} – Mail-Versand funktioniert!'
    msg['From']    = smtp_user
    msg['To']      = to_addr

    send_alert_email(test_alert, smtp_host, smtp_port, smtp_user, smtp_pass, to_addr,
                     subject_override=f'[TEST] Breakout-Alarm {today_str} – '
                                      f'Mail-Versand funktioniert!')
    print('Test-Mail gesendet.')

    tg_token   = os.environ.get('TELEGRAM_TOKEN', '')
    tg_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if tg_token and tg_chat_id:
        from telegram_handler import send_breakout_telegram
        send_breakout_telegram(tg_token, tg_chat_id, test_alert[0])
        print('Test-Telegram gesendet.')

    # Letzte Charge auch im Testmodus persistieren, damit das Backend die
    # Willkommens-Nachreichung (neuer Telegram-User) testen kann.
    save_last_breakout_batch(test_alert)
    print('last_breakout_alerts.json (Test) geschrieben.')


def main():
    test_mode = '--test' in sys.argv or os.environ.get('ALERT_TEST_MODE', '') == 'true'

    # Backfill-Modus: letzte Charge aus signals.json rekonstruieren (kein Versand)
    backfill_date = os.environ.get('BACKFILL_LAST_BATCH', '').strip()
    if backfill_date:
        if backfill_date.lower() in ('today', 'heute'):
            backfill_date = datetime.now().strftime('%Y-%m-%d')
        backfill_last_batch(backfill_date)
        return

    smtp_host = os.environ.get('SMTP_HOST', '')
    smtp_port = os.environ.get('SMTP_PORT', '587')
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    to_addr   = os.environ.get('ALERT_EMAIL_TO', '')

    if not all([smtp_host, smtp_user, smtp_pass, to_addr]):
        print('FEHLER: Bitte SMTP_HOST, SMTP_USER, SMTP_PASS und ALERT_EMAIL_TO setzen.')
        sys.exit(1)

    if test_mode:
        run_test_mode(smtp_host, smtp_port, smtp_user, smtp_pass, to_addr)
        return

    today_str  = datetime.now().strftime('%Y-%m-%d')
    state      = load_state()
    prev_states = state.get('states', {})
    alerted     = state.get('alerted', {})  # ticker → letztes Alert-Datum
    signals     = load_signals()             # für Breakout-Datum-Vergleich (Wiederkehr-Erkennung)

    print(f'check_alerts.py  –  {today_str}')
    print(f'Vorheriger Zustand: {len(prev_states)} Ticker')

    all_new_states = {}
    all_alerts     = []

    # US-Aktien (QQQ)
    print('\n── US-Aktien (rs_full.json) ──')
    new_us, alerts_us = process_json('rs_full.json', 'QQQ', prev_states, today_str, signals)
    all_new_states.update(new_us)
    all_alerts.extend(alerts_us)

    # DAX-Aktien
    print('\n── DAX-Aktien (rs_dax.json) ──')
    new_dax, alerts_dax = process_json('rs_dax.json', 'DAX', prev_states, today_str, signals)
    all_new_states.update(new_dax)
    all_alerts.extend(alerts_dax)

    # S&P 500 Aktien
    print('\n── S&P 500 (rs_sp500.json) ──')
    new_sp500, alerts_sp500 = process_json('rs_sp500.json', 'SPX', prev_states, today_str, signals)
    all_new_states.update(new_sp500)
    all_alerts.extend(alerts_sp500)

    # Ticker, die in mehreren Quellen vorkommen (z.B. NASDAQ-100 + S&P 500),
    # deduplizieren – nur der erste Treffer (Reihenfolge QQQ > DAX > SPX) bleibt,
    # sonst würde derselbe Ticker mehrfach in derselben Mail auftauchen.
    seen_tickers = set()
    deduped_alerts = []
    for a in all_alerts:
        if a['ticker'] in seen_tickers:
            print(f'  DEDUP: {a["ticker"]} ({a["source"]}) – bereits aus anderer Quelle gemeldet.')
            continue
        seen_tickers.add(a['ticker'])
        deduped_alerts.append(a)
    all_alerts = deduped_alerts

    # Bereits heute gemeldete Ticker herausfiltern
    fresh_alerts = [a for a in all_alerts
                    if alerted.get(a['ticker']) != today_str]
    # Top-20-Aktien zuerst, danach alle weiteren Breakouts (stabile Sortierung)
    fresh_alerts.sort(key=lambda a: 0 if a.get('in_top20') else 1)

    print(f'\nAlertes gesamt: {len(all_alerts)}  '
          f'(davon neu heute: {len(fresh_alerts)})')

    # Nur Top-20-Aktien der Indizes werden per Mail/Telegram gemeldet.
    report_alerts = [a for a in fresh_alerts if a.get('in_top20')]
    print(f'Davon Top-20 (werden gemeldet): {len(report_alerts)}')

    tg_token   = os.environ.get('TELEGRAM_TOKEN', '')
    tg_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')

    if report_alerts:
        send_alert_email(report_alerts, smtp_host, smtp_port,
                         smtp_user, smtp_pass, to_addr)
        if tg_token:
            from telegram_handler import send_breakout_telegram, resolve_recipients
            tg_recipients = resolve_recipients(tg_chat_id)
            if tg_recipients:
                print(f'Telegram-Empfaenger: {len(tg_recipients)}')
                for a in report_alerts:
                    send_breakout_telegram(tg_token, tg_recipients, a)
        # Letzte verschickte Charge persistieren (für Willkommens-Nachreichung)
        save_last_breakout_batch(report_alerts)
    if fresh_alerts:
        for a in fresh_alerts:
            alerted[a['ticker']] = today_str
            trigger_tf = 'weekly' if a['new_weekly'] else ('daily' if a['new_daily'] else '4h')
            signals.setdefault(a['ticker'], []).append({
                'signal_date':     today_str,
                'trigger_tf':      trigger_tf,
                'weekly_bar_date': a.get('weekly_bar_date'),
                'daily_bar_date':  a.get('daily_bar_date'),
                'h4_bar_date':     a.get('h4_bar_date'),
                'source':          a['source'],
            })
        save_signals(signals)

        # KI-Analysen für alle neu gemeldeten Ticker generieren
        try:
            import generate_rating
            for a in fresh_alerts:
                real_ticker = a['ticker']
                gws = {
                    'weekly':      a['info']['weekly'],
                    'daily':       a['info']['daily'],
                    'h4':          a['info']['h4'],
                    'points':      a['info']['points'],
                    'signal_type': 'Erstmaliger Breakout',
                }
                generate_rating.generate_for_ticker(
                    real_ticker, a['score'], a.get('windows', {}), gws
                )
        except Exception as _e:
            print(f'Rating-Generierung fehlgeschlagen (nicht kritisch): {_e}')
    else:
        print('Keine neuen 2→3-Übergänge heute.')

    # Zustand speichern
    state['states']  = all_new_states
    state['alerted'] = alerted
    save_state(state)
    print(f'Zustand gespeichert ({len(all_new_states)} Ticker).')


if __name__ == '__main__':
    main()
