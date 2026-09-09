#!/usr/bin/env python3
# VERSION: 2026-09-09-pc1
"""pinclose.py -- ARE WE PLAYING TOO CLOSE TO THE LINE?

THE OPERATOR'S QUESTION, VERBATIM: "Or is it a case of playing it too close to
the line? And perhaps we lose some gains by not bettering or buying hedges if
we near that?"

WHY THIS IS NOT THE ENTRY-GATE WORK ALREADY REFUTED. That work asked "does
feature X separate losers from winners once the model's own z is held fixed",
and every candidate came back p = 0.14-0.99. THIS file asks a different
question: is there an ABSOLUTE cushion -- a raw distance between the index and
the strike -- below which we should refuse to trade REGARDLESS of what the
model says, because at that scale the model's sigma is not a trustworthy
description of what the index can do in one second?

The distinction matters because the model's own z is |required move| / sd, and
sd is built from sigma. If sigma is the thing that breaks, then conditioning on
z cannot reveal it: z is already contaminated. A cushion measured WITHOUT
sigma -- distance in basis points, or distance divided by the index's own
realised RANGE -- is a genuinely different instrument.

THE THREE CUSHION MEASURES, and why each one is here:

  1. dist_bps = 10,000 * |spot - K_eff| / spot
     Absolute. Uses no volatility estimate at all. Pools across coins because
     it is a fraction of the coin's own price. Tonight's loss: 3.62 bps.

  2. cr_W = |spot - K_eff| / (realised range of the index over the last W s)
     The operator's own ratio, W in {60, 300, 900}. Uses the index's realised
     travel rather than a modelled sigma, so a step-function index that sits
     still and then jumps is scored by how far it ACTUALLY went, not by an RMS
     that a long flat stretch has already crushed. Tonight: 0.00085 / 0.01060
     = 0.080 at W = 300.

  3. z_model = req / sd -- the model's own number, carried as a CONTROL. Any
     claim that 1 or 2 adds information must survive holding this fixed.

WHAT IS MEASURED

  A. Flip rate by cushion bucket, on two populations, clustered on close.
  B. CLIFF OR SLOPE: a binned logistic fit that is smooth in log(cushion),
     against the best single-threshold step, compared by likelihood ratio with
     a PARAMETRIC BOOTSTRAP under the smooth model as the null. A smooth
     relationship means sizing; a cliff means a gate.
  C. THE COST of every candidate gate, in cents AND in WINS TO RECOVER --
     winners refused per loss avoided, profit destroyed, worst position, worst
     close.
  D. The same threshold used as a HEDGE trigger after entry instead of an
     entry gate.

TWO POPULATIONS, and the reason there are two:

  BOOK  results/pindata/rows.jsonl -- one row per moment somebody actually
        offered us the model-favoured side at a real price in real size. This
        is the RIGHT population (scoring moments nobody would sell us gives a
        flip rate ~90x too good) but it is 44 hours long and contains only a
        few dozen losing markets.
  INDEX built here from the index tape plus settled outcomes, on an EXOGENOUS
        tau grid, over every settled market on disk (~12 days). No prices, so
        it cannot cost a gate -- but it has ~9x the markets, so it is where the
        SHAPE question has any power at all.

THE HONEST LIMIT, STATED BEFORE ANY NUMBER: the loss events are few. The MDE
block printed above every table says what size of effect this sample could
have seen. A bucket table with three losers in it is not evidence of a cliff
and is not reported as one.
"""
import argparse
import array
import calendar
import glob
import gzip
import json
import math
import os
import random
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                       # noqa: E402
from statistics import NormalDist                          # noqa: E402
import pinhedge                                            # noqa: E402

ND = NormalDist()
DATA = r"C:\kals\kalshi_data"
FULLTAPE = r"C:\kals\fulltape\markets.json"
ROWS = r"C:\kals-repo\results\pindata\rows.jsonl"

SERIES_TO_INDEX = {
    "KXBTC15M": "BRTI", "KXETH15M": "ETHUSD_RTI", "KXSOL15M": "SOLUSD_RTI",
    "KXXRP15M": "XRPUSD_RTI", "KXDOGE15M": "DOGEUSD_RTI",
    "KXBNB15M": "BNBUSD_RTI", "KXZEC15M": "ZECUSD_RTI",
    "KXHYPE15M": "HYPEUSD_RTI", "KXNEAR15M": "NEARUSD_RTI",
}
ROUND_DIGITS = {"KXBTC15M": 2, "KXETH15M": 2, "KXBNB15M": 2,
                "KXSOL15M": 4, "KXXRP15M": 4, "KXZEC15M": 4,
                "KXHYPE15M": 4, "KXNEAR15M": 4, "KXDOGE15M": 7}

# pin's own live rule, so the cost section prices the gate against what we
# actually trade rather than against an invented strategy.
PIN_P = 0.02
CEILING = 0.988
EV_FLOOR = 0.003

BS = chr(92)                       # the tape stores msg.data as a JSON STRING
TKEY = BS + '"time' + BS + '":'
VKEY = BS + '"value' + BS + '":' + BS + '"'

CR_EDGES = (0.05, 0.10, 0.20, 0.40, 0.80)
BPS_EDGES = (2.0, 5.0, 10.0, 25.0, 60.0)


# ===========================================================================
# small arithmetic
# ===========================================================================
def eff_strike(k, d):
    return float(k) - 0.5 * (10.0 ** (-int(d))) if d is not None else float(k)


def k_from_row(r):
    """Recover K_eff from a pindata row. req = (60/rr)*(K - mu)."""
    return r["mu"] + r["req"] * r["r"] / float(N_AVG)


def model_sd(sig, rr):
    return sig * math.sqrt(var_factor(int(rr), [1.0])) * (float(N_AVG) / rr)


def model_pflip(req, sig, rr):
    """Model probability the FAVOURED side loses."""
    if sig is None or rr < 1:
        return None
    sd = model_sd(sig, rr)
    if sd <= 0:
        return 0.0 if req <= 0 else 1.0
    z = req / sd
    return (1 - ND.cdf(z)) if req > 0 else ND.cdf(z)


def bucket(v, edges):
    if v is None:
        return None
    for i, e in enumerate(edges):
        if v < e:
            return i
    return len(edges)


def bucket_labels(edges, fmt="{:.2f}"):
    out = ["< " + fmt.format(edges[0])]
    for i in range(len(edges) - 1):
        out.append(fmt.format(edges[i]) + "-" + fmt.format(edges[i + 1]))
    out.append(">= " + fmt.format(edges[-1]))
    return out


def pct_of(vals, q):
    """The q-th percentile of `vals` by nearest rank on the SORTED values.
    Used for the tail of the per-close P&L distribution, which is the shape
    the operator actually feels."""
    if not vals:
        return None
    v = sorted(vals)
    i = int(math.ceil(q * len(v))) - 1
    return v[max(0, min(len(v) - 1, i))]


def wins_to_recover(loss_c, mean_win_c):
    """The operator's unit. loss_c and mean_win_c are cents per contract."""
    if mean_win_c <= 0:
        return float("inf")
    return abs(loss_c) / mean_win_c


# ===========================================================================
# the index tape
# ===========================================================================
def index_files(lo_stamp=None, hi_stamp=None):
    fs = sorted(glob.glob(os.path.join(DATA, "cfbenchmarks_value",
                                       "2026*.jsonl.gz")))[:-1]
    if lo_stamp:
        fs = [f for f in fs if os.path.basename(f)[:11] >= lo_stamp]
    if hi_stamp:
        fs = [f for f in fs if os.path.basename(f)[:11] <= hi_stamp]
    return fs


def load_index(files, verbose=True):
    """{index_id: (base_second, array('d') with NaN holes)}.

    Pre-allocated from the file stamps rather than accumulated in dicts: at
    341 hours x 11 indices a dict-of-dicts is ~1.5 GB and this box has 2.4 GB
    free with a live trader on it.
    """
    if not files:
        return {}
    def stamp_epoch(f):
        b = os.path.basename(f)[:11]           # 20260904T12
        return calendar.timegm(time.strptime(b, "%Y%m%dT%H"))
    base = stamp_epoch(files[0])
    span = stamp_epoch(files[-1]) + 3600 - base
    out = {}
    t0 = time.time()
    for n, f in enumerate(files):
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    i = line.find('"index_id":"')
                    if i < 0:
                        continue
                    j = line.find('"', i + 12)
                    iid = line[i + 12:j]
                    k = line.find(TKEY, j)
                    if k < 0:
                        continue
                    k += len(TKEY)
                    e = line.find(',', k)
                    try:
                        sec = int(line[k:e]) // 1000
                    except ValueError:
                        continue
                    v = line.find(VKEY, e)
                    if v < 0:
                        continue
                    v += len(VKEY)
                    e2 = line.find(BS, v)
                    try:
                        val = float(line[v:e2])
                    except ValueError:
                        continue
                    p = sec - base
                    if 0 <= p < span:
                        a = out.get(iid)
                        if a is None:
                            a = out[iid] = array.array(
                                "d", [float("nan")]) * 1 if False else \
                                array.array("d", [float("nan")] * span)
                        a[p] = val
        except Exception:
            continue
        if verbose and (n + 1) % 50 == 0:
            print(f"    {n+1}/{len(files)} index hours  "
                  f"{time.time()-t0:.0f}s", flush=True)
    return {k: (base, v) for k, v in out.items()}


def realised_range(base, arr, sec, w):
    """max-min of the index over [sec-w+1, sec]. None if the window is holed."""
    i1 = sec - base
    i0 = i1 - w + 1
    if i0 < 0 or i1 >= len(arr):
        return None
    mn = float("inf")
    mx = float("-inf")
    got = 0
    for j in range(i0, i1 + 1):
        v = arr[j]
        if v == v:
            got += 1
            if v < mn:
                mn = v
            if v > mx:
                mx = v
    if got < 0.8 * w:
        return None
    return mx - mn


def sigma_at(base, arr, sec, w=300):
    i = sec - base
    if i - w < 0 or i >= len(arr):
        return None
    tot = k = 0
    for j in range(i - w, i + 1):
        a, b = arr[j - 1], arr[j]
        if a == a and b == b:
            d = b - a
            tot += d * d
            k += 1
    return math.sqrt(tot / k) if k >= 15 else None


# ===========================================================================
# binned logistic: smooth in log(cushion) vs the best single step
# ===========================================================================
def _solve(H, g):
    k = len(g)
    M = [row[:] + [g[i]] for i, row in enumerate(H)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-14:
            return None
        M[c], M[p] = M[p], M[c]
        pv = M[c][c]
        for r in range(k):
            if r == c:
                continue
            f = M[r][c] / pv
            for cc in range(c, k + 1):
                M[r][cc] -= f * M[c][cc]
    return [M[i][k] / M[i][i] for i in range(k)]


def logit_fit(X, n, y, iters=40):
    """Weighted binomial logistic on BINNED data. X rows are feature vectors,
    n[i] trials, y[i] successes. Returns (beta, loglik)."""
    k = len(X[0])
    b = [0.0] * k
    for _ in range(iters):
        g = [0.0] * k
        H = [[1e-7 if i == j else 0.0 for j in range(k)] for i in range(k)]
        for xi, ni, yi in zip(X, n, y):
            z = sum(b[j] * xi[j] for j in range(k))
            z = max(-30.0, min(30.0, z))
            p = 1.0 / (1.0 + math.exp(-z))
            r = yi - ni * p
            w = ni * p * (1 - p)
            for j in range(k):
                g[j] += r * xi[j]
                for m in range(k):
                    H[j][m] += w * xi[j] * xi[m]
        d = _solve(H, g)
        if d is None:
            break
        b = [b[j] + d[j] for j in range(k)]
        if max(abs(x) for x in d) < 1e-9:
            break
    ll = 0.0
    for xi, ni, yi in zip(X, n, y):
        z = max(-30.0, min(30.0, sum(b[j] * xi[j] for j in range(k))))
        p = 1.0 / (1.0 + math.exp(-z))
        p = min(max(p, 1e-12), 1 - 1e-12)
        ll += yi * math.log(p) + (ni - yi) * math.log(1 - p)
    return b, ll


def cliff_test(cells, nboot=200, seed=7):
    """cells: list of (logx, n, k) bins ordered by cushion.

    Fits  SMOOTH  logit(p) = a + b*logx
    and   STEP    logit(p) = a + b*logx + c*1[bin < j], best j
    Returns dict with the likelihood ratio, the chosen break, and a p-value
    from a PARAMETRIC BOOTSTRAP under the fitted smooth model -- the correct
    null for "is there a cliff BEYOND the trend", which a label permutation
    would not give because permutation also destroys the trend.
    """
    cells = [c for c in cells if c[1] > 0]
    if len(cells) < 4:
        return None
    lx = [c[0] for c in cells]
    nn = [c[1] for c in cells]
    kk = [c[2] for c in cells]
    Xs = [[1.0, v] for v in lx]
    bs, lls = logit_fit(Xs, nn, kk)

    def best_step(kv):
        best = (None, -1e18, None)
        for j in range(1, len(cells)):
            Xt = [[1.0, lx[i], 1.0 if i < j else 0.0]
                  for i in range(len(cells))]
            bt, llt = logit_fit(Xt, nn, kv)
            if llt > best[1]:
                best = (j, llt, bt)
        return best

    j0, llt0, bt0 = best_step(kk)
    _, lls0 = logit_fit(Xs, nn, kk)
    lr = 2.0 * (llt0 - lls0)

    rnd = random.Random(seed)
    ps = []
    for i in range(len(cells)):
        z = max(-30.0, min(30.0, bs[0] + bs[1] * lx[i]))
        ps.append(1.0 / (1.0 + math.exp(-z)))
    worse = 0
    for _ in range(nboot):
        sim = [sum(1 for _ in range(nn[i]) if rnd.random() < ps[i])
               if nn[i] < 4000 else
               int(round(nn[i] * ps[i] +
                         math.sqrt(nn[i] * ps[i] * (1 - ps[i]))
                         * rnd.gauss(0, 1)))
               for i in range(len(cells))]
        sim = [max(0, min(nn[i], sim[i])) for i in range(len(cells))]
        _, ll_s = logit_fit(Xs, nn, sim)
        _, ll_t, _ = best_step(sim)
        if 2.0 * (ll_t - ll_s) >= lr:
            worse += 1
    return {"lr": lr, "break": j0, "slope": bs[1], "p": (worse + 1) /
            (nboot + 1.0), "nboot": nboot}


# ===========================================================================
# clustered bootstrap over closes
# ===========================================================================
def cluster_rates(per_close, nb, nboot=400, seed=11):
    """per_close: {close: [ (n, k) per bucket ]}.  Returns point rates and the
    bootstrap sd of each bucket rate, resampling CLOSES with replacement."""
    keys = list(per_close)
    tot = [[0, 0] for _ in range(nb)]
    for c in keys:
        for b in range(nb):
            tot[b][0] += per_close[c][b][0]
            tot[b][1] += per_close[c][b][1]
    point = [(t[1] / t[0]) if t[0] else None for t in tot]
    rnd = random.Random(seed)
    draws = [[] for _ in range(nb)]
    for _ in range(nboot):
        s = [[0, 0] for _ in range(nb)]
        for _ in range(len(keys)):
            c = keys[rnd.randrange(len(keys))]
            for b in range(nb):
                s[b][0] += per_close[c][b][0]
                s[b][1] += per_close[c][b][1]
        for b in range(nb):
            if s[b][0]:
                draws[b].append(s[b][1] / s[b][0])
    sd = []
    for b in range(nb):
        d = draws[b]
        if len(d) < 20:
            sd.append(None)
            continue
        m = sum(d) / len(d)
        sd.append(math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1)))
    return point, sd, tot


# ===========================================================================
# SELF-TEST -- plant a cliff, plant a slope, plant nothing
# ===========================================================================
def selftest():
    print("SELF-TEST -- pinclose")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # ---- the strike recovery the whole file rests on --------------------
    mu, rr, K = 100.0, 20.0, 100.5
    req = (60.0 / rr) * (K - mu)
    ck(abs(k_from_row({"mu": mu, "req": req, "r": rr}) - K) < 1e-9,
       f"K_eff recovers from mu, req and r exactly "
       f"({k_from_row({'mu': mu, 'req': req, 'r': rr}):.6f} vs {K})")
    ck(abs(eff_strike(2.3492, 4) - 2.34915) < 1e-12,
       f"the rounded-settlement strike for a 4-digit coin is K - 0.00005 "
       f"({eff_strike(2.3492, 4):.5f}) -- this is tonight's 2.34915")

    # ---- realised range --------------------------------------------------
    a = array.array("d", [1.0, 1.0, 1.0, 1.5, 1.2, 1.0, 1.0, 1.0, 1.0, 1.0])
    ck(abs(realised_range(0, a, 9, 10) - 0.5) < 1e-12,
       f"range over a window that contains the spike is 0.5 "
       f"({realised_range(0, a, 9, 10)})")
    ck(abs(realised_range(0, a, 9, 4) - 0.0) < 1e-12,
       "and 0.0 over a window that does not -- which is exactly the failure "
       "mode: a flat 60 s says 'nothing can happen' one second before a jump")
    ck(realised_range(0, a, 9, 40) is None,
       "a window that runs off the start of the tape returns None, not a "
       "silently short range")

    # ---- the snapshot keys, which a previous class got wrong -------------
    _b = FpBook()
    _b.snapshot({"yes_dollars_fp": [["0.60", "100"]],
                 "no_dollars_fp": [["0.35", "80"]]})
    ck(_b.yes == {0.6: 100.0} and _b.no == {0.35: 80.0},
       "the snapshot is read from the *_fp keys the tape actually carries")
    ck(abs(_b.best_ask("yes")[0] - 0.65) < 1e-12
       and _b.best_ask("yes")[1] == 80.0,
       f"the YES ask is 1 - the best NO bid ({_b.best_ask('yes')[0]}) with "
       f"that level's size ({_b.best_ask('yes')[1]})")
    _b2 = FpBook()
    _b2.snapshot({"yes_dollars": [["0.60", "100"]],
                  "no_dollars": [["0.35", "80"]]})
    ck(_b2.yes == {} and _b2.no == {},
       "NULL: the OLD key names load nothing at all -- which is exactly the "
       "open bug this class exists to avoid, and it must stay visible")
    _b.delta("no", 0.35, -80.0)
    ck(_b.best_ask("yes") == (None, 0.0),
       "and emptying the other side leaves no ask rather than a stale one")

    # ---- the SIGN, which is the whole of section F -----------------------
    ck(signed_cushion(101.0, 100.0, True) > 0
       and signed_cushion(99.0, 100.0, True) < 0,
       "holding YES, above the strike is a cushion and below it is a deficit")
    ck(signed_cushion(101.0, 100.0, False) < 0
       and signed_cushion(99.0, 100.0, False) > 0,
       "holding NO the sign flips -- the cushion is always measured on the "
       "side we need")
    ck(abs(signed_cushion(2.34830, 2.34915, False) - 0.00085) < 1e-9,
       "tonight's entry: NO with the index 0.00085 BELOW the strike is a "
       "POSITIVE cushion of 0.00085")
    ck(abs(signed_cushion(2.35050, 2.34915, False) + 0.00135) < 1e-9,
       "and after the jump it is MINUS 0.00135 -- while the UNSIGNED gap "
       "grew from 0.00085 to 0.00135 and so looked safer")
    ck(first_cross([(22, 0.00085), (21, 0.00085), (17, 0.00075),
                    (16, -0.00135), (15, -0.0013)]) == 16,
       "planted CROSSING: found at tau 16, which is tonight's actual second")
    ck(first_cross([(22, 0.001), (21, 0.002), (16, 0.003)]) is None,
       "NULL: a path that never crosses returns None, not a spurious tau")
    _stay = [(20, 1.0, 0.001, 0.0), (19, 1.0, -0.001, 0.0),
             (18, 1.0, -0.002, 0.0), (17, 1.0, -0.002, 0.0),
             (16, 1.0, -0.003, 0.0)]
    _blip = [(20, 1.0, 0.001, 0.0), (19, 1.0, -0.001, 0.0),
             (18, 1.0, 0.002, 0.0), (17, 1.0, 0.003, 0.0),
             (16, 1.0, 0.004, 0.0)]
    ck(trigger_tau(_stay, 0) == 19 and trigger_tau(_stay, 2) == 17,
       f"planted PERSISTENT crossing: fires at tau 19 with no confirmation "
       f"and tau 17 after 2 s of it ({trigger_tau(_stay, 0)}, "
       f"{trigger_tau(_stay, 2)})")
    ck(trigger_tau(_blip, 0) == 19 and trigger_tau(_blip, 2) is None,
       "NULL: a one-second blip back over the line fires without confirmation "
       "and is correctly SUPPRESSED by 2 s of it -- the false-alarm control")

    # ---- the tail percentiles the operator actually feels ---------------
    _v = [-10.0, -9.0, -8.0, -7.0, -6.0, -5.0, -4.0, -3.0, -2.0, -1.0]         + [1.0] * 90
    ck(pct_of(_v, 0.01) == -10.0 and pct_of(_v, 0.05) == -6.0,
       f"planted TAIL: in 100 closes with ten losses the 1st percentile is "
       f"the worst ({pct_of(_v, 0.01)}) and the 5th is the fifth worst "
       f"({pct_of(_v, 0.05)})")
    ck(pct_of([-10.0, -5.0, -1.0] + [1.0] * 97, 0.05) == 1.0,
       "and with only THREE losses in 100 closes the 5th percentile is a "
       "WIN -- the tail is shallower than the worst case, which is the whole "
       "reason to print both")
    ck(pct_of([2.0] * 100, 0.01) == 2.0,
       "NULL: a world with no losses has a 1st percentile equal to the win, "
       "not a fabricated loss")
    ck(pct_of([], 0.05) is None, "and an empty sample returns None")

    # ---- wins to recover -------------------------------------------------
    ck(abs(wins_to_recover(-90.0, 3.0) - 30.0) < 1e-9,
       "a 90c loss against a 3c mean win costs 30 WINS to recover")
    ck(abs(wins_to_recover(-4.0, 4.0) - 1.0) < 1e-9,
       "and a loss the size of one win costs one win")

    # ---- PLANT A CLIFF ---------------------------------------------------
    # flip rate 12% below bin 3, 1% above. The estimator must find a break at
    # bin 3 and reject the smooth model.
    nb = 10
    cells_cliff = []
    for i in range(nb):
        p = 0.12 if i < 3 else 0.01
        n = 3000
        cells_cliff.append((math.log(0.03 * (1.6 ** i)), n, int(round(n * p))))
    r = cliff_test(cells_cliff, nboot=120, seed=3)
    ck(r is not None and r["break"] == 3,
       f"planted CLIFF at bin 3: estimator puts the break at "
       f"{None if r is None else r['break']}")
    ck(r is not None and r["p"] <= 0.05,
       f"and rejects the smooth model (p = {None if r is None else r['p']:.3f})")

    # ---- PLANT A SLOPE (smooth) -- the step must NOT win -----------------
    cells_slope = []
    for i in range(nb):
        lx = math.log(0.03 * (1.6 ** i))
        z = -1.2 - 0.85 * lx
        p = 1.0 / (1.0 + math.exp(-z))
        n = 3000
        cells_slope.append((lx, n, int(round(n * p))))
    r2 = cliff_test(cells_slope, nboot=120, seed=5)
    ck(r2 is not None and r2["p"] > 0.05,
       f"planted SMOOTH SLOPE: the step model must NOT beat it "
       f"(p = {None if r2 is None else r2['p']:.3f}) -- a estimator that "
       f"calls every downward trend a cliff would gate on noise")

    # ---- NULL WORLD: flat rate, no trend, no cliff -----------------------
    rnd = random.Random(99)
    cells_null = []
    for i in range(nb):
        n = 3000
        cells_null.append((math.log(0.03 * (1.6 ** i)), n,
                           sum(1 for _ in range(n) if rnd.random() < 0.03)))
    r3 = cliff_test(cells_null, nboot=120, seed=13)
    ck(r3 is not None and r3["p"] > 0.05,
       f"NULL world (flat 3% everywhere): no cliff found "
       f"(p = {None if r3 is None else r3['p']:.3f})")
    ck(r3 is not None and abs(r3["slope"]) < 0.25,
       f"and no slope found (b = {None if r3 is None else r3['slope']:.3f})")

    # ---- STRATIFIED estimator: plant Simpson's paradox, then a real effect
    # Band A is high-risk and mostly LOW-cushion; band B is low-risk and
    # mostly HIGH-cushion. Marginally the low stratum looks far worse; within
    # bands there is no difference at all, and the estimator must say zero.
    simpson = [(900, 90, 100, 10), (100, 1, 900, 9)]
    ck(abs(stratified_diff(simpson)) < 1e-9,
       f"planted SIMPSON: marginal rates are 10.1% vs 1.9% but the within-"
       f"band difference is {100*stratified_diff(simpson):+.4f} pp -- zero, "
       f"which is the correct answer")
    real = [(500, 50, 500, 25), (500, 40, 500, 20)]
    ck(abs(stratified_diff(real) - 0.045) < 1e-9,
       f"planted REAL effect of +4.5 pp inside every band: estimator returns "
       f"{100*stratified_diff(real):+.3f} pp")
    ck(stratified_diff([(0, 0, 0, 0)]) is None,
       "and an empty stratum returns None rather than a fabricated zero")

    # ---- cluster bootstrap finds a planted difference, and nothing in null
    pc = {}
    for c in range(60):
        pc[c] = [(50, 10 if c % 2 == 0 else 10), (50, 1)]
    pt, sd, tot = cluster_rates(pc, 2, nboot=120, seed=4)
    ck(abs(pt[0] - 0.20) < 1e-9 and abs(pt[1] - 0.02) < 1e-9,
       f"cluster bootstrap point rates {pt[0]:.3f} / {pt[1]:.3f} match the "
       f"planted 0.200 / 0.020")
    ck(sd[0] is not None and sd[0] < 0.02,
       f"and its sd is finite and small on 60 identical closes "
       f"({sd[0]:.4f})")
    pc2 = {c: [(50, 5), (50, 5)] for c in range(60)}
    pt2, sd2, _ = cluster_rates(pc2, 2, nboot=120, seed=4)
    ck(abs(pt2[0] - pt2[1]) < 1e-12,
       "NULL: two buckets with the same planted rate come back identical")

    # ---- gate cost arithmetic -------------------------------------------
    ents = [{"price": 0.95, "flip": False, "cr": 0.30, "close": 1, "tk": "a"},
            {"price": 0.95, "flip": False, "cr": 0.02, "close": 2, "tk": "b"},
            {"price": 0.95, "flip": True, "cr": 0.02, "close": 3, "tk": "c"}]
    g = gate_cost(ents, 0.05)
    ck(g["refused_win"] == 1 and g["refused_loss"] == 1,
       f"a gate at 0.05 refuses 1 winner and 1 loser "
       f"({g['refused_win']} / {g['refused_loss']})")
    ck(abs(g["ratio"] - 1.0) < 1e-9,
       f"so it costs 1.0 winners per loss avoided ({g['ratio']:.2f})")
    ck(g["kept_worst"] > 0.0 and g["base_worst"] < -0.9,
       f"and it removes the worst loss entirely: base worst "
       f"{100*g['base_worst']:.1f}c -> kept worst {100*g['kept_worst']:+.1f}c "
       f"(no losing position survives the gate)")
    g0 = gate_cost(ents, 0.0)
    ck(g0["refused_win"] == 0 and g0["refused_loss"] == 0,
       "NULL: a gate at zero refuses nothing and changes nothing")
    ck(abs(g0["kept_pnl"] - g0["base_pnl"]) < 1e-12,
       "and leaves P&L identical to the base case")

    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


# ===========================================================================
def gate_cost(ents, thresh):
    """Refuse every entry whose cushion ratio is below `thresh`."""
    base = [pinhedge.unhedged_pnl(e["price"], not e["flip"]) for e in ents]
    keep, refu = [], []
    for e, p in zip(ents, base):
        (refu if (e.get("cr") is not None and e["cr"] < thresh)
         else keep).append((e, p))
    def worst_close(rows):
        by = defaultdict(float)
        for e, p in rows:
            by[e["close"]] += p
        return min(by.values()) if by else 0.0
    kept_pnl = sum(p for _, p in keep)
    base_pnl = sum(base)
    wins = [p for e, p in zip(ents, base) if not e["flip"]]
    return {
        "thresh": thresh,
        "n": len(ents), "kept": len(keep), "refused": len(refu),
        "refused_win": sum(1 for e, _ in refu if not e["flip"]),
        "refused_loss": sum(1 for e, _ in refu if e["flip"]),
        "ratio": (sum(1 for e, _ in refu if not e["flip"]) /
                  max(1, sum(1 for e, _ in refu if e["flip"]))),
        "base_pnl": base_pnl, "kept_pnl": kept_pnl,
        "base_worst": min(base) if base else 0.0,
        "kept_worst": min((p for _, p in keep), default=0.0),
        "base_worst_close": worst_close(list(zip(ents, base))),
        "kept_worst_close": worst_close(keep),
        "mean_win": (sum(wins) / len(wins)) if wins else 0.0,
        "kept_closes": len({e["close"] for e, _ in keep}),
    }


def hedge_quote_for(e, trig, bym):
    """The ask we would pay on the other side at or after tau `trig`."""
    cand = [x for x in bym[(e["tk"], e["close"])] if x["tau"] <= trig]
    cand.sort(key=lambda x: -x["tau"])
    for x in cand:
        q = pinhedge.hedge_price(x, e["side_yes"])
        if 0.0 < q < 1.0:
            return q, x["tau"]
    return None, None


def evaluate_trigger(ents, paths, bym, trig_fn, cap=1.0):
    """Score one hedge rule. trig_fn(path) -> tau or None."""
    per_close = defaultdict(float)
    tot = 0.0
    nh = nl_h = noprice = capped = 0
    saved = cost = 0.0
    worst = 0.0
    prices = []
    for e in ents:
        u = pinhedge.unhedged_pnl(e["price"], not e["flip"])
        trig = trig_fn(paths[id(e)])
        v = u
        if trig is not None:
            hp, htau = hedge_quote_for(e, trig, bym)
            if hp is None:
                noprice += 1
            elif hp > cap:
                capped += 1
            else:
                v = pinhedge.hedged_pnl(e["price"], hp)
                prices.append(hp)
                nh += 1
                if e["flip"]:
                    nl_h += 1
                if v > u:
                    saved += v - u
                else:
                    cost += u - v
        tot += v
        worst = min(worst, v)
        per_close[e["close"]] += v
    return {"tot": tot, "nh": nh, "nl_h": nl_h, "saved": saved, "cost": cost,
            "worst": worst, "noprice": noprice, "capped": capped,
            "worst_close": min(per_close.values()) if per_close else 0.0,
            "per_close": dict(per_close),
            "med_px": (sorted(prices)[len(prices) // 2] if prices else None)}


def trigger_compare(ents, idx, bym, mw, label, nboot=1500, seed=41):
    """Every hedge trigger family through IDENTICAL accounting, so the
    crossing can be compared with the model-confidence trigger that was
    already tested rather than argued about."""
    print("")
    print("  " + "-" * 74)
    print(f"  G. EVERY TRIGGER, SAME ACCOUNTING -- {label}")
    print("  " + "-" * 74)
    paths = {id(e): walk_entry(idx, e) for e in ents}
    ents = [e for e in ents if paths[id(e)]]
    if not ents:
        print("  no index path for any entry -- NOT MEASURED")
        return
    base_pc = defaultdict(float)
    for e in ents:
        base_pc[e["close"]] += pinhedge.unhedged_pnl(e["price"],
                                                     not e["flip"])
    base_tot = sum(base_pc.values())
    base_worst = min(pinhedge.unhedged_pnl(e["price"], not e["flip"])
                     for e in ents)
    base_worst_close = min(base_pc.values())
    closes = sorted(base_pc)
    rnd = random.Random(seed)
    boot_idx = [[rnd.randrange(len(closes)) for _ in range(len(closes))]
                for _ in range(nboot)]

    def net_ci(pc):
        d = []
        for draw in boot_idx:
            t = 0.0
            for j in draw:
                c = closes[j]
                t += pc.get(c, 0.0) - base_pc[c]
            d.append(t)
        d.sort()
        return d[int(0.025 * len(d))], d[int(0.975 * len(d))]

    rules = [("no hedge at all", lambda p: None)]
    for c in (0, 1, 2, 3):
        rules.append((f"CROSSED, confirmed {c}s",
                      (lambda cc: (lambda p: trigger_tau(p, cc)))(c)))
    for t in (0.10, 0.20, 0.35, 0.50, 0.75, 0.90):
        def mk(tt):
            def f(p):
                for tau, spot, sc, pf in p:
                    if pf is not None and pf >= tt:
                        return tau
                return None
            return f
        rules.append((f"model p(lose) >= {100*t:.0f}%", mk(t)))
    for t in (0.35, 0.50):
        def mk2(tt):
            def f(p):
                for tau, spot, sc, pf in p:
                    if sc <= 0 and pf is not None and pf >= tt:
                        return tau
                return None
            return f
        rules.append((f"CROSSED and model >= {100*t:.0f}%", mk2(t)))
    print("  Per-CLOSE tail: p1 = worst 1% of closes, p5 = worst 5%. "
          "'wins' converts at")
    print(f"  the mean winning trade of {100*mw:.2f}c per contract, which is "
          f"the operator's unit.")
    print(f"  {'rule':>28}{'hedged':>7}{'lose':>6}{'cost':>8}"
          f"{'total':>9}{'net':>8}{'95% CI on net':>18}{'worst close':>13}"
          f"{'wins':>6}{'p1 close':>10}{'wins':>6}{'p5 close':>10}"
          f"{'wins':>6}{'no px':>6}")
    for name, fn in rules:
        r = evaluate_trigger(ents, paths, bym, fn)
        if name.startswith("no hedge"):
            bv = list(base_pc.values())
            b1, b5 = pct_of(bv, 0.01), pct_of(bv, 0.05)
            print(f"  {name:>28}{'-':>7}{'-':>6}{'-':>8}"
                  f"{100*base_tot:>8.1f}c{'-':>8}{'-':>18}"
                  f"{100*base_worst_close:>12.1f}c"
                  f"{wins_to_recover(base_worst_close, mw):>6.1f}"
                  f"{100*b1:>9.1f}c{wins_to_recover(b1, mw):>6.1f}"
                  f"{100*b5:>9.1f}c{wins_to_recover(b5, mw):>6.1f}{'-':>6}")
            continue
        lo, hi = net_ci(r["per_close"])
        ci = f"[{100*lo:+.0f}, {100*hi:+.0f}]c"
        hv = list(r["per_close"].values())
        h1, h5 = pct_of(hv, 0.01), pct_of(hv, 0.05)
        print(f"  {name:>28}{r['nh']:>7}{r['nl_h']:>6}"
              f"{100*r['cost']:>7.0f}c{100*r['tot']:>8.1f}c"
              f"{100*(r['tot']-base_tot):>7.0f}c{ci:>18}"
              f"{100*r['worst_close']:>12.1f}c"
              f"{wins_to_recover(r['worst_close'], mw):>6.1f}"
              f"{100*h1:>9.1f}c{wins_to_recover(h1, mw):>6.1f}"
              f"{100*h5:>9.1f}c{wins_to_recover(h5, mw):>6.1f}"
              f"{r['noprice']:>6}")
    print("  'net' is total minus the no-hedge total. A CI that spans zero "
          "means the rule")
    print("  is not a demonstrated improvement on P&L -- which under the "
          "operator's")
    print("  objective is allowed, PROVIDED the worst-loss columns actually "
          "fall.")


# ===========================================================================
# The raw book for ONE market, replayed. Used only to price tonight's hedge.
# ===========================================================================
class FpBook:
    """A book rebuilt from orderbook_snapshot + orderbook_delta.

    IT READS THE `_fp` KEYS ON PURPOSE. pindata.Book.snapshot() reads
    `yes_dollars` / `no_dollars`, which are NOT what the tape carries -- the
    snapshot messages are `yes_dollars_fp` / `no_dollars_fp`, so every book
    that class has ever rebuilt was delta-only. That bug is on the open list
    and this class must not repeat it; the self-test pins the key names.
    """

    def __init__(self):
        self.yes = {}
        self.no = {}

    def snapshot(self, msg):
        self.yes.clear()
        self.no.clear()
        for key, d in (("yes_dollars_fp", self.yes),
                       ("no_dollars_fp", self.no)):
            for pair in (msg.get(key) or []):
                try:
                    p, q = round(float(pair[0]), 4), float(pair[1])
                except Exception:
                    continue
                if q > 0:
                    d[p] = q

    def delta(self, side, price, dq):
        d = self.yes if side == "yes" else self.no
        p = round(float(price), 4)
        now = d.get(p, 0.0) + float(dq)
        if now <= 1e-9:
            d.pop(p, None)
        else:
            d[p] = now

    def best_ask(self, side):
        """Ask on `side` = 1 - best bid on the other side."""
        other = self.no if side == "yes" else self.yes
        if not other:
            return None, 0.0
        b = max(other)
        return round(1.0 - b, 4), other[b]


def price_tonight_hedge(ticker, close_s, hour_stamp, taus):
    """What the other side actually cost, second by second, on the real tape."""
    snapf = os.path.join(DATA, "orderbook_snapshot", hour_stamp + ".jsonl.gz")
    deltaf = os.path.join(DATA, "orderbook_delta", hour_stamp + ".jsonl.gz")
    bk = FpBook()
    seen_snap = False
    try:
        with gzip.open(snapf, "rt") as fh:
            for line in fh:
                if ticker not in line:
                    continue
                try:
                    m = json.loads(line)["msg"]
                except Exception:
                    continue
                if m.get("market_ticker") != ticker:
                    continue
                if m.get("yes_dollars_fp") or m.get("no_dollars_fp"):
                    bk.snapshot(m)
                    seen_snap = True
                    break
    except Exception as ex:
        print(f"    snapshot read failed: {ex}")
        return None
    if not seen_snap:
        print("    no populated snapshot for this market -- NOT MEASURED")
        return None
    out = {}
    want = set(taus)
    try:
        with gzip.open(deltaf, "rt") as fh:
            for line in fh:
                if ticker not in line:
                    continue
                try:
                    m = json.loads(line)["msg"]
                except Exception:
                    continue
                if m.get("market_ticker") != ticker:
                    continue
                ts = int(m.get("ts_ms") or 0)
                try:
                    bk.delta(str(m.get("side", "")).lower(),
                             m.get("price_dollars", m.get("price")),
                             m.get("delta_fp", m.get("delta")) or 0.0)
                except Exception:
                    continue
                tau = close_s - ts // 1000
                if tau in want:
                    ask, size = bk.best_ask("yes")
                    out[tau] = (ask, size)
    except Exception as ex:
        print(f"    delta read failed: {ex}")
    return out


# ===========================================================================
# G. THE CONTROL THAT DECIDES IT: does an ABSOLUTE cushion add anything once
#    the model's own z is held fixed?
# ===========================================================================
def stratified_diff(strata):
    """strata: [(n_lo, k_lo, n_hi, k_hi), ...] one per z band.

    Returns the sample-size-weighted mean of (rate_lo - rate_hi) across bands.
    A MARGINAL difference can be entirely produced by the strata having
    different base rates; this estimator is zero when that is all there is.
    """
    num = den = 0.0
    for nl, kl, nh, kh in strata:
        if nl == 0 or nh == 0:
            continue
        w = (nl * nh) / float(nl + nh)
        num += w * (kl / nl - kh / nh)
        den += w
    return (num / den) if den else None


def z_control(rows, key, lo_hi, zbands, nboot=1000, seed=31, label=""):
    """Flip rate in a LOW-cushion stratum vs a HIGH-cushion stratum, WITHIN
    bands of the model's own z, pooled across bands and bootstrapped on
    CLOSES. The unit is the MARKET."""
    lo_max, hi_min = lo_hi
    print("")
    print(f"  {label}: is {key} still informative INSIDE a band of model z?")
    print(f"  low stratum = {key} < {lo_max}, high stratum = {key} >= "
          f"{hi_min}. Unit = market, clustering = close.")
    print(f"  {'z band':>12}{'lo mkts':>9}{'lo flip':>9}{'lo rate':>9}"
          f"{'hi mkts':>9}{'hi flip':>9}{'hi rate':>9}{'diff pp':>9}")
    # collapse to markets first: a market is 'low' if ANY sampled row is low
    per = {}
    for r in rows:
        v = r.get(key)
        z = r.get("z")
        if v is None or z is None:
            continue
        band = None
        for i, (a, b) in enumerate(zbands):
            if a <= z < b:
                band = i
                break
        if band is None:
            continue
        side = 0 if v < lo_max else (1 if v >= hi_min else None)
        if side is None:
            continue
        kk = (r["tk"], r["close"], band, side)
        if kk not in per:
            per[kk] = (r["close"], band, side, bool(r["flip"]))
    strata = []
    bycl = {}
    for (tk, cl, band, side), (_, _, _, fl) in per.items():
        strata.append((band, side, fl))
        bycl.setdefault(cl, []).append((band, side, fl))
    nb = len(zbands)
    def tab(items):
        t = [[0, 0, 0, 0] for _ in range(nb)]
        for band, side, fl in items:
            if side == 0:
                t[band][0] += 1
                t[band][1] += 1 if fl else 0
            else:
                t[band][2] += 1
                t[band][3] += 1 if fl else 0
        return t
    T = tab(strata)
    for i, (a, b) in enumerate(zbands):
        nl, kl, nh, kh = T[i]
        if nl == 0 and nh == 0:
            continue
        rl = (100.0 * kl / nl) if nl else float("nan")
        rh = (100.0 * kh / nh) if nh else float("nan")
        print(f"  {(str(a) + '-' + str(b)):>12}{nl:>9,}{kl:>9}{rl:>8.2f}%"
              f"{nh:>9,}{kh:>9}{rh:>8.2f}%{rl-rh:>9.2f}")
    pt = stratified_diff([tuple(x) for x in T])
    if pt is None:
        print("  pooled: NOT ESTIMABLE (a stratum is empty)")
        return None
    rnd = random.Random(seed)
    cls = list(bycl)
    draws = []
    for _ in range(nboot):
        items = []
        for _ in range(len(cls)):
            items.extend(bycl[cls[rnd.randrange(len(cls))]])
        d = stratified_diff([tuple(x) for x in tab(items)])
        if d is not None:
            draws.append(d)
    draws.sort()
    lo = draws[int(0.025 * len(draws))] if draws else float("nan")
    hi = draws[int(0.975 * len(draws))] if draws else float("nan")
    print(f"  POOLED within-z difference: {100*pt:+.3f} pp   "
          f"95% CI [{100*lo:+.3f}, {100*hi:+.3f}] pp on {len(cls)} closes"
          + ("   -- EXCLUDES ZERO" if (lo > 0 or hi < 0)
             else "   -- INCLUDES ZERO: no information beyond the model's z"))
    return {"pooled": pt, "lo": lo, "hi": hi}


# ===========================================================================
# F. THE CROSSING -- the only event that is actually a warning
# ===========================================================================
def market_window(idx, sr, close_s):
    iid = SERIES_TO_INDEX.get(sr)
    if iid not in idx:
        return None
    base, arr = idx[iid]
    i_lo = close_s - N_AVG - base
    if i_lo < 900 or close_s - base >= len(arr):
        return None
    return base, arr, i_lo


def pf_at(base, arr, i_lo, K, tau, side_yes):
    """The model's probability that OUR side loses, at tau seconds to close,
    rebuilt from the index alone so the walk is on an exogenous 1 s grid."""
    rr = tau - 1
    if rr < 1:
        return None, None
    want = N_AVG + 1 - tau
    vals = [v for v in arr[i_lo:i_lo + want] if v == v]
    if len(vals) < want * 0.95:
        return None, None
    locked = sum(vals) * (want / len(vals))
    sec = (i_lo + N_AVG) + base - tau
    spot = arr[sec - base]
    if spot != spot:
        return None, None
    sig = sigma_at(base, arr, sec, 300)
    if sig is None:
        return None, spot
    mu = (locked + rr * spot) / N_AVG
    req = (60.0 / rr) * (K - mu)
    pf = model_pflip(req, sig, rr)
    if pf is not None and (req <= 0) != bool(side_yes):
        pf = 1.0 - pf                  # the model has switched sides on us
    return pf, spot


def walk_entry(idx, e):
    """Per-second path from one second after entry to the last settling print.

    Returns [(tau, spot, signed_cushion, model_p_lose)] with DECREASING tau.
    """
    w = market_window(idx, e["sr"], e["close"])
    if w is None:
        return []
    base, arr, i_lo = w
    K = k_from_row(e)
    out = []
    for tau in range(e["tau"] - 1, 0, -1):
        pf, spot = pf_at(base, arr, i_lo, K, tau, e["side_yes"])
        if spot is None:
            continue
        out.append((tau, spot, signed_cushion(spot, K, e["side_yes"]), pf))
    return out


def trigger_tau(path, confirm):
    """First tau at which a crossing has been CONFIRMED for `confirm` extra
    seconds. Returns None if the index steps back over the line inside the
    confirmation window -- which is the whole point of having one."""
    for i, p in enumerate(path):
        if p[2] <= 0:
            nxt = path[i:i + confirm + 1]
            if len(nxt) >= confirm + 1 and all(q[2] <= 0 for q in nxt):
                return nxt[-1][0]
            return None
    return None


def crossing_report(ents, idx, bym, mw, label):
    print("")
    print("  " + "-" * 74)
    print(f"  F. THE CROSSING -- {label}")
    print("  " + "-" * 74)
    print("  A position is 'crossed' at the first second the index sits on the")
    print("  WRONG side of K_eff. This is the only after-entry event with any")
    print("  lead time, and unlike the unsigned cushion it does not invert.")
    paths = {}
    for e in ents:
        paths[id(e)] = walk_entry(idx, e)
    have = [e for e in ents if paths[id(e)]]
    if not have:
        print("  no index path for any entry -- NOT MEASURED")
        return
    rows = []
    for e in have:
        pth = paths[id(e)]
        ct = first_cross([(p[0], p[2]) for p in pth])
        stay = None
        if ct is not None:
            after = [p for p in pth if p[0] <= ct]
            stay = all(p[2] <= 0 for p in after)
        pf_at_cross = None
        if ct is not None:
            for p in pth:
                if p[0] == ct:
                    pf_at_cross = p[3]
                    break
        rows.append((e, ct, stay, pf_at_cross))
    L = [r for r in rows if r[0]["flip"]]
    W = [r for r in rows if not r[0]["flip"]]
    def frac(rs):
        return sum(1 for r in rs if r[1] is not None), len(rs)
    lc, ln = frac(L)
    wc, wn = frac(W)
    print("")
    print(f"  LOSERS  that ever crossed after entry: {lc} of {ln}")
    print(f"  WINNERS that ever crossed after entry: {wc} of {wn}")
    if ln:
        cts = sorted(r[1] for r in L if r[1] is not None)
        if cts:
            print(f"  losers  cross at tau (s before close): "
                  f"{', '.join(str(c) for c in cts)}")
            print(f"    median lead time {cts[len(cts)//2]} s; "
                  f"min {min(cts)} s; max {max(cts)} s")
            print(f"    stayed crossed to the end: "
                  f"{sum(1 for r in L if r[2])} of {lc}")
            pfs = [r[3] for r in L if r[3] is not None]
            if pfs:
                pfs.sort()
                print(f"    the model's own p(lose) AT the crossing second: "
                      f"median {100*pfs[len(pfs)//2]:.1f}%, "
                      f"min {100*pfs[0]:.1f}%, max {100*pfs[-1]:.1f}%")
    if wc:
        wts = sorted(r[1] for r in W if r[1] is not None)
        print(f"  winners cross at tau: median {wts[len(wts)//2]} s "
              f"(these are the FALSE ALARMS a crossing trigger must pay for)")
        print(f"    of the {wc} winners that crossed, "
              f"{sum(1 for r in W if r[2])} stayed crossed and still WON "
              f"(the average was already locked in our favour)")
    # ---- hedge on the crossing --------------------------------------
    def hedge_quote(e, trig):
        """The ask we would pay on the other side at or after `trig`."""
        cand = [x for x in bym[(e["tk"], e["close"])] if x["tau"] <= trig]
        cand.sort(key=lambda x: -x["tau"])
        for x in cand:
            q = pinhedge.hedge_price(x, e["side_yes"])
            if 0.0 < q < 1.0:
                return q, x["tau"], x.get("size")
        return None, None, None

    def run_rule(conf, cap):
        per_close = defaultdict(float)
        tot = 0.0
        nh = nl_h = noprice = capped = 0
        saved = cost = 0.0
        worst = 0.0
        detail = []
        for e in ents:
            u = pinhedge.unhedged_pnl(e["price"], not e["flip"])
            trig = trigger_tau(paths[id(e)], conf)
            v = u
            hp = None
            if trig is not None:
                hp, htau, hsize = hedge_quote(e, trig)
                if hp is None:
                    noprice += 1
                elif hp > cap:
                    capped += 1
                    hp = None
                else:
                    v = pinhedge.hedged_pnl(e["price"], hp)
                    nh += 1
                    if e["flip"]:
                        nl_h += 1
                    if v > u:
                        saved += v - u
                    else:
                        cost += u - v
            tot += v
            worst = min(worst, v)
            per_close[e["close"]] += v
            if e["flip"]:
                detail.append((e, trig, hp, u, v))
        return {"tot": tot, "nh": nh, "nl_h": nl_h, "saved": saved,
                "cost": cost, "worst": worst, "noprice": noprice,
                "capped": capped, "detail": detail,
                "worst_close": min(per_close.values()) if per_close else 0.0,
                "per_close": dict(per_close)}

    base_tot = sum(pinhedge.unhedged_pnl(e["price"], not e["flip"])
                   for e in ents)
    base_pc = defaultdict(float)
    for e in ents:
        base_pc[e["close"]] += pinhedge.unhedged_pnl(e["price"],
                                                     not e["flip"])
    base_worst_close = min(base_pc.values()) if base_pc else 0.0
    base_worst = min(pinhedge.unhedged_pnl(e["price"], not e["flip"])
                     for e in ents)
    print("")
    print("  HEDGING ON THE CROSSING. Confirm = wait this many seconds and")
    print("  require the index to still be on the wrong side before paying.")
    print("  cap = refuse to pay more than this for the other side; hedging "
          "at 90c")
    print("  against a 95c entry locks -85c and is barely worth the fee.")
    print(f"  {'confirm':>8}{'cap':>6}{'hedged':>8}{'losers':>8}{'saved':>9}"
          f"{'cost':>9}{'net':>9}{'total':>9}{'worst pos':>11}{'wins':>7}"
          f"{'worst close':>13}{'wins':>7}{'no px':>7}{'too dear':>9}")
    print(f"  {'NONE':>8}{'-':>6}{'-':>8}{'-':>8}{'-':>9}{'-':>9}{'-':>9}"
          f"{100*base_tot:>8.1f}c{100*base_worst:>10.1f}c"
          f"{wins_to_recover(base_worst, mw):>7.1f}"
          f"{100*base_worst_close:>12.1f}c"
          f"{wins_to_recover(base_worst_close, mw):>7.1f}")
    best = None
    for conf in (0, 1, 2, 3, 5):
        for cap in (1.0, 0.80, 0.60, 0.40):
            r = run_rule(conf, cap)
            print(f"  {conf:>8}{cap:>6.2f}{r['nh']:>8}{r['nl_h']:>8}"
                  f"{100*r['saved']:>8.1f}c{100*r['cost']:>8.1f}c"
                  f"{100*(r['saved']-r['cost']):>8.1f}c{100*r['tot']:>8.1f}c"
                  f"{100*r['worst']:>10.1f}c"
                  f"{wins_to_recover(r['worst'], mw):>7.1f}"
                  f"{100*r['worst_close']:>12.1f}c"
                  f"{wins_to_recover(r['worst_close'], mw):>7.1f}"
                  f"{r['noprice']:>7}{r['capped']:>9}")
            if best is None or r["tot"] > best[1]["tot"]:
                best = ((conf, cap), r)
    # ---- the losers, one line each ----------------------------------
    if best and best[1]["detail"]:
        (bc, bcap), br = best
        print("")
        print(f"  EVERY LOSER under the best cell (confirm {bc}, cap "
              f"{bcap:.2f}), so the saving can be checked by hand:")
        print(f"  {'ticker':>26}{'entry tau':>10}{'entry px':>9}"
              f"{'cross tau':>10}{'hedge px':>9}{'unhedged':>10}"
              f"{'hedged':>9}{'saved':>8}{'wins':>7}")
        for e, trig, hp, u, v in sorted(br["detail"], key=lambda d: d[3]):
            print(f"  {e['tk'][-26:]:>26}{e['tau']:>10}{100*e['price']:>8.1f}c"
                  f"{(trig if trig is not None else 0):>10}"
                  f"{(('%8.1fc' % (100*hp)) if hp else '       -'):>9}"
                  f"{100*u:>9.1f}c{100*v:>8.1f}c{100*(v-u):>7.1f}c"
                  f"{wins_to_recover(v - u, mw):>7.1f}")
        # ---- cluster bootstrap on the NET, resampling CLOSES ---------
        closes = sorted(set(e["close"] for e in ents))
        bpc = base_pc
        hpc = br["per_close"]
        rnd = random.Random(23)
        diffs = []
        for _ in range(2000):
            d = 0.0
            for _ in range(len(closes)):
                c = closes[rnd.randrange(len(closes))]
                d += hpc.get(c, 0.0) - bpc.get(c, 0.0)
            diffs.append(d)
        diffs.sort()
        lo = diffs[int(0.025 * len(diffs))]
        hi = diffs[int(0.975 * len(diffs))]
        print(f"  NET vs no hedge: {100*(br['tot']-base_tot):+.1f}c, "
              f"cluster-bootstrap 95% CI on {len(closes)} closes "
              f"[{100*lo:+.1f}c, {100*hi:+.1f}c]"
              + ("  -- EXCLUDES ZERO" if lo > 0 or hi < 0 else
                 "  -- INCLUDES ZERO, so this is not a demonstrated edge"))


# ===========================================================================
def build_index_pop(idx, markets, grid, verbose=True):
    """The exogenous-grid population: no book, no prices, every settled market."""
    out = []
    t0 = time.time()
    for n, r in enumerate(markets):
        sr = r["series"]
        iid = SERIES_TO_INDEX.get(sr)
        if iid is None or iid not in idx:
            continue
        base, arr = idx[iid]
        close_s = int(float(r["close"]))
        i_lo = close_s - N_AVG - base
        if i_lo < 900 or close_s - base >= len(arr):
            continue
        win = arr[i_lo:i_lo + N_AVG]           # seconds close-60 .. close-1
        if len(win) < N_AVG:
            continue
        K = eff_strike(r["strike"], ROUND_DIGITS.get(sr))
        won_yes = float(r["result"]) >= 0.5
        for tau in grid:
            rr = tau - 1
            if rr < 1:
                continue
            want = N_AVG + 1 - tau
            vals = [v for v in win[:want] if v == v]
            if len(vals) < want * 0.95:
                continue
            locked = sum(vals) * (want / len(vals))
            sec = close_s - tau
            spot = arr[sec - base]
            if spot != spot:
                continue
            sig = sigma_at(base, arr, sec, 300)
            if sig is None:
                continue
            mu = (locked + rr * spot) / N_AVG
            req = (60.0 / rr) * (K - mu)
            pf = model_pflip(req, sig, rr)
            if pf is None:
                continue
            side_yes = req <= 0
            row = {"tk": r["ticker"], "sr": sr, "close": close_s, "sec": sec,
                   "tau": tau, "r": rr, "mu": mu, "req": req, "spot": spot,
                   "sig": sig, "side_yes": side_yes,
                   "flip": (side_yes != won_yes), "pf": pf, "K": K}
            attach_cushion(row, base, arr)
            out.append(row)
        if verbose and (n + 1) % 2000 == 0:
            print(f"    {n+1}/{len(markets)} markets  "
                  f"{time.time()-t0:.0f}s", flush=True)
    return out


def signed_cushion(spot, K, side_yes):
    """How far the index sits on the side we NEED, in index units.

    THE POINT OF THE SIGN, AND IT IS THE WHOLE SECTION. |spot - K| GROWS as a
    position loses: tonight the gap went 0.00085 -> 0.00135 while the index
    crossed and stayed crossed. An unsigned cushion therefore looks HEALTHIER
    at the exact moment the trade dies. Signed, the same path goes
    +0.00085 -> -0.00135 and the crossing is unmistakable.
    """
    return (spot - K) if side_yes else (K - spot)


def first_cross(path):
    """path: [(tau, signed_cushion), ...] ordered by DECREASING tau.
    Returns the tau at which the signed cushion first goes <= 0, else None."""
    for tau, sc in path:
        if sc <= 0:
            return tau
    return None


def attach_cushion(row, base, arr):
    K = row.get("K")
    if K is None:
        K = k_from_row(row)
        row["K"] = K
    d = abs(row["spot"] - K)
    row["dist"] = d
    row["bps"] = 1e4 * d / row["spot"] if row["spot"] else None
    for w, tag in ((60, "cr60"), (300, "cr300"), (900, "cr900")):
        rg = realised_range(base, arr, row["sec"], w)
        row["rng%d" % w] = rg
        row[tag] = (d / rg) if (rg is not None and rg > 0) else None
    sd = model_sd(row["sig"], row["r"]) if row.get("sig") else None
    row["z"] = (abs(row["req"]) / sd) if (sd and sd > 0) else None
    sc = signed_cushion(row["spot"], K, bool(row["side_yes"]))
    row["scush"] = sc
    row["sbps"] = 1e4 * sc / row["spot"] if row["spot"] else None
    for w, tag in ((60, "scr60"), (300, "scr300"), (900, "scr900")):
        rg = row.get("rng%d" % w)
        row[tag] = (sc / rg) if (rg is not None and rg > 0) else None


# ===========================================================================
def table(name, rows, key, edges, fmt, nboot, alpha_looks):
    nb = len(edges) + 1
    per_close = defaultdict(lambda: [[0, 0] for _ in range(nb)])
    pred = [0.0] * nb
    for r in rows:
        b = bucket(r.get(key), edges)
        if b is None:
            continue
        c = per_close[r["close"]][b]
        c[0] += 1
        c[1] += 1 if r["flip"] else 0
        pred[b] += r.get("pf", 0.0) or 0.0
    if not per_close:
        print(f"  {name}: nothing to bucket on {key}")
        return None
    pc = {c: [tuple(x) for x in v] for c, v in per_close.items()}
    point, sd, tot = cluster_rates(pc, nb, nboot=nboot)
    labs = bucket_labels(edges, fmt)

    # MDE FIRST, before the estimate.
    print(f"\n  {name}  --  bucketed on {key}, n reported as CLOSES")
    print(f"  MDE, STATED BEFORE THE ESTIMATE. Unit of inference is the "
          f"MARKET (one settlement); clustering is on CLOSE.")
    print(f"  Bonferroni alpha {0.05/nb:.4f} over {nb} buckets at 80% power: "
          f"a bucket can only show an effect larger than 3.48 x its")
    print(f"  bootstrap sd. A bucket with ZERO flipped markets measures "
          f"nothing below its 95% upper bound (rule of three, 3/n).")
    mkts = [set() for _ in range(nb)]
    mkflip = [set() for _ in range(nb)]
    clos = [set() for _ in range(nb)]
    for r in rows:
        b = bucket(r.get(key), edges)
        if b is None:
            continue
        mkts[b].add((r["tk"], r["close"]))
        clos[b].add(r["close"])
        if r["flip"]:
            mkflip[b].add((r["tk"], r["close"]))
    print(f"  {'bucket':>14}{'rows':>8}{'mkts':>7}{'closes':>8}"
          f"{'mkts flipped':>14}{'mkt rate':>10}{'95% UB':>9}"
          f"{'row rate':>10}{'boot sd':>9}{'model p':>9}{'real/model':>11}")
    for b in range(nb):
        n, k = tot[b]
        if n == 0:
            continue
        nm, nf = len(mkts[b]), len(mkflip[b])
        mp = pred[b] / n
        ratio = (k / n) / mp if mp > 0 else float("nan")
        sb = sd[b]
        # 95% upper bound on the MARKET flip rate: Wilson where there are
        # events, the rule of three (3/n) where there are none. A zero is
        # not a measurement of zero and is never printed as one.
        if nf == 0:
            ub = 3.0 / nm if nm else 1.0
        else:
            ph = nf / nm
            z = 1.96
            den = 1 + z * z / nm
            ctr = ph + z * z / (2 * nm)
            rad = z * math.sqrt(ph * (1 - ph) / nm + z * z / (4 * nm * nm))
            ub = (ctr + rad) / den
        print(f"  {labs[b]:>14}{n:>8,}{nm:>7,}{len(clos[b]):>8}{nf:>14}"
              f"{100*nf/nm:>9.2f}%{100*ub:>8.2f}%"
              f"{100*point[b]:>9.3f}%"
              f"{('%9.4f' % (100*sb)) if sb is not None else '        -'}"
              f"{100*mp:>8.3f}%{ratio:>11.2f}")
    skipped = sum(1 for r in rows if bucket(r.get(key), edges) is None)
    if skipped:
        print(f"  {skipped:,} rows had no {key} (index range zero or window "
              f"holed) and are excluded -- reported, not hidden.")

    cells = []
    for b in range(nb):
        n, k = tot[b]
        if n:
            lo = edges[0] * 0.5 if b == 0 else edges[b - 1]
            hi = edges[-1] * 2 if b == nb - 1 else edges[b]
            cells.append((math.log(max(1e-6, math.sqrt(lo * hi))), n, k))
    return {"cells": cells, "tot": tot, "point": point, "sd": sd,
            "pred": pred, "labels": labs}


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=ROWS)
    ap.add_argument("--pop", default="both", choices=("book", "index", "both"))
    ap.add_argument("--tau-lo", type=int, default=3)
    ap.add_argument("--tau-hi", type=int, default=200)
    ap.add_argument("--nboot", type=int, default=400)
    ap.add_argument("--cliffboot", type=int, default=200)
    ap.add_argument("--only-tonight", action="store_true")
    ap.add_argument("--index-hours", type=int, default=0,
                    help="0 = every hour on disk")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    print("\n" + "=" * 78)
    print("  PLAYING TOO CLOSE TO THE LINE -- pinclose.py")
    print("=" * 78)

    # ---------------- the book population ------------------------------
    rows = []
    with open(a.rows, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    lo = min(r["sec"] for r in rows)
    hi = max(r["sec"] for r in rows)
    print(f"\n  BOOK population: {len(rows):,} rows, "
          f"{len({(r['tk'], r['close']) for r in rows}):,} markets, "
          f"{len({r['close'] for r in rows})} closes")
    print(f"  span {time.strftime('%Y-%m-%d %H:%M', time.gmtime(lo))} -> "
          f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(hi))} UTC")

    lo_stamp = time.strftime("%Y%m%dT%H", time.gmtime(lo - 1200))
    print("\n  loading index tape ...", flush=True)
    files = index_files()
    if a.index_hours:
        files = files[-a.index_hours:]
    idx = load_index(files)
    print(f"  {len(idx)} indices over {len(files)} hours", flush=True)

    # reconciliation: K recovered from the row must match the settlement file
    mk_all = json.load(open(FULLTAPE, encoding="utf-8"))
    mk = {}
    for v in mk_all.values():
        for r in v:
            mk[r["ticker"]] = r
    bad = 0
    chk = 0
    for r in rows[:4000]:
        m = mk.get(r["tk"])
        if not m:
            continue
        chk += 1
        want = eff_strike(m["strike"], ROUND_DIGITS.get(r["sr"]))
        if abs(k_from_row(r) - want) > 1e-6 * max(1.0, abs(want)):
            bad += 1
    print(f"  RECONCILIATION: K_eff recovered from (mu, req, r) matches the "
          f"settlement file on {chk-bad:,} of {chk:,} rows checked"
          + (f"  *** {bad} MISMATCHES ***" if bad else ""))

    for r in rows:
        iid = SERIES_TO_INDEX.get(r["sr"])
        if iid in idx:
            base, arr = idx[iid]
            attach_cushion(r, base, arr)
        else:
            r["cr300"] = None
        r["pf"] = model_pflip(r["req"], r.get("sig"), r["r"])

    # ---------------- tonight's loss, placed in the distribution --------
    print("\n" + "-" * 78)
    print("  TONIGHT'S LOSS, RECONSTRUCTED FROM THE INDEX TAPE")
    print("-" * 78)
    close_s = 1788914700
    Kn = 2.34915
    base, arr = idx.get("NEARUSD_RTI", (None, None))
    tonight = None
    if arr is not None:
        i_lo = close_s - N_AVG - base
        print("  Full per-second path from entry to the last settling print.")
        print("  side = NO, so the cushion is POSITIVE while the index is "
              "BELOW K_eff.")
        print(f"  {'tau':>5}{'spot':>10}{'signed cushion':>16}{'bps':>8}"
              f"{'cr300':>8}{'model p(lose)':>15}")
        fired50 = fired90 = crossed = None
        for tau in range(22, 0, -1):
            sec = close_s - tau
            if not (0 <= sec - base < len(arr)):
                continue
            spot = arr[sec - base]
            if spot != spot:
                continue
            pf, _sp = pf_at(base, arr, i_lo, Kn, tau, False)
            sc = signed_cushion(spot, Kn, False)
            r300 = realised_range(base, arr, sec, 300)
            if crossed is None and sc <= 0:
                crossed = tau
            if pf is not None and fired50 is None and pf >= 0.50:
                fired50 = tau
            if pf is not None and fired90 is None and pf >= 0.90:
                fired90 = tau
            print(f"  {tau:>5}{spot:>10.5f}{sc:>16.5f}"
                  f"{1e4*sc/spot:>8.2f}"
                  f"{(sc/r300 if r300 else float('nan')):>8.3f}"
                  f"{(100*pf if pf is not None else float('nan')):>14.2f}%")
        print("")
        print("  WHAT THE OTHER SIDE ACTUALLY COST, from the raw book:")
        px = price_tonight_hedge("KXNEAR15M-26SEP082045-45", close_s,
                                 "20260909T00", set(range(1, 23)))
        entry_avg = (96.2 * 20 + 95.6 * 20 + 73.0 * 19) / 59.0 / 100.0
        if px:
            print(f"  {'tau':>5}{'YES ask':>10}{'size':>10}"
                  f"{'locked P&L if hedged here':>28}{'wins':>8}")
            for tau in sorted(px, reverse=True):
                ask, size = px[tau]
                if ask is None:
                    continue
                v = pinhedge.hedged_pnl(entry_avg, ask)
                print(f"  {tau:>5}{100*ask:>9.1f}c{size:>10.0f}"
                      f"{100*v:>27.1f}c"
                      f"{wins_to_recover(v, 0.0508):>8.1f}")
            print(f"  (our average entry was {100*entry_avg:.1f}c across 59 "
                  f"contracts; unhedged that lost "
                  f"{100*pinhedge.unhedged_pnl(entry_avg, False):.1f}c each, "
                  f"which is the -$52.60)")
        print(f"  index CROSSED to the wrong side at tau {crossed}")
        print(f"  the model reached 50% at tau "
              f"{fired50 if fired50 is not None else 'NEVER'}"
              f"; 90% at tau {fired90 if fired90 is not None else 'NEVER'}")
        if fired50 is None:
            print("  *** THE 50% HEDGE TRIGGER WOULD NEVER HAVE FIRED ON THIS")
            print("  *** LOSS. Every hedge rule scored on the wide window is")
            print("  *** scored on losers that do not look like this one.")
        print("")
        for tau in (22, 21, 17, 16):
            sec = close_s - tau
            if not (0 <= sec - base < len(arr)):
                continue
            spot = arr[sec - base]
            if spot != spot:
                continue
            d = abs(spot - Kn)
            r60 = realised_range(base, arr, sec, 60)
            r300 = realised_range(base, arr, sec, 300)
            r900 = realised_range(base, arr, sec, 900)
            print(f"    tau {tau:>3}  spot {spot:.5f}  |spot-K| {d:.5f}  "
                  f"{1e4*d/spot:6.2f} bps   "
                  f"cr60 {('%.3f' % (d/r60)) if r60 else '   -':>7}  "
                  f"cr300 {('%.3f' % (d/r300)) if r300 else '   -':>7}  "
                  f"cr900 {('%.3f' % (d/r900)) if r900 else '   -':>7}")
            if tau == 22:
                tonight = {"bps": 1e4 * d / spot,
                           "cr300": (d / r300) if r300 else None,
                           "cr60": (d / r60) if r60 else None}
    else:
        print("    NEARUSD_RTI not in the loaded index tape -- NOT MEASURED")

    if a.only_tonight:
        print("")
        print("  --only-tonight: stopping before the population work.")
        return

    # ---------------- A. flip rate by cushion --------------------------
    print("\n" + "=" * 78)
    print("  A. LOSS RATE BY CUSHION")
    print("=" * 78)
    conf = [r for r in rows if r["pf"] is not None and r["pf"] <= PIN_P]
    print(f"\n  model-confident rows (p_flip <= {PIN_P:.0%}): {len(conf):,}, "
          f"{len({(r['tk'], r['close']) for r in conf}):,} markets, "
          f"{len({(r['tk'], r['close']) for r in conf if r['flip']}):,} of "
          f"which flipped, over {len({r['close'] for r in conf})} closes")

    res = {}
    for key, edges, fmt, lab in (
            ("bps", BPS_EDGES, "{:.0f}", "distance in BASIS POINTS"),
            ("cr60", CR_EDGES, "{:.2f}", "cushion / 60 s range"),
            ("cr300", CR_EDGES, "{:.2f}", "cushion / 300 s range"),
            ("cr900", CR_EDGES, "{:.2f}", "cushion / 900 s range")):
        res[key] = table(f"BOOK, all rows -- {lab}", rows, key, edges, fmt,
                         a.nboot, 0.05)
    resc = {}
    for key, edges, fmt, lab in (
            ("bps", BPS_EDGES, "{:.0f}", "distance in BASIS POINTS"),
            ("cr300", CR_EDGES, "{:.2f}", "cushion / 300 s range")):
        resc[key] = table(f"BOOK, model says <= {PIN_P:.0%} -- {lab}", conf,
                          key, edges, fmt, a.nboot, 0.05)

    # ---------------- B. cliff or slope --------------------------------
    print("\n" + "=" * 78)
    print("  B. CLIFF OR SLOPE?  (step model vs smooth, parametric bootstrap)")
    print("=" * 78)
    print("  A significant p means the data prefer a THRESHOLD to a trend --")
    print("  a gate. A non-significant p means sizing, not gating.")
    print("  Run twice: on ALL rows (where the answer is trivially yes -- "
          "closer to")
    print("  the line is more dangerous, which is what the model already "
          "knows), and")
    print("  on the MODEL-CONFIDENT rows, which is the only population we "
          "would trade.")
    for key in ("bps", "cr60", "cr300", "cr900"):
        r = res.get(key)
        if not r:
            continue
        ct = cliff_test(r["cells"], nboot=a.cliffboot)
        if ct is None:
            print(f"  {key:>6}: too few populated buckets to test")
            continue
        print(f"  {key:>6}: slope in log(cushion) = {ct['slope']:+.3f}   "
              f"best break at bucket {ct['break']} ({r['labels'][ct['break']]})"
              f"   LR = {ct['lr']:.2f}   p = {ct['p']:.3f}  "
              f"({ct['nboot']} parametric draws)")
    print("  --- the same test on the MODEL-CONFIDENT rows only ---")
    for key in ("bps", "cr300"):
        r = resc.get(key)
        if not r:
            continue
        ct = cliff_test(r["cells"], nboot=a.cliffboot)
        if ct is None:
            print(f"  {key:>6}: too few populated buckets to test")
            continue
        print(f"  {key:>6}: slope {ct['slope']:+.3f}   break at bucket "
              f"{ct['break']} ({r['labels'][ct['break']]})   "
              f"LR = {ct['lr']:.2f}   p = {ct['p']:.3f}")

    # ---------------- C. the cost of a gate ----------------------------
    print("\n" + "=" * 78)
    print("  C. WHAT A GATE COSTS -- in cents AND in WINS TO RECOVER")
    print("=" * 78)
    bym = defaultdict(list)
    for r in rows:
        bym[(r["tk"], r["close"])].append(r)
    for k in bym:
        bym[k].sort(key=lambda x: -x["tau"])

    for wname, (tl, th) in (("LIVE window tau 3-30", (3, 30)),
                            ("WIDE window tau 3-%d" % a.tau_hi,
                             (a.tau_lo, a.tau_hi))):
        ents = []
        for k, seq in bym.items():
            for x in seq:
                if not (tl <= x["tau"] <= th):
                    continue
                if x["pf"] is None or x["pf"] > PIN_P:
                    continue
                if x["price"] > CEILING or pinhedge.ev(x["price"]) < EV_FLOOR:
                    continue
                ents.append(x)
                break
        nl = sum(1 for e in ents if e["flip"])
        print(f"\n  {wname}: {len(ents)} positions, "
              f"{len({e['close'] for e in ents})} closes, {nl} LOSERS")
        if not ents:
            continue
        b0 = gate_cost(ents, 0.0)
        mw = b0["mean_win"]
        print(f"  mean WIN {100*mw:.2f}c per contract, so one 90c loss costs "
              f"{wins_to_recover(-0.90, mw):.0f} wins.")
        print(f"  base: total {100*b0['base_pnl']:+.1f}c, worst position "
              f"{100*b0['base_worst']:+.1f}c "
              f"({wins_to_recover(b0['base_worst'], mw):.1f} wins), "
              f"worst close {100*b0['base_worst_close']:+.1f}c "
              f"({wins_to_recover(b0['base_worst_close'], mw):.1f} wins)")
        for key in ("cr300", "bps"):
            grid = ((0.02, 0.05, 0.08, 0.12, 0.20, 0.35)
                    if key.startswith("cr") else (1.0, 2.0, 4.0, 8.0, 15.0))
            print(f"\n  {'gate: refuse if ' + key + ' <':>26}{'kept':>6}"
                  f"{'ref W':>7}{'ref L':>7}{'W/L':>7}{'total':>10}"
                  f"{'d profit':>10}{'worst pos':>11}{'wins':>7}"
                  f"{'worst close':>13}{'wins':>7}")
            for th_ in grid:
                for e in ents:
                    e["cr"] = e.get(key)
                g = gate_cost(ents, th_)
                print(f"  {th_:>26.3f}{g['kept']:>6}{g['refused_win']:>7}"
                      f"{g['refused_loss']:>7}"
                      f"{(g['ratio'] if g['refused_loss'] else float('nan')):>7.1f}"
                      f"{100*g['kept_pnl']:>9.1f}c"
                      f"{100*(g['kept_pnl']-g['base_pnl']):>9.1f}c"
                      f"{100*g['kept_worst']:>10.1f}c"
                      f"{wins_to_recover(g['kept_worst'], mw):>7.1f}"
                      f"{100*g['kept_worst_close']:>12.1f}c"
                      f"{wins_to_recover(g['kept_worst_close'], mw):>7.1f}")

        # ------------- D. the same threshold as a HEDGE trigger ---------
        print(f"\n  D. SAME THRESHOLD, USED AS A HEDGE TRIGGER INSTEAD "
              f"({wname})")
        print(f"  {'hedge if cr300 falls below':>28}{'hedged':>8}{'saved':>9}"
              f"{'cost':>9}{'total':>10}{'d profit':>10}{'worst pos':>11}"
              f"{'wins':>7}")
        base_tot = sum(pinhedge.unhedged_pnl(e["price"], not e["flip"])
                       for e in ents)
        for th_ in (0.02, 0.05, 0.08, 0.12, 0.20, 0.35):
            tot = 0.0
            nh = saved = cost = 0.0
            nh = 0
            worst = 0.0
            bad = 0
            for e in ents:
                later = [x for x in bym[(e["tk"], e["close"])]
                         if x["tau"] < e["tau"]]
                hp = None
                for x in later:
                    c = x.get("cr300")
                    if c is not None and c < th_:
                        q = pinhedge.hedge_price(x, e["side_yes"])
                        if not (0.0 < q < 1.0):
                            bad += 1
                            continue
                        hp = q
                        break
                u = pinhedge.unhedged_pnl(e["price"], not e["flip"])
                if hp is None:
                    v = u
                else:
                    v = pinhedge.hedged_pnl(e["price"], hp)
                    nh += 1
                    if v > u:
                        saved += v - u
                    else:
                        cost += u - v
                tot += v
                worst = min(worst, v)
            print(f"  {th_:>28.3f}{nh:>8}{100*saved:>8.1f}c{100*cost:>8.1f}c"
                  f"{100*tot:>9.1f}c{100*(tot-base_tot):>9.1f}c"
                  f"{100*worst:>10.1f}c{wins_to_recover(worst, mw):>7.1f}"
                  + (f"   ({bad} derived prices outside (0,1))" if bad else ""))

        crossing_report(ents, idx, bym, mw, wname)
        trigger_compare(ents, idx, bym, mw, wname)

    # ---------------- the INDEX population ------------------------------
    if a.pop in ("index", "both"):
        print("\n" + "=" * 78)
        print("  E. THE EXOGENOUS-GRID POPULATION (no book, ~12 days)")
        print("=" * 78)
        markets = []
        for v in mk_all.values():
            for r in v:
                if r["series"] in SERIES_TO_INDEX:
                    markets.append(r)
        print(f"  {len(markets):,} settled markets on disk; building rows on "
              f"an exogenous tau grid ...", flush=True)
        grid = (5, 10, 15, 20, 25, 30, 40, 50, 60)
        ip = build_index_pop(idx, markets, grid)
        print(f"  {len(ip):,} rows, "
              f"{len({(r['tk'], r['close']) for r in ip}):,} markets, "
              f"{len({r['close'] for r in ip})} closes, "
              f"{sum(1 for r in ip if r['flip']):,} flip rows")
        ipc = [r for r in ip if r["pf"] <= PIN_P]
        print(f"  model-confident (<= {PIN_P:.0%}): {len(ipc):,} rows, "
              f"{len({(r['tk'], r['close']) for r in ipc}):,} markets, "
              f"{len({(r['tk'], r['close']) for r in ipc if r['flip']}):,} "
              f"flipped, {len({r['close'] for r in ipc})} closes")
        res2 = {}
        res2c = {}
        for key, edges, fmt, lab in (
                ("bps", BPS_EDGES, "{:.0f}", "distance in BASIS POINTS"),
                ("cr300", CR_EDGES, "{:.2f}", "cushion / 300 s range")):
            res2[key] = table(f"INDEX, all rows -- {lab}", ip, key, edges,
                              fmt, a.nboot, 0.05)
            res2c[key] = table(f"INDEX, model says <= {PIN_P:.0%} -- {lab}",
                               ipc, key, edges, fmt, a.nboot, 0.05)
        print("\n  cliff test on the INDEX population:")
        for key in ("bps", "cr300"):
            r = res2.get(key)
            if not r:
                continue
            ct = cliff_test(r["cells"], nboot=a.cliffboot)
            if ct is None:
                print(f"  {key:>6}: too few populated buckets")
                continue
            print(f"  {key:>6}: slope {ct['slope']:+.3f}   break at bucket "
                  f"{ct['break']} ({r['labels'][ct['break']]})   "
                  f"LR = {ct['lr']:.2f}   p = {ct['p']:.3f}")
        print("  --- and on the MODEL-CONFIDENT rows only ---")
        for key, edges, fmt in (("bps", BPS_EDGES, "{:.0f}"),
                                ("cr300", CR_EDGES, "{:.2f}")):
            rr = res2c.get(key)
            if not rr:
                continue
            ct = cliff_test(rr["cells"], nboot=a.cliffboot)
            if ct is None:
                print(f"  {key:>6}: too few populated buckets")
                continue
            print(f"  {key:>6}: slope {ct['slope']:+.3f}   break at bucket "
                  f"{ct['break']} ({rr['labels'][ct['break']]})   "
                  f"LR = {ct['lr']:.2f}   p = {ct['p']:.3f}")

        # THE CONTROL: does cushion add anything once the model's own z is
        # held fixed? If not, this is the refuted entry-gate work again.
        print("\n" + "-" * 78)
        print("  CONTROL: cushion WITHIN bands of the model's own z")
        print("-" * 78)
        ZBANDS = ((2.0, 3.0), (3.0, 4.0), (4.0, 6.0), (6.0, 10.0),
                  (10.0, 1e9))
        z_control(ip, "bps", (5.0, 10.0), ZBANDS, label="INDEX, all rows")
        z_control(ipc, "bps", (5.0, 10.0), ZBANDS,
                  label=f"INDEX, model says <= {PIN_P:.0%}")
        z_control(ip, "cr300", (0.10, 0.20), ZBANDS, label="INDEX, all rows")
        z_control(ipc, "cr300", (0.10, 0.20), ZBANDS,
                  label=f"INDEX, model says <= {PIN_P:.0%}")
        for zlo, zhi in ((2.0, 3.0), (3.0, 4.0), (4.0, 6.0), (6.0, 1e9)):
            sub = [r for r in ip if r.get("z") is not None
                   and zlo <= r["z"] < zhi]
            if len(sub) < 500:
                print(f"  z {zlo}-{zhi}: only {len(sub)} rows, skipped")
                continue
            nb = len(CR_EDGES) + 1
            tot = [[0, 0] for _ in range(nb)]
            for r in sub:
                b = bucket(r.get("cr300"), CR_EDGES)
                if b is None:
                    continue
                tot[b][0] += 1
                tot[b][1] += 1 if r["flip"] else 0
            cells = " ".join(
                f"{bucket_labels(CR_EDGES)[b]}:{tot[b][1]}/{tot[b][0]}"
                f"={100*tot[b][1]/tot[b][0]:.2f}%"
                for b in range(nb) if tot[b][0] >= 50)
            print(f"  z {zlo:>4}-{zhi if zhi < 1e8 else float('inf'):<5}  "
                  f"n={len(sub):,}  {cells}")

    print("\n  DONE. Every number above is per contract unless marked "
          "otherwise.")


if __name__ == "__main__":
    main()
