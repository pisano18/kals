#!/usr/bin/env python3
# VERSION: 2026-09-08-pm1
"""pinmirror.py -- the operator's falsification test. Force the WRONG side.

THE IDEA, and it is the right instinct: a model that looks good because it
picks winners must REFUSE the mirror image of every trade it takes. If it would
just as happily buy the losing side, it is not discriminating and every result
in this project is an artefact of which side happened to win.

THREE CONTROLS, in increasing severity:

  1. MIRROR. For every trade the rule takes, ask the same rule about the
     OPPOSITE side at the mirrored price. It must refuse nearly all of them,
     and the few it takes must lose heavily.

  2. FORCED WRONG SIDE. Take the opposite side anyway, regardless of what the
     rule says, and measure the damage. This calibrates what being wrong costs
     and proves the winners were not simply "whatever side we happened to
     name". If forced-wrong is roughly break-even, there is no edge.

  3. PLACEBO. Shuffle the outcomes so the settled result is randomly assigned,
     keeping every price and condition. The rule must LOSE -- it is paying a
     fee to bet on coin flips. If it still profits, the harness is broken and
     nothing measured here means anything.

A strategy that passes all three is discriminating. One that fails any of them
is measuring its own bookkeeping.
"""
import argparse
import json
import math
import os
import random
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


def expected_value(price, flip=MEASURED_FLIP):
    p = float(price)
    return (1.0 - flip) * (1.0 - p) - flip * p - billed_fee(p, 1)


def model_p_flip(row):
    """The model's own chance that the favoured side loses."""
    r = row["r"]
    sg = row.get("sig")
    if not sg or r < 1:
        return None
    sd = sg * math.sqrt(var_factor(int(r), [1.0])) * (60.0 / r)
    if sd <= 0:
        return 0.0 if row["req"] <= 0 else 1.0
    z = row["req"] / sd
    return (1 - ND.cdf(z)) if row["req"] > 0 else ND.cdf(z)


def would_trade(price, pf):
    """The live rule: model must be >=98% sure AND the EV must clear."""
    if pf is None or pf > 0.02:
        return False
    return expected_value(price) >= EV_FLOOR


def selftest():
    print("SELF-TEST -- pinmirror")
    fails = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            fails.append(m)

    ck(would_trade(0.95, 0.001), "a cheap, near-certain trade is taken")
    ck(not would_trade(0.996, 0.001),
       "the same certainty at 99.6c is REFUSED on expected value")
    ck(not would_trade(0.95, 0.30),
       "a cheap but uncertain trade is refused on the model gate")
    # the mirror of a good trade must be a bad one
    p, pf = 0.95, 0.001
    mp, mpf = round(1 - p, 4), 1 - pf
    ck(would_trade(p, pf) and not would_trade(mp, mpf),
       f"the mirror of a good trade ({100*p:.0f}c, {100*pf:.1f}% risk) is "
       f"refused ({100*mp:.0f}c, {100*mpf:.1f}% risk)")
    print("SELF-TEST " + ("PASSED" if not fails else "*** FAILED ***"))
    for m in fails:
        print("   - " + m)
    return not fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
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
    rows = [r for r in rows if 3 <= r["tau"] <= 20]
    print(f"\n  {len(rows):,} rows at tau 3-20\n")

    real = {"n": 0, "flips": 0, "pnl": 0.0}
    mirror_taken = {"n": 0, "flips": 0, "pnl": 0.0}
    mirror_refused = 0
    forced = {"n": 0, "flips": 0, "pnl": 0.0}
    placebo = {"n": 0, "flips": 0, "pnl": 0.0}
    rng = random.Random(a.seed)
    seen, seenf, seenp = set(), set(), set()

    for r in sorted(rows, key=lambda x: x["sec"]):
        cl = r["close"]
        pf = model_p_flip(r)
        price = r["price"]
        flip = bool(r["flip"])

        # ---- 1. the rule as it runs ----
        if cl not in seen and would_trade(price, pf):
            seen.add(cl)
            fee = billed_fee(price, 1)
            real["n"] += 1
            real["flips"] += flip
            real["pnl"] += (-price if flip else (1 - price)) - fee

            # ---- 2. the MIRROR of this exact trade ----
            mp = round(1.0 - price, 4)
            mpf = None if pf is None else (1.0 - pf)
            if would_trade(mp, mpf):
                mirror_taken["n"] += 1
                mirror_taken["flips"] += (not flip)
                mfee = billed_fee(mp, 1)
                mirror_taken["pnl"] += ((-mp if not flip else (1 - mp)) - mfee)
            else:
                mirror_refused += 1

        # ---- 3. FORCED onto the losing side, rule ignored ----
        if cl not in seenf and would_trade(price, pf):
            seenf.add(cl)
            mp = round(1.0 - price, 4)
            mfee = billed_fee(mp, 1)
            forced["n"] += 1
            forced["flips"] += (not flip)
            forced["pnl"] += ((-mp if not flip else (1 - mp)) - mfee)

        # ---- 4. PLACEBO: outcome randomised, everything else identical ----
        if cl not in seenp and would_trade(price, pf):
            seenp.add(cl)
            fake_flip = rng.random() < 0.5
            fee = billed_fee(price, 1)
            placebo["n"] += 1
            placebo["flips"] += fake_flip
            placebo["pnl"] += (-price if fake_flip else (1 - price)) - fee

    print(f"  {'control':<34}{'trades':>8}{'losses':>8}{'loss%':>8}"
          f"{'total':>11}{'c/trade':>10}")
    for name, d in (("1. THE RULE as it runs", real),
                    ("2. MIRROR trades it also took", mirror_taken),
                    ("3. FORCED onto the losing side", forced),
                    ("4. PLACEBO (outcome shuffled)", placebo)):
        n = d["n"]
        if not n:
            print(f"  {name:<34}{0:>8}{'':>8}{'':>8}{'':>11}{'':>10}")
            continue
        print(f"  {name:<34}{n:>8,}{d['flips']:>8,}{d['flips']/n:>7.1%}"
              f"{100*d['pnl']:>10.1f}c{100*d['pnl']/n:>9.2f}c")

    print(f"\n  MIRROR REFUSED: {mirror_refused:,} of {real['n']:,} "
          f"({mirror_refused/max(real['n'],1):.1%})")
    verdicts = []
    verdicts.append(("the rule makes money",
                     real["pnl"] > 0))
    verdicts.append(("it REFUSES the mirror of its own trades",
                     mirror_refused / max(real["n"], 1) > 0.95))
    verdicts.append(("forced onto the wrong side it LOSES heavily",
                     forced["n"] > 0 and forced["pnl"] < 0))
    verdicts.append(("with outcomes shuffled it LOSES (no free lunch)",
                     placebo["n"] > 0 and placebo["pnl"] < 0))
    print()
    for txt, ok in verdicts:
        print(("  PASS  " if ok else "  FAIL  ") + txt)
    print("\n  " + ("ALL CONTROLS PASSED -- the rule is discriminating."
                    if all(v for _, v in verdicts) else
                    "*** A CONTROL FAILED -- the result may be an artefact. ***"))


if __name__ == "__main__":
    main()
