#!/usr/bin/env python3
"""ADVERSARIAL VERIFICATION of research/pinmatch.py.

The three things pinmatch.py did NOT test:

 1. SELF-INCLUSION.  The event's own cell is on the scan grid (t+tau is a real
    15-min boundary, so it is force-included whatever the stride), its distance
    to the target is exactly 0, and its flip is 1 by construction.  It is
    therefore the nearest of its own k neighbours.  Re-run with it excluded.

 2. THE FLIP-CONDITIONAL PLACEBO -- the correct null.  pinmatch's placebo draws
    targets from cells chosen UNIFORMLY AT RANDOM.  But the real target was not
    chosen at random: it was chosen BECAUSE IT FLIPPED.  If flip probability
    varies smoothly over feature space (volatility clustering guarantees it
    does), then E[p(x*) | x* drawn from flipped cells] = E[p^2]/E[p] > E[p],
    i.e. the neighbourhood of ANY flipped cell is elevated with no predictive
    content whatever.  The honest question is not "is 36% > 10.2%" but "is 36%
    high AMONG THE NEIGHBOURHOODS OF FLIPPED CELLS".  Draw targets from flip==1
    cells, rarity-matched, identical machinery.

 3. A TIME-BLOCKED SHUFFLE.  pinmatch's shuffle permutes labels i.i.d. within
    an index, which destroys the temporal clustering of volatility.  If the
    ball selects volatile HOURS, an i.i.d. shuffle will call that significant.
    Reassign each analogue to a random hour of its own coin instead.
"""
import math
import os
import random
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinmatch as P

T0 = time.time()


def log(*a):
    print("[%7.1fs]" % (time.time() - T0), *a, flush=True)


def main():
    want = set(P.SERIES_TO_INDEX.values())
    log("loading index tape")
    indices, files = P.load_index(0, datadir=P.IDXDIR, want=want, verbose=False)
    ev_ix = indices[P.EVENT["index"]]
    ev_ix.build()
    raw, why, extra = P.event_fingerprint(ev_ix)
    assert raw is not None, why
    dos, zmod = extra["dist_over_sig"], extra["z"]
    log("event refingerprinted: dist/sig=%.4f z=%.4f p_lose=%.4f flipped=%s"
        % (dos, zmod, extra["p_lose_model"], extra["flipped"]))

    log("scanning tape (tau=22, stride=5)")
    T, drop = P.scan(indices, P.EVENT["tau"], dos, zmod, 5, verbose=False)
    indices.clear()
    log("cells=%d" % T.n)
    scales = P.standardise(T)
    ev_ord = T.names.index(P.EVENT["index"])
    tgt = P.z_target(raw, scales, ev_ord)

    # ---------------------------------------------------------------- 1
    print("\n" + "=" * 78)
    print("1. IS THE EVENT ITS OWN NEAREST NEIGHBOUR?")
    print("=" * 78)
    ev_t = P.EVENT["close"] - P.EVENT["tau"]
    ev_row = None
    for i in range(T.n):
        if T.t[i] == ev_t and T.ix[i] == ev_ord:
            ev_row = i
            break
    mask_noev = None
    if ev_row is None:
        print("  event cell NOT in the scan -- no self-inclusion")
    else:
        d2 = sum((T.F[ev_row * P.NF + f] - tgt[f]) ** 2 for f in range(P.NF))
        print("  event cell IS row %d, t=%d, distance to target = %.6f"
              % (ev_row, T.t[ev_row], math.sqrt(d2)))
        print("  its flipA=%d flipB=%d flipC=%d flipD=%d aligned=%d"
              % (T.flipA[ev_row], T.flipB[ev_row], T.flipC[ev_row],
                 T.flipD[ev_row], T.aligned[ev_row]))
        print("  -> the target is a member of its own analogue set, with an")
        print("     outcome that is a flip BY CONSTRUCTION.")
        mask_noev = bytearray(b"\x01" * T.n)
        mask_noev[ev_row] = 0

    print("\n  RE-RUN WITH THE EVENT CELL EXCLUDED:")
    print("  %-6s%6s%12s%12s%12s%10s"
          % ("which", "k", "incl rate", "excl rate", "excl ratio", "excl p"))
    for which in ("A", "B", "C", "D"):
        for k in (50, 200, 1000):
            r_in = P.analogue_test(T, tgt, k, which=which, shuffle_reps=2000)
            r_ex = P.analogue_test(T, tgt, k, which=which, shuffle_reps=2000,
                                   row_mask=mask_noev)
            print("  %-6s%6d%11.2f%%%11.2f%%%12.2f%10.4f"
                  % (which, k, 100 * r_in["rate"], 100 * r_ex["rate"],
                     r_ex["ratio"], r_ex["p_shuffle"]))

    # ---------------------------------------------------------------- 2
    print("\n" + "=" * 78)
    print("2. THE FLIP-CONDITIONAL PLACEBO -- the null pinmatch did not test")
    print("=" * 78)
    real = {}
    for which in ("A", "B"):
        real[which] = P.analogue_test(T, tgt, 200, which=which,
                                      shuffle_reps=2000)
        print("  REAL placement %s: k=200 rate=%.2f%% base=%.4f%% "
              "ratio=%.2f radius=%.3f"
              % (which, 100 * real[which]["rate"], 100 * real[which]["base"],
                 real[which]["ratio"], real[which]["radius"]))

    NDRAW = int(os.environ.get("VP_PLACEBOS", "150"))
    for which in ("A", "B"):
        col = P._col(T, which)
        pool_idx = [i for i in range(T.n) if col[i]]
        print("\n  placement %s: %d cells flipped; drawing targets FROM THOSE"
              % (which, len(pool_idx)))
        rnd = random.Random(4242)
        rr = real[which]
        rates, radii = [], []
        tried = 0
        while len(rates) < NDRAW and tried < NDRAW * 8:
            tried += 1
            j = rnd.choice(pool_idx)
            if j == ev_row:
                continue
            t2 = [T.F[j * P.NF + f] for f in range(P.NF)]
            # NOTE: no row_mask.  The placebo target is left in its
            # own neighbour set exactly as the real target is left in
            # its own, so the comparison is like for like (and
            # base_rate's O(n) masked path is avoided).
            r = P.analogue_test(T, t2, 200, which=which,
                                shuffle_reps=0)
            if r["n"] < 100:
                continue
            if not (0.5 * rr["radius"] <= r["radius"] <= 2.0 * rr["radius"]):
                continue
            rates.append(r["rate"])
            radii.append(r["radius"])
            if len(rates) % 25 == 0:
                log("    %s: %d/%d placebos" % (which, len(rates), NDRAW))
        rates.sort()
        n = len(rates)
        if n < 20:
            print("    only %d rarity-matched placebos -- NO POWER" % n)
            continue
        r_ex = P.analogue_test(T, tgt, 200, which=which, shuffle_reps=0,
                               row_mask=mask_noev)
        ge = sum(1 for x in rates if x >= r_ex["rate"])
        print("    kept %d rarity-matched flip-conditional placebos "
              "(tried %d)" % (n, tried))
        print("    placebo neighbour flip rate: min %.2f%% p25 %.2f%% "
              "median %.2f%% p75 %.2f%% p90 %.2f%% max %.2f%%"
              % (100 * rates[0], 100 * P.quantile(rates, 0.25),
                 100 * P.quantile(rates, 0.5), 100 * P.quantile(rates, 0.75),
                 100 * P.quantile(rates, 0.9), 100 * rates[-1]))
        print("    unconditional base rate for %s: %.4f%%"
              % (which, 100 * rr["base"]))
        print("    MEDIAN PLACEBO / BASE = %.2fx   <- the lift you get for "
              "FREE by picking a target that flipped"
              % (P.quantile(rates, 0.5) / rr["base"]))
        print("    REAL (event excluded) = %.2f%%" % (100 * r_ex["rate"]))
        ge_in = sum(1 for x in rates if x >= rr["rate"])
        print("    REAL (event INCLUDED, like-for-like) = %.2f%%"
              % (100 * rr["rate"]))
        print("    placebos >= real(excl): %d/%d -> p = %.4f"
              % (ge, n, (ge + 1.0) / (n + 1.0)))
        print("    placebos >= real(incl): %d/%d -> p = %.4f   <-- LIKE FOR LIKE"
              % (ge_in, n, (ge_in + 1.0) / (n + 1.0)))
        print("    placebo radii median %.3f vs real %.3f"
              % (P.quantile(radii, 0.5), rr["radius"]))

    # ---------------------------------------------------------------- 3
    print("\n" + "=" * 78)
    print("3. BLOCK SHUFFLE -- reassign analogues to random HOURS, not cells")
    print("=" * 78)
    for which in ("A", "B"):
        r_ex = P.analogue_test(T, tgt, 200, which=which, shuffle_reps=2000,
                               row_mask=mask_noev)
        kept = r_ex["rows"]
        kf = r_ex["flips"]
        col = P._col(T, which)
        blocks = defaultdict(lambda: [0, 0])
        for i in range(T.n):
            b = blocks[(T.ix[i], T.t[i] // 3600)]
            b[0] += 1
            b[1] += col[i]
        by_ix = defaultdict(list)
        for (o, h), nk in blocks.items():
            if nk[0] >= 20:
                by_ix[o].append(nk[1] / nk[0])
        comp = defaultdict(int)
        for _d, i in kept:
            comp[(T.ix[i], T.t[i] // 3600)] += 1
        rnd = random.Random(11)
        REPS = 2000
        ge = 0
        for _ in range(REPS):
            tot = 0
            for oh, cnt in comp.items():
                lst = by_ix.get(oh[0])
                if not lst:
                    continue
                pr = rnd.choice(lst)
                for _i in range(cnt):
                    if rnd.random() < pr:
                        tot += 1
            if tot >= kf:
                ge += 1
        print("  placement %s: k=200 flips=%d/%d (%.2f%%)"
              % (which, kf, r_ex["n"], 100 * r_ex["rate"]))
        print("    i.i.d.-within-coin shuffle p (pinmatch's) = %.4f"
              % r_ex["p_shuffle"])
        print("    HOUR-BLOCK shuffle p (each analogue reassigned to a random "
              "hour of its own coin) = %.4f" % ((ge + 1.0) / (REPS + 1.0)))

    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
