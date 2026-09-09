#!/usr/bin/env python3
"""Is 'the shape predicts a large move' anything more than 'sigma_300 is
stale'?

pinmatch measures the largest future one-second move in units of sigma_300 --
the SAME sigma_300 that the fingerprint itself reports as out of date (the
event's sigma_10 is 1.94x sigma_300, z = +1.99).  Dividing a future move by a
volatility you have already established is too small is guaranteed to produce
a big number.  The test that means something is to divide by a volatility that
is NOT stale:

    jump / sigma_10    -- the most recent 10 s
    jump / sigma_C     -- max(sigma_30, sigma_300), the defensive fix the
                          report itself recommends

If the lift survives in those units the shape genuinely forecasts a jump.  If
it vanishes -- or inverts -- the whole 'large movement' finding is a restatement
of volatility persistence and carries no information the model could not get by
using a better sigma.
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinmatch as P

T0 = time.time()


def log(*a):
    print("[%7.1fs]" % (time.time() - T0), *a, flush=True)


def dist(xs, label, thresh):
    xs = sorted(xs)
    n = len(xs)
    ge = sum(1 for x in xs if x >= thresh)
    print("  %-34s n=%7d  median %6.2f  p90 %6.2f  p99 %7.2f  "
          "P(>= %.2f) = %6.2f%%"
          % (label, n, P.quantile(xs, 0.5), P.quantile(xs, 0.9),
             P.quantile(xs, 0.99), thresh, 100.0 * ge / n))
    return P.quantile(xs, 0.5), P.quantile(xs, 0.9), ge / n


def main():
    want = set(P.SERIES_TO_INDEX.values())
    log("loading")
    indices, _f = P.load_index(0, datadir=P.IDXDIR, want=want, verbose=False)
    ev = indices[P.EVENT["index"]]
    ev.build()
    raw, why, extra = P.event_fingerprint(ev)
    assert raw is not None, why
    log("scanning")
    T, _d = P.scan(indices, P.EVENT["tau"], extra["dist_over_sig"],
                   extra["z"], 5, verbose=False)
    indices.clear()
    log("cells=%d" % T.n)

    # keep the RAW features before standardise() overwrites them in place
    import array
    F_raw = array.array("f", T.F)
    scales = P.standardise(T)
    tgt = P.z_target(raw, scales, T.names.index(P.EVENT["index"]))

    r = P.analogue_test(T, tgt, 200, which="A", shuffle_reps=0)
    kept = set(i for _d2, i in r["rows"])
    print("\n  k=200 analogues found: %d" % len(kept))

    # event's own numbers
    ev_jump_s300 = extra["max1s_future_z"]
    ev_s10_s300 = raw[1]
    ev_s30_s300 = raw[2]
    ev_sC_s300 = max(1.0, ev_s30_s300)
    print("  EVENT: future max 1s move = %.2f x sigma_300"
          % ev_jump_s300)
    print("         sigma_10/sigma_300 = %.3f -> %.2f x sigma_10"
          % (ev_s10_s300, ev_jump_s300 / max(1.0, ev_s10_s300)))
    print("         sigma_C /sigma_300 = %.3f -> %.2f x sigma_C"
          % (ev_sC_s300, ev_jump_s300 / ev_sC_s300))

    # unconditional sample, same stride the report used
    step = max(1, T.n // 350000)
    uncond = [i for i in range(0, T.n, step)]

    for unit, getden, thr in (
            ("sigma_300 (pinmatch's unit -- THE STALE ONE)",
             lambda i: 1.0, ev_jump_s300),
            ("max(sigma_10, sigma_300) -- CURRENT 10 s vol, floored",
             lambda i: max(1.0, F_raw[i * P.NF + 1]),
             ev_jump_s300 / max(1.0, ev_s10_s300)),
            ("max(sigma_30, sigma_300) = sigma_C, the report's own fix",
             lambda i: max(1.0, F_raw[i * P.NF + 2]),
             ev_jump_s300 / ev_sC_s300)):
        print("\n  ---- future max 1s move measured in units of %s ----" % unit)
        print("       (threshold = the event's own jump in these units = "
              "%.2f)" % thr)
        c = [T.jumpz[i] / getden(i) for i in kept]
        u = [T.jumpz[i] / getden(i) for i in uncond]
        _m1, _p1, t1 = dist(c, "k=200 ANALOGUES", thr)
        _m0, _p0, t0 = dist(u, "UNCONDITIONAL", thr)
        print("  %-34s tail ratio = %.2fx   (p90 ratio %.2fx, "
              "median ratio %.2fx)"
              % ("", (t1 / t0) if t0 else float("nan"),
                 _p1 / _p0 if _p0 else float("nan"),
                 _m1 / _m0 if _m0 else float("nan")))
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
