#!/usr/bin/env python3
# VERSION: 2026-09-08-es1
"""empscore.py -- NEW FILE, READ-ONLY. Score the Gaussian fair value against
the index's own empirical move distribution, on every settled 15-minute crypto
market the index tape can reach.

WHAT IT PRINTS
  1. reliability of both estimators, bucketed by stated probability
  2. the gate pin actually trades, by tau: calls, closes, realised flip rate,
     and what each estimator SAID the flip rate would be -- on the identical
     set of calls, so the only difference is Phi vs the empirical CDF
  3. the empirical/Gaussian tail ratio by tau
  4. what happens to pin's trade list if the empirical estimator is added as a
     second gate: trades kept, flips removed
  5. the two deliberately leaking controls, so the reader can see in these very
     tables what a lookahead leak looks like here

n IS CLOSES. Twelve series settle on the same quarter hour at rho ~ 0.8, so a
per-market-second n overstates the independent count by ~50x. Every
significance number here is a block bootstrap resampling WHOLE CLOSES.

NO PEEKING: see empfair.py's header. Every empirical query goes through
IndexModel.tail, which calls _assert_causal on every single call.
"""
import argparse
import json
import math
import os
import random
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import idxload                                              # noqa: E402
import empfair                                              # noqa: E402
from empfair import (IndexModel, SERIES_TO_INDEX, PIN, WINDOWS_H, W_PRIMARY,
                     SETTLED)                                # noqa: E402

TAUS = [3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20]

BINS = [0.0, 0.002, 0.005, 0.01, 0.02, 0.05, 0.10, 0.25, 0.50,
        0.75, 0.90, 0.95, 0.98, 0.99, 0.995, 0.998, 1.0001]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def load_markets():
    S = json.load(open(SETTLED, encoding="utf-8"))
    out = []
    for s, rows in S.items():
        if s not in SERIES_TO_INDEX:
            continue
        for r in rows:
            if r["result"] not in ("yes", "no"):
                continue
            out.append(dict(ticker=r["ticker"], series=s, close=int(r["close"]),
                            K=float(r["strike"]), rd=int(r["rd"]),
                            won=1.0 if r["result"] == "yes" else 0.0))
    return out


def score(taus, hours=None, verbose=True, leak=None, limit_series=None):
    mk = load_markets()
    by_idx = defaultdict(list)
    for m in mk:
        if limit_series and m["series"] not in limit_series:
            continue
        by_idx[SERIES_TO_INDEX[m["series"]]].append(m)
    ids = sorted(by_idx)
    dense = idxload.load(ids, hours=hours, verbose=verbose)
    rs = sorted({t - 1 for t in taus})
    rows = []
    for iid in ids:
        t0 = time.time()
        im = IndexModel(dense[iid], rs)
        n0 = len(rows)
        for m in by_idx[iid]:
            for tau in taus:
                o = im.price(m["close"], tau, m["K"], m["rd"], leak=leak)
                if o is None:
                    continue
                rows.append((m["close"], m["series"], m["ticker"], tau,
                             m["won"], o["fair_g"],
                             o.get("std%d" % W_PRIMARY),
                             o.get("raw%d" % W_PRIMARY),
                             o.get("std%d" % WINDOWS_H[0]),
                             o.get("std%d" % WINDOWS_H[2]),
                             o.get("nstd%d" % W_PRIMARY, 0),
                             o.get("leakemp")))
        if verbose:
            print(f"    {iid:<14} {len(rows)-n0:>7,} cells "
                  f"({time.time()-t0:.0f}s)")
        del im
    return rows


# ---- columns ---------------------------------------------------------------
C_CLOSE, C_SER, C_TICK, C_TAU, C_WON, C_G, C_S24, C_R24, C_S6, C_S72, \
    C_N, C_LEAK = range(12)


def reliability(rows, col, label):
    tab = [[0, 0.0, 0.0] for _ in BINS]
    for r in rows:
        p = r[col]
        if p is None:
            continue
        b = 0
        while b + 1 < len(BINS) and p >= BINS[b + 1]:
            b += 1
        tab[b][0] += 1
        tab[b][1] += p
        tab[b][2] += r[C_WON]
    print(f"\n  RELIABILITY -- {label}")
    print(f"    {'stated P(YES)':>18}{'cells':>10}{'mean stated':>14}"
          f"{'realised YES':>15}{'95% CI':>20}")
    for b in range(len(BINS) - 1):
        n, sp, sw = tab[b]
        if not n:
            continue
        lo, hi = wilson(sw, n)
        print(f"    {BINS[b]:>7.3f}-{BINS[b+1]:<10.3f}{n:>10,}"
              f"{100*sp/n:>13.2f}%{100*sw/n:>14.2f}%"
              f"{'  [%5.2f, %5.2f]%%' % (100*lo, 100*hi):>20}")


def gate_rows(rows, col, pin=PIN):
    """(row, side) for cells where estimator `col` is decided."""
    out = []
    for r in rows:
        p = r[col]
        if p is None:
            continue
        if p >= pin:
            out.append((r, 1.0))
        elif p <= 1 - pin:
            out.append((r, 0.0))
    return out


PBANDS = [(0.0, 1e-6), (1e-6, 1e-4), (1e-4, 1e-3), (1e-3, 0.005),
          (0.005, 0.01), (0.01, 0.02), (0.02, 1.0)]


def band_table(rows, taus):
    """The head-to-head that decides anything.

    Averaging over every gate crossing is dominated by markets 40 sigma from
    the strike, which pin never trades because nobody offers the other side of
    them. What pin trades is the MARGINAL cell: the Gaussian says 0.2%-2% and
    somebody is still quoting 3c. This table cuts the gate calls by the
    Gaussian's own stated flip probability and asks, inside each slice, what
    actually happened and what the empirical estimator had said instead."""
    g = gate_rows(rows, C_G)
    print("\n  THE DECISION-RELEVANT SLICE -- gate calls cut by the "
          "Gaussian's own stated flip probability")
    print(f"    {'Gaussian says P(flip)':>24}{'calls':>9}{'closes':>8}"
          f"{'flips':>7}{'REALISED':>11}{'Gaussian':>10}{'empirical':>11}"
          f"{'ratio':>8}")
    for lo, hi in PBANDS:
        sub = [(r, s) for r, s in g
               if lo <= (((1 - r[C_G]) if s else r[C_G])) < hi]
        if not sub:
            continue
        n = len(sub)
        fl = sum(1 for r, s in sub if r[C_WON] != s)
        pg = sum(((1 - r[C_G]) if s else r[C_G]) for r, s in sub) / n
        se = [(r, s) for r, s in sub if r[C_S24] is not None]
        pe = (sum(((1 - r[C_S24]) if s else r[C_S24]) for r, s in se)
              / len(se)) if se else float("nan")
        cl = len({r[C_CLOSE] for r, s in sub})
        wl, wh = wilson(fl, n)
        print(f"    {('%.0e-%.0e' % (lo, hi)):>24}{n:>9,}{cl:>8,}{fl:>7,}"
              f"{100*fl/n:>10.3f}%{100*pg:>9.3f}%{100*pe:>10.3f}%"
              f"{(pe/pg if pg else 0):>7.1f}x")
        print(f"    {'':>24}{'':>9}{'':>8}{'':>7}"
              f"{('95%% CI [%.3f, %.3f]%%' % (100*wl, 100*wh)):>46}")


def gate_table(rows, taus):
    print(f"\n  THE GATE pin TRADES -- Gaussian fair >= {PIN:.2f} "
          f"or <= {1-PIN:.2f}")
    print(f"    {'tau':>4}{'r':>4}{'calls':>9}{'closes':>8}{'flips':>7}"
          f"{'REALISED':>11}{'Gaussian says':>15}{'empirical says':>16}"
          f"{'ratio':>8}")
    tot = [0, 0, 0.0, 0.0, set()]
    for tau in taus:
        sub = [(r, s) for r, s in gate_rows(rows, C_G) if r[C_TAU] == tau]
        if not sub:
            continue
        n = len(sub)
        fl = sum(1 for r, s in sub if r[C_WON] != s)
        pg = sum((1 - r[C_G]) if s else r[C_G] for r, s in sub) / n
        se = [(r, s) for r, s in sub if r[C_S24] is not None]
        pe = (sum((1 - r[C_S24]) if s else r[C_S24] for r, s in se) / len(se)
              if se else float("nan"))
        cl = {r[C_CLOSE] for r, s in sub}
        tot[0] += n
        tot[1] += fl
        tot[2] += pg * n
        tot[3] += pe * len(se)
        tot[4] |= cl
        print(f"    {tau:>4}{tau-1:>4}{n:>9,}{len(cl):>8,}{fl:>7,}"
              f"{100*fl/n:>10.2f}%{100*pg:>14.2f}%{100*pe:>15.2f}%"
              f"{pe/pg if pg else 0:>7.2f}x")
    n, fl = tot[0], tot[1]
    if n:
        lo, hi = wilson(fl, n)
        print(f"    {'ALL':>4}{'':>4}{n:>9,}{len(tot[4]):>8,}{fl:>7,}"
              f"{100*fl/n:>10.2f}%{100*tot[2]/n:>14.2f}%"
              f"{100*tot[3]/n:>15.2f}%{(tot[3]/tot[2]) if tot[2] else 0:>7.2f}x")
        print(f"    realised flip rate 95% CI (cells, NOT clustered): "
              f"[{100*lo:.2f}%, {100*hi:.2f}%]")
    return tot


def second_gate(rows, taus, col, label):
    """What pin's trade list becomes when `col` must ALSO clear the gate."""
    base = gate_rows(rows, C_G)
    base = [(r, s) for r, s in base if r[col] is not None]
    keep, drop = [], []
    for r, s in base:
        p = r[col]
        ok = (p >= PIN) if s else (p <= 1 - PIN)
        (keep if ok else drop).append((r, s))
    def stat(x):
        n = len(x)
        f = sum(1 for r, s in x if r[C_WON] != s)
        return n, f, (100.0 * f / n if n else 0.0)
    bn, bf, bp = stat(base)
    kn, kf, kp = stat(keep)
    dn, df_, dp = stat(drop)
    print(f"\n  SECOND GATE -- {label} must also clear {PIN}")
    print(f"    {'set':<26}{'calls':>9}{'closes':>8}{'flips':>7}{'flip rate':>11}")
    for nm, x in (("Gaussian gate (pin today)", base),
                  ("  kept by both", keep),
                  ("  DROPPED by the new gate", drop)):
        n, f, p = stat(x)
        cl = len({r[C_CLOSE] for r, s in x})
        print(f"    {nm:<26}{n:>9,}{cl:>8,}{f:>7,}{p:>10.2f}%")
    if bn and kn:
        print(f"    keeps {100.0*kn/bn:.1f}% of the calls and removes "
              f"{100.0*df_/max(bf,1):.1f}% of the flips")
    return base, keep, drop


def boot_close(base, keep, iters=4000, seed=3):
    """Block bootstrap on CLOSES of (flip rate kept) - (flip rate all)."""
    bc, kc = defaultdict(list), defaultdict(list)
    for r, s in base:
        bc[r[C_CLOSE]].append(1 if r[C_WON] != s else 0)
    for r, s in keep:
        kc[r[C_CLOSE]].append(1 if r[C_WON] != s else 0)
    closes = sorted(bc)
    rng = random.Random(seed)
    diffs = []
    for _ in range(iters):
        bn = bf = kn = kf = 0
        for _ in range(len(closes)):
            c = closes[rng.randrange(len(closes))]
            x = bc[c]
            bn += len(x)
            bf += sum(x)
            y = kc.get(c)
            if y:
                kn += len(y)
                kf += sum(y)
        if bn and kn:
            diffs.append(kf / kn - bf / bn)
    diffs.sort()
    if not diffs:
        return None
    return (diffs[int(0.025 * len(diffs))], diffs[len(diffs) // 2],
            diffs[int(0.975 * len(diffs))])


def one_per_market(rows):
    """Closest proxy to a pin fire without the book: the LARGEST tau in the
    grid at which the Gaussian gate is open, one row per market."""
    best = {}
    for r in rows:
        p = r[C_G]
        if p is None or not (p >= PIN or p <= 1 - PIN):
            continue
        k = r[C_TICK]
        if k not in best or r[C_TAU] > best[k][C_TAU]:
            best[k] = r
    return list(best.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=None)
    ap.add_argument("--taus", default=",".join(str(t) for t in TAUS))
    ap.add_argument("--leaks", action="store_true",
                    help="also run the two deliberately leaking controls")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if empfair.selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1":
        if not empfair.selftest():
            raise SystemExit("self-test failed")
        print()
    taus = [int(x) for x in a.taus.split(",")]

    print("LOADING")
    rows = score(taus, hours=a.hours)
    if not rows:
        print("loaded nothing")
        return
    closes = {r[C_CLOSE] for r in rows}
    mkts = {r[C_TICK] for r in rows}
    lo = min(closes)
    hi = max(closes)
    print(f"\n  {len(rows):,} priced (market, tau) cells over {len(mkts):,} "
          f"settled markets and {len(closes):,} closes")
    print(f"  {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(lo))} .. "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(hi))}  "
          f"({(hi-lo)/86400.0:.1f} days)")
    na = [r[C_N] for r in rows if r[C_S24] is not None]
    if na:
        na.sort()
        print(f"  trailing anchors behind each {W_PRIMARY}h empirical "
              f"estimate: median {na[len(na)//2]:,}, min {na[0]:,}")

    reliability(rows, C_G, "GAUSSIAN  Phi((mu-K_eff)/sd)   [the model today]")
    reliability(rows, C_S24,
                f"EMPIRICAL standardised, {W_PRIMARY}h trailing  [the "
                f"replacement]")
    reliability(rows, C_R24,
                f"EMPIRICAL raw price units, {W_PRIMARY}h trailing")

    gate_table(rows, taus)

    band_table(rows, taus)

    print("\n  TAIL RATIO empirical/Gaussian on Gaussian-gate calls, by tau")
    print("    The 'all' column is unbounded because the Gaussian returns "
          "denormal\n    probabilities (1e-40) where the empirical floor is "
          "1/anchors; only the\n    'resolvable' column, where the Gaussian "
          "itself says >= 1e-4, is meaningful.")
    print(f"    {'tau':>4}{'r':>4}{'calls':>9}{'median (all)':>14}"
          f"{'share >1':>10}{'  |':>3}{'calls':>8}{'median':>10}"
          f"{'share >1':>10}")
    for tau in taus:
        sub = [(r, s) for r, s in gate_rows(rows, C_G)
               if r[C_TAU] == tau and r[C_S24] is not None]
        rr, rz = [], []
        for r, s in sub:
            pg = (1 - r[C_G]) if s else r[C_G]
            pe = (1 - r[C_S24]) if s else r[C_S24]
            if pg > 0:
                rr.append(pe / pg)
                if pg >= 1e-4:
                    rz.append(pe / pg)
        if not rr:
            continue
        rr.sort()
        rz.sort()
        m2 = f"{rz[len(rz)//2]:>9.2f}x" if rz else f"{'--':>10}"
        s2 = (f"{100*sum(1 for x in rz if x > 1)/len(rz):>9.0f}%"
              if rz else f"{'--':>10}")
        print(f"    {tau:>4}{tau-1:>4}{len(rr):>9,}{rr[len(rr)//2]:>13.3g}x"
              f"{100*sum(1 for x in rr if x > 1)/len(rr):>9.0f}%{'  |':>3}"
              f"{len(rz):>8,}{m2}{s2}")

    marg = [r for r in rows
            if r[C_G] is not None
            and (r[C_G] >= PIN or r[C_G] <= 1 - PIN)
            and min(r[C_G], 1 - r[C_G]) >= 1e-4]
    print(f"\n  ===== RESTRICTED TO THE DECISION-RELEVANT SLICE "
          f"(Gaussian P(flip) >= 1e-4) =====")
    mb, mk_, md = second_gate(marg, taus, C_S24,
                              f"EMPIRICAL std {W_PRIMARY}h")
    mbt = boot_close(mb, mk_)
    if mbt:
        print(f"    block bootstrap on {len({r[C_CLOSE] for r,s in mb}):,} "
              f"CLOSES, change in flip rate from adding the gate:")
        print(f"      median {100*mbt[1]:+.3f}pp, 95% CI "
              f"[{100*mbt[0]:+.3f}, {100*mbt[2]:+.3f}]pp")
    nb = len(mb)
    fb = sum(1 for r, s in mb if r[C_WON] != s)
    if nb:
        p0 = fb / nb
        # MDE stated BEFORE reading the point estimate, per the house rule:
        # two-proportion, 80% power, alpha 0.05, and then inflated by the
        # design effect for clustering on closes (1 + (m-1)*rho, rho ~ 0.8).
        m_ = nb / max(len({r[C_CLOSE] for r, s in mb}), 1)
        deff = 1 + (m_ - 1) * 0.8
        se = math.sqrt(2 * p0 * (1 - p0) / nb * deff)
        print(f"    MDE: baseline {100*p0:.2f}% on {nb:,} calls in "
              f"{len({r[C_CLOSE] for r,s in mb}):,} closes, {m_:.1f} calls per "
              f"close,\n         design effect {deff:.1f} at rho=0.8 -> "
              f"detectable difference {100*2.8*se:.2f}pp at 80% power.")
    second_gate(marg, taus, C_LEAK,
                "*** LEAK_EMP *** same estimator, window slid PAST the close")

    base, keep, drop = second_gate(rows, taus, C_S24,
                                   f"EMPIRICAL std {W_PRIMARY}h")
    bt = boot_close(base, keep)
    if bt:
        print(f"    block bootstrap on {len({r[C_CLOSE] for r,s in base}):,} "
              f"CLOSES, change in flip rate from adding the gate:")
        print(f"      median {100*bt[1]:+.3f}pp, 95% CI "
              f"[{100*bt[0]:+.3f}, {100*bt[2]:+.3f}]pp")
    for col, lab in ((C_S6, f"EMPIRICAL std {WINDOWS_H[0]}h"),
                     (C_S72, f"EMPIRICAL std {WINDOWS_H[2]}h"),
                     (C_R24, f"EMPIRICAL raw {W_PRIMARY}h")):
        second_gate(rows, taus, col, lab)

    op = one_per_market(rows)
    n = len(op)
    f = sum(1 for r in op if r[C_WON] != (1.0 if r[C_G] >= PIN else 0.0))
    opk = [r for r in op if r[C_S24] is not None and
           ((r[C_S24] >= PIN) if r[C_G] >= PIN else (r[C_S24] <= 1 - PIN))]
    fk = sum(1 for r in opk if r[C_WON] != (1.0 if r[C_G] >= PIN else 0.0))
    print(f"\n  ONE CALL PER MARKET (largest gate-open tau; the closest proxy "
          f"to a pin fire without the book)")
    print(f"    Gaussian gate    : {n:,} markets, {f} flips, "
          f"{100.0*f/max(n,1):.2f}%")
    print(f"    + empirical gate : {len(opk):,} markets, {fk} flips, "
          f"{100.0*fk/max(len(opk),1):.2f}%")

    # ---- the case study the improvement was proposed from ----------------
    cs = [r for r in rows if r[C_TICK] == "KXETH15M-26SEP071745-45"]
    if cs:
        print("\n  CASE STUDY -- KXETH15M-26SEP071745-45, the one loss in the "
              "2026-09-07 live replay")
        print(f"    {'tau':>4}{'r':>4}{'Gaussian fair':>15}"
              f"{'empirical 24h':>15}{'emp raw 24h':>13}{'gate?':>8}")
        for r in sorted(cs, key=lambda x: -x[C_TAU]):
            gt = "YES" if r[C_G] >= PIN else ("NO" if r[C_G] <= 1 - PIN else "-")
            e = "--" if r[C_S24] is None else f"{r[C_S24]:.4f}"
            w = "--" if r[C_R24] is None else f"{r[C_R24]:.4f}"
            print(f"    {r[C_TAU]:>4}{r[C_TAU]-1:>4}{r[C_G]:>15.4f}"
                  f"{e:>15}{w:>13}{gt:>8}")
        print(f"    settled {'YES' if cs[0][C_WON] else 'NO'}; pin bought the "
              f"other side at tau=5")

    if a.leaks:
        print("\n  ==================================================")
        print("  DELIBERATELY LEAKING CONTROLS -- these MUST look better.")
        print("  They are here so the reader can see what a lookahead leak")
        print("  does to these very tables. If the honest rows above looked")
        print("  like these, the honest rows would be a leak.")
        for nm in ("spot", "vol"):
            lr = score(taus, hours=a.hours, verbose=False, leak=nm)
            g = gate_rows(lr, C_G)
            n = len(g)
            fl = sum(1 for r, s in g if r[C_WON] != s)
            print(f"    LEAK_{nm.upper():<5} {n:>9,} gate calls, {fl:>5,} "
                  f"flips, {100.0*fl/max(n,1):>6.3f}%")
            del lr


if __name__ == "__main__":
    main()
