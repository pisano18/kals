#!/usr/bin/env python3
# VERSION: 2026-09-10-px1
"""pincross.py -- IS TROUBLE VISIBLE IN THE OTHER TEN COINS?

THE OPERATOR, 2026-09-10:

    "We can control our own losses because we already do. We don't try to buy
     into every bet, we look at the conditions and see if it's favorable. We
     need better conditions, and a faster understanding of how 'favorable'
     changes."

WHY EVERY EARLIER ATTEMPT FAILED, AND WHY THIS ONE IS DIFFERENT

Six investigations tried to cut the loss rate and every one of them was a
FILTER BOLTED ONTO THE SAME NUMBER: the traded coin's own 300-second sigma.
Once that number is held fixed, its relatives (s30, s120, transient, drift,
jump) add nothing -- they are the same measurement at different lags.

This file asks a question none of them asked: at the second we buy SOL, are
the OTHER TEN COINS calm or rough? That is genuinely new information. It is
not a lag of the traded coin's own volatility, and it is available one second
after it happens.

The mechanism being tested: all five live losses landed in two hours out of
thirty. Volatility arrives market-wide -- a macro print, a liquidation
cascade, a session gap -- and hits eleven coins at once. If that is true, the
other ten coins are an EARLY, INDEPENDENT read on whether this close is
dangerous, and the coin we are about to trade is the last place to look.

THE INDEX, and every part of it is backward-looking:

    z_c(t)   = RMS 1s log-return over the last 30s
               ------------------------------------   (a coin's roughness
               RMS 1s log-return over the last 3600s    against its own
                                                        recent normal)

    X_c(t)   = mean of z_o(t) over every coin o != c   <- THE TRADED COIN IS
    N_c(t)   = count of o != c with z_o(t) > 2            EXCLUDED, BY
    dX_c(t)  = X_c(t) - X_c(t - 60)                       CONSTRUCTION

Dividing by the coin's own trailing hour is what makes BTC and DOGE
comparable without a fitted constant, and it is what makes the index sit near
1 in calm conditions whatever the coins are doing in absolute terms.

CLUSTERING. Twelve series settle on the same second at rho ~ 0.8. Market-level
counts here are DESCRIPTION ONLY; every significance claim comes from a
permutation test that shuffles whole CLOSES, which is the honest unit.

THE CONTROL IS NOT OPTIONAL. A shuffled index must show no gradient. An
estimator never shown incapable of finding a fake effect cannot be trusted
when it finds a real one.
"""
import argparse
import array
import glob
import gzip
import json
import math
import os
import random
import sys
import time
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor                                # noqa: E402
from statistics import NormalDist                            # noqa: E402

ND = NormalDist()
DATA = r"C:\kals\kalshi_data"
ROWS = r"C:\kals-repo\results\pindata_fixed\rows.jsonl"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}

# THE LIVE RULE, as pinrun enforces it today. Anything that fails this is not
# a moment we would have traded, and measuring it answers a question nobody
# asked.
TAU_LO, TAU_HI = 3, 30
PIN = 0.98
PRICE_CEILING = 0.980
EDGE_FLOOR = EV_FLOOR = 0.003
MEASURED_FLIP = 0.0090
SIZE = 20.0
MIN_FILL_FRAC = 0.50

FAST, SLOW = 30, 3600      # the two horizons in the roughness ratio
ROUGH = 2.0                # z above this counts a coin as "moving"


# --------------------------------------------------------------- the gate
def billed_fee(price, count):
    raw = 0.07 * float(count) * price * (1.0 - price)
    return math.ceil(raw * 10000.0 - 1e-9) / 10000.0


def row_fair(rw):
    """P(YES settles in) reconstructed from the row, exactly as pinrun does.

    pinrun: fair = Phi((mu - K) / (sigma * sqrt(var_factor(r)))).
    The row stores req = (60/r)*(K - mu), so (mu - K) = -req * r / 60.
    """
    r = int(rw["r"])
    sg = rw.get("sig")
    if not sg or r < 1:
        return None
    sd = float(sg) * math.sqrt(var_factor(r, [1.0]))
    if sd <= 0:
        return None
    return ND.cdf((-float(rw["req"]) * r / 60.0) / sd)


def passes_live_gate(rw):
    """True if pinrun would have bought this moment."""
    if not (TAU_LO <= int(rw["tau"]) <= TAU_HI):
        return False
    f = row_fair(rw)
    if f is None:
        return False
    want_yes = f >= PIN
    want_no = f <= 1.0 - PIN
    if not (want_yes or want_no):
        return False
    # the row priced the side the SIGN rule favours; the confidence gate must
    # agree or we would be pricing the wrong side of the book
    if want_yes != bool(rw["side_yes"]):
        return False
    p = float(rw["price"])
    if not (0.5 < p <= PRICE_CEILING):
        return False
    if float(rw["size"]) < max(1.0, MIN_FILL_FRAC * SIZE):
        return False
    gross = (f - p) if want_yes else ((1.0 - f) - p)
    if gross - billed_fee(p, SIZE) / SIZE < EDGE_FLOOR:
        return False
    ev = (1.0 - MEASURED_FLIP) * (1.0 - p) - MEASURED_FLIP * p \
        - billed_fee(p, 1)
    return ev >= EV_FLOOR


# --------------------------------------------------------------- the index
def prefix_sq(arr):
    """Cumulative sum of squared 1s LOG returns, plus a count of live steps.

    Gaps are SKIPPED, never carried forward. A carried-forward price
    manufactures a zero return, which would make a dead feed look like the
    calmest coin on the board -- the exact direction that would fake this
    whole result into existence.
    """
    n = len(arr)
    S = array.array("d", [0.0] * (n + 1))
    C = array.array("l", [0] * (n + 1))
    prev = None
    for i in range(n):
        v = arr[i]
        s, c = S[i], C[i]
        if v == v and v > 0:
            if prev is not None and prev > 0:
                d = math.log(v / prev)
                s += d * d
                c += 1
            prev = v
        S[i + 1], C[i + 1] = s, c
    return S, C


def rms(S, C, i, w):
    """RMS log return over the w seconds ending at index i, or None."""
    lo = i - w
    if lo < 0 or i + 1 >= len(S):
        return None
    k = C[i + 1] - C[lo + 1]
    if k < max(5, w // 8):        # a window mostly made of gaps is not a read
        return None
    return math.sqrt(max(0.0, S[i + 1] - S[lo + 1]) / k)


class Cross:
    """z per coin per second, then the leave-one-out cross-market index."""

    def __init__(self, idx):
        self.base = {}
        self.z = {}
        for iid, (base, arr) in idx.items():
            S, C = prefix_sq(arr)
            n = len(arr)
            zz = array.array("d", [float("nan")] * n)
            for i in range(n):
                f = rms(S, C, i, FAST)
                if f is None:
                    continue
                s = rms(S, C, i, SLOW)
                if s is None or s <= 0:
                    continue
                zz[i] = f / s
            self.base[iid] = base
            self.z[iid] = zz

    def zof(self, iid, sec):
        b = self.base.get(iid)
        if b is None:
            return None
        i = sec - b
        zz = self.z[iid]
        if i < 0 or i >= len(zz):
            return None
        v = zz[i]
        return v if v == v else None

    def cross(self, exclude_iid, sec):
        """(mean z, count rough, coins used) over every coin BUT this one."""
        tot, k, nrough = 0.0, 0, 0
        for iid in self.z:
            if iid == exclude_iid:
                continue
            v = self.zof(iid, sec)
            if v is None:
                continue
            tot += v
            k += 1
            if v > ROUGH:
                nrough += 1
        if k < 4:
            return None
        return tot / k, nrough, k


# --------------------------------------------------------------- statistics
def cp_interval(k, n, conf=0.95):
    """Clopper-Pearson exact interval, by bisection on the Beta quantiles."""
    if n == 0:
        return (float("nan"), float("nan"))
    a = (1.0 - conf) / 2.0

    def binom_cdf(p, kk, nn):
        # P(X <= kk) for X ~ Bin(nn, p)
        tot = 0.0
        lp = math.log(p) if p > 0 else float("-inf")
        lq = math.log1p(-p) if p < 1 else float("-inf")
        for i in range(0, kk + 1):
            lc = (math.lgamma(nn + 1) - math.lgamma(i + 1)
                  - math.lgamma(nn - i + 1))
            t = lc + (i * lp if i else 0.0) + ((nn - i) * lq if nn - i else 0.0)
            tot += math.exp(t) if t > -700 else 0.0
        return tot

    def solve(target, kk, hi_side):
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = (lo + hi) / 2.0
            v = binom_cdf(mid, kk, n)
            if (v > target) == hi_side:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    low = 0.0 if k == 0 else solve(1.0 - a, k - 1, True)
    high = 1.0 if k == n else solve(a, k, True)
    return low, high


def perm_test(closes, key, hi_frac=0.25, draws=4000, seed=7):
    """Do high-`key` CLOSES flip more? Permutation over CLOSES, not markets.

    Each close contributes (its index value, its markets, its flips). The
    statistic is the flip rate in the top quartile of closes minus the rest.
    Shuffling the index across closes destroys the link while preserving every
    bit of the clustering, so the null distribution is the honest one.
    """
    vals = [c[key] for c in closes]
    mk = [c["n"] for c in closes]
    fl = [c["flips"] for c in closes]
    n = len(closes)
    if n < 8:
        return None
    cut = max(1, int(round(hi_frac * n)))

    def stat(order):
        rank = sorted(range(n), key=lambda i: -vals[order[i]])
        hi, lo = rank[:cut], rank[cut:]
        ah, nh = sum(fl[i] for i in hi), sum(mk[i] for i in hi)
        al, nl = sum(fl[i] for i in lo), sum(mk[i] for i in lo)
        if not nh or not nl:
            return None
        return ah / nh - al / nl

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


def mde(base_rate, n_hi, n_lo, power=0.80, alpha=0.05):
    """Smallest lift in the high bucket this design could detect."""
    if not n_hi or not n_lo:
        return float("nan")
    za, zb = 1.959964, 0.8416212
    v = base_rate * (1 - base_rate) * (1.0 / n_hi + 1.0 / n_lo)
    return (za + zb) * math.sqrt(v)


# --------------------------------------------------------------- self-test
def selftest():
    print("SELF-TEST -- pincross")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # 1. the ratio sits near 1 for a series whose roughness never changes
    n = 5000
    rng = random.Random(1)
    arr = array.array("d", [0.0] * n)
    p = 100.0
    for i in range(n):
        p *= math.exp(rng.gauss(0, 0.001))
        arr[i] = p
    S, C = prefix_sq(arr)
    z = rms(S, C, 4500, FAST) / rms(S, C, 4500, SLOW)
    ck(0.5 < z < 1.9, f"constant-vol series gives z ~ 1 (got {z:.2f})")

    # 2. and it RISES when the last 30s turn rough -- the whole point
    arr3 = array.array("d", list(arr))
    q = arr3[4470]
    for i in range(4471, 4501):
        q *= math.exp(rng.gauss(0, 0.02))
        arr3[i] = q
    S3, C3 = prefix_sq(arr3)
    z2 = rms(S3, C3, 4500, FAST) / rms(S3, C3, 4500, SLOW)
    ck(z2 > 3.0 * z, f"a rough last 30s lifts z far above calm ({z2:.2f} vs "
                     f"{z:.2f})")

    # 3. gaps must not read as calm
    arr2 = array.array("d", list(arr))
    for i in range(4400, 4500):
        arr2[i] = float("nan")
    S2, C2 = prefix_sq(arr2)
    ck(rms(S2, C2, 4499, FAST) is None,
       "a window that is mostly gap returns None, never 0 -- a dead feed must "
       "not impersonate the calmest coin on the board")

    # 4. THE EXCLUSION. Scaling a coin's own vol must not move ITS OWN index.
    idx = {}
    for j, iid in enumerate("ABCDEFGH"):
        a = array.array("d", [0.0] * 4200)
        pp = 100.0
        for i in range(4200):
            pp *= math.exp(rng.gauss(0, 0.001))
            a[i] = pp
        idx[iid] = (0, a)
    cx = Cross(idx)
    before = cx.cross("A", 4100)[0]
    beforeB = cx.cross("B", 4100)[0]
    a = array.array("d", list(idx["A"][1]))
    qq = a[4070]
    for i in range(4071, 4101):
        qq *= math.exp(rng.gauss(0, 0.05))
        a[i] = qq
    idx["A"] = (0, a)
    cx2 = Cross(idx)
    ck(abs(before - cx2.cross("A", 4100)[0]) < 1e-12,
       "blowing up coin A's own volatility leaves A's OWN cross index EXACTLY "
       "unchanged -- otherwise this is the refuted own-sigma test wearing a "
       "new name")
    ck(abs(cx2.cross("B", 4100)[0] - beforeB) > 1e-9,
       "and it DOES move coin B's index, so the exclusion is not simply "
       "returning a constant")

    # 5. PLANT an effect and demand the test finds it
    rng2 = random.Random(4)
    planted = []
    for _ in range(160):
        x = rng2.random() * 3
        nm = rng2.randint(4, 9)
        pr = 0.002 + (0.09 if x > 2.25 else 0.0)
        planted.append({"x": x, "n": nm,
                        "flips": sum(1 for _ in range(nm)
                                     if rng2.random() < pr)})
    got = perm_test(planted, "x", draws=1500)
    ck(got is not None and got[1] < 0.01,
       f"a planted burst effect IS found (diff {got[0]*100:+.2f}pp, "
       f"p={got[1]:.4f})")

    # 6. and demand it finds NOTHING when nothing is planted.
    #
    # THE FIRST VERSION OF THIS CHECK WAS WRONG AND IT FAILED, CORRECTLY.
    # It built ONE null world and demanded p > 0.05. But a null world's
    # p-value is itself a uniform random variable, so that check fails on 5%
    # of seeds BY DESIGN -- and seed 4 was one of them (p = 0.034). The
    # tempting fix is to try seeds until one passes, which is precisely the
    # sin this project forbids: changing the bar after seeing the result.
    # The property that actually matters is CALIBRATION -- across many null
    # worlds, p must be roughly uniform, so about 5% land under 0.05. That is
    # what is tested now, and it is a strictly stronger claim than the
    # original single draw.
    hits = 0
    worlds = 40
    for w in range(worlds):
        rw = random.Random(1000 + w)
        null = []
        for _ in range(160):
            nm = rw.randint(4, 9)
            null.append({"x": rw.random() * 3, "n": nm,
                         "flips": sum(1 for _ in range(nm)
                                      if rw.random() < 0.02)})
        g = perm_test(null, "x", draws=400, seed=w)
        if g is not None and g[1] < 0.05:
            hits += 1
    ck(hits <= 6,
       f"across {worlds} worlds with NO effect planted, only {hits} came out "
       f"significant at 5% -- a calibrated test, not one that fires on noise "
       f"(expect ~2, allow up to 6)")

    # 7. the gate must actually reject things
    base = {"tau": 10, "r": 9, "sig": 0.02, "req": -0.9, "price": 0.95,
            "size": 50, "side_yes": True}
    ck(passes_live_gate(dict(base)), "a clean confident cheap moment passes")
    ck(not passes_live_gate(dict(base, price=0.985)),
       "the same moment above the 98.0c ceiling is refused")
    ck(not passes_live_gate(dict(base, size=3)),
       "and refused when only 3 contracts are on offer at size 20")
    ck(not passes_live_gate(dict(base, req=-0.0001, sig=0.5)),
       "and refused when the model is not confident")

    # 8. Clopper-Pearson sanity -- a known textbook pair
    lo, hi = cp_interval(0, 100)
    ck(lo == 0.0 and abs(hi - 0.0362) < 0.002,
       f"CP interval for 0/100 is [0, 0.0362] (got [{lo:.4f}, {hi:.4f}])")
    lo, hi = cp_interval(5, 100)
    ck(abs(lo - 0.0164) < 0.002 and abs(hi - 0.1128) < 0.002,
       f"CP interval for 5/100 is [0.0164, 0.1128] (got [{lo:.4f}, "
       f"{hi:.4f}])")

    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


# --------------------------------------------------------------- real data
def load_index_window(lo_sec, hi_sec):
    """Index tape for [lo, hi], straight into preallocated arrays.

    pindata.load_index builds a dict-of-dicts first, which costs ~100 bytes a
    print. Over 116 hours of 11 feeds that is 4.6M entries and roughly half a
    gigabyte for a structure thrown away seconds later. The collector outranks
    every job here, so this loader never builds it.
    """
    lo_h = time.strftime("%Y%m%dT%H", time.gmtime(lo_sec - 3700))
    hi_h = time.strftime("%Y%m%dT%H", time.gmtime(hi_sec + 60))
    files = [p for p in sorted(glob.glob(os.path.join(
        DATA, "cfbenchmarks_value", "2026*.jsonl.gz")))
        if lo_h <= os.path.basename(p)[:11] <= hi_h]
    base = lo_sec - 3700
    n = hi_sec + 60 - base + 1
    out = {}
    kept = dropped = 0
    for fp in files:
        try:
            with gzip.open(fp, "rt") as fh:
                for line in fh:
                    if '"cfbenchmarks_value"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                        dd = json.loads(m["data"])
                        s = int(dd["time"]) // 1000
                        v = float(dd["value"])
                    except Exception:
                        continue
                    i = s - base
                    if i < 0 or i >= n:
                        dropped += 1
                        continue
                    iid = m["index_id"]
                    a = out.get(iid)
                    if a is None:
                        a = out[iid] = array.array("d", [float("nan")] * n)
                    a[i] = v
                    kept += 1
        except (EOFError, zlib.error, OSError):
            pass
    return {k: (base, v) for k, v in out.items()}, len(files), kept, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=ROWS)
    ap.add_argument("--draws", type=int, default=4000)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    print(f"\n  reading {a.rows}")
    raw = []
    lo_sec = hi_sec = None
    nrows = 0
    for line in open(a.rows, encoding="utf-8"):
        try:
            rw = json.loads(line)
        except Exception:
            continue
        nrows += 1
        if not passes_live_gate(rw):
            continue
        raw.append(rw)
        s = int(rw["sec"])
        lo_sec = s if lo_sec is None else min(lo_sec, s)
        hi_sec = s if hi_sec is None else max(hi_sec, s)
    if not raw:
        print("  loaded nothing that passes the live gate")
        return
    print(f"  {nrows:,} rows -> {len(raw):,} pass the live rule")

    # ONE observation per market: the first second the bot could have hit it.
    best = {}
    for rw in raw:
        k = rw["tk"]
        if k not in best or rw["tau"] > best[k]["tau"]:
            best[k] = rw
    mkts = list(best.values())
    closes_n = len(set(m["close"] for m in mkts))
    flips = sum(1 for m in mkts if m["flip"])
    print(f"  {len(mkts):,} markets over {closes_n} closes, "
          f"{flips} flips ({100.0*flips/len(mkts):.2f}%)")
    lo, hi = cp_interval(flips, len(mkts))
    print(f"  flip rate 95% CI (markets, ignores clustering): "
          f"[{100*lo:.2f}%, {100*hi:.2f}%]")

    print(f"\n  loading index tape "
          f"{time.strftime('%m-%d %H:%MZ', time.gmtime(lo_sec))} -> "
          f"{time.strftime('%m-%d %H:%MZ', time.gmtime(hi_sec))} ...")
    t0 = time.time()
    idx, nf, kept, dropped = load_index_window(lo_sec, hi_sec)
    print(f"  {len(idx)} feeds, {nf} files, {kept:,} prints kept, "
          f"{dropped:,} outside window ({time.time()-t0:.0f}s)")
    if len(idx) < 5:
        print("  loaded nothing usable -- fewer than 5 feeds")
        return

    print("  building the roughness index ...")
    t0 = time.time()
    cx = Cross(idx)
    print(f"  done ({time.time()-t0:.0f}s)")

    # attach the cross-market index to every market
    keep = []
    nomatch = 0
    for m in mkts:
        iid = SERIES_TO_INDEX.get(m["sr"])
        c = cx.cross(iid, int(m["sec"]))
        c60 = cx.cross(iid, int(m["sec"]) - 60)
        own = cx.zof(iid, int(m["sec"]))
        if c is None or own is None:
            nomatch += 1
            continue
        m["X"] = c[0]
        m["N"] = c[1]
        m["own"] = own
        m["dX"] = (c[0] - c60[0]) if c60 else 0.0
        keep.append(m)
    print(f"  {len(keep):,} markets carry a cross index "
          f"({nomatch} could not be scored)")
    if len(keep) < 50:
        print("  loaded nothing -- too few scored markets")
        return

    _report(keep, a.draws)


def _bucket_table(mkts, key, edges, label):
    print(f"\n  {label}")
    print(f"  {'band':>16}{'markets':>9}{'closes':>8}{'flips':>7}"
          f"{'rate':>8}{'95% CI (markets)':>22}")
    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        sel = [m for m in mkts if a <= m[key] < b]
        if not sel:
            continue
        k = sum(1 for m in sel if m["flip"])
        cl = len(set(m["close"] for m in sel))
        lo, hi = cp_interval(k, len(sel))
        print(f"  {a:6.2f}-{b:<9.2f}{len(sel):>9}{cl:>8}{k:>7}"
              f"{100.0*k/len(sel):>7.2f}%"
              f"{'[' + f'{100*lo:.2f}, {100*hi:.2f}' + ']':>22}")


def _report(mkts, draws):
    # close-level aggregation -- the honest unit
    byclose = defaultdict(lambda: {"n": 0, "flips": 0, "X": 0.0, "N": 0.0,
                                   "dX": 0.0, "own": 0.0})
    for m in mkts:
        c = byclose[m["close"]]
        c["n"] += 1
        c["flips"] += 1 if m["flip"] else 0
        c["X"] += m["X"]
        c["N"] += m["N"]
        c["dX"] += m["dX"]
        c["own"] += m["own"]
    closes = []
    for cs, c in byclose.items():
        closes.append({"close": cs, "n": c["n"], "flips": c["flips"],
                       "X": c["X"] / c["n"], "N": c["N"] / c["n"],
                       "dX": c["dX"] / c["n"], "own": c["own"] / c["n"]})
    closes.sort(key=lambda c: c["close"])
    nmk = sum(c["n"] for c in closes)
    nfl = sum(c["flips"] for c in closes)
    base = nfl / nmk

    print(f"\n  {'='*66}")
    print(f"  POPULATION: {nmk:,} markets over {len(closes)} closes, "
          f"{nfl} flips, base rate {100*base:.2f}%")
    cut = max(1, int(round(0.25 * len(closes))))
    n_hi = sum(c["n"] for c in sorted(closes, key=lambda c: -c["X"])[:cut])
    n_lo = nmk - n_hi
    print(f"  MDE, top quartile of closes vs the rest ({n_hi} vs {n_lo} "
          f"markets, 80% power): {100*mde(base, n_hi, n_lo):+.2f}pp")
    print(f"  -- stated BEFORE the estimate. A null smaller than this is NO "
          f"POWER, not no effect.")
    print(f"  {'='*66}")

    _bucket_table(mkts, "X", [0.0, 0.8, 1.0, 1.2, 1.5, 99.0],
                  "FLIP RATE BY CROSS-MARKET ROUGHNESS X (traded coin "
                  "EXCLUDED)")
    _bucket_table(mkts, "own", [0.0, 0.8, 1.0, 1.2, 1.5, 99.0],
                  "and the SAME table on the traded coin's OWN roughness "
                  "(the refuted measurement, for contrast)")
    _bucket_table(mkts, "N", [0, 1, 2, 3, 5, 99],
                  "FLIP RATE BY HOW MANY OTHER COINS ARE MOVING (z > 2)")

    print(f"\n  PERMUTATION TESTS -- shuffled over {len(closes)} CLOSES, "
          f"{draws} draws")
    print(f"  {'statistic':<34}{'top-quartile lift':>20}{'p':>10}")
    for key, lbl in (("X", "cross-market roughness X"),
                     ("N", "coins moving (N)"),
                     ("dX", "change in X over 60s"),
                     ("own", "own roughness (refuted control)")):
        got = perm_test(closes, key, draws=draws)
        if got is None:
            continue
        print(f"  {lbl:<34}{100*got[0]:>19.2f}pp{got[1]:>10.4f}")

    # THE CONTROL. Shuffle the index across closes and demand nothing.
    rng = random.Random(99)
    sh = [dict(c) for c in closes]
    vals = [c["X"] for c in closes]
    rng.shuffle(vals)
    for c, v in zip(sh, vals):
        c["X"] = v
    got = perm_test(sh, "X", draws=draws)
    print(f"\n  CONTROL (X shuffled across closes, must show nothing): "
          f"lift {100*got[0]:+.2f}pp, p={got[1]:.4f}")

    print("\n  WHAT WOULD HAVE TO BE TRUE FOR THIS TO BE AN ARTEFACT:")
    print("   * if the index were a lag of the traded coin's own vol, the OWN "
          "row would move with the X row -- compare them above")
    print("   * if it were reading time-of-day, high-X closes would bunch in "
          "one session; the close list is printed below")
    print("   * if it were reading a dead feed as calm, gap handling would be "
          "wrong -- prefix_sq skips gaps and rms() refuses thin windows")

    top = sorted(closes, key=lambda c: -c["X"])[:cut]
    hrs = defaultdict(int)
    for c in top:
        hrs[time.gmtime(c["close"]).tm_hour] += 1
    print(f"\n  top-quartile closes by UTC hour: "
          f"{dict(sorted(hrs.items()))}")


if __name__ == "__main__":
    main()
