#!/usr/bin/env python3
# VERSION: 2026-09-08-px1
"""pinexit.py -- AFTER we bought, when does a loser start looking different
from a winner?

THE OPERATOR'S QUESTION, VERBATIM: "After we bought when did it start being
different than a winning bet? When and what said that it's about to either go
volatile or even better cross the line? Or is it a case of playing it too close
to the line?"

WHY THIS IS A DIFFERENT QUESTION FROM EVERY EARLIER STUDY

Everything measured so far looked at ENTRY time and asked "could we have known
not to take this trade?" -- answer, refuted: no entry feature separates losers
from winners once the model's own z is held fixed (p = 0.14-0.99), and every
entry gate costs 22-44 winners per loss avoided. THIS file asks the opposite:
given that we are already in, does the position TELL US, second by second, that
it is going wrong, EARLY ENOUGH TO ACT?

"Early enough" is a hard number, not a feeling. Our order round trip is ~100 ms
plus a 50 ms decision loop plus the time to actually get filled in a race we
lose 26% of the time. So a signal is USABLE only if it fires with >= 3 seconds
still on the clock. Anything at tau 1-2 is a report, not a warning.

AND THERE IS A SECOND, HARDER BAR THAT MOST OF THIS FILE EXISTS TO MEASURE.
A signal that fires only AFTER the projected settlement mu has already crossed
K_eff is worthless even with time on the clock, because by then the market has
repriced: IDEAS_LOG #32 measured the other side at 76-98c once the model is 90%
sure. Buying a 95c entry and a 93c hedge pays 188c for a $1.00 payout. So every
signal is scored on TWO clocks:

    tau_fire              seconds left when it fires  (>= 3 = executable)
    tau_fire - tau_cross  seconds it fires BEFORE mu crosses (> 0 = a warning,
                          <= 0 = a report of something that already happened)

WHAT IS TRACKED, per second, from entry to the last settling print

    cush_sd     how many settlement-sd of cushion are LEFT: (mu - K_eff)/sd,
                signed so positive = we are winning. This is the model's own z.
    cush_bp     the same cushion in basis points of the index level -- the
                "playing too close to the line" measure, comparable across coins
    reqmv_bp    required_move: how far the average of the REMAINING prints must
                travel against us, in bp. Blows up as r -> 0.
    d_reqmv     its change over the last 3 s (positive = the required move is
                growing, i.e. we are getting safer)
    p_model     the model's p(WE LOSE), recomputed live with the live r
    p_mkt       the market's implied p(we lose) = 1 - (our side's book mid)
    mkt_lead    p_mkt - p_model: the MARKET is more frightened than we are.
                This is the direction tonight's loss actually moved in -- the
                book repriced NO from 97c to ~60c INSIDE the second before the
                index print that justified it -- and it is the opposite sign to
                the EV-optimal hedge rule in pinhedge.py, which fires when the
                MODEL is more pessimistic than the market. Both signs are
                carried and both are scored, because assuming the sign is how a
                real effect gets reported backwards.
    diverge     p_model - p_mkt (the pinhedge direction)
    rv_ratio    realised sd of 1 s index moves SINCE ENTRY / the sigma we
                entered on (the "is it about to go volatile" measure)
    spot_bp     distance of the CURRENT spot to K_eff in bp, signed for safety

    (cush_bp and spot_bp are reported in bp, not raw index units, because raw
    units are not comparable between BTC at ~$79,000 and DOGE at ~$0.088, and an
    AUC pooled over nine coins in raw units would rank coins, not danger. The
    raw absolute number IS given for tonight's loss, where one coin is all
    there is.)

THE ARITHMETIC IS NOT RE-DERIVED, IT IS REPRODUCED. mu, r, req and sigma are
recomputed here from the raw 1/sec index tape with pindata.py's exact formulae,
and main() checks them against the mu/req already stored in rows.jsonl before
using anything. A replay that cannot reproduce the dataset it is extending has
no business scoring it.

HOW SEPARATION IS SCORED, AND WHY AUC

AUC (the Mann-Whitney statistic) = the probability that a randomly chosen LOSER
looks worse on the signal than a randomly chosen WINNER. 0.50 is nothing; 1.00
is perfect. It is used because it is invariant to any monotone rescaling, so it
cannot be flattered by picking a threshold after seeing the answer.

n IS CLOSES. Every confidence interval comes from a bootstrap that resamples the
132 CLOSES, not the rows -- nine coins settle on the same quarter hour at
rho ~ 0.8, so rows are not independent. The MDE is printed BEFORE the estimate.

SELF-TEST: builds (a) a PLANTED world where the outcome is decided by a feature
that only becomes visible at a known second, and requires the estimator to find
AUC ~ 0.5 before it and ~ 1.0 after; and (b) a NULL world where the outcome is a
coin flip independent of every path, and requires the estimator to find nothing
-- no AUC significantly off 0.500 and no usable signal.
"""
import argparse
import array
import bisect
import glob
import gzip
import json
import math
import os
import pickle
import random
import sys
import time
import zlib
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                            # noqa: E402

ND = NormalDist()

DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"
ROWS = r"C:\kals-repo\results\pindata\rows.jsonl"
WORK = r"C:\Users\Joe\AppData\Local\Temp\kals-work"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}
ROUND_DIGITS = {"KXBTC15M": 2, "KXETH15M": 2, "KXBNB15M": 2,
                "KXSOL15M": 4, "KXXRP15M": 4, "KXZEC15M": 4,
                "KXHYPE15M": 4, "KXNEAR15M": 4, "KXDOGE15M": 7}

# Features are all oriented so that HIGH = DANGER, and the safety-shaped ones
# are stored negated with a "neg_" name, so every column of every table reads
# the same way and a sign error is visible rather than absorbed.
FEATS = ["p_gain", "sd_loss", "p_model", "p_mkt", "mkt_lead", "diverge",
         "rv_ratio", "neg_cush_sd", "neg_cush_bp", "neg_reqmv_bp",
         "neg_d_reqmv", "neg_spot_bp"]
SHORT = {"p_gain": "pGAIN", "sd_loss": "sdLOST",
         "p_model": "pmodel", "p_mkt": "pmkt", "mkt_lead": "mktLEAD",
         "diverge": "diverg",
         "rv_ratio": "rvrat", "neg_cush_sd": "-cushSD",
         "neg_cush_bp": "-cushBP", "neg_reqmv_bp": "-reqBP",
         "neg_d_reqmv": "-dreq3", "neg_spot_bp": "-spotBP"}
NICE = {
    "p_gain": "p(lose) NOW minus p(lose) AT ENTRY -- zero at k=0 by "
              "construction, so its AUC at k=0 must be exactly 0.500",
    "sd_loss": "settlement-sd of cushion LOST since entry -- also exactly "
               "zero at k=0",
    "p_model": "the model's own p(we lose), recomputed live",
    "p_mkt": "the market's implied p(we lose), from the book mid",
    "mkt_lead": "the MARKET is more scared than the model: p_mkt - p_model",
    "diverge": "divergence: model p(lose) minus market p(lose)",
    "rv_ratio": "realised vol since entry / the sigma we entered on",
    "neg_cush_sd": "cushion left in settlement-sd (low = close to the line)",
    "neg_cush_bp": "cushion left in bp of the index (low = close to the line)",
    "neg_reqmv_bp": "required move in bp (low = little left to protect us)",
    "neg_d_reqmv": "3 s change in required move (low = eroding fast)",
    "neg_spot_bp": "current spot's distance to K_eff in bp",
}

MIN_CLUSTERS = 30
USABLE_TAU = 3          # a hedge needs >= 3 s to reach the exchange and fill


# ===========================================================================
# separation statistics
# ===========================================================================
def auc(pos, neg):
    """P(a random LOSER scores higher than a random WINNER), ties at 0.5."""
    if not pos or not neg:
        return None
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    ranks = [0.0] * len(allv)
    i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            ranks[t] = r
        i = j + 1
    rp = sum(ranks[t] for t in range(len(allv)) if allv[t][1] == 1)
    n1, n0 = len(pos), len(neg)
    return (rp - n1 * (n1 + 1) / 2.0) / (n1 * n0)


class ClusterAUC:
    """AUC with a CLOSE-clustered bootstrap CI, computed on binned values.

    Binning to nbins quantile bins makes one bootstrap draw a histogram sum
    (n_closes x nbins) instead of a re-sort of every row, which is what makes a
    300-draw CI affordable in pure Python on a million cells. The bins come from
    the POOLED distribution, so they cannot separate the groups by themselves;
    the self-test proves that by running the whole machine on a null world.
    """

    __slots__ = ("nbins", "v", "y", "c")

    def __init__(self, nbins=128):
        self.nbins = nbins
        self.v = array.array("d")
        self.y = array.array("b")
        self.c = array.array("i")

    def add(self, val, lose, close):
        self.v.append(val)
        self.y.append(1 if lose else 0)
        self.c.append(close)

    def n(self):
        return len(self.v)

    def npos(self):
        return sum(self.y)

    def nclust(self):
        return len(set(self.c))

    def point(self):
        pos = [self.v[i] for i in range(len(self.v)) if self.y[i]]
        neg = [self.v[i] for i in range(len(self.v)) if not self.y[i]]
        return auc(pos, neg)

    def _hists(self):
        srt = sorted(self.v)
        n = len(srt)
        edges = [srt[max(0, min(n - 1, (n * k) // self.nbins))]
                 for k in range(1, self.nbins)]
        byc = {}
        for i in range(n):
            b = bisect.bisect_right(edges, self.v[i])
            h = byc.get(self.c[i])
            if h is None:
                h = byc[self.c[i]] = [array.array("i", [0] * self.nbins),
                                      array.array("i", [0] * self.nbins)]
            h[self.y[i]][b] += 1
        # h is indexed [negatives, positives]; every caller wants (POS, NEG),
        # and getting that pair the wrong way round returns 1 - AUC, which the
        # self-test caught by comparing the binned figure to the exact one.
        return [(h[1], h[0]) for h in byc.values()]

    @staticmethod
    def _auc_hist(hp, hn):
        n1 = sum(hp)
        n0 = sum(hn)
        if n1 == 0 or n0 == 0:
            return None
        below = 0
        tot = 0.0
        for b in range(len(hp)):
            if hp[b]:
                tot += hp[b] * (below + 0.5 * hn[b])
            below += hn[b]
        return tot / (n1 * n0)

    def ci(self, draws=300, seed=17):
        """95% CI on AUC from resampling CLOSES with replacement."""
        hs = self._hists()
        if len(hs) < 2:
            return None, None
        rnd = random.Random(seed)
        nb = self.nbins
        m = len(hs)
        out = []
        for _ in range(draws):
            hp = [0] * nb
            hn = [0] * nb
            for _k in range(m):
                a, b = hs[rnd.randrange(m)]
                for j in range(nb):
                    if a[j]:
                        hp[j] += a[j]
                    if b[j]:
                        hn[j] += b[j]
            g = ClusterAUC._auc_hist(hp, hn)
            if g is not None:
                out.append(g)
        if len(out) < 20:
            return None, None
        out.sort()
        return out[int(0.025 * len(out))], out[max(0, int(0.975 * len(out)) - 1)]


def mde_auc(n_pos, n_neg, infl=None):
    """Smallest |AUC - 0.5| detectable, two-sided 95%, 80% power.

    The independent-observation SE of AUC under the null is
    sqrt((n1+n0+1)/(12*n1*n0)). Rows are NOT independent -- nine coins settle on
    the same quarter hour and one market contributes ~40 consecutive seconds --
    so the true SE is inflated by a design effect. `infl` is that inflation,
    MEASURED from the cluster bootstrap rather than assumed. Without it the
    number returned is a FLOOR on the MDE, never the MDE.
    """
    if n_pos < 1 or n_neg < 1:
        return None
    se = math.sqrt((n_pos + n_neg + 1.0) / (12.0 * n_pos * n_neg))
    if infl:
        se *= infl
    return (1.96 + 0.84) * se


# ===========================================================================
# the settlement arithmetic, reproduced from pindata.py
# ===========================================================================
def eff_strike(k, d):
    return float(k) - 0.5 * (10.0 ** (-int(d)))


class IndexTape:
    """One index's 1/sec prints, with O(1) window sums and O(1) realised vol."""

    __slots__ = ("base", "a", "ps", "pn", "ss", "sn")

    def __init__(self, base, arr):
        self.base = base
        self.a = arr
        n = len(arr)
        ps = array.array("d", [0.0] * (n + 1))
        pn = array.array("i", [0] * (n + 1))
        for i in range(n):
            v = arr[i]
            ok = v == v
            ps[i + 1] = ps[i] + (v if ok else 0.0)
            pn[i + 1] = pn[i] + (1 if ok else 0)
        self.ps, self.pn = ps, pn
        ss = array.array("d", [0.0] * (n + 1))
        sn = array.array("i", [0] * (n + 1))
        for i in range(1, n):
            a_, b_ = arr[i - 1], arr[i]
            ok = (a_ == a_) and (b_ == b_)
            d = (b_ - a_) if ok else 0.0
            ss[i + 1] = ss[i] + d * d
            sn[i + 1] = sn[i] + (1 if ok else 0)
        self.ss, self.sn = ss, sn

    def val(self, sec):
        i = sec - self.base
        if i < 0 or i >= len(self.a):
            return None
        v = self.a[i]
        return v if v == v else None

    def wsum(self, lo, hi):
        """(coverage-scaled sum, coverage) over [lo, hi] inclusive.

        The sum is taken DIRECTLY over the (at most 60) window values, in the
        same order pindata.py takes it, so the result matches bit for bit. It
        was first written as a difference of two whole-tape prefix sums, which
        is O(1) but loses ~5e-12 of relative precision on BTC (cancelling two
        numbers near 1.4e10 to get one near 4.7e6). That is far too small to
        change any conclusion, but it broke exact reproduction of rows.jsonl,
        and a replay that only ALMOST reproduces its input is a replay whose
        disagreements have to be argued about instead of being zero.
        """
        i, j = lo - self.base, hi - self.base
        if i < 0 or j >= len(self.a) or j < i:
            return None
        got = self.pn[j + 1] - self.pn[i]          # exact integer count
        want = j - i + 1
        if got < want * 0.95:
            return None
        # NOT the builtin sum(): from CPython 3.12 sum() uses Neumaier
        # compensated summation on floats, which is MORE accurate than
        # pindata.py's plain accumulator and therefore disagrees with it by one
        # ULP. Reproducing the dataset exactly is worth more here than being
        # marginally more accurate than it, so the loop is written out.
        tot = 0
        if got == want:
            for v in self.a[i:j + 1]:
                tot += v
        else:
            for v in self.a[i:j + 1]:
                if v == v:
                    tot += v
        return tot * (want / got), got / want

    def rms(self, lo, hi, need=15):
        """rms of the 1 s differences over the pairs ending in [lo, hi]."""
        i, j = lo - self.base, hi - self.base
        if i < 1 or j >= len(self.a) or j < i:
            return None
        k = self.sn[j + 1] - self.sn[i]
        if k < need:
            return None
        return math.sqrt((self.ss[j + 1] - self.ss[i]) / k)


def state(tape, close_s, sec, K):
    """Everything the model knows at `sec`, or None if it cannot be formed."""
    lo, hi = close_s - N_AVG, min(sec, close_s - 1)
    if hi < lo:
        return None
    w = tape.wsum(lo, hi)
    if w is None:
        return None
    locked, cov = w
    want = hi - lo + 1
    r = N_AVG - want
    if r < 1:
        return None
    spot = tape.val(sec)
    if spot is None:
        return None
    sg = tape.rms(sec - 300, sec)
    mu = (locked + r * spot) / N_AVG
    req = (60.0 / r) * (K - mu)
    sd = (sg * math.sqrt(var_factor(int(r), [1.0]))) if sg is not None else None
    return {"r": r, "cov": cov, "spot": spot, "mu": mu, "req": req,
            "sig": sg, "sd": sd}


def p_lose(st, K, our_yes):
    """The model's probability that OUR side loses, at this instant."""
    if st is None or st["sd"] is None:
        return None
    if st["sd"] <= 0:
        below = st["mu"] < K
        return 1.0 if ((our_yes and below) or ((not our_yes) and not below)) \
            else 0.0
    z = (K - st["mu"]) / st["sd"]
    return ND.cdf(z) if our_yes else 1.0 - ND.cdf(z)


def our_mid(row, our_yes):
    """The market's mid price for OUR side, from a rows.jsonl row.

    rows.jsonl's `price` is the ask on the MODEL-FAVOURED side and `spread` is
    that side's ask minus its bid. The favoured side SWITCHES as the index
    moves, and inverting unconditionally is exactly the bug that flattered the
    first hedge study (IDEAS_LOG #31). So:
        favoured side is OURS   -> our ask = price,             bid = price-spread
        favoured side is THEIRS -> our ask = 1 - price + spread, bid = 1 - price
    """
    px = float(row["price"])
    sp = float(row.get("spread") or 0.0)
    if bool(row["side_yes"]) == bool(our_yes):
        return px - sp / 2.0
    return 1.0 - px + sp / 2.0


# ===========================================================================
# the per-entry replay
# ===========================================================================
def walk(tape, close_s, K, our_yes, entry_sec, books, kmax=200):
    """Yield (k, tau, feature dict) for every second from entry to close-1.

    `books` maps sec -> rows.jsonl row for this market, so the market-implied
    columns exist only at seconds where the order book was actually recorded.
    That gap is reported, never filled in.
    """
    ent = state(tape, close_s, entry_sec, K)
    if ent is None or ent["sig"] is None:
        return
    sig0 = ent["sig"]
    p0 = p_lose(ent, K, our_yes)
    sgn0 = 1.0 if our_yes else -1.0
    cush0 = sgn0 * (ent["mu"] - K)
    csd0 = (cush0 / ent["sd"]) if (ent["sd"] and ent["sd"] > 0) else None
    hist = {}
    for sec in range(entry_sec, close_s):
        k = sec - entry_sec
        if k > kmax:
            break
        st = state(tape, close_s, sec, K)
        if st is None:
            continue
        tau = close_s - sec
        lvl = abs(st["spot"]) or 1.0
        sgn = 1.0 if our_yes else -1.0
        cush = sgn * (st["mu"] - K)                     # > 0 = we are winning
        cush_bp = 1e4 * cush / lvl
        cush_sd = (cush / st["sd"]) if (st["sd"] and st["sd"] > 0) else None
        reqmv = -sgn * st["req"]                        # > 0 = must move vs us
        reqmv_bp = 1e4 * reqmv / lvl
        spot_bp = 1e4 * sgn * (st["spot"] - K) / lvl
        pm = p_lose(st, K, our_yes)
        rv = tape.rms(entry_sec, sec, need=3) if k >= 3 else None
        rvr = (rv / sig0) if (rv is not None and sig0 > 0) else None
        hist[k] = reqmv_bp
        d3 = (reqmv_bp - hist[k - 3]) if (k - 3) in hist else None
        row = books.get(sec)
        pmkt = None
        if row is not None:
            mid = our_mid(row, our_yes)
            if 0.0 < mid < 1.0:
                pmkt = 1.0 - mid
        yield k, tau, {
            # p_gain and sd_loss are the ONLY two columns that are zero for
            # every path at k = 0. Their AUC at k = 0 is therefore exactly
            # 0.500 by construction, and that is deliberate: it is a null
            # planted inside the real table. Every other column starts high
            # simply because the model already knew something at entry, and a
            # rise in those cannot be told apart from the answer arriving.
            # A rise in THESE two is post-entry information and nothing else.
            "p_gain": (pm - p0) if (pm is not None and p0 is not None)
            else None,
            "sd_loss": (csd0 - cush_sd)
            if (csd0 is not None and cush_sd is not None) else None,
            "p_model": pm, "p_mkt": pmkt,
            "mkt_lead": (pmkt - pm) if (pm is not None and pmkt is not None)
            else None,
            "diverge": (pm - pmkt) if (pm is not None and pmkt is not None)
            else None,
            "rv_ratio": rvr,
            "neg_cush_sd": (-cush_sd) if cush_sd is not None else None,
            "neg_cush_bp": -cush_bp,
            "neg_reqmv_bp": -reqmv_bp,
            "neg_d_reqmv": (-d3) if d3 is not None else None,
            "neg_spot_bp": -spot_bp,
            "_cush": cush, "_cush_bp": cush_bp, "_spot_bp": spot_bp,
            "_mu": st["mu"], "_spot": st["spot"], "_sd": st["sd"],
            "_r": st["r"], "_sig": st["sig"], "_pmkt": pmkt}


# ===========================================================================
# table builders -- shared by main() and the self-test
# ===========================================================================
def accumulate(paths, kmax, nbins=128):
    """paths = iterable of (close_id, lose, [(k, tau, feats), ...])."""
    byk = {f: defaultdict(lambda: ClusterAUC(nbins)) for f in FEATS}
    bytau = {f: defaultdict(lambda: ClusterAUC(nbins)) for f in FEATS}
    alive_k = defaultdict(lambda: [0, 0])
    alive_t = defaultdict(lambda: [0, 0])
    for close, lose, cells in paths:
        li = 1 if lose else 0
        for k, tau, f in cells:
            if k > kmax:
                continue
            alive_k[k][li] += 1
            alive_t[tau][li] += 1
            for name in FEATS:
                v = f.get(name)
                if v is None:
                    continue
                byk[name][k].add(v, lose, close)
                bytau[name][tau].add(v, lose, close)
    return byk, bytau, alive_k, alive_t


def table(acc, alive, keys, label, floor=MIN_CLUSTERS):
    """Print one separation table. Returns {(feat, key): auc}."""
    out = {}
    hdr = f"  {label:>6}{'n':>9}{'losers':>8}{'closes':>7}"
    for f in FEATS:
        hdr += f"{SHORT[f]:>9}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for kk in keys:
        if kk not in alive:
            continue
        w, l = alive[kk][0], alive[kk][1]
        if l == 0 or w == 0:
            continue
        nc = acc["p_model"][kk].nclust() if kk in acc["p_model"] else 0
        line = f"  {kk:>6}{w + l:>9,}{l:>8,}{nc:>7}"
        for f in FEATS:
            a = acc[f].get(kk)
            g = a.point() if (a is not None and a.npos() and
                              a.n() - a.npos()) else None
            out[(f, kk)] = g
            if g is None:
                line += f"{'.':>9}"
            elif nc < floor:
                line += f"{g:>8.3f}!"
            else:
                line += f"{g:>9.3f}"
        print(line)
    return out


# ===========================================================================
# self-test
# ===========================================================================
def _mk_path(rng, n_k, planted_at, lose, close):
    """One synthetic path. If planted_at is not None, the DANGER features only
    become informative from that second onward."""
    cells = []
    for k in range(n_k + 1):
        shift = 0.0
        if planted_at is not None and k >= planted_at:
            shift = 3.0 if lose else -3.0
        # each feature gets its OWN draw, so the null world's cells are
        # genuinely independent and "how many cells fired" is a real
        # false-positive count rather than one event counted ten times.
        f = {name: rng.gauss(0, 1) + shift for name in FEATS}
        cells.append((k, n_k + 5 - k, f))
    return (close, lose, cells)


def selftest():
    print("SELF-TEST -- pinexit")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # --- AUC itself ------------------------------------------------------
    ck(abs(auc([2, 3, 4], [0, 1]) - 1.0) < 1e-12,
       "perfectly separated groups give AUC 1.000")
    ck(abs(auc([0, 1], [2, 3, 4]) - 0.0) < 1e-12,
       "separated the WRONG way gives 0.000, so a sign error shows up as a "
       "number below 0.5 instead of being silently absorbed")
    ck(abs(auc([1, 1, 1], [1, 1, 1]) - 0.5) < 1e-12,
       "an all-ties column gives exactly 0.500, not 1.000")
    ck(abs(auc([1, 2, 3, 4], [1, 2, 3, 4]) - 0.5) < 1e-12,
       "identical distributions give 0.500")

    c = ClusterAUC(nbins=64)
    rng = random.Random(5)
    for i in range(4000):
        y = i % 2
        c.add(rng.gauss(y * 0.8, 1.0), y, i % 40)
    tp = [0] * 64
    tn = [0] * 64
    for hpos, hneg in c._hists():
        for j in range(64):
            tp[j] += hpos[j]
            tn[j] += hneg[j]
    ck(abs(ClusterAUC._auc_hist(tp, tn) - c.point()) < 0.005,
       f"the binned AUC the bootstrap uses agrees with the exact one "
       f"({ClusterAUC._auc_hist(tp, tn):.4f} vs {c.point():.4f})")

    # --- the settlement arithmetic ---------------------------------------
    flat = IndexTape(0, array.array("d", [100.0] * 1000))
    st = state(flat, 900, 890, 100.0)
    ck(st is not None and st["r"] == 9,
       f"at tau=10 there are 9 prints still to come "
       f"({st['r'] if st else None}) -- the settlement window is "
       f"[close-60, close-1] and the print AT this second is already in it. "
       f"pindata.py's own self-test asserts the same 9.")
    ck(st and abs(st["mu"] - 100.0) < 1e-12,
       "a dead flat index projects a settlement equal to itself")
    ck(st and abs(st["req"]) < 1e-9,
       "and with the strike AT that level the required move is zero")
    st2 = state(flat, 900, 890, 100.6)
    ck(st2 and abs(st2["req"] - 4.0) < 1e-9,
       f"a strike 0.6 above needs the 9 remaining prints to average 4.0 "
       f"higher, because 9/60 of 4.0 is exactly 0.6 ({st2['req']:.4f})")
    _fr = flat.rms(500, 800)
    ck(_fr is not None and abs(_fr) < 1e-12,
       f"a flat index has zero realised volatility ({_fr})")
    saw = IndexTape(0, array.array("d",
                                   [100.0 + (i % 2) * 0.2 for i in range(1000)]))
    ck(abs((saw.rms(500, 800) or 0) - 0.2) < 1e-9,
       "a +/-0.2 sawtooth has realised volatility exactly 0.2")

    # --- p_lose orientation, which decides every table --------------------
    s = state(flat, 900, 890, 100.0)
    s["sd"] = 1.0
    s["mu"] = 101.0
    ck(abs(p_lose(s, 100.0, True) - ND.cdf(-1.0)) < 1e-12,
       "holding YES with mu one sd ABOVE the strike, p(lose) is 15.9%")
    ck(abs(p_lose(s, 100.0, False) - (1 - ND.cdf(-1.0))) < 1e-12,
       "holding NO in the same state, p(lose) is 84.1% -- the two sides must "
       "sum to exactly 1.000 or the orientation is wrong")

    # --- market mid inversion (the IDEAS_LOG #31 bug) --------------------
    still = {"price": 0.95, "spread": 0.01, "side_yes": True}
    sw = {"price": 0.30, "spread": 0.01, "side_yes": False}
    ck(abs(our_mid(still, True) - 0.945) < 1e-12,
       f"while the model still favours our side, our mid is ask - spread/2 "
       f"({our_mid(still, True):.4f})")
    ck(abs(our_mid(sw, True) - 0.705) < 1e-12,
       f"once the model has SWITCHED, the stored ask belongs to the OTHER "
       f"side and our mid is 1 - price + spread/2 ({our_mid(sw, True):.4f})")
    ck(abs(our_mid(sw, True) + our_mid(sw, False) - 1.0) < 1e-12,
       "the two sides' mids always sum to exactly 1.000")

    # --- PLANTED world: separation must APPEAR at a known second ---------
    rng = random.Random(11)
    KM = 12
    paths = [_mk_path(rng, KM, 6, i % 2 == 0, i % 40) for i in range(600)]
    byk, _bt, _ak, _at = accumulate(paths, KM, nbins=64)
    a5 = byk["p_model"][5].point()
    a8 = byk["p_model"][8].point()
    ck(abs(a5 - 0.5) < 0.08,
       f"PLANTED: before the plant (k=5) the estimator finds nothing "
       f"({a5:.3f})")
    ck(a8 > 0.95,
       f"PLANTED: from the plant onward (k=8) it finds it ({a8:.3f})")
    lo, hi = byk["p_model"][8].ci(draws=120, seed=3)
    ck(lo is not None and lo > 0.5,
       f"PLANTED: and the close-clustered CI excludes 0.500 "
       f"([{lo:.3f}, {hi:.3f}])")
    flo, fwin = first_fire_stats(paths, "p_model", 2.5)
    ck(flo is not None and flo == 6,
       f"PLANTED: at a threshold only the plant can reach, the first-fire "
       f"detector names the planted second exactly ({flo})")
    _pl, _pw = first_fire_rate(paths, "p_model", 2.5)
    ck(_pl > 0.95 and _pw < 0.10,
       f"PLANTED: it fires on {100*_pl:.1f}% of losers and only "
       f"{100*_pw:.1f}% of winners -- a warning, not a coin flip")

    # --- NULL world: it must find NOTHING --------------------------------
    rng2 = random.Random(23)
    npaths = [_mk_path(rng2, KM, None, rng2.random() < 0.5, i % 40)
              for i in range(600)]
    nbyk, _b2, _a2, _t2 = accumulate(npaths, KM, nbins=64)
    worst = 0.0
    bad = 0
    cells = 0
    for k in range(KM + 1):
        for f in FEATS:
            g = nbyk[f][k].point()
            if g is None:
                continue
            cells += 1
            worst = max(worst, abs(g - 0.5))
            lo2, hi2 = nbyk[f][k].ci(draws=160, seed=7 + k * 31 +
                                     FEATS.index(f))
            if lo2 is not None and (lo2 > 0.5 or hi2 < 0.5):
                bad += 1
    ck(worst < 0.12,
       f"NULL: no second on any signal separates by more than 0.12 "
       f"(worst |AUC-0.5| = {worst:.3f})")
    ck(bad <= max(2, int(0.12 * cells)),
       f"NULL: the clustered CI excludes 0.500 in only {bad} of {cells} "
       f"independent cells ({100 * bad / cells:.1f}%), at or below the rate "
       f"chance alone produces")

    # --- is the CI itself calibrated? -----------------------------------
    excl = 0
    T = 60
    for t in range(T):
        rr = random.Random(9000 + t)
        cc = ClusterAUC(nbins=64)
        for i in range(600):
            cc.add(rr.gauss(0, 1), rr.random() < 0.5, i % 40)
        l3, h3 = cc.ci(draws=120, seed=t)
        if l3 is not None and (l3 > 0.5 or h3 < 0.5):
            excl += 1
    ck(excl <= max(3, int(0.15 * T)),
       f"CALIBRATION: on {T} independent null worlds the nominal 95% "
       f"close-clustered CI excluded 0.500 {excl} times "
       f"({100 * excl / T:.1f}%, nominal 5%) -- the interval is not too "
       f"narrow, so a real interval that excludes 0.500 means something")
    nflo, nfwin = first_fire_stats(npaths, "p_model", 2.5)
    _nl, _nw = first_fire_rate(npaths, "p_model", 2.5)
    ck(abs(_nl - _nw) < 0.10,
       f"NULL: the first-fire detector fires on losers and winners at the "
       f"same rate ({100*_nl:.1f}% vs {100*_nw:.1f}%) -- it invents no "
       f"warning where there is nothing to warn about")

    # --- MDE arithmetic ---------------------------------------------------
    m1 = mde_auc(100, 1000)
    m2 = mde_auc(400, 4000)
    ck(m2 < m1, f"the MDE floor shrinks as the sample grows "
                f"({m1:.3f} -> {m2:.3f})")
    ck(abs(mde_auc(100, 1000, infl=2.0) - 2 * m1) < 1e-12,
       "and doubles when the measured design effect doubles it")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


def first_fire_rate(paths, feat, thresh):
    """Share of LOSERS and share of WINNERS on which the rule ever fires."""
    nl = nw = fl = fw = 0
    for close, lose, cells in paths:
        got = any(f.get(feat) is not None and f[feat] >= thresh
                  for _k, _t, f in cells)
        if lose:
            nl += 1
            fl += 1 if got else 0
        else:
            nw += 1
            fw += 1 if got else 0
    return (fl / nl if nl else 0.0), (fw / nw if nw else 0.0)


def first_fire_stats(paths, feat, thresh):
    """Median k of first fire among LOSERS, and among WINNERS. Used by the
    self-test to prove the firing logic names the planted second."""
    lk, wk = [], []
    for close, lose, cells in paths:
        got = None
        for k, tau, f in cells:
            v = f.get(feat)
            if v is not None and v >= thresh:
                got = k
                break
        if got is None:
            continue
        (lk if lose else wk).append(got)
    lk.sort()
    wk.sort()
    return (lk[len(lk) // 2] if lk else None), (wk[len(wk) // 2] if wk else None)


# ===========================================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a, _rest = ap.parse_known_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    import pinexit_run                                          # noqa: E402
    pinexit_run.main()
