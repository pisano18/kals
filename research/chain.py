#!/usr/bin/env python3
# VERSION: 2026-08-25-c1
"""
chain.py -- everything you can learn WITHOUT the index feed.

    python chain.py --selftest                       # prove the harness first
    python chain.py --series KXBTC15M --markets 3000 # then real data

THE OBSERVATION THIS IS BUILT ON

Window N+1 opens at exactly the moment window N closes. So:

    strike(N+1) = mean of the 60 BRTI ticks before open(N+1)
    settle(N)   = mean of the 60 BRTI ticks before close(N)

open(N+1) == close(N), so those are averages over THE SAME SIXTY SECONDS.
They must be equal, to the cent.

Two consequences, both large:

1. GATE. This is a stronger settlement gate than kalshi_gate1.py and it needs
   NO index data -- only public settled-market records. If the chain does not
   close to the cent, we do not understand the contract and everything else
   stops. kalshi_gate1.py can only run on markets that closed inside the
   recording window; this runs on all settled history, today.

2. FREE DATA. The chain settle(1), settle(2), ... IS a time series of 60-second
   TWAPs spaced 15 minutes apart, per asset, going back as far as settled
   markets are served. We never had to record it. Every window's return is
   exactly (settle - strike), the quantity the contract pays on.

WHAT THAT SERIES ANSWERS, with no BRTI and no collector

  * sigma, per series, per regime -- the ONE free parameter of the fair-value
    model. Get this wrong and every probability is wrong.
  * Does sigma cluster? Crypto vol is GARCH-like. If the book quotes a slow
    sigma and we quote a fast one, we are right more often at both ends. That
    is the most durable edge shape available here and it needs no forecasting
    of direction.
  * Does window return N predict window return N+1? If yes, that is a signal
    available AT THE OPEN, the most liquid moment, requiring nothing but the
    previous window's settled result.
  * Time-of-day volatility seasonality -- when is a fixed sigma most wrong?
  * Fat tails, per series, done without pooling assets whose kurtosis ranges
    25 to 153.

DISCIPLINE

Every test below is also run on synthetic data with a KNOWN answer (--selftest)
before it is allowed near real data. A test that cannot recover an effect it
was told to find, or that invents one in clean noise, is not a test. This
project's history is of measurement bugs producing fake edges; the fix is not
care, it is calibration.

Multiple testing is counted and reported explicitly at the end. Sweeping k
tests at p<0.05 yields 0.05k false positives by construction.
"""

import argparse
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from statistics import NormalDist, mean, median, pstdev

ND = NormalDist()
BASE = "https://api.elections.kalshi.com/trade-api/v2"
WINDOW = 900          # seconds between consecutive closes
# A cached series older than this is refreshed even when it is
# already long enough. Size alone let KXBTC15M -- the anchor of the
# whole detectability table -- supply a report from a ~10-hour-old
# cache, with nothing in the output saying so.
STALE_HOURS = 6.0

CRYPTO_15M = ["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M",
              "KXBNB15M", "KXADA15M", "KXBCH15M", "KXZEC15M", "KXHYPE15M",
              "KXNEAR15M", "KXTON15M"]


# ===========================================================================
# plumbing
# ===========================================================================
def parse_ts(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s if s < 1e12 else s / 1000.0)
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def fetch_settled(series, want, verbose=True, stats=None, session=None,
                  sleep=time.sleep, tries=5):
    """Public endpoint, no key. /historical/* is stale (RUNBOOK) -- not used.

    A page that fails is RETRIED, not surrendered to. The old version broke
    out of the loop on any non-200 and on any exception, which turned a single
    HTTP 429 -- the routine consequence of paginating a 200-row endpoint
    thousands of times -- into a silently short series. Worse, it returned
    that short list with no way for the caller to tell "this is the whole
    history" from "we gave up here", so a truncated pull was reported as a
    finding about the market.

    `stats` (a dict, filled in place) now carries that distinction:
        pages     pages actually fetched
        http      the last non-200 status seen, if any
        retries   how many retries were spent
        stopped   'want' | 'exhausted' | 'gave_up' | 'empty'
        truncated True when the history is short because WE failed
    """
    if stats is None:
        stats = {}
    stats.update({"pages": 0, "http": None, "retries": 0,
                  "stopped": "empty", "truncated": False})
    if session is None:
        try:
            import requests
        except ImportError:
            raise SystemExit(
                "\n  This stage needs `requests`, which is not installed for "
                "this\n  interpreter. Install it with:\n\n"
                f"      {sys.executable} -m pip install requests\n\n"
                "  Every other stage is stdlib-only and will run without it.")
        session = requests.Session()

    out, cursor, pages = [], None, 0
    while len(out) < want and pages < 200:
        p = {"series_ticker": series, "status": "settled", "limit": 200}
        if cursor:
            p["cursor"] = cursor

        js = None
        for attempt in range(tries):
            try:
                r = session.get(BASE + "/markets", params=p, timeout=30)
                if r.status_code == 200:
                    js = r.json()
                    break
                stats["http"] = r.status_code
                # 4xx that is not 429 will not become 200 by asking again.
                if r.status_code != 429 and r.status_code < 500:
                    if verbose:
                        print(f"    HTTP {r.status_code}: "
                              f"{getattr(r, 'text', '')[:160]}")
                    break
                wait = None
                try:
                    ra = r.headers.get("Retry-After")
                    if ra is not None:
                        wait = float(ra)
                except (AttributeError, TypeError, ValueError):
                    wait = None
                if wait is None:
                    wait = 0.5 * (2 ** attempt)         # 0.5 1 2 4 8
                if attempt == tries - 1:
                    if verbose:
                        print(f"    HTTP {r.status_code} after {tries} tries; "
                              f"giving up on this page")
                    break
                if verbose:
                    print(f"    HTTP {r.status_code}, retry "
                          f"{attempt + 1}/{tries - 1} in {wait:.1f}s")
                stats["retries"] += 1
                sleep(wait)
            except Exception as e:
                stats["http"] = type(e).__name__
                if attempt == tries - 1:
                    if verbose:
                        print(f"    {type(e).__name__}: {e} -- giving up")
                    break
                wait = 0.5 * (2 ** attempt)
                if verbose:
                    print(f"    {type(e).__name__}: {e}; retry "
                          f"{attempt + 1}/{tries - 1} in {wait:.1f}s")
                stats["retries"] += 1
                sleep(wait)

        if js is None:
            # Out of retries with pages still to go: the history is short
            # because we failed, not because it ended.
            stats["stopped"] = "gave_up"
            stats["truncated"] = True
            break

        b = js.get("markets", [])
        if not b:
            stats["stopped"] = "exhausted"
            break
        for m in b:
            try:
                k = float(m.get("floor_strike") or m.get("strike"))
                v = float(m["expiration_value"])
                c = parse_ts(m.get("close_time"))
                o = parse_ts(m.get("open_time"))
            except (KeyError, TypeError, ValueError):
                continue
            if k and v and c:
                out.append({"ticker": m["ticker"], "strike": k, "settle": v,
                            "close": c, "open": o})
        cursor = js.get("cursor")
        pages += 1
        stats["pages"] = pages
        if not cursor:
            stats["stopped"] = "exhausted"
            break
        if len(out) >= want:
            stats["stopped"] = "want"
            break
        sleep(0.08)                            # Basic tier ~20 reads/s
    else:
        stats["stopped"] = "want" if len(out) >= want else "gave_up"
    return out


def build_chains(mkts):
    """Split into runs of consecutive windows (close times exactly 900s apart).
    A gap breaks the chain -- we must never difference across a hole."""
    by_close = {}
    dupes = 0
    for m in sorted(mkts, key=lambda x: x["close"]):
        c = int(round(m["close"]))
        if c in by_close:
            dupes += 1
            continue
        by_close[c] = m
    times = sorted(by_close)
    chains, cur = [], []
    for i, t in enumerate(times):
        if not cur:
            cur = [by_close[t]]
            continue
        if t - int(round(cur[-1]["close"])) == WINDOW:
            cur.append(by_close[t])
        else:
            if len(cur) > 1:
                chains.append(cur)
            cur = [by_close[t]]
    if len(cur) > 1:
        chains.append(cur)
    return chains, dupes


# ===========================================================================
# statistics -- deliberately simple, and each one self-tested
# ===========================================================================
def autocorr(x, lag):
    n = len(x)
    if n <= lag + 5:
        return None
    m = mean(x)
    num = sum((x[i] - m) * (x[i + lag] - m) for i in range(n - lag))
    den = sum((v - m) ** 2 for v in x)
    return num / den if den > 0 else None


# ---------------------------------------------------------------------------
# THE NULL FOR CONSECUTIVE-WINDOW RETURN AUTOCORRELATION IS NOT ZERO.
#
# settle(N) is the mean of the 60 index prints ending at T_N = N*900, and
# r_N = settle(N) - settle(N-1). For a driftless random walk,
#   Cov(avg over [a,b], avg over [c,d]) = (a+b)/2   for b < c
#   Var(avg over [a,b])                 = a + (b-a)/3
# which gives Cov(r_N, r_N+1) = 10*sigma^2 against Var(r) = 880*sigma^2, so
#
#   rho_1 = 10/880 = 1/88 = +0.011364
#
# purely from the overlapping-average structure. No market, no inefficiency,
# just arithmetic. Verified by simulating 60,000 windows of a pure random walk:
# rho_1 = +0.0127, which is t = +3.12 against a ZERO null and t = +0.34 against
# this one. Testing against zero would report a screaming signal from nothing.
# ---------------------------------------------------------------------------
TWAP_RHO1 = 10.0 / 880.0


def ac_t(x, lag, null=0.0):
    """t-stat for autocorrelation against `null` (SE ~ 1/sqrt(n))."""
    r = autocorr(x, lag)
    if r is None:
        return None, None
    return r, (r - null) * math.sqrt(len(x) - lag)


def segments_of(rows, field="r"):
    """Split the flat row list back into its chains.

    build_chains exists to guarantee we never difference across a hole, and
    chain_returns then concatenated every chain into one list -- so lag-1
    autocorrelation happily paired the last window before a two-day gap with
    the first window after it. The pairs that straddle a hole are not
    consecutive 15-minute windows and carry none of the overlap structure the
    null is built on; including them biases every lag toward zero and inflates
    n, which is the wrong direction on both counts.
    """
    segs, cur, cid = [], [], object()
    for x in rows:
        c = x.get("chain")
        if c != cid:
            if len(cur) > 1:
                segs.append(cur)
            cur, cid = [], c
        cur.append(x[field])
    if len(cur) > 1:
        segs.append(cur)
    return segs


def autocorr_seg(segs, lag):
    """Pooled autocorrelation over WITHIN-chain pairs only.

    Returns (r, n_pairs). The variance is pooled across everything (it is not
    a lagged quantity) and rescaled to the pairs actually used, so r stays a
    correlation instead of being shrunk by the pairs the holes removed.
    """
    allv = [v for sg in segs for v in sg]
    n = len(allv)
    if n <= lag + 5:
        return None, 0
    m = mean(allv)
    den = sum((v - m) ** 2 for v in allv)
    if den <= 0:
        return None, 0
    num, npairs = 0.0, 0
    for sg in segs:
        for i in range(len(sg) - lag):
            num += (sg[i] - m) * (sg[i + lag] - m)
            npairs += 1
    if npairs == 0:
        return None, 0
    return num / (den * npairs / n), npairs


def ac_t_seg(segs, lag, null=0.0):
    r, npairs = autocorr_seg(segs, lag)
    if r is None:
        return None, None
    return r, (r - null) * math.sqrt(npairs)


# ---------------------------------------------------------------------------
# WHY 1/sqrt(n) IS THE WRONG RULER FOR |r|
#
# ac_t_seg divides by 1/sqrt(npairs). That SE is derived under INDEPENDENCE.
# It is the right ruler for the returns, which are near-independent. It is the
# wrong ruler for |returns|, whose entire claim is that they are strongly
# dependent -- and a dependent series carries far less information per
# observation than n independent ones do. Applying the iid SE to |r| tests a
# dependence claim with a ruler that assumes the claim is false, and inflates
# the t-stat by however true the claim happens to be.
#
# The fix is a moving-block bootstrap: resample CONTIGUOUS runs, so every
# resample keeps the local dependence intact, and read the SE off the spread
# of the statistic across resamples. Blocks never straddle a chain boundary,
# for the same reason segments_of exists.
#
# This matters because volatility clustering is the one finding in this
# project that has survived everything. It deserves to be measured with a
# ruler that does not assume its own conclusion.
# ---------------------------------------------------------------------------
def block_len(n, lag=0):
    """n^(1/3) -- the standard MBB rate -- floored so a block spans the lag
    being measured. A block shorter than the lag holds no pair at that lag, so
    the bootstrap would be resampling nothing but edge effects."""
    b = int(round(n ** (1.0 / 3.0)))
    return max(lag + 1, 2, min(b, max(2, n // 4)))


def _blocks(cols, b):
    """cols is a tuple of per-segment aligned lists (P, V) or (X,). Returns
    (prefix_tuples, starts) where starts is every legal (segment, offset)."""
    pref, starts = [], []
    for j, seg in enumerate(zip(*cols)):
        # seg is a tuple of the aligned lists for segment j
        L = len(seg[0])
        if L < b:
            continue
        ps = []
        for arr in seg:
            c = [0.0] * (L + 1)
            for i, v in enumerate(arr):
                c[i + 1] = c[i] + v
            ps.append(c)
        idx = len(pref)
        pref.append(ps)
        starts.extend((idx, s) for s in range(L - b + 1))
    return pref, starts


def _pair_series(segs, lag):
    """Per-segment (P, V) arrays about the pooled mean, index-aligned so a
    block drawn from one is the same block drawn from the other.

    P is the lag-`lag` cross-product; V the squared deviation. The pooled
    autocorrelation is mean(P) / mean(V), so bootstrapping the two together
    bootstraps the ratio without ever re-centering on resampled data."""
    allv = [v for sg in segs for v in sg]
    if len(allv) <= lag + 5:
        return None, None
    m = mean(allv)
    P, V = [], []
    for sg in segs:
        if len(sg) <= lag:
            continue
        P.append([(sg[i] - m) * (sg[i + lag] - m) for i in range(len(sg) - lag)])
        V.append([(sg[i] - m) ** 2 for i in range(len(sg) - lag)])
    return P, V


def ac_block_se(segs, lag, B=1000, seed=20260827, block=None):
    """Moving-block-bootstrap SE of the pooled autocorrelation.

    Returns (se, block_len, npairs); se is None if the bootstrap cannot run
    (every chain shorter than one block, or a degenerate denominator).
    """
    P, V = _pair_series(segs, lag)
    if not P:
        return None, None, 0
    npairs = sum(len(x) for x in P)
    b = block or block_len(npairs, lag)
    pref, starts = _blocks((P, V), b)
    if not starts:
        return None, b, npairs
    k = max(1, int(math.ceil(npairs / float(b))))
    rng = random.Random(seed)
    pick = rng.randrange
    nst = len(starts)
    out = []
    for _ in range(B):
        sp = sv = 0.0
        for _ in range(k):
            j, s = starts[pick(nst)]
            cp, cv = pref[j]
            sp += cp[s + b] - cp[s]
            sv += cv[s + b] - cv[s]
        if sv > 0:
            out.append(sp / sv)
    if len(out) < 50:
        return None, b, npairs
    return pstdev(out), b, npairs


def ac_t_block(segs, lag, null=0.0, B=1000, seed=20260827):
    """(r, t, se, block) using the block-bootstrap SE.

    Falls back to the iid t only when the bootstrap cannot run, and signals
    that by returning se=None -- a caller printing a t must be able to say
    which ruler produced it.
    """
    r, npairs = autocorr_seg(segs, lag)
    if r is None:
        return None, None, None, None
    se, b, _ = ac_block_se(segs, lag, B=B, seed=seed)
    if not se or se <= 0:
        return r, (r - null) * math.sqrt(npairs), None, None
    return r, (r - null) / se, se, b


def block_mean_se(seg_lists, B=1000, seed=20260827, block=None):
    """Moving-block-bootstrap SE for the mean of a within-chain series.

    The sign-persistence test used sqrt(0.25/n) -- the SE of a mean of
    INDEPENDENT Bernoullis. If direction persists at all, consecutive
    indicators are not independent and that SE is too small, in the direction
    that manufactures significance.
    """
    n = sum(len(x) for x in seg_lists)
    if n < 30:
        return None, None
    b = block or block_len(n)
    pref, starts = _blocks((seg_lists,), b)
    if not starts:
        return None, b
    k = max(1, int(math.ceil(n / float(b))))
    rng = random.Random(seed)
    pick = rng.randrange
    nst = len(starts)
    out = []
    for _ in range(B):
        t = 0.0
        for _ in range(k):
            j, s = starts[pick(nst)]
            c = pref[j][0]
            t += c[s + b] - c[s]
        out.append(t / (k * b))
    return pstdev(out), b


def box_pierce_seg(segs, lags=5):
    """Sum_k n_k * r_k^2 ~ chi2(lags) under the null. The classic Ljung-Box
    n(n+2)/(n-k) correction assumes one unbroken series; with chains the
    honest sample size is the pair count at each lag."""
    q = 0.0
    for k in range(1, lags + 1):
        r, npairs = autocorr_seg(segs, k)
        if r is None:
            continue
        q += npairs * r * r
    return q


def ljung_box(x, lags=5):
    n = len(x)
    q = 0.0
    for k in range(1, lags + 1):
        r = autocorr(x, k)
        if r is None:
            continue
        q += r * r / (n - k)
    return n * (n + 2) * q          # ~ chi2(lags) under the null


def excess_kurtosis(x):
    n = len(x)
    m = mean(x)
    m2 = sum((v - m) ** 2 for v in x) / n
    m4 = sum((v - m) ** 4 for v in x) / n
    return (m4 / (m2 * m2) - 3.0) if m2 > 0 else float("nan")


# ===========================================================================
# the tests
# ===========================================================================
def gate_chain(chains, label, tol=1e-6):
    """strike(N+1) must equal settle(N). The whole contract in one identity."""
    errs, n = [], 0
    for ch in chains:
        for a, b in zip(ch, ch[1:]):
            n += 1
            if a["settle"] > 0:
                errs.append(abs(b["strike"] - a["settle"]) / a["settle"])
    if not errs:
        print(f"  {label:>11}: no consecutive pairs")
        return None
    errs.sort()
    med, p90, mx = errs[len(errs) // 2], errs[int(len(errs) * .9)], errs[-1]
    exact = sum(1 for e in errs if e < tol) / len(errs)
    # Verdict must key on the WORST case, not the median. Corrupting every 7th
    # pair leaves the median at exactly 0 -- an earlier version printed PASS on
    # data it had already flagged as 85.7% exact.
    verdict = ("PASS" if (exact > 0.995 and p90 < 1e-6)
               else "MARGINAL" if (exact > 0.95 and med < 1e-4)
               else "*FAIL*")
    print(f"  {label:>11}{n:>8,}{med:>12.2e}{p90:>12.2e}{mx:>12.2e}"
          f"{100*exact:>9.1f}%   {verdict}")
    return {"n": n, "median": med, "exact_frac": exact}


def chain_returns(chains):
    """Log returns of the TWAP chain. Each one IS a window's (settle-strike)."""
    rows = []
    for ci, ch in enumerate(chains):
        for m in ch:
            if m["strike"] > 0 and m["settle"] > 0:
                # Ties score 0.5, not 1.0. `settle >= strike` counted every
                # exact tie as an up-move: XRP has 57 ties in 1,994 windows,
                # which is 51.15% with the old convention against 48.29%
                # strictly above -- the convention moved the number by MORE
                # than the deviation being reported, and flipped its sign.
                # Neither ">=" nor ">" is defensible when the tie count is
                # comparable to the effect; 0.5 is the only neutral choice,
                # and the count is now reported so it cannot hide again.
                up = (1.0 if m["settle"] > m["strike"]
                      else 0.5 if m["settle"] == m["strike"] else 0.0)
                rows.append({"r": math.log(m["settle"] / m["strike"]),
                             "close": m["close"], "chain": ci,
                             "tie": 1.0 if m["settle"] == m["strike"] else 0.0,
                             "up": up})
    return rows


def report_sigma(rows, label):
    """sigma per second, the single free parameter of the fair-value model."""
    if len(rows) < 50:
        return None
    r = [x["r"] for x in rows]
    sd_window = pstdev(r)
    # Var(settle-strike) = 880 sigma^2  (verified exactly in settlement_math.py)
    sig_s = sd_window / math.sqrt(880.0)
    ann = sd_window / math.sqrt(880.0) * math.sqrt(365 * 24 * 3600) * 100
    up = mean([x["up"] for x in rows])
    ties = sum(x.get("tie", 0.0) for x in rows)
    # ties contribute zero variance under the 0.5 convention, so the effective
    # n for the binomial SE is the number of windows that actually resolved
    n_eff = max(len(rows) - ties, 1)
    se_up = math.sqrt(0.25 / n_eff)
    print(f"  {label:>11}{len(rows):>7,}{100*sd_window:>11.4f}%"
          f"{1e6*sig_s:>13.2f}{ann:>10.1f}%{100*up:>9.2f}%"
          f"{(up-0.5)/se_up:>8.1f}{int(ties):>7,}")
    return {"sd": sd_window, "sigma_s": sig_s, "n": len(rows),
            "up": up, "ties": int(ties)}


def test_vol_clustering(rows, label):
    """Does |return| predict the NEXT |return|? If the book quotes a slow
    sigma, a fast one is a durable edge with no directional view."""
    if len(rows) < 200:
        return None
    segs = segments_of([{"r": abs(x["r"]), "chain": x.get("chain")}
                        for x in rows])
    a = [v for sg in segs for v in sg]
    if len(a) < 200:
        return None
    r1, t1, se1, b1 = ac_t_block(segs, 1)
    _, t_iid = ac_t_seg(segs, 1)
    r5, _ = ac_t_seg(segs, 5)
    r20, _ = ac_t_seg(segs, 20)
    if r1 is None or r5 is None or r20 is None:
        return None
    lb = box_pierce_seg(segs, 5)
    print(f"  {label:>11}{len(a):>7,}{r1:>9.3f}{t1:>8.1f}{t_iid:>8.1f}"
          f"{r5:>9.3f}{r20:>9.3f}{lb:>10.1f}   "
          f"{'CLUSTERS' if t1 > 3 else 'weak' if t1 > 2 else 'no'}")
    return {"ac1": r1, "t": t1, "t_iid": t_iid, "se": se1, "block": b1}


def test_return_autocorr(rows, label):
    """Does window N's direction predict window N+1? Tradeable AT THE OPEN."""
    if len(rows) < 200:
        return None
    segs = segments_of(rows)
    r = [v for sg in segs for v in sg]
    if len(r) < 200:
        return None
    # lag 1 carries the mechanical TWAP-overlap term; lag 2 does not (the
    # windows are far enough apart that the covariance is exactly zero).
    # Both are measured within chains only -- the overlap term the null
    # encodes exists between CONSECUTIVE windows and nowhere else, so a pair
    # spanning a gap is being tested against a null that does not apply to it.
    r1, t1, se1, b1 = ac_t_block(segs, 1, null=TWAP_RHO1)
    r2, t2, _, _ = ac_t_block(segs, 2)
    _, t1_iid = ac_t_seg(segs, 1, null=TWAP_RHO1)
    if r1 is None or r2 is None:
        return None
    # sign persistence is the tradeable version -- also within-chain only
    # Ties (r == 0 exactly; XRP alone has 57) are EXCLUDED from the pairs,
    # not forced into the down class. chain_returns argues at length above
    # that lumping ties one side is indefensible for the up-rate, and the old
    # code here did exactly that anyway: unequal classes give a symmetric iid
    # series an agreement rate of 0.5 + q^2/2, a positive bias under the
    # test's own null.
    same = npairs = 0
    for sg in segs:
        for i in range(len(sg) - 1):
            a_, b_ = sg[i], sg[i + 1]
            if a_ == 0.0 or b_ == 0.0:
                continue
            npairs += 1
            if (a_ > 0) == (b_ > 0):
                same += 1
    if npairs < 100:
        return None
    frac = same / npairs
    se = math.sqrt(0.25 / npairs)
    print(f"  {label:>11}{len(r):>7,}{r1:>10.4f}{t1:>8.1f}{t1_iid:>8.1f}"
          f"{r2:>10.4f}{t2:>8.1f}{100*frac:>10.2f}%{(frac-0.5)/se:>8.1f}   "
          f"{'SIGNAL' if abs(t1) > 3 else 'weak' if abs(t1) > 2 else 'no'}")
    return {"ac1": r1, "t": t1, "t_iid": t1_iid, "se": se1, "block": b1,
            "sign_frac": frac, "sign_t": (frac - 0.5) / se}


def test_hour_of_day(rows, label):
    """When is a fixed sigma most wrong? Also: is the up-rate regime-dependent?"""
    if len(rows) < 500:
        return None
    by = defaultdict(list)
    for x in rows:
        h = datetime.fromtimestamp(x["close"], timezone.utc).hour
        by[(h // 4) * 4].append(x["r"])
    base = pstdev([x["r"] for x in rows])
    parts = []
    for h in sorted(by):
        v = by[h]
        if len(v) < 40:
            continue
        parts.append(f"{h:02d}h {pstdev(v)/base:.2f}x")
    print(f"  {label:>11}  " + "  ".join(parts))
    return None


def test_tails(rows, label):
    """Per series. Ratio of observed to Gaussian exceedance at each threshold.
    >1 means fatter than Gaussian at that quantile. The crossover is the price
    at which a Gaussian model flips from under- to over-valuing the favourite."""
    if len(rows) < 300:
        return None
    r = sorted(x["r"] for x in rows)
    # THIS USED TO DELETE THE EXTREMES AND THEN STANDARDISE BY THE SURVIVORS'
    # STANDARD DEVIATION -- a trim labelled "winsorize" in its own comment. It
    # is the difference between measuring a tail and removing it: dropping the
    # ten largest of 5,195 BTC returns takes excess kurtosis from 17.61 to
    # 5.6, and the sd it then divides by is 7-12% below the sd the SIGMA table
    # publishes and a pricing model would use. Four of the five "crossovers"
    # this table reported do not exist without it.
    #
    # Winsorize properly: CLIP the extremes to the 0.1% quantiles, keep every
    # observation, and standardise by the sd of the FULL sample.
    k = max(int(len(r) * 0.001), 1)
    lo, hi = r[k], r[len(r) - 1 - k]
    sd_full = pstdev(r)
    r_full = list(r)
    r = [min(max(v, lo), hi) for v in r]
    sd = sd_full
    if sd <= 0:
        return None
    z = [(v - mean(r)) / sd for v in r]
    n = len(z)
    ratios = {}
    for zz in (1.282, 1.645, 2.054, 2.326, 2.576):
        g = 2 * (1 - ND.cdf(zz))
        o = sum(1 for x in z if abs(x) > zz) / n
        ratios[zz] = o / g if g > 0 else float("nan")
    # A crossover is only meaningful if the ratios it sits between are
    # themselves distinguishable from 1. Without this guard, clean Gaussian
    # noise reports a confident crossover at ~99c every time.
    # The gate's SE must respect clustering: tail exceedances arrive in
    # RUNS (a volatile stretch delivers several 2-sigma windows together),
    # and the binomial sqrt(g(1-g)/n) assumed independence -- Monte Carlo on
    # this file's own garch fixtures put the true sd at 1.6-2.7x nominal,
    # turning the "2 SE" gate into a ~17-21% false-positive machine per
    # threshold. Moving-block bootstrap over the window-ordered indicators.
    def sig(zz, _B=200):
        g = 2 * (1 - ND.cdf(zz))
        ind = [1.0 if abs(x) > zz else 0.0 for x in z]
        b = max(2, int(round(n ** (1.0 / 3.0))))
        starts = n - b + 1
        if starts < 2:
            return False
        cum = [0.0]
        for v in ind:
            cum.append(cum[-1] + v)
        bs = [cum[i + b] - cum[i] for i in range(starts)]
        k_ = max(1, -(-n // b))
        rng = random.Random(int(zz * 1000) ^ 77)
        props = []
        for _ in range(_B):
            t_ = 0.0
            for _ in range(k_):
                t_ += bs[rng.randrange(starts)]
            props.append(t_ / (k_ * b))
        se = pstdev(props) / g if g > 0 else float("inf")
        return abs(ratios[zz] - 1) > 2 * se
    cross = None
    xs = sorted(ratios)
    for i in range(len(xs) - 1):
        a, b = ratios[xs[i]], ratios[xs[i + 1]]
        if not (sig(xs[i]) and sig(xs[i + 1])):
            continue
        if a > 0 and b > 0 and (a - 1) * (b - 1) < 0:
            la, lb = math.log(a), math.log(b)
            cz = xs[i] + (0 - la) / (lb - la) * (xs[i + 1] - xs[i])
            cross = ND.cdf(cz)
            break
    # Kurtosis on the FULL sample. excess_kurtosis is scale-invariant --
    # it computes its own m2 -- so "standardise by sd_full" did nothing for
    # it, and what was printed was the WINSORIZED sample's kurtosis: 4.7
    # where the full-sample truth on the file's own garch fixture is 14.9.
    # The tail-ratio columns are legitimately computed on the clipped sample;
    # kurtosis is exactly the statistic clipping destroys.
    m_f = mean(r_full)
    m2_f = sum((v - m_f) ** 2 for v in r_full) / len(r_full)
    m4_f = sum((v - m_f) ** 4 for v in r_full) / len(r_full)
    ek = (m4_f / (m2_f * m2_f) - 3.0) if m2_f > 0 else float("nan")
    print(f"  {label:>11}{n:>7,}{ek:>9.1f}" +
          "".join(f"{ratios[z_]:>8.2f}" for z_ in xs) +
          (f"{100*cross:>11.1f}c" if cross else f"{'none':>12}"))
    return {"kurt": ek, "cross": cross}


# ===========================================================================
# SELF-TEST -- synthetic data with a known answer, run before real data
# ===========================================================================
def synth(n, rho=0.0, garch=0.0, sd=0.002, seed=1, break_chain=False):
    """Generate a fake settled-market list with KNOWN properties.

    rho    lag-1 autocorrelation injected into returns
    garch  vol persistence: sigma_t^2 = (1-g)*base + g*sigma_{t-1}^2 * (z^2)
    """
    rnd = random.Random(seed)
    out, price, prev_r, var = [], 60000.0, 0.0, sd * sd
    t0 = 1_700_000_000
    for i in range(n):
        if garch > 0:
            var = (1 - garch) * sd * sd + garch * (prev_r * prev_r)
            var = max(var, 1e-12)
        e = rnd.gauss(0, math.sqrt(var))
        r = rho * prev_r + e
        prev_r = r
        strike = price
        price = price * math.exp(r)
        out.append({"ticker": f"T-{i}", "strike": strike, "settle": price,
                    "close": t0 + i * WINDOW, "open": t0 + (i - 1) * WINDOW})
    if break_chain:
        for m in out[::7]:                      # corrupt every 7th strike
            m["strike"] *= 1.0003
    return out


def selftest():
    print("=" * 78)
    print("SELF-TEST -- every statistic run against a KNOWN answer")
    print("=" * 78)
    fails = []

    print("\n1. CHAIN GATE must PASS on clean data and FAIL on corrupted data")
    print(f"  {'case':>11}{'pairs':>8}{'median':>12}{'p90':>12}{'max':>12}"
          f"{'exact':>9}   verdict")
    clean, _ = build_chains(synth(2000, seed=3))
    g_ok = gate_chain(clean, "clean")
    dirty, _ = build_chains(synth(2000, seed=3, break_chain=True))
    g_bad = gate_chain(dirty, "corrupted")
    if not (g_ok and g_ok["exact_frac"] > 0.99):
        fails.append("chain gate did not pass on clean data")
    if not (g_bad and g_bad["exact_frac"] < 0.95):
        fails.append("chain gate did not detect corrupted data")

    print("\n2. RETURN AUTOCORRELATION -- must find injected rho, and only that")
    print(f"  {'injected':>11}{'n':>7}{'ac1':>10}{'t_blk':>8}{'t_iid':>8}"
          f"{'ac2':>10}{'t':>8}{'sign%':>11}{'t':>8}   verdict")
    for tag, rho, sd in (("null-a", 0.0, 1), ("null-b", 0.0, 2),
                         ("rho=+0.05", 0.05, 3), ("rho=-0.10", -0.10, 4)):
        rows = chain_returns(build_chains(synth(4000, rho=rho, seed=700 + sd))[0])
        got = test_return_autocorr(rows, tag)
        if rho == 0.0 and got and abs(got["t"]) > 3:
            fails.append(f"invented autocorrelation in clean noise (t={got['t']:.1f})")
        if rho != 0.0 and got and abs(got["ac1"] - rho) > 0.04:
            fails.append(f"failed to recover rho={rho} (got {got['ac1']:.3f})")

    print("\n2b. HOLES IN THE HISTORY must not be differenced across")
    print("   40 independent AR(1) chains, rho=+0.30, spliced end to end.")
    print("   Within-chain the answer is 0.30. The 39 pairs that straddle a")
    print("   splice are independent by construction, so a flat estimate over")
    print("   the concatenation must come out LOW -- and did, because")
    print("   chain_returns handed every consumer one undifferentiated list.")
    rnd_h = random.Random(99)
    RHO_H, NSEG, SEGLEN = 0.30, 40, 60
    seg_rows = []
    for ci in range(NSEG):
        prev = rnd_h.gauss(0, 1)
        for j in range(SEGLEN):
            v = RHO_H * prev + math.sqrt(1 - RHO_H ** 2) * rnd_h.gauss(0, 1)
            prev = v
            seg_rows.append({"r": v, "chain": ci})
    segs_h = segments_of(seg_rows)
    r_seg, npairs = autocorr_seg(segs_h, 1)
    r_flat = autocorr([x["r"] for x in seg_rows], 1)
    print(f"\n   {'estimator':>22}{'pairs':>9}{'ac1':>9}{'error':>9}")
    print(f"   {'within-chain':>22}{npairs:>9,}{r_seg:>9.3f}"
          f"{r_seg - RHO_H:>+9.3f}")
    print(f"   {'flat concatenation':>22}{len(seg_rows)-1:>9,}{r_flat:>9.3f}"
          f"{r_flat - RHO_H:>+9.3f}")
    if len(segs_h) != NSEG:
        fails.append(f"segments_of found {len(segs_h)} chains, not {NSEG}")
    if npairs != NSEG * (SEGLEN - 1):
        fails.append(f"used {npairs} pairs, expected {NSEG*(SEGLEN-1)} "
                     "-- some pair crossed a hole")
    if abs(r_seg - RHO_H) > 0.05:
        fails.append(f"within-chain estimate missed rho={RHO_H} "
                     f"(got {r_seg:.3f})")
    if abs(r_flat - RHO_H) <= abs(r_seg - RHO_H):
        fails.append("the flat estimate was not worse than the within-chain "
                     "one -- this test has stopped testing anything")

    print("\n3. VOL CLUSTERING -- must find injected GARCH, and only that")
    print(f"  {'injected':>11}{'n':>7}{'ac1|r|':>9}{'t_blk':>8}{'t_iid':>8}"
          f"{'ac5':>9}{'ac20':>9}{'LB(5)':>10}   verdict")
    for tag, g, sd in (("null-a", 0.0, 1), ("null-b", 0.0, 2),
                       ("garch=0.30", 0.30, 3), ("garch=0.60", 0.60, 4)):
        rows = chain_returns(build_chains(synth(4000, garch=g, seed=800 + sd))[0])
        got = test_vol_clustering(rows, tag)
        if g == 0.0 and got and got["t"] > 3:
            fails.append(f"invented vol clustering in clean noise (t={got['t']:.1f})")
        if g >= 0.30 and got and got["t"] < 3:
            fails.append(f"missed injected vol clustering g={g}")

    print("\n4. SIGMA RECOVERY -- must back out the sigma it was given")
    print(f"  {'injected':>11}{'n':>7}{'sd/window':>12}{'sig(1e-6/s)':>13}"
          f"{'annual':>10}{'up-rate':>9}{'t':>8}{'ties':>7}")
    for sd in (0.001, 0.002, 0.004):
        rows = chain_returns(build_chains(synth(4000, sd=sd, seed=int(sd*1e6)))[0])
        got = report_sigma(rows, f"sd={sd:.4f}")
        if got and abs(got["sd"] / sd - 1) > 0.06:
            fails.append(f"sigma recovery off: injected {sd}, got {got['sd']:.5f}")

    print("\n5. TAILS -- Gaussian input must show ratios ~1.0 and no crossover")
    print(f"  {'case':>11}{'n':>7}{'exkurt':>9}{'80%':>8}{'90%':>8}{'96%':>8}"
          f"{'98%':>8}{'99%':>8}{'crossover':>12}")
    rows = chain_returns(build_chains(synth(6000, seed=9))[0])
    tg = test_tails(rows, "gaussian")
    rows = chain_returns(build_chains(synth(6000, garch=0.7, seed=10))[0])
    test_tails(rows, "garch(fat)")
    if tg and abs(tg["kurt"]) > 0.6:
        fails.append(f"found excess kurtosis {tg['kurt']:.2f} in Gaussian data")
    if tg and tg["cross"] is not None:
        fails.append(f"invented a tail crossover at {100*tg['cross']:.1f}c "
                     "in clean Gaussian data")

    print("\n6. THE SE ITSELF must be tested -- COVERAGE under vol clustering")
    print("   Every t in tables 2 and 3 is a number divided by a standard")
    print("   error, and an SE is a claim like any other. The iid SE assumes")
    print("   independence. Volatility clustering -- the one thing this")
    print("   project has actually confirmed -- breaks that assumption, and")
    print("   it breaks it for the RETURN table too, because a return series")
    print("   with clustered variance is not iid even when its true")
    print("   autocorrelation is exactly zero.")
    print("\n   So: generate many datasets with KNOWN true rho = 0 and heavy")
    print("   vol clustering, and count how often a nominal 95% interval")
    print("   actually contains 0. It should be 95 in 100.")
    M, NN = 150, 1200
    r_hat, se_blk = [], []
    for k in range(M):
        rows = chain_returns(build_chains(
            synth(NN, garch=0.6, sd=0.002, seed=31000 + k))[0])
        segs = segments_of(rows)
        r, npairs = autocorr_seg(segs, 1)
        if r is None:
            continue
        se, _b, _n = ac_block_se(segs, 1, B=250, seed=900 + k)
        r_hat.append((r, 1.0 / math.sqrt(npairs)))
        se_blk.append(se)
    # Against ZERO, not TWAP_RHO1. synth() builds returns directly -- no
    # 60-second averaging anywhere -- so the overlap term does not exist in
    # this fixture and its true rho is exactly 0. The audit caught this file
    # measuring coverage against a null 0.0114 away from its own fixture's
    # truth, in the very section that lectures about testing SEs. Both
    # rulers absorbed it (the offset is ~0.4 iid SEs), which is why the
    # numbers looked plausible; that is an argument for deriving nulls from
    # the fixture, never from the prose.
    cov_iid = sum(1 for (r, si) in r_hat
                  if abs(r - 0.0) / si < 1.96) / max(len(r_hat), 1)
    cov_blk = sum(1 for (r, _si), sb in zip(r_hat, se_blk)
                  if sb and abs(r - 0.0) / sb < 1.96) / max(len(r_hat), 1)
    med_i = median([si for _r, si in r_hat])
    med_b = median([x for x in se_blk if x])
    print(f"\n   {'ruler':>22}{'median SE':>12}{'95% cover':>12}   verdict")
    print(f"   {'iid  1/sqrt(n)':>22}{med_i:>12.4f}{100*cov_iid:>11.0f}%   "
          f"{'OK' if cov_iid > 0.90 else '*** BROKEN ***'}")
    print(f"   {'moving-block boot':>22}{med_b:>12.4f}{100*cov_blk:>11.0f}%   "
          f"{'OK' if cov_blk > 0.85 else '*** BROKEN ***'}")
    print(f"\n   {len(r_hat)} datasets, {NN} windows each, true rho = 0")
    print("   (synth builds returns directly; no TWAP overlap exists here).")
    if cov_iid > 0.90:
        fails.append("the iid SE covered {:.0%} here -- this fixture is not "
                     "heteroskedastic enough to test the SE, so section 6 "
                     "proves nothing".format(cov_iid))
    if cov_blk < 0.85:
        fails.append(f"block-bootstrap SE covered only {cov_blk:.0%} of the "
                     "time against a nominal 95%")
    if cov_blk <= cov_iid + 0.03:
        fails.append("the block SE was no better calibrated than the iid SE")
    print("\n   NOTE the block bootstrap lands near 90%, not 95%: it is")
    print("   mildly optimistic in finite samples, so a block t is still a")
    print("   slight overstatement. That is why the verdict bar in this file")
    print("   is |t| > 3 and not 1.96.")

    print("\n7. THE PULL must survive a rate limit, and must SAY when it did not")
    print("   A 429 is the routine consequence of paginating a 200-row")
    print("   endpoint thousands of times. The old code broke out of the loop")
    print("   on any non-200 and returned the short list with no way to tell")
    print("   'this is the whole history' from 'we gave up here' -- so a rate")
    print("   limit was reported as a fact about the market.")

    class _Resp(object):
        def __init__(self, status, payload=None, headers=None):
            self.status_code = status
            self._p = payload or {}
            self.headers = headers or {}
            self.text = "" if status == 200 else f"error {status}"

        def json(self):
            return self._p

    class _Session(object):
        def __init__(self, script):
            self.script = list(script)
            self.n = 0

        def get(self, url, params=None, timeout=None):
            self.n += 1
            item = (self.script.pop(0) if self.script
                    else _Resp(200, {"markets": [], "cursor": None}))
            if isinstance(item, Exception):
                raise item
            return item

    def _page(i, n=200, cursor=None):
        t0 = 1_700_000_000
        return _Resp(200, {"markets": [
            {"ticker": f"T-{i}-{j}", "floor_strike": 60000.0,
             "expiration_value": 60000.0 + j,
             "close_time": t0 + (i * n + j) * WINDOW,
             "open_time": t0 + (i * n + j - 1) * WINDOW}
            for j in range(n)], "cursor": cursor})

    waits = []
    cases = [
        # want=150 but a page is 200 rows: pages are taken whole, so a
        # recovered pull returns 200. Asserting 150 here would be asserting a
        # truncation the code has never done.
        ("429 then ok",
         [_Resp(429), _page(0)], 150, dict(n=200, trunc=False, retried=True)),
        ("Retry-After honoured",
         [_Resp(429, headers={"Retry-After": "2.5"}), _page(0)], 150,
         dict(n=200, trunc=False, retried=True)),
        ("429 forever",
         [_Resp(429)] * 12, 150, dict(n=0, trunc=True, retried=True)),
        ("404 -- do not retry",
         [_Resp(404)], 150, dict(n=0, trunc=True, retried=False)),
        ("timeout then ok",
         [OSError("timed out"), _page(0)], 150,
         dict(n=200, trunc=False, retried=True)),
        ("clean exhaustion",
         [_page(0, n=50, cursor=None)], 5000,
         dict(n=50, trunc=False, retried=False)),
    ]
    print(f"\n   {'case':>24}{'markets':>9}{'retries':>9}{'stopped':>11}"
          f"{'truncated':>11}   verdict")
    for name, script, want, exp in cases:
        waits.clear()
        st = {}
        got = fetch_settled("KXTEST", want, verbose=False, stats=st,
                            session=_Session(script),
                            sleep=lambda w: waits.append(w))
        ok = (len(got) == exp["n"] and st["truncated"] == exp["trunc"]
              and (st["retries"] > 0) == exp["retried"])
        print(f"   {name:>24}{len(got):>9,}{st['retries']:>9}"
              f"{st['stopped']:>11}{str(st['truncated']):>11}   "
              f"{'ok' if ok else '*** WRONG ***'}")
        if not ok:
            fails.append(f"pull case '{name}': got {len(got)} markets, "
                         f"retries={st['retries']}, "
                         f"truncated={st['truncated']}; expected "
                         f"{exp['n']}, retried={exp['retried']}, "
                         f"truncated={exp['trunc']}")
        if name == "Retry-After honoured":
            if 2.5 not in waits:
                fails.append(f"ignored the server's Retry-After: waited "
                             f"{waits} instead of 2.5s")
        if name == "429 forever":
            grew = all(waits[i] <= waits[i + 1] for i in range(len(waits) - 1))
            if not grew or len(waits) < 3:
                fails.append(f"backoff did not grow across retries: {waits}")

    print("\n   'truncated' is the column that matters. It is the difference")
    print("   between a short history and a short pull, and only one of those")
    print("   is a finding.")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        print("\nDo not run this against real data until these are fixed.")
        return False
    print("SELF-TEST PASSED -- every statistic recovered what it was given and")
    print("none of them invented an effect in clean noise. The harness may now")
    print("be pointed at real data.")
    return True


# ===========================================================================
# POWER -- the question that decides whether a null result means anything
# ===========================================================================
def power_analysis(reps=400):
    """How big must an effect be before this harness can see it?

    A null result is only informative if the test had the power to find the
    effect. PLAN.md sec.5 tabulates this for a trading edge; this does it for
    the two chain statistics, by simulation rather than by formula, so it
    includes every approximation the code actually makes."""
    print("\n" + "=" * 78)
    print("POWER -- detection rate at |t|>2, by true effect size and sample")
    print("=" * 78)
    print("  RETURN AUTOCORRELATION (the open-time signal)")
    print(f"  {'true rho':>10}" + "".join(f"{'n='+str(n):>12}"
                                          for n in (1000, 4000, 16000, 50000)))
    for rho in (0.0, 0.02, 0.05, 0.10):
        row = f"  {rho:>10.2f}"
        for n in (1000, 4000, 16000, 50000):
            hit = 0
            for s in range(reps):
                d = synth(n, rho=rho, seed=90000 + s * 13 + n)
                r = [math.log(m["settle"] / m["strike"]) for m in d]
                # synth() builds returns directly, with no TWAP overlap, so the
                # null here is genuinely zero -- this measures the test's power,
                # not the real-data null.
                _, t = ac_t(r, 1)
                if t is not None and abs(t) > 2:
                    hit += 1
            row += f"{100*hit/reps:>11.0f}%"
        print(row)
    print("\n  VOL CLUSTERING (the sigma-forecast edge)")
    print(f"  {'true garch':>10}" + "".join(f"{'n='+str(n):>12}"
                                            for n in (1000, 4000, 16000)))
    for g in (0.0, 0.05, 0.10, 0.20):
        row = f"  {g:>10.2f}"
        for n in (1000, 4000, 16000):
            hit = 0
            for s in range(max(reps // 4, 40)):
                d = synth(n, garch=g, seed=70000 + s * 7 + n)
                r = [abs(math.log(m["settle"] / m["strike"])) for m in d]
                _, t = ac_t(r, 1)
                if t is not None and t > 2:
                    hit += 1
            row += f"{100*hit/max(reps//4,40):>11.0f}%"
        print(row)
    print("\n  Read the rho=0.00 and garch=0.00 rows as the FALSE POSITIVE rate.")
    print("  They should sit near 5%. Anything else means the test is broken.")
    print("\n  This is why the chain matters: these two tests need only")
    print("  (strike, settle) per window, which public settled-market records")
    print("  already contain thousands of. No waiting for the collector.")


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", nargs="*", default=CRYPTO_15M)
    ap.add_argument("--markets", type=int, default=3000)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--power", action="store_true")
    ap.add_argument("--cache", default="./chain_cache.json")
    a = ap.parse_args()

    if a.power:
        power_analysis()
        raise SystemExit(0)
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)

    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)

    data = {}
    if os.path.exists(a.cache):
        try:
            data = json.load(open(a.cache, encoding="utf-8"))
            print(f"loaded cache {a.cache}: "
                  f"{sum(len(v) for v in data.values()):,} markets")
        except Exception:
            data = {}
    now = time.time()
    prov = {}

    def newest_of(rows):
        return max((m.get("close") or 0.0 for m in rows), default=0.0)

    for s in a.series:
        cached = data.get(s, ())
        have = len(cached)
        age = (now - newest_of(cached)) / 3600.0 if have else float("inf")
        if have >= a.markets * 0.9 and age < STALE_HOURS:
            prov[s] = {"n": have, "src": "cache", "age": age, "trunc": False,
                       "pages": 0, "retries": 0}
            continue
        why = "stale" if have >= a.markets * 0.9 else "short"
        agestr = "never" if have == 0 else f"{age:.1f}h old"
        print(f"  pulling {s} ({why}: {have:,} cached, newest {agestr}) ...",
              flush=True)
        st = {}
        got = fetch_settled(s, a.markets, stats=st)
        # NEVER let a bad pull destroy the cache. This file is thousands of
        # paginated API calls and it is the only 15-minute-spaced settlement
        # history the project has; a rate limit, a dropped connection or a
        # renamed field all return [] from fetch_settled, and assigning that
        # over a good series -- then dumping -- deletes history that costs
        # hours to rebuild. Keep whichever pull is larger.
        if len(got) >= have:
            data[s] = got
            src = "pulled"
            print(f"    {len(got):,} settled markets", flush=True)
        else:
            src = "cache"
            print(f"    pulled only {len(got):,}, KEEPING the cached "
                  f"{have:,} -- treat this run's numbers for {s} as stale",
                  flush=True)
        rows = data.get(s, ())
        prov[s] = {"n": len(rows), "src": src,
                   "age": (now - newest_of(rows)) / 3600.0 if rows
                          else float("inf"),
                   "trunc": bool(st.get("truncated")),
                   "pages": st.get("pages", 0),
                   "retries": st.get("retries", 0)}

    # Write to a sibling and rename: json.dump straight onto the cache path
    # truncates it the instant the file is opened, so any serialization error
    # (or a Ctrl-C at the wrong moment) leaves an empty cache behind.
    tmp_path = a.cache + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp_path, a.cache)

    print("\n" + "=" * 78)
    print("DATA PROVENANCE -- where each series' numbers came from")
    print("=" * 78)
    print("  A short series is not a fact about the market until we know the")
    print("  pull finished. TRUNCATED means we ran out of retries, so the")
    print("  history below is ours, not Kalshi's.")
    print(f"\n  {'series':>12}{'markets':>10}{'source':>9}{'newest':>11}"
          f"{'pages':>7}{'retries':>9}   note")
    for sname in a.series:
        pv = prov.get(sname)
        if not pv:
            print(f"  {sname:>12}{'--':>10}{'--':>9}{'--':>11}"
                  f"{'--':>7}{'--':>9}   not requested")
            continue
        agestr = "never" if pv["age"] == float("inf") else f"{pv['age']:.1f}h"
        note = ("*** TRUNCATED ***" if pv["trunc"]
                else "stale" if pv["age"] > STALE_HOURS
                else "")
        print(f"  {sname:>12}{pv['n']:>10,}{pv['src']:>9}{agestr:>11}"
              f"{pv['pages']:>7}{pv['retries']:>9}   {note}")

    chains_by = {}
    print("\n" + "=" * 78)
    print("GATE C  strike(N+1) == settle(N)   [needs no index feed]")
    print("=" * 78)
    print(f"  {'series':>11}{'pairs':>8}{'median':>12}{'p90':>12}{'max':>12}"
          f"{'exact':>9}   verdict")
    gate_ok = True
    for s in a.series:
        if not data.get(s):
            continue
        ch, dup = build_chains(data[s])
        chains_by[s] = ch
        g = gate_chain(ch, s)
        # Key on the gate's own worst-case verdict, not the median. The gate
        # carries a comment explaining that corrupting every 7th pair leaves
        # the median at exactly 0 -- and main() then re-derived its stop/go
        # from the median anyway, reintroducing one level up the precise bug
        # the gate was rebuilt to kill.
        if g and (g["exact_frac"] < 0.95 or g["median"] > 1e-4):
            gate_ok = False
    if not gate_ok:
        print("\n  *** GATE C FAILED for at least one series. Either the")
        print("  windows are not contiguous, or strike is not the previous")
        print("  settle, and the contract is not what we think. STOP. ***")

    rows_by = {s: chain_returns(c) for s, c in chains_by.items()}

    print("\n" + "=" * 78)
    print("SIGMA -- the one free parameter of the fair-value model")
    print("=" * 78)
    print(f"  {'series':>11}{'windows':>7}{'sd/window':>12}{'sig(1e-6/s)':>13}"
          f"{'annual':>10}{'up-rate':>9}{'t':>8}{'ties':>7}")
    for s in a.series:
        if rows_by.get(s):
            report_sigma(rows_by[s], s)
    print("\n  up-rate should be ~50%. A |t|>3 there would mean a directional")
    print("  drift in the contract itself, which would be extraordinary.")

    print("\n" + "=" * 78)
    print("VOL CLUSTERING -- can we forecast sigma better than a constant?")
    print("=" * 78)
    print(f"  {'series':>11}{'n':>7}{'ac1|r|':>9}{'t_blk':>8}{'t_iid':>8}"
          f"{'ac5':>9}{'ac20':>9}{'LB(5)':>10}   verdict")
    for s in a.series:
        if rows_by.get(s):
            test_vol_clustering(rows_by[s], s)

    print("\n" + "=" * 78)
    print("RETURN AUTOCORRELATION -- a signal available AT THE OPEN")
    print("=" * 78)
    print(f"  {'series':>11}{'n':>7}{'ac1':>10}{'t_blk':>8}{'t_iid':>8}"
          f"{'ac2':>10}{'t':>8}{'sign%':>11}{'t':>8}   verdict")
    for s in a.series:
        if rows_by.get(s):
            test_return_autocorr(rows_by[s], s)
    print(f"\n  ac1 is tested against a null of {TWAP_RHO1:+.5f}, NOT zero. That")
    print("  much autocorrelation is mechanical: consecutive settlement windows")
    print("  are 60-second averages 900s apart, and the overlap structure alone")
    print("  gives Cov/Var = 10/880. Against a zero null a pure random walk")
    print("  reads t=+3.1 at 60k windows. ac2 has no such term and IS tested")
    print("  against zero.")

    print("\n" + "=" * 78)
    print("TAILS, per series  [pooling assets with kurtosis 25..153 was wrong]")
    print("=" * 78)
    print(f"  {'series':>11}{'n':>7}{'exkurt':>9}{'80%':>8}{'90%':>8}{'96%':>8}"
          f"{'98%':>8}{'99%':>8}{'crossover':>12}")
    for s in a.series:
        if rows_by.get(s):
            test_tails(rows_by[s], s)

    print("\n" + "=" * 78)
    print("VOL BY TIME OF DAY (UTC), relative to each series' own mean")
    print("=" * 78)
    for s in a.series:
        if rows_by.get(s):
            test_hour_of_day(rows_by[s], s)

    n_tests = 4 * len([s for s in a.series if rows_by.get(s)])
    print("\n" + "=" * 78)
    print("MULTIPLE TESTING")
    print("=" * 78)
    print(f"  {n_tests} headline tests were run. At p<0.05 that is "
          f"{0.05*n_tests:.1f} false positives expected by chance alone.")
    print(f"  Bonferroni-corrected |t| threshold: "
          f"{ND.inv_cdf(1 - 0.025/max(n_tests,1)):.2f}")
    print("  The 12 series are ~0.8 correlated, so they are NOT 12 independent")
    print("  tests -- closer to 1.2 effective. Treat a result as real only if")
    print("  it appears in most series independently AND clears the corrected")
    print("  threshold in the largest one.")


if __name__ == "__main__":
    main()
