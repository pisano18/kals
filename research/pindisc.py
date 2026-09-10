#!/usr/bin/env python3
# VERSION: 2026-09-10-pdc1
"""pindisc.py -- does DISCOUNT TO FAIR predict flips, once PRICE is held fixed?

    python research/pindisc.py --selftest
    python research/pindisc.py --rows results/pindata_fixed/rows.jsonl

THE QUESTION

The live bot buys near-certainties in the last 3-30 s of a 15-minute crypto
binary. Its backtest flips ~0.7% of the time; live it has flipped 5 times in
~57 closes. The leading live suspect is adverse selection IN THE FILL: the
losing fills carried far more price improvement than the winning ones, so
"somebody dumping a near-certainty on us far below its model value may know
something". That claim rests on five losses, and the single largest win in
the project's history was ALSO its largest improvement.

Restated so the historical dataset can test it: conditional on the model
being confident (fair >= 0.98) and the moment being tradeable (the live gate),
does a LARGER discount to fair, `fair_fav - price`, predict a HIGHER flip
rate, ONCE PRICE LEVEL IS CONTROLLED? The price-ladder result already says
cheap trades are SAFER in net-margin terms; the open question is whether the
market's DISAGREEMENT with our model behaves differently from price itself.

Note what "controlling for price" turns the question into. Inside a narrow
price band, price is nearly constant, so discount = fair - price varies
almost entirely through FAIR. "High discount at a fixed price" therefore
means "the model is MORE confident than usual at this price" -- and the
adverse-selection story says that is exactly when the model is most wrong.
A calibrated model predicts the opposite: higher fair, fewer flips. So this
stage is a head-to-head between the model and the book at the margin, and it
prints BOTH conditionings: split by discount within price band (the live
claim) and split by price within fair band (the ladder's claim).

WHAT IS MEASURED, AND HOW

  * every row of the pindata table is pushed through the LIVE gate exactly
    as pinrun enforces it (tau, fair, side agreement, price ceiling, size,
    fee-netted edge, EV floor). Rows the bot would never have traded are
    not a population of interest.
  * ONE observation per market: the row the bot would have hit FIRST
    (largest tau among qualifying rows), never the best one.
  * ONE observation per CLOSE for inference: the first-hit market of the
    close (largest tau, ticker order on ties), because twelve series settle
    on the same second at rho ~ 0.8 and a per-market statistic would be
    wrong by up to ~14x. n is reported as CLOSES, and as markets labelled
    as such, never as rows.
  * flip rates per discount bucket, per price band, and per (price band x
    discount half) with EXACT Clopper-Pearson intervals on every rate.
  * significance from a stratified rank permutation test on the one-per-
    close units: discounts are ranked within price band, the statistic is
    the sum of the centred ranks of the units that FLIPPED, and the null is
    built by shuffling discounts within band across closes. That is an
    exact conditional test of "flip independent of discount given band".
  * the MDE is printed BEFORE the estimate, from a simulation that plants a
    higher flip rate in the high-discount half and reruns the same test.
    With a base rate under 1% the honest answer may be "no power"; the
    report says so in those words rather than calling a wide null a result.

NOTHING HERE PLACES AN ORDER. Nothing here is deployed by this file.
"""

import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor            # noqa: E402
from tdist import betainc                # noqa: E402

ND = NormalDist()

DEFAULT_ROWS = os.path.join(HERE, "..", "results", "pindata_fixed", "rows.jsonl")

# --- the live gate, copied from the operator's statement of pinrun's rule ---
TAU_LO, TAU_HI = 3, 30
PIN = 0.98
PRICE_LO, PRICE_HI = 0.5, 0.980
MIN_SIZE = 10.0
FEE_QTY = 20
EDGE_FLOOR = 0.003
EV_FLOOR = 0.003
MEASURED_FLIP = 0.009

# price bands for the primary (live) population; the last one is the
# ceiling itself. The 0.50-0.80 band is kept so nothing the gate passes is
# silently dropped from the tables.
BANDS = ((0.50, 0.80), (0.80, 0.93), (0.93, 0.97), (0.97, 0.9801))
# the relaxed population lifts the ceiling to see the dear side too
BANDS_RELAXED = BANDS[:-1] + ((0.97, 0.98), (0.98, 0.99), (0.99, 1.0))
FAIR_BANDS = ((0.980, 0.985), (0.985, 0.992), (0.992, 0.999), (0.999, 1.0001))

ALPHA = 0.05
POWER_TARGET = 0.80


# ===========================================================================
# arithmetic
# ===========================================================================
def billed_fee(p, n=1):
    """Kalshi's billed taker fee for n contracts at price p, rounded UP to
    the cent-of-a-dollar the exchange actually charges."""
    return math.ceil(0.07 * p * (1 - p) * n * 10000 - 1e-9) / 10000


def ev_measured(p, flip=MEASURED_FLIP):
    return (1.0 - flip) * (1.0 - p) - flip * p - billed_fee(p, 1)


def fair_of(row):
    """(fair_yes, fair_fav, discount) exactly as the live bot computes them,
    or None when the model has no variance to speak of."""
    r = int(row["r"])
    sig = float(row["sig"])
    if r < 1 or sig <= 0.0:
        return None
    sd = sig * math.sqrt(var_factor(r, [1.0]))
    if sd <= 0.0:
        return None
    fair_yes = ND.cdf((-float(row["req"]) * r / 60.0) / sd)
    fair_fav = fair_yes if row["side_yes"] else 1.0 - fair_yes
    return fair_yes, fair_fav, fair_fav - float(row["price"])


def gate(row, ceiling=PRICE_HI, ev_gate=True):
    """The live gate. Returns (ok, reason, fair_fav, discount)."""
    tau = row["tau"]
    if not (TAU_LO <= tau <= TAU_HI):
        return False, "tau", None, None
    f = fair_of(row)
    if f is None:
        return False, "sd", None, None
    fair_yes, fair_fav, disc = f
    if fair_fav < PIN:
        return False, "fair", fair_fav, disc
    if (fair_yes >= 0.5) != bool(row["side_yes"]):
        return False, "side", fair_fav, disc
    p = float(row["price"])
    if not (PRICE_LO < p <= ceiling):
        return False, "price", fair_fav, disc
    if float(row["size"]) < MIN_SIZE:
        return False, "size", fair_fav, disc
    if disc - billed_fee(p, FEE_QTY) / FEE_QTY < EDGE_FLOOR:
        return False, "edge", fair_fav, disc
    if ev_gate and ev_measured(p) < EV_FLOOR:
        return False, "ev", fair_fav, disc
    return True, "ok", fair_fav, disc


def first_hit_per_market(rows, ceiling=PRICE_HI, ev_gate=True):
    """One observation per market: the qualifying row with the LARGEST tau,
    i.e. the first moment the bot would have fired. Also returns the reason
    tally so the report can say what the gate threw away."""
    best = {}
    reasons = defaultdict(int)
    for row in rows:
        ok, why, fair_fav, disc = gate(row, ceiling, ev_gate)
        reasons[why] += 1
        if not ok:
            continue
        tk = row["tk"]
        cur = best.get(tk)
        if cur is None or row["tau"] > cur["tau"]:
            obs = dict(row)
            obs["fair"] = fair_fav
            obs["disc"] = disc
            best[tk] = obs
    return best, dict(reasons)


def one_per_close(markets):
    """The first-hit market of each close: largest tau, ticker order on ties.
    This is the unit of inference."""
    by_close = {}
    for tk in sorted(markets):
        m = markets[tk]
        c = m["close"]
        cur = by_close.get(c)
        if cur is None or m["tau"] > cur["tau"]:
            by_close[c] = m
    return by_close


# ===========================================================================
# Clopper-Pearson
# ===========================================================================
def _binom_cdf(k, n, p):
    """P(X <= k) for X ~ Bin(n, p), via the regularised incomplete beta."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return betainc(n - k, k + 1, 1.0 - p)


def cp_interval(k, n, conf=0.95):
    """Exact two-sided Clopper-Pearson interval on k successes in n."""
    if n <= 0:
        return 0.0, 1.0
    a = (1.0 - conf) / 2.0
    if k <= 0:
        lo = 0.0
    else:
        # P(X >= k | p) = a  <=>  1 - cdf(k-1) = a
        l, h = 0.0, 1.0
        for _ in range(100):
            mid = 0.5 * (l + h)
            if 1.0 - _binom_cdf(k - 1, n, mid) < a:
                l = mid
            else:
                h = mid
        lo = 0.5 * (l + h)
    if k >= n:
        hi = 1.0
    else:
        l, h = 0.0, 1.0
        for _ in range(100):
            mid = 0.5 * (l + h)
            if _binom_cdf(k, n, mid) > a:
                l = mid
            else:
                h = mid
        hi = 0.5 * (l + h)
    return lo, hi


def rate_str(k, n):
    if n == 0:
        return "      --                 "
    lo, hi = cp_interval(k, n)
    return f"{100.0*k/n:6.2f}%  [{100*lo:5.2f}, {100*hi:6.2f}]"


# ===========================================================================
# the stratified rank permutation test
# ===========================================================================
def band_of(p, bands):
    for lo, hi in bands:
        if lo <= p < hi:
            return (lo, hi)
    return None


def centred_ranks(units, key="disc"):
    """Within-band centred ranks of `key` (average ranks on ties). Returns
    a list aligned with `units`."""
    by_band = defaultdict(list)
    for i, u in enumerate(units):
        by_band[u["band"]].append(i)
    s = [0.0] * len(units)
    for band, idx in by_band.items():
        idx.sort(key=lambda i: units[i][key])
        n = len(idx)
        j = 0
        while j < n:
            k = j
            while k + 1 < n and units[idx[k + 1]][key] == units[idx[j]][key]:
                k += 1
            avg = 0.5 * (j + k) + 1.0            # 1-based average rank
            for t in range(j, k + 1):
                s[idx[t]] = avg - 0.5 * (n + 1)
            j = k + 1
    return s


def rank_stat(scores, flips):
    return sum(sc for sc, y in zip(scores, flips) if y)


def perm_test(units, flips, n_perm, rng, key="disc"):
    """Stratified rank permutation test. Discounts are shuffled WITHIN band
    across the units (closes). Returns (T_obs, p_one_sided_high, p_two_sided,
    null_sd). p_one_sided_high is P(T_perm >= T_obs): the live claim is that
    a higher discount raises the flip rate, so a flipped unit carrying a
    high rank is evidence FOR it."""
    scores = centred_ranks(units, key)
    by_band = defaultdict(list)
    for i, u in enumerate(units):
        by_band[u["band"]].append(i)
    t_obs = rank_stat(scores, flips)
    flipped = [i for i, y in enumerate(flips) if y]
    if not flipped or len(flipped) == len(units):
        return t_obs, 1.0, 1.0, 0.0
    ge = 0
    far = 0
    tot = 0.0
    tot2 = 0.0
    for _ in range(n_perm):
        perm = {}
        for band, idx in by_band.items():
            sc = [scores[i] for i in idx]
            rng.shuffle(sc)
            for i, v in zip(idx, sc):
                perm[i] = v
        t = sum(perm[i] for i in flipped)
        if t >= t_obs - 1e-12:
            ge += 1
        if abs(t) >= abs(t_obs) - 1e-12:
            far += 1
        tot += t
        tot2 += t * t
    mean = tot / n_perm
    sd = math.sqrt(max(tot2 / n_perm - mean * mean, 0.0))
    return t_obs, (ge + 1) / (n_perm + 1), (far + 1) / (n_perm + 1), sd


def cluster_robust_z(markets, bands, key="disc"):
    """Secondary, APPROXIMATE: the same rank statistic over every market,
    with a cluster-robust variance summed over closes. Only meaningful once
    there are tens of flipped closes; printed so the code is in place."""
    units = [m for m in markets if band_of(m["price"], bands) is not None]
    for u in units:
        u["band"] = band_of(u["price"], bands)
    scores = centred_ranks(units, key)
    by_band = defaultdict(list)
    for i, u in enumerate(units):
        by_band[u["band"]].append(i)
    ybar = {b: sum(units[i]["flip"] for i in idx) / len(idx)
            for b, idx in by_band.items()}
    per_close = defaultdict(float)
    for i, u in enumerate(units):
        per_close[u["close"]] += scores[i] * (u["flip"] - ybar[u["band"]])
    t = sum(per_close.values())
    v = sum(x * x for x in per_close.values())
    return t, (t / math.sqrt(v) if v > 0 else 0.0), len(per_close)


# ===========================================================================
# power / MDE
# ===========================================================================
def high_half(units, key="disc"):
    """Boolean list: is the unit above its band's median `key`? (strictly
    above; the median itself counts as low.)"""
    by_band = defaultdict(list)
    for u in units:
        by_band[u["band"]].append(u[key])
    med = {}
    for b, vals in by_band.items():
        vals.sort()
        n = len(vals)
        med[b] = vals[n // 2] if n % 2 else 0.5 * (vals[n // 2 - 1] + vals[n // 2])
    return [u[key] > med[u["band"]] for u in units]


def power_curve(units, base_rate, high_rates, n_sims, n_perm, rng, key="disc"):
    """Plant flip rate `hr` in the high-discount half and `base_rate` in the
    low half, rerun the SAME permutation test, and count rejections at
    ALPHA one-sided. Returns [(hr, power)]."""
    hi = high_half(units, key)
    out = []
    for hr in high_rates:
        rej = 0
        for _ in range(n_sims):
            flips = [rng.random() < (hr if h else base_rate) for h in hi]
            _, p1, _, _ = perm_test(units, flips, n_perm, rng, key)
            if p1 <= ALPHA:
                rej += 1
        out.append((hr, rej / n_sims))
    return out


def analytic_mde(n1, n2, p0, alpha=ALPHA, power=POWER_TARGET):
    """Normal-approximation MDE on a two-proportion one-sided test. With a
    base rate under 1% this is optimistic; the simulated curve is the one
    to quote."""
    if n1 <= 0 or n2 <= 0:
        return float("nan")
    za = ND.inv_cdf(1 - alpha)
    zb = ND.inv_cdf(power)
    return (za + zb) * math.sqrt(p0 * (1 - p0) * (1.0 / n1 + 1.0 / n2))


# ===========================================================================
# tables
# ===========================================================================
def _closes(ms):
    return len(set(m["close"] for m in ms))


def split_table(markets, bands, key="disc", label="discount", price_key="price"):
    """Per band: high vs low half of `key`, with n as markets AND closes,
    flips, rate and exact CP. Returns pooled (k_hi, n_hi, k_lo, n_lo) over
    the one-per-close units is done by the caller; here n is markets."""
    units = [m for m in markets if band_of(m[price_key], bands) is not None]
    for u in units:
        u["band"] = band_of(u[price_key], bands)
    hi = high_half(units, key)
    print(f"    {'band':<13}{'half':<6}{'mkts':>6}{'closes':>8}{'flips':>7}"
          f"   flip rate  [95% Clopper-Pearson]   median {label}")
    pooled = {"hi": [0, 0], "lo": [0, 0]}
    for band in bands:
        for which, want in (("hi", True), ("lo", False)):
            sub = [u for u, h in zip(units, hi) if u["band"] == band and h == want]
            if not sub:
                continue
            k = sum(1 for u in sub if u["flip"])
            n = len(sub)
            pooled[which][0] += k
            pooled[which][1] += n
            ds = sorted(u[key] for u in sub)
            print(f"    {band[0]:.3f}-{band[1]:.3f}  {which:<6}{n:>6}{_closes(sub):>8}"
                  f"{k:>7}   {rate_str(k, n)}   {100*ds[len(ds)//2]:6.2f}c")
    kh, nh = pooled["hi"]
    kl, nl = pooled["lo"]
    print(f"    {'pooled':<13}{'hi':<6}{nh:>6}{'':>8}{kh:>7}   {rate_str(kh, nh)}")
    print(f"    {'pooled':<13}{'lo':<6}{nl:>6}{'':>8}{kl:>7}   {rate_str(kl, nl)}")
    return kh, nh, kl, nl


def bucket_table(markets, edges, key="disc", label="discount"):
    print(f"    {label:<16}{'mkts':>6}{'closes':>8}{'flips':>7}   flip rate  [95% CP]")
    for lo, hi in zip(edges[:-1], edges[1:]):
        sub = [m for m in markets if lo <= m[key] < hi]
        k = sum(1 for m in sub if m["flip"])
        print(f"    {100*lo:5.1f}-{100*hi:5.1f}c     {len(sub):>6}{_closes(sub):>8}{k:>7}"
              f"   {rate_str(k, len(sub))}")


def band_table(markets, bands, price_key="price"):
    print(f"    {'price band':<16}{'mkts':>6}{'closes':>8}{'flips':>7}   flip rate  [95% CP]")
    for band in bands:
        sub = [m for m in markets if band_of(m[price_key], bands) == band]
        k = sum(1 for m in sub if m["flip"])
        print(f"    {band[0]:.3f}-{band[1]:.3f}     {len(sub):>6}{_closes(sub):>8}{k:>7}"
              f"   {rate_str(k, len(sub))}")


# ===========================================================================
# the report for one population
# ===========================================================================
def analyse(markets, bands, title, n_perm, n_sims, seed, quiet=False):
    rng = random.Random(seed)
    ms = list(markets.values())
    ms = [m for m in ms if band_of(m["price"], bands) is not None]
    n_mk = len(ms)
    n_cl = _closes(ms)
    k_all = sum(1 for m in ms if m["flip"])
    print(f"\n=== {title} ===")
    print(f"  population: markets: {n_mk}, closes: {n_cl}, flipped markets: {k_all}, "
          f"flipped closes: {len(set(m['close'] for m in ms if m['flip']))}")
    print(f"  flip rate per market {rate_str(k_all, n_mk)}")
    if n_mk == 0:
        print("  nothing passes the gate in this population.")
        return None

    # -- inference units ----------------------------------------------------
    opc = one_per_close({m["tk"]: m for m in ms})
    units = [dict(m) for _, m in sorted(opc.items())]
    for u in units:
        u["band"] = band_of(u["price"], bands)
    flips = [bool(u["flip"]) for u in units]
    k_u = sum(flips)
    n_u = len(units)
    base = k_u / n_u if n_u else 0.0
    print(f"  one-per-close units (first-hit market of each close): closes: {n_u}, "
          f"flipped: {k_u}  rate {rate_str(k_u, n_u)}")

    # -- MDE BEFORE the estimate -------------------------------------------
    hi = high_half(units)
    n_hi = sum(hi)
    n_lo = n_u - n_hi
    sim_base = max(base, 0.005)
    print(f"\n  MDE (stated before the estimate). Test: stratified rank permutation, "
          f"one-sided at alpha={ALPHA}, target power {POWER_TARGET:.0%}.")
    print(f"  halves: high-discount {n_hi} closes vs low-discount {n_lo} closes; "
          f"low-half flip rate assumed {100*sim_base:.2f}% "
          f"({'observed' if base >= 0.005 else 'floored at 0.5% because observed is lower'}).")
    am = analytic_mde(n_hi, n_lo, sim_base)
    print(f"  normal-approx MDE on the rate DIFFERENCE: {100*am:.2f} pct-points "
          f"(high half would need >= {100*(sim_base+am):.2f}% flips) -- optimistic at this base rate.")
    rates = [sim_base, 0.02, 0.05, 0.10, 0.25]
    pc = power_curve(units, sim_base, rates, n_sims, max(200, n_perm // 10), rng)
    print(f"  simulated power ({n_sims} worlds each), high-half flip rate -> P(reject):")
    mde_sim = None
    for hr, pw in pc:
        tag = " (null: should be ~alpha)" if abs(hr - sim_base) < 1e-12 else ""
        print(f"      {100*hr:6.2f}%  ->  {pw:5.2f}{tag}")
        if mde_sim is None and pw >= POWER_TARGET and hr > sim_base:
            mde_sim = hr
    if mde_sim is None:
        print(f"  simulated MDE: NOT REACHED at any planted rate up to 25% -- this sample "
              f"cannot see even the live-sized claim.")
    else:
        print(f"  simulated MDE: high half at >= {100*mde_sim:.0f}% flips vs {100*sim_base:.2f}% "
              f"is detectable with {POWER_TARGET:.0%} power; anything smaller is NOT.")

    # -- descriptive tables (n = markets, with closes alongside) -----------
    print(f"\n  A. flip rate by DISCOUNT-TO-FAIR bucket, ALL first-hit markets "
          f"(no price control -- for orientation only)")
    bucket_table(ms, [0.0, 0.01, 0.02, 0.04, 0.08, 1.0])
    print(f"\n  B. flip rate by PRICE band, ALL first-hit markets")
    band_table(ms, bands)
    print(f"\n  C. THE QUESTION: within each PRICE band, high- vs low-discount half "
          f"(halves split at the band's median discount)")
    kh, nh, kl, nl = split_table(ms, bands)
    print(f"\n  D. THE MIRROR: within each FAIR band, high- vs low-PRICE half "
          f"(the ladder's conditioning: cheaper at the same model confidence)")
    fm = [dict(m) for m in ms]
    split_table(fm, FAIR_BANDS, key="price", label="price", price_key="fair")

    # -- inference ---------------------------------------------------------
    print(f"\n  E. inference on the one-per-close units (n = {n_u} closes)")
    ku = sum(1 for u, h, y in zip(units, hi, flips) if h and y)
    kl_u = k_u - ku
    print(f"     high-discount half: {ku} flips in {n_hi} closes  {rate_str(ku, n_hi)}")
    print(f"     low-discount half:  {kl_u} flips in {n_lo} closes  {rate_str(kl_u, n_lo)}")
    t_obs, p1, p2, nsd = perm_test(units, flips, n_perm, rng)
    print(f"     stratified rank statistic T = {t_obs:+.1f} (sum of within-band centred "
          f"discount ranks of the flipped closes; null sd {nsd:.1f}, {n_perm} close-level shuffles)")
    print(f"     P(T_null >= T_obs) one-sided = {p1:.3f}   two-sided = {p2:.3f}")
    # the mirror on the same units
    fu = [dict(u) for u in units]
    for u in fu:
        u["band"] = band_of(u["fair"], FAIR_BANDS)
    fu2 = [u for u in fu if u["band"] is not None]
    fl2 = [bool(u["flip"]) for u in fu2]
    t_m, p1_m, p2_m, _ = perm_test(fu2, fl2, n_perm, rng, key="price")
    print(f"     mirror (price rank within FAIR band): T = {t_m:+.1f}, "
          f"P(T_null >= T_obs) = {p1_m:.3f} (high = DEARER flips more), two-sided {p2_m:.3f}")
    t_c, z_c, ncl = cluster_robust_z(fm, bands)
    print(f"     secondary, approximate: all-markets rank statistic with cluster-robust "
          f"variance over {ncl} closes: z = {z_c:+.2f} (only meaningful with tens of flipped closes)")
    return {"n_units": n_u, "k_units": k_u, "p1": p1, "p2": p2, "t": t_obs,
            "mde_sim": mde_sim, "n_hi": n_hi, "n_lo": n_lo, "kh": ku, "kl": kl_u,
            "p1_mirror": p1_m, "k_mk": k_all, "n_mk": n_mk, "n_cl": n_cl}


# ===========================================================================
# loading
# ===========================================================================
def load_rows(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


# ===========================================================================
# self-test
# ===========================================================================
def _synth_row(tk, sr, close, tau, price, fair, size=50.0, sig=1.0,
               side_yes=True, flip=False):
    """A row that the live gate will read as (price, fair). `req` is solved
    from `fair` so fair_of() reproduces it to machine precision."""
    r = tau
    sd = sig * math.sqrt(var_factor(r, [1.0]))
    fy = fair if side_yes else 1.0 - fair
    fy = min(max(fy, 1e-12), 1 - 1e-12)
    req = -ND.inv_cdf(fy) * sd * 60.0 / r
    return {"tk": tk, "sr": sr, "close": close, "sec": close - tau, "tau": tau,
            "r": r, "price": price, "size": size, "spread": 0.01,
            "dep_y": 100.0, "dep_n": 100.0, "age_ms": 100, "mu": 0.0, "req": req,
            "cov": 1.0, "spot": 0.0, "sig": sig, "s30": sig, "s120": sig,
            "tr5": 0.0, "tr15": 0.0, "dr15": 0.0, "dr60": 0.0, "jump": 0,
            "hour": 12, "side_yes": side_yes, "flip": flip}


def _synth_world(rng, n_closes, planted, base=0.01, high_rate=0.30):
    """n_closes closes x 6 markets. Each market gets a price in one of the
    bands and a fair in [0.981, 0.9999]; the flip probability is `base`
    everywhere in the null world, and `high_rate` for markets whose discount
    is in the top half of their band in the planted world. Flips are
    CLUSTERED: a close-level shock with prob `base` flips every market of
    the close, so the null world has the correlated structure the test must
    survive."""
    prices = [0.75, 0.85, 0.90, 0.95, 0.96, 0.975]
    fair_lo, fair_hi = 0.981, 0.9999
    # decide discount rank first so planting can target it
    rows = []
    markets = []
    for c in range(n_closes):
        close = 1_788_000_000 + 900 * c
        shock = rng.random() < base
        for j, p in enumerate(prices):
            fair = fair_lo + rng.random() * (fair_hi - fair_lo)
            tau = rng.randint(4, 30)
            markets.append((f"KXS{j}15M-{c}", f"KXS{j}15M", close, tau, p, fair, shock))
    # top-half discount per band
    by_band = defaultdict(list)
    for m in markets:
        by_band[band_of(m[4], BANDS)].append(m[5] - m[4])
    med = {b: sorted(v)[len(v) // 2] for b, v in by_band.items()}
    for tk, sr, close, tau, p, fair, shock in markets:
        hi = (fair - p) > med[band_of(p, BANDS)]
        if planted:
            flip = shock or (hi and rng.random() < high_rate)
        else:
            flip = shock
        # two rows per market: the first-hit (largest tau) and a later,
        # slightly different one, so dedupe has something to do
        rows.append(_synth_row(tk, sr, close, tau, p, fair, flip=flip))
        rows.append(_synth_row(tk, sr, close, max(3, tau - 1), p + 0.001, fair,
                               flip=flip))
    rng.shuffle(rows)
    return rows


def selftest():
    fails = []

    def ck(cond, msg):
        if not cond:
            fails.append(msg)
        print(("  ok   " if cond else "  FAIL ") + msg)

    print("pindisc self-test")
    # --- fair reconstruction -----------------------------------------------
    r0 = _synth_row("A", "A", 0, 10, 0.95, 0.99)
    f = fair_of(r0)
    ck(f is not None and abs(f[1] - 0.99) < 1e-9,
       f"fair_of reproduces a planted fair of 0.99: {f[1] if f else None:.9f}")
    r1 = dict(r0)
    r1["req"] = 0.0
    ck(abs(fair_of(r1)[0] - 0.5) < 1e-12, "req = 0 means fair_yes = 0.5")
    rn = _synth_row("A", "A", 0, 10, 0.95, 0.99, side_yes=False)
    fn = fair_of(rn)
    ck(fn is not None and abs(fn[1] - 0.99) < 1e-9 and fn[0] < 0.5,
       "NO-side row: fair_fav is 1 - fair_yes")

    # --- the gate ------------------------------------------------------------
    good = _synth_row("A", "A", 0, 10, 0.95, 0.99)
    ck(gate(good)[0], "a clean row passes the live gate")
    bad = [("tau", dict(good, tau=31, r=31)), ("tau", dict(good, tau=2, r=2)),
           ("fair", _synth_row("A", "A", 0, 10, 0.95, 0.975)),
           ("price", dict(good, price=0.985)), ("price", dict(good, price=0.5)),
           ("size", dict(good, size=9.9)),
           ("edge", _synth_row("A", "A", 0, 10, 0.979, 0.9805)),
           ("sd", dict(good, sig=0.0))]
    for why, row in bad:
        ok, got, _, _ = gate(row)
        ck((not ok) and got == why, f"gate rejects on '{why}': got '{got}'")
    # the EV gate binds above ~98.7c; with the ceiling lifted it must be the
    # only thing that stops a 99c row
    dear = _synth_row("A", "A", 0, 10, 0.99, 0.9999)
    ck(gate(dear, ceiling=1.0)[1] == "ev", "EV floor rejects 99c when the ceiling is lifted")
    ck(gate(dear, ceiling=1.0, ev_gate=False)[0], "...and without it the row passes")
    ck(abs(billed_fee(0.16, 12.37) - 0.1164) < 1e-9 or
       abs(math.ceil(0.07 * 0.16 * 0.84 * 12.37 * 10000 - 1e-9) / 10000 - 0.1164) < 1e-9,
       "fee arithmetic matches the operator's real charge (12.37 @ 16c = $0.1164)")

    # --- dedupe --------------------------------------------------------------
    rows = [_synth_row("M1", "S", 100, 8, 0.95, 0.99), _synth_row("M1", "S", 100, 20, 0.94, 0.99),
            _synth_row("M1", "S", 100, 12, 0.93, 0.99),
            _synth_row("M2", "S", 100, 15, 0.95, 0.99), _synth_row("M3", "S", 200, 15, 0.95, 0.99)]
    mk, reasons = first_hit_per_market(rows)
    ck(len(mk) == 3 and mk["M1"]["tau"] == 20 and abs(mk["M1"]["price"] - 0.94) < 1e-12,
       "first-hit per market keeps the LARGEST tau row, not the cheapest")
    opc = one_per_close(mk)
    ck(len(opc) == 2 and opc[100]["tk"] == "M1", "one-per-close keeps the earliest-firing market")
    rows2 = rows + [_synth_row("M4", "S", 100, 20, 0.95, 0.99)]
    opc2 = one_per_close(first_hit_per_market(rows2)[0])
    ck(opc2[100]["tk"] == "M1", "ties on tau break by ticker order (deterministic)")

    # --- Clopper-Pearson -----------------------------------------------------
    lo, hi = cp_interval(0, 147)
    ck(lo == 0.0 and abs(hi - (1 - 0.025 ** (1 / 147))) < 1e-7,
       f"CP 0/147 upper = 1 - 0.025^(1/147) = {100*hi:.3f}%")
    lo, hi = cp_interval(147, 147)
    ck(hi == 1.0 and abs(lo - 0.025 ** (1 / 147)) < 1e-7, "CP n/n lower = 0.025^(1/n)")

    def brute_cdf(k, n, p):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
    lo, hi = cp_interval(2, 254)
    ck(abs(1 - brute_cdf(1, 254, lo) - 0.025) < 1e-6 and abs(brute_cdf(2, 254, hi) - 0.025) < 1e-6,
       f"CP 2/254 = [{100*lo:.3f}%, {100*hi:.3f}%] reproduces the binomial tails exactly")
    lo, hi = cp_interval(5, 57)
    ck(0.029 < lo < 0.030 and 0.19 < hi < 0.20,
       f"CP 5/57 (the live record) = [{100*lo:.2f}%, {100*hi:.2f}%]")

    # --- ranks ---------------------------------------------------------------
    us = [{"band": "a", "disc": 1}, {"band": "a", "disc": 3}, {"band": "a", "disc": 2},
          {"band": "b", "disc": 5}, {"band": "b", "disc": 5}]
    ck(centred_ranks(us) == [-1.0, 1.0, 0.0, 0.0, 0.0],
       "centred ranks are within-band and tie-averaged")

    # --- the estimator, planted vs null -----------------------------------
    rng = random.Random(7)
    planted = _synth_world(rng, 150, planted=True)
    mk_p, _ = first_hit_per_market(planted)
    ck(len(mk_p) == 900, f"synthetic world: {len(mk_p)} markets pass the gate (900 expected)")
    units = [dict(m) for _, m in sorted(one_per_close(mk_p).items())]
    for u in units:
        u["band"] = band_of(u["price"], BANDS)
    fl = [bool(u["flip"]) for u in units]
    t, p1, p2, _ = perm_test(units, fl, 2000, rng)
    ck(p1 < 0.01, f"PLANTED (high half flips 30% vs 1%): one-sided p = {p1:.4f} < 0.01 on "
                  f"{len(units)} closes, T = {t:+.1f}")
    hi = high_half(units)
    kh = sum(1 for h, y in zip(hi, fl) if h and y)
    kl = sum(1 for h, y in zip(hi, fl) if (not h) and y)
    ck(kh > 3 * max(kl, 1), f"planted split shows it: high {kh} flips vs low {kl}")

    null = _synth_world(rng, 150, planted=False)
    mk_n, _ = first_hit_per_market(null)
    units_n = [dict(m) for _, m in sorted(one_per_close(mk_n).items())]
    for u in units_n:
        u["band"] = band_of(u["price"], BANDS)
    fl_n = [bool(u["flip"]) for u in units_n]
    t, p1n, _, _ = perm_test(units_n, fl_n, 2000, rng)
    ck(p1n >= 0.05, f"NULL world (nothing planted, flips clustered by close): p = {p1n:.3f} >= 0.05")
    # false-positive rate over many null worlds, one-sided alpha 0.05
    rej = 0
    worlds = 40
    for w in range(worlds):
        rw = random.Random(1000 + w)
        nw = _synth_world(rw, 150, planted=False, base=0.03)
        mkw, _ = first_hit_per_market(nw)
        uw = [dict(m) for _, m in sorted(one_per_close(mkw).items())]
        for u in uw:
            u["band"] = band_of(u["price"], BANDS)
        fw = [bool(u["flip"]) for u in uw]
        _, pw, _, _ = perm_test(uw, fw, 400, rw)
        rej += pw <= ALPHA
    ck(rej <= 6, f"false-positive rate over {worlds} null worlds: {rej}/{worlds} rejected "
                 f"(expect ~2, allow <= 6)")

    # --- power routine -------------------------------------------------------
    pc = power_curve(units_n, 0.01, [0.01, 0.50], 40, 200, random.Random(3))
    ck(pc[0][1] <= 0.20, f"power at NO effect is near alpha: {pc[0][1]:.2f}")
    ck(pc[1][1] >= 0.90, f"power at a huge effect (50% vs 1%) is near 1: {pc[1][1]:.2f}")

    print(f"\nself-test: {'PASS' if not fails else 'FAIL'} ({len(fails)} failures)")
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--rows", default=DEFAULT_ROWS)
    ap.add_argument("--perms", type=int, default=4000)
    ap.add_argument("--sims", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260910)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        print("self-test failed; refusing to touch real data")
        raise SystemExit(1)
    if a.quick:
        a.perms, a.sims = 500, 40

    path = os.path.abspath(a.rows)
    if not os.path.exists(path):
        print(f"pindisc: {path} does not exist -- nothing to analyse")
        return 0
    rows = load_rows(path)
    print(f"\npindisc: {len(rows):,} rows from {path}")
    if not rows:
        print("pindisc: the table is empty -- nothing to analyse")
        return 0
    closes_all = set(r["close"] for r in rows)
    span = (min(r["sec"] for r in rows), max(r["sec"] for r in rows))
    import time as _t
    print(f"  span {_t.strftime('%Y-%m-%d %H:%MZ', _t.gmtime(span[0]))} to "
          f"{_t.strftime('%Y-%m-%d %H:%MZ', _t.gmtime(span[1]))}, closes in table: {len(closes_all)}, "
          f"markets in table: {len(set(r['tk'] for r in rows))}")
    print("  rows are (market, second) observations; they are NOT the unit of anything below.")

    # PRIMARY: the live gate
    mk, reasons = first_hit_per_market(rows)
    print(f"\n  live gate (3<=tau<=30, fair>=0.98, side agrees, 0.5<price<=0.980, size>=10, "
          f"net edge>=0.3c at 20, EV>=0.3c at 0.9% flip):")
    print(f"    rows rejected by reason: " + ", ".join(f"{k}={v:,}" for k, v in sorted(reasons.items())))
    if not mk:
        print("  no row survives the live gate -- nothing to analyse")
        return 0
    res = analyse(mk, BANDS, "PRIMARY: the live population (price ceiling 98.0c)",
                  a.perms, a.sims, a.seed)

    # SECONDARY: ceiling lifted, EV gate dropped -- NOT the live population
    mk2, reasons2 = first_hit_per_market(rows, ceiling=0.9999, ev_gate=False)
    print(f"\n  relaxed gate rejections: " + ", ".join(f"{k}={v:,}" for k, v in sorted(reasons2.items())))
    res2 = analyse(mk2, BANDS_RELAXED,
                   "SECONDARY: ceiling lifted to 99.99c, EV gate off -- NOT the live population, "
                   "shown for power only", a.perms, a.sims, a.seed + 1)

    # -- adversarial notes ---------------------------------------------------
    print("\n=== read before believing ===")
    print("  * within a price band, discount = fair - price moves through FAIR; a 'high-discount'")
    print("    unit is one where the MODEL is more confident. Table C therefore tests whether the")
    print("    model's extra confidence is informative (fewer flips), uninformative, or")
    print("    anti-informative (more flips: the adverse-selection story). Table D is the mirror.")
    print("  * the permutation is over CLOSES on one-per-close units. Any per-market number in")
    print("    tables A-D is descriptive; its CP interval treats markets as independent and is")
    print("    therefore too NARROW by up to ~14x in effective n when markets share a close.")
    print("  * the flipped closes are few. Check by hand which band and half each one sits in")
    print("    before reading any rate as a rate; one close moving halves changes the sign.")
    if res is not None:
        k = res["k_units"]
        print(f"  * PRIMARY one-per-close: {k} flipped close(s) in {res['n_units']}; a permutation")
        print(f"    p-value on {k} events can never go below ~{1.0/(res['n_units']):.3f} per event, so")
        print(f"    a p of {res['p1']:.3f} is a statement about {k} coin(s), not about the population.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
