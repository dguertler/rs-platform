/**
 * Depot-Simulation für den historischen Backtest: ein Depot mit Startkapital,
 * höchstens MAX_POSITIONS gleichzeitig offenen Positionen und Zinseszins.
 *
 * Die Trades (Einstieg, Ausstieg, Kurse) kommen unverändert aus der Engine
 * (frontend/backtest_logic.js). Nur die Positionsgröße wird skaliert:
 *   Slot     = aktueller Depotwert / MAX_POSITIONS   (live 10.000 € bei 100.000 €)
 *   Position = Slot × (Einsatz der Engine / 10.000 €)
 * Die Engine kauft höchstens für 10.000 € und riskiert höchstens 1.000 €, bei
 * weitem Stopp also weniger Stück — dieses Verhältnis bleibt erhalten, das
 * Risiko je Trade liegt damit bei höchstens 10 % des Slots (1 % des Depots).
 *
 * Reihenfolge je Handelstag: erst Ausstiege (zur Eröffnung), dann Einstiege
 * (zur Eröffnung) nach RS-Rang am Einstiegstag, dann Bewertung zum Schluss.
 * Sind alle Slots belegt, wird ein Signal ausgelassen.
 */
const START_CAPITAL = 100000;
const MAX_POSITIONS = 10;
const ENGINE_CAPITAL = 10000;

/** Handelstage aus allen Kursreihen der gehandelten Symbole. */
function tradingCalendar(closesBySymbol, from) {
  const days = new Set();
  for (const closes of Object.values(closesBySymbol)) {
    for (const d of closes.keys()) if (d >= from) days.add(d);
  }
  return [...days].sort();
}

function simulatePortfolio(trades, closesBySymbol, { start, startCapital = START_CAPITAL, maxPositions = MAX_POSITIONS } = {}) {
  const ordered = [...trades].sort((a, b) =>
    a.entryDate !== b.entryDate ? (a.entryDate < b.entryDate ? -1 : 1)
      : a.rank !== b.rank ? a.rank - b.rank
        : a.ticker < b.ticker ? -1 : 1);
  const from = start || (ordered[0] ? ordered[0].entryDate : null);
  const calendar = from ? tradingCalendar(closesBySymbol, from) : [];

  let cash = startCapital;
  const open = [];                 // { trade, shares, cost, lastClose }
  const results = new Map();       // trade → { taken, depotPnl, depotInvested }
  let next = 0;
  const equityByDay = [];

  const markValue = () => open.reduce((s, p) => s + p.shares * p.lastClose, 0);

  for (const day of calendar) {
    // 1. Ausstiege zur Eröffnung (auch nachgeholte, falls der Ausstiegstag fehlt)
    for (let i = open.length - 1; i >= 0; i--) {
      const p = open[i];
      if (p.trade.isOpen || p.trade.exitDate > day) continue;
      const proceeds = p.shares * p.trade.exitPrice;
      cash += proceeds;
      results.set(p.trade, { taken: true, depotInvested: p.cost, depotPnl: proceeds - p.cost });
      open.splice(i, 1);
    }

    // 2. Einstiege zur Eröffnung, bester RS-Rang zuerst
    while (next < ordered.length && ordered[next].entryDate <= day) {
      const t = ordered[next++];
      if (open.length >= maxPositions) {
        results.set(t, { taken: false });
        continue;
      }
      const slot = (cash + markValue()) / maxPositions;
      const fraction = Math.min(1, t.invested / ENGINE_CAPITAL);
      const cost = Math.min(slot * fraction, cash);
      if (cost <= 0 || !(t.entryPrice > 0)) {
        results.set(t, { taken: false });
        continue;
      }
      cash -= cost;
      open.push({ trade: t, shares: cost / t.entryPrice, cost, lastClose: t.entryPrice });
    }

    // 3. Bewertung zum Tagesschluss
    for (const p of open) {
      const c = closesBySymbol[p.trade.ticker]?.get(day);
      if (c != null) p.lastClose = c;
    }
    equityByDay.push([day, cash + markValue()]);
  }

  // Zum Schluss noch offene Positionen: Buchgewinn zum letzten Kurs
  for (const p of open) {
    const value = p.shares * p.lastClose;
    results.set(p.trade, { taken: true, depotInvested: p.cost, depotPnl: value - p.cost, stillOpen: true });
  }
  return { equityByDay, results, startCapital, maxPositions };
}

/** Jahreswerte, maximaler Rückgang und Kennzahlen der genommenen Trades. */
function portfolioStats({ equityByDay, results, startCapital, maxPositions }, trades) {
  const years = {};
  let prevEnd = startCapital;
  let peakAll = startCapital, maxDDAll = 0;
  let current = null;
  for (const [day, eq] of equityByDay) {
    const y = day.slice(0, 4);
    if (!years[y]) {
      if (current) prevEnd = current.endEquity;
      current = years[y] = { startEquity: prevEnd, endEquity: eq, peak: prevEnd, maxDD: 0 };
    }
    current.endEquity = eq;
    current.peak = Math.max(current.peak, eq);
    current.maxDD = Math.min(current.maxDD, (eq / current.peak - 1) * 100);
    peakAll = Math.max(peakAll, eq);
    maxDDAll = Math.min(maxDDAll, (eq / peakAll - 1) * 100);
  }

  const tradeStats = (list) => {
    const taken = list.filter((t) => results.get(t)?.taken);
    const pnl = taken.map((t) => results.get(t).depotPnl);
    const wins = pnl.filter((v) => v > 0).reduce((s, v) => s + v, 0);
    const losses = pnl.filter((v) => v <= 0).reduce((s, v) => s + v, 0);
    return {
      taken: taken.length,
      skipped: list.length - taken.length,
      winrate: taken.length ? (pnl.filter((v) => v > 0).length / taken.length) * 100 : null,
      profitFactor: losses < 0 ? Math.abs(wins / losses) : null,
      pnl: pnl.reduce((s, v) => s + v, 0),
    };
  };

  const byEntryYear = {};
  for (const t of trades) (byEntryYear[t.entryDate.slice(0, 4)] ||= []).push(t);
  const out = {};
  for (const [y, v] of Object.entries(years)) {
    out[y] = {
      startEquity: v.startEquity,
      endEquity: v.endEquity,
      returnPct: (v.endEquity / v.startEquity - 1) * 100,
      maxDD: v.maxDD,
      ...tradeStats(byEntryYear[y] || []),
    };
  }

  const endEquity = equityByDay.length ? equityByDay[equityByDay.length - 1][1] : startCapital;
  const first = equityByDay[0]?.[0], last = equityByDay[equityByDay.length - 1]?.[0];
  const yearsSpan = first && last ? (new Date(last) - new Date(first)) / (365.25 * 864e5) : 0;
  // Monatsendstände für eine Verlaufskurve
  const monthly = [];
  for (let i = 0; i < equityByDay.length; i++) {
    const [d, eq] = equityByDay[i];
    const nextDay = equityByDay[i + 1]?.[0];
    if (!nextDay || nextDay.slice(0, 7) !== d.slice(0, 7)) monthly.push([d, Math.round(eq)]);
  }
  return {
    startCapital,
    maxPositions,
    endEquity,
    returnPct: (endEquity / startCapital - 1) * 100,
    cagr: yearsSpan > 0 ? ((endEquity / startCapital) ** (1 / yearsSpan) - 1) * 100 : null,
    maxDD: maxDDAll,
    ...tradeStats(trades),
    years: out,
    monthly,
  };
}

module.exports = { simulatePortfolio, portfolioStats, START_CAPITAL, MAX_POSITIONS };
