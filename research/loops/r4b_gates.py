import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r4b import *
import r4b as l4
import wd
mode = sys.argv[1]
if mode == 'check':
    for fee in (0.001, 0.0025):
        r = {k: metrics(sim_sweep(sigs4, F4, CAND['S3 (Referenz)'], *P[k], fee=fee)['equity'])['cagr'] for k in ('16-21', '22-26', '16-26')}
        print('S3 Referenz fee', fee, {k: round(v, 1) for k, v in r.items()})
    sys.exit()
RUNS = 30; NPERM = 500
raw = wd.build_all(); sw = wd.to_sigs(m, raw, top_filter=True); Fw = wd.features(m, sw, 'wd')
print('QQQ', {k: round(v, 1) for k, v in QC.items()})
print('| Kandidat | 16–21 | 22–26 | 16–26 | PF € [95 %] / gleichgew. | MaxDD | Trades/J | Ø Haltedauer | Kostenlast % p. a. | robust 16–21/22–26 | G1 | 08–15 CAGR / PF € | G2 | Perzentil 16–21/22–26 | G3 |')
pool = {}
for i, lst in sigs4.items():
    for sg in lst: pool.setdefault(sg['entryDate'][:7], []).append(sg)
for name, cfg in CAND.items():
    l4.CTX.update(sigs=sigs4, F=F4)
    res = {k: sim_sweep(sigs4, F4, cfg, *P[k]) for k in ('16-21', '22-26', '16-26')}
    mt = {k: metrics(v['equity'], v['trades']) for k, v in res.items()}
    full = res['16-26']; ret = np.array([t['ret'] for t in full['trades']]); pfe = ret[ret > 0].sum() / -ret[ret <= 0].sum()
    ci = pf_ci(full['trades'])
    with Pool(4) as pl:
        rob = {per: float(np.mean(pl.map(l4._rob, [(name, sd, per) for sd in range(RUNS)]))) for per in ('16-21', '22-26')}
    g1 = mt['16-26']['pf'] >= 3 and mt['16-21']['cagr'] > QC['16-21'] and mt['22-26']['cagr'] > QC['22-26'] and min(rob.values()) >= 0.7
    # G2 Tagesnäherung 2008-15
    r08 = sim_sweep(sw, Fw, cfg, *P['08-15']); m08 = metrics(r08['equity'], r08['trades'])
    g2 = m08['cagr'] > QC['08-15'] and m08['pf'] >= 3
    # G3 Nullmodell
    real = set((sg['sym'], sg['entryDate']) for lst in sigs4.values() for sg in lst if select(sg, F4, cfg[0]))
    cnt = {}
    for k in real: cnt[k[1][:7]] = cnt.get(k[1][:7], 0) + 1
    rng = np.random.default_rng(4242); draws = []
    for d in range(NPERM):
        al = set()
        for mo, n in cnt.items():
            cs = pool[mo]; idx = rng.choice(len(cs), size=min(n, len(cs)), replace=False)
            for j in idx: al.add((cs[j]['sym'], cs[j]['entryDate']))
        draws.append((name, al))
    with Pool(4) as pl:
        pr = pl.map(l4._perm, draws)
    pct = {per: float(np.mean([x[per] < mt[per]['cagr'] for x in pr]) * 100) for per in ('16-21', '22-26')}
    g3 = min(pct.values()) >= 90
    days = np.mean([t['days'] for t in full['trades']])
    print(f"| {name} | {mt['16-21']['cagr']:.1f} | {mt['22-26']['cagr']:.1f} | {mt['16-26']['cagr']:.1f} | {mt['16-26']['pf']:.2f} [{ci[1]:.2f}–{ci[2]:.2f}] / {pfe:.2f} | "
          f"{mt['16-26']['maxDD']:.1f} | {full['trades_pa']:.1f} | {days:.0f} T | {full['fee_pa']:.2f} | {rob['16-21']:.0%}/{rob['22-26']:.0%} | {'JA' if g1 else 'nein'} | "
          f"{m08['cagr']:.1f} (QQQ {QC['08-15']:.1f}) / {m08['pf']:.2f} | {'JA' if g2 else 'nein'} | {pct['16-21']:.0f}/{pct['22-26']:.0f} | {'JA' if g3 else 'nein'} |", flush=True)
    pickle.dump(dict(mt=mt, rob=rob, m08=m08, pct=pct, perm=pr), open(f"l4_{name.split()[0]}.pkl", 'wb'))
