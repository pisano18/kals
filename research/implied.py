#!/usr/bin/env python3
# VERSION: 2026-08-27-i2
"""
implied.py -- stop asking "is the market wrong". Ask what the market believes.

    python research/implied.py --selftest
    python research/implied.py --data ./kalshi_data --out ./fulltape

THE REFRAME

Every other test here compares a price to an OUTCOME, which means waiting for
settlements and spending statistical power on a single Bernoulli bit per window.
But the price already contains the market's own volatility assumption, and it can
simply be read out:

    P = Phi( (mu - K) / sd )      =>      sd = (mu - K) / Phi^-1(P)

with mu the settlement mean implied by the index and K the strike, both known.
Divide by the model's variance factor and you have the market's IMPLIED SIGMA at
that instant.

No outcomes. No waiting. Every quote in the recording is one observation, so
seven hours of data gives tens of thousands of them instead of a few hundred
settlements.

WHAT THE SHAPE OF THAT SURFACE REVEALS -- none of which needs anyone to be wrong

  LEVEL: implied vs realised sigma is the variance risk premium. If implied sits
  persistently above realised, sellers of these contracts are being PAID to carry
  variance risk -- exactly like the equity VRP. That is a risk premium, not an
  error, which is why it would persist. Being paid it is a real strategy.

  TERM STRUCTURE: under the confirmed settlement rule, implied sigma should be
  FLAT across time-to-close. Any tilt means the market is using a different
  variance formula than the one derived in settlement_math.py. And note the
  specific shape to look for: if the market used `tau + 20` where the truth is
  `tau - 39.5` -- the exact error found in RUNBOOK -- implied sigma would sag
  toward expiry in a predictable way. This test would catch that.

  SMILE: implied sigma flat across moneyness means the market prices a Gaussian.
  A smile means it prices fat tails, and the CURVATURE says how fat. That
  settles PLAN sec.10.3 from prices alone, without needing a single settlement,
  and tells us whether the market has already priced what we would be trying to
  exploit.

  SKEW: a tilt between the yes side and the no side is directional pricing --
  or inventory. A maker long the complex shades quotes to shed it. That is not
  an error either; it is a chance to be paid for absorbing it.

  BY SERIES / BY HOUR: where the maker's attention is thin.

A read-out of beliefs is more neutral than a hunt for mistakes, and it points at
the risk-premium and segmentation edges rather than only at arithmetic slips.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import NormalDist, mean, median, pstdev, stdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settlewin import cond_mean as sw_cond_mean   # noqa: E402
from engine import var_factor, N_AVG                      # noqa: E402

ND = NormalDist()

# Prices too close to the boundary invert unstably: Phi^-1 explodes and one tick
# of quantization becomes an enormous change in sigma. Stay where the inversion
# is well conditioned.
P_LO, P_HI = 0.06, 0.94


def implied_sigma(price, mu, strike, tau):
    """The sigma the market must be using to quote `price`. None where the
    inversion is ill-conditioned."""
    if not (P_LO <= price <= P_HI):
        return None
    z = ND.inv_cdf(price)
    if abs(z) < 1e-9:
        return None                      # at 50c the price carries no sigma info
    vf = var_factor(tau, [1.0])
    if vf <= 0:
        return None
    sd = (mu - strike) / z
    # SIGNED, deliberately. sd's estimation error is multiplicative and
    # symmetric (sd_est = sd_true * (1 + err/z)), and near 50c, where z is
    # tiny, a sizeable fraction of that symmetric error lands below zero.
    # This function used to `return None` for sd <= 0 -- deleting ONLY the
    # negative half of a symmetric distribution -- and the audit measured
    # the consequence on a fixture whose truth was exactly flat: the 45-55c
    # cell median shifted from 0.998 (unbiased) to 1.032, manufacturing the
    # "frown" the smile table then reported as a market phenomenon. The
    # median of the SIGNED values is unbiased; every consumer of iv takes
    # cell medians, so negatives are rare symmetric noise that cancels
    # instead of a tail that got amputated.
    return sd / math.sqrt(vf)


def collect(index, quotes, markets, series_to_index, ttc_max=900):
    """One row per (market, second) with a usable inversion."""
    rows = []
    for tk, q in quotes.items():
        m = markets.get(tk)
        if not m:
            continue
        iid = series_to_index.get(m.get("series") or tk.split("-")[0])
        ticks = index.get(iid)
        if not ticks:
            continue
        close_s = int(round(m["close"]))
        strike = m.get("strike")
        if not strike:
            continue
        lo_run = close_s - N_AVG + 1
        # EXOGENOUS one-second grid, not one row per ticker message. The
        # ticker channel is publish-on-change, so message times are chosen
        # by the market: a second where the touch moved four times used to
        # contribute four rows and a quiet second none -- implied sigma at a
        # typical QUOTE, divided by a calendar-time realised sigma. Quote
        # intensity rises with volatility, so that ratio picked up the
        # coupling, biasing every implied/realised figure UP. One prevailing
        # quote per second, carried forward at most 30s, is the calendar-
        # time numerator the denominator always was.
        last_by_sec = {}
        for rec in q:
            last_by_sec[rec[0]] = rec
        grid = []
        if last_by_sec:
            secs_sorted = sorted(last_by_sec)
            j = 0
            cur = None
            for t in range(max(secs_sorted[0], close_s - ttc_max),
                           close_s):
                while j < len(secs_sorted) and secs_sorted[j] <= t:
                    cur = last_by_sec[secs_sorted[j]]
                    j += 1
                if cur is not None and t - cur[0] <= 30:
                    # carry the AGE too. A quote carried forward is priced off
                    # a var_factor that has since moved, and var_factor
                    # collapses fast into the close: sd/sigma falls from 0.893
                    # at tau=20 to 0.327 at tau=10, so a 30-second-old quote
                    # inverted at tau=10 returns ~6.8x the sigma the quoter
                    # actually used. Consumers that care about the tau SHAPE
                    # (term.py) must be able to drop those; the level results
                    # below are biased UP by them, which makes every
                    # implied/realised ratio reported here CONSERVATIVE
                    # against the finding that the ratio is below 1.
                    grid.append((t, cur[1], cur[2], cur[3], cur[4],
                                 t - cur[0]))
        for (t, bid, ask, bs, as_, age) in grid:
            tau = close_s - t
            if not (1 <= tau <= ttc_max) or t not in ticks:
                continue
            spot = ticks[t]
            mu = sw_cond_mean(ticks, close_s, t, spot)
            if mu is None:
                continue
            mid = (bid + ask) / 2.0
            iv = implied_sigma(mid, mu, strike, tau)
            if iv is None:
                continue
            rows.append({"series": m.get("series") or tk.split("-")[0],
                         "tau": tau, "price": mid, "iv": iv, "close": close_s,
                         "spread": ask - bid, "age": age,
                         "z": (mu - strike) / max(math.sqrt(
                             var_factor(tau, [1.0])) * abs(iv), 1e-12)})
    return rows


def realised_sigma(index):
    out = {}
    for iid, ticks in index.items():
        secs = sorted(ticks)
        d = [ticks[b] - ticks[a] for a, b in zip(secs, secs[1:]) if b - a == 1]
        if len(d) < 200:
            continue
        m = mean(d)
        out[iid] = math.sqrt(sum((x - m) ** 2 for x in d) / len(d))
    return out


def realised_scaling(ticks, ks=(1, 2, 5, 15, 60)):
    """Realised sigma estimated from k-second-spaced increments, each rescaled
    to a 1-second equivalent by dividing by sqrt(k).

    Under any driftless process with independent increments every k gives the
    SAME number. They diverge when the index feed is gappy in a way that
    correlates with activity: realised_sigma() above keeps only the pairs that
    are exactly 1 second apart, i.e. the seconds the feed CHOSE to publish. If
    it publishes more often while the price is moving, the 1s estimate is
    biased UP, and every implied/realised ratio built on it is biased DOWN by
    the same factor.

    This matters because the index here is 59.9%% covered. A ratio below 1
    across the liquid series is either a real negative variance risk premium
    -- a strong claim -- or this artefact. sigma(1s) / sigma(60s) separates
    them: ~1.00 means the gaps are benign, >1 means the denominator is
    inflated and the sub-1 ratios are the feed talking, not the market.
    """
    out = {}
    for k in ks:
        d = [ticks[t + k] - ticks[t] for t in ticks if t + k in ticks]
        if len(d) < 200:
            continue
        m = mean(d)
        out[k] = math.sqrt(sum((x - m) ** 2 for x in d) / len(d) / k)
    return out


def realised_audit(index, series_to_index):
    """Print the scaling check per series and return sigma(1s)/sigma(long)."""
    i2s = {v: k for k, v in series_to_index.items()}
    print("\n  REALISED-SIGMA AUDIT -- is the denominator trustworthy?")
    hdr = "".join(f"{'s(%ds)' % k:>12}" for k in (1, 2, 5, 15, 60))
    print(f"  {'series':>14}{'cover':>8}" + hdr + f"{'1s/60s':>9}")
    bias = {}
    for iid, ticks in sorted(index.items()):
        s = i2s.get(iid)
        if not s or len(ticks) < 1000:
            continue
        sc = realised_scaling(ticks)
        if 1 not in sc:
            continue
        span = max(ticks) - min(ticks) + 1
        long_k = max((k for k in sc if k >= 15), default=None)
        b = sc[1] / sc[long_k] if long_k else float("nan")
        bias[s] = b
        print(f"  {s:>14}{100 * len(ticks) / span:>7.1f}%"
              + "".join(f"{sc[k]:>12.6g}" if k in sc else f"{'--':>12}"
                        for k in (1, 2, 5, 15, 60))
              + f"{b:>9.3f}")
    off = {s: b for s, b in bias.items()
           if math.isfinite(b) and abs(b - 1) > 0.05}
    if off:
        print("  *** sigma does NOT scale as sqrt(t) for: "
              + ", ".join(f"{s} {b:.2f}" for s, b in sorted(off.items())))
        print("  The 1s realised sigma is measured only on seconds the feed")
        print("  published. Every implied/realised ratio below is divided by")
        print("  that number, so a bias of b here moves every ratio by 1/b.")
        print("  Resolve this BEFORE reading anything into a sub-1 VRP.")
    else:
        print("  sigma scales as sqrt(t) within 5% -- the gaps are benign and")
        print("  the denominator can be trusted.")
    return bias


# ===========================================================================
# POOLING
#
# Implied sigma is in $/sqrt(s) OF THAT SERIES' OWN INDEX. BTC's is ~5.6,
# DOGE's is ~2e-5 -- six orders of magnitude apart. Any statistic that mixes
# raw sigmas across series measures the price level of the coins, not the
# market's beliefs, and any ratio built from two DIFFERENT mixes (a pooled
# mean over a pooled median, say) measures nothing at all.
#
# So: normalise every row by its OWN series' realised sigma first. The
# resulting `rel` = implied_i / realised_i is dimensionless and is the only
# thing that may be pooled. Everything downstream reads `rel`, never `iv`.
#
# Pooling of `rel` is three-stage, because the observations are nested:
#   1. (close, series) cell -> median. Quotes inside one 15-minute window on
#      one series are one path, one strike, one inventory: near-perfectly
#      correlated. 60,000 quotes are not 60,000 observations.
#   2. close-time cluster -> geometric mean ACROSS SERIES, equally weighted.
#      Every series closes on the same wall-clock second, so a cluster holds
#      all nine. Weighting a cluster by quote count would let whichever
#      series happened to quote most set the answer.
#   3. across clusters -> geometric mean, SE from the spread BETWEEN
#      clusters. The close-time window is the unit of independence.
# Geometric, not arithmetic, because the quantity is a ratio: 2.0 and 0.5
# must average to 1.0, not to 1.25.
# ===========================================================================

MIN_CELL = 3        # quotes needed before a (close, series) cell counts
MIN_CLUSTERS = 8    # clusters needed before a bucket is reported


def ci(a, d=3):
    """[lo, hi] formatted to d decimals."""
    return f"[{a['lo']:.{d}f}, {a['hi']:.{d}f}]"


def _gm(vals):
    """Geometric mean of positive values, or None."""
    lg = [math.log(v) for v in vals if v > 0 and math.isfinite(v)]
    if not lg:
        return None
    return math.exp(mean(lg))


def _agg(vals, blocks=None):
    """Geometric mean of `vals` with a cluster SE, in log space.

    `blocks` is the ordered cluster key list; when given, the SE is a
    moving-block bootstrap so that vol regimes persisting across adjacent
    windows are not counted as independent evidence.
    """
    lg = [math.log(v) for v in vals if v > 0 and math.isfinite(v)]
    n = len(lg)
    if n < 2:
        return None
    m = mean(lg)
    sd = stdev(lg)
    se = sd / math.sqrt(n) if sd > 0 else 0.0
    if blocks and n >= 12:
        se = max(se, _block_se(lg))
    return {"gm": math.exp(m), "n": n, "se_log": se,
            "lo": math.exp(m - 1.96 * se), "hi": math.exp(m + 1.96 * se),
            "t": (m / se) if se > 0 else 0.0}


def _block_se(lg, blk=None, reps=400, seed=11):
    """Moving-block bootstrap SE of mean(lg). Adjacent close-times share a
    volatility regime; an iid SE over clusters understates the spread by
    roughly sqrt((1+r)/(1-r))."""
    n = len(lg)
    blk = blk or max(2, int(round(n ** (1 / 3))))
    nb = max(1, -(-n // blk))
    rnd = random.Random(seed)
    ms = []
    for _ in range(reps):
        s = []
        for _ in range(nb):
            i = rnd.randrange(0, n - blk + 1)
            s.extend(lg[i:i + blk])
        ms.append(mean(s[:n]))
    return pstdev(ms)


def _pool(sel):
    """Three-stage pooled ratio for a set of rows carrying `rel`.

    Returns the aggregate plus how many series and clusters fed it -- a
    bucket populated by one series is NOT comparable to one populated by
    nine, and saying so is half the point of the fix.
    """
    cell = defaultdict(list)
    for r in sel:
        cell[(r["close"], r["series"])].append(r["rel"])
    per_cluster = defaultdict(list)
    for (c, s), v in cell.items():
        if len(v) >= MIN_CELL:
            per_cluster[c].append(median(v))
    keys = sorted(per_cluster)
    vals, used = [], set()
    for c in keys:
        g = _gm(per_cluster[c])
        if g is None:
            continue
        vals.append(g)
        used.update(s for (cc, s) in cell
                    if cc == c and len(cell[(cc, s)]) >= MIN_CELL)
    if len(vals) < MIN_CLUSTERS:
        return None
    a = _agg(vals, blocks=keys)
    if a:
        a["series"] = len(used)
        a["obs"] = len(sel)
    return a


def per_series_ratio(rows):
    """One ratio per series, with a close-time-clustered SE. This is the
    primary result: it is the only cut where numerator and denominator are
    measured in the same units."""
    by = defaultdict(list)
    for r in rows:
        by[r["series"]].append(r)
    out = {}
    for s, sel in by.items():
        cl = defaultdict(list)
        for r in sel:
            cl[r["close"]].append(r["rel"])
        keys = sorted(k for k, v in cl.items() if len(v) >= MIN_CELL)
        vals = [median(cl[k]) for k in keys]
        if len(vals) < MIN_CLUSTERS:
            continue
        a = _agg(vals, blocks=keys)
        if a:
            a["obs"] = len(sel)
            a["spread"] = median([r["spread"] for r in sel])
            out[s] = a
    return out


def profile(rows, key, buckets, label):
    """Pooled implied/realised RATIO by bucket, comparable across series."""
    n_all = len({r["series"] for r in rows})
    print(f"\n  {label}")
    print(f"  {'bucket':>14}{'obs':>9}{'clus':>6}{'ser':>5}"
          f"{'implied/realised':>18}{'95% CI':>18}")
    out = []
    for lo, hi, name in buckets:
        sel = [r for r in rows if lo <= r[key] < hi]
        if len(sel) < 200:
            continue
        a = _pool(sel)
        if not a:
            continue
        flag = ("  <-- only %d/%d series" % (a["series"], n_all)
                if a["series"] < n_all else "")
        print(f"  {name:>14}{a['obs']:>9,}{a['n']:>6}{a['series']:>5}"
              f"{a['gm']:>17.3f}x"
              f"{ci(a, 3):>18}"
              + flag)
        out.append((name, a["gm"], a["lo"], a["hi"], a["n"], a["series"]))
    return out


def report(rows, real_sigma_by_series):
    if not rows:
        print("  no invertible quotes.")
        return None

    # --- normalise BEFORE pooling. Rows whose series has no realised sigma
    #     are dropped, not silently folded into a cross-series median.
    kept, dropped = [], defaultdict(int)
    for r in rows:
        rs = real_sigma_by_series.get(r["series"])
        if not rs or not math.isfinite(rs) or rs <= 0:
            dropped[r["series"]] += 1
            continue
        r = dict(r)
        r["rel"] = r["iv"] / rs
        kept.append(r)
    if not kept:
        print("  no series has both implied quotes and a realised sigma.")
        return None

    print("=" * 78)
    print("WHAT THE MARKET BELIEVES")
    print("=" * 78)
    print(f"  {len(kept):,} invertible quotes across "
          f"{len({r['close'] for r in kept}):,} close-time clusters and "
          f"{len({r['series'] for r in kept})} series")
    if dropped:
        print("  dropped (no realised sigma): "
              + ", ".join(f"{s} {n:,}" for s, n in sorted(dropped.items())))
    print("  Implied sigma is in $/sqrt(s) of each series' OWN index, so raw")
    print("  sigmas are NOT pooled anywhere below. Every figure is a ratio to")
    print("  that series' own realised sigma.")

    ps = per_series_ratio(kept)
    print("\n  BY SERIES -- the primary result")
    print(f"  {'series':>14}{'obs':>9}{'clus':>6}{'implied':>14}"
          f"{'realised':>14}{'ratio':>9}{'95% CI':>18}{'spread':>9}")
    for s, a in sorted(ps.items(), key=lambda kv: kv[1]["gm"]):
        rs = real_sigma_by_series[s]
        print(f"  {s:>14}{a['obs']:>9,}{a['n']:>6}"
              f"{median([r['iv'] for r in kept if r['series'] == s]):>14.6g}"
              f"{rs:>14.6g}{a['gm']:>9.3f}"
              f"{ci(a, 2):>18}"
              f"{100 * a['spread']:>8.2f}c")

    # --- the complex-level number: pool the RATIOS, never the sigmas.
    vals = [a["gm"] for a in ps.values()]
    summary = None
    if len(vals) >= 2:
        med = median(vals)
        gm = _gm(vals)
        se_b = stdev([math.log(v) for v in vals]) / math.sqrt(len(vals))
        summary = {"median": med, "gm": gm, "n_series": len(vals),
                   "se_log_between": se_b,
                   "lo": math.exp(math.log(gm) - 1.96 * se_b),
                   "hi": math.exp(math.log(gm) + 1.96 * se_b),
                   "per_series": {s: a["gm"] for s, a in ps.items()}}
        print(f"\n  VARIANCE RISK PREMIUM across {len(vals)} series")
        print(f"    median of per-series ratios : {med:.3f}x")
        print(f"    geometric mean              : {gm:.3f}x"
              f"   [{summary['lo']:.3f}, {summary['hi']:.3f}] "
              f"(between-series spread only)")
        print(f"    range                       : {min(vals):.3f}x "
              f"to {max(vals):.3f}x")
        print("  The median of per-series ratios is the headline: the series")
        print("  are ~9 draws with near-equal cluster counts, so precision")
        print("  weighting buys nothing, while between-series dispersion is")
        print("  real heterogeneity rather than sampling noise.")
        print("  CAUTION: the between-series interval does NOT cover the")
        print("  common factor. All series share one 46h realised-vol draw")
        print("  and one var_factor, so the LEVEL is far less certain than the")
        print("  CROSS-SECTION. Trust the spread; do not trade the level.")

    profile(kept, "tau",
            [(1, 30, "0-30s"), (30, 60, "30-60s"), (60, 120, "60-120s"),
             (120, 300, "120-300s"), (300, 600, "300-600s"),
             (600, 901, "600-900s")],
            "TERM STRUCTURE -- should be FLAT if the market uses our variance "
            "formula")
    print("  A tilt means the market's variance formula differs from")
    print("  settlement_math.py's. Sagging toward expiry is the specific")
    print("  signature of using `tau + 20` where the truth is `tau - 39.5`.")
    print("  Check the 'ser' column first: a bucket fed by two series is a")
    print("  statement about those two series, not about the term structure.")

    profile(kept, "price",
            [(0.06, 0.15, "6-15c"), (0.15, 0.30, "15-30c"),
             (0.30, 0.45, "30-45c"), (0.45, 0.55, "45-55c"),
             (0.55, 0.70, "55-70c"), (0.70, 0.85, "70-85c"),
             (0.85, 0.95, "85-94c")],
            "SMILE -- flat means the market prices a Gaussian")
    print("  A U-shape means fat tails are ALREADY PRICED, which would mean")
    print("  PLAN sec.10.3's tail trade is not available. Asymmetry between the")
    print("  two wings is directional pricing or maker inventory.")

    by_hour = defaultdict(list)
    for r in kept:
        by_hour[(datetime.fromtimestamp(r["close"], timezone.utc).hour // 4)
                * 4].append(r)
    if len(by_hour) > 2:
        print("\n  BY HOUR (UTC) -- pooled implied/realised ratio")
        parts = []
        for h, v in sorted(by_hour.items()):
            a = _pool(v)
            if a:
                parts.append(f"{h:02d}h {a['gm']:.2f}x({a['series']}s)")
        print("  " + "   ".join(parts))
        print("  Ratios, not raw sigma relative to a pooled median: the mix of")
        print("  series quoting changes hour to hour and would otherwise show")
        print("  up as a spurious intraday vol cycle.")
    return summary


# ===========================================================================
def _attach_rel(rows, real_by_series):
    out = []
    for r in rows:
        rs = real_by_series.get(r["series"])
        if rs and math.isfinite(rs) and rs > 0:
            r = dict(r)
            r["rel"] = r["iv"] / rs
            out.append(r)
    return out


def _build(quote_fn, series="KXBTC15M", iid="BRTI", S0=80_000.0, sig=6.0,
           n_win=200, seed=7):
    """A synthetic series at an arbitrary PRICE LEVEL. S0 and sig scale
    together, so the implied/realised ratio is invariant to the level while
    every raw sigma is not -- which is the whole point of tests 4-6."""
    rnd = random.Random(seed)
    t0 = 1_760_000_000
    total = 60 + n_win * 900 + 200
    S, ticks = S0, {}
    for k in range(total):
        S += rnd.gauss(0, sig)
        ticks[t0 + k] = S
    markets, quotes = {}, {}
    for w in range(n_win):
        open_s = t0 + 60 + w * 900
        close_s = open_s + 900
        if close_s not in ticks:
            break
        strike = sum(ticks[s] for s in range(open_s - 59, open_s + 1)) / 60.0
        tk = f"{series}-T{w:04d}"
        markets[tk] = {"ticker": tk, "series": series,
                       "strike": strike, "close": float(close_s),
                       "result": 0.0}
        qs = []
        for s in range(open_s, close_s, 3):
            tau = close_s - s
            lo_run = close_s - N_AVG + 1
            hi = min(s, close_s)
            if hi >= lo_run:
                lk = [ticks[x] for x in range(lo_run, hi + 1) if x in ticks]
                mu = (sum(lk) + (N_AVG - len(lk)) * ticks[s]) / N_AVG
            else:
                mu = ticks[s]
            sd = math.sqrt(var_factor(tau, [1.0]))
            p = quote_fn(mu, strike, sd, tau, sig)
            if p is None:
                continue
            p = min(max(p, 0.01), 0.99)
            qs.append((s, p - 0.005, p + 0.005, 500, 500))
        quotes[tk] = qs
    return {iid: ticks}, quotes, markets


def _series_set(specs, n_win=60, seed=7):
    """Several series at wildly different price levels, each quoting a KNOWN
    multiple of its OWN sigma.

    specs: {series: (index_id, price_level, sigma, vrp)}. Three series
    spanning 1e6 in price is the minimum that reproduces the real failure:
    with only two, a pooled MEDIAN lands on the boundary and picks the same
    series for numerator and denominator, so a broken pooler passes by
    accident. Do not reduce this below three.
    """
    idx, quotes, markets, s2i = {}, {}, {}, {}
    for k, (series, (iid, lvl, sig, vrp)) in enumerate(specs.items()):
        def q(mu, kk, sd, tau, sg, _v=vrp):
            return 1 - ND.cdf((kk - mu) / (sd * sg * _v))
        i, qq, mm = _build(q, series, iid, lvl, sig, n_win, seed + k)
        idx.update(i)
        quotes.update(qq)
        markets.update(mm)
        s2i[series] = iid
    rs_i = realised_sigma(idx)
    rs = {s: rs_i[i] for s, i in s2i.items() if i in rs_i}
    return idx, quotes, markets, s2i, rs


def _spec(vrps, btc=(80_000.0, 6.0), doge=(0.08, 6.0e-6)):
    a, b, c = vrps
    return {"KXBTC15M":  ("BRTI",         btc[0],  btc[1],  a),
            "KXETH15M":  ("ETHUSD_RTI",   4_000.0, 0.18,    b),
            "KXDOGE15M": ("DOGEUSD_RTI",  doge[0], doge[1], c)}


def _old_stats(rows, rs):
    """The two statistics this file used to print, reimplemented ONLY so the
    tests below can watch them fail.

      head  -- pooled MEDIAN raw implied sigma / pooled MEDIAN raw realised
               sigma. Printed as "VARIANCE RISK PREMIUM". Both medians are
               taken over rows mixed across series, so each one reports
               whichever series happens to sit at the middle of the quote
               count. It is one arbitrary series' ratio wearing a pooled
               label, which is why it looked plausible (1.192x) instead of
               absurd.

      table -- MEAN over close-time clusters of the MEAN raw implied sigma in
               that cluster, over the same pooled MEDIAN realised. Printed as
               the "vs realised" column. Numerator and denominator are
               different mixes of different series, and the mean is dominated
               by the highest-priced coin, which is where 59x-141x came from.
    """
    iv = sorted(r["iv"] for r in rows)
    nm = median([rs[r["series"]] for r in rows if r["series"] in rs])
    by = defaultdict(list)
    for r in rows:
        by[r["close"]].append(r["iv"])
    return {"head": iv[len(iv) // 2] / nm,
            "table": mean([mean(v) for v in by.values()]) / nm}


def selftest():
    print("=" * 78)
    print("SELF-TEST -- can it read back a volatility surface it was given?")
    print("=" * 78)
    fails = []
    sigma = 6.0
    s2i = {"KXBTC15M": "BRTI"}
    real1 = {"KXBTC15M": sigma}

    print("\n1. market quotes a FLAT sigma of exactly 6.0")
    idx, q, mk = _build(lambda mu, k, sd, tau, sig:
                        1 - ND.cdf((k - mu) / (sd * sig)))
    rows = collect(idx, q, mk, s2i)
    got = median([r["iv"] for r in rows])
    print(f"   recovered median implied sigma = {got:.4f}  (true 6.0000)")
    if abs(got - sigma) > 0.05:
        fails.append(f"flat surface recovered as {got:.4f}, expected 6.0")
    rel = _attach_rel(rows, real1)
    res = profile(rel, "tau", [(1, 60, "0-60s"), (60, 300, "60-300s"),
                               (300, 901, "300-900s")], "term structure")
    if res and max(abs(r[1] - 1) for r in res) > 0.05:
        fails.append("flat input produced a tilted term structure")

    print("\n2. market quotes a SMILE (+30% sigma in both wings)")

    def smile(mu, k, sd, tau, sig):
        p0 = 1 - ND.cdf((k - mu) / (sd * sig))
        bump = 1.0 + 0.30 * min(abs(p0 - 0.5) / 0.44, 1.0)
        return 1 - ND.cdf((k - mu) / (sd * sig * bump))
    idx, q, mk = _build(smile)
    rel = _attach_rel(collect(idx, q, mk, s2i), real1)
    res = profile(rel, "price",
                  [(0.06, 0.20, "6-20c"), (0.40, 0.60, "40-60c"),
                   (0.80, 0.95, "80-94c")], "smile")
    if len(res) == 3:
        wings = (res[0][1] + res[2][1]) / 2.0
        belly = res[1][1]
        print(f"   wings {wings:.2f}x vs belly {belly:.2f}x")
        if wings - belly < 0.12:
            fails.append(f"failed to see a planted smile "
                         f"(wings {wings:.2f} vs belly {belly:.2f})")

    print("\n3. market uses the WRONG variance formula (tau+20, the RUNBOOK error)")

    def wrongvar(mu, k, sd, tau, sig):
        bad = math.sqrt(tau + 20) if tau >= 60 else sd
        return 1 - ND.cdf((k - mu) / (bad * sig))
    idx, q, mk = _build(wrongvar)
    rel = _attach_rel(collect(idx, q, mk, s2i), real1)
    res = profile(rel, "tau", [(60, 120, "60-120s"), (300, 600, "300-600s"),
                               (600, 901, "600-900s")], "term structure")
    if len(res) >= 2:
        tilt = res[0][1] / res[-1][1]
        print(f"   near/far implied ratio = {tilt:.2f}x "
              f"(a flat, correct market gives 1.00x)")
        if abs(tilt - 1.0) < 0.15:
            fails.append("failed to detect a wrong variance formula")

    # -------------------------------------------------------------------
    # THE TEST THAT WAS MISSING. Everything above uses ONE series, so the
    # cross-series pooling degenerates and cannot be wrong. Plant TWO series
    # 1e6 apart in price with the SAME known ratio: a correct pooler returns
    # the ratio, a broken one returns the price-level difference.
    # -------------------------------------------------------------------
    VRP = 1.20
    print(f"\n4. THREE series spanning 1,000,000x in price, ALL quoting "
          f"{VRP:.2f}x their own sigma")
    idx, q, mk, s2i2, rs2 = _series_set(_spec((VRP, VRP, VRP)))
    rows = collect(idx, q, mk, s2i2)
    print("   realised sigma: "
          + "  ".join(f"{s.replace('KX', '').replace('15M', '')} {v:.4g}"
                      for s, v in sorted(rs2.items(), key=lambda kv: -kv[1])))
    summ = report(rows, rs2)
    if not summ:
        fails.append("multi-series case produced no summary at all")
    else:
        for k in ("median", "gm"):
            if abs(summ[k] - VRP) > 0.05:
                fails.append(f"pooled {k} = {summ[k]:.3f}x, planted {VRP:.2f}x"
                             f" -- pooling is contaminated by price level")
        for s, v in summ["per_series"].items():
            if abs(v - VRP) > 0.06:
                fails.append(f"{s} ratio {v:.3f}x, planted {VRP:.2f}x")
        rel = _attach_rel(rows, rs2)
        for key, bk, nm in (("tau", [(1, 120, "0-120s"), (120, 600, "120-600s"),
                                     (600, 901, "600-900s")], "term structure"),
                            ("price", [(0.06, 0.30, "6-30c"),
                                       (0.30, 0.70, "30-70c"),
                                       (0.70, 0.95, "70-94c")], "smile")):
            for name, gm, lo, hi, nc, ns in profile(rel, key, bk, nm):
                if ns < len(rs2):
                    fails.append(f"{nm} bucket {name} lost a series")
                if abs(gm - VRP) > 0.08:
                    fails.append(f"{nm} bucket {name} = {gm:.2f}x with "
                                 f"{VRP:.2f}x planted in every series")
        o = _old_stats(rows, rs2)
        print(f"   for contrast, the OLD 'vs realised' column on this same "
              f"input: {o['table']:,.2f}x")
        print(f"   (planted truth {VRP:.2f}x -- that gap IS the reported "
              f"59x-141x, at three series instead of nine)")
        if abs(o["table"] / VRP - 1) < 0.25:
            fails.append("test 4 is not discriminating: the OLD table "
                         "statistic also recovered the planted ratio")

    print("\n5. the three series quote DIFFERENT ratios (0.85x, 1.60x, 0.85x),")
    print("   with the OUTLIER on the middle-priced series -- the case the old")
    print("   headline cannot survive, because that is the series it reports")
    idx, q, mk, s2i2, rs2 = _series_set(_spec((0.85, 1.60, 0.85)))
    rows = collect(idx, q, mk, s2i2)
    summ = report(rows, rs2)
    if summ:
        want = (0.85 * 1.60 * 0.85) ** (1 / 3)
        got = [summ["per_series"].get(s, 0)
               for s in ("KXBTC15M", "KXETH15M", "KXDOGE15M")]
        print(f"   per-series {got[0]:.2f}x / {got[1]:.2f}x / {got[2]:.2f}x, "
              f"pooled {summ['gm']:.3f}x (geometric mean {want:.3f}x)")
        for g, w, s in zip(got, (0.85, 1.60, 0.85),
                           ("KXBTC15M", "KXETH15M", "KXDOGE15M")):
            if abs(g - w) > 0.08:
                fails.append(f"{s} recovered {g:.2f}x, planted {w:.2f}x")
        if abs(summ["gm"] - want) > 0.06:
            fails.append(f"pooled {summ['gm']:.3f}x, want {want:.3f}x")
        o = _old_stats(rows, rs2)
        print(f"   the OLD headline gives {o['head']:.3f}x -- the ratio of the")
        print(f"   ONE series sitting at the middle of the quote count, not a")
        print(f"   pooled anything. With equal ratios it looks right, which is")
        print(f"   exactly why 1.192x passed review. Keep this unequal case.")
        if abs(o["head"] - want) < 0.15:
            fails.append(f"test 5 is not discriminating: the OLD headline "
                         f"({o['head']:.3f}x) also landed on the pooled ratio "
                         f"({want:.3f}x) -- re-plant the outlier")
    else:
        fails.append("mixed-ratio case produced no summary")

    print("\n6. UNIT INVARIANCE -- restate BTC in millidollars (x1,000). The")
    print("   market is identical; only the units changed. Nothing about the")
    print("   answer may move.")
    outs, olds = [], []
    for btc in ((80_000.0, 6.0), (80_000_000.0, 6_000.0)):
        idx, q, mk, s2i2, rs2 = _series_set(_spec((VRP, VRP, VRP), btc=btc))
        rows = collect(idx, q, mk, s2i2)
        sm = report(rows, rs2)
        rel = _attach_rel(rows, rs2)
        got = {"gm": sm["gm"], "median": sm["median"]} if sm else {}
        for k, v in (sm or {}).get("per_series", {}).items():
            got["S:" + k] = v
        got.update({"B:" + b[0]: b[1] for b in
                    profile(rel, "tau",
                            [(1, 300, "1-300s"), (300, 901, "300-900s")],
                            "term structure")})
        outs.append(got)
        olds.append(_old_stats(rows, rs2))
    moved = (max(abs(outs[1][k] / outs[0][k] - 1) for k in outs[0])
             if outs[0] and set(outs[0]) == set(outs[1]) else 1.0)
    om = abs(olds[1]["table"] / olds[0]["table"] - 1)
    print(f"   corrected: all {len(outs[0])} reported numbers moved at most "
          f"{moved * 100:.2f}%")
    print(f"   the OLD 'vs realised' column: {olds[0]['table']:,.2f}x -> "
          f"{olds[1]['table']:,.2f}x   (moved {om * 100:,.0f}%)  <-- the bug")
    if not outs[0]:
        fails.append("scale-invariance case produced no summary")
    elif moved > 0.02:
        fails.append(f"a reported number moved {moved * 100:.1f}% when only a "
                     f"price level changed")
    if om < 5.0:
        fails.append("test 6 is not discriminating: the OLD broken statistic "
                     "also passed it")

    # -------------------------------------------------------------------
    # The denominator deserves a test of its own. realised_sigma() keeps only
    # index ticks exactly 1s apart, and the real index is 59.9% covered.
    # -------------------------------------------------------------------
    print("\n7. REALISED-SIGMA AUDIT -- a gappy index that drops ticks when")
    print("   the market is QUIET inflates realised sigma and pushes every")
    print("   implied/realised ratio below 1 for free")

    def gappy(bias, seed=3, n=120_000):
        """Ticks whose per-second vol alternates between busy and quiet.
        `bias`=0 drops seconds at random (MCAR); bias>0 drops preferentially
        while vol is low, which is what a publish-on-change feed does."""
        rnd = random.Random(seed)
        t0, S, ticks = 1_760_000_000, 80_000.0, {}
        for k in range(n):
            loc = 2.0 if rnd.random() < 0.4 else 0.30
            S += rnd.gauss(0, 6.0 * loc)
            keep = (0.6 if bias == 0
                    else min(0.95, max(0.05, 0.6 + bias * (loc - 1))))
            if rnd.random() < keep:
                ticks[t0 + k] = S
        return ticks

    for bias, name, want_flag in (
            (0.0, "gaps at random (MCAR)", False),
            (0.35, "gaps when quiet (publish-on-change)", True)):
        sc = realised_scaling(gappy(bias))
        b = sc[1] / sc[60]
        print(f"   {name:>38}: "
              + " ".join(f"s({k}s) {sc[k]:.2f}" for k in sorted(sc))
              + f"   1s/60s {b:.3f}")
        if want_flag and b < 1.10:
            fails.append(f"audit missed an activity-linked gappy index "
                         f"(1s/60s = {b:.3f}, wanted > 1.10)")
        if not want_flag and abs(b - 1) > 0.05:
            fails.append(f"audit false-alarmed on a benign gappy index "
                         f"(1s/60s = {b:.3f})")
    print("   NOTE the shape, not just the ratio: an activity-linked gap")
    print("   pattern decays MONOTONICALLY in k toward the true sigma. The")
    print("   check has little power when the tick-rate/vol coupling runs on")
    print("   an hour timescale rather than a per-second one.")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- recovers a flat surface exactly, sees a planted")
    print("smile, detects a market using the wrong variance formula, and")
    print("recovers a common ratio from three series priced 1,000,000x apart")
    print("without the price level leaking into any pooled number, and flags")
    print("an index whose gaps would fake a sub-1 variance risk premium.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed")

    from replay import load_index, load_quotes, load_markets, SERIES_TO_INDEX
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    index = load_index(a.data)
    if not index:
        print("  no cfbenchmarks_value -- cannot invert without the index.")
        return
    quotes = load_quotes(a.data)
    if not quotes:
        try:
            from book import rebuild
            quotes, _ = rebuild(a.data)
        except Exception:
            quotes = {}
    markets = load_markets(a.out)
    rs_by_index = realised_sigma(index)
    i2s = {v: k for k, v in SERIES_TO_INDEX.items()}
    rs = {i2s[k]: v for k, v in rs_by_index.items() if k in i2s}
    realised_audit(index, SERIES_TO_INDEX)
    rows = collect(index, quotes, markets, SERIES_TO_INDEX)
    report(rows, rs)
    print("\n  NOTE: this needs no settlements at all, so it runs on however")
    print("  many hours are recorded. It is the cheapest large-sample view of")
    print("  the market's model available.")


if __name__ == "__main__":
    main()
