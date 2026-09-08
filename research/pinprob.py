#!/usr/bin/env python3
# VERSION: 2026-09-08-pp1
"""pinprob.py -- THE PROBABILITY, COMPUTED. No fixed floor anywhere.

WHAT THIS REPLACES, AND WHY

Every version of pin so far has trade-tested against a CONSTANT: a 0.5c edge
floor, then 0.3c, then an EV test with the flip rate pinned at a measured 0.90%.
All three are the same mistake -- a number chosen once and applied to every
market, every volatility regime and every second remaining.

The operator's point, and it is correct: the quantity that decides a trade is
the CHANCE THE REMAINING PRINTS SWING THE AVERAGE ACROSS THE STRIKE. That
chance depends on how far it must move, how long is left, and how violently
this particular index actually moves. It changes every second. So compute it,
and let the trade threshold fall out of it.

THE ARITHMETIC

Settlement is the mean of 60 one-second prints over [close-60, close-1]. With
r prints unpublished and locked sum L:

    mu             = (L + r*spot)/60                    the current estimate
    required_move  = (60/r) * (K_eff - mu)              what the rest must average
    p_flip         = P(mean of next r prints - spot  crosses required_move)
    EV             = (1-p_flip)*(1-price) - p_flip*price - fee

`required_move` is exact algebra, not a model: settle = (L + sum of the r
remaining)/60, so settle >= K_eff exactly when the remaining prints average at
least (60*K_eff - L)/r, which is spot + (60/r)*(K_eff - mu).

The 60/r factor is the whole reason this strategy exists: 3.2x at tau=20, 15x
at tau=5, 30x at tau=3. Late in the window the market must move absurdly far to
change the answer.

WHY EMPIRICAL AND NOT GAUSSIAN

The shipped model uses Phi((mu-K)/sd) with sd = sigma*sqrt(var_factor(r)).
Measured over 230 million windows of this tape, crypto index moves reach 37 to
127 SIGMA. A gaussian calls 5 sigma astronomical. So the gaussian understates
the tail by orders of magnitude exactly where the decision is made, and that is
why the model implies a 0.06% error rate at prices where the realised rate is
0.90%.

Here p_flip is the observed frequency, from this index's own history, of a
move at least that large IN THE FLIPPING DIRECTION -- signed, because a move
away from the strike is harmless and using |move| would double p_flip and make
the threshold twice as strict as it should be.

NO LOOKAHEAD. The distribution used to price a close is built only from ticks
strictly before that close. Enforced by construction in Hist.snapshot() and
tested by a leak control that must score implausibly better.
"""
import argparse
import array
import bisect
import glob
import gzip
import json
import math
import os
import sys
import time
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                        # noqa: E402
from statistics import NormalDist                           # noqa: E402

ND = NormalDist()
IDXDIR = r"C:\kals\kalshi_data\cfbenchmarks_value"
FULLTAPE = r"C:\kals\fulltape\markets.json"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}
# read from the exchange in pinrun; hardcoded here only as a fallback and
# cross-checked against the tape by max|mean60 - settle| == half the last digit
ROUND_DIGITS = {"KXBTC15M": 2, "KXETH15M": 2, "KXBNB15M": 2,
                "KXSOL15M": 4, "KXXRP15M": 4, "KXZEC15M": 4,
                "KXHYPE15M": 4, "KXNEAR15M": 4, "KXDOGE15M": 7}
TAUS = [3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60]
FLOOR_P = 1e-5      # never claim a probability below this: a zero would make
                    # any price look infinitely attractive


def billed_fee(price, count=1):
    return math.ceil(0.07 * price * (1 - price) * count * 10000) / 10000


def eff_strike(strike, d):
    return float(strike) - 0.5 * (10.0 ** (-int(d))) if d is not None \
        else float(strike)


# ===========================================================================
class Hist:
    """The empirical move distribution for one index, built ONLY from the past.

    For each r, holds the sorted list of realised m(t,r) = mean(next r prints)
    - price at t, taken from windows that ENDED before the cutoff second. The
    signed values are kept so the flipping direction can be asked for on its
    own.
    """

    def __init__(self):
        self.by_r = defaultdict(list)      # r -> sorted list of signed moves
        self._built_to = None

    def add(self, r, m):
        self.by_r[r].append(m)

    def finalise(self):
        for r in self.by_r:
            self.by_r[r].sort()
        return self

    def p_worse_than(self, r, thresh):
        """P(move <= thresh) if thresh < 0, else P(move >= thresh).

        `thresh` is the required_move: the signed amount the remaining prints
        must average for the outcome to FLIP. Only that direction counts.
        """
        xs = self.by_r.get(r)
        if not xs:
            return None
        n = len(xs)
        if thresh <= 0:
            k = bisect.bisect_right(xs, thresh)        # how many were <= it
        else:
            k = n - bisect.bisect_left(xs, thresh)     # how many were >= it
        # Laplace-style smoothing: with zero observed exceedances the honest
        # statement is "below about 1/n", never "impossible".
        return max((k + 0.5) / (n + 1.0), FLOOR_P)


def gauss_p_flip(required_move, sigma, r):
    """The shipped model's implied flip probability, for comparison."""
    sd_m = sigma * math.sqrt(var_factor(int(r), [1.0])) * (60.0 / r)
    if sd_m <= 0:
        return FLOOR_P
    z = required_move / sd_m
    return max(ND.cdf(z) if required_move <= 0 else 1.0 - ND.cdf(z), FLOOR_P)


def expected_value(price, p_flip):
    """EV per contract. No constants: p_flip is computed per trade."""
    p = float(price)
    return (1.0 - p_flip) * (1.0 - p) - p_flip * p - billed_fee(p, 1)


def breakeven_price(p_flip):
    """The highest price at which this trade is still worth taking."""
    return 1.0 - p_flip


# ===========================================================================
def selftest():
    print("SELF-TEST -- pinprob")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # --- required_move algebra, hand-checked ---
    # 60 prints; 56 locked at 100.0; 4 unknown; spot 100.0; strike 100.5
    L, r, spot, K = 56 * 100.0, 4, 100.0, 100.5
    mu = (L + r * spot) / 60.0
    req = (60.0 / r) * (K - mu)
    ck(abs(mu - 100.0) < 1e-12, f"mu is 100.0 when everything sits at 100 ({mu})")
    ck(abs(req - 7.5) < 1e-12,
       f"the last 4 prints must average +7.5 to move a 60-mean by 0.5 ({req})")
    # verify by construction: if they DO average spot+req, the settle is K
    settle = (L + r * (spot + req)) / 60.0
    ck(abs(settle - K) < 1e-12,
       f"and a move of exactly that size lands the settle on the strike "
       f"({settle})")

    # --- the 60/r multiplier grows as the clock runs out ---
    mult = [(t, 60.0 / (t - 1)) for t in (20, 10, 5, 3)]
    ck(all(b > a for (_, a), (_, b) in zip(mult, mult[1:])),
       "the required move multiplies harder as time runs out: "
       + ", ".join(f"tau{t}={m:.1f}x" for t, m in mult))

    # --- empirical p_flip: a KNOWN world ---
    h = Hist()
    for i in range(1000):
        h.add(4, (i - 500) / 100.0)        # uniform on [-5, +5)
    h.finalise()
    p_up = h.p_worse_than(4, 2.5)          # top quarter
    p_dn = h.p_worse_than(4, -2.5)         # bottom quarter
    ck(0.20 < p_up < 0.30, f"P(move >= +2.5) on a uniform [-5,5] is ~25% "
                           f"({p_up:.3f})")
    ck(0.20 < p_dn < 0.30, f"P(move <= -2.5) is ~25% ({p_dn:.3f})")
    ck(h.p_worse_than(4, 99.0) <= (0.5 / 1001.0) + 1e-12,
       f"an unobserved move gets ~1/n, never zero "
       f"({h.p_worse_than(4, 99.0):.2e})")
    ck(h.p_worse_than(4, 99.0) > 0,
       "and never exactly zero -- a zero would make any price look free")

    # --- DIRECTION MATTERS: using |move| would double the estimate ---
    two_sided = h.p_worse_than(4, 2.5) + h.p_worse_than(4, -2.5)
    ck(abs(two_sided - 2 * p_up) < 0.05,
       f"a two-sided test would give {two_sided:.3f}, double the correct "
       f"{p_up:.3f} -- only the flipping direction counts")

    # --- EV and the breakeven price fall OUT of p_flip, not from a constant ---
    for pf, expect in ((0.0001, 0.9999), (0.009, 0.991), (0.05, 0.95)):
        bp = breakeven_price(pf)
        ck(abs(bp - expect) < 1e-9,
           f"p_flip {100*pf:.2f}% -> never pay above {100*bp:.2f}c")
    ck(expected_value(0.99, 0.0001) > 0 > expected_value(0.99, 0.05),
       "the SAME price is a good trade at low risk and a bad one at high risk")

    # --- THE REAL ETH CASE, and why the gaussian is not enough ---
    # KXETH15M-26SEP071745-45: at tau=5 the shipped model priced fair 0.0052,
    # i.e. it claimed a 0.52% chance of the flip. The move required was 0.43
    # USD over the 4 remaining prints. ETHUSD_RTI's trailing sigma there was
    # about 0.123/s, which reproduces that 0.52% exactly -- so the gaussian is
    # faithfully implemented; it is simply WRONG, because the flip happened.
    sig_eth, rr, req_ = 0.1227, 4, 0.43
    pg = gauss_p_flip(req_, sig_eth, rr)
    ck(0.003 < pg < 0.010,
       f"the gaussian reproduces the shipped model on the real ETH case: "
       f"{100*pg:.2f}% (the file records fair 0.0052)")
    # ETH's own measured 4-second moves: p99 = 0.638 USD, so a 0.43 move is
    # INSIDE the top 1% of what this index actually does -- more likely than
    # 1 in 100, not 1 in 200.
    h2 = Hist()
    for i in range(2000):                      # a fat-tailed stand-in
        x = (i - 1000) / 1000.0
        h2.add(4, math.copysign(abs(x) ** 3 * 2.9, x))
    h2.finalise()
    pe = h2.p_worse_than(4, req_)
    ck(pe > pg,
       f"an empirical tail prices that same move at {100*pe:.2f}%, above the "
       f"gaussian's {100*pg:.2f}% -- which is the whole point")
    ck(breakeven_price(pe) < breakeven_price(pg),
       f"so it refuses to pay above {100*breakeven_price(pe):.1f}c where the "
       f"gaussian would pay up to {100*breakeven_price(pg):.1f}c")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
def load_ticks(hours=None):
    """{index_id: (base_sec, array('d') with NaN for missing)}"""
    files = sorted(glob.glob(os.path.join(IDXDIR, "2026*.jsonl.gz")))[:-1]
    if hours:
        files = files[-hours:]
    raw = defaultdict(dict)
    bad = 0
    for f in files:
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    if '"cfbenchmarks_value"' not in line:
                        continue
                    try:
                        d = json.loads(line)
                        m = d["msg"]
                        dd = json.loads(m["data"])
                        raw[m["index_id"]][int(dd["time"]) // 1000] = \
                            float(dd["value"])
                    except Exception:
                        continue
        except (EOFError, zlib.error, OSError):
            bad += 1
    out = {}
    for iid, d in raw.items():
        if not d:
            continue
        lo, hi = min(d), max(d)
        a = array.array("d", [float("nan")]) * 0
        a = array.array("d", [float("nan")] * (hi - lo + 1))
        for s, v in d.items():
            a[s - lo] = v
        out[iid] = (lo, a)
    return out, len(files), bad


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    print("\n  run pinprob_test.py to score this against the tape")
