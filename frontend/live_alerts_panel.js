// Echte Live-Bilanz der verschickten Breakout-Alerts (früher auf B-HISTORIE),
// jetzt oben auf B-ÜBERSICHT. Eigener Gültigkeitsbereich, damit die Namen nicht
// mit dem Seiten-Skript kollidieren.
(() => {
const { useState, useEffect } = React;
const green = '#4ade80', red = '#f87171', amber = '#fbbf24', neutral = '#64748b';
const pnlColor = v => v > 0 ? green : v < 0 ? red : neutral;
const pfColor  = v => v == null ? neutral : v >= 1.5 ? green : v >= 1 ? amber : red;
const num = (v, d = 1) => v == null ? '–' : v.toLocaleString('de-DE', { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (v, d = 1) => v == null ? '–' : (v >= 0 ? '+' : '') + num(v, d) + ' %';
const eur = v => v == null ? '–' : (v >= 0 ? '+' : '−') + Math.round(Math.abs(v)).toLocaleString('de-DE') + ' €';
const eurAbs = v => v == null ? '–' : Math.round(v).toLocaleString('de-DE') + ' €';

function Tile({ label, value, color, sub }) {
  return (
    <div className="card" style={{ flex: '1 1 150px', minWidth: 140 }}>
      <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color || '#e2e8f0', fontFamily: 'monospace' }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

const LIVE_GROUPS = {
  QQQ: 'NASDAQ-100', SPX: 'S&P 500', alle: 'Beide Indizes', nur4H: 'nur 4H-Auslöser (Backtest-Regel)',
  ohneNaeherung: 'nur exakt belegte Alerts (ab Mitte Mai)',
};

function PfStages({ stages, live }) {
  if (!stages) return null;
  const rows = [...stages.stages, { label: `jetzt · echte verschickte Alerts (${live.generated})`, now: true, ...live.groups }];
  const cell = (g) => (
    <>
      <td>{g ? `${g.nTrades} (${g.nOpen})` : '–'}</td>
      <td style={{ color: pfColor(g?.profitFactor), fontWeight: 700 }}>{num(g?.profitFactor, 2)}</td>
      <td style={{ color: pfColor(g?.profitFactorClosed) }}>{num(g?.profitFactorClosed, 2)}</td>
      <td style={{ color: pnlColor(g?.totalPnl) }}>{eur(g?.totalPnl)}</td>
    </>
  );
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>Vorher / Nachher: PF seit Live-Start je Korrekturstand</div>
      <div className="note" style={{ marginBottom: 8 }}>
        Die früheren Stände simulierten die Einstiege selbst (Wochenlauf, nur 4H, Kauf am Folgetag) und lagen
        deshalb neben den echten Alerts. Maßgeblich ist die letzte Zeile.
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table>
          <thead>
            <tr><th>Stand</th>{['NASDAQ-100', 'S&P 500', 'Beide'].map(h => <th key={h} colSpan="4" style={{ textAlign: 'center' }}>{h}</th>)}</tr>
            <tr><th></th>{[0, 1, 2].map(i => <React.Fragment key={i}><th>Trades (offen)</th><th>PF</th><th>PF abgeschl.</th><th>Σ P&L</th></React.Fragment>)}</tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="data-row" style={r.now ? { fontWeight: 700 } : undefined}>
                <td style={{ whiteSpace: 'nowrap' }}>{r.label}</td>{cell(r.QQQ)}{cell(r.SPX)}{cell(r.alle)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LiveAlerts({ live, stages }) {
  const [show, setShow] = useState(false);
  if (!live) return null;
  const row = (k) => {
    const g = live.groups[k];
    if (!g) return null;
    return (
      <tr key={k} className="data-row">
        <td style={{ fontWeight: k === 'QQQ' || k === 'SPX' ? 700 : 400 }}>{LIVE_GROUPS[k]}</td>
        <td>{g.nTrades} ({g.nOpen})</td>
        <td>{num(g.winrate)} %</td>
        <td style={{ color: pfColor(g.profitFactor), fontWeight: 700 }}>{num(g.profitFactor, 2)}</td>
        <td style={{ color: pfColor(g.profitFactorClosed) }}>{num(g.profitFactorClosed, 2)}</td>
        <td style={{ color: pnlColor(g.avgReturnPerTrade) }}>{pct(g.avgReturnPerTrade)}</td>
        <td style={{ color: pnlColor(g.returnOnInvested) }}>{pct(g.returnOnInvested)}</td>
        <td style={{ color: pnlColor(g.totalPnl) }}>{eur(g.totalPnl)}</td>
      </tr>
    );
  };
  return (
    <div className="card" style={{ marginBottom: 20, borderColor: '#1d4ed8' }}>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>Echte Live-Alerts seit {live.firstAlert}</div>
      <div className="note" style={{ marginBottom: 10 }}>
        Jeder tatsächlich per Mail/Telegram verschickte Breakout-Alert ({live.alertsSent} Alerts) als Trade: Kauf zur
        Eröffnung am Alert-Tag, Stopp und Ausstieg wie in der Backtest-Engine, 10.000 € je Signal, max. 1.000 € Risiko,
        eine Position je Titel ({live.skipped.position_offen} Alerts fielen in eine laufende Position). Welche Alerts
        verschickt wurden, stammt aus der Git-Historie (Top 20 zum Versandzeitpunkt); vor Mitte Mai 2026 angenähert.
        PF inkl. offener Positionen, daneben nur abgeschlossene.
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table>
          <thead><tr><th>Gruppe</th><th>Trades (offen)</th><th>Treffer</th><th>PF</th><th>PF abgeschl.</th>
            <th>Ø/Trade</th><th>Rendite auf Einsatz</th><th>Σ P&L</th></tr></thead>
          <tbody>{Object.keys(LIVE_GROUPS).map(row)}</tbody>
        </table>
      </div>
      <PfStages stages={stages} live={live} />
      <button onClick={() => setShow(!show)}
        style={{ marginTop: 10, background: 'transparent', border: '1px solid #334155', borderRadius: 6,
          padding: '4px 12px', color: '#94a3b8', fontFamily: 'monospace', fontSize: 12, cursor: 'pointer' }}>
        {show ? 'Trades ausblenden' : `Alle ${live.trades.length} Trades zeigen`}
      </button>
      {show && (
        <div style={{ overflow: 'auto', maxHeight: 420, marginTop: 10 }}>
          <table>
            <thead><tr><th>Ticker</th><th>Index</th><th>Auslöser</th><th>Alert</th><th>Ausstieg</th><th>Rendite</th><th>P&L</th></tr></thead>
            <tbody>
              {[...live.trades].reverse().map((t, i) => (
                <tr key={i} className="data-row">
                  <td style={{ fontWeight: 700 }}>{t.ticker}</td>
                  <td style={{ color: '#94a3b8' }}>{t.source === 'QQQ' ? 'NDX' : 'SPX'}</td>
                  <td style={{ color: '#94a3b8' }}>{t.trigger}</td>
                  <td>{t.alertDate}{t.basis === 'naeherung' ? '*' : ''}</td>
                  <td style={{ color: t.isOpen ? amber : '#e2e8f0' }}>{t.isOpen ? 'offen' : t.exitDate}</td>
                  <td style={{ color: pnlColor(t.pnlPct) }}>{pct(t.pnlPct)}</td>
                  <td style={{ color: pnlColor(t.pnl) }}>{eur(t.pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


function LivePanel() {
  const [live, setLive] = useState(null);
  const [stages, setStages] = useState(null);
  useEffect(() => {
    fetch('data/live_alerts_performance.json', { cache: 'no-store' })
      .then(r => (r.ok ? r.json() : null)).then(setLive).catch(() => setLive(null));
    fetch('data/live_pf_stages.json', { cache: 'no-store' })
      .then(r => (r.ok ? r.json() : null)).then(setStages).catch(() => setStages(null));
  }, []);
  return <div style={{ maxWidth: 1400, margin: '0 auto', padding: '16px 12px 0' }}><LiveAlerts live={live} stages={stages} /></div>;
}
ReactDOM.createRoot(document.getElementById('live-root')).render(<LivePanel />);
})();
