#!/usr/bin/env python3
# VERSION: 2026-09-08-rfv1
"""remainfv.py -- WHAT THE REMAINING-PRINT ESTIMATOR DOES TO A TRADE.

remain.py measures the estimation error on its own.  This file carries the
same walk-forward estimators through to the number pin actually acts on:

    mu   = (locked_sum + r * xhat) / 60
    fair = Phi((mu - K_eff) / sd)
    gate = fair >= 0.98 (buy YES) or <= 0.02 (buy NO)

and scores the DECIDED-SIDE FLIP RATE against the settled result.  Flip rate
is the number that decides pin: the P&L shape is win ~1-3c, lose ~97c, so the
breakeven against a 2c win is 2.00%.

TWO VARIANTS, KEPT SEPARATE ON PURPOSE

  A. point estimate only -- sd stays sigma*sqrt(var_factor(r)), the shipped
     random-walk variance.  This isolates IMPROVEMENT 2 exactly as asked:
     change what stands in for the unprinted prints, change nothing else.
  B. point estimate AND sd, where sd = sigma * (r/60) * RMSE_wf(estimator, r)
     and RMSE_wf is that estimator's own realised error measured WALK-FORWARD
     on strictly earlier closes.  Under a pure random walk RMSE_wf(spot, r)
     equals sqrt((r+1)(2r+1)/6r) and variant B reduces exactly to variant A --
     the self-test checks that identity to 1e-12, so B is a strict
     generalisation and any difference it makes is a measured miscalibration
     of the variance, not a modelling choice.

NO PEEKING

Same discipline as remain.py and enforced the same way: closes are walked in
time order, every fitted quantity (lam, k, phi, RMSE_wf) is a running
sufficient statistic, and a close is absorbed into those statistics only
AFTER it has been scored.  The oracle and full-sample-lam leaks are carried
through to the flip-rate table too, so a leak shows up as an impossible flip
rate rather than as silence.

STRIKES.  fulltape `strike` is used as-is except for DOGE, where it is
provably truncated: strike(N+1) == round(mean of the 60 index prints of
window N, round_digits) reproduces the tape exactly for SOL and XRP and to
the last digit elsewhere, but misses 907 of 1011 DOGE strikes by up to 9e-7
against a 5e-8 settlement band.  round_digits is MEASURED from the tape (the
largest |mean60 - settle| per series is exactly half the last digit) and
cross-checked against custom_strike from the API when it is reachable.
A strike error moves every estimator identically, so the comparison between
estimators is unaffected by it; only the absolute flip rate is.
"""
import argparse
import collections
import json
import math
import os
import sys
import time
from array import array
from collections import defaultdict
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import remain                                               # noqa: E402
from remain import (cell, Fitter, estimates, EST_ORDER, KFIX, KS,  # noqa: E402
                    IDX_IDS, SERIES_TO_INDEX, load_cache, NAN)
from engine import var_factor, N_AVG                        # noqa: E402

ND = NormalDist()
PIN = 0.98
FULLTAPE = r"C:\kals\fulltape\markets.json"

# MEASURED, not assumed: max|mean60 - settle| per series is exactly half the
# last digit of `settle`.  Verified below in main() and re-checked against the
# API when kauth is reachable.
ROUND_DIGITS = {"KXBTC15M": 2, "KXETH15M": 2, "KXBNB15M": 2,
                "KXSOL15M": 4, "KXXRP15M": 4, "KXZEC15M": 4,
                "KXHYPE15M": 4, "KXNEAR15M": 4, "KXDOGE15M": 7}


def eff_strike(strike, d):
    return float(strike) - 0.5 * (10.0 ** (-int(d)))


def rw_rmse(r):
    """RMSE of (mean of r remaining prints - spot) in sigma units, random walk."""
    return math.sqrt((r + 1) * (2 * r + 1) / (6.0 * r))


def fair_from(locked, want, r, xhat, K, sd):
    mu = (locked + r * xhat) / N_AVG
    if sd <= 0:
        return 1.0 if mu >= K else 0.0
    return ND.cdf((mu - K) / sd)


class RmseWF:
    """Running per-(estimator, r) RMSE, updated only after a close is scored."""

    def __init__(self):
        self.s2 = defaultdict(float)
        self.n = defaultdict(int)

    def get(self, name, r):
        k = (name, r)
        if self.n[k] < 300:
            return None
        return math.sqrt(self.s2[k] / self.n[k])

    def add(self, name, r, e):
        k = (name, r)
        self.s2[k] += e * e
        self.n[k] += 1


# ===========================================================================
def selftest():
    print("SELF-TEST -- remainfv")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    # 1. variant B collapses onto variant A under the random walk
    worst = 0.0
    for r in range(1, 30):
        a = math.sqrt(var_factor(r, [1.0]))
        b = (r / float(N_AVG)) * rw_rmse(r)
        worst = max(worst, abs(a - b))
    ck(worst < 1e-12,
       "sd = sigma*(r/60)*RMSE_rw(r) IS sigma*sqrt(var_factor(r)) "
       "(max gap %.2e) -- variant B is a strict generalisation of A" % worst)

    # 2. eff_strike is the rounding band, checked by hand
    ck(abs(eff_strike(2492.82, 2) - 2492.815) < 1e-9,
       "eff_strike(2492.82, d=2) = %.4f (want 2492.815)"
       % eff_strike(2492.82, 2))

    # 3. fair_from arithmetic by hand: 30 locked prints at 100, r=30, xhat=100,
    #    K = 100 -> mu = 100 -> fair = 0.5 exactly
    f = fair_from(30 * 100.0, 30, 30, 100.0, 100.0, 1.0)
    ck(abs(f - 0.5) < 1e-12, "fair_from at the money is exactly 0.5 (%.6f)" % f)
    #    push mu one sd above K
    f2 = fair_from(30 * 100.0, 30, 30, 102.0, 100.0, 1.0)
    # mu = (3000 + 30*102)/60 = 101.0 -> z = 1 -> 0.8413
    ck(abs(f2 - 0.841344746) < 1e-6,
       "fair_from one sd in the money = %.6f (want 0.841345)" % f2)

    # 4. PLANTED OVERCONFIDENCE.  Truth has 2x the sd the model assumes, so
    #    the model's 98% gate must flip far more than 2% of the time, and
    #    widening sd by the measured factor must pull it back.
    import random
    rng = random.Random(5)
    nA = flA = nB = flB = 0
    for _ in range(20000):
        r, sigma = 5, 1.0
        locked = 55 * 100.0
        true_sd = 2.0 * sigma * math.sqrt(var_factor(r, [1.0]))
        settle = 100.0 + rng.gauss(0, true_sd)
        K = 100.0 + rng.gauss(0, 0.25)
        xhat = 100.0
        fA = fair_from(locked, 55, r, xhat, K,
                       sigma * math.sqrt(var_factor(r, [1.0])))
        fB = fair_from(locked, 55, r, xhat, K,
                       2.0 * sigma * math.sqrt(var_factor(r, [1.0])))
        won = 1.0 if settle >= K else 0.0
        for f, tag in ((fA, "A"), (fB, "B")):
            if f >= PIN or f <= 1 - PIN:
                side = 1.0 if f >= PIN else 0.0
                if tag == "A":
                    nA += 1
                    flA += int(side != won)
                else:
                    nB += 1
                    flB += int(side != won)
    rA = 100.0 * flA / max(nA, 1)
    rB = 100.0 * flB / max(nB, 1)
    print("  planted 2x-overconfident world: gate A %d calls, flip %.2f%%;  "
          "gate B (sd corrected) %d calls, flip %.2f%%" % (nA, rA, nB, rB))
    ck(nA > 200 and rA > 4.0,
       "the harness SEES an overconfident model as a high flip rate "
       "(%.2f%%, must be well above the 2%% claim)" % rA)
    ck(rB < rA / 2.0,
       "widening sd by the measured factor cuts the flip rate "
       "(%.2f%% -> %.2f%%)" % (rA, rB))

    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


# ===========================================================================
def api_round_digits():
    out = {}
    try:
        sys.path.append(r"C:\Users\Joe\AppData\Local\Temp\kals-work")
        from kauth import get
    except Exception as e:
        print("  round_digits cross-check: kauth unavailable (%s)" % e)
        return out
    for s in sorted(ROUND_DIGITS):
        try:
            st, b = get("/markets", {"series_ticker": s, "status": "open",
                                     "limit": "1"})
            ms = (b or {}).get("markets") or []
            if ms:
                d = (ms[0].get("custom_strike") or {}).get("round_digits")
                if d is not None:
                    out[s] = int(d)
        except Exception:
            pass
    return out


def measured_round_digits(ticks, base, by_series):
    """round_digits inferred from max|mean60 - settle| per series."""
    out = {}
    for s, iid in SERIES_TO_INDEX.items():
        if s not in by_series:
            continue
        arr = ticks[iid]
        worst = 0.0
        n = 0
        for C, row in by_series[s].items():
            i = C - base
            if i - N_AVG < 0 or i >= len(arr):
                continue
            vals = [arr[j] for j in range(i - N_AVG, i)]
            if any(v != v for v in vals):
                continue
            worst = max(worst, abs(sum(vals) / N_AVG - float(row["settle"])))
            n += 1
        if n >= 100 and worst > 0:
            # worst is half the last digit: 0.5 * 10^-d
            d = int(round(-math.log10(2.0 * worst)))
            out[s] = d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--taus", default="3,4,5,6,8,10,12,15,20")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    print()
    meta, ticks, avg60 = load_cache()
    base, n = meta["t0"], meta["n"]
    taus = [int(x) for x in a.taus.split(",")]
    rows = [r for v in json.load(open(FULLTAPE, encoding="utf-8")).values()
            for r in v]
    by_series = defaultdict(dict)
    for r in rows:
        by_series[r["series"]][int(float(r["close"]))] = r
    print("  fulltape: %d settled markets, %d series" % (len(rows),
                                                         len(by_series)))
    md = measured_round_digits(ticks, base, by_series)
    print("  round_digits MEASURED from max|mean60 - settle| : "
          + ", ".join("%s=%d" % kv for kv in sorted(md.items())))
    bad = {k: v for k, v in md.items() if ROUND_DIGITS.get(k) != v}
    print("  disagreements with the table used: %s" % (bad or "none"))
    ad = api_round_digits()
    if ad:
        print("  round_digits from custom_strike (API)          : "
              + ", ".join("%s=%d" % kv for kv in sorted(ad.items())))
        print("  API vs measured disagreements: %s"
              % ({k: (ad[k], md.get(k)) for k in ad if md.get(k) != ad[k]}
                 or "none"))

    # ---- strikes: derive DOGE from the index, keep fulltape elsewhere ----
    derived = 0
    for s in list(by_series):
        d = ROUND_DIGITS.get(s)
        if s != "KXDOGE15M" or d is None:
            continue
        arr = ticks[SERIES_TO_INDEX[s]]
        for C, row in by_series[s].items():
            i = C - 900 - base
            if i - N_AVG < 0 or i >= len(arr):
                continue
            vals = [arr[j] for j in range(i - N_AVG, i)]
            if any(v != v for v in vals):
                continue
            row["strike_used"] = round(sum(vals) / N_AVG, d)
            derived += 1
    for s in by_series:
        for C, row in by_series[s].items():
            row.setdefault("strike_used", float(row["strike"]))
    print("  DOGE strikes rebuilt from the index (fulltape truncates them): "
          "%d" % derived)

    closes = sorted(set(
        C for s in by_series for C in by_series[s]
        if base + 400 < C < base + n))
    print("  %d closes with settled markets inside the index window\n"
          % len(closes))

    fit = Fitter()
    rm = RmseWF()
    # gate[(variant, estimator)] -> [calls, flips]; per-close for clustering
    gate = defaultdict(lambda: [0, 0])
    gate_tau = defaultdict(lambda: [0, 0])
    per_close = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    sdratio = defaultdict(list)
    marg = defaultdict(lambda: [0, 0, 0, 0])
    roc = defaultdict(list)
    closes_used = set()
    t0 = time.time()

    for C in closes:
        cells = {}
        for s, iid in SERIES_TO_INDEX.items():
            if s not in by_series or C not in by_series[s]:
                continue
            arr = ticks[iid]
            for tau in taus:
                c = cell(arr, base, C, tau)
                if c is not None:
                    cells[(s, iid, tau)] = c
        if not cells:
            continue
        for (s, iid, tau), c in cells.items():
            row = by_series[s][C]
            d = ROUND_DIGITS.get(s)
            if d is None:
                continue
            K = eff_strike(row["strike_used"], d)
            won = 1.0 if float(row["result"]) >= 0.5 else 0.0
            r, sg = c["r"], c["sigma"]
            es = estimates(c, fit, iid)
            sdA = sg * math.sqrt(var_factor(r, [1.0]))
            f_spot = fair_from(c["locked"], c["want"], r, es["spot"], K, sdA)
            in_band = (0.002 <= f_spot <= 0.02) or (0.98 <= f_spot <= 0.998)
            for name in EST_ORDER:
                xhat = es[name]
                fA = fair_from(c["locked"], c["want"], r, xhat, K, sdA)
                if in_band:
                    dec_s = (f_spot >= PIN or f_spot <= 1 - PIN)
                    dec_e = (fA >= PIN or fA <= 1 - PIN)
                    if dec_e:
                        side = 1.0 if fA >= PIN else 0.0
                        marg[name][0] += 1
                        marg[name][1] += int(side != won)
                    if dec_s and not dec_e:
                        marg[name][2] += 1
                    if dec_e and not dec_s:
                        marg[name][3] += 1
                rr = rm.get(name, r)
                sdB = sdA if rr is None else sg * (r / float(N_AVG)) * rr
                fB = fair_from(c["locked"], c["want"], r, xhat, K, sdB)
                if name == "spot" and rr is not None:
                    sdratio[r].append(sdB / sdA)
                side = 1.0 if fA >= 0.5 else 0.0
                roc[name].append((max(fA, 1.0 - fA), int(side != won)))
                for var, f in (("A", fA), ("B", fB)):
                    if f >= PIN or f <= 1 - PIN:
                        side = 1.0 if f >= PIN else 0.0
                        ok = int(side == won)
                        gate[(var, name)][0] += 1
                        gate[(var, name)][1] += (1 - ok)
                        gate_tau[(var, name, tau)][0] += 1
                        gate_tau[(var, name, tau)][1] += (1 - ok)
                        per_close[(var, name)][C][0] += 1
                        per_close[(var, name)][C][1] += (1 - ok)
                        closes_used.add(C)
        # ---- absorb AFTER scoring ----
        for (s, iid, tau), c in cells.items():
            es = estimates(c, fit, iid)
            for name in EST_ORDER:
                rm.add(name, c["r"], (c["target"] - es[name]) / c["sigma"])
        seen = set()
        for (s, iid, tau), c in cells.items():
            if (iid, tau) in seen:
                continue
            seen.add((iid, tau))
            fit.absorb_cell(c)
        for iid in set(i for (_, i, _) in cells):
            fit.absorb_acf(iid, ticks[iid], base, C)

    print("  scored %d closes in %.0f s\n" % (len(closes_used), time.time() - t0))

    print("  VARIANT A -- POINT ESTIMATE ONLY (sd unchanged).  This is")
    print("  IMPROVEMENT 2 on its own: swap what stands in for the unprinted")
    print("  prints and change nothing else.")
    print("    %-14s %9s %8s %11s %11s" % ("estimator", "calls", "flips",
                                           "FLIP RATE", "vs spot"))
    bs = gate[("A", "spot")]
    b_rate = bs[1] / max(bs[0], 1)
    for name in EST_ORDER:
        g = gate[("A", name)]
        if not g[0]:
            continue
        rate = g[1] / g[0]
        print("    %-14s %9d %8d %10.3f%% %+10.3f pp"
              % (name, g[0], g[1], 100 * rate, 100 * (rate - b_rate)))
    print("    breakeven flip rate against a 2c win is 2.000%")

    print("\n  VARIANT B -- point estimate AND a walk-forward sd")
    print("    %-14s %9s %8s %11s" % ("estimator", "calls", "flips",
                                      "FLIP RATE"))
    for name in EST_ORDER:
        g = gate[("B", name)]
        if not g[0]:
            continue
        print("    %-14s %9d %8d %10.3f%%"
              % (name, g[0], g[1], 100 * g[1] / g[0]))

    print("\n  THE sd THE TAPE ACTUALLY WANTS (spot estimator)")
    print("    %-5s %9s %14s" % ("r", "n", "sd_B / sd_A"))
    for r in sorted(sdratio):
        v = sdratio[r]
        print("    %-5d %9d %14.3f" % (r, len(v), sum(v) / len(v)))
    print("    >1 means the shipped random-walk sd is TOO NARROW at that r,")
    print("    i.e. the model is overconfident there.")

    print("\n  FLIP RATE BY tau, variant A")
    print("    %-5s %10s %10s %10s %10s"
          % ("tau", "spot n", "spot flip", "ar1 flip", "shrink flip"))
    for tau in taus:
        g = gate_tau[("A", "spot", tau)]
        if not g[0]:
            continue
        def rt(nm):
            h = gate_tau[("A", nm, tau)]
            return "%.3f%%" % (100 * h[1] / h[0]) if h[0] else "--"
        print("    %-5d %10d %10s %10s %10s"
              % (tau, g[0], rt("spot"), rt("ar1"), rt("shrink")))

    print("\n  EQUAL-SELECTIVITY TEST -- is this INFORMATION or just a")
    print("  CONFIDENCE HAIRCUT?  Every estimator in the marginal band only")
    print("  ever DECLINES trades, never adds one, which is what tightening")
    print("  the gate does for free.  So rank every cell by how decisive that")
    print("  estimator says it is, take the top N, and count flips.  An")
    print("  estimator that carries real information wins at MATCHED N.")
    NS = [0, 100, 250, 500, 1000, 2000, 4000, 8000]
    print("    %-14s %s" % ("flips left after dropping the least-confident N:",
                            ""))
    print("    %-14s %s" % ("N dropped =", " ".join("%7d" % x for x in NS)))
    for name in ("spot", "mean2", "mean3", "mean5", "mean10", "shrink",
                 "shrink_ksel", "ar1", "LEAK_oracle"):
        v = sorted(roc[name], key=lambda z: z[0])   # least confident first
        tot = sum(x[1] for x in v)
        out, dropped, idx = [], 0, 0
        for N in NS:                      # ascending: cumulative is valid
            while idx < min(N, len(v)):
                dropped += v[idx][1]
                idx += 1
            out.append(tot - dropped)
        print("    %-14s %s" % (name, " ".join("%7d" % x for x in out)))
    print("    Cells are ranked by max(fair, 1-fair) ASCENDING, so dropping N")
    print("    means refusing the N calls that estimator is least sure of --")
    print("    exactly what tightening the gate does.  At matched N, an")
    print("    estimator carrying real information leaves fewer flips.")

    print("\n  THE MARGINAL BAND -- the only cells where a change of point")
    print("  estimate can change a decision.  spot's fair in [0.002,0.02] or")
    print("  [0.98,0.998]; the known ETH loss sat at 0.0052, inside it.")
    print("    %-14s %8s %7s %10s %9s %9s %9s"
          % ("estimator", "calls", "flips", "FLIP RATE", "chg out", "chg in",
             "net flips"))
    for name in EST_ORDER:
        m = marg[name]
        if not m[0]:
            continue
        print("    %-14s %8d %7d %9.3f%% %9d %9d %+9d"
              % (name, m[0], m[1], 100.0 * m[1] / m[0], m[2], m[3],
                 m[1] - marg["spot"][1]))
    print("    'chg out' = spot traded, this estimator did not.")
    print("    'chg in'  = this estimator traded where spot did not.")

    print("\n  CLUSTERED ON CLOSE -- flips per close, spot vs each estimator")
    print("    %-14s %8s %13s %9s" % ("estimator", "closes", "d flips/close",
                                      "t"))
    cl = sorted(per_close[("A", "spot")])
    for name in EST_ORDER:
        if name == "spot":
            continue
        ds = []
        for C in cl:
            a1 = per_close[("A", "spot")][C]
            a2 = per_close[("A", name)][C]
            ds.append(a2[1] - a1[1])
        if not ds:
            continue
        m = sum(ds) / len(ds)
        v = sum((x - m) ** 2 for x in ds) / (len(ds) - 1) if len(ds) > 2 else 0
        t = m / math.sqrt(v / len(ds)) if v > 0 else float("nan")
        print("    %-14s %8d %+13.5f %+9.2f" % (name, len(ds), m, t))
    print("    n is CLOSES, the independent unit; all coins settle on the")
    print("    same quarter hour at rho ~ 0.8.")
    return dict(gate=gate, rm=rm, fit=fit)


if __name__ == "__main__":
    main()
