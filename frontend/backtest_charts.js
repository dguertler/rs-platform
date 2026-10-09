// Gemeinsame Chart-Bausteine für B-DETAILS (backtest.html) und B-DETAILS 2
// (backtest_history_details.html). Wird als <script type="text/babel" src>
// geladen; die React-Hooks (useState, useRef, …) deklariert die jeweilige Seite.

function ChartWeekly({ ohlcvW, structureW, chartId, benchOhlcv, benchLabel, signals = [], tradeMarkers = [] }) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);
  const W = 600, H = 260;
  const PL = 56, PR = 52, PT = 18, PB = 32;
  const cW = W - PL - PR, cH = H - PT - PB;
  const n = ohlcvW.length;
  const allH = ohlcvW.map(d => d.h), allL = ohlcvW.map(d => d.l);
  const rawMax = Math.max(...allH), rawMin = Math.min(...allL);
  const pad = (rawMax - rawMin) * 0.07;
  const maxP = rawMax + pad, minP = rawMin - pad, range = maxP - minP;
  const toY = p => PT + (1 - (p - minP) / range) * cH;
  const toX = i => PL + (i + 0.5) * (cW / n);
  const bW  = Math.max(2, cW / n * 0.65);

  const yTicks = [];
  for (let k = 0; k <= 5; k++) yTicks.push(minP + k * range / 5);

  // Monats-Labels für Weekly
  const monthLabels = [];
  let lastMonth = null;
  ohlcvW.forEach((d, i) => {
    const m = d.d.slice(0, 7);
    if (m !== lastMonth) { monthLabels.push({ i, label: d.d.slice(5,7)+"/"+d.d.slice(2,4) }); lastMonth = m; }
  });

  const { gwswHigh, breakoutIdx, breakoutPrice, broken, prevGwswHigh, prevBreakoutIdx } = structureW || {};

  // Index-Linie (grau) – normalisiert auf Aktien-Preisskala
  const benchLine = useMemo(() => {
    if (!benchOhlcv || !ohlcvW.length) return [];
    const benchMap = {};
    benchOhlcv.forEach(d => { benchMap[d.d] = d.c; });
    let stockRef = null, benchRef = null;
    for (const d of ohlcvW) {
      if (benchMap[d.d] != null) { stockRef = d.c; benchRef = benchMap[d.d]; break; }
    }
    if (!stockRef || !benchRef) return [];
    return ohlcvW.map((d, i) => {
      const bc = benchMap[d.d];
      return bc != null ? { i, price: stockRef * (bc / benchRef) } : null;
    }).filter(Boolean);
  }, [benchOhlcv, ohlcvW]);
  const gwswColor  = "#f59e0b"; // Amber für Weekly
  const gwswLineEnd = breakoutIdx !== null ? breakoutIdx : n - 1;

  const handleMouseMove = useCallback((e) => {
    const svg = svgRef.current; if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (W / rect.width);
    const idx = Math.round((mx - PL) / (cW / n) - 0.5);
    setHover(idx >= 0 && idx < n ? idx : null);
  }, [n, cW]);

  const hd = hover !== null ? ohlcvW[hover] : null;

  return (
    <div className="chart-wrap" style={{background:"#07090f",borderRadius:8,border:"1px solid #1e293b",overflow:"hidden"}}>
      <div style={{height:28,padding:"0 12px",display:"flex",alignItems:"center",gap:14,background:"#0a0f1e",borderBottom:"1px solid #1e293b",fontSize:10,fontFamily:"monospace"}}>
        {hd ? <>
          <span style={{color:"#475569"}}>{hd.d}</span>
          <span>O <span style={{color:"#e2e8f0"}}>{hd.o.toFixed(2)}</span></span>
          <span>H <span style={{color:"#4ade80"}}>{hd.h.toFixed(2)}</span></span>
          <span>L <span style={{color:"#f87171"}}>{hd.l.toFixed(2)}</span></span>
          <span>C <span style={{color:hd.c>=hd.o?"#4ade80":"#f87171",fontWeight:700}}>{hd.c.toFixed(2)}</span></span>
          <span style={{color:"#475569",marginLeft:"auto"}}>{hd.c>=hd.o?"▲":"▼"} {((hd.c-hd.o)/hd.o*100).toFixed(2)}%</span>
        </> : <span style={{color:"#334155"}}>Hover für Weekly-Details</span>}
      </div>

      <svg ref={svgRef} width="100%" viewBox={`0 0 ${W} ${H}`}
        onMouseMove={handleMouseMove} onMouseLeave={()=>setHover(null)} style={{cursor:"crosshair"}}>
        <defs>
          <linearGradient id={`bgW_${chartId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#22c55e" stopOpacity="0.10"/>
            <stop offset="100%" stopColor="#22c55e" stopOpacity="0.01"/>
          </linearGradient>
          <clipPath id={`clipW_${chartId}`}>
            <rect x={PL} y={PT} width={cW} height={cH}/>
          </clipPath>
        </defs>
        <rect x={PL} y={PT} width={cW} height={cH} fill="#07090f"/>

        {/* Gitter */}
        {yTicks.map((val, k) => {
          const y = toY(val);
          return <g key={k}>
            <line x1={PL} x2={PL+cW} y1={y} y2={y} stroke="#1a2235" strokeWidth="0.8"/>
            <text x={PL-5} y={y+3.5} textAnchor="end" fill="#334155" fontSize="9" fontFamily="monospace">{val.toFixed(0)}</text>
          </g>;
        })}

        {/* Monatstrennlinien */}
        {monthLabels.map(({i, label}) => (
          <g key={i}>
            <line x1={toX(i)} x2={toX(i)} y1={PT} y2={PT+cH} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,4" opacity="0.25"/>
            <text x={toX(i)} y={PT+cH+14} textAnchor="middle" fill="#334155" fontSize="8.5" fontFamily="monospace">{label}</text>
          </g>
        ))}

        {/* Breakout-Zone */}
        {breakoutIdx !== null && (
          <rect x={toX(breakoutIdx)} y={PT} width={PL+cW-toX(breakoutIdx)} height={cH} fill={`url(#bgW_${chartId})`}/>
        )}

        {/* Index-Linie (grau) */}
        {benchLine.length > 1 && (
          <polyline
            points={benchLine.map(({i, price}) => `${toX(i)},${toY(price)}`).join(' ')}
            fill="none" stroke="#64748b" strokeWidth="1.2" opacity="0.55"
            clipPath={`url(#clipW_${chartId})`}/>
        )}

        {/* Vorheriger GWS-W Break (gedimmt) */}
        {prevGwswHigh && (() => {
          const prevLineEnd = prevBreakoutIdx !== null ? prevBreakoutIdx : (gwswHigh ? gwswHigh.idx : n - 1);
          const y  = toY(prevGwswHigh.price);
          const x1 = toX(prevGwswHigh.idx);
          const x2 = toX(prevLineEnd);
          return <>
            <line x1={x1} x2={x2} y1={y} y2={y} stroke={gwswColor} strokeWidth="1.2" strokeDasharray="4,4" opacity="0.30"/>
          </>;
        })()}

        {/* Aktueller GWS-W */}
        {gwswHigh && (() => {
          const y  = toY(breakoutPrice ?? gwswHigh.price);
          const x1 = toX(gwswHigh.idx);
          const x2 = toX(gwswLineEnd);
          return <line x1={x1} x2={x2} y1={y} y2={y} stroke={gwswColor} strokeWidth="1.8" strokeDasharray="5,4"/>;
        })()}
                {/* Trend-Fallback: kein GWS aber höhere Hochs (Weekly) */}
        {broken && !gwswHigh && structureW?.swingHighs?.length >= 2 && (() => {
          const lastSH = structureW.swingHighs[structureW.swingHighs.length - 1];
          const y = toY(lastSH.price);
          return <>
            <line x1={PL} x2={PL+cW} y1={y} y2={y} stroke="#4ade80" strokeWidth="1.2" strokeDasharray="3,6" opacity="0.7"/>
            <text x={PL+6} y={y-4} fill="#4ade80" fontSize="8" fontFamily="monospace" opacity="0.8">Trend ↑</text>
          </>;
        })()}

        {/* Kerzen */}
        {ohlcvW.map((d, i) => {
          const bull = d.c >= d.o;
          const isBoc = i === breakoutIdx;
          const col  = bull ? "#22c55e" : "#ef4444";
          const bTop = toY(Math.max(d.o, d.c));
          const bH   = Math.max(1.5, toY(Math.min(d.o, d.c)) - bTop);
          const isHov = hover === i;
          return <g key={i}>
            <line x1={toX(i)} x2={toX(i)} y1={toY(d.h)} y2={toY(d.l)} stroke={col} strokeWidth={isHov?1.5:1} opacity={0.9}/>
            <rect x={toX(i)-bW/2} y={bTop} width={bW} height={bH}
              fill={col} opacity={isBoc?1:isHov?0.95:0.8}
              stroke={isBoc?gwswColor:"none"} strokeWidth={isBoc?1.2:0}/>
          </g>;
        })}

        {/* Trade-Marker */}
        {tradeMarkers.map((m, mi) => {
          const idx = ohlcvW.findIndex(d => d.d.slice(0,10) === (m.weeklyDate ?? m.date).slice(0,10));
          if (idx < 0) return null;
          const x = toX(idx);
          if (m.type === 'entry') {
            const yTip = Math.min(toY(ohlcvW[idx].l) + 3, PT + cH - 16);
            return <g key={`tm${mi}`}>
              <polygon points={`${x-5},${yTip+10} ${x+5},${yTip+10} ${x},${yTip}`} fill="#4ade80" opacity="0.95"/>
              <line x1={x} x2={x} y1={yTip+10} y2={Math.min(yTip+20, PT+cH)} stroke="#4ade80" strokeWidth="1.5"/>
            </g>;
          } else {
            const yTip = Math.max(toY(ohlcvW[idx].h) - 3, PT + 14);
            return <g key={`tm${mi}`}>
              <polygon points={`${x-5},${yTip-10} ${x+5},${yTip-10} ${x},${yTip}`} fill="#f87171" opacity="0.95"/>
              <line x1={x} x2={x} y1={yTip-10} y2={Math.max(yTip-20, PT)} stroke="#f87171" strokeWidth="1.5"/>
            </g>;
          }
        })}

        {/* Signal-Pfeile (Weekly-Chart: alle Timeframes) */}
        {signals.filter(s => s.weekly_bar_date).map((sig, si) => {
          const idx = ohlcvW.findIndex(d => d.d.slice(0,10) === sig.weekly_bar_date.slice(0,10));
          if (idx < 0) return null;
          const x = toX(idx);
          const yTip = Math.min(toY(ohlcvW[idx].l) + 4, PT + cH - 28);
          const lbl = [sig.weekly_bar_date&&'W', sig.daily_bar_date&&'D', sig.h4_bar_date&&'4H'].filter(Boolean).join('/');
          return <g key={si}>
            <rect x={x-6} y={yTip-2} width={12} height={22} rx={2} fill="#eab308" opacity={0.2}/>
            <polygon points={`${x-4},${yTip+8} ${x+4},${yTip+8} ${x},${yTip}`} fill="#eab308" opacity="0.95"/>
            <line x1={x} x2={x} y1={yTip+8} y2={yTip+18} stroke="#eab308" strokeWidth="1.5" opacity="0.95"/>
            <text x={x} y={yTip+28} textAnchor="middle" fill="#eab308" fontSize="7" fontFamily="monospace" opacity="0.9">{lbl}</text>
          </g>;
        })}

        {/* Aktueller Preis */}
        <line x1={PL} x2={PL+cW} y1={toY(ohlcvW[n-1].c)} y2={toY(ohlcvW[n-1].c)} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.45"/>
        <rect x={PL+cW+2} y={toY(ohlcvW[n-1].c)-8} width={46} height={15} rx="3" fill="#1e293b"/>
        <text x={PL+cW+25} y={toY(ohlcvW[n-1].c)+3} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">{ohlcvW[n-1].c.toFixed(2)}</text>

        {/* Crosshair */}
        {hover !== null && <>
          <line x1={toX(hover)} x2={toX(hover)} y1={PT} y2={PT+cH} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.5"/>
          <line x1={PL} x2={PL+cW} y1={toY(ohlcvW[hover].c)} y2={toY(ohlcvW[hover].c)} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.5"/>
          <rect x={PL-52} y={toY(ohlcvW[hover].c)-8} width={48} height={15} rx="3" fill="#1e293b"/>
          <text x={PL-28} y={toY(ohlcvW[hover].c)+3} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">{ohlcvW[hover].c.toFixed(2)}</text>
        </>}
        <rect x={PL} y={PT} width={cW} height={cH} fill="none" stroke="#1e293b" strokeWidth="0.8"/>
      </svg>

      <div style={{padding:"5px 12px",display:"flex",gap:14,alignItems:"center",background:"#0a0f1e",borderTop:"1px solid #0f172a",flexWrap:"wrap"}}>
        <div style={{display:"flex",alignItems:"center",gap:4}}>
          <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#f59e0b" strokeWidth="1.8" strokeDasharray="4,3"/></svg>
          <span style={{fontSize:9,color:"#64748b"}}>GWS-W</span>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:4}}>
          <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#f59e0b" strokeWidth="1.2" strokeDasharray="4,4" opacity="0.30"/></svg>
          <span style={{fontSize:9,color:"#64748b"}}>Letzter Break</span>
        </div>
        {benchLine.length > 1 && benchLabel && (
          <div style={{display:"flex",alignItems:"center",gap:4}}>
            <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#64748b" strokeWidth="1.2" opacity="0.55"/></svg>
            <span style={{fontSize:9,color:"#64748b"}}>{benchLabel}</span>
          </div>
        )}
        {signals.length > 0 && (
          <div style={{display:"flex",alignItems:"center",gap:4}}>
            <svg width="10" height="16"><polygon points="5,0 9,8 1,8" fill="#eab308"/><line x1="5" x2="5" y1="8" y2="16" stroke="#eab308" strokeWidth="1.5"/></svg>
            <span style={{fontSize:9,color:"#eab308"}}>Signal</span>
          </div>
        )}
        <div style={{marginLeft:"auto",fontSize:9,color:"#334155",fontFamily:"monospace"}}>{ohlcvW.length} Wochen · Weekly</div>
      </div>
    </div>
  );
}

// ── Daily Candlestick Chart ────────────────────────────────────────────────
function CandleChart({ ohlcv, structure, chartId, benchOhlcv, benchLabel, signals = [], tradeMarkers = [] }) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);
  const W = 600, H = 270;
  const PL = 56, PR = 52, PT = 18, PB = 32;
  const cW = W - PL - PR, cH = H - PT - PB;
  const n = ohlcv.length;
  const allH = ohlcv.map(d => d.h), allL = ohlcv.map(d => d.l);
  const rawMax = Math.max(...allH), rawMin = Math.min(...allL);
  const pad = (rawMax - rawMin) * 0.07;
  const maxP = rawMax + pad, minP = rawMin - pad, range = maxP - minP;
  const toY = p => PT + (1 - (p - minP) / range) * cH;
  const toX = i => PL + (i + 0.5) * (cW / n);
  const bW  = Math.max(2, cW / n * 0.65);

  const yTicks = [];
  for (let k = 0; k <= 5; k++) yTicks.push(minP + k * range / 5);

  const monthLabels = [];
  let lastMonth = null;
  ohlcv.forEach((d, i) => {
    const m = d.d.slice(0, 7);
    if (m !== lastMonth) { monthLabels.push({ i, label: d.d.slice(5,7)+"/"+d.d.slice(2,4) }); lastMonth = m; }
  });

  const { gwsdHigh, breakoutIdx, breakoutPrice, broken, prevGwsdHigh, prevBreakoutIdx } = structure || {};

  // Index-Linie (grau) – normalisiert auf Aktien-Preisskala
  const benchLine = useMemo(() => {
    if (!benchOhlcv || !ohlcv.length) return [];
    const benchMap = {};
    benchOhlcv.forEach(d => { benchMap[d.d] = d.c; });
    let stockRef = null, benchRef = null;
    for (const d of ohlcv) {
      if (benchMap[d.d] != null) { stockRef = d.c; benchRef = benchMap[d.d]; break; }
    }
    if (!stockRef || !benchRef) return [];
    return ohlcv.map((d, i) => {
      const bc = benchMap[d.d];
      return bc != null ? { i, price: stockRef * (bc / benchRef) } : null;
    }).filter(Boolean);
  }, [benchOhlcv, ohlcv]);
  const gwsdColor   = "#ef4444";
  const gwsdLineEnd = breakoutIdx !== null ? breakoutIdx : n - 1;

  const handleMouseMove = useCallback((e) => {
    const svg = svgRef.current; if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (W / rect.width);
    const idx = Math.round((mx - PL) / (cW / n) - 0.5);
    setHover(idx >= 0 && idx < n ? idx : null);
  }, [n, cW]);

  const hd = hover !== null ? ohlcv[hover] : null;

  return (
    <div className="chart-wrap" style={{background:"#07090f",borderRadius:8,border:"1px solid #1e293b",overflow:"hidden"}}>
      <div style={{height:28,padding:"0 12px",display:"flex",alignItems:"center",gap:14,background:"#0a0f1e",borderBottom:"1px solid #1e293b",fontSize:10,fontFamily:"monospace"}}>
        {hd ? <>
          <span style={{color:"#475569"}}>{hd.d}</span>
          <span>O <span style={{color:"#e2e8f0"}}>{hd.o.toFixed(2)}</span></span>
          <span>H <span style={{color:"#4ade80"}}>{hd.h.toFixed(2)}</span></span>
          <span>L <span style={{color:"#f87171"}}>{hd.l.toFixed(2)}</span></span>
          <span>C <span style={{color:hd.c>=hd.o?"#4ade80":"#f87171",fontWeight:700}}>{hd.c.toFixed(2)}</span></span>
          <span style={{color:"#475569",marginLeft:"auto"}}>{hd.c>=hd.o?"▲":"▼"} {((hd.c-hd.o)/hd.o*100).toFixed(2)}%</span>
        </> : <span style={{color:"#334155"}}>Hover für Daily-Details</span>}
      </div>

      <svg ref={svgRef} width="100%" viewBox={`0 0 ${W} ${H}`}
        onMouseMove={handleMouseMove} onMouseLeave={()=>setHover(null)} style={{cursor:"crosshair"}}>
        <defs>
          <linearGradient id={`bg_${chartId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#22c55e" stopOpacity="0.12"/>
            <stop offset="100%" stopColor="#22c55e" stopOpacity="0.01"/>
          </linearGradient>
          <clipPath id={`clipD_${chartId}`}>
            <rect x={PL} y={PT} width={cW} height={cH}/>
          </clipPath>
        </defs>
        <rect x={PL} y={PT} width={cW} height={cH} fill="#07090f"/>

        {/* Gitter */}
        {yTicks.map((val, k) => {
          const y = toY(val);
          return <g key={k}>
            <line x1={PL} x2={PL+cW} y1={y} y2={y} stroke="#1a2235" strokeWidth="0.8"/>
            <text x={PL-5} y={y+3.5} textAnchor="end" fill="#334155" fontSize="9" fontFamily="monospace">{val.toFixed(0)}</text>
          </g>;
        })}

        {/* Monatstrennlinien */}
        {monthLabels.map(({i, label}) => (
          <g key={i}>
            <line x1={toX(i)} x2={toX(i)} y1={PT} y2={PT+cH} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,4" opacity="0.25"/>
            <text x={toX(i)} y={PT+cH+14} textAnchor="middle" fill="#334155" fontSize="8.5" fontFamily="monospace">{label}</text>
          </g>
        ))}

        {/* Breakout-Zone */}
        {breakoutIdx !== null && (
          <rect x={toX(breakoutIdx)} y={PT}
            width={PL+cW-toX(breakoutIdx)} height={cH}
            fill={`url(#bg_${chartId})`}/>
        )}

        {/* Index-Linie (grau) */}
        {benchLine.length > 1 && (
          <polyline
            points={benchLine.map(({i, price}) => `${toX(i)},${toY(price)}`).join(' ')}
            fill="none" stroke="#64748b" strokeWidth="1.2" opacity="0.55"
            clipPath={`url(#clipD_${chartId})`}/>
        )}

        {/* Vorheriger GWS-D Break (gedimmt) */}
        {prevGwsdHigh && (() => {
          const prevLineEnd = prevBreakoutIdx !== null ? prevBreakoutIdx : (gwsdHigh ? gwsdHigh.idx : n - 1);
          const y  = toY(prevGwsdHigh.price);
          const x1 = toX(prevGwsdHigh.idx);
          const x2 = toX(prevLineEnd);
          return <>
            <line x1={x1} x2={x2} y1={y} y2={y} stroke="#ef4444" strokeWidth="1.2" strokeDasharray="4,4" opacity="0.35"/>
          </>;
        })()}

        {/* Aktueller GWS-D */}
        {gwsdHigh && (() => {
          const levelPrice = breakoutPrice ?? gwsdHigh.price;
          const y  = toY(levelPrice);
          const x1 = toX(gwsdHigh.idx);
          const x2 = toX(gwsdLineEnd);
          return <line x1={x1} x2={x2} y1={y} y2={y} stroke={gwsdColor} strokeWidth="1.8" strokeDasharray="5,4"/>;
        })()}

                {/* Trend-Fallback: kein GWS aber höhere Hochs (Daily) */}
        {broken && !gwsdHigh && structure?.swingHighs?.length >= 2 && (() => {
          const lastSH = structure.swingHighs[structure.swingHighs.length - 1];
          const y = toY(lastSH.price);
          return <>
            <line x1={PL} x2={PL+cW} y1={y} y2={y} stroke="#4ade80" strokeWidth="1.2" strokeDasharray="3,6" opacity="0.7"/>
            <text x={PL+6} y={y-4} fill="#4ade80" fontSize="8" fontFamily="monospace" opacity="0.8">Trend ↑</text>
          </>;
        })()}

        {/* Kerzen */}
        {ohlcv.map((d, i) => {
          const bull = d.c >= d.o;
          const isBoc = i === breakoutIdx;
          const col  = bull ? "#22c55e" : "#ef4444";
          const bTop = toY(Math.max(d.o, d.c));
          const bH   = Math.max(1.5, toY(Math.min(d.o, d.c)) - bTop);
          const isHov = hover === i;
          return <g key={i}>
            <line x1={toX(i)} x2={toX(i)} y1={toY(d.h)} y2={toY(d.l)} stroke={col} strokeWidth={isHov?1.5:1} opacity={0.9}/>
            <rect x={toX(i)-bW/2} y={bTop} width={bW} height={bH}
              fill={col} opacity={isBoc?1:isHov?0.95:0.8}
              stroke={isBoc?"#ef4444":"none"} strokeWidth={isBoc?1.2:0}/>
          </g>;
        })}

        {/* Trade-Marker mit SL-Linie */}
        {tradeMarkers.map((m, mi) => {
          const target = m.date.slice(0,10);
          let best = Infinity, idx = -1;
          ohlcv.forEach((d, i) => { const diff = Math.abs(new Date(d.d.slice(0,10)) - new Date(target)); if (diff < best) { best = diff; idx = i; } });
          if (idx < 0 || best > 2 * 86400000) return null;
          const x = toX(idx);
          if (m.type === 'entry') {
            const yTip = Math.min(toY(ohlcv[idx].l) + 3, PT + cH - 16);
            const ySL  = m.stopPrice != null ? toY(m.stopPrice) : null;
            const x2SL = Math.min(toX(idx + 5), PL + cW - 4);
            return <g key={`tm${mi}`}>
              <polygon points={`${x-5},${yTip+10} ${x+5},${yTip+10} ${x},${yTip}`} fill="#4ade80" opacity="0.95"/>
              <line x1={x} x2={x} y1={yTip+10} y2={Math.min(yTip+20, PT+cH)} stroke="#4ade80" strokeWidth="1.5"/>
              {ySL != null && ySL > PT && ySL < PT + cH && <>
                <line x1={x} x2={x2SL} y1={ySL} y2={ySL} stroke="#e2e8f0" strokeWidth="1.2" strokeDasharray="4,3" opacity="0.85"/>
                <text x={x2SL + 2} y={ySL + 3} fill="#e2e8f0" fontSize="8" fontFamily="monospace" opacity="0.85">SL</text>
              </>}
            </g>;
          } else {
            const yTip = Math.max(toY(ohlcv[idx].h) - 3, PT + 14);
            return <g key={`tm${mi}`}>
              <polygon points={`${x-5},${yTip-10} ${x+5},${yTip-10} ${x},${yTip}`} fill="#f87171" opacity="0.95"/>
              <line x1={x} x2={x} y1={yTip-10} y2={Math.max(yTip-20, PT)} stroke="#f87171" strokeWidth="1.5"/>
            </g>;
          }
        })}

        {/* Signal-Pfeile (Daily-Chart: alle Signale mit daily_bar_date) */}
        {signals.filter(s => s.daily_bar_date).map((sig, si) => {
          const idx = ohlcv.findIndex(d => d.d.slice(0,10) === sig.daily_bar_date.slice(0,10));
          if (idx < 0) return null;
          const x = toX(idx);
          const yTip = Math.min(toY(ohlcv[idx].l) + 4, PT + cH - 28);
          const lbl = [sig.weekly_bar_date&&'W', sig.daily_bar_date&&'D', sig.h4_bar_date&&'4H'].filter(Boolean).join('/');
          return <g key={si}>
            <rect x={x-6} y={yTip-2} width={12} height={22} rx={2} fill="#eab308" opacity={0.2}/>
            <polygon points={`${x-4},${yTip+8} ${x+4},${yTip+8} ${x},${yTip}`} fill="#eab308" opacity="0.95"/>
            <line x1={x} x2={x} y1={yTip+8} y2={yTip+18} stroke="#eab308" strokeWidth="1.5" opacity="0.95"/>
            <text x={x} y={yTip+28} textAnchor="middle" fill="#eab308" fontSize="7" fontFamily="monospace" opacity="0.9">{lbl}</text>
          </g>;
        })}

        {/* Aktueller Preis */}
        <line x1={PL} x2={PL+cW} y1={toY(ohlcv[n-1].c)} y2={toY(ohlcv[n-1].c)} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.45"/>
        <rect x={PL+cW+2} y={toY(ohlcv[n-1].c)-8} width={46} height={15} rx="3" fill="#1e293b"/>
        <text x={PL+cW+25} y={toY(ohlcv[n-1].c)+3} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">{ohlcv[n-1].c.toFixed(2)}</text>

        {/* Crosshair */}
        {hover !== null && <>
          <line x1={toX(hover)} x2={toX(hover)} y1={PT} y2={PT+cH} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.5"/>
          <line x1={PL} x2={PL+cW} y1={toY(ohlcv[hover].c)} y2={toY(ohlcv[hover].c)} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.5"/>
          <rect x={PL-52} y={toY(ohlcv[hover].c)-8} width={48} height={15} rx="3" fill="#1e293b"/>
          <text x={PL-28} y={toY(ohlcv[hover].c)+3} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">{ohlcv[hover].c.toFixed(2)}</text>
        </>}
        <rect x={PL} y={PT} width={cW} height={cH} fill="none" stroke="#1e293b" strokeWidth="0.8"/>
      </svg>

      <div style={{padding:"5px 12px",display:"flex",gap:14,alignItems:"center",background:"#0a0f1e",borderTop:"1px solid #0f172a",flexWrap:"wrap"}}>
        <div style={{display:"flex",alignItems:"center",gap:4}}>
          <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#ef4444" strokeWidth="1.8" strokeDasharray="4,3"/></svg>
          <span style={{fontSize:9,color:"#64748b"}}>GWS-D</span>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:4}}>
          <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#ef4444" strokeWidth="1.2" strokeDasharray="4,4" opacity="0.35"/></svg>
          <span style={{fontSize:9,color:"#64748b"}}>Letzter Break</span>
        </div>
        {benchLine.length > 1 && benchLabel && (
          <div style={{display:"flex",alignItems:"center",gap:4}}>
            <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#64748b" strokeWidth="1.2" opacity="0.55"/></svg>
            <span style={{fontSize:9,color:"#64748b"}}>{benchLabel}</span>
          </div>
        )}
        {signals.filter(s => s.trigger_tf === 'daily' || s.trigger_tf === '4h').length > 0 && (
          <div style={{display:"flex",alignItems:"center",gap:4}}>
            <svg width="10" height="16"><polygon points="5,0 9,8 1,8" fill="#eab308"/><line x1="5" x2="5" y1="8" y2="16" stroke="#eab308" strokeWidth="1.5"/></svg>
            <span style={{fontSize:9,color:"#eab308"}}>Signal</span>
          </div>
        )}
        <div style={{marginLeft:"auto",fontSize:9,color:"#334155",fontFamily:"monospace"}}>{ohlcv.length} Tage · Daily</div>
      </div>
    </div>
  );
}

// ── 4H Candlestick Chart (60 Kerzen) ─────────────────────────────────────────
function Chart4H({ ohlcv4h, structure4h, chartId, signals = [], tradeMarkers = [] }) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);
  const W = 600, H = 260;
  const PL = 56, PR = 52, PT = 18, PB = 32;
  const cW = W - PL - PR, cH = H - PT - PB;

  const display4h = useMemo(() => ohlcv4h, [ohlcv4h]);
  const n = display4h.length;

  const allH = display4h.map(d => d.h), allL = display4h.map(d => d.l);
  const rawMax = Math.max(...allH), rawMin = Math.min(...allL);
  const pad = (rawMax - rawMin) * 0.07;
  const maxP = rawMax + pad, minP = rawMin - pad, range = maxP - minP;
  const toY = p => PT + (1 - (p - minP) / range) * cH;
  const toX = i => PL + (i + 0.5) * (cW / n);
  const bW  = Math.max(1.5, cW / n * 0.65);

  const yTicks = [];
  for (let k = 0; k <= 5; k++) yTicks.push(minP + k * range / 5);

  const dayLabels = [];
  let lastDay = null;
  display4h.forEach((d, i) => {
    const day = d.d.slice(0, 10);
    if (day !== lastDay && i % 2 === 0) { dayLabels.push({ i, label: d.d.slice(5, 10) }); lastDay = day; }
  });

  const offset = 0;
  const { gws4hHigh, breakout4hIdx, broken4h, prevGws4hHigh, prevBreakout4hIdx } = structure4h || {};
  const col4h = broken4h ? "#ef4444" : "#a78bfa";

  const localGws4hIdx      = gws4hHigh      ? gws4hHigh.idx - offset      : null;
  const localBreakout4hIdx = breakout4hIdx  !== null ? breakout4hIdx - offset  : null;
  const localPrevGws4hIdx  = prevGws4hHigh  ? prevGws4hHigh.idx - offset  : null;
  const localPrevBreakIdx  = prevBreakout4hIdx !== null ? prevBreakout4hIdx - offset : null;

  const lineEnd4h = localBreakout4hIdx !== null && localBreakout4hIdx >= 0
    ? Math.min(localBreakout4hIdx, n - 1)
    : n - 1;

  const handleMouseMove = useCallback((e) => {
    const svg = svgRef.current; if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (W / rect.width);
    const idx = Math.round((mx - PL) / (cW / n) - 0.5);
    setHover(idx >= 0 && idx < n ? idx : null);
  }, [n, cW]);

  const hd = hover !== null ? display4h[hover] : null;

  return (
    <div className="chart-wrap" style={{background:"#07090f",borderRadius:8,border:"1px solid #1e293b",overflow:"hidden"}}>
      <div style={{height:28,padding:"0 12px",display:"flex",alignItems:"center",gap:14,background:"#0a0f1e",borderBottom:"1px solid #1e293b",fontSize:10,fontFamily:"monospace"}}>
        {hd ? <>
          <span style={{color:"#475569"}}>{hd.d}</span>
          <span>O <span style={{color:"#e2e8f0"}}>{hd.o.toFixed(2)}</span></span>
          <span>H <span style={{color:"#4ade80"}}>{hd.h.toFixed(2)}</span></span>
          <span>L <span style={{color:"#f87171"}}>{hd.l.toFixed(2)}</span></span>
          <span>C <span style={{color:hd.c>=hd.o?"#4ade80":"#f87171",fontWeight:700}}>{hd.c.toFixed(2)}</span></span>
        </> : <span style={{color:"#334155"}}>Hover für 4H-Details</span>}
      </div>

      <svg ref={svgRef} width="100%" viewBox={`0 0 ${W} ${H}`}
        onMouseMove={handleMouseMove} onMouseLeave={()=>setHover(null)} style={{cursor:"crosshair"}}>
        <defs>
          <linearGradient id={`g4h_${chartId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#22c55e" stopOpacity="0.13"/>
            <stop offset="100%" stopColor="#22c55e" stopOpacity="0.01"/>
          </linearGradient>
        </defs>
        <rect x={PL} y={PT} width={cW} height={cH} fill="#07090f"/>

        {yTicks.map((val, k) => {
          const y = toY(val);
          return <g key={k}>
            <line x1={PL} x2={PL+cW} y1={y} y2={y} stroke="#1a2235" strokeWidth="0.8"/>
            <text x={PL-5} y={y+3.5} textAnchor="end" fill="#334155" fontSize="9" fontFamily="monospace">{val.toFixed(0)}</text>
          </g>;
        })}

        {/* Tagestrennlinien */}
        {dayLabels.map(({i, label}) => (
          <g key={i}>
            <line x1={toX(i)} x2={toX(i)} y1={PT} y2={PT+cH} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,4" opacity="0.25"/>
            <text x={toX(i)} y={PT+cH+14} textAnchor="middle" fill="#334155" fontSize="8" fontFamily="monospace">{label}</text>
          </g>
        ))}

        {/* Breakout-Zone 4H */}
        {localBreakout4hIdx !== null && localBreakout4hIdx >= 0 && (
          <rect x={toX(localBreakout4hIdx)} y={PT} width={PL+cW-toX(localBreakout4hIdx)} height={cH} fill={`url(#g4h_${chartId})`}/>
        )}

        {/* Vorheriger GWS-4H Break (gedimmt) */}
        {prevGws4hHigh && localPrevGws4hIdx !== null && localPrevGws4hIdx >= 0 && (() => {
          const prevEnd = localPrevBreakIdx !== null && localPrevBreakIdx >= 0
            ? Math.min(localPrevBreakIdx, localGws4hIdx !== null && localGws4hIdx >= 0 ? localGws4hIdx : n - 1)
            : (localGws4hIdx !== null && localGws4hIdx >= 0 ? localGws4hIdx : n - 1);
          const y  = toY(prevGws4hHigh.price);
          const x1 = toX(Math.max(0, localPrevGws4hIdx));
          const x2 = toX(prevEnd);
          return <>
            <line x1={x1} x2={x2} y1={y} y2={y} stroke={col4h} strokeWidth="1.1" strokeDasharray="4,4" opacity="0.3"/>
          </>;
        })()}

        {/* Aktueller GWS-4H */}
        {gws4hHigh && localGws4hIdx !== null && localGws4hIdx >= 0 && (() => {
          const y  = toY(gws4hHigh.price);
          const x1 = toX(localGws4hIdx);
          const x2 = toX(lineEnd4h);
          return <>
            <line x1={x1} x2={x2} y1={y} y2={y} stroke={col4h} strokeWidth="1.8" strokeDasharray="4,3"/>
          </>;
        })()}

                {/* Trend-Fallback: kein GWS aber höhere Hochs (4H) */}
        {broken4h && !gws4hHigh && structure4h?.swingHighs?.length >= 2 && (() => {
          const lastSH4h = structure4h.swingHighs[structure4h.swingHighs.length - 1];
          const localIdx = lastSH4h.idx - offset;
          if (localIdx < 0) return null;
          const y = toY(lastSH4h.price);
          return <>
            <line x1={PL} x2={PL+cW} y1={y} y2={y} stroke="#4ade80" strokeWidth="1.2" strokeDasharray="3,6" opacity="0.7"/>
            <text x={PL+6} y={y-4} fill="#4ade80" fontSize="8" fontFamily="monospace" opacity="0.8">Trend ↑</text>
          </>;
        })()}

        {/* Kerzen 4H */}
        {display4h.map((d, i) => {
          const bull = d.c >= d.o;
          const isBoc = i === localBreakout4hIdx;
          const col  = bull ? "#22c55e" : "#ef4444";
          const bTop = toY(Math.max(d.o, d.c));
          const bH   = Math.max(1, toY(Math.min(d.o, d.c)) - bTop);
          const isHov = hover === i;
          return <g key={i}>
            <line x1={toX(i)} x2={toX(i)} y1={toY(d.h)} y2={toY(d.l)} stroke={col} strokeWidth={isHov?1.5:0.8} opacity={0.85}/>
            <rect x={toX(i)-bW/2} y={bTop} width={bW} height={bH}
              fill={col} opacity={isBoc?1:isHov?0.95:0.75}
              stroke={isBoc?col4h:"none"} strokeWidth={isBoc?1:0}/>
          </g>;
        })}

        {/* Trade-Marker */}
        {tradeMarkers.map((m, mi) => {
          const target = m.date.slice(0,10);
          let best = Infinity, idx = -1;
          display4h.forEach((d, i) => { const diff = Math.abs(new Date(d.d.slice(0,10)) - new Date(target)); if (diff < best) { best = diff; idx = i; } });
          if (idx < 0 || best > 3 * 86400000) return null;
          const x = toX(idx);
          if (m.type === 'entry') {
            const yTip = Math.min(toY(display4h[idx].l) + 3, PT + cH - 16);
            return <g key={`tm${mi}`}>
              <polygon points={`${x-5},${yTip+10} ${x+5},${yTip+10} ${x},${yTip}`} fill="#4ade80" opacity="0.95"/>
              <line x1={x} x2={x} y1={yTip+10} y2={Math.min(yTip+20, PT+cH)} stroke="#4ade80" strokeWidth="1.5"/>
            </g>;
          } else {
            const yTip = Math.max(toY(display4h[idx].h) - 3, PT + 14);
            return <g key={`tm${mi}`}>
              <polygon points={`${x-5},${yTip-10} ${x+5},${yTip-10} ${x},${yTip}`} fill="#f87171" opacity="0.95"/>
              <line x1={x} x2={x} y1={yTip-10} y2={Math.max(yTip-20, PT)} stroke="#f87171" strokeWidth="1.5"/>
            </g>;
          }
        })}

        {/* Signal-Pfeile (4H-Chart: alle Signale mit h4_bar_date) */}
        {signals.filter(s => s.h4_bar_date).map((sig, si) => {
          const idx = display4h.findIndex(d => d.d.slice(0,16) === sig.h4_bar_date.slice(0,16));
          if (idx < 0) return null;
          const x = toX(idx);
          const yTip = Math.min(toY(display4h[idx].l) + 4, PT + cH - 20);
          return <g key={si}>
            <rect x={x-6} y={yTip-2} width={12} height={22} rx={2} fill="#eab308" opacity={0.2}/>
            <polygon points={`${x-4},${yTip+8} ${x+4},${yTip+8} ${x},${yTip}`} fill="#eab308" opacity="0.95"/>
            <line x1={x} x2={x} y1={yTip+8} y2={yTip+18} stroke="#eab308" strokeWidth="1.5" opacity="0.95"/>
          </g>;
        })}

        {/* Aktueller Preis */}
        <line x1={PL} x2={PL+cW} y1={toY(display4h[n-1].c)} y2={toY(display4h[n-1].c)} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.45"/>
        <rect x={PL+cW+2} y={toY(display4h[n-1].c)-8} width={46} height={15} rx="3" fill="#1e293b"/>
        <text x={PL+cW+25} y={toY(display4h[n-1].c)+3} textAnchor="middle" fill="#94a3b8" fontSize="8.5" fontFamily="monospace">{display4h[n-1].c.toFixed(2)}</text>

        {/* Crosshair */}
        {hover !== null && <>
          <line x1={toX(hover)} x2={toX(hover)} y1={PT} y2={PT+cH} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.5"/>
          <line x1={PL} x2={PL+cW} y1={toY(display4h[hover].c)} y2={toY(display4h[hover].c)} stroke="#7dd3fc" strokeWidth="0.7" strokeDasharray="2,3" opacity="0.5"/>
        </>}
        <rect x={PL} y={PT} width={cW} height={cH} fill="none" stroke="#1e293b" strokeWidth="0.8"/>
      </svg>

      <div style={{padding:"5px 12px",display:"flex",gap:14,alignItems:"center",background:"#0a0f1e",borderTop:"1px solid #0f172a",flexWrap:"wrap"}}>
        <div style={{display:"flex",alignItems:"center",gap:4}}>
          <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#a78bfa" strokeWidth="1.8" strokeDasharray="4,3"/></svg>
          <span style={{fontSize:9,color:"#64748b"}}>GWS-4H</span>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:4}}>
          <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="#a78bfa" strokeWidth="1.1" strokeDasharray="4,4" opacity="0.3"/></svg>
          <span style={{fontSize:9,color:"#64748b"}}>Letzter Break</span>
        </div>
        {signals.filter(s => s.trigger_tf === '4h').length > 0 && (
          <div style={{display:"flex",alignItems:"center",gap:4}}>
            <svg width="10" height="16"><polygon points="5,0 9,8 1,8" fill="#eab308"/><line x1="5" x2="5" y1="8" y2="16" stroke="#eab308" strokeWidth="1.5"/></svg>
            <span style={{fontSize:9,color:"#eab308"}}>Signal</span>
          </div>
        )}
        <div style={{marginLeft:"auto",fontSize:9,color:"#334155",fontFamily:"monospace"}}>{n} Kerzen (von {ohlcv4h.length}) · 4H</div>
      </div>
    </div>
  );
}


// ── Hilfsfunktionen ────────────────────────────────────────────────────────

function PktDot({ val, has }) {
  if (!has) return <span style={{color:'#334155',fontSize:11,fontFamily:'monospace'}}>–</span>;
  return <span className="dot" style={{background: val ? '#4ade80' : '#1e293b', border: val ? 'none' : '1px solid #334155'}}/>;
}

function PktBadge({ pts, has4h }) {
  const max = has4h ? 3 : 2;
  const colors = ['#1e293b','#854d0e','#713f12','#14532d'];
  const textColors = ['#475569','#fbbf24','#fde047','#4ade80'];
  return (
    <span style={{
      display:'inline-block', minWidth:28, textAlign:'center',
      background: pts >= max ? colors[3] : pts >= 2 ? colors[2] : pts >= 1 ? colors[1] : colors[0],
      color: pts >= max ? textColors[3] : pts >= 2 ? textColors[2] : pts >= 1 ? textColors[1] : textColors[0],
      borderRadius:4, padding:'1px 6px', fontFamily:'monospace', fontSize:12, fontWeight:700
    }}>{pts}{has4h ? '' : '*'}</span>
  );
}

// ── Equity-Kurve ─────────────────────────────────────────────────────────────
function EquityCurve({ curve }) {
  const W = 600, H = 90, PL = 52, PR = 12, PT = 8, PB = 22;
  const cW = W - PL - PR, cH = H - PT - PB;
  const equities = curve.map(p => p.equity);
  const minE = Math.min(...equities), maxE = Math.max(...equities);
  const range = maxE - minE || 1;
  const toX = i => PL + (i / (curve.length - 1)) * cW;
  const toY = e => PT + cH - ((e - minE) / range) * cH;
  const pts = curve.map((p, i) => `${toX(i)},${toY(p.equity)}`).join(' ');
  const yBase = toY(10000);
  return (
    <div style={{marginBottom:12}}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{width:'100%',maxWidth:W,display:'block',
        background:'#07090f',borderRadius:6,border:'1px solid #1e293b'}}>
        <line x1={PL} x2={W-PR} y1={yBase} y2={yBase} stroke="#1e293b" strokeWidth="1" strokeDasharray="4,3"/>
        <text x={PL-4} y={yBase+3} fill="#334155" fontSize="7" textAnchor="end">10k</text>
        <polyline points={pts} fill="none" stroke="#4ade80" strokeWidth="1.5"/>
        {curve.map((p, i) => (
          <circle key={i} cx={toX(i)} cy={toY(p.equity)} r="2.5"
            fill={p.equity >= 10000 ? '#4ade80' : '#f87171'} opacity="0.9"/>
        ))}
        <text x={PL-4} y={PT+6} fill="#475569" fontSize="7" textAnchor="end">
          {maxE >= 10000 ? '+' : ''}€{(maxE-10000).toFixed(0)}
        </text>
        <text x={PL-4} y={H-PB+6} fill="#475569" fontSize="7" textAnchor="end">
          {minE >= 10000 ? '+' : ''}€{(minE-10000).toFixed(0)}
        </text>
        <text x={W/2} y={H-3} fill="#334155" fontSize="7" textAnchor="middle">
          Equity-Kurve · {curve.length - 1} abgeschl. Trades · Start €10.000
        </text>
      </svg>
    </div>
  );
}

const fmtK = v => Math.round(Math.abs(v)).toLocaleString('de-DE');

