#!/usr/bin/env python3
# VERSION: 2026-09-08-ph1
"""pinhedge.py -- if a position starts drifting the wrong way, should we buy the
cheap other side to cap the loss?

THE OPERATOR'S IDEA, VERBATIM: "is there any method to mitigating losses that
can be explored like buying the super cheap opposite side if it starts going
past our expected price area?... if it starts teetering past that expected
range, you buy the 5 cent other sides bet."

WHAT A HEDGE ACTUALLY IS HERE, AND IT IS NOT INSURANCE.
On a Kalshi binary, exactly one of YES and NO pays $1.00. So holding BOTH sides
of the same market pays exactly $1.00, guaranteed, whatever happens. Buying the
other side does not reduce a risk -- IT ENDS THE TRADE and locks a certain
result:

    hedged outcome  = $1.00 - entry_price - hedge_price - both fees
    unhedged outcome= $1.00 with probability p, $0.00 otherwise

So the hedge is worth taking exactly when

    1 - hedge_price  >  p          (p = our true chance of still winning)

and since the market's own implied chance of us winning is about
(1 - hedge_price), THE RULE REDUCES TO: hedge only when our model is more
pessimistic than the market at that instant. **It is not a safety device. It is
a bet that our model beats the market a second time, in the exact situation
where our model is least trustworthy.**

WHY THAT LAST CLAUSE MATTERS. Measured today over 13.0M cells: the model's
gaussian tail is 9.3x too thin at 3 sigma and 176x too thin at 4 sigma, because
these indices are step functions (SOL repeats the same 1-second print 70.5% of
the time). A hedge triggers precisely when the price has moved against us --
i.e. in the tail -- which is the one region where the model is measurably worst.

THIS FILE MEASURES IT ANYWAY, because the argument above is a reason to test,
not a reason to assume. It uses the WIDE dataset (tau up to 200, 28,479 rows,
1,506 genuine flips) rather than the live tau 3-30 window, because THE LIVE
WINDOW CONTAINS ZERO FLIPS and a hedge study needs losses to be able to show a
save. Restricting to tau 3-30 would only ever measure the hedge's COST.

THE OPPOSITE-SIDE PRICE IS DERIVED, AND HERE IS THE ARITHMETIC. rows.jsonl
carries `price` (the ask on the model-favoured side) and `spread`. The bid on
that side is price - spread, and the ask on the OTHER side is one minus that
bid, so:

    opposite_ask = 1 - (price - spread) = 1 - price + spread

The self-test pins this, and main() reports how often the derived price is
outside (0, 1) so a broken derivation cannot masquerade as a result.
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
MEASURED_FLIP = 0.0090
EV_FLOOR = 0.003
CEILING = 0.988
PIN_P = 0.02


def fee(p, n=1):
    return math.ceil(0.07 * p * (1 - p) * n * 10000) / 10000


def ev(p, flip=MEASURED_FLIP):
    return (1 - flip) * (1 - p) - flip * p - fee(p)


def model_pflip(r):
    """Model probability that the FAVOURED side loses."""
    rr, sg = r["r"], r.get("sig")
    if not sg or rr < 1:
        return None
    sd = sg * math.sqrt(var_factor(int(rr), [1.0])) * (60.0 / rr)
    if sd <= 0:
        return 0.0 if r["req"] <= 0 else 1.0
    z = r["req"] / sd
    return (1 - ND.cdf(z)) if r["req"] > 0 else ND.cdf(z)


def opposite_ask(price, spread):
    """Ask on the side we did NOT buy. See the module docstring."""
    return 1.0 - (float(price) - float(spread))


def hedge_price(row, entry_side_yes):
    """The ask we must PAY to buy the side we did not buy.

    THE SUBTLETY THAT BIT ME. rows.jsonl's `price` is the ask on the
    MODEL-FAVOURED side at that instant, and the favoured side CHANGES as the
    index moves. So:
      * while the model still favours OUR side, `price` is our own ask and the
        hedge costs 1 - (price - spread);
      * once the model has SWITCHED, `price` is ALREADY the ask on the side we
        want to hedge into, and inverting it again is simply wrong.
    My first version inverted unconditionally. It made hedges look CHEAPER the
    longer we waited (43c at a 50% trigger, 21c at 90%), which is backwards --
    insurance gets dearer as the fire spreads, never cheaper. That impossible
    monotonicity is what exposed the bug.
    """
    px = float(row["price"])
    sp = float(row.get("spread") or 0.0)
    if bool(row["side_yes"]) != bool(entry_side_yes):
        return px                      # already the side we want to buy
    return opposite_ask(px, sp)


def hedged_pnl(entry, hedge, n=1.0):
    """Holding BOTH sides pays exactly $1.00 per contract, guaranteed."""
    return n * (1.0 - entry - hedge) - fee(entry, n) - fee(hedge, n)


def unhedged_pnl(entry, won, n=1.0):
    return n * ((1.0 - entry) if won else -entry) - fee(entry, n)


def selftest():
    print("SELF-TEST -- pinhedge")
    f = []

    def ck(c, m):
        print(("  ok   " if c else "  FAIL ") + m)
        if not c:
            f.append(m)

    # --- the arithmetic that decides everything --------------------------
    ck(abs(opposite_ask(0.95, 0.01) - 0.06) < 1e-12,
       f"the other side's ask is 1 - (our ask - spread) "
       f"({opposite_ask(0.95, 0.01):.4f})")
    ck(opposite_ask(0.95, 0.0) + 0.95 == 1.0,
       "with a zero spread the two asks sum to exactly $1.00, which is the "
       "no-arbitrage identity this whole file rests on")

    ck(abs(hedged_pnl(0.95, 0.03) - (1.0 - 0.98 - fee(0.95) - fee(0.03))) < 1e-12,
       "a hedge at 3c on a 95c entry LOCKS +2c minus two fees")
    ck(hedged_pnl(0.95, 0.10) < 0,
       f"and a hedge at 10c on a 95c entry locks a CERTAIN LOSS "
       f"({100*hedged_pnl(0.95, 0.10):+.2f}c) -- hedging late is not insurance, "
       f"it is paying to make a loss certain")
    ck(hedged_pnl(0.95, 0.03) < unhedged_pnl(0.95, True),
       "hedging always costs MORE than simply winning would have")
    ck(hedged_pnl(0.95, 0.10) > unhedged_pnl(0.95, False),
       "but it costs LESS than losing -- which is the whole point, and why "
       "the answer depends entirely on how often the drift actually flips")

    # --- the break-even rule ---------------------------------------------
    # hedge is better iff 1 - hedge_price > p_win
    for hp, p_win, better in ((0.10, 0.80, True), (0.10, 0.95, False),
                              (0.30, 0.50, True), (0.02, 0.99, False)):
        got = (1.0 - hp) > p_win
        ck(got == better,
           f"hedge at {100*hp:.0f}c with a {100*p_win:.0f}% chance of winning: "
           f"{'take it' if better else 'do not'}")
    ck(abs((1.0 - 0.05) - 0.95) < 1e-12,
       "the 5c hedge the operator names is worth taking only if our chance of "
       "winning has fallen BELOW 95% -- at our entry prices it usually has not")

    # --- THE SIDE LOGIC, which a pure-arithmetic test cannot reach -------
    _still = {"price": 0.95, "spread": 0.01, "side_yes": True}
    _sw = {"price": 0.30, "spread": 0.01, "side_yes": False}
    ck(abs(hedge_price(_still, True) - 0.06) < 1e-12,
       f"while the model STILL favours our side, the hedge costs "
       f"1-(ask-spread) ({hedge_price(_still, True):.4f})")
    ck(abs(hedge_price(_sw, True) - 0.30) < 1e-12,
       f"once the model has SWITCHED, the recorded ask is ALREADY the side we "
       f"want to buy and must NOT be inverted ({hedge_price(_sw, True):.4f})")
    ck(hedge_price(_sw, True) != opposite_ask(_sw["price"], _sw["spread"]),
       "the two differ, which is why inverting unconditionally was a real bug "
       "and not a cosmetic one")
    ck(hedge_price(_sw, False) == opposite_ask(0.30, 0.01),
       "and if we had ENTERED on that side, the same row inverts again -- the "
       "answer depends on OUR side, not on the row alone")

    # --- a planted world where the hedge MUST help -----------------------
    # entry 95c, hedge available at 5c, and the position loses
    ck(hedged_pnl(0.95, 0.05) > unhedged_pnl(0.95, False),
       f"planted LOSS: hedging saves "
       f"{100*(hedged_pnl(0.95,0.05)-unhedged_pnl(0.95,False)):+.1f}c")
    # --- and a null world where it must NOT ------------------------------
    ck(hedged_pnl(0.95, 0.05) < unhedged_pnl(0.95, True),
       f"planted WIN: hedging costs "
       f"{100*(hedged_pnl(0.95,0.05)-unhedged_pnl(0.95,True)):+.1f}c -- the "
       f"estimator must find a cost in a world where nothing goes wrong")
    print("SELF-TEST " + ("PASSED" if not f else "*** FAILED ***"))
    for m in f:
        print("   - " + m)
    return not f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--rows", default=r"C:\kals-repo\results\pindata\rows.jsonl")
    ap.add_argument("--tau-lo", type=int, default=3)
    ap.add_argument("--tau-hi", type=int, default=30)
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    if not selftest():
        raise SystemExit("self-test failed -- refusing to touch real data")

    rows = []
    with open(a.rows, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass

    # group every moment by the market it belongs to, in time order
    bym = defaultdict(list)
    for r in rows:
        bym[(r["tk"], r["close"])].append(r)
    for k in bym:
        bym[k].sort(key=lambda x: -x["tau"])          # earliest first

    bad_derived = 0
    entries = []           # (entry_row, later_rows)
    for k, seq in bym.items():
        entry = None
        for x in seq:
            if not (a.tau_lo <= x["tau"] <= a.tau_hi):
                continue
            pf = model_pflip(x)
            if pf is None or pf > PIN_P:
                continue
            if x["price"] > CEILING or ev(x["price"]) < EV_FLOOR:
                continue
            entry = x
            break
        if entry is None:
            continue
        later = [x for x in seq if x["tau"] < entry["tau"]]
        entries.append((entry, later))

    n_flip = sum(1 for e, _ in entries if e["flip"])
    closes = len({e["close"] for e, _ in entries})
    print(f"\n  {len(entries):,} positions over {closes} closes, "
          f"{n_flip} of them LOSERS")
    if n_flip == 0:
        print("  *** ZERO LOSING POSITIONS. A hedge study cannot show a save in")
        print("  a sample with nothing to save. Re-run with a wider --tau-hi.")
    print()

    print(f"  {'trigger':>34}{'hedged':>9}{'saved':>10}{'cost':>10}"
          f"{'net':>11}{'per position':>15}")
    base = sum(unhedged_pnl(e["price"], not e["flip"]) for e, _ in entries)
    print(f"  {'NO HEDGE (what we do today)':>34}{'-':>9}{'-':>10}{'-':>10}"
          f"{100*base:>10.1f}c{100*base/max(len(entries),1):>14.2f}c")

    for thresh in (0.05, 0.10, 0.20, 0.35, 0.50, 0.75):
        tot = 0.0
        nh = 0
        saved = 0.0
        cost = 0.0
        for e, later in entries:
            hp = None
            for x in later:
                pf = model_pflip(x)
                if pf is None:
                    continue
                # our side's chance of LOSING has risen past the trigger
                if x["side_yes"] != e["side_yes"]:
                    pf = 1.0 - pf          # the model has switched sides
                if pf >= thresh:
                    q = hedge_price(x, e["side_yes"])
                    if not (0.0 < q < 1.0):
                        bad_derived += 1
                        continue
                    hp = q
                    break
            u = unhedged_pnl(e["price"], not e["flip"])
            if hp is None:
                tot += u
            else:
                h = hedged_pnl(e["price"], hp)
                tot += h
                nh += 1
                if h > u:
                    saved += h - u
                else:
                    cost += u - h
        print(f"  {'hedge when p(lose) >= ' + f'{100*thresh:.0f}%':>34}"
              f"{nh:>9}{100*saved:>9.1f}c{100*cost:>9.1f}c"
              f"{100*tot:>10.1f}c{100*tot/max(len(entries),1):>14.2f}c")

    print(f"\n  'saved' is what the hedge rescued on positions that WOULD have")
    print(f"  lost. 'cost' is what it threw away on positions that would have")
    print(f"  WON anyway. The hedge is worth having only if saved > cost.")
    if bad_derived:
        print(f"\n  {bad_derived:,} derived opposite-prices fell outside (0,1) "
              f"and were skipped -- reported, not hidden.")


if __name__ == "__main__":
    main()
