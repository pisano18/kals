#!/usr/bin/env python3
# VERSION: 2026-09-08-pw1
"""pinwindow.py -- does starting EARLIER get us a better price, or just a worse bet?

THE OPERATOR'S QUESTION: run the EXACT live rule but open the window at 3
minutes, then 2, then 1.5, then the current 30 s, and see what actually
happens on real historical data.

WHY IT MIGHT WORK. Earlier in a window fewer participants have done the
settlement arithmetic, so the book should be deeper and the mispricings
larger. There is a real chance of a better price.

WHY IT MIGHT NOT. At tau seconds, tau-1 of the 60 settlement prints are still
unpublished, so the fraction of the answer that is already FIXED collapses:
  tau  30 -> 51% of the settlement already published
  tau  90 -> 0% (the settlement window has not even opened)
  tau 180 -> 0%
Beyond 60 seconds NONE of the settlement has happened yet. The model is then
pricing a pure forecast, and the project has already measured that its
confidence is 10.9x overconfident by tau 46-60.

THE RULE IS HELD EXACTLY AS IT RUNS LIVE -- model p_flip <= 0.02, EV >= 0.3c at
the measured 0.90% flip rate, scale in up to 2 buys per close on a >= 0.5c
improvement, one close at a time. ONLY the window start moves. That is what
makes it a fair test rather than a new strategy.
"""
import argparse
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor, N_AVG                        # noqa: E402
from statistics import NormalDist                           # noqa: E402

ND = NormalDist()
MEASURED_FLIP = 0.0090
EV_FLOOR = 0.003
IMPROVE_BY = 0.005
MAX_PER_CLOSE = 2


def billed_fee(p, n=1):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def ev(price, flip=MEASURED_FLIP):
    return (1 - flip) * (1 - price) - flip * price - billed_fee(price, 1)


def model_p_flip(row):
    r = row["r"]
    sg = row.get("sig")
    if not sg or r < 1:
        return None
    sd = sg * math.sqrt(var_factor(int(r), [1.0])) * (60.0 / r)
    if sd <= 0:
        return 0.0 if row["req"] <= 0 else 1.0
    z = row["req"] / sd
    return (1 - ND.cdf(z)) if row["req"] > 0 else ND.cdf(z)


def selftest():
    print("SELF-TEST -- pinwindow")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    ck(ev(0.95) > EV_FLOOR > ev(0.99), "the EV gate is the live one")
    # the settlement window has not even opened before tau 61
    for tau, locked in ((30, 31), (60, 1), (90, 0), (180, 0)):
        r = tau - 1
        got = max(0, N_AVG - r)
        ck(got == locked or (tau > 60 and got == 0),
           f"at tau={tau}, {got} of 60 settlement prints are published")
    ck(N_AVG - (90 - 1) <= 0,
       "beyond 60 seconds NOTHING of the settlement has happened yet -- the "
       "model is pricing a pure forecast")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def run(rows, tau_hi, tau_lo=3):
    byclose = defaultdict(list)
    for r in rows:
        if not (tau_lo <= r["tau"] <= tau_hi):
            continue
        pf = model_p_flip(r)
        if pf is None or pf > 0.02:
            continue
        if ev(r["price"]) < EV_FLOOR:
            continue
        r["_pf"] = pf
        byclose[r["close"]].append(r)
    for cl in byclose:
        byclose[cl].sort(key=lambda x: -x["tau"])       # earliest first
    n = flips = 0
    pnl = 0.0
    px = []
    closes = 0
    for cl, seq in byclose.items():
        closes += 1
        best = None
        bought = 0
        for x in seq:
            if bought >= MAX_PER_CLOSE:
                break
            if best is not None and x["price"] >= best - IMPROVE_BY:
                continue
            best = x["price"] if best is None else min(best, x["price"])
            bought += 1
            n += 1
            px.append(x["price"])
            fl = bool(x["flip"])
            flips += fl
            pnl += (-x["price"] if fl else (1 - x["price"])) - billed_fee(x["price"], 1)
    return {"closes": closes, "n": n, "flips": flips, "pnl": pnl,
            "avg": (sum(px) / len(px)) if px else 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=r"C:\kals-repo\results\pindata_long\rows.jsonl")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")
    if not os.path.exists(a.rows):
        raise SystemExit(f"no dataset at {a.rows}")

    rows = []
    with open(a.rows, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    mx = max(r["tau"] for r in rows)
    print(f"\n  {len(rows):,} rows, tau up to {mx}s\n")
    print(f"  {'window':<22}{'closes':>8}{'buys':>7}{'avg px':>9}{'flips':>7}"
          f"{'flip%':>8}{'total':>11}{'c/close':>10}")
    base = None
    for tau_hi, lab in ((30, "3-30s  (LIVE)"), (45, "3-45s"), (60, "3-60s"),
                        (90, "3-90s  (1.5 min)"), (120, "3-120s (2 min)"),
                        (180, "3-180s (3 min)")):
        if tau_hi > mx:
            continue
        d = run(rows, tau_hi)
        if not d["n"]:
            continue
        cc = 100 * d["pnl"] / d["closes"]
        if base is None:
            base = cc
        mark = "" if base is None else ("  <-- LIVE" if tau_hi == 30 else
                                        f"  {cc-base:+.2f}c vs live")
        print(f"  {lab:<22}{d['closes']:>8,}{d['n']:>7,}{100*d['avg']:>8.2f}c"
              f"{d['flips']:>7}{(d['flips']/d['n']):>7.2%}{100*d['pnl']:>10.1f}c"
              f"{cc:>9.2f}c{mark}")

    print("\n  'c/close' is profit per OPPORTUNITY -- the fair comparison, since")
    print("  a wider window naturally finds more closes.")
    print("\n  Reminder of the arithmetic: at tau>60 NONE of the 60 settlement")
    print("  prints has been published yet, so the model is pricing a pure")
    print("  forecast. Calibration was already measured at 10.9x overconfident")
    print("  by tau 46-60.")


if __name__ == "__main__":
    main()
