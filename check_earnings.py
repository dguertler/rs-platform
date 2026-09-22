import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "matplotlib", "lxml", "deep-translator", "requests", "-q"])

import json
import os
import smtplib
import base64
import io
import sys
from datetime import datetime, timedelta, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import yfinance as yf
import pandas as pd
from deep_translator import GoogleTranslator

# ── Konfiguration ─────────────────────────────────────────────────────────────

# Schwellen und Gate-Logik liegen in earnings_gate.py (Single Source of Truth
# für alle drei Scanner). Re-Export, damit bestehende Importe weiter greifen.
from earnings_gate import (          # noqa: E402  (nach dem pip-install-Block)
    MIN_PRICE_JUMP, MIN_EPS_SURPRISE, MIN_REACTION_JUMP,
    TRIGGER_EPS_BEAT, TRIGGER_PRICE_REACTION,
    detect_eps_oneoff, evaluate_gate,
)

# ── News-Abruf ────────────────────────────────────────────────────────────────

def fetch_news(ticker, max_specific=5, max_general=5):
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

        specific, general = [], []
        for p in all_parsed:
            if p['is_specific'] and len(specific) < max_specific:
                specific.append(p['entry'])
            elif not p['is_specific'] and len(general) < max_general:
                general.append(p['entry'])

        if not specific:
            flat = [p['entry'] for p in all_parsed]
            specific = flat[:max_specific]
            general  = flat[max_specific:max_specific + max_general]

        return {'specific': specific, 'general': general}
    except Exception as e:
        print(f'  News-Abruf für {ticker} fehlgeschlagen: {e}')
        return {'specific': [], 'general': []}


# ── Chart-Rendering ───────────────────────────────────────────────────────────

BG_DARK  = '#07090f'
BG_PANEL = '#0a0f1e'
BULL_CLR = '#4ade80'
BEAR_CLR = '#f87171'
GWS_CLR  = '#f59e0b'
TICK_CLR = '#475569'
GRID_CLR = '#1e293b'
TEXT_CLR = '#e2e8f0'


def render_chart(ohlcv, ticker, timeframe, gws_price=None, n_candles=40):
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
        ax.plot([i, i], [l, h], color=color, linewidth=0.8, zorder=1)
        body_h = max(abs(cl - o), (h - l) * 0.01)
        body_y = min(cl, o)
        rect = mpatches.Rectangle(
            (i - 0.35, body_y), 0.7, body_h,
            facecolor=color, edgecolor=color, zorder=2
        )
        ax.add_patch(rect)

    if gws_price:
        ax.axhline(gws_price, color=GWS_CLR, linewidth=1.2, linestyle='--',
                   label=f'GWS  {gws_price:.2f}', zorder=3)

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
        ax.legend(loc='upper left', facecolor=BG_PANEL,
                  edgecolor=GRID_CLR, labelcolor=GWS_CLR, fontsize=8)

    buf = io.BytesIO()
    fig.tight_layout(pad=0.5)
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight',
                facecolor=BG_DARK)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


# ── Kurssprung ermitteln ──────────────────────────────────────────────────────

def get_price_jump(ohlcv, target_date_str):
    closes = [(c['d'][:10], c['c']) for c in ohlcv if c.get('c')]
    if len(closes) < 2:
        return None, None, None
    for i in range(len(closes) - 1, 0, -1):
        day, close = closes[i]
        if day == target_date_str:
            prev_close = closes[i - 1][1]
            return close / prev_close - 1, close, prev_close
    return None, None, None


# ── Earnings-Daten via yfinance ───────────────────────────────────────────────

def get_earnings_surprise(ticker, target_date_str):
    try:
        tk = yf.Ticker(ticker)
        # limit=40 deckt ~10 Quartale ab; Standard (12) reicht für historische Tests nicht
        try:
            ed = tk.get_earnings_dates(limit=40)
        except Exception:
            ed = tk.earnings_dates
        if ed is None or ed.empty:
            return None

        ed = ed.copy()
        # Timezone entfernen bevor mit naivem Timestamp verglichen wird
        ed.index = pd.to_datetime(ed.index).normalize().tz_localize(None)

        target_dt = pd.Timestamp(target_date_str)

        # ±1 Handelstag: AMC-Meldungen am Vortag wirken sich am target_date aus
        window = [target_dt - pd.Timedelta(days=1), target_dt]
        mask = (ed.index >= window[0]) & (ed.index <= window[1])
        hits = ed[mask]

        if hits.empty:
            return None

        row = hits.iloc[0]
        eps_est    = row.get('EPS Estimate')
        eps_actual = row.get('Reported EPS')
        surprise   = row.get('Surprise(%)')

        if pd.isna(surprise) and not pd.isna(eps_est) and not pd.isna(eps_actual) \
                and eps_est != 0:
            surprise = (eps_actual - eps_est) / abs(eps_est) * 100

        if pd.isna(surprise):
            return None

        # EPS-Historie der Vorquartale (jüngstes zuerst) für die
        # Einmaleffekt-Prüfung — alles, was älter ist als der Treffer.
        prior_eps = []
        try:
            older = ed[ed.index < hits.index[0]].sort_index(ascending=False)
            for val in older.get('Reported EPS', pd.Series(dtype=float)):
                if not pd.isna(val):
                    prior_eps.append(float(val))
        except Exception as he:
            print(f'  EPS-Historie-Fehler {ticker}: {he}')

        # YoY-Umsatzvergleich: letztes Quartal vs. Vorjahresquartal
        revenue_growth_yoy = None
        _rev_labels = ('Total Revenue', 'Revenue', 'Operating Revenue',
                       'Total Revenues', 'Revenues', 'Net Revenue')
        try:
            def _find_rev_row(df):
                for lbl in _rev_labels:
                    if lbl in df.index:
                        return df.loc[lbl]
                return None

            # Primär: Quartalsdaten (mindestens 5 Quartale = echtes YoY)
            fins = tk.quarterly_financials
            if fins is not None and not fins.empty:
                rev_row = _find_rev_row(fins)
                if rev_row is not None and len(rev_row) >= 5:
                    r0, r1 = rev_row.iloc[0], rev_row.iloc[4]
                    if pd.notna(r0) and pd.notna(r1) and r1 != 0:
                        revenue_growth_yoy = float((r0 - r1) / abs(r1))

            # Fallback: Jahresdaten (fast immer 4 Jahre verfügbar)
            if revenue_growth_yoy is None:
                for ann_attr in ('income_stmt', 'financials'):
                    ann = getattr(tk, ann_attr, None)
                    if ann is not None and not ann.empty:
                        rev_row = _find_rev_row(ann)
                        if rev_row is not None and len(rev_row) >= 2:
                            r0, r1 = rev_row.iloc[0], rev_row.iloc[1]
                            if pd.notna(r0) and pd.notna(r1) and r1 != 0:
                                revenue_growth_yoy = float((r0 - r1) / abs(r1))
                        break

        except Exception as re:
            print(f'  revenue-Fehler {ticker}: {re}')

        eps_actual_val = float(eps_actual) if not pd.isna(eps_actual) else None
        eps_distorted = detect_eps_oneoff(eps_actual_val, prior_eps, revenue_growth_yoy)
        if eps_distorted:
            print(f'  Hinweis {ticker}: EPS {eps_actual_val} weicht stark von der '
                  f'Quartalshistorie {prior_eps[:4]} ab — Surprise gilt als verzerrt')

        return {
            'date':               str(hits.index[0].date()),
            'eps_estimate':       float(eps_est)    if not pd.isna(eps_est)    else None,
            'eps_actual':         eps_actual_val,
            'surprise_pct':       float(surprise),
            'revenue_growth_yoy': revenue_growth_yoy,
            'eps_distorted':      eps_distorted,
        }

    except Exception as e:
        print(f'  earnings-Fehler {ticker}: {e}')
        return None


# ── GWS-Analyse ───────────────────────────────────────────────────────────────

def _find_swing_points(highs, lows, n, window=2):
    swing_highs, swing_lows = [], []
    for i in range(window, n - window):
        if all(highs[i] >= highs[i-k] and highs[i] >= highs[i+k] for k in range(1, window+1)):
            swing_highs.append({'idx': i, 'price': highs[i]})
        if all(lows[i] <= lows[i-k] and lows[i] <= lows[i+k] for k in range(1, window+1)):
            swing_lows.append({'idx': i, 'price': lows[i]})
    return swing_highs, swing_lows


def get_gws_price(ohlcv, window=2):
    if not ohlcv or len(ohlcv) < 10:
        return None
    n = len(ohlcv)
    highs  = [c['h'] for c in ohlcv]
    lows   = [c['l'] for c in ohlcv]
    swing_highs, swing_lows = _find_swing_points(highs, lows, n, window)
    candidates = []
    for j in range(1, len(swing_lows)):
        if swing_lows[j]['price'] < swing_lows[j-1]['price']:
            hochs = [h for h in swing_highs
                     if swing_lows[j-1]['idx'] < h['idx'] < swing_lows[j]['idx']]
            if hochs:
                candidates.append(max(hochs, key=lambda h: h['price']))
    return candidates[-1]['price'] if candidates else None


# ── E-Mail versenden ──────────────────────────────────────────────────────────

def send_earnings_email(alerts, smtp_host, smtp_port, smtp_user, smtp_pass, to_addr, subject_prefix=''):
    today_str = datetime.now().strftime('%d.%m.%Y')
    subject   = f'{subject_prefix}Earnings-Überraschung {today_str}: {len(alerts)} Aktie(n) mit starkem Beat'

    msg = MIMEMultipart('related')
    msg['Subject'] = subject
    msg['From']    = smtp_user
    msg['To']      = to_addr

    html_parts = [f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="background:#060b14;color:#e2e8f0;font-family:monospace;
             padding:24px;max-width:780px;margin:0 auto">
  <h2 style="color:#86efac;margin:0 0 4px">
    Earnings-Überraschung &mdash; {today_str}
  </h2>
  <p style="color:#64748b;margin:0 0 24px;font-size:12px">
    Aktien mit &ge;{MIN_EPS_SURPRISE:.0f}&nbsp;% EPS-Surprise &ndash; oder
    &ge;{MIN_REACTION_JUMP*100:.0f}&nbsp;% Kursreaktion bei einem RS-getrackten Titel:
  </p>
"""]

    cid_counter = 0
    inline_imgs = []

    for a in alerts:
        ticker   = a['ticker']
        display  = ticker.replace('.DE', '') if ticker.endswith('.DE') else ticker
        source   = a['source']
        score    = a['score']
        score_str = f"{score:.1f}" if isinstance(score, (int, float)) else "–"
        jump_pct = a['jump_pct'] * 100
        surprise = a['surprise_pct']
        eps_est  = a['eps_estimate']
        eps_act  = a['eps_actual']

        # Kanonische App-Origin (gleiche Origin wie Login + Analyse), damit der
        # Login beim Klick aufs Dashboard erhalten bleibt — identisch zu check_alerts.py.
        _base_url = os.environ.get('FRONTEND_URL', os.environ.get('APP_URL', 'https://dguertler.github.io/rs-platform')).rstrip('/')
        if source == 'SPX':
            dash_url, dash_label = f'{_base_url}/sp500.html', 'S&P 500-Dashboard'
        else:
            dash_url, dash_label = f'{_base_url}/', 'Nasdaq-Dashboard'

        eps_est_str = f'{eps_est:.2f}' if eps_est is not None else '–'
        eps_act_str = f'{eps_act:.2f}' if eps_act is not None else '–'
        rev_yoy     = a.get('revenue_growth_yoy')
        if rev_yoy is not None:
            rev_sign    = '+' if rev_yoy >= 0 else ''
            rev_clr     = '#4ade80' if rev_yoy >= 0 else '#f87171'
            rev_str     = f'<span><span style="color:#64748b">Umsatz YoY:</span>&nbsp;<strong style="color:{rev_clr}">{rev_sign}{rev_yoy*100:.1f}&nbsp;%</strong></span>'
        else:
            rev_str     = '<span style="color:#64748b">Umsatz YoY: n/a</span>'

        # Auslöser-Badge: macht sichtbar, warum der Alert kam — bei
        # Mega-Caps trägt die Kursreaktion, nicht die EPS-Surprise.
        if a.get('trigger') == TRIGGER_PRICE_REACTION:
            trigger_str = ('<span style="font-size:10px;padding:2px 8px;border-radius:10px;'
                           'background:#1e3a5f;color:#93c5fd">Kursreaktion</span>')
        else:
            trigger_str = ('<span style="font-size:10px;padding:2px 8px;border-radius:10px;'
                           'background:#3f2d0a;color:#fbbf24">EPS-Beat</span>')
        if a.get('eps_distorted'):
            trigger_str += ('&nbsp;<span style="font-size:10px;padding:2px 8px;'
                            'border-radius:10px;background:#3f1d1d;color:#fca5a5">'
                            'EPS durch Einmaleffekt verzerrt</span>')

        html_parts.append(f"""
  <div style="margin:0 0 28px;padding:16px;
              background:#061a0e;border:1px solid #22c55e;
              border-left:4px solid #22c55e;border-radius:8px">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
      <span style="font-size:18px">&#128200;</span>
      <span style="font-size:16px;font-weight:bold;color:#86efac">{display}</span>
      <span style="font-size:11px;color:#64748b">({source})</span>
      {trigger_str}
      <span style="margin-left:auto;font-size:11px;color:#94a3b8">
        RS-Score:&nbsp;<strong style="color:#f1f5f9">{score_str}</strong>
      </span>
    </div>
    <div style="font-size:12px;margin-bottom:8px;display:flex;gap:24px">
      <span><span style="color:#64748b">Kurssprung:</span>&nbsp;
        <strong style="color:#4ade80">{jump_pct:+.1f}&nbsp;%</strong></span>
      <span><span style="color:#64748b">EPS-Surprise:</span>&nbsp;
        <strong style="color:#fbbf24">{surprise:+.1f}&nbsp;%</strong></span>
      {rev_str}
    </div>
    <div style="font-size:11px;margin-bottom:10px;color:#94a3b8">
      EPS Schätzung:&nbsp;<strong>{eps_est_str}</strong>
      &nbsp;&nbsp;|&nbsp;&nbsp;
      EPS Ist:&nbsp;<strong style="color:#86efac">{eps_act_str}</strong>
      &nbsp;&nbsp;&nbsp;
      <a href="{dash_url}" style="color:#3b82f6;text-decoration:none">&rarr; {dash_label}</a>
    </div>
""")

        for chart_b64, _ in a.get('charts', []):
            if chart_b64:
                cid = f'echart_{cid_counter}'
                cid_counter += 1
                inline_imgs.append((cid, chart_b64))
                html_parts.append(
                    f'    <img src="cid:{cid}" '
                    f'style="width:100%;max-width:720px;display:block;'
                    f'margin:6px 0;border-radius:6px">\n'
                )

        news = a.get('news', {})
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

        news_block(specific_news, f'NEWS – {display}',
                   accent_color='#3b82f6', bg_color='#0c1929', icon='&#9679;')
        news_block(general_news,  'BRANCHE / MARKT',
                   accent_color='#94a3b8', bg_color='#0f172a', icon='&#9675;')

        html_parts.append('  </div>\n')

    html_parts.append("""
  <p style="font-size:10px;color:#334155;margin-top:24px">
    Generiert von RS-Dashboard &middot; check_earnings.py
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

    print(f'Earnings-Mail gesendet an {to_addr}')


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

SOURCES = [
    ('rs_full.json',     'QQQ'),
    ('rs_sp500.json',    'SPX'),
    ('rs_smallcap.json', 'SC600'),
]


def main():
    smtp_host = os.environ.get('SMTP_HOST', '')
    smtp_port = os.environ.get('SMTP_PORT', '587')
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    to_addr   = os.environ.get('ALERT_EMAIL_TO', '')

    if not all([smtp_host, smtp_user, smtp_pass, to_addr]):
        print('FEHLER: Bitte SMTP_HOST, SMTP_USER, SMTP_PASS und ALERT_EMAIL_TO setzen.')
        sys.exit(1)

    test_date = os.environ.get('TEST_DATE', '').strip()
    if test_date:
        yesterday_str = test_date
        print(f'check_earnings.py – TEST-MODUS, Datum: {yesterday_str}')
    else:
        today     = date.today()
        yesterday = today - timedelta(days=1)
        if yesterday.weekday() == 6:
            yesterday = yesterday - timedelta(days=2)
        elif yesterday.weekday() == 5:
            yesterday = yesterday - timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        print(f'check_earnings.py – Prüfe Earnings vom {yesterday_str}')

    all_alerts = []

    for json_path, source_label in SOURCES:
        if not os.path.exists(json_path):
            print(f'  {json_path} nicht gefunden – übersprungen')
            continue

        with open(json_path) as f:
            data = json.load(f)

        entries = data.get('data', [])
        print(f'\n── {source_label} ({json_path}): {len(entries)} Ticker ──')

        for entry in entries:
            ticker = entry['ticker']
            score  = entry.get('score', 0)
            ohlcv  = entry.get('ohlcv', [])

            jump, close_y, close_prev = get_price_jump(ohlcv, yesterday_str)
            if jump is None or jump < MIN_PRICE_JUMP:
                continue

            print(f'  Kurssprung {ticker}: +{jump*100:.1f}% – prüfe Earnings …')

            earnings = get_earnings_surprise(ticker, yesterday_str)
            if earnings is None:
                print(f'    → keine Earnings gefunden')
                continue

            surprise = earnings['surprise_pct']
            rev_yoy  = earnings.get('revenue_growth_yoy')
            print(f'    → Surprise: {surprise:.1f}%  |  Revenue YoY: {rev_yoy*100:.1f}%' if rev_yoy is not None else f'    → Surprise: {surprise:.1f}%  |  Revenue YoY: n/a')

            # RS-Ticker: Kursreaktions-Trigger zulässig (siehe earnings_gate.py)
            gate = evaluate_gate(jump, surprise, rev_yoy,
                                 eps_distorted=earnings.get('eps_distorted', False),
                                 rs_tracked=True)
            if not gate.passed:
                print(f'    → {gate.reason} – übersprungen')
                continue

            print(f'  ✓ ALERT [{gate.trigger}]: {ticker} ({source_label})  '
                  f'Sprung={jump*100:.1f}%  Surprise={surprise:.1f}%')

            gws_d  = get_gws_price(ohlcv)
            gws_w  = get_gws_price(entry.get('ohlcv_w', []), window=1)
            gws_4h = get_gws_price(entry.get('ohlcv_4h', []))

            w_b64  = render_chart(entry.get('ohlcv_w',  []), ticker, 'Weekly (letzten 30 Kerzen)',
                                  gws_price=gws_w,  n_candles=30)
            d_b64  = render_chart(ohlcv,               ticker, 'Daily (letzten 40 Kerzen)',
                                  gws_price=gws_d)
            h4_b64 = render_chart(entry.get('ohlcv_4h', []), ticker, '4H (letzten 60 Kerzen)',
                                  gws_price=gws_4h, n_candles=60)

            charts = []
            if w_b64:  charts.append((w_b64,  'Weekly'))
            if d_b64:  charts.append((d_b64,  'Daily'))
            if h4_b64: charts.append((h4_b64, '4H'))

            news = fetch_news(ticker)

            all_alerts.append({
                'ticker':             ticker,
                'score':              score,
                'source':             source_label,
                'jump_pct':           jump,
                'surprise_pct':       surprise,
                'eps_estimate':       earnings['eps_estimate'],
                'eps_actual':         earnings['eps_actual'],
                'revenue_growth_yoy': rev_yoy,
                'trigger':            gate.trigger,
                'eps_distorted':      earnings.get('eps_distorted', False),
                'charts':             charts,
                'news':               news,
            })

    all_alerts.sort(key=lambda a: a['score'] if a.get('score') is not None else float("-inf"), reverse=True)
    print(f'\nEarnings-Alerts gesamt: {len(all_alerts)}')

    if all_alerts:
        send_earnings_email(all_alerts, smtp_host, smtp_port, smtp_user, smtp_pass, to_addr)
        tg_token   = os.environ.get('TELEGRAM_TOKEN', '')
        tg_chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
        if tg_token:
            from telegram_handler import send_earnings_telegram, resolve_recipients
            tg_recipients = resolve_recipients(tg_chat_id)
            if tg_recipients:
                for a in all_alerts:
                    send_earnings_telegram(tg_token, tg_recipients, a)
    else:
        print('Keine Earnings-Überraschungen heute.')


if __name__ == '__main__':
    main()
