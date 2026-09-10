#!/usr/bin/env python3
# VERSION: 2026-09-10-pt1
"""pintail.py -- STOP COUNTING FLIPS. MEASURE THE ERROR THAT CAUSES THEM.

WHY THIS FILE EXISTS

pincross.py asked the right question -- do the other ten coins tell us this
close is dangerous? -- and could not answer it. The reason is arithmetic, not
biology: the whole historical tape contains 254 markets that pass our live
rule and exactly TWO of them flipped. Its own stated MDE was +3.34pp and the
shuffled control produced a LARGER apparent effect (+2.78pp) than the real
signal (+2.50pp). Counting flips on this dataset is hopeless and no amount of
cleverness about factors changes that.

THE FIX IS TO CHANGE THE MEASUREMENT, NOT THE FACTOR.

A flip is a rare binary event, but it is produced by a continuous one. With
tau seconds left we forecast the settlement mean as

    mu = (locked_sum + r * spot) / 60          r = unpublished prints

and we claim its error has standard deviation

    sd = sigma_300s * sqrt(var_factor(r))

Define the STANDARDISED FORECAST ERROR, one real number per market:

    surprise = (settle - mu) / sd

Every settled market yields one, whether or not anyone offered us a price.
That is ~10,000 observations instead of 2.

AND IT IS NOT A PROXY FOR THE LOSS RATE -- IT IS THE LOSS RATE.

Our gate fires at fair >= 0.98, which is exactly |mu - K| >= 2.0537 * sd. The
favoured side loses if and only if the surprise crosses the strike, so

    P(flip | gate at 0.98)  =  P(surprise < -2.0537)

A market deeper than the boundary is safer than this, so the empirical tail
probability is an UPPER BOUND on the gate's flip rate, and stating it as
anything else would be flattery. The model assumes surprise ~ N(0,1) and
therefore claims 2.00%. The live bot has lost 5.71%. This file measures the
real number, and -- the point of the exercise -- measures whether it depends
on conditions we can see BEFORE we buy.

WHAT COULD MAKE THIS AN ARTEFACT, checked in main():
  * If `settle` from the exchange is not the mean of the 60 tape prints, mu is
    being compared with the wrong thing. Reconciled directly at r = 0, where
    mu IS that mean, and reported before anything else.
  * If sigma were measured on the same seconds it is being tested against,
    the tail would be mechanically flat. It is not: sigma_300 ends at the
    evaluation second and every print in the surprise is later.
  * If the cross-market index were a relabelled copy of the traded coin's own
    volatility, this would be the refuted study again. The index EXCLUDES the
    traded coin by construction (pincross.Cross, self-tested), and the own-coin
    version is reported beside it for contrast.
"""
import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor                                # noqa: E402
from statistics import NormalDist                            # noqa: E402
import pincross                                              # noqa: E402
from pincross import Cross, cp_interval, load_index_window    # noqa: E402

ND = NormalDist()
FULLTAPE = r"C:\kals\fulltape\markets.json"
SERIES_TO_INDEX = pincross.SERIES_TO_INDEX

GATE_Z = ND.inv_cdf(0.98)      # 2.0537 -- what fair >= 0.98 means in sd
SIG_WIN = 300                  # the sigma horizon the live bot actually uses


def sigma_at(arr, base, sec, win=SIG_WIN):
    """RMS 1-second CHANGE over the win seconds ending at sec.

    Absolute changes, not log returns: this must match what pinrun feeds into
    fair(), which is engine-native price units. A log-return sigma here would
    be a different number wearing the same name.
    """
    i = sec - base
    if i < win + 2 or i >= len(arr):
        return None
    tot = k = 0
    prev = None
    for j in range(i - win, i + 1):
        v = arr[j]
        if v == v:
            if prev is not None:
                d = v - prev
                tot += d * d
                k += 1
            prev = v
        else:
            prev = None
    if k < win // 4:
        return None
    return math.sqrt(tot / k)


def sigma_live_at(arr, base, sec, win=SIG_WIN):
    """EXACTLY what pinrun.IndexWS.sigma() computes, so the two can be
    compared on the same seconds.

    pinrun:  sqrt(sum((d - mean)^2) / (n - 1))     <- sd ABOUT THE MEAN
    tape:    sqrt(sum(d^2) / n)                    <- RMS, no mean removed

    RMS^2 = variance + mean^2, so the live number is ALWAYS the smaller of the
    two, and the gap is exactly the drift. A smaller sigma makes sd smaller,
    which makes `fair` more confident, which makes the 0.98 gate LOOSER -- and
    it loosens most when the index is trending, which is when we lose. That is
    a bug-shaped story with the right sign, so it gets measured, not asserted.
    """
    i = sec - base
    if i < win + 2 or i >= len(arr):
        return None
    diffs = []
    prev = None
    for j in range(i - win, i + 1):
        v = arr[j]
        if v == v:
            if prev is not None:
                diffs.append(v - prev)
            prev = v
        else:
            prev = None
    if len(diffs) < 20:
        return None
    m = sum(diffs) / len(diffs)
    return math.sqrt(sum((x - m) ** 2 for x in diffs) / (len(diffs) - 1))


def window_state(arr, base, close_s, sec):
    """(locked_sum, r, coverage, spot) for the settlement window at `sec`.

    Settlement is the mean of the 60 prints at seconds [close-60, close-1].
    Those at or before `sec` are already on disk; the rest are unpublished.
    """
    lo = close_s - 60
    locked = 0.0
    nl = 0
    r = 0
    for s in range(lo, close_s):
        i = s - base
        if s <= sec:
            if 0 <= i < len(arr):
                v = arr[i]
                if v == v:
                    locked += v
                    nl += 1
        else:
            r += 1
    have = close_s - lo - r          # seconds that should be locked
    if have <= 0:
        cov = 1.0
    else:
        cov = nl / have
    spot = None
    for s in range(sec, sec - 30, -1):
        i = s - base
        if 0 <= i < len(arr):
            v = arr[i]
            if v == v:
                spot = v
                break
    return locked, r, cov, spot


# ------------------------------------------------------------- statistics
def perm_generic(closes, key, sumkey, nkey="n", hi_frac=0.25,
                 draws=4000, seed=11):
    """Weighted mean of `sumkey`/`nkey` in the top quartile of CLOSES vs rest.

    Permuting the index across whole closes preserves every bit of the
    rho ~ 0.8 clustering between the twelve series that settle on the same
    second. A market-level or row-level shuffle would not, and this project
    has already been burned by exactly that.
    """
    import random
    vals = [c[key] for c in closes]
    wt = [c[nkey] for c in closes]
    sm = [c[sumkey] for c in closes]
    n = len(closes)
    if n < 8:
        return None
    cut = max(1, int(round(hi_frac * n)))

    def stat(order):
        rank = sorted(range(n), key=lambda i: -vals[order[i]])
        hi, lo = rank[:cut], rank[cut:]
        sh, nh = sum(sm[i] for i in hi), sum(wt[i] for i in hi)
        sl, nl = sum(sm[i] for i in lo), sum(wt[i] for i in lo)
        if not nh or not nl:
            return None
        return sh / nh - sl / nl

    obs = stat(list(range(n)))
    if obs is None:
        return None
    rng = random.Random(seed)
    order = list(range(n))
    ge = 0
    for _ in range(draws):
        rng.shuffle(order)
        s = stat(order)
        if s is not None and s >= obs:
            ge += 1
    return obs, (ge + 1) / (draws + 1)


# ------------------------------------------------------------- self-test
def selftest():
    print("SELF-TEST -- pintail")
    import array
    import random
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    ck(abs(GATE_Z - 2.0537) < 0.001,
       f"fair >= 0.98 is exactly |mu-K| >= {GATE_Z:.4f} sd, so the flip "
       f"probability the gate implies is the tail beyond it")
    ck(abs(2.0 * (1.0 - ND.cdf(GATE_Z)) - 0.04) < 1e-9,
       "and a two-sided Gaussian puts 4.00% beyond it, 2.00% on the losing "
       "side -- the model's own claim, which live experience contradicts")

    # window_state: build a tape where the answer is known by hand
    base = 1000
    arr = array.array("d", [float("nan")] * 400)
    for i in range(400):
        arr[i] = 100.0 + i * 0.5
    close_s = 1300
    # at sec = close-60-1 nothing in the window is locked
    lk, r, cov, spot = window_state(arr, base, close_s, close_s - 61)
    ck(r == 60 and lk == 0.0,
       "one second before the window opens, all 60 prints are unpublished")
    lk, r, cov, spot = window_state(arr, base, close_s, close_s - 1)
    ck(r == 0 and abs(lk / 60.0 - sum(
        arr[s - base] for s in range(close_s - 60, close_s)) / 60.0) < 1e-9,
       "at the last second r = 0 and the locked mean IS the settlement mean")
    lk, r, cov, spot = window_state(arr, base, close_s, close_s - 15)
    ck(r == 14 and cov == 1.0,
       f"with 15s to go, 14 prints remain unpublished (got r={r})")

    # sigma_at on a known-variance series
    rng = random.Random(3)
    a2 = array.array("d", [0.0] * 2000)
    p = 100.0
    for i in range(2000):
        p += rng.gauss(0, 0.25)
        a2[i] = p
    s = sigma_at(a2, 0, 1500)
    ck(0.2 < s < 0.31, f"sigma recovers a planted 0.25 per second ({s:.3f})")

    # THE HEADLINE ESTIMATOR. Plant a fat tail that depends on X and demand
    # the permutation test finds it.
    worlds = []
    rng2 = random.Random(8)
    for _ in range(200):
        x = rng2.random() * 2.0
        nm = rng2.randint(4, 9)
        # tail is 4x fatter when x is high
        scale = 1.9 if x > 1.5 else 1.0
        hits = sum(1 for _ in range(nm)
                   if abs(rng2.gauss(0, scale)) > GATE_Z)
        worlds.append({"x": x, "n": nm, "tail": hits})
    got = perm_generic(worlds, "x", "tail", draws=1500)
    ck(got is not None and got[1] < 0.01,
       f"a planted state-dependent fat tail IS found "
       f"(lift {100*got[0]:+.2f}pp, p={got[1]:.4f})")

    # AND MUST BE CALIBRATED. One null world is a coin flip -- pincross's
    # first version of this check failed on a 1-in-30 seed and the honest fix
    # was to test the property, not to hunt for a kinder seed.
    hits = 0
    nworlds = 40
    for w in range(nworlds):
        rw = random.Random(500 + w)
        nul = []
        for _ in range(200):
            nm = rw.randint(4, 9)
            nul.append({"x": rw.random() * 2.0, "n": nm,
                        "tail": sum(1 for _ in range(nm)
                                    if abs(rw.gauss(0, 1)) > GATE_Z)})
        g = perm_generic(nul, "x", "tail", draws=400, seed=w)
        if g is not None and g[1] < 0.05:
            hits += 1
    ck(hits <= 6,
       f"across {nworlds} worlds with a CONSTANT tail, only {hits} came out "
       f"significant at 5% (expect ~2, allow 6)")

    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


# ------------------------------------------------------------- real data
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--tau", type=int, default=15)
    ap.add_argument("--draws", type=int, default=4000)
    ap.add_argument("--hours", type=int, default=0,
                    help="0 = every hour of tape we hold")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    mk = []
    for v in json.load(open(FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in SERIES_TO_INDEX and r.get("settle") is not None:
                mk.append(r)
    mk.sort(key=lambda r: r["close"])
    print(f"\n  {len(mk):,} settled markets with a settlement LEVEL, "
          f"{time.strftime('%m-%d %H:%MZ', time.gmtime(mk[0]['close']))} -> "
          f"{time.strftime('%m-%d %H:%MZ', time.gmtime(mk[-1]['close']))}")

    lo_sec = int(mk[0]["close"]) - 400
    hi_sec = int(mk[-1]["close"])
    if a.hours:
        lo_sec = max(lo_sec, hi_sec - a.hours * 3600)
    print(f"  loading index tape ...")
    t0 = time.time()
    idx, nf, kept, dropped = load_index_window(lo_sec, hi_sec)
    print(f"  {len(idx)} feeds, {nf} files, {kept:,} prints ({time.time()-t0:.0f}s)")
    if len(idx) < 5:
        print("  loaded nothing usable")
        return

    # ---------- RECONCILE BEFORE BELIEVING ANYTHING -----------------------
    # At r = 0 our mu IS the mean of the 60 tape prints. If that does not
    # equal the exchange's `settle`, every surprise below is measured against
    # the wrong quantity and nothing else in this file means anything.
    print("\n  RECONCILIATION: our locked mean at r=0 vs the exchange's "
          "settle")
    errs = []
    for r in mk:
        iid = SERIES_TO_INDEX[r["series"]]
        if iid not in idx:
            continue
        base, arr = idx[iid]
        cs = int(r["close"])
        lk, rr, cov, spot = window_state(arr, base, cs, cs - 1)
        if rr != 0 or cov < 1.0:
            continue
        ours = lk / 60.0
        st = float(r["settle"])
        if st:
            errs.append(abs(ours - st) / st)
        if len(errs) >= 4000:
            break
    if errs:
        errs.sort()
        med = errs[len(errs) // 2]
        p95 = errs[int(0.95 * len(errs))]
        print(f"    {len(errs):,} fully-covered markets: median relative "
              f"error {med:.2e}, p95 {p95:.2e}, worst {errs[-1]:.2e}")
        if med > 1e-4:
            print("    *** THE SETTLEMENT MODEL DOES NOT RECONCILE. "
                  "Everything below is void. ***")
            return
        print("    -> the settlement model reconciles; mu is comparable to "
              "settle")
    else:
        print("    no fully-covered market found -- cannot reconcile, "
              "stopping")
        return

    # ---------- the surprise, one per market ------------------------------
    print(f"\n  building the cross-market roughness index ...")
    t0 = time.time()
    cx = Cross(idx)
    print(f"  done ({time.time()-t0:.0f}s)")

    print(f"  scoring every market at tau = {a.tau}s ...")
    obs = []
    skip = defaultdict(int)
    for r in mk:
        iid = SERIES_TO_INDEX[r["series"]]
        if iid not in idx:
            skip["no_feed"] += 1
            continue
        base, arr = idx[iid]
        cs = int(r["close"])
        sec = cs - a.tau
        lk, rr, cov, spot = window_state(arr, base, cs, sec)
        if spot is None or rr < 1:
            skip["no_spot"] += 1
            continue
        if cov < 0.95:
            skip["thin_lock"] += 1
            continue
        sg = sigma_at(arr, base, sec)
        if sg is None or sg <= 0:
            skip["no_sigma"] += 1
            continue
        sgl = sigma_live_at(arr, base, sec)
        mu = (lk + rr * spot) / 60.0
        vf = math.sqrt(var_factor(int(rr), [1.0]))
        sd = sg * vf
        if sd <= 0 or not sgl or sgl <= 0:
            skip["no_sd"] += 1
            continue
        z = (float(r["settle"]) - mu) / sd
        zl = (float(r["settle"]) - mu) / (sgl * vf)
        c = cx.cross(iid, sec)
        own = cx.zof(iid, sec)
        if c is None or own is None:
            skip["no_index"] += 1
            continue
        obs.append({"close": cs, "sr": r["series"], "z": z, "zl": zl,
                    "sig_ratio": sgl / sg,
                    "X": c[0], "N": c[1], "own": own})
    print(f"  {len(obs):,} markets scored; skipped {dict(skip)}")
    if len(obs) < 500:
        print("  loaded nothing -- too few scored markets")
        return

    _sigma_compare(obs)
    _report(obs, a.tau, a.draws)
    # Two anchors, because the measured tail is an upper bound and the live
    # rate is only 57 closes old. If a gate is worth deploying it must look
    # worth deploying under BOTH.
    for anchor in (0.0258, 0.0571):
        gates(obs, anchor, 0.96)


def _sigma_compare(obs):
    """THE LIVE ESTIMATOR vs THE TAPE ESTIMATOR, on the same seconds.

    If these disagree, the backtest has never been testing the bot we run, and
    every threshold calibrated on the tape is calibrated for a different gate.
    """
    rr = sorted(o["sig_ratio"] for o in obs)
    n = len(rr)
    med = rr[n // 2]
    p05, p95 = rr[int(0.05 * n)], rr[int(0.95 * n)]
    tape = sum(1 for o in obs if o["z"] < -GATE_Z) / n
    live = sum(1 for o in obs if o["zl"] < -GATE_Z) / n
    lot, hit = cp_interval(sum(1 for o in obs if o["z"] < -GATE_Z), n)
    lol, hil = cp_interval(sum(1 for o in obs if o["zl"] < -GATE_Z), n)
    print(f"\n  {'='*72}")
    print(f"  THE LIVE SIGMA vs THE BACKTEST SIGMA -- same seconds, "
          f"{n:,} markets")
    print(f"  {'='*72}")
    print(f"    live/tape sigma ratio: median {med:.4f}, "
          f"5th {p05:.4f}, 95th {p95:.4f}")
    print(f"    loss-tail using the TAPE sigma (RMS)    "
          f"{100*tape:.2f}%  [{100*lot:.2f}, {100*hit:.2f}]")
    print(f"    loss-tail using the LIVE sigma (sd)     "
          f"{100*live:.2f}%  [{100*lol:.2f}, {100*hil:.2f}]")
    if tape > 0:
        print(f"    the live estimator's gate is {live/tape:.2f}x as "
              f"dangerous as the one the backtest scores")
    worse = sum(1 for o in obs if o["sig_ratio"] < 1.0)
    print(f"    live sigma is the SMALLER number in {100.0*worse/n:.1f}% of "
          f"markets")
    print(f"    -- I predicted 100% here, and I was WRONG: removing the mean "
          f"shrinks the live\n       number but dividing by (n-1) instead of "
          f"n inflates it by sqrt(300/299), and\n       at this drift the two "
          f"effects very nearly cancel. THE SIGMA HYPOTHESIS IS DEAD.")


def _tail_table(obs, key, edges, label):
    print(f"\n  {label}")
    print(f"  {'band':>15}{'markets':>9}{'closes':>8}{'mean|z|':>9}"
          f"{'P(z<-2.05)':>12}{'95% CI':>20}{'vs model':>10}")
    for i in range(len(edges) - 1):
        a_, b_ = edges[i], edges[i + 1]
        sel = [o for o in obs if a_ <= o[key] < b_]
        if len(sel) < 20:
            continue
        k = sum(1 for o in sel if o["z"] < -GATE_Z)
        cl = len(set(o["close"] for o in sel))
        mz = sum(abs(o["z"]) for o in sel) / len(sel)
        lo, hi = cp_interval(k, len(sel))
        rt = k / len(sel)
        print(f"  {a_:5.2f}-{b_:<9.2f}{len(sel):>9}{cl:>8}{mz:>9.3f}"
              f"{100*rt:>11.2f}%"
              f"{'[' + f'{100*lo:.2f}, {100*hi:.2f}' + ']':>20}"
              f"{rt/0.02:>9.1f}x")


def _report(obs, tau, draws):
    n = len(obs)
    ncl = len(set(o["close"] for o in obs))
    tail = sum(1 for o in obs if o["z"] < -GATE_Z)
    both = sum(1 for o in obs if abs(o["z"]) > GATE_Z)
    lo, hi = cp_interval(tail, n)
    mz = sum(abs(o["z"]) for o in obs) / n

    print(f"\n  {'='*72}")
    print(f"  THE HEADLINE, at tau = {tau}s over {n:,} markets / {ncl:,} "
          f"closes")
    print(f"  {'='*72}")
    print(f"    mean |surprise|                          {mz:.3f} sd "
          f"(a correct model gives 0.798)")
    print(f"    P(surprise beyond the gate, either way)  "
          f"{100.0*both/n:.2f}%   model says 4.00%")
    print(f"    P(surprise past it the LOSING way)       "
          f"{100.0*tail/n:.2f}%   model says 2.00%")
    print(f"    exact 95% CI on that                     "
          f"[{100*lo:.2f}%, {100*hi:.2f}%]")
    print(f"    ratio to the model's own claim           "
          f"{(tail/n)/0.02:.2f}x")
    print(f"\n    THIS IS AN UPPER BOUND on the gate's flip rate: it counts "
          f"every market\n    as if it sat exactly on the 0.98 boundary, and "
          f"most sit deeper.")

    _tail_table(obs, "X", [0.0, 0.7, 0.9, 1.1, 1.4, 2.0, 99.0],
                "BY CROSS-MARKET ROUGHNESS X -- the traded coin EXCLUDED")
    _tail_table(obs, "own", [0.0, 0.7, 0.9, 1.1, 1.4, 2.0, 99.0],
                "BY THE TRADED COIN'S OWN fast/slow ROUGHNESS (a regime "
                "ratio, NOT the refuted sigma level)")
    _tail_table(obs, "N", [0, 1, 2, 3, 5, 99],
                "BY HOW MANY OTHER COINS ARE MOVING (z > 2)")

    byclose = defaultdict(lambda: {"n": 0, "tail": 0, "az": 0.0, "X": 0.0,
                                   "N": 0.0, "own": 0.0})
    for o in obs:
        c = byclose[o["close"]]
        c["n"] += 1
        c["tail"] += 1 if o["z"] < -GATE_Z else 0
        c["az"] += abs(o["z"])
        c["X"] += o["X"]
        c["N"] += o["N"]
        c["own"] += o["own"]
    closes = []
    for cs, c in byclose.items():
        closes.append({"close": cs, "n": c["n"], "tail": c["tail"],
                       "az": c["az"], "X": c["X"] / c["n"],
                       "N": c["N"] / c["n"], "own": c["own"] / c["n"]})

    print(f"\n  PERMUTATION TESTS -- shuffled over {len(closes):,} CLOSES, "
          f"{draws} draws")
    print(f"  {'statistic':<40}{'top-quartile lift':>19}{'p':>9}")
    for key, lbl in (("X", "cross-market roughness X"),
                     ("own", "own fast/slow roughness"),
                     ("N", "how many other coins are moving")):
        g = perm_generic(closes, key, "tail", draws=draws)
        if g:
            print(f"  loss-tail on {lbl:<27}{100*g[0]:>18.2f}pp{g[1]:>9.4f}")
        g = perm_generic(closes, key, "az", draws=draws)
        if g:
            print(f"  mean|z|  on {lbl:<28}{g[0]:>18.3f}sd{g[1]:>9.4f}")

    import random
    rng = random.Random(4242)
    sh = [dict(c) for c in closes]
    vals = [c["X"] for c in closes]
    rng.shuffle(vals)
    for c, v in zip(sh, vals):
        c["X"] = v
    g = perm_generic(sh, "X", "tail", draws=draws)
    print(f"\n  CONTROL (X shuffled across closes, must show nothing): "
          f"lift {100*g[0]:+.2f}pp, p={g[1]:.4f}")

    print(f"\n  MULTIPLE LOOKS: {6} permutation tests are printed above. At "
          f"6 looks the\n  5% threshold is 0.0083, not 0.05. Read every p "
          f"against that number.")


# ------------------------------------------------------------- the decision
def ev_per_trade(f, p, size=20.0):
    """Dollars per contract at flip rate f and price p, after the taker fee."""
    fee = math.ceil(0.07 * size * p * (1 - p) * 10000 - 1e-9) / 10000 / size
    return (1.0 - f) * (1.0 - p) - f * p - fee


GATES = [
    ("N >= 1", lambda o: o["N"] >= 1),
    ("N >= 2", lambda o: o["N"] >= 2),
    ("N >= 3", lambda o: o["N"] >= 3),
    ("X >= 1.4", lambda o: o["X"] >= 1.4),
    ("own >= 1.4", lambda o: o["own"] >= 1.4),
    ("own >= 1.1", lambda o: o["own"] >= 1.1),
    ("N >= 2 or own >= 1.4", lambda o: o["N"] >= 2 or o["own"] >= 1.4),
    ("N >= 1 or own >= 1.4", lambda o: o["N"] >= 1 or o["own"] >= 1.4),
    ("N >= 3 or own >= 2.0", lambda o: o["N"] >= 3 or o["own"] >= 2.0),
]


def _gate_row(obs, name, fn, anchor, price):
    """What refusing `fn` would cost and save, on this slice of markets."""
    ref = [o for o in obs if fn(o)]
    kep = [o for o in obs if not fn(o)]
    if not kep or not ref:
        return None
    base_rate = sum(1 for o in obs if o["z"] < -GATE_Z) / len(obs)
    if base_rate <= 0:
        return None
    scale = anchor / base_rate     # anchor the measured tail to a believed
    fk = scale * sum(1 for o in kep if o["z"] < -GATE_Z) / len(kep)
    fr = scale * sum(1 for o in ref if o["z"] < -GATE_Z) / len(ref)
    vol = len(kep) / len(obs)
    ev0 = ev_per_trade(anchor, price)
    ev1 = ev_per_trade(fk, price)
    tot0, tot1 = ev0, vol * ev1
    return {"name": name, "kept": len(kep), "ref": len(ref), "vol": vol,
            "fk": fk, "fr": fr, "ev0": ev0, "ev1": ev1,
            "gain": (tot1 / tot0 - 1.0) if tot0 else float("nan")}


def gates(obs, anchor, price, split=0.70):
    cl = sorted(set(o["close"] for o in obs))
    cut = cl[int(split * len(cl))]
    fit = [o for o in obs if o["close"] < cut]
    hold = [o for o in obs if o["close"] >= cut]
    print(f"\n  {'='*78}")
    print(f"  WHAT WOULD A GATE COST? anchored so the ungated loss rate is "
          f"{100*anchor:.2f}%,")
    print(f"  every trade priced at {100*price:.0f}c.")
    print(f"  FIT on {len(fit):,} markets to "
          f"{time.strftime('%m-%d %H:%MZ', time.gmtime(cut))}, "
          f"HOLDOUT the {len(hold):,} after it.")
    print(f"  A threshold chosen on the fit half and re-measured on the "
          f"holdout is the only\n  version of this table that is not curve "
          f"fitting.")
    print(f"  {'='*78}")
    print(f"  {'refuse when':<24}{'trades kept':>12}{'loss kept':>11}"
          f"{'loss refused':>14}{'profit':>9}  {'HOLDOUT profit':>15}")
    for name, fn in GATES:
        a = _gate_row(fit, name, fn, anchor, price)
        b = _gate_row(hold, name, fn, anchor, price)
        if a is None:
            continue
        hb = f"{100*b['gain']:+.1f}%" if b else "  --"
        print(f"  {name:<24}{100*a['vol']:>11.1f}%{100*a['fk']:>10.2f}%"
              f"{100*a['fr']:>13.2f}%{100*a['gain']:>8.1f}%  {hb:>15}")
    print(f"\n  'profit' is the change in TOTAL expected profit: fewer trades "
          f"at a lower loss\n  rate. Negative means the gate throws away more "
          f"good trades than bad ones.")


if __name__ == "__main__":
    main()
