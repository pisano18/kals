#!/usr/bin/env python3
# VERSION: 2026-09-08-pt1
"""pinprob_test.py -- score the COMPUTED probability against the tape.

Walk-forward by day: to price any close on day D, the move distribution is
built only from days strictly BEFORE D. A leak control (distribution built from
ALL days) is scored alongside; if the leak does not look better, the harness
cannot detect leakage and nothing here can be trusted.

Answers, on real settled markets:
  1. Is the EMPIRICAL p_flip better calibrated than the gaussian?
  2. What price ceiling does each imply, and which one matches reality?
  3. Trading on EV computed from each: trades, flips, realised c/contract,
     and -- the operator's bar -- CONSISTENCY ACROSS DAYS.
"""
import argparse
import array
import bisect
import json
import math
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pinprob as P                                          # noqa: E402
from engine import N_AVG                                     # noqa: E402

TAUS = [3, 5, 10, 15, 20]
SUB = 3          # subsample stride when building the move distribution


def day_of(ts):
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def build_hist(base, arr, upto_sec, taus, stride=SUB):
    """Move distribution from ticks STRICTLY BEFORE upto_sec."""
    h = P.Hist()
    n = len(arr)
    end = min(n, upto_sec - base)
    for tau in taus:
        r = tau - 1
        lst = h.by_r[r]
        i = 0
        lim = end - r - 1
        while i < lim:
            v0 = arr[i]
            if v0 == v0:                      # not NaN
                s = 0.0
                ok = True
                for j in range(1, r + 1):
                    x = arr[i + j]
                    if x != x:
                        ok = False
                        break
                    s += x
                if ok:
                    lst.append(s / r - v0)
            i += stride
    return h.finalise()


def sigma_at(base, arr, now_sec, win=300):
    i = now_sec - base
    lo = max(1, i - win)
    tot = k = 0
    for j in range(lo, i + 1):
        a, b = arr[j - 1], arr[j]
        if a == a and b == b:
            d = b - a
            tot += d * d
            k += 1
    return math.sqrt(tot / k) if k >= 20 else None


def cell(base, arr, close_s, tau, strike, d):
    """(mu, required_move, spot) or None."""
    now = close_s - tau
    r = tau - 1
    if r < 1:
        return None
    lo, hi = close_s - N_AVG, now
    if lo - base < 0 or hi - base >= len(arr):
        return None
    got = tot = 0
    for s in range(lo, hi + 1):
        v = arr[s - base]
        if v == v:
            tot += v
            got += 1
    want = hi - lo + 1
    if got < want * 0.95:
        return None
    locked = tot * (want / got)
    spot = arr[now - base]
    if spot != spot:
        return None
    mu = (locked + r * spot) / N_AVG
    K = P.eff_strike(strike, d)
    return mu, (60.0 / r) * (K - mu), spot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=336)
    ap.add_argument("--evfloor", type=float, default=0.003)
    a = ap.parse_args()
    if not P.selftest():
        raise SystemExit("pinprob self-test failed")

    print("\n  loading index tape ...")
    t0 = time.time()
    ticks, nf, bad = P.load_ticks(a.hours)
    print(f"  {nf} hour files ({bad} damaged), {len(ticks)} indices, "
          f"{time.time()-t0:.0f}s")

    rows = [r for v in json.load(open(P.FULLTAPE, encoding="utf-8")).values()
            for r in v if r["series"] in P.SERIES_TO_INDEX]
    rows.sort(key=lambda r: float(r["close"]))
    print(f"  {len(rows):,} settled markets\n")

    days = sorted({day_of(float(r["close"])) for r in rows})
    hist_wf, hist_leak = {}, {}
    res = defaultdict(lambda: defaultdict(lambda: [0, 0, 0.0]))  # model->day->[n,flips,pnl]
    cal = defaultdict(lambda: defaultdict(lambda: [0, 0]))       # model->bucket->[n,flips]
    ceil_hit = defaultdict(int)

    for di, day in enumerate(days):
        drows = [r for r in rows if day_of(float(r["close"])) == day]
        if di < 3:
            continue                                   # need history first
        day_start = min(float(r["close"]) for r in drows)
        for iid, (base, arr) in ticks.items():
            hist_wf[iid] = build_hist(base, arr, int(day_start), TAUS)
            if iid not in hist_leak:
                hist_leak[iid] = build_hist(base, arr, base + len(arr), TAUS)

        for r_ in drows:
            iid = P.SERIES_TO_INDEX[r_["series"]]
            if iid not in ticks:
                continue
            base, arr = ticks[iid]
            close_s = int(float(r_["close"]))
            won_yes = float(r_["result"]) >= 0.5
            d = P.ROUND_DIGITS.get(r_["series"])
            for tau in TAUS:
                c = cell(base, arr, close_s, tau, float(r_["strike"]), d)
                if c is None:
                    continue
                mu, req, spot = c
                sg = sigma_at(base, arr, close_s - tau)
                if sg is None:
                    continue
                # which side does the model favour? mu above K -> YES
                side_yes = req <= 0
                # the FLIP is the outcome going the other way
                flipped = (side_yes != won_yes)
                for name, hsrc in (("empirical", hist_wf),
                                   ("LEAK", hist_leak)):
                    pf = hsrc[iid].p_worse_than(tau - 1, req)
                    if pf is None:
                        continue
                    cal[name][min(9, int(-math.log10(max(pf, 1e-9))))][0] += 1
                    cal[name][min(9, int(-math.log10(max(pf, 1e-9))))][1] += flipped
                pg = P.gauss_p_flip(req, sg, tau - 1)
                cal["gaussian"][min(9, int(-math.log10(max(pg, 1e-9))))][0] += 1
                cal["gaussian"][min(9, int(-math.log10(max(pg, 1e-9))))][1] += flipped

                # ---- trading: pay the market's price, capped by EV ----
                # we do not have the book here, so score at a RANGE of prices
                for price in (0.999, 0.996, 0.99, 0.98, 0.97, 0.95):
                    for name, pf in (("empirical",
                                      hist_wf[iid].p_worse_than(tau - 1, req)),
                                     ("gaussian", pg)):
                        if pf is None:
                            continue
                        ev = P.expected_value(price, pf)
                        if ev < a.evfloor:
                            continue
                        key = f"{name}@{100*price:.1f}c"
                        cell_ = res[key][day]
                        cell_[0] += 1
                        cell_[1] += flipped
                        cell_[2] += (-price if flipped else (1 - price)) \
                            - P.billed_fee(price, 1)
                        ceil_hit[key] += 1

    print("  CALIBRATION -- when a model says the flip chance is about X,")
    print("  how often did the flip actually happen?\n")
    print(f"  {'model':<12}{'says ~':>10}{'n':>9}{'flips':>8}{'realised':>11}")
    for name in ("gaussian", "empirical", "LEAK"):
        for b in sorted(cal[name]):
            n, f = cal[name][b]
            if n < 30:
                continue
            print(f"  {name:<12}{10.0**-b:>9.1e}{n:>9,}{f:>8,}"
                  f"{(f/n if n else 0):>10.2%}")
        print()

    print("  TRADING ON EV, walk-forward, by price paid\n")
    print(f"  {'rule':<22}{'trades':>8}{'flips':>7}{'flip%':>8}"
          f"{'realised c':>12}{'days+':>7}{'days-':>7}")
    for key in sorted(res, key=lambda k: (k.split("@")[1], k)):
        byday = res[key]
        n = sum(v[0] for v in byday.values())
        f = sum(v[1] for v in byday.values())
        p = sum(v[2] for v in byday.values())
        if n < 20:
            continue
        dp = sum(1 for v in byday.values() if v[2] > 0)
        dn = sum(1 for v in byday.values() if v[2] < 0)
        print(f"  {key:<22}{n:>8,}{f:>7,}{(f/n):>7.2%}"
              f"{100*p/n:>11.2f}c{dp:>7}{dn:>7}")


if __name__ == "__main__":
    main()
