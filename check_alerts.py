import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "matplotlib", "deep-translator", "-q"])

import json
import os
import smtplib
import base64
import io
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import yfinance as yf
from deep_translator import GoogleTranslator
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── News-Abruf ────────────────────────────────────────────

def fetch_news(ticker, max_specific=5, max_general=5):
    """
    Holt News via yfinance, übersetzt ins Deutsche.
    Gibt {'specific': [...], 'general': [...]} zurück.
    specific  = Artikel wo ticker primär getaggt ist (stockTickers ≤ 3)
    general   = Branchen-/Markt-News aus dem gleichen Feed
    Fallback: wenn keine spezifischen gefunden, erste 5 / nächste 5 aus dem Feed.
    """
    try:
        raw = yf.Ticker(ticker).news or []
        ticker_upper = ticker.upper().replace('.DE', '')
        all_parsed = []

        for item in raw:
            if len(all_parsed) >= max_specific + max_general:
                break
            content = item.get('content', {}) or {}
            title = content.get('title') or item.get('title', '')
            url = (content.get('canonicalUrl', {}) or {}).get('url') or \
                  (content.get('clickThroughUrl', {}) or {}).get('url') or \
                  item.get('link', '')
            if not title or not url:
                continue
            publisher = (content.get('provider') or {}).get('displayName') or item.get('publisher', '')
            pub_time = content.get('pubDate') or ''
            if pub_time:
                date_str = pub_time[:10]
            else:
                ts = item.get('providerPublishTime', 0)
                date_str = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d') if ts else ''

            tagged = [t.get('symbol', '').upper() for t in
                      (content.get('finance') or {}).get('stockTickers', [])]
            if not tagged:
                tagged = [t.upper() for t in item.get('relatedTickers', [])]

            is_specific = ticker_upper in tagged and len(tagged) <= 3

            try:
                title = GoogleTranslator(source='auto', target='de').translate(title)
            except Exception:
                pass

            all_parsed.append({
                'entry': {'title': title, 'url': url, 'publisher': publisher, 'date_str': date_str},
                'is_specific': is_specific,
            })

        # Tag-basierter Split
        specific, general = [], []
        for p in all_parsed:
            if p['is_specific'] and len(specific) < max_specific:
                specific.append(p['entry'])
            elif not p['is_specific'] and len(general) < max_general:
                general.append(p['entry'])

        # Fallback: wenn kein einziger aktienspezifischer Artikel gefunden wurde,
        # erste 5 Artikel als specific, nächste 5 als general verwenden
        if not specific:
            flat = [p['entry'] for p in all_parsed]
            specific = flat[:max_specific]
            general  = flat[max_specific:max_specific + max_general]

        return {'specific': specific, 'general': general}
    except Exception as e:
        print(f'  News-Abruf für {ticker} fehlgeschlagen: {e}')
        return {'specific': [], 'general': []}


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


def _gws_core(swing_highs, swing_lows, closes, n):
    """Kernlogik: tiefere Tiefs erkennen → GWS = höchstes Hoch dazwischen."""
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
        for i in range(gws_high['idx'] + 1, n):
            if closes[i] > gws_high['price']:
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
        ticker         = alert['ticker']
        display_ticker = ticker.replace('.DE', '') if ticker.endswith('.DE') else ticker
        score    = alert['score']
        info     = alert['info']
        source   = alert.get('source', 'QQQ')

        w_dot  = dot_html(info['weekly'], alert.get('new_weekly', False))
        d_dot  = dot_html(info['daily'],  alert.get('new_daily',  False))
        h4_dot = dot_html(info['h4'],     alert.get('new_h4',     False))
        top20_badge = ('<span style="background:#1e3a5f;color:#60a5fa;padding:2px 7px;'
                       'border-radius:10px;font-size:10px;font-weight:bold">TOP&nbsp;20</span>&nbsp;'
                       if alert.get('in_top20') else '')

        if source == 'DAX':
            dashboard_url   = 'https://dguertler.github.io/Rel.-Strength/dax.html'
            dashboard_label = 'DAX-Dashboard'
        elif source == 'SPX':
            dashboard_url   = 'https://dguertler.github.io/Rel.-Strength/sp500.html'
            dashboard_label = 'S&P 500-Dashboard'
        else:
            dashboard_url   = 'https://dguertler.github.io/Rel.-Strength/'
            dashboard_label = 'Nasdaq-Dashboard'

        html_parts.append(f"""
  <div style="margin:0 0 28px;padding:16px;
              background:#160303;border:1px solid #ef4444;
              border-left:4px solid #ef4444;border-radius:8px">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
      <span style="font-size:18px">&#128293;</span>
      <span style="font-size:16px;font-weight:bold;color:#fca5a5">{display_ticker}</span>
      <span style="font-size:11px;color:#64748b">({source})</span>
      <span style="margin-left:auto;font-size:11px;color:#94a3b8;display:flex;align-items:center;gap:6px">
        {top20_badge}RS-Score:&nbsp;<strong style="color:#f1f5f9">{score:.1f}</strong>
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

        news = alert.get('news', {})
        specific_news = news.get('specific', []) if isinstance(news, dict) else []
        general_news  = news.get('general',  []) if isinstance(news, dict) else []

        def news_block(items, label, accent_color, bg_color, icon):
            if not items:
                return
            html_parts.append(
                f'    <div style="margin-top:12px;padding:10px 12px;'
                f'background:{bg_color};border-left:3px solid {accent_color};border-radius:4px">\n'
            )
            html_parts.append(
                f'      <div style="font-size:10px;color:{accent_color};'
                f'margin-bottom:7px;letter-spacing:1px;font-weight:bold">'
                f'{icon}&nbsp;{label}</div>\n'
            )
            for n in items:
                date_label      = f'<span style="color:#475569">{n["date_str"]}</span>&nbsp;&middot;&nbsp;' if n['date_str'] else ''
                publisher_label = f'<span style="color:#475569">{n["publisher"]}</span>&nbsp;&mdash;&nbsp;' if n['publisher'] else ''
                html_parts.append(
                    f'      <div style="margin-bottom:6px;font-size:11px;line-height:1.4">'
                    f'{date_label}{publisher_label}'
                    f'<a href="{n["url"]}" style="color:#93c5fd;text-decoration:none">{n["title"]}</a>'
                    f'</div>\n'
                )
            html_parts.append('    </div>\n')

        news_block(specific_news, f'NEWS – {display_ticker}',
                   accent_color='#3b82f6', bg_color='#0c1929', icon='&#9679;')
        news_block(general_news,  'BRANCHE / MARKT',
                   accent_color='#94a3b8', bg_color='#0f172a', icon='&#9675;')

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

    with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_addr, msg.as_bytes())

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


# ── Hauptprogramm ───────────────────────────────────────────────

def process_json(json_path, source_label, prev_states, today_str):
    """
    Lädt eine RS-JSON-Datei, berechnet Punkte, gibt neue Zustände
    und eine Liste von Alert-Dicts zurück.
    """
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

        # Auslöser: genau 2 → 3, nur für Top-20-Aktien des Index
        if prev_points == 2 and info['points'] == 3 and ticker in top20_set:
            print(f'  ALERT: {ticker} ({source_label})  {prev_points} → {info["points"]} Punkte')

            # Welcher Punkt ist neu hinzugekommen?
            new_w  = info['weekly'] and not prev.get('weekly', False)
            new_d  = info['daily']  and not prev.get('daily',  False)
            new_h4 = info['h4']     and not prev.get('h4',     False)

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

            news = fetch_news(ticker)
            alerts.append({
                'ticker':          ticker,
                'score':           score,
                'info':            info,
                'source':          source_label,
                'charts':          charts,
                'new_weekly':      new_w,
                'new_daily':       new_d,
                'new_h4':          new_h4,
                'weekly_bar_date': _breakout_date(entry.get('ohlcv_w',   []), info['struct_w']),
                'daily_bar_date':  _breakout_date(entry.get('ohlcv',     []), info['struct_d']),
                'h4_bar_date':     _breakout_date(entry.get('ohlcv_4h',  []), info['struct_4h']),
                'news':            news,
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
    score  = entry.get('score', 0)
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
        'news':       fetch_news(ticker),
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


def main():
    test_mode = '--test' in sys.argv or os.environ.get('ALERT_TEST_MODE', '') == 'true'

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

    print(f'check_alerts.py  –  {today_str}')
    print(f'Vorheriger Zustand: {len(prev_states)} Ticker')

    all_new_states = {}
    all_alerts     = []

    # US-Aktien (QQQ)
    print('\n── US-Aktien (rs_full.json) ──')
    new_us, alerts_us = process_json('rs_full.json', 'QQQ', prev_states, today_str)
    all_new_states.update(new_us)
    all_alerts.extend(alerts_us)

    # DAX-Aktien
    print('\n── DAX-Aktien (rs_dax.json) ──')
    new_dax, alerts_dax = process_json('rs_dax.json', 'DAX', prev_states, today_str)
    all_new_states.update(new_dax)
    all_alerts.extend(alerts_dax)

    # S&P 500 Aktien
    print('\n── S&P 500 (rs_sp500.json) ──')
    new_sp500, alerts_sp500 = process_json('rs_sp500.json', 'SPX', prev_states, today_str)
    all_new_states.update(new_sp500)
    all_alerts.extend(alerts_sp500)

    # Bereits heute gemeldete Ticker herausfiltern
    fresh_alerts = [a for a in all_alerts
                    if alerted.get(a['ticker']) != today_str]

    print(f'\nAlertes gesamt: {len(all_alerts)}  '
          f'(davon neu heute: {len(fresh_alerts)})')

    if fresh_alerts:
        send_alert_email(fresh_alerts, smtp_host, smtp_port,
                         smtp_user, smtp_pass, to_addr)
        signals = load_signals()
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
    else:
        print('Keine neuen 2→3-Übergänge heute.')

    # Zustand speichern
    state['states']  = all_new_states
    state['alerted'] = alerted
    save_state(state)
    print(f'Zustand gespeichert ({len(all_new_states)} Ticker).')


if __name__ == '__main__':
    main()
