#!/usr/bin/env python3
# VERSION: 2026-09-08-ar1
"""acrun.py -- run acvar's questions against the real tape.

  python research/acrun.py --selftest
  python research/acrun.py                      # the whole measurement

Four outputs, in this order:

  1. rho(h), h = 1..30, per index, over the whole tape.
  2. sd correction factor sqrt(var_factor(r, rho_meas)/var_factor(r, [1])) for
     r = 1..60, with r = 19, 9, 4, 2 called out (those are the r values pin
     actually prices at, since r = tau - 1).
  3. The pin gate re-scored WALK FORWARD. rho for close C is estimated only
     from index increments whose last readable second is strictly before
     C - 900. Reliability table before and after, flip rate before and after,
     and the disjoint sets where the two models disagree about trading.
  4. The 880 identity, measured two ways.

Beside 3 run two CANARIES that are allowed to cheat, so the report can show
what a leak looks like in this harness:
   ORACLE  -- mu is the realised settlement average, fed through the same
              fair_at() call. Must score far better than the honest model.
   RHOLEAK -- rho estimated on hour blocks centred on the close, half in the
              future.
"""
import argparse
import glob
import json
import math
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import acvar                                                    # noqa: E402
from acvar import (BLOCK, FULLTAPE, IDXDIR, MAXLAG, N_AVG, PIN,   # noqa: E402
                   SERIES_TO_INDEX, RhoBook, bartlett, fair_at, gap_weights,
                   hour_of, load_index, qform, qform_se, sigma_from,
                   true_settle, var_factor_rho)

RHO_HOURS = 24           # trailing hours of increments behind each rho
TAUS = [20, 15, 10, 6, 4, 3]
# read from the exchange 2026-09-08 via /markets custom_strike.round_digits;
# BCH and ADA return no round_digits and have no settled markets in fulltape.
ROUND_DIGITS = {"KXBTC15M": 2, "KXETH15M": 2, "KXBNB15M": 2,
                "KXSOL15M": 4, "KXXRP15M": 4, "KXZEC15M": 4,
                "KXHYPE15M": 4, "KXNEAR15M": 4, "KXDOGE15M": 7}


def raw_factor(n, rho):
    """Var(X_{t+n} - X_t)/gamma0 under autocorrelation rho."""
    tot = n * rho[0]
    for h in range(1, len(rho)):
        if h < n:
            tot += 2 * rho[h] * (n - h)
    return tot


def wilson(k, n):
    if not n:
        return (0.0, 0.0)
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - s) / d, (c + s) / d)


def selftest():
    print("SELF-TEST -- acrun (delegates to acvar, then checks its own math)")
    ok = acvar.selftest()
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    ck(abs(raw_factor(959, [1.0]) - 959) < 1e-9,
       "raw_factor is n under white noise")
    ck(abs(raw_factor(100, [1.0, 0.5]) - (100 + 2 * 0.5 * 99)) < 1e-9,
       "raw_factor adds 2*rho_1*(n-1) at lag 1")
    ck(abs(qform(gap_weights(), [1.0]) / raw_factor(959, [1.0])
           - 880.0056 / 959) < 1e-6,
       "the gap/raw ratio is 880/959 = %.4f under white noise"
       % (880.0056 / 959))
    lo, hi = wilson(0, 300)
    ck(hi > 0.0 and hi < 0.02,
       "Wilson upper bound on 0/300 is a real bound (%.4f)" % hi)
    print("SELF-TEST " + ("PASSED" if (ok and not fails) else "*** FAILED ***"))
    return ok and not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rho-hours", type=int, default=RHO_HOURS)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if os.environ.get("KALS_SELFTESTED") != "1":
        if not selftest():
            raise SystemExit("self-test failed")
    t0 = time.time()

    # ---------------------------------------------------------------- data
    rows = [r for v in json.load(open(FULLTAPE, encoding="utf-8")).values()
            for r in v]
    ft_lo = min(float(r["close"]) for r in rows)
    ft_hi = max(float(r["close"]) for r in rows)
    print("\nSETTLEMENT TAPE: %d markets, closes %s .. %s"
          % (len(rows), time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(ft_lo)),
             time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(ft_hi))))

    files = sorted(glob.glob(os.path.join(IDXDIR, "2026*.jsonl.gz")))[:-1]
    files = [f for f in files if hour_of(f) <= ft_hi + 3600]
    if not files:
        raise SystemExit("loaded nothing: no index hours overlap the tape")
    print("INDEX TAPE: %s .. %s" % (os.path.basename(files[0]),
                                    os.path.basename(files[-1])))
    base, span, vals = load_index(files)
    if not vals:
        raise SystemExit("loaded nothing: no index ticks parsed")
    print("  grid %s .. %s  (%d seconds)"
          % (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(base)),
             time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(base + span)), span))
    for iid in sorted(vals):
        a_ = vals[iid]
        have = sum(1 for x in a_ if x == x)
        print("    %-14s %s / %s seconds present (%.1f%%)"
              % (iid, format(have, ","), format(span, ","),
                 100.0 * have / span))
    print("  load %.0fs" % (time.time() - t0))

    t1 = time.time()
    rb = RhoBook(base, span, vals, maxlag=MAXLAG)
    print("  rho blocks built in %.0fs (%d hour blocks per index)"
          % (time.time() - t1, rb.nblk))

    # ------------------------------------------------- 1. rho over the tape
    print("\n" + "=" * 78)
    print("1. AUTOCORRELATION OF ONE-SECOND INDEX INCREMENTS, WHOLE TAPE")
    print("=" * 78)
    end = base + span
    glob_rho = {}
    print("  %-14s%9s%9s%9s%9s%9s%9s%9s%12s"
          % ("index", "rho1", "rho2", "rho3", "rho5", "rho10", "rho20",
             "rho30", "n incr"))
    for iid in sorted(vals):
        r_, n_ = rb.at(iid, end + 10 ** 6, rb.nblk)
        if r_ is None:
            print("  %-14s  (too few increments)" % iid)
            continue
        glob_rho[iid] = (r_, n_)
        print("  %-14s%9.4f%9.4f%9.4f%9.4f%9.4f%9.4f%9.4f%12s"
              % (iid, r_[1], r_[2], r_[3], r_[5], r_[10], r_[20], r_[30],
                 format(n_, ",")))
    if not glob_rho:
        raise SystemExit("loaded nothing: no index had enough increments")
    anyn = max(n for _, n in glob_rho.values())
    print("  se(rho_h) under the white-noise null is ~1/sqrt(n) = %.5f "
          "at n = %s" % (1.0 / math.sqrt(anyn), format(anyn, ",")))
    print("  |rho_h| > %.5f is 2 sd." % (2.0 / math.sqrt(anyn)))

    print("\n  FULL LAG PROFILE, lags 1..30")
    print("  %-14s%s" % ("index", "".join("%7d" % h for h in range(1, 16))))
    for iid in sorted(glob_rho):
        r_ = glob_rho[iid][0]
        print("  %-14s%s"
              % (iid, "".join("%7.3f" % r_[h] for h in range(1, 16))))
    print("  %-14s%s" % ("", "".join("%7d" % h for h in range(16, 31))))
    for iid in sorted(glob_rho):
        r_ = glob_rho[iid][0]
        print("  %-14s%s"
              % (iid, "".join("%7.3f" % r_[h] for h in range(16, 31))))

    # -------------------------------------- 2. what that does to var_factor
    print("\n" + "=" * 78)
    print("2. sd RATIO  sqrt(var_factor(r, rho_measured) / "
          "var_factor(r, [1.0]))")
    print("   r = tau - 1, so r = 19 is tau = 20 and r = 2 is tau = 3.")
    print("=" * 78)
    heads = [1, 2, 3, 4, 5, 9, 14, 19, 29, 39, 59]
    print("  %-14s%s" % ("index r=", "".join("%8d" % r for r in heads)))
    for iid in sorted(glob_rho):
        r_ = glob_rho[iid][0]
        cells = []
        for r in heads:
            a_ = var_factor_rho(r, r_)
            b_ = var_factor_rho(r, [1.0])
            cells.append("%8.4f" % (math.sqrt(a_ / b_) if a_ > 0 and b_ > 0
                                    else float("nan")))
        print("  %-14s%s" % (iid, "".join(cells)))
    print("\n  same, with a Bartlett(30) taper on rho (noise-shrunk, PSD-safe)")
    print("  %-14s%s" % ("index r=", "".join("%8d" % r for r in heads)))
    for iid in sorted(glob_rho):
        r_ = bartlett(glob_rho[iid][0], MAXLAG)
        cells = []
        for r in heads:
            a_ = var_factor_rho(r, r_)
            b_ = var_factor_rho(r, [1.0])
            cells.append("%8.4f" % (math.sqrt(a_ / b_) if a_ > 0 and b_ > 0
                                    else float("nan")))
        print("  %-14s%s" % (iid, "".join(cells)))

    # ------------------------------------------------- 4. the 880 identity
    #   (printed before the calibration because it is cheap and it frames it)
    print("\n" + "=" * 78)
    print("4. DOES Var(settle - strike) = 880 sigma^2 SURVIVE THE MEASURED "
          "rho?")
    print("=" * 78)
    W = gap_weights()
    print("  predicted Var(settle-strike)/gamma0, and the same quantity")
    print("  divided by Var(X_t+959 - X_t)/gamma0 -- that RATIO cancels the")
    print("  level of sigma and most of the vol-of-vol, so it is the")
    print("  identity's shape rather than its scale.")
    print("  %-14s%12s%10s%12s%12s"
          % ("index", "pred /g0", "se", "pred ratio", "raw factor"))
    print("  %-14s%12.1f%10s%12.5f%12.1f"
          % ("white noise", qform(W, [1.0]), "-",
             qform(W, [1.0]) / raw_factor(959, [1.0]), raw_factor(959, [1.0])))
    pred880 = {}
    for iid in sorted(glob_rho):
        r_, n_ = glob_rho[iid]
        g = qform(W, r_)
        se = qform_se(W, n_)
        rf = raw_factor(959, r_)
        pred880[iid] = (g, se, rf)
        print("  %-14s%12.1f%10.1f%12.5f%12.1f"
              % (iid, g, se, g / rf if rf else float("nan"), rf))

    # ---- the decisive check: does the measured rho ACCUMULATE?
    # A rho that is real must show up as an n-second move whose variance
    # exceeds n*gamma0 by exactly 1 + 2*sum_h (1 - h/n) rho_h. A rho that is an
    # estimation artefact of the 1-second grid will not. This is the classic
    # variance-ratio test and it is the only thing that decides whether
    # rewriting var_factor is a correction or a decoration.
    print("\n  VARIANCE RATIO  V(n) / (n * gamma0):  measured vs predicted "
          "from rho")
    print("  gamma0 is the tape-wide mean square one-second increment; V(n)")
    print("  the tape-wide mean square n-second change over the same grid.")
    NS = [1, 2, 5, 10, 30, 60, 120, 300, 900]
    print("  %-14s%6s%s" % ("index", "", "".join("%9d" % n for n in NS)))
    for iid in sorted(vals):
        a_ = vals[iid]
        g0n = 0.0
        g0c = 0
        for i in range(len(a_) - 1):
            x = a_[i]
            y = a_[i + 1]
            if x == x and y == y:
                g0n += (y - x) ** 2
                g0c += 1
        if g0c < 1000:
            continue
        g0 = g0n / g0c
        meas = []
        for n in NS:
            step = 1 if n <= 30 else 5
            s = 0.0
            c = 0
            for i in range(0, len(a_) - n, step):
                x = a_[i]
                y = a_[i + n]
                if x == x and y == y:
                    s += (y - x) ** 2
                    c += 1
            meas.append((s / c / (n * g0)) if c > 1000 else float("nan"))
        r_ = glob_rho.get(iid, ([1.0], 0))[0]
        pred = [raw_factor(n, r_) / n for n in NS]
        print("  %-14s%6s%s" % (iid, "meas", "".join("%9.3f" % v
                                                     for v in meas)))
        print("  %-14s%6s%s" % ("", "pred", "".join("%9.3f" % v
                                                    for v in pred)))

    # empirical: over every quarter hour the index covers
    print("\n  MEASURED on the index tape itself (strike(N) = settle(N-1), so")
    print("  no published strike and no rounding enters this).")
    print("  ratio-of-means sum(d^2)/sum(sigma^2) is the honest analogue of")
    print("  Var(settle-strike)/gamma0; mean z2 divides case by case and is")
    print("  wrecked by vol clustering, so both are shown.")
    print("  %-14s%7s%11s%10s%11s%9s%9s%9s"
          % ("index", "n", "sum d2/", "mean z2", "median z2", "gap/raw",
             "predWN", "predrho"))
    print("  %-14s%7s%11s%10s%11s%9s%9s%9s"
          % ("", "", "sum sg2", "", "", "meas", "880", ""))
    first_c = ((base + 1000) // 900 + 2) * 900
    for iid in sorted(vals):
        a_ = vals[iid]
        s2 = []
        num = 0.0
        den = 0.0
        sg2 = 0.0
        c = first_c
        while c < base + span:
            st = true_settle(a_, base, c)
            pr = true_settle(a_, base, c - 900)
            if st is not None and pr is not None:
                i0 = c - 960 - base
                i1 = c - 1 - base
                if 0 <= i0 and i1 < len(a_) and a_[i0] == a_[i0] \
                        and a_[i1] == a_[i1]:
                    sg = sigma_from(a_, base, c - 960)
                    if sg and sg > 0:
                        d = st - pr
                        s2.append((d / sg) ** 2)
                        num += d * d
                        den += (a_[i1] - a_[i0]) ** 2
                        sg2 += sg * sg
            c += 900
        if len(s2) < 50:
            print("  %-14s  (only %d usable quarter hours)" % (iid, len(s2)))
            continue
        s2s = sorted(s2)
        mean = sum(s2) / len(s2)
        med = s2s[len(s2s) // 2]
        g, se, rf = pred880.get(iid, (float("nan"),) * 3)
        print("  %-14s%7d%11.1f%10.1f%11.1f%9.4f%9.1f%9.1f"
              % (iid, len(s2), (num / sg2) if sg2 else float("nan"), mean,
                 med, (num / den) if den else float("nan"), 880.0, g))

    # ------------------------------------------- 3. the gate, walk forward
    print("\n" + "=" * 78)
    print("3. THE pin GATE RE-SCORED WITH THE CORRECTED VARIANCE, WALK "
          "FORWARD")
    print("   rho for close C uses only hour blocks whose last readable")
    print("   second is < C - 900 (the PREVIOUS close). Trailing window "
          "%d h." % a.rho_hours)
    print("=" * 78)

    variants = ["WN", "AC30", "AC30T", "AC5", "ORACLE", "RHOLEAK"]
    buckets = {v: defaultdict(lambda: [0, 0]) for v in variants}
    fine = {v: defaultdict(lambda: [0, 0]) for v in variants}
    gate = {v: [0, 0] for v in variants}
    gate_tau = {v: defaultdict(lambda: [0, 0]) for v in variants}
    brier = {v: [0.0, 0] for v in variants}
    closes = {v: set() for v in variants}
    disagree = {"WN only": [0, 0], "AC only": [0, 0], "both": [0, 0]}
    dis_who = {"WN only": set(), "AC only": set(), "both": set()}
    dis_cl = {"WN only": set(), "AC only": set(), "both": set()}
    near = {v: [0, 0] for v in ["WN", "AC30T"]}     # marginal calls only
    calls = []     # every WN gate call: (wn_fair, ac_fair, won, iid)
    sdfac = defaultdict(list)   # per index, the walk-forward sd factor at r=19
    leakproof = {"checked": 0, "violations": 0, "max_read": None}
    rho_cache = {}
    seen_markets = 0
    nrho_none = 0

    def rho_for(iid, close_s):
        # keyed on the NEWEST ADMISSIBLE BLOCK, not on the hour containing the
        # cutoff. Four closes share an hour; keying on the hour let whichever
        # close was iterated first fix the block set for the other three, and
        # since fulltape rows are not in ascending close order that leaked
        # blocks forward. Caught by the audit below on the first run.
        lb = rb.last_block(iid, close_s - 900)
        key = (iid, lb)
        hit = rho_cache.get(key)
        if hit is None:
            r_, n_ = rb.at(iid, close_s - 900, a.rho_hours)
            lt = rb.last_touched_sec(iid, close_s - 900, a.rho_hours)
            hit = (r_, n_, lt)
            rho_cache[key] = hit
        return hit

    vf_cache = {}

    def vf(key, r, rho):
        k = (key, r)
        hit = vf_cache.get(k)
        if hit is None:
            hit = vf_cache[k] = var_factor_rho(r, rho)
        return hit

    for row in rows:
        s = row["series"]
        iid = SERIES_TO_INDEX.get(s)
        d = ROUND_DIGITS.get(s)
        if not iid or iid not in vals or d is None:
            continue
        a_ = vals[iid]
        close_s = int(float(row["close"]))
        if not (base + 1300 < close_s < base + span):
            continue
        K = float(row["strike"]) - 0.5 * (10.0 ** (-d))
        won = 1.0 if float(row["result"]) >= 0.5 else 0.0
        r_wf, n_wf, lt = rho_for(iid, close_s)
        if r_wf is None:
            nrho_none += 1
            continue
        leakproof["checked"] += 1
        if lt is None or lt >= close_s - 900:
            leakproof["violations"] += 1
        off = close_s - lt
        if leakproof["max_read"] is None or off < leakproof["max_read"]:
            leakproof["max_read"] = off
        r_lk, _ = rb.centred(iid, close_s, a.rho_hours)
        lb = rb.last_block(iid, close_s - 900)
        cb = (close_s - base) // BLOCK
        rs = {"WN": [1.0], "AC30": r_wf, "AC30T": bartlett(r_wf, MAXLAG),
              "AC5": r_wf[:6], "ORACLE": [1.0],
              "RHOLEAK": r_lk if r_lk else [1.0]}
        # every vf cache key must determine its rho exactly, or the cache
        # becomes a second, quieter leak.
        keys = {"WN": "wn", "AC30": (iid, lb, "a"),
                "AC30T": (iid, lb, "t"), "AC5": (iid, lb, "5"),
                "ORACLE": "wn", "RHOLEAK": (iid, cb, "L")}
        seen_markets += 1
        ts = true_settle(a_, base, close_s)
        w19 = vf(keys["AC30T"], 19, rs["AC30T"])
        b19 = vf("wn", 19, [1.0])
        if w19 > 0 and b19 > 0:
            sdfac[iid].append(math.sqrt(w19 / b19))

        for tau in TAUS:
            now = close_s - tau
            sg = sigma_from(a_, base, now)
            if sg is None or sg <= 0:
                continue
            r = tau - 1
            f_by = {}
            for v in variants:
                mu_ov = ts if v == "ORACLE" else None
                if v == "ORACLE" and ts is None:
                    continue
                rr = rs[v]
                vfac = vf(keys[v], r, rr)
                if vfac <= 0:
                    continue
                fv = fair_at(a_, base, close_s, now, K, sg, rr,
                             mu_override=mu_ov)
                if fv is None:
                    continue
                f_by[v] = fv
                buckets[v][min(9, int(fv * 10))][0] += 1
                buckets[v][min(9, int(fv * 10))][1] += won
                fb = (int(fv * 100) if fv < 0.99 else 99)
                if fv >= 0.98 or fv <= 0.02:
                    fine[v][int(round(fv * 1000))][0] += 1
                    fine[v][int(round(fv * 1000))][1] += won
                brier[v][0] += (fv - won) ** 2
                brier[v][1] += 1
                if fv >= PIN or fv <= 1 - PIN:
                    side = 1.0 if fv >= PIN else 0.0
                    gate[v][0] += 1
                    gate[v][1] += int(side == won)
                    gate_tau[v][tau][0] += 1
                    gate_tau[v][tau][1] += int(side == won)
                    closes[v].add(close_s)
            if "WN" in f_by and "AC30T" in f_by:
                w_ = f_by["WN"]
                c_ = f_by["AC30T"]
                gw = w_ >= PIN or w_ <= 1 - PIN
                gc = c_ >= PIN or c_ <= 1 - PIN
                if gw:
                    calls.append((w_, c_, won, iid))
                k = None
                if gw and gc:
                    k, side = "both", (1.0 if w_ >= PIN else 0.0)
                elif gw:
                    k, side = "WN only", (1.0 if w_ >= PIN else 0.0)
                elif gc:
                    k, side = "AC only", (1.0 if c_ >= PIN else 0.0)
                if k:
                    disagree[k][0] += 1
                    disagree[k][1] += int(side == won)
                    if side != won:
                        dis_who[k].add(row["ticker"])
                        dis_cl[k].add(close_s)
                # the MARGINAL band: calls the shipped model makes with a fair
                # value close enough to the gate that a few percent of sd can
                # move the decision. Everything outside it is decided by a
                # mile and tells us nothing about the variance model.
                if 0.98 <= w_ <= 0.999 or 0.001 <= w_ <= 0.02:
                    side = 1.0 if w_ >= PIN else 0.0
                    near["WN"][0] += 1
                    near["WN"][1] += int(side == won)
                    if gc:
                        side2 = 1.0 if c_ >= PIN else 0.0
                        near["AC30T"][0] += 1
                        near["AC30T"][1] += int(side2 == won)

    print("  %d settled markets priced; %d skipped for no walk-forward rho"
          % (seen_markets, nrho_none))
    print("  NO-LOOKAHEAD AUDIT: %d rho draws checked, %d read a second at or"
          " after their cutoff." % (leakproof["checked"],
                                    leakproof["violations"]))
    print("  The closest any admitted rho block came to a close was %s "
          "seconds before it." % format(leakproof["max_read"], ","))

    print("\n  RELIABILITY, all taus pooled, per decile of model fair value")
    print("  %-8s%s" % ("bucket", "".join("%22s" % v for v in
                                          ["WN (shipped)", "AC30T (corrected)",
                                           "ORACLE (cheats)"])))
    for b in range(10):
        cells = []
        for v in ["WN", "AC30T", "ORACLE"]:
            n, h = buckets[v][b]
            cells.append("%22s" % ("%s / %.1f%%" % (format(n, ","),
                                                    100.0 * h / n)
                                   if n else "-"))
        print("  %2d-%3d%% %s" % (b * 10, b * 10 + 10, "".join(cells)))

    print("\n  BRIER SCORE over every priced market-second (lower is better)")
    for v in variants:
        s_, n_ = brier[v]
        if n_:
            print("    %-8s %.6f   (n = %s)" % (v, s_ / n_, format(n_, ",")))

    print("\n  THE GATE (fair >= %.2f or <= %.2f)" % (PIN, 1 - PIN))
    print("  %-9s%10s%9s%12s%14s%10s"
          % ("variant", "calls", "wrong", "flip rate", "95% CI upper",
             "closes"))
    for v in variants:
        n, h = gate[v]
        if not n:
            continue
        fl = n - h
        lo, hi = wilson(fl, n)
        print("  %-9s%10s%9d%11.2f%%%13.2f%%%10s"
              % (v, format(n, ","), fl, 100.0 * fl / n, 100.0 * hi,
                 format(len(closes[v]), ",")))

    print("\n  THE GATE BY tau  (r = tau - 1)")
    print("  %-6s%s" % ("tau", "".join("%26s" % v for v in
                                       ["WN", "AC30T", "ORACLE"])))
    for tau in TAUS:
        cells = []
        for v in ["WN", "AC30T", "ORACLE"]:
            n, h = gate_tau[v][tau]
            cells.append("%26s" % ("%s calls, %.2f%% flips"
                                   % (format(n, ","), 100.0 * (n - h) / n)
                                   if n else "-"))
        print("  %-6d%s" % (tau, "".join(cells)))

    print("\n  THE CORRECTION ACTUALLY DEPLOYED, per close, WALK FORWARD.")
    print("  sd factor at r = 19 (tau = 20) from the trailing-%dh rho only."
          % a.rho_hours)
    print("  A wide min-max here means the correction is being re-estimated")
    print("  into noise; a tight one means it is a stable property of the "
          "index.")
    print("  %-14s%8s%9s%9s%9s%9s%12s"
          % ("index", "closes", "mean", "p10", "p50", "p90", "min .. max"))
    for iid in sorted(sdfac):
        v = sorted(sdfac[iid])
        if len(v) < 20:
            continue
        n = len(v)
        print("  %-14s%8d%9.4f%9.4f%9.4f%9.4f%12s"
              % (iid, n, sum(v) / n, v[n // 10], v[n // 2], v[9 * n // 10],
                 "%.3f..%.3f" % (v[0], v[-1])))

    print("\n  RELIABILITY IN THE TAIL ONLY -- the part pin trades.")
    print("  fair >= 0.98 side YES, fair <= 0.02 side NO, binned by how far")
    print("  inside the gate the model claims to be.")
    edges = [(0.980, 0.990), (0.990, 0.995), (0.995, 0.999), (0.999, 1.001)]
    print("  %-16s%s" % ("|fair| band", "".join("%24s" % v for v in
                                                ["WN (shipped)",
                                                 "AC30T (corrected)"])))
    for lo_, hi_ in edges:
        cells = []
        for v in ["WN", "AC30T"]:
            n = h = 0
            for key, (kn, kh) in fine[v].items():
                p = key / 1000.0
                q = p if p >= 0.5 else 1.0 - p
                if lo_ <= q < hi_:
                    n += kn
                    h += kh if p >= 0.5 else (kn - kh)
            cells.append("%24s" % ("%s calls, %.3f%% flip"
                                   % (format(n, ","), 100.0 * (n - h) / n)
                                   if n else "-"))
        print("  %.3f-%.3f  %s" % (lo_, hi_, "".join(cells)))

    print("\n  THE MARGINAL BAND (shipped fair in [0.980,0.999] or "
          "[0.001,0.020])")
    for v in ["WN", "AC30T"]:
        n, h = near[v]
        if n:
            lo_, hi_ = wilson(n - h, n)
            print("    %-8s %s calls, %d wrong, flip rate %.2f%% "
                  "(95%% CI %.2f-%.2f%%)"
                  % (v, format(n, ","), n - h, 100.0 * (n - h) / n,
                     100.0 * lo_, 100.0 * hi_))

    print("\n  WHERE THE TWO MODELS DISAGREE ABOUT TRADING "
          "(WN vs AC30T, same taus)")
    print("  %-12s%10s%9s%12s%10s%9s"
          % ("set", "calls", "wrong", "flip rate", "flip mkts", "flip cls"))
    for k in ["both", "WN only", "AC only"]:
        n, h = disagree[k]
        print("  %-12s%10s%9d%11s%10s%9s"
              % (k, format(n, ","), n - h,
                 ("%.2f%%" % (100.0 * (n - h) / n)) if n else "-",
                 format(len(dis_who[k]), ","), format(len(dis_cl[k]), ",")))
    nb, hb = disagree["both"]
    nw, hw = disagree["WN only"]
    if nb and nw:
        base_rate = (nb - hb + nw - hw) / float(nb + nw)
        lam = base_rate * nw
        k_ = nw - hw
        p = 1.0 - sum(math.exp(-lam) * lam ** i / math.factorial(i)
                      for i in range(k_))
        print("  If the calls the correction DROPS were no worse than the "
              "rest,")
        print("  the %d dropped calls would carry %.3f flips on average; "
              "they carry %d." % (nw, lam, k_))
        print("  Poisson P(>= %d) = %.2g.  Independent unit is the CLOSE: "
              "those %d flips" % (k_, p, k_))
        print("  sit on %d distinct closes and %d distinct markets."
              % (len(dis_cl["WN only"]), len(dis_who["WN only"])))

    # ------------------------------------------------------------------
    # THE CONTROL THAT MATTERS. Widening sd by a per-index factor mostly
    # amounts to raising the gate. If simply raising the gate -- with no
    # autocorrelation model at all -- drops the SAME flips, the correction is
    # a threshold tweak wearing a variance model's clothes. So: take the same
    # NUMBER of calls the correction drops, but drop the least confident ones
    # under the SHIPPED model, and compare.
    # How big is the correction in the units pin actually trades? pin needs
    # net edge >= 0.5c after fees. The correction moves fair value, and the
    # move IS a change in claimed edge, cent for cent.
    print("\n  HOW MUCH FAIR VALUE MOVES, in cents, on calls the shipped "
          "model gates")
    print("  (positive = the correction says the shipped model was too "
          "confident)")
    print("  %-14s%9s%10s%10s%10s%12s"
          % ("index", "calls", "mean c", "p50 c", "p90 c", ">=0.5c"))
    bys = defaultdict(list)
    for w_, c_, won, iid in calls:
        conf_w = w_ if w_ >= 0.5 else 1.0 - w_
        conf_c = c_ if w_ >= 0.5 else 1.0 - c_
        bys[iid].append(100.0 * (conf_w - conf_c))
    for iid in sorted(bys):
        v = sorted(bys[iid])
        n = len(v)
        big = sum(1 for x in v if x >= 0.5)
        print("  %-14s%9s%10.3f%10.3f%10.3f%12s"
              % (iid, format(n, ","), sum(v) / n, v[n // 2], v[9 * n // 10],
                 "%s (%.1f%%)" % (format(big, ","), 100.0 * big / n)))
    allv = sorted(x for v in bys.values() for x in v)
    if allv:
        n = len(allv)
        big = sum(1 for x in allv if x >= 0.5)
        print("  %-14s%9s%10.3f%10.3f%10.3f%12s"
              % ("ALL", format(n, ","), sum(allv) / n, allv[n // 2],
                 allv[9 * n // 10], "%s (%.1f%%)" % (format(big, ","),
                                                     100.0 * big / n)))
    marg = sorted(100.0 * ((w_ if w_ >= 0.5 else 1 - w_)
                           - (c_ if w_ >= 0.5 else 1 - c_))
                  for w_, c_, won, iid in calls
                  if 0.98 <= (w_ if w_ >= 0.5 else 1 - w_) <= 0.999)
    if marg:
        n = len(marg)
        big = sum(1 for x in marg if x >= 0.5)
        print("  %-14s%9s%10.3f%10.3f%10.3f%12s"
              % ("MARGINAL", format(n, ","), sum(marg) / n, marg[n // 2],
                 marg[9 * n // 10], "%s (%.1f%%)" % (format(big, ","),
                                                     100.0 * big / n)))

    print("\n  CONTROL: is this a variance correction, or just a higher gate?")
    if calls:
        def conf(x):
            return abs(x[0] - 0.5)
        dropped_ac = [c for c in calls
                      if not (c[1] >= PIN or c[1] <= 1 - PIN)]
        m = len(dropped_ac)
        order = sorted(calls, key=conf)
        dropped_cf = order[:m]

        def flips(sub):
            f = 0
            for w_, c_, won, _ in sub:
                side = 1.0 if w_ >= PIN else 0.0
                f += int(side != won)
            return f
        tot_calls = len(calls)
        tot_flips = flips(calls)
        f_ac = flips(dropped_ac)
        f_cf = flips(dropped_cf)
        print("    shipped model: %s gate calls, %d flips"
              % (format(tot_calls, ","), tot_flips))
        print("    drop the %d calls the AUTOCORRELATION model rejects: "
              "%d flips removed" % (m, f_ac))
        print("    drop the %d LEAST CONFIDENT calls instead (no rho, just a "
              "higher gate): %d flips removed" % (m, f_cf))
        cut = conf(order[m - 1]) + 0.5 if m else 0.0
        print("    (that confidence-matched drop is the same as moving the "
              "gate to %.5f)" % cut)
        ov = len(set(map(id, dropped_ac)) & set(map(id, dropped_cf)))
        print("    the two dropped sets share %d of %d calls" % (ov, m))
        print("    per-index sd factors are what the rho model adds over a "
              "flat gate;")
        print("    if the two columns above are equal, that addition is "
              "worth nothing.")

    print("\n  done in %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
