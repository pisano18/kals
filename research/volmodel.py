#!/usr/bin/env python3
# VERSION: 2026-08-25-v1
"""
volmodel.py -- is the fat tail REAL, or is it vol clustering wearing a costume?

    python volmodel.py --selftest
    python volmodel.py --cache ./chain_cache.json

WHY THIS IS THE CENTRAL QUESTION

RUNBOOK records a tail crossover replicated at 96.6c and 96.7c on two
independent datasets and treats it as a fixed property of the distribution.
chain.py's self-test showed that injecting plain GARCH -- with NO fat tails
whatsoever -- reproduces a crossover at 96.7c. Mixing high- and low-volatility
periods manufactures excess kurtosis out of conditionally Gaussian returns.

The two explanations look identical in the unconditional data and imply
OPPOSITE strategies:

  static fat tails   -> the threshold is a constant. You avoid deep favourites,
                        always. There is nothing to forecast. Weak edge at best,
                        because it is a one-off recalibration any quant does.

  vol clustering     -> there is no fixed threshold. The correct price depends
                        on RECENT REALIZED VOL, which is forecastable. If the
                        book quotes a slow sigma and we quote a fast one, we are
                        right at both ends of the vol distribution, with no
                        directional view at all. That is a durable edge.

THE DISCRIMINATOR

Standardize each window's return by a volatility estimated from PRIOR windows
only, then re-measure the tails.

    fat tails are real  -> standardized returns are STILL fat
    it was clustering   -> standardized returns are ~Gaussian, kurtosis -> 0

That is a clean, one-shot test and it needs only the (strike, settle) chain.

LOOK-AHEAD
Every volatility estimate at window t uses windows < t only. There is no
in-sample fitting anywhere in the tail test. Lambda is chosen on the first half
of the sample and evaluated on the second.
"""

import argparse
import json
import math
import os
import random
from collections import defaultdict
from statistics import NormalDist, mean, pstdev

ND = NormalDist()


# ===========================================================================
# volatility estimators -- all strictly causal
# ===========================================================================
# Sample-size floors, derived rather than guessed. tail_profile needs TAIL_MIN
# vol-adjusted returns before its exceedance ratios mean anything; analyse()
# spends half its returns choosing lambda and loses WARMUP more to the causal
# estimator's burn-in, so it needs 2*(TAIL_MIN + WARMUP) to hand tail_profile a
# usable sample. The old floor of 400 was a guess: at n=430 tail_profile got
# 165 returns, returned None, and the summary table unpacked it as
# r["raw"]["kurt"] -- a TypeError on any series with four to five hundred
# settled markets, which is a completely ordinary amount of history.
TAIL_MIN = 200
WARMUP = 50
MIN_RETURNS = 2 * (TAIL_MIN + WARMUP)


def ewma_sigma(rets, lam, warmup=WARMUP):
    """sigma_t estimated from returns STRICTLY BEFORE t. Returns list of
    (index, sigma_t) for t >= warmup."""
    out = []
    var = None
    for i, r in enumerate(rets):
        if var is not None and i >= warmup:
            out.append((i, math.sqrt(var)))
        var = (r * r) if var is None else lam * var + (1 - lam) * r * r
    return out


def const_sigma(rets, warmup=WARMUP):
    """Expanding-window constant sigma -- also causal, the honest 'static' rival."""
    out, s2, n = [], 0.0, 0
    for i, r in enumerate(rets):
        if n > 0 and i >= warmup:
            out.append((i, math.sqrt(s2 / n)))
        s2 += r * r
        n += 1
    return out


def gaussian_loglik(rets, sig_list):
    """Sum log N(r_t; 0, sigma_t). Higher is better. Out-of-sample by
    construction because sigma_t never sees r_t."""
    ll = 0.0
    for i, s in sig_list:
        if s <= 0:
            continue
        ll += -0.5 * math.log(2 * math.pi * s * s) - rets[i] ** 2 / (2 * s * s)
    return ll


def loglik_terms(rets, sig_list):
    """{window index: log N(r_i; 0, sigma_i)} -- the per-window pieces the
    dLL t-statistic needs."""
    out = {}
    for i, s in sig_list:
        if s > 0:
            out[i] = (-0.5 * math.log(2 * math.pi * s * s)
                      - rets[i] ** 2 / (2 * s * s))
    return out


def dll_t(rets, sig_e, sig_c, common, B=300, seed=7):
    """Moving-block-bootstrap t for the summed log-likelihood difference.

    d_ll is a raw sum over windows that are serially dependent (that is the
    file's whole thesis) and heavy-tailed (each term carries r^2/sigma^2, so
    one wild window contributes tens of nats). A sign read off it with no
    dispersion is not a verdict. Blocks over the window ORDER keep the
    dependence; the t is the sum divided by the bootstrap sd of the sum.
    """
    te = loglik_terms(rets, sig_e)
    tc = loglik_terms(rets, sig_c)
    d = [te[i] - tc[i] for i in sorted(common) if i in te and i in tc]
    n = len(d)
    if n < 30:
        return None
    b = max(2, int(round(n ** (1.0 / 3.0))))
    starts = n - b + 1
    cum = [0.0]
    for v in d:
        cum.append(cum[-1] + v)
    bsum = [cum[i + b] - cum[i] for i in range(starts)]
    k = max(1, -(-n // b))
    rng = random.Random(seed)
    sums = []
    for _ in range(B):
        t_ = 0.0
        for _ in range(k):
            t_ += bsum[rng.randrange(starts)]
        sums.append(t_ * (n / (k * b)))
    sd = pstdev(sums)
    return (sum(d) / sd) if sd > 0 else None


# ===========================================================================
def excess_kurtosis(x):
    n = len(x)
    if n < 20:
        return float("nan")
    m = mean(x)
    m2 = sum((v - m) ** 2 for v in x) / n
    m4 = sum((v - m) ** 4 for v in x) / n
    return (m4 / (m2 * m2) - 3.0) if m2 > 0 else float("nan")


def tail_profile(z, label, quiet=False):
    """Observed/Gaussian exceedance ratios, with a significance guard so that
    clean noise cannot report a crossover (that bug was real -- see R2)."""
    n = len(z)
    if n < TAIL_MIN:
        return None
    sd = pstdev(z)
    if sd <= 0:
        return None
    zz_list = (1.282, 1.645, 2.054, 2.326, 2.576)
    ratios, sigflag = {}, {}
    m = mean(z)
    for zz in zz_list:
        g = 2 * (1 - ND.cdf(zz))
        ind = [1.0 if abs((v - m) / sd) > zz else 0.0 for v in z]
        o = sum(ind) / n
        ratios[zz] = o / g
        # Block-bootstrap SE, not binomial: exceedances arrive in RUNS when
        # vol clusters (chain.py measured the true sd at 1.6-2.7x nominal on
        # its garch fixtures), so the iid gate was a ~20% false-positive
        # machine per threshold.
        b_ = max(2, int(round(n ** (1.0 / 3.0))))
        starts = n - b_ + 1
        if starts >= 2:
            cum = [0.0]
            for v in ind:
                cum.append(cum[-1] + v)
            bsum = [cum[i + b_] - cum[i] for i in range(starts)]
            k_ = max(1, -(-n // b_))
            rng = random.Random(int(zz * 1000) ^ 55)
            props = []
            for _ in range(200):
                t_ = 0.0
                for _ in range(k_):
                    t_ += bsum[rng.randrange(starts)]
                props.append(t_ / (k_ * b_))
            se = (pstdev(props) / g) if g > 0 else float("inf")
        else:
            se = math.sqrt(g * (1 - g) / n) / g
        sigflag[zz] = abs(ratios[zz] - 1) > 2 * se
    cross = None
    for i in range(len(zz_list) - 1):
        a, b = ratios[zz_list[i]], ratios[zz_list[i + 1]]
        if not (sigflag[zz_list[i]] and sigflag[zz_list[i + 1]]):
            continue
        if a > 0 and b > 0 and (a - 1) * (b - 1) < 0:
            la, lb = math.log(a), math.log(b)
            cz = zz_list[i] + (0 - la) / (lb - la) * (zz_list[i + 1] - zz_list[i])
            cross = ND.cdf(cz)
            break
    ek = excess_kurtosis(z)
    if not quiet:
        print(f"  {label:>22}{n:>7,}{ek:>9.2f}" +
              "".join(f"{ratios[q]:>8.2f}" for q in zz_list) +
              (f"{100*cross:>11.1f}c" if cross else f"{'none':>12}"))
    return {"kurt": ek, "cross": cross, "ratios": ratios}


# ===========================================================================
# what the edge is WORTH if the book quotes a static sigma
# ===========================================================================
def edge_table(vol_ratios):
    """If the market prices with V_mkt and truth is V_true, the mispricing at a
    quoted price P is  Phi(z * V_mkt/V_true) - P,  z = Phi^-1(P).

    No forecasting of direction anywhere. Purely a disagreement about scale."""
    print("\n" + "=" * 78)
    print("WHAT A VOL DISAGREEMENT IS WORTH, in cents")
    print("=" * 78)
    print("  Rows: the market's quoted price. Columns: how wrong its sigma is.")
    print("  Positive = true value ABOVE the quote (buy). Negative = sell.\n")
    hdr = "".join(f"{f'x{k:.2f}':>10}" for k in vol_ratios)
    print(f"  {'quote':>7}{hdr}")
    for pm in (0.60, 0.75, 0.85, 0.90, 0.95, 0.98):
        z = ND.inv_cdf(pm)
        row = f"  {100*pm:>6.0f}c"
        for k in vol_ratios:
            # k = V_true / V_mkt ; market too-low vol => k>1
            pt = ND.cdf(z / k)
            row += f"{100*(pt-pm):>+10.2f}"
        print(row)
    print("\n  Breakeven bar (fee + half tick, PLAN.md sec.2): ~2.25pp at 50c,")
    print("  ~1.13pp at 90c, ~0.38pp at 95c. Compare down each column.")
    print("  A 20-25% sigma error is worth 3-5 cents -- an order of magnitude")
    print("  above cost. So this only survives as an edge if the book's sigma")
    print("  really is slow. That is the thing to measure, not to assume.")


# ===========================================================================
# synthetic ground truth
# ===========================================================================
def synth_garch(n, omega=None, alpha=0.0, beta=0.0, sd=0.002, nu=None, seed=1):
    """Proper GARCH(1,1) with optional Student-t innovations.

    alpha=beta=0, nu=None  -> iid Gaussian          (no tails, no clustering)
    alpha,beta > 0         -> clustering, conditionally Gaussian
    nu set                 -> genuinely fat-tailed innovations
    """
    rnd = random.Random(seed)
    if omega is None:
        omega = sd * sd * max(1e-9, (1 - alpha - beta))
    var = sd * sd
    out, r = [], 0.0
    for _ in range(n):
        var = omega + alpha * r * r + beta * var
        if nu:
            # Student-t scaled to unit variance
            g = rnd.gauss(0, 1)
            chi = sum(rnd.gauss(0, 1) ** 2 for _ in range(int(nu)))
            t = g / math.sqrt(chi / nu)
            z = t / math.sqrt(nu / (nu - 2.0))
        else:
            z = rnd.gauss(0, 1)
        r = math.sqrt(var) * z
        out.append(r)
    return out


def analyse(rets, label, lam_grid=(0.80, 0.90, 0.94, 0.97, 0.99), quiet=False):
    """Choose lambda on the first half, report on the second. Returns the
    verdict dict."""
    n = len(rets)
    if n < MIN_RETURNS:
        return None
    half = n // 2
    best_lam, best_ll = None, -1e18
    for lam in lam_grid:
        ll = gaussian_loglik(rets[:half], ewma_sigma(rets[:half], lam))
        if ll > best_ll:
            best_lam, best_ll = lam, ll

    test = rets[half:]
    sig_e = ewma_sigma(test, best_lam)
    sig_c = const_sigma(test)
    ll_e = gaussian_loglik(test, sig_e)
    ll_c = gaussian_loglik(test, sig_c)
    common = set(i for i, _ in sig_e) & set(i for i, _ in sig_c)
    ll_e = gaussian_loglik(test, [(i, s) for i, s in sig_e if i in common])
    ll_c = gaussian_loglik(test, [(i, s) for i, s in sig_c if i in common])

    raw = [test[i] for i in sorted(common)]
    sd_map = dict(sig_e)
    zc = [test[i] / sd_map[i] for i in sorted(common) if sd_map[i] > 0]

    t_raw = tail_profile(raw, f"{label} raw", quiet)
    t_cond = tail_profile(zc, f"{label} vol-adjusted", quiet)

    if t_raw is None or t_cond is None:
        # Belt and braces: the caller's only contract is "None means not
        # enough data", so never hand back a dict with a None inside it.
        return None

    sds = sorted(sd_map[i] for i in sorted(common))
    spread = sds[int(len(sds) * .9)] / sds[int(len(sds) * .1)] if sds else 1.0
    return {"lam": best_lam, "d_ll": ll_e - ll_c,
            "d_ll_t": dll_t(test, sig_e, sig_c, common),
            "n": len(common),
            "raw": t_raw, "cond": t_cond, "vol_p90_p10": spread}


def selftest():
    print("=" * 78)
    print("SELF-TEST -- can the discriminator tell clustering from real tails?")
    print("=" * 78)
    print("  Three processes with KNOWN structure. The vol-adjusted row is the")
    print("  discriminator: it must go flat for clustering, stay fat for real")
    print("  tails, and never invent structure in clean noise.\n")
    print(f"  {'case':>22}{'n':>7}{'exkurt':>9}{'80%':>8}{'90%':>8}"
          f"{'96%':>8}{'98%':>8}{'99%':>8}{'crossover':>12}")
    fails = []

    cases = [
        ("iid gaussian", dict(alpha=0.0, beta=0.0, nu=None, seed=1)),
        ("garch, cond-normal", dict(alpha=0.12, beta=0.85, nu=None, seed=2)),
        ("iid student-t(4)", dict(alpha=0.0, beta=0.0, nu=4, seed=3)),
        ("garch + student-t", dict(alpha=0.12, beta=0.85, nu=5, seed=4)),
    ]
    res = {}
    for name, kw in cases:
        r = synth_garch(8000, **kw)
        res[name] = analyse(r, name)
        print()

    g = res["iid gaussian"]
    if abs(g["raw"]["kurt"]) > 0.5:
        fails.append("found kurtosis in iid Gaussian data")
    if g["raw"]["cross"] is not None:
        fails.append("invented a crossover in iid Gaussian data")
    if g["d_ll"] > 20:
        fails.append(f"EWMA 'beat' constant sigma on iid data by {g['d_ll']:.0f}")

    c = res["garch, cond-normal"]
    if c["raw"]["kurt"] < 1.0:
        fails.append("GARCH data did not show unconditional excess kurtosis")
    if c["cond"]["kurt"] > 0.8:
        fails.append(f"vol-adjusting GARCH left kurtosis {c['cond']['kurt']:.2f} "
                     "-- discriminator not working")
    if c["d_ll"] < 20:
        fails.append("EWMA failed to beat constant sigma on GARCH data")

    t = res["iid student-t(4)"]
    if t["cond"]["kurt"] < 1.0:
        fails.append(f"vol-adjusting killed a REAL fat tail "
                     f"({t['raw']['kurt']:.1f} -> {t['cond']['kurt']:.1f}) "
                     "-- discriminator gives false 'it was clustering'")

    # Sample-size contract: analyse() returns either None or a dict whose
    # 'raw' and 'cond' are both real. Anything in between is the TypeError the
    # summary table used to die on, and it fired at ordinary history lengths.
    print("\n  SAMPLE-SIZE CONTRACT (None, or a complete dict -- never both)")
    bad_n = []
    for n in (250, 399, 400, 430, 499, 500, 501, 700, 1200):
        r = analyse(synth_garch(n, alpha=0.10, beta=0.85, seed=11),
                    "size", quiet=True)
        if r is not None and (r.get("raw") is None or r.get("cond") is None):
            bad_n.append(n)
    print(f"  {'n swept':>16}   250..1200      "
          f"incomplete dicts: {len(bad_n)}")
    if bad_n:
        fails.append(f"analyse returned a dict with a None tail profile at "
                     f"n={bad_n} -- the summary table unpacks that")
    if analyse(synth_garch(MIN_RETURNS, alpha=0.1, beta=0.85, seed=12),
               "size", quiet=True) is None:
        fails.append(f"analyse refused its own stated floor of {MIN_RETURNS}")

    print("\n" + "-" * 78)
    print(f"  {'case':>22}{'best lam':>10}{'dLL vs const':>14}{'t':>7}"
          f"{'kurt raw':>10}{'kurt adj':>10}{'vol p90/p10':>13}")
    for name, _ in cases:
        r = res[name]
        print(f"  {name:>22}{r['lam']:>10.2f}{r['d_ll']:>+14.1f}{(r.get('d_ll_t') or 0):>7.1f}"
              f"{r['raw']['kurt']:>10.2f}{r['cond']['kurt']:>10.2f}"
              f"{r['vol_p90_p10']:>13.2f}")
    print("\n  Read it: 'kurt raw' high + 'kurt adj' near zero => CLUSTERING.")
    print("  Both high => genuinely fat tails. dLL counts only with its t:")
    print("  it is a sum over dependent, heavy-tailed windows, and a sign")
    print("  with no dispersion is not a verdict. |t| > 3 or nothing.")
    print("  dLL>0 => a conditional sigma")
    print("  predicts better than a constant one, out of sample.")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- the discriminator separates clustering from real")
    print("tails, and stays silent on clean noise.")
    return True


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="./chain_cache.json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1" and not selftest():
        raise SystemExit("self-test failed; refusing to touch real data")

    edge_table((0.80, 0.90, 1.00, 1.15, 1.30, 1.50))

    if not os.path.exists(a.cache):
        print(f"\n  no {a.cache} -- run chain.py first to build it.")
        return
    data = json.load(open(a.cache, encoding="utf-8"))
    print("\n\n" + "#" * 78)
    print("# REAL DATA")
    print("#" * 78)
    print(f"  {'case':>22}{'n':>7}{'exkurt':>9}{'80%':>8}{'90%':>8}"
          f"{'96%':>8}{'98%':>8}{'99%':>8}{'crossover':>12}")
    summary, thin = {}, []
    for s, mkts in sorted(data.items()):
        chain = sorted(mkts, key=lambda m: m["close"])
        rets = [math.log(m["settle"] / m["strike"]) for m in chain
                if m.get("strike", 0) > 0 and m.get("settle", 0) > 0]
        if len(rets) < MIN_RETURNS:
            thin.append((s, len(rets)))
            continue
        r = analyse(rets, s)
        if r:
            summary[s] = r
            print()
        else:
            thin.append((s, len(rets)))
    if thin:
        print(f"\n  {len(thin)} series had too little history "
              f"(need {MIN_RETURNS} settled markets): "
              + ", ".join(f"{k} ({v})" for k, v in sorted(thin)))
    if not summary:
        print("  not enough history in the cache.")
        return
    print("\n" + "-" * 78)
    print(f"  {'series':>22}{'best lam':>10}{'dLL vs const':>14}{'t':>7}"
          f"{'kurt raw':>10}{'kurt adj':>10}{'vol p90/p10':>13}")
    for s, r in sorted(summary.items()):
        print(f"  {s:>22}{r['lam']:>10.2f}{r['d_ll']:>+14.1f}{(r.get('d_ll_t') or 0):>7.1f}"
              f"{r['raw']['kurt']:>10.2f}{r['cond']['kurt']:>10.2f}"
              f"{r['vol_p90_p10']:>13.2f}")
    print("\n  VERDICT KEY")
    print("   kurt adj near 0  -> the 96.7c crossover is a CLUSTERING artefact.")
    print("                       The tradeable object is a sigma forecast.")
    print("   kurt adj still high -> genuine fat tails; refit with Student-t")
    print("                       before any tail strategy, per PLAN sec.10.3.")
    print("   vol p90/p10      -> how far sigma actually roams. Cross-reference")
    print("                       this against the edge table above: that is")
    print("                       the edge IF the book quotes a static sigma.")


if __name__ == "__main__":
    main()
