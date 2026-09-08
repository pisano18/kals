#!/usr/bin/env python3
# VERSION: 2026-09-08-rz1
"""remainz.py -- IS THE INDEX ACTUALLY MEAN-REVERTING, AND WHAT WOULD EACH
ESTIMATOR HAVE DONE TO THE KNOWN ETH LOSS?

Three things remain.py could not answer from a |z| table:

1. SIGNED z.  Bucketing on |spot - trailing mean| hides direction.  Mean
   reversion means the future mean sits on the OPPOSITE side of spot from the
   move that just happened, i.e. E[target - spot] has the opposite sign to
   z = (spot - mean5)/sigma.  Momentum means the same sign.  A |z| table
   cannot tell those apart; this one can.

2. IS RMSE OUTLIER-DRIVEN?  RMSE over 118k cells can be moved by a handful of
   jumps.  Median |error| and p95 |error| say whether the conclusion survives
   a robust statistic.

3. THE KNOWN LOSS.  KXETH15M-26SEP071745-45 -- ETHUSD_RTI dipped to 2492.60
   at tau 5-6, the model priced fair 0.005 and bought NO at 0.903, and the
   index recovered to 2493.08 by tau=3 for a settle of 2492.8158 -> YES.
   Every estimator is priced on that exact market at every tau, using ONLY
   parameters fitted on closes strictly before it.

NO PEEKING: identical discipline to remain.py.  Closes are walked in time
order; the Fitter is updated only after a close has been scored; when the
walk reaches the ETH close the fitted state is snapshotted and used, and the
ETH close itself is scored before being absorbed.
"""
import argparse
import calendar
import json
import math
import os
import sys
import time
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import remain                                               # noqa: E402
from remain import (cell, Fitter, estimates, EST_ORDER, KFIX, KS, IDX_IDS,
                    load_cache)                             # noqa: E402
from remainfv import eff_strike, fair_from, rw_rmse         # noqa: E402
from engine import var_factor, N_AVG                        # noqa: E402

ND = NormalDist()
PIN = 0.98
ETH_CLOSE = calendar.timegm((2026, 9, 7, 21, 45, 0))
# The Kalshi ticker stamp 26SEP071745 is EASTERN time, not UTC.  Taking it
# as UTC reconstructs a different market entirely (strike 2489.05, settle
# 2492.654, no dip), which is why the identity below is asserted against
# the two numbers already on the record rather than trusted.
ETH_STRIKE_ON_RECORD = 2492.82
ETH_SETTLE_ON_RECORD = 2492.8158
ETH_D = 2                       # round_digits for KXETH15M, measured + API


def pct(xs, q):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    i = min(len(xs) - 1, max(0, int(q * (len(xs) - 1))))
    return xs[i]


def selftest():
    print("SELF-TEST -- remainz")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    stamp = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(ETH_CLOSE))
    ck(stamp == "2026-09-07T21:45Z" and ETH_CLOSE % 900 == 0,
       "the ETH close resolves to the right epoch (%d -> %s)"
       % (ETH_CLOSE, stamp))

    # signed-z detector: plant reversion and plant momentum, and require the
    # table to separate them.
    import random
    from array import array
    for tag, phi, want in (("reverting", -0.6, "negative"),
                           ("trending", +0.6, "positive")):
        rng = random.Random(3)
        num = den = 0.0
        for _ in range(400):
            a = array("d", [remain.NAN]) * 1000
            v, d = 100.0, 0.0
            for s in range(1000):
                d = phi * d + rng.gauss(0, 1.0)
                v += d
                a[s] = v
            c = cell(a, 0, 900, 10)
            if c is None:
                continue
            z = (c["p0"] - c["mk"][KFIX]) / c["sigma"]
            e = (c["target"] - c["p0"]) / c["sigma"]
            num += z * e
            den += z * z
        slope = num / den if den else 0.0
        ok = (slope < -0.05) if want == "negative" else (slope > 0.05)
        ck(ok, "planted %s world gives slope of (target-spot) on z = %+.3f "
               "(want %s)" % (tag, slope, want))

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


ZEDGES = [-1e9, -2.0, -1.0, -0.5, 0.5, 1.0, 2.0, 1e9]
ZLAB = ["z < -2", "-2 .. -1", "-1 .. -0.5", "-0.5 .. 0.5",
        "0.5 .. 1", "1 .. 2", "z > 2"]


def zbin(z):
    for i in range(len(ZEDGES) - 1):
        if ZEDGES[i] <= z < ZEDGES[i + 1]:
            return i
    return len(ZLAB) - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--taus", default="3,4,5,6,8,10,12,15,20")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    print()
    meta, ticks, avg60 = load_cache()
    base, n = meta["t0"], meta["n"]
    taus = [int(x) for x in a.taus.split(",")]
    closes = list(range(base + (900 - base % 900) % 900, base + n, 900))

    fit = Fitter()
    zerr = defaultdict(lambda: [0, 0.0, 0.0])     # zbin -> n, sum e, sum e^2
    zslope_num = zslope_den = 0.0
    abserr = defaultdict(list)                    # estimator -> |error|
    eth = None
    per_close_sq = defaultdict(lambda: defaultdict(list))
    t0 = time.time()

    for C in closes:
        rows = []
        for iid in IDX_IDS:
            arr = ticks[iid]
            for tau in taus:
                c = cell(arr, base, C, tau)
                if c is not None:
                    rows.append((iid, c))
        if not rows:
            continue
        for iid, c in rows:
            sg = c["sigma"]
            z = (c["p0"] - c["mk"][KFIX]) / sg
            e_spot = (c["target"] - c["p0"]) / sg
            b = zbin(z)
            zerr[b][0] += 1
            zerr[b][1] += e_spot
            zerr[b][2] += e_spot * e_spot
            zslope_num += z * e_spot
            zslope_den += z * z
            es = estimates(c, fit, iid)
            for name in EST_ORDER:
                if name.startswith("LEAK"):
                    continue
                er = (c["target"] - es[name]) / sg
                abserr[name].append(abs(er))
                per_close_sq[name][C].append(er * er)
        if C == ETH_CLOSE:
            eth = snapshot_eth(ticks, base, fit)
        for iid, c in rows:
            fit.absorb_cell(c)
        for iid in IDX_IDS:
            fit.absorb_acf(iid, ticks[iid], base, C)

    print("  walked %d closes in %.0f s" % (len(closes), time.time() - t0))

    print("\n  MEAN REVERSION, DIRECTLY.  z = (spot - mean5)/sigma, signed.")
    print("  error = (mean of the actual remaining prints - spot)/sigma.")
    print("  Mean reversion => mean error has the OPPOSITE sign to z.")
    print("    %-12s %9s %13s %11s" % ("z bucket", "n", "mean error", "SE"))
    for b in range(len(ZLAB)):
        nn, s, s2 = zerr[b]
        if not nn:
            continue
        m = s / nn
        var = max(s2 / nn - m * m, 0.0)
        se = math.sqrt(var / nn)
        print("    %-12s %9d %+13.5f %11.5f" % (ZLAB[b], nn, m, se))
    slope = zslope_num / zslope_den if zslope_den else float("nan")
    print("    OLS slope of error on z = %+.5f" % slope)
    print("    negative slope = mean reversion, positive = momentum, 0 = "
          "martingale.")
    print("    NOTE the SE here is the naive per-cell one; the independent")
    print("    unit is the close.  It is printed only to show the point")
    print("    estimates are small relative to their own scatter.")

    print("\n  IS THE RMSE VERDICT OUTLIER-DRIVEN?  robust error stats")
    print("    %-14s %10s %11s %11s %11s"
          % ("estimator", "n", "median|e|", "p90|e|", "p99|e|"))
    for name in EST_ORDER:
        if name.startswith("LEAK"):
            continue
        v = abserr[name]
        print("    %-14s %10d %11.4f %11.4f %11.4f"
              % (name, len(v), pct(v, 0.50), pct(v, 0.90), pct(v, 0.99)))

    print("\n  MDE OF THE PAIRED CLOSE-CLUSTERED TEST (what a real")
    print("  improvement would have had to be for this study to see it)")
    cl = sorted(per_close_sq["spot"])
    for name in ("mean3", "shrink", "ar1"):
        ds = []
        for C in cl:
            a1, a2 = per_close_sq["spot"][C], per_close_sq[name][C]
            if len(a1) != len(a2) or not a1:
                continue
            ds.append(sum(a2) / len(a2) - sum(a1) / len(a1))
        m = sum(ds) / len(ds)
        v = sum((x - m) ** 2 for x in ds) / (len(ds) - 1)
        se = math.sqrt(v / len(ds))
        base_mse = sum(sum(per_close_sq["spot"][C]) / len(per_close_sq["spot"][C])
                       for C in cl) / len(cl)
        mde = 2.8 * se
        print("    %-12s closes %d  dMSE %+.6f  SE %.6f  "
              "MDE(80%%,5%%) %.6f = %.2f%% of spot MSE"
              % (name, len(ds), m, se, mde, 100 * mde / base_mse))

    if eth:
        print_eth(eth)
    else:
        print("\n  ETH case study: close %d not present in the index cache"
              % ETH_CLOSE)


def snapshot_eth(ticks, base, fit):
    """Price KXETH15M-26SEP071745-45 under every estimator, with the fitter
    state as it stood BEFORE this close was absorbed."""
    arr = ticks["ETHUSD_RTI"]
    C = ETH_CLOSE
    i = C - base
    prev = [arr[j] for j in range(i - 900 - N_AVG, i - 900)]
    cur = [arr[j] for j in range(i - N_AVG, i)]
    if any(v != v for v in prev) or any(v != v for v in cur):
        return None
    strike = round(sum(prev) / N_AVG, ETH_D)
    settle = sum(cur) / N_AVG
    K = eff_strike(strike, ETH_D)
    won = 1.0 if round(settle, ETH_D) >= strike else 0.0
    out = dict(strike=strike, settle=settle, K=K, won=won, rows=[],
               path=[(C - base - t, arr[i - t]) for t in range(12, 0, -1)])
    for tau in (10, 8, 6, 5, 4, 3):
        c = cell(arr, base, C, tau)
        if c is None:
            continue
        es = estimates(c, fit, "ETHUSD_RTI")
        sdA = c["sigma"] * math.sqrt(var_factor(c["r"], [1.0]))
        row = dict(tau=tau, r=c["r"], spot=c["p0"], sigma=c["sigma"],
                   target=c["target"], sd=sdA,
                   z=(c["p0"] - c["mk"][KFIX]) / c["sigma"],
                   lam=fit.lam(c["r"], KFIX), phi=fit.phi("ETHUSD_RTI"),
                   est={}, fair={})
        for name in EST_ORDER:
            row["est"][name] = es[name]
            row["fair"][name] = fair_from(c["locked"], c["want"], c["r"],
                                          es[name], K, sdA)
        out["rows"].append(row)
    return out


def print_eth(e):
    print("\n" + "=" * 74)
    print("  THE KNOWN LOSS: KXETH15M-26SEP071745-45")
    print("  strike rebuilt from the previous window's 60 prints = %.4f"
          % e["strike"])
    print("  settle rebuilt from this window's 60 prints          = %.6f"
          % e["settle"])
    print("  effective threshold K - 0.5e-2                        = %.4f"
          % e["K"])
    print("  settles %s   (round(settle,2) = %.2f vs strike %.2f)"
          % ("YES" if e["won"] else "NO", round(e["settle"], 2), e["strike"]))
    ok = (abs(e["strike"] - ETH_STRIKE_ON_RECORD) < 5e-3
          and abs(e["settle"] - ETH_SETTLE_ON_RECORD) < 5e-5)
    print("  IDENTITY CHECK vs the numbers already on the record "
          "(strike %.2f, settle %.4f): %s"
          % (ETH_STRIKE_ON_RECORD, ETH_SETTLE_ON_RECORD,
             "MATCH" if ok else "*** MISMATCH - WRONG MARKET ***"))
    print("  index path, last 12 seconds: "
          + " ".join("%.2f" % v for _, v in e["path"]))
    print("\n  FAIR VALUE UNDER EACH ESTIMATOR (all params fitted on earlier")
    print("  closes only).  pin buys NO when fair <= 0.02.")
    names = ["spot", "mean2", "mean3", "mean5", "mean10", "shrink",
             "shrink_ksel", "ar1", "LEAK_oracle"]
    hdr = "    %-4s %8s %8s %8s" % ("tau", "spot", "truth", "sd")
    for nm in names:
        hdr += " %9s" % nm[:9]
    print(hdr)
    for r in e["rows"]:
        line = "    %-4d %8.2f %8.4f %8.4f" % (r["tau"], r["spot"],
                                               r["target"], r["sd"])
        for nm in names:
            line += " %9.4f" % r["fair"][nm]
        print(line)
    print("\n  the estimate of the remaining prints itself (truth in bold "
          "position 2)")
    hdr = "    %-4s %8s %8s" % ("tau", "spot", "truth")
    for nm in ("mean2", "mean3", "mean5", "mean10", "shrink", "ar1"):
        hdr += " %9s" % nm
    print(hdr)
    for r in e["rows"]:
        line = "    %-4d %8.2f %8.4f" % (r["tau"], r["spot"], r["target"])
        for nm in ("mean2", "mean3", "mean5", "mean10", "shrink", "ar1"):
            line += " %9.4f" % r["est"][nm]
        print(line)
    print("\n  walk-forward params in force at that close:")
    for r in e["rows"]:
        print("    tau %-3d r %-3d sigma %.4f  z %+.3f  lam(r,k=5) %s  "
              "phi %s" % (r["tau"], r["r"], r["sigma"], r["z"],
                          ("%.3f" % r["lam"]) if r["lam"] is not None else "--",
                          ("%+.4f" % r["phi"]) if r["phi"] is not None else "--"))
    print("=" * 74)


if __name__ == "__main__":
    main()
