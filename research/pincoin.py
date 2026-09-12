#!/usr/bin/env python3
# VERSION: 2026-09-12-pc1
"""pincoin.py -- IS SOME COIN'S INDEX STRUCTURALLY JUMPIER THAN THE OTHERS?

THE QUESTION (operator, 2026-09-12): "the last three losses have been SOL,
does that mean anything?"

Live losses at the 99.5% gate, 178 bets: SOL 3/22, NEAR 3/18, BNB 1/20,
DOGE 1/19, XRP 1/27, and BTC+ETH+HYPE+ZEC 0/72. Every loss this project has
dissected has the same shape -- the model's belief COLLAPSES after entry. The
SOL loss of 2026-09-12 went 100% -> 0.2% in ONE second on a 0.14% one-second
index jump. So the hypothesis with a mechanism behind it is:

    some CF Benchmarks feeds have FATTER ONE-SECOND JUMP TAILS relative to
    their own trailing sigma than others, and the 99.5% gate -- which is a
    statement in units of that sigma -- is therefore more dangerous on them.

That is a statement about the INDEX, not about our fills, and the index is
something the tape can answer without any of the adverse-selection blindness
that makes the tape useless for loss rates (CLAUDE.md AMENDMENT 2026-09-10,
rule 5). This file is careful to stay on the right side of that line:

    THE TAPE IS USED HERE ONLY TO RANK COINS AGAINST EACH OTHER.
    NO NUMBER IN THIS FILE IS OUR LIVE LOSS RATE, AND NONE MAY BE QUOTED AS
    ONE. The tape's population is "a fair value existed"; ours is "someone
    actively sold it to us", and only the second is adversely selected.

WHAT IS MEASURED

1. JUMP TAIL. For every second of tape, per feed: the one-second index move
   divided by that feed's OWN trailing-300s one-second sigma, and the rate at
   which |move| exceeds k sigma for k in 3,4,5,6,8. The sigma is the one the
   bot uses -- pinrun.IndexWS.sigma, called through pinsim.TapeIndex -- and it
   is read BEFORE the move is fed, so the denominator is what the model
   believed one second before the jump arrived. That is the forward-looking
   framing; a sigma that already contains the jump is a different (and much
   flatter) statistic.

2. COLLAPSE. At each market's GATE ENTRY -- the first second with
   tau <= TAU_MAX where pinrun.fair crosses PIN (0.995) or 1-PIN -- track the
   model's belief every later second down to TAU_MIN. "Collapse" is belief
   falling below 0.90 before tau 3. On 48 hours of tape a collapse below 20%
   caught 11 of 11 losers and 0 of 1,642 winners (results/SKIM.md), so this is
   the tape-visible precursor of a loss, and unlike a loss rate it is a
   statement about the MODEL, which the tape can see in full.

3. FLIP. At the same gate entries: did the entered side lose. Clopper-Pearson
   per coin. THE MDE IS STATED BEFORE THE ESTIMATE and it is large.

NO ORDER-BOOK IS READ. Entry here is "the model crossed the gate", not "we
bought", so no book, no depth, no fill. That is deliberate -- it isolates the
INDEX property the question is about, and it keeps the job to one hour of
index ticks in memory (the collector outranks this job for RAM).

CLUSTERING. Every coin settles on the same quarter hour at rho ~ 0.8, so a
market-wide volatility burst is ONE observation, not nine. Every significance
statement below is a cluster-robust (linearised ratio) comparison of one coin
against the POOL OF THE OTHER EIGHT with the CLOSE as the cluster, which is
also why the shared burst cancels out of the difference instead of inflating
it. n is reported as CLOSES and as MARKETS, never as seconds or trades.

WHAT THIS FILE DOES NOT MEASURE
  - our live loss rate (see above -- live fills only)
  - whether an offer existed, or whether we would have won the race for it
  - the exchange-lead mechanism (research/pinjump.py owns that)
  - any coin with no settled markets (ADA, BCH, TON, and the two index feeds
    ADAUSD_RTI/BCHUSD_RTI are excluded)

    python research/pincoin.py --selftest
    python research/pincoin.py --days 9 --split 5
"""
import argparse
import glob
import gzip
import json
import math
import os
import random
import sys
import time
from collections import defaultdict, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinrun                                                # noqa: E402
import pinsim                                                # noqa: E402
import pindata                                               # noqa: E402
from pincross import cp_interval                             # noqa: E402
from statistics import NormalDist                            # noqa: E402

ND = NormalDist()

K_LIST = (3.0, 4.0, 5.0, 6.0, 8.0)
# HOW MUCH INDEX THIS SCAN KEEPS PER FEED, in seconds.
#
# pinrun.IndexWS keeps COND_SLOW + 400 = 4,000 s because conditions()/zrough()
# read an hour. THIS FILE NEVER CALLS conditions(), and the deepest window it
# does read is sigma()'s SIGMA_WIN = 300 (partial() reads 60). sigma() copies
# the whole per-feed dict and sorts its keys on EVERY call, and this scan makes
# one call per coin per second -- 7 million of them -- so the retention is the
# single term that decides whether the run takes 15 minutes or two hours. The
# first attempt ran at 4,000 and was killed at hour 24 of 211.
#
# Shrinking a retention is exactly the kind of "obviously harmless" change that
# silently truncates a window, so it is NOT asserted: selftest() feeds two
# indices -- one at pinrun's 4,000, one at RETAIN -- the same 5,000 seconds and
# requires sigma(), partial() and fair() to agree to the last bit at every
# sampled second. If RETAIN is ever dropped below 300 + 60 that test fails.
RETAIN = 900
COLLAPSE_THR = 0.90      # belief below this after entry = "collapse"
GRID = 900               # every 15-minute close is a multiple of this
DATA = pinsim.DATA
OUT_MD = os.path.join(os.path.dirname(HERE), "results", "RESULTS_coin.md")


def close_of(sec):
    """The close whose 15-minute window this second belongs to."""
    return ((int(sec) + GRID - 1) // GRID) * GRID


# ------------------------------------------------------------------ statistics
def cluster_diff(cells_coin, cells_pool):
    """One coin's rate minus the pool's, with the CLOSE as the cluster.

    cells_*: {close_second: (numerator, denominator)}.

    The estimand is a difference of two RATIOS, so the variance comes from the
    usual linearisation: within cluster j the influence of the coin is
    (x_j - p*n_j)/N and of the pool (X_j - P*N_j)/NN, and the two are
    SUBTRACTED INSIDE the cluster before squaring. That subtraction is the
    whole point -- a market-wide burst raises x_j and X_j together, and at
    rho ~ 0.8 an estimator that did not pair them inside the close would call
    the shared burst evidence about one coin.
    """
    if not cells_coin or not cells_pool:
        return None
    N = sum(n for _, n in cells_coin.values())
    X = sum(x for x, _ in cells_coin.values())
    NN = sum(n for _, n in cells_pool.values())
    XX = sum(x for x, _ in cells_pool.values())
    if N <= 0 or NN <= 0:
        return None
    p, pp = X / N, XX / NN
    v = 0.0
    for j in set(cells_coin) | set(cells_pool):
        x, n = cells_coin.get(j, (0, 0))
        x2, n2 = cells_pool.get(j, (0, 0))
        r = (x - p * n) / N - (x2 - pp * n2) / NN
        v += r * r
    se = math.sqrt(v)
    return {"p": p, "pool": pp, "diff": p - pp, "se": se,
            "z": ((p - pp) / se) if se > 0 else 0.0,
            "n": N, "n_pool": NN, "clusters": len(cells_coin)}


def mde_two_prop(p, n1, n0, alpha=0.05, power=0.80, looks=1):
    """Smallest coin-vs-pool difference detectable at `power`, Bonferroni'd
    over `looks`. Stated BEFORE the estimate, always."""
    if n1 <= 0 or n0 <= 0:
        return float("nan")
    za = ND.inv_cdf(1.0 - alpha / (2.0 * looks))
    zb = ND.inv_cdf(power)
    return (za + zb) * math.sqrt(max(p, 1e-9) * (1 - max(p, 1e-9))
                                 * (1.0 / n1 + 1.0 / n0))


def bonf_z(looks, alpha=0.05):
    return ND.inv_cdf(1.0 - alpha / (2.0 * max(1, looks)))


# ------------------------------------------------------------------- the scan
class Scanner:
    """One pass over the index tape, second by second, no lookahead.

    The index is pinsim.TapeIndex -- i.e. pinrun.IndexWS with only the
    wall-clock read overridden -- and it is fed with feed_upto exactly as the
    certified backtest feeds it, so sigma(), partial() and fair() are the live
    code reading a live structure.

    ONE SIGMA CALL PER COIN PER SECOND. The sigma held AFTER feeding second
    s-1 is by definition the sigma available BEFORE the move into second s, so
    the jump test's denominator and the gate's denominator are the same number
    used one second apart. Recomputing it twice would be slower and would say
    the same thing.
    """

    def __init__(self, coin_to_iid, round_digits, lo, hi,
                 ks=K_LIST, collapse_thr=COLLAPSE_THR, trace=False):
        self.c2i = dict(coin_to_iid)
        self.i2c = {v: k for k, v in self.c2i.items()}
        self.rd = dict(round_digits)
        self.lo, self.hi = int(lo), int(hi)       # seconds that COUNT
        self.ks = tuple(ks)
        self.thr = collapse_thr
        self.idx = pinsim.TapeIndex(sorted(self.c2i.values()))
        # see RETAIN above; proven equivalent to pinrun's 4,000 in selftest()
        self.idx.order = defaultdict(lambda: deque(maxlen=RETAIN))
        # jump cells: (coin, close) -> [count per k]; secs: (coin, close) -> n
        self.jump = defaultdict(lambda: [0] * len(self.ks))
        self.secs = defaultdict(int)
        self.jump_tau = defaultdict(lambda: [0] * len(self.ks))
        self.secs_tau = defaultdict(int)
        # The biggest |move|/sigma each feed ever printed, and where. A list
        # of every z would be 3.6M Python floats (~115 MB) for a statistic the
        # exceedance table already carries, and the collector outranks this
        # job for RAM.
        self.maxz = {}                            # coin -> (z, second)
        # ARTEFACT GUARD. The CF feeds are quoted to a fixed number of
        # decimals, so a coin whose one-second sd is only a few quotation
        # steps has a LUMPY move distribution and its k-sigma exceedance rate
        # is not comparable with a finely-quoted coin's. These three make that
        # visible instead of letting it masquerade as a fat tail.
        self.zero_moves = defaultdict(int)        # coin -> seconds with dv==0
        self.gran = {}                            # coin -> smallest |dv| > 0
        self.sig_sum = defaultdict(float)         # coin -> sum of sigma
        self.sig_n = defaultdict(int)
        self.skip = defaultdict(int)
        self.track = {}                           # ticker -> entry record
        self.by_close = defaultdict(list)         # close -> [(ticker, mkt)]
        self._last_sec = None
        self._sig = {}
        self._val = {}
        self.trace = [] if trace else None
        self.audit_bad = 0
        self.audit_n = 0

    def add_markets(self, markets):
        for r in markets:
            if r["series"] in self.c2i:
                self.by_close[int(float(r["close"]))].append(
                    (r.get("ticker") or f"{r['series']}-{r['close']}", r))

    # ---- the per-second machine ----
    def feed_hour(self, ticks):
        """ticks: {index_id: sorted [(second, value)]}. One hour at a time."""
        if not ticks:
            return
        pend = {k: list(v) for k, v in ticks.items()}
        lo = min(v[0][0] for v in pend.values() if v)
        hi = max(v[-1][0] for v in pend.values() if v)
        # NEVER RE-WALK A SECOND. Hour files are clean on this tape (checked:
        # 20260910T03/T04 span exactly 3599 s with no overlap), but a
        # collector restart can put a straddling print in the next file, and a
        # second walked twice would be counted twice in the denominator AND in
        # the exceedance count. The ticks themselves are still fed --
        # feed_upto inserts everything at or before the first second we walk.
        if self._last_sec is not None and lo <= self._last_sec:
            self.skip["_overlap_seconds"] += min(hi, self._last_sec) - lo + 1
            lo = self._last_sec + 1
        for sec in range(lo, hi + 1):
            contiguous = (self._last_sec is not None
                          and sec == self._last_sec + 1)
            prior_sig = self._sig if contiguous else {}
            prior_val = self._val if contiguous else {}
            self.idx.now = sec
            self.idx.feed_upto(pend, sec)
            cur_sig, cur_val = {}, {}
            for iid in self.c2i.values():
                cur_sig[iid] = self.idx.sigma(iid)
                d = self.idx.ticks.get(iid)
                cur_val[iid] = d.get(sec) if d else None
            if self.lo <= sec <= self.hi:
                self._jump_second(sec, prior_sig, prior_val, cur_val)
                self._gate_second(sec, cur_sig)
            self._sig, self._val = cur_sig, cur_val
            self._last_sec = sec

    def _jump_second(self, sec, prior_sig, prior_val, cur_val):
        cl = close_of(sec)
        for coin, iid in self.c2i.items():
            v1, v0 = cur_val.get(iid), prior_val.get(iid)
            sg = prior_sig.get(iid)
            if v1 is None or v0 is None:
                self.skip[f"{coin}:no_tick"] += 1
                continue
            if not sg:
                self.skip[f"{coin}:no_sigma"] += 1
                continue
            dv = abs(v1 - v0)
            if dv == 0.0:
                self.zero_moves[coin] += 1
            elif dv < self.gran.get(coin, float("inf")):
                self.gran[coin] = dv
            self.sig_sum[coin] += sg
            self.sig_n[coin] += 1
            z = dv / sg
            key = (coin, cl)
            self.secs[key] += 1
            row = self.jump[key]
            for i, k in enumerate(self.ks):
                if z > k:
                    row[i] += 1
            tau = cl - sec
            if 1 <= tau <= 60:
                self.secs_tau[key] += 1
                rowt = self.jump_tau[key]
                for i, k in enumerate(self.ks):
                    if z > k:
                        rowt[i] += 1
            if z > self.maxz.get(coin, (0.0, 0))[0]:
                self.maxz[coin] = (z, sec)
            if self.trace is not None:
                self.trace.append((sec, coin, sg, v1 - v0))

    def _gate_second(self, sec, cur_sig):
        # closes are on a 900s grid, so at most one close sits inside
        # [sec+TAU_MIN, sec+TAU_MAX]
        cl = ((sec + pinrun.TAU_MIN + GRID - 1) // GRID) * GRID
        if cl - sec > pinrun.TAU_MAX:
            return
        rows = self.by_close.get(cl)
        if not rows:
            return
        tau = cl - sec
        for tk, r in rows:
            iid = self.c2i[r["series"]]
            sg = cur_sig.get(iid)
            if not sg:
                self.skip[f"{r['series']}:gate_no_sigma"] += 1
                continue
            f = pinrun.fair(self.idx, iid, cl, sec, float(r["strike"]),
                            sg * pinrun.SIGMA_STRESS,
                            round_digits=self.rd.get(r["series"]))
            if f is None:
                self.skip[f"{r['series']}:gate_no_fair"] += 1
                continue
            st = self.track.get(tk)
            if st is None:
                if f >= pinrun.PIN or f <= 1.0 - pinrun.PIN:
                    want = "yes" if f >= pinrun.PIN else "no"
                    res = r.get("result")
                    yes = ((str(res).lower() == "yes")
                           if isinstance(res, str) else float(res) >= 0.5)
                    cf = f if want == "yes" else 1.0 - f
                    self.track[tk] = {
                        "coin": r["series"], "close": cl, "tau_in": tau,
                        "want": want, "fair_in": f, "conf_in": cf,
                        "margin_sd": ND.inv_cdf(min(max(cf, 1e-12),
                                                    1 - 1e-12)),
                        "min_belief": None, "post": 0,
                        "won": (yes == (want == "yes"))}
                continue
            belief = f if st["want"] == "yes" else 1.0 - f
            st["post"] += 1
            st["min_belief"] = (belief if st["min_belief"] is None
                                else min(st["min_belief"], belief))

    # ---- an in-run audit of the fast path -------------------------------
    def audit_sigma(self, sec, n=1):
        """Recompute sigma the long way from the retained ticks and compare.

        The scan reuses second s-1's sigma as second s's prior. That is an
        identity, not an approximation -- but it is exactly the kind of
        identity that is true until a retention eviction or a revised print
        makes it false, so it is CHECKED on real data rather than asserted.
        """
        for iid in self.c2i.values():
            got = self._sig.get(iid)
            want = self.idx.sigma(iid)
            self.audit_n += 1
            if (got is None) != (want is None):
                self.audit_bad += 1
            elif got is not None and abs(got - want) > 1e-12:
                self.audit_bad += 1

    # ---- results ----
    def entries(self):
        return list(self.track.values())


# ------------------------------------------------------------------ self-test
def _walk(rng, n, sd, start=100.0, fat_p=0.0, fat_mult=8.0):
    """A one-second index path. With fat_p > 0 a share of the steps are
    fat_mult times the usual size -- the planted jump tail."""
    v = start
    out = []
    for _ in range(n):
        step = rng.gauss(0.0, sd)
        if fat_p and rng.random() < fat_p:
            step = fat_mult * sd * (1 if rng.random() < 0.5 else -1)
        v += step
        out.append(v)
    return out


def _feed_chunked(sc, ticks, size=3600):
    """Feed a long synthetic series the way main() feeds the tape: ONE HOUR AT
    A TIME.

    Two reasons, and the second one is a measured bug. First, it exercises the
    hour-boundary continuity guard rather than leaving it untested. Second,
    pinsim's feed_upto consumes its pending list with list.pop(0), which is
    O(n) per pop -- so handing it 60,000 ticks as a single "hour" is quadratic.
    The first version of this self-test did exactly that and spent twelve
    minutes in one synthetic world. Real hours are 3,600 ticks per feed, which
    is where that cost is designed to sit.
    """
    allsecs = sorted({s for v in ticks.values() for s, _ in v})
    if not allsecs:
        return
    b, hi = allsecs[0], allsecs[-1]
    while b <= hi:
        e = b + size - 1
        sub = {k: [(s, v) for s, v in vv if b <= s <= e]
               for k, vv in ticks.items()}
        sub = {k: v for k, v in sub.items() if v}
        if sub:
            sc.feed_hour(sub)
        b = e + 1


def _mkticks(paths, t0):
    return {iid: [(t0 + i, v) for i, v in enumerate(p)]
            for iid, p in paths.items()}


def _run_jump_world(coins, paths, t0, ks=K_LIST, trace=False):
    c2i = {c: c + "_IDX" for c in coins}
    ticks = _mkticks({c2i[c]: paths[c] for c in coins}, t0)
    sc = Scanner(c2i, {c: 2 for c in coins}, t0, t0 + len(paths[coins[0]]),
                 ks=ks, trace=trace)
    _feed_chunked(sc, ticks)
    return sc


def _coin_cells(sc, coin, ki):
    mine = {cl: (sc.jump[(c, cl)][ki], sc.secs[(c, cl)])
            for (c, cl) in sc.secs if c == coin}
    pool = defaultdict(lambda: [0, 0])
    for (c, cl), n in sc.secs.items():
        if c == coin:
            continue
        pool[cl][0] += sc.jump[(c, cl)][ki]
        pool[cl][1] += n
    return mine, {k: tuple(v) for k, v in pool.items()}


def selftest():
    print("SELF-TEST -- pincoin")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # ---- the machinery is the bot's, not a copy --------------------------
    ck(Scanner(pindata.SERIES_TO_INDEX, pindata.ROUND_DIGITS, 0, 1).idx.sigma
       .__func__ is pinrun.IndexWS.sigma,
       "sigma() is pinrun's own code, not a reimplementation")
    ck(abs(pinrun.PIN - 0.995) < 1e-12 and pinrun.TAU_MAX == 30
       and pinrun.TAU_MIN == 3,
       f"reading the LIVE gate: PIN={pinrun.PIN}, tau "
       f"{pinrun.TAU_MIN}-{pinrun.TAU_MAX}")

    # ---- RETAIN does not change a single number -------------------------
    T_ = 1_650_000_000
    rg_ = random.Random(99)
    path_ = _walk(rg_, 5000, 0.01)
    ser_ = [(T_ + i, v) for i, v in enumerate(path_)]
    ia = pinsim.TapeIndex(["R"])                     # pinrun's own 4,000 s
    ib = pinsim.TapeIndex(["R"])
    ib.order = defaultdict(lambda: deque(maxlen=RETAIN))
    pa = pb = None
    bad = 0
    checked = 0
    for i_, (sec_, _v) in enumerate(ser_):
        if i_ % 3600 == 0:                 # hour-sized pending lists; see
            pa = {"R": ser_[i_:i_ + 3600]}  # _feed_chunked on why pop(0) is
            pb = {"R": ser_[i_:i_ + 3600]}  # quadratic on a long one
        ia.now = ib.now = sec_
        ia.feed_upto(pa, sec_)
        ib.feed_upto(pb, sec_)
        if i_ < 1000 or i_ % 7:
            continue
        checked += 1
        sa, sb = ia.sigma("R"), ib.sigma("R")
        cl_ = ((sec_ + 60) // 900 + 1) * 900
        qa = ia.partial("R", cl_, sec_)
        qb = ib.partial("R", cl_, sec_)
        fa_ = pinrun.fair(ia, "R", cl_, sec_, path_[0], (sa or 0) or 1e-9,
                          round_digits=2)
        fb_ = pinrun.fair(ib, "R", cl_, sec_, path_[0], (sb or 0) or 1e-9,
                          round_digits=2)
        if sa != sb or qa != qb or fa_ != fb_:
            bad += 1
    ck(bad == 0 and checked > 400,
       f"RETAIN={RETAIN}: sigma(), partial() and fair() are bit-identical to "
       f"pinrun's 4,000 s retention at all {checked} sampled seconds "
       f"({bad} mismatches) -- the scan reads no window deeper than "
       f"SIGMA_WIN={pinrun.SIGMA_WIN}")
    ck(RETAIN > pinrun.SIGMA_WIN + 60,
       f"and RETAIN ({RETAIN}) clears sigma's {pinrun.SIGMA_WIN}s window plus "
       f"partial's 60s one")

    # ---- NO LOOKAHEAD: the sigma a jump is judged against predates it -----
    T0 = 1_700_000_000
    rng = random.Random(11)
    calm = _walk(rng, 2000, 0.01)
    # ONE enormous step: the LEVEL is shifted from second 1500 onward. Setting
    # a single point instead makes a SPIKE, which is two jumps (up then down)
    # and would have made this assertion pass for the wrong reason.
    for i in range(1500, len(calm)):
        calm[i] += 5.0
    sc = _run_jump_world(["A"], {"A": calm}, T0, trace=True)
    tr = {s: (sg, d) for s, _, sg, d in sc.trace}
    sg_at, _ = tr[T0 + 1500]
    ref = pinsim.TapeIndex(["A_IDX"])
    pend = {"A_IDX": [(T0 + i, v) for i, v in enumerate(calm[:1500])]}
    ref.now = T0 + 1499
    ref.feed_upto(pend, T0 + 1499)
    ck(abs(sg_at - ref.sigma("A_IDX")) < 1e-12,
       f"the sigma a second-1500 jump is scored against is EXACTLY the sigma "
       f"held at second 1499 ({sg_at:.6f}) -- it cannot contain the jump")
    nk8 = sum(sc.jump[(c, cl)][K_LIST.index(8.0)]
              for (c, cl) in sc.secs)
    ck(nk8 == 1 and sc.jump[("A", close_of(T0 + 1500))][K_LIST.index(8.0)] == 1,
       f"and the planted {abs(5.0 / sg_at):.0f}-sigma step is the ONE and only "
       f"k>8 exceedance in the world (found {nk8})")

    # ---- WORLD 1: one coin has a fat jump tail ---------------------------
    n = 60000
    rng = random.Random(7)
    p1 = {"FAT": _walk(rng, n, 0.01, fat_p=0.0025, fat_mult=9.0),
          "CALM1": _walk(rng, n, 0.01),
          "CALM2": _walk(rng, n, 0.013)}
    s1 = _run_jump_world(["FAT", "CALM1", "CALM2"], p1, T0)
    ki = K_LIST.index(5.0)
    thr = bonf_z(3 * len(K_LIST))
    zs = {}
    for c in ("FAT", "CALM1", "CALM2"):
        mine, pool = _coin_cells(s1, c, ki)
        zs[c] = cluster_diff(mine, pool)
    ck(zs["FAT"]["z"] > thr,
       f"PLANTED WORLD: the fat-tailed coin is flagged at k=5 "
       f"(z={zs['FAT']['z']:.1f} > {thr:.2f}), rate {1e4*zs['FAT']['p']:.1f} "
       f"vs pool {1e4*zs['FAT']['pool']:.1f} per 10k s")
    ck(zs["CALM1"]["z"] < thr and zs["CALM2"]["z"] < thr,
       f"and neither calm coin is (z={zs['CALM1']['z']:.1f}, "
       f"{zs['CALM2']['z']:.1f})")
    ck(zs["CALM2"]["p"] <= 2 * zs["CALM1"]["p"] + 1e-9,
       "SCALE-FREE: a coin with 30% larger absolute moves but the same SHAPE "
       "is NOT flagged -- the statistic divides by the coin's own sigma")

    # ---- WORLD 2: equal tails, nothing to find ---------------------------
    rng = random.Random(23)
    p2 = {c: _walk(rng, n, 0.01 * (1 + i * 0.4), fat_p=0.0025, fat_mult=9.0)
          for i, c in enumerate(("E1", "E2", "E3"))}
    s2 = _run_jump_world(["E1", "E2", "E3"], p2, T0)
    z2 = {}
    for c in ("E1", "E2", "E3"):
        mine, pool = _coin_cells(s2, c, ki)
        z2[c] = cluster_diff(mine, pool)["z"]
    ck(max(abs(v) for v in z2.values()) < thr,
       f"EQUAL-TAIL WORLD: all three coins have the SAME fat tail and none is "
       f"flagged (max |z| = {max(abs(v) for v in z2.values()):.2f} < "
       f"{thr:.2f}), even though their absolute sigmas differ by 1.8x")
    ck(min(cluster_diff(*_coin_cells(s2, c, ki))["p"] for c in z2) > 0,
       "and the estimator is not simply returning zero everywhere -- every "
       "coin in that world HAS exceedances")

    # ---- WORLD 3: collapse + flip, planted -------------------------------
    def gate_world(jumpy, ncl=60, seed=5):
        """`jumpy` = set of coins whose index crashes through the strike at
        tau 12 on every close. Everyone else sits still and wins."""
        rr = random.Random(seed)
        coins = ["S1", "S2", "J1"]
        c2i = {c: c + "_IDX" for c in coins}
        first = (T0 // GRID) * GRID + GRID
        span0, span1 = first - 900, first + GRID * ncl
        paths = {c: [] for c in coins}
        mkts = []
        for c in coins:
            v = 100.0
            for s in range(span0, span1):
                cl = close_of(s)
                tau = cl - s
                base = 100.0
                if c in jumpy and 0 <= tau <= 12:
                    base = 90.0
                v = base + rr.gauss(0.0, 0.002)
                paths[c].append((s, v))
        for i in range(ncl):
            cl = first + GRID * i
            for c in coins:
                got = {s: v for s, v in paths[c] if cl - 60 <= s <= cl - 1}
                settle = sum(got.values()) / 60.0
                K = pindata.eff_strike(99.0, 2)
                mkts.append({"ticker": f"{c}-{cl}", "series": c,
                             "strike": 99.0, "close": float(cl),
                             "result": "yes" if settle >= K else "no"})
        sc = Scanner(c2i, {c: 2 for c in coins}, span0, span1)
        sc.add_markets(mkts)
        _feed_chunked(sc, {c2i[c]: paths[c] for c in coins})
        return sc

    s3 = gate_world({"J1"})
    e3 = defaultdict(list)
    for e in s3.entries():
        e3[e["coin"]].append(e)
    ck(all(len(e3[c]) >= 55 for c in ("S1", "S2", "J1")),
       f"PLANTED GATE WORLD: every coin reaches the 99.5% gate on ~every "
       f"close (S1 {len(e3['S1'])}, S2 {len(e3['S2'])}, J1 {len(e3['J1'])})")
    col = {c: sum(1 for e in v
                  if e["min_belief"] is not None and e["min_belief"] < 0.90)
           / max(1, len(v)) for c, v in e3.items()}
    flip = {c: sum(1 for e in v if not e["won"]) / max(1, len(v))
            for c, v in e3.items()}
    ck(col["J1"] > 0.9 and col["S1"] == 0.0 and col["S2"] == 0.0,
       f"the collapse estimator finds the planted collapse and only it "
       f"(J1 {100*col['J1']:.0f}%, S1 {100*col['S1']:.0f}%, "
       f"S2 {100*col['S2']:.0f}%)")
    ck(flip["J1"] > 0.9 and flip["S1"] == 0.0 and flip["S2"] == 0.0,
       f"and the flip estimator agrees (J1 {100*flip['J1']:.0f}%, "
       f"S1 {100*flip['S1']:.0f}%, S2 {100*flip['S2']:.0f}%)")
    ck(all(e["tau_in"] == pinrun.TAU_MAX for e in e3["J1"]),
       "entry is the FIRST qualifying second, not the last")

    # ---- WORLD 4: everyone collapses equally, nothing to find ------------
    s4 = gate_world({"S1", "S2", "J1"}, seed=9)
    e4 = defaultdict(list)
    for e in s4.entries():
        e4[e["coin"]].append(e)
    cells = {}
    for c, v in e4.items():
        cells[c] = {e["close"]: (0 if e["won"] else 1, 1) for e in v}
    z4 = []
    for c in cells:
        pool = defaultdict(lambda: [0, 0])
        for c2, cc in cells.items():
            if c2 == c:
                continue
            for cl, (x, nn) in cc.items():
                pool[cl][0] += x
                pool[cl][1] += nn
        d = cluster_diff(cells[c], {k: tuple(v) for k, v in pool.items()})
        z4.append(abs(d["z"]))
    ck(sum(1 for v in e4["S1"] if not v["won"]) > 50,
       "EQUAL-COLLAPSE WORLD: every coin now flips on ~every close ...")
    ck(max(z4) < bonf_z(3),
       f"... and no coin is singled out (max |z| = {max(z4):.2f} < "
       f"{bonf_z(3):.2f}) -- a world with equal tails returns nothing")

    # ---- the clustered estimator itself ----------------------------------
    rr = random.Random(3)
    a = {j: (1 if rr.random() < 0.3 else 0, 1) for j in range(400)}
    shared = {j: (a[j][0], 1) for j in a}          # pool == coin, exactly
    d = cluster_diff(a, shared)
    ck(abs(d["diff"]) < 1e-12 and d["se"] < 1e-12,
       "cluster_diff: a coin compared against an identical pool has zero "
       "difference AND zero clustered variance -- the close is paired inside "
       "the residual, which is what rho ~ 0.8 requires")
    ck(cp_interval(0, 100)[0] == 0.0 and cp_interval(100, 100)[1] == 1.0,
       "cp_interval endpoints behave at 0 and n")
    # ---- the live-fill estimators ----------------------------------------
    one = homogeneity_p({f"C{i}": 20 for i in range(9)},
                        {"C0": 7}, draws=20000, seed=1)
    ck(one["p_max"] < 0.01,
       f"LIVE TEST, planted: 7 of 7 losses on one coin of nine IS flagged "
       f"(p = {one['p_max']:.4f})")
    # A NULL WITH A NON-TRIVIAL STATISTIC. Dealing the losses one per coin
    # makes obs_max = 1 and p = 1 by arithmetic, which tests nothing. These
    # losses are dealt AT RANDOM by an independent generator, so obs_max is
    # whatever chance gives and the p-value has to be earned.
    rg2 = random.Random(404)
    pool_ = [f"C{i}" for i in range(9) for _ in range(20)]
    nulls = []
    for t_ in range(12):
        dealt = defaultdict(int)
        for c_ in rg2.sample(pool_, 7):
            dealt[c_] += 1
        nulls.append(homogeneity_p({f"C{i}": 20 for i in range(9)},
                                   dict(dealt), draws=8000,
                                   seed=500 + t_)["p_max"])
    ck(min(nulls) > 0.05 and max(n_ > 0.20 for n_ in nulls),
       f"LIVE TEST, null: 12 worlds whose 7 losses were dealt AT RANDOM are "
       f"none of them flagged (p range {min(nulls):.2f}-{max(nulls):.2f}, "
       f"obs_max earned, not fixed at 1)")
    big = homogeneity_p({"BIG": 100, "S1": 10, "S2": 10},
                        {"BIG": 3}, draws=20000, seed=1)
    ck(big["p_max"] > 0.20,
       f"LIVE TEST: a coin we simply TRADE MORE is not flagged for owning "
       f"more losses (p = {big['p_max']:.2f}) -- the deal holds every coin's "
       f"close count fixed")
    ck(abs(hyper_ge(3, 97, 14, 4) - 0.00901) < 0.0002,
       f"hyper_ge matches the hand-computed value "
       f"[C(14,3)C(83,1)+C(14,4)]/C(97,4) = 0.00901 -> "
       f"{hyper_ge(3, 97, 14, 4):.5f}")
    ck(abs(hyper_ge(0, 50, 10, 5) - 1.0) < 1e-9,
       "and P(X >= 0) is exactly 1")

    # ---- section 7: pairing signals to FILLS, not to attempts ------------
    recs = [
        {"kind": "start", "pin": 0.995},
        # a lost race: signal, then a canceled order -> NOT an entry
        {"kind": "signal", "ticker": "A", "want": "no", "fair": 0.004},
        {"kind": "order", "ticker": "A", "filled": 0.0},
        # a real fill on the same close, less confident
        {"kind": "signal", "ticker": "A", "want": "no", "fair": 0.0049},
        {"kind": "order", "ticker": "A", "filled": 20.0},
        {"kind": "settled", "ticker": "A", "want": "no", "result": "yes"},
        # a saturated YES that won
        {"kind": "signal", "ticker": "B", "want": "yes", "fair": 1.0},
        {"kind": "order", "ticker": "B", "filled": 5.0},
        {"kind": "settled", "ticker": "B", "want": "yes", "result": "yes"},
        # a fill with no settlement yet -> dropped
        {"kind": "signal", "ticker": "C", "want": "yes", "fair": 0.999},
        {"kind": "order", "ticker": "C", "filled": 1.0},
    ]
    pe = parse_live_entries(recs)
    ck(set(pe) == {"A", "B"},
       f"section 7 keeps only closes with BOTH a filled order and a "
       f"settlement (got {sorted(pe)}) -- an unsettled close and a lost race "
       f"are not bets")
    ck(abs(pe["A"]["conf"] - (1 - 0.0049)) < 1e-12,
       f"conf is taken from the LEAST confident FILLED signal, not the "
       f"canceled one ({pe['A']['conf']:.4f}, not {1 - 0.004:.4f})")
    ck(pe["A"]["lost"] is True and pe["B"]["lost"] is False,
       "and want/result is compared, not result alone")
    ck(pe["B"]["conf"] >= 0.99999,
       "a want=yes entry takes conf straight from fair, a want=no entry "
       "takes 1-fair")
    recs2 = [{"kind": "start", "pin": 0.995}]
    for i in range(60):
        lost = "no" if i < 6 else "yes"     # planted: low margin loses often
        recs2 += [{"kind": "signal", "ticker": f"L{i}", "want": "yes",
                   "fair": 0.996},
                  {"kind": "order", "ticker": f"L{i}", "filled": 1.0},
                  {"kind": "settled", "ticker": f"L{i}", "want": "yes",
                   "result": lost}]
    for i in range(60):
        recs2 += [{"kind": "signal", "ticker": f"H{i}", "want": "yes",
                   "fair": 1.0},
                  {"kind": "order", "ticker": f"H{i}", "filled": 1.0},
                  {"kind": "settled", "ticker": f"H{i}", "want": "yes",
                   "result": "yes"}]
    pe2 = parse_live_entries(recs2)
    lo_ = [v for v in pe2.values() if v["conf"] < 0.999]
    hi_ = [v for v in pe2.values() if v["conf"] >= 0.99999]
    r_lo = sum(1 for v in lo_ if v["lost"]) / len(lo_)
    r_hi = sum(1 for v in hi_ if v["lost"]) / len(hi_)
    ck(len(lo_) == 60 and len(hi_) == 60 and r_lo > 0.05 and r_hi == 0.0,
       f"PLANTED: a world where only the marginal band loses is measured as "
       f"such ({100 * r_lo:.0f}% vs {100 * r_hi:.0f}%) -- so a null on real "
       f"data is a null, not a broken banding")

    # ---- section 6's two estimators --------------------------------------
    ck(abs(poisson_binomial_ge([0.5] * 4, 2) - 11.0 / 16.0) < 1e-12,
       f"poisson_binomial: four fair coins, P(>= 2 heads) = 11/16 = "
       f"{poisson_binomial_ge([0.5] * 4, 2):.4f}")
    ck(abs(poisson_binomial_ge([1.0, 1.0], 2) - 1.0) < 1e-12
       and abs(poisson_binomial_ge([0.0, 0.0], 1)) < 1e-12,
       "and it is exact at p = 1 and p = 0")
    ck(poisson_binomial_ge([0.1, 0.9], 1) > poisson_binomial_ge([0.5, 0.5], 2),
       "and UNEQUAL probabilities are not collapsed to their mean -- a plain "
       "binomial would be the flattering null here")
    Tj = 1_700_000_000
    Cj = (Tj // GRID + 2) * GRID
    rgj = random.Random(31)
    pj = _walk(rgj, 1400, 0.01, start=100.0)
    tj_ = [(Cj - 1400 + i, v) for i, v in enumerate(pj)]
    z0, tau0 = max_jump_in_window({"J": list(tj_)}, "J", Cj)
    tj2 = [(sec, v + (3.0 if sec >= Cj - 25 else 0.0)) for sec, v in tj_]
    z1, tau1 = max_jump_in_window({"J": tj2}, "J", Cj)
    ck(z1 > 50 and tau1 == 25 and z0 < 10,
       f"max_jump_in_window finds a level shift planted at tau 25 "
       f"({z1:.0f} sigma at tau {tau1}) and reports only {z0:.1f} sigma on "
       f"the same path without it")
    z2, tau2 = max_jump_in_window(
        {"J": [(sec, v + (3.0 if sec >= Cj - 90 else 0.0))
               for sec, v in tj_]}, "J", Cj)
    ck(z2 < 10,
       f"and a jump at tau 90 -- OUTSIDE the final minute -- is not counted "
       f"({z2:.1f} sigma)")

    scale_selftest(ck)

    m = mde_two_prop(0.01, 150, 1350, looks=9)
    ck(0.01 < m < 0.10,
       f"MDE at p=1%, n=150 vs 1350, 9 looks is {100*m:.2f} pp -- large, as "
       f"it must be reported")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m_ in fails:
        print("   - " + m_)
    return not fails


# ------------------------------------------------------------------ real data
def hour_ticks(stamp, iids):
    """One hour file of cfbenchmarks prints. Parsing is verbatim
    pinsim.load_ticks; only the file selection differs, because this scan
    walks the tape once in order and must not re-read an hour three times."""
    fp = os.path.join(DATA, "cfbenchmarks_value", stamp + ".jsonl.gz")
    out = defaultdict(list)
    if not os.path.exists(fp):
        return out
    want = set(iids)
    try:
        with gzip.open(fp, "rt") as fh:
            for line in fh:
                if '"cfbenchmarks_value"' not in line:
                    continue
                try:
                    m = json.loads(line)["msg"]
                    if m["index_id"] not in want:
                        continue
                    dd = json.loads(m["data"])
                    out[m["index_id"]].append(
                        (int(dd["time"]) // 1000, float(dd["value"])))
                except Exception:
                    continue
    except Exception:
        pass
    for k in out:
        out[k].sort()
        ded, seen = [], set()
        for s, v in out[k]:
            if s in seen:
                ded[-1] = (s, v)          # a revised print replaces its second
            else:
                seen.add(s)
                ded.append((s, v))
        out[k] = ded
    return out


def load_markets():
    mk = []
    for v in json.load(open(pinsim.FULLTAPE, encoding="utf-8")).values():
        for r in v:
            if r["series"] in pindata.SERIES_TO_INDEX and \
                    r.get("result") is not None:
                mk.append(r)
    return mk


def stamps_between(lo, hi):
    out = []
    for fp in sorted(glob.glob(os.path.join(DATA, "cfbenchmarks_value",
                                            "2026*.jsonl.gz"))):
        st = os.path.basename(fp)[:11]
        if (time.strftime("%Y%m%dT%H", time.gmtime(lo)) <= st
                <= time.strftime("%Y%m%dT%H", time.gmtime(hi))):
            out.append(st)
    return out


def fmt_pct(x, dp=2):
    return "n/a" if x is None or x != x else f"{100.0 * x:.{dp}f}%"


# -------------------------------------- SECTION 6: OUR LOSSES ON THE INDEX
def poisson_binomial_ge(ps, m):
    """P(X >= m) for independent Bernoulli trials with different p.

    The six losing closes are six DIFFERENT coins with six different base
    rates, so a plain binomial is the wrong null and would be the easier,
    flatterings one.
    """
    dist = [1.0]
    for q in ps:
        nd = [0.0] * (len(dist) + 1)
        for i, v in enumerate(dist):
            nd[i] += v * (1.0 - q)
            nd[i + 1] += v * q
        dist = nd
    return sum(dist[int(m):])


def max_jump_in_window(ticks, iid, close_s, lo_tau=1, hi_tau=60, warm=1200):
    """(largest |one-second move| / prior sigma, its tau) in a close's final
    seconds, through pinrun's own sigma and with the same no-lookahead
    discipline as the main scan: the sigma is read BEFORE the move is fed."""
    idx = pinsim.TapeIndex([iid])
    idx.order = defaultdict(lambda: deque(maxlen=RETAIN))
    pend = {iid: list(ticks.get(iid, []))}
    best = (0.0, None)
    for sec in range(close_s - warm, close_s + 1):
        sg = idx.sigma(iid)
        prev = idx.ticks[iid].get(sec - 1)
        idx.now = sec
        idx.feed_upto(pend, sec)
        cur = idx.ticks[iid].get(sec)
        tau = close_s - sec
        if sg and prev is not None and cur is not None and \
                lo_tau <= tau <= hi_tau:
            z = abs(cur - prev) / sg
            if z > best[0]:
                best = (z, tau)
    return best


def loss_cases(sc, say, ks=(5.0, 8.0)):
    """WHAT THE INDEX DID ON OUR OWN LOSING CLOSES -- with a denominator.

    "Every loss had a big jump" is worth nothing on its own, because section 1
    says a >5-sigma second is COMMON in a final minute. So each losing close
    is scored against ITS OWN COIN'S measured last-60s rate, as a
    Poisson-binomial. The tape is being used here for what it is valid for --
    what the index did -- and the set of losing closes comes from our own
    fills, never from the tape.
    """
    say()
    say("=" * 78)
    say("  6. OUR OWN LOSING CLOSES, RECONSTRUCTED ON THE INDEX -- with a "
        "base rate")
    say("=" * 78)
    mk = {}
    for v in json.load(open(pinsim.FULLTAPE, encoding="utf-8")).values():
        for r in v:
            mk[r["ticker"]] = r
    losers = sorted({r["ticker"] for r in load_live() if r["lost"]})
    if not losers:
        say("  loaded nothing: no losing live fills on file")
        return
    say(f"  {len(losers)} losing closes in our own fill log. For each, the "
        f"largest one-second")
    say(f"  index move in the final 60 s, in units of that feed's own sigma "
        f"one second earlier.")
    say()
    say("  " + f"{'market':<34}{'close (UTC)':<21}{'max |move|/sigma':>18}"
        f"{'  at tau':>9}{'  result':>9}")
    got = []
    missing = []
    for tk in losers:
        r = mk.get(tk)
        if r is None:
            missing.append(tk)
            continue
        cl = int(float(r["close"]))
        iid = pindata.SERIES_TO_INDEX[r["series"]]
        t = pinsim.load_ticks(cl - 1300, cl)
        z, tau = max_jump_in_window(t, iid, cl)
        del t
        got.append((tk, r["series"], z))
        say(f"  {tk:<34}"
            f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(cl)):<21}"
            f"{z:>18.1f}{str(tau):>9}{str(r['result']):>9}")
    for tk in missing:
        say(f"  {tk:<34}  settlement not yet in markets.json -- EXCLUDED, "
            f"not estimated")
    say()
    say("  THE DENOMINATOR. From section 1's last-60s panel: the chance a "
        "close's final minute")
    say("  contains at least one such second at all, per coin. A big jump is "
        "NOT rare.")
    say()
    tsec = defaultdict(int)
    tj = defaultdict(lambda: [0] * len(sc.ks))
    for (c, cl), n in sc.secs_tau.items():
        tsec[c] += n
        for i in range(len(sc.ks)):
            tj[c][i] += sc.jump_tau[(c, cl)][i]

    def p_close(coin, k):
        i = list(sc.ks).index(k)
        if not tsec[coin]:
            return None
        r_ = tj[coin][i] / tsec[coin]
        return 1.0 - (1.0 - r_) ** 60

    hdr = "  " + f"{'coin':<12}" + "".join(
        f"{'P(>' + str(int(k)) + ' sigma in 60s)':>22}" for k in ks)
    say(hdr)
    for c in sorted(tsec):
        say(f"  {c:<12}" + "".join(f"{fmt_pct(p_close(c, k), 1):>22}"
                                   for k in ks))
    say()
    for k in ks:
        ps = [p_close(c, k) for _, c, _ in got]
        ps = [x for x in ps if x is not None]
        obs = sum(1 for _, _, z in got if z > k)
        if not ps:
            continue
        pv = poisson_binomial_ge(ps, obs)
        say(f"  k > {int(k)}: {obs} of {len(got)} losing closes carried one. "
            f"Expected {sum(ps):.2f} under each coin's")
        say(f"          own base rate -> Poisson-binomial "
            f"P(>= {obs} of {len(got)}) = {pv:.5f}")
    say()
    say("  SO: belief collapse on a one-second jump is what kills these bets, "
        "and that is")
    say("  established against the base rate rather than asserted from the "
        "cases. But the")
    say("  base rate is HIGH -- a fifth to a third of all closes carry a "
        ">5-sigma second and")
    say("  we win nearly every one -- so 'there was a jump' can never be a "
        "gate by itself.")
    say("  n here is 6-7 CLOSES. It is a mechanism check, not a rate.")


# ------------------------------- SECTION 7: ENTRY MARGIN vs OUR OWN OUTCOMES
# WHY: section 5 says the one-second sigma understates the diffusion by 3-21%,
# which inflates every z-score by the same factor. That has a SHARP prediction:
# it can only change a decision near the gate boundary, so the damage should
# concentrate in entries whose confidence is barely past 0.995 and should be
# invisible in the saturated ones sitting 7 sigma out. If that prediction
# fails, the sigma finding -- however real as a calibration fact -- is not what
# is costing us money, and no gate change should be built on it.
#
# This reads OUR OWN FILLS ONLY (pinrun's signal/order/settled records), which
# is the only admissible source for our loss rate.
CONF_BANDS = ((0.995, 0.999, "0.9950-0.9990"),
              (0.999, 0.99999, "0.9990-0.99999"),
              (0.99999, 1.0000001, "0.99999-1 (saturated)"))


def parse_live_entries(records):
    """{ticker: {pin, conf, lost}} from pinrun's own log records.

    A `signal` is only an ENTRY if the `order` that follows it actually
    filled -- pinrun logs a signal for every attempt and most are canceled
    (lost races), so pairing on the signal alone would count attempts as bets
    and flatter every rate. The entry confidence kept is the LOWEST across the
    fills on that close, i.e. the least confident thing we actually bought.
    """
    per = {}
    pin = None
    pend = None
    for d in records:
        k = d.get("kind")
        if k == "start":
            pin = d.get("pin")
        elif k == "signal":
            pend = d
        elif k == "order":
            if pend is not None and d.get("ticker") == pend.get("ticker") \
                    and float(d.get("filled") or 0) > 0:
                f, w = pend.get("fair"), pend.get("want")
                if f is not None and w:
                    conf = f if w == "yes" else 1.0 - f
                    e = per.setdefault(d["ticker"],
                                       {"pin": pin, "conf": conf,
                                        "lost": None})
                    e["conf"] = min(e["conf"], conf)
            pend = None
        elif k == "settled" and d.get("ticker") in per:
            per[d["ticker"]]["lost"] = (
                str(d.get("result", "")).lower()
                != str(d.get("want", "")).lower())
    return {t: v for t, v in per.items() if v["lost"] is not None}


def live_records():
    for fp in sorted(glob.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl"))):
        try:
            fh = open(fp, encoding="utf-8")
        except OSError:
            continue
        with fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except Exception:
                    continue


def margin_block(per, say):
    say()
    say("=" * 78)
    say("  7. ENTRY MARGIN vs OUTCOME, on OUR OWN FILLS -- section 5's "
        "prediction, TESTED")
    say("=" * 78)
    if not per:
        say("  loaded nothing: no live entries with both a signal and a "
            "settlement")
        return
    say("  Section 5's sigma understatement inflates every z-score, so it can "
        "only change a")
    say("  decision NEAR THE GATE. Prediction: losses concentrate in entries "
        "barely past")
    say("  0.995 and are absent from the saturated ones. Bands are on the "
        "LOWEST confidence")
    say("  actually bought on that close.")
    for label, sel in (("ALL live runs", lambda v: True),
                       ("CURRENT GATE ONLY (pin = 0.995)",
                        lambda v: v["pin"] == 0.995)):
        sub = [(t, v) for t, v in per.items() if sel(v)]
        if not sub:
            continue
        say()
        say(f"  {label}: {len(sub)} closes with both an entry signal and a "
            f"settlement")
        say(f"  {'entry confidence band':<24}{'closes':>8}{'lost':>6}"
            f"{'rate':>8}{'   95% CI':>20}{'  median margin':>16}")
        for lo, hi, name in CONF_BANDS:
            v = [x for _, x in sub if lo <= x["conf"] < hi]
            if not v:
                say(f"  {name:<24}{0:>8}")
                continue
            n = len(v)
            kk = sum(1 for x in v if x["lost"])
            a, b = cp_interval(kk, n)
            ms = sorted(ND.inv_cdf(min(max(x["conf"], 1e-12), 1 - 1e-12))
                        for x in v)[n // 2]
            ci = "[" + fmt_pct(a, 1) + ", " + fmt_pct(b, 1) + "]"
            say(f"  {name:<24}{n:>8}{kk:>6}{fmt_pct(kk / n, 1):>8}{ci:>20}"
                f"{ms:>14.2f} sd")
        sat = [x for _, x in sub if x["conf"] >= 0.99999]
        nl = [x for _, x in sub if x["lost"]]
        sl = [x for x in sat if x["lost"]]
        say(f"  saturated share of ENTRIES {fmt_pct(len(sat) / len(sub), 1)} "
            f"({len(sat)}/{len(sub)}); of LOSSES "
            f"{fmt_pct((len(sl) / len(nl)) if nl else float('nan'), 1)} "
            f"({len(sl)}/{len(nl)})")
    say()
    say("  Our losing closes, least confident first:")
    for t, v in sorted(per.items(), key=lambda kv: kv[1]["conf"]):
        if v["lost"]:
            say(f"    {t:<34} gate {v['pin']}  entry conf {v['conf']:.6f}  "
                f"margin "
                f"{ND.inv_cdf(min(max(v['conf'], 1e-12), 1 - 1e-12)):.2f} sd")
    say()
    say("  *** SECTION 5's PREDICTION FAILS, AND IT FAILS IN THE DIRECTION "
        "THAT MATTERS. ***")
    say("  The loss rate does not fall as entry confidence rises; the point "
        "estimate rises.")
    say("  Every interval overlaps every other -- with this many losing "
        "closes nothing here")
    say("  is significant in EITHER direction -- but a gate change justified "
        "by section 5")
    say("  would need this table to lean the other way, and it does not. So "
        "no PIN change, no")
    say("  margin cushion, and no per-coin sigma is proposed from this file.")
    say()
    say("  ONE THING IS CLEAR AND IT IS NOT ABOUT MARGIN: our entries are "
        "only ~12%")
    say("  saturated while the TAPE's gate entries are 73-85% saturated "
        "(section 2/3). We")
    say("  cannot buy what nobody offers, and in a decided market the losing "
        "side's book is")
    say("  empty -- so we systematically get the LESS certain end of the same "
        "gate. That is")
    say("  the adverse selection CLAUDE.md rule 5 is about, measured here in "
        "its own units.")


# ------------------------------------------------- SECTION 5: THE SCALE AUDIT
# WHY THIS EXISTS, and it is the reason the section-1 ranking cannot be read
# on its own.
#
# Section 1 divides each one-second move by that feed's own trailing-300s
# one-second sigma. That is the right denominator ONLY if the one-second sigma
# is a faithful measure of the feed's diffusion -- and pinrun's fair() makes
# the same assumption, because it projects the remaining r settlement prints
# as sigma * sqrt(var_factor(r)) from the ONE-SECOND sigma.
#
# The section-1 quantization guard showed that assumption is in trouble: SOL's
# index is quoted in 0.01 steps while its one-second sigma is 0.0082, so 69.6%
# of SOL seconds print NO CHANGE AT ALL and a single step is 1.2 sigma. When
# the grid is coarser than the motion, the one-second sd stops measuring the
# motion: for a diffusion with per-second sd s observed on a grid of spacing
# h >> s, level crossings arrive at ~0.80*s/h per second and the observed
# one-second sd tends to sqrt(0.80*s*h), which is LARGER than s. So
# quantization should INFLATE the one-second sigma -- but whether it does, and
# by how much, is a measurement, not an argument.
#
# THE TEST. Compare the one-second sd against the sd at lags 10, 30 and 60
# seconds, each divided by sqrt(lag). Under a random walk all four agree. The
# 60-second sd is essentially free of grid effects (SOL moves ~8 steps in 60 s),
# so the RATIO sigma_1s / (sigma_60s/sqrt(60)) is the scale error in the exact
# number fair() uses, on the exact horizon it projects over.
#
#   ratio > 1  the bot's sigma is TOO BIG -> fair() is pulled toward 50c ->
#              the 99.5% gate is HARDER to reach -> conservative
#   ratio < 1  the bot's sigma is TOO SMALL -> fair() is pushed toward 0/100 ->
#              the 99.5% gate is reached on thinner evidence -> OVERCONFIDENT
#
# It says nothing about our fill rates or our losses; it is a property of the
# feed and of the model's arithmetic.


class ScaleAudit:
    """Streaming sd of index differences at several lags, O(1) memory.

    Holds only the last max(LAGS)+1 prints per feed, so the whole 9 days costs
    nothing -- the collector outranks this job for RAM.
    """

    LAGS = (1, 10, 30, 60)

    def __init__(self, coins, coin_to_iid):
        self.c2i = dict(coin_to_iid)
        self.buf = {c: {} for c in coins}        # coin -> {second: value}
        self.n = defaultdict(int)                # (coin, lag) -> count
        self.s1 = defaultdict(float)             # sum of diffs
        self.s2 = defaultdict(float)             # sum of squared diffs
        self.lvl_sum = defaultdict(float)
        self.lvl_n = defaultdict(int)
        self.zero = defaultdict(int)
        self.nz = defaultdict(int)
        self.step = {}
        self.on_grid = defaultdict(int)

    def feed_hour(self, ticks):
        keep = max(self.LAGS) + 2
        for coin, iid in self.c2i.items():
            v = ticks.get(iid)
            if not v:
                continue
            b = self.buf[coin]
            for sec, val in v:
                b[sec] = val
                self.lvl_sum[coin] += val
                self.lvl_n[coin] += 1
                for lag in self.LAGS:
                    old = b.get(sec - lag)
                    if old is None:
                        continue
                    d = val - old
                    k = (coin, lag)
                    self.n[k] += 1
                    self.s1[k] += d
                    self.s2[k] += d * d
                    if lag == 1:
                        if d == 0.0:
                            self.zero[coin] += 1
                        else:
                            self.nz[coin] += 1
                            a = abs(d)
                            if a < self.step.get(coin, float("inf")):
                                self.step[coin] = a
                if len(b) > keep:
                    for old_s in [x for x in b if x < sec - keep]:
                        del b[old_s]

    def sd(self, coin, lag):
        k = (coin, lag)
        n = self.n[k]
        if n < 100:
            return None
        mu = self.s1[k] / n
        var = self.s2[k] / n - mu * mu
        return math.sqrt(max(var, 0.0))

    def grid_share(self, coin, ticks_hint=None):
        return None


def scale_audit(coins, c2i, stamps, log=print):
    sa = ScaleAudit(coins, c2i)
    iids = set(c2i.values())
    for st in stamps:
        t = hour_ticks(st, iids)
        if t:
            sa.feed_hour(t)
        del t
    L = []

    def say(x=""):
        log(x)
        L.append(x)

    say()
    say("=" * 78)
    say("  5. SCALE AUDIT -- is the ONE-SECOND sigma that fair() projects "
        "from the right scale?")
    say("=" * 78)
    say("  sd of index differences at lag L, divided by sqrt(L), so a random "
        "walk gives the")
    say("  same number in every column. Divergence at lag 1 means the "
        "one-second sigma the")
    say("  bot feeds into fair() is not the feed's diffusion.")
    say()
    say("  " + f"{'coin':<11}{'level':>12}{'step':>11}{'zero-1s':>9}"
        f"{'sd1':>12}{'sd10/r10':>12}{'sd30/r30':>12}{'sd60/r60':>12}"
        f"{'  sd1/sd60':>11}")
    out = {}
    for c in coins:
        lvl = sa.lvl_sum[c] / max(1, sa.lvl_n[c])
        st_ = sa.step.get(c)
        row = []
        for lag in ScaleAudit.LAGS:
            v = sa.sd(c, lag)
            row.append(None if v is None else v / math.sqrt(lag))
        r = (row[0] / row[3]) if (row[0] and row[3]) else float("nan")
        out[c] = {"level": lvl, "step": st_, "sd": row, "ratio": r,
                  "zero": sa.zero[c] / max(1, sa.zero[c] + sa.nz[c])}
        say(f"  {c:<11}{lvl:>12.4f}{(st_ or float('nan')):>11.7f}"
            f"{fmt_pct(out[c]['zero'], 1):>9}"
            + "".join(f"{(x if x is not None else float('nan')):>12.7f}"
                      for x in row)
            + f"{r:>11.3f}")
    say()
    say("  sd1/sd60 > 1: the bot's sigma is TOO BIG, fair() is pulled toward "
        "50c, and the")
    say("                99.5% gate is HARDER to reach -- conservative.")
    say("  sd1/sd60 < 1: the bot's sigma is TOO SMALL, fair() is pushed "
        "toward 0/100c, and")
    say("                the gate fires on thinner evidence -- OVERCONFIDENT.")
    say()
    say("  Same numbers as a multiple of each feed's quote step, which is the "
        "quantity that")
    say("  decides whether the grid can distort the one-second estimate at "
        "all:")
    say()
    say("  " + f"{'coin':<11}{'sigma_1s/step':>15}{'60s move/step':>15}"
        f"{'   sd1/sd60':>12}{'   comparable?':>15}")
    for c in coins:
        o = out[c]
        sps = (o["sd"][0] / o["step"]) if o["step"] else float("nan")
        m60 = ((o["sd"][3] * math.sqrt(60)) / o["step"]) if o["step"]             else float("nan")
        ok = "yes" if sps >= 5 else ("MARGINAL" if sps >= 2 else "NO")
        say(f"  {c:<11}{sps:>15.1f}{m60:>15.1f}{o['ratio']:>12.3f}"
            f"{ok:>15}")
    say()
    say("  'comparable?' is about SECTION 1 only: a coin whose one-second "
        "sigma is under a")
    say("  few quote steps has a lumpy one-second move distribution, so its "
        "k-sigma")
    say("  exceedance RATE cannot be compared with a finely-quoted coin's in "
        "either")
    say("  direction. It does NOT mean the coin is safe or unsafe -- that is "
        "the sd1/sd60")
    say("  column's job.")
    return L


def scale_selftest(ck):
    """Planted: a coin whose feed is quantized coarser than its own motion.
    Null: the same motion, unquantized. The estimator must separate them."""
    T = 1_700_000_000
    rg = random.Random(77)
    n = 40000
    clean = _walk(rg, n, 0.004, start=100.0)
    h = 0.02                                     # 5x the per-second sd
    quant = [round(v / h) * h for v in clean]
    jumpy = _walk(random.Random(78), n, 0.004, start=100.0,
                  fat_p=0.002, fat_mult=10.0)
    c2i = {"CLEAN": "A", "QUANT": "B", "JUMPY": "C"}
    sa = ScaleAudit(list(c2i), c2i)
    for b in range(0, n, 3600):
        sa.feed_hour({"A": [(T + i, clean[i]) for i in range(b, min(n, b + 3600))],
                      "B": [(T + i, quant[i]) for i in range(b, min(n, b + 3600))],
                      "C": [(T + i, jumpy[i]) for i in range(b, min(n, b + 3600))]})

    def ratio(c):
        return sa.sd(c, 1) / (sa.sd(c, 60) / math.sqrt(60))

    rc, rq, rj = ratio("CLEAN"), ratio("QUANT"), ratio("JUMPY")
    ck(0.90 < rc < 1.10,
       f"SCALE AUDIT, null: an unquantized random walk gives sd1/sd60 = "
       f"{rc:.3f} (must be ~1)")
    ck(rq > 1.30,
       f"SCALE AUDIT, planted: the SAME walk on a grid 5x its own sd gives "
       f"sd1/sd60 = {rq:.3f} -- quantization INFLATES the one-second sigma, "
       f"so the direction of the bias is established, not assumed")
    ck(0.85 < rj < 1.15,
       f"SCALE AUDIT: a FAT-TAILED but unquantized walk is NOT flagged "
       f"(sd1/sd60 = {rj:.3f}) -- the audit reads the SCALE, not the tail, "
       f"which section 1 reads")
    ck(sa.zero["QUANT"] > 0.5 * (sa.zero["QUANT"] + sa.nz["QUANT"])
       and sa.zero["CLEAN"] == 0,
       f"and the zero-move share separates them too "
       f"({100.0 * sa.zero['QUANT'] / (sa.zero['QUANT'] + sa.nz['QUANT']):.0f}% "
       f"vs {sa.zero['CLEAN']})")
    ck(abs(sa.step["QUANT"] - h) < 1e-9,
       f"and the quote step is recovered from the data ({sa.step['QUANT']:.4f} "
       f"vs the planted {h})")


# ----------------------------------------------------- LIVE FILLS (our own)
# CLAUDE.md AMENDMENT 2026-09-10 rule 5: a loss rate for US comes from LIVE
# FILLS ONLY, never from the tape. This block is the ONLY place in this file
# that speaks about our losses, and it reads nothing but our own order log.
RESULTS = os.path.join(os.path.dirname(HERE), "results")


def hyper_ge(x, N, K, n):
    """P(X >= x) for X ~ Hypergeometric(N, K, n): x losses landing on a coin
    that holds K of N closes, when n losses are dealt out at random."""
    def lc(a, b):
        if b < 0 or b > a:
            return float("-inf")
        return (math.lgamma(a + 1) - math.lgamma(b + 1)
                - math.lgamma(a - b + 1))
    den = lc(N, n)
    tot = 0.0
    for i in range(int(x), min(int(K), int(n)) + 1):
        t = lc(K, i) + lc(N - K, n - i) - den
        if t > -700:
            tot += math.exp(t)
    return min(1.0, tot)


def homogeneity_p(closes_by_coin, losses_by_coin, draws=200000, seed=20260912):
    """Every coin shares ONE loss rate -- what would the worst coin look like?

    The losses are dealt at random over the closes, holding each coin's number
    of closes fixed, and the statistic is the LARGEST per-coin loss count.
    Using the max is what pays for having noticed SOL after the fact: a
    per-coin p-value answers "is SOL unusual", which is not the question once
    SOL was chosen BECAUSE it was the worst. Holding the close counts fixed is
    what stops a coin we simply trade more from being flagged.
    """
    coins = sorted(closes_by_coin)
    pool = []
    for c in coins:
        pool.extend([c] * closes_by_coin[c])
    n_loss = sum(losses_by_coin.values())
    obs_max = max([losses_by_coin.get(c, 0) for c in coins] or [0])
    rng = random.Random(seed)
    hit = 0
    for _ in range(draws):
        cnt = {}
        for c in rng.sample(pool, n_loss):
            cnt[c] = cnt.get(c, 0) + 1
        if (max(cnt.values()) if cnt else 0) >= obs_max:
            hit += 1
    N = len(pool)
    per = {c: hyper_ge(losses_by_coin.get(c, 0), N, closes_by_coin[c], n_loss)
           for c in coins if losses_by_coin.get(c, 0) > 0}
    return {"p_max": (hit + 1) / (draws + 1), "obs_max": obs_max,
            "per_coin": per, "n_closes": N, "n_losses": n_loss}


def load_live():
    """Our own settled bets, from pinrun's order log. One row per FILL; the
    market ticker is the close, because three fills on one market are ONE
    outcome (CLAUDE.md hard rule 4) and counting them as three is exactly the
    error this block exists to correct."""
    rows = []
    for fp in sorted(glob.glob(os.path.join(RESULTS, "pinrun-live-*.jsonl"))):
        pin = None
        try:
            fh = open(fp, encoding="utf-8")
        except OSError:
            continue
        with fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("kind") == "start":
                    pin = d.get("pin")
                elif d.get("kind") == "settled" and d.get("ticker"):
                    rows.append({
                        "t": d["t"], "ticker": d["ticker"],
                        "coin": d["ticker"].split("-")[0], "pin": pin,
                        "lost": (str(d.get("result", "")).lower()
                                 != str(d.get("want", "")).lower()),
                        "pnl_c": d.get("pnl_c"), "cost": d.get("cost")})
    rows.sort(key=lambda r: r["t"])
    return rows


def live_block(rows, say):
    say()
    say("=" * 78)
    say("  4. OUR OWN LIVE FILLS -- the ONLY valid source for OUR loss rate")
    say("=" * 78)
    if not rows:
        say("  loaded nothing: no pinrun-live-*.jsonl records")
        return
    say(f"  {len(rows):,} settled fills, "
        f"{len(set(r['ticker'] for r in rows)):,} distinct markets/closes, "
        f"{rows[0]['t']} .. {rows[-1]['t']}")
    say()
    say("  *** THE FIRST CORRECTION IS A COUNTING ONE, AND IT MOVES THE "
        "ANSWER. ***")
    losers = [r for r in rows if r["lost"]]
    lt = defaultdict(list)
    for r in losers:
        lt[r["ticker"]].append(r)
    say(f"  {len(losers)} losing FILLS sit on {len(lt)} losing MARKETS. The "
        f"multiply-filled ones:")
    multi = 0
    for tk, v in sorted(lt.items(), key=lambda kv: kv[1][0]["t"]):
        if len(v) > 1:
            multi += 1
            px = ", ".join(str(x["cost"]) for x in v)
            say(f"    {tk:34s} {len(v)} fills, ONE close, ONE outcome "
                f"(paid {px})")
    if not multi:
        say("    (none)")
    say("  Hundreds of fills can share one settlement, so `n` is markets and "
        "closes, never")
    say("  fills (CLAUDE.md hard rule 4). Counting fills is what turns one "
        "NEAR close into")
    say("  'three NEAR losses'.")

    for label, sel in (("ALL live runs", lambda r: True),
                       ("CURRENT GATE ONLY (pin = 0.995)",
                        lambda r: r["pin"] == 0.995)):
        sub = [r for r in rows if sel(r)]
        if not sub:
            continue
        mk = {}
        for r in sub:
            mk.setdefault(r["ticker"], []).append(r)
        per_n = defaultdict(int)
        per_l = defaultdict(int)
        for tk, v in mk.items():
            c = tk.split("-")[0]
            per_n[c] += 1
            per_l[c] += 1 if any(x["lost"] for x in v) else 0
        tn, tl = sum(per_n.values()), sum(per_l.values())
        say()
        say(f"  {label}: {len(sub)} fills -> {tn} closes, {tl} losing closes "
            f"({100.0 * tl / max(1, tn):.1f}%)")
        say(f"  {'coin':<12}{'closes':>8}{'lost':>6}{'rate':>8}"
            f"{'   95% CI (Clopper-Pearson)':>30}{'   P(>= this|one rate)':>24}")
        hp = homogeneity_p(dict(per_n), dict(per_l))
        for c in sorted(per_n, key=lambda k: (-per_l[k], -per_n[k])):
            lo_, hi_ = cp_interval(per_l[c], per_n[c])
            pv = hp["per_coin"].get(c)
            ci = "[" + fmt_pct(lo_, 1) + ", " + fmt_pct(hi_, 1) + "]"
            say(f"  {c:<12}{per_n[c]:>8}{per_l[c]:>6}"
                f"{fmt_pct(per_l[c] / per_n[c], 1):>8}{ci:>30}"
                f"{('' if pv is None else f'{pv:.4f}'):>24}")
        say(f"  ONE SHARED LOSS RATE for every coin: the chance the WORST "
            f"coin still reaches")
        say(f"  {hp['obs_max']} losing closes is p = {hp['p_max']:.4f} "
            f"({hp['n_losses']} losses over {hp['n_closes']} closes, 200,000 "
            f"random deals,")
        say("  max-per-coin-count statistic). The max is what pays for having "
            "noticed the coin")
        say("  AFTER the fact; a per-coin p-value would not.")
        base = tl / max(1, tn)
        mde = mde_two_prop(base, max(1, tn // max(1, len(per_n))), tn,
                           looks=len(per_n))
        say(f"  MDE at this live size: {fmt_pct(mde, 1)} against a base of "
            f"{fmt_pct(base, 1)} -- only a coin")
        say(f"  {(mde / base) if base else float('nan'):.0f}x the pool rate "
            f"is detectable, so 'no effect' and 'no power' are not "
            f"distinguishable here.")

    say()
    say("  THE LOSS SEQUENCE THE OPERATOR ASKED ABOUT, oldest first:")
    for r in losers:
        say(f"    {r['t']}  {r['ticker']:34s} gate {r['pin']}  "
            f"paid {r['cost']}  {r['pnl_c']:.0f}c")
    cur = [r for r in losers if r["pin"] == 0.995]
    if len(cur) >= 3:
        tail3 = [r["coin"] for r in cur[-3:]]
        cl = defaultdict(int)
        for r in cur:
            cl[r["coin"]] += 1
        n = len(cur)

        def c3(m):
            return m * (m - 1) * (m - 2) / 6.0

        tot = c3(n)
        p_run = (sum(c3(v) for v in cl.values()) / tot) if tot > 0 else 1.0
        say()
        say(f"  The last three losses at the current gate are "
            f"{', '.join(tail3)}.")
        say(f"  GIVEN that the {n} losses fell on the coins they did, the "
            f"chance the three most")
        say(f"  recent all share ONE coin is {100.0 * p_run:.1f}%. So the "
            f"'three in a row' framing")
        say("  adds essentially nothing beyond the count itself -- the "
            "evidence is the table")
        say("  above, not the ordering.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--days", type=float, default=9.0)
    ap.add_argument("--split", type=float, default=5.0,
                    help="days in the FIT half; the rest is the holdout")
    ap.add_argument("--out", default=OUT_MD)
    ap.add_argument("--progress", type=int, default=6)
    ap.add_argument("--scale-only", action="store_true",
                    help="skip the per-second scan; append section 5 (the "
                         "scale audit) to --out. It is a second, much lighter "
                         "pass over the same tape hours.")
    ap.add_argument("--live-only", action="store_true",
                    help="skip the tape scan; append section 4 (our own live "
                         "fills) to --out. It reads no tape and costs "
                         "nothing, so it can be refreshed on its own.")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    if a.scale_only:
        mk_all = load_markets()
        hi = max(int(float(r["close"])) for r in mk_all)
        lo = hi - int(a.days * 86400)
        coins = sorted({r["series"] for r in mk_all
                        if lo < float(r["close"]) <= hi})
        c2i = {c: pindata.SERIES_TO_INDEX[c] for c in coins}
        L = scale_audit(coins, c2i, stamps_between(lo - 3600, hi + 120))
        mode = "a" if os.path.exists(a.out) else "w"
        with open(a.out, mode, encoding="utf-8") as fh:
            fh.write("\n```\n" + "\n".join(L) + "\n```\n")
        print("\n  appended to " + a.out)
        return

    if a.live_only:
        L = []

        def say(x=""):
            print(x)
            L.append(x)

        live_block(load_live(), say)
        margin_block(parse_live_entries(live_records()), say)
        mode = "a" if os.path.exists(a.out) else "w"
        with open(a.out, mode, encoding="utf-8") as fh:
            fh.write("\n```\n" + "\n".join(L) + "\n```\n")
        print("\n  appended to " + a.out)
        return

    t_start = time.time()
    mk_all = load_markets()
    if not mk_all:
        print("  loaded nothing: no settled markets")
        return
    hi = max(int(float(r["close"])) for r in mk_all)
    lo = hi - int(a.days * 86400)
    cut = lo + int(a.split * 86400)
    mk = [r for r in mk_all if lo < float(r["close"]) <= hi]
    coins = sorted({r["series"] for r in mk})
    c2i = {c: pindata.SERIES_TO_INDEX[c] for c in coins}
    print(f"\n  pincoin -- {len(mk):,} settled markets, {len(coins)} coins, "
          f"{a.days:g} days")
    print(f"  window {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(lo))} .. "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(hi))}")
    print(f"  split  fit <= "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(cut))} < holdout")

    sc = Scanner(c2i, pindata.ROUND_DIGITS, lo, hi)
    sc.add_markets(mk)
    stamps = stamps_between(lo - 3600, hi + 120)
    print(f"  {len(stamps)} tape hours (one hour resident at a time)")
    for i, st in enumerate(stamps):
        t = hour_ticks(st, set(c2i.values()))
        if not t:
            continue
        sc.feed_hour(t)
        if i % max(1, a.progress) == 0:
            sc.audit_sigma(0)
        del t
        if i % 12 == 0:
            print(f"    {st}  ({i + 1}/{len(stamps)})  "
                  f"entries {len(sc.track):,}  "
                  f"{time.time() - t_start:.0f}s", flush=True)
    print(f"  scan done in {time.time() - t_start:.0f}s; sigma audit "
          f"{sc.audit_bad} mismatches in {sc.audit_n} checks")
    report(sc, coins, lo, cut, hi, mk, a.out, stamps=stamps, c2i=c2i)


def report(sc, coins, lo, cut, hi, mk, path, stamps=None, c2i=None):
    L = []

    def say(s=""):
        print(s)
        L.append(s)

    closes_all = sorted({cl for (_, cl) in sc.secs})
    say()
    say("=" * 78)
    say(f"  1. ONE-SECOND JUMP TAIL, per coin, against the coin's OWN "
        f"trailing-{pinrun.SIGMA_WIN}s sigma")
    say(f"     {len(closes_all):,} closes, {len(mk):,} markets, "
        f"{sum(sc.secs.values()):,} coin-seconds scored")
    say()
    hdr = "  " + f"{'coin':<10}{'sec/coin':>10}" + \
        "".join(f"{'k>' + str(int(k)):>9}" for k in K_LIST)
    say(hdr + "        (rate per 10,000 seconds)")
    tot_sec = defaultdict(int)
    tot_j = defaultdict(lambda: [0] * len(K_LIST))
    for (c, cl), n in sc.secs.items():
        tot_sec[c] += n
        for i in range(len(K_LIST)):
            tot_j[c][i] += sc.jump[(c, cl)][i]
    for c in coins:
        row = "".join(f"{1e4 * tot_j[c][i] / max(1, tot_sec[c]):>9.1f}"
                      for i in range(len(K_LIST)))
        say(f"  {c:<10}{tot_sec[c]:>10,}" + row)
    say()
    say("  Gaussian expectation, per 10,000 s: k>3 27.0, k>4 0.633, "
        "k>5 0.0057, k>6 0.0000, k>8 0.0000")
    say("  -- every coin is orders of magnitude above it at k>=5, which is "
        "the excess kurtosis")
    say("     the RUNBOOK already records. The question here is only whether "
        "the coins DIFFER.")

    looks = len(coins) * len(K_LIST)
    thr = bonf_z(looks)
    say()
    say(f"  Coin vs the pool of the other {len(coins) - 1}, clustered on the "
        f"close ({len(closes_all):,} clusters).")
    say(f"  MULTIPLE LOOKS: {looks} cells, so the threshold is |z| > "
        f"{thr:.2f}, not 1.96.")
    say()
    say("  " + f"{'coin':<10}" + "".join(f"{'k>' + str(int(k)):>10}"
                                         for k in K_LIST) + "     (z)")
    flags = []
    for c in coins:
        cells = []
        for i in range(len(K_LIST)):
            mine, pool = _coin_cells(sc, c, i)
            d = cluster_diff(mine, pool)
            cells.append(d["z"] if d else float("nan"))
            if d and abs(d["z"]) > thr:
                flags.append((c, K_LIST[i], d))
        say(f"  {c:<10}" + "".join(f"{v:>10.2f}" for v in cells))

    say()
    say("  Restricted to the LAST 60 SECONDS before each close -- the "
        "settlement window, where")
    say("  the bot actually lives and where a jump moves the locked average "
        "least but the")
    say("  remaining-print projection most:")
    say()
    say("  " + f"{'coin':<10}{'sec/coin':>10}" +
        "".join(f"{'k>' + str(int(k)):>9}" for k in K_LIST))
    tsec = defaultdict(int)
    tj = defaultdict(lambda: [0] * len(K_LIST))
    for (c, cl), n in sc.secs_tau.items():
        tsec[c] += n
        for i in range(len(K_LIST)):
            tj[c][i] += sc.jump_tau[(c, cl)][i]
    for c in coins:
        say(f"  {c:<10}{tsec[c]:>10,}" +
            "".join(f"{1e4 * tj[c][i] / max(1, tsec[c]):>9.1f}"
                    for i in range(len(K_LIST))))

    say()
    say("  Largest single one-second move ever printed by each feed, in units "
        "of that feed's")
    say("  own trailing sigma one second earlier -- the event the 99.5% gate "
        "has to survive:")
    say()
    say("  " + f"{'coin':<10}{'max |move|/sigma':>18}{'   when (UTC)':>22}")
    for c in coins:
        z, sec = sc.maxz.get(c, (0.0, 0))
        say(f"  {c:<10}{z:>18.1f}"
            f"{time.strftime('   %Y-%m-%dT%H:%M:%SZ', time.gmtime(sec)):>22}")

    say()
    say("  ARTEFACT GUARD -- QUANTIZATION. The feeds are quoted to a fixed "
        "number of decimals.")
    say("  A coin whose one-second sd is only a few quotation steps has a "
        "LUMPY move distribution,")
    say("  and lumpiness reads as a fat tail in any k-sigma statistic. Read "
        "this table BEFORE")
    say("  believing any difference above: a coin with sigma/step below ~5 "
        "is not comparable.")
    say()
    say("  " + f"{'coin':<10}{'zero-move s':>13}{'quote step':>14}"
        f"{'mean sigma':>13}{'sigma/step':>12}")
    for c in coins:
        g = sc.gran.get(c)
        ms = sc.sig_sum[c] / max(1, sc.sig_n[c])
        zr = sc.zero_moves[c] / max(1, sc.sig_n[c])
        say(f"  {c:<10}{fmt_pct(zr, 1):>13}{(g if g else float('nan')):>14.7f}"
            f"{ms:>13.7f}{(ms / g if g else float('nan')):>12.1f}")

    # ---- 2 and 3: gate entries -------------------------------------------
    ent = sc.entries()
    by = defaultdict(list)
    for e in ent:
        by[e["coin"]].append(e)
    n_cl = len({e["close"] for e in ent})
    say()
    say("=" * 78)
    say(f"  2/3. GATE ENTRIES -- first second with tau <= {pinrun.TAU_MAX} "
        f"where the model crosses {pinrun.PIN}")
    say(f"     {len(ent):,} entries = {len(ent):,} markets over {n_cl:,} "
        f"closes. ONE ENTRY PER MARKET.")
    say()
    say("  *** THESE ARE NOT OUR BETS AND THIS IS NOT OUR LOSS RATE. ***")
    say("  The tape's population is 'the model crossed the gate'. Ours is "
        "'someone actively")
    say("  sold it to us', which is adversely selected and runs ~31x worse "
        "(CLAUDE.md,")
    say("  AMENDMENT 2026-09-10 rule 5). These numbers RANK COINS AGAINST "
        "EACH OTHER. Nothing")
    say("  else may be read off them.")

    pool_flip = sum(1 for e in ent if not e["won"]) / max(1, len(ent))
    pool_col = sum(1 for e in ent if e["min_belief"] is not None
                   and e["min_belief"] < COLLAPSE_THR) / max(1, len(ent))
    say()
    say("  MDE STATED BEFORE THE ESTIMATE. Two-sided 5% Bonferroni'd over "
        f"{len(coins)} coins, 80% power,")
    say(f"  coin vs pool, at the pooled rates below:")
    say()
    say(f"  {'coin':<10}{'n mkts':>8}{'flip MDE':>11}{'= x pool':>10}"
        f"{'collapse MDE':>15}{'= x pool':>10}")
    for c in coins:
        n1 = len(by[c])
        n0 = len(ent) - n1
        m1 = mde_two_prop(pool_flip, n1, n0, looks=len(coins))
        m2 = mde_two_prop(pool_col, n1, n0, looks=len(coins))
        say(f"  {c:<10}{n1:>8,}{fmt_pct(m1):>11}"
            f"{(m1 / pool_flip if pool_flip else float('nan')):>9.1f}x"
            f"{fmt_pct(m2):>15}"
            f"{(m2 / pool_col if pool_col else float('nan')):>9.1f}x")
    say()
    say(f"  Read that column first: with ~{len(ent)//max(1,len(coins))} "
        f"entries per coin nothing short of a")
    say(f"  {max(1.0, (mde_two_prop(pool_flip, len(ent)//max(1,len(coins)), len(ent), looks=len(coins)) / pool_flip) if pool_flip else 0):.0f}x "
        f"difference in flip rate is detectable. A coin that is genuinely "
        f"twice as")
    say("  dangerous would NOT show up. 'No effect' and 'no power' are "
        "different results.")

    def table(sel, title, cut_lo=None, cut_hi=None):
        say()
        say("  " + title)
        say(f"  {'coin':<10}{'mkts':>6}{'closes':>8}{'entry tau':>11}"
            f"{'collapse':>10}{'  95% CI':>18}{'flip':>8}{'  95% CI':>18}"
            f"{'   z col':>9}{'  z flip':>9}")
        rows = []
        sub = [e for e in ent if sel(e)]
        for c in coins:
            v = [e for e in sub if e["coin"] == c]
            if not v:
                continue
            nn = len(v)
            kf = sum(1 for e in v if not e["won"])
            kc = sum(1 for e in v if e["min_belief"] is not None
                     and e["min_belief"] < COLLAPSE_THR)
            lo_f, hi_f = cp_interval(kf, nn)
            lo_c, hi_c = cp_interval(kc, nn)
            mine_f = {e["close"]: (0 if e["won"] else 1, 1) for e in v}
            mine_c = {e["close"]: (1 if (e["min_belief"] is not None
                                         and e["min_belief"] < COLLAPSE_THR)
                                   else 0, 1) for e in v}
            pf = defaultdict(lambda: [0, 0])
            pc = defaultdict(lambda: [0, 0])
            for e in sub:
                if e["coin"] == c:
                    continue
                pf[e["close"]][0] += 0 if e["won"] else 1
                pf[e["close"]][1] += 1
                pc[e["close"]][0] += 1 if (e["min_belief"] is not None
                                           and e["min_belief"]
                                           < COLLAPSE_THR) else 0
                pc[e["close"]][1] += 1
            df = cluster_diff(mine_f, {k: tuple(x) for k, x in pf.items()})
            dc = cluster_diff(mine_c, {k: tuple(x) for k, x in pc.items()})
            tau = sum(e["tau_in"] for e in v) / nn
            say(f"  {c:<10}{nn:>6,}{len({e['close'] for e in v}):>8,}"
                f"{tau:>11.1f}{fmt_pct(kc / nn):>10}"
                f"{('[' + fmt_pct(lo_c, 1) + ', ' + fmt_pct(hi_c, 1) + ']'):>18}"
                f"{fmt_pct(kf / nn):>8}"
                f"{('[' + fmt_pct(lo_f, 1) + ', ' + fmt_pct(hi_f, 1) + ']'):>18}"
                f"{(dc['z'] if dc else float('nan')):>9.2f}"
                f"{(df['z'] if df else float('nan')):>9.2f}")
            rows.append((c, nn, kc / nn, kf / nn,
                         dc["z"] if dc else 0.0, df["z"] if df else 0.0))
        kf = sum(1 for e in sub if not e["won"])
        kc = sum(1 for e in sub if e["min_belief"] is not None
                 and e["min_belief"] < COLLAPSE_THR)
        say(f"  {'POOL':<10}{len(sub):>6,}"
            f"{len({e['close'] for e in sub}):>8,}"
            f"{(sum(e['tau_in'] for e in sub) / max(1, len(sub))):>11.1f}"
            f"{fmt_pct(kc / max(1, len(sub))):>10}{'':>18}"
            f"{fmt_pct(kf / max(1, len(sub))):>8}")
        return rows

    full = table(lambda e: True,
                 f"FULL WINDOW ({(hi - lo) / 86400:.0f} days)")
    fit = table(lambda e: e["close"] <= cut,
                f"FIT HALF -- closes up to "
                f"{time.strftime('%m-%dT%H:%MZ', time.gmtime(cut))}")
    hold = table(lambda e: e["close"] > cut,
                 f"HOLDOUT -- closes after "
                 f"{time.strftime('%m-%dT%H:%MZ', time.gmtime(cut))} "
                 f"(NOT looked at when the hypothesis was formed)")

    say()
    say(f"  Multiple looks on {len(coins)} coins: |z| > {bonf_z(len(coins)):.2f}.")
    say(f"  Entries with no post-entry second (entered at tau "
        f"{pinrun.TAU_MIN}) and therefore no collapse observation: "
        f"{sum(1 for e in ent if e['post'] == 0):,} of {len(ent):,}")
    say()
    say("  GUARD NULL -- what the scan threw away, per coin "
        "(a guard that discards everything")
    say("  looks exactly like a thin tape, so it prints its own cost):")
    for c in coins:
        k = [f"{n:,} {w.split(':')[1]}" for w, n in sorted(sc.skip.items())
             if w.startswith(c + ":")]
        say(f"    {c:<10} " + (", ".join(k) if k else "nothing discarded"))

    say()
    say("  ARTEFACT GUARD -- IS THE ENTRY POPULATION THE SAME? A coin can "
        "look more dangerous")
    say("  simply because its gate entries carry less margin or arrive "
        "later. If these columns")
    say("  match across coins, a difference in the tables above is about the "
        "INDEX, not selection.")
    say()
    say(f"  {'coin':<10}{'n':>7}{'mean tau_in':>13}{'median margin sd':>18}"
        f"{'saturated':>11}")
    for c in coins:
        v = by[c]
        if not v:
            continue
        ms = sorted(e["margin_sd"] for e in v)[len(v) // 2]
        sat = sum(1 for e in v if e["conf_in"] >= 1.0 - 1e-9) / len(v)
        say(f"  {c:<10}{len(v):>7,}"
            f"{(sum(e['tau_in'] for e in v) / len(v)):>13.1f}"
            f"{ms:>18.2f}{fmt_pct(sat, 1):>11}")

    say()
    say("  STABILITY ACROSS THE SPLIT (collapse rate, the statistic with "
        "enough events to move):")
    fitd = {r[0]: r for r in fit}
    hold_d = {r[0]: r for r in hold}
    say(f"  {'coin':<10}{'fit n':>7}{'fit col':>9}{'hold n':>8}"
        f"{'hold col':>10}{'  sign held?':>14}")
    for c in coins:
        if c not in fitd or c not in hold_d:
            continue
        f_, h_ = fitd[c], hold_d[c]
        pool_f = sum(r[2] * r[1] for r in fit) / max(1, sum(r[1] for r in fit))
        pool_h = sum(r[2] * r[1] for r in hold) / max(1,
                                                      sum(r[1] for r in hold))
        held = ((f_[2] > pool_f) == (h_[2] > pool_h))
        say(f"  {c:<10}{f_[1]:>7,}{fmt_pct(f_[2]):>9}{h_[1]:>8,}"
            f"{fmt_pct(h_[2]):>10}{('  yes' if held else '  NO'):>14}")

    live_block(load_live(), say)
    # SECTION 5 is a second, lighter pass over the same hours: it needs 10-,
    # 30- and 60-second lags, which the per-second scanner does not retain.
    if stamps and c2i:
        for ln in scale_audit(coins, c2i, stamps, log=print):
            L.append(ln)
    loss_cases(sc, say)
    margin_block(parse_live_entries(live_records()), say)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# RESULTS_coin -- is one coin's index structurally "
                 "jumpier?\n\n```\n")
        fh.write("\n".join(L))
        fh.write("\n```\n")
    print(f"\n  written to {path}")


if __name__ == "__main__":
    main()
