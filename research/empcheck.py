#!/usr/bin/env python3
# VERSION: 2026-09-08-ec1
"""empcheck.py -- NEW FILE, READ-ONLY. Reconcile empfair's fast machinery
against brute force, on real cells, by hand.

WHY THIS EXISTS. empfair replaces three things with fast equivalents: a
prefix-sum sigma, per-hour PRE-SORTED float32 arrays of forward moves, and a
bisect over a merged set of those arrays. Each is a place a silent error hides,
and the project's history is that every large edge it has produced was a
measurement bug. So this file recomputes, for randomly chosen real cells:

  * locked_sum, r, spot, sigma, mu, sd, fair_G      -- direct loops, no prefixes
  * required_move                                    -- from the definition
  * the RAW empirical tail                           -- one explicit pass over
    every trailing anchor, computing mean(v[t+1..t+r]) - v[t] with a plain sum
  * the STANDARDISED empirical tail                  -- same explicit pass, in
    float64, no sorting and no bisect

and it independently RE-DERIVES the causality bound: the maximum index second
any anchor in the brute-force set touches, which must be strictly below the
close being priced. That is the no-lookahead claim checked as arithmetic
rather than asserted in a docstring.

It also prints the ETH figure the improvement was proposed from, so that
number is measured here rather than quoted.
"""
import argparse
import math
import os
import random
import sys
import time
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import idxload                                              # noqa: E402
import empfair                                              # noqa: E402
from empfair import IndexModel, SERIES_TO_INDEX, PIN, W_PRIMARY, S_r  # noqa
from empscore import load_markets                           # noqa: E402
from engine import var_factor, N_AVG                        # noqa: E402

ND = NormalDist()


def bf_sigma(v, base, now, win=300, need=20):
    """pincal.sigma_from, written out: consecutive-second diffs only."""
    ds = []
    for s in range(now - win + 1, now + 1):
        i, j = s - base, s - 1 - base
        a, b = v[j], v[i]
        if a == a and b == b:
            ds.append(b - a)
    if len(ds) < need:
        return None
    m = sum(ds) / len(ds)
    return math.sqrt(sum((x - m) ** 2 for x in ds) / (len(ds) - 1))


def brute(im, close_s, tau, K, rd, hours=W_PRIMARY):
    v, base, n = im.v, im.base, im.n
    now = close_s - tau
    lo, hi = close_s - N_AVG, min(now, close_s - 1)
    got = []
    for s in range(lo, hi + 1):
        x = v[s - base]
        if x == x:
            got.append(x)
    want = hi - lo + 1
    if not got or len(got) < want * 0.95:
        return None
    locked = sum(got) * (want / len(got))
    r = N_AVG - want
    spot = v[now - base]
    sg = bf_sigma(v, base, now)
    if spot != spot or sg is None or sg <= 0:
        return None
    K_eff = K - 0.5 * (10.0 ** (-rd))
    mu = (locked + r * spot) / N_AVG
    sd = sg * math.sqrt(var_factor(int(r), [1.0]))
    fair_g = ND.cdf((mu - K_eff) / sd)
    req = (N_AVG / r) * (K_eff - mu)
    scale = sg * math.sqrt(S_r(r)) / r
    z0 = req / scale

    # ---- the anchor set, derived here from scratch ----------------------
    h_hi = ((now - base - r) // 3600) - 1
    h_lo = max(0, h_hi - hours + 1)
    a_lo = base + h_lo * 3600
    a_hi = base + (h_hi + 1) * 3600 - 1
    touched = -1
    craw = ctot = czn = czc = 0
    for t in range(a_lo, a_hi + 1):
        i = t - base
        a = v[i]
        if a != a:
            continue
        s = 0.0
        ok = True
        for k in range(1, r + 1):
            x = v[i + k]
            if x != x:
                ok = False
                break
            s += x
        if not ok:
            continue
        touched = max(touched, t + r)
        m = s / r - a
        ctot += 1
        if m >= req:
            craw += 1
        g = im.sig[i]
        if g == g and g > 0:
            czn += 1
            if m / (g * scale / sg) >= z0:
                czc += 1
    return dict(r=r, mu=mu, sigma=sg, sd=sd, fair_g=fair_g, req=req, z0=z0,
                raw=(craw / ctot if ctot else None), nraw=ctot,
                std=(czc / czn if czn else None), nstd=czn,
                touched=touched, close=close_s, now=now)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", type=int, default=14)
    ap.add_argument("--seed", type=int, default=17)
    a = ap.parse_args()

    mk = [m for m in load_markets()]
    rng = random.Random(a.seed)
    rng.shuffle(mk)

    # one index at a time keeps memory at one IndexModel
    want_series = ["KXETH15M", "KXBTC15M", "KXDOGE15M", "KXSOL15M"]
    taus = [3, 5, 10, 20]
    dense = idxload.load(sorted({SERIES_TO_INDEX[s] for s in want_series}),
                         verbose=False)
    worst = dict(fair=0.0, raw=0.0, std=0.0)
    ncheck = 0
    minslack = None
    for s in want_series:
        iid = SERIES_TO_INDEX[s]
        im = IndexModel(dense[iid], [t - 1 for t in taus])
        cand = [m for m in mk if m["series"] == s]
        done = 0
        print(f"\n  {s} / {iid}")
        print(f"    {'ticker':<32}{'tau':>4}{'fair_G fast':>14}"
              f"{'fair_G brute':>14}{'raw fast':>11}{'raw brute':>11}"
              f"{'std fast':>11}{'std brute':>11}{'slack s':>9}")
        for m in cand:
            if done >= a.cells // len(want_series) + 1:
                break
            # Reconcile the cells that DECIDE things. A random market is 40
            # sigma from its strike and every column prints 1.000000, which
            # checks nothing: the first version of this file did that and
            # "agreed to 0.000e+00" without ever exercising a bisect.
            hit = None
            for tau in taus:
                f = im.price(m["close"], tau, m["K"], m["rd"])
                if f is None:
                    continue
                q = min(f["fair_g"], 1 - f["fair_g"])
                if 1e-5 <= q <= 0.3:
                    hit = tau
                    break
            if hit is None:
                continue
            tau = hit
            f = im.price(m["close"], tau, m["K"], m["rd"])
            b = brute(im, m["close"], tau, m["K"], m["rd"])
            if f is None or b is None:
                continue
            done += 1
            ncheck += 1
            df = abs(f["fair_g"] - b["fair_g"])
            dr = abs((f["raw%d" % W_PRIMARY] or 0) - (b["raw"] or 0))
            dz = abs((f["std%d" % W_PRIMARY] or 0) - (b["std"] or 0))
            worst["fair"] = max(worst["fair"], df)
            worst["raw"] = max(worst["raw"], dr)
            worst["std"] = max(worst["std"], dz)
            slack = b["close"] - b["touched"]
            minslack = slack if minslack is None else min(minslack, slack)
            print(f"    {m['ticker'][:32]:<32}{tau:>4}{f["fair_g"]:>14.8f}"
                  f"{b["fair_g"]:>14.8f}{(f['raw%d'%W_PRIMARY] or -1):>11.5f}"
                  f"{(b['raw'] or -1):>11.5f}{(f['std%d'%W_PRIMARY] or -1):>11.5f}"
                  f"{(b['std'] or -1):>11.5f}{slack:>9,}")
        del im

    print(f"\n  {ncheck} cells reconciled against brute force")
    print(f"    worst |fair_G fast - brute|          {worst['fair']:.3e}")
    print(f"    worst |raw empirical fast - brute|   {worst['raw']:.3e}")
    print(f"    worst |std empirical fast - brute|   {worst['std']:.3e}")
    print(f"    NO-LOOKAHEAD, re-derived here: the highest index second any "
          f"anchor touched\n    sat at least {minslack:,} s BEFORE the close "
          f"it was pricing, over every cell above.")

    # ---- the ETH number the improvement was proposed from ---------------
    iid = "ETHUSD_RTI"
    d = dense.get(iid)
    if d is not None:
        v, base, n = d.v, d.base, d.n
        for r in (4,):
            ms = []
            for i in range(n - r):
                a = v[i]
                if a != a:
                    continue
                s = 0.0
                ok = True
                for k in range(1, r + 1):
                    x = v[i + k]
                    if x != x:
                        ok = False
                        break
                    s += x
                if ok:
                    ms.append(abs(s / r - a))
            ms.sort()
            print(f"\n  ETHUSD_RTI |{r}-print forward average - spot|, whole "
                  f"tape, {len(ms):,} windows")
            for q in (0.5, 0.9, 0.99, 0.999, 0.9999):
                print(f"    p{100*q:<7g} {ms[int(q*len(ms))]:.4f} USD")
            print(f"    max      {ms[-1]:.4f} USD")


if __name__ == "__main__":
    main()
