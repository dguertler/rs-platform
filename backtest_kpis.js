/**
 * Kennzahlen über eine Trade-Liste der Backtest-Engine (frontend/backtest_logic.js).
 * Gemeinsam genutzt von track_top20_performance.js und backtest_history/run_backtest.js.
 */
function kpis(trades, CAPITAL) {
  if (!trades.length) return null;
  const closed = trades.filter((t) => !t.isOpen);
  const open = trades.filter((t) => t.isOpen);
  const wins = closed.filter((t) => t.pnl > 0);
  const losses = closed.filter((t) => t.pnl <= 0);
  const sum = (arr, f) => arr.reduce((s, t) => s + f(t), 0);
  const grossProfit = sum(wins, (t) => t.pnl);
  const grossLoss = sum(losses, (t) => t.pnl);
  const totalPnl = sum(trades, (t) => t.pnl);
  const invested = sum(trades, (t) => t.invested);

  // Profitfaktor inklusive offener Positionen zum aktuellen Stand — nur über
  // geschlossene Trades gerechnet zeigt er in jungen Zeiträumen fast nur die
  // schnell geschlossenen Verlierer, während die Gewinner noch laufen.
  const pfProfit = sum(trades.filter((t) => t.pnl > 0), (t) => t.pnl);
  const pfLoss = sum(trades.filter((t) => t.pnl <= 0), (t) => t.pnl);

  let equity = CAPITAL;
  let peak = CAPITAL;
  let maxDD = 0;
  for (const t of [...closed].sort((a, b) => (a.exitDate < b.exitDate ? -1 : 1))) {
    equity += t.pnl;
    peak = Math.max(peak, equity);
    maxDD = Math.max(maxDD, ((peak - equity) / peak) * 100);
  }

  const byPnl = [...trades].sort((a, b) => b.pnl - a.pnl);
  const slim = (t) => ({
    ticker: t.ticker,
    entryDate: t.entryDate,
    exitDate: t.exitDate,
    isOpen: t.isOpen,
    pnl: Math.round(t.pnl),
    pnlPct: +t.pnlPct.toFixed(1),
  });

  return {
    nTrades: trades.length,
    nClosed: closed.length,
    nOpen: open.length,
    nTickers: new Set(trades.map((t) => t.ticker)).size,
    winrate: closed.length ? (wins.length / closed.length) * 100 : null,
    totalPnl,
    realizedPnl: sum(closed, (t) => t.pnl),
    openPnl: sum(open, (t) => t.pnl),
    invested,
    returnOnInvested: invested ? (totalPnl / invested) * 100 : null,
    avgPnlPerTrade: totalPnl / trades.length,
    avgReturnPerTrade: sum(trades, (t) => t.pnlPct) / trades.length,
    avgInvested: invested / trades.length,
    avgRisk: sum(trades, (t) => t.riskAmount) / trades.length,
    avgWin: wins.length ? grossProfit / wins.length : 0,
    avgWinPct: wins.length ? sum(wins, (t) => t.pnlPct) / wins.length : 0,
    avgLoss: losses.length ? grossLoss / losses.length : 0,
    avgLossPct: losses.length ? sum(losses, (t) => t.pnlPct) / losses.length : 0,
    profitFactor: pfLoss < 0 ? Math.abs(pfProfit / pfLoss) : null,
    profitFactorClosed: grossLoss < 0 ? Math.abs(grossProfit / grossLoss) : null,
    avgHoldingWeeks: sum(trades, (t) => t.holdingWeeks) / trades.length,
    maxDD,
    best: byPnl.slice(0, 5).map(slim),
    worst: byPnl.slice(-5).reverse().map(slim),
  };
}

module.exports = { kpis };
