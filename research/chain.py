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


def fetch_settled(series, want, verbose=True):
    """Public endpoint, no key. /historical/* is stale (RUNBOOK) -- not used."""
    try:
        import requests
    except ImportError:
        raise SystemExit(
            "\n  This stage needs `requests`, which is not installed for this\n"
            "  interpreter. Install it with:\n\n"
            f"      {sys.executable} -m pip install requests\n\n"
            "  Every other stage is stdlib-only and will run without it.")
    sess = requests.Session()
    out, cursor, pages = [], None, 0
    while len(out) < want and pages < 200:
        p = {"series_ticker": series, "status": "settled", "limit": 200}
        if cursor:
            p["cursor"] = cursor
        try:
            r = sess.get(BASE + "/markets", params=p, timeout=30)
            if r.status_code != 200:
                if verbose:
                    print(f"    HTTP {r.status_code}: {r.text[:160]}")
                break
            js = r.json()
        except Exception as e:
            if verbose:
                print(f"    {type(e).__name__}: {e}")
            break
        b = js.get("markets", [])
        if not b:
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
        if not cursor:
            break
        time.sleep(0.08)                       # Basic tier ~20 reads/s
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
    for ch in chains:
        for m in ch:
            if m["strike"] > 0 and m["settle"] > 0:
                rows.append({"r": math.log(m["settle"] / m["strike"]),
                             "close": m["close"],
                             "up": 1.0 if m["settle"] >= m["strike"] else 0.0})
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
    se_up = math.sqrt(up * (1 - up) / len(rows))
    print(f"  {label:>11}{len(rows):>7,}{100*sd_window:>11.4f}%"
          f"{1e6*sig_s:>13.2f}{ann:>10.1f}%{100*up:>9.2f}%"
          f"{(up-0.5)/se_up:>8.1f}")
    return {"sd": sd_window, "sigma_s": sig_s, "n": len(rows)}


def test_vol_clustering(rows, label):
    """Does |return| predict the NEXT |return|? If the book quotes a slow
    sigma, a fast one is a durable edge with no directional view."""
    if len(rows) < 200:
        return None
    a = [abs(x["r"]) for x in rows]
    r1, t1 = ac_t(a, 1)
    r5, _ = ac_t(a, 5)
    r20, _ = ac_t(a, 20)
    lb = ljung_box(a, 5)
    print(f"  {label:>11}{len(a):>7,}{r1:>9.3f}{t1:>8.1f}{r5:>9.3f}"
          f"{r20:>9.3f}{lb:>10.1f}   "
          f"{'CLUSTERS' if t1 > 3 else 'weak' if t1 > 2 else 'no'}")
    return {"ac1": r1, "t": t1}


def test_return_autocorr(rows, label):
    """Does window N's direction predict window N+1? Tradeable AT THE OPEN."""
    if len(rows) < 200:
        return None
    r = [x["r"] for x in rows]
    # lag 1 carries the mechanical TWAP-overlap term; lag 2 does not (the
    # windows are far enough apart that the covariance is exactly zero).
    r1, t1 = ac_t(r, 1, null=TWAP_RHO1)
    r2, t2 = ac_t(r, 2)
    # sign persistence is the tradeable version
    s = [1 if x > 0 else 0 for x in r]
    same = sum(1 for i in range(len(s) - 1) if s[i] == s[i + 1])
    frac = same / (len(s) - 1)
    se = math.sqrt(0.25 / (len(s) - 1))
    print(f"  {label:>11}{len(r):>7,}{r1:>10.4f}{t1:>8.1f}{r2:>10.4f}"
          f"{t2:>8.1f}{100*frac:>10.2f}%{(frac-0.5)/se:>8.1f}   "
          f"{'SIGNAL' if abs(t1) > 3 else 'weak' if abs(t1) > 2 else 'no'}")
    return {"ac1": r1, "t": t1, "sign_frac": frac, "sign_t": (frac - 0.5) / se}


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
    k = max(int(len(r) * 0.001), 1)
    r = r[k:len(r) - k]                       # winsorize the extreme 0.1%
    sd = pstdev(r)
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
    def sig(zz):
        g = 2 * (1 - ND.cdf(zz))
        se = math.sqrt(g * (1 - g) / n) / g
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
    ek = excess_kurtosis(z)
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
    print(f"  {'injected':>11}{'n':>7}{'ac1':>10}{'t':>8}{'ac2':>10}{'t':>8}"
          f"{'sign%':>11}{'t':>8}   verdict")
    for tag, rho, sd in (("null-a", 0.0, 1), ("null-b", 0.0, 2),
                         ("rho=+0.05", 0.05, 3), ("rho=-0.10", -0.10, 4)):
        rows = chain_returns(build_chains(synth(4000, rho=rho, seed=700 + sd))[0])
        got = test_return_autocorr(rows, tag)
        if rho == 0.0 and got and abs(got["t"]) > 3:
            fails.append(f"invented autocorrelation in clean noise (t={got['t']:.1f})")
        if rho != 0.0 and got and abs(got["ac1"] - rho) > 0.04:
            fails.append(f"failed to recover rho={rho} (got {got['ac1']:.3f})")

    print("\n3. VOL CLUSTERING -- must find injected GARCH, and only that")
    print(f"  {'injected':>11}{'n':>7}{'ac1|r|':>9}{'t':>8}{'ac5':>9}"
          f"{'ac20':>9}{'LB(5)':>10}   verdict")
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
          f"{'annual':>10}{'up-rate':>9}{'t':>8}")
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
            data = json.load(open(a.cache))
            print(f"loaded cache {a.cache}: "
                  f"{sum(len(v) for v in data.values()):,} markets")
        except Exception:
            data = {}
    for s in a.series:
        if s in data and len(data[s]) >= a.markets * 0.9:
            continue
        print(f"  pulling {s} ...", flush=True)
        data[s] = fetch_settled(s, a.markets)
        print(f"    {len(data[s]):,} settled markets", flush=True)
    json.dump(data, open(a.cache, "w"))

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
        if g and g["median"] > 1e-4:
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
          f"{'annual':>10}{'up-rate':>9}{'t':>8}")
    for s in a.series:
        if rows_by.get(s):
            report_sigma(rows_by[s], s)
    print("\n  up-rate should be ~50%. A |t|>3 there would mean a directional")
    print("  drift in the contract itself, which would be extraordinary.")

    print("\n" + "=" * 78)
    print("VOL CLUSTERING -- can we forecast sigma better than a constant?")
    print("=" * 78)
    print(f"  {'series':>11}{'n':>7}{'ac1|r|':>9}{'t':>8}{'ac5':>9}"
          f"{'ac20':>9}{'LB(5)':>10}   verdict")
    for s in a.series:
        if rows_by.get(s):
            test_vol_clustering(rows_by[s], s)

    print("\n" + "=" * 78)
    print("RETURN AUTOCORRELATION -- a signal available AT THE OPEN")
    print("=" * 78)
    print(f"  {'series':>11}{'n':>7}{'ac1':>10}{'t':>8}{'ac2':>10}{'t':>8}"
          f"{'sign%':>11}{'t':>8}   verdict")
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
