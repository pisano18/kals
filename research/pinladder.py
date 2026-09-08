#!/usr/bin/env python3
# VERSION: 2026-09-08-pl1
"""pinladder.py -- one shot, or keep buying as the price improves?

THE OPERATOR'S QUESTION, and it is a real trade-off with three horns:

  * take the FIRST safe price and you never miss, but you never get the best
    price either;
  * WAIT for the best price and you get more per contract, but sometimes it
    never comes and you get nothing at all;
  * SCALE IN -- buy at the first safe price and keep buying as it improves --
    and you always own something, but early capital is spent at worse prices
    and may not be there for the good one.

The operator's own framing: "I do want maximum gains on the lowest price, but
also what if it never hits, but then what if too much money goes into a higher
price so not enough to spend on low."

STRATEGIES SCORED, all on the same qualifying seconds (tau 3-20, model >= 98%
sure, EV clears at the measured flip rate):

  FIRST        buy 1 at the first qualifying second.  <-- what runs live
  BEST         buy 1 at the window's lowest price. IMPOSSIBLE LIVE (it needs
               to know the future) and included ONLY as the ceiling on what
               any timing rule could achieve.
  SCALE_ALL    buy 1 every qualifying second, capped.
  SCALE_IMPROVE buy 1 only when the price beats our own last fill -- the
               operator's "continue buying as it changes" with discipline.
  PATIENT_k    skip the first k qualifying seconds, then behave like FIRST.
               Measures directly what waiting costs when the low never comes.
  BUDGET       spend at most N contracts per close, weighted toward better
               prices: 1 at the first safe price, 2 more only below it, etc.

Every strategy is capped at the same maximum contracts per close so the
comparison is per unit of risk, not per unit of size.
"""
import argparse
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import var_factor                                # noqa: E402
from statistics import NormalDist                            # noqa: E402

ND = NormalDist()
ROWS = r"C:\kals-repo\results\pindata\rows.jsonl"
MEASURED_FLIP = 0.0090
EV_FLOOR = 0.003


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


def pnl(price, flip, qty=1.0):
    return qty * ((-price if flip else (1 - price)) - billed_fee(price, 1))


def selftest():
    print("SELF-TEST -- pinladder")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    ck(pnl(0.95, False) > 0 > pnl(0.95, True), "a win pays, a loss costs")
    ck(abs(pnl(0.95, False) - (0.05 - billed_fee(0.95))) < 1e-12,
       "a win at 95c pays 5c minus the fee")
    ck(pnl(0.90, False) > pnl(0.97, False),
       "buying lower pays more when right")
    ck(pnl(0.90, True) > pnl(0.97, True),
       "and ALSO loses less when wrong -- lower is better both ways")
    # a ladder of 3 at falling prices beats 3 at the first price
    lad = pnl(0.97, False) + pnl(0.95, False) + pnl(0.93, False)
    flat = 3 * pnl(0.97, False)
    ck(lad > flat, f"a falling ladder beats three at the first price "
                   f"({100*lad:.1f}c vs {100*flat:.1f}c)")
    # but when wrong, the ladder loses more in total than one contract
    ck(pnl(0.97, True) + pnl(0.95, True) < pnl(0.97, True),
       "and when wrong the ladder loses more -- size is risk")
    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--cap", type=int, default=3,
                    help="max contracts per close, same for every strategy")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed")

    rows = []
    with open(ROWS, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    # qualifying seconds only, grouped by close
    byclose = defaultdict(list)
    for r in rows:
        if not (3 <= r["tau"] <= 20):
            continue
        pf = model_p_flip(r)
        if pf is None or pf > 0.02:
            continue
        if ev(r["price"]) < EV_FLOOR:
            continue
        byclose[r["close"]].append(r)
    for cl in byclose:
        byclose[cl].sort(key=lambda x: -x["tau"])      # earliest first
    print(f"\n  {len(byclose):,} closes with at least one qualifying second")
    nq = sum(len(v) for v in byclose.values())
    print(f"  {nq:,} qualifying seconds "
          f"({nq/max(len(byclose),1):.1f} per close)\n")

    res = defaultdict(lambda: {"n": 0, "qty": 0.0, "pnl": 0.0, "flips": 0,
                               "closes": 0, "px": []})

    def book(name, fills, flip):
        d = res[name]
        if not fills:
            return
        d["closes"] += 1
        for p in fills:
            d["n"] += 1
            d["qty"] += 1
            d["px"].append(p)
            d["pnl"] += pnl(p, flip)
        d["flips"] += flip

    for cl, seq in byclose.items():
        flip = bool(seq[0]["flip"])
        prices = [x["price"] for x in seq]

        book("FIRST (live rule)", prices[:1], flip)
        book("BEST (needs the future)", [min(prices)], flip)
        book(f"SCALE_ALL cap{a.cap}", prices[:a.cap], flip)

        # buy only when it beats our last fill
        fills, last = [], None
        for p in prices:
            if last is None or p < last - 1e-9:
                fills.append(p)
                last = p
                if len(fills) >= a.cap:
                    break
        book(f"SCALE_IMPROVE cap{a.cap}", fills, flip)

        for k in (1, 2, 4):
            book(f"PATIENT skip{k}", prices[k:k + 1], flip)

        # budget: 1 at first, then 1 more only if 1c better, then 1c better again
        fills, last = [], None
        for p in prices:
            if last is None:
                fills.append(p)
                last = p
            elif p <= last - 0.01:
                fills.append(p)
                last = p
            if len(fills) >= a.cap:
                break
        book(f"BUDGET step1c cap{a.cap}", fills, flip)

    print(f"  {'strategy':<26}{'closes':>8}{'buys':>7}{'avg px':>9}"
          f"{'losses':>8}{'total':>11}{'c/contract':>12}{'c/close':>10}")
    order = ["FIRST (live rule)", f"SCALE_IMPROVE cap{a.cap}",
             f"BUDGET step1c cap{a.cap}", f"SCALE_ALL cap{a.cap}",
             "PATIENT skip1", "PATIENT skip2", "PATIENT skip4",
             "BEST (needs the future)"]
    base = None
    for name in order:
        d = res.get(name)
        if not d or not d["n"]:
            print(f"  {name:<26}{0:>8}")
            continue
        avg = sum(d["px"]) / len(d["px"])
        cpc = 100 * d["pnl"] / d["n"]
        ccl = 100 * d["pnl"] / max(d["closes"], 1)
        if base is None:
            base = d["pnl"]
        print(f"  {name:<26}{d['closes']:>8,}{d['n']:>7,}{100*avg:>8.2f}c"
              f"{d['flips']:>8}{100*d['pnl']:>10.1f}c{cpc:>11.2f}c"
              f"{ccl:>9.2f}c")

    print(f"\n  'c/close' is the fair comparison -- it is profit per "
          f"OPPORTUNITY,\n  not per contract, so a strategy is not rewarded "
          f"merely for buying more.")
    print(f"  BEST needs to know the future and is only the ceiling on what "
          f"any\n  timing rule could reach. PATIENT shows what waiting costs "
          f"when the\n  better price never arrives.")


if __name__ == "__main__":
    main()
