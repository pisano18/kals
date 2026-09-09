#!/usr/bin/env python3
# VERSION: 2026-09-08-ps1
"""pinsignal.py -- AT THE MOMENT WE DECIDED TO BUY, was anything different
about the trades that go on to LOSE?

THE OPERATOR'S QUESTION, VERBATIM: "Shouldn't you also check if back when you
originally decided it was a good buy if anything there signaled the potential
loss that winning trades don't?"

WHY THIS FILE EXISTS AND WHAT IT REFUSES TO DO

On 2026-09-09 00:45Z we lost $52.60 on KXNEAR15M in three buys, the first of
them at 96.2c where the scale-in rule cannot be blamed.  The obvious story --
"the index was flat for eight seconds, so trailing sigma was tiny, so the model
was falsely confident" -- is a HYPOTHESIS.  This file tests it against every
trade we could have taken, and against five rival stories, and reports the ones
that do not separate anything just as loudly as the ones that do.

ONLY FEATURES KNOWABLE AT ENTRY COUNT.  Every column here is computed from
index prints at or before the entry second, or from the resting book at that
instant.  A feature computed from later data would "predict" perfectly and be
worth less than nothing.  The outcome enters exactly once, at scoring time.

THE POPULATION.  rows.jsonl (pindata.py) is one row per GENUINELY AVAILABLE
trade -- a second where somebody really was offering the model-favoured side at
a real price in real size.  The LIVE window (tau 3-30) contains ZERO flips, so
nothing can be learned in it: every study of losers must use the WIDE window
(tau 3-200), where 1,506 flips exist over 132 distinct closes.  Two populations
are reported side by side and never pooled:

    P1  WIDE, every available second, tau 3-200
    P2  WIDE and the LIVE RULE's own gates (price <= 98.8c, model p_flip <= 2%,
        EV >= 0.3c) -- the population the real loss was drawn from

INFERENCE.  n is CLOSES, never trades.  Hundreds of rows share one settlement.
All twelve crypto series settle on the same quarter hour at rho ~ 0.8, so a
close is the cluster, not a market and certainly not a row.  Confidence
intervals come from a bootstrap that RESAMPLES CLOSES, carrying every market
and every row of a close together.

THE MDE IS PRINTED BEFORE THE ESTIMATE for every feature, because "no effect"
and "no power" are different results.

THE SHUFFLED-LABEL CONTROL.  For each feature the same statistic is recomputed
on permuted outcomes: the vector of per-market settled results is shuffled
across markets while every row, every side_yes and every feature value stays
exactly where it was.  If the feature separates losers on shuffled outcomes it
separates nothing.  Caveat stated once: the market-level shuffle breaks the
cross-coin correlation WITHIN a close, so its null spread is if anything too
narrow -- which is why the close-cluster bootstrap, not the shuffle, is the
primary inference and a claim needs BOTH.

WHAT THIS FILE CANNOT SEE.  pindata.Book.snapshot() reads `yes_dollars` /
`no_dollars` but the tape carries `yes_dollars_fp` / `no_dollars_fp` (confirmed
against the raw snapshot channel), so snapshot seeding never worked and the
replayed books are DELTA-ONLY.  Every book-derived feature here -- price,
spread, size, dep_y, dep_n, age_ms -- inherits that.  Every INDEX-derived
feature -- flatness, the sigma regime, jumps, range, the required move -- is
computed here directly from the raw cfbenchmarks tape and is untouched by it.
The leading hypotheses all live on the clean side.
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
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor                                  # noqa: E402

ND = NormalDist()
DATA = r"C:\kals\kalshi_data"
ROWS = r"C:\kals-repo\results\pindata\rows.jsonl"
OUTDIR = r"C:\kals-repo\results"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}

# The live rule, as deployed (pinrun.py).
CEILING = 0.988
EV_FLOOR = 0.003
PIN_P = 0.02
MEASURED_FLIP = 0.0090

# THE LIVE LOSS.  KXNEAR15M-26SEP082045-45, close 1788914700.
LOSS_CLOSE = 1788914700
LOSS_INDEX = "NEARUSD_RTI"
LOSS_K_EFF = 2.34915
LOSS_BUYS = [(22, 0.962, 20), (21, 0.956, 20), (17, 0.730, 19)]


def billed_fee(p, n=1.0):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def model_pflip(req, r, sig):
    """Model probability the FAVOURED side loses.  Backward-looking only."""
    if sig is None or r is None or r < 1:
        return None
    sd = sig * math.sqrt(var_factor(int(r), [1.0])) * (60.0 / r)
    if sd <= 0:
        return 0.0 if req <= 0 else 1.0
    z = req / sd
    return (1 - ND.cdf(z)) if req > 0 else ND.cdf(z)


def model_z(req, r, sig):
    """|required move| in units of the model's own predicted sd."""
    if sig is None or r is None or r < 1 or sig <= 0:
        return None
    sd = sig * math.sqrt(var_factor(int(r), [1.0])) * (60.0 / r)
    return abs(req) / sd if sd > 0 else None


def entry_ev(price, flip=MEASURED_FLIP):
    return (1 - flip) * (1 - price) - flip * price - billed_fee(price)


# ---------------------------------------------------------------------------
# INDEX TAPE -> prefix sums, so every window statistic is O(1) or O(window)
# ---------------------------------------------------------------------------
class Idx:
    """One index's second-by-second tape plus backward-looking prefix sums.

    Cd[i] = number of VALID consecutive pairs (i-1,i) at or before i
    Ce[i] = number of those pairs that are EXACTLY equal
    Cs[i] = sum of squared one-second differences over those pairs
    """

    __slots__ = ("base", "v", "Cd", "Ce", "Cs", "n")

    def __init__(self, base, v):
        self.base = base
        self.v = v
        n = len(v)
        self.n = n
        Cd = array.array("d", [0.0] * n)
        Ce = array.array("d", [0.0] * n)
        Cs = array.array("d", [0.0] * n)
        cd = ce = cs = 0.0
        for i in range(1, n):
            a, b = v[i - 1], v[i]
            if a == a and b == b:
                cd += 1.0
                d = b - a
                cs += d * d
                if a == b:
                    ce += 1.0
            Cd[i] = cd
            Ce[i] = ce
            Cs[i] = cs
        self.Cd, self.Ce, self.Cs = Cd, Ce, Cs

    def _i(self, sec):
        i = sec - self.base
        return i if 0 <= i < self.n else None

    def flat(self, sec, win):
        """Fraction of the last `win` consecutive prints EXACTLY equal."""
        i = self._i(sec)
        if i is None or i - win < 0:
            return None
        nd = self.Cd[i] - self.Cd[i - win]
        if nd < win * 0.9 or nd < 5:
            return None
        return (self.Ce[i] - self.Ce[i - win]) / nd

    def sigma(self, sec, win):
        """RMS one-second difference over the last `win` seconds."""
        i = self._i(sec)
        if i is None or i - win < 0:
            return None
        nd = self.Cd[i] - self.Cd[i - win]
        if nd < win * 0.9 or nd < 5:
            return None
        return math.sqrt((self.Cs[i] - self.Cs[i - win]) / nd)

    def maxmove(self, sec, win):
        """Largest ABSOLUTE one-second move in the last `win` seconds."""
        i = self._i(sec)
        if i is None or i - win < 0:
            return None
        v, best, seen = self.v, 0.0, 0
        for j in range(i - win + 1, i + 1):
            a, b = v[j - 1], v[j]
            if a == a and b == b:
                seen += 1
                d = abs(b - a)
                if d > best:
                    best = d
        return best if seen >= win * 0.9 else None

    def rng(self, sec, win):
        """max - min of the index over the last `win` seconds."""
        i = self._i(sec)
        if i is None or i - win < 0:
            return None
        v = self.v
        lo = hi = None
        seen = 0
        for j in range(i - win, i + 1):
            x = v[j]
            if x == x:
                seen += 1
                if lo is None or x < lo:
                    lo = x
                if hi is None or x > hi:
                    hi = x
        return (hi - lo) if seen >= win * 0.9 else None

    def val(self, sec):
        i = self._i(sec)
        if i is None:
            return None
        x = self.v[i]
        return x if x == x else None


def load_index(t_lo, t_hi, only=None):
    """Raw cfbenchmarks tape over [t_lo, t_hi] seconds -> {index_id: Idx}.

    READ-ONLY.  Truncated gzip on the hour still being written is tolerated,
    and the number of files that ended early is returned so a short tape can
    never masquerade as a quiet one.
    """
    files = sorted(glob.glob(os.path.join(
        DATA, "cfbenchmarks_value", "2026*.jsonl.gz")))
    keep = []
    for f in files:
        stamp = os.path.basename(f)[:11]
        try:
            t = int(time.mktime(time.strptime(stamp, "%Y%m%dT%H"))
                    - time.timezone)
        except Exception:
            continue
        if t + 3600 >= t_lo and t <= t_hi:
            keep.append(f)
    raw = defaultdict(dict)
    trunc = 0
    for f in keep:
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    if '"cfbenchmarks_value"' not in line:
                        continue
                    try:
                        m = json.loads(line)["msg"]
                        iid = m["index_id"]
                        if only and iid not in only:
                            continue
                        dd = json.loads(m["data"])
                        s = int(dd["time"]) // 1000
                        if t_lo <= s <= t_hi:
                            raw[iid][s] = float(dd["value"])
                    except Exception:
                        continue
        except (EOFError, zlib.error, OSError):
            trunc += 1
    out = {}
    for iid, d in raw.items():
        if not d:
            continue
        lo, hi = min(d), max(d)
        arr = array.array("d", [float("nan")] * (hi - lo + 1))
        for s, x in d.items():
            arr[s - lo] = x
        out[iid] = Idx(lo, arr)
    return out, len(keep), trunc


# ---------------------------------------------------------------------------
# FEATURES -- every one of them backward-looking from `sec`
# ---------------------------------------------------------------------------
FEATS = [
    ("flat10",   "frac of last 10s prints exactly equal to the previous"),
    ("flat30",   "frac of last 30s prints exactly equal"),
    ("flat60",   "frac of last 60s prints exactly equal"),
    ("flat300",  "frac of last 300s prints exactly equal"),
    ("s30_s300", "sigma_30 / sigma_300  (low = unusually quiet right now)"),
    ("s300_s900", "sigma_300 / sigma_900 (low = quiet vs the last 15 min)"),
    ("s300_s3600", "sigma_300 / sigma_3600 (low = quiet vs the hour)"),
    ("s300_sday", "sigma_300 / sigma_86400 (low = quiet vs the day)"),
    ("mx10_sig", "largest 1s move in last 10s, in sigma_300"),
    ("mx30_sig", "largest 1s move in last 30s, in sigma_300"),
    ("mx60_sig", "largest 1s move in last 60s, in sigma_300"),
    ("req_rng30", "|required move| / index range over last 30s"),
    ("req_rng60", "|required move| / index range over last 60s"),
    ("req_rng300", "|required move| / index range over last 300s"),
    ("gap",      "market implied p(lose) minus model p(lose)"),
    ("lgap",     "log( market implied p(lose) / model p(lose) )"),
    ("z",        "|required move| in model sd (higher should be safer)"),
    ("pmod",     "model p(lose) at entry"),
    ("tau",      "seconds to close at entry"),
    ("price",    "price paid, dollars"),
    ("spread",   "bid-ask spread at entry"),
    ("size",     "contracts resting at the touch"),
    ("age_ms",   "age of the resting level, ms"),
]


def add_features(rows, idxs):
    """Attach every entry-time feature.  Returns (kept, dropped-by-reason)."""
    drop = defaultdict(int)
    out = []
    for rw in rows:
        iid = SERIES_TO_INDEX.get(rw["sr"])
        ix = idxs.get(iid)
        if ix is None:
            drop["no index tape"] += 1
            continue
        sec = rw["sec"]
        f = {}
        for w, nm in ((10, "flat10"), (30, "flat30"),
                      (60, "flat60"), (300, "flat300")):
            f[nm] = ix.flat(sec, w)
        s300 = rw.get("sig")
        s900 = ix.sigma(sec, 900)
        s3600 = ix.sigma(sec, 3600)
        sday = ix.sigma(sec, 86400)
        s30 = rw.get("s30")
        f["s30_s300"] = (s30 / s300) if (s30 is not None and s300) else None
        f["s300_s900"] = (s300 / s900) if (s300 is not None and s900) else None
        f["s300_s3600"] = (s300 / s3600) if (s300 is not None and s3600) \
            else None
        f["s300_sday"] = (s300 / sday) if (s300 is not None and sday) else None
        for w, nm in ((10, "mx10_sig"), (30, "mx30_sig"), (60, "mx60_sig")):
            mm = ix.maxmove(sec, w)
            f[nm] = (mm / s300) if (mm is not None and s300) else None
        areq = abs(rw["req"])
        for w, nm in ((30, "req_rng30"), (60, "req_rng60"),
                      (300, "req_rng300")):
            rg = ix.rng(sec, w)
            f[nm] = (areq / rg) if (rg is not None and rg > 0) else None
        pm = model_pflip(rw["req"], rw["r"], s300)
        f["pmod"] = pm
        pmkt = 1.0 - float(rw["price"])
        f["gap"] = (pmkt - pm) if pm is not None else None
        if pm is not None and pm > 1e-12 and pmkt > 1e-12:
            f["lgap"] = math.log(pmkt / pm)
        else:
            f["lgap"] = None
        f["z"] = model_z(rw["req"], rw["r"], s300)
        f["tau"] = float(rw["tau"])
        f["price"] = float(rw["price"])
        f["spread"] = float(rw["spread"]) if rw.get("spread") is not None \
            else None
        f["size"] = float(rw["size"]) if rw.get("size") is not None else None
        f["age_ms"] = (float(rw["age_ms"])
                       if rw.get("age_ms") is not None else None)
        f["_s900"] = s900
        f["_s3600"] = s3600
        f["_sday"] = sday
        f["_rng60"] = ix.rng(sec, 60)
        f["_areq"] = areq
        f["_s300"] = s300
        rw["f"] = f
        out.append(rw)
    return out, drop


# ---------------------------------------------------------------------------
# THE ESTIMATOR.  Buckets by quantile, loss rate per bucket, close-cluster
# bootstrap for the CI, market-level outcome shuffle for the null.
# ---------------------------------------------------------------------------
def quantile_cuts(vals, nb):
    s = sorted(vals)
    if not s:
        return []
    cuts = []
    for k in range(1, nb):
        q = s[min(len(s) - 1, int(round(k * len(s) / nb)))]
        if not cuts or q > cuts[-1]:
            cuts.append(q)
    return cuts


def bucket_of(x, cuts):
    lo, hi = 0, len(cuts)
    while lo < hi:
        mid = (lo + hi) // 2
        if x < cuts[mid]:
            hi = mid
        else:
            lo = mid + 1
    return lo


def analyse(rows, name, nb=5, boots=2000, shufs=500, seed=11):
    """Loss rate by quantile bucket of `name`, with CI, MDE and control."""
    use = [r for r in rows if r["f"].get(name) is not None]
    if len(use) < 200:
        return None
    vals = [r["f"][name] for r in use]
    cuts = quantile_cuts(vals, nb)
    nbk = len(cuts) + 1
    if nbk < 2:
        return {"name": name, "degenerate": True, "rows": len(use),
                "dropped": len(rows) - len(use)}
    for r in use:
        r["_b"] = bucket_of(r["f"][name], cuts)
    # Heavy ties (flat10 takes only 11 distinct values, say) can leave a
    # quantile bucket with nothing in it.  An empty bucket is not a result and
    # must never become the "top" or "bottom" of the comparison, so drop it
    # and renumber.  The number that survives is reported.
    seen = sorted({r["_b"] for r in use})
    if len(seen) < nbk:
        remap = {b: k for k, b in enumerate(seen)}
        for r in use:
            r["_b"] = remap[r["_b"]]
        nbk = len(seen)
    if nbk < 2:
        return {"name": name, "degenerate": True, "rows": len(use),
                "dropped": len(rows) - len(use)}

    n = [0] * nbk
    fl = [0] * nbk
    pr = [0.0] * nbk            # SUM of the model's own p(lose) in the bucket
    mk = [set() for _ in range(nbk)]
    cl = [set() for _ in range(nbk)]
    vmin = [None] * nbk
    vmax = [None] * nbk
    for r in use:
        b = r["_b"]
        n[b] += 1
        fl[b] += 1 if r["flip"] else 0
        pm = r["f"].get("pmod")
        pr[b] += pm if pm is not None else 0.0
        mk[b].add(r["tk"])
        cl[b].add(r["close"])
        x = r["f"][name]
        vmin[b] = x if vmin[b] is None or x < vmin[b] else vmin[b]
        vmax[b] = x if vmax[b] is None or x > vmax[b] else vmax[b]

    # ---- close-cluster bootstrap ----------------------------------------
    # Two statistics, and the second one is the one that answers the question.
    #   RAW  = loss rate(top) - loss rate(bottom)
    #   EXC  = the same on EXCESS OVER MODEL, (observed - mean model p).
    # RAW fires for any feature that merely restates "this trade is risky" --
    # price, z, p_model and the range ratios are all the same fact wearing a
    # different hat, and the model already charges for it. EXC asks the only
    # question that could change the rule: is the model MORE WRONG here?
    byclose = defaultdict(lambda: [[0, 0, 0.0] for _ in range(nbk)])
    for r in use:
        c = byclose[r["close"]][r["_b"]]
        c[0] += 1
        c[1] += 1 if r["flip"] else 0
        pm = r["f"].get("pmod")
        c[2] += pm if pm is not None else 0.0
    closes = list(byclose.values())
    nc = len(closes)
    rnd = random.Random(seed)
    diffs = []
    ediffs = []
    hi_b, lo_b = nbk - 1, 0
    for _ in range(boots):
        a0 = a1 = b0 = b1 = 0
        ap = bp = 0.0
        for _k in range(nc):
            g = closes[rnd.randrange(nc)]
            a0 += g[hi_b][0]
            a1 += g[hi_b][1]
            ap += g[hi_b][2]
            b0 += g[lo_b][0]
            b1 += g[lo_b][1]
            bp += g[lo_b][2]
        if a0 and b0:
            diffs.append(a1 / a0 - b1 / b0)
            ediffs.append((a1 - ap) / a0 - (b1 - bp) / b0)
    diffs.sort()
    ediffs.sort()
    obs = (fl[hi_b] / n[hi_b] if n[hi_b] else float("nan")) - \
          (fl[lo_b] / n[lo_b] if n[lo_b] else float("nan"))
    eobs = ((fl[hi_b] - pr[hi_b]) / n[hi_b] if n[hi_b] else float("nan")) - \
           ((fl[lo_b] - pr[lo_b]) / n[lo_b] if n[lo_b] else float("nan"))
    if len(diffs) >= 20:
        ci = (diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))])
        mean = sum(diffs) / len(diffs)
        se = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (len(diffs) - 1))
        eci = (ediffs[int(0.025 * len(ediffs))],
               ediffs[int(0.975 * len(ediffs))])
        em = sum(ediffs) / len(ediffs)
        ese = math.sqrt(sum((d - em) ** 2 for d in ediffs) /
                        (len(ediffs) - 1))
    else:
        ci, se = (float("nan"), float("nan")), float("nan")
        eci, ese = (float("nan"), float("nan")), float("nan")

    # ---- shuffled-label control ------------------------------------------
    bym = defaultdict(lambda: [[0, 0] for _ in range(nbk)])
    won = {}
    for r in use:
        c = bym[r["tk"]][r["_b"]]
        c[0 if r["side_yes"] else 1] += 1
        won[r["tk"]] = (r["side_yes"] != r["flip"])
    mkts = list(bym.keys())
    wons = [won[t] for t in mkts]
    blocks = [bym[t] for t in mkts]
    tot = [0] * nbk
    for bl in blocks:
        for b in range(nbk):
            tot[b] += bl[b][0] + bl[b][1]
    rnd2 = random.Random(seed + 7919)
    sd_ = []
    for _ in range(shufs):
        rnd2.shuffle(wons)
        a1 = b1 = 0
        for k, bl in enumerate(blocks):
            # flip = side_yes != won_yes; if won_yes is True the side_yes=False
            # rows are the flips, and vice versa.
            j = 1 if wons[k] else 0
            a1 += bl[hi_b][j]
            b1 += bl[lo_b][j]
        if tot[hi_b] and tot[lo_b]:
            sd_.append(a1 / tot[hi_b] - b1 / tot[lo_b])
    sd_.sort()
    if len(sd_) >= 20:
        m2 = sum(sd_) / len(sd_)
        nse = math.sqrt(sum((d - m2) ** 2 for d in sd_) / (len(sd_) - 1))
        nlo, nhi = sd_[int(0.025 * len(sd_))], sd_[int(0.975 * len(sd_))]
        pv = (sum(1 for d in sd_ if abs(d - m2) >= abs(obs - m2)) + 1) / \
             (len(sd_) + 1)
        # The model's predicted sums per bucket do not move under a shuffle,
        # so the EXCESS null is the RAW null shifted by a constant and the
        # centred permutation p is identical by construction.  Stated rather
        # than recomputed, so nobody reads two p-values as two tests.
        shift = pr[hi_b] / tot[hi_b] - pr[lo_b] / tot[lo_b] \
            if (tot[hi_b] and tot[lo_b]) else float("nan")
        enlo, enhi = nlo - shift, nhi - shift
    else:
        nse = nlo = nhi = enlo = enhi = float("nan")
        pv = float("nan")

    return {
        "name": name, "rows": len(use), "dropped": len(rows) - len(use),
        "loss_closes": len({r["close"] for r in use if r["flip"]}),
        "loss_markets": len({r["tk"] for r in use if r["flip"]}),
        "nb": nbk, "cuts": cuts, "n": n, "flips": fl,
        "rate": [fl[b] / n[b] if n[b] else float("nan") for b in range(nbk)],
        "pred": [pr[b] / n[b] if n[b] else float("nan") for b in range(nbk)],
        "markets": [len(s) for s in mk], "closes": [len(s) for s in cl],
        "vmin": vmin, "vmax": vmax,
        "n_closes": nc, "obs": obs, "se": se, "ci": ci,
        "mde": 2.80 * se if se == se else float("nan"),
        "eobs": eobs, "ese": ese, "eci": eci,
        "emde": 2.80 * ese if ese == ese else float("nan"),
        "enull_ci": (enlo, enhi),
        "null_se": nse, "null_ci": (nlo, nhi), "p_shuffle": pv,
    }


def analyse_strat(rows, name, strat, nb=3, ns=5, boots=1000, shufs=300,
                  seed=13):
    """Does `name` still separate losers AFTER `strat` is held fixed?

    Every strong feature in this file -- price, z, p_model, the range ratios --
    is the same underlying fact ("the strike is close relative to the noise")
    wearing a different hat, and the model already charges for that fact.  The
    only question that can change the trading rule is whether a feature adds
    anything ON TOP of the model's own number.  So: cut the population into
    quantile strata of `strat`, bucket `name` WITHIN each stratum, and pool the
    top-minus-bottom difference with the strata weighted by their row counts.
    A feature that is merely a re-labelling of `strat` collapses to zero here,
    and the self-test plants exactly that world to prove it does.
    """
    use = [r for r in rows if r["f"].get(name) is not None
           and r["f"].get(strat) is not None]
    if len(use) < 400:
        return None
    scuts = quantile_cuts([r["f"][strat] for r in use], ns)
    for r in use:
        r["_s"] = bucket_of(r["f"][strat], scuts)
    nsk = len(scuts) + 1
    cells = defaultdict(list)
    for r in use:
        cells[r["_s"]].append(r)
    keep = []
    for s in range(nsk):
        grp = cells.get(s) or []
        if len(grp) < 60:
            continue
        cuts = quantile_cuts([r["f"][name] for r in grp], nb)
        if len(cuts) < 1:
            continue
        for r in grp:
            r["_b"] = bucket_of(r["f"][name], cuts)
        seen = sorted({r["_b"] for r in grp})
        if len(seen) < 2:
            continue
        remap = {b: k for k, b in enumerate(seen)}
        for r in grp:
            r["_b"] = remap[r["_b"]]
        r_top = len(seen) - 1
        for r in grp:
            r["_top"] = 1 if r["_b"] == r_top else (0 if r["_b"] == 0 else -1)
        keep.append(s)
    use2 = [r for r in use if r["_s"] in keep and r.get("_top", -1) >= 0]
    if len(use2) < 200:
        return None

    def stat(cnt):
        """cnt[s] = [[n_bot, f_bot], [n_top, f_top]] -> weighted difference."""
        num = den = 0.0
        for s in keep:
            c = cnt.get(s)
            if not c or not c[0][0] or not c[1][0]:
                continue
            w = c[0][0] + c[1][0]
            num += w * (c[1][1] / c[1][0] - c[0][1] / c[0][0])
            den += w
        return num / den if den else float("nan")

    obs_cnt = defaultdict(lambda: [[0, 0], [0, 0]])
    for r in use2:
        c = obs_cnt[r["_s"]][r["_top"]]
        c[0] += 1
        c[1] += 1 if r["flip"] else 0
    obs = stat(obs_cnt)

    byclose = defaultdict(lambda: defaultdict(lambda: [[0, 0], [0, 0]]))
    for r in use2:
        c = byclose[r["close"]][r["_s"]][r["_top"]]
        c[0] += 1
        c[1] += 1 if r["flip"] else 0
    closes = list(byclose.values())
    nc = len(closes)
    rnd = random.Random(seed)
    ds = []
    for _ in range(boots):
        acc = defaultdict(lambda: [[0, 0], [0, 0]])
        for _k in range(nc):
            g = closes[rnd.randrange(nc)]
            for s, c in g.items():
                a = acc[s]
                a[0][0] += c[0][0]
                a[0][1] += c[0][1]
                a[1][0] += c[1][0]
                a[1][1] += c[1][1]
        v = stat(acc)
        if v == v:
            ds.append(v)
    ds.sort()
    if len(ds) >= 20:
        ci = (ds[int(0.025 * len(ds))], ds[int(0.975 * len(ds))])
        m = sum(ds) / len(ds)
        se = math.sqrt(sum((d - m) ** 2 for d in ds) / (len(ds) - 1))
    else:
        ci, se = (float("nan"), float("nan")), float("nan")

    bym = defaultdict(lambda: defaultdict(lambda: [[0, 0], [0, 0]]))
    won = {}
    for r in use2:
        c = bym[r["tk"]][r["_s"]][r["_top"]]
        c[0 if r["side_yes"] else 1] += 1
        won[r["tk"]] = (r["side_yes"] != r["flip"])
    mkts = list(bym.keys())
    wons = [won[t] for t in mkts]
    blocks = [bym[t] for t in mkts]
    base = defaultdict(lambda: [[0, 0], [0, 0]])
    for bl in blocks:
        for s, c in bl.items():
            base[s][0][0] += c[0][0] + c[0][1]
            base[s][1][0] += c[1][0] + c[1][1]
    rnd2 = random.Random(seed + 104729)
    nl = []
    for _ in range(shufs):
        rnd2.shuffle(wons)
        acc = {s: [[base[s][0][0], 0], [base[s][1][0], 0]] for s in base}
        for k, bl in enumerate(blocks):
            j = 1 if wons[k] else 0
            for s, c in bl.items():
                acc[s][0][1] += c[0][j]
                acc[s][1][1] += c[1][j]
        v = stat(acc)
        if v == v:
            nl.append(v)
    nl.sort()
    if len(nl) >= 20:
        m2 = sum(nl) / len(nl)
        nse = math.sqrt(sum((d - m2) ** 2 for d in nl) / (len(nl) - 1))
        nci = (nl[int(0.025 * len(nl))], nl[int(0.975 * len(nl))])
        pv = (sum(1 for d in nl if abs(d - m2) >= abs(obs - m2)) + 1) / \
             (len(nl) + 1)
    else:
        nse, nci, pv = float("nan"), (float("nan"), float("nan")), float("nan")
    return {"name": name, "strat": strat, "rows": len(use2),
            "strata": len(keep), "n_closes": nc,
            "loss_closes": len({r["close"] for r in use2 if r["flip"]}),
            "obs": obs, "se": se, "ci": ci,
            "mde": 2.80 * se if se == se else float("nan"),
            "null_ci": nci, "null_se": nse, "p_shuffle": pv}


def pct_rank(x, pool):
    """Percentile of x among pool (fraction of pool at or below x)."""
    if x is None or not pool:
        return None
    return sum(1 for v in pool if v <= x) / len(pool)


# ---------------------------------------------------------------------------
def _synth(planted, seed=3, nclose=180, nmk=6, nrow=25, calibrated=False):
    """Build a world.

    planted=True     -> high `q` really does cause flips.
    calibrated=True  -> and the MODEL ALREADY KNOWS IT (pmod == the true
                        probability).  That world is the sharpest null this
                        file has: the raw loss rate must still rise with q,
                        and the EXCESS OVER MODEL must not.
    """
    rnd = random.Random(seed)
    rows = []
    for c in range(nclose):
        close = 1788000000 + c * 900
        for m in range(nmk):
            q = rnd.random()
            p = (0.02 + 0.40 * (q ** 3)) if planted else 0.12
            pm = p if calibrated else 0.12
            won_yes = rnd.random() > 0.5
            lost = rnd.random() < p
            tk = f"T{c}-{m}"
            for k in range(nrow):
                side_yes = (not won_yes) if lost else won_yes
                rows.append({
                    "tk": tk, "close": close, "sec": close - 100 + k,
                    "price": 0.95, "side_yes": side_yes,
                    "flip": side_yes != won_yes,
                    "f": {"q": q + rnd.random() * 1e-9,
                          "noise": rnd.random(), "pmod": pm},
                })
    return rows


def selftest():
    print("SELF-TEST -- pinsignal")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # ---- window statistics on a hand-made tape ---------------------------
    v = array.array("d", [1.0] * 50)
    ix = Idx(1000, v)
    ck(ix.flat(1040, 10) == 1.0, "a dead-flat tape is 100% flat")
    ck(ix.sigma(1040, 10) == 0.0, "and has zero one-second sigma")
    ck(ix.rng(1040, 10) == 0.0, "and zero range")
    ck(ix.maxmove(1040, 10) == 0.0, "and no largest move")
    v2 = array.array("d", [1.0 + (i % 2) * 0.5 for i in range(50)])
    ix2 = Idx(1000, v2)
    ck(ix2.flat(1040, 10) == 0.0, "an alternating tape is 0% flat")
    ck(abs(ix2.maxmove(1040, 10) - 0.5) < 1e-12,
       f"largest 1s move 0.5 ({ix2.maxmove(1040, 10)})")
    v3 = array.array("d", [1.0] * 50)
    for i in range(41, 50):
        v3[i] = 2.0
    ix3 = Idx(1000, v3)
    ck(abs(ix3.flat(1049, 5) - 1.0) < 1e-12,
       f"flat over the last 5s ignores a jump 8s earlier "
       f"({ix3.flat(1049, 5)})")
    ck(ix3.flat(1049, 30) < 1.0, "but the 30s window still sees that jump")
    ck(ix3.maxmove(1049, 30) == 1.0, "and reports its size")
    ck(abs(ix3.rng(1049, 30) - 1.0) < 1e-12, "and the range is 1.0")
    v4 = array.array("d", [1.0] * 50)
    v4[20] = float("nan")
    ix4 = Idx(1000, v4)
    ck(ix4.flat(1049, 10) == 1.0, "a NaN outside the window is harmless")
    ck(ix4.flat(1025, 10) is None,
       "a window that is mostly missing returns None, not a number")

    # ---- the model probability -------------------------------------------
    p_far = model_pflip(0.10, 20, 0.001)
    p_near = model_pflip(0.001, 20, 0.001)
    ck(p_far is not None and p_far < 1e-6,
       f"a far strike is essentially safe ({p_far:.2e})")
    ck(p_near > p_far, "a near strike is riskier")
    ck(model_pflip(0.001, 20, 0.0) == 1.0,
       "with zero sigma a required move above zero is certain loss")

    # ---- bucketing --------------------------------------------------------
    cuts = quantile_cuts(list(range(100)), 5)
    ck(len(cuts) == 4, f"5 buckets need 4 cuts ({len(cuts)})")
    ck(bucket_of(-1, cuts) == 0 and bucket_of(999, cuts) == 4,
       "values below and above every cut land in the end buckets")

    # ---- THE PLANTED WORLD.  High q really does cause flips. -------------
    got = analyse(_synth(True), "q", nb=5, boots=400, shufs=300, seed=5)
    ck(got is not None and got["obs"] > 0.15,
       f"planted: top-vs-bottom loss-rate gap is large "
       f"({got['obs'] if got else None})")
    ck(got and got["ci"][0] > 0,
       f"planted: the close-cluster 95% CI excludes zero "
       f"({got['ci'] if got else None})")
    ck(got and got["p_shuffle"] < 0.01,
       f"planted: the shuffled-label control does NOT reproduce it "
       f"(p={got['p_shuffle'] if got else None})")

    # ---- THE NULL WORLD.  Nothing is planted; find nothing. --------------
    bad = 0
    for sd in (3, 4, 5, 6, 7):
        g = analyse(_synth(False, seed=sd), "q", nb=5, boots=400,
                    shufs=300, seed=sd)
        if g and (g["ci"][0] > 0 or g["ci"][1] < 0):
            bad += 1
    ck(bad <= 1, f"null world: the CI excludes zero in {bad} of 5 seeds "
                 f"(chance alone gives 0-1)")
    g2 = analyse(_synth(True, seed=9), "noise", nb=5, boots=400,
                 shufs=300, seed=9)
    ck(g2 and not (g2["ci"][0] > 0 or g2["ci"][1] < 0),
       f"a pure-noise feature finds nothing even when a REAL signal exists "
       f"in the same world ({g2['ci'] if g2 else None})")

    # ---- THE EXCESS-OVER-MODEL STATISTIC ---------------------------------
    # planted, model blind: the model is genuinely more wrong at high q.
    ck(got and got["eobs"] > 0.15 and got["eci"][0] > 0,
       f"planted + blind model: EXCESS over model is large and its CI "
       f"excludes zero ({got['eci'] if got else None})")
    # planted, model RIGHT: raw rate still rises, excess must not.  This is
    # the null that kills every feature which merely restates "risky trade".
    badc = 0
    for sd in (11, 12, 13, 14):
        gc = analyse(_synth(True, seed=sd, calibrated=True), "q", nb=5,
                     boots=400, shufs=300, seed=sd)
        ck(gc and gc["obs"] > 0.15,
           f"calibrated world seed {sd}: the RAW loss rate still rises with q "
           f"({gc['obs'] if gc else None})")
        if gc and (gc["eci"][0] > 0 or gc["eci"][1] < 0):
            badc += 1
    ck(badc <= 1,
       f"calibrated world: EXCESS over model excludes zero in {badc} of 4 "
       f"seeds -- a feature the model already prices must NOT survive here")

    # ---- STRATIFICATION: does a feature add anything on top of another? --
    # A world where the outcome depends ONLY on `s`, and `q` is `s` plus
    # noise.  Unstratified, q separates losers -- but it is only wearing s's
    # hat, and holding s fixed must send it to zero.  The noise is deliberately
    # LARGE (sd 0.25): with a near-perfect proxy, stratifying on it removes
    # almost all of the real cause's variation too, and the estimator would
    # then have no power to find EITHER -- which is a property of the design,
    # not a bug, and is why the power leg below is checked on the same world.
    rndx = random.Random(21)
    srows = []
    for c in range(220):
        for m in range(6):
            s_ = rndx.random()
            q_ = max(0.0, min(1.0, s_ + rndx.gauss(0, 0.25)))
            won_yes = rndx.random() > 0.5
            lost = rndx.random() < (0.02 + 0.40 * (s_ ** 3))
            for k in range(20):
                sy = (not won_yes) if lost else won_yes
                srows.append({"tk": f"S{c}-{m}", "close": 1788000000 + c * 900,
                              "sec": k, "side_yes": sy,
                              "flip": sy != won_yes, "price": 0.95,
                              "f": {"q": q_ + rndx.random() * 1e-9,
                                    "s": s_, "pmod": 0.12}})
    raw = analyse(srows, "q", nb=5, boots=400, shufs=300, seed=2)
    ck(raw and raw["obs"] > 0.15 and raw["ci"][0] > 0,
       f"proxy world: UNSTRATIFIED, q separates losers "
       f"({raw['obs'] if raw else None})")
    st = analyse_strat(srows, "q", "s", nb=3, ns=5, boots=400, shufs=300,
                       seed=2)
    ck(st is not None and not (st["ci"][0] > 0 or st["ci"][1] < 0),
       f"proxy world: with `s` held fixed, q adds NOTHING "
       f"({st['ci'] if st else None})")
    ck(st is not None and st["p_shuffle"] > 0.05,
       f"proxy world: and the shuffled control agrees "
       f"(p={st['p_shuffle'] if st else None})")
    st2 = analyse_strat(srows, "s", "q", nb=3, ns=5, boots=400, shufs=300,
                        seed=2)
    ck(st2 is not None and st2["ci"][0] > 0,
       f"proxy world: the REAL cause still separates with the proxy held "
       f"fixed ({st2['ci'] if st2 else None})")

    # ---- the gate arithmetic ---------------------------------------------
    ck(abs(trade_pnl(0.95, False) - 4.66) < 1e-9,
       f"a 95c winner nets 4.66c after the 0.34c fee "
       f"({trade_pnl(0.95, False)})")
    ck(abs(trade_pnl(0.95, True) + 95.34) < 1e-9,
       f"a 95c loser costs 95.34c ({trade_pnl(0.95, True)})")
    tr = [{"tk": "a", "price": 0.95, "flip": False, "f": {"x": 1.0}},
          {"tk": "b", "price": 0.95, "flip": False, "f": {"x": 9.0}},
          {"tk": "c", "price": 0.95, "flip": True, "f": {"x": 9.0}},
          {"tk": "d", "price": 0.95, "flip": False, "f": {"x": 9.0}}]
    gs = gate_study(tr, "x", [5.0], refuse_above=True)
    r0 = gs["rows"][0]
    ck(r0["refused"] == 3 and r0["losses_avoided"] == 1
       and r0["wins_refused"] == 2,
       f"gate at x>=5 refuses 3 trades: 2 wins and the 1 loss ({r0})")
    ck(abs(r0["wins_per_loss"] - 2.0) < 1e-9,
       "and that is 2 winning trades refused per loss avoided")
    ck(abs(gs["base_pnl"] - (3 * 4.66 - 95.34)) < 1e-9,
       f"ungated P&L is 3 winners minus 1 loser ({gs['base_pnl']})")
    ck(abs(r0["pnl_after"] - 4.66) < 1e-9,
       f"after the gate only the one surviving winner is left "
       f"({r0['pnl_after']})")
    fp = first_per_market([{"tk": "a", "sec": 5}, {"tk": "a", "sec": 3},
                           {"tk": "b", "sec": 9}])
    ck(len(fp) == 2 and min(t["sec"] for t in fp if t["tk"] == "a") == 3,
       "one trade per market, and it is the EARLIEST qualifying second")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ---------------------------------------------------------------------------
def fmt_row(res, desc):
    L = []
    L.append(f"\n### `{res['name']}` -- {desc}")
    if res.get("degenerate"):
        L.append(f"\nDEGENERATE: only one distinct value over "
                 f"{res['rows']:,} rows. No test possible.")
        return "\n".join(L)
    L.append(f"\nrows {res['rows']:,}   closes {res['n_closes']}   "
             f"**loss-carrying closes {res['loss_closes']}**   "
             f"losing markets {res['loss_markets']}   "
             f"dropped (feature unavailable) {res['dropped']:,}")
    if res["loss_closes"] < 30:
        L.append(f"\n**BELOW THE 30-CLUSTER FLOOR ({res['loss_closes']} "
                 f"loss-carrying closes). Nothing below is a significance "
                 f"claim, whatever the interval says.**")
    L.append(f"\n**MDE (stated before the estimate): "
             f"{100*res['mde']:.3f} pp** difference in loss rate between the "
             f"top and bottom bucket, at 80% power.")
    L.append("")
    L.append("| bucket | range | rows | markets | closes | losses "
             "| loss rate | model said | obs/model |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for b in range(res["nb"]):
        p = res["pred"][b]
        L.append(f"| {b+1} | {res['vmin'][b]:.4g} .. {res['vmax'][b]:.4g} "
                 f"| {res['n'][b]:,} | {res['markets'][b]:,} "
                 f"| {res['closes'][b]} | {res['flips'][b]:,} "
                 f"| **{100*res['rate'][b]:.2f}%** | {100*p:.2f}% | "
                 f"{(res['rate'][b]/p if p > 0 else float('nan')):.1f}x |")
    L.append(f"\nRAW  top - bottom = **{100*res['obs']:+.2f} pp**   "
             f"95% CI (close-cluster bootstrap) "
             f"[{100*res['ci'][0]:+.2f}, {100*res['ci'][1]:+.2f}] pp   "
             f"SE {100*res['se']:.3f} pp")
    L.append(f"\nEXCESS OVER MODEL, top - bottom = "
             f"**{100*res['eobs']:+.2f} pp**   95% CI "
             f"[{100*res['eci'][0]:+.2f}, {100*res['eci'][1]:+.2f}] pp   "
             f"MDE {100*res['emde']:.3f} pp")
    L.append(f"\nSHUFFLED-LABEL CONTROL: null 95% range "
             f"[{100*res['null_ci'][0]:+.2f}, {100*res['null_ci'][1]:+.2f}] "
             f"pp, null SE {100*res['null_se']:.3f} pp, "
             f"permutation p = **{res['p_shuffle']:.4f}**")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# WHAT A GATE WOULD COST.  A gate that avoids one loss and refuses 200 wins is
# worse than no gate, so the only honest unit is winning trades refused PER
# LOSS AVOIDED, next to the cents of profit destroyed.
# ---------------------------------------------------------------------------
def trade_pnl(price, flip, n=1.0):
    """Cents per contract, fee included.  Takers pay the fee both ways."""
    if flip:
        return -100.0 * price - 100.0 * billed_fee(price, 1.0)
    return 100.0 * (1.0 - price) - 100.0 * billed_fee(price, 1.0)


def first_per_market(rows):
    """One TRADE per market: the earliest qualifying second, which is what the
    live rule actually takes (it buys the first quote that clears its gates)."""
    best = {}
    for r in rows:
        b = best.get(r["tk"])
        if b is None or r["sec"] < b["sec"]:
            best[r["tk"]] = r
    return list(best.values())


def gate_study(trades, name, thresholds, refuse_above):
    """For each threshold: what the gate refuses and what that costs."""
    base_w = sum(1 for t in trades if not t["flip"])
    base_l = sum(1 for t in trades if t["flip"])
    base_p = sum(trade_pnl(t["price"], t["flip"]) for t in trades)
    rowsout = []
    for th in thresholds:
        ref = [t for t in trades
               if t["f"].get(name) is not None
               and ((t["f"][name] >= th) if refuse_above
                    else (t["f"][name] <= th))]
        rw = sum(1 for t in ref if not t["flip"])
        rl = sum(1 for t in ref if t["flip"])
        rp = sum(trade_pnl(t["price"], t["flip"]) for t in ref)
        rowsout.append({
            "th": th, "refused": len(ref), "wins_refused": rw,
            "losses_avoided": rl,
            "wins_per_loss": (rw / rl) if rl else float("inf"),
            "pnl_refused": rp, "pnl_after": base_p - rp,
            "pnl_change": -rp,
        })
    return {"base_wins": base_w, "base_losses": base_l, "base_pnl": base_p,
            "rows": rowsout}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=ROWS)
    ap.add_argument("--out",
                    default=os.path.join(OUTDIR, "RESULTS_pinsignal.md"))
    ap.add_argument("--nb", type=int, default=5)
    ap.add_argument("--boots", type=int, default=2000)
    ap.add_argument("--shufs", type=int, default=500)
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")
    if a.quick:
        a.boots, a.shufs = 400, 200

    t0 = time.time()
    rows = []
    with open(a.rows, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            if 3 <= d["tau"] <= 200:
                rows.append(d)
    print(f"  {len(rows):,} wide-window rows (tau 3-200)")
    if not rows:
        print("  loaded nothing")
        return

    lo = min(r["sec"] for r in rows)
    hi = max(r["sec"] for r in rows)
    print(f"  index tape needed "
          f"{time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(lo - 86400))}"
          f" .. {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime(hi))}")
    idxs, nfiles, trunc = load_index(lo - 86400 - 60, hi + 5)
    print(f"  {len(idxs)} indices from {nfiles} hourly files "
          f"({trunc} ended early)")
    if not idxs:
        print("  loaded nothing")
        return

    rows, drop = add_features(rows, idxs)
    print(f"  features attached to {len(rows):,} rows  "
          f"({dict(drop)})  {time.time()-t0:.0f}s")

    P1 = rows
    P2 = [r for r in rows
          if r["f"]["pmod"] is not None
          and r["price"] <= CEILING
          and r["f"]["pmod"] <= PIN_P
          and entry_ev(r["price"]) >= EV_FLOOR]
    # tau is by far the strongest thing in this table (0 flips under tau 30,
    # 3.05% at tau 55-60), so ANY feature correlated with tau will separate
    # losers for a reason that has nothing to do with the feature.  These two
    # bands hold tau nearly fixed and are the control for that.
    P1H = [r for r in P1 if r["tau"] >= 45]
    P1M_ = [r for r in P1 if 30 <= r["tau"] < 45]
    POPS = [
        ("P1", "WIDE, every available second, tau 3-60", P1),
        ("P1_tau45+", "WIDE, tau 45-60 only -- tau held nearly fixed", P1H),
        ("P1_tau30-44", "WIDE, tau 30-44 only -- tau held nearly fixed",
         P1M_),
        ("P2", "WIDE and the LIVE RULE's gates "
               "(price<=98.8c, model p<=2%, EV>=0.3c)", P2),
        ("P1M", "one TRADE per market (earliest qualifying second), WIDE",
         first_per_market(P1)),
        ("P2M", "one TRADE per market, LIVE RULE's gates", first_per_market(P2)),
    ]
    for nm, _d, P in POPS:
        print(f"  {nm}: rows {len(P):,}  markets "
              f"{len({r['tk'] for r in P}):,}  closes "
              f"{len({r['close'] for r in P})}  losses "
              f"{sum(1 for r in P if r['flip']):,}  loss-markets "
              f"{len({r['tk'] for r in P if r['flip']})}  loss-closes "
              f"{len({r['close'] for r in P if r['flip']})}")

    out = []
    out.append("# pinsignal -- what, at ENTRY, separates the losers?\n")
    out.append(f"Generated {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"
               f" from `{a.rows}`.\n")
    out.append(f"Index tape: {nfiles} hourly files, {trunc} ended early "
               f"(truncated gzip tolerated).\n")
    out.append("\n**CORRECTION TO THE BRIEF, measured not assumed:** the wide "
               "window is tau 3-**60**, not 3-200. `pindata.partial()` needs "
               "at least one still-unpublished print inside the 60-second "
               "settlement window, so no row can exist above tau 60. The "
               "largest tau in rows.jsonl is 60.\n")
    for tag, dsc, P in POPS:
        nm = f"{tag} -- {dsc}"
        out.append(f"\n**{nm}**: rows {len(P):,}, markets "
                   f"{len({r['tk'] for r in P}):,}, "
                   f"**closes {len({r['close'] for r in P})}**, "
                   f"losing rows {sum(1 for r in P if r['flip']):,}, "
                   f"losing markets {len({r['tk'] for r in P if r['flip']})}, "
                   f"**loss-carrying closes "
                   f"{len({r['close'] for r in P if r['flip']})}**, "
                   f"row loss rate "
                   f"{100*sum(1 for r in P if r['flip'])/max(1,len(P)):.2f}%\n")
        pm = [r["f"]["pmod"] for r in P if r["f"].get("pmod") is not None]
        if pm:
            obs_ = sum(1 for r in P if r["flip"]) / max(1, len(P))
            prd_ = sum(pm) / len(pm)
            out.append(f"POPULATION CALIBRATION: the model predicted "
                       f"{100*prd_:.3f}% and reality delivered "
                       f"{100*obs_:.3f}% -- **{obs_/prd_:.1f}x** "
                       f"more losses than the gaussian says.\n")

    nfeat = len(FEATS)
    out.append(f"\nMULTIPLE LOOKS: {nfeat} features are tested in each "
               f"population, so the 5% threshold after Bonferroni is "
               f"p = {0.05/nfeat:.4f}. A permutation p above that is not a "
               f"finding.\n")

    results = {}
    for tag, dsc, P in POPS:
        out.append(f"\n---\n\n## Population {tag} -- {dsc}\n")
        lcl = len({r['close'] for r in P if r['flip']})
        if lcl < 30:
            out.append(f"\n**FEWER THAN 30 LOSS-CARRYING CLOSES ({lcl}) -- NO "
                       f"SIGNIFICANCE IS CLAIMED ANYWHERE IN THIS POPULATION.** "
                       f"The intervals are printed so the size of the "
                       f"uncertainty is visible, not so they can be read as "
                       f"findings.\n")
        res = {}
        for name, desc in FEATS:
            g = analyse(P, name, nb=a.nb, boots=a.boots, shufs=a.shufs)
            if g is None:
                out.append(f"\n### `{name}` -- {desc}\n\nNOT TESTED: fewer "
                           f"than 200 rows carry this feature.")
                continue
            res[name] = g
            out.append(fmt_row(g, desc))
            print(f"    {tag} {name:12s} "
                  f"obs {100*g.get('obs', float('nan')):+7.2f}pp"
                  f"  p_shuf {g.get('p_shuffle', float('nan')):.4f}"
                  f"  {time.time()-t0:.0f}s", flush=True)
        results[tag] = res

        for key, lab in (("sr", "coin"), ("hour", "hour of day (UTC)")):
            out.append(f"\n### control: {lab}\n")
            agg = defaultdict(lambda: [0, 0, set()])
            for r in P:
                g = agg[r[key]]
                g[0] += 1
                g[1] += 1 if r["flip"] else 0
                g[2].add(r["close"])
            out.append("| value | rows | closes | losses | loss rate |")
            out.append("|---|---|---|---|---|")
            for k in sorted(agg, key=lambda x: -agg[x][1] / max(1, agg[x][0])):
                v = agg[k]
                out.append(f"| {k} | {v[0]:,} | {len(v[2])} | {v[1]:,} | "
                           f"{100*v[1]/max(1,v[0]):.2f}% |")

    # ---- THE LIVE LOSS ----------------------------------------------------
    out.append("\n---\n\n## The live loss, on every feature\n")
    print("\n  reconstructing the live loss ...")
    live = {}
    lidx, lf, lt = load_index(LOSS_CLOSE - 86400 - 4000, LOSS_CLOSE,
                              only={LOSS_INDEX})
    if LOSS_INDEX not in lidx:
        out.append("\n**COULD NOT RECONSTRUCT** -- the NEAR index tape did not "
                   "load for that window. No feature values are reported and "
                   "none are estimated.\n")
        print("    FAILED: no NEAR tape")
    else:
        ix = lidx[LOSS_INDEX]
        out.append(f"\nNEAR index tape: {lf} hourly files, {lt} ended early.\n")
        winners = {}
        losers = {}
        for tag, P in (("P1", P1), ("P2", P2)):
            winners[tag] = {nm: [r["f"][nm] for r in P
                                 if not r["flip"] and r["f"].get(nm) is not None]
                            for nm, _d in FEATS}
            losers[tag] = {nm: [r["f"][nm] for r in P
                                if r["flip"] and r["f"].get(nm) is not None]
                           for nm, _d in FEATS}
        for tau, px, sz in LOSS_BUYS:
            sec = LOSS_CLOSE - tau
            r_ = tau - 1
            spot = ix.val(sec)
            lock = 0.0
            got = 0
            for s in range(LOSS_CLOSE - 60, sec + 1):
                x = ix.val(s)
                if x is not None:
                    lock += x
                    got += 1
            want = sec - (LOSS_CLOSE - 60) + 1
            if spot is None or got < want:
                out.append(f"\n**tau {tau}: tape incomplete "
                           f"({got}/{want} locked prints) -- NOT reported.**")
                continue
            mu = (lock + r_ * spot) / 60.0
            req = (60.0 / r_) * (LOSS_K_EFF - mu)
            s300 = ix.sigma(sec, 300)
            fake = {"sr": "KXNEAR15M", "sec": sec, "req": req, "r": r_,
                    "sig": s300, "s30": ix.sigma(sec, 30),
                    "price": px, "spread": None, "size": None, "age_ms": None,
                    "tau": tau, "tk": "LIVE", "close": LOSS_CLOSE,
                    "side_yes": False, "flip": True}
            kept, _d = add_features([fake], {LOSS_INDEX: ix})
            if not kept:
                out.append(f"\n**tau {tau}: features unavailable -- "
                           f"NOT reported.**")
                continue
            f = kept[0]["f"]
            live[tau] = f
            out.append(f"\n### buy at tau {tau}s, NO @ {100*px:.1f}c x{sz}\n")
            out.append(f"recomputed here from the raw tape: locked sum over "
                       f"{got} prints, mu {mu:.6f}, required move {req:+.6f}, "
                       f"sigma_300 "
                       f"{'None' if s300 is None else round(s300, 8)}, "
                       f"model p(lose) "
                       f"{'None' if f['pmod'] is None else round(100*f['pmod'], 3)}"
                       f"%\n")
            out.append("| feature | live-loss value | pctile among P1 WINNERS "
                       "| pctile among P2 WINNERS | P1 winner median | "
                       "P1 loser median |")
            out.append("|---|---|---|---|---|---|")
            for nm, _d in FEATS:
                x = f.get(nm)
                if x is None:
                    out.append(f"| `{nm}` | unavailable | | | | |")
                    continue
                p1 = pct_rank(x, winners["P1"][nm])
                p2 = pct_rank(x, winners["P2"][nm])
                w = sorted(winners["P1"][nm])
                l_ = sorted(losers["P1"][nm])
                wm = w[len(w) // 2] if w else float("nan")
                lm = l_[len(l_) // 2] if l_ else float("nan")
                out.append(f"| `{nm}` | {x:.4g} | "
                           f"{'' if p1 is None else f'{100*p1:.1f}%'} | "
                           f"{'' if p2 is None else f'{100*p2:.1f}%'} | "
                           f"{wm:.4g} | {lm:.4g} |")

    # ---- IS ANY OF IT NEW? ----------------------------------------------
    out.append("\n---\n\n## Does any feature add anything the model does "
               "not already charge for?\n")
    out.append("\nEvery strong column above -- price, `z`, `pmod`, `lgap`, "
               "the range ratios -- is the same underlying fact (the strike is "
               "close relative to the noise) wearing a different hat, and the "
               "live rule ALREADY refuses trades on it via the 2% model gate. "
               "The only result that could change the rule is a feature that "
               "still separates losers with the model's own number held "
               "fixed. Each row below buckets the feature WITHIN quintiles of "
               "the conditioner and pools.\n")
    PAIRS = [("req_rng60", "z"), ("req_rng300", "z"), ("z", "req_rng60"),
             ("flat10", "z"), ("flat30", "z"), ("flat300", "z"),
             ("mx10_sig", "z"), ("mx60_sig", "z"), ("s30_s300", "z"),
             ("s300_sday", "z"), ("tau", "z"), ("spread", "z"),
             ("age_ms", "z"), ("price", "z"), ("gap", "z")]
    for tag, dsc, P in POPS:
        if tag not in ("P1", "P1_tau45+", "P2"):
            continue
        out.append(f"\n### {tag}\n")
        lcl = len({r["close"] for r in P if r["flip"]})
        if lcl < 30:
            out.append(f"\n**{lcl} loss-carrying closes -- below the floor. "
                       f"No claim.**\n")
        out.append("| feature | held fixed | rows | loss-closes | "
                   "top-bottom | 95% CI | MDE | permutation p |")
        out.append("|---|---|---|---|---|---|---|---|")
        for nm, sc in PAIRS:
            g = analyse_strat(P, nm, sc, nb=3, ns=5,
                              boots=max(400, a.boots // 2),
                              shufs=max(200, a.shufs // 2))
            if g is None:
                out.append(f"| `{nm}` | `{sc}` | too few | | NOT TESTED | | |")
                continue
            out.append(f"| `{nm}` | `{sc}` | {g['rows']:,} | "
                       f"{g['loss_closes']} | "
                       f"**{100*g['obs']:+.2f} pp** | "
                       f"[{100*g['ci'][0]:+.2f}, {100*g['ci'][1]:+.2f}] | "
                       f"{100*g['mde']:.2f} pp | {g['p_shuffle']:.4f} |")
            print(f"    STRAT {tag} {nm:12s}|{sc:10s} "
                  f"{100*g['obs']:+7.2f}pp  p {g['p_shuffle']:.4f}",
                  flush=True)

    # ---- WHAT A GATE WOULD COST ------------------------------------------
    out.append("\n---\n\n## What a gate would cost\n")
    out.append("\nOne TRADE per market -- the earliest second that clears the "
               "gates, which is what the live rule actually buys. P&L is cents "
               "per contract, fee included, at the price really on offer.\n")
    GATES = [
        ("flat10", True, "refuse when the last 10s were too flat", ()),
        ("flat30", True, "refuse when the last 30s were too flat", ()),
        ("mx30_sig", True, "refuse when a big 1s move already happened", ()),
        ("req_rng60", False,
         "refuse when the required move is small vs the 60s range", ()),
        ("z", False, "refuse when the model's own cushion is thin", ()),
        ("pmod", True, "TIGHTEN THE MODEL CEILING below the live 2%",
         (0.02, 0.01, 0.005, 0.002, 0.001)),
        ("price", True, "refuse when the price is too high", ()),
    ]
    PLIVE = [r for r in P2 if r["tau"] <= 30]
    for tag, P in (("P2 (live rule, tau 3-60)", P2),
                   ("PLIVE (live rule AND the live tau 3-30 window)", PLIVE),
                   ("P1 (wide)", P1)):
        trades = first_per_market(P)
        nl = sum(1 for t in trades if t["flip"])
        out.append(f"\n### {tag}: {len(trades):,} trades over "
                   f"{len({t['close'] for t in trades})} closes, "
                   f"{nl} of them losers, "
                   f"ungated P&L "
                   f"{sum(trade_pnl(t['price'], t['flip']) for t in trades):+.1f}c\n")
        if nl == 0:
            out.append("\nNo losers -- a gate can only cost here.\n")
        for nm, above, desc, fixed in GATES:
            vals = sorted(t["f"][nm] for t in trades
                          if t["f"].get(nm) is not None)
            if len(vals) < 50:
                out.append(f"\n**`{nm}`** -- fewer than 50 trades carry it, "
                           f"NOT TESTED.")
                continue
            qs = list(fixed) if fixed else [
                vals[int(q * (len(vals) - 1))]
                for q in ((0.5, 0.7, 0.8, 0.9, 0.95) if above
                          else (0.5, 0.3, 0.2, 0.1, 0.05))]
            # The FIRST buy is the one the entry study is about -- the one at
            # tau 22 and 96.2c, which the scale-in rule cannot explain.
            live_v = None
            for tau in sorted(live, reverse=True):
                if live[tau].get(nm) is not None:
                    live_v = live[tau][nm]
                    break
            if live_v is not None:
                qs.append(live_v)
            gs = gate_study(trades, nm, sorted(set(qs), reverse=not above),
                            refuse_above=above)
            out.append(f"\n**`{nm}` -- {desc}**  "
                       f"(refuse when {'>=' if above else '<='} threshold)\n")
            out.append("| threshold | trades refused | wins refused | "
                       "losses avoided | wins refused per loss avoided | "
                       "P&L change |")
            out.append("|---|---|---|---|---|---|")
            for rr in gs["rows"]:
                tagl = "  **<- the live loss's own value**" \
                    if live_v is not None and abs(rr["th"] - live_v) < 1e-12 \
                    else ""
                wpl = rr["wins_per_loss"]
                out.append(f"| {rr['th']:.4g}{tagl} | {rr['refused']:,} | "
                           f"{rr['wins_refused']:,} | "
                           f"{rr['losses_avoided']} | "
                           f"{'INF (no loss avoided)' if wpl == float('inf') else f'{wpl:.1f}'}"
                           f" | {rr['pnl_change']:+.1f}c |")

    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"\n  wrote {a.out}  ({time.time()-t0:.0f}s)")

    # machine-readable copies for the gate study
    jp = a.out.replace(".md", ".json")
    with open(jp, "w", encoding="utf-8") as fh:
        json.dump({t: {k: {kk: vv for kk, vv in v.items() if kk != "cuts"}
                       for k, v in r.items()} for t, r in results.items()},
                  fh, default=str, indent=1)
    fp = a.out.replace(".md", "_rows.jsonl")
    with open(fp, "w", encoding="utf-8", newline="\n") as fh:
        p2ids = {id(r) for r in P2}
        for r in P1:
            fh.write(json.dumps({
                "tk": r["tk"], "sr": r["sr"], "close": r["close"],
                "sec": r["sec"], "tau": r["tau"], "price": r["price"],
                "flip": r["flip"], "in_p2": id(r) in p2ids,
                "f": {k: v for k, v in r["f"].items()
                      if not k.startswith("_")},
            }) + "\n")
    lp = a.out.replace(".md", "_live.json")
    with open(lp, "w", encoding="utf-8") as fh:
        json.dump({str(k): {kk: vv for kk, vv in v.items()}
                   for k, v in live.items()}, fh, default=str, indent=1)
    print(f"  wrote {jp}\n  wrote {fp}\n  wrote {lp}")


if __name__ == "__main__":
    main()
