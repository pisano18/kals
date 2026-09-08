#!/usr/bin/env python3
# VERSION: 2026-09-08-eg1
"""empsig.py -- NEW FILE, READ-ONLY. Is the Gaussian's miscalibration bigger
than chance, once n is counted in CLOSES and not in market-seconds?

The reliability table in empscore.py prints Wilson intervals on CELLS. That is
the wrong unit whenever several coins clear the gate at the same quarter hour,
because all twelve settle off correlated indices. This file:

  * counts, for each stated-probability band, how many CLOSES the calls and the
    flips actually fall in
  * gives the exact binomial tail P(flips >= observed | the model's own stated
    probability) at the cell unit, and again after collapsing to ONE CALL PER
    CLOSE (the most conservative unit available -- if two coins flip at the
    same close it counts as one)
  * lists the flips so a human can see whether they are one bad afternoon

If the miscalibration survives the one-call-per-close collapse it is not a
clustering artefact.
"""
import argparse
import math
import os
import random
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import empfair                                              # noqa: E402
from empscore import (score, gate_rows, C_CLOSE, C_SER, C_TICK, C_TAU, C_WON,
                      C_G, C_S24, TAUS)                     # noqa: E402
from empfair import PIN                                     # noqa: E402

BANDS = [(1e-4, 1e-3), (1e-3, 5e-3), (5e-3, 1e-2), (1e-2, 2e-2), (1e-4, 2e-2)]


def binom_tail(k, n, p):
    """P(X >= k) for X ~ Binomial(n, p), exact, log-space."""
    if k <= 0:
        return 1.0
    if p <= 0:
        return 0.0
    lp, lq = math.log(p), math.log1p(-p)
    tot = 0.0
    lg = math.lgamma
    for i in range(k, n + 1):
        t = lg(n + 1) - lg(i + 1) - lg(n - i + 1) + i * lp + (n - i) * lq
        tot += math.exp(t)
        if t < -60 and i > k + 5:
            break
    return min(tot, 1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taus", default=",".join(str(t) for t in TAUS))
    a = ap.parse_args()
    taus = [int(x) for x in a.taus.split(",")]
    rows = score(taus, verbose=True)
    g = gate_rows(rows, C_G)
    print(f"\n  {len(g):,} Gaussian gate calls")

    print("\n  IS THE GAUSSIAN'S OVERCONFIDENCE BIGGER THAN CHANCE?")
    print("  Cell unit first, then collapsed to one call per close (a close")
    print("  where any call flipped counts as one flip). The collapse is the")
    print("  conservative bound: it throws away every repeat within a close.")
    print(f"    {'Gaussian says':>17}{'calls':>8}{'flips':>7}{'closes':>8}"
          f"{'flip closes':>12}{'stated':>9}{'realised':>10}"
          f"{'P(cells)':>11}{'P(closes)':>11}")
    for lo, hi in BANDS:
        sub = [(r, s) for r, s in g
               if lo <= (((1 - r[C_G]) if s else r[C_G])) < hi]
        if not sub:
            continue
        n = len(sub)
        fl = sum(1 for r, s in sub if r[C_WON] != s)
        p = sum(((1 - r[C_G]) if s else r[C_G]) for r, s in sub) / n
        cl = {r[C_CLOSE] for r, s in sub}
        fc = {r[C_CLOSE] for r, s in sub if r[C_WON] != s}
        pcell = binom_tail(fl, n, p)
        pclose = binom_tail(len(fc), len(cl), p)
        print(f"    {('%.0e-%.0e' % (lo, hi)):>17}{n:>8,}{fl:>7}{len(cl):>8,}"
              f"{len(fc):>12}{100*p:>8.3f}%{100*fl/n:>9.3f}%"
              f"{pcell:>11.2e}{pclose:>11.2e}")

    print("\n  SAME BANDS, EMPIRICAL std 24h stated probability")
    print(f"    {'empirical says':>17}{'calls':>8}{'flips':>7}{'closes':>8}"
          f"{'flip closes':>12}{'stated':>9}{'realised':>10}"
          f"{'P(cells)':>11}{'P(closes)':>11}")
    ge = gate_rows(rows, C_S24)
    for lo, hi in BANDS:
        sub = [(r, s) for r, s in ge
               if r[C_S24] is not None
               and lo <= (((1 - r[C_S24]) if s else r[C_S24])) < hi]
        if not sub:
            continue
        n = len(sub)
        fl = sum(1 for r, s in sub if r[C_WON] != s)
        p = sum(((1 - r[C_S24]) if s else r[C_S24]) for r, s in sub) / n
        cl = {r[C_CLOSE] for r, s in sub}
        fc = {r[C_CLOSE] for r, s in sub if r[C_WON] != s}
        print(f"    {('%.0e-%.0e' % (lo, hi)):>17}{n:>8,}{fl:>7}{len(cl):>8,}"
              f"{len(fc):>12}{100*p:>8.3f}%{100*fl/n:>9.3f}%"
              f"{binom_tail(fl, n, p):>11.2e}"
              f"{binom_tail(len(fc), len(cl), p):>11.2e}")

    # ---- are the flips one bad afternoon? --------------------------------
    marg = [(r, s) for r, s in g
            if 1e-4 <= (((1 - r[C_G]) if s else r[C_G])) < 2e-2]
    fl = [(r, s) for r, s in marg if r[C_WON] != s]
    byday = defaultdict(int)
    for r, s in fl:
        byday[time.strftime("%m-%d", time.gmtime(r[C_CLOSE]))] += 1
    nday = defaultdict(int)
    for r, s in marg:
        nday[time.strftime("%m-%d", time.gmtime(r[C_CLOSE]))] += 1
    print(f"\n  THE {len(fl)} FLIPS IN THE MARGINAL BAND, BY DAY "
          f"(are they one afternoon?)")
    print(f"    {'day':<8}{'calls':>8}{'flips':>7}")
    for d in sorted(nday):
        print(f"    {d:<8}{nday[d]:>8}{byday.get(d, 0):>7}")
    print(f"    flips fall on {len(byday)} of {len(nday)} days, "
          f"{len({r[C_CLOSE] for r, s in fl})} distinct closes, "
          f"{len({r[C_SER] for r, s in fl})} distinct series")
    print(f"\n    each flip, and what each estimator had said:")
    print(f"    {'ticker':<34}{'tau':>4}{'gauss':>9}{'emp24':>9}"
          f"{'emp gate would':>16}")
    for r, s in sorted(fl, key=lambda x: x[0][C_CLOSE]):
        e = r[C_S24]
        blocked = "-"
        if e is not None:
            blocked = "PASS" if ((e >= PIN) if s else (e <= 1 - PIN)) else "BLOCK"
        print(f"    {r[C_TICK][:34]:<34}{r[C_TAU]:>4}{r[C_G]:>9.5f}"
              f"{(-1 if e is None else e):>9.5f}{blocked:>16}")


if __name__ == "__main__":
    main()
