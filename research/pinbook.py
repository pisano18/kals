#!/usr/bin/env python3
# VERSION: 2026-09-08-pb1
"""pinbook.py -- does the ORDER BOOK carry information the live rule ignores?

Read-only. Places nothing, cancels nothing, writes nothing outside `results/`.

WHY THIS EXISTS

The live rule (pinrun.py) reads exactly two things off the book: the price on
the favoured side, and the size resting at that price (>= 1 contract). It also
refuses a book message older than 2000 ms -- but that is the age of OUR LAST
WEBSOCKET FRAME, a staleness guard on our own feed, NOT the age of the resting
level. Depth, spread, book imbalance and the level's own age are recorded in
results/pindata/rows.jsonl and enter no decision at all.

The obvious test -- do these features predict a flip on the trades we take --
is IMPOSSIBLE, because there are ZERO flips in the eligible tau 3-30 sample.
So this file tests them against four things that DO vary:

  1  PRICE IMPROVEMENT.  At the first moment a close becomes tradeable, does
     book state predict that a cheaper price arrives later in the same close?
     A yes is a direct profit lever: wait when the book says wait.
  2  FILL RISK.  4 of 16 live orders came back "canceled" with no fill.
     Reconciled against the live log, plus a large-sample QUOTE-PERSISTENCE
     PROXY from the tape (does the offer survive one more second?).
  3  FLIPS ON THE WIDER SAMPLE.  The full table has 28,479 rows and 1,506
     flips at wider tau and cheaper prices. Flip rate there runs from 0.19%
     (tau<10) to 7.45% (tau 60) and from 0.58% (price ~1.00) to 40% (price
     ~0.50), so ANY test must hold price and tau fixed or it will simply
     rediscover them.
  4  THE EXCEEDANCE TAIL.  Is a thin or wide book a warning that the index is
     about to jump? Measured as the standardised forward index move over the
     next 5 seconds, one observation per (series, second).

METHOD, AND WHY EACH PIECE IS THERE

  * Stratum fixed effects on price x tau. Book state correlates with both, and
    both drive every outcome here. Without the strata this file would report
    "thin books flip more" and mean "cheap late markets flip more".
  * Cluster-robust covariance on CLOSE TIME. Nine series settle on the same
    quarter hour at rho ~ 0.8; rows are one per second within a market. Both
    correlations live inside a close.
  * MDE BEFORE THE ESTIMATE. The minimum detectable effect is computed from
    the null model -- the outcome with the features excluded -- so it does not
    depend on the answer. "No effect" and "no power" are different results.
  * CLUSTER SIGN-FLIP RANDOMISATION as the control and the p-value. Flipping
    the sign of every row in a close leaves X'X and the within-close structure
    untouched, so beta* = (X'X)^-1 sum_g s_g X_g'y_g and the cluster-robust
    score is s_g A_g - B_g beta* -- both computable from quantities cached
    once. That makes an exact 5,000-draw randomisation test cost less than a
    single extra regression, and it is the random-sign control the repo
    requires. A cruder LABEL SHUFFLE is run alongside: it must find nothing.
  * MULTIPLE LOOKS. Five features are tested. The randomisation distribution
    of max_j |t_j| is reported, and that is the threshold a single feature
    must clear, not 1.96.

FEATURE DEFINITIONS -- note the second one, it is easy to misread

  size     contracts resting AT the price we would pay, on the side we take
  dep_y/n  NOT the top three PRICE levels. pindata.Book.depth sums the three
           LARGEST resting sizes on that side at ANY price. It is a thickness
           measure, not a ladder measure, and is used here as one.
  spread   1 - no_bid - yes_bid, in cents
  age_ms   how long the level we would take has rested, from the delta stream

  take  = the side we BUY FROM (dep_n when we want YES: a NO bid is the offer
          of YES). join = the crowd bidding the same side as us.
  imb   = (join - take) / (join + take), in [-1, +1].

NOTHING HERE PLACES AN ORDER.
"""
import argparse
import glob
import json
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor                                  # noqa: E402

ND = NormalDist()
ROWS = os.path.join(os.path.dirname(HERE), "results", "pindata", "rows.jsonl")
LIVE = os.path.join(os.path.dirname(HERE), "results")

# --- the live rule, copied from pinrun.py so this file states its own gate ---
PIN = 0.98
TAU_MIN, TAU_MAX = 3, 30
EDGE_FLOOR = 0.003
EV_FLOOR = 0.003
PRICE_CEILING = 0.988
MEASURED_FLIP = 0.0090
IMPROVE_BY = 0.005
MIN_LEVEL = 1.0

FEATS = ("lsize", "lspread", "ldep", "imb", "lage")
FEATLABEL = {
    "lsize": "log10 size at touch",
    "lspread": "spread (cents)",
    "ldep": "log10 total top-3 depth",
    "imb": "book imbalance toward us",
    "lage": "log10 level age (ms)",
    "lpfail": "log10 model failure prob",
    "act_jump": "index jumped in last 30s",
    "act_tr5": "|5s transient| (sigmas)",
    "act_dr15": "|15s drift| (sigmas)",
    "act_s30": "log10 sigma_30 / sigma_300",
    "back3": "|PAST 5s z| > 3 (0/1)",
}
# The index's OWN recent activity. Any book feature that predicts a forward
# index jump has to beat these, or it is a proxy for volatility clustering
# rather than information sitting in the book.
ACT = ("act_jump", "act_tr5", "act_dr15", "act_s30")
Z975, Z80 = 1.959964, 0.8416212     # two-sided 5%, 80% power
MDE_MULT = Z975 + Z80


# ===========================================================================
# linear algebra (stdlib only)
# ===========================================================================
def _inv(A):
    n = len(A)
    M = [list(A[i]) + [1.0 if i == j else 0.0 for j in range(n)]
         for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-13:
            raise ValueError("singular normal matrix")
        M[c], M[piv] = M[piv], M[c]
        d = M[c][c]
        M[c] = [v / d for v in M[c]]
        for r in range(n):
            if r != c:
                f = M[r][c]
                if f:
                    M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    return [row[n:] for row in M]


def _mv(A, v):
    return [sum(a * b for a, b in zip(row, v)) for row in A]


def _outer_add(M, v):
    n = len(v)
    for i in range(n):
        vi = v[i]
        Mi = M[i]
        for j in range(n):
            Mi[j] += vi * v[j]


# ===========================================================================
# the estimator
# ===========================================================================
class ClusterFit:
    """OLS with stratum fixed effects absorbed and cluster-robust covariance.

    Caches, per cluster g, A_g = X_g' y_g and B_g = X_g' X_g. Those two are
    everything the sign-flip randomisation needs, which is why it is cheap.
    """

    def __init__(self, y, X, cluster, absorbed=0):
        self.n = len(y)
        self.k = len(X[0]) if X else 0
        self.absorbed = absorbed
        groups = defaultdict(list)
        for i, g in enumerate(cluster):
            groups[g].append(i)
        self.G = len(groups)
        k = self.k
        self.A, self.B = [], []
        XtX = [[0.0] * k for _ in range(k)]
        Xty = [0.0] * k
        for g in sorted(groups, key=repr):
            idxs = groups[g]
            Ag = [0.0] * k
            Bg = [[0.0] * k for _ in range(k)]
            for i in idxs:
                xi, yi = X[i], y[i]
                for a in range(k):
                    Ag[a] += xi[a] * yi
                    xa = xi[a]
                    Bga = Bg[a]
                    for b in range(k):
                        Bga[b] += xa * xi[b]
            self.A.append(Ag)
            self.B.append(Bg)
            for a in range(k):
                Xty[a] += Ag[a]
                for b in range(k):
                    XtX[a][b] += Bg[a][b]
        self.XtX, self.Xty = XtX, Xty
        self.XtXi = _inv(XtX)
        self.beta = _mv(self.XtXi, Xty)
        # small-sample correction, Cameron-Gelbach-Miller
        kk = k + absorbed
        self.corr = (self.G / max(self.G - 1.0, 1.0)) * \
                    ((self.n - 1.0) / max(self.n - kk, 1.0))
        self.se = self._se(self.beta, [1.0] * self.G)
        self.t = [b / s if s > 0 else 0.0 for b, s in zip(self.beta, self.se)]

    def _se(self, beta, signs):
        k = self.k
        meat = [[0.0] * k for _ in range(k)]
        for gi in range(self.G):
            Ag, Bg, s = self.A[gi], self.B[gi], signs[gi]
            Bb = _mv(Bg, beta)
            _outer_add(meat, [s * Ag[a] - Bb[a] for a in range(k)])
        tmp = [[sum(self.XtXi[a][m] * meat[m][b] for m in range(k))
                for b in range(k)] for a in range(k)]
        out = []
        for a in range(k):
            v = sum(tmp[a][m] * self.XtXi[m][a] for m in range(k)) * self.corr
            out.append(math.sqrt(v) if v > 0 else 0.0)
        return out

    # -- MDE from the null model: outcome with the features excluded --------
    def null_se(self):
        k = self.k
        meat = [[0.0] * k for _ in range(k)]
        for Ag in self.A:
            _outer_add(meat, Ag)
        tmp = [[sum(self.XtXi[a][m] * meat[m][b] for m in range(k))
                for b in range(k)] for a in range(k)]
        out = []
        for a in range(k):
            v = sum(tmp[a][m] * self.XtXi[m][a] for m in range(k)) * self.corr
            out.append(math.sqrt(v) if v > 0 else 0.0)
        return out

    # -- cluster sign-flip randomisation ------------------------------------
    def signflip(self, B=5000, seed=12345):
        rng = random.Random(seed)
        k = self.k
        obs = [abs(v) for v in self.t]
        obsmax = max(obs) if obs else 0.0
        ge = [0] * k
        gemax = 0
        for _ in range(B):
            s = [1.0 if rng.random() < 0.5 else -1.0 for _ in range(self.G)]
            Xty = [0.0] * k
            for gi in range(self.G):
                Ag, sg = self.A[gi], s[gi]
                for a in range(k):
                    Xty[a] += sg * Ag[a]
            bstar = _mv(self.XtXi, Xty)
            sestar = self._se(bstar, s)
            tst = [abs(bstar[a] / sestar[a]) if sestar[a] > 0 else 0.0
                   for a in range(k)]
            for a in range(k):
                if tst[a] >= obs[a] - 1e-12:
                    ge[a] += 1
            if max(tst) >= obsmax - 1e-12:
                gemax += 1
        p = [(1 + ge[a]) / (B + 1.0) for a in range(k)]
        return p, (1 + gemax) / (B + 1.0)


def absorb(y, X, strata):
    """Demean the outcome and every column within stratum. Returns the
    number of strata absorbed so the df correction can account for them."""
    k = len(X[0])
    tot = defaultdict(lambda: [0.0] * (k + 1))
    cnt = defaultdict(int)
    for i, s in enumerate(strata):
        t = tot[s]
        t[0] += y[i]
        xi = X[i]
        for a in range(k):
            t[a + 1] += xi[a]
        cnt[s] += 1
    yo, Xo = [0.0] * len(y), []
    for i, s in enumerate(strata):
        t, c = tot[s], cnt[s]
        yo[i] = y[i] - t[0] / c
        Xo.append([X[i][a] - t[a + 1] / c for a in range(k)])
    return yo, Xo, len(cnt)


def standardise(X):
    """Unit-sd columns so every coefficient reads 'per 1 sd of the feature'."""
    n, k = len(X), len(X[0])
    sds = []
    for a in range(k):
        m = sum(r[a] for r in X) / n
        v = sum((r[a] - m) ** 2 for r in X) / max(n - 1, 1)
        sds.append(math.sqrt(v) if v > 1e-30 else 1.0)
    return [[r[a] / sds[a] for a in range(k)] for r in X], sds


def run_panel(name, y, Xall, strata, cluster, cols, B=5000, seed=1,
              unit="pp", scale=100.0, quiet=False):
    """Univariate then joint, with MDE first, then estimate, then controls."""
    y0, X0, nstr = absorb(y, Xall, strata)
    X0, _ = standardise(X0)
    out = {"name": name, "n": len(y), "clusters": len(set(cluster)),
           "strata": nstr, "base": sum(y) / len(y), "uni": {}, "joint": {}}
    if not quiet:
        print("\n  " + name)
        print(f"    n = {len(y):,} rows   closes (clusters) = "
              f"{len(set(cluster))}   strata = {nstr}   "
              f"outcome mean = {scale*sum(y)/len(y):.3f} {unit}")
        if len(set(cluster)) < 30:
            print("    FEWER THAN 30 CLUSTERS -- inference below is not "
                  "claimed at any level.")
        print(f"    {'feature':<26} {'MDE':>8} {'est':>9} {'t':>7} "
              f"{'p_rand':>8}")
    for a, c in enumerate(cols):
        Xu = [[r[a]] for r in X0]
        f = ClusterFit(y0, Xu, cluster, absorbed=nstr)
        mde = MDE_MULT * f.null_se()[0]
        p, _ = f.signflip(B=B, seed=seed + a)
        out["uni"][c] = {"mde": mde * scale, "beta": f.beta[0] * scale,
                         "t": f.t[0], "p": p[0]}
        if not quiet:
            print(f"    {FEATLABEL.get(c, c):<26} {mde*scale:8.3f} "
                  f"{f.beta[0]*scale:+9.3f} {f.t[0]:+7.2f} {p[0]:8.4f}")
    fj = ClusterFit(y0, X0, cluster, absorbed=nstr)
    mdej = [MDE_MULT * s for s in fj.null_se()]
    pj, pmax = fj.signflip(B=B, seed=seed + 900)
    if not quiet:
        print(f"    -- all {len(cols)} together --")
        for a, c in enumerate(cols):
            print(f"    {FEATLABEL.get(c, c):<26} {mdej[a]*scale:8.3f} "
                  f"{fj.beta[a]*scale:+9.3f} {fj.t[a]:+7.2f} {pj[a]:8.4f}")
        print(f"    multiple-looks: p(max|t| over {len(cols)} features) = "
              f"{pmax:.4f}   [max|t| observed "
              f"{max(abs(v) for v in fj.t):.2f}]")
    for a, c in enumerate(cols):
        out["joint"][c] = {"mde": mdej[a] * scale, "beta": fj.beta[a] * scale,
                           "t": fj.t[a], "p": pj[a]}
    out["pmax"] = pmax
    # crude control: destroy the row-level link entirely
    rng = random.Random(seed + 77)
    ysh = list(y)
    rng.shuffle(ysh)
    ys0, _, _ = absorb(ysh, Xall, strata)
    fs = ClusterFit(ys0, X0, cluster, absorbed=nstr)
    out["shuffle_maxt"] = max(abs(v) for v in fs.t)
    if not quiet:
        print("    CONTROL, labels shuffled across rows: max|t| = "
              f"{out['shuffle_maxt']:.2f} (must be small)")
    return out


# ===========================================================================
# data
# ===========================================================================
def billed_fee(p, n=1):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def derive(r):
    """Attach the model's own view and the book features. No lookahead: every
    field used here was computed from data at or before r['sec']."""
    rr = int(r["r"])
    sd = r["sig"] * math.sqrt(var_factor(rr, [1.0])) if rr > 0 else 0.0
    if sd <= 0:
        fair = 1.0 if r["req"] <= 0 else 0.0
    else:
        fair = ND.cdf(-r["req"] / (sd * (60.0 / rr)))
    r["fair"] = fair
    pw = fair if r["side_yes"] else 1.0 - fair
    r["pw"] = pw
    p = r["price"]
    r["edge"] = pw - p - billed_fee(p, 1)
    r["ev"] = (1 - MEASURED_FLIP) * (1 - p) - MEASURED_FLIP * p - billed_fee(p)
    take = r["dep_n"] if r["side_yes"] else r["dep_y"]
    join = r["dep_y"] if r["side_yes"] else r["dep_n"]
    r["take"], r["join"] = take, join
    tot = take + join
    r["imb"] = (join - take) / tot if tot > 0 else 0.0
    r["lsize"] = math.log10(1.0 + r["size"])
    r["ldep"] = math.log10(1.0 + tot)
    r["lspread"] = 100.0 * (r["spread"] if r["spread"] is not None else 0.0)
    r["lage"] = math.log10(1.0 + max(r["age_ms"], 0))
    r["act_jump"] = float(r.get("jump") or 0)
    r["act_tr5"] = abs(r.get("tr5") or 0.0)
    r["act_dr15"] = abs(r.get("dr15") or 0.0)
    s30, sg = r.get("s30") or 0.0, r["sig"]
    r["act_s30"] = math.log10((s30 + 1e-12) / (sg + 1e-12)) if sg > 0 else 0.0
    return r


def eligible(r):
    """The live rule as of v7, applied to a replayed row."""
    return (TAU_MIN <= r["tau"] <= TAU_MAX and r["pw"] >= PIN
            and r["edge"] >= EDGE_FLOOR and r["price"] <= PRICE_CEILING
            and r["ev"] >= EV_FLOOR and r["size"] >= MIN_LEVEL)


def stratum(r):
    p = r["price"]
    pb = (0 if p < 0.70 else 1 if p < 0.80 else 2 if p < 0.90 else
          3 if p < 0.95 else 4 if p < 0.98 else 5)
    tb = min(int(r["tau"] // 10), 5)
    return (pb, tb)


def stratum_sr(r):
    """Same strata, split by SERIES as well. SOL's index repeats the previous
    print 70.5% of the time and ZEC's 0.07%; if those coins also carry
    systematically older books, a cross-series difference would masquerade as
    a within-market signal. This is the check that separates the two."""
    return stratum(r) + (r["sr"],)


def load(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(derive(json.loads(line)))
    return rows


# ===========================================================================
# TEST 1 -- price improvement
# ===========================================================================
def build_improve(rows):
    """One observation per (market, close): the FIRST tradeable moment, and
    whether a genuinely cheaper tradeable price arrived later in that market."""
    bym = defaultdict(list)
    for r in rows:
        bym[r["tk"]].append(r)
    obs = []
    for tk in sorted(bym):
        rs = sorted(bym[tk], key=lambda r: r["sec"])
        el = [r for r in rs if eligible(r)]
        if not el:
            continue
        first = el[0]
        later = [r for r in el[1:] if r["sec"] > first["sec"]]
        best_later = min((r["price"] for r in later), default=None)
        improved = (best_later is not None
                    and best_later <= first["price"] - IMPROVE_BY)
        gain = 0.0 if best_later is None else max(
            0.0, first["price"] - best_later)
        obs.append({"row": first, "improved": 1.0 if improved else 0.0,
                    "gain_c": 100.0 * gain, "n_later": len(later),
                    "best_later": best_later})
    return obs


# ===========================================================================
# TEST 2 -- fill risk
# ===========================================================================
def live_orders(resdir):
    """Pair each live `order` with the `signal` that produced it."""
    out = []
    for f in sorted(glob.glob(os.path.join(resdir, "pinrun-live-*.jsonl"))):
        pending = {}
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("kind") == "signal":
                pending[d.get("ticker")] = d
            elif d.get("kind") == "order":
                s = pending.pop(d.get("ticker"), None)
                out.append({"file": os.path.basename(f), "sig": s, "ord": d})
    return out


def persistence(rows):
    """LARGE-SAMPLE PROXY for fill risk, and it is a proxy, not a fill.

    At an eligible second, is the same market still offering our side at a
    price no worse than the one we saw, one second later? A vanished offer is
    the thing that turns an IOC into a cancel. It is NOT the same measurement:
    our order lands in ~100 ms, not 1,000 ms, and a row is only emitted when a
    delta arrived AND an offer existed, so an absent row conflates 'quote
    gone' with 'book quiet'. Base rates are reported for both readings."""
    idx = {}
    for r in rows:
        idx[(r["tk"], r["sec"])] = r
    obs = []
    for r in rows:
        if not eligible(r):
            continue
        nxt = idx.get((r["tk"], r["sec"] + 1))
        why = None
        if nxt is None:
            gone = None
        elif nxt["side_yes"] != r["side_yes"]:
            gone, why = 1.0, "side_changed"
        elif nxt["price"] > r["price"]:
            gone, why = 1.0, "price_worse"
        elif nxt["size"] < MIN_LEVEL:
            gone, why = 1.0, "dust"
        else:
            gone, why = 0.0, "still_there"
        obs.append({"row": r, "gone": gone, "have_next": nxt is not None,
                    "why": why,
                    "worse_c": (100.0 * (nxt["price"] - r["price"])
                                if nxt is not None else None)})
    return obs


# ===========================================================================
# out-of-sample evaluation: fit on the earlier half of closes, score the later
# ===========================================================================
def oos_quartiles(y, X, strata, cluster, times):
    """Split on CLOSE TIME, fit on the earlier half, rank the later half.

    In-sample fitted values always separate; the only question that matters is
    whether the ranking survives on closes the fit never saw. Stratum means
    come from the training half only, so no test-half information leaks in."""
    order = sorted(set(times))
    cut = order[len(order) // 2]
    tr = [i for i in range(len(y)) if times[i] < cut]
    te = [i for i in range(len(y)) if times[i] >= cut]
    if len(tr) < 50 or len(te) < 50:
        return None
    k = len(X[0])
    tot = defaultdict(lambda: [0.0] * (k + 1))
    cnt = defaultdict(int)
    for i in tr:
        t = tot[strata[i]]
        t[0] += y[i]
        for a in range(k):
            t[a + 1] += X[i][a]
        cnt[strata[i]] += 1
    ytr = [y[i] - tot[strata[i]][0] / cnt[strata[i]] for i in tr]
    Xtr = [[X[i][a] - tot[strata[i]][a + 1] / cnt[strata[i]]
            for a in range(k)] for i in tr]
    Xtr, sds = standardise(Xtr)
    f = ClusterFit(ytr, Xtr, [cluster[i] for i in tr], absorbed=len(cnt))
    scored = []
    for i in te:
        s = strata[i]
        if s not in cnt:
            continue
        xb = sum(f.beta[a] * (X[i][a] - tot[s][a + 1] / cnt[s]) / sds[a]
                 for a in range(k))
        scored.append((xb, y[i], tot[s][0] / cnt[s]))
    if len(scored) < 40:
        return None
    scored.sort()
    q = len(scored) // 4
    out = []
    for j in range(4):
        lo = j * q
        hi = (j + 1) * q if j < 3 else len(scored)
        cell = scored[lo:hi]
        out.append({"n": len(cell),
                    "raw": sum(c[1] for c in cell) / len(cell),
                    "adj": sum(c[1] - c[2] for c in cell) / len(cell)})
    return {"train": len(tr), "test": len(scored), "cut": cut, "q": out}


# ===========================================================================
# TEST 4 -- forward index jump
# ===========================================================================
def build_jump(rows, k=5):
    """One observation per (series, second): the standardised index move over
    the next k seconds. Deduped because nine markets share one index and the
    move is a property of the index, not of any one market."""
    spot = {}
    for r in rows:
        spot[(r["sr"], r["sec"])] = r["spot"]
    best = {}
    for r in rows:
        key = (r["sr"], r["sec"])
        cur = best.get(key)
        if cur is None or r["tau"] < cur["tau"]:
            best[key] = r
    obs, missing = [], 0
    for key in sorted(best):
        sr, sec = key
        r = best[key]
        s1 = spot.get((sr, sec + k))
        if s1 is None:
            missing += 1
            continue
        if r["sig"] <= 0:
            continue
        z = (s1 - r["spot"]) / (r["sig"] * math.sqrt(k))
        # THE BACKWARD-LOOKING COMPANION the repo requires. A jump reprices the
        # book, so book state MUST relate to the move that just happened. If it
        # does not, the estimator has no power on this population and the
        # forward null would be uninterpretable.
        s0 = spot.get((sr, sec - k))
        zb = ((r["spot"] - s0) / (r["sig"] * math.sqrt(k))
              if s0 is not None else None)
        obs.append({"row": r, "z": z, "ex3": 1.0 if abs(z) > 3 else 0.0,
                    "ex2": 1.0 if abs(z) > 2 else 0.0,
                    "back3": None if zb is None else (1.0 if abs(zb) > 3
                                                      else 0.0)})
    return obs, missing


# ===========================================================================
# small helpers used by the fill-risk reconciliation
# ===========================================================================
def _perm_diff(a, b, seed=0, B=20000):
    """Two-sided permutation p on the difference of means. Makes no
    normality claim, which matters at n = 12 vs 4."""
    obs = abs(sum(a) / len(a) - sum(b) / len(b))
    pool = list(a) + list(b)
    na = len(a)
    rng = random.Random(seed)
    ge = 0
    for _ in range(B):
        rng.shuffle(pool)
        d = abs(sum(pool[:na]) / na - sum(pool[na:]) / (len(pool) - na))
        if d >= obs - 1e-12:
            ge += 1
    return (1 + ge) / (B + 1.0)


def _two_prop_mde(n1, n2, p=0.25):
    """Smallest detectable difference in two proportions at 80% power."""
    if n1 < 1 or n2 < 1:
        return 1.0
    se = math.sqrt(p * (1 - p) * (1.0 / n1 + 1.0 / n2))
    return min(1.0, MDE_MULT * se)


# ===========================================================================
# SELF-TEST
# ===========================================================================
def _make_world(n_clusters, per, beta, seed, cx=0.35, cy=0.12):
    """A world with a KNOWN book->outcome relation.

    The cluster effect on the FEATURE and the cluster effect on the OUTCOME are
    drawn INDEPENDENTLY. That matters, and the first version of this file got
    it wrong: one shared cluster effect entering both makes the planted
    coefficient unidentified -- the regression correctly returns
    beta + var(u)/var(x), which was 0.128 against a planted 0.030, and the
    beta = 0 world was not null at all (4 of 4 'false positives' were a real
    confounded relation the estimator was right to find). Drawn separately, the
    feature is still cluster-correlated and the outcome still has cluster
    random effects -- so ignoring the clustering still over-rejects -- but the
    planted effect is the only link between them.
    """
    rng = random.Random(seed)
    y, X, strata, cl = [], [], [], []
    for g in range(n_clusters):
        ux = rng.gauss(0, cx)          # cluster effect on the FEATURE
        uy = rng.gauss(0, cy)          # cluster effect on the OUTCOME
        for _ in range(per):
            s = rng.randrange(4)
            x1 = rng.gauss(0, 1) + ux
            x2 = rng.gauss(0, 1)
            p = 0.45 + 0.03 * s + uy + beta * x1
            p = min(max(p, 0.02), 0.98)
            y.append(1.0 if rng.random() < p else 0.0)
            X.append([x1, x2])
            strata.append(s)
            cl.append(g)
    return y, X, strata, cl


def selftest():
    print("SELF-TEST -- pinbook")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # -- linear algebra ----------------------------------------------------
    A = [[4.0, 1.0], [1.0, 3.0]]
    I = _inv(A)
    prod = [[sum(A[i][m] * I[m][j] for m in range(2)) for j in range(2)]
            for i in range(2)]
    ck(abs(prod[0][0] - 1) < 1e-12 and abs(prod[0][1]) < 1e-12
       and abs(prod[1][1] - 1) < 1e-12, "matrix inverse is an inverse")

    # -- the model's own fair value ----------------------------------------
    r = derive({"r": 30, "sig": 1.0, "req": 0.0, "side_yes": True,
                "price": 0.9, "dep_n": 10.0, "dep_y": 30.0, "size": 5.0,
                "spread": 0.01, "age_ms": 999})
    ck(abs(r["fair"] - 0.5) < 1e-9, f"req = 0 is a coin flip ({r['fair']:.4f})")
    ck(abs(r["imb"] - 0.5) < 1e-12,
       f"join 30 vs take 10 gives imbalance +0.5 ({r['imb']})")
    r2 = derive({"r": 30, "sig": 1.0, "req": -10.0, "side_yes": True,
                 "price": 0.9, "dep_n": 1.0, "dep_y": 1.0, "size": 5.0,
                 "spread": 0.01, "age_ms": 0})
    ck(r2["fair"] > 0.99, "a large favourable required move prices near 1")
    ck(abs(r2["lage"]) < 1e-12, "a level born this instant has log-age 0")

    # -- fee, against a real charge in the operator's fill history ---------
    ck(abs(billed_fee(0.16, 12.37) - 0.1164) < 5e-5,
       "fee reproduces the real charge 12.37 @ 0.16 -> $0.1164")

    # -- PLANTED WORLD: the estimator must find what is there --------------
    y, X, st, cl = _make_world(60, 50, beta=0.100, seed=7)
    res = run_panel("planted", y, X, st, cl, ["lsize", "imb"], B=1200,
                    seed=3, quiet=True)
    b1 = res["uni"]["lsize"]["beta"] / 100.0
    p1 = res["uni"]["lsize"]["p"]
    ck(0.060 < b1 < 0.150, f"planted +0.100/sd recovered as {b1:+.4f}/sd")
    ck(p1 < 0.05, f"and it is significant (sign-flip p = {p1:.4f})")
    ck(res["uni"]["imb"]["p"] > 0.05,
       f"the UNPLANTED feature stays quiet (p = {res['uni']['imb']['p']:.4f})")
    ck(res["shuffle_maxt"] < 3.0,
       f"shuffling the labels kills it (max|t| = {res['shuffle_maxt']:.2f})")

    # -- NULL WORLD: it must find nothing ----------------------------------
    bad = 0
    for s in (11, 12, 13, 14):
        y0, X0, st0, cl0 = _make_world(60, 50, beta=0.0, seed=s)
        r0 = run_panel("null", y0, X0, st0, cl0, ["lsize", "imb"], B=800,
                       seed=100 + s, quiet=True)
        if r0["pmax"] < 0.05:
            bad += 1
    ck(bad == 0, f"four worlds with nothing planted: {bad} false positives")

    # -- the MDE must be honest about power --------------------------------
    ysm, Xsm, stsm, clsm = _make_world(35, 6, beta=0.100, seed=21)
    small = run_panel("tiny", ysm, Xsm, stsm, clsm, ["lsize"], B=400,
                      seed=5, quiet=True)
    big = res["uni"]["lsize"]["mde"]
    ck(small["uni"]["lsize"]["mde"] > big,
       f"a 210-row sample has a WORSE MDE than a 3,000-row one "
       f"({small['uni']['lsize']['mde']:.2f} vs {big:.2f} pp)")

    # -- clustering must actually cost something ---------------------------
    # cy is raised here on purpose: the inflation a clustered design causes is
    # rho_x * rho_y * (rows per cluster), so a world whose OUTCOME barely
    # clusters cannot demonstrate it. This world is still null -- ux and uy
    # remain independent -- it just clusters harder.
    y2, X2, st2, cl2 = _make_world(60, 50, beta=0.0, seed=31, cy=0.30)
    y2a, X2a, nstr = absorb(y2, X2, st2)
    X2a, _ = standardise(X2a)
    fc = ClusterFit(y2a, X2a, cl2, absorbed=nstr)
    fi = ClusterFit(y2a, X2a, list(range(len(y2a))), absorbed=nstr)
    ck(fc.se[0] > fi.se[0] * 1.2,
       f"cluster-robust se {fc.se[0]:.5f} exceeds the iid one "
       f"{fi.se[0]:.5f} when the feature is cluster-correlated")

    # -- sign-flip machinery must reproduce the analytic fit ---------------
    se_all_plus = fc._se(fc.beta, [1.0] * fc.G)
    ck(all(abs(a - b) < 1e-9 for a, b in zip(se_all_plus, fc.se)),
       "all-positive signs reproduce the observed standard errors exactly")

    # -- improvement extractor, planted and shuffled -----------------------
    rng = random.Random(5)
    rows = []
    for c in range(40):
        close = 1788000000 + 900 * c
        for m in range(6):
            tk = f"T{c}-{m}"
            thin = rng.random() < 0.5
            for tau in (25, 20, 15, 10):
                px = 0.93 - (0.02 if (thin and tau <= 15) else 0.0)
                rows.append(derive({
                    "tk": tk, "sr": "S", "close": close, "sec": close - tau,
                    "tau": tau, "r": tau - 1, "price": px,
                    "size": 5.0 if thin else 400.0, "spread": 0.01,
                    "dep_y": 50.0, "dep_n": 50.0, "age_ms": 500, "mu": 0.0,
                    "req": -50.0, "cov": 1.0, "spot": 100.0, "sig": 1.0,
                    "jump": 0, "hour": 0, "side_yes": True, "flip": False}))
    obs = build_improve(rows)
    ck(len(obs) == 240, f"one observation per market ({len(obs)})")
    got = sum(o["improved"] for o in obs) / len(obs)
    ck(0.35 < got < 0.65, f"about half the markets improve ({got:.2f})")
    yy = [o["improved"] for o in obs]
    XX = [[o["row"]["lsize"]] for o in obs]
    ss = [stratum(o["row"]) for o in obs]
    ccl = [o["row"]["close"] for o in obs]
    pr = run_panel("improve-planted", yy, XX, ss, ccl, ["lsize"], B=1000,
                   seed=9, quiet=True)
    ck(pr["uni"]["lsize"]["beta"] < 0 and pr["uni"]["lsize"]["p"] < 0.05,
       f"a planted thin-book-improves relation is found with the right sign "
       f"({pr['uni']['lsize']['beta']:+.2f} pp/sd, p = "
       f"{pr['uni']['lsize']['p']:.4f})")
    rng2 = random.Random(6)
    yshuf = list(yy)
    rng2.shuffle(yshuf)
    pr0 = run_panel("improve-shuffled", yshuf, XX, ss, ccl, ["lsize"], B=1000,
                    seed=10, quiet=True)
    ck(pr0["uni"]["lsize"]["p"] > 0.05,
       f"and nothing is found once the outcome is shuffled "
       f"(p = {pr0['uni']['lsize']['p']:.4f})")

    # -- forward-jump extractor -------------------------------------------
    jrows = []
    for s in range(200):
        jrows.append(derive({
            "tk": "J", "sr": "S", "close": 1788000000 + 100, "sec": 1000 + s,
            "tau": 30, "r": 29, "price": 0.9, "size": 3.0, "spread": 0.01,
            "dep_y": 5.0, "dep_n": 5.0, "age_ms": 10, "mu": 0.0,
            "req": -5.0, "cov": 1.0,
            "spot": 100.0 + (10.0 if s >= 100 else 0.0),
            "sig": 1.0, "jump": 0, "hour": 0, "side_yes": True,
            "flip": False}))
    jobs, miss = build_jump(jrows, k=5)
    hits = [o for o in jobs if o["ex3"] > 0]
    ck(len(hits) == 5 and all(1095 <= o["row"]["sec"] <= 1099 for o in hits),
       f"a +10 sigma step is flagged in exactly the 5 seconds before it "
       f"({len(hits)} flagged)")
    ck(miss == 5, f"the last 5 seconds have no forward window ({miss})")

    # -- the index-activity controls ---------------------------------------
    ra = derive({"r": 30, "sig": 2.0, "req": -1.0, "side_yes": True,
                 "price": 0.9, "dep_n": 1.0, "dep_y": 1.0, "size": 1.0,
                 "spread": 0.01, "age_ms": 0, "s30": 0.2, "tr5": -3.0,
                 "dr15": 2.0, "jump": 1})
    ck(abs(ra["act_s30"] - math.log10(0.1)) < 1e-6,
       f"sigma_30 a tenth of sigma_300 reads -1 ({ra['act_s30']:.4f})")
    ck(ra["act_tr5"] == 3.0 and ra["act_dr15"] == 2.0 and ra["act_jump"] == 1.0,
       "the activity controls are unsigned and the jump flag carries through")

    # -- out-of-sample ranking, planted and shuffled -----------------------
    rng3 = random.Random(17)
    yq, Xq, sq, cq = [], [], [], []
    for g in range(80):
        for _ in range(40):
            x = rng3.gauss(0, 1)
            yq.append(1.0 if rng3.random() < min(max(0.5 + 0.15 * x, 0.02),
                                                 0.98) else 0.0)
            Xq.append([x, rng3.gauss(0, 1)])
            sq.append(rng3.randrange(3))
            cq.append(1000 + g)
    oq = oos_quartiles(yq, Xq, sq, cq, cq)
    ck(oq is not None and oq["q"][0]["raw"] < oq["q"][3]["raw"] - 0.15,
       f"a planted relation still ranks out of sample "
       f"({100*oq['q'][0]['raw']:.0f}% vs {100*oq['q'][3]['raw']:.0f}%)")
    rng4 = random.Random(18)
    yshq = list(yq)
    rng4.shuffle(yshq)
    oq0 = oos_quartiles(yshq, Xq, sq, cq, cq)
    ck(oq0 is not None
       and abs(oq0["q"][0]["raw"] - oq0["q"][3]["raw"]) < 0.10,
       f"and a shuffled outcome does not "
       f"({100*oq0['q'][0]['raw']:.0f}% vs {100*oq0['q'][3]['raw']:.0f}%)")

    # -- the permutation helper --------------------------------------------
    ck(_perm_diff([1.0] * 8, [0.0] * 8, seed=1, B=2000) < 0.01,
       "a perfectly separated split gives a small permutation p")
    ck(_perm_diff([1.0, 0.0] * 4, [1.0, 0.0] * 4, seed=1, B=2000) > 0.5,
       "two identical groups give a large one")

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=ROWS)
    ap.add_argument("--results", default=LIVE)
    ap.add_argument("--boot", type=int, default=5000)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1":
        if not selftest():
            raise SystemExit("self-test failed -- refusing to touch real data")
    print()

    rows = load(a.rows)
    closes = sorted({r["close"] for r in rows})
    print("=" * 74)
    print("PINBOOK -- can the order book improve the decision?")
    print("=" * 74)
    print(f"  {len(rows):,} rows   {len({r['tk'] for r in rows}):,} markets   "
          f"{len(closes)} distinct closes   "
          f"{sum(1 for r in rows if r['flip']):,} flips")
    el = [r for r in rows if eligible(r)]
    print(f"  under the LIVE rule (tau {TAU_MIN}-{TAU_MAX}, pin {PIN}, edge "
          f"{EDGE_FLOOR}, ceiling {PRICE_CEILING}): {len(el):,} rows over "
          f"{len({r['close'] for r in el})} closes, "
          f"{sum(1 for r in el if r['flip'])} flips")
    print("  The four features under test are the ones the live rule ignores; "
          "`size`\n  is the one it already uses and is carried as a benchmark.")

    out = {}

    # ---------------- 1. price improvement ------------------------------
    print("\n" + "=" * 74)
    print("1. PRICE IMPROVEMENT -- does book state say a cheaper price is "
          "coming?")
    print("=" * 74)
    obs = build_improve(rows)
    nimp = int(sum(o["improved"] for o in obs))
    print(f"  {len(obs)} first-tradeable moments over "
          f"{len({o['row']['close'] for o in obs})} closes; {nimp} of them "
          f"({100.0*nimp/max(len(obs),1):.1f}%) saw a price at least "
          f"{100*IMPROVE_BY:.1f}c better later.")
    print(f"  mean best improvement, counting zeros: "
          f"{sum(o['gain_c'] for o in obs)/max(len(obs),1):.3f}c")
    if len(obs) >= 60:
        yb = [o["improved"] for o in obs]
        yg = [o["gain_c"] for o in obs]
        X = [[o["row"][c] for c in FEATS] for o in obs]
        st = [stratum(o["row"]) for o in obs]
        cl = [o["row"]["close"] for o in obs]
        out["improve_bin"] = run_panel(
            "P(a >=0.5c better price arrives later), pp per 1 sd",
            yb, X, st, cl, list(FEATS), B=a.boot, seed=11)
        out["improve_gain"] = run_panel(
            "size of the best later improvement, cents per 1 sd",
            yg, X, st, cl, list(FEATS), B=a.boot, seed=21,
            unit="cents", scale=1.0)
    else:
        print("  too few first-moments for a clustered test; the count above "
              "is all that is claimed.")

    # ---------------- 2. fill risk --------------------------------------
    print("\n" + "=" * 74)
    print("2. FILL RISK -- 4 of 16 live orders came back canceled")
    print("=" * 74)
    lo = live_orders(a.results)
    filled = [o for o in lo if float(o["ord"].get("filled") or 0) > 0]
    missed = [o for o in lo if float(o["ord"].get("filled") or 0) == 0]
    print(f"  live orders {len(lo)}   filled {len(filled)}   "
          f"no fill {len(missed)}")
    if lo:
        print(f"    {'ticker':<28} {'px':>7} {'size@touch':>11} "
              f"{'frame_ms':>9} {'tau':>4}  outcome")
        for o in lo:
            s = o["sig"] or {}
            print(f"    {o['ord'].get('ticker', ''):<28} "
                  f"{s.get('price', float('nan')):7.4f} "
                  f"{s.get('size', float('nan')):11.2f} "
                  f"{s.get('book_age_ms', -1):9d} {s.get('tau', -1):4d}  "
                  f"{o['ord'].get('status')}")
        for key, lab in (("size", "size resting at the touch"),
                         ("book_age_ms", "age of our own book frame (ms)"),
                         ("price", "price"), ("tau", "tau (s)"),
                         ("edge_c", "model edge (cents)")):
            fv = [o["sig"][key] for o in filled if o["sig"] and key in o["sig"]]
            mv = [o["sig"][key] for o in missed if o["sig"] and key in o["sig"]]
            if len(fv) >= 2 and len(mv) >= 2:
                print(f"    {lab:<32} filled {sum(fv)/len(fv):12.4f}   "
                      f"no-fill {sum(mv)/len(mv):12.4f}   permutation p = "
                      f"{_perm_diff(fv, mv, seed=4):.3f}")
        print(f"    MDE at {len(filled)} fills vs {len(missed)} misses: the "
              f"smallest miss-rate\n    difference detectable at 80% power is "
              f"about {100*_two_prop_mde(len(filled), len(missed)):.0f} "
              "percentage points. This is a\n    reconciliation, not a test.")

    print("\n  QUOTE-PERSISTENCE PROXY (large sample, and it is a proxy)")
    pobs = persistence(rows)
    have = [o for o in pobs if o["have_next"]]
    print(f"    {len(pobs):,} eligible moments; a row exists one second later "
          f"for {len(have):,} ({100.0*len(have)/max(len(pobs),1):.1f}%).")
    if have:
        gone = sum(o["gone"] for o in have)
        print(f"    of those, the offer was gone or worse {int(gone)} times = "
              f"{100.0*gone/len(have):.2f}%.")
        print("    treating a MISSING next row as gone instead: "
              f"{100.0*(gone + len(pobs) - len(have))/len(pobs):.2f}%.")
        print(f"    live miss rate for comparison: "
              f"{100.0*len(missed)/max(len(lo), 1):.1f}% "
              f"({len(missed)}/{len(lo)}).")
        why = defaultdict(int)
        for o in have:
            why[o["why"]] += 1
        print("    WHY it counts as gone -- the reading turns on this: "
              + ", ".join(f"{k} {v}" for k, v in sorted(why.items())))
        worse = sorted(o["worse_c"] for o in have if o["why"] == "price_worse")
        if worse:
            print(f"    when the price got worse it got worse by a median of "
                  f"{worse[len(worse)//2]:.2f}c "
                  f"(p10 {worse[len(worse)//10]:.2f}c, "
                  f"p90 {worse[9*len(worse)//10]:.2f}c). A one-tick drift "
                  "toward\n    1.00 counts here, so this is 'our limit would "
                  "not have filled', not 'the book emptied'.")
        if len({o["row"]["close"] for o in have}) >= 30:
            y = [o["gone"] for o in have]
            X = [[o["row"][c] for c in FEATS] for o in have]
            st = [stratum(o["row"]) for o in have]
            cl = [o["row"]["close"] for o in have]
            out["persist"] = run_panel(
                "P(the offer is gone one second later), pp per 1 sd",
                y, X, st, cl, list(FEATS), B=a.boot, seed=31)
            print("\n  ARTEFACT CHECK -- SERIES fixed effects added, so no "
                  "comparison is ever\n  between one coin and another:")
            out["persist_sr"] = run_panel(
                "P(the offer is gone one second later), series FE, pp per sd",
                y, X, [stratum_sr(o["row"]) for o in have], cl, list(FEATS),
                B=a.boot, seed=131)
            oq = oos_quartiles(y, X, st, cl, cl)
            if oq:
                print(f"\n    OUT OF SAMPLE -- fit on the {oq['train']:,} rows "
                      f"before close {oq['cut']}, rank the {oq['test']:,} "
                      "after it:")
                print(f"      {'quartile of predicted miss':<30} {'n':>6} "
                      f"{'miss rate':>11} {'vs stratum':>11}")
                for j, c in enumerate(oq["q"]):
                    print(f"      {'Q'+str(j+1)+(' (best book)' if j == 0 else ' (worst book)' if j == 3 else ''):<30} "
                          f"{c['n']:6d} {100*c['raw']:10.1f}% "
                          f"{100*c['adj']:+10.1f}pp")

    # ---------------- 3. flips on the wider sample ----------------------
    print("\n" + "=" * 74)
    print("3. FLIPS ON THE WIDER SAMPLE -- price and tau held fixed")
    print("=" * 74)
    y = [1.0 if r["flip"] else 0.0 for r in rows]
    X = [[r[c] for c in FEATS] for r in rows]
    st = [stratum(r) for r in rows]
    cl = [r["close"] for r in rows]
    out["flip"] = run_panel("P(the favoured side loses), pp per 1 sd",
                            y, X, st, cl, list(FEATS), B=a.boot, seed=41)
    for lab, cols in (("book imbalance alone", ["imb"]),
                      ("all five book features", list(FEATS))):
        oq = oos_quartiles(y, [[r[c] for c in cols] for r in rows], st, cl, cl)
        if oq:
            print(f"\n    OUT OF SAMPLE, ranked by {lab}: fit on the "
                  f"{oq['train']:,} rows before close\n    {oq['cut']}, rank "
                  f"the {oq['test']:,} after it.")
            for j, c in enumerate(oq["q"]):
                print(f"      Q{j+1}  n = {c['n']:6d}   flip rate "
                      f"{100*c['raw']:6.2f}%   vs its stratum "
                      f"{100*c['adj']:+6.2f}pp")
            print("      A quartile table carries no error bar. The clustered "
                  "regression above\n      does, and it is the one that "
                  "decides.")

    print("\n  The same test with the model's own probability added as a "
          "control, so a\n  feature has to beat the gaussian rather than "
          "merely agree with it:")
    lp = [[math.log10(min(max(1.0 - r["pw"], 1e-6), 1.0))] for r in rows]
    X2 = [x + l for x, l in zip(X, lp)]
    out["flip_ctrl"] = run_panel(
        "P(flip) controlling for log10 model failure probability, pp per 1 sd",
        y, X2, st, cl, list(FEATS) + ["lpfail"], B=a.boot, seed=51)

    # ---------------- 4. the exceedance tail ----------------------------
    print("\n" + "=" * 74)
    print("4. THE EXCEEDANCE TAIL -- is a thin or wide book a jump warning?")
    print("=" * 74)
    jobs, miss = build_jump(rows, k=5)
    print(f"  {len(jobs):,} (series, second) observations with a 5-second "
          f"forward window; {miss:,} had none.")
    if jobs:
        e3 = sum(o["ex3"] for o in jobs)
        e2 = sum(o["ex2"] for o in jobs)
        print(f"  realised |z| > 2 in {100.0*e2/len(jobs):.2f}% of them "
              f"(gaussian 4.55%), |z| > 3 in {100.0*e3/len(jobs):.2f}% "
              f"(gaussian 0.270%).")
        print("  An anchor against volcheck.py's 13.0M-cell measurement, not a "
              "re-derivation\n  of it: this is a 5-second forward move on the "
              "book-row grid, not the\n  settlement horizon.")
        if len({o["row"]["close"] for o in jobs}) >= 30:
            y = [o["ex3"] for o in jobs]
            X = [[o["row"][c] for c in FEATS] for o in jobs]
            st = [stratum(o["row"]) for o in jobs]
            cl = [o["row"]["close"] for o in jobs]
            out["jump"] = run_panel("P(|forward 5s z| > 3), pp per 1 sd",
                                    y, X, st, cl, list(FEATS), B=a.boot,
                                    seed=61)
            print("\n  WHAT WOULD HAVE TO BE TRUE FOR THAT TO BE AN ARTEFACT:"
                  "\n  volatility clusters, and a book level's age is a proxy "
                  "for how recently\n  the index moved -- a jump reprices the "
                  "book, so a fresh level and a\n  forthcoming jump would both "
                  "follow from the same recent activity, with no\n  "
                  "information in the book at all. So: the same test with the "
                  "index's OWN\n  recent activity added as controls. A book "
                  "feature that survives this is\n  carrying something the "
                  "index tape does not.")
            Xa = [[o["row"][c] for c in FEATS + ACT] for o in jobs]
            out["jump_ctrl"] = run_panel(
                "P(|forward 5s z| > 3) given recent index activity, pp per sd",
                y, Xa, st, cl, list(FEATS) + list(ACT), B=a.boot, seed=71)
            print("\n  SECOND ARTEFACT CHECK -- the same test with SERIES "
                  "fixed effects added,\n  so the comparison is between "
                  "markets of the same coin at the same price\n  and the same "
                  "tau, never between a step-function coin and a smooth one:")
            out["jump_sr"] = run_panel(
                "P(|forward 5s z| > 3), series fixed effects, pp per 1 sd",
                y, X, [stratum_sr(o["row"]) for o in jobs], cl, list(FEATS),
                B=a.boot, seed=81)
            bk = [o for o in jobs if o["back3"] is not None]
            if len(bk) >= 500:
                print("\n  BACKWARD-LOOKING COMPANION -- the move that ALREADY "
                      "happened. A jump\n  reprices the book, so this must be "
                      "large. A null here would mean the\n  estimator cannot "
                      "see anything on this population and the forward null\n"
                      "  above would say nothing.")
                out["jump_back"] = run_panel(
                    "P(|PAST 5s z| > 3), pp per 1 sd",
                    [o["back3"] for o in bk],
                    [[o["row"][c] for c in FEATS] for o in bk],
                    [stratum(o["row"]) for o in bk],
                    [o["row"]["close"] for o in bk],
                    list(FEATS), B=a.boot, seed=91)
                print("\n  THE DECIDING TEST. If the book carried FORWARD "
                      "information, the forward\n  relation would survive "
                      "conditioning on the move that already happened.\n  If "
                      "instead level age is a marker of an active regime, "
                      "conditioning on\n  the backward move should absorb most "
                      "of it -- the same coefficient in\n  both directions of "
                      "time is the signature of a regime, not a forecast.")
                out["jump_fwd_given_back"] = run_panel(
                    "P(|forward 5s z| > 3) given the PAST move, pp per 1 sd",
                    [o["ex3"] for o in bk],
                    [[o["row"][c] for c in FEATS] + [o["back3"]] for o in bk],
                    [stratum(o["row"]) for o in bk],
                    [o["row"]["close"] for o in bk],
                    list(FEATS) + ["back3"], B=a.boot, seed=101)

    print("\n" + "=" * 74)
    print("VERDICT")
    print("=" * 74)
    for k, v in out.items():
        best = max(v["uni"].items(), key=lambda kv: abs(kv[1]["t"]))
        print(f"  {v['name'][:70]}")
        print(f"     strongest single feature: "
              f"{FEATLABEL.get(best[0], best[0])}  est {best[1]['beta']:+.3f} "
              f"vs MDE {best[1]['mde']:.3f}, t {best[1]['t']:+.2f}, "
              f"p {best[1]['p']:.4f}; joint multiple-looks p {v['pmax']:.4f}")
    print("\n  A feature is worth adding only where its estimate exceeds its "
          "own MDE AND\n  the joint multiple-looks p-value is small. Anything "
          "else is noise with an\n  honest error bar around it.")


if __name__ == "__main__":
    main()
