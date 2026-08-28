#!/usr/bin/env python3
# VERSION: 2026-08-25-x1
"""
proxy.py -- which price is the market maker ACTUALLY quoting off?

    python research/proxy.py --selftest
    python research/proxy.py --data ./kalshi_data --feeds ./feed_data --out ./fulltape

THE IDEA

Settlement is defined on CF Benchmarks' BRTI. But nothing forces the maker to
QUOTE off BRTI. Plenty of reasonable desks would quote off whatever they already
have wired in: Coinbase spot, a house consolidated mid, a perp mark, or BRTI
delayed by their own plumbing.

If they do, then every time their reference diverges from BRTI, their quote is
wrong by a knowable amount -- and it is wrong in a direction we can compute from
data we already record. Nobody has to be mistaken about anything. They are
pricing a different number, for perfectly good operational reasons, and the
contract settles on ours.

THE REGRESSION, AND WHY IT IS ON CHANGES

If the maker quotes off proxy X while the contract settles on BRTI:

    quote_t   = f(X_t)          =>   d(quote) = f' * d(X)
    our fair  = f(BRTI_t)       =>   d(fair)  = f' * d(BRTI)

    d(quote) - d(fair) = -f' * d(BRTI - X)

So regressing the RESIDUAL CHANGE on the change in (BRTI - candidate) gives a
significantly NEGATIVE slope for whichever candidate the maker is really using,
and roughly zero for the others.

Deliberately on changes, not levels. Our sigma carries 2-12% error (PLAN_V3 §4),
which shifts the implied level in a slowly-varying way and would contaminate a
level regression completely. Differencing removes anything that moves slowly,
sigma error included.

CANDIDATES TESTED
  random_control        an independent walk of the same scale -- must come out
                        ~0 or the method is broken. (BRTI-vs-itself CANNOT be
                        the control: that gap is identically zero, so every
                        observation is filtered out and it silently tests
                        nothing. It looked like a control and was not one.)
  BRTI lagged 1..5s     the maker is simply behind
  Coinbase / Kraken mid a single-venue reference
  consolidated replica  our own size-weighted mid across venues

WHAT A HIT WOULD BE WORTH
The edge is (BRTI - X) times the delta, phi(z)/sd * (r_live/60). Divergences
between a single venue and a consolidated index run to several dollars in fast
markets, and leadlag.py's table prices a dollar of index error at anywhere from
a fraction of a cent to several cents depending on time to close.
"""

import argparse
import math
import os
import random
import sys
from collections import defaultdict
from statistics import NormalDist, mean, pstdev

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settlewin import cond_mean as sw_cond_mean   # noqa: E402
from engine import var_factor, N_AVG                       # noqa: E402

ND = NormalDist()


def fair_from_mu(mu, strike, tau, gamma0):
    """Fair value given the conditional mean of the settlement average.

    Split out from fair_from so callers that already hold a correctly
    reconstructed mu -- settlewin.cond_mean, which rescales the locked sum for
    missing ticks -- do not have to re-derive it from a raw (sum, count) pair.
    """
    vf = var_factor(tau, [1.0])
    if vf <= 0:
        return None
    sd = math.sqrt(vf * gamma0)
    if sd <= 0:
        return None
    return 1.0 - ND.cdf((strike - mu) / sd)


def fair_from(index_at_t, strike, tau, gamma0, locked_sum=0.0, n_locked=0):
    r = N_AVG - n_locked
    return fair_from_mu((locked_sum + r * index_at_t) / N_AVG,
                        strike, tau, gamma0)


def build(quotes, markets, index, proxies, gamma0, series_to_index,
          only_index=None,
          min_tau=30, max_tau=880):
    """Residual quote change, paired with the change in (BRTI - each candidate)."""
    rows = defaultdict(list)
    used = 0
    for tk, q in quotes.items():
        m = markets.get(tk)
        if not m:
            continue
        iid = series_to_index.get(m.get("series") or tk.split("-")[0])
        # Only markets whose OWN index is the one the candidates proxy. Every
        # candidate on the real path is built from BRTI (brti_lagN, and the
        # feeds loaded for --asset), but nothing here filtered the markets --
        # so a DOGE market's residual was regressed on the BTC gap, whose
        # variance is ~10^12 larger than anything DOGE-scale. Those rows are
        # pure noise in x, which attenuates beta toward zero: a
        # false-NEGATIVE machine. "No candidate beats the control" was partly
        # this dilution, not a finding about the maker.
        if only_index is not None and iid != only_index:
            continue
        ticks, g0 = index.get(iid), gamma0.get(iid)
        if not ticks or not g0:
            continue
        close_s = int(round(m["close"]))
        strike = m.get("strike")
        if not strike:
            continue
        mids = {t: (b + a) / 2.0 for t, b, a, _, _ in q}
        lo_run = close_s - N_AVG + 1
        secs = sorted(t for t in mids if t in ticks)
        prev = None
        for t in secs:
            tau = close_s - t
            if not (min_tau <= tau <= max_tau):
                prev = None
                continue
            mu = sw_cond_mean(ticks, close_s, t, ticks[t])
            if mu is None:
                prev = None
                continue
            fv = fair_from_mu(mu, strike, tau, g0)
            if fv is None:
                prev = None
                continue
            cur = (t, mids[t], fv)
            if prev is not None and t - prev[0] == 1:
                d_q = cur[1] - prev[1]
                d_f = cur[2] - prev[2]
                resid = d_q - d_f
                for name, series in proxies.items():
                    if t in series and (t - 1) in series and \
                       t in ticks and (t - 1) in ticks:
                        gap_now = ticks[t] - series[t]
                        gap_prev = ticks[t - 1] - series[t - 1]
                        rows[name].append((gap_now - gap_prev, resid, close_s))
            prev = cur
        used += 1
    return rows, used


def regress(rows, label):
    """Slope through the origin, with block-bootstrapped standard errors."""
    out = {}
    for name, pairs in sorted(rows.items()):
        pairs = [(x, y, c) for x, y, c in pairs if x != 0.0]
        if len(pairs) < 500:
            continue
        den = sum(x * x for x, _, _ in pairs)
        if den <= 0:
            continue
        beta = sum(x * y for x, y, _ in pairs) / den
        by = defaultdict(lambda: [0.0, 0.0])
        for x, y, c in pairs:
            by[c][0] += x * y
            by[c][1] += x * x
        cl = [n / d for n, d in by.values() if d > 0]
        if len(cl) < 10:
            continue
        m, sd = mean(cl), pstdev(cl)
        se = sd / math.sqrt(len(cl)) if sd > 0 else float("inf")
        out[name] = {"beta": beta, "n": len(pairs), "clusters": len(cl),
                     "t": m / se if se > 0 else 0.0}
    return out


def report(res, label="CANDIDATE REFERENCES"):
    print(f"\n  {label}")
    if not res:
        print("    not enough paired observations")
        return None
    print(f"  {'candidate':>22}{'slope':>12}{'t':>8}{'obs':>10}"
          f"{'clusters':>10}   reading")
    # A hit needs BOTH significance and magnitude. The slope should be close to
    # -d(fair)/d(spot), order 1e-3 to 1e-2 per dollar. A slope of -3e-5 with
    # t=-6.9 is a precisely measured nothing, and ranking by t alone called it
    # a finding.
    strongest = min((v["beta"] for v in res.values()), default=0.0)
    floor = min(-1e-4, 0.3 * strongest)
    # The bar a candidate must clear is the CONFOUND row, not zero: any
    # sub-second quote lag loads resid negatively on every innovation-
    # correlated candidate, and delta_confound_lag0 carries that at full
    # strength. Beating zero while losing to the confound row is the
    # confound, described twice.
    conf = res.get("delta_confound_lag0")
    conf_bar = (conf["beta"] - 2.0 * abs(conf["beta"] / conf["t"])
                if conf and conf.get("t") else 0.0)
    best = None
    for k, v in sorted(res.items(), key=lambda kv: kv[1]["beta"]):
        hit = (v["t"] < -3 and v["beta"] <= floor
               and v["beta"] < conf_bar
               and k not in ("random_control", "delta_confound_lag0"))
        r = "<== the maker follows THIS" if hit else (
            "(control)" if k == "random_control" else
            "(confound bar)" if k == "delta_confound_lag0" else
            "significant but negligible" if v["t"] < -3 else "")
        if hit and best is None:
            best = k
        print(f"  {k:>22}{v['beta']:>12.5f}{v['t']:>8.1f}{v['n']:>10,}"
              f"{v['clusters']:>10}   {r}")
    print("\n  A significantly NEGATIVE slope means the maker's quote tracks")
    print("  that candidate rather than BRTI: when BRTI moves away from it, the")
    print("  quote fails to follow, and the residual absorbs the difference.")
    print("  'random_control' is an independent walk of the same scale and")
    print("  must come out near zero, or the method itself is broken.")
    if best and best != "brti":
        print(f"\n  => The maker appears to quote off '{best}', not BRTI.")
        print("     Every divergence between them is then a knowable mispricing,")
        print("     and it requires nobody to be wrong -- they are pricing a")
        print("     different number for sound operational reasons, and the")
        print("     contract settles on ours.")
    else:
        print("\n  => No candidate beats BRTI. The maker is quoting the same")
        print("     number the contract settles on, which closes this line.")
    return best


# ===========================================================================
def selftest():
    print("=" * 78)
    print("SELF-TEST -- plant a maker quoting off a known proxy, recover it")
    print("=" * 78)
    fails = []
    sigma, g0 = 6.0, 36.0
    s2i = {"KXBTC15M": "BRTI"}

    def build_world(quote_off, n_win=150, seed=4):
        rnd = random.Random(seed)
        t0 = 1_760_000_000
        total = 60 + n_win * 900 + 200
        brti, coinbase, x = {}, {}, 80_000.0
        drift = 0.0
        for k in range(total):
            x += rnd.gauss(0, sigma)
            brti[t0 + k] = x
            # coinbase wanders around BRTI on its own slow path
            drift += rnd.gauss(0, 0.8) - 0.05 * drift
            coinbase[t0 + k] = x + drift
        markets, quotes = {}, {}
        for w in range(n_win):
            open_s = t0 + 60 + w * 900
            close_s = open_s + 900
            if close_s not in brti:
                break
            strike = sum(brti[s] for s in range(open_s - 59, open_s + 1)) / 60.0
            tk = f"KXBTC15M-P{w:04d}"
            markets[tk] = {"ticker": tk, "series": "KXBTC15M",
                           "strike": strike, "close": float(close_s),
                           "result": 0.0}
            src = brti if quote_off == "brti" else coinbase
            qs = []
            for s in range(open_s, close_s - 29):
                tau = close_s - s
                lo_run = close_s - N_AVG + 1
                hi = min(s, close_s)
                if hi >= lo_run:
                    lk = [src[z] for z in range(lo_run, hi + 1) if z in src]
                    fv = fair_from(src[s], strike, tau, g0, sum(lk), len(lk))
                else:
                    fv = fair_from(src[s], strike, tau, g0)
                if fv is None:
                    continue
                fv = min(max(fv, 0.01), 0.99)
                qs.append((s, fv - 0.005, fv + 0.005, 500, 500))
            quotes[tk] = qs
        return brti, coinbase, markets, quotes

    rnd = random.Random(77)
    for truth in ("brti", "coinbase"):
        brti, coinbase, mk, q = build_world(truth)
        rc, cx = {}, 0.0
        for t in sorted(brti):
            cx += rnd.gauss(0, sigma)
            rc[t] = brti[t] + cx
        proxies = {"random_control": rc, "coinbase": coinbase,
                   "brti_lag2": {t + 2: v for t, v in brti.items()}}
        rows, used = build(q, mk, {"BRTI": brti}, proxies, {"BRTI": g0}, s2i)
        print(f"\n  maker actually quotes off: {truth}   ({used} markets)")
        res = regress(rows, truth)
        got = report(res)
        if truth == "brti" and got is not None:
            fails.append(f"accused the maker of following '{got}' when it "
                         "followed BRTI")
        if truth == "coinbase":
            c = res.get("coinbase")
            if not c or c["t"] > -3:
                fails.append("failed to detect a maker quoting off coinbase")

    print("\n" + "=" * 78)
    if fails:
        print("*** SELF-TEST FAILED ***")
        for f in fails:
            print("   -", f)
        return False
    print("SELF-TEST PASSED -- identifies the reference the maker is really")
    print("using, and does not accuse it of following the wrong one.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./kalshi_data")
    ap.add_argument("--feeds", default="./feed_data")
    ap.add_argument("--out", default="./fulltape")
    ap.add_argument("--asset", default="BTC")
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
        print("  no cfbenchmarks_value -- impossible without it.")
        return
    quotes = load_quotes(a.data)
    if not quotes:
        try:
            from book import rebuild
            quotes, _ = rebuild(a.data)
        except Exception:
            quotes = {}
    markets = load_markets(a.out)

    g0 = {}
    for iid, ticks in index.items():
        secs = sorted(ticks)
        d = [ticks[b] - ticks[a_] for a_, b in zip(secs, secs[1:]) if b - a_ == 1]
        if len(d) > 200:
            m = mean(d)
            g0[iid] = sum((x - m) ** 2 for x in d) / len(d)

    brti = index.get("BRTI", {})
    # NOT brti-vs-itself: that gap is identically zero and every observation
    # gets filtered out, so it silently tests nothing. Use an independent random
    # walk of similar scale as the control -- if THAT shows a slope, the method
    # is broken.
    rnd = random.Random(17)
    ctrl, cx = {}, 0.0
    for t in sorted(brti):
        cx += rnd.gauss(0, math.sqrt(g0.get("BRTI", 36.0)))
        ctrl[t] = brti[t] + cx
    proxies = {"random_control": ctrl}
    # The CONFOUND CONTROL. The declared null was beta = 0, but zero is not
    # the null: the recorded quote reflects the index with SOME sub-second
    # lag (maker reaction, collector receive, last-message-in-second offset),
    # so resid under-responds to the current second's innovation and loads
    # negatively on ANY candidate correlated with that innovation -- which
    # every genuine candidate is. Regressing on the raw innovation itself
    # (brti_lag0's gap is exactly -e_t) measures that confound at full
    # strength. A candidate is only "followed" if it beats THIS row, not
    # zero.
    proxies["delta_confound_lag0"] = dict(brti)
    for lag in (1, 2, 3, 5):
        proxies[f"brti_lag{lag}"] = {t + lag: v for t, v in brti.items()}
    try:
        from feeds import load_replica, load_tob
        rep = load_replica(a.feeds, a.asset, verbose=False)
        if rep:
            proxies["replica"] = rep
        tob = load_tob(a.feeds, a.asset, verbose=False)
        for ex in ("coinbase", "kraken", "bitstamp"):
            ser = {s: (v[ex][0] + v[ex][2]) / 2.0
                   for s, v in tob.items() if ex in v}
            if len(ser) > 1000:
                proxies[ex] = ser
    except Exception as e:
        print(f"  constituent feeds unavailable ({type(e).__name__}: {e})")

    print(f"  candidates: {sorted(proxies)}")
    # BRTI-built candidates test BTC markets only; see build()'s comment.
    rows, used = build(quotes, markets, index, proxies, g0, SERIES_TO_INDEX,
                       only_index="BRTI")
    print(f"  {used:,} markets contributed")
    report(regress(rows, "real"))


if __name__ == "__main__":
    main()
