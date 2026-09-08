#!/usr/bin/env python3
# VERSION: 2026-09-08-ag1
"""acgapchk.py -- could the measured index autocorrelation be a GAP artefact?

WHAT WOULD HAVE TO BE TRUE FOR THE RESULT TO BE FAKE

acrun.py measures gamma0 from CONSECUTIVE-second pairs and V(n) from pairs n
seconds apart. Those are different samples. The index tape is 88.5% present.
If seconds go missing preferentially when the index is MOVING -- a congested
websocket during a burst is the obvious mechanism -- then gamma0 is estimated
on calm seconds while V(n) spans bursts, and V(n)/(n*gamma0) would come out
above 1 with no autocorrelation anywhere.

THE CHECK

Restrict to windows [i, i+n] in which EVERY ONE of the n+1 seconds is present,
and compute both gamma0 and V(n) on exactly those windows. Same seconds, same
market conditions, no selection difference left. If the ratio survives, the
gap story is dead and the autocorrelation is real.

Also reports the same ratio on windows that CONTAIN a gap, so the size of the
selection effect is measured rather than assumed.

SELF-TEST: a white-noise series with holes punched preferentially at large
moves. The naive ratio must be inflated and the gap-free ratio must not be --
an estimator that cannot see the artefact cannot clear the tape of it.
"""
import argparse
import glob
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from acvar import IDXDIR, hour_of, load_index                   # noqa: E402

NS = [2, 5, 10, 30, 60]


def ratios(a, n):
    """(gapfree_ratio, gapfree_windows, gappy_ratio, gappy_windows).

    Both ratios are V(n)/(n*gamma0) with gamma0 measured on the SAME windows
    that produced V(n), so nothing but the gap status differs between them."""
    gf_v = gf_g = 0.0
    gf_nv = gf_ng = 0
    gp_v = gp_g = 0.0
    gp_nv = gp_ng = 0
    L = len(a)
    for i in range(0, L - n):
        x = a[i]
        y = a[i + n]
        if x != x or y != y:
            continue
        full = True
        for j in range(i + 1, i + n):
            if a[j] != a[j]:
                full = False
                break
        if full:
            gf_v += (y - x) ** 2
            gf_nv += 1
            for j in range(i, i + n):
                gf_g += (a[j + 1] - a[j]) ** 2
                gf_ng += 1
        else:
            gp_v += (y - x) ** 2
            gp_nv += 1
            for j in range(i, i + n):
                p = a[j]
                q = a[j + 1]
                if p == p and q == q:
                    gp_g += (q - p) ** 2
                    gp_ng += 1
    gf = ((gf_v / gf_nv) / (n * gf_g / gf_ng)) if gf_nv > 100 and gf_ng \
        else float("nan")
    gp = ((gp_v / gp_nv) / (n * gp_g / gp_ng)) if gp_nv > 100 and gp_ng \
        else float("nan")
    return gf, gf_nv, gp, gp_nv


def selftest():
    print("SELF-TEST -- acgapchk")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    import array
    rng = random.Random(3)
    N = 400000
    v = 100.0
    a = array.array("d", [0.0]) * N
    d = [rng.gauss(0, 1.0) for _ in range(N)]
    for i in range(N):
        a[i] = v
        v += d[i] if i < N - 1 else 0.0
    # PUNCH HOLES where the index just moved hard. This is the artefact the
    # real check has to be able to see.
    holes = 0
    for i in range(1, N - 1):
        if abs(d[i]) > 1.6 and rng.random() < 0.75:
            a[i] = float("nan")
            holes += 1
    print("  planted %s holes at large moves (%.1f%% of the series)"
          % (format(holes, ","), 100.0 * holes / N))
    # naive: gamma0 over all consecutive pairs, V(n) over all n-apart pairs
    g0n = 0.0
    g0c = 0
    for i in range(N - 1):
        x = a[i]
        y = a[i + 1]
        if x == x and y == y:
            g0n += (y - x) ** 2
            g0c += 1
    g0 = g0n / g0c
    s = 0.0
    c = 0
    n = 30
    for i in range(N - n):
        x = a[i]
        y = a[i + n]
        if x == x and y == y:
            s += (y - x) ** 2
            c += 1
    naive = (s / c) / (n * g0)
    gf, gfn, gp, gpn = ratios(a, n)
    print("  n=30: naive ratio %.3f, gap-free ratio %.3f (%s windows), "
          "gappy %.3f" % (naive, gf, format(gfn, ","), gp))
    ck(naive > 1.15,
       "the planted artefact INFLATES the naive variance ratio (%.3f)"
       % naive)
    ck(abs(gf - 1.0) < 0.05,
       "and the gap-free ratio is clean (%.3f, must be ~1)" % gf)
    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=72)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    t0 = time.time()
    files = sorted(glob.glob(os.path.join(IDXDIR, "2026*.jsonl.gz")))[:-1]
    files = files[-a.hours:]
    print("\nINDEX HOURS: %s .. %s" % (os.path.basename(files[0]),
                                       os.path.basename(files[-1])))
    base, span, vals = load_index(files)
    if not vals:
        raise SystemExit("loaded nothing")
    print("\n  V(n)/(n*gamma0) on windows with EVERY second present, next to")
    print("  the same ratio on windows that contain a gap. gamma0 is measured")
    print("  inside the same windows, so the two differ only by gap status.")
    print("  %-14s%6s%s" % ("index", "", "".join("%9d" % n for n in NS)))
    for iid in sorted(vals):
        arr = vals[iid]
        gfs = []
        gps = []
        nw = []
        for n in NS:
            gf, gfn, gp, gpn = ratios(arr, n)
            gfs.append(gf)
            gps.append(gp)
            nw.append(gfn)
        print("  %-14s%6s%s" % (iid, "full", "".join("%9.3f" % x
                                                     for x in gfs)))
        print("  %-14s%6s%s" % ("", "gappy", "".join("%9.3f" % x
                                                     for x in gps)))
        print("  %-14s%6s%s" % ("", "n win", "".join("%9s" % format(x, ",")
                                                     for x in nw)))
    print("\n  done in %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
